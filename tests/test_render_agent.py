from pathlib import Path
from types import SimpleNamespace

from cineu_demo.agents import RenderAgent


def test_render_agent_outputs_absolute_artifact_dir_for_relative_workspace():
    ctx = SimpleNamespace(
        sequence_path="/Game/CineU/Sequences/SEQ_run_x",
        ledger=SimpleNamespace(run_dir=Path("workspace") / "runs" / "run_x"),
        task=SimpleNamespace(render=SimpleNamespace(resolution=[1280, 720], format="mp4", quality="preview")),
        template_store=SimpleNamespace(retrieve=lambda operation_type, agent: SimpleNamespace(template_id=f"{operation_type}.v1")),
    )

    op = RenderAgent().build(ctx)

    assert Path(op.inputs["output_dir"]).is_absolute()


def test_render_agent_outputs_absolute_world_state_path_for_preview_context():
    ctx = SimpleNamespace(
        sequence_path="/Game/CineU/Sequences/SEQ_run_x",
        ledger=SimpleNamespace(run_dir=Path("workspace") / "runs" / "run_x"),
        task=SimpleNamespace(render=SimpleNamespace(resolution=[1280, 720], format="mp4", quality="preview")),
        template_store=SimpleNamespace(retrieve=lambda operation_type, agent: SimpleNamespace(template_id=f"{operation_type}.v1")),
    )

    op = RenderAgent().build(ctx)

    assert Path(op.inputs["world_state_path"]).is_absolute()
    assert Path(op.inputs["world_state_path"]).name == "world_current.json"


def test_render_agent_requires_storyboard_manifest_for_sequence_preview():
    ctx = SimpleNamespace(
        sequence_path="/Game/CineU/Sequences/SEQ_run_x",
        ledger=SimpleNamespace(run_dir=Path("workspace") / "runs" / "run_x"),
        task=SimpleNamespace(render=SimpleNamespace(resolution=[1280, 720], format="mp4", quality="preview")),
        template_store=SimpleNamespace(retrieve=lambda operation_type, agent: SimpleNamespace(template_id=f"{operation_type}.v1")),
    )

    op = RenderAgent().build(ctx)

    assert "storyboard_manifest.json" in op.expected["render_artifacts_exist"]


def test_render_agent_requires_sequence_preview_clip_for_sequence_preview():
    ctx = SimpleNamespace(
        sequence_path="/Game/CineU/Sequences/SEQ_run_x",
        ledger=SimpleNamespace(run_dir=Path("workspace") / "runs" / "run_x"),
        task=SimpleNamespace(render=SimpleNamespace(resolution=[1280, 720], format="mp4", quality="preview")),
        template_store=SimpleNamespace(retrieve=lambda operation_type, agent: SimpleNamespace(template_id=f"{operation_type}.v1")),
    )

    op = RenderAgent().build(ctx)

    assert "sequence_preview.gif" in op.expected["render_artifacts_exist"]


def test_render_agent_requires_mp4_preview_when_task_format_is_mp4():
    ctx = SimpleNamespace(
        task=SimpleNamespace(render=SimpleNamespace(resolution=[1280, 720], format="mp4", quality="preview")),
        sequence_path="/Game/CineU/Sequences/SEQ_x",
        ledger=SimpleNamespace(run_dir=Path("workspace/runs/run_x")),
        template_store=SimpleNamespace(retrieve=lambda operation_type, agent: SimpleNamespace(template_id=f"{operation_type}.v1")),
    )

    op = RenderAgent().build(ctx)

    assert "sequence_preview.mp4" in op.expected["render_artifacts_exist"]


def test_render_agent_final_quality_uses_output_rate_mrq_for_native_source_frames():
    ctx = SimpleNamespace(
        task=SimpleNamespace(render=SimpleNamespace(resolution=[1280, 720], format="mp4", quality="final")),
        sequence_path="/Game/AnimalHitchcockZoom",
        ledger=SimpleNamespace(run_dir=Path("workspace/runs/run_x")),
        variables={
            "active_sequence_timeline": {"fps": 30, "start_frame": 0, "end_frame": 6},
            "active_native_capture_frame_range": {"start_frame": 10, "end_frame": 20},
        },
        template_store=SimpleNamespace(retrieve=lambda operation_type, agent: SimpleNamespace(template_id=f"{operation_type}.v1")),
    )

    op = RenderAgent().build(ctx)

    assert op.inputs["render_backend"] == "movie_render_pipeline"
    assert "mrq_sampled_source_frames" not in op.inputs
    assert op.inputs["mrq_output_frame_rate"] == {"numerator": 360, "denominator": 10}


def test_render_agent_final_quality_output_rate_targets_world4_frame_count():
    ctx = SimpleNamespace(
        task=SimpleNamespace(render=SimpleNamespace(resolution=[1280, 720], format="mp4", quality="final")),
        sequence_path="/Game/AnimalHitchcockZoom",
        ledger=SimpleNamespace(run_dir=Path("workspace/runs/run_x")),
        variables={
            "active_sequence_timeline": {"fps": 30, "start_frame": 0, "end_frame": 166},
            "active_native_capture_frame_range": {"start_frame": 10, "end_frame": 330},
        },
        template_store=SimpleNamespace(retrieve=lambda operation_type, agent: SimpleNamespace(template_id=f"{operation_type}.v1")),
    )

    op = RenderAgent().build(ctx)

    assert op.inputs["render_backend"] == "movie_render_pipeline"
    assert op.inputs["mrq_output_frame_rate"] == {"numerator": 9960, "denominator": 320}
    assert "mrq_sampled_source_frames" not in op.inputs
