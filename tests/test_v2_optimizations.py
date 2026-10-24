import json
from pathlib import Path

from cineu_demo.camera_math import compute_hitchcock_zoom_keys_for_target_path
from cineu_demo.codegen import CodeAssembler, StaticVerifier
from cineu_demo.demo_workspace import create_demo_workspace
from cineu_demo.engine import CineUOrchestrator
from cineu_demo.operation_plan import renumber_operations
from cineu_demo.planner import RuleBasedPlanner
from cineu_demo.preflight import PreconditionVerifier
from cineu_demo.schemas import Operation
from cineu_demo.template_store import TemplateStore


def test_moving_hitchcock_camera_follows_target_path():
    keys = compute_hitchcock_zoom_keys_for_target_path(
        [-600, 0, 100], [600, 0, 100], [0, -1, 0], 900, 350, 35, 0, 192, num_keys=4
    )
    assert keys[0]["location"][0] == -600
    assert keys[-1]["location"][0] == 600
    ratios = [k["focal_length"] / k["focus_distance"] for k in keys]
    assert max(abs(r - ratios[0]) for r in ratios) < 1e-9


def test_zebra_pipeline_has_transform_and_animation_tracks(tmp_path: Path):
    workspace = tmp_path / "workspace"
    create_demo_workspace(workspace, overwrite=True)
    run_dir = CineUOrchestrator(workspace=workspace, knowledge_dir=Path("knowledge")).run("斑马从左到右移动，Hitchcock zoom")
    report = json.loads((run_dir / "verification" / "final_report.json").read_text(encoding="utf-8"))
    assert report["success"] is True
    state = json.loads((run_dir / "snapshots" / "world_final.json").read_text(encoding="utf-8"))
    seq = next(iter(state["sequences"].values()))
    assert "zebra_01" in seq["transform_tracks"]
    assert "zebra_01" in seq["animation_tracks"]
    transform_keys = seq["transform_tracks"]["zebra_01"]["keys"]
    assert transform_keys[0]["transform"]["location"][2] == 0.0
    assert transform_keys[-1]["transform"]["location"][2] == 0.0
    assert state["actors"]["zebra_01"]["transform"]["location"][2] == 0.0
    assert report["metrics"]["operation_success_count"] >= 9


def test_operation_renumbering_prevents_collisions():
    task, _, _ = RuleBasedPlanner().plan("gallery")
    ops = [
        Operation(op_id="same", node_id="a", agent="CamAgent", type="camera.dolly_in", template_id="camera.dolly_in.v1", inputs={"shot_id": "shot_001"}),
        Operation(op_id="same", node_id="b", agent="CamAgent", type="camera.wide_aerial", template_id="camera.wide_aerial.v1", inputs={"shot_id": "shot_002"}),
        Operation(op_id="same", node_id="c", agent="SeqAgent", type="sequence.camera_cut", template_id="sequence.camera_cut.v1"),
    ]
    numbered = renumber_operations(ops)
    assert len({op.op_id for op in numbered}) == len(numbered)
    assert numbered[0].op_id.startswith("0001_")


def test_template_input_static_verification_catches_missing_required_input():
    store = TemplateStore(Path("knowledge/templates"))
    template = store.get("sequence.init.v1")
    op = Operation(op_id="op", node_id="seq.init", agent="SeqAgent", type="sequence.init", template_id="sequence.init.v1", inputs={"sequence_path": "/Game/X"})
    script = CodeAssembler().assemble(template, op, context={"world_state_path": "x.json"})
    report = StaticVerifier().verify(script, op, template=template)
    assert not report.passed
    assert report.diagnostics["error_type"] == "TEMPLATE_INPUT_VIOLATION"


def test_precondition_verifier_catches_camera_before_sequence():
    store = TemplateStore(Path("knowledge/templates"))
    template = store.get("camera.dolly_in.v1")
    op = Operation(
        op_id="op",
        node_id="seq.camera",
        agent="CamAgent",
        type="camera.dolly_in",
        template_id="camera.dolly_in.v1",
        inputs={"sequence_path": "/Game/Missing", "target_actor": "world_origin", "camera_name": "CAM", "keys": []},
    )
    report = PreconditionVerifier().verify(template, op, {"actors": {}, "sequences": {}})
    assert not report.passed
    assert report.diagnostics["error_type"] == "PRECONDITION_FAILED"
