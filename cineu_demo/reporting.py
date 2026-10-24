from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .index import scan_run


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def summarize_run(run_dir: Path) -> dict[str, Any]:
    run_dir = Path(run_dir)
    row = scan_run(run_dir)
    task_spec = _read_json(run_dir / "planning" / "task_spec.json", {}) or {}
    dag = _read_json(run_dir / "planning" / "dag.json", {}) or {}
    operations = (_read_json(run_dir / "planning" / "operations_plan.json", {}) or {}).get("operations", [])
    world_final = _read_json(run_dir / "snapshots" / "world_final.json", {}) or {}
    verification_counts: dict[str, Counter[str]] = defaultdict(Counter)
    failed_checks: list[dict[str, Any]] = []
    for vf in sorted((run_dir / "verification").glob("*.jsonl")):
        for record in _read_jsonl(vf):
            bucket = "passed" if record.get("passed") else "failed"
            verification_counts[vf.stem][bucket] += 1
            if not record.get("passed"):
                failed_checks.append({"stage": vf.stem, "op_id": record.get("op_id"), "diagnostics": record.get("diagnostics")})
    events = _read_jsonl(run_dir / "traces" / "events.jsonl")
    event_counts = Counter(e.get("event", "unknown") for e in events)
    row.update(
        {
            "schema_version": "cineu.run_summary.v3",
            "task_id": task_spec.get("task_id"),
            "environment": task_spec.get("scene", {}).get("environment"),
            "duration_sec": task_spec.get("scene", {}).get("duration_sec"),
            "fps": task_spec.get("scene", {}).get("fps"),
            "entity_count": len(task_spec.get("entities", [])),
            "shot_count": len(task_spec.get("camera", {}).get("shots", [])),
            "dag_node_count": len(dag.get("nodes", [])),
            "operation_count": len(operations),
            "actor_count_final": len(world_final.get("actors", {})),
            "sequence_count_final": len(world_final.get("sequences", {})),
            "verification_counts": {k: dict(v) for k, v in sorted(verification_counts.items())},
            "verification_failed": failed_checks,
            "event_counts": dict(sorted(event_counts.items())),
        }
    )
    return row


def validate_run(run_dir: Path) -> dict[str, Any]:
    run_dir = Path(run_dir)
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, message: str = "") -> None:
        checks.append({"name": name, "passed": bool(passed), "message": message})

    add("run_dir_exists", run_dir.exists(), str(run_dir))
    for rel in [
        "manifest.json",
        "prompt.txt",
        "planning/task_spec.json",
        "planning/dag.json",
        "planning/operations_plan.json",
        "traces/events.jsonl",
        "verification/final_report.json",
        "snapshots/world_final.json",
        "status.json",
    ]:
        add(f"required_file:{rel}", (run_dir / rel).exists())
    plan = _read_json(run_dir / "planning" / "operations_plan.json", {"operations": []}) or {"operations": []}
    planned = [op.get("op_id") for op in plan.get("operations", [])]
    op_files = {p.stem for p in (run_dir / "operations").glob("*.json")} if (run_dir / "operations").exists() else set()
    script_files = {p.stem for p in (run_dir / "scripts").glob("*.py")} if (run_dir / "scripts").exists() else set()
    add("operation_files_cover_plan", set(planned).issubset(op_files), f"missing={sorted(set(planned)-op_files)}")
    add("script_files_cover_plan", set(planned).issubset(script_files), f"missing={sorted(set(planned)-script_files)}")
    final = _read_json(run_dir / "verification" / "final_report.json", {}) or {}
    add("final_report_has_success_field", "success" in final)
    add("final_report_success_true", final.get("success") is True)
    if final.get("success"):
        add("successful_run_has_artifacts", bool(final.get("artifacts")), "expected at least preview artifact")
    return {"schema_version": "cineu.run_validation.v3", "run_id": run_dir.name, "passed": all(c["passed"] for c in checks), "checks": checks}


def render_markdown_report(run_dir: Path) -> str:
    run_dir = Path(run_dir)
    summary = summarize_run(run_dir)
    validation = validate_run(run_dir)
    task = _read_json(run_dir / "planning" / "task_spec.json", {}) or {}
    operations = (_read_json(run_dir / "planning" / "operations_plan.json", {}) or {}).get("operations", [])
    prompt = (run_dir / "prompt.txt").read_text(encoding="utf-8", errors="replace") if (run_dir / "prompt.txt").exists() else ""
    lines = [
        f"# CineU Run Report: `{run_dir.name}`",
        "",
        "## Summary",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Success: `{summary.get('success')}`",
        f"- Environment: `{summary.get('environment')}`",
        f"- Duration / FPS: `{summary.get('duration_sec')}` sec / `{summary.get('fps')}` fps",
        f"- Entities / Shots / Operations: `{summary.get('entity_count')}` / `{summary.get('shot_count')}` / `{summary.get('operation_count')}`",
        f"- Final actors / sequences: `{summary.get('actor_count_final')}` / `{summary.get('sequence_count_final')}`",
        "",
        "## Prompt",
        "",
        "> " + prompt.strip().replace("\n", "\n> "),
        "",
        "## Operation Plan",
        "",
        "| # | op_id | type | agent | template |",
        "|---:|---|---|---|---|",
    ]
    for i, op in enumerate(operations, start=1):
        lines.append(f"| {i} | `{op.get('op_id')}` | `{op.get('type')}` | `{op.get('agent')}` | `{op.get('template_id')}` |")
    lines.extend(["", "## Verification Counts", "", "| Stage | Passed | Failed |", "|---|---:|---:|"])
    for stage, counts in summary.get("verification_counts", {}).items():
        lines.append(f"| `{stage}` | {counts.get('passed', 0)} | {counts.get('failed', 0)} |")
    lines.extend(["", "## Artifacts", ""])
    for artifact in summary.get("artifacts") or ["No artifacts recorded."]:
        lines.append(f"- `{artifact}`")
    lines.extend(["", "## Ledger Validation", "", f"- Passed: `{validation['passed']}`"])
    for c in validation["checks"]:
        if not c["passed"]:
            lines.append(f"- Failed `{c['name']}`: {c.get('message', '')}")
    lines.extend(["", "## TaskSpec Snapshot", "", "```json", json.dumps(task, ensure_ascii=False, indent=2), "```", ""])
    return "\n".join(lines)


def write_run_report(run_dir: Path) -> Path:
    run_dir = Path(run_dir)
    reports = run_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "run_summary.json").write_text(json.dumps(summarize_run(run_dir), ensure_ascii=False, indent=2), encoding="utf-8")
    (reports / "run_validation.json").write_text(json.dumps(validate_run(run_dir), ensure_ascii=False, indent=2), encoding="utf-8")
    path = reports / "run_report.md"
    path.write_text(render_markdown_report(run_dir), encoding="utf-8")
    return path
