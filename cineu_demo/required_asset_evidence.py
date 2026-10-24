from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .ledger import utc_now_iso
from .paths import HILLSIDE_PROJECT_ROOT


REPORT_SCHEMA_VERSION = "cineu.required_asset_evidence_report.v1"
DEFAULT_TARGET_PROJECT_ROOT = HILLSIDE_PROJECT_ROOT
MAX_EVIDENCE_ASSETS_PER_REQUIREMENT = 16
MIXAMO_MOTION_URL = "https://www.mixamo.com/#/?type=Motion%2CMotionPack"


@dataclass(frozen=True)
class RequiredAsset:
    requirement_id: str
    name: str
    category: str
    listing_id: str
    source: str
    asset_tokens: tuple[str, ...]
    next_action: str = "add_to_hillside_project"


REQUIRED_ASSETS: tuple[RequiredAsset, ...] = (
    RequiredAsset(
        requirement_id="art_fashion_automotive_galleries",
        name="Art / Fashion / Automotive Galleries",
        category="environment",
        listing_id="a85dcedb-f434-4ed3-bc25-6a9b302e6d1c",
        source="fab",
        asset_tokens=("artfashionautomotivegalleries", "automotivegallery", "fashiongallery", "artgallery", "carshowcase"),
    ),
    RequiredAsset(
        requirement_id="archinteriors_museum_scene",
        name="Archinteriors Museum Gallery",
        category="environment",
        listing_id="4d4f9b35-8df2-4590-8df5-fc265fb4a583",
        source="fab",
        asset_tokens=("aiue5vol1001", "aiuevol1001", "archinteriorsmuseum", "museumgallery"),
    ),
    RequiredAsset(
        requirement_id="warehouse_pack",
        name="Warehouse Pack",
        category="environment",
        listing_id="ef0311b7-fd62-414a-b2c3-66ba95d8a21d",
        source="fab",
        asset_tokens=("warehouse", "warehousepack", "warehouseenvironment", "industrialwarehousepack"),
    ),
    RequiredAsset(
        requirement_id="car_dealer",
        name="Car Dealer",
        category="environment",
        listing_id="06ac3ca0-175f-4331-b232-62ad1011b24e",
        source="fab",
        asset_tokens=("cardealer", "carshowcase", "cardisplay", "carshowroom", "dealershipshowroom", "automotive"),
    ),
    RequiredAsset(
        requirement_id="downtown_west",
        name="Downtown West",
        category="environment",
        listing_id="0faf8b5d-7a5f-4fee-a297-7a8efaba8896",
        source="fab",
        asset_tokens=("downtownwest", "purepolygonsdowntown", "downtowncitypack"),
    ),
    RequiredAsset(
        requirement_id="citypark_lite",
        name="City Park Environment Collection LITE",
        category="environment",
        listing_id="e08aa2af-ade4-4b57-9a5d-06ffd6fe0916",
        source="fab",
        asset_tokens=("citypark", "cityparkenvironmentcollectionlite"),
    ),
    RequiredAsset(
        requirement_id="city_sample_crowds",
        name="City Sample Crowds",
        category="pedestrian",
        listing_id="903037e9-e1ac-4f41-96e8-1683c6fa7ad4",
        source="fab",
        asset_tokens=("citysamplecrowds", "masscrowd", "crowdcharacter"),
    ),
    RequiredAsset(
        requirement_id="scanned_3d_people",
        name="Scanned 3D People / Renderpeople",
        category="pedestrian",
        listing_id="2e872a96-686e-4955-8256-82fa19904f92",
        source="fab",
        asset_tokens=("renderpeople", "scanned3dpeople", "scannedpeople"),
    ),
    RequiredAsset(
        requirement_id="metahuman_epic_games",
        name="Epic Games MetaHumans",
        category="pedestrian",
        listing_id="epic-games-metahuman",
        source="fab",
        asset_tokens=("metahumans", "metahumankellan", "mmednrwbody"),
    ),
    RequiredAsset(
        requirement_id="mixamo_city_pedestrian_actions",
        name="Mixamo City Pedestrian Actions",
        category="animation",
        listing_id="mixamo",
        source="mixamo",
        asset_tokens=("mixamo",),
        next_action="download_city_pedestrian_actions",
    ),
)


