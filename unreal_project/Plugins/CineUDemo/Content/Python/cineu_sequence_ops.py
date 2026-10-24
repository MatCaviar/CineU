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


def _is_generated_cineu_sequence(sequence_path: str) -> bool:
    return sequence_path.startswith("/Game/CineU/Sequences/SEQ_")


def create_level_sequence(inputs: dict[str, Any]) -> dict[str, Any]:
    _require_unreal()
    sequence_path = inputs["sequence_path"]
    package_path, name = sequence_path.rsplit("/", 1)
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    factory = unreal.LevelSequenceFactoryNew()
    existing = unreal.EditorAssetLibrary.load_asset(sequence_path)
    if existing is not None and _is_generated_cineu_sequence(sequence_path):
        try:
            unreal.EditorAssetLibrary.delete_asset(sequence_path)
        except Exception:
            pass
        existing = None
    seq = existing if existing is not None else asset_tools.create_asset(name, package_path, unreal.LevelSequence, factory)
    seq.set_display_rate(unreal.FrameRate(inputs["fps"], 1))
    seq.set_playback_start(inputs["start_frame"])
    seq.set_playback_end(inputs["end_frame"])
    unreal.EditorAssetLibrary.save_asset(sequence_path)
    return {"sequence_path": sequence_path}


def _object_class_name(value: Any) -> str | None:
    get_class = getattr(value, "get_class", None)
    if get_class is None:
        return None
    try:
        klass = get_class()
        get_name = getattr(klass, "get_name", None)
        return str(get_name()) if get_name is not None else str(klass)
    except Exception:
        return None


def _object_display_name(value: Any) -> str | None:
    for name in ("get_display_name", "get_name"):
        getter = getattr(value, name, None)
        if getter is None:
            continue
        try:
            result = getter()
            if result is not None:
                return str(result)
        except Exception:
            continue
    return None


def _object_export_text(value: Any) -> str | None:
    export_text = getattr(value, "export_text", None)
    if export_text is not None:
        try:
            return str(export_text())
        except Exception:
            return None
    return str(value) if value is not None else None


def _section_range(section: Any) -> dict[str, int] | None:
    start = None
    end = None
    for name in ("get_start_frame", "get_start_frame_seconds"):
        getter = getattr(section, name, None)
        if getter is None:
            continue
        try:
            start = int(getter())
            break
        except Exception:
            continue
    for name in ("get_end_frame", "get_end_frame_seconds"):
        getter = getattr(section, name, None)
        if getter is None:
            continue
        try:
            end = int(getter())
            break
        except Exception:
            continue
    if start is None or end is None:
        return None
    return {"start_frame": start, "end_frame": end}


def _track_sections(track: Any) -> list[dict[str, int]]:
    getter = getattr(track, "get_sections", None)
    if getter is None:
        return []
    try:
        sections = list(getter())
    except Exception:
        return []
    ranges: list[dict[str, int]] = []
    for section in sections:
        record = _section_range(section)
        if record is not None:
            ranges.append(record)
    return ranges


def _track_summary(track: Any) -> dict[str, Any]:
    sections = _track_sections(track)
    return {
        "name": _object_display_name(track),
        "type": _object_class_name(track),
        "section_count": len(sections),
        "sections": sections,
    }


def _binding_summary(binding: Any) -> dict[str, Any]:
    binding_id = None
    get_id = getattr(binding, "get_id", None)
    if get_id is not None:
        try:
            binding_id = _object_export_text(get_id())
        except Exception:
            binding_id = None
    tracks: list[dict[str, Any]] = []
    get_tracks = getattr(binding, "get_tracks", None)
    if get_tracks is not None:
        try:
            tracks = [_track_summary(track) for track in list(get_tracks())]
        except Exception:
            tracks = []
    return {"name": _object_display_name(binding), "id": binding_id, "tracks": tracks}


def _sequence_bindings(seq: Any) -> list[dict[str, Any]]:
    get_bindings = getattr(seq, "get_bindings", None)
    if get_bindings is None:
        return []
    try:
        return [_binding_summary(binding) for binding in list(get_bindings())]
    except Exception:
        return []


def _sequence_master_tracks(seq: Any) -> list[dict[str, Any]]:
    for name in ("get_master_tracks", "get_tracks"):
        getter = getattr(seq, name, None)
        if getter is None:
            continue
        try:
            return [_track_summary(track) for track in list(getter())]
        except Exception:
            continue
    return []


