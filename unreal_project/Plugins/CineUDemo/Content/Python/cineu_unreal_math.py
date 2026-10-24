from __future__ import annotations

from typing import Any


def rotator_from_pitch_roll_yaw(unreal_module: Any, rotation: list[float] | tuple[float, ...]):
    pitch = float(rotation[0])
    yaw = float(rotation[1])
    roll = float(rotation[2])
    try:
        return unreal_module.Rotator(pitch=pitch, roll=roll, yaw=yaw)
    except TypeError:
        return unreal_module.Rotator(pitch, yaw, roll)
