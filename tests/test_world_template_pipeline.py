import json
from pathlib import Path

import pytest

from cineu_demo.demo_workspace import create_demo_workspace
from cineu_demo.engine import CineUOrchestrator


def test_city_rooftop_template_pipeline_builds_hitchcock_and_orbit(tmp_path: Path):
    workspace = tmp_path / "workspace"
    create_demo_workspace(workspace, overwrite=True)

    run_dir = CineUOrchestrator(workspace=workspace, knowledge_dir=Path("knowledge")).run(
        "Cityscape. Man on a rooftop is on the phone. Hitchcock zoom, followed by an orbit shot."
    )

    report = json.loads((run_dir / "verification" / "final_report.json").read_text(encoding="utf-8"))
    assert report["success"] is True

    state = json.loads((run_dir / "snapshots" / "world_final.json").read_text(encoding="utf-8"))
    assert "rooftop_floor" in state["support_surfaces"]
    seq = next(iter(state["sequences"].values()))
    assert [cut["shot_id"] for cut in seq["camera_cuts"]] == ["shot_001", "shot_002"]
    assert "CAM_shot_001" in seq["cameras"]
    assert "CAM_shot_002" in seq["cameras"]
    assert len(seq["cameras"]["CAM_shot_001"]["focal_length_keys"]) == 8
    orbit_locations = [key["location"] for key in seq["cameras"]["CAM_shot_002"]["transform_keys"]]
    assert len(orbit_locations) >= 5
    assert orbit_locations[0][0] != orbit_locations[-1][0]
    assert "phone_actor_01" in seq["animation_tracks"]


@pytest.mark.parametrize(
    ("prompt", "environment"),
    [
        ("Large building. External wide shot to push-in, revealing a car parked inside.", "large_building"),
        ("River scene and two statue. Focus: one statue above water, then the other underwater.", "river"),
        ("In a park, a zebra is moving forward. The camera focuses on the zebra for Hitchcock zoom.", "park"),
        ("All-angles tour: gallery entry to exit.", "gallery"),
    ],
)
def test_world_template_reference_prompts_run_in_mock_pipeline(tmp_path: Path, prompt: str, environment: str):
    workspace = tmp_path / "workspace"
    create_demo_workspace(workspace, overwrite=True)

    run_dir = CineUOrchestrator(workspace=workspace, knowledge_dir=Path("knowledge")).run(prompt)

    report = json.loads((run_dir / "verification" / "final_report.json").read_text(encoding="utf-8"))
    task = json.loads((run_dir / "planning" / "task_spec.json").read_text(encoding="utf-8"))
    state = json.loads((run_dir / "snapshots" / "world_final.json").read_text(encoding="utf-8"))
    assert report["success"] is True
    assert task["scene"]["environment"] == environment
    assert state["support_surfaces"]
    assert next(iter(state["sequences"].values()))["camera_cuts"]


