from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .ledger import utc_now_iso


PLAN_SCHEMA_VERSION = "cineu.target_asset_link_plan.v1"
APPLY_SCHEMA_VERSION = "cineu.target_asset_link_apply.v1"


def build_target_asset_link_plan(required_asset_report: dict[str, Any], *, target_project_root: str | Path | None = None) -> dict[str, Any]:
    target_root = Path(target_project_root or required_asset_report["target_project_root"])
    links_by_target: dict[str, dict[str, Any]] = {}

    for requirement in required_asset_report.get("requirements") or []:
        if requirement.get("status") != "available" or requirement.get("target_project_ready"):
            continue
        link = _link_from_requirement(requirement, target_root)
        if not link:
            continue
        links_by_target.setdefault(_path_key(Path(link["target_dir"])), link)

    links = list(links_by_target.values())
    return {
        "schema_version": PLAN_SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "target_project_root": str(target_root),
        "summary": {
            "planned": len(links),
            "already_present": sum(1 for link in links if link["status"] == "already_present"),
            "conflict": sum(1 for link in links if link["status"] == "conflict"),
        },
        "links": links,
    }


def apply_target_asset_link_plan(plan: dict[str, Any], *, dry_run: bool = True) -> dict[str, Any]:
    results = []
    for link in plan.get("links") or []:
        results.append(_apply_link(link, dry_run=dry_run))
    return {
        "schema_version": APPLY_SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "dry_run": dry_run,
        "summary": {
            "attempted": len(results),
            "created": sum(1 for item in results if item["status"] == "created"),
            "already_present": sum(1 for item in results if item["status"] == "already_present"),
            "conflict": sum(1 for item in results if item["status"] == "conflict"),
            "failed": sum(1 for item in results if item["status"] == "failed"),
            "planned": sum(1 for item in results if item["status"] == "planned"),
        },
        "results": results,
    }


def _link_from_requirement(requirement: dict[str, Any], target_root: Path) -> dict[str, Any] | None:
    assets = ((requirement.get("evidence") or {}).get("assets")) or []
    for asset in assets:
        source_path = asset.get("source_path")
        source_dir, content_mount = _content_mount_from_source(source_path)
        if source_dir is None or content_mount is None:
            continue
        target_dir = target_root / "Content" / content_mount
        status = _planned_status(source_dir, target_dir)
        return {
            "requirement_id": requirement.get("requirement_id"),
            "content_mount": f"/Game/{content_mount}",
            "source_dir": str(source_dir),
            "target_dir": str(target_dir),
            "status": status,
            "action": "create_junction" if status == "planned" else "",
        }
    return None


def _content_mount_from_source(source_path: Any) -> tuple[Path | None, str | None]:
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
    mount = parts[0]
    return Path(content_root) / "Content" / mount, mount


def _planned_status(source_dir: Path, target_dir: Path) -> str:
    if not source_dir.exists():
        return "missing_source"
    if not target_dir.exists():
        return "planned"
    if _same_path(source_dir, target_dir):
        return "already_present"
    return "conflict"


def _apply_link(link: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    source_dir = Path(link["source_dir"])
    target_dir = Path(link["target_dir"])
    status = _planned_status(source_dir, target_dir)
    result = {**link, "status": status}
    if dry_run or status != "planned":
        return result

    target_dir.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        ["cmd.exe", "/c", "mklink", "/J", str(target_dir), str(source_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        result["status"] = "created"
    else:
        result["status"] = "failed"
        result["stderr"] = completed.stderr.strip()
        result["stdout"] = completed.stdout.strip()
    return result


def _same_path(left: Path, right: Path) -> bool:
    try:
        return _path_key(left.resolve(strict=False)) == _path_key(right.resolve(strict=False))
    except OSError:
        return False


def _path_key(path: Path) -> str:
    return str(path).replace("/", "\\").rstrip("\\").lower()
