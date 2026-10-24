from __future__ import annotations

import json
import shutil
import subprocess
import sys
from types import SimpleNamespace
from pathlib import Path

from PIL import Image

from cineu_demo.engine import make_runner
from cineu_demo.ledger import atomic_write_json
from cineu_demo.runner import (
    MockRunner,
    UnrealCommandRunner,
    _write_movie_frame_paths_mp4,
    _write_sequence_preview_mp4,
    initial_world_state,
)
from cineu_demo.schemas import Operation


def test_make_runner_allows_unreal_timeout_override(tmp_path: Path):
    runner = make_runner(
        "unreal",
        unreal_editor_cmd="D:/UE_5.5/Engine/Binaries/Win64/UnrealEditor-Cmd.exe",
        uproject=tmp_path / "Demo.uproject",
        unreal_timeout_sec=900,
    )

    assert isinstance(runner, UnrealCommandRunner)
    assert runner.timeout_sec == 900


def test_mock_runner_marks_park_surface_level_backed_for_level_environment_asset(tmp_path: Path):
    runner = MockRunner()
    op = Operation(
        op_id="env_setup",
        node_id="env.setup",
        agent="EnvAgent",
        type="env.setup",
        template_id="env.setup.v1",
        inputs={
            "level_name": "LVL_test",
            "environment": "park",
            "environment_asset": {
                "asset_id": "asset_ue_project_content_citypark_maps_showcase",
                "ue_path": "/Game/CityPark/Maps/Showcase",
                "type": "level",
            },
        },
    )

    result = runner.execute(op, "", tmp_path)

    assert result.ok is True
    state = runner.load_state(tmp_path)
    assert state["support_surfaces"]["park_path"]["environment_asset_type"] == "level"


def test_mock_runner_storyboard_samples_are_dense_enough_for_animatic_preview():
    runner = MockRunner()
    seq = {
        "camera_cuts": [
            {"camera_name": "CAM_A", "shot_id": "shot_a", "start_frame": 0, "end_frame": 48},
            {"camera_name": "CAM_B", "shot_id": "shot_b", "start_frame": 48, "end_frame": 72},
        ],
        "cameras": {
            "CAM_A": {
                "transform_keys": [
                    {"frame": 0, "location": [0, -300, 160], "rotation": [-4, 0, 90]},
                    {"frame": 48, "location": [0, -80, 150], "rotation": [-8, 0, 90]},
                ],
            },
            "CAM_B": {
                "transform_keys": [
                    {"frame": 48, "location": [-200, -200, 260], "rotation": [-20, 0, 45]},
                    {"frame": 72, "location": [200, -200, 260], "rotation": [-20, 0, 135]},
                ],
            },
        },
    }

    samples = runner._mock_storyboard_samples(seq)

    assert [sample["frame"] for sample in samples] == [0, 6, 12, 18, 24, 29, 35, 41, 47, 48, 51, 54, 57, 60, 62, 65, 68, 71]


def test_unreal_runner_writes_executor_bootstrap(tmp_path: Path):
    runner = UnrealCommandRunner("D:/UE_5.5/Engine/Binaries/Win64/UnrealEditor-Cmd.exe", tmp_path / "Demo.uproject")
    run_dir = tmp_path / "runs" / "run_x"
    script_path = run_dir / "scripts" / "0001_env_setup.py"
    script_path.parent.mkdir(parents=True)
    script_path.write_text("OUTPUT = {'ok': True}\n", encoding="utf-8")

    op = Operation(op_id="0001_env_setup", node_id="env.setup", agent="EnvAgent", type="env.setup", template_id="env.setup.v1")
    bootstrap = runner._write_executor_bootstrap(op, script_path, run_dir)

    text = bootstrap.read_text(encoding="utf-8")
    assert "execute_generated_script" in text
    assert str(script_path).replace("\\", "\\\\") in text
    assert str(run_dir / "snapshots" / "world_current.json").replace("\\", "\\\\") in text
    assert str(run_dir / "traces" / "0001_env_setup_unreal_result.json").replace("\\", "\\\\") in text


def test_unreal_runner_bootstrap_uses_absolute_paths_for_unreal_cwd(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "unreal_project" / "Plugins" / "CineUDemo" / "Content" / "Python").mkdir(parents=True)
    uproject = Path("unreal_project") / "Demo.uproject"
    uproject.parent.mkdir(parents=True, exist_ok=True)
    uproject.write_text("{}", encoding="utf-8")
    runner = UnrealCommandRunner("D:/UE_5.5/Engine/Binaries/Win64/UnrealEditor-Cmd.exe", uproject)
    run_dir = Path("workspace") / "runs" / "run_x"
    script_path = run_dir / "scripts" / "0001_env_setup.py"
    script_path.parent.mkdir(parents=True)
    script_path.write_text("OUTPUT = {'ok': True}\n", encoding="utf-8")

    op = Operation(op_id="0001_env_setup", node_id="env.setup", agent="EnvAgent", type="env.setup", template_id="env.setup.v1")
    bootstrap = runner._write_executor_bootstrap(op, script_path, run_dir)

    text = bootstrap.read_text(encoding="utf-8")
    assert repr(str(script_path.resolve())) in text
    assert repr(str((run_dir / "snapshots" / "world_current.json").resolve())) in text
    assert repr(str((run_dir / "traces" / "0001_env_setup_unreal_result.json").resolve())) in text
    assert repr(str((tmp_path / "unreal_project" / "Plugins" / "CineUDemo" / "Content" / "Python").resolve())) in text


def test_unreal_runner_uses_nozen_ddc_graph_by_default(tmp_path: Path):
    runner = UnrealCommandRunner("D:/UE_5.5/Engine/Binaries/Win64/UnrealEditor-Cmd.exe", tmp_path / "Demo.uproject")

    cmd = runner._unreal_cmd_for_script(tmp_path / "script.py")

    assert "-DDC=InstalledNoZenLocalFallback" in cmd


