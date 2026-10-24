from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable
import os
import re
import sqlite3

from .asset_store import AssetStore
from .ledger import atomic_write_json, utc_now_iso
from .schemas import AssetMetadata


def build_local_asset_index(
    asset_store: AssetStore,
    *,
    project_roots: Iterable[Path] | None = None,
    max_candidates: int = 80,
) -> dict[str, Any]:
    """Build a persistent asset-first snapshot from the assets AssetStore can already discover."""
    project_hints = [Path(root).resolve() for root in project_roots or []]
    assets = [asset for asset in asset_store.list_assets() if _is_real_asset(asset)]
    assets.sort(key=lambda item: (item.source_type, item.ue_path, item.asset_id))

    grouped: dict[str, list[AssetMetadata]] = defaultdict(list)
    for asset in assets:
        grouped[_project_key(asset, project_hints)].append(asset)

    projects = [_project_record(key, items, project_hints) for key, items in sorted(grouped.items())]
    counts_by_type = Counter(asset.type for asset in assets)
    counts_by_source_type = Counter(asset.source_type for asset in assets)
    environment_candidates = _candidate_records([asset for asset in assets if _is_environment_candidate(asset)], max_candidates)
    character_candidates = _candidate_records([asset for asset in assets if asset.type == "skeletal_mesh"], max_candidates)
    animation_candidates = _candidate_records([asset for asset in assets if asset.type == "animation"], max_candidates)
    sequence_candidates = _candidate_records([asset for asset in assets if asset.type == "level_sequence"], max_candidates)
    fab_library = _fab_library_evidence(asset_store)

    return {
        "schema_version": "cineu.local_asset_index.v1",
        "generated_at": utc_now_iso(),
        "asset_first_ready": bool(environment_candidates) and (bool(character_candidates) or bool(animation_candidates)),
        "asset_count": len(assets),
        "counts_by_type": dict(sorted(counts_by_type.items())),
        "counts_by_source_type": dict(sorted(counts_by_source_type.items())),
        "projects": projects,
        "assets": [_asset_record(asset) for asset in assets],
        "environment_candidates": environment_candidates,
        "character_candidates": character_candidates,
        "animation_candidates": animation_candidates,
        "sequence_candidates": sequence_candidates,
        "fab_library": fab_library,
    }


def build_run_asset_index_snapshot(
    asset_store: AssetStore,
    *,
    project_roots: Iterable[Path] | None = None,
    max_candidates: int = 80,
) -> dict[str, Any]:
    """Build a compact per-run asset-first snapshot for the planning ledger."""
    index = build_local_asset_index(asset_store, project_roots=project_roots, max_candidates=max_candidates)
    return {
        "schema_version": "cineu.run_asset_index_snapshot.v1",
        "source_schema_version": index["schema_version"],
        "generated_at": index["generated_at"],
        "asset_first_ready": index["asset_first_ready"],
        "asset_count": index["asset_count"],
        "counts_by_type": index["counts_by_type"],
        "counts_by_source_type": index["counts_by_source_type"],
        "projects": index["projects"],
        "environment_candidates": index["environment_candidates"],
        "character_candidates": index["character_candidates"],
        "animation_candidates": index["animation_candidates"],
        "sequence_candidates": index["sequence_candidates"],
        "fab_library": index.get("fab_library", {}),
    }


def asset_first_preflight_report(snapshot: dict[str, Any], target_environment: str) -> dict[str, Any]:
    environment = target_environment.lower().strip()
    candidates = snapshot.get("environment_candidates", [])
    matched = [candidate for candidate in candidates if _candidate_matches_environment(candidate, environment)]
    checks = [
        {
            "name": "asset_index_snapshot_ready",
            "passed": bool(snapshot.get("asset_first_ready")),
            "actual": bool(snapshot.get("asset_first_ready")),
        },
        {
            "name": "target_environment_candidate_available",
            "passed": bool(matched),
            "expected": environment,
            "actual": [candidate.get("ue_path") for candidate in matched[:8]],
        },
    ]
    return {
        "schema_version": "cineu.asset_first_preflight_report.v1",
        "target_environment": environment,
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
        "matched_environment_candidates": matched[:12],
        "diagnostics": {
            "asset_count": snapshot.get("asset_count", 0),
            "environment_candidate_count": len(candidates),
        },
    }