def _camera_cut_sections(seq: Any) -> list[dict[str, int]]:
    track_type = getattr(unreal, "MovieSceneCameraCutTrack", None)
    if track_type is None:
        return []
    for finder_name in ("find_master_tracks_by_type", "find_tracks_by_type", "find_tracks_by_exact_type"):
        finder = getattr(seq, finder_name, None)
        if finder is None:
            continue
        try:
            tracks = list(finder(track_type))
        except Exception:
            continue
        if tracks:
            sections: list[dict[str, int]] = []
            for track in tracks:
                sections.extend(_track_sections(track))
            return sections
    return []


def use_existing_level_sequence(inputs: dict[str, Any]) -> dict[str, Any]:
    _require_unreal()
    sequence_path = inputs["sequence_path"]
    seq = unreal.EditorAssetLibrary.load_asset(sequence_path)
    if seq is None:
        raise RuntimeError(f"Sequence not found: {sequence_path}")
    output: dict[str, Any] = {"sequence_path": sequence_path}
    try:
        display_rate = seq.get_display_rate()
        numerator = int(getattr(display_rate, "numerator", 24) or 24)
        denominator = int(getattr(display_rate, "denominator", 1) or 1)
        output["fps"] = numerator
        output["display_rate"] = {"numerator": numerator, "denominator": denominator}
    except Exception:
        pass
    try:
        output["range"] = [int(seq.get_playback_start()), int(seq.get_playback_end())]
    except Exception:
        pass
    output["bindings"] = _sequence_bindings(seq)
    output["master_tracks"] = _sequence_master_tracks(seq)
    output["camera_cut_sections"] = _camera_cut_sections(seq)
    return output


def _find_or_add_camera_cut_track(seq, warnings: list[Any]):
    track_type = unreal.MovieSceneCameraCutTrack
    finders = ["find_master_tracks_by_type", "find_tracks_by_type", "find_tracks_by_exact_type"]
    for finder_name in finders:
        finder = getattr(seq, finder_name, None)
        if finder is None:
            continue
        try:
            tracks = finder(track_type)
            if tracks:
                return tracks[0]
        except Exception as exc:  # noqa: BLE001
            warnings.append({"api": finder_name, "error": str(exc)})
    adders = ["add_master_track", "add_track"]
    for adder_name in adders:
        adder = getattr(seq, adder_name, None)
        if adder is None:
            continue
        try:
            return adder(track_type)
        except Exception as exc:  # noqa: BLE001
            warnings.append({"api": adder_name, "error": str(exc)})
    warnings.append({"reason": "camera_cut_track_api_unavailable"})
    return None


def _clear_camera_cut_sections(track, warnings: list[Any]) -> None:
    get_sections = getattr(track, "get_sections", None)
    remove_section = getattr(track, "remove_section", None)
    if get_sections is None or remove_section is None:
        return
    try:
        sections = list(get_sections())
    except Exception as exc:  # noqa: BLE001
        warnings.append({"api": "get_sections", "error": str(exc)})
        return
    for section in sections:
        try:
            remove_section(section)
        except Exception as exc:  # noqa: BLE001
            warnings.append({"api": "remove_section", "error": str(exc)})


def _find_binding_by_name(seq, name: str | None):
    if not name:
        return None
    get_bindings = getattr(seq, "get_bindings", None)
    if get_bindings is None:
        return None
    try:
        bindings = list(get_bindings())
    except Exception:
        return None
    for binding in bindings:
        try:
            if str(binding.get_name()) == str(name):
                return binding
        except Exception:
            continue
    return None


def _camera_binding_id(binding):
    if binding is None:
        return None
    binding_id_class = getattr(unreal, "MovieSceneObjectBindingID", None)
    get_id = getattr(binding, "get_id", None)
    if binding_id_class is not None and get_id is not None:
        try:
            guid = get_id()
            binding_id = binding_id_class()
            guid_export = getattr(guid, "export_text", None)
            import_text = getattr(binding_id, "import_text", None)
            if guid_export is not None and import_text is not None:
                import_text(f"(Guid={guid_export()},SequenceID=0,ResolveParentIndex=-1)")
                return binding_id
            binding_id.set_editor_property("guid", guid)
            binding_id.set_editor_property("sequence_id", 0)
            binding_id.set_editor_property("resolve_parent_index", -1)
            return binding_id
        except Exception:
            pass
    value = getattr(binding, "binding_id", None)
    if value is not None:
        return value
    get_binding_id = getattr(binding, "get_binding_id", None)
    if get_binding_id is not None:
        try:
            return get_binding_id()
        except Exception:
            pass
    return None


def _set_section_frame_range(section, start_frame: int, end_frame: int, display_rate: int, warnings: list[Any]) -> None:
    set_range = getattr(section, "set_range", None)
    if set_range is not None:
        try:
            set_range(int(start_frame), int(end_frame))
            return
        except Exception as exc:  # noqa: BLE001
            warnings.append({"api": "set_range", "error": str(exc)})
    try:
        section.set_start_frame_seconds(start_frame / display_rate)
        section.set_end_frame_seconds(end_frame / display_rate)
    except Exception as exc:  # noqa: BLE001
        warnings.append({"api": "set_frame_seconds", "error": str(exc)})


