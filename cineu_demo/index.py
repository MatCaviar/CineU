from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .ledger import atomic_write_json


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - index must be best-effort and rebuildable
        return default
    return default


def _read_prompt(run_dir: Path, limit: int = 240) -> str:
    p = run_dir / "prompt.txt"
    if not p.exists():
        return ""
    text = p.read_text(encoding="utf-8", errors="replace").strip().replace("\n", " ")
    return text[:limit]


def scan_run(run_dir: Path) -> dict[str, Any]:
    """Create a compact, rebuildable index row for a run directory."""
    run_dir = Path(run_dir)
    manifest = _read_json(run_dir / "manifest.json", {}) or {}
    status = _read_json(run_dir / "status.json", {}) or {}
    report = _read_json(run_dir / "verification" / "final_report.json", {}) or {}
    operations_plan = _read_json(run_dir / "planning" / "operations_plan.json", {}) or {}
    artifacts = []
    art_dir = run_dir / "artifacts"
    if art_dir.exists():
        artifacts = sorted(str(p.relative_to(run_dir)) for p in art_dir.iterdir() if p.is_file())
    operation_count = len(operations_plan.get("operations", []))
    events_path = run_dir / "traces" / "events.jsonl"
    event_count = 0
    if events_path.exists():
        event_count = sum(1 for line in events_path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())
    return {
        "schema_version": "cineu.run_index_row.v1",
        "run_id": manifest.get("run_id") or run_dir.name,
        "run_dir": str(run_dir),
        "project_id": manifest.get("project_id") or status.get("project_id"),
        "created_at": manifest.get("created_at"),
        "status": status.get("status") or ("success" if report.get("success") else "unknown"),
        "success": bool(report.get("success", False)),
        "prompt_excerpt": _read_prompt(run_dir),
        "operation_count": operation_count,
        "event_count": event_count,
        "metrics": report.get("metrics", {}),
        "artifacts": artifacts,
    }


def rebuild_run_index(workspace: Path) -> dict[str, Any]:
    """Rebuild local JSONL index from the file ledger.

    The index is deliberately derived data. Deleting workspace/index is safe;
    this function reconstructs it from workspace/runs/*.
    """
    workspace = Path(workspace)
    runs_dir = workspace / "runs"
    out_dir = workspace / "index"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    if runs_dir.exists():
        for run_dir in sorted(p for p in runs_dir.iterdir() if p.is_dir()):
            if (run_dir / "manifest.json").exists():
                rows.append(scan_run(run_dir))
    rows_path = out_dir / "runs_index.jsonl"
    rows_path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + ("\n" if rows else ""), encoding="utf-8")
    status_counts = Counter(r.get("status", "unknown") for r in rows)
    summary = {
        "schema_version": "cineu.run_index_summary.v1",
        "run_count": len(rows),
        "success_count": sum(1 for r in rows if r.get("success")),
        "success_rate": (sum(1 for r in rows if r.get("success")) / len(rows)) if rows else None,
        "status_counts": dict(status_counts),
        "rows_file": str(rows_path),
    }
    atomic_write_json(out_dir / "summary.json", summary)
    return summary
