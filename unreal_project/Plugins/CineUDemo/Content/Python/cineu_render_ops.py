from __future__ import annotations

import base64
import json
import math
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any

from cineu_unreal_math import rotator_from_pitch_roll_yaw
from cineu_world_ops import apply_actor_transforms

try:
    import unreal  # type: ignore
except Exception:  # pragma: no cover
    unreal = None


_ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVR4nGP4z8DwHwAFgwJ/luzWnQAAAABJRU5ErkJggg=="
)
_MIN_SCREENSHOT_BYTES = 128
_STORYBOARD_SAMPLES_PER_CUT = 9
_MAX_STORYBOARD_SAMPLES = 24
_ACTIVE_MOVIE_PIPELINE_RENDERS: list[dict[str, Any]] = []


def _windows_long_path(path: Path) -> str:
    resolved = str(Path(path).resolve())
    if os.name != "nt" or resolved.startswith("\\\\?\\"):
        return resolved
    if resolved.startswith("\\\\"):
        return "\\\\?\\UNC\\" + resolved.lstrip("\\")
    return "\\\\?\\" + resolved


def _path_exists(path: Path) -> bool:
    return os.path.exists(_windows_long_path(path))


def _path_size(path: Path) -> int:
    return os.path.getsize(_windows_long_path(path))


def _mkdir(path: Path) -> None:
    os.makedirs(_windows_long_path(path), exist_ok=True)


def _unlink(path: Path) -> None:
    os.unlink(_windows_long_path(path))


def _read_text(path: Path, encoding: str = "utf-8") -> str:
    with open(_windows_long_path(path), "r", encoding=encoding) as handle:
        return handle.read()


def _write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    _mkdir(path.parent)
    with open(_windows_long_path(path), "w", encoding=encoding) as handle:
        handle.write(text)


def _write_bytes(path: Path, data: bytes) -> None:
    _mkdir(path.parent)
    with open(_windows_long_path(path), "wb") as handle:
        handle.write(data)


def _write_fallback_png(path: Path) -> None:
    _write_bytes(path, _ONE_PIXEL_PNG)


def _is_valid_screenshot_artifact(path: Path) -> bool:
    try:
        return _path_exists(path) and _path_size(path) > _MIN_SCREENSHOT_BYTES
    except OSError:
        return False


def _warn_invalid_screenshot(path: Path, warnings: list[Any], reason: str = "screenshot_artifact_too_small") -> None:
    try:
        size = _path_size(path) if _path_exists(path) else 0
    except OSError:
        size = 0
    warning = {"reason": reason, "artifact": str(path), "size": size}
    if warning not in warnings:
        warnings.append(warning)


def _prepare_screenshot_path(path: Path) -> None:
    if not _path_exists(path) or _is_valid_screenshot_artifact(path):
        return
    try:
        _unlink(path)
    except OSError:
        pass