def add_camera_cuts(inputs: dict[str, Any]) -> dict[str, Any]:
    _require_unreal()
    seq = unreal.EditorAssetLibrary.load_asset(inputs["sequence_path"])
    if seq is None:
        raise RuntimeError(f"Sequence not found: {inputs['sequence_path']}")
    warnings = []
    cut_track = _find_or_add_camera_cut_track(seq, warnings)
    if cut_track is not None:
        _clear_camera_cut_sections(cut_track, warnings)
    for cut in inputs["cuts"]:
        if cut_track is None:
            continue
        section = cut_track.add_section()
        display_rate = int(getattr(seq.get_display_rate(), "numerator", 24) or 24)
        _set_section_frame_range(section, int(cut["start_frame"]), int(cut["end_frame"]), display_rate, warnings)
        binding_id = _camera_binding_id(_find_binding_by_name(seq, cut.get("camera_name")))
        set_camera_binding_id = getattr(section, "set_camera_binding_id", None)
        if binding_id is not None and set_camera_binding_id is not None:
            try:
                set_camera_binding_id(binding_id)
            except Exception as exc:  # noqa: BLE001
                warnings.append({"camera_name": cut.get("camera_name"), "api": "set_camera_binding_id", "error": str(exc)})
        else:
            warnings.append({"camera_name": cut.get("camera_name"), "reason": "camera_binding_unavailable"})
    unreal.EditorAssetLibrary.save_asset(inputs["sequence_path"])
    return {"camera_cuts": inputs["cuts"], "warnings": warnings}


def _try_add_channel_key(channel: Any, frame: int, value: float, warnings: list[Any], actor_name: str) -> None:
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
                    "actor": actor_name,
                    "frame": frame,
                    "error": f"{type(first_exc).__name__}:{first_exc};{type(second_exc).__name__}:{second_exc}",
                }
            )


def _movie_scene_rotation_values(transform: dict[str, Any]) -> list[float]:
    pitch, yaw, roll = [float(v) for v in transform.get("rotation", [0, 0, 0])]
    return [roll, pitch, yaw]


def add_transform_tracks(inputs: dict[str, Any]) -> dict[str, Any]:
    """Add transform track scaffold for actors in a Level Sequence.

    Channel key insertion differs across UE minor versions. This conservative
    implementation creates possessables/tracks/sections when possible and leaves
    exact channel binding as a project-specific extension point; the generated IR
    and state verifier preserve exact key data for research evaluation.
    """
    _require_unreal()
    seq = unreal.EditorAssetLibrary.load_asset(inputs["sequence_path"])
    if seq is None:
        raise RuntimeError(f"Sequence not found: {inputs['sequence_path']}")
    added = []
    warnings = []
    actors = {a.get_actor_label(): a for a in unreal.EditorLevelLibrary.get_all_level_actors()}
    for track_spec in inputs.get("tracks", []):
        actor_name = track_spec["actor_name"]
        actor = actors.get(actor_name)
        if actor is None:
            raise RuntimeError(f"Actor not found: {actor_name}")
        binding = seq.add_possessable(actor)
        transform_track = binding.add_track(unreal.MovieScene3DTransformTrack)
        section = transform_track.add_section()
        section.set_range(track_spec["start_frame"], track_spec["end_frame"])
        channel_getter = getattr(section, "get_channels", None) or getattr(section, "get_all_channels", None)
        if channel_getter is not None:
            channels = list(channel_getter())
            for key in track_spec.get("keys", []):
                transform = key.get("transform", {})
                values = [
                    *[float(v) for v in transform.get("location", [0, 0, 0])],
                    *_movie_scene_rotation_values(transform),
                    *[float(v) for v in transform.get("scale", [1, 1, 1])],
                ]
                for channel, value in zip(channels, values):
                    _try_add_channel_key(channel, int(key["frame"]), float(value), warnings, actor_name)
        else:
            warnings.append({"actor": actor_name, "reason": "section_channels_unavailable"})
        first_key = track_spec.get("keys", [{}])[0].get("transform")
        if first_key:
            actor.set_actor_location(unreal.Vector(*first_key["location"]), False, False)
            actor.set_actor_rotation(rotator_from_pitch_roll_yaw(unreal, first_key["rotation"]), False)
        added.append(actor_name)
    unreal.EditorAssetLibrary.save_asset(inputs["sequence_path"])
    return {"transform_tracks": added, "warnings": warnings}