def test_park_hitchcock_uses_reference_level_sequence_when_available(tmp_path: Path):
    workspace = tmp_path / "workspace"
    create_demo_workspace(workspace, overwrite=True)
    content = tmp_path / "CityParkEnv55" / "Content"
    (content / "CityPark" / "Maps").mkdir(parents=True)
    (content / "AfricanAnimalsPack" / "Zebra" / "Meshes").mkdir(parents=True)
    (content / "AfricanAnimalsPack" / "Zebra" / "Animations").mkdir(parents=True)
    (content / "AfricanAnimalsPack" / "Zebra" / "Materials").mkdir(parents=True)
    (content / "CityPark" / "Maps" / "Showcase.umap").write_bytes(b"showcase")
    (content / "AfricanAnimalsPack" / "Zebra" / "Meshes" / "SK_Zebra.uasset").write_bytes(b"mesh")
    (content / "AfricanAnimalsPack" / "Zebra" / "Animations" / "ANIM_Zebra_WalkTurnR.uasset").write_bytes(b"walk turn anim")
    (content / "AfricanAnimalsPack" / "Zebra" / "Materials" / "M_Zebra.uasset").write_bytes(b"material")
    (content / "AnimalHitchcockZoom.uasset").write_bytes(b"sequence")
    (content / "AnimalHitchcockZoom_ablation.uasset").write_bytes(b"subject framed sequence")
    capture = tmp_path / "CityParkEnv55" / "Saved" / "VideoCaptures" / "Showcase_(2).avi"
    capture.parent.mkdir(parents=True)
    capture.write_bytes(b"existing citypark capture")

    run_dir = CineUOrchestrator(workspace=workspace, knowledge_dir=Path("knowledge")).run(
        "In a park, a zebra is moving forward. The camera focuses on the zebra for Hitchcock zoom."
    )

    state = json.loads((run_dir / "snapshots" / "world_final.json").read_text(encoding="utf-8"))
    park_path = state["support_surfaces"]["park_path"]
    asset_index = json.loads((run_dir / "planning" / "local_asset_index_snapshot.json").read_text(encoding="utf-8"))
    index_env_paths = {asset["ue_path"] for asset in asset_index["environment_candidates"]}
    index_sequence_paths = {asset["ue_path"] for asset in asset_index["sequence_candidates"]}
    assert asset_index["schema_version"] == "cineu.run_asset_index_snapshot.v1"
    assert asset_index["asset_first_ready"] is True
    assert "/Game/CityPark/Maps/Showcase" in index_env_paths
    assert "/Game/AnimalHitchcockZoom" in index_sequence_paths
    assert park_path["z"] == -630.004
    assert park_path["anchor_actor"] == "InstancedFoliageActor2"
    assert park_path["bounds"] == [5600.0, 6800.0, -12650.0, -11850.0]
    task_spec = json.loads((run_dir / "planning" / "task_spec.json").read_text(encoding="utf-8"))
    plan = json.loads((run_dir / "planning" / "operations_plan.json").read_text(encoding="utf-8"))
    op_types = [op["type"] for op in plan["operations"]]
    assert task_spec["entities"][0]["animation"]["type"] == "walk"
    assert task_spec["entities"][0]["animation"]["preferred_asset_path"] == "/Game/AfricanAnimalsPack/Zebra/Animations/ANIM_Zebra_WalkTurnR"
    assert task_spec["entities"][0]["animation"]["reference_yaw"] == 0.0
    assert "sequence.use_existing" in op_types
    assert "sequence.init" not in op_types
    assert "camera.hitchcock_zoom" not in op_types
    assert "animation.add_tracks" not in op_types
    render_op = next(op for op in plan["operations"] if op["type"] == "render.preview")
    assert render_op["inputs"]["fps"] == 30
    assert render_op["inputs"]["end_frame"] == 320
    assert render_op["inputs"]["reference_capture_source"] == str(capture.resolve())
    assert render_op["inputs"]["reference_capture_start_frame"] == 10
    assert render_op["inputs"]["reference_capture_end_frame"] == 330
    assert render_op["inputs"]["native_capture_start_frame"] == 10
    assert render_op["inputs"]["native_capture_end_frame"] == 330
    assert "/Game/AnimalHitchcockZoom" in state["sequences"]
    seq = state["sequences"]["/Game/AnimalHitchcockZoom"]
    assert seq["sequence_path"] == "/Game/AnimalHitchcockZoom"
    assert seq["camera_cuts"] == [{"camera_name": "NativeSequenceCamera", "shot_id": "shot_001", "start_frame": 0, "end_frame": 320}]


def test_park_hitchcock_keeps_sequencer_render_fallback_when_reference_capture_missing(tmp_path: Path):
    workspace = tmp_path / "workspace"
    create_demo_workspace(workspace, overwrite=True)
    content = tmp_path / "CityParkEnv55" / "Content"
    (content / "CityPark" / "Maps").mkdir(parents=True)
    (content / "AfricanAnimalsPack" / "Zebra" / "Meshes").mkdir(parents=True)
    (content / "AfricanAnimalsPack" / "Zebra" / "Animations").mkdir(parents=True)
    (content / "AfricanAnimalsPack" / "Zebra" / "Materials").mkdir(parents=True)
    (content / "CityPark" / "Maps" / "Showcase.umap").write_bytes(b"showcase")
    (content / "AfricanAnimalsPack" / "Zebra" / "Meshes" / "SK_Zebra.uasset").write_bytes(b"mesh")
    (content / "AfricanAnimalsPack" / "Zebra" / "Animations" / "ANIM_Zebra_WalkTurnR.uasset").write_bytes(b"walk turn anim")
    (content / "AfricanAnimalsPack" / "Zebra" / "Materials" / "M_Zebra.uasset").write_bytes(b"material")
    (content / "AnimalHitchcockZoom.uasset").write_bytes(b"sequence")

    run_dir = CineUOrchestrator(workspace=workspace, knowledge_dir=Path("knowledge")).run(
        "In a park, a zebra is moving forward. The camera focuses on the zebra for Hitchcock zoom."
    )

    plan = json.loads((run_dir / "planning" / "operations_plan.json").read_text(encoding="utf-8"))
    render_op = next(op for op in plan["operations"] if op["type"] == "render.preview")
    assert render_op["inputs"]["sequence_path"] == "/Game/AnimalHitchcockZoom"
    assert render_op["inputs"]["fps"] == 30
    assert render_op["inputs"]["end_frame"] == 166
    assert render_op["inputs"]["native_capture_start_frame"] == 10
    assert render_op["inputs"]["native_capture_end_frame"] == 330
    assert "reference_capture_source" not in render_op["inputs"]
