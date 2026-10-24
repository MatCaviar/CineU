from __future__ import annotations

from typing import Any

from cineu_unreal_math import rotator_from_pitch_roll_yaw

try:
    import unreal  # type: ignore
except Exception:  # pragma: no cover
    unreal = None


def _require_unreal():
    if unreal is None:
        raise RuntimeError("This module must be executed inside Unreal Editor Python.")


def _try_add_channel_key(channel: Any, frame: int, value: float, warnings: list[Any]) -> None:
    try:
        channel.add_key(unreal.FrameNumber(int(frame)), float(value))
        return
    except Exception as first_exc:  # noqa: BLE001
        try:
            channel.add_key(unreal.FrameNumber(int(frame)), float(value), 0.0)
            return
        except Exception as second_exc:  # noqa: BLE001
            warnings.append(
                {
                    "channel": str(channel),
                    "frame": frame,
                    "error": f"{type(first_exc).__name__}:{first_exc};{type(second_exc).__name__}:{second_exc}",
                }
            )


def _try_key_transform_section(section: Any, keys: list[dict[str, Any]], warnings: list[Any]) -> None:
    if hasattr(section, "get_channels"):
        channels = list(section.get_channels())
    elif hasattr(section, "get_all_channels"):
        channels = list(section.get_all_channels())
    else:
        warnings.append("transform_section_has_no_supported_channel_api")
        return
    for key in keys:
        pitch, roll, yaw = [float(v) for v in key.get("rotation", [0, 0, 0])]
        values = [
            *[float(v) for v in key.get("location", [0, 0, 0])],
            roll,
            pitch,
            yaw,
            1.0,
            1.0,
            1.0,
        ]
        for channel, value in zip(channels, values):
            _try_add_channel_key(channel, int(key["frame"]), value, warnings)


def _channels_for_section(section: Any) -> list[Any]:
    if hasattr(section, "get_channels"):
        return list(section.get_channels())
    if hasattr(section, "get_all_channels"):
        return list(section.get_all_channels())
    channel = getattr(section, "get_channel", None)
    if channel is not None:
        try:
            return [channel()]
        except Exception:
            return []
    return []


def _add_focal_length_track(seq: Any, camera_binding: Any, cam: Any, keys: list[dict[str, Any]], start_frame: int, end_frame: int, warnings: list[Any]) -> None:
    component = cam.get_cine_camera_component() if hasattr(cam, "get_cine_camera_component") else None
    if component is None or not keys:
        return
    focal_values = [float(key.get("focal_length", 35.0)) for key in keys if key.get("focal_length") is not None]
    if not focal_values:
        return
    component.current_focal_length = min(focal_values)
    track_type = getattr(unreal, "MovieSceneFloatTrack", None)
    if track_type is None:
        warnings.append({"camera": getattr(cam, "get_actor_label", lambda: "camera")(), "reason": "movie_scene_float_track_unavailable"})
        return
    try:
        component_binding = seq.add_possessable(component)
        set_parent = getattr(component_binding, "set_parent", None)
        if set_parent is not None:
            set_parent(camera_binding)
        focal_track = component_binding.add_track(track_type)
        set_property = getattr(focal_track, "set_property_name_and_path", None)
        if set_property is not None:
            set_property("CurrentFocalLength", "CurrentFocalLength")
        section = focal_track.add_section()
        section.set_range(start_frame, end_frame)
        channels = _channels_for_section(section)
        if not channels:
            warnings.append({"camera": getattr(cam, "get_actor_label", lambda: "camera")(), "reason": "focal_length_channel_unavailable"})
            return
        channel = channels[0]
        for key in keys:
            if key.get("focal_length") is not None:
                _try_add_channel_key(channel, int(key["frame"]), float(key["focal_length"]), warnings)
    except Exception as exc:  # noqa: BLE001
        warnings.append({"camera": getattr(cam, "get_actor_label", lambda: "camera")(), "reason": "focal_length_track_failed", "error": str(exc)})


def create_camera_shot(inputs: dict[str, Any]) -> dict[str, Any]:
    _require_unreal()
    seq = unreal.EditorAssetLibrary.load_asset(inputs["sequence_path"])
    if seq is None:
        raise RuntimeError(f"Sequence not found: {inputs['sequence_path']}")
    warnings = []
    keys = inputs["keys"]
    first = keys[0]
    cam = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.CineCameraActor, unreal.Vector(*first["location"]))
    cam.set_actor_label(inputs["camera_name"])
    cam.set_actor_rotation(rotator_from_pitch_roll_yaw(unreal, first["rotation"]), False)
    cam.get_cine_camera_component().current_focal_length = first.get("focal_length", 35.0)
    binding = seq.add_possessable(cam)
    transform_track = binding.add_track(unreal.MovieScene3DTransformTrack)
    transform_section = transform_track.add_section()
    transform_section.set_range(inputs["start_frame"], inputs["end_frame"])
    _try_key_transform_section(transform_section, keys, warnings)
    _add_focal_length_track(seq, binding, cam, keys, int(inputs["start_frame"]), int(inputs["end_frame"]), warnings)
    unreal.EditorAssetLibrary.save_asset(inputs["sequence_path"])
    return {"camera_name": inputs["camera_name"], "key_count": len(keys), "warnings": warnings}
