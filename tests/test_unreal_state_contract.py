from __future__ import annotations

import json
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1] / "unreal_project" / "Plugins" / "CineUDemo" / "Content" / "Python"


def test_state_dump_merges_sequence_camera_cut_and_render_metadata(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    from cineu_verify_ops import dump_world_state_to_file

    state_path = tmp_path / "world_current.json"
    seq_path = "/Game/CineU/Sequences/SEQ_run_x"
    dump_world_state_to_file(
        str(state_path),
        {"operation_type": "env.setup", "inputs": {"level_name": "LVL_run_x", "environment": "gallery", "mood": "clean"}},
        {"level": "LVL_run_x"},
    )
    dump_world_state_to_file(
        str(state_path),
        {"operation_type": "sequence.init", "inputs": {"sequence_path": seq_path, "fps": 24, "start_frame": 0, "end_frame": 288}},
        {"sequence_path": seq_path},
    )
    dump_world_state_to_file(
        str(state_path),
        {
            "operation_type": "camera.dolly_in",
            "inputs": {
                "sequence_path": seq_path,
                "shot_id": "shot_001",
                "camera_name": "CAM_shot_001",
                "target_actor": "sculpture_01",
                "keys": [
                    {"frame": 0, "location": [0, -500, 120], "rotation": [0, 0, 90], "focal_length": 35, "focus_distance": 500},
                    {"frame": 100, "location": [0, -200, 120], "rotation": [0, 0, 90], "focal_length": 35, "focus_distance": 200},
                ],
            },
        },
        {"camera_name": "CAM_shot_001"},
    )
    dump_world_state_to_file(
        str(state_path),
        {
            "operation_type": "sequence.camera_cut",
            "inputs": {
                "sequence_path": seq_path,
                "cuts": [{"camera_name": "CAM_shot_001", "shot_id": "shot_001", "start_frame": 0, "end_frame": 288}],
            },
        },
        {"camera_cuts": []},
    )
    dump_world_state_to_file(
        str(state_path),
        {
            "operation_type": "render.preview",
            "inputs": {"sequence_path": seq_path, "output_dir": str(tmp_path), "resolution": [1280, 720], "quality": "preview"},
        },
        {"artifacts": {"preview_manifest.json": str(tmp_path / "preview_manifest.json"), "preview_frame.png": str(tmp_path / "preview_frame.png")}},
    )

    state = json.loads(state_path.read_text(encoding="utf-8"))
    seq = state["sequences"][seq_path]
    assert state["level"] == "LVL_run_x"
    assert seq["fps"] == 24
    assert seq["range"] == [0, 288]
    assert "CAM_shot_001" in seq["cameras"]
    assert seq["camera_cuts"][0]["camera_name"] == "CAM_shot_001"
    assert state["renders"][-1]["artifacts"]["preview_manifest.json"].endswith("preview_manifest.json")


def test_state_dump_resolves_actor_asset_path_from_import_record(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    from cineu_verify_ops import dump_world_state_to_file

    state_path = tmp_path / "world_current.json"

    dump_world_state_to_file(
        str(state_path),
        {"operation_type": "asset.import_many", "inputs": {"assets": []}},
        {
            "assets": [
                {
                    "asset_id": "asset_public_free_zebra",
                    "status": "imported",
                    "ue_path": "/Game/CineU/Imported/public_free/zebra1.zebra1",
                    "imported_object_paths": [
                        "/Game/CineU/Imported/public_free/zebra1.zebra1",
                        "/Game/CineU/Imported/public_free/Zebra.Zebra",
                    ],
                }
            ]
        },
    )
    dump_world_state_to_file(
        str(state_path),
        {
            "operation_type": "entity.spawn_many",
            "inputs": {
                "actors": [
                    {
                        "actor_name": "zebra_01",
                        "semantic_type": "zebra",
                        "asset_id": "asset_public_free_zebra",
                        "asset_path": "/Game/CineU/Imported/public_free/zebra",
                        "asset_type": "skeletal_mesh",
                    }
                ]
            },
        },
        {"spawned": ["zebra_01"]},
    )

    state = json.loads(state_path.read_text(encoding="utf-8"))

    assert state["asset_imports"]["asset_public_free_zebra"]["ue_path"] == "/Game/CineU/Imported/public_free/zebra1.zebra1"
    assert state["actors"]["zebra_01"]["asset_path"] == "/Game/CineU/Imported/public_free/zebra1.zebra1"


def test_state_dump_preserves_reused_actor_name_for_unreal_rehydration(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    from cineu_verify_ops import dump_world_state_to_file

    state_path = tmp_path / "world_current.json"

    dump_world_state_to_file(
        str(state_path),
        {
            "operation_type": "entity.spawn_many",
            "inputs": {
                "actors": [
                    {
                        "actor_name": "zebra_01",
                        "reuse_actor_name": "ANIM_Zebra_WalkTurnR",
                        "semantic_type": "zebra",
                        "asset_id": "asset_citypark_zebra",
                        "asset_path": "/Game/AfricanAnimalsPack/Zebra/Meshes/SK_Zebra",
                        "asset_type": "skeletal_mesh",
                    }
                ]
            },
        },
        {"created_actors": ["zebra_01"], "reused_actors": [{"actor": "zebra_01", "source": "ANIM_Zebra_WalkTurnR"}]},
    )

    state = json.loads(state_path.read_text(encoding="utf-8"))

    assert state["actors"]["zebra_01"]["reuse_actor_name"] == "ANIM_Zebra_WalkTurnR"


def test_state_dump_resolves_animation_track_to_actor_imported_animation(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    from cineu_verify_ops import dump_world_state_to_file

    state_path = tmp_path / "world_current.json"
    seq_path = "/Game/CineU/Sequences/SEQ_run_x"

    dump_world_state_to_file(
        str(state_path),
        {"operation_type": "asset.import_many", "inputs": {"assets": []}},
        {
            "assets": [
                {
                    "asset_id": "asset_public_free_zebra",
                    "status": "imported",
                    "ue_path": "/Game/CineU/Imported/public_free/zebra1.zebra1",
                    "imported_object_paths": [
                        "/Game/CineU/Imported/public_free/zebra1.zebra1",
                        "/Game/CineU/Imported/public_free/zebra_Anim.zebra_Anim",
                    ],
                    "imported_animation_paths": ["/Game/CineU/Imported/public_free/zebra_Anim.zebra_Anim"],
                }
            ]
        },
    )
    dump_world_state_to_file(
        str(state_path),
        {
            "operation_type": "entity.spawn_many",
            "inputs": {
                "actors": [
                    {
                        "actor_name": "zebra_01",
                        "semantic_type": "zebra",
                        "asset_id": "asset_public_free_zebra",
                        "asset_path": "/Game/CineU/Imported/public_free/zebra",
                        "asset_type": "skeletal_mesh",
                    }
                ]
            },
        },
        {"spawned": ["zebra_01"]},
    )
    dump_world_state_to_file(
        str(state_path),
        {"operation_type": "sequence.init", "inputs": {"sequence_path": seq_path, "fps": 24, "start_frame": 0, "end_frame": 192}},
        {"sequence_path": seq_path},
    )
    dump_world_state_to_file(
        str(state_path),
        {
            "operation_type": "animation.add_tracks",
            "inputs": {
                "sequence_path": seq_path,
                "clips": [
                    {
                        "actor_name": "zebra_01",
                        "animation_type": "run",
                        "start_frame": 0,
                        "end_frame": 192,
                        "animation_path": "/Game/AfricanAnimalsPack/Zebra/Animations/ANIM_Zebra_Gallop",
                    }
                ],
            },
        },
        {"animation_tracks": ["zebra_01"]},
    )

    state = json.loads(state_path.read_text(encoding="utf-8"))

    assert state["sequences"][seq_path]["animation_tracks"]["zebra_01"]["animation_path"] == "/Game/CineU/Imported/public_free/zebra_Anim.zebra_Anim"
    assert state["sequences"][seq_path]["animation_tracks"]["zebra_01"]["source_type"] == "imported_with_actor"


def test_sequence_use_existing_keeps_task_range_separate_from_asset_range(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    from cineu_verify_ops import dump_world_state_to_file

    state_path = tmp_path / "world_current.json"
    seq_path = "/Game/AnimalHitchcockZoom_ablation"

    dump_world_state_to_file(
        str(state_path),
        {
            "operation_type": "sequence.use_existing",
            "inputs": {
                "sequence_path": seq_path,
                "sequence_asset": {"asset_id": "asset_ue_project_content_animalhitchcockzoom_ablation", "type": "level_sequence"},
                "fps": 24,
                "start_frame": 0,
                "end_frame": 126,
                "native_camera_name": "NativeSequenceCamera",
                "shot_id": "shot_001",
            },
        },
        {"sequence_path": seq_path, "fps": 60, "range": [0, 1728]},
    )

    state = json.loads(state_path.read_text(encoding="utf-8"))
    seq = state["sequences"][seq_path]

    assert seq["range"] == [0, 126]
    assert seq["fps"] == 24
    assert seq["asset_range"] == [0, 1728]
    assert seq["asset_fps"] == 60
    assert seq["camera_cuts"] == [{"camera_name": "NativeSequenceCamera", "shot_id": "shot_001", "start_frame": 0, "end_frame": 126}]


def test_sequence_use_existing_persists_unreal_sequence_metadata(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    from cineu_verify_ops import dump_world_state_to_file

    state_path = tmp_path / "world_current.json"
    seq_path = "/Game/AnimalHitchcockZoom"
    ue_metadata = {
        "display_rate": {"numerator": 60, "denominator": 1},
        "bindings": [
            {
                "name": "CineCameraActor_0",
                "id": "binding-guid-camera",
                "tracks": [
                    {
                        "name": "CameraComponent",
                        "type": "MovieSceneFloatTrack",
                        "sections": [{"start_frame": 0, "end_frame": 1728}],
                    }
                ],
            }
        ],
        "master_tracks": [{"name": "CameraCut", "type": "MovieSceneCameraCutTrack", "section_count": 1}],
        "camera_cut_sections": [{"start_frame": 0, "end_frame": 1728}],
    }

    dump_world_state_to_file(
        str(state_path),
        {
            "operation_type": "sequence.use_existing",
            "inputs": {
                "sequence_path": seq_path,
                "sequence_asset": {"asset_id": "asset_ue_project_content_animalhitchcockzoom", "type": "level_sequence"},
                "fps": 30,
                "start_frame": 0,
                "end_frame": 166,
                "native_camera_name": "NativeSequenceCamera",
                "shot_id": "shot_001",
            },
        },
        {"sequence_path": seq_path, "fps": 60, "range": [0, 1728], **ue_metadata},
    )

    state = json.loads(state_path.read_text(encoding="utf-8"))
    seq = state["sequences"][seq_path]

    assert seq["ue_sequence_metadata"] == ue_metadata
    assert seq["asset_range"] == [0, 1728]
    assert seq["range"] == [0, 166]


def test_asset_import_dump_does_not_pollute_actor_transform_from_editor_level(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_verify_ops

    state_path = tmp_path / "world_current.json"
    state_path.write_text(
        json.dumps(
            {
                "schema_version": "cineu.world_state.v1",
                "level": "Showcase",
                "support_surfaces": {},
                "asset_imports": {},
                "actors": {
                    "zebra_01": {
                        "name": "zebra_01",
                        "semantic_type": "zebra",
                        "asset_id": "asset_public_free_zebra",
                        "asset_path": "/Game/CineU/Imported/public_free/zebra",
                        "asset_type": "skeletal_mesh",
                        "transform": {"location": [-87000.0, 16400.0, 600.0], "rotation": [0.0, 0.0, 90.0], "scale": [1.0, 1.0, 1.0]},
                    }
                },
                "sequences": {},
                "renders": [],
                "warnings": [],
            }
        ),
        encoding="utf-8",
    )

    class Vector:
        x = -10.0
        y = -20.0
        z = -30.0

    class Rotator:
        pitch = 1.0
        roll = 2.0
        yaw = 3.0

    class Scale:
        x = 2.3
        y = 0.7
        z = 1.7

    class ActorClass:
        @staticmethod
        def get_name():
            return "StaleSkeletalMeshActor"

    class StaleActor:
        @staticmethod
        def get_actor_label():
            return "zebra_01"

        @staticmethod
        def get_actor_location():
            return Vector()

        @staticmethod
        def get_actor_rotation():
            return Rotator()

        @staticmethod
        def get_actor_scale3d():
            return Scale()

        @staticmethod
        def get_actor_bounds(_only_colliding):
            return Vector(), Vector()

        @staticmethod
        def get_class():
            return ActorClass()

    class FakeLevelLibrary:
        @staticmethod
        def get_editor_world():
            return None

        @staticmethod
        def get_all_level_actors():
            return [StaleActor()]

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary

    monkeypatch.setattr(cineu_verify_ops, "unreal", FakeUnreal)

    cineu_verify_ops.dump_world_state_to_file(
        str(state_path),
        {"operation_type": "asset.import_many", "inputs": {"assets": []}},
        {
            "assets": [
                {
                    "asset_id": "asset_public_free_zebra",
                    "status": "already_exists",
                    "ue_path": "/Game/CineU/Imported/public_free/zebra1.zebra1",
                    "imported_animation_paths": ["/Game/CineU/Imported/public_free/zebra_Anim.zebra_Anim"],
                }
            ]
        },
    )

    state = json.loads(state_path.read_text(encoding="utf-8"))
    zebra = state["actors"]["zebra_01"]
    assert zebra["asset_path"] == "/Game/CineU/Imported/public_free/zebra1.zebra1"
    assert zebra["transform"] == {"location": [-87000.0, 16400.0, 600.0], "rotation": [0.0, 0.0, 90.0], "scale": [1.0, 1.0, 1.0]}
