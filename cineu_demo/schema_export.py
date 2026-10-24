from __future__ import annotations

import json
from pathlib import Path

from .schemas import AssetMetadata, Dag, ExecutionResult, Operation, RunManifest, TaskSpec, TemplateManifest, VerificationReport

SCHEMA_MODELS = {
    "task_spec": TaskSpec,
    "dag": Dag,
    "operation": Operation,
    "asset": AssetMetadata,
    "template": TemplateManifest,
    "verification_report": VerificationReport,
    "execution_result": ExecutionResult,
    "run_manifest": RunManifest,
}


def export_json_schemas(out_dir: Path) -> dict[str, str]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}
    for name, model in SCHEMA_MODELS.items():
        path = out_dir / f"{name}.schema.json"
        path.write_text(json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2), encoding="utf-8")
        written[name] = str(path)
    manifest = {"schema_version": "cineu.schema_export_manifest.v1", "schemas": written}
    (out_dir / "schemas_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return written
