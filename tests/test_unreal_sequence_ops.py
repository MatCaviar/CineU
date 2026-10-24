from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace


PLUGIN_DIR = Path(__file__).resolve().parents[1] / "unreal_project" / "Plugins" / "CineUDemo" / "Content" / "Python"


def test_create_level_sequence_rebuilds_generated_cineu_sequence(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_sequence_ops

    events = []

    class FakeSequence:
        def set_display_rate(self, frame_rate):
            events.append(("display_rate", frame_rate.numerator))

        def set_playback_start(self, frame):
            events.append(("start", frame))

        def set_playback_end(self, frame):
            events.append(("end", frame))

    class FakeAssetTools:
        def create_asset(self, name, package_path, asset_class, factory):
            events.append(("create", name, package_path))
            return FakeSequence()

    fake_unreal = SimpleNamespace(
        AssetToolsHelpers=SimpleNamespace(get_asset_tools=lambda: FakeAssetTools()),
        LevelSequenceFactoryNew=lambda: object(),
        LevelSequence=object,
        FrameRate=lambda numerator, denominator: SimpleNamespace(numerator=numerator, denominator=denominator),
        EditorAssetLibrary=SimpleNamespace(
            load_asset=lambda path: object(),
            delete_asset=lambda path: events.append(("delete", path)) or True,
            save_asset=lambda path: events.append(("save", path)) or True,
        ),
    )
    monkeypatch.setattr(cineu_sequence_ops, "unreal", fake_unreal)

    cineu_sequence_ops.create_level_sequence(
        {
            "sequence_path": "/Game/CineU/Sequences/SEQ_test",
            "fps": 24,
            "start_frame": 0,
            "end_frame": 48,
        }
    )

    assert events[:2] == [("delete", "/Game/CineU/Sequences/SEQ_test"), ("create", "SEQ_test", "/Game/CineU/Sequences")]


def test_use_existing_level_sequence_exports_bindings_tracks_and_camera_cuts(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_sequence_ops

    class FakeSection:
        def __init__(self, start, end):
            self.start = start
            self.end = end

        def get_start_frame(self):
            return self.start

        def get_end_frame(self):
            return self.end

    class FakeTrack:
        def __init__(self, name, sections):
            self.name = name
            self.sections = sections

        def get_display_name(self):
            return self.name

        def get_sections(self):
            return self.sections

        def get_class(self):
            return SimpleNamespace(get_name=lambda: f"{self.name}Class")

    class FakeBinding:
        def get_name(self):
            return "CineCameraActor_0"

        def get_id(self):
            return SimpleNamespace(export_text=lambda: "binding-guid-camera")

        def get_tracks(self):
            return [FakeTrack("CameraComponent", [FakeSection(0, 1728)]), FakeTrack("Transform", [FakeSection(0, 1728)])]

    class FakeSequence:
        def get_display_rate(self):
            return SimpleNamespace(numerator=60, denominator=1)

        def get_playback_start(self):
            return 0

        def get_playback_end(self):
            return 1728

        def get_bindings(self):
            return [FakeBinding()]

        def find_master_tracks_by_type(self, track_type):
            return [FakeTrack("CameraCut", [FakeSection(0, 1728)])]

    fake_unreal = SimpleNamespace(
        EditorAssetLibrary=SimpleNamespace(load_asset=lambda path: FakeSequence()),
        MovieSceneCameraCutTrack=object,
    )
    monkeypatch.setattr(cineu_sequence_ops, "unreal", fake_unreal)

    result = cineu_sequence_ops.use_existing_level_sequence({"sequence_path": "/Game/AnimalHitchcockZoom"})

    assert result["fps"] == 60
    assert result["display_rate"] == {"numerator": 60, "denominator": 1}
    assert result["range"] == [0, 1728]
    assert result["bindings"][0]["name"] == "CineCameraActor_0"
    assert result["bindings"][0]["id"] == "binding-guid-camera"
    assert [track["name"] for track in result["bindings"][0]["tracks"]] == ["CameraComponent", "Transform"]
    assert result["bindings"][0]["tracks"][0]["sections"] == [{"start_frame": 0, "end_frame": 1728}]
    assert result["camera_cut_sections"] == [{"start_frame": 0, "end_frame": 1728}]


def test_add_camera_cuts_uses_non_master_track_api_when_needed(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_sequence_ops

    class FakeSection:
        def set_start_frame_seconds(self, value):
            self.start = value

        def set_end_frame_seconds(self, value):
            self.end = value

    class FakeTrack:
        def __init__(self):
            self.sections = []

        def add_section(self):
            section = FakeSection()
            self.sections.append(section)
            return section

    class FakeSequence:
        def __init__(self):
            self.track = FakeTrack()

        def find_tracks_by_type(self, track_type):
            return []

        def add_track(self, track_type):
            return self.track

        def get_display_rate(self):
            return SimpleNamespace(numerator=24)

    fake_seq = FakeSequence()
    fake_unreal = SimpleNamespace(
        EditorAssetLibrary=SimpleNamespace(load_asset=lambda path: fake_seq, save_asset=lambda path: True),
        MovieSceneCameraCutTrack=object,
    )
    monkeypatch.setattr(cineu_sequence_ops, "unreal", fake_unreal)

    result = cineu_sequence_ops.add_camera_cuts(
        {
            "sequence_path": "/Game/CineU/Sequences/SEQ_test",
            "cuts": [{"camera_name": "CAM_A", "start_frame": 0, "end_frame": 24}],
        }
    )

    assert result["camera_cuts"][0]["camera_name"] == "CAM_A"
    assert len(fake_seq.track.sections) == 1


def test_add_camera_cuts_replaces_stale_sections_and_binds_named_camera(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_sequence_ops

    class FakeBinding:
        def __init__(self, name):
            self.name = name
            self.binding_id = f"binding:{name}"

        def get_name(self):
            return self.name

    class FakeSection:
        def __init__(self, label):
            self.label = label
            self.binding_id = None

        def set_range(self, start, end):
            self.range = (start, end)

        def set_camera_binding_id(self, binding_id):
            self.binding_id = binding_id

    class FakeTrack:
        def __init__(self):
            self.stale = FakeSection("stale")
            self.sections = [self.stale]
            self.removed = []

        def get_sections(self):
            return list(self.sections)

        def remove_section(self, section):
            self.removed.append(section.label)
            self.sections.remove(section)

        def add_section(self):
            section = FakeSection("new")
            self.sections.append(section)
            return section

    class FakeSequence:
        def __init__(self):
            self.track = FakeTrack()
            self.bindings = [FakeBinding("CAM_A")]

        def find_tracks_by_type(self, track_type):
            return [self.track]

        def get_display_rate(self):
            return SimpleNamespace(numerator=24)

        def get_bindings(self):
            return self.bindings

    fake_seq = FakeSequence()
    fake_unreal = SimpleNamespace(
        EditorAssetLibrary=SimpleNamespace(load_asset=lambda path: fake_seq, save_asset=lambda path: True),
        MovieSceneCameraCutTrack=object,
    )
    monkeypatch.setattr(cineu_sequence_ops, "unreal", fake_unreal)

    result = cineu_sequence_ops.add_camera_cuts(
        {
            "sequence_path": "/Game/CineU/Sequences/SEQ_test",
            "cuts": [{"camera_name": "CAM_A", "start_frame": 12, "end_frame": 36}],
        }
    )

    assert result["camera_cuts"][0]["camera_name"] == "CAM_A"
    assert fake_seq.track.removed == ["stale"]
    assert len(fake_seq.track.sections) == 1
    assert fake_seq.track.sections[0].range == (12, 36)
    assert fake_seq.track.sections[0].binding_id == "binding:CAM_A"


def test_add_camera_cuts_builds_movie_scene_object_binding_id_when_available(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_sequence_ops

    class FakeBindingId:
        def __init__(self):
            self.properties = {}

        def set_editor_property(self, name, value):
            self.properties[name] = value

    class FakeBinding:
        def get_name(self):
            return "CAM_A"

        def get_id(self):
            return "guid:CAM_A"

    class FakeSection:
        def set_range(self, start, end):
            self.range = (start, end)

        def set_camera_binding_id(self, binding_id):
            self.binding_id = binding_id

    class FakeTrack:
        def __init__(self):
            self.section = None

        def get_sections(self):
            return []

        def remove_section(self, section):
            raise AssertionError("no stale sections should be removed")

        def add_section(self):
            self.section = FakeSection()
            return self.section

    class FakeSequence:
        def __init__(self):
            self.track = FakeTrack()

        def find_tracks_by_type(self, track_type):
            return [self.track]

        def get_display_rate(self):
            return SimpleNamespace(numerator=24)

        def get_bindings(self):
            return [FakeBinding()]

    fake_seq = FakeSequence()
    fake_unreal = SimpleNamespace(
        EditorAssetLibrary=SimpleNamespace(load_asset=lambda path: fake_seq, save_asset=lambda path: True),
        MovieSceneCameraCutTrack=object,
        MovieSceneObjectBindingID=FakeBindingId,
    )
    monkeypatch.setattr(cineu_sequence_ops, "unreal", fake_unreal)

    cineu_sequence_ops.add_camera_cuts(
        {
            "sequence_path": "/Game/CineU/Sequences/SEQ_test",
            "cuts": [{"camera_name": "CAM_A", "start_frame": 0, "end_frame": 24}],
        }
    )

    binding_id = fake_seq.track.section.binding_id
    assert isinstance(binding_id, FakeBindingId)
    assert binding_id.properties["guid"] == "guid:CAM_A"
    assert binding_id.properties["sequence_id"] == 0
    assert binding_id.properties["resolve_parent_index"] == -1


def test_add_transform_tracks_uses_channel_key_fallback_and_ue_rotation_order(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_sequence_ops

    calls = []

    class FakeFrameNumber:
        def __init__(self, value):
            self.value = value

    class FakeChannel:
        def add_key(self, frame, value, *args):
            if not args:
                raise TypeError("UE channel requires sub-frame")
            calls.append((frame.value, value, args[0]))

    class FakeSection:
        def set_range(self, start, end):
            self.range = (start, end)

        def get_channels(self):
            return [FakeChannel() for _ in range(9)]

    class FakeTrack:
        def add_section(self):
            return FakeSection()

    class FakeBinding:
        def add_track(self, track_type):
            return FakeTrack()

    class FakeActor:
        def __init__(self):
            self.label = "zebra_01"

        def get_actor_label(self):
            return self.label

        def set_actor_location(self, location, sweep, teleport):
            self.location = location

        def set_actor_rotation(self, rotation, teleport):
            self.rotation = rotation

    class FakeSequence:
        def add_possessable(self, actor):
            return FakeBinding()

    actor = FakeActor()
    fake_unreal = SimpleNamespace(
        EditorAssetLibrary=SimpleNamespace(load_asset=lambda path: FakeSequence(), save_asset=lambda path: True),
        EditorLevelLibrary=SimpleNamespace(get_all_level_actors=lambda: [actor]),
        MovieScene3DTransformTrack=object,
        FrameNumber=FakeFrameNumber,
        Vector=lambda *values: values,
        Rotator=lambda *args, **kwargs: ("rotator", args, kwargs),
    )
    monkeypatch.setattr(cineu_sequence_ops, "unreal", fake_unreal)

    result = cineu_sequence_ops.add_transform_tracks(
        {
            "sequence_path": "/Game/CineU/Sequences/SEQ_test",
            "tracks": [
                {
                    "actor_name": "zebra_01",
                    "start_frame": 0,
                    "end_frame": 24,
                    "keys": [
                        {
                            "frame": 12,
                            "transform": {
                                "location": [1, 2, 3],
                                "rotation": [4, 5, 6],
                                "scale": [1, 1, 1],
                            },
                        }
                    ],
                }
            ],
        }
    )

    assert result["warnings"] == []
    assert calls[:6] == [(12, 1.0, 0.0), (12, 2.0, 0.0), (12, 3.0, 0.0), (12, 6.0, 0.0), (12, 4.0, 0.0), (12, 5.0, 0.0)]
