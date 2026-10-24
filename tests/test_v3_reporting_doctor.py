from __future__ import annotations

import json
from pathlib import Path

from cineu_demo.demo_workspace import create_demo_workspace
from cineu_demo.doctor import doctor
from cineu_demo.engine import CineUOrchestrator
from cineu_demo.reporting import render_markdown_report, summarize_run, validate_run, write_run_report


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def test_reporting_validation_and_doctor(tmp_path: Path):
    workspace = tmp_path / "workspace"
    create_demo_workspace(workspace, overwrite=True)
    repo_root = Path(__file__).resolve().parents[1]
    run_dir = CineUOrchestrator(workspace=workspace, knowledge_dir=repo_root / "knowledge").run(
        "创建一个现代画廊场景，入口处有三幅画，中间有一个雕塑。"
    )

    summary = summarize_run(run_dir)
    assert summary["success"] is True
    assert summary["operation_count"] >= 8
    assert summary["actor_count_final"] >= 6

    validation = validate_run(run_dir)
    assert validation["passed"] is True

    md = render_markdown_report(run_dir)
    assert "Operation Plan" in md
    assert "TaskSpec Snapshot" in md
    report_path = write_run_report(run_dir)
    assert report_path.exists()
    assert (run_dir / "reports" / "run_summary.json").exists()

    doctor_report = doctor(workspace=workspace, knowledge_dir=repo_root / "knowledge", unreal_project=repo_root / "unreal_project" / "CineU_Demo.uproject")
    assert doctor_report["passed"] is True


def test_validate_run_rejects_failed_final_report(tmp_path: Path):
    run_dir = tmp_path / "run_failed"
    _write_json(run_dir / "manifest.json", {})
    (run_dir / "prompt.txt").write_text("prompt", encoding="utf-8")
    _write_json(run_dir / "planning" / "task_spec.json", {})
    _write_json(run_dir / "planning" / "dag.json", {})
    _write_json(run_dir / "planning" / "operations_plan.json", {"operations": []})
    (run_dir / "traces").mkdir(parents=True, exist_ok=True)
    (run_dir / "traces" / "events.jsonl").write_text("", encoding="utf-8")
    _write_json(run_dir / "verification" / "final_report.json", {"success": False, "artifacts": []})
    _write_json(run_dir / "snapshots" / "world_final.json", {})
    _write_json(run_dir / "status.json", {"status": "failed"})

    validation = validate_run(run_dir)

    assert validation["passed"] is False
    assert any(c["name"] == "final_report_success_true" and c["passed"] is False for c in validation["checks"])
