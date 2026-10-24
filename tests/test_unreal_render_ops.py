from __future__ import annotations

import json
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1] / "unreal_project" / "Plugins" / "CineUDemo" / "Content" / "Python"


def test_render_preview_writes_manifest_and_png_without_unreal(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    from cineu_render_ops import render_preview

    result = render_preview(
        {"sequence_path": "/Game/Seq", "output_dir": str(tmp_path), "resolution": [1280, 720], "format": "mp4", "quality": "preview"}
    )

    assert (tmp_path / "preview_manifest.json").exists()
    assert (tmp_path / "preview_frame.png").exists()
    assert result["artifacts"]["preview_manifest.json"] == str(tmp_path / "preview_manifest.json")
    assert result["artifacts"]["preview_frame.png"] == str(tmp_path / "preview_frame.png")


def test_render_preview_records_first_camera_cut_from_world_state(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    from cineu_render_ops import render_preview

    state_path = tmp_path / "world_current.json"
    state_path.write_text(
        json.dumps(
            {
                "sequences": {
                    "/Game/Seq": {
                        "camera_cuts": [
                            {"camera_name": "CAM_A", "shot_id": "shot_a", "start_frame": 24, "end_frame": 72},
                            {"camera_name": "CAM_B", "shot_id": "shot_b", "start_frame": 72, "end_frame": 96},
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    result = render_preview(
        {
            "sequence_path": "/Game/Seq",
            "output_dir": str(tmp_path),
            "world_state_path": str(state_path),
            "resolution": [1280, 720],
            "format": "mp4",
            "quality": "preview",
        }
    )

    manifest = json.loads((tmp_path / "preview_manifest.json").read_text(encoding="utf-8"))
    assert result["preview_camera"] == "CAM_A"
    assert result["preview_shot_id"] == "shot_a"
    assert result["preview_frame"] == 24
    assert manifest["preview_camera"] == "CAM_A"
    assert manifest["preview_shot_id"] == "shot_a"
    assert manifest["preview_frame"] == 24


def test_render_preview_writes_storyboard_frames_from_camera_keys(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    from cineu_render_ops import render_preview

    state_path = tmp_path / "world_current.json"
    state_path.write_text(
        json.dumps(
            {
                "sequences": {
                    "/Game/Seq": {
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
                                "focal_length_keys": [{"frame": 0, "focal_length": 24}, {"frame": 48, "focal_length": 24}],
                            },
                            "CAM_B": {
                                "transform_keys": [
                                    {"frame": 48, "location": [-200, -200, 260], "rotation": [-20, 0, 45]},
                                    {"frame": 72, "location": [200, -200, 260], "rotation": [-20, 0, 135]},
                                ],
                                "focal_length_keys": [{"frame": 48, "focal_length": 24}, {"frame": 72, "focal_length": 24}],
                            },
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    result = render_preview(
        {
            "sequence_path": "/Game/Seq",
            "output_dir": str(tmp_path),
            "world_state_path": str(state_path),
            "resolution": [1280, 720],
            "format": "mp4",
            "quality": "preview",
        }
    )

    storyboard = json.loads((tmp_path / "storyboard_manifest.json").read_text(encoding="utf-8"))
    assert len(result["storyboard_frames"]) == 18
    assert [frame["frame"] for frame in storyboard["frames"]] == [0, 6, 12, 18, 24, 29, 35, 41, 47, 48, 51, 54, 57, 60, 62, 65, 68, 71]
    assert (tmp_path / "storyboard_000.png").exists()
    assert result["artifacts"]["storyboard_manifest.json"] == str(tmp_path / "storyboard_manifest.json")


def test_storyboard_samples_can_cover_all_one_frame_camera_cuts_for_scene_probe():
    import sys

    sys.path.insert(0, str(PLUGIN_DIR))
    import cineu_render_ops

    camera_cuts = []
    cameras = {}
    for index in range(77):
        camera_name = f"CAM_{index:02d}"
        camera_cuts.append({"camera_name": camera_name, "shot_id": camera_name, "start_frame": index, "end_frame": index + 1})
        cameras[camera_name] = {
            "transform_keys": [{"frame": index, "location": [float(index), 0.0, 100.0], "rotation": [0.0, 0.0, 0.0]}],
            "focal_length_keys": [{"frame": index, "focal_length": 24.0}],
        }
    state = {"sequences": {"/Game/Seq": {"camera_cuts": camera_cuts, "cameras": cameras}}}

    default_samples = cineu_render_ops._storyboard_samples(state, "/Game/Seq")
    expanded_samples = cineu_render_ops._storyboard_samples(state, "/Game/Seq", max_samples=77)

    assert len(default_samples) == 24
    assert len(expanded_samples) == 77
    assert expanded_samples[0]["camera_name"] == "CAM_00"
    assert expanded_samples[-1]["camera_name"] == "CAM_76"


def test_native_preview_samples_map_one_frame_camera_cuts_when_expanded_for_scene_probe():
    import sys

    sys.path.insert(0, str(PLUGIN_DIR))
    import cineu_render_ops

    camera_cuts = [
        {"camera_name": f"CAM_{index:02d}", "shot_id": f"shot_{index:02d}", "start_frame": index, "end_frame": index + 1}
        for index in range(56)
    ]
    sequence = {"camera_cuts": camera_cuts}

    default_samples = cineu_render_ops._native_preview_samples(sequence, 0, 56)
    expanded_samples = cineu_render_ops._native_preview_samples(sequence, 0, 56, max_samples=56)

    assert len(default_samples) == 9
    assert len(expanded_samples) == 56
    assert expanded_samples[0]["camera_name"] == "CAM_00"
    assert expanded_samples[0]["shot_id"] == "shot_00"
    assert expanded_samples[-1]["camera_name"] == "CAM_55"
    assert expanded_samples[-1]["shot_id"] == "shot_55"


def test_render_preview_interpolates_storyboard_camera_pose_at_sample_frame(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    from cineu_render_ops import render_preview

    state_path = tmp_path / "world_current.json"
    state_path.write_text(
        json.dumps(
            {
                "sequences": {
                    "/Game/Seq": {
                        "camera_cuts": [{"camera_name": "CAM_A", "shot_id": "shot_a", "start_frame": 0, "end_frame": 101}],
                        "cameras": {
                            "CAM_A": {
                                "transform_keys": [
                                    {"frame": 0, "location": [0, 0, 100], "rotation": [-10, 0, 0]},
                                    {"frame": 100, "location": [100, 200, 300], "rotation": [-30, 0, 90]},
                                ],
                                "focal_length_keys": [{"frame": 0, "focal_length": 20}, {"frame": 100, "focal_length": 40}],
                            }
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    render_preview(
        {
            "sequence_path": "/Game/Seq",
            "output_dir": str(tmp_path),
            "world_state_path": str(state_path),
            "resolution": [1280, 720],
            "format": "mp4",
            "quality": "preview",
        }
    )

    storyboard = json.loads((tmp_path / "storyboard_manifest.json").read_text(encoding="utf-8"))
    middle = next(frame for frame in storyboard["frames"] if frame["frame"] == 50)

    assert middle["location"] == [50.0, 100.0, 200.0]
    assert middle["rotation"] == [-20.0, 0.0, 45.0]
    assert middle["focal_length"] == 30.0


def test_apply_sequence_frame_state_interpolates_actor_transform_tracks(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_render_ops

    applied = []
    state = {
        "actors": {
            "zebra_01": {
                "bounds_extent": [115, 35, 85],
                "spatial_relation": {"relation": "on_ground", "target": "park_path"},
            }
        },
        "sequences": {
            "/Game/Seq": {
                "transform_tracks": {
                    "zebra_01": {
                        "actor_name": "zebra_01",
                        "keys": [
                            {"frame": 0, "transform": {"location": [-600, 0, 85], "rotation": [0, 0, 0], "scale": [1, 1, 1]}},
                            {"frame": 200, "transform": {"location": [600, 0, 85], "rotation": [0, 0, 20], "scale": [1, 1, 1]}},
                        ],
                    }
                }
            }
        },
    }

    monkeypatch.setattr(cineu_render_ops, "apply_actor_transforms", lambda placements: applied.extend(placements) or {"transformed": []})

    warnings = []
    cineu_render_ops._apply_sequence_frame_state(state, "/Game/Seq", 100, warnings)

    assert warnings == []
    assert applied[0]["actor_name"] == "zebra_01"
    assert applied[0]["transform"]["location"] == [0.0, 0.0, 85.0]
    assert applied[0]["transform"]["rotation"] == [0.0, 0.0, 10.0]
    assert applied[0]["bounds_extent"] == [115, 35, 85]
    assert applied[0]["relation"] == "on_ground"
    assert applied[0]["target"] == "park_path"


def test_apply_sequence_frame_state_samples_skeletal_animation_clip(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_render_ops

    events = []

    class Animation:
        def get_editor_property(self, name):
            if name == "sequence_length":
                return 4.0
            raise AttributeError(name)

    class SkeletalComponent:
        def set_animation_mode(self, mode):
            events.append(("animation_mode", mode))

        def set_animation(self, animation):
            events.append(("animation", animation))

        def set_position(self, position, fire_notifies=False):
            events.append(("position", position, fire_notifies))

        def tick_animation(self, delta_time, needs_valid_root_motion=False):
            events.append(("tick", delta_time, needs_valid_root_motion))

        def refresh_bone_transforms(self):
            events.append(("refresh",))

    component = SkeletalComponent()

    class Actor:
        def get_actor_label(self):
            return "zebra_01"

        def get_name(self):
            return "zebra_01"

        def get_component_by_class(self, component_class):
            events.append(("component_class", component_class))
            return component

    class FakeEditorAssetLibrary:
        @staticmethod
        def load_asset(path):
            events.append(("load", path))
            return Animation() if path == "/Game/CineU/Imported/public_free/zebra_Anim.zebra_Anim" else None

    class FakeLevelLibrary:
        @staticmethod
        def get_all_level_actors():
            return [Actor()]

    class FakeAnimationMode:
        ANIMATION_SINGLE_NODE = "single-node"

    class FakeUnreal:
        EditorAssetLibrary = FakeEditorAssetLibrary
        EditorLevelLibrary = FakeLevelLibrary
        SkeletalMeshComponent = "SkeletalMeshComponent"
        AnimationMode = FakeAnimationMode

    monkeypatch.setattr(cineu_render_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_render_ops, "apply_actor_transforms", lambda placements: None)

    warnings = []
    cineu_render_ops._apply_sequence_frame_state(
        {
            "sequences": {
                "/Game/Seq": {
                    "fps": 24,
                    "animation_tracks": {
                        "zebra_01": {
                            "actor_name": "zebra_01",
                            "start_frame": 0,
                            "end_frame": 192,
                            "animation_path": "/Game/CineU/Imported/public_free/zebra_Anim.zebra_Anim",
                        }
                    },
                }
            }
        },
        "/Game/Seq",
        48,
        warnings,
    )

    assert warnings == []
    assert ("load", "/Game/CineU/Imported/public_free/zebra_Anim.zebra_Anim") in events
    assert ("animation_mode", "single-node") in events
    assert any(event[0] == "animation" and isinstance(event[1], Animation) for event in events)
    assert ("position", 2.0, False) in events
    assert ("refresh",) in events


def test_apply_sequence_frame_state_evaluates_level_sequence_time(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_render_ops

    events = []

    class FakeEditorAssetLibrary:
        @staticmethod
        def load_asset(path):
            events.append(("load", path))
            return "LevelSequenceAsset" if path == "/Game/Seq" else None

    class FakeLevelSequenceEditorBlueprintLibrary:
        @staticmethod
        def open_level_sequence(sequence):
            events.append(("open", sequence))
            return True

        @staticmethod
        def set_current_time(frame):
            events.append(("set_current_time", frame))

        @staticmethod
        def refresh_current_level_sequence():
            events.append(("refresh_sequence",))

    class FakeLevelLibrary:
        @staticmethod
        def editor_invalidate_viewports():
            events.append(("invalidate",))

    class FakeUnreal:
        EditorAssetLibrary = FakeEditorAssetLibrary
        EditorLevelLibrary = FakeLevelLibrary
        LevelSequenceEditorBlueprintLibrary = FakeLevelSequenceEditorBlueprintLibrary

    monkeypatch.setattr(cineu_render_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_render_ops, "apply_actor_transforms", lambda placements: None)

    warnings = []
    cineu_render_ops._apply_sequence_frame_state({"sequences": {"/Game/Seq": {"fps": 24}}}, "/Game/Seq", 48, warnings)

    assert warnings == []
    assert ("load", "/Game/Seq") in events
    assert ("open", "LevelSequenceAsset") in events
    assert ("set_current_time", 48) in events
    assert ("refresh_sequence",) in events
    assert ("invalidate",) in events


def test_apply_camera_sample_hides_non_active_camera_actors(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_render_ops

    class Actor:
        def __init__(self, label):
            self.label = label
            self.hidden_in_game = None
            self.hidden_in_editor = None

        def get_actor_label(self):
            return self.label

        def get_name(self):
            return self.label

        def set_actor_location(self, location, sweep, teleport):
            self.location = location

        def set_actor_rotation(self, rotation, teleport):
            self.rotation = rotation

        def set_actor_hidden_in_game(self, hidden):
            self.hidden_in_game = hidden

        def set_is_temporarily_hidden_in_editor(self, hidden):
            self.hidden_in_editor = hidden

    active = Actor("CAM_A")
    other = Actor("CAM_B")
    prop = Actor("painting_01")

    class FakeLevelLibrary:
        @staticmethod
        def get_all_level_actors():
            return [active, other, prop]

        @staticmethod
        def pilot_level_actor(actor):
            return None

        @staticmethod
        def editor_set_game_view(enabled):
            return None

        @staticmethod
        def editor_invalidate_viewports():
            return None

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary

        @staticmethod
        def Vector(*values):
            return list(values)

        @staticmethod
        def Rotator(*values):
            return list(values)

    monkeypatch.setattr(cineu_render_ops, "unreal", FakeUnreal)

    assert cineu_render_ops._apply_camera_sample({"camera_name": "CAM_A", "location": [1, 2, 3], "rotation": [4, 5, 6]}, []) is True

    assert active.hidden_in_game is False
    assert active.hidden_in_editor is False
    assert other.hidden_in_game is True
    assert other.hidden_in_editor is True
    assert prop.hidden_in_game is None


def test_capture_storyboard_frame_waits_for_screenshot_task(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_render_ops

    path = tmp_path / "frame.png"
    calls = {"done": 0}

    class Actor:
        def get_actor_label(self):
            return "CAM_A"

        def get_name(self):
            return "CAM_A"

        def set_actor_location(self, location, sweep, teleport):
            return None

        def set_actor_rotation(self, rotation, teleport):
            return None

    class Task:
        def is_task_done(self):
            calls["done"] += 1
            path.write_bytes(b"valid screenshot bytes" + b"x" * 160)
            return True

    class FakeLevelLibrary:
        @staticmethod
        def get_all_level_actors():
            return [Actor()]

        @staticmethod
        def pilot_level_actor(actor):
            return None

        @staticmethod
        def editor_set_game_view(enabled):
            return None

        @staticmethod
        def editor_invalidate_viewports():
            return None

    class FakeAutomationLibrary:
        @staticmethod
        def take_high_res_screenshot(width, height, output_path):
            return Task()

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary
        AutomationLibrary = FakeAutomationLibrary

        @staticmethod
        def Vector(*values):
            return list(values)

        @staticmethod
        def Rotator(*values):
            return list(values)

    monkeypatch.setattr(cineu_render_ops, "unreal", FakeUnreal)

    warnings = []
    cineu_render_ops._capture_storyboard_frame(
        path,
        1280,
        720,
        {"camera_name": "CAM_A", "location": [0, 0, 0], "rotation": [0, 0, 0]},
        warnings,
    )

    assert calls["done"] == 1
    assert path.read_bytes() == b"valid screenshot bytes" + b"x" * 160
    assert warnings == []


def test_capture_storyboard_frame_exports_scene_capture_render_target_in_unreal_mode(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_render_ops

    path = tmp_path / "frame.png"
    captured = {}

    class CameraActor:
        def __init__(self):
            self.location = None
            self.rotation = None

        def get_actor_label(self):
            return "CAM_A"

        def get_name(self):
            return "CAM_A"

        def set_actor_location(self, location, sweep, teleport):
            self.location = location

        def set_actor_rotation(self, rotation, teleport):
            self.rotation = rotation

        def get_actor_location(self):
            return self.location

        def get_actor_rotation(self):
            return self.rotation

    class SceneCaptureComponent:
        def __init__(self):
            self.capture_count = 0

        def set_editor_property(self, name, value):
            setattr(self, name, value)

        def capture_scene(self):
            self.capture_count += 1

    class SceneCaptureActor:
        def __init__(self, location, rotation):
            self.location = location
            self.rotation = rotation
            self.component = SceneCaptureComponent()

        def get_component_by_class(self, component_class):
            captured["component_class"] = component_class
            return self.component

    camera = CameraActor()

    class FakeLevelLibrary:
        @staticmethod
        def get_all_level_actors():
            return [camera]

        @staticmethod
        def get_editor_world():
            return "editor-world"

        @staticmethod
        def pilot_level_actor(actor):
            return None

        @staticmethod
        def editor_set_game_view(enabled):
            return None

        @staticmethod
        def editor_invalidate_viewports():
            return None

        @staticmethod
        def spawn_actor_from_class(actor_class, location, rotation):
            captured["spawn_actor_class"] = actor_class
            captured["spawn_location"] = location
            captured["spawn_rotation"] = rotation
            captured["scene_capture_actor"] = SceneCaptureActor(location, rotation)
            return captured["scene_capture_actor"]

        @staticmethod
        def destroy_actor(actor):
            captured["destroyed_actor"] = actor

    class FakeRenderingLibrary:
        @staticmethod
        def create_render_target2d(world, width, height, texture_format, clear_color, force_linear_gamma=False, support_uav=False):
            captured["render_target_args"] = (world, width, height, texture_format, clear_color, force_linear_gamma, support_uav)
            return {"width": width, "height": height}

        @staticmethod
        def export_render_target(world, render_target, directory, filename):
            captured["export_args"] = (world, render_target, directory, filename)
            Path(directory, filename).write_bytes(b"scene capture png bytes" + b"x" * 160)
            return True

    class FakeAutomationLibrary:
        @staticmethod
        def take_high_res_screenshot(*args, **kwargs):
            raise AssertionError("high-res screenshot should not be used for Unreal storyboards")

    class FakeTextureRenderTargetFormat:
        RTF_RGBA8 = "rgba8"

    class FakeSceneCaptureSource:
        SCS_FinalColorLDR = "final-color-ldr"

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary
        RenderingLibrary = FakeRenderingLibrary
        AutomationLibrary = FakeAutomationLibrary
        TextureRenderTargetFormat = FakeTextureRenderTargetFormat
        SceneCaptureSource = FakeSceneCaptureSource
        SceneCapture2D = "SceneCapture2D"
        SceneCaptureComponent2D = "SceneCaptureComponent2D"

        @staticmethod
        def Vector(*values):
            return list(values)

        @staticmethod
        def Rotator(*values):
            return list(values)

        @staticmethod
        def LinearColor(*values):
            return tuple(values)

    monkeypatch.setattr(cineu_render_ops, "unreal", FakeUnreal)

    warnings = []
    cineu_render_ops._capture_storyboard_frame(
        path,
        1280,
        720,
        {"camera_name": "CAM_A", "location": [10, 20, 30], "rotation": [-5, 0, 90], "focal_length": 32},
        warnings,
    )

    assert path.exists()
    assert captured["render_target_args"][0:4] == ("editor-world", 1280, 720, "rgba8")
    assert captured["component_class"] == "SceneCaptureComponent2D"
    assert captured["scene_capture_actor"].component.texture_target == {"width": 1280, "height": 720}
    assert captured["scene_capture_actor"].component.capture_source == "final-color-ldr"
    assert captured["scene_capture_actor"].component.capture_count >= 1
    assert captured["export_args"][0:2] == ("editor-world", {"width": 1280, "height": 720})
    assert captured["export_args"][2:] == (str(tmp_path), "frame.png")
    assert captured["destroyed_actor"] is captured["scene_capture_actor"]
    assert warnings == []


def test_capture_storyboard_frame_falls_back_to_high_res_screenshot_when_scene_capture_exports_no_file(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_render_ops

    path = tmp_path / "frame.png"
    captured = {"fallback_calls": 0}

    class CameraActor:
        def __init__(self):
            self.location = None
            self.rotation = None

        def get_actor_label(self):
            return "CAM_A"

        def get_name(self):
            return "CAM_A"

        def set_actor_location(self, location, sweep, teleport):
            self.location = location

        def set_actor_rotation(self, rotation, teleport):
            self.rotation = rotation

        def get_actor_location(self):
            return self.location

        def get_actor_rotation(self):
            return self.rotation

    class SceneCaptureComponent:
        def set_editor_property(self, name, value):
            setattr(self, name, value)

        def capture_scene(self):
            return None

    class SceneCaptureActor:
        def __init__(self, location, rotation):
            self.component = SceneCaptureComponent()

        def get_component_by_class(self, component_class):
            return self.component

    camera = CameraActor()

    class FakeLevelLibrary:
        @staticmethod
        def get_all_level_actors():
            return [camera]

        @staticmethod
        def get_editor_world():
            return "editor-world"

        @staticmethod
        def pilot_level_actor(actor):
            return None

        @staticmethod
        def editor_set_game_view(enabled):
            return None

        @staticmethod
        def editor_invalidate_viewports():
            return None

        @staticmethod
        def spawn_actor_from_class(actor_class, location, rotation):
            return SceneCaptureActor(location, rotation)

        @staticmethod
        def destroy_actor(actor):
            return None

    class FakeRenderingLibrary:
        @staticmethod
        def create_render_target2d(world, width, height, texture_format, clear_color, force_linear_gamma=False, support_uav=False):
            return {"width": width, "height": height}

        @staticmethod
        def export_render_target(world, render_target, directory, filename):
            captured["scene_capture_export"] = (directory, filename)
            return True

    class FakeAutomationLibrary:
        @staticmethod
        def take_high_res_screenshot(width, height, output_path, camera_actor=None):
            captured["fallback_calls"] += 1
            captured["fallback_camera"] = camera_actor
            Path(output_path).write_bytes(b"fallback screenshot bytes" + b"x" * 160)
            return None

    class FakeTextureRenderTargetFormat:
        RTF_RGBA8 = "rgba8"

    class FakeSceneCaptureSource:
        SCS_FinalColorLDR = "final-color-ldr"

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary
        RenderingLibrary = FakeRenderingLibrary
        AutomationLibrary = FakeAutomationLibrary
        TextureRenderTargetFormat = FakeTextureRenderTargetFormat
        SceneCaptureSource = FakeSceneCaptureSource
        SceneCapture2D = "SceneCapture2D"
        SceneCaptureComponent2D = "SceneCaptureComponent2D"

        @staticmethod
        def Vector(*values):
            return list(values)

        @staticmethod
        def Rotator(*values):
            return list(values)

        @staticmethod
        def LinearColor(*values):
            return tuple(values)

    monkeypatch.setattr(cineu_render_ops, "unreal", FakeUnreal)

    warnings = []
    cineu_render_ops._capture_storyboard_frame(
        path,
        1280,
        720,
        {"camera_name": "CAM_A", "location": [10, 20, 30], "rotation": [-5, 0, 90], "focal_length": 32},
        warnings,
    )

    assert captured["scene_capture_export"] == (str(tmp_path), "frame.png")
    assert captured["fallback_calls"] == 1
    assert captured["fallback_camera"] is camera
    assert path.stat().st_size > 128
    assert any(item["reason"] == "scene_capture_artifact_missing" for item in warnings)


def test_capture_storyboard_frame_skips_high_res_screenshot_fallback_in_commandlet(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_render_ops

    path = tmp_path / "frame.png"
    captured = {"fallback_calls": 0}
    monkeypatch.setattr(cineu_render_ops.sys, "argv", ["UnrealEditor-Cmd.exe", "-run=pythonscript", "-unattended"])

    class CameraActor:
        def get_actor_label(self):
            return "CAM_A"

        def get_name(self):
            return "CAM_A"

        def set_actor_location(self, location, sweep, teleport):
            return None

        def set_actor_rotation(self, rotation, teleport):
            return None

        def get_actor_location(self):
            return [0, 0, 0]

        def get_actor_rotation(self):
            return [0, 0, 0]

    camera = CameraActor()

    class SceneCaptureComponent:
        def set_editor_property(self, name, value):
            setattr(self, name, value)

        def capture_scene(self):
            return None

    class SceneCaptureActor:
        def __init__(self, location, rotation):
            self.component = SceneCaptureComponent()

        def get_component_by_class(self, component_class):
            return self.component

    class FakeLevelLibrary:
        @staticmethod
        def get_all_level_actors():
            return [camera]

        @staticmethod
        def get_editor_world():
            return "editor-world"

        @staticmethod
        def pilot_level_actor(actor):
            return None

        @staticmethod
        def editor_set_game_view(enabled):
            return None

        @staticmethod
        def editor_invalidate_viewports():
            return None

        @staticmethod
        def spawn_actor_from_class(actor_class, location, rotation):
            return SceneCaptureActor(location, rotation)

        @staticmethod
        def destroy_actor(actor):
            return None

    class FakeRenderingLibrary:
        @staticmethod
        def create_render_target2d(world, width, height, texture_format, clear_color, force_linear_gamma=False, support_uav=False):
            return {"width": width, "height": height}

        @staticmethod
        def export_render_target(world, render_target, directory, filename):
            return True

    class FakeAutomationLibrary:
        @staticmethod
        def take_high_res_screenshot(width, height, output_path, camera_actor=None):
            captured["fallback_calls"] += 1
            Path(output_path).write_bytes(b"unexpected fallback")
            return None

    class FakeTextureRenderTargetFormat:
        RTF_RGBA8 = "rgba8"

    class FakeSceneCaptureSource:
        SCS_FinalColorLDR = "final-color-ldr"

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary
        RenderingLibrary = FakeRenderingLibrary
        AutomationLibrary = FakeAutomationLibrary
        TextureRenderTargetFormat = FakeTextureRenderTargetFormat
        SceneCaptureSource = FakeSceneCaptureSource
        SceneCapture2D = "SceneCapture2D"
        SceneCaptureComponent2D = "SceneCaptureComponent2D"

        @staticmethod
        def Vector(*values):
            return list(values)

        @staticmethod
        def Rotator(*values):
            return list(values)

        @staticmethod
        def LinearColor(*values):
            return tuple(values)

    monkeypatch.setattr(cineu_render_ops, "unreal", FakeUnreal)

    warnings = []
    cineu_render_ops._capture_storyboard_frame(
        path,
        1280,
        720,
        {"camera_name": "CAM_A", "location": [10, 20, 30], "rotation": [-5, 0, 90], "focal_length": 32},
        warnings,
    )

    assert captured["fallback_calls"] == 0
    assert not path.exists()
    assert any(item["reason"] == "scene_capture_artifact_missing" for item in warnings)
    assert any(item["reason"] == "high_res_screenshot_fallback_skipped_unattended" for item in warnings)


def test_render_preview_exports_preview_frame_with_scene_capture_in_unreal_mode(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_render_ops

    state_path = tmp_path / "world_current.json"
    state_path.write_text(
        json.dumps(
            {
                "sequences": {
                    "/Game/Seq": {
                        "camera_cuts": [{"camera_name": "CAM_A", "shot_id": "shot_a", "start_frame": 12, "end_frame": 24}],
                        "cameras": {
                            "CAM_A": {
                                "transform_keys": [{"frame": 12, "location": [10, 20, 30], "rotation": [-5, 0, 90]}],
                                "focal_length_keys": [{"frame": 12, "focal_length": 32}],
                            }
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    captured = {"exports": []}

    class CameraActor:
        def __init__(self):
            self.location = None
            self.rotation = None

        def get_actor_label(self):
            return "CAM_A"

        def get_name(self):
            return "CAM_A"

        def set_actor_location(self, location, sweep, teleport):
            self.location = location

        def set_actor_rotation(self, rotation, teleport):
            self.rotation = rotation

        def get_actor_location(self):
            return self.location

        def get_actor_rotation(self):
            return self.rotation

    class SceneCaptureComponent:
        def set_editor_property(self, name, value):
            setattr(self, name, value)

        def capture_scene(self):
            return None

    class SceneCaptureActor:
        def __init__(self, location, rotation):
            self.location = location
            self.rotation = rotation
            self.component = SceneCaptureComponent()

        def get_component_by_class(self, component_class):
            return self.component

    camera = CameraActor()

    class FakeLevelLibrary:
        @staticmethod
        def get_all_level_actors():
            return [camera]

        @staticmethod
        def get_editor_world():
            return "editor-world"

        @staticmethod
        def pilot_level_actor(actor):
            return None

        @staticmethod
        def editor_set_game_view(enabled):
            return None

        @staticmethod
        def editor_invalidate_viewports():
            return None

        @staticmethod
        def spawn_actor_from_class(actor_class, location, rotation):
            return SceneCaptureActor(location, rotation)

        @staticmethod
        def destroy_actor(actor):
            return None

    class FakeRenderingLibrary:
        @staticmethod
        def create_render_target2d(world, width, height, texture_format, clear_color, force_linear_gamma=False, support_uav=False):
            return {"width": width, "height": height}

        @staticmethod
        def export_render_target(world, render_target, directory, filename):
            captured["exports"].append((directory, filename, render_target))
            Path(directory, filename).write_bytes(b"scene capture png bytes" + b"x" * 160)
            return True

    class FakeAutomationLibrary:
        @staticmethod
        def take_high_res_screenshot(*args, **kwargs):
            raise AssertionError("high-res screenshot should not be used for Unreal preview")

    class FakeTextureRenderTargetFormat:
        RTF_RGBA8 = "rgba8"

    class FakeSceneCaptureSource:
        SCS_FinalColorLDR = "final-color-ldr"

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary
        RenderingLibrary = FakeRenderingLibrary
        AutomationLibrary = FakeAutomationLibrary
        TextureRenderTargetFormat = FakeTextureRenderTargetFormat
        SceneCaptureSource = FakeSceneCaptureSource
        SceneCapture2D = "SceneCapture2D"
        SceneCaptureComponent2D = "SceneCaptureComponent2D"

        @staticmethod
        def Vector(*values):
            return list(values)

        @staticmethod
        def Rotator(*values):
            return list(values)

        @staticmethod
        def LinearColor(*values):
            return tuple(values)

    monkeypatch.setattr(cineu_render_ops, "unreal", FakeUnreal)

    result = cineu_render_ops.render_preview(
        {
            "sequence_path": "/Game/Seq",
            "output_dir": str(tmp_path),
            "world_state_path": str(state_path),
            "resolution": [640, 360],
            "format": "mp4",
            "quality": "preview",
        }
    )

    assert (tmp_path / "preview_frame.png").exists()
    assert ("preview_frame.png" in {filename for _, filename, _ in captured["exports"]})
    assert camera.location == [10, 20, 30]
    assert result["warnings"] == []


def test_scene_capture_export_skips_missing_capture_source_enum_value(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_render_ops

    path = tmp_path / "frame.png"
    captured = {}

    class CameraActor:
        def get_actor_location(self):
            return [1, 2, 3]

        def get_actor_rotation(self):
            return [4, 5, 6]

    class SceneCaptureComponent:
        def set_editor_property(self, name, value):
            setattr(self, name, value)

        def capture_scene(self):
            return None

    class SceneCaptureActor:
        def __init__(self):
            self.component = SceneCaptureComponent()

        def get_component_by_class(self, component_class):
            captured["component"] = self.component
            return self.component

    class FakeLevelLibrary:
        @staticmethod
        def get_editor_world():
            return "editor-world"

        @staticmethod
        def spawn_actor_from_class(actor_class, location, rotation):
            return SceneCaptureActor()

        @staticmethod
        def editor_invalidate_viewports():
            return None

        @staticmethod
        def destroy_actor(actor):
            return None

    class FakeRenderingLibrary:
        @staticmethod
        def create_render_target2d(world, width, height, texture_format, clear_color, force_linear_gamma=False, support_uav=False):
            return {"width": width, "height": height}

        @staticmethod
        def export_render_target(world, render_target, directory, filename):
            Path(directory, filename).write_bytes(b"scene capture png bytes" + b"x" * 160)
            return True

    class FakeTextureRenderTargetFormat:
        RTF_RGBA8 = "rgba8"

    class FakeSceneCaptureSource:
        pass

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary
        RenderingLibrary = FakeRenderingLibrary
        TextureRenderTargetFormat = FakeTextureRenderTargetFormat
        SceneCaptureSource = FakeSceneCaptureSource
        SceneCapture2D = "SceneCapture2D"
        SceneCaptureComponent2D = "SceneCaptureComponent2D"

        @staticmethod
        def LinearColor(*values):
            return tuple(values)

    monkeypatch.setattr(cineu_render_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_render_ops, "_find_actor_by_label", lambda label: CameraActor())

    warnings = []
    assert cineu_render_ops._capture_scene_to_png(path, 640, 360, "CAM_A", None, warnings) is True

    assert path.exists()
    assert not hasattr(captured["component"], "capture_source")
    assert warnings == []


def test_scene_capture_export_uses_uppercase_final_color_ldr_enum_value(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_render_ops

    path = tmp_path / "frame.png"
    captured = {}

    class CameraActor:
        def get_actor_location(self):
            return [1, 2, 3]

        def get_actor_rotation(self):
            return [4, 5, 6]

    class SceneCaptureComponent:
        def set_editor_property(self, name, value):
            setattr(self, name, value)

        def capture_scene(self):
            return None

    class SceneCaptureActor:
        def __init__(self):
            self.component = SceneCaptureComponent()

        def get_component_by_class(self, component_class):
            captured["component"] = self.component
            return self.component

    class FakeLevelLibrary:
        @staticmethod
        def get_editor_world():
            return "editor-world"

        @staticmethod
        def spawn_actor_from_class(actor_class, location, rotation):
            return SceneCaptureActor()

        @staticmethod
        def editor_invalidate_viewports():
            return None

        @staticmethod
        def destroy_actor(actor):
            return None

    class FakeRenderingLibrary:
        @staticmethod
        def create_render_target2d(world, width, height, texture_format, clear_color, force_linear_gamma=False, support_uav=False):
            return {"width": width, "height": height}

        @staticmethod
        def export_render_target(world, render_target, directory, filename):
            Path(directory, filename).write_bytes(b"scene capture png bytes" + b"x" * 160)
            return True

    class FakeTextureRenderTargetFormat:
        RTF_RGBA8 = "rgba8"

    class FakeSceneCaptureSource:
        SCS_FINAL_COLOR_LDR = "ue55-final-color-ldr"

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary
        RenderingLibrary = FakeRenderingLibrary
        TextureRenderTargetFormat = FakeTextureRenderTargetFormat
        SceneCaptureSource = FakeSceneCaptureSource
        SceneCapture2D = "SceneCapture2D"
        SceneCaptureComponent2D = "SceneCaptureComponent2D"

        @staticmethod
        def LinearColor(*values):
            return tuple(values)

    monkeypatch.setattr(cineu_render_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_render_ops, "_find_actor_by_label", lambda label: CameraActor())

    warnings = []
    assert cineu_render_ops._capture_scene_to_png(path, 640, 360, "CAM_A", None, warnings) is True

    assert captured["component"].capture_source == "ue55-final-color-ldr"
    assert warnings == []


def test_scene_capture_export_sets_stable_exposure_for_commandline_preview(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_render_ops

    path = tmp_path / "frame.png"
    captured = {}

    class CameraActor:
        def get_actor_location(self):
            return [1, 2, 3]

        def get_actor_rotation(self):
            return [4, 5, 6]

    class PostProcessSettings:
        def __init__(self):
            self.properties = {}

        def set_editor_property(self, name, value):
            self.properties[name] = value

    class SceneCaptureComponent:
        def __init__(self):
            self.post_process_settings = PostProcessSettings()

        def get_editor_property(self, name):
            return getattr(self, name)

        def set_editor_property(self, name, value):
            setattr(self, name, value)

        def capture_scene(self):
            return None

    class SceneCaptureActor:
        def __init__(self):
            self.component = SceneCaptureComponent()

        def get_component_by_class(self, component_class):
            captured["component"] = self.component
            return self.component

    class FakeLevelLibrary:
        @staticmethod
        def get_editor_world():
            return "editor-world"

        @staticmethod
        def spawn_actor_from_class(actor_class, location, rotation):
            return SceneCaptureActor()

        @staticmethod
        def editor_invalidate_viewports():
            return None

        @staticmethod
        def destroy_actor(actor):
            return None

    class FakeRenderingLibrary:
        @staticmethod
        def create_render_target2d(world, width, height, texture_format, clear_color, force_linear_gamma=False, support_uav=False):
            return {"width": width, "height": height}

        @staticmethod
        def export_render_target(world, render_target, directory, filename):
            Path(directory, filename).write_bytes(b"scene capture png bytes" + b"x" * 160)
            return True

    class FakeTextureRenderTargetFormat:
        RTF_RGBA8 = "rgba8"

    class FakeSceneCaptureSource:
        SCS_SCENE_COLOR_HDR = "scene-color-hdr"

    class FakeAutoExposureMethod:
        AEM_MANUAL = "manual-exposure"

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary
        RenderingLibrary = FakeRenderingLibrary
        TextureRenderTargetFormat = FakeTextureRenderTargetFormat
        SceneCaptureSource = FakeSceneCaptureSource
        AutoExposureMethod = FakeAutoExposureMethod
        SceneCapture2D = "SceneCapture2D"
        SceneCaptureComponent2D = "SceneCaptureComponent2D"

        @staticmethod
        def LinearColor(*values):
            return tuple(values)

    monkeypatch.setattr(cineu_render_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_render_ops, "_find_actor_by_label", lambda label: CameraActor())

    warnings = []
    assert cineu_render_ops._capture_scene_to_png(path, 640, 360, "CAM_A", None, warnings) is True

    component = captured["component"]
    settings = component.post_process_settings.properties
    assert component.post_process_blend_weight == 1.0
    assert settings["auto_exposure_method"] == "manual-exposure"
    assert 0.35 <= settings["auto_exposure_min_brightness"] <= 0.7
    assert settings["auto_exposure_max_brightness"] == settings["auto_exposure_min_brightness"]
    assert -0.8 <= settings["exposure_compensation"] <= -0.3
    assert settings["auto_exposure_bias"] == settings["exposure_compensation"]
    assert settings["bloom_intensity"] <= 0.08
    assert settings["vignette_intensity"] <= 0.10
    assert settings["scene_color_tint"] == (1.0, 1.0, 1.0, 1.0)


def test_scene_capture_export_applies_camera_sample_exposure_controls(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_render_ops

    path = tmp_path / "frame.png"
    captured = {}

    class CameraActor:
        def get_actor_location(self):
            return [1, 2, 3]

        def get_actor_rotation(self):
            return [4, 5, 6]

    class PostProcessSettings:
        def __init__(self):
            self.properties = {}

        def set_editor_property(self, name, value):
            self.properties[name] = value

    class SceneCaptureComponent:
        def __init__(self):
            self.post_process_settings = PostProcessSettings()

        def get_editor_property(self, name):
            return getattr(self, name)

        def set_editor_property(self, name, value):
            setattr(self, name, value)

        def capture_scene(self):
            return None

    class SceneCaptureActor:
        def __init__(self):
            self.component = SceneCaptureComponent()

        def get_component_by_class(self, component_class):
            captured["component"] = self.component
            return self.component

    class FakeLevelLibrary:
        @staticmethod
        def get_editor_world():
            return "editor-world"

        @staticmethod
        def spawn_actor_from_class(actor_class, location, rotation):
            return SceneCaptureActor()

        @staticmethod
        def editor_invalidate_viewports():
            return None

        @staticmethod
        def destroy_actor(actor):
            return None

    class FakeRenderingLibrary:
        @staticmethod
        def create_render_target2d(world, width, height, texture_format, clear_color, force_linear_gamma=False, support_uav=False):
            return {"width": width, "height": height}

        @staticmethod
        def export_render_target(world, render_target, directory, filename):
            Path(directory, filename).write_bytes(b"scene capture png bytes" + b"x" * 160)
            return True

    class FakeTextureRenderTargetFormat:
        RTF_RGBA8 = "rgba8"

    class FakeSceneCaptureSource:
        SCS_FINAL_COLOR_LDR = "final-color-ldr"

    class FakeAutoExposureMethod:
        AEM_MANUAL = "manual-exposure"

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary
        RenderingLibrary = FakeRenderingLibrary
        TextureRenderTargetFormat = FakeTextureRenderTargetFormat
        SceneCaptureSource = FakeSceneCaptureSource
        AutoExposureMethod = FakeAutoExposureMethod
        SceneCapture2D = "SceneCapture2D"
        SceneCaptureComponent2D = "SceneCaptureComponent2D"

        @staticmethod
        def LinearColor(*values):
            return tuple(values)

    monkeypatch.setattr(cineu_render_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_render_ops, "_find_actor_by_label", lambda label: CameraActor())

    warnings = []
    assert cineu_render_ops._capture_scene_to_png(
        path,
        640,
        360,
        "CAM_A",
        35.0,
        warnings,
        exposure_bias=-0.9,
        exposure_brightness=0.52,
    ) is True

    settings = captured["component"].post_process_settings.properties
    assert settings["auto_exposure_min_brightness"] == 0.52
    assert settings["auto_exposure_max_brightness"] == 0.52
    assert settings["auto_exposure_bias"] == -0.9
    assert settings["exposure_compensation"] == -0.9
    assert settings["bloom_intensity"] <= 0.08
    assert settings["depth_of_field_fstop"] <= 3.6
    assert 900.0 <= settings["depth_of_field_focal_distance"] <= 1400.0
    assert warnings == []


def test_scene_capture_export_allows_explicit_high_daylight_exposure(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_render_ops

    class PostProcessSettings:
        def __init__(self):
            self.properties = {}

        def set_editor_property(self, name, value):
            self.properties[name] = value

    class SceneCaptureComponent:
        def __init__(self):
            self.post_process_settings = PostProcessSettings()

        def get_editor_property(self, name):
            return getattr(self, name)

        def set_editor_property(self, name, value):
            setattr(self, name, value)

    class FakeAutoExposureMethod:
        AEM_MANUAL = "manual-exposure"

    class FakeUnreal:
        AutoExposureMethod = FakeAutoExposureMethod

        @staticmethod
        def LinearColor(*values):
            return tuple(values)

    component = SceneCaptureComponent()
    monkeypatch.setattr(cineu_render_ops, "unreal", FakeUnreal)

    cineu_render_ops._configure_scene_capture_exposure(
        component,
        focal_length=24.0,
        exposure_bias=2.0,
        exposure_brightness=4.2,
    )

    settings = component.post_process_settings.properties
    assert settings["auto_exposure_min_brightness"] == 4.2
    assert settings["auto_exposure_max_brightness"] == 4.2
    assert settings["auto_exposure_bias"] == 2.0
    assert settings["exposure_compensation"] == 2.0


def test_scene_capture_export_prefers_tonemapped_final_color_ldr_over_hdr(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_render_ops

    path = tmp_path / "frame.png"
    captured = {}

    class CameraActor:
        def get_actor_location(self):
            return [1, 2, 3]

        def get_actor_rotation(self):
            return [4, 5, 6]

    class SceneCaptureComponent:
        def set_editor_property(self, name, value):
            setattr(self, name, value)

        def capture_scene(self):
            return None

    class SceneCaptureActor:
        def __init__(self):
            self.component = SceneCaptureComponent()

        def get_component_by_class(self, component_class):
            captured["component"] = self.component
            return self.component

    class FakeLevelLibrary:
        @staticmethod
        def get_editor_world():
            return "editor-world"

        @staticmethod
        def spawn_actor_from_class(actor_class, location, rotation):
            return SceneCaptureActor()

        @staticmethod
        def editor_invalidate_viewports():
            return None

        @staticmethod
        def destroy_actor(actor):
            return None

    class FakeRenderingLibrary:
        @staticmethod
        def create_render_target2d(world, width, height, texture_format, clear_color, force_linear_gamma=False, support_uav=False):
            return {"width": width, "height": height}

        @staticmethod
        def export_render_target(world, render_target, directory, filename):
            Path(directory, filename).write_bytes(b"scene capture png bytes" + b"x" * 160)
            return True

    class FakeTextureRenderTargetFormat:
        RTF_RGBA8 = "rgba8"

    class FakeSceneCaptureSource:
        SCS_SCENE_COLOR_HDR = "scene-color-hdr"
        SCS_FINAL_COLOR_LDR = "final-color-ldr"

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary
        RenderingLibrary = FakeRenderingLibrary
        TextureRenderTargetFormat = FakeTextureRenderTargetFormat
        SceneCaptureSource = FakeSceneCaptureSource
        SceneCapture2D = "SceneCapture2D"
        SceneCaptureComponent2D = "SceneCaptureComponent2D"

        @staticmethod
        def LinearColor(*values):
            return tuple(values)

    monkeypatch.setattr(cineu_render_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_render_ops, "_find_actor_by_label", lambda label: CameraActor())

    warnings = []
    assert cineu_render_ops._capture_scene_to_png(path, 640, 360, "CAM_A", None, warnings) is True

    assert captured["component"].capture_source == "final-color-ldr"
    assert warnings == []


def test_scene_capture_source_can_be_overridden_for_visual_debug(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_render_ops

    class FakeSceneCaptureSource:
        SCS_SCENE_COLOR_HDR = "scene-color-hdr"
        SCS_FINAL_COLOR_LDR = "final-color-ldr"

    class FakeUnreal:
        SceneCaptureSource = FakeSceneCaptureSource

    monkeypatch.setattr(cineu_render_ops, "unreal", FakeUnreal)
    monkeypatch.setenv("CINEU_SCENE_CAPTURE_SOURCE", "final_color_ldr")

    assert cineu_render_ops._scene_capture_visible_color_source() == "final-color-ldr"


def test_screenshot_wait_rejects_tiny_completed_artifact(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_render_ops

    path = tmp_path / "frame.png"
    path.write_bytes(b"x" * 70)
    monotonic_values = iter([0.0, 0.0, 0.02])

    class Task:
        def is_task_done(self):
            return True

    class FakeLevelLibrary:
        @staticmethod
        def editor_invalidate_viewports():
            return None

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary

    monkeypatch.setattr(cineu_render_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_render_ops.time, "monotonic", lambda: next(monotonic_values, 0.03))
    monkeypatch.setattr(cineu_render_ops.time, "sleep", lambda _seconds: None)

    warnings = []
    cineu_render_ops._wait_for_screenshot_task(Task(), path, warnings, timeout_sec=0.01)

    assert warnings
    assert warnings[-1]["reason"] == "screenshot_artifact_too_small"
    assert warnings[-1]["artifact"] == str(path)


def test_screenshot_wait_reports_missing_artifact_after_timeout(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_render_ops

    path = tmp_path / "missing.png"
    monotonic_values = iter([0.0, 0.0, 0.02])

    class Task:
        def is_task_done(self):
            return False

    class FakeLevelLibrary:
        @staticmethod
        def editor_invalidate_viewports():
            return None

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary

    monkeypatch.setattr(cineu_render_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_render_ops.time, "monotonic", lambda: next(monotonic_values, 0.03))
    monkeypatch.setattr(cineu_render_ops.time, "sleep", lambda _seconds: None)

    warnings = []
    cineu_render_ops._wait_for_screenshot_task(Task(), path, warnings, timeout_sec=0.01)

    assert warnings
    assert warnings[-1]["reason"] == "screenshot_artifact_missing"
    assert warnings[-1]["artifact"] == str(path)


def test_capture_storyboard_frame_does_not_write_fallback_in_unreal_mode(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_render_ops

    path = tmp_path / "frame.png"

    class Actor:
        def get_actor_label(self):
            return "CAM_A"

        def get_name(self):
            return "CAM_A"

        def set_actor_location(self, location, sweep, teleport):
            return None

        def set_actor_rotation(self, rotation, teleport):
            return None

    class FakeLevelLibrary:
        @staticmethod
        def get_all_level_actors():
            return [Actor()]

        @staticmethod
        def pilot_level_actor(actor):
            return None

        @staticmethod
        def editor_set_game_view(enabled):
            return None

        @staticmethod
        def editor_invalidate_viewports():
            return None

    class FakeAutomationLibrary:
        @staticmethod
        def take_high_res_screenshot(width, height, output_path, camera_actor=None):
            return None

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary
        AutomationLibrary = FakeAutomationLibrary

        @staticmethod
        def Vector(*values):
            return list(values)

        @staticmethod
        def Rotator(*values):
            return list(values)

    monkeypatch.setattr(cineu_render_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(
        cineu_render_ops,
        "_wait_for_screenshot_task",
        lambda task, output_path, warnings, timeout_sec=5.0: warnings.append(
            {"reason": "screenshot_artifact_missing", "artifact": str(output_path), "size": 0}
        ),
    )

    warnings = []
    cineu_render_ops._capture_storyboard_frame(
        path,
        1280,
        720,
        {"camera_name": "CAM_A", "location": [0, 0, 0], "rotation": [0, 0, 0]},
        warnings,
    )

    assert not path.exists()
    assert warnings[-1]["reason"] == "screenshot_artifact_missing"


def test_capture_storyboard_frame_passes_camera_actor_to_screenshot(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_render_ops

    path = tmp_path / "frame.png"
    captured = {}

    class Actor:
        def get_actor_label(self):
            return "CAM_A"

        def get_name(self):
            return "CAM_A"

        def set_actor_location(self, location, sweep, teleport):
            return None

        def set_actor_rotation(self, rotation, teleport):
            return None

    camera = Actor()

    class FakeLevelLibrary:
        @staticmethod
        def get_all_level_actors():
            return [camera]

        @staticmethod
        def pilot_level_actor(actor):
            return None

        @staticmethod
        def editor_set_game_view(enabled):
            return None

        @staticmethod
        def editor_invalidate_viewports():
            return None

    class FakeAutomationLibrary:
        @staticmethod
        def take_high_res_screenshot(width, height, output_path, camera_actor=None):
            captured["camera_actor"] = camera_actor
            Path(output_path).write_bytes(b"valid screenshot bytes" + b"x" * 160)
            return None

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary
        AutomationLibrary = FakeAutomationLibrary

        @staticmethod
        def Vector(*values):
            return list(values)

        @staticmethod
        def Rotator(*values):
            return list(values)

    monkeypatch.setattr(cineu_render_ops, "unreal", FakeUnreal)

    warnings = []
    cineu_render_ops._capture_storyboard_frame(
        path,
        1280,
        720,
        {"camera_name": "CAM_A", "location": [0, 0, 0], "rotation": [0, 0, 0]},
        warnings,
    )

    assert captured["camera_actor"] is camera
    assert warnings == []


def test_render_preview_uses_movie_capture_for_native_level_sequence(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_render_ops

    state_path = tmp_path / "world_current.json"
    state_path.write_text(
        json.dumps(
            {
                "sequences": {
                    "/Game/AnimalHitchcockZoom": {
                        "sequence_path": "/Game/AnimalHitchcockZoom",
                        "source_asset_type": "level_sequence",
                        "fps": 24,
                        "range": [0, 4],
                        "camera_cuts": [
                            {"camera_name": "NativeSequenceCamera", "shot_id": "existing_sequence", "start_frame": 0, "end_frame": 4}
                        ],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    captured = {}

    class FrameNumber:
        def __init__(self, value):
            self.value = int(value)

    class FrameRate:
        def __init__(self, numerator, denominator):
            self.numerator = numerator
            self.denominator = denominator

    class DirectoryPath(str):
        pass

    class SoftObjectPath(str):
        pass

    class Resolution:
        res_x = 0
        res_y = 0

    class CaptureSettings:
        def __init__(self):
            self.resolution = Resolution()

    class CaptureProtocol:
        compression_quality = 0

    class AutomatedLevelSequenceCapture:
        def __init__(self):
            self.settings = CaptureSettings()
            self.protocol = CaptureProtocol()

        def set_image_capture_protocol_type(self, protocol_type):
            captured["protocol_type"] = protocol_type

        def get_image_capture_protocol(self):
            return self.protocol

    class OnRenderMovieStopped:
        def bind_callable(self, callback):
            captured["callback"] = callback

    class SequencerTools:
        @staticmethod
        def render_movie(capture, callback):
            from PIL import Image

            captured["capture"] = capture
            start = capture.custom_start_frame.value
            end = capture.custom_end_frame.value
            out_dir = Path(str(capture.settings.output_directory))
            out_dir.mkdir(parents=True, exist_ok=True)
            for frame in range(start, end):
                Image.new("RGB", (256, 144), color=(frame * 20, 80, 160)).save(out_dir / f"movie_frame_{frame:04d}.png")
            captured["callback"](True)
            return True

        @staticmethod
        def is_rendering_movie():
            return False

    class EditorLevelLibrary:
        @staticmethod
        def get_all_level_actors():
            raise AssertionError("native level sequence render must not require a camera actor lookup")

        @staticmethod
        def get_editor_world():
            return object()

    class EditorPythonScripting:
        @staticmethod
        def set_keep_python_script_alive(_enabled):
            return None

    class SystemLibrary:
        @staticmethod
        def execute_console_command(world, command):
            captured.setdefault("console_commands", []).append(command)

        @staticmethod
        def quit_editor():
            captured["quit_editor"] = True

    def load_class(_outer, path):
        return path

    def register_slate_post_tick_callback(callback):
        callback(0.016)
        return 1

    def unregister_slate_post_tick_callback(_handle):
        captured["unregistered"] = True

    FakeUnreal = type(
        "FakeUnreal",
        (),
        {
            "AutomatedLevelSequenceCapture": AutomatedLevelSequenceCapture,
            "DirectoryPath": DirectoryPath,
            "FrameNumber": FrameNumber,
            "FrameRate": FrameRate,
            "SoftObjectPath": SoftObjectPath,
            "OnRenderMovieStopped": OnRenderMovieStopped,
            "SequencerTools": SequencerTools,
            "EditorLevelLibrary": EditorLevelLibrary,
            "EditorPythonScripting": EditorPythonScripting,
            "SystemLibrary": SystemLibrary,
            "load_class": staticmethod(load_class),
            "register_slate_post_tick_callback": staticmethod(register_slate_post_tick_callback),
            "unregister_slate_post_tick_callback": staticmethod(unregister_slate_post_tick_callback),
        },
    )

    monkeypatch.setattr(cineu_render_ops, "unreal", FakeUnreal)

    result = cineu_render_ops.render_preview(
        {
            "sequence_path": "/Game/AnimalHitchcockZoom",
            "output_dir": str(tmp_path / "artifacts"),
            "world_state_path": str(state_path),
            "resolution": [1280, 720],
            "format": "mp4",
            "quality": "preview",
        }
    )

    out_dir = tmp_path / "artifacts"
    manifest = json.loads((out_dir / "preview_manifest.json").read_text(encoding="utf-8"))

    assert result["render_backend"] == "sequencer_movie_capture"
    assert manifest["render_backend"] == "sequencer_movie_capture"
    assert str(captured["capture"].level_sequence_asset) == "/Game/AnimalHitchcockZoom"
    assert captured["capture"].custom_start_frame.value == 0
    assert captured["capture"].custom_end_frame.value == 4
    assert captured["console_commands"] == [
        "r.TextureStreaming 0",
        "r.Streaming.FullyLoadUsedTextures 1",
        "r.Streaming.UseAllMips 1",
        "r.ViewDistanceScale 2",
    ]
    assert (out_dir / "preview_frame.png").stat().st_size > 128
    assert (out_dir / "storyboard_000.png").stat().st_size > 128
    assert len(manifest["storyboard_frames"]) == 4


def test_render_preview_uses_native_capture_source_frame_range_for_level_sequence(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_render_ops

    state_path = tmp_path / "world_current.json"
    state_path.write_text(
        json.dumps(
            {
                "sequences": {
                    "/Game/AnimalHitchcockZoom": {
                        "sequence_path": "/Game/AnimalHitchcockZoom",
                        "source_asset_type": "level_sequence",
                        "fps": 30,
                        "range": [0, 166],
                        "asset_fps": 60,
                        "asset_range": [0, 1728],
                        "camera_cuts": [
                            {"camera_name": "NativeSequenceCamera", "shot_id": "shot_001", "start_frame": 0, "end_frame": 166}
                        ],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    captured = {}

    class FrameNumber:
        def __init__(self, value):
            self.value = int(value)

    class FrameRate:
        def __init__(self, numerator, denominator):
            self.numerator = numerator
            self.denominator = denominator

    class DirectoryPath(str):
        pass

    class SoftObjectPath(str):
        pass

    class Resolution:
        res_x = 0
        res_y = 0

    class CaptureSettings:
        def __init__(self):
            self.resolution = Resolution()

    class CaptureProtocol:
        compression_quality = 0

    class AutomatedLevelSequenceCapture:
        def __init__(self):
            self.settings = CaptureSettings()
            self.protocol = CaptureProtocol()

        def set_image_capture_protocol_type(self, protocol_type):
            captured["protocol_type"] = protocol_type

        def get_image_capture_protocol(self):
            return self.protocol

    class OnRenderMovieStopped:
        def bind_callable(self, callback):
            captured["callback"] = callback

    class SequencerTools:
        @staticmethod
        def render_movie(capture, callback):
            from PIL import Image

            captured["capture"] = capture
            out_dir = Path(str(capture.settings.output_directory))
            out_dir.mkdir(parents=True, exist_ok=True)
            for frame in [10, 50, 90, 130, 170, 209, 249, 289, 329]:
                Image.new("RGB", (256, 144), color=(frame % 255, 80, 160)).save(out_dir / f"movie_frame_{frame:04d}.png")
            captured["callback"](True)
            return True

        @staticmethod
        def is_rendering_movie():
            return False

    class EditorLevelLibrary:
        @staticmethod
        def get_all_level_actors():
            raise AssertionError("native level sequence render must not require camera actor lookup")

        @staticmethod
        def get_editor_world():
            return object()

    class EditorPythonScripting:
        @staticmethod
        def set_keep_python_script_alive(_enabled):
            return None

    class SystemLibrary:
        @staticmethod
        def execute_console_command(_world, _command):
            return None

    fake_unreal = type(
        "FakeUnreal",
        (),
        {
            "AutomatedLevelSequenceCapture": AutomatedLevelSequenceCapture,
            "DirectoryPath": DirectoryPath,
            "FrameNumber": FrameNumber,
            "FrameRate": FrameRate,
            "SoftObjectPath": SoftObjectPath,
            "OnRenderMovieStopped": OnRenderMovieStopped,
            "SequencerTools": SequencerTools,
            "EditorLevelLibrary": EditorLevelLibrary,
            "EditorPythonScripting": EditorPythonScripting,
            "SystemLibrary": SystemLibrary,
            "load_class": staticmethod(lambda _outer, path: path),
            "register_slate_post_tick_callback": staticmethod(lambda callback: callback(0.016) or 1),
            "unregister_slate_post_tick_callback": staticmethod(lambda _handle: None),
        },
    )
    monkeypatch.setattr(cineu_render_ops, "unreal", fake_unreal)

    result = cineu_render_ops.render_preview(
        {
            "sequence_path": "/Game/AnimalHitchcockZoom",
            "output_dir": str(tmp_path / "artifacts"),
            "world_state_path": str(state_path),
            "resolution": [1280, 720],
            "format": "mp4",
            "quality": "preview",
            "fps": 30,
            "start_frame": 0,
            "end_frame": 166,
            "native_capture_start_frame": 10,
            "native_capture_end_frame": 330,
        }
    )

    manifest = json.loads((tmp_path / "artifacts" / "preview_manifest.json").read_text(encoding="utf-8"))

    assert result["render_backend"] == "sequencer_movie_capture"
    assert captured["capture"].custom_start_frame.value == 10
    assert captured["capture"].custom_end_frame.value == 330
    assert captured["capture"].settings.custom_frame_rate.numerator == 60
    assert captured["capture"].settings.custom_frame_rate.denominator == 1
    assert manifest["native_capture_frame_range"] == [10, 330]
    assert [frame["frame"] for frame in manifest["storyboard_frames"]] == [10, 50, 90, 130, 170, 209, 249, 289, 329]


def test_native_movie_capture_view_respects_low_memory_cvars(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_render_ops

    captured = []

    class EditorLevelLibrary:
        @staticmethod
        def get_editor_world():
            return object()

    class SystemLibrary:
        @staticmethod
        def execute_console_command(_world, command):
            captured.append(command)

    fake_unreal = type(
        "FakeUnreal",
        (),
        {
            "EditorLevelLibrary": EditorLevelLibrary,
            "SystemLibrary": SystemLibrary,
        },
    )
    monkeypatch.setattr(cineu_render_ops, "unreal", fake_unreal)

    commands = cineu_render_ops._prepare_native_movie_capture_view({"mrq_low_memory": True})

    assert "r.TextureStreaming 1" in commands
    assert "r.Streaming.FullyLoadUsedTextures 0" in commands
    assert "r.Streaming.UseAllMips 0" in commands
    assert "r.ViewDistanceScale 0.75" in commands
    assert "r.TextureStreaming 0" not in commands
    assert "r.Streaming.FullyLoadUsedTextures 1" not in commands
    assert captured == commands


def test_render_preview_uses_movie_render_pipeline_when_requested(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_render_ops

    state_path = tmp_path / "world_current.json"
    state_path.write_text(
        json.dumps(
            {
                "level": "Showcase",
                "sequences": {
                    "/Game/AnimalHitchcockZoom": {
                        "sequence_path": "/Game/AnimalHitchcockZoom",
                        "source_asset_type": "level_sequence",
                        "level_path": "/Game/CityPark/Maps/Showcase",
                        "fps": 30,
                        "asset_fps": 60,
                        "range": [0, 166],
                        "camera_cuts": [
                            {"camera_name": "NativeSequenceCamera", "shot_id": "shot_001", "start_frame": 0, "end_frame": 166}
                        ],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    captured = {}

    class SoftObjectPath(str):
        pass

    class FrameRate:
        def __init__(self, numerator, denominator):
            self.numerator = int(numerator)
            self.denominator = int(denominator)

    class IntPoint:
        def __init__(self, x, y):
            self.x = int(x)
            self.y = int(y)

    class OutputDirectory:
        def __init__(self):
            self.path = ""

        def set_editor_property(self, name, value):
            assert name == "path"
            self.path = str(value)

    class MoviePipelineOutputSetting:
        def __init__(self):
            self.output_directory = OutputDirectory()

    class MoviePipelineDeferredPassBase:
        pass

    class MoviePipelineImageSequenceOutput_PNG:
        pass

    class MoviePipelineAntiAliasingSetting:
        pass

    class MoviePipelineGameOverrideSetting:
        pass

    class JobConfig:
        def __init__(self):
            self.settings = {}

        def find_or_add_setting_by_class(self, cls):
            self.settings.setdefault(cls, cls())
            return self.settings[cls]

        def initialize_transient_settings(self):
            captured["initialized_transient_settings"] = True

    class MoviePipelineExecutorJob:
        def __init__(self):
            self.config = JobConfig()
            self.editor_properties = {}

        def get_configuration(self):
            return self.config

        def set_editor_property(self, name, value):
            self.editor_properties[name] = value
            setattr(self, name, value)

    class MoviePipelineQueue:
        def __init__(self):
            self.jobs = []

        def delete_all_jobs(self):
            self.jobs.clear()

        def allocate_new_job(self, cls):
            job = cls()
            self.jobs.append(job)
            return job

        def get_jobs(self):
            return list(self.jobs)

    class Delegate:
        def __init__(self):
            self.callback = None

        def add_callable_unique(self, callback):
            self.callback = callback

    class MoviePipelinePIEExecutor:
        def __init__(self, subsystem=None):
            self.subsystem = subsystem
            self.on_executor_finished_delegate = Delegate()

    class MoviePipelineInProcessExecutor:
        def __init__(self, subsystem=None):
            self.subsystem = subsystem
            self.on_executor_finished_delegate = Delegate()

    class MoviePipelineQueueSubsystem:
        def __init__(self):
            self.queue = MoviePipelineQueue()

        def get_queue(self):
            return self.queue

        def render_queue_with_executor_instance(self, executor):
            from PIL import Image

            captured["executor_class"] = executor.__class__.__name__
            [job] = self.queue.get_jobs()
            captured["job"] = job
            output = job.get_configuration().settings[MoviePipelineOutputSetting]
            captured["output"] = output
            out_dir = Path(output.output_directory.path)
            out_dir.mkdir(parents=True, exist_ok=True)
            frame_step = int(getattr(output, "output_frame_step", 1) or 1)
            for frame in range(output.custom_start_frame, output.custom_end_frame, frame_step):
                Image.new("RGB", (256, 144), color=(frame % 255, 120, 180)).save(out_dir / f"movie_frame_{frame:04d}.png")
            executor.on_executor_finished_delegate.callback(executor, True)

    subsystem = MoviePipelineQueueSubsystem()

    class EditorWorld:
        @staticmethod
        def get_path_name():
            return "/Game/CityPark/Maps/Showcase.Showcase"

    class EditorLevelLibrary:
        @staticmethod
        def get_editor_world():
            return EditorWorld()

        @staticmethod
        def load_level(path):
            captured["loaded_level"] = path
            return True

    class EditorPythonScripting:
        @staticmethod
        def set_keep_python_script_alive(enabled):
            captured.setdefault("keep_alive", []).append(bool(enabled))

    class SystemLibrary:
        @staticmethod
        def execute_console_command(world, command):
            captured.setdefault("console_commands", []).append(command)

    fake_unreal = type(
        "FakeUnreal",
        (),
        {
            "SoftObjectPath": SoftObjectPath,
            "FrameRate": FrameRate,
            "IntPoint": IntPoint,
            "MoviePipelineQueueSubsystem": MoviePipelineQueueSubsystem,
            "MoviePipelineExecutorJob": MoviePipelineExecutorJob,
            "MoviePipelinePIEExecutor": MoviePipelinePIEExecutor,
            "MoviePipelineInProcessExecutor": MoviePipelineInProcessExecutor,
            "MoviePipelineOutputSetting": MoviePipelineOutputSetting,
            "MoviePipelineDeferredPassBase": MoviePipelineDeferredPassBase,
            "MoviePipelineImageSequenceOutput_PNG": MoviePipelineImageSequenceOutput_PNG,
            "MoviePipelineAntiAliasingSetting": MoviePipelineAntiAliasingSetting,
            "MoviePipelineGameOverrideSetting": MoviePipelineGameOverrideSetting,
            "EditorLevelLibrary": EditorLevelLibrary,
            "EditorPythonScripting": EditorPythonScripting,
            "SystemLibrary": SystemLibrary,
            "get_editor_subsystem": staticmethod(lambda cls: subsystem),
            "register_slate_post_tick_callback": staticmethod(lambda _callback: 1),
            "unregister_slate_post_tick_callback": staticmethod(lambda _handle: captured.setdefault("unregistered", True)),
        },
    )
    monkeypatch.setattr(cineu_render_ops, "unreal", fake_unreal)

    result = cineu_render_ops.render_preview(
        {
            "sequence_path": "/Game/AnimalHitchcockZoom",
            "output_dir": str(tmp_path / "artifacts"),
            "world_state_path": str(state_path),
            "resolution": [1280, 720],
            "format": "mp4",
            "quality": "preview",
            "render_backend": "movie_render_pipeline",
            "fps": 30,
            "start_frame": 0,
            "end_frame": 166,
            "native_capture_start_frame": 10,
            "native_capture_end_frame": 14,
            "mrq_output_frame_step": 2,
            "warm_up_frame_count": 0,
            "mrq_low_memory": True,
        }
    )

    out_dir = tmp_path / "artifacts"
    manifest = json.loads((out_dir / "preview_manifest.json").read_text(encoding="utf-8"))

    assert result["render_backend"] == "movie_render_pipeline"
    assert manifest["render_backend"] == "movie_render_pipeline"
    assert captured["executor_class"] == "MoviePipelinePIEExecutor"
    assert manifest["movie_render_pipeline_executor"] == "MoviePipelinePIEExecutor"
    assert "loaded_level" not in captured
    assert str(captured["job"].sequence) == "/Game/AnimalHitchcockZoom.AnimalHitchcockZoom"
    assert str(captured["job"].map) == "/Game/CityPark/Maps/Showcase.Showcase"
    assert str(captured["job"].editor_properties["sequence"]) == "/Game/AnimalHitchcockZoom.AnimalHitchcockZoom"
    assert str(captured["job"].editor_properties["map"]) == "/Game/CityPark/Maps/Showcase.Showcase"
    assert captured["output"].custom_start_frame == 10
    assert captured["output"].custom_end_frame == 14
    assert getattr(captured["output"], "output_frame_step", None) == 2
    assert captured["output"].output_frame_rate.numerator == 60
    assert captured["output"].output_frame_rate.denominator == 1
    aa = captured["job"].get_configuration().settings[MoviePipelineAntiAliasingSetting]
    game = captured["job"].get_configuration().settings[MoviePipelineGameOverrideSetting]
    assert aa.engine_warm_up_count == 0
    assert aa.render_warm_up_count == 0
    assert game.cinematic_quality_settings is False
    assert captured["console_commands"] == [
        "r.RayTracing.ForceAllRayTracingEffects 0",
        "r.Lumen.HardwareRayTracing 0",
        "r.DynamicGlobalIlluminationMethod 0",
        "r.ReflectionMethod 0",
        "r.SSGI.Quality 0",
        "r.Shadow.Virtual.Enable 0",
        "r.MotionBlurQuality 0",
        "r.DefaultFeature.MotionBlur 0",
        "r.HairStrands.Enable 0",
        "r.HeterogeneousVolumes 0",
        "r.SkyAtmosphere.FastSkyLUT 1",
        "r.TextureStreaming 1",
        "r.Streaming.FullyLoadUsedTextures 0",
        "r.Streaming.UseAllMips 0",
        "r.Streaming.PoolSize 1024",
        "r.ViewDistanceScale 0.75",
        "foliage.DensityScale 0.25",
        "grass.DensityScale 0.25",
        "r.Nanite.MaxPixelsPerEdge 4",
        "r.MipMapLODBias 1",
    ]
    assert manifest["movie_render_pipeline_frame_range"] == [10, 14]
    assert manifest.get("movie_render_pipeline_frame_step") == 2
    assert manifest["movie_render_pipeline_cvars"] == captured["console_commands"]
    assert manifest["movie_frame_dir"] == str(out_dir / "movie_frames")
    assert (out_dir / "preview_frame.png").stat().st_size > 128
    assert [frame["frame"] for frame in manifest["storyboard_frames"]] == [10, 12]

    try:
        cineu_render_ops._movie_render_pipeline_executor_class({"mrq_executor": "in_process"}, [])
    except RuntimeError as exc:
        assert "requires a Game/PIE world" in str(exc)
    else:
        raise AssertionError("Editor MRQ must reject MoviePipelineInProcessExecutor")


def test_movie_render_pipeline_async_completion_writes_final_build_summary(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_render_ops

    state_path = tmp_path / "world_current.json"
    state_path.write_text(
        json.dumps(
            {
                "level": "Showcase",
                "sequences": {
                    "/Game/AnimalHitchcockZoom": {
                        "sequence_path": "/Game/AnimalHitchcockZoom",
                        "source_asset_type": "level_sequence",
                        "level_path": "/Game/CityPark/Maps/Showcase",
                        "fps": 30,
                        "asset_fps": 60,
                        "range": [0, 166],
                        "camera_cuts": [
                            {"camera_name": "NativeSequenceCamera", "shot_id": "shot_001", "start_frame": 0, "end_frame": 166}
                        ],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    captured = {}

    class SoftObjectPath(str):
        pass

    class FrameRate:
        def __init__(self, numerator, denominator):
            self.numerator = int(numerator)
            self.denominator = int(denominator)

    class IntPoint:
        def __init__(self, x, y):
            self.x = int(x)
            self.y = int(y)

    class OutputDirectory:
        def __init__(self):
            self.path = ""

        def set_editor_property(self, name, value):
            assert name == "path"
            self.path = str(value)

    class MoviePipelineOutputSetting:
        def __init__(self):
            self.output_directory = OutputDirectory()

    class MoviePipelineDeferredPassBase:
        pass

    class MoviePipelineImageSequenceOutput_PNG:
        pass

    class MoviePipelineAntiAliasingSetting:
        pass

    class MoviePipelineGameOverrideSetting:
        pass

    class JobConfig:
        def __init__(self):
            self.settings = {}

        def find_or_add_setting_by_class(self, cls):
            self.settings.setdefault(cls, cls())
            return self.settings[cls]

        def initialize_transient_settings(self):
            captured["initialized_transient_settings"] = True

    class MoviePipelineExecutorJob:
        def __init__(self):
            self.config = JobConfig()
            self.editor_properties = {}

        def get_configuration(self):
            return self.config

        def set_editor_property(self, name, value):
            self.editor_properties[name] = value
            setattr(self, name, value)

    class MoviePipelineQueue:
        def __init__(self):
            self.jobs = []

        def delete_all_jobs(self):
            self.jobs.clear()

        def allocate_new_job(self, cls):
            job = cls()
            self.jobs.append(job)
            return job

        def get_jobs(self):
            return list(self.jobs)

    class Delegate:
        def __init__(self):
            self.callback = None

        def add_callable_unique(self, callback):
            self.callback = callback

    class MoviePipelinePIEExecutor:
        def __init__(self, subsystem=None):
            self.subsystem = subsystem
            self.on_executor_finished_delegate = Delegate()

    class MoviePipelineQueueSubsystem:
        def __init__(self):
            self.queue = MoviePipelineQueue()

        def get_queue(self):
            return self.queue

        def render_queue_with_executor_instance(self, executor):
            [job] = self.queue.get_jobs()
            captured["executor"] = executor
            captured["job"] = job
            captured["output"] = job.get_configuration().settings[MoviePipelineOutputSetting]

    subsystem = MoviePipelineQueueSubsystem()

    class EditorLevelLibrary:
        @staticmethod
        def load_level(path):
            captured["loaded_level"] = path
            return True

    class EditorPythonScripting:
        @staticmethod
        def set_keep_python_script_alive(enabled):
            captured.setdefault("keep_alive", []).append(bool(enabled))

    fake_unreal = type(
        "FakeUnreal",
        (),
        {
            "SoftObjectPath": SoftObjectPath,
            "FrameRate": FrameRate,
            "IntPoint": IntPoint,
            "MoviePipelineQueueSubsystem": MoviePipelineQueueSubsystem,
            "MoviePipelineExecutorJob": MoviePipelineExecutorJob,
            "MoviePipelinePIEExecutor": MoviePipelinePIEExecutor,
            "MoviePipelineOutputSetting": MoviePipelineOutputSetting,
            "MoviePipelineDeferredPassBase": MoviePipelineDeferredPassBase,
            "MoviePipelineImageSequenceOutput_PNG": MoviePipelineImageSequenceOutput_PNG,
            "MoviePipelineAntiAliasingSetting": MoviePipelineAntiAliasingSetting,
            "MoviePipelineGameOverrideSetting": MoviePipelineGameOverrideSetting,
            "EditorLevelLibrary": EditorLevelLibrary,
            "EditorPythonScripting": EditorPythonScripting,
            "get_editor_subsystem": staticmethod(lambda cls: subsystem),
            "register_slate_post_tick_callback": staticmethod(lambda callback: captured.setdefault("tick_callbacks", []).append(callback) or 7),
            "unregister_slate_post_tick_callback": staticmethod(lambda _handle: captured.setdefault("unregistered", True)),
        },
    )
    monkeypatch.setattr(cineu_render_ops, "unreal", fake_unreal)

    out_dir = tmp_path / "artifacts"
    final_summary_path = out_dir / "build_render_summary.json"
    latest_summary_path = tmp_path / "latest_build_render_summary.json"
    result = cineu_render_ops.render_preview(
        {
            "sequence_path": "/Game/AnimalHitchcockZoom",
            "output_dir": str(out_dir),
            "world_state_path": str(state_path),
            "resolution": [1280, 720],
            "format": "mp4",
            "quality": "cinematic",
            "render_backend": "movie_render_pipeline",
            "fps": 30,
            "start_frame": 0,
            "end_frame": 166,
            "native_capture_start_frame": 10,
            "native_capture_end_frame": 14,
            "mrq_output_frame_step": 2,
            "completion_summary_path": str(final_summary_path),
            "latest_summary_path": str(latest_summary_path),
            "completion_summary_base": {"scene_id": "scene19", "render_result": {"stale": True}},
        }
    )

    assert result["capture_pending"] is True
    assert result["capture_success"] is None
    assert captured["keep_alive"] == [True]
    assert not final_summary_path.exists()

    from PIL import Image

    movie_dir = Path(captured["output"].output_directory.path)
    movie_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (256, 144), color=(10, 120, 180)).save(movie_dir / "movie_frame_0010.png")
    Image.new("RGB", (256, 144), color=(12, 120, 180)).save(movie_dir / "movie_frame_0012.png")

    captured["executor"].on_executor_finished_delegate.callback(captured["executor"], True)

    manifest = json.loads((out_dir / "preview_manifest.json").read_text(encoding="utf-8"))
    final_summary = json.loads(final_summary_path.read_text(encoding="utf-8"))
    latest_summary = json.loads(latest_summary_path.read_text(encoding="utf-8"))

    assert manifest["capture_success"] is True
    assert manifest["capture_pending"] is False
    assert final_summary["scene_id"] == "scene19"
    assert final_summary["render_result"]["capture_success"] is True
    assert final_summary["render_result"]["capture_pending"] is False
    assert latest_summary == final_summary
    assert (out_dir / "preview_frame.png").stat().st_size > 128
    assert captured["keep_alive"] == [True, False]
    assert captured["unregistered"] is True

    polling_out_dir = tmp_path / "polling_artifacts"
    polling_summary_path = polling_out_dir / "build_render_summary.json"
    polling_latest_summary_path = tmp_path / "polling_latest_build_render_summary.json"
    polling_result = cineu_render_ops.render_preview(
        {
            "sequence_path": "/Game/AnimalHitchcockZoom",
            "output_dir": str(polling_out_dir),
            "world_state_path": str(state_path),
            "resolution": [1280, 720],
            "format": "mp4",
            "quality": "cinematic",
            "render_backend": "movie_render_pipeline",
            "fps": 30,
            "start_frame": 0,
            "end_frame": 166,
            "native_capture_start_frame": 10,
            "native_capture_end_frame": 14,
            "mrq_output_frame_step": 2,
            "capture_timeout_sec": 600,
            "completion_summary_path": str(polling_summary_path),
            "latest_summary_path": str(polling_latest_summary_path),
            "completion_summary_base": {"scene_id": "scene19", "render_result": {"stale": True}},
        }
    )

    assert polling_result["capture_pending"] is True
    assert not polling_summary_path.exists()

    movie_dir = Path(captured["output"].output_directory.path)
    movie_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (256, 144), color=(10, 120, 180)).save(movie_dir / "movie_frame_0010.png")
    Image.new("RGB", (256, 144), color=(12, 120, 180)).save(movie_dir / "movie_frame_0012.png")

    captured["tick_callbacks"][-1](0.016)

    polling_manifest = json.loads((polling_out_dir / "preview_manifest.json").read_text(encoding="utf-8"))
    polling_summary = json.loads(polling_summary_path.read_text(encoding="utf-8"))

    assert polling_manifest["capture_success"] is True
    assert polling_manifest["capture_pending"] is False
    assert any(warning.get("reason") == "movie_render_pipeline_completed_without_delegate" for warning in polling_manifest["warnings"])
    assert all(warning.get("reason") != "deadline" for warning in polling_manifest["warnings"])
    assert polling_summary["render_result"]["capture_success"] is True
    assert polling_summary["render_result"]["capture_pending"] is False
    assert json.loads(polling_latest_summary_path.read_text(encoding="utf-8")) == polling_summary
    assert (polling_out_dir / "preview_frame.png").stat().st_size > 128

    deadline_out_dir = tmp_path / "deadline_artifacts"
    deadline_summary_path = deadline_out_dir / "build_render_summary.json"
    deadline_latest_summary_path = tmp_path / "deadline_latest_build_render_summary.json"
    deadline_result = cineu_render_ops.render_preview(
        {
            "sequence_path": "/Game/AnimalHitchcockZoom",
            "output_dir": str(deadline_out_dir),
            "world_state_path": str(state_path),
            "resolution": [1280, 720],
            "format": "mp4",
            "quality": "cinematic",
            "render_backend": "movie_render_pipeline",
            "fps": 30,
            "start_frame": 0,
            "end_frame": 166,
            "native_capture_start_frame": 10,
            "native_capture_end_frame": 14,
            "mrq_output_frame_step": 2,
            "capture_timeout_sec": -1,
            "completion_summary_path": str(deadline_summary_path),
            "latest_summary_path": str(deadline_latest_summary_path),
            "completion_summary_base": {"scene_id": "scene19", "render_result": {"stale": True}},
        }
    )

    assert deadline_result["capture_pending"] is True
    assert not deadline_summary_path.exists()

    movie_dir = Path(captured["output"].output_directory.path)
    movie_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (256, 144), color=(10, 120, 180)).save(movie_dir / "movie_frame_0010.png")
    Image.new("RGB", (256, 144), color=(12, 120, 180)).save(movie_dir / "movie_frame_0012.png")

    captured["tick_callbacks"][-1](0.016)

    deadline_manifest = json.loads((deadline_out_dir / "preview_manifest.json").read_text(encoding="utf-8"))
    deadline_summary = json.loads(deadline_summary_path.read_text(encoding="utf-8"))

    assert deadline_manifest["capture_success"] is True
    assert deadline_manifest["capture_pending"] is False
    assert any(warning.get("reason") == "movie_render_pipeline_completed_without_delegate" for warning in deadline_manifest["warnings"])
    assert all(warning.get("reason") != "deadline" for warning in deadline_manifest["warnings"])
    assert deadline_summary["render_result"]["capture_success"] is True
    assert deadline_summary["render_result"]["capture_pending"] is False
    assert json.loads(deadline_latest_summary_path.read_text(encoding="utf-8")) == deadline_summary
    assert (deadline_out_dir / "preview_frame.png").stat().st_size > 128
    assert captured["keep_alive"] == [True, False, True, False, True, False]


def test_render_preview_uses_movie_render_pipeline_sampled_source_frames(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_render_ops

    state_path = tmp_path / "world_current.json"
    state_path.write_text(
        json.dumps(
            {
                "level": "Showcase",
                "sequences": {
                    "/Game/AnimalHitchcockZoom": {
                        "sequence_path": "/Game/AnimalHitchcockZoom",
                        "source_asset_type": "level_sequence",
                        "level_path": "/Game/CityPark/Maps/Showcase",
                        "fps": 30,
                        "asset_fps": 60,
                        "range": [0, 166],
                        "camera_cuts": [
                            {"camera_name": "NativeSequenceCamera", "shot_id": "shot_001", "start_frame": 0, "end_frame": 166}
                        ],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    captured = {}

    class SoftObjectPath(str):
        pass

    class FrameRate:
        def __init__(self, numerator, denominator):
            self.numerator = int(numerator)
            self.denominator = int(denominator)

    class IntPoint:
        def __init__(self, x, y):
            self.x = int(x)
            self.y = int(y)

    class OutputDirectory:
        def __init__(self):
            self.path = ""

        def set_editor_property(self, name, value):
            assert name == "path"
            self.path = str(value)

    class MoviePipelineOutputSetting:
        def __init__(self):
            self.output_directory = OutputDirectory()

    class MoviePipelineDeferredPassBase:
        pass

    class MoviePipelineImageSequenceOutput_PNG:
        pass

    class MoviePipelineAntiAliasingSetting:
        pass

    class MoviePipelineGameOverrideSetting:
        pass

    class JobConfig:
        def __init__(self):
            self.settings = {}

        def find_or_add_setting_by_class(self, cls):
            self.settings.setdefault(cls, cls())
            return self.settings[cls]

        def initialize_transient_settings(self):
            captured.setdefault("initialized_jobs", 0)
            captured["initialized_jobs"] += 1

    class MoviePipelineExecutorJob:
        def __init__(self):
            self.config = JobConfig()

        def get_configuration(self):
            return self.config

    class MoviePipelineQueue:
        def __init__(self):
            self.jobs = []

        def delete_all_jobs(self):
            self.jobs.clear()

        def allocate_new_job(self, cls):
            job = cls()
            self.jobs.append(job)
            return job

        def get_jobs(self):
            return list(self.jobs)

    class Delegate:
        def __init__(self):
            self.callback = None

        def add_callable_unique(self, callback):
            self.callback = callback

    class MoviePipelinePIEExecutor:
        def __init__(self, subsystem=None):
            self.subsystem = subsystem
            self.on_executor_finished_delegate = Delegate()

    class MoviePipelineQueueSubsystem:
        def __init__(self):
            self.queue = MoviePipelineQueue()

        def get_queue(self):
            return self.queue

        def render_queue_with_executor_instance(self, executor):
            from PIL import Image

            captured["jobs"] = self.queue.get_jobs()
            for job in captured["jobs"]:
                output = job.get_configuration().settings[MoviePipelineOutputSetting]
                out_dir = Path(output.output_directory.path)
                out_dir.mkdir(parents=True, exist_ok=True)
                for frame in range(output.custom_start_frame, output.custom_end_frame):
                    Image.new("RGB", (256, 144), color=(frame % 255, 140, 160)).save(out_dir / f"movie_frame_{frame:04d}.png")
            executor.on_executor_finished_delegate.callback(executor, True)

    subsystem = MoviePipelineQueueSubsystem()

    class EditorLevelLibrary:
        @staticmethod
        def load_level(path):
            captured["loaded_level"] = path
            return True

    class EditorPythonScripting:
        @staticmethod
        def set_keep_python_script_alive(enabled):
            captured.setdefault("keep_alive", []).append(bool(enabled))

    fake_unreal = type(
        "FakeUnreal",
        (),
        {
            "SoftObjectPath": SoftObjectPath,
            "FrameRate": FrameRate,
            "IntPoint": IntPoint,
            "MoviePipelineQueueSubsystem": MoviePipelineQueueSubsystem,
            "MoviePipelineExecutorJob": MoviePipelineExecutorJob,
            "MoviePipelinePIEExecutor": MoviePipelinePIEExecutor,
            "MoviePipelineOutputSetting": MoviePipelineOutputSetting,
            "MoviePipelineDeferredPassBase": MoviePipelineDeferredPassBase,
            "MoviePipelineImageSequenceOutput_PNG": MoviePipelineImageSequenceOutput_PNG,
            "MoviePipelineAntiAliasingSetting": MoviePipelineAntiAliasingSetting,
            "MoviePipelineGameOverrideSetting": MoviePipelineGameOverrideSetting,
            "EditorLevelLibrary": EditorLevelLibrary,
            "EditorPythonScripting": EditorPythonScripting,
            "get_editor_subsystem": staticmethod(lambda cls: subsystem),
            "register_slate_post_tick_callback": staticmethod(lambda _callback: 1),
            "unregister_slate_post_tick_callback": staticmethod(lambda _handle: captured.setdefault("unregistered", True)),
        },
    )
    monkeypatch.setattr(cineu_render_ops, "unreal", fake_unreal)

    result = cineu_render_ops.render_preview(
        {
            "sequence_path": "/Game/AnimalHitchcockZoom",
            "output_dir": str(tmp_path / "artifacts"),
            "world_state_path": str(state_path),
            "resolution": [1280, 720],
            "format": "mp4",
            "quality": "cinematic",
            "render_backend": "movie_render_pipeline",
            "fps": 30,
            "start_frame": 0,
            "end_frame": 166,
            "native_capture_start_frame": 10,
            "native_capture_end_frame": 20,
            "mrq_sampled_source_frames": [10, 13, 18],
        }
    )

    out_dir = tmp_path / "artifacts"
    manifest = json.loads((out_dir / "preview_manifest.json").read_text(encoding="utf-8"))
    job_ranges = [
        (
            job.get_configuration().settings[MoviePipelineOutputSetting].custom_start_frame,
            job.get_configuration().settings[MoviePipelineOutputSetting].custom_end_frame,
        )
        for job in captured["jobs"]
    ]

    assert result["render_backend"] == "movie_render_pipeline"
    assert job_ranges == [(10, 11), (13, 14), (18, 19)]
    assert manifest["movie_render_pipeline_frame_range"] == [10, 20]
    assert manifest["movie_render_pipeline_sampled_source_frames"] == [10, 13, 18]
    assert [frame["frame"] for frame in manifest["storyboard_frames"]] == [10, 13, 18]
    assert (out_dir / "movie_frames" / "movie_frame_0010.png").stat().st_size > 128
    assert (out_dir / "movie_frames" / "movie_frame_0013.png").stat().st_size > 128
    assert (out_dir / "movie_frames" / "movie_frame_0018.png").stat().st_size > 128
    assert (out_dir / "preview_frame.png").stat().st_size > 128


def test_render_preview_records_movie_render_pipeline_output_rate_mapping(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_render_ops

    state_path = tmp_path / "world_current.json"
    state_path.write_text(
        json.dumps(
            {
                "level": "Showcase",
                "sequences": {
                    "/Game/AnimalHitchcockZoom": {
                        "sequence_path": "/Game/AnimalHitchcockZoom",
                        "source_asset_type": "level_sequence",
                        "level_path": "/Game/CityPark/Maps/Showcase",
                        "fps": 30,
                        "asset_fps": 60,
                        "range": [0, 166],
                        "camera_cuts": [
                            {"camera_name": "NativeSequenceCamera", "shot_id": "shot_001", "start_frame": 0, "end_frame": 166}
                        ],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    captured = {}

    class SoftObjectPath(str):
        pass

    class FrameRate:
        def __init__(self, numerator, denominator):
            self.numerator = int(numerator)
            self.denominator = int(denominator)

    class IntPoint:
        def __init__(self, x, y):
            self.x = int(x)
            self.y = int(y)

    class OutputDirectory:
        def __init__(self):
            self.path = ""

        def set_editor_property(self, name, value):
            assert name == "path"
            self.path = str(value)

    class MoviePipelineOutputSetting:
        def __init__(self):
            self.output_directory = OutputDirectory()

    class MoviePipelineDeferredPassBase:
        pass

    class MoviePipelineImageSequenceOutput_PNG:
        pass

    class MoviePipelineAntiAliasingSetting:
        pass

    class MoviePipelineGameOverrideSetting:
        pass

    class JobConfig:
        def __init__(self):
            self.settings = {}

        def find_or_add_setting_by_class(self, cls):
            self.settings.setdefault(cls, cls())
            return self.settings[cls]

        def initialize_transient_settings(self):
            captured["initialized_transient_settings"] = True

    class MoviePipelineExecutorJob:
        def __init__(self):
            self.config = JobConfig()

        def get_configuration(self):
            return self.config

    class MoviePipelineQueue:
        def __init__(self):
            self.jobs = []

        def delete_all_jobs(self):
            self.jobs.clear()

        def allocate_new_job(self, cls):
            job = cls()
            self.jobs.append(job)
            return job

        def get_jobs(self):
            return list(self.jobs)

    class Delegate:
        def __init__(self):
            self.callback = None

        def add_callable_unique(self, callback):
            self.callback = callback

    class MoviePipelinePIEExecutor:
        def __init__(self, subsystem=None):
            self.subsystem = subsystem
            self.on_executor_finished_delegate = Delegate()

    class MoviePipelineQueueSubsystem:
        def __init__(self):
            self.queue = MoviePipelineQueue()

        def get_queue(self):
            return self.queue

        def render_queue_with_executor_instance(self, executor):
            from PIL import Image

            [job] = self.queue.get_jobs()
            captured["job"] = job
            output = job.get_configuration().settings[MoviePipelineOutputSetting]
            captured["output"] = output
            out_dir = Path(output.output_directory.path)
            out_dir.mkdir(parents=True, exist_ok=True)
            output_start = int(round(output.custom_start_frame * output.output_frame_rate.numerator / 60))
            output_count = int(round((output.custom_end_frame - output.custom_start_frame) * output.output_frame_rate.numerator / 60))
            for frame in range(output_start, output_start + output_count):
                Image.new("RGB", (256, 144), color=(frame % 255, 120, 180)).save(out_dir / f"movie_frame_{frame:04d}.png")
            executor.on_executor_finished_delegate.callback(executor, True)

    subsystem = MoviePipelineQueueSubsystem()

    class EditorLevelLibrary:
        @staticmethod
        def load_level(path):
            captured["loaded_level"] = path
            return True

    class EditorPythonScripting:
        @staticmethod
        def set_keep_python_script_alive(enabled):
            captured.setdefault("keep_alive", []).append(bool(enabled))

    fake_unreal = type(
        "FakeUnreal",
        (),
        {
            "SoftObjectPath": SoftObjectPath,
            "FrameRate": FrameRate,
            "IntPoint": IntPoint,
            "MoviePipelineQueueSubsystem": MoviePipelineQueueSubsystem,
            "MoviePipelineExecutorJob": MoviePipelineExecutorJob,
            "MoviePipelinePIEExecutor": MoviePipelinePIEExecutor,
            "MoviePipelineOutputSetting": MoviePipelineOutputSetting,
            "MoviePipelineDeferredPassBase": MoviePipelineDeferredPassBase,
            "MoviePipelineImageSequenceOutput_PNG": MoviePipelineImageSequenceOutput_PNG,
            "MoviePipelineAntiAliasingSetting": MoviePipelineAntiAliasingSetting,
            "MoviePipelineGameOverrideSetting": MoviePipelineGameOverrideSetting,
            "EditorLevelLibrary": EditorLevelLibrary,
            "EditorPythonScripting": EditorPythonScripting,
            "get_editor_subsystem": staticmethod(lambda cls: subsystem),
            "register_slate_post_tick_callback": staticmethod(lambda _callback: 1),
            "unregister_slate_post_tick_callback": staticmethod(lambda _handle: captured.setdefault("unregistered", True)),
        },
    )
    monkeypatch.setattr(cineu_render_ops, "unreal", fake_unreal)

    result = cineu_render_ops.render_preview(
        {
            "sequence_path": "/Game/AnimalHitchcockZoom",
            "output_dir": str(tmp_path / "artifacts"),
            "world_state_path": str(state_path),
            "resolution": [1280, 720],
            "format": "mp4",
            "quality": "cinematic",
            "render_backend": "movie_render_pipeline",
            "fps": 30,
            "start_frame": 0,
            "end_frame": 166,
            "native_capture_start_frame": 10,
            "native_capture_end_frame": 30,
            "mrq_output_frame_rate": 30,
        }
    )

    out_dir = tmp_path / "artifacts"
    manifest = json.loads((out_dir / "preview_manifest.json").read_text(encoding="utf-8"))
    output_map = manifest["movie_render_pipeline_output_frame_map"]

    assert result["render_backend"] == "movie_render_pipeline"
    assert captured["output"].custom_start_frame == 10
    assert captured["output"].custom_end_frame == 30
    assert captured["output"].output_frame_rate.numerator == 30
    assert captured["output"].output_frame_rate.denominator == 1
    assert manifest["movie_render_pipeline_source_frame_rate"] == {"numerator": 60, "denominator": 1}
    assert manifest["movie_render_pipeline_output_frame_rate"] == {"numerator": 30, "denominator": 1}
    assert manifest["movie_render_pipeline_output_frame_range"] == [5, 15]
    assert output_map[0] == {"output_frame": 5, "source_frame": 10, "file_name": "movie_frame_0005.png"}
    assert output_map[-1] == {"output_frame": 14, "source_frame": 28, "file_name": "movie_frame_0014.png"}
    assert [frame["frame"] for frame in manifest["storyboard_frames"]] == [5, 6, 7, 8, 9, 11, 12, 13, 14]
    assert manifest["storyboard_frames"][0]["source_frame"] == 10
    assert (out_dir / "preview_frame.png").stat().st_size > 128


def test_render_preview_uses_movie_capture_for_generated_sequence(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_render_ops

    state_path = tmp_path / "world_current.json"
    sequence_path = "/Game/CineU/Sequences/SEQ_run_real"
    state_path.write_text(
        json.dumps(
            {
                "sequences": {
                    sequence_path: {
                        "sequence_path": sequence_path,
                        "fps": 24,
                        "range": [0, 126],
                        "camera_cuts": [
                            {"camera_name": "CAM_shot_001", "shot_id": "shot_001", "start_frame": 0, "end_frame": 126}
                        ],
                        "cameras": {
                            "CAM_shot_001": {
                                "transform_keys": [
                                    {"frame": 0, "location": [0, 0, 100], "rotation": [0, 0, 0]},
                                    {"frame": 126, "location": [100, 0, 100], "rotation": [0, 0, 0]},
                                ],
                                "focal_length_keys": [
                                    {"frame": 0, "focal_length": 45.0},
                                    {"frame": 126, "focal_length": 30.0},
                                ],
                            }
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    called = {}

    def fake_native_preview(inputs, state, out, preview_frame, preview_manifest, storyboard_manifest, warnings):
        called["sequence_path"] = inputs["sequence_path"]
        return {"render_backend": "sequencer_movie_capture", "sequence_path": inputs["sequence_path"], "warnings": warnings}

    class FakeUnreal:
        AutomatedLevelSequenceCapture = object
        SequencerTools = object

    monkeypatch.setattr(cineu_render_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_render_ops, "_render_native_level_sequence_preview", fake_native_preview)

    result = cineu_render_ops.render_preview(
        {
            "sequence_path": sequence_path,
            "output_dir": str(tmp_path / "artifacts"),
            "world_state_path": str(state_path),
            "resolution": [1280, 720],
            "format": "mp4",
            "quality": "preview",
        }
    )

    assert result["render_backend"] == "sequencer_movie_capture"
    assert called["sequence_path"] == sequence_path


def test_render_preview_scene_capture_backend_skips_native_movie_capture(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_render_ops

    state_path = tmp_path / "world_current.json"
    sequence_path = "/Game/CineU/Sequences/SEQ_scene_capture_requested"
    state_path.write_text(
        json.dumps(
            {
                "sequences": {
                    sequence_path: {
                        "sequence_path": sequence_path,
                        "fps": 24,
                        "range": [0, 24],
                        "camera_cuts": [
                            {"camera_name": "CAM_scene_capture", "shot_id": "shot_001", "start_frame": 0, "end_frame": 24}
                        ],
                        "cameras": {
                            "CAM_scene_capture": {
                                "transform_keys": [
                                    {"frame": 0, "location": [0, 0, 100], "rotation": [0, 0, 0]},
                                    {"frame": 24, "location": [100, 0, 100], "rotation": [0, 0, 0]},
                                ],
                                "focal_length_keys": [{"frame": 0, "focal_length": 35.0}],
                            }
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    def fail_native_preview(*_args, **_kwargs):
        raise AssertionError("scene_capture backend should not call native movie capture")

    class FakeUnreal:
        AutomatedLevelSequenceCapture = object
        SequencerTools = object

    monkeypatch.setattr(cineu_render_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_render_ops, "_render_native_level_sequence_preview", fail_native_preview)

    result = cineu_render_ops.render_preview(
        {
            "sequence_path": sequence_path,
            "output_dir": str(tmp_path / "artifacts"),
            "world_state_path": str(state_path),
            "resolution": [1280, 720],
            "format": "png",
            "quality": "preview",
            "render_backend": "scene_capture",
        }
    )

    assert result["preview_camera"] == "CAM_scene_capture"
    assert result["storyboard_frames"]
    assert "render_backend" not in result


def test_render_preview_scene_capture_sequence_writes_full_frame_sequence(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("CINEU_SCENE_CAPTURE_EVALUATE_SEQUENCE", raising=False)
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_render_ops

    state_path = tmp_path / "world_current.json"
    sequence_path = "/Game/CineU/Sequences/SEQ_scene_capture_sequence"
    state_path.write_text(
        json.dumps(
            {
                "sequences": {
                    sequence_path: {
                        "sequence_path": sequence_path,
                        "fps": 24,
                        "range": [0, 5],
                        "camera_cuts": [
                            {"camera_name": "CAM_A", "shot_id": "shot_a", "start_frame": 0, "end_frame": 3},
                            {"camera_name": "CAM_B", "shot_id": "shot_b", "start_frame": 3, "end_frame": 5},
                        ],
                        "cameras": {
                            "CAM_A": {
                                "transform_keys": [
                                    {"frame": 0, "location": [0, 0, 100], "rotation": [0, 0, 0]},
                                    {"frame": 3, "location": [30, 0, 100], "rotation": [0, 0, 15]},
                                ],
                                "focal_length_keys": [{"frame": 0, "focal_length": 35.0}],
                            },
                            "CAM_B": {
                                "transform_keys": [
                                    {"frame": 3, "location": [30, 10, 110], "rotation": [-2, 0, 25]},
                                    {"frame": 5, "location": [45, 20, 110], "rotation": [-4, 0, 35]},
                                ],
                                "focal_length_keys": [{"frame": 3, "focal_length": 50.0}],
                            },
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    applied_frames = []
    captured_frames = []

    monkeypatch.setattr(cineu_render_ops, "unreal", object())
    monkeypatch.setattr(
        cineu_render_ops,
        "_apply_sequence_frame_state",
        lambda _state, _sequence_path, frame, _warnings, evaluate_sequence=True: applied_frames.append(
            (frame, evaluate_sequence)
        ),
    )
    monkeypatch.setattr(cineu_render_ops, "_apply_camera_sample", lambda sample, _warnings, pilot_preview=True: True)

    def fake_capture(path, width, height, camera_name, focal_length, warnings, exposure_bias=None, exposure_brightness=None):
        captured_frames.append((Path(path).name, width, height, camera_name, focal_length, exposure_bias, exposure_brightness))
        Path(path).write_bytes(b"scene capture frame bytes" + b"x" * 160)
        return True

    monkeypatch.setattr(cineu_render_ops, "_capture_scene_to_png", fake_capture)

    result = cineu_render_ops.render_preview(
        {
            "sequence_path": sequence_path,
            "output_dir": str(tmp_path / "artifacts"),
            "world_state_path": str(state_path),
            "resolution": [640, 360],
            "format": "mp4",
            "quality": "preview",
            "render_backend": "scene_capture_sequence",
            "start_frame": 1,
            "end_frame": 5,
        }
    )

    out_dir = tmp_path / "artifacts"
    movie_dir = out_dir / "movie_frames"
    manifest = json.loads((out_dir / "preview_manifest.json").read_text(encoding="utf-8"))
    storyboard = json.loads((out_dir / "storyboard_manifest.json").read_text(encoding="utf-8"))

    assert result["render_backend"] == "scene_capture_sequence"
    assert result["capture_success"] is True
    assert manifest["render_backend"] == "scene_capture_sequence"
    assert manifest["scene_capture_sequence_frame_range"] == [1, 5]
    assert manifest["movie_frame_dir"] == str(movie_dir)
    assert storyboard["render_backend"] == "scene_capture_sequence"
    assert [path.name for path in sorted(movie_dir.glob("movie_frame_*.png"))] == [
        "movie_frame_0001.png",
        "movie_frame_0002.png",
        "movie_frame_0003.png",
        "movie_frame_0004.png",
    ]
    assert [item[0] for item in captured_frames[:4]] == [
        "movie_frame_0001.png",
        "movie_frame_0002.png",
        "movie_frame_0003.png",
        "movie_frame_0004.png",
    ]
    assert [item[0] for item in applied_frames[:4]] == [1, 2, 3, 4]
    assert all(item[1] is True for item in applied_frames[:4])
    assert captured_frames[0][1:4] == (640, 360, "CAM_A")
    assert captured_frames[2][3] == "CAM_B"
    assert (out_dir / "preview_frame.png").stat().st_size > 128


def test_scene_capture_sequence_sample_preserves_camera_exposure_controls(tmp_path: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_render_ops

    sequence = {
        "camera_cuts": [{"camera_name": "CAM_A", "shot_id": "shot_a", "start_frame": 0, "end_frame": 10}],
        "cameras": {
            "CAM_A": {
                "transform_keys": [{"frame": 0, "location": [0, 0, 0], "rotation": [0, 0, 0]}],
                "focal_length_keys": [{"frame": 0, "focal_length": 35.0}],
                "exposure_bias": -0.9,
                "exposure_brightness": 0.52,
            }
        },
    }

    sample = cineu_render_ops._scene_capture_sequence_sample(sequence, 4, 0, 10)

    assert sample["camera_name"] == "CAM_A"
    assert sample["exposure_bias"] == -0.9
    assert sample["exposure_brightness"] == 0.52