def _load_world_state(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not _path_exists(p):
        return {}
    try:
        return json.loads(_read_text(p, encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _first_camera_cut(state: dict[str, Any], sequence_path: str) -> dict[str, Any] | None:
    seq = state.get("sequences", {}).get(sequence_path, {})
    cuts = sorted(seq.get("camera_cuts", []), key=lambda item: item.get("start_frame", 0))
    return cuts[0] if cuts else None


def _focal_at_frame(camera: dict[str, Any], frame: int) -> float | None:
    focal_keys = sorted([key for key in camera.get("focal_length_keys", []) if key.get("focal_length") is not None], key=lambda item: item.get("frame", 0))
    if not focal_keys:
        return None
    if frame <= int(focal_keys[0].get("frame", 0)):
        return float(focal_keys[0]["focal_length"])
    if frame >= int(focal_keys[-1].get("frame", 0)):
        return float(focal_keys[-1]["focal_length"])
    for left, right in zip(focal_keys, focal_keys[1:]):
        left_frame = int(left.get("frame", 0))
        right_frame = int(right.get("frame", left_frame))
        if left_frame <= frame <= right_frame:
            span = max(1, right_frame - left_frame)
            alpha = (frame - left_frame) / span
            return float(left["focal_length"]) + (float(right["focal_length"]) - float(left["focal_length"])) * alpha
    return float(focal_keys[-1]["focal_length"])


def _lerp_vec3(a: list[Any], b: list[Any], alpha: float) -> list[float]:
    return [float(a[index]) + (float(b[index]) - float(a[index])) * alpha for index in range(3)]


def _transform_at_frame(keys: list[dict[str, Any]], frame: int) -> dict[str, Any] | None:
    ordered = sorted([key for key in keys if "transform" in key], key=lambda item: int(item.get("frame", 0)))
    if not ordered:
        return None
    if frame <= int(ordered[0].get("frame", 0)):
        return dict(ordered[0]["transform"])
    if frame >= int(ordered[-1].get("frame", 0)):
        return dict(ordered[-1]["transform"])
    for left, right in zip(ordered, ordered[1:]):
        left_frame = int(left.get("frame", 0))
        right_frame = int(right.get("frame", left_frame))
        if left_frame <= frame <= right_frame:
            span = max(1, right_frame - left_frame)
            alpha = (frame - left_frame) / span
            left_transform = left["transform"]
            right_transform = right["transform"]
            return {
                "location": _lerp_vec3(left_transform.get("location", [0, 0, 0]), right_transform.get("location", [0, 0, 0]), alpha),
                "rotation": _lerp_vec3(left_transform.get("rotation", [0, 0, 0]), right_transform.get("rotation", [0, 0, 0]), alpha),
                "scale": _lerp_vec3(left_transform.get("scale", [1, 1, 1]), right_transform.get("scale", [1, 1, 1]), alpha),
            }
    return dict(ordered[-1]["transform"])


def _camera_transform_at_frame(camera: dict[str, Any], frame: int) -> dict[str, Any] | None:
    ordered = sorted(camera.get("transform_keys", []), key=lambda item: int(item.get("frame", 0)))
    if not ordered:
        return None
    if frame <= int(ordered[0].get("frame", 0)):
        return {"location": ordered[0].get("location"), "rotation": ordered[0].get("rotation")}
    if frame >= int(ordered[-1].get("frame", 0)):
        return {"location": ordered[-1].get("location"), "rotation": ordered[-1].get("rotation")}
    for left, right in zip(ordered, ordered[1:]):
        left_frame = int(left.get("frame", 0))
        right_frame = int(right.get("frame", left_frame))
        if left_frame <= frame <= right_frame:
            span = max(1, right_frame - left_frame)
            alpha = (frame - left_frame) / span
            return {
                "location": _lerp_vec3(left.get("location", [0, 0, 0]), right.get("location", [0, 0, 0]), alpha),
                "rotation": _lerp_vec3(left.get("rotation", [0, 0, 0]), right.get("rotation", [0, 0, 0]), alpha),
            }
    return {"location": ordered[-1].get("location"), "rotation": ordered[-1].get("rotation")}


def _storyboard_sample_frames(start: int, end: int, sample_count: int = _STORYBOARD_SAMPLES_PER_CUT) -> list[int]:
    last_inclusive_frame = max(start, end - 1)
    if last_inclusive_frame == start:
        return [start]
    available = last_inclusive_frame - start + 1
    if available <= sample_count:
        return list(range(start, last_inclusive_frame + 1))
    span = last_inclusive_frame - start
    return sorted({int(round(start + span * (index / (sample_count - 1)))) for index in range(sample_count)})


def _storyboard_sample_frames_for_step(
    start: int,
    end: int,
    frame_step: int,
    sample_count: int = _STORYBOARD_SAMPLES_PER_CUT,
) -> list[int]:
    if frame_step <= 1:
        return _storyboard_sample_frames(start, end, sample_count)
    return _storyboard_sample_frames_from_candidates(list(range(start, end, frame_step)), sample_count)


def _storyboard_sample_frames_from_candidates(candidates: list[int], sample_count: int = _STORYBOARD_SAMPLES_PER_CUT) -> list[int]:
    unique_candidates = []
    seen = set()
    for frame in candidates:
        if frame in seen:
            continue
        seen.add(frame)
        unique_candidates.append(frame)
    candidates = unique_candidates
    if not candidates:
        return []
    if len(candidates) <= sample_count:
        return candidates
    last_index = len(candidates) - 1
    return sorted({candidates[int(round(last_index * (index / (sample_count - 1))))] for index in range(sample_count)})


def _apply_sequence_frame_state(
    state: dict[str, Any],
    sequence_path: str | None,
    frame: int | None,
    warnings: list[Any],
    evaluate_sequence: bool = True,
) -> None:
    if not state or not sequence_path or frame is None:
        return
    seq = state.get("sequences", {}).get(sequence_path, {})
    fps = int(seq.get("fps", 24) or 24)
    sequence_evaluated = _evaluate_level_sequence_frame(sequence_path, int(frame), warnings) if evaluate_sequence else False
    placements = []
    for actor_name, track in seq.get("transform_tracks", {}).items():
        transform = _transform_at_frame(track.get("keys", []), int(frame))
        if transform is None:
            continue
        actor_spec = state.get("actors", {}).get(actor_name, {})
        relation = actor_spec.get("spatial_relation", {}) if isinstance(actor_spec.get("spatial_relation"), dict) else {}
        placements.append(
            {
                "actor_name": actor_name,
                "transform": transform,
                "bounds_extent": actor_spec.get("bounds_extent", track.get("bounds_extent", [50, 50, 50])),
                "relation": relation.get("relation"),
                "target": relation.get("target"),
            }
        )
    if placements:
        try:
            apply_actor_transforms(placements)
        except Exception as exc:  # noqa: BLE001
            warnings.append({"reason": "storyboard_actor_frame_apply_failed", "frame": frame, "error": str(exc)})
    _restore_sequence_actor_visibility(seq)
    if not sequence_evaluated:
        _apply_sequence_animation_frame_state(seq, int(frame), fps, warnings)


def _animation_tracks(sequence: dict[str, Any]) -> list[dict[str, Any]]:
    tracks = sequence.get("animation_tracks", {})
    if isinstance(tracks, dict):
        return [track for track in tracks.values() if isinstance(track, dict)]
    if isinstance(tracks, list):
        return [track for track in tracks if isinstance(track, dict)]
    return []


def _animation_length_seconds(animation: Any, fallback: float) -> float:
    for name in ["sequence_length", "play_length"]:
        value = _get_unreal_property(animation, name)
        if value:
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
    method = getattr(animation, "get_play_length", None)
    if method is not None:
        try:
            value = float(method())
            if value > 0:
                return value
        except Exception:
            pass
    return fallback


def _skeletal_component_for_actor(actor: Any) -> Any:
    component_class = getattr(unreal, "SkeletalMeshComponent", None)
    if component_class is not None:
        try:
            component = actor.get_component_by_class(component_class)
            if component is not None:
                return component
        except Exception:
            pass
    try:
        for component in actor.get_components_by_class(getattr(unreal, "ActorComponent", object)):
            try:
                class_name = str(component.get_class().get_name())
            except Exception:
                class_name = str(type(component).__name__)
            if "skeletalmesh" in class_name.replace("_", "").lower():
                return component
    except Exception:
        pass
    return None


def _set_skeletal_animation_position(component: Any, animation: Any, time_seconds: float) -> None:
    mode_enum = getattr(unreal, "AnimationMode", None)
    single_node_mode = getattr(mode_enum, "ANIMATION_SINGLE_NODE", None) if mode_enum is not None else None
    set_animation_mode = getattr(component, "set_animation_mode", None)
    if set_animation_mode is not None and single_node_mode is not None:
        set_animation_mode(single_node_mode)
    set_animation = getattr(component, "set_animation", None)
    if set_animation is not None:
        set_animation(animation)
    set_position = getattr(component, "set_position", None)
    if set_position is not None:
        set_position(float(time_seconds), False)
    tick_animation = getattr(component, "tick_animation", None)
    if tick_animation is not None:
        try:
            tick_animation(0.0, False)
        except TypeError:
            tick_animation(0.0)
    refresh = getattr(component, "refresh_bone_transforms", None)
    if refresh is not None:
        refresh()


def _apply_sequence_animation_frame_state(sequence: dict[str, Any], frame: int, fps: int, warnings: list[Any]) -> None:
    if unreal is None:
        return
    for clip in _animation_tracks(sequence):
        actor_name = str(clip.get("actor_name") or "")
        if not actor_name:
            continue
        actor = _find_actor_by_label(actor_name)
        if actor is None:
            warnings.append({"reason": "storyboard_animation_actor_missing", "actor": actor_name, "frame": frame})
            continue
        animation_path = clip.get("animation_path")
        animation = unreal.EditorAssetLibrary.load_asset(str(animation_path)) if animation_path else None
        if animation is None:
            warnings.append({"reason": "storyboard_animation_asset_missing", "actor": actor_name, "animation_path": animation_path, "frame": frame})
            continue
        component = _skeletal_component_for_actor(actor)
        if component is None:
            warnings.append({"reason": "storyboard_skeletal_component_missing", "actor": actor_name, "frame": frame})
            continue
        start_frame = int(clip.get("start_frame", 0) or 0)
        end_frame = int(clip.get("end_frame", frame) or frame)
        duration = max(0.0, (end_frame - start_frame) / max(1, fps))
        position = max(0.0, (frame - start_frame) / max(1, fps))
        length = _animation_length_seconds(animation, duration or position)
        if length > 0:
            position = position % length
        try:
            _set_skeletal_animation_position(component, animation, position)
        except Exception as exc:  # noqa: BLE001
            warnings.append({"reason": "storyboard_animation_pose_failed", "actor": actor_name, "animation_path": animation_path, "frame": frame, "error": str(exc)})


def _restore_sequence_actor_visibility(sequence: dict[str, Any]) -> None:
    if unreal is None:
        return
    actor_names = set()
    tracks = sequence.get("transform_tracks", {})
    if isinstance(tracks, dict):
        actor_names.update(str(name) for name in tracks.keys())
    for clip in _animation_tracks(sequence):
        actor_name = clip.get("actor_name")
        if actor_name:
            actor_names.add(str(actor_name))
    for actor_name in actor_names:
        actor = _find_actor_by_label(actor_name)
        if actor is not None:
            _set_actor_capture_hidden(actor, False)


def _evaluate_level_sequence_frame(sequence_path: str | None, frame: int, warnings: list[Any]) -> bool:
    if unreal is None or not sequence_path:
        return False
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    if library is None:
        return False
    try:
        sequence = unreal.EditorAssetLibrary.load_asset(str(sequence_path))
    except Exception as exc:  # noqa: BLE001
        warnings.append({"reason": "storyboard_sequence_load_failed", "sequence_path": sequence_path, "frame": frame, "error": str(exc)})
        return False
    if sequence is None:
        warnings.append({"reason": "storyboard_sequence_missing", "sequence_path": sequence_path, "frame": frame})
        return False
    try:
        open_level_sequence = getattr(library, "open_level_sequence", None)
        if open_level_sequence is not None:
            open_level_sequence(sequence)
        set_current_time = getattr(library, "set_current_time", None)
        if set_current_time is not None:
            set_current_time(int(frame))
        refresh = getattr(library, "refresh_current_level_sequence", None)
        if refresh is not None:
            refresh()
        try:
            unreal.EditorLevelLibrary.editor_invalidate_viewports()
        except Exception:
            pass
        return True
    except Exception as exc:  # noqa: BLE001
        warnings.append({"reason": "storyboard_sequence_evaluation_failed", "sequence_path": sequence_path, "frame": frame, "error": str(exc)})
        return False


def _native_movie_capture_cvars(inputs: dict[str, Any] | None = None) -> list[str]:
    if _truthy((inputs or {}).get("mrq_low_memory", os.environ.get("CINEU_MRQ_LOW_MEMORY", ""))):
        return _movie_render_pipeline_cvars({"mrq_low_memory": True})
    return [
        "r.TextureStreaming 0",
        "r.Streaming.FullyLoadUsedTextures 1",
        "r.Streaming.UseAllMips 1",
        "r.ViewDistanceScale 2",
    ]


def _prepare_native_movie_capture_view(inputs: dict[str, Any] | None = None) -> list[str]:
    if unreal is None:
        return []
    world = _get_editor_world()
    commands = _native_movie_capture_cvars(inputs)
    applied: list[str] = []
    for command in commands:
        try:
            unreal.SystemLibrary.execute_console_command(world, command)
            applied.append(command)
        except Exception:
            pass
    return applied


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _movie_render_pipeline_cvars(inputs: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    low_memory = _truthy(inputs.get("mrq_low_memory", os.environ.get("CINEU_MRQ_LOW_MEMORY", "")))
    if low_memory:
        commands.extend(
            [
                "r.RayTracing.ForceAllRayTracingEffects 0",
                "r.Lumen.HardwareRayTracing 0",
                "r.DynamicGlobalIlluminationMethod 0",
                "r.ReflectionMethod 0",
                "r.SSGI.Quality 0",
                "r.Shadow.Virtual.Enable 0",
                "r.MotionBlurQuality 0",
                "r.DefaultFeature.MotionBlur 0",
                "r.HairStrands.Enable 0",
                "r.HeterogeneousVolumes 0",
                "r.SkyAtmosphere.FastSkyLUT 1",
                "r.TextureStreaming 1",
                "r.Streaming.FullyLoadUsedTextures 0",
                "r.Streaming.UseAllMips 0",
                "r.Streaming.PoolSize 1024",
                "r.ViewDistanceScale 0.75",
                "foliage.DensityScale 0.25",
                "grass.DensityScale 0.25",
                "r.Nanite.MaxPixelsPerEdge 4",
                "r.MipMapLODBias 1",
            ]
        )
    elif _is_movie_render_pipeline_cinematic_quality(inputs):
        commands.extend(
            [
                "r.TextureStreaming 1",
                "r.Streaming.FullyLoadUsedTextures 0",
                "r.Streaming.UseAllMips 0",
                "r.Streaming.PoolSize 4096",
                "r.MipMapLODBias 0",
                "r.ViewDistanceScale 2",
                "r.DynamicGlobalIlluminationMethod 1",
                "r.ReflectionMethod 1",
                "r.SSGI.Quality 3",
                "r.Shadow.Virtual.Enable 1",
                "r.MotionBlurQuality 4",
                "r.DefaultFeature.MotionBlur 1",
                "r.TSR.Quality 4",
                "r.TemporalAA.Quality 2",
                "r.Nanite.MaxPixelsPerEdge 1",
                "r.HairStrands.Enable 1",
                "foliage.DensityScale 1",
                "grass.DensityScale 1",
            ]
        )
    extra = inputs.get("mrq_cvars")
    if isinstance(extra, str):
        commands.extend(line.strip() for line in extra.splitlines() if line.strip())
    elif isinstance(extra, (list, tuple)):
        commands.extend(str(line).strip() for line in extra if str(line).strip())
    return list(dict.fromkeys(commands))


def _is_movie_render_pipeline_cinematic_quality(inputs: dict[str, Any]) -> bool:
    quality = str(inputs.get("quality", "") or "").strip().lower()
    return quality in {"cinematic", "final", "film", "production", "high", "hq"}


def _movie_render_pipeline_default_sample_counts(inputs: dict[str, Any]) -> tuple[int, int]:
    if _truthy(inputs.get("mrq_low_memory", os.environ.get("CINEU_MRQ_LOW_MEMORY", ""))):
        return (1, 1)
    quality = str(inputs.get("quality", "") or "").strip().lower()
    if quality == "final":
        return (4, 8)
    if _is_movie_render_pipeline_cinematic_quality(inputs):
        return (2, 8)
    return (1, 1)


def _movie_render_pipeline_sample_count(inputs: dict[str, Any], key: str, default_value: int) -> int:
    value = inputs.get(key)
    if value in (None, ""):
        return int(default_value)
    return max(1, int(value))


def _apply_movie_render_pipeline_cvars(inputs: dict[str, Any], warnings: list[Any]) -> list[str]:
    commands = _movie_render_pipeline_cvars(inputs)
    if unreal is None or not commands:
        return []
    system_library = getattr(unreal, "SystemLibrary", None)
    execute = getattr(system_library, "execute_console_command", None) if system_library is not None else None
    if execute is None:
        warnings.append({"reason": "movie_render_pipeline_cvars_unavailable"})
        return []
    world = _get_editor_world()
    applied: list[str] = []
    for command in commands:
        try:
            execute(world, command)
            applied.append(command)
        except Exception as exc:  # noqa: BLE001
            warnings.append({"reason": "movie_render_pipeline_cvar_failed", "command": command, "error": str(exc)})
    return applied


def _movie_render_pipeline_executor_class(inputs: dict[str, Any], warnings: list[Any]) -> tuple[Any, str]:
    requested = str(inputs.get("mrq_executor", os.environ.get("CINEU_MRQ_EXECUTOR", "")) or "").strip().lower()
    if requested in {"", "auto", "pie", "moviepipelinepieexecutor"}:
        candidates = ["MoviePipelinePIEExecutor"]
    elif requested in {"new_process", "new-process", "newprocess", "moviepipelinenewprocessexecutor"}:
        candidates = ["MoviePipelineNewProcessExecutor", "MoviePipelinePIEExecutor"]
    elif requested in {"in_process", "in-process", "inprocess", "moviepipelineinprocessexecutor"}:
        raise RuntimeError(
            "MoviePipelineInProcessExecutor requires a Game/PIE world and cannot run through "
            "MoviePipelineQueueSubsystem in Editor mode; use mrq_executor='pie'."
        )
    else:
        warnings.append({"reason": "movie_render_pipeline_unknown_executor", "requested": requested})
        candidates = ["MoviePipelinePIEExecutor"]

    for name in candidates:
        cls = getattr(unreal, name, None)
        if cls is not None:
            return cls, name
    raise RuntimeError(f"No supported Movie Render Pipeline executor is available; tried {candidates}")


def _quit_editor_after_render_if_requested(inputs: dict[str, Any], warnings: list[Any]) -> None:
    if not _truthy(inputs.get("exit_after_render", os.environ.get("CINEU_EXIT_AFTER_RENDER", ""))):
        return
    system_library = getattr(unreal, "SystemLibrary", None) if unreal is not None else None
    quit_editor = getattr(system_library, "quit_editor", None) if system_library is not None else None
    if callable(quit_editor):
        try:
            quit_editor()
            return
        except Exception as exc:  # noqa: BLE001
            warnings.append({"reason": "movie_render_pipeline_quit_editor_failed", "error": str(exc)})
    execute = getattr(system_library, "execute_console_command", None) if system_library is not None else None
    if callable(execute):
        try:
            execute(_get_editor_world(), "QUIT_EDITOR")
            return
        except Exception as exc:  # noqa: BLE001
            warnings.append({"reason": "movie_render_pipeline_quit_command_failed", "error": str(exc)})
    warnings.append({"reason": "movie_render_pipeline_quit_editor_unavailable"})


def _storyboard_samples(
    state: dict[str, Any],
    sequence_path: str,
    max_samples: int = _MAX_STORYBOARD_SAMPLES,
) -> list[dict[str, Any]]:
    seq = state.get("sequences", {}).get(sequence_path, {})
    cuts = sorted(seq.get("camera_cuts", []), key=lambda item: item.get("start_frame", 0))
    cameras = seq.get("cameras", {})
    samples: list[dict[str, Any]] = []
    for cut in cuts:
        camera_name = cut.get("camera_name")
        camera = cameras.get(camera_name, {})
        keys = sorted(camera.get("transform_keys", []), key=lambda item: item.get("frame", 0))
        if not keys:
            continue
        start = int(cut.get("start_frame", keys[0].get("frame", 0)))
        end = int(cut.get("end_frame", keys[-1].get("frame", start)))
        sample_frames = _storyboard_sample_frames(start, end)
        for frame in sample_frames:
            camera_transform = _camera_transform_at_frame(camera, frame) or {}
            samples.append(
                {
                    "camera_name": camera_name,
                    "shot_id": cut.get("shot_id"),
                    "frame": frame,
                    "location": camera_transform.get("location"),
                    "rotation": camera_transform.get("rotation"),
                    "focal_length": _focal_at_frame(camera, frame),
                }
            )
    return samples[: max(0, int(max_samples))]


def _sequence_record(state: dict[str, Any], sequence_path: str) -> dict[str, Any]:
    seq = state.get("sequences", {}).get(sequence_path, {})
    return seq if isinstance(seq, dict) else {}


def _is_native_level_sequence(state: dict[str, Any], sequence_path: str) -> bool:
    return str(_sequence_record(state, sequence_path).get("source_asset_type", "")).lower() == "level_sequence"


def _should_use_movie_capture_sequence(state: dict[str, Any], sequence_path: str) -> bool:
    sequence = _sequence_record(state, sequence_path)
    if not sequence:
        return False
    if _is_native_level_sequence(state, sequence_path):
        return True
    return bool(sequence.get("camera_cuts"))


def _should_use_movie_render_pipeline(inputs: dict[str, Any], state: dict[str, Any], sequence_path: str) -> bool:
    if not _should_use_movie_capture_sequence(state, sequence_path):
        return False
    requested = str(inputs.get("render_backend") or inputs.get("capture_backend") or "").strip().lower()
    if requested in {"movie_render_pipeline", "movie_render_queue", "mrq"}:
        return True
    env_backend = os.environ.get("CINEU_RENDER_BACKEND", "").strip().lower()
    if env_backend in {"movie_render_pipeline", "movie_render_queue", "mrq"}:
        return True
    quality = str(inputs.get("quality") or "").strip().lower()
    return quality in {"final", "cinematic"} and _is_native_level_sequence(state, sequence_path)


def _native_frame_range(inputs: dict[str, Any], sequence: dict[str, Any]) -> tuple[int, int]:
    raw_range = sequence.get("range") if isinstance(sequence.get("range"), list) else [0, 1]
    start_key = "native_capture_start_frame" if inputs.get("native_capture_start_frame") is not None else "start_frame"
    end_key = "native_capture_end_frame" if inputs.get("native_capture_end_frame") is not None else "end_frame"
    start = int(inputs.get(start_key, raw_range[0] if raw_range else 0) or 0)
    end = int(inputs.get(end_key, raw_range[1] if len(raw_range) > 1 else start + 1) or start + 1)
    if end <= start:
        end = start + 1
    return start, end


def _native_capture_frame_rate(inputs: dict[str, Any], sequence: dict[str, Any], output_fps: int) -> tuple[int, int]:
    if inputs.get("native_capture_start_frame") is None and inputs.get("native_capture_end_frame") is None:
        return max(1, int(output_fps)), 1
    display_rate = (sequence.get("ue_sequence_metadata") or {}).get("display_rate") or {}
    try:
        numerator = int(display_rate.get("numerator", 0) or 0)
        denominator = int(display_rate.get("denominator", 1) or 1)
    except (TypeError, ValueError):
        numerator, denominator = 0, 1
    if numerator > 0 and denominator > 0:
        return numerator, denominator
    try:
        asset_fps = int(sequence.get("asset_fps", 0) or 0)
    except (TypeError, ValueError):
        asset_fps = 0
    return (asset_fps, 1) if asset_fps > 0 else (max(1, int(output_fps)), 1)


def _movie_pipeline_output_frame_step(inputs: dict[str, Any]) -> int:
    try:
        frame_step = int(inputs.get("mrq_output_frame_step", 1) or 1)
    except (TypeError, ValueError):
        return 1
    return max(1, frame_step)


def _movie_pipeline_requested_output_frame_rate(inputs: dict[str, Any]) -> tuple[int, int] | None:
    raw_rate = inputs.get("mrq_output_frame_rate")
    if raw_rate is None:
        return None
    try:
        if isinstance(raw_rate, dict):
            numerator = int(raw_rate.get("numerator", 0) or 0)
            denominator = int(raw_rate.get("denominator", 1) or 1)
        elif isinstance(raw_rate, (list, tuple)):
            numerator = int(raw_rate[0])
            denominator = int(raw_rate[1] if len(raw_rate) > 1 else 1)
        else:
            numerator = int(raw_rate)
            denominator = int(inputs.get("mrq_output_frame_rate_denominator", 1) or 1)
    except (IndexError, TypeError, ValueError):
        return None
    if numerator <= 0 or denominator <= 0:
        return None
    return numerator, denominator


def _frame_rate_payload(frame_rate: tuple[int, int]) -> dict[str, int]:
    return {"numerator": int(frame_rate[0]), "denominator": int(frame_rate[1])}


def _same_frame_rate(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return int(left[0]) * int(right[1]) == int(right[0]) * int(left[1])


def _project_frame_between_rates(frame: int, source_rate: tuple[int, int], output_rate: tuple[int, int]) -> int:
    source_num, source_den = source_rate
    output_num, output_den = output_rate
    return int(round(int(frame) * output_num * source_den / (output_den * source_num)))


def _source_frame_from_output_frame(output_frame: int, source_rate: tuple[int, int], output_rate: tuple[int, int]) -> int:
    source_num, source_den = source_rate
    output_num, output_den = output_rate
    return int(round(int(output_frame) * source_num * output_den / (source_den * output_num)))


def _movie_pipeline_output_rate_plan(
    start_frame: int,
    end_frame: int,
    source_rate: tuple[int, int],
    output_rate: tuple[int, int],
) -> dict[str, Any] | None:
    if _same_frame_rate(source_rate, output_rate):
        return None
    source_count = max(1, int(end_frame) - int(start_frame))
    output_start = _project_frame_between_rates(start_frame, source_rate, output_rate)
    output_count = max(1, int(round(source_count * output_rate[0] * source_rate[1] / (output_rate[1] * source_rate[0]))))
    output_end = output_start + output_count
    frame_map = []
    last_source_frame = max(start_frame, end_frame - 1)
    for output_frame in range(output_start, output_end):
        source_frame = _source_frame_from_output_frame(output_frame, source_rate, output_rate)
        source_frame = min(last_source_frame, max(start_frame, source_frame))
        frame_map.append(
            {
                "output_frame": output_frame,
                "source_frame": source_frame,
                "file_name": f"movie_frame_{output_frame:04d}.png",
            }
        )
    return {
        "source_frame_rate": _frame_rate_payload(source_rate),
        "output_frame_rate": _frame_rate_payload(output_rate),
        "output_frame_range": [output_start, output_end],
        "output_frame_map": frame_map,
    }


def _movie_pipeline_sampled_source_frames(inputs: dict[str, Any], start_frame: int, end_frame: int) -> list[int] | None:
    raw_frames = inputs.get("mrq_sampled_source_frames")
    if raw_frames is None:
        return None
    if not isinstance(raw_frames, list):
        return None
    frames = []
    seen = set()
    for raw_frame in raw_frames:
        try:
            frame = int(raw_frame)
        except (TypeError, ValueError):
            continue
        if frame < start_frame or frame >= end_frame or frame in seen:
            continue
        seen.add(frame)
        frames.append(frame)
    return frames or None


def _native_preview_samples(
    sequence: dict[str, Any],
    start_frame: int,
    end_frame: int,
    frame_step: int = 1,
    sampled_source_frames: list[int] | None = None,
    max_samples: int = _MAX_STORYBOARD_SAMPLES,
) -> list[dict[str, Any]]:
    cuts = sorted(sequence.get("camera_cuts", []), key=lambda item: item.get("start_frame", start_frame))
    sample_count = max_samples if max_samples > _MAX_STORYBOARD_SAMPLES else _STORYBOARD_SAMPLES_PER_CUT
    samples = []
    sample_frames = (
        _storyboard_sample_frames_from_candidates(sampled_source_frames, sample_count)
        if sampled_source_frames is not None
        else _storyboard_sample_frames_for_step(start_frame, end_frame, frame_step, sample_count)
    )
    for frame in sample_frames:
        cut = next(
            (
                item
                for item in cuts
                if int(item.get("start_frame", start_frame)) <= int(frame) < int(item.get("end_frame", end_frame))
            ),
            cuts[0] if cuts else {},
        )
        camera_name = cut.get("camera_name") or "NativeSequenceCamera"
        shot_id = cut.get("shot_id") or "existing_sequence"
        samples.append({"camera_name": camera_name, "shot_id": shot_id, "frame": frame})
    return samples[: max(0, int(max_samples))]


def _scene_capture_sequence_sample(sequence: dict[str, Any], frame: int, start_frame: int, end_frame: int) -> dict[str, Any]:
    cuts = sorted(sequence.get("camera_cuts", []), key=lambda item: item.get("start_frame", start_frame))
    cut = next(
        (
            item
            for item in cuts
            if int(item.get("start_frame", start_frame)) <= int(frame) < int(item.get("end_frame", end_frame))
        ),
        cuts[0] if cuts else {},
    )
    camera_name = cut.get("camera_name")
    sample: dict[str, Any] = {
        "camera_name": camera_name,
        "shot_id": cut.get("shot_id"),
        "frame": int(frame),
    }
    camera = sequence.get("cameras", {}).get(camera_name, {}) if camera_name else {}
    if isinstance(camera, dict):
        camera_transform = _camera_transform_at_frame(camera, int(frame)) or {}
        sample["location"] = camera_transform.get("location")
        sample["rotation"] = camera_transform.get("rotation")
        sample["focal_length"] = _focal_at_frame(camera, int(frame))
        if camera.get("exposure_bias") is not None:
            sample["exposure_bias"] = camera.get("exposure_bias")
        if camera.get("exposure_brightness") is not None:
            sample["exposure_brightness"] = camera.get("exposure_brightness")
    return sample


def _native_movie_frame_path(movie_dir: Path, frame: int) -> Path:
    return movie_dir / f"movie_frame_{int(frame):04d}.png"


def _asset_object_path(asset_path: str | None) -> str | None:
    if not asset_path:
        return None
    normalized = str(asset_path).replace("\\", "/")
    leaf = normalized.rsplit("/", 1)[-1]
    if "." in leaf:
        return normalized
    return f"{normalized}.{leaf}"


def _movie_pipeline_level_path(state: dict[str, Any], sequence: dict[str, Any]) -> str | None:
    for value in (sequence.get("level_path"), sequence.get("map_path")):
        if value:
            return str(value)
    environment_asset = state.get("environment_asset")
    if isinstance(environment_asset, dict) and str(environment_asset.get("type", "")).lower() == "level":
        ue_path = environment_asset.get("ue_path")
        if ue_path:
            return str(ue_path)
    return None


def _load_movie_pipeline_level(level_path: str | None, warnings: list[Any]) -> bool:
    if unreal is None or not level_path:
        return False
    target_package = str(level_path).split(".", 1)[0].rstrip("/").lower()
    try:
        get_world = getattr(unreal.EditorLevelLibrary, "get_editor_world", None)
        world = get_world() if callable(get_world) else None
        if world is not None:
            current_paths: list[str] = []
            get_path_name = getattr(world, "get_path_name", None)
            if callable(get_path_name):
                current_paths.append(str(get_path_name()))
            get_outermost = getattr(world, "get_outermost", None)
            if callable(get_outermost):
                outermost = get_outermost()
                get_name = getattr(outermost, "get_name", None)
                if callable(get_name):
                    current_paths.append(str(get_name()))
            if any(path.lower().split(".", 1)[0].rstrip("/") == target_package for path in current_paths):
                return True
    except Exception:
        pass
    try:
        load_level = getattr(unreal.EditorLevelLibrary, "load_level", None)
        if load_level is not None:
            return bool(load_level(level_path))
    except Exception as exc:  # noqa: BLE001
        warnings.append({"reason": "movie_render_pipeline_level_load_failed", "level_path": level_path, "error": str(exc)})
    try:
        subsystem_type = getattr(unreal, "LevelEditorSubsystem", None)
        get_subsystem = getattr(unreal, "get_editor_subsystem", None)
        if subsystem_type is None or get_subsystem is None:
            return False
        subsystem = get_subsystem(subsystem_type)
        load_level = getattr(subsystem, "load_level", None)
        if load_level is None:
            return False
        return bool(load_level(level_path))
    except Exception as exc:  # noqa: BLE001
        warnings.append({"reason": "movie_render_pipeline_level_load_failed", "level_path": level_path, "error": str(exc)})
        return False


def _set_movie_pipeline_property(obj: Any, name: str, value: Any, warnings: list[Any]) -> bool:
    setter = getattr(obj, "set_editor_property", None)
    if setter is not None:
        try:
            setter(name, value)
            return True
        except Exception:
            pass
    try:
        setattr(obj, name, value)
        return True
    except Exception as exc:  # noqa: BLE001
        warnings.append({"reason": "movie_render_pipeline_property_failed", "property": name, "error": str(exc)})
        return False


def _write_native_preview_manifests(
    *,
    inputs: dict[str, Any],
    preview_manifest: Path,
    storyboard_manifest: Path,
    preview_camera: str | None,
    preview_shot_id: str | None,
    preview_frame_number: int,
    storyboard_frames: list[dict[str, Any]],
    artifacts: dict[str, str],
    warnings: list[Any],
    movie_dir: Path,
    capture_started: bool,
    capture_success: bool | None,
    native_capture_cvars: list[str] | None = None,
) -> None:
    native_range = [
        int(inputs.get("native_capture_start_frame", storyboard_frames[0]["frame"] if storyboard_frames else inputs.get("start_frame", 0))),
        int(inputs.get("native_capture_end_frame", (storyboard_frames[-1]["frame"] + 1) if storyboard_frames else inputs.get("end_frame", 1))),
    ]
    _write_text(
        storyboard_manifest,
        json.dumps(
            {
                "sequence_path": inputs["sequence_path"],
                "resolution": inputs.get("resolution", [1280, 720]),
                "render_backend": "sequencer_movie_capture",
                "native_capture_frame_range": native_range,
                "movie_frame_dir": str(movie_dir),
                "frames": storyboard_frames,
                "warnings": warnings,
                "capture_started": capture_started,
                "capture_success": capture_success,
                "native_capture_cvars": native_capture_cvars or [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_text(
        preview_manifest,
        json.dumps(
            {
                "sequence_path": inputs["sequence_path"],
                "resolution": inputs.get("resolution", [1280, 720]),
                "format": inputs.get("format", "mp4"),
                "quality": inputs.get("quality", "preview"),
                "render_backend": "sequencer_movie_capture",
                "native_capture_frame_range": native_range,
                "preview_camera": preview_camera,
                "preview_shot_id": preview_shot_id,
                "preview_frame": preview_frame_number,
                "storyboard_frames": storyboard_frames,
                "warnings": warnings,
                "artifacts": artifacts,
                "movie_frame_dir": str(movie_dir),
                "capture_started": capture_started,
                "capture_success": capture_success,
                "native_capture_cvars": native_capture_cvars or [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_movie_pipeline_preview_manifests(
    *,
    inputs: dict[str, Any],
    preview_manifest: Path,
    storyboard_manifest: Path,
    preview_camera: str | None,
    preview_shot_id: str | None,
    preview_frame_number: int,
    storyboard_frames: list[dict[str, Any]],
    artifacts: dict[str, str],
    warnings: list[Any],
    movie_dir: Path,
    capture_started: bool,
    capture_success: bool | None,
    capture_pending: bool,
    frame_range: tuple[int, int],
    frame_step: int,
    sampled_source_frames: list[int] | None,
    output_rate_plan: dict[str, Any] | None,
    level_path: str | None,
    movie_render_pipeline_cvars: list[str] | None = None,
    movie_render_pipeline_executor: str | None = None,
) -> None:
    mrq_range = [int(frame_range[0]), int(frame_range[1])]
    mrq_step = max(1, int(frame_step))
    sampled_frames = [int(frame) for frame in sampled_source_frames] if sampled_source_frames is not None else None
    storyboard_payload = {
        "sequence_path": inputs["sequence_path"],
        "level_path": level_path,
        "resolution": inputs.get("resolution", [1280, 720]),
        "render_backend": "movie_render_pipeline",
        "movie_render_pipeline_frame_range": mrq_range,
        "movie_render_pipeline_frame_step": mrq_step,
        "native_capture_frame_range": mrq_range,
        "movie_frame_dir": str(movie_dir),
        "frames": storyboard_frames,
        "warnings": warnings,
        "capture_started": capture_started,
        "capture_success": capture_success,
        "capture_pending": capture_pending,
        "movie_render_pipeline_cvars": movie_render_pipeline_cvars or [],
        "movie_render_pipeline_executor": movie_render_pipeline_executor,
    }
    preview_payload = {
        "sequence_path": inputs["sequence_path"],
        "level_path": level_path,
        "resolution": inputs.get("resolution", [1280, 720]),
        "format": inputs.get("format", "mp4"),
        "quality": inputs.get("quality", "preview"),
        "render_backend": "movie_render_pipeline",
        "movie_render_pipeline_frame_range": mrq_range,
        "movie_render_pipeline_frame_step": mrq_step,
        "native_capture_frame_range": mrq_range,
        "preview_camera": preview_camera,
        "preview_shot_id": preview_shot_id,
        "preview_frame": preview_frame_number,
        "storyboard_frames": storyboard_frames,
        "warnings": warnings,
        "artifacts": artifacts,
        "movie_frame_dir": str(movie_dir),
        "capture_started": capture_started,
        "capture_success": capture_success,
        "capture_pending": capture_pending,
        "movie_render_pipeline_cvars": movie_render_pipeline_cvars or [],
        "movie_render_pipeline_executor": movie_render_pipeline_executor,
    }
    if sampled_frames is not None:
        storyboard_payload["movie_render_pipeline_sampled_source_frames"] = sampled_frames
        preview_payload["movie_render_pipeline_sampled_source_frames"] = sampled_frames
    if output_rate_plan is not None:
        storyboard_payload["movie_render_pipeline_source_frame_rate"] = output_rate_plan["source_frame_rate"]
        storyboard_payload["movie_render_pipeline_output_frame_rate"] = output_rate_plan["output_frame_rate"]
        storyboard_payload["movie_render_pipeline_output_frame_range"] = output_rate_plan["output_frame_range"]
        storyboard_payload["movie_render_pipeline_output_frame_map"] = output_rate_plan["output_frame_map"]
        preview_payload["movie_render_pipeline_source_frame_rate"] = output_rate_plan["source_frame_rate"]
        preview_payload["movie_render_pipeline_output_frame_rate"] = output_rate_plan["output_frame_rate"]
        preview_payload["movie_render_pipeline_output_frame_range"] = output_rate_plan["output_frame_range"]
        preview_payload["movie_render_pipeline_output_frame_map"] = output_rate_plan["output_frame_map"]
    _write_text(
        storyboard_manifest,
        json.dumps(storyboard_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_text(
        preview_manifest,
        json.dumps(preview_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _copy_native_movie_outputs(
    *,
    movie_dir: Path,
    preview_frame: Path,
    storyboard_frames: list[dict[str, Any]],
    warnings: list[Any],
) -> None:
    for frame in storyboard_frames:
        source = _native_movie_frame_path(movie_dir, int(frame["frame"]))
        destination = Path(str(frame["artifact"]))
        if _is_valid_screenshot_artifact(source):
            _mkdir(destination.parent)
            shutil.copyfile(_windows_long_path(source), _windows_long_path(destination))
        else:
            _warn_invalid_screenshot(source, warnings, "movie_capture_frame_missing")
    if storyboard_frames:
        first_storyboard = Path(str(storyboard_frames[0]["artifact"]))
        if _is_valid_screenshot_artifact(first_storyboard):
            shutil.copyfile(_windows_long_path(first_storyboard), _windows_long_path(preview_frame))
        else:
            _warn_invalid_screenshot(first_storyboard, warnings, "movie_capture_preview_source_missing")


def _native_movie_outputs_are_complete(movie_dir: Path, storyboard_frames: list[dict[str, Any]]) -> bool:
    if not storyboard_frames:
        return False
    return all(_is_valid_screenshot_artifact(_native_movie_frame_path(movie_dir, int(frame["frame"]))) for frame in storyboard_frames)


def _movie_pipeline_expected_output_frames(
    start_frame: int,
    end_frame: int,
    frame_step: int,
    sampled_source_frames: list[int] | None,
    output_rate_plan: dict[str, Any] | None,
) -> list[int]:
    if sampled_source_frames is not None:
        return [int(frame) for frame in sampled_source_frames]
    frame_map = (output_rate_plan or {}).get("output_frame_map", [])
    if frame_map:
        return [int(item["output_frame"]) for item in frame_map if isinstance(item, dict)]
    return list(range(int(start_frame), int(end_frame), max(1, int(frame_step))))


def _movie_pipeline_outputs_are_complete(movie_dir: Path, expected_frames: list[int]) -> bool:
    if not expected_frames:
        return False
    return all(_is_valid_screenshot_artifact(_native_movie_frame_path(movie_dir, frame)) for frame in expected_frames)


def _render_movie_pipeline_level_sequence_preview(
    inputs: dict[str, Any],
    state: dict[str, Any],
    out: Path,
    preview_frame: Path,
    preview_manifest: Path,
    storyboard_manifest: Path,
    warnings: list[Any],
) -> dict[str, Any]:
    sequence_path = inputs["sequence_path"]
    sequence = _sequence_record(state, sequence_path)
    start_frame, end_frame = _native_frame_range(inputs, sequence)
    frame_step = _movie_pipeline_output_frame_step(inputs)
    sampled_source_frames = _movie_pipeline_sampled_source_frames(inputs, start_frame, end_frame)
    fps = int(inputs.get("fps", sequence.get("fps", 24)) or 24)
    width, height = inputs.get("resolution", [1280, 720])
    movie_dir = out / "movie_frames"
    _mkdir(movie_dir)
    for old in movie_dir.glob("movie_frame_*.png"):
        try:
            _unlink(old)
        except OSError:
            pass

    source_rate_num, source_rate_den = _native_capture_frame_rate(inputs, sequence, fps)
    source_frame_rate = (source_rate_num, source_rate_den)
    requested_output_frame_rate = _movie_pipeline_requested_output_frame_rate(inputs)
    output_frame_rate = source_frame_rate
    if sampled_source_frames is None and frame_step <= 1 and requested_output_frame_rate is not None:
        output_frame_rate = requested_output_frame_rate
    output_rate_plan = _movie_pipeline_output_rate_plan(start_frame, end_frame, source_frame_rate, output_frame_rate)
    output_frame_source_map = {
        int(item["output_frame"]): int(item["source_frame"])
        for item in (output_rate_plan or {}).get("output_frame_map", [])
        if isinstance(item, dict)
    }
    expected_output_frames = _movie_pipeline_expected_output_frames(
        start_frame,
        end_frame,
        frame_step,
        sampled_source_frames,
        output_rate_plan,
    )
    preview_sample_frames = list(output_frame_source_map) if output_frame_source_map else sampled_source_frames
    samples = _native_preview_samples(
        sequence,
        start_frame,
        end_frame,
        frame_step,
        preview_sample_frames,
        max_samples=int(inputs.get("max_storyboard_samples", _MAX_STORYBOARD_SAMPLES)),
    )
    storyboard_frames: list[dict[str, Any]] = []
    artifacts = {
        "preview_frame.png": str(preview_frame),
        "preview_manifest.json": str(preview_manifest),
        "storyboard_manifest.json": str(storyboard_manifest),
        "movie_frame_dir": str(movie_dir),
    }
    for index, sample in enumerate(samples):
        name = f"storyboard_{index:03d}.png"
        record = {**sample, "artifact": str(out / name), "artifact_name": name}
        if int(sample["frame"]) in output_frame_source_map:
            record["source_frame"] = output_frame_source_map[int(sample["frame"])]
        storyboard_frames.append(record)
        artifacts[name] = str(out / name)

    preview_camera = samples[0].get("camera_name") if samples else None
    preview_shot_id = samples[0].get("shot_id") if samples else None
    preview_frame_number = int(samples[0].get("frame", start_frame)) if samples else start_frame
    level_path = _movie_pipeline_level_path(state, sequence)
    movie_render_pipeline_cvars: list[str] = []
    movie_render_pipeline_executor = ""
    capture_state = {"started": False, "success": None, "finished": False, "tick_handle": None, "last_output_check": 0.0}
    active_render: dict[str, Any] | None = None

    def build_result(capture_pending: bool, result_warnings: list[Any] | None = None) -> dict[str, Any]:
        return {
            "sequence_path": sequence_path,
            "level_path": level_path,
            "quality": inputs.get("quality"),
            "render_backend": "movie_render_pipeline",
            "preview_camera": preview_camera,
            "preview_shot_id": preview_shot_id,
            "preview_frame": preview_frame_number,
            "storyboard_frames": storyboard_frames,
            "artifacts": artifacts,
            "warnings": warnings if result_warnings is None else result_warnings,
            "capture_started": bool(capture_state["started"]),
            "capture_success": capture_state["success"],
            "capture_pending": bool(capture_pending),
            "movie_render_pipeline_sampled_source_frames": sampled_source_frames or [],
            "movie_render_pipeline_cvars": movie_render_pipeline_cvars,
            "movie_render_pipeline_executor": movie_render_pipeline_executor,
        }

    def write_completion_summary(render_result: dict[str, Any]) -> None:
        summary_base = inputs.get("completion_summary_base")
        if not isinstance(summary_base, dict):
            return
        summary = {**summary_base, "render_result": render_result}
        for key in ("completion_summary_path", "latest_summary_path"):
            path_value = inputs.get(key)
            if not path_value:
                continue
            try:
                path = Path(str(path_value))
                _write_text(path, json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception as exc:  # noqa: BLE001
                warnings.append({"reason": "movie_render_pipeline_completion_summary_failed", "path": str(path_value), "error": str(exc)})

    def finish(reason: str) -> None:
        if capture_state["finished"]:
            return
        capture_state["finished"] = True
        if (
            not capture_state["success"]
            and reason in {"deadline", "frames_complete"}
            and _movie_pipeline_outputs_are_complete(movie_dir, expected_output_frames)
        ):
            capture_state["success"] = True
            warnings.append({"reason": "movie_render_pipeline_completed_without_delegate"})
        if capture_state["success"]:
            _copy_native_movie_outputs(
                movie_dir=movie_dir,
                preview_frame=preview_frame,
                storyboard_frames=storyboard_frames,
                warnings=warnings,
            )
        else:
            warnings.append({"reason": reason, "capture_success": capture_state["success"]})
        _write_movie_pipeline_preview_manifests(
            inputs=inputs,
            preview_manifest=preview_manifest,
            storyboard_manifest=storyboard_manifest,
            preview_camera=preview_camera,
            preview_shot_id=preview_shot_id,
            preview_frame_number=preview_frame_number,
            storyboard_frames=storyboard_frames,
            artifacts=artifacts,
            warnings=warnings,
            movie_dir=movie_dir,
            capture_started=bool(capture_state["started"]),
            capture_success=capture_state["success"],
            frame_range=(start_frame, end_frame),
            frame_step=frame_step,
            sampled_source_frames=sampled_source_frames,
            output_rate_plan=output_rate_plan,
            level_path=level_path,
            capture_pending=False,
            movie_render_pipeline_cvars=movie_render_pipeline_cvars,
            movie_render_pipeline_executor=movie_render_pipeline_executor,
        )
        write_completion_summary(build_result(False))
        handle = capture_state.get("tick_handle")
        if handle is not None:
            try:
                unreal.unregister_slate_post_tick_callback(handle)
            except Exception:
                pass
        if active_render is not None:
            try:
                _ACTIVE_MOVIE_PIPELINE_RENDERS.remove(active_render)
            except ValueError:
                pass
        try:
            unreal.EditorPythonScripting.set_keep_python_script_alive(False)
        except Exception:
            pass
        _quit_editor_after_render_if_requested(inputs, warnings)

    def on_finished(_executor: Any, render_success: Any) -> None:
        capture_state["success"] = bool(render_success)
        finish("callback_done")

    def on_tick(_delta_seconds: Any) -> None:
        now = time.monotonic()
        if now - float(capture_state.get("last_output_check") or 0.0) >= 1.0:
            capture_state["last_output_check"] = now
            if capture_state["success"] is None and _movie_pipeline_outputs_are_complete(movie_dir, expected_output_frames):
                finish("frames_complete")
                return
        if now >= deadline:
            finish("deadline")

    _load_movie_pipeline_level(level_path, warnings)
    movie_render_pipeline_cvars = _apply_movie_render_pipeline_cvars(inputs, warnings)
    subsystem = unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem)
    queue = subsystem.get_queue()
    if hasattr(queue, "delete_all_jobs"):
        queue.delete_all_jobs()
    else:
        for job_to_delete in list(queue.get_jobs()):
            queue.delete_job(job_to_delete)
    capture_rate_num, capture_rate_den = output_frame_rate

    def configure_job(job_start_frame: int, job_end_frame: int, job_name: str, use_frame_step: bool) -> None:
        job = queue.allocate_new_job(unreal.MoviePipelineExecutorJob)
        _set_movie_pipeline_property(job, "sequence", unreal.SoftObjectPath(_asset_object_path(sequence_path) or sequence_path), warnings)
        level_object_path = _asset_object_path(level_path)
        if level_object_path is not None:
            _set_movie_pipeline_property(job, "map", unreal.SoftObjectPath(level_object_path), warnings)
        if hasattr(job, "job_name"):
            job.job_name = job_name
        if hasattr(job, "author"):
            job.author = "CineU"

        config = job.get_configuration()
        output = config.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
        output.output_directory.set_editor_property("path", str(movie_dir))
        _set_movie_pipeline_property(output, "output_resolution", unreal.IntPoint(int(width), int(height)), warnings)
        _set_movie_pipeline_property(output, "file_name_format", "movie_frame_{frame_number}", warnings)
        _set_movie_pipeline_property(output, "zero_pad_frame_numbers", 4, warnings)
        _set_movie_pipeline_property(output, "override_existing_output", True, warnings)
        _set_movie_pipeline_property(output, "flush_disk_writes_per_shot", True, warnings)
        _set_movie_pipeline_property(output, "use_custom_playback_range", True, warnings)
        _set_movie_pipeline_property(output, "custom_start_frame", int(job_start_frame), warnings)
        _set_movie_pipeline_property(output, "custom_end_frame", int(job_end_frame), warnings)
        if use_frame_step and frame_step > 1:
            _set_movie_pipeline_property(output, "output_frame_step", frame_step, warnings)
        _set_movie_pipeline_property(output, "use_custom_frame_rate", True, warnings)
        _set_movie_pipeline_property(output, "output_frame_rate", unreal.FrameRate(capture_rate_num, capture_rate_den), warnings)

        render_pass = config.find_or_add_setting_by_class(unreal.MoviePipelineDeferredPassBase)
        _set_movie_pipeline_property(render_pass, "render_main_pass", True, warnings)
        _set_movie_pipeline_property(render_pass, "disable_multisample_effects", False, warnings)
        config.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_PNG)
        if hasattr(unreal, "MoviePipelineAntiAliasingSetting"):
            aa = config.find_or_add_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
            default_spatial_samples, default_temporal_samples = _movie_render_pipeline_default_sample_counts(inputs)
            _set_movie_pipeline_property(
                aa,
                "spatial_sample_count",
                _movie_render_pipeline_sample_count(inputs, "mrq_spatial_samples", default_spatial_samples),
                warnings,
            )
            _set_movie_pipeline_property(
                aa,
                "temporal_sample_count",
                _movie_render_pipeline_sample_count(inputs, "mrq_temporal_samples", default_temporal_samples),
                warnings,
            )
            warm_up_value = inputs.get("warm_up_frame_count", 8)
            warm_up_count = 8 if warm_up_value in (None, "") else max(0, int(warm_up_value))
            _set_movie_pipeline_property(aa, "engine_warm_up_count", warm_up_count, warnings)
            _set_movie_pipeline_property(aa, "render_warm_up_count", warm_up_count, warnings)
        if hasattr(unreal, "MoviePipelineGameOverrideSetting"):
            preview_quality = str(inputs.get("quality", "")).strip().lower() in {"preview", "draft", "fast", "smoke"}
            low_memory_render = _truthy(inputs.get("mrq_low_memory", os.environ.get("CINEU_MRQ_LOW_MEMORY", "")))
            enable_cinematic_game_override = (not preview_quality) and (not low_memory_render)
            game = config.find_or_add_setting_by_class(unreal.MoviePipelineGameOverrideSetting)
            _set_movie_pipeline_property(game, "cinematic_quality_settings", enable_cinematic_game_override, warnings)
            _set_movie_pipeline_property(game, "use_lod_zero", enable_cinematic_game_override, warnings)
            _set_movie_pipeline_property(game, "flush_streaming_managers", enable_cinematic_game_override, warnings)
            _set_movie_pipeline_property(game, "flush_grass_streaming", enable_cinematic_game_override, warnings)
        config.initialize_transient_settings()

    if sampled_source_frames is not None:
        for frame in sampled_source_frames:
            configure_job(frame, frame + 1, f"CineU_Movie_Render_Pipeline_{frame:04d}", False)
    else:
        configure_job(start_frame, end_frame, "CineU_Movie_Render_Pipeline", True)

    executor_class, movie_render_pipeline_executor = _movie_render_pipeline_executor_class(inputs, warnings)
    try:
        executor = executor_class(subsystem)
    except TypeError:
        executor = executor_class()
    executor.on_executor_finished_delegate.add_callable_unique(on_finished)
    active_render = {"executor": executor, "subsystem": subsystem, "queue": queue, "capture_state": capture_state}
    _ACTIVE_MOVIE_PIPELINE_RENDERS.append(active_render)
    deadline = time.monotonic() + float(inputs.get("capture_timeout_sec", os.environ.get("CINEU_MOVIE_RENDER_PIPELINE_DEADLINE", "600")) or 600)
    try:
        unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    except Exception:
        pass
    register_tick = getattr(unreal, "register_slate_post_tick_callback", None)
    if register_tick is not None:
        capture_state["tick_handle"] = register_tick(on_tick)
    capture_state["started"] = True
    subsystem.render_queue_with_executor_instance(executor)
    if not capture_state["finished"] and capture_state["success"] is not None:
        finish("callback_done")

    if capture_state["finished"]:
        return build_result(False)

    pending_warnings = [*warnings, {"reason": "movie_render_pipeline_async_pending"}]
    _write_movie_pipeline_preview_manifests(
        inputs=inputs,
        preview_manifest=preview_manifest,
        storyboard_manifest=storyboard_manifest,
        preview_camera=preview_camera,
        preview_shot_id=preview_shot_id,
        preview_frame_number=preview_frame_number,
        storyboard_frames=storyboard_frames,
        artifacts=artifacts,
        movie_dir=movie_dir,
        capture_started=bool(capture_state["started"]),
        capture_success=capture_state["success"],
        frame_range=(start_frame, end_frame),
        frame_step=frame_step,
        sampled_source_frames=sampled_source_frames,
        output_rate_plan=output_rate_plan,
        level_path=level_path,
        capture_pending=True,
        warnings=pending_warnings,
        movie_render_pipeline_cvars=movie_render_pipeline_cvars,
        movie_render_pipeline_executor=movie_render_pipeline_executor,
    )
    return build_result(True, pending_warnings)


def _render_native_level_sequence_preview(
    inputs: dict[str, Any],
    state: dict[str, Any],
    out: Path,
    preview_frame: Path,
    preview_manifest: Path,
    storyboard_manifest: Path,
    warnings: list[Any],
) -> dict[str, Any]:
    sequence_path = inputs["sequence_path"]
    sequence = _sequence_record(state, sequence_path)
    start_frame, end_frame = _native_frame_range(inputs, sequence)
    fps = int(inputs.get("fps", sequence.get("fps", 24)) or 24)
    width, height = inputs.get("resolution", [1280, 720])
    movie_dir = out / "movie_frames"
    _mkdir(movie_dir)
    for old in movie_dir.glob("movie_frame_*.png"):
        try:
            _unlink(old)
        except OSError:
            pass

    samples = _native_preview_samples(
        sequence,
        start_frame,
        end_frame,
        max_samples=int(inputs.get("max_storyboard_samples", _MAX_STORYBOARD_SAMPLES)),
    )
    storyboard_frames: list[dict[str, Any]] = []
    artifacts = {
        "preview_frame.png": str(preview_frame),
        "preview_manifest.json": str(preview_manifest),
        "storyboard_manifest.json": str(storyboard_manifest),
        "movie_frame_dir": str(movie_dir),
    }
    for index, sample in enumerate(samples):
        name = f"storyboard_{index:03d}.png"
        record = {**sample, "artifact": str(out / name), "artifact_name": name}
        storyboard_frames.append(record)
        artifacts[name] = str(out / name)

    preview_camera = samples[0].get("camera_name") if samples else None
    preview_shot_id = samples[0].get("shot_id") if samples else None
    preview_frame_number = int(samples[0].get("frame", start_frame)) if samples else start_frame
    capture_state = {"started": False, "done": False, "success": None, "finished": False, "tick_handle": None}
    native_capture_cvars = _prepare_native_movie_capture_view(inputs)

    def finish(reason: str) -> None:
        if capture_state["finished"]:
            return
        capture_state["finished"] = True
        if capture_state["success"]:
            _copy_native_movie_outputs(
                movie_dir=movie_dir,
                preview_frame=preview_frame,
                storyboard_frames=storyboard_frames,
                warnings=warnings,
            )
        else:
            warnings.append({"reason": reason, "capture_success": capture_state["success"]})
        _write_native_preview_manifests(
            inputs=inputs,
            preview_manifest=preview_manifest,
            storyboard_manifest=storyboard_manifest,
            preview_camera=preview_camera,
            preview_shot_id=preview_shot_id,
            preview_frame_number=preview_frame_number,
            storyboard_frames=storyboard_frames,
            artifacts=artifacts,
            warnings=warnings,
            movie_dir=movie_dir,
            capture_started=bool(capture_state["started"]),
            capture_success=capture_state["success"],
            native_capture_cvars=native_capture_cvars,
        )
        handle = capture_state.get("tick_handle")
        if handle is not None:
            try:
                unreal.unregister_slate_post_tick_callback(handle)
            except Exception:
                pass
        try:
            unreal.EditorPythonScripting.set_keep_python_script_alive(False)
        except Exception:
            pass

    def on_finished(render_success: Any) -> None:
        capture_state["done"] = True
        capture_state["success"] = bool(render_success)

    expected_frame_count = max(1, end_frame - start_frame)

    def captured_frame_count() -> int:
        return sum(1 for path in movie_dir.glob("movie_frame_*.png") if _is_valid_screenshot_artifact(path))

    def on_tick(_delta_seconds: Any) -> None:
        try:
            rendering = bool(unreal.SequencerTools.is_rendering_movie())
        except Exception:
            rendering = False
        if not capture_state["done"] and captured_frame_count() >= expected_frame_count:
            capture_state["done"] = True
            capture_state["success"] = True
        if capture_state["done"] and not rendering:
            finish("callback_done")
        elif time.monotonic() >= deadline:
            finish("deadline")

    capture = unreal.AutomatedLevelSequenceCapture()
    capture.settings.output_directory = unreal.DirectoryPath(str(movie_dir))
    capture.settings.output_format = "movie_frame_{frame}"
    capture.settings.overwrite_existing = True
    capture.settings.use_relative_frame_numbers = False
    capture.settings.zero_pad_frame_numbers = 4
    capture.settings.use_custom_frame_rate = True
    capture_rate_num, capture_rate_den = _native_capture_frame_rate(inputs, sequence, fps)
    capture.settings.custom_frame_rate = unreal.FrameRate(capture_rate_num, capture_rate_den)
    capture.settings.resolution.res_x = int(width)
    capture.settings.resolution.res_y = int(height)
    capture.settings.enable_texture_streaming = False
    capture.settings.cinematic_engine_scalability = True
    capture.settings.cinematic_mode = True
    capture.settings.allow_movement = False
    capture.settings.allow_turning = False
    capture.settings.show_player = False
    capture.settings.show_hud = False
    capture.use_separate_process = False
    capture.close_editor_when_capture_starts = False
    capture.additional_command_line_arguments = "-NOSCREENMESSAGES -NoLoadingScreen -AllowCommandletRendering"
    capture.inherited_command_line_arguments = ""
    capture.use_custom_start_frame = True
    capture.use_custom_end_frame = True
    capture.custom_start_frame = unreal.FrameNumber(start_frame)
    capture.custom_end_frame = unreal.FrameNumber(end_frame)
    capture.warm_up_frame_count = int(inputs.get("warm_up_frame_count", 8) or 8)
    capture.delay_before_warm_up = 0.0
    capture.delay_before_shot_warm_up = 0.0
    capture.delay_every_frame = 0.0
    capture.write_edit_decision_list = False
    capture.write_final_cut_pro_xml = False
    capture.level_sequence_asset = unreal.SoftObjectPath(sequence_path)
    protocol_type = unreal.load_class(None, "/Script/MovieSceneCapture.ImageSequenceProtocol_PNG")
    if protocol_type is not None:
        capture.set_image_capture_protocol_type(protocol_type)
        protocol = capture.get_image_capture_protocol()
        if protocol is not None:
            protocol.compression_quality = 100

    callback = unreal.OnRenderMovieStopped()
    callback.bind_callable(on_finished)
    deadline = time.monotonic() + float(inputs.get("capture_timeout_sec", os.environ.get("CINEU_MOVIE_CAPTURE_DEADLINE", "240")) or 240)
    try:
        unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    except Exception:
        pass
    capture_state["started"] = bool(unreal.SequencerTools.render_movie(capture, callback))
    if capture_state["started"]:
        register_tick = getattr(unreal, "register_slate_post_tick_callback", None)
        if register_tick is not None:
            capture_state["tick_handle"] = register_tick(on_tick)
        else:
            while time.monotonic() < deadline:
                on_tick(0.0)
                if capture_state["finished"]:
                    break
                time.sleep(0.05)
    else:
        finish("render_movie_not_started")

    _write_native_preview_manifests(
        inputs=inputs,
        preview_manifest=preview_manifest,
        storyboard_manifest=storyboard_manifest,
        preview_camera=preview_camera,
        preview_shot_id=preview_shot_id,
        preview_frame_number=preview_frame_number,
        storyboard_frames=storyboard_frames,
        artifacts=artifacts,
        warnings=warnings,
        movie_dir=movie_dir,
        capture_started=bool(capture_state["started"]),
        capture_success=capture_state["success"],
        native_capture_cvars=native_capture_cvars,
    )
    return {
        "sequence_path": sequence_path,
        "quality": inputs.get("quality"),
        "render_backend": "sequencer_movie_capture",
        "preview_camera": preview_camera,
        "preview_shot_id": preview_shot_id,
        "preview_frame": preview_frame_number,
        "storyboard_frames": storyboard_frames,
        "artifacts": artifacts,
        "warnings": warnings,
        "capture_started": bool(capture_state["started"]),
        "capture_success": capture_state["success"],
        "native_capture_cvars": native_capture_cvars,
    }


def _find_actor_by_label(label: str):
    if unreal is None:
        return None
    for actor in unreal.EditorLevelLibrary.get_all_level_actors():
        if actor.get_actor_label() == label or actor.get_name() == label:
            return actor
    return None


def _has_scene_capture_api() -> bool:
    return (
        unreal is not None
        and hasattr(unreal, "RenderingLibrary")
        and hasattr(unreal, "SceneCapture2D")
        and hasattr(unreal, "SceneCaptureComponent2D")
        and hasattr(unreal, "TextureRenderTargetFormat")
    )


def _has_movie_capture_api() -> bool:
    return unreal is not None and hasattr(unreal, "AutomatedLevelSequenceCapture") and hasattr(unreal, "SequencerTools")


def _has_movie_render_pipeline_api() -> bool:
    return (
        unreal is not None
        and hasattr(unreal, "MoviePipelineQueueSubsystem")
        and hasattr(unreal, "MoviePipelineExecutorJob")
        and (hasattr(unreal, "MoviePipelineInProcessExecutor") or hasattr(unreal, "MoviePipelinePIEExecutor"))
        and hasattr(unreal, "MoviePipelineOutputSetting")
        and hasattr(unreal, "MoviePipelineDeferredPassBase")
        and hasattr(unreal, "MoviePipelineImageSequenceOutput_PNG")
        and hasattr(unreal, "get_editor_subsystem")
    )


def _get_editor_world() -> Any:
    if unreal is None:
        return None
    get_world = getattr(getattr(unreal, "EditorLevelLibrary", None), "get_editor_world", None)
    if get_world is not None:
        try:
            return get_world()
        except Exception:
            pass
    subsystem_class = getattr(unreal, "UnrealEditorSubsystem", None)
    get_subsystem = getattr(unreal, "get_editor_subsystem", None)
    if subsystem_class is not None and get_subsystem is not None:
        try:
            subsystem = get_subsystem(subsystem_class)
            return subsystem.get_editor_world()
        except Exception:
            pass
    return None


def _set_unreal_property(obj: Any, name: str, value: Any) -> None:
    setter = getattr(obj, "set_editor_property", None)
    if setter is not None:
        try:
            setter(name, value)
            return
        except Exception:
            pass
    try:
        setattr(obj, name, value)
    except Exception:
        pass


def _get_unreal_property(obj: Any, name: str) -> Any:
    getter = getattr(obj, "get_editor_property", None)
    if getter is not None:
        try:
            return getter(name)
        except Exception:
            pass
    return getattr(obj, name, None)


def _clamped_float(value: Any, default: float, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = float(default)
    return max(float(low), min(float(high), number))


def _configure_scene_capture_exposure(
    component: Any,
    focal_length: float | None = None,
    exposure_bias: float | None = None,
    exposure_brightness: float | None = None,
) -> None:
    _set_unreal_property(component, "post_process_blend_weight", 1.0)
    settings = _get_unreal_property(component, "post_process_settings")
    if settings is None:
        return
    bias = _clamped_float(exposure_bias, -0.55, -4.0, 2.0)
    brightness_default = max(0.08, min(0.72, 0.72 * (2.0 ** bias))) if exposure_brightness is None else 0.62
    brightness_max = 1.25 if exposure_brightness is None else 6.0
    brightness = _clamped_float(exposure_brightness, brightness_default, 0.05, brightness_max)
    bloom_intensity = 0.05 if brightness < 0.7 or bias < -0.25 else 0.1
    exposure_enum = getattr(unreal, "AutoExposureMethod", None)
    manual_exposure = getattr(exposure_enum, "AEM_MANUAL", None) if exposure_enum is not None else None
    if manual_exposure is not None:
        _set_unreal_property(settings, "override_auto_exposure_method", True)
        _set_unreal_property(settings, "auto_exposure_method", manual_exposure)
    for name, value in [
        ("override_auto_exposure_min_brightness", True),
        ("override_auto_exposure_max_brightness", True),
        ("override_auto_exposure_bias", True),
        ("override_exposure_compensation", True),
        ("override_auto_exposure_apply_physical_camera_exposure", True),
        ("auto_exposure_apply_physical_camera_exposure", False),
        ("auto_exposure_min_brightness", brightness),
        ("auto_exposure_max_brightness", brightness),
        ("auto_exposure_bias", bias),
        ("exposure_compensation", bias),
        ("bloom_intensity", bloom_intensity),
        ("vignette_intensity", 0.08),
        ("depth_of_field_fstop", 3.2),
        ("depth_of_field_focal_distance", _scene_capture_focus_distance(focal_length)),
    ]:
        _set_unreal_property(settings, name, value)
    _set_unreal_property(settings, "scene_color_tint", unreal.LinearColor(1.0, 1.0, 1.0, 1.0))
    _set_unreal_property(component, "post_process_settings", settings)


def _scene_capture_focus_distance(focal_length: float | None) -> float:
    if focal_length is None or focal_length <= 0:
        return 1120.0
    return max(900.0, min(1400.0, 1650.0 - 12.0 * float(focal_length)))


def _fov_from_focal_length(focal_length: float | None) -> float:
    if focal_length is None or focal_length <= 0:
        return 55.0
    return max(15.0, min(90.0, math.degrees(2.0 * math.atan(36.0 / (2.0 * float(focal_length))))))


def _scene_capture_visible_color_source() -> Any:
    source_enum = getattr(unreal, "SceneCaptureSource", None)
    override = os.environ.get("CINEU_SCENE_CAPTURE_SOURCE", "").strip().lower()
    override_names = {
        "scene_color_hdr": ["SCS_SCENE_COLOR_HDR", "SCS_SCENE_COLOR_HDR_NO_ALPHA"],
        "hdr": ["SCS_SCENE_COLOR_HDR", "SCS_SCENE_COLOR_HDR_NO_ALPHA"],
        "final_color_ldr": ["SCS_FINAL_COLOR_LDR", "SCS_FinalColorLDR"],
        "ldr": ["SCS_FINAL_COLOR_LDR", "SCS_FinalColorLDR"],
    }.get(override, [])
    for name in override_names:
        value = getattr(source_enum, name, None)
        if value is not None:
            return value
    for name in ["SCS_FINAL_COLOR_LDR", "SCS_FinalColorLDR", "SCS_SCENE_COLOR_HDR", "SCS_SCENE_COLOR_HDR_NO_ALPHA"]:
        value = getattr(source_enum, name, None)
        if value is not None:
            return value
    return None


def _capture_scene_to_png(
    path: Path,
    width: int,
    height: int,
    camera_name: str | None,
    focal_length: float | None,
    warnings: list[Any],
    exposure_bias: float | None = None,
    exposure_brightness: float | None = None,
) -> bool:
    if not _has_scene_capture_api():
        return False
    _prepare_screenshot_path(path)
    world = _get_editor_world()
    if world is None:
        warnings.append({"reason": "scene_capture_world_missing", "artifact": str(path)})
        return False
    camera_actor = _find_actor_by_label(camera_name) if camera_name else None
    if camera_actor is None:
        warnings.append({"reason": "scene_capture_camera_actor_missing", "camera_name": camera_name, "artifact": str(path)})
        return False
    capture_actor = None
    try:
        render_target = unreal.RenderingLibrary.create_render_target2d(
            world,
            int(width),
            int(height),
            unreal.TextureRenderTargetFormat.RTF_RGBA8,
            unreal.LinearColor(0, 0, 0, 1),
            False,
            False,
        )
        location = camera_actor.get_actor_location()
        rotation = camera_actor.get_actor_rotation()
        capture_actor = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.SceneCapture2D, location, rotation)
        component = capture_actor.get_component_by_class(unreal.SceneCaptureComponent2D)
        _set_unreal_property(component, "texture_target", render_target)
        capture_source = _scene_capture_visible_color_source()
        if capture_source is not None:
            _set_unreal_property(component, "capture_source", capture_source)
        _set_unreal_property(component, "capture_every_frame", False)
        _set_unreal_property(component, "capture_on_movement", False)
        _set_unreal_property(component, "fov_angle", _fov_from_focal_length(focal_length))
        _configure_scene_capture_exposure(component, focal_length, exposure_bias, exposure_brightness)
        for _ in range(2):
            component.capture_scene()
            try:
                unreal.EditorLevelLibrary.editor_invalidate_viewports()
            except Exception:
                pass
            time.sleep(0.05)
        unreal.RenderingLibrary.export_render_target(world, render_target, str(path.parent), path.name)
    except Exception as exc:  # noqa: BLE001
        warnings.append({"reason": "scene_capture_export_failed", "artifact": str(path), "error": str(exc)})
        return False
    finally:
        if capture_actor is not None:
            destroy_actor = getattr(unreal.EditorLevelLibrary, "destroy_actor", None)
            if destroy_actor is not None:
                try:
                    destroy_actor(capture_actor)
                except Exception:
                    pass
    if _is_valid_screenshot_artifact(path):
        return True
    _warn_invalid_screenshot(path, warnings, "scene_capture_artifact_too_small" if _path_exists(path) else "scene_capture_artifact_missing")
    return False


def _set_actor_capture_hidden(actor, hidden: bool) -> None:
    for method_name in ["set_actor_hidden_in_game", "set_is_temporarily_hidden_in_editor"]:
        method = getattr(actor, method_name, None)
        if method is None:
            continue
        try:
            method(bool(hidden))
        except Exception:
            pass


def _hide_non_active_cameras(active_camera_name: str | None) -> None:
    if unreal is None or not active_camera_name:
        return
    try:
        actors = unreal.EditorLevelLibrary.get_all_level_actors()
    except Exception:
        return
    for actor in actors:
        try:
            label = actor.get_actor_label()
        except Exception:
            continue
        if not str(label).startswith("CAM_"):
            continue
        _set_actor_capture_hidden(actor, str(label) != str(active_camera_name))


def _pilot_preview_camera(camera_name: str | None, warnings: list[Any]) -> bool:
    if unreal is None or not camera_name:
        return False
    actor = _find_actor_by_label(camera_name)
    if actor is None:
        warnings.append({"reason": "preview_camera_actor_missing", "camera_name": camera_name})
        return False
    try:
        _hide_non_active_cameras(camera_name)
        unreal.EditorLevelLibrary.pilot_level_actor(actor)
        unreal.EditorLevelLibrary.editor_set_game_view(True)
        unreal.EditorLevelLibrary.editor_invalidate_viewports()
        return True
    except Exception as exc:  # noqa: BLE001
        warnings.append({"reason": "preview_camera_pilot_failed", "camera_name": camera_name, "error": str(exc)})
        return False


def _apply_camera_sample(sample: dict[str, Any], warnings: list[Any], pilot_preview: bool = True) -> bool:
    if unreal is None:
        return False
    camera_name = sample.get("camera_name")
    actor = _find_actor_by_label(camera_name) if camera_name else None
    if actor is None:
        warnings.append({"reason": "storyboard_camera_actor_missing", "camera_name": camera_name, "frame": sample.get("frame")})
        return False
    try:
        location = sample.get("location")
        rotation = sample.get("rotation")
        if location:
            actor.set_actor_location(unreal.Vector(*location), False, False)
        if rotation:
            actor.set_actor_rotation(rotator_from_pitch_roll_yaw(unreal, rotation), False)
        focal_length = sample.get("focal_length")
        if focal_length is not None and hasattr(actor, "get_cine_camera_component"):
            actor.get_cine_camera_component().current_focal_length = float(focal_length)
        if pilot_preview:
            _pilot_preview_camera(camera_name, warnings)
        return True
    except Exception as exc:  # noqa: BLE001
        warnings.append({"reason": "storyboard_camera_pose_failed", "camera_name": camera_name, "frame": sample.get("frame"), "error": str(exc)})
        return False


def _wait_for_screenshot_task(task: Any, path: Path, warnings: list[Any], timeout_sec: float = 0.75) -> None:
    if task is None or not hasattr(task, "is_task_done"):
        if _is_valid_screenshot_artifact(path):
            return
        _warn_invalid_screenshot(path, warnings, "screenshot_artifact_too_small" if _path_exists(path) else "screenshot_artifact_missing")
        return
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() <= deadline:
        if _is_valid_screenshot_artifact(path):
            return
        try:
            done = bool(task.is_task_done())
            if done and _is_valid_screenshot_artifact(path):
                return
        except Exception as exc:  # noqa: BLE001
            warnings.append({"reason": "screenshot_task_poll_failed", "artifact": str(path), "error": str(exc)})
            return
        try:
            unreal.EditorLevelLibrary.editor_invalidate_viewports()
        except Exception:
            pass
        time.sleep(0.05)
    if _path_exists(path) and not _is_valid_screenshot_artifact(path):
        _warn_invalid_screenshot(path, warnings)
    elif not _path_exists(path):
        _warn_invalid_screenshot(path, warnings, "screenshot_artifact_missing")


def _take_high_res_screenshot(path: Path, width: int, height: int, camera_name: str | None) -> Any:
    _prepare_screenshot_path(path)
    camera_actor = _find_actor_by_label(camera_name) if camera_name else None
    try:
        return unreal.AutomationLibrary.take_high_res_screenshot(int(width), int(height), str(path), camera_actor)
    except TypeError:
        return unreal.AutomationLibrary.take_high_res_screenshot(int(width), int(height), str(path))


def _commandlet_screenshot_fallback_allowed() -> bool:
    if _truthy(os.environ.get("CINEU_ALLOW_COMMANDLET_HIGHRES_SCREENSHOT_FALLBACK", "")):
        return True
    if _truthy(os.environ.get("CINEU_DISABLE_HIGHRES_SCREENSHOT_FALLBACK", "")):
        return False
    command_line_parts = list(sys.argv)
    system_library = getattr(unreal, "SystemLibrary", None) if unreal is not None else None
    get_command_line = getattr(system_library, "get_command_line", None) if system_library is not None else None
    if callable(get_command_line):
        try:
            command_line_parts.append(str(get_command_line()))
        except Exception:
            pass
    command_line = " ".join(command_line_parts).lower()
    commandlet_tokens = ("unrealeditor-cmd", "-run=pythonscript", "-unattended", "-allowcommandletrendering")
    return not any(token in command_line for token in commandlet_tokens)


def _scene_capture_failure_allows_screenshot_fallback(path: Path, warnings: list[Any]) -> bool:
    if not _commandlet_screenshot_fallback_allowed():
        warnings.append({"reason": "high_res_screenshot_fallback_skipped_unattended", "artifact": str(path)})
        return False
    fallback_reasons = {
        "scene_capture_artifact_missing",
        "scene_capture_artifact_too_small",
        "scene_capture_export_failed",
    }
    for item in reversed(warnings[-6:]):
        if not isinstance(item, dict):
            continue
        if item.get("artifact") == str(path) and item.get("reason") in fallback_reasons:
            return True
    return False


def _capture_high_res_screenshot_to_png(path: Path, width: int, height: int, camera_name: str | None, warnings: list[Any]) -> None:
    task = _take_high_res_screenshot(path, int(width), int(height), camera_name)
    _wait_for_screenshot_task(task, path, warnings, timeout_sec=30.0)


def _capture_storyboard_frame(
    path: Path,
    width: int,
    height: int,
    sample: dict[str, Any],
    warnings: list[Any],
    state: dict[str, Any] | None = None,
    sequence_path: str | None = None,
    evaluate_sequence: bool = True,
    pilot_preview: bool = True,
) -> None:
    if unreal is not None:
        try:
            _apply_sequence_frame_state(state or {}, sequence_path, sample.get("frame"), warnings, evaluate_sequence=evaluate_sequence)
            _apply_camera_sample(sample, warnings, pilot_preview=pilot_preview)
            if not _capture_scene_to_png(
                path,
                int(width),
                int(height),
                sample.get("camera_name"),
                sample.get("focal_length"),
                warnings,
                sample.get("exposure_bias"),
                sample.get("exposure_brightness"),
            ):
                if not _has_scene_capture_api() or _scene_capture_failure_allows_screenshot_fallback(path, warnings):
                    _capture_high_res_screenshot_to_png(path, int(width), int(height), sample.get("camera_name"), warnings)
        except Exception as exc:  # noqa: BLE001
            warnings.append({"reason": "storyboard_screenshot_failed", "frame": sample.get("frame"), "error": str(exc)})
    if unreal is None and not _path_exists(path):
        _write_fallback_png(path)


def capture_storyboard_frame_once(inputs: dict[str, Any]) -> dict[str, Any]:
    path = Path(inputs["output_path"])
    _mkdir(path.parent)
    width, height = inputs.get("resolution", [1280, 720])
    sample = inputs["sample"]
    state = _load_world_state(inputs.get("world_state_path"))
    sequence_path = inputs.get("sequence_path")
    warnings: list[Any] = []
    if unreal is not None:
        try:
            _apply_sequence_frame_state(state, sequence_path, sample.get("frame"), warnings)
            _apply_camera_sample(sample, warnings)
            if not _capture_scene_to_png(
                path,
                int(width),
                int(height),
                sample.get("camera_name"),
                sample.get("focal_length"),
                warnings,
                sample.get("exposure_bias"),
                sample.get("exposure_brightness"),
            ):
                if not _has_scene_capture_api() or _scene_capture_failure_allows_screenshot_fallback(path, warnings):
                    _capture_high_res_screenshot_to_png(path, int(width), int(height), sample.get("camera_name"), warnings)
        except Exception as exc:  # noqa: BLE001
            warnings.append({"reason": "single_storyboard_screenshot_failed", "frame": sample.get("frame"), "error": str(exc)})
    else:
        _write_fallback_png(path)
    return {"output_path": str(path), "sample": sample, "warnings": warnings}


def _render_scene_capture_sequence_preview(
    inputs: dict[str, Any],
    state: dict[str, Any],
    out: Path,
    preview_frame: Path,
    preview_manifest: Path,
    storyboard_manifest: Path,
    warnings: list[Any],
) -> dict[str, Any]:
    sequence_path = inputs["sequence_path"]
    sequence = _sequence_record(state, sequence_path)
    start_frame, end_frame = _native_frame_range(inputs, sequence)
    width, height = inputs.get("resolution", [1280, 720])
    movie_dir = out / "movie_frames"
    _mkdir(movie_dir)
    for old in movie_dir.glob("movie_frame_*.png"):
        try:
            _unlink(old)
        except OSError:
            pass

    evaluate_sequence = str(
        inputs.get("scene_capture_evaluate_sequence")
        or os.environ.get("CINEU_SCENE_CAPTURE_EVALUATE_SEQUENCE", "1")
    ).strip().lower() not in {"0", "false", "no", "off"}
    expected_frames = list(range(start_frame, end_frame))
    for frame in expected_frames:
        sample = _scene_capture_sequence_sample(sequence, frame, start_frame, end_frame)
        _capture_storyboard_frame(
            _native_movie_frame_path(movie_dir, frame),
            int(width),
            int(height),
            sample,
            warnings,
            state,
            sequence_path,
            evaluate_sequence=evaluate_sequence,
            pilot_preview=False,
        )

    captured_successfully = [
        frame for frame in expected_frames if _is_valid_screenshot_artifact(_native_movie_frame_path(movie_dir, frame))
    ]
    capture_success = len(captured_successfully) == len(expected_frames) and bool(expected_frames)

    max_storyboard_samples = int(inputs.get("max_storyboard_samples", _MAX_STORYBOARD_SAMPLES))
    storyboard_source_samples = _native_preview_samples(
        sequence,
        start_frame,
        end_frame,
        max_samples=max_storyboard_samples,
    )
    storyboard_frames: list[dict[str, Any]] = []
    artifacts = {
        "preview_frame.png": str(preview_frame),
        "preview_manifest.json": str(preview_manifest),
        "storyboard_manifest.json": str(storyboard_manifest),
        "movie_frame_dir": str(movie_dir),
    }
    for index, source_sample in enumerate(storyboard_source_samples):
        sample = _scene_capture_sequence_sample(sequence, int(source_sample["frame"]), start_frame, end_frame)
        name = f"storyboard_{index:03d}.png"
        source = _native_movie_frame_path(movie_dir, int(sample["frame"]))
        destination = out / name
        if _is_valid_screenshot_artifact(source):
            shutil.copyfile(_windows_long_path(source), _windows_long_path(destination))
        else:
            _warn_invalid_screenshot(source, warnings, "scene_capture_sequence_storyboard_source_missing")
        record = {**sample, "artifact": str(destination), "artifact_name": name}
        storyboard_frames.append(record)
        artifacts[name] = str(destination)

    first_movie_frame = _native_movie_frame_path(movie_dir, captured_successfully[0]) if captured_successfully else None
    if first_movie_frame is not None and _is_valid_screenshot_artifact(first_movie_frame):
        shutil.copyfile(_windows_long_path(first_movie_frame), _windows_long_path(preview_frame))
    elif storyboard_frames:
        _warn_invalid_screenshot(Path(str(storyboard_frames[0]["artifact"])), warnings, "scene_capture_sequence_preview_source_missing")
    elif unreal is None and not _path_exists(preview_frame):
        _write_fallback_png(preview_frame)

    first_sample = _scene_capture_sequence_sample(sequence, start_frame, start_frame, end_frame) if expected_frames else {}
    preview_camera = first_sample.get("camera_name")
    preview_shot_id = first_sample.get("shot_id")
    preview_frame_number = start_frame
    manifest = {
        "sequence_path": sequence_path,
        "resolution": inputs.get("resolution", [1280, 720]),
        "format": inputs.get("format", "mp4"),
        "quality": inputs.get("quality", "preview"),
        "render_backend": "scene_capture_sequence",
        "scene_capture_sequence_frame_range": [int(start_frame), int(end_frame)],
        "scene_capture_sequence_frame_count": len(captured_successfully),
        "native_capture_frame_range": [int(start_frame), int(end_frame)],
        "preview_camera": preview_camera,
        "preview_shot_id": preview_shot_id,
        "preview_frame": preview_frame_number,
        "storyboard_frames": storyboard_frames,
        "warnings": warnings,
        "artifacts": artifacts,
        "movie_frame_dir": str(movie_dir),
        "capture_started": True,
        "capture_success": capture_success,
    }
    storyboard_payload = {
        "sequence_path": sequence_path,
        "resolution": inputs.get("resolution", [1280, 720]),
        "render_backend": "scene_capture_sequence",
        "scene_capture_sequence_frame_range": [int(start_frame), int(end_frame)],
        "native_capture_frame_range": [int(start_frame), int(end_frame)],
        "movie_frame_dir": str(movie_dir),
        "frames": storyboard_frames,
        "warnings": warnings,
        "capture_started": True,
        "capture_success": capture_success,
    }
    _write_text(storyboard_manifest, json.dumps(storyboard_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_text(preview_manifest, json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "sequence_path": sequence_path,
        "quality": inputs.get("quality"),
        "render_backend": "scene_capture_sequence",
        "preview_camera": preview_camera,
        "preview_shot_id": preview_shot_id,
        "preview_frame": preview_frame_number,
        "storyboard_frames": storyboard_frames,
        "artifacts": artifacts,
        "warnings": warnings,
        "capture_started": True,
        "capture_success": capture_success,
        "movie_frame_dir": str(movie_dir),
        "scene_capture_sequence_frame_range": [int(start_frame), int(end_frame)],
    }


def render_preview(inputs: dict[str, Any]) -> dict[str, Any]:
    out = Path(inputs["output_dir"])
    _mkdir(out)
    preview_frame = out / "preview_frame.png"
    preview_manifest = out / "preview_manifest.json"
    storyboard_manifest = out / "storyboard_manifest.json"
    warnings: list[Any] = []
    state = _load_world_state(inputs.get("world_state_path"))
    requested_backend = str(inputs.get("render_backend") or inputs.get("capture_backend") or "").strip().lower()
    force_scene_capture_sequence = requested_backend in {"scene_capture_sequence", "scene_capture_movie", "sync_scene_capture"}
    force_scene_capture = requested_backend in {"scene_capture", "scene_capture2d", "screenshot", "storyboard"}
    if force_scene_capture_sequence:
        return _render_scene_capture_sequence_preview(
            inputs,
            state,
            out,
            preview_frame,
            preview_manifest,
            storyboard_manifest,
            warnings,
        )
    if (
        not force_scene_capture
        and not force_scene_capture_sequence
        and _has_movie_render_pipeline_api()
        and _should_use_movie_render_pipeline(inputs, state, inputs["sequence_path"])
    ):
        return _render_movie_pipeline_level_sequence_preview(
            inputs,
            state,
            out,
            preview_frame,
            preview_manifest,
            storyboard_manifest,
            warnings,
        )
    if (
        not force_scene_capture
        and not force_scene_capture_sequence
        and _has_movie_capture_api()
        and _should_use_movie_capture_sequence(state, inputs["sequence_path"])
    ):
        return _render_native_level_sequence_preview(
            inputs,
            state,
            out,
            preview_frame,
            preview_manifest,
            storyboard_manifest,
            warnings,
        )
    first_cut = _first_camera_cut(state, inputs["sequence_path"])
    preview_camera = first_cut.get("camera_name") if first_cut else None
    preview_shot_id = first_cut.get("shot_id") if first_cut else None
    preview_frame_number = first_cut.get("start_frame") if first_cut else 0
    width, height = inputs.get("resolution", [1280, 720])
    max_storyboard_samples = int(inputs.get("max_storyboard_samples", _MAX_STORYBOARD_SAMPLES))
    preview_sample = next(
        (
            sample
            for sample in _storyboard_samples(state, inputs["sequence_path"], max_samples=max_storyboard_samples)
            if sample.get("camera_name") == preview_camera and sample.get("frame") == preview_frame_number
        ),
        {"camera_name": preview_camera, "frame": preview_frame_number, "focal_length": None} if preview_camera else None,
    )
    if unreal is not None:
        try:
            if preview_sample is not None:
                _apply_sequence_frame_state(
                    state,
                    inputs["sequence_path"],
                    preview_sample.get("frame"),
                    warnings,
                    evaluate_sequence=not force_scene_capture,
                )
                _apply_camera_sample(preview_sample, warnings, pilot_preview=not force_scene_capture)
            else:
                if not force_scene_capture:
                    _pilot_preview_camera(preview_camera, warnings)
            if not _capture_scene_to_png(
                preview_frame,
                int(width),
                int(height),
                preview_camera,
                preview_sample.get("focal_length") if preview_sample else None,
                warnings,
                preview_sample.get("exposure_bias") if preview_sample else None,
                preview_sample.get("exposure_brightness") if preview_sample else None,
            ):
                if not _has_scene_capture_api() or _scene_capture_failure_allows_screenshot_fallback(preview_frame, warnings):
                    _capture_high_res_screenshot_to_png(preview_frame, int(width), int(height), preview_camera, warnings)
        except Exception as exc:  # noqa: BLE001
            warnings.append({"reason": "high_res_screenshot_failed", "error": str(exc)})
    if unreal is None and not _path_exists(preview_frame):
        _write_fallback_png(preview_frame)
    storyboard_frames = []
    artifacts = {
        "preview_frame.png": str(preview_frame),
        "preview_manifest.json": str(preview_manifest),
        "storyboard_manifest.json": str(storyboard_manifest),
    }
    for index, sample in enumerate(_storyboard_samples(state, inputs["sequence_path"], max_samples=max_storyboard_samples)):
        name = f"storyboard_{index:03d}.png"
        path = out / name
        _capture_storyboard_frame(
            path,
            int(width),
            int(height),
            sample,
            warnings,
            state,
            inputs["sequence_path"],
            evaluate_sequence=not force_scene_capture,
            pilot_preview=not force_scene_capture,
        )
        frame_record = {**sample, "artifact": str(path), "artifact_name": name}
        storyboard_frames.append(frame_record)
        artifacts[name] = str(path)
    _write_text(
        storyboard_manifest,
        json.dumps(
            {
                "sequence_path": inputs["sequence_path"],
                "resolution": inputs.get("resolution", [1280, 720]),
                "frames": storyboard_frames,
                "warnings": warnings,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    manifest = {
        "sequence_path": inputs["sequence_path"],
        "resolution": inputs.get("resolution", [1280, 720]),
        "format": inputs.get("format", "mp4"),
        "quality": inputs.get("quality", "preview"),
        "preview_camera": preview_camera,
        "preview_shot_id": preview_shot_id,
        "preview_frame": preview_frame_number,
        "storyboard_frames": storyboard_frames,
        "warnings": warnings,
        "artifacts": artifacts,
    }
    _write_text(preview_manifest, json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "sequence_path": inputs["sequence_path"],
        "quality": inputs.get("quality"),
        "preview_camera": preview_camera,
        "preview_shot_id": preview_shot_id,
        "preview_frame": preview_frame_number,
        "storyboard_frames": storyboard_frames,
        "artifacts": artifacts,
        "warnings": warnings,
    }