def build_required_asset_evidence_report(
    local_asset_index: dict[str, Any],
    *,
    target_project_root: str | Path | None = None,
) -> dict[str, Any]:
    """Report whether the user-required Fab/MetaHuman/Mixamo assets are evidenced locally."""
    target_root = Path(target_project_root) if target_project_root else DEFAULT_TARGET_PROJECT_ROOT
    fab_listings = _fab_listings_by_id(local_asset_index)
    orphan_downloads = list((local_asset_index.get("fab_library") or {}).get("orphan_downloads") or [])
    assets = list(local_asset_index.get("assets") or [])

    requirements = [
        _build_requirement_report(requirement, fab_listings, orphan_downloads, assets, target_root)
        for requirement in REQUIRED_ASSETS
    ]
    available_count = sum(1 for item in requirements if item["status"] == "available")
    missing_count = len(requirements) - available_count
    required_actions = [item["user_action"] for item in requirements if item["user_action"]["required"]]

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "target_project_root": str(target_root),
        "source_schema_version": local_asset_index.get("schema_version"),
        "passed": missing_count == 0,
        "summary": {
            "required_count": len(requirements),
            "available": available_count,
            "missing": missing_count,
        },
        "requirements": requirements,
        "user_action_plan": {
            "schema_version": "cineu.required_asset_user_action_plan.v1",
            "action_count": len(required_actions),
            "blocked_full_quality": bool(required_actions),
            "actions": required_actions,
        },
    }


