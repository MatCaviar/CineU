from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import unreal  # type: ignore
except Exception:  # pragma: no cover
    unreal = None


def _empty_state() -> dict[str, Any]:
    return {
        "schema_version": "cineu.world_state.v1",
        "level": None,
        "support_surfaces": {},
        "asset_imports": {},
        "actors": {},
        "sequences": {},
        "renders": [],
        "warnings": [],
    }


def _load_state(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return _empty_state()
    try:
        state = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        state = _empty_state()
    for key, default in _empty_state().items():
        state.setdefault(key, default)
    return state


def _write_state(path: str, state: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _static_mesh_asset_path_from_actor(actor: Any) -> str | None:
    component = None
    get_editor_property = getattr(actor, "get_editor_property", None)
    if get_editor_property is not None:
        try:
            component = get_editor_property("static_mesh_component")
        except Exception:
            component = None
    if component is None and unreal is not None:
        try:
            component = actor.get_component_by_class(unreal.StaticMeshComponent)
        except Exception:
            component = None
    if component is None:
        component = getattr(actor, "static_mesh_component", None)
    if component is None:
        return None
    mesh = None
    component_get_editor_property = getattr(component, "get_editor_property", None)
    if component_get_editor_property is not None:
        try:
            mesh = component_get_editor_property("static_mesh")
        except Exception:
            mesh = None
    if mesh is None:
        mesh = getattr(component, "static_mesh", None)
    if mesh is None:
        return None
    get_path_name = getattr(mesh, "get_path_name", None)
    if get_path_name is not None:
        try:
            return str(get_path_name()).split(".", 1)[0]
        except Exception:
            return None
    return None


def _merge_unreal_actor_scan(state: dict[str, Any]) -> None:
    if unreal is None:
        return
    try:
        world = unreal.EditorLevelLibrary.get_editor_world()
        state["level"] = world.get_name() if world else state.get("level")
        for actor in unreal.EditorLevelLibrary.get_all_level_actors():
            label = actor.get_actor_label()
            loc = actor.get_actor_location()
            rot = actor.get_actor_rotation()
            scale = actor.get_actor_scale3d()
            try:
                _origin, extent = actor.get_actor_bounds(False)
                bounds_extent = [float(extent.x), float(extent.y), float(extent.z)]
            except Exception:
                bounds_extent = [0.0, 0.0, 0.0]
            current = state["actors"].get(label, {})
            mesh_asset_path = _static_mesh_asset_path_from_actor(actor)
            current.update(
                {
                    "name": label,
                    "asset_type": current.get("asset_type", actor.get_class().get_name()),
                    "asset_path": current.get("asset_path") or mesh_asset_path,
                    "bounds_extent": current.get("bounds_extent", bounds_extent),
                    "transform": {
                        "location": [float(loc.x), float(loc.y), float(loc.z)],
                        "rotation": [float(rot.pitch), float(rot.roll), float(rot.yaw)],
                        "scale": [float(scale.x), float(scale.y), float(scale.z)],
                    },
                }
            )
            state["actors"][label] = current
    except Exception as exc:  # noqa: BLE001
        state.setdefault("warnings", []).append(f"actor_scan_failed:{type(exc).__name__}:{exc}")


def _should_merge_unreal_actor_scan(params: dict[str, Any] | None) -> bool:
    if not params:
        return True
    op_type = str(params.get("operation_type", ""))
    return op_type == "env.setup" or op_type == "entity.spawn_many" or op_type == "spatial.apply_transforms" or op_type.startswith("camera.")


def _ensure_sequence(state: dict[str, Any], sequence_path: str) -> dict[str, Any]:
    return state.setdefault("sequences", {}).setdefault(
        sequence_path,
        {
            "sequence_path": sequence_path,
            "fps": 24,
            "range": [0, 0],
            "cameras": {},
            "camera_cuts": [],
            "transform_tracks": {},
            "animation_tracks": {},
            "bound_actors": [],
        },
    )


def _resolved_asset_path_for_actor(state: dict[str, Any], actor: dict[str, Any]) -> Any:
    asset_id = actor.get("asset_id")
    if not asset_id:
        return actor.get("asset_path")
    record = state.get("asset_imports", {}).get(asset_id)
    if isinstance(record, dict) and record.get("ue_path") and record.get("status") in {"imported", "already_exists", "available"}:
        return record.get("ue_path")
    return actor.get("asset_path")


def _sync_actor_asset_paths_from_imports(state: dict[str, Any]) -> None:
    imports = state.get("asset_imports", {})
    if not isinstance(imports, dict):
        return
    for actor in state.get("actors", {}).values():
        if not isinstance(actor, dict):
            continue
        resolved = _resolved_asset_path_for_actor(state, actor)
        if resolved:
            actor["asset_path"] = resolved


def _imported_animation_path_for_actor(state: dict[str, Any], actor_name: str) -> str | None:
    actor = state.get("actors", {}).get(actor_name)
    if not isinstance(actor, dict):
        return None
    asset_id = actor.get("asset_id")
    if not asset_id:
        return None
    record = state.get("asset_imports", {}).get(asset_id)
    if not isinstance(record, dict):
        return None
    paths = record.get("imported_animation_paths")
    if not paths:
        paths = [path for path in record.get("imported_object_paths", []) if "anim" in str(path).lower()]
    for path in paths:
        if path:
            return str(path)
    return None


def _resolved_animation_clip(state: dict[str, Any], clip: dict[str, Any]) -> dict[str, Any]:
    resolved = dict(clip)
    animation_path = _imported_animation_path_for_actor(state, str(clip.get("actor_name", "")))
    if animation_path:
        resolved["animation_path"] = animation_path
        resolved["source_type"] = "imported_with_actor"
    return resolved


def _sync_animation_tracks_from_imports(state: dict[str, Any]) -> None:
    for sequence in state.get("sequences", {}).values():
        if not isinstance(sequence, dict):
            continue
        tracks = sequence.get("animation_tracks")
        if not isinstance(tracks, dict):
            continue
        for actor_name, clip in list(tracks.items()):
            if isinstance(clip, dict):
                tracks[actor_name] = _resolved_animation_clip(state, clip)


def _merge_operation_metadata(state: dict[str, Any], params: dict[str, Any] | None, output: Any) -> None:
    if not params:
        return
    op_type = params.get("operation_type")
    inputs = params.get("inputs", {})
    if op_type == "env.setup":
        state["level"] = inputs.get("level_name") or (output or {}).get("level")
        environment_asset = inputs.get("environment_asset") or ((output or {}).get("environment_asset") if isinstance(output, dict) else None)
        if environment_asset:
            state["environment_asset"] = environment_asset
        support = (output or {}).get("support_surfaces") if isinstance(output, dict) else None
        if support:
            state["support_surfaces"] = support
        elif "desert" in str(inputs.get("environment", "gallery")).lower():
            state["support_surfaces"] = {
                "desert_floor": {"type": "ground", "z": 0.0, "bounds": [-2000, 2000, -2000, 2000]},
            }
        else:
            state["support_surfaces"] = {
                "gallery_floor": {"type": "ground", "z": 0.0, "bounds": [-500, 500, -500, 500]},
                "left_wall": {"type": "wall", "x": -500.0, "bounds": [-500, -500, -500, 500, 0, 800]},
                "right_wall": {"type": "wall", "x": 500.0, "bounds": [500, 500, -500, 500, 0, 800]},
                "back_wall": {"type": "wall", "y": 500.0, "bounds": [-500, 500, 500, 500, 0, 800]},
            }
    elif op_type == "entity.spawn_many":
        for actor in inputs.get("actors", []):
            name = actor["actor_name"]
            current = state["actors"].setdefault(
                name,
                {
                    "name": name,
                    "transform": {"location": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
                },
            )
            current.update(
                {
                    "name": name,
                    "semantic_type": actor.get("semantic_type"),
                    "asset_id": actor.get("asset_id"),
                    "asset_path": _resolved_asset_path_for_actor(state, actor),
                    "asset_type": actor.get("asset_type"),
                    "reuse_actor_name": actor.get("reuse_actor_name", current.get("reuse_actor_name")),
                    "source_path": actor.get("source_path"),
                    "source_type": actor.get("source_type"),
                    "import_required": actor.get("import_required", False),
                    "materials": actor.get("materials", current.get("materials", [])),
                    "bounds_extent": actor.get("bounds_extent", current.get("bounds_extent", [50, 50, 50])),
                }
            )
    elif op_type == "asset.import_many":
        state.setdefault("asset_imports", {})
        records = []
        if isinstance(output, dict):
            records = output.get("assets", [])
        for record in records:
            if isinstance(record, dict) and record.get("asset_id"):
                state["asset_imports"][record["asset_id"]] = record
        _sync_actor_asset_paths_from_imports(state)
    elif op_type == "spatial.apply_transforms":
        for placement in inputs.get("placements", []):
            actor = state["actors"].setdefault(placement["actor_name"], {"name": placement["actor_name"]})
            actor["transform"] = placement["transform"]
            actor["bounds_extent"] = placement.get("bounds_extent", actor.get("bounds_extent", [50, 50, 50]))
            actor["spatial_relation"] = {"relation": placement.get("relation"), "target": placement.get("target")}
    elif op_type == "sequence.init":
        seq = _ensure_sequence(state, inputs["sequence_path"])
        seq["fps"] = inputs["fps"]
        seq["range"] = [inputs["start_frame"], inputs["end_frame"]]
    elif op_type == "sequence.use_existing":
        seq = _ensure_sequence(state, inputs["sequence_path"])
        asset = inputs.get("sequence_asset") or {}
        seq["source_asset_id"] = asset.get("asset_id")
        seq["source_asset_type"] = asset.get("type")
        seq["source_path"] = asset.get("source_path")
        if isinstance(output, dict) and output.get("fps"):
            seq["asset_fps"] = output["fps"]
        seq["fps"] = inputs.get("fps", seq.get("fps", 24))
        if isinstance(output, dict) and output.get("range"):
            seq["asset_range"] = output["range"]
        seq["range"] = [inputs.get("start_frame", 0), inputs.get("end_frame", 0)]
        if isinstance(output, dict):
            metadata = {
                key: output[key]
                for key in ["display_rate", "bindings", "master_tracks", "camera_cut_sections"]
                if key in output
            }
            if metadata:
                seq["ue_sequence_metadata"] = metadata
        camera_name = inputs.get("native_camera_name") or "NativeSequenceCamera"
        if not seq.get("camera_cuts"):
            seq["camera_cuts"] = [
                {
                    "camera_name": camera_name,
                    "shot_id": inputs.get("shot_id", "existing_sequence"),
                    "start_frame": seq["range"][0],
                    "end_frame": seq["range"][1],
                }
            ]
    elif str(op_type).startswith("camera."):
        seq = _ensure_sequence(state, inputs["sequence_path"])
        camera_name = inputs["camera_name"]
        keys = inputs.get("keys", [])
        if keys:
            first = keys[0]
            state["actors"][camera_name] = {
                "name": camera_name,
                "semantic_type": "camera",
                "asset_id": "cine_camera_actor",
                "asset_path": "/Script/CinematicCamera.CineCameraActor",
                "asset_type": "camera",
                "bounds_extent": [0, 0, 0],
                "transform": {"location": first["location"], "rotation": first["rotation"], "scale": [1, 1, 1]},
            }
        seq["cameras"][camera_name] = {
            "shot_id": inputs.get("shot_id"),
            "target_actor": inputs.get("target_actor"),
            "transform_keys": [{k: key[k] for k in ["frame", "location", "rotation"]} for key in keys],
            "focal_length_keys": [{"frame": key["frame"], "focal_length": key.get("focal_length")} for key in keys],
            "focus_distance_keys": [{"frame": key["frame"], "focus_distance": key.get("focus_distance")} for key in keys],
        }
    elif op_type == "transform.add_tracks":
        seq = _ensure_sequence(state, inputs["sequence_path"])
        for track in inputs.get("tracks", []):
            seq["transform_tracks"][track["actor_name"]] = track
    elif op_type == "animation.add_tracks":
        seq = _ensure_sequence(state, inputs["sequence_path"])
        for clip in inputs.get("clips", []):
            seq["animation_tracks"][clip["actor_name"]] = _resolved_animation_clip(state, clip)
    elif op_type == "sequence.camera_cut":
        seq = _ensure_sequence(state, inputs["sequence_path"])
        seq["camera_cuts"] = sorted(inputs.get("cuts", []), key=lambda item: item["start_frame"])
    elif op_type == "render.preview":
        artifacts = (output or {}).get("artifacts", {}) if isinstance(output, dict) else {}
        state.setdefault("renders", []).append(
            {
                "sequence_path": inputs.get("sequence_path"),
                "quality": inputs.get("quality"),
                "preview_camera": (output or {}).get("preview_camera") if isinstance(output, dict) else None,
                "preview_shot_id": (output or {}).get("preview_shot_id") if isinstance(output, dict) else None,
                "preview_frame": (output or {}).get("preview_frame") if isinstance(output, dict) else None,
                "artifacts": artifacts,
            }
        )
    _sync_actor_asset_paths_from_imports(state)
    _sync_animation_tracks_from_imports(state)


def dump_world_state_to_file(
    path: str,
    params: dict[str, Any] | None = None,
    output: Any | None = None,
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = _load_state(path)
    _merge_operation_metadata(state, params, output)
    if _should_merge_unreal_actor_scan(params):
        _merge_unreal_actor_scan(state)
    if result and result.get("error"):
        state.setdefault("warnings", []).append(result["error"])
    _write_state(path, state)
    return state
