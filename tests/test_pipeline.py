import json
from pathlib import Path

from cineu_demo.demo_workspace import create_demo_workspace
from cineu_demo.engine import CineUOrchestrator


def test_gallery_pipeline_mock(tmp_path: Path):
    workspace = tmp_path / "workspace"
    create_demo_workspace(workspace, overwrite=True)
    orchestrator = CineUOrchestrator(workspace=workspace, knowledge_dir=Path("knowledge"))
    run_dir = orchestrator.run("创建一个现代画廊，三幅画和一个雕塑，镜头推进后广角俯拍。")
    report = json.loads((run_dir / "verification" / "final_report.json").read_text(encoding="utf-8"))
    assert report["success"] is True
    assert (run_dir / "artifacts" / "preview_frame.png").exists()
    assert (run_dir / "artifacts" / "sequence_preview.gif").exists()
    state = json.loads((run_dir / "snapshots" / "world_final.json").read_text(encoding="utf-8"))
    assert "sculpture_01" in state["actors"]
    sculpture_extent = state["actors"]["sculpture_01"]["bounds_extent"]
    assert sculpture_extent[0] <= 45.0
    assert sculpture_extent[2] <= 95.0
    painting_extents = [state["actors"][name]["bounds_extent"] for name in ["painting_01", "painting_02", "painting_03"]]
    assert all(extent[1] >= 120.0 and extent[2] >= 80.0 for extent in painting_extents)
    assert [state["actors"][name]["spatial_relation"]["target"] for name in ["painting_01", "painting_02", "painting_03"]] == ["back_wall", "back_wall", "back_wall"]
    painting_xs = [state["actors"][name]["transform"]["location"][0] for name in ["painting_01", "painting_02", "painting_03"]]
    assert all(
        (right_x - left_x) >= (left_extent[1] + right_extent[1] + 30.0)
        for left_x, right_x, left_extent, right_extent in zip(painting_xs, painting_xs[1:], painting_extents, painting_extents[1:])
    )
    assert len(state["sequences"]) == 1
    seq = next(iter(state["sequences"].values()))
    assert len(seq["camera_cuts"]) >= 4
    assert {"CAM_shot_001", "CAM_shot_002", "CAM_shot_003", "CAM_shot_004"}.issubset(seq["cameras"])
    dolly_camera = seq["cameras"]["CAM_shot_001"]
    dolly_locations = [key["location"] for key in dolly_camera["transform_keys"]]
    assert all(-450.0 <= loc[0] <= 450.0 and -720.0 <= loc[1] <= 450.0 for loc in dolly_locations)
    assert abs(dolly_locations[0][0]) <= 80.0
    assert dolly_locations[0][1] <= -620.0
    assert 150.0 <= dolly_locations[0][2] <= 180.0
    assert -390.0 <= dolly_locations[-1][1] <= -320.0
    assert dolly_camera["transform_keys"][0]["rotation"][0] <= -3.0
    assert dolly_camera["focal_length_keys"][0]["focal_length"] <= 28.0
    artwork_camera = seq["cameras"]["CAM_shot_002"]
    assert artwork_camera["target_actor"] == "painting_02"
    artwork_locations = [key["location"] for key in artwork_camera["transform_keys"]]
    assert all(40.0 <= loc[1] <= 330.0 and 150.0 <= loc[2] <= 230.0 for loc in artwork_locations)
    assert artwork_camera["focal_length_keys"][0]["focal_length"] >= 32.0
    wide_locations = [key["location"] for key in seq["cameras"]["CAM_shot_003"]["transform_keys"]]
    assert all(-450.0 <= loc[0] <= 450.0 and -450.0 <= loc[1] <= 450.0 and loc[2] >= 320.0 for loc in wide_locations)
    exit_locations = [key["location"] for key in seq["cameras"]["CAM_shot_004"]["transform_keys"]]
    assert -390.0 <= exit_locations[0][1] <= -320.0
    assert exit_locations[-1][1] <= -620.0
    exit_yaws = [key["rotation"][2] for key in seq["cameras"]["CAM_shot_004"]["transform_keys"]]
    assert all(yaw >= 70.0 for yaw in exit_yaws)


def test_zebra_pipeline_mock(tmp_path: Path):
    workspace = tmp_path / "workspace"
    create_demo_workspace(workspace, overwrite=True)
    orchestrator = CineUOrchestrator(workspace=workspace, knowledge_dir=Path("knowledge"))
    run_dir = orchestrator.run("创建黄昏沙漠场景，一只斑马从左到右移动，镜头做 Hitchcock zoom。")
    report = json.loads((run_dir / "verification" / "final_report.json").read_text(encoding="utf-8"))
    assert report["success"] is True
    state = json.loads((run_dir / "snapshots" / "world_final.json").read_text(encoding="utf-8"))
    seq = next(iter(state["sequences"].values()))
    cam = seq["cameras"]["CAM_shot_001"]
    assert len(cam["focal_length_keys"]) == 8
    assert "zebra_01" in seq["animation_tracks"]