def write_local_asset_index(index: dict[str, Any], out_dir: Path) -> dict[str, str]:
    out_dir = Path(out_dir)
    index_file = out_dir / "local_asset_index.json"
    summary_file = out_dir / "local_asset_index_summary.json"
    summary = {
        "schema_version": "cineu.local_asset_index_summary.v1",
        "generated_at": index.get("generated_at"),
        "asset_first_ready": bool(index.get("asset_first_ready")),
        "project_count": len(index.get("projects", [])),
        "asset_count": int(index.get("asset_count", 0)),
        "counts_by_type": index.get("counts_by_type", {}),
        "counts_by_source_type": index.get("counts_by_source_type", {}),
        "environment_candidate_count": len(index.get("environment_candidates", [])),
        "character_candidate_count": len(index.get("character_candidates", [])),
        "animation_candidate_count": len(index.get("animation_candidates", [])),
        "sequence_candidate_count": len(index.get("sequence_candidates", [])),
        "fab_listing_count": int((index.get("fab_library") or {}).get("listing_count", 0)),
        "fab_download_count": int((index.get("fab_library") or {}).get("download_count", 0)),
        "fab_orphan_download_count": int((index.get("fab_library") or {}).get("orphan_download_count", 0)),
    }
    atomic_write_json(index_file, index)
    atomic_write_json(summary_file, summary)
    return {"index_file": str(index_file), "summary_file": str(summary_file)}


def _candidate_matches_environment(candidate: dict[str, Any], environment: str) -> bool:
    tokens = set(_index_tokens(environment))
    tokens.update(_environment_aliases(environment))
    candidate_tokens: set[str] = set()
    for value in [
        candidate.get("name", ""),
        candidate.get("ue_path", ""),
        *candidate.get("semantic_tags", []),
        *candidate.get("functional_tags", []),
    ]:
        candidate_tokens.update(_index_tokens(str(value)))
    return bool(tokens & candidate_tokens)


def _environment_aliases(environment: str) -> set[str]:
    aliases: dict[str, set[str]] = {
        "park": {"citypark", "park"},
        "gallery": {"gallery", "museum"},
        "river": {"river", "water"},
        "desert": {"desert", "sand"},
        "large_building": {"large", "building"},
        "city_rooftop": {"city", "rooftop"},
        "hillside": {"hillside", "hill", "lv", "exterior", "interior"},
    }
    return aliases.get(environment, set())


def _index_tokens(text: str) -> list[str]:
    normalized = re.sub(r"[_\\/\-]+", " ", text)
    normalized = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", normalized)
    return [token.lower() for token in re.findall(r"[a-zA-Z0-9\u4e00-\u9fff]+", normalized)]


def _is_real_asset(asset: AssetMetadata) -> bool:
    source_type = str(asset.source_type or "").lower()
    if source_type in {"metadata_placeholder", "generated_proxy"}:
        return False
    if asset.source_path:
        return Path(asset.source_path).exists()
    return bool(asset.ue_path)


def _is_environment_candidate(asset: AssetMetadata) -> bool:
    if asset.type == "level":
        return _is_environment_level(asset)
    if asset.type != "static_mesh":
        return False
    tags = {tag.lower() for tag in [*asset.semantic_tags, *asset.functional_tags]}
    return bool(tags & {"environment", "park", "hillside", "landscape", "tree", "vegetation", "foliage", "city"})


def _is_environment_level(asset: AssetMetadata) -> bool:
    tags = {tag.lower() for tag in [*asset.semantic_tags, *asset.functional_tags]}
    text = " ".join([asset.ue_path, asset.name, *tags]).lower()
    non_environment_pack_tags = {
        "animal",
        "animals",
        "character",
        "creature",
        "humanoid",
        "quadruped",
        "zebra",
        "lion",
        "lioness",
        "elephant",
        "crocodile",
        "hippopotamus",
        "rhinoceros",
        "dragon",
        "griffon",
        "centaur",
        "barghest",
        "zombie",
        "animation",
    }
    environment_level_tags = {
        "environment",
        "park",
        "city",
        "landscape",
        "hillside",
        "hill",
        "exterior",
        "interior",
        "gallery",
        "museum",
        "river",
        "water",
        "desert",
        "building",
        "rooftop",
        "persistent",
        "main",
    }
    if tags & environment_level_tags:
        return True
    if tags & non_environment_pack_tags:
        return False
    return any(marker in text for marker in ["/maps/lv_", "/maps/persistent", "/maps/main", "/maps/showcase"])


