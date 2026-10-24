from pathlib import Path
from types import SimpleNamespace


PLUGIN_DIR = Path(__file__).resolve().parents[1] / "unreal_project" / "Plugins" / "CineUDemo" / "Content" / "Python"


def test_rotator_from_pitch_roll_yaw_uses_project_pitch_yaw_roll_order(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    from cineu_unreal_math import rotator_from_pitch_roll_yaw

    class Rotator:
        def __init__(self, *, pitch, roll, yaw):
            self.pitch = pitch
            self.roll = roll
            self.yaw = yaw

    rotator = rotator_from_pitch_roll_yaw(SimpleNamespace(Rotator=Rotator), [-12.5, 90.0, 3.0])

    assert rotator.pitch == -12.5
    assert rotator.roll == 3.0
    assert rotator.yaw == 90.0
