from __future__ import annotations

from math import atan2, cos, degrees, radians, sin, sqrt
from typing import Any

import numpy as np


def normalize(v: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(v))
    if norm == 0:
        raise ValueError("Cannot normalize zero vector")
    return v / norm


def lerp_vec3(a: list[float], b: list[float], alpha: float) -> list[float]:
    return [float(a[i] + alpha * (b[i] - a[i])) for i in range(3)]


def look_at_rotation(camera_location: list[float], target_location: list[float]) -> list[float]:
    cx, cy, cz = camera_location
    tx, ty, tz = target_location
    dx, dy, dz = tx - cx, ty - cy, tz - cz
    yaw = degrees(atan2(dy, dx))
    horizontal = sqrt(dx * dx + dy * dy)
    pitch = degrees(atan2(dz, horizontal))
    return [pitch, 0.0, yaw]


def compute_hitchcock_zoom_keys(
    target_center: list[float],
    direction: list[float],
    distance_start: float,
    distance_end: float,
    focal_start: float,
    start_frame: int,
    end_frame: int,
    num_keys: int = 8,
) -> list[dict[str, Any]]:
    return compute_hitchcock_zoom_keys_for_target_path(
        target_start=target_center,
        target_end=target_center,
        direction=direction,
        distance_start=distance_start,
        distance_end=distance_end,
        focal_start=focal_start,
        start_frame=start_frame,
        end_frame=end_frame,
        num_keys=num_keys,
    )


def compute_hitchcock_zoom_keys_for_target_path(
    target_start: list[float],
    target_end: list[float],
    direction: list[float],
    distance_start: float,
    distance_end: float,
    focal_start: float,
    start_frame: int,
    end_frame: int,
    num_keys: int = 8,
) -> list[dict[str, Any]]:
    """Generate coupled camera/lens keys for static or moving subjects.

    The constant-framing invariant follows f(t) = f0 * d(t) / d0. For a moving
    target, the camera follows the target center while preserving the specified
    approach direction and distance schedule.
    """
    direction_v = normalize(np.array(direction, dtype=float))
    d0 = float(distance_start)
    if d0 <= 0:
        raise ValueError("distance_start must be positive")
    if num_keys < 2:
        raise ValueError("num_keys must be at least 2")
    keys: list[dict[str, Any]] = []
    for i in range(num_keys):
        alpha = i / (num_keys - 1)
        frame = round(start_frame + alpha * (end_frame - start_frame))
        distance = float(distance_start + alpha * (distance_end - distance_start))
        target = np.array(lerp_vec3(target_start, target_end, alpha), dtype=float)
        cam_pos = target - direction_v * distance
        focal = float(focal_start * distance / d0)
        rotation = look_at_rotation(cam_pos.tolist(), target.tolist())
        keys.append(
            {
                "frame": int(frame),
                "location": [float(x) for x in cam_pos.tolist()],
                "rotation": rotation,
                "focal_length": focal,
                "focus_distance": distance,
                "target_location": [float(x) for x in target.tolist()],
            }
        )
    return keys


def reference_camera_path_keys(
    location_start: list[float],
    location_end: list[float],
    target_location: list[float],
    focal_start: float,
    focal_end: float,
    start_frame: int,
    end_frame: int,
    num_keys: int = 8,
    rotation_start: list[float] | None = None,
    rotation_end: list[float] | None = None,
) -> list[dict[str, Any]]:
    if num_keys < 2:
        raise ValueError("num_keys must be at least 2")
    keys: list[dict[str, Any]] = []
    target = np.array(target_location, dtype=float)
    start_distance = float(np.linalg.norm(target - np.array(location_start, dtype=float)))
    if start_distance <= 0:
        raise ValueError("reference camera path start must not equal target location")
    for i in range(num_keys):
        alpha = i / (num_keys - 1)
        frame = round(start_frame + alpha * (end_frame - start_frame))
        loc = np.array(lerp_vec3(location_start, location_end, alpha), dtype=float)
        focus_distance = float(np.linalg.norm(target - loc))
        focal = float(focal_start * focus_distance / start_distance)
        rotation = (
            lerp_vec3(rotation_start, rotation_end, alpha)
            if rotation_start is not None and rotation_end is not None
            else look_at_rotation(loc.tolist(), target.tolist())
        )
        keys.append(
            {
                "frame": int(frame),
                "location": [float(x) for x in loc.tolist()],
                "rotation": rotation,
                "focal_length": focal,
                "focus_distance": focus_distance,
                "target_location": [float(x) for x in target.tolist()],
            }
        )
    return keys


def linear_camera_keys(
    start_location: list[float],
    end_location: list[float],
    target_location: list[float],
    start_frame: int,
    end_frame: int,
    focal_length: float,
) -> list[dict[str, Any]]:
    keys = []
    for frame, loc in [(start_frame, start_location), (end_frame, end_location)]:
        keys.append(
            {
                "frame": int(frame),
                "location": [float(x) for x in loc],
                "rotation": look_at_rotation(loc, target_location),
                "focal_length": float(focal_length),
                "focus_distance": float(np.linalg.norm(np.array(loc) - np.array(target_location))),
                "target_location": [float(x) for x in target_location],
            }
        )
    return keys


def orbit_camera_keys(
    target_location: list[float],
    radius: float,
    height: float,
    start_angle: float,
    end_angle: float,
    start_frame: int,
    end_frame: int,
    focal_length: float,
    num_keys: int = 8,
) -> list[dict[str, Any]]:
    if radius <= 0:
        raise ValueError("orbit radius must be positive")
    if num_keys < 2:
        raise ValueError("num_keys must be at least 2")
    keys = []
    for i in range(num_keys):
        alpha = i / (num_keys - 1)
        frame = round(start_frame + alpha * (end_frame - start_frame))
        angle = radians(start_angle + alpha * (end_angle - start_angle))
        loc = [
            float(target_location[0] + cos(angle) * radius),
            float(target_location[1] + sin(angle) * radius),
            float(target_location[2] + height),
        ]
        keys.append(
            {
                "frame": int(frame),
                "location": loc,
                "rotation": look_at_rotation(loc, target_location),
                "focal_length": float(focal_length),
                "focus_distance": float(np.linalg.norm(np.array(loc) - np.array(target_location))),
                "target_location": [float(x) for x in target_location],
            }
        )
    return keys
