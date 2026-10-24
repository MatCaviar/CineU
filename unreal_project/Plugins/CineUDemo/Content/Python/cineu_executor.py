from __future__ import annotations

import json
import runpy
import traceback
from pathlib import Path
from typing import Any

from cineu_verify_ops import dump_world_state_to_file


def _load_state(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _support_surfaces_for_rehydrate(state: dict[str, Any], *, level_environment: bool) -> dict[str, Any]:
    surfaces = state.get("support_surfaces", {})
    if not isinstance(surfaces, dict):
        return {}
    if not level_environment:
        return surfaces
    park_surface = surfaces.get("park_path")
    if not isinstance(park_surface, dict):
        return surfaces
    normalized = dict(surfaces)
    normalized["park_path"] = {**park_surface, "environment_asset_type": "level"}
    return normalized


def _is_planned_actor(spec: dict[str, Any]) -> bool:
    name = str(spec.get("name", ""))
    if str(spec.get("semantic_type", "")).lower() == "camera":
        return False
    if str(spec.get("asset_type", "")).lower() == "camera":
        return False
    if str(spec.get("asset_id", "")).lower() == "cine_camera_actor":
        return False
    return bool(
        spec.get("asset_id")
        or spec.get("semantic_type")
        or name.startswith("CineU_Gallery_Label_")
        or name.startswith("CineU_Gallery_ArtAccent_")
        or name.startswith("CineU_Gallery_ArtStripe_")
        or name.startswith("CineU_Gallery_ArtBrush")
        or name.startswith("CineU_Gallery_ArtFlow")
        or name.startswith("CineU_Gallery_HeroBackdrop_")
        or name.startswith("CineU_Gallery_LightPatch_")
        or name.startswith("CineU_Gallery_Entry")
        or name.startswith("CineU_Gallery_WindowPane_")
        or name.startswith("CineU_Gallery_WindowMullion_")
        or name.startswith("CineU_Gallery_CeilingBeam_")
        or name.startswith("CineU_Gallery_SkylightPane_")
        or name.startswith("CineU_Gallery_Exterior")
        or name.startswith("CineU_Zebra_Stripe_")
        or name.startswith("CineU_LevelPark_ForegroundWillow_")
        or name.startswith("CineU_LevelPark_CanopyWillow_")
        or name.startswith("CineU_LevelPark_HangingIvy_")
        or name.startswith("CineU_LevelPark_ImportedCanopy_")
    )


def _records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [item for item in value.values() if isinstance(item, dict)]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _sequence_range(sequence: dict[str, Any]) -> tuple[int, int]:
    raw = sequence.get("range") or [sequence.get("start_frame", 0), sequence.get("end_frame", 0)]
    if isinstance(raw, list) and len(raw) >= 2:
        return int(raw[0]), int(raw[1])
    return 0, 0


def _camera_cut_for(cuts: list[dict[str, Any]], camera_name: str) -> dict[str, Any] | None:
    for cut in cuts:
        if str(cut.get("camera_name")) == camera_name:
            return cut
    return None


def _focal_length_for_frame(focal_keys: list[dict[str, Any]], frame: int) -> float:
    if not focal_keys:
        return 35.0
    ordered = sorted(focal_keys, key=lambda item: int(item.get("frame", 0)))
    selected = ordered[0]
    for key in ordered:
        if int(key.get("frame", 0)) <= frame:
            selected = key
        else:
            break
    return float(selected.get("focal_length", 35.0))


def _camera_keys(camera: dict[str, Any]) -> list[dict[str, Any]]:
    focal_keys = _records(camera.get("focal_length_keys"))
    keys: list[dict[str, Any]] = []
    for key in _records(camera.get("transform_keys")):
        frame = int(key.get("frame", 0))
        keys.append(
            {
                "frame": frame,
                "location": key.get("location", [0.0, 0.0, 0.0]),
                "rotation": key.get("rotation", [0.0, 0.0, 0.0]),
                "focal_length": _focal_length_for_frame(focal_keys, frame),
            }
        )
    return keys


def _rehydrate_sequences_from_state(state: dict[str, Any]) -> None:
    sequences = state.get("sequences")
    if not isinstance(sequences, dict):
        return
    from cineu_anim_ops import add_animation_tracks
    from cineu_camera_ops import create_camera_shot
    from cineu_sequence_ops import add_camera_cuts, add_transform_tracks, create_level_sequence

    for fallback_path, sequence in sequences.items():
        if not isinstance(sequence, dict):
            continue
        sequence_path = str(sequence.get("sequence_path") or fallback_path)
        if sequence.get("source_asset_type") == "level_sequence":
            continue
        start_frame, end_frame = _sequence_range(sequence)
        create_level_sequence(
            {
                "sequence_path": sequence_path,
                "fps": int(sequence.get("fps", 24)),
                "start_frame": start_frame,
                "end_frame": end_frame,
            }
        )
        cuts = _records(sequence.get("camera_cuts"))
        for camera_name, camera in (sequence.get("cameras") or {}).items():
            if not isinstance(camera, dict):
                continue
            keys = _camera_keys(camera)
            if not keys:
                continue
            cut = _camera_cut_for(cuts, str(camera_name))
            camera_start = int(cut.get("start_frame", start_frame)) if cut else min(int(key["frame"]) for key in keys)
            camera_end = int(cut.get("end_frame", end_frame)) if cut else max(int(key["frame"]) for key in keys)
            create_camera_shot(
                {
                    "sequence_path": sequence_path,
                    "shot_id": str(camera.get("shot_id") or camera_name),
                    "camera_name": str(camera_name),
                    "target_actor": camera.get("target_actor"),
                    "start_frame": camera_start,
                    "end_frame": camera_end,
                    "keys": keys,
                }
            )
        transform_tracks = _records(sequence.get("transform_tracks"))
        if transform_tracks:
            add_transform_tracks({"sequence_path": sequence_path, "tracks": transform_tracks})
        animation_tracks = _records(sequence.get("animation_tracks"))
        if animation_tracks:
            add_animation_tracks({"sequence_path": sequence_path, "clips": animation_tracks})
        if cuts:
            add_camera_cuts({"sequence_path": sequence_path, "cuts": cuts})


def _rehydrate_world_state(world_state_path: str | None) -> None:
    state = _load_state(world_state_path)
    if not state:
        return
    try:
        from cineu_world_ops import _is_level_environment_asset, _spawn_environment_asset_if_available, ensure_actor_from_state, ensure_support_surfaces

        environment_asset = state.get("environment_asset")
        level_environment = _is_level_environment_asset(environment_asset)
        if level_environment:
            _spawn_environment_asset_if_available(environment_asset)
        ensure_support_surfaces(_support_surfaces_for_rehydrate(state, level_environment=level_environment))
        if environment_asset and not level_environment:
            _spawn_environment_asset_if_available(environment_asset)
        for actor_name, spec in state.get("actors", {}).items():
            if isinstance(spec, dict) and _is_planned_actor(spec):
                ensure_actor_from_state(actor_name, spec)
        _rehydrate_sequences_from_state(state)
    except Exception:
        # Rehydration is best-effort. The operation wrapper remains responsible
        # for reporting hard failures when it cannot satisfy its own contract.
        return


def _write_json(path: str | None, data: dict[str, Any]) -> None:
    if not path:
        return
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def execute_generated_script(script_path: str, world_state_path: str | None = None, result_path: str | None = None) -> dict[str, Any]:
    """Execute a generated script inside Unreal Editor Python.

    This wrapper is intentionally thin: host-side middleware owns the source of
    truth, verification, and rollback. The executor captures a JSON result and
    dumps editor world state after execution.
    """
    result: dict[str, Any] = {"ok": False, "script_path": script_path, "output": None, "error": None}
    params: dict[str, Any] | None = None
    output: Any = None
    try:
        _rehydrate_world_state(world_state_path)
        namespace = runpy.run_path(script_path)
        params = namespace.get("PARAMS")
        output = namespace.get("OUTPUT")
        result.update({"ok": True, "output": output})
    except Exception as exc:  # noqa: BLE001
        result["error"] = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
    finally:
        if world_state_path:
            result["world_state"] = dump_world_state_to_file(world_state_path, params=params, output=output, result=result)
        _write_json(result_path, result)
    if not result["ok"]:
        raise RuntimeError(result["error"])
    return result