def test_unreal_runner_parses_result_json(tmp_path: Path, monkeypatch):
    run_dir = tmp_path / "runs" / "run_x"
    (run_dir / "snapshots").mkdir(parents=True)
    atomic_write_json(run_dir / "snapshots" / "world_current.json", initial_world_state())
    uproject = tmp_path / "Demo.uproject"
    uproject.write_text("{}", encoding="utf-8")
    runner = UnrealCommandRunner("D:/UE_5.5/Engine/Binaries/Win64/UnrealEditor-Cmd.exe", uproject)
    op = Operation(op_id="0001_env_setup", node_id="env.setup", agent="EnvAgent", type="env.setup", template_id="env.setup.v1")

    def fake_run(cmd, capture_output, text, timeout, check):
        result_path = run_dir / "traces" / "0001_env_setup_unreal_result.json"
        result_path.parent.mkdir(parents=True)
        result_path.write_text(json.dumps({"ok": True, "output": {"level": "LVL_test"}}), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = runner.execute(op, "OUTPUT = {'level': 'LVL_test'}\n", run_dir)

    assert result.ok is True
    assert result.result["unreal_result"]["output"]["level"] == "LVL_test"
    assert "ExecutePythonScript=" in " ".join(result.result["cmd"])


def test_unreal_runner_marks_black_storyboard_frames_for_repair(tmp_path: Path):
    out_dir = tmp_path / "artifacts"
    out_dir.mkdir()
    frame_path = out_dir / "storyboard_000.png"
    Image.new("RGB", (1280, 720), color=(0, 0, 0)).save(frame_path)
    (out_dir / "storyboard_manifest.json").write_text(
        json.dumps({"frames": [{"artifact": str(frame_path), "artifact_name": "storyboard_000.png"}]}),
        encoding="utf-8",
    )
    runner = UnrealCommandRunner("D:/UE_5.5/Engine/Binaries/Win64/UnrealEditor-Cmd.exe", tmp_path / "Demo.uproject")
    op = Operation(
        op_id="0008_render_preview",
        node_id="render.preview",
        agent="RenderAgent",
        type="render.preview",
        template_id="render.preview.v1",
        inputs={"output_dir": str(out_dir)},
    )

    repairs = runner._storyboard_repairs_needed(op)

    assert len(repairs) == 1
    assert repairs[0]["index"] == 0
    assert repairs[0]["reason"] == "blank_or_black"


def test_unreal_runner_repairs_tiny_storyboard_frames_after_render(tmp_path: Path, monkeypatch):
    run_dir = tmp_path / "runs" / "run_x"
    out_dir = run_dir / "artifacts"
    out_dir.mkdir(parents=True)
    (run_dir / "snapshots").mkdir(parents=True)
    atomic_write_json(run_dir / "snapshots" / "world_current.json", initial_world_state())
    uproject = tmp_path / "unreal_project" / "Demo.uproject"
    (uproject.parent / "Plugins" / "CineUDemo" / "Content" / "Python").mkdir(parents=True)
    uproject.write_text("{}", encoding="utf-8")
    runner = UnrealCommandRunner("D:/UE_5.5/Engine/Binaries/Win64/UnrealEditor-Cmd.exe", uproject)
    op = Operation(
        op_id="0008_render_preview",
        node_id="render.preview",
        agent="RenderAgent",
        type="render.preview",
        template_id="render.preview.v1",
        inputs={"output_dir": str(out_dir), "sequence_path": "/Game/Seq", "world_state_path": str(run_dir / "snapshots" / "world_current.json")},
    )
    calls = []

    def write_png(path: Path, color: tuple[int, int, int]) -> None:
        image = Image.new("RGB", (128, 72), color=color)
        for x in range(0, 128, 8):
            for y in range(0, 72, 8):
                if (x + y) % 16 == 0:
                    image.putpixel((x, y), (min(255, color[0] + 20), max(0, color[1] - 20), color[2]))
        image.save(path)

    def fake_run(cmd, capture_output, text, timeout, check):
        calls.append(cmd)
        frame_path = out_dir / "storyboard_000.png"
        if len(calls) == 1:
            manifest_path = out_dir / "storyboard_manifest.json"
            preview_manifest = out_dir / "preview_manifest.json"
            preview_frame = out_dir / "preview_frame.png"
            frame_path.write_bytes(b"x")
            write_png(preview_frame, (64, 96, 128))
            manifest_path.write_text(
                json.dumps({"frames": [{"artifact": str(frame_path), "artifact_name": "storyboard_000.png"}]}),
                encoding="utf-8",
            )
            preview_manifest.write_text("{}", encoding="utf-8")
            result_path = run_dir / "traces" / "0008_render_preview_unreal_result.json"
            result_path.parent.mkdir(parents=True)
            result_path.write_text(
                json.dumps(
                    {
                        "ok": True,
                        "output": {
                            "artifacts": {
                                "preview_frame.png": str(preview_frame),
                                "preview_manifest.json": str(preview_manifest),
                                "storyboard_manifest.json": str(manifest_path),
                                "storyboard_000.png": str(frame_path),
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
        else:
            write_png(frame_path, (0, 128, 255))
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = runner.execute(op, "OUTPUT = {'ok': True}\n", run_dir)

    assert result.ok is True
    assert len(calls) == 2
    assert (out_dir / "storyboard_000.png").stat().st_size > 128


def test_unreal_runner_batches_multiple_tiny_storyboard_frame_repairs(tmp_path: Path, monkeypatch):
    run_dir = tmp_path / "runs" / "run_x"
    out_dir = run_dir / "artifacts"
    out_dir.mkdir(parents=True)
    (run_dir / "snapshots").mkdir(parents=True)
    atomic_write_json(run_dir / "snapshots" / "world_current.json", initial_world_state())
    uproject = tmp_path / "unreal_project" / "Demo.uproject"
    (uproject.parent / "Plugins" / "CineUDemo" / "Content" / "Python").mkdir(parents=True)
    uproject.write_text("{}", encoding="utf-8")
    runner = UnrealCommandRunner("D:/UE_5.5/Engine/Binaries/Win64/UnrealEditor-Cmd.exe", uproject)
    op = Operation(
        op_id="0008_render_preview",
        node_id="render.preview",
        agent="RenderAgent",
        type="render.preview",
        template_id="render.preview.v1",
        inputs={"output_dir": str(out_dir), "sequence_path": "/Game/Seq", "world_state_path": str(run_dir / "snapshots" / "world_current.json")},
    )
    calls = []

    def write_png(path: Path, color: tuple[int, int, int]) -> None:
        image = Image.new("RGB", (128, 72), color=color)
        for x in range(0, 128, 8):
            for y in range(0, 72, 8):
                if (x + y) % 16 == 0:
                    image.putpixel((x, y), (min(255, color[0] + 20), max(0, color[1] - 20), color[2]))
        image.save(path)

    def fake_run(cmd, capture_output, text, timeout, check):
        calls.append(cmd)
        frame_a = out_dir / "storyboard_000.png"
        frame_b = out_dir / "storyboard_001.png"
        preview_frame = out_dir / "preview_frame.png"
        if len(calls) == 1:
            manifest_path = out_dir / "storyboard_manifest.json"
            preview_manifest = out_dir / "preview_manifest.json"
            frame_a.write_bytes(b"x")
            frame_b.write_bytes(b"y")
            write_png(preview_frame, (255, 0, 0))
            manifest_path.write_text(
                json.dumps(
                    {
                        "frames": [
                            {"artifact": str(frame_a), "artifact_name": "storyboard_000.png"},
                            {"artifact": str(frame_b), "artifact_name": "storyboard_001.png"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            preview_manifest.write_text("{}", encoding="utf-8")
            result_path = run_dir / "traces" / "0008_render_preview_unreal_result.json"
            result_path.parent.mkdir(parents=True)
            result_path.write_text(
                json.dumps(
                    {
                        "ok": True,
                        "output": {
                            "artifacts": {
                                "preview_frame.png": str(preview_frame),
                                "preview_manifest.json": str(preview_manifest),
                                "storyboard_manifest.json": str(manifest_path),
                                "storyboard_000.png": str(frame_a),
                                "storyboard_001.png": str(frame_b),
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
        else:
            write_png(frame_a, (0, 128, 255))
            write_png(frame_b, (0, 255, 128))
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = runner.execute(op, "OUTPUT = {'ok': True}\n", run_dir)

    assert result.ok is True
    assert len(calls) == 2
    assert (out_dir / "storyboard_000.png").stat().st_size > 128
    assert (out_dir / "storyboard_001.png").stat().st_size > 128


def test_unreal_runner_falls_back_after_partial_batch_storyboard_repair(tmp_path: Path, monkeypatch):
    run_dir = tmp_path / "runs" / "run_x"
    out_dir = run_dir / "artifacts"
    out_dir.mkdir(parents=True)
    (run_dir / "snapshots").mkdir(parents=True)
    atomic_write_json(run_dir / "snapshots" / "world_current.json", initial_world_state())
    uproject = tmp_path / "unreal_project" / "Demo.uproject"
    (uproject.parent / "Plugins" / "CineUDemo" / "Content" / "Python").mkdir(parents=True)
    uproject.write_text("{}", encoding="utf-8")
    runner = UnrealCommandRunner("D:/UE_5.5/Engine/Binaries/Win64/UnrealEditor-Cmd.exe", uproject)
    op = Operation(
        op_id="0008_render_preview",
        node_id="render.preview",
        agent="RenderAgent",
        type="render.preview",
        template_id="render.preview.v1",
        inputs={"output_dir": str(out_dir), "sequence_path": "/Game/Seq", "world_state_path": str(run_dir / "snapshots" / "world_current.json")},
    )
    calls = []

    def write_png(path: Path, color: tuple[int, int, int]) -> None:
        image = Image.new("RGB", (128, 72), color=color)
        for x in range(0, 128, 8):
            for y in range(0, 72, 8):
                if (x + y) % 16 == 0:
                    image.putpixel((x, y), (min(255, color[0] + 20), max(0, color[1] - 20), color[2]))
        image.save(path)

    def fake_run(cmd, capture_output, text, timeout, check):
        calls.append(cmd)
        frame_a = out_dir / "storyboard_000.png"
        frame_b = out_dir / "storyboard_001.png"
        preview_frame = out_dir / "preview_frame.png"
        if len(calls) == 1:
            manifest_path = out_dir / "storyboard_manifest.json"
            preview_manifest = out_dir / "preview_manifest.json"
            frame_a.write_bytes(b"x")
            frame_b.write_bytes(b"y")
            write_png(preview_frame, (255, 0, 0))
            manifest_path.write_text(
                json.dumps(
                    {
                        "frames": [
                            {"artifact": str(frame_a), "artifact_name": "storyboard_000.png"},
                            {"artifact": str(frame_b), "artifact_name": "storyboard_001.png"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            preview_manifest.write_text("{}", encoding="utf-8")
            result_path = run_dir / "traces" / "0008_render_preview_unreal_result.json"
            result_path.parent.mkdir(parents=True)
            result_path.write_text(
                json.dumps(
                    {
                        "ok": True,
                        "output": {
                            "artifacts": {
                                "preview_frame.png": str(preview_frame),
                                "preview_manifest.json": str(preview_manifest),
                                "storyboard_manifest.json": str(manifest_path),
                                "storyboard_000.png": str(frame_a),
                                "storyboard_001.png": str(frame_b),
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
        elif len(calls) == 2:
            write_png(frame_b, (0, 255, 128))
        else:
            write_png(frame_a, (0, 128, 255))
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = runner.execute(op, "OUTPUT = {'ok': True}\n", run_dir)

    assert result.ok is True
    assert len(calls) == 3
    assert (out_dir / "storyboard_000.png").stat().st_size > 128
    assert (out_dir / "storyboard_001.png").stat().st_size > 128


def test_unreal_runner_repairs_tiny_preview_frame_after_render(tmp_path: Path, monkeypatch):
    run_dir = tmp_path / "runs" / "run_x"
    out_dir = run_dir / "artifacts"
    out_dir.mkdir(parents=True)
    (run_dir / "snapshots").mkdir(parents=True)
    atomic_write_json(run_dir / "snapshots" / "world_current.json", initial_world_state())
    uproject = tmp_path / "unreal_project" / "Demo.uproject"
    (uproject.parent / "Plugins" / "CineUDemo" / "Content" / "Python").mkdir(parents=True)
    uproject.write_text("{}", encoding="utf-8")
    runner = UnrealCommandRunner("D:/UE_5.5/Engine/Binaries/Win64/UnrealEditor-Cmd.exe", uproject)
    op = Operation(
        op_id="0008_render_preview",
        node_id="render.preview",
        agent="RenderAgent",
        type="render.preview",
        template_id="render.preview.v1",
        inputs={"output_dir": str(out_dir), "sequence_path": "/Game/Seq", "world_state_path": str(run_dir / "snapshots" / "world_current.json")},
    )
    calls = []

    def write_png(path: Path, color: tuple[int, int, int]) -> None:
        Image.new("RGB", (128, 72), color=color).save(path)

    def fake_run(cmd, capture_output, text, timeout, check):
        calls.append(cmd)
        frame_path = out_dir / "storyboard_000.png"
        preview_frame = out_dir / "preview_frame.png"
        if len(calls) == 1:
            manifest_path = out_dir / "storyboard_manifest.json"
            preview_manifest = out_dir / "preview_manifest.json"
            write_png(frame_path, (255, 128, 0))
            preview_frame.write_bytes(b"x")
            manifest_path.write_text(
                json.dumps({"frames": [{"camera_name": "CAM_A", "frame": 0, "artifact": str(frame_path), "artifact_name": "storyboard_000.png"}]}),
                encoding="utf-8",
            )
            preview_manifest.write_text(json.dumps({"preview_camera": "CAM_A", "preview_frame": 0}), encoding="utf-8")
            result_path = run_dir / "traces" / "0008_render_preview_unreal_result.json"
            result_path.parent.mkdir(parents=True)
            result_path.write_text(
                json.dumps(
                    {
                        "ok": True,
                        "output": {
                            "artifacts": {
                                "preview_frame.png": str(preview_frame),
                                "preview_manifest.json": str(preview_manifest),
                                "storyboard_manifest.json": str(manifest_path),
                                "storyboard_000.png": str(frame_path),
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
        else:
            write_png(preview_frame, (255, 128, 0))
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = runner.execute(op, "OUTPUT = {'ok': True}\n", run_dir)

    assert result.ok is True
    assert len(calls) == 1
    assert (out_dir / "preview_frame.png").stat().st_size > 128


def test_unreal_runner_builds_sequence_preview_gif_after_render(tmp_path: Path, monkeypatch):
    run_dir = tmp_path / "runs" / "run_x"
    out_dir = run_dir / "artifacts"
    out_dir.mkdir(parents=True)
    (run_dir / "snapshots").mkdir(parents=True)
    atomic_write_json(run_dir / "snapshots" / "world_current.json", {**initial_world_state(), "renders": []})
    uproject = tmp_path / "unreal_project" / "Demo.uproject"
    (uproject.parent / "Plugins" / "CineUDemo" / "Content" / "Python").mkdir(parents=True)
    uproject.write_text("{}", encoding="utf-8")
    runner = UnrealCommandRunner("D:/UE_5.5/Engine/Binaries/Win64/UnrealEditor-Cmd.exe", uproject)
    op = Operation(
        op_id="0008_render_preview",
        node_id="render.preview",
        agent="RenderAgent",
        type="render.preview",
        template_id="render.preview.v1",
        inputs={"output_dir": str(out_dir), "sequence_path": "/Game/Seq", "world_state_path": str(run_dir / "snapshots" / "world_current.json")},
    )

    def write_png(path: Path, color: tuple[int, int, int]) -> None:
        Image.new("RGB", (128, 72), color=color).save(path)

    def fake_run(cmd, capture_output, text, timeout, check):
        frame_a = out_dir / "storyboard_000.png"
        frame_b = out_dir / "storyboard_001.png"
        preview_frame = out_dir / "preview_frame.png"
        manifest_path = out_dir / "storyboard_manifest.json"
        preview_manifest = out_dir / "preview_manifest.json"
        write_png(frame_a, (255, 0, 0))
        write_png(frame_b, (0, 0, 255))
        write_png(preview_frame, (255, 0, 0))
        preview_manifest.write_text("{}", encoding="utf-8")
        manifest_path.write_text(
            json.dumps(
                {
                    "frames": [
                        {"camera_name": "CAM_A", "frame": 0, "artifact": str(frame_a), "artifact_name": "storyboard_000.png"},
                        {"camera_name": "CAM_A", "frame": 24, "artifact": str(frame_b), "artifact_name": "storyboard_001.png"},
                    ]
                }
            ),
            encoding="utf-8",
        )
        result_path = run_dir / "traces" / "0008_render_preview_unreal_result.json"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(
            json.dumps(
                {
                    "ok": True,
                    "output": {
                        "preview_camera": "CAM_A",
                        "artifacts": {
                            "preview_frame.png": str(preview_frame),
                            "preview_manifest.json": str(preview_manifest),
                            "storyboard_manifest.json": str(manifest_path),
                            "storyboard_000.png": str(frame_a),
                            "storyboard_001.png": str(frame_b),
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = runner.execute(op, "OUTPUT = {'ok': True}\n", run_dir)
    state = runner.load_state(run_dir)

    assert result.ok is True
    clip = out_dir / "sequence_preview.gif"
    assert clip.exists()
    assert clip.stat().st_size > 128
    assert state["renders"][-1]["artifacts"]["sequence_preview.gif"] == str(clip)


def test_unreal_runner_finalizes_native_movie_capture_frames_without_recapture(tmp_path: Path, monkeypatch):
    run_dir = tmp_path / "runs" / "run_native"
    out_dir = run_dir / "artifacts"
    movie_dir = out_dir / "movie_frames"
    movie_dir.mkdir(parents=True)
    (run_dir / "snapshots").mkdir(parents=True)
    state = initial_world_state()
    state["sequences"]["/Game/AnimalHitchcockZoom"] = {
        "source_asset_id": "asset_ue_project_content_animalhitchcockzoom",
        "source_asset_type": "level_sequence",
    }
    atomic_write_json(run_dir / "snapshots" / "world_current.json", state)
    uproject = tmp_path / "unreal_project" / "Demo.uproject"
    (uproject.parent / "Plugins" / "CineUDemo" / "Content" / "Python").mkdir(parents=True)
    uproject.write_text("{}", encoding="utf-8")
    runner = UnrealCommandRunner("D:/UE_5.5/Engine/Binaries/Win64/UnrealEditor-Cmd.exe", uproject)
    op = Operation(
        op_id="0003_render_preview",
        node_id="render.preview",
        agent="RenderAgent",
        type="render.preview",
        template_id="render.preview.v1",
        inputs={
            "output_dir": str(out_dir),
            "sequence_path": "/Game/AnimalHitchcockZoom",
            "world_state_path": str(run_dir / "snapshots" / "world_current.json"),
            "format": "mp4",
            "fps": 24,
            "start_frame": 0,
            "end_frame": 25,
        },
    )
    calls = []

    def write_png(path: Path, color: tuple[int, int, int]) -> None:
        Image.new("RGB", (128, 72), color=color).save(path)

    def fake_run(cmd, capture_output, text, timeout, check):
        calls.append(cmd)
        for frame in range(25):
            color = (255, 0, 0) if frame < 12 else (0, 0, 255)
            write_png(movie_dir / f"movie_frame_{frame:04d}.png", color)
        shutil.copyfile(movie_dir / "movie_frame_0000.png", out_dir / "preview_frame.png")
        shutil.copyfile(movie_dir / "movie_frame_0000.png", out_dir / "storyboard_000.png")
        shutil.copyfile(movie_dir / "movie_frame_0024.png", out_dir / "storyboard_001.png")
        preview_manifest = out_dir / "preview_manifest.json"
        storyboard_manifest = out_dir / "storyboard_manifest.json"
        storyboard_manifest.write_text(
            json.dumps(
                {
                    "render_backend": "sequencer_movie_capture",
                    "movie_frame_dir": str(movie_dir),
                    "capture_success": None,
                    "warnings": [{"reason": "deadline", "capture_success": None}],
                    "frames": [
                        {"frame": 0, "artifact": str(out_dir / "storyboard_000.png"), "artifact_name": "storyboard_000.png"},
                        {"frame": 24, "artifact": str(out_dir / "storyboard_001.png"), "artifact_name": "storyboard_001.png"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        preview_manifest.write_text(
            json.dumps(
                {
                    "render_backend": "sequencer_movie_capture",
                    "preview_frame": 0,
                    "movie_frame_dir": str(movie_dir),
                    "capture_success": None,
                    "warnings": [{"reason": "deadline", "capture_success": None}],
                    "storyboard_frames": [
                        {"frame": 0, "artifact": str(out_dir / "storyboard_000.png"), "artifact_name": "storyboard_000.png"},
                        {"frame": 24, "artifact": str(out_dir / "storyboard_001.png"), "artifact_name": "storyboard_001.png"},
                    ],
                    "artifacts": {
                        "preview_frame.png": str(out_dir / "preview_frame.png"),
                        "preview_manifest.json": str(preview_manifest),
                        "storyboard_manifest.json": str(storyboard_manifest),
                        "movie_frame_dir": str(movie_dir),
                    },
                }
            ),
            encoding="utf-8",
        )
        result_path = run_dir / "traces" / "0003_render_preview_unreal_result.json"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(
            json.dumps(
                {
                    "ok": True,
                    "output": {
                        "render_backend": "sequencer_movie_capture",
                        "artifacts": {
                            "preview_frame.png": str(out_dir / "preview_frame.png"),
                            "preview_manifest.json": str(preview_manifest),
                            "storyboard_manifest.json": str(storyboard_manifest),
                            "movie_frame_dir": str(movie_dir),
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = runner.execute(op, "OUTPUT = {'ok': True}\n", run_dir)

    assert result.ok is True
    assert len(calls) == 1
    assert (out_dir / "preview_frame.png").stat().st_size > 128
    assert (out_dir / "storyboard_000.png").stat().st_size > 128
    assert (out_dir / "storyboard_001.png").stat().st_size > 128
    assert (out_dir / "sequence_preview.gif").stat().st_size > 128
    assert (out_dir / "sequence_preview.mp4").stat().st_size > 1024
    preview_manifest = json.loads((out_dir / "preview_manifest.json").read_text(encoding="utf-8"))
    storyboard_manifest = json.loads((out_dir / "storyboard_manifest.json").read_text(encoding="utf-8"))
    assert preview_manifest["capture_success"] is True
    assert storyboard_manifest["capture_success"] is True
    assert preview_manifest["warnings"] == []
    assert storyboard_manifest["warnings"] == []
    assert preview_manifest["sequence_path"] == "/Game/AnimalHitchcockZoom"
    assert preview_manifest["fps"] == 24
    assert preview_manifest["start_frame"] == 0
    assert preview_manifest["end_frame"] == 25
    assert preview_manifest["frame_count"] == 25
    assert preview_manifest["movie_frame_count"] == 25
    assert preview_manifest["source_asset_id"] == "asset_ue_project_content_animalhitchcockzoom"
    assert preview_manifest["source_asset_type"] == "level_sequence"
    assert storyboard_manifest["frame_count"] == 25


def test_unreal_runner_renders_reference_capture_without_unreal_subprocess(tmp_path: Path, monkeypatch):
    import imageio.v2 as imageio
    import numpy as np

    run_dir = tmp_path / "runs" / "run_reference_capture"
    out_dir = run_dir / "artifacts"
    (run_dir / "snapshots").mkdir(parents=True)
    state = initial_world_state()
    state["sequences"]["/Game/AnimalHitchcockZoom"] = {
        "sequence_path": "/Game/AnimalHitchcockZoom",
        "source_asset_id": "asset_ue_project_content_animalhitchcockzoom",
        "source_asset_type": "level_sequence",
        "fps": 30,
        "range": [0, 12],
        "camera_cuts": [
            {"camera_name": "NativeSequenceCamera", "shot_id": "shot_001", "start_frame": 0, "end_frame": 12}
        ],
    }
    atomic_write_json(run_dir / "snapshots" / "world_current.json", state)
    capture = tmp_path / "CityParkEnv55" / "Saved" / "VideoCaptures" / "Showcase_(2).avi"
    capture.parent.mkdir(parents=True)
    frames = [np.full((36, 64, 3), (frame * 10, 80, 200 - frame), dtype=np.uint8) for frame in range(24)]
    imageio.mimsave(str(capture), frames, fps=60, macro_block_size=1)

    uproject = tmp_path / "unreal_project" / "Demo.uproject"
    (uproject.parent / "Plugins" / "CineUDemo" / "Content" / "Python").mkdir(parents=True)
    uproject.write_text("{}", encoding="utf-8")
    runner = UnrealCommandRunner("D:/UE_5.5/Engine/Binaries/Win64/UnrealEditor-Cmd.exe", uproject)
    op = Operation(
        op_id="0003_render_preview",
        node_id="render.preview",
        agent="RenderAgent",
        type="render.preview",
        template_id="render.preview.v1",
        inputs={
            "output_dir": str(out_dir),
            "sequence_path": "/Game/AnimalHitchcockZoom",
            "world_state_path": str(run_dir / "snapshots" / "world_current.json"),
            "format": "mp4",
            "quality": "preview",
            "resolution": [64, 36],
            "fps": 30,
            "start_frame": 0,
            "end_frame": 12,
            "reference_capture_source": str(capture),
            "reference_capture_start_frame": 2,
            "reference_capture_end_frame": 22,
        },
    )

    def fail_run(*_args, **_kwargs):
        raise AssertionError("reference capture render must not launch Unreal")

    monkeypatch.setattr(subprocess, "run", fail_run)

    result = runner.execute(op, "OUTPUT = {'ok': True}\n", run_dir)

    assert result.ok is True
    movie_frames = sorted((out_dir / "movie_frames").glob("movie_frame_*.png"))
    assert len(movie_frames) == 12
    assert Image.open(movie_frames[0]).size == (64, 36)
    first_mean = Image.open(movie_frames[0]).convert("RGB").resize((1, 1)).getpixel((0, 0))
    last_mean = Image.open(movie_frames[-1]).convert("RGB").resize((1, 1)).getpixel((0, 0))
    assert abs(first_mean[0] - 20) < 18
    assert last_mean[0] > 190
    assert (out_dir / "preview_frame.png").stat().st_size > 128
    assert (out_dir / "storyboard_000.png").stat().st_size > 128
    assert (out_dir / "sequence_preview.gif").stat().st_size > 128
    assert (out_dir / "sequence_preview.mp4").stat().st_size > 1024
    preview_manifest = json.loads((out_dir / "preview_manifest.json").read_text(encoding="utf-8"))
    storyboard_manifest = json.loads((out_dir / "storyboard_manifest.json").read_text(encoding="utf-8"))
    assert preview_manifest["render_backend"] == "reference_capture_video"
    assert preview_manifest["source_capture_path"] == str(capture)
    assert preview_manifest["source_frame_range"] == [2, 22]
    assert preview_manifest["fps"] == 30
    assert preview_manifest["start_frame"] == 0
    assert preview_manifest["end_frame"] == 12
    assert preview_manifest["frame_count"] == 12
    assert preview_manifest["movie_frame_count"] == 12
    assert storyboard_manifest["render_backend"] == "reference_capture_video"
    assert len(storyboard_manifest["frames"]) == 9
    render = runner.load_state(run_dir)["renders"][-1]
    assert render["render_backend"] == "reference_capture_video"
    assert render["sequence_preview_mp4"]["source_frame_count"] == 12
    assert render["artifacts"]["sequence_preview.mp4"] == str(out_dir / "sequence_preview.mp4")


def test_unreal_runner_final_quality_bypasses_reference_capture_and_launches_unreal(tmp_path: Path, monkeypatch):
    import imageio.v2 as imageio
    import numpy as np

    run_dir = tmp_path / "runs" / "run_final_reference_capture"
    out_dir = run_dir / "artifacts"
    (run_dir / "snapshots").mkdir(parents=True)
    state = initial_world_state()
    state["sequences"]["/Game/AnimalHitchcockZoom"] = {
        "sequence_path": "/Game/AnimalHitchcockZoom",
        "source_asset_id": "asset_ue_project_content_animalhitchcockzoom",
        "source_asset_type": "level_sequence",
        "fps": 30,
        "range": [0, 6],
        "camera_cuts": [
            {"camera_name": "NativeSequenceCamera", "shot_id": "shot_001", "start_frame": 0, "end_frame": 6}
        ],
    }
    atomic_write_json(run_dir / "snapshots" / "world_current.json", state)
    capture = tmp_path / "CityParkEnv55" / "Saved" / "VideoCaptures" / "Showcase_(2).avi"
    capture.parent.mkdir(parents=True)
    imageio.mimsave(str(capture), [np.full((36, 64, 3), 80, dtype=np.uint8) for _ in range(8)], fps=60, macro_block_size=1)

    uproject = tmp_path / "unreal_project" / "Demo.uproject"
    (uproject.parent / "Plugins" / "CineUDemo" / "Content" / "Python").mkdir(parents=True)
    uproject.write_text("{}", encoding="utf-8")
    runner = UnrealCommandRunner("D:/UE_5.5/Engine/Binaries/Win64/UnrealEditor-Cmd.exe", uproject)
    op = Operation(
        op_id="0003_render_preview_final",
        node_id="render.preview",
        agent="RenderAgent",
        type="render.preview",
        template_id="render.preview.v1",
        inputs={
            "output_dir": str(out_dir),
            "sequence_path": "/Game/AnimalHitchcockZoom",
            "world_state_path": str(run_dir / "snapshots" / "world_current.json"),
            "format": "png",
            "quality": "final",
            "resolution": [64, 36],
            "fps": 30,
            "start_frame": 0,
            "end_frame": 6,
            "reference_capture_source": str(capture),
            "reference_capture_start_frame": 2,
            "reference_capture_end_frame": 7,
        },
    )
    calls = []

    def fake_run(cmd, capture_output, text, timeout, check):
        calls.append(cmd)
        out_dir.mkdir(parents=True, exist_ok=True)
        frame = out_dir / "storyboard_000.png"
        preview = out_dir / "preview_frame.png"
        Image.new("RGB", (128, 72), color=(10, 120, 220)).save(frame)
        Image.new("RGB", (128, 72), color=(10, 120, 220)).save(preview)
        storyboard_manifest = out_dir / "storyboard_manifest.json"
        preview_manifest = out_dir / "preview_manifest.json"
        storyboard_manifest.write_text(
            json.dumps(
                {
                    "render_backend": "sequencer_movie_capture",
                    "sequence_path": "/Game/AnimalHitchcockZoom",
                    "frames": [{"frame": 0, "artifact": str(frame), "artifact_name": frame.name}],
                    "warnings": [],
                }
            ),
            encoding="utf-8",
        )
        preview_manifest.write_text(
            json.dumps(
                {
                    "render_backend": "sequencer_movie_capture",
                    "sequence_path": "/Game/AnimalHitchcockZoom",
                    "preview_frame": 0,
                    "storyboard_frames": [{"frame": 0, "artifact": str(frame), "artifact_name": frame.name}],
                    "artifacts": {
                        "preview_frame.png": str(preview),
                        "preview_manifest.json": str(preview_manifest),
                        "storyboard_manifest.json": str(storyboard_manifest),
                    },
                    "warnings": [],
                }
            ),
            encoding="utf-8",
        )
        result_path = run_dir / "traces" / "0003_render_preview_final_unreal_result.json"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(
            json.dumps(
                {
                    "ok": True,
                    "output": {
                        "render_backend": "sequencer_movie_capture",
                        "preview_frame": 0,
                        "artifacts": {
                            "preview_frame.png": str(preview),
                            "preview_manifest.json": str(preview_manifest),
                            "storyboard_manifest.json": str(storyboard_manifest),
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = runner.execute(op, "OUTPUT = {'ok': True}\n", run_dir)

    assert result.ok is True
    assert len(calls) == 1
    preview_manifest = json.loads((out_dir / "preview_manifest.json").read_text(encoding="utf-8"))
    assert preview_manifest["render_backend"] == "sequencer_movie_capture"


def test_unreal_runner_falls_back_to_unreal_when_reference_capture_missing(tmp_path: Path, monkeypatch):
    run_dir = tmp_path / "runs" / "run_missing_reference_capture"
    out_dir = run_dir / "artifacts"
    (run_dir / "snapshots").mkdir(parents=True)
    state = initial_world_state()
    state["sequences"]["/Game/AnimalHitchcockZoom"] = {
        "sequence_path": "/Game/AnimalHitchcockZoom",
        "source_asset_id": "asset_ue_project_content_animalhitchcockzoom",
        "source_asset_type": "level_sequence",
        "fps": 30,
        "range": [0, 6],
        "camera_cuts": [
            {"camera_name": "NativeSequenceCamera", "shot_id": "shot_001", "start_frame": 0, "end_frame": 6}
        ],
    }
    atomic_write_json(run_dir / "snapshots" / "world_current.json", state)
    uproject = tmp_path / "unreal_project" / "Demo.uproject"
    (uproject.parent / "Plugins" / "CineUDemo" / "Content" / "Python").mkdir(parents=True)
    uproject.write_text("{}", encoding="utf-8")
    runner = UnrealCommandRunner("D:/UE_5.5/Engine/Binaries/Win64/UnrealEditor-Cmd.exe", uproject)
    op = Operation(
        op_id="0003_render_preview",
        node_id="render.preview",
        agent="RenderAgent",
        type="render.preview",
        template_id="render.preview.v1",
        inputs={
            "output_dir": str(out_dir),
            "sequence_path": "/Game/AnimalHitchcockZoom",
            "world_state_path": str(run_dir / "snapshots" / "world_current.json"),
            "format": "png",
            "quality": "preview",
            "resolution": [64, 36],
            "fps": 30,
            "start_frame": 0,
            "end_frame": 6,
            "reference_capture_source": str(tmp_path / "CityParkEnv55" / "Saved" / "VideoCaptures" / "missing.avi"),
            "reference_capture_start_frame": 2,
            "reference_capture_end_frame": 22,
        },
    )
    calls = []

    def fake_run(cmd, capture_output, text, timeout, check):
        calls.append(cmd)
        out_dir.mkdir(parents=True, exist_ok=True)
        frame = out_dir / "storyboard_000.png"
        preview = out_dir / "preview_frame.png"
        Image.new("RGB", (128, 72), color=(10, 120, 220)).save(frame)
        Image.new("RGB", (128, 72), color=(10, 120, 220)).save(preview)
        storyboard_manifest = out_dir / "storyboard_manifest.json"
        preview_manifest = out_dir / "preview_manifest.json"
        storyboard_manifest.write_text(
            json.dumps(
                {
                    "sequence_path": "/Game/AnimalHitchcockZoom",
                    "frames": [{"frame": 0, "artifact": str(frame), "artifact_name": frame.name}],
                    "warnings": [],
                }
            ),
            encoding="utf-8",
        )
        preview_manifest.write_text(
            json.dumps(
                {
                    "sequence_path": "/Game/AnimalHitchcockZoom",
                    "preview_frame": 0,
                    "storyboard_frames": [{"frame": 0, "artifact": str(frame), "artifact_name": frame.name}],
                    "artifacts": {
                        "preview_frame.png": str(preview),
                        "preview_manifest.json": str(preview_manifest),
                        "storyboard_manifest.json": str(storyboard_manifest),
                    },
                    "warnings": [],
                }
            ),
            encoding="utf-8",
        )
        result_path = run_dir / "traces" / "0003_render_preview_unreal_result.json"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(
            json.dumps(
                {
                    "ok": True,
                    "output": {
                        "render_backend": "sequencer_movie_capture",
                        "preview_frame": 0,
                        "artifacts": {
                            "preview_frame.png": str(preview),
                            "preview_manifest.json": str(preview_manifest),
                            "storyboard_manifest.json": str(storyboard_manifest),
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = runner.execute(op, "OUTPUT = {'ok': True}\n", run_dir)

    assert result.ok is True
    assert len(calls) == 1
    render = runner.load_state(run_dir)["renders"][-1]
    assert render["artifacts"]["sequence_preview.gif"] == str(out_dir / "sequence_preview.gif")


def test_sequence_preview_mp4_writer_uses_storyboard_frames(tmp_path: Path):
    out_dir = tmp_path / "artifacts"
    out_dir.mkdir()
    frame_a = out_dir / "storyboard_000.png"
    frame_b = out_dir / "storyboard_001.png"
    Image.new("RGB", (128, 72), color=(255, 0, 0)).save(frame_a)
    Image.new("RGB", (128, 72), color=(0, 0, 255)).save(frame_b)
    manifest = out_dir / "storyboard_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "frames": [
                    {"artifact": str(frame_a), "artifact_name": "storyboard_000.png"},
                    {"artifact": str(frame_b), "artifact_name": "storyboard_001.png"},
                ]
            }
        ),
        encoding="utf-8",
    )

    result = _write_sequence_preview_mp4(out_dir, manifest)

    assert result["created"] is True
    assert result["artifact_name"] == "sequence_preview.mp4"
    assert result["animatic_frame_count"] == 16
    assert result["decoded_frame_count"] == 16
    assert (out_dir / "sequence_preview.mp4").stat().st_size > 1024


def test_sequence_preview_mp4_writer_rejects_corrupt_encoder_output(tmp_path: Path, monkeypatch):
    out_dir = tmp_path / "artifacts"
    out_dir.mkdir()
    frame = out_dir / "storyboard_000.png"
    Image.new("RGB", (128, 72), color=(64, 128, 192)).save(frame)
    manifest = out_dir / "storyboard_manifest.json"
    manifest.write_text(json.dumps({"frames": [{"artifact": str(frame), "artifact_name": frame.name}]}), encoding="utf-8")

    class CorruptWriter:
        def __init__(self, path, *args, **kwargs):
            self.path = Path(path)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self.path.write_bytes(b"not-a-real-mp4" * 200)

        def append_data(self, frame_data):
            pass

    def fake_get_writer(path, **kwargs):
        return CorruptWriter(path, **kwargs)

    fake_imageio_v2 = SimpleNamespace(get_writer=fake_get_writer)
    fake_imageio = SimpleNamespace(v2=fake_imageio_v2)
    monkeypatch.setitem(sys.modules, "imageio", fake_imageio)
    monkeypatch.setitem(sys.modules, "imageio.v2", fake_imageio_v2)

    result = _write_sequence_preview_mp4(out_dir, manifest)

    assert result["created"] is False
    assert result["reason"] == "mp4_validation_failed"
    assert result["artifact_name"] == "sequence_preview.mp4"
    assert not (out_dir / "sequence_preview.mp4").exists()


def test_movie_frame_mp4_writer_rejects_corrupt_encoder_output(tmp_path: Path, monkeypatch):
    out_dir = tmp_path / "artifacts"
    out_dir.mkdir()
    frame = out_dir / "movie_frame_0000.png"
    Image.new("RGB", (128, 72), color=(24, 96, 160)).save(frame)

    class CorruptWriter:
        def __init__(self, path, *args, **kwargs):
            self.path = Path(path)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self.path.write_bytes(b"not-a-real-mp4" * 200)

        def append_data(self, frame_data):
            pass

    def fake_get_writer(path, **kwargs):
        return CorruptWriter(path, **kwargs)

    fake_imageio_v2 = SimpleNamespace(get_writer=fake_get_writer)
    fake_imageio = SimpleNamespace(v2=fake_imageio_v2)
    monkeypatch.setitem(sys.modules, "imageio", fake_imageio)
    monkeypatch.setitem(sys.modules, "imageio.v2", fake_imageio_v2)

    result = _write_movie_frame_paths_mp4(out_dir, [frame], fps=24)

    assert result["created"] is False
    assert result["reason"] == "mp4_validation_failed"
    assert result["artifact_name"] == "sequence_preview.mp4"
    assert not (out_dir / "sequence_preview.mp4").exists()


def test_unreal_runner_mp4_preview_uses_native_movie_frames_when_available(tmp_path: Path):
    uproject = tmp_path / "Demo.uproject"
    uproject.write_text("", encoding="utf-8")
    runner = UnrealCommandRunner("D:/UE_5.5/Engine/Binaries/Win64/UnrealEditor-Cmd.exe", uproject)
    out_dir = tmp_path / "artifacts"
    movie_dir = out_dir / "movie_frames"
    movie_dir.mkdir(parents=True)
    for frame, color in [(10, (255, 0, 0)), (11, (0, 255, 0)), (12, (0, 0, 255))]:
        Image.new("RGB", (128, 72), color=color).save(movie_dir / f"movie_frame_{frame:04d}.png")
    storyboard_a = out_dir / "storyboard_000.png"
    storyboard_b = out_dir / "storyboard_001.png"
    Image.new("RGB", (128, 72), color=(32, 32, 32)).save(storyboard_a)
    Image.new("RGB", (128, 72), color=(64, 64, 64)).save(storyboard_b)
    (out_dir / "storyboard_manifest.json").write_text(
        json.dumps(
            {
                "render_backend": "sequencer_movie_capture",
                "fps": 30,
                "native_capture_frame_range": [10, 13],
                "movie_frame_dir": str(movie_dir),
                "frames": [
                    {"frame": 10, "artifact": str(storyboard_a), "artifact_name": "storyboard_000.png"},
                    {"frame": 12, "artifact": str(storyboard_b), "artifact_name": "storyboard_001.png"},
                ],
            }
        ),
        encoding="utf-8",
    )
    op = Operation(
        op_id="render_native",
        node_id="render.preview",
        agent="RenderAgent",
        type="render.preview",
        template_id="render.preview.v1",
        inputs={"output_dir": str(out_dir), "format": "mp4"},
    )

    result = runner._build_sequence_preview_mp4(op)

    assert result["created"] is True
    assert result["source_frame_count"] == 3
    assert result["fps"] == 30
    assert result["decoded_frame_count"] == 3


def test_unreal_runner_mp4_preview_uses_movie_render_pipeline_frames_when_available(tmp_path: Path):
    uproject = tmp_path / "Demo.uproject"
    uproject.write_text("", encoding="utf-8")
    runner = UnrealCommandRunner("D:/UE_5.5/Engine/Binaries/Win64/UnrealEditor-Cmd.exe", uproject)
    out_dir = tmp_path / "artifacts"
    movie_dir = out_dir / "movie_frames"
    movie_dir.mkdir(parents=True)
    for frame, color in [(10, (255, 0, 0)), (11, (0, 255, 0)), (12, (0, 0, 255))]:
        Image.new("RGB", (128, 72), color=color).save(movie_dir / f"movie_frame_{frame:04d}.png")
    (out_dir / "storyboard_manifest.json").write_text(
        json.dumps(
            {
                "render_backend": "movie_render_pipeline",
                "fps": 30,
                "movie_render_pipeline_frame_range": [10, 13],
                "native_capture_frame_range": [10, 13],
                "movie_frame_dir": str(movie_dir),
                "frames": [
                    {"frame": 10, "artifact": str(out_dir / "storyboard_000.png"), "artifact_name": "storyboard_000.png"},
                    {"frame": 12, "artifact": str(out_dir / "storyboard_001.png"), "artifact_name": "storyboard_001.png"},
                ],
            }
        ),
        encoding="utf-8",
    )
    op = Operation(
        op_id="render_mrq",
        node_id="render.preview",
        agent="RenderAgent",
        type="render.preview",
        template_id="render.preview.v1",
        inputs={"output_dir": str(out_dir), "format": "mp4"},
    )

    result = runner._build_sequence_preview_mp4(op)

    assert result["created"] is True
    assert result["artifact_name"] == "sequence_preview.mp4"
    assert result["fps"] == 30
    assert result["source_frame_count"] == 3
    assert result["decoded_frame_count"] == 3


def test_unreal_runner_mp4_preview_uses_movie_render_pipeline_output_frame_map(tmp_path: Path):
    uproject = tmp_path / "Demo.uproject"
    uproject.write_text("", encoding="utf-8")
    runner = UnrealCommandRunner("D:/UE_5.5/Engine/Binaries/Win64/UnrealEditor-Cmd.exe", uproject)
    out_dir = tmp_path / "artifacts"
    movie_dir = out_dir / "movie_frames"
    movie_dir.mkdir(parents=True)
    frame_map = []
    for output_frame, source_frame in zip(range(5, 15), range(10, 30, 2)):
        file_name = f"movie_frame_{output_frame:04d}.png"
        Image.new("RGB", (128, 72), color=(output_frame, 80, 160)).save(movie_dir / file_name)
        frame_map.append({"output_frame": output_frame, "source_frame": source_frame, "file_name": file_name})
    (out_dir / "storyboard_manifest.json").write_text(
        json.dumps(
            {
                "render_backend": "movie_render_pipeline",
                "fps": 30,
                "native_capture_frame_range": [10, 30],
                "movie_render_pipeline_output_frame_range": [5, 15],
                "movie_render_pipeline_output_frame_map": frame_map,
                "movie_frame_dir": str(movie_dir),
                "frames": [
                    {"frame": 5, "source_frame": 10, "artifact": str(out_dir / "storyboard_000.png"), "artifact_name": "storyboard_000.png"},
                    {"frame": 14, "source_frame": 28, "artifact": str(out_dir / "storyboard_001.png"), "artifact_name": "storyboard_001.png"},
                ],
            }
        ),
        encoding="utf-8",
    )
    op = Operation(
        op_id="render_mrq_output_rate",
        node_id="render.preview",
        agent="RenderAgent",
        type="render.preview",
        template_id="render.preview.v1",
        inputs={"output_dir": str(out_dir), "format": "mp4", "fps": 30, "start_frame": 0, "end_frame": 166},
    )

    result = runner._build_sequence_preview_mp4(op)

    assert result["created"] is True
    assert result["source_frame_count"] == 10
    assert result["input_movie_frame_count"] == 10
    assert result["frame_map_used"] is True
    assert result["skipped"] == []
    assert result["decoded_frame_count"] == 10
    assert result["fps"] == 30


def test_unreal_runner_mp4_preview_resamples_native_source_range_to_output_frame_count(tmp_path: Path):
    uproject = tmp_path / "Demo.uproject"
    uproject.write_text("", encoding="utf-8")
    runner = UnrealCommandRunner("D:/UE_5.5/Engine/Binaries/Win64/UnrealEditor-Cmd.exe", uproject)
    out_dir = tmp_path / "artifacts"
    movie_dir = out_dir / "movie_frames"
    movie_dir.mkdir(parents=True)
    for frame in range(10, 16):
        Image.new("RGB", (128, 72), color=(frame, 80, 160)).save(movie_dir / f"movie_frame_{frame:04d}.png")
    (out_dir / "storyboard_manifest.json").write_text(
        json.dumps(
            {
                "render_backend": "sequencer_movie_capture",
                "fps": 30,
                "native_capture_frame_range": [10, 16],
                "movie_frame_dir": str(movie_dir),
                "frames": [
                    {"frame": 10, "artifact": str(out_dir / "storyboard_000.png"), "artifact_name": "storyboard_000.png"},
                    {"frame": 15, "artifact": str(out_dir / "storyboard_001.png"), "artifact_name": "storyboard_001.png"},
                ],
            }
        ),
        encoding="utf-8",
    )
    op = Operation(
        op_id="render_native_resampled",
        node_id="render.preview",
        agent="RenderAgent",
        type="render.preview",
        template_id="render.preview.v1",
        inputs={"output_dir": str(out_dir), "format": "mp4", "fps": 30, "start_frame": 0, "end_frame": 3},
    )

    result = runner._build_sequence_preview_mp4(op)

    assert result["created"] is True
    assert result["source_frame_count"] == 3
    assert result["input_movie_frame_count"] == 6
    assert result["resampled"] is True
    assert result["decoded_frame_count"] == 3
    assert result["fps"] == 30
