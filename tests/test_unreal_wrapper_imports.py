from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1] / "unreal_project" / "Plugins" / "CineUDemo" / "Content" / "Python"


def test_sequence_and_camera_modules_import_outside_unreal(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_anim_ops
    import cineu_camera_ops
    import cineu_sequence_ops

    assert cineu_camera_ops.unreal is None
    assert cineu_sequence_ops.unreal is None
    assert cineu_anim_ops.find_clip_path({"animation_type": "run"}, {"animations": [{"name": "run", "path": "/Game/A_Run"}]}) == "/Game/A_Run"
