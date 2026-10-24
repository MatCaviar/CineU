from __future__ import annotations

from typing import Any

try:
    import unreal  # type: ignore
except Exception:  # pragma: no cover
    unreal = None


def find_clip_path(clip: dict[str, Any], actor_metadata: dict[str, Any] | None = None) -> str | None:
    animation_type = str(clip.get("animation_type", "")).lower()
    for item in (actor_metadata or {}).get("animations", []):
        if str(item.get("name", "")).lower() == animation_type:
            return item.get("path")
    return clip.get("animation_path")


def add_animation_tracks(inputs: dict[str, Any]) -> dict[str, Any]:
    clips = inputs.get("clips", [])
    if unreal is None:
        return {"animation_tracks": [c["actor_name"] for c in clips], "warnings": ["unreal_module_unavailable"]}
    seq = unreal.EditorAssetLibrary.load_asset(inputs["sequence_path"])
    if seq is None:
        raise RuntimeError(f"Sequence not found: {inputs['sequence_path']}")
    actors = {a.get_actor_label(): a for a in unreal.EditorLevelLibrary.get_all_level_actors()}
    added = []
    warnings = []
    for clip in clips:
        actor_name = clip["actor_name"]
        actor = actors.get(actor_name)
        if actor is None:
            raise RuntimeError(f"Actor not found for animation track: {actor_name}")
        clip_path = find_clip_path(clip)
        animation = unreal.EditorAssetLibrary.load_asset(str(clip_path)) if clip_path else None
        if animation is None:
            warnings.append({"actor": actor_name, "reason": "animation_asset_missing", "animation_path": clip_path})
            continue
        binding = seq.add_possessable(actor)
        track = binding.add_track(unreal.MovieSceneSkeletalAnimationTrack)
        section = track.add_section()
        try:
            section.set_range(int(clip.get("start_frame", 0)), int(clip.get("end_frame", clip.get("start_frame", 0))))
        except Exception as exc:  # noqa: BLE001
            warnings.append({"actor": actor_name, "reason": "animation_section_range_failed", "error": str(exc)})
        if not _assign_animation_to_section(section, animation):
            warnings.append({"actor": actor_name, "reason": "animation_section_assignment_failed", "animation_path": clip_path})
            continue
        added.append(actor_name)
    unreal.EditorAssetLibrary.save_asset(inputs["sequence_path"])
    return {"animation_tracks": added, "warnings": warnings}


def _assign_animation_to_section(section: Any, animation: Any) -> bool:
    params = getattr(section, "params", None)
    if params is not None:
        try:
            params.set_editor_property("animation", animation)
        except Exception:
            try:
                params.animation = animation
            except Exception:
                return False
        try:
            section.set_editor_property("params", params)
        except Exception:
            try:
                section.params = params
            except Exception:
                pass
        return True
    try:
        section.set_editor_property("animation", animation)
        return True
    except Exception:
        try:
            section.animation = animation
            return True
        except Exception:
            return False