def _candidate_records(assets: list[AssetMetadata], limit: int) -> list[dict[str, Any]]:
    ranked = sorted(assets, key=_candidate_rank, reverse=True)
    return [_asset_record(asset) for asset in ranked[:limit]]


def _candidate_rank(asset: AssetMetadata) -> tuple[int, int, int, str]:
    tags = {tag.lower() for tag in [*asset.semantic_tags, *asset.functional_tags]}
    project_bonus = 1 if asset.source_type == "ue_project_content" else 0
    level_bonus = 1 if asset.type == "level" else 0
    primary_level_bonus = _primary_level_priority(asset)
    semantic_bonus = len(tags & {"showcase", "environment", "park", "hillside", "city", "character", "animation", "walk"})
    return project_bonus, level_bonus, primary_level_bonus, semantic_bonus, asset.ue_path


def _primary_level_priority(asset: AssetMetadata) -> int:
    if asset.type != "level":
        return 0
    text = asset.ue_path.lower()
    if any(token in text for token in ["lv_exterior", "lv_interior", "showcase", "overview", "persistent", "main"]):
        return 3
    if any(token in text for token in ["/maps/setdress/", "/maps/qc/", "/maps/sa/"]):
        return -1
    return 1


def _asset_record(asset: AssetMetadata) -> dict[str, Any]:
    return {
        "asset_id": asset.asset_id,
        "name": asset.name,
        "type": asset.type,
        "ue_path": asset.ue_path,
        "source_type": asset.source_type,
        "source_path": asset.source_path,
        "import_required": asset.import_required,
        "semantic_tags": asset.semantic_tags,
        "functional_tags": asset.functional_tags,
        "provenance": {
            key: asset.provenance[key]
            for key in ["source_root", "ue_content_root", "bundle_root", "bundle_package_path", "catalog", "discovered_by"]
            if key in asset.provenance
        },
    }


def _fab_library_evidence(asset_store: AssetStore) -> dict[str, Any]:
    db_paths = _fab_library_db_paths(asset_store)
    listings_by_id: dict[str, dict[str, Any]] = {}
    download_count = 0
    for db_path in db_paths:
        try:
            payload = _read_fab_library_db(db_path)
        except (OSError, sqlite3.Error):
            continue
        download_count += len(payload["downloads"])
        for listing in payload["listings"]:
            current = listings_by_id.setdefault(
                listing["listing_id"],
                {
                    "listing_id": listing["listing_id"],
                    "listing_uid": listing.get("listing_uid", ""),
                    "listing_url": listing.get("listing_url", ""),
                    "title": listing.get("title", ""),
                    "description": listing.get("description", ""),
                    "thumbnail": listing.get("thumbnail", ""),
                    "namespace": listing.get("namespace", ""),
                    "download_status": "not_downloaded",
                    "download_path": "",
                    "download_format": "",
                    "cache_size": 0,
                    "source_db": str(db_path),
                },
            )
            for key, value in listing.items():
                if value and not current.get(key):
                    current[key] = value
        for download in payload["downloads"]:
            listing_id = download["listing_id"]
            current = listings_by_id.setdefault(
                listing_id,
                {
                    "listing_id": listing_id,
                    "listing_uid": download.get("listing_uid", ""),
                    "listing_url": "",
                    "title": "",
                    "description": "",
                    "thumbnail": "",
                    "namespace": "",
                    "download_status": "not_downloaded",
                    "download_path": "",
                    "download_format": "",
                    "cache_size": 0,
                    "source_db": str(db_path),
                },
            )
            download_path = str(download.get("path") or "")
            current["download_path"] = download_path
            current["download_format"] = str(download.get("format") or "")
            current["cache_size"] = int(download.get("cache_size") or 0)
            current["download_status"] = "downloaded" if download_path and Path(download_path).exists() else "download_record_path_missing"
    listings = sorted(listings_by_id.values(), key=lambda item: (item.get("title", ""), item["listing_id"]))
    orphan_downloads = _orphan_vault_cache_downloads(asset_store, listings)
    return {
        "schema_version": "cineu.fab_library_evidence.v1",
        "db_paths": [str(path) for path in db_paths],
        "listing_count": len(listings),
        "download_count": download_count,
        "listings": listings,
        "orphan_download_count": len(orphan_downloads),
        "orphan_downloads": orphan_downloads,
    }


