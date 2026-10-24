from __future__ import annotations

from typing import Any


CITYPARK_PATH_ANCHOR_ACTOR = "InstancedFoliageActor2"
CITYPARK_PATH_START = (6241.53, -12053.676, -630.004)
CITYPARK_PATH_END = (6241.53, -12303.676, -630.004)
CITYPARK_PATH_BOUNDS = (5600.0, 6800.0, -12650.0, -11850.0)
CITYPARK_REFERENCE_SEQUENCE_PATH = "/Game/AnimalHitchcockZoom"
CITYPARK_REFERENCE_CAPTURE_PATH = "Saved/VideoCaptures/Showcase_(2).avi"
CITYPARK_REFERENCE_CAPTURE_START_FRAME = 10
CITYPARK_REFERENCE_CAPTURE_END_FRAME = 330
CITYPARK_REFERENCE_CAMERA_PATH = {
    "source_frame_range": [0, 144],
    "location_start": [5790.256, -13167.531, -491.342],
    "location_end": [5922.887, -12845.076, -488.91],
    "rotation_start": [-0.000002, 0.399902, 67.641907],
    "rotation_end": [-0.000002, 0.399902, 67.641907],
    "target_location": [6241.53, -12153.676, -604.504],
    "focal_length_start": 35.0,
    "focal_length_end": 24.16,
}


def citypark_path_support_surface(*, level_backed: bool = False) -> dict[str, Any]:
    surface: dict[str, Any] = {
        "type": "ground",
        "z": CITYPARK_PATH_START[2],
        "bounds": list(CITYPARK_PATH_BOUNDS),
        "anchor_actor": CITYPARK_PATH_ANCHOR_ACTOR,
    }
    if level_backed:
        surface["environment_asset_type"] = "level"
    return surface
