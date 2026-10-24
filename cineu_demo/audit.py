from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def audit_run(run_dir: Path) -> dict[str, Any]:
    run_dir = Path(run_dir)
    events = _read_jsonl(run_dir / "traces" / "events.jsonl")
    static = _read_jsonl(run_dir / "verification" / "static.jsonl")
    precondition = _read_jsonl(run_dir / "verification" / "precondition.jsonl")
    runtime = _read_jsonl(run_dir / "verification" / "runtime.jsonl")
    state = _read_jsonl(run_dir / "verification" / "state.jsonl")
    operations = sorted((run_dir / "operations").glob("*.json"))
    event_counts = Counter(e.get("event") for e in events)
    failure_types = Counter()
    for records in (static, precondition, runtime, state):
        for r in records:
            if not r.get("passed", True):
                failure_types[r.get("diagnostics", {}).get("error_type", "UNKNOWN")] += 1
    final_report_path = run_dir / "verification" / "final_report.json"
    final_report = json.loads(final_report_path.read_text(encoding="utf-8")) if final_report_path.exists() else {}
    artifacts = sorted(str(p.relative_to(run_dir)) for p in (run_dir / "artifacts").glob("*")) if (run_dir / "artifacts").exists() else []
    return {
        "schema_version": "cineu.audit_report.v1",
        "run_dir": str(run_dir),
        "success": final_report.get("success"),
        "operation_count": len(operations),
        "event_counts": dict(event_counts),
        "verification_counts": {
            "static": len(static),
            "precondition": len(precondition),
            "runtime": len(runtime),
            "state": len(state),
        },
        "failure_types": dict(failure_types),
        "reflection_patch_count": event_counts.get("operation_patched", 0),
        "artifacts": artifacts,
    }


def audit_workspace(workspace: Path) -> dict[str, Any]:
    workspace = Path(workspace)
    runs = sorted((workspace / "runs").glob("run_*")) if (workspace / "runs").exists() else []
    audits = [audit_run(run) for run in runs]
    success = sum(1 for a in audits if a.get("success") is True)
    failure_types = Counter()
    for a in audits:
        failure_types.update(a.get("failure_types", {}))
    return {
        "schema_version": "cineu.workspace_audit.v1",
        "workspace": str(workspace),
        "run_count": len(audits),
        "success_count": success,
        "success_rate": success / len(audits) if audits else None,
        "failure_types": dict(failure_types),
        "runs": audits,
    }
