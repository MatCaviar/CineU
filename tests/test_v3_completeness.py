from __future__ import annotations

from pathlib import Path

from cineu_demo.index import rebuild_run_index
from cineu_demo.model_provider import EchoModelProvider
from cineu_demo.schema_export import export_json_schemas


def test_export_json_schemas(tmp_path: Path):
    written = export_json_schemas(tmp_path / "schemas")
    assert "task_spec" in written
    assert Path(written["operation"]).exists()


def test_rebuild_index_empty_workspace(tmp_path: Path):
    (tmp_path / "runs").mkdir()
    summary = rebuild_run_index(tmp_path)
    assert summary["run_count"] == 0
    assert (tmp_path / "index" / "runs_index.jsonl").exists()


def test_echo_provider_contract():
    provider = EchoModelProvider()
    out = provider.complete_json("hello", {"title": "Demo"}, context={"a": 1})
    assert out["schema_title"] == "Demo"
    assert provider.complete_text("x") == "x"
