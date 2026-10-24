from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1] / "unreal_project" / "Plugins" / "CineUDemo" / "Content" / "Python"


def test_add_animation_tracks_binds_skeletal_animation_section(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_anim_ops

    calls = []

    class Actor:
        def get_actor_label(self):
            return "zebra_01"

    class Params:
        def __init__(self):
            self.animation = None

        def set_editor_property(self, name, value):
            calls.append(("params_prop", name, value))
            setattr(self, name, value)

    class Section:
        def __init__(self):
            self.params = Params()

        def set_range(self, start, end):
            calls.append(("range", start, end))

        def set_editor_property(self, name, value):
            calls.append(("section_prop", name, value))
            setattr(self, name, value)

    class Track:
        def __init__(self):
            self.section = Section()

        def add_section(self):
            calls.append(("add_section",))
            return self.section

    class Binding:
        def add_track(self, track_type):
            calls.append(("add_track", track_type))
            return Track()

    class Sequence:
        def add_possessable(self, actor):
            calls.append(("possess", actor.get_actor_label()))
            return Binding()

    class FakeAssetLibrary:
        @staticmethod
        def load_asset(path):
            calls.append(("load", path))
            if path == "/Game/CineU/Sequences/Test":
                return Sequence()
            if path == "/Game/AfricanAnimalsPack/Zebra/Animations/ANIM_Zebra_Gallop":
                return "ZebraGallopAnimation"
            return None

        @staticmethod
        def save_asset(path):
            calls.append(("save", path))

    class FakeLevelLibrary:
        @staticmethod
        def get_all_level_actors():
            return [Actor()]

    class FakeUnreal:
        EditorAssetLibrary = FakeAssetLibrary
        EditorLevelLibrary = FakeLevelLibrary
        MovieSceneSkeletalAnimationTrack = "skeletal_animation_track"

    monkeypatch.setattr(cineu_anim_ops, "unreal", FakeUnreal)

    result = cineu_anim_ops.add_animation_tracks(
        {
            "sequence_path": "/Game/CineU/Sequences/Test",
            "clips": [
                {
                    "actor_name": "zebra_01",
                    "animation_path": "/Game/AfricanAnimalsPack/Zebra/Animations/ANIM_Zebra_Gallop",
                    "start_frame": 0,
                    "end_frame": 192,
                }
            ],
        }
    )

    assert result["animation_tracks"] == ["zebra_01"]
    assert not result["warnings"]
    assert ("possess", "zebra_01") in calls
    assert ("add_track", "skeletal_animation_track") in calls
    assert ("range", 0, 192) in calls
    assert ("params_prop", "animation", "ZebraGallopAnimation") in calls
    assert ("section_prop", "params", next(call[2] for call in calls if call[0] == "section_prop")) in calls
    assert ("save", "/Game/CineU/Sequences/Test") in calls