def build_required_asset_user_actions_markdown(report: dict[str, Any]) -> str:
    """Render the current required-asset report into a user-facing action list."""
    summary = report.get("summary") or {}
    action_plan = report.get("user_action_plan") or {}
    actions = list(action_plan.get("actions") or [])
    lines = [
        "# CineU Required Asset User Actions",
        "",
        f"Generated: {report.get('generated_at', '')}",
        f"Target project: `{report.get('target_project_root', '')}`",
        "",
        "## Current Local Evidence",
        "",
        f"- Required groups checked: {int(summary.get('required_count') or 0)}",
        f"- Available and target-ready: {int(summary.get('available') or 0)}",
        f"- Still requiring user action: {len(actions)}",
        "",
        "## Actions Needed",
        "",
    ]
    if not actions:
        lines.append("No manual asset action is currently required.")
    else:
        for index, action in enumerate(actions, start=1):
            name = action.get("name") or action.get("requirement_id") or f"Action {index}"
            lines.extend(
                [
                    f"{index}. {name}",
                    f"   - Kind: `{action.get('kind', '')}`",
                    f"   - Reason: `{action.get('reason', '')}`",
                    f"   - URL: {action.get('url', '')}",
                ]
            )
            source_path = action.get("source_path")
            if source_path:
                lines.append(f"   - Source path: `{source_path}`")
            diagnostics = action.get("diagnostics") or {}
            next_launcher_action = diagnostics.get("required_next_launcher_action")
            if next_launcher_action:
                lines.append(f"   - Launcher action: {next_launcher_action}")
            orphan_candidates = diagnostics.get("orphan_vault_cache_candidates") or []
            if orphan_candidates:
                lines.append("   - Orphan VaultCache candidates:")
                for candidate in orphan_candidates[:5]:
                    lines.append(
                        "     - "
                        f"{candidate.get('name', '')} "
                        f"({candidate.get('state', '')}, {candidate.get('cache_size', 0)} bytes): "
                        f"`{candidate.get('path', '')}`"
                    )
    lines.extend(
        [
            "",
            "## After Import",
            "",
            "Refresh the local asset index after importing assets, then rerun the evidence report:",
            "",
            "```powershell",
            'cineu-demo rebuild-asset-index --source-dir "<project>/Content" --project-root "<project>"',
            'cineu-demo required-asset-evidence --asset-index workspace/asset_index/local_asset_index.json',
            "```",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _build_requirement_report(
    requirement: RequiredAsset,
    fab_listings: dict[str, dict[str, Any]],
    orphan_downloads: list[dict[str, Any]],
    assets: list[dict[str, Any]],
    target_root: Path,
) -> dict[str, Any]:
    listing = fab_listings.get(requirement.listing_id.lower())
    matched_assets, matched_asset_count, target_project_ready = _matching_assets(requirement, assets, target_root)
    status = "available" if _listing_is_available(listing) or matched_asset_count else "missing"
    target_action = ""
    if status == "available" and not target_project_ready:
        target_action = "migrate_or_add_to_target_project"
    user_action = _requirement_user_action(
        requirement,
        listing=listing,
        status=status,
        target_project_ready=target_project_ready,
        target_root=target_root,
        matched_assets=matched_assets,
        matched_asset_count=matched_asset_count,
        orphan_downloads=orphan_downloads,
    )

    return {
        "requirement_id": requirement.requirement_id,
        "name": requirement.name,
        "category": requirement.category,
        "source": requirement.source,
        "listing_id": requirement.listing_id,
        "status": status,
        "next_action": "" if status == "available" else requirement.next_action,
        "target_project_ready": target_project_ready,
        "target_action": target_action,
        "target_project_root": str(target_root),
        "user_action": user_action,
        "evidence": {
            "fab_listing": listing,
            "asset_match_count": matched_asset_count,
            "coverage": _requirement_evidence_coverage(requirement, matched_assets),
            "assets": matched_assets,
        },
    }


def _requirement_user_action(
    requirement: RequiredAsset,
    *,
    listing: dict[str, Any] | None,
    status: str,
    target_project_ready: bool,
    target_root: Path,
    matched_assets: list[dict[str, Any]],
    matched_asset_count: int,
    orphan_downloads: list[dict[str, Any]],
) -> dict[str, Any]:
    base = {
        "required": False,
        "kind": "none",
        "requirement_id": requirement.requirement_id,
        "name": requirement.name,
        "category": requirement.category,
        "source": requirement.source,
        "listing_id": requirement.listing_id,
        "url": _requirement_url(requirement),
        "target_project_root": str(target_root),
        "reason": "",
    }
    if status == "available" and target_project_ready:
        return base

    action = {**base, "required": True}
    if status == "available":
        source_path = _listing_download_path(listing) or _first_asset_source_path(matched_assets)
        if listing and _listing_is_available(listing):
            action.update(
                {
                    "kind": "import_downloaded_fab_pack_to_target_project",
                    "reason": "downloaded_fab_pack_not_ready_in_target_project",
                    "source_path": source_path,
                }
            )
        else:
            action.update(
                {
                    "kind": "migrate_or_link_existing_assets_to_target_project",
                    "reason": "asset_evidence_exists_outside_target_project",
                    "source_path": source_path,
                }
            )
        return action

    if requirement.source == "mixamo":
        action.update(
            {
                "kind": "download_mixamo_city_pedestrian_actions",
                "reason": "mixamo_city_pedestrian_actions_missing_from_local_project",
            }
        )
        return action

    if listing is not None:
        action.update(
            {
                "kind": "download_fab_listing_to_target_project",
                "reason": "fab_listing_acquired_but_not_downloaded_or_local_path_missing",
                "source_path": _listing_download_path(listing),
                "diagnostics": _missing_fab_diagnostics(requirement, listing, matched_asset_count, orphan_downloads),
            }
        )
        return action

    action.update(
        {
            "kind": "acquire_or_add_fab_listing_to_library",
            "reason": "fab_listing_missing_from_local_fab_library_evidence",
            "diagnostics": _missing_fab_diagnostics(requirement, listing, matched_asset_count, orphan_downloads),
        }
    )
    return action


def _missing_fab_diagnostics(
    requirement: RequiredAsset,
    listing: dict[str, Any] | None,
    matched_asset_count: int,
    orphan_downloads: list[dict[str, Any]],
) -> dict[str, Any]:
    download_path = _listing_download_path(listing)
    orphan_candidates = _orphan_download_candidates(requirement, orphan_downloads)
    return {
        "fab_listing_found": listing is not None,
        "fab_download_found": bool(download_path and Path(download_path).exists()),
        "local_asset_match_count": int(matched_asset_count),
        "searched_asset_tokens": list(requirement.asset_tokens),
        "orphan_vault_cache_candidate_count": len(orphan_candidates),
        "orphan_vault_cache_candidates": orphan_candidates[:8],
        "checked_sources": [
            "local_asset_index.fab_library.listings",
            "local_asset_index.fab_library.orphan_downloads",
            "local_asset_index.assets",
        ],
        "required_next_launcher_action": (
            f"Add the Fab listing to your Library and download/add it to the target Unreal project: "
            f"{_requirement_url(requirement)}"
        ),
    }


def _orphan_download_candidates(requirement: RequiredAsset, orphan_downloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked: list[tuple[int, str, dict[str, Any]]] = []
    for item in orphan_downloads:
        text = _normalize(
            " ".join(str(item.get(key) or "") for key in ["name", "path", "state"])
        )
        token_hit = 1 if any(token in text for token in requirement.asset_tokens) else 0
        ranked.append(
            (
                token_hit,
                str(item.get("name") or item.get("path") or ""),
                {
                    "name": item.get("name"),
                    "path": item.get("path"),
                    "state": item.get("state"),
                    "cache_size": item.get("cache_size"),
                    "token_match": bool(token_hit),
                },
            )
        )
    ranked.sort(key=lambda item: (-item[0], item[1].lower()))
    return [item[2] for item in ranked]


def _requirement_url(requirement: RequiredAsset) -> str:
    if requirement.source == "mixamo":
        return MIXAMO_MOTION_URL
    if requirement.source == "fab":
        return f"https://www.fab.com/listings/{requirement.listing_id}"
    return ""


def _listing_download_path(listing: dict[str, Any] | None) -> str:
    if not listing:
        return ""
    return str(listing.get("download_path") or listing.get("local_path") or "")


def _first_asset_source_path(matched_assets: list[dict[str, Any]]) -> str:
    for asset in matched_assets:
        source_path = asset.get("source_path")
        if source_path:
            return str(source_path)
    return ""


def _fab_listings_by_id(local_asset_index: dict[str, Any]) -> dict[str, dict[str, Any]]:
    listings = (local_asset_index.get("fab_library") or {}).get("listings") or []
    return {
        str(listing.get("listing_id", "")).lower(): listing
        for listing in listings
        if listing.get("listing_id")
    }


def _listing_is_available(listing: dict[str, Any] | None) -> bool:
    if not listing:
        return False
    status = str(listing.get("download_status") or listing.get("status") or "").lower()
    if status not in {"downloaded", "available", "installed", "local"}:
        return False
    download_path = listing.get("download_path") or listing.get("local_path")
    return not download_path or Path(str(download_path)).exists()


def _matching_assets(requirement: RequiredAsset, assets: list[dict[str, Any]], target_root: Path) -> tuple[list[dict[str, Any]], int, bool]:
    matches = []
    target_project_ready = False
    for asset in assets:
        searchable = _asset_search_text(asset)
        if _asset_satisfies_requirement(requirement, searchable):
            matches.append(_asset_evidence(asset))
            target_project_ready = target_project_ready or _asset_is_inside_target(asset, target_root)
    matches.sort(key=_evidence_sort_key)
    return matches[:MAX_EVIDENCE_ASSETS_PER_REQUIREMENT], len(matches), target_project_ready


def _evidence_sort_key(asset: dict[str, Any]) -> tuple[int, str]:
    type_rank = {
        "level": 0,
        "skeletal_mesh": 1,
        "animation": 2,
        "static_mesh": 3,
        "material": 4,
    }
    return (type_rank.get(str(asset.get("type") or ""), 9), str(asset.get("ue_path") or asset.get("source_path") or ""))


def _asset_search_text(asset: dict[str, Any]) -> str:
    fields = [
        asset.get("asset_id"),
        asset.get("name"),
        asset.get("type"),
        asset.get("ue_path"),
        _content_relative_path(asset.get("source_path")),
        " ".join(str(tag) for tag in asset.get("semantic_tags") or []),
        " ".join(str(tag) for tag in asset.get("functional_tags") or []),
    ]
    return _normalize(" ".join(str(field) for field in fields if field))


def _asset_satisfies_requirement(requirement: RequiredAsset, searchable: str) -> bool:
    if requirement.requirement_id == "city_sample_crowds" and "citysamplevehicles" in searchable:
        return False
    if requirement.requirement_id == "mixamo_city_pedestrian_actions":
        if any(token in searchable for token in requirement.asset_tokens):
            return True
        return "citysamplecrowdcharacteranimsloco" in searchable and "walk" in searchable
    return any(token in searchable for token in requirement.asset_tokens)


def _requirement_evidence_coverage(requirement: RequiredAsset, matched_assets: list[dict[str, Any]]) -> str:
    if not matched_assets:
        return "missing"
    if requirement.requirement_id != "mixamo_city_pedestrian_actions":
        return "direct"
    for asset in matched_assets:
        text = _normalize(" ".join(str(asset.get(key) or "") for key in ["asset_id", "name", "ue_path", "source_path"]))
        if "mixamo" in text:
            return "direct_mixamo"
    return "covered_by_city_sample_crowd_locomotion"


def _asset_evidence(asset: dict[str, Any]) -> dict[str, Any]:
    return {
        "asset_id": asset.get("asset_id"),
        "name": asset.get("name"),
        "type": asset.get("type"),
        "ue_path": asset.get("ue_path"),
        "source_type": asset.get("source_type"),
        "source_path": asset.get("source_path"),
    }


def _asset_is_inside_target(asset: dict[str, Any], target_root: Path) -> bool:
    source_path = asset.get("source_path")
    if not source_path:
        return False
    try:
        asset_path = Path(str(source_path)).resolve(strict=False)
        root_path = target_root.resolve(strict=False)
        if asset_path == root_path or root_path in asset_path.parents:
            return True
        mount_source, mount_name = _content_mount_source(source_path)
        if mount_source is None or mount_name is None:
            return False
        target_mount = root_path / "Content" / mount_name
        return target_mount.exists() and _same_path(target_mount, mount_source)
    except OSError:
        return False


def _normalize(text: str) -> str:
    return "".join(ch.lower() for ch in text if ch.isalnum())


def _content_relative_path(source_path: Any) -> str:
    if not source_path:
        return ""
    normalized = str(source_path).replace("/", "\\")
    marker = "\\Content\\"
    if marker in normalized:
        return normalized.split(marker, 1)[1]
    return Path(normalized).name


def _content_mount_source(source_path: Any) -> tuple[Path | None, str | None]:
    if not source_path:
        return None, None
    normalized = str(source_path).replace("/", "\\")
    marker = "\\Content\\"
    if marker not in normalized:
        return None, None
    content_root, relative = normalized.split(marker, 1)
    parts = [part for part in relative.split("\\") if part]
    if not parts:
        return None, None
    return Path(content_root) / "Content" / parts[0], parts[0]


def _same_path(left: Path, right: Path) -> bool:
    try:
        return _path_key(left.resolve(strict=False)) == _path_key(right.resolve(strict=False))
    except OSError:
        return False


def _path_key(path: Path) -> str:
    return str(path).replace("/", "\\").rstrip("\\").lower()