def _orphan_vault_cache_downloads(asset_store: AssetStore, listings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    listed_paths = {
        _path_key(Path(str(listing.get("download_path"))))
        for listing in listings
        if listing.get("download_path")
    }
    downloads: list[dict[str, Any]] = []
    for root in _fab_vault_cache_roots(asset_store):
        try:
            children = list(root.iterdir())
        except OSError:
            continue
        for child in children:
            if not child.is_dir() or child.name.lower() == "fablibrary":
                continue
            key = _path_key(child)
            if key in listed_paths:
                continue
            if not ((child / "data").exists() or (child / "stage").exists()):
                continue
            downloads.append(
                {
                    "name": child.name,
                    "path": str(child),
                    "state": _vault_cache_state(child),
                    "cache_size": _directory_size(child),
                }
            )
    return sorted(downloads, key=lambda item: item["name"].lower())


def _fab_vault_cache_roots(asset_store: AssetStore) -> list[Path]:
    candidates: list[Path] = []
    extra = os.environ.get("CINEU_EPIC_VAULT_DIRS", "")
    candidates.extend(Path(item.strip()) for item in extra.split(";") if item.strip())
    if getattr(asset_store, "include_global_libraries", False):
        program_data = Path(os.environ.get("ProgramData", r"C:\ProgramData"))
        public_home = Path(os.environ.get("PUBLIC", r"C:\Users\Public"))
        user_home = Path.home()
        candidates.extend(
            [
                program_data / "Epic" / "EpicGamesLauncher" / "VaultCache",
                program_data / "Epic" / "UnrealEngineLauncher" / "VaultCache",
                public_home / "Documents" / "Epic Games" / "VaultCache",
                user_home / "Documents" / "Epic Games" / "VaultCache",
            ]
        )
    for source_dir in getattr(asset_store, "source_dirs", []):
        path = Path(source_dir)
        for parent in [path, *path.parents]:
            candidates.append(parent / "FabCache" / "VaultCache")
            if parent.name.lower() == "vaultcache":
                candidates.append(parent)
                break

    seen: set[str] = set()
    roots: list[Path] = []
    for candidate in candidates:
        if not candidate.exists() or not candidate.is_dir():
            continue
        key = _path_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        roots.append(candidate)
    return roots


def _vault_cache_state(path: Path) -> str:
    if (path / "data" / "Content").exists():
        return "content"
    if (path / "data").exists() and (path / "stage").exists():
        return "staged"
    if (path / "stage").exists():
        return "staged"
    return "unknown"


def _directory_size(path: Path) -> int:
    total = 0
    try:
        files = path.rglob("*")
        for item in files:
            if item.is_file():
                try:
                    total += item.stat().st_size
                except OSError:
                    continue
    except OSError:
        return total
    return total


def _path_key(path: Path) -> str:
    return str(path.resolve(strict=False)).replace("/", "\\").rstrip("\\").lower()


def _fab_library_db_paths(asset_store: AssetStore) -> list[Path]:
    candidates: list[Path] = []
    extra = os.environ.get("CINEU_FAB_LIBRARY_DBS", "")
    candidates.extend(Path(item.strip()) for item in extra.split(";") if item.strip())
    for source_dir in getattr(asset_store, "source_dirs", []):
        path = Path(source_dir)
        for parent in [path, *path.parents]:
            candidates.append(parent / "listings_v1.db")
            if parent.name.lower() == "fablibrary":
                break
    if getattr(asset_store, "include_global_libraries", False):
        program_data = Path(os.environ.get("ProgramData", r"C:\ProgramData"))
        candidates.append(program_data / "Epic" / "EpicGamesLauncher" / "VaultCache" / "FabLibrary" / "listings_v1.db")
        candidates.append(Path.home() / "Documents" / "FabLibrary" / "listings_v1.db")

    seen: set[str] = set()
    paths: list[Path] = []
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            resolved = candidate
        key = str(resolved).lower()
        if key in seen or not candidate.exists():
            continue
        seen.add(key)
        paths.append(candidate)
    return paths


def _read_fab_library_db(db_path: Path) -> dict[str, list[dict[str, Any]]]:
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    try:
        listings: list[dict[str, Any]] = []
        downloads: list[dict[str, Any]] = []
        if _sqlite_table_exists(connection, "catalog"):
            for row in connection.execute("select listing_uid, title, description, thumbnail, namespace from catalog"):
                listings.append(_fab_listing_record(row, db_path))
        if _sqlite_table_exists(connection, "local_listing"):
            for row in connection.execute("select uid as listing_uid, title, description, thumbnail, '' as namespace from local_listing"):
                listings.append(_fab_listing_record(row, db_path))
        if _sqlite_table_exists(connection, "download_meta"):
            for row in connection.execute("select listing_uid, format, path, cache_size from download_meta"):
                listing_uid = str(row["listing_uid"] or "")
                downloads.append(
                    {
                        "listing_uid": listing_uid,
                        "listing_id": _fab_listing_id(listing_uid),
                        "format": str(row["format"] or ""),
                        "path": str(row["path"] or ""),
                        "cache_size": int(row["cache_size"] or 0),
                        "source_db": str(db_path),
                    }
                )
        return {"listings": listings, "downloads": downloads}
    finally:
        connection.close()


def _sqlite_table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute("select 1 from sqlite_master where type='table' and name=? limit 1", (table_name,)).fetchone()
    return row is not None


def _fab_listing_record(row: sqlite3.Row, db_path: Path) -> dict[str, Any]:
    listing_uid = str(row["listing_uid"] or "")
    listing_url = listing_uid if listing_uid.startswith(("http://", "https://")) else ""
    return {
        "listing_uid": listing_uid,
        "listing_id": _fab_listing_id(listing_uid),
        "listing_url": listing_url,
        "title": str(row["title"] or ""),
        "description": str(row["description"] or ""),
        "thumbnail": str(row["thumbnail"] or ""),
        "namespace": str(row["namespace"] or ""),
        "source_db": str(db_path),
    }


def _fab_listing_id(listing_uid: str) -> str:
    value = str(listing_uid or "").strip().rstrip("/")
    if "/" in value:
        value = value.rsplit("/", 1)[-1]
    return value


def _project_key(asset: AssetMetadata, project_hints: list[Path]) -> str:
    source_path = Path(asset.source_path).resolve() if asset.source_path else None
    if source_path is not None:
        for hint in project_hints:
            try:
                source_path.relative_to(hint)
            except ValueError:
                continue
            return str(hint)
        project_root = _nearest_unreal_project_root(source_path)
        if project_root is not None:
            return str(project_root)
    root = asset.provenance.get("source_root") or asset.provenance.get("ue_content_root") or asset.source_type
    return str(root)


def _nearest_unreal_project_root(path: Path) -> Path | None:
    for parent in [path.parent, *path.parents]:
        try:
            if any(parent.glob("*.uproject")):
                return parent.resolve()
        except OSError:
            return None
    return None


def _project_record(key: str, assets: list[AssetMetadata], project_hints: list[Path]) -> dict[str, Any]:
    root = Path(key)
    uproject = _find_uproject(root)
    project_name = uproject.stem if uproject is not None else root.name
    counts_by_type = Counter(asset.type for asset in assets)
    source_types = sorted({asset.source_type for asset in assets})
    return {
        "project_name": project_name,
        "project_root": str(root),
        "uproject": str(uproject) if uproject is not None else None,
        "content_root": str(root / "Content") if (root / "Content").exists() else None,
        "asset_count": len(assets),
        "counts_by_type": dict(sorted(counts_by_type.items())),
        "source_types": source_types,
        "environment_candidates": _candidate_records([asset for asset in assets if _is_environment_candidate(asset)], 12),
        "character_candidates": _candidate_records([asset for asset in assets if asset.type == "skeletal_mesh"], 12),
        "animation_candidates": _candidate_records([asset for asset in assets if asset.type == "animation"], 12),
    }


def _find_uproject(root: Path) -> Path | None:
    if root.exists():
        matches = sorted(root.glob("*.uproject"))
        if matches:
            return matches[0]
    return None
