from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .index import rebuild_run_index
from .ledger import atomic_write_json


def _count_files(root: Path) -> tuple[int, int]:
    if not root.exists():
        return 0, 0
    files = [p for p in root.rglob("*") if p.is_file()]
    return len(files), sum(p.stat().st_size for p in files)


def build_system_report(project_root: Path, workspace: Path | None = None) -> dict[str, Any]:
    project_root = Path(project_root)
    workspace = Path(workspace) if workspace else project_root / "workspace"
    sections = {}
    for rel in ["cineu_demo", "knowledge/templates", "unreal_project", "examples", "tests", "workspace"]:
        count, size = _count_files(project_root / rel)
        sections[rel] = {"file_count": count, "bytes": size}
    index_summary = rebuild_run_index(workspace) if workspace.exists() else None
    report = {
        "schema_version": "cineu.system_report.v1",
        "project_root": str(project_root),
        "sections": sections,
        "index_summary": index_summary,
    }
    out = project_root / "SYSTEM_REPORT.json"
    atomic_write_json(out, report)
    return report
