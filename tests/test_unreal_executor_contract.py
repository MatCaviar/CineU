from __future__ import annotations

import json
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1] / "unreal_project" / "Plugins" / "CineUDemo" / "Content" / "Python"


def test_executor_writes_success_result(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    from cineu_executor import execute_generated_script

    script = tmp_path / "script.py"
    script.write_text(
        "PARAMS = {'operation_type': 'env.setup', 'inputs': {'level_name': 'LVL_x'}}\nOUTPUT = {'level': 'LVL_x'}\n",
        encoding="utf-8",
    )
    state_path = tmp_path / "world_current.json"
    result_path = tmp_path / "result.json"

    result = execute_generated_script(str(script), str(state_path), str(result_path))

    assert result["ok"] is True
    assert json.loads(result_path.read_text(encoding="utf-8"))["ok"] is True
    assert json.loads(state_path.read_text(encoding="utf-8"))["schema_version"] == "cineu.world_state.v1"


def test_executor_writes_failure_result(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    from cineu_executor import execute_generated_script

    script = tmp_path / "bad_script.py"
    script.write_text("raise RuntimeError('boom')\n", encoding="utf-8")
    state_path = tmp_path / "world_current.json"
    result_path = tmp_path / "result.json"

    try:
        execute_generated_script(str(script), str(state_path), str(result_path))
    except RuntimeError:
        pass

    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["ok"] is False
    assert result["error"]["type"] == "RuntimeError"
    assert "boom" in result["error"]["message"]
    assert json.loads(state_path.read_text(encoding="utf-8"))["schema_version"] == "cineu.world_state.v1"


def test_executor_passes_params_output_and_result_to_state_dump(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_executor

    script = tmp_path / "script.py"
    script.write_text(
        "PARAMS = {'operation_type': 'env.setup', 'inputs': {'level_name': 'LVL_x'}}\nOUTPUT = {'level': 'LVL_x'}\n",
        encoding="utf-8",
    )
    state_path = tmp_path / "world_current.json"
    result_path = tmp_path / "result.json"
    captured = {}

    def fake_dump(path, params=None, output=None, result=None):
        captured["path"] = path
        captured["params"] = params
        captured["output"] = output
        captured["result"] = result
        Path(path).write_text(json.dumps({"schema_version": "cineu.world_state.v1"}), encoding="utf-8")
        return {"schema_version": "cineu.world_state.v1"}

    monkeypatch.setattr(cineu_executor, "dump_world_state_to_file", fake_dump)

    cineu_executor.execute_generated_script(str(script), str(state_path), str(result_path))

    assert captured["path"] == str(state_path)
    assert captured["params"]["operation_type"] == "env.setup"
    assert captured["output"] == {"level": "LVL_x"}
    assert captured["result"]["ok"] is True


def test_executor_rehydrates_world_state_before_running_script(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_executor

    marker = tmp_path / "rehydrated.txt"

    def fake_rehydrate(path):
        marker.write_text(path, encoding="utf-8")

    monkeypatch.setattr(cineu_executor, "_rehydrate_world_state", fake_rehydrate, raising=False)
    script = tmp_path / "script.py"
    script.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                f"assert Path({str(marker)!r}).exists()",
                "PARAMS = {'operation_type': 'spatial.apply_transforms', 'inputs': {'placements': []}}",
                "OUTPUT = {'transformed': []}",
            ]
        ),
        encoding="utf-8",
    )
    state_path = tmp_path / "world_current.json"
    result_path = tmp_path / "result.json"

    cineu_executor.execute_generated_script(str(script), str(state_path), str(result_path))

    assert marker.read_text(encoding="utf-8") == str(state_path)


def test_executor_treats_gallery_detail_actors_as_rehydratable(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    from cineu_executor import _is_planned_actor

    assert _is_planned_actor({"name": "CineU_Gallery_Label_painting_01"})
    assert _is_planned_actor({"name": "CineU_Gallery_ArtAccent_painting_01"})
    assert _is_planned_actor({"name": "CineU_Gallery_ArtStripe_painting_01_00"})
    assert _is_planned_actor({"name": "CineU_Gallery_ArtBrushLight_painting_01_00"})
    assert _is_planned_actor({"name": "CineU_Gallery_ArtBrushShadow_painting_01_00"})
    assert _is_planned_actor({"name": "CineU_Gallery_ArtFlowLight_painting_02_00"})
    assert _is_planned_actor({"name": "CineU_Gallery_HeroBackdrop_painting_02"})
    assert _is_planned_actor({"name": "CineU_Gallery_LightPatch_00"})
    assert _is_planned_actor({"name": "CineU_Gallery_EntryGlass_00"})
    assert _is_planned_actor({"name": "CineU_Gallery_WindowPane_Right_00"})
    assert _is_planned_actor({"name": "CineU_Gallery_WindowMullion_Right_00"})
    assert _is_planned_actor({"name": "CineU_Gallery_CeilingBeam_Long_00"})
    assert _is_planned_actor({"name": "CineU_Gallery_SkylightPane_00"})
    assert _is_planned_actor({"name": "CineU_Gallery_ExteriorWalkway"})
    assert _is_planned_actor({"name": "CineU_Gallery_ExteriorLawn_Left"})


def test_executor_treats_zebra_detail_actors_as_rehydratable(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    from cineu_executor import _is_planned_actor

    assert _is_planned_actor({"name": "CineU_Zebra_Stripe_zebra_01_00"})
    assert _is_planned_actor({"name": "CineU_Zebra_Stripe_zebra_01_leg_00"})


def test_executor_treats_level_park_asset_dressing_as_rehydratable(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    from cineu_executor import _is_planned_actor

    assert _is_planned_actor({"name": "CineU_LevelPark_ForegroundWillow_Right_00"})
    assert _is_planned_actor({"name": "CineU_LevelPark_CanopyWillow_Right_00"})
    assert _is_planned_actor({"name": "CineU_LevelPark_HangingIvy_Right_00"})
    assert _is_planned_actor({"name": "CineU_LevelPark_ImportedCanopy_Left_00"})


def test_actor_scan_extracts_static_mesh_asset_path_for_rehydration(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    from cineu_verify_ops import _static_mesh_asset_path_from_actor

    class Mesh:
        def get_path_name(self):
            return "/Game/ExternalAssets/Twinmotion/Vegetation/Trees/XF_FicusBenjamina/SM_A_FicusBenjamina_LOD0"

    class Component:
        def get_editor_property(self, name):
            if name == "static_mesh":
                return Mesh()
            raise AttributeError(name)

    class Actor:
        def get_editor_property(self, name):
            if name == "static_mesh_component":
                return Component()
            raise AttributeError(name)

    assert (
        _static_mesh_asset_path_from_actor(Actor())
        == "/Game/ExternalAssets/Twinmotion/Vegetation/Trees/XF_FicusBenjamina/SM_A_FicusBenjamina_LOD0"
    )


def test_state_dump_preserves_spawn_actor_native_materials(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    from cineu_verify_ops import dump_world_state_to_file

    state_path = tmp_path / "world_current.json"
    params = {
        "operation_type": "entity.spawn_many",
        "inputs": {
            "actors": [
                {
                    "actor_name": "zebra_01",
                    "semantic_type": "zebra",
                    "asset_id": "asset_zebra",
                    "asset_path": "/Game/AfricanAnimalsPack/Zebra/Meshes/SK_Zebra",
                    "asset_type": "skeletal_mesh",
                    "materials": ["/Game/AfricanAnimalsPack/Zebra/Materials/M_Zebra"],
                    "bounds_extent": [115.0, 35.0, 85.0],
                }
            ]
        },
    }

    state = dump_world_state_to_file(str(state_path), params=params, output={"created_actors": ["zebra_01"]})

    assert state["actors"]["zebra_01"]["materials"] == ["/Game/AfricanAnimalsPack/Zebra/Materials/M_Zebra"]


def test_executor_rehydrates_imported_environment_asset(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_executor
    import cineu_world_ops

    calls = []
    state_path = tmp_path / "world_current.json"
    state_path.write_text(
        json.dumps(
            {
                "schema_version": "cineu.world_state.v1",
                "support_surfaces": {"park_path": {"type": "ground"}},
                "environment_asset": {"asset_id": "asset_local_file_hillpath_lo", "ue_path": "/Game/CineU/Imported/local_file/hillpath_lo"},
                "actors": {},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(cineu_world_ops, "ensure_support_surfaces", lambda surfaces: calls.append(("surfaces", surfaces)))
    monkeypatch.setattr(cineu_world_ops, "ensure_actor_from_state", lambda actor_name, spec: calls.append(("actor", actor_name)))
    monkeypatch.setattr(cineu_world_ops, "_spawn_environment_asset_if_available", lambda asset: calls.append(("environment_asset", asset)))

    cineu_executor._rehydrate_world_state(str(state_path))

    assert ("environment_asset", {"asset_id": "asset_local_file_hillpath_lo", "ue_path": "/Game/CineU/Imported/local_file/hillpath_lo"}) in calls


def test_executor_rehydrates_level_environment_before_support_surfaces(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_executor
    import cineu_world_ops

    calls = []
    state_path = tmp_path / "world_current.json"
    level_asset = {"asset_id": "asset_ue_project_content_citypark_maps_showcase", "ue_path": "/Game/CityPark/Maps/Showcase", "type": "level"}
    state_path.write_text(
        json.dumps(
            {
                "schema_version": "cineu.world_state.v1",
                "support_surfaces": {"park_path": {"type": "ground"}},
                "environment_asset": level_asset,
                "actors": {"zebra_01": {"name": "zebra_01", "asset_id": "asset_zebra"}},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(cineu_world_ops, "ensure_support_surfaces", lambda surfaces: calls.append(("surfaces", surfaces)))
    monkeypatch.setattr(cineu_world_ops, "ensure_actor_from_state", lambda actor_name, spec: calls.append(("actor", actor_name)))
    monkeypatch.setattr(cineu_world_ops, "_spawn_environment_asset_if_available", lambda asset: calls.append(("environment_asset", asset)))

    cineu_executor._rehydrate_world_state(str(state_path))

    assert calls == [
        ("environment_asset", level_asset),
        ("surfaces", {"park_path": {"type": "ground", "environment_asset_type": "level"}}),
        ("actor", "zebra_01"),
    ]


def test_executor_rehydrates_sequence_tracks_before_rendering(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_anim_ops
    import cineu_camera_ops
    import cineu_executor
    import cineu_sequence_ops
    import cineu_world_ops

    calls = []
    state_path = tmp_path / "world_current.json"
    sequence_path = "/Game/CineU/Sequences/SEQ_test"
    transform_track = {
        "actor_name": "zebra_01",
        "start_frame": 0,
        "end_frame": 48,
        "keys": [
            {"frame": 0, "transform": {"location": [0, 0, 90], "rotation": [0, 0, 0], "scale": [1, 1, 1]}},
            {"frame": 48, "transform": {"location": [500, 0, 90], "rotation": [0, 0, 0], "scale": [1, 1, 1]}},
        ],
    }
    animation_track = {
        "actor_name": "zebra_01",
        "animation_type": "run",
        "start_frame": 0,
        "end_frame": 48,
        "animation_path": "/Game/AfricanAnimalsPack/Zebra/Animations/ANIM_Zebra_Gallop",
    }
    camera = {
        "shot_id": "shot_001",
        "target_actor": "zebra_01",
        "transform_keys": [
            {"frame": 0, "location": [-300, -500, 180], "rotation": [-8, 0, 32]},
            {"frame": 48, "location": [-120, -240, 150], "rotation": [-8, 0, 32]},
        ],
        "focal_length_keys": [
            {"frame": 0, "focal_length": 35.0},
            {"frame": 48, "focal_length": 70.0},
        ],
    }
    cuts = [{"camera_name": "CAM_shot_001", "shot_id": "shot_001", "start_frame": 0, "end_frame": 48}]
    state_path.write_text(
        json.dumps(
            {
                "schema_version": "cineu.world_state.v1",
                "support_surfaces": {},
                "actors": {
                    "zebra_01": {"name": "zebra_01", "asset_id": "asset_zebra"},
                    "CAM_shot_001": {"name": "CAM_shot_001", "asset_id": "cine_camera_actor"},
                },
                "sequences": {
                    sequence_path: {
                        "sequence_path": sequence_path,
                        "fps": 24,
                        "range": [0, 48],
                        "cameras": {"CAM_shot_001": camera},
                        "transform_tracks": {"zebra_01": transform_track},
                        "animation_tracks": {"zebra_01": animation_track},
                        "camera_cuts": cuts,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(cineu_world_ops, "ensure_support_surfaces", lambda surfaces: calls.append(("surfaces", surfaces)))
    monkeypatch.setattr(cineu_world_ops, "ensure_actor_from_state", lambda actor_name, spec: calls.append(("actor", actor_name)))
    monkeypatch.setattr(cineu_sequence_ops, "create_level_sequence", lambda inputs: calls.append(("sequence", inputs)) or {})
    monkeypatch.setattr(cineu_camera_ops, "create_camera_shot", lambda inputs: calls.append(("camera", inputs)) or {})
    monkeypatch.setattr(cineu_sequence_ops, "add_transform_tracks", lambda inputs: calls.append(("transform", inputs)) or {})
    monkeypatch.setattr(cineu_anim_ops, "add_animation_tracks", lambda inputs: calls.append(("animation", inputs)) or {})
    monkeypatch.setattr(cineu_sequence_ops, "add_camera_cuts", lambda inputs: calls.append(("cuts", inputs)) or {})

    cineu_executor._rehydrate_world_state(str(state_path))

    assert ("actor", "CAM_shot_001") not in calls
    assert ("sequence", {"sequence_path": sequence_path, "fps": 24, "start_frame": 0, "end_frame": 48}) in calls
    camera_call = next(inputs for kind, inputs in calls if kind == "camera")
    assert camera_call["sequence_path"] == sequence_path
    assert camera_call["camera_name"] == "CAM_shot_001"
    assert camera_call["start_frame"] == 0
    assert camera_call["end_frame"] == 48
    assert camera_call["keys"][0]["focal_length"] == 35.0
    assert camera_call["keys"][-1]["focal_length"] == 70.0
    assert ("transform", {"sequence_path": sequence_path, "tracks": [transform_track]}) in calls
    assert ("animation", {"sequence_path": sequence_path, "clips": [animation_track]}) in calls
    assert ("cuts", {"sequence_path": sequence_path, "cuts": cuts}) in calls
