from __future__ import annotations

from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1] / "unreal_project" / "Plugins" / "CineUDemo" / "Content" / "Python"


def test_transform_section_uses_get_all_channels_when_get_channels_is_unavailable(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_camera_ops

    calls = []

    class FakeChannel:
        def add_key(self, frame, value, *args):
            calls.append((frame.value, value))

    class FakeFrameNumber:
        def __init__(self, value):
            self.value = value

    class FakeSection:
        def get_all_channels(self):
            return [FakeChannel() for _ in range(9)]

    monkeypatch.setattr(cineu_camera_ops, "unreal", type("FakeUnreal", (), {"FrameNumber": FakeFrameNumber}))
    warnings = []

    cineu_camera_ops._try_key_transform_section(
        FakeSection(),
        [{"frame": 12, "location": [1, 2, 3], "rotation": [4, 5, 6]}],
        warnings,
    )

    assert warnings == []
    assert calls[:6] == [(12, 1.0), (12, 2.0), (12, 3.0), (12, 5.0), (12, 4.0), (12, 6.0)]


def test_create_camera_shot_keys_cine_camera_focal_length_track(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_camera_ops

    focal_keys = []
    property_paths = []

    class FakeFrameNumber:
        def __init__(self, value):
            self.value = value

    class FakeFloatChannel:
        def add_key(self, frame, value, *args):
            if not args:
                raise TypeError("requires sub-frame")
            focal_keys.append((frame.value, value, args[0]))

    class FakeFloatSection:
        def set_range(self, start, end):
            self.range = (start, end)

        def get_all_channels(self):
            return [FakeFloatChannel()]

    class FakeFloatTrack:
        def set_property_name_and_path(self, name, path):
            property_paths.append((name, path))

        def add_section(self):
            return FakeFloatSection()

    class FakeTransformSection:
        def set_range(self, start, end):
            self.range = (start, end)

        def get_all_channels(self):
            return []

    class FakeTransformTrack:
        def add_section(self):
            return FakeTransformSection()

    class FakeBinding:
        def __init__(self, label):
            self.label = label
            self.parent = None

        def add_track(self, track_type):
            if track_type == "float-track":
                return FakeFloatTrack()
            return FakeTransformTrack()

        def set_parent(self, parent):
            self.parent = parent

    class FakeCameraComponent:
        def __init__(self):
            self.current_focal_length = None

    class FakeCamera:
        def __init__(self):
            self.component = FakeCameraComponent()

        def set_actor_label(self, label):
            self.label = label

        def set_actor_rotation(self, rotation, teleport):
            self.rotation = rotation

        def get_cine_camera_component(self):
            return self.component

    class FakeSequence:
        def __init__(self):
            self.bindings = []

        def add_possessable(self, obj):
            binding = FakeBinding(getattr(obj, "label", "component"))
            self.bindings.append(binding)
            return binding

    camera = FakeCamera()
    sequence = FakeSequence()
    fake_unreal = type(
        "FakeUnreal",
        (),
        {
            "EditorAssetLibrary": type("AssetLib", (), {"load_asset": staticmethod(lambda path: sequence), "save_asset": staticmethod(lambda path: True)}),
            "EditorLevelLibrary": type("LevelLib", (), {"spawn_actor_from_class": staticmethod(lambda cls, loc: camera)}),
            "CineCameraActor": object,
            "MovieScene3DTransformTrack": "transform-track",
            "MovieSceneFloatTrack": "float-track",
            "FrameNumber": FakeFrameNumber,
            "Vector": staticmethod(lambda *values: values),
            "Rotator": staticmethod(lambda *args, **kwargs: ("rotator", args, kwargs)),
        },
    )
    monkeypatch.setattr(cineu_camera_ops, "unreal", fake_unreal)

    result = cineu_camera_ops.create_camera_shot(
        {
            "sequence_path": "/Game/CineU/Sequences/SEQ_test",
            "shot_id": "shot_001",
            "camera_name": "CAM_A",
            "start_frame": 0,
            "end_frame": 24,
            "keys": [
                {"frame": 0, "location": [0, 0, 0], "rotation": [0, 0, 0], "focal_length": 45.0},
                {"frame": 24, "location": [0, 0, 0], "rotation": [0, 0, 0], "focal_length": 27.0},
            ],
        }
    )

    assert result["warnings"] == []
    assert camera.component.current_focal_length == 27.0
    assert property_paths == [("CurrentFocalLength", "CurrentFocalLength")]
    assert focal_keys == [(0, 45.0, 0.0), (24, 27.0, 0.0)]
