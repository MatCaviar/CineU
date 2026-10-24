from __future__ import annotations

import json
import importlib
from pathlib import Path
from typing import Any

from PIL import Image, ImageStat

from .schemas import Operation, VerificationCheck, VerificationReport


_MIN_RENDER_IMAGE_BYTES = 128
_MIN_RENDER_VIDEO_BYTES = 1024


def _image_artifact_status(path: Path) -> tuple[bool, dict[str, Any], str]:
    size = path.stat().st_size if path.exists() else 0
    details: dict[str, Any] = {"path": str(path), "bytes": size}
    if size <= _MIN_RENDER_IMAGE_BYTES:
        return False, details, "image artifact is too small"
    if path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        return True, details, ""
    try:
        with Image.open(path) as opened:
            details["size"] = list(opened.size)
            image = opened.convert("RGB")
            thumb = image.resize((min(160, image.width), min(90, image.height)))
            stat = ImageStat.Stat(thumb)
    except Exception as exc:  # noqa: BLE001
        return False, details, f"image artifact is not decodable: {exc}"
    mean = stat.mean
    stddev = stat.stddev
    luma = 0.2126 * mean[0] + 0.7152 * mean[1] + 0.0722 * mean[2]
    details["luma"] = luma
    details["stddev"] = stddev
    if luma < 3.0 and max(stddev) < 3.0:
        return False, details, "image artifact is blank or black"
    return True, details, ""


def _video_artifact_metadata(path: Path) -> tuple[bool, dict[str, Any], str]:
    try:
        imageio = importlib.import_module("imageio.v2")
        reader = imageio.get_reader(str(path), format="FFMPEG")
    except Exception as exc:  # noqa: BLE001
        return False, {}, f"video artifact is not decodable: {exc}"
    try:
        meta = reader.get_meta_data()
        try:
            frame_count: Any = reader.count_frames()
        except Exception:
            frame_count = meta.get("nframes")
        size = meta.get("size")
        fps = meta.get("fps")
        ok = bool(size and fps and (frame_count is None or frame_count == float("inf") or int(frame_count) > 0))
        details = {"size": size, "fps": fps, "duration": meta.get("duration"), "frame_count": frame_count}
        return ok, details, "" if ok else "video artifact is not decodable"
    except Exception as exc:  # noqa: BLE001
        return False, {}, f"video artifact is not decodable: {exc}"
    finally:
        try:
            reader.close()
        except Exception:
            pass


def _actor_exists(state: dict[str, Any], name: str) -> bool:
    return name in state.get("actors", {})


def _sequence(state: dict[str, Any], path: str) -> dict[str, Any] | None:
    return state.get("sequences", {}).get(path)


def _aabb(actor: dict[str, Any]) -> tuple[list[float], list[float]] | None:
    transform = actor.get("transform") or {}
    loc = transform.get("location")
    extent = actor.get("bounds_extent")
    if not loc or not extent:
        return None
    return [float(x) for x in loc], [float(x) for x in extent]


def _is_planned_collision_actor(actor: dict[str, Any]) -> bool:
    if actor.get("asset_type") == "camera":
        return False
    return bool(actor.get("asset_id") or actor.get("semantic_type"))


def _intersects(a: tuple[list[float], list[float]], b: tuple[list[float], list[float]]) -> bool:
    ca, ea = a
    cb, eb = b
    return all(abs(ca[i] - cb[i]) <= ea[i] + eb[i] for i in range(3))


def _support_surface_ground_z(state: dict[str, Any], target: str | None) -> float:
    if not target:
        return 0.0
    surface = state.get("support_surfaces", {}).get(target, {})
    if not isinstance(surface, dict):
        return 0.0
    try:
        return float(surface.get("z", 0.0))
    except (TypeError, ValueError):
        return 0.0


class StateVerifier:
    def verify(self, op: Operation, state: dict[str, Any]) -> VerificationReport:
        checks: list[VerificationCheck] = []
        expected = op.expected or {}

        if expected.get("level_exists"):
            checks.append(VerificationCheck(name="level_exists", passed=bool(state.get("level")), actual=state.get("level")))
        if "support_surfaces_min" in expected:
            actual = len(state.get("support_surfaces", {}))
            checks.append(VerificationCheck(name="support_surfaces_min", passed=actual >= expected["support_surfaces_min"], expected=expected["support_surfaces_min"], actual=actual))
        if "actors_exist" in expected:
            for actor in expected["actors_exist"]:
                checks.append(VerificationCheck(name=f"actor_exists:{actor}", passed=_actor_exists(state, actor)))
        if "assets_imported" in expected:
            imports = state.get("asset_imports", {})
            for asset_id in expected["assets_imported"]:
                record = imports.get(asset_id, {})
                passed = bool(record.get("ue_path")) and record.get("status") in {"imported", "available", "already_exists"}
                checks.append(VerificationCheck(name=f"asset_imported:{asset_id}", passed=passed, actual=record))
        if "actors_transformed" in expected:
            for actor in expected["actors_transformed"]:
                data = state.get("actors", {}).get(actor, {})
                loc = data.get("transform", {}).get("location")
                checks.append(VerificationCheck(name=f"actor_transformed:{actor}", passed=loc is not None, actual=loc))
        if "relations" in expected:
            for rel in expected["relations"]:
                actor = rel["actor"]
                actor_state = state.get("actors", {}).get(actor, {})
                loc = actor_state.get("transform", {}).get("location", [0, 0, 0])
                extent = actor_state.get("bounds_extent", [0, 0, 0])
                if rel["relation"] == "on_ground":
                    ground_z = _support_surface_ground_z(state, rel.get("target"))
                    expected_z = ground_z if str(actor_state.get("asset_type", "")).lower() == "skeletal_mesh" else ground_z + float(extent[2])
                    passed = abs(float(loc[2]) - expected_z) <= 1e-3
                    checks.append(VerificationCheck(name=f"relation_on_ground:{actor}", passed=passed, expected=expected_z, actual=loc[2]))
                elif rel["relation"] == "on_wall":
                    tolerance = max(80.0, float(extent[0]) + 1.0)
                    if rel.get("target") == "back_wall":
                        passed = abs(float(loc[1]) - 500.0) <= tolerance
                    elif rel.get("target") in {"left_wall", "right_wall"}:
                        passed = abs(abs(float(loc[0])) - 500.0) <= tolerance
                    else:
                        passed = abs(abs(float(loc[0])) - 500.0) <= tolerance or abs(float(loc[1]) - 500.0) <= tolerance
                    checks.append(VerificationCheck(name=f"relation_on_wall:{actor}", passed=passed, actual=loc))
        if expected.get("no_actor_overlap"):
            checks.append(self._verify_no_actor_overlap(state))
        if "sequence_exists" in expected:
            seq = _sequence(state, expected["sequence_exists"])
            checks.append(VerificationCheck(name="sequence_exists", passed=seq is not None, actual=expected["sequence_exists"]))
            if seq and "sequence_range" in expected:
                checks.append(VerificationCheck(name="sequence_range", passed=seq.get("range") == expected["sequence_range"], expected=expected["sequence_range"], actual=seq.get("range")))
            if seq and "fps" in expected:
                checks.append(VerificationCheck(name="sequence_fps", passed=seq.get("fps") == expected["fps"], expected=expected["fps"], actual=seq.get("fps")))
        if "cameras_exist" in expected:
            for cam in expected["cameras_exist"]:
                checks.append(VerificationCheck(name=f"camera_exists:{cam}", passed=_actor_exists(state, cam)))
        if "camera_transform_keys_min" in expected:
            for cam, min_count in expected["camera_transform_keys_min"].items():
                actual = self._camera_key_count(state, cam, "transform_keys")
                checks.append(VerificationCheck(name=f"camera_transform_keys:{cam}", passed=actual >= min_count, expected=min_count, actual=actual))
        if "focal_length_keys_min" in expected:
            for cam, min_count in expected["focal_length_keys_min"].items():
                actual = self._camera_key_count(state, cam, "focal_length_keys")
                checks.append(VerificationCheck(name=f"focal_length_keys:{cam}", passed=actual >= min_count, expected=min_count, actual=actual))
        if "camera_key_range" in expected:
            for cam, frame_range in expected["camera_key_range"].items():
                actual = self._camera_key_range(state, cam)
                checks.append(VerificationCheck(name=f"camera_key_range:{cam}", passed=actual == frame_range, expected=frame_range, actual=actual))
        if "hitchcock_zoom_coupling" in expected:
            for cam, cfg in expected["hitchcock_zoom_coupling"].items():
                checks.append(self._verify_hitchcock_coupling(state, cam, float(cfg.get("max_relative_error", 1e-6))))
        if expected.get("camera_cut_no_gaps"):
            checks.extend(self._verify_camera_cuts(state))
        if "camera_cut_count" in expected:
            actual = sum(len(seq.get("camera_cuts", [])) for seq in state.get("sequences", {}).values())
            checks.append(VerificationCheck(name="camera_cut_count", passed=actual == expected["camera_cut_count"], expected=expected["camera_cut_count"], actual=actual))
        if "transform_tracks" in expected:
            for actor in expected["transform_tracks"]:
                actual = self._transform_track_exists(state, actor)
                checks.append(VerificationCheck(name=f"transform_track:{actor}", passed=actual))
        if "animation_tracks" in expected:
            for actor in expected["animation_tracks"]:
                actual = self._animation_track_exists(state, actor)
                checks.append(VerificationCheck(name=f"animation_track:{actor}", passed=actual))
        if "motion_alignment" in expected:
            checks.extend(self._verify_motion_alignment(state, expected["motion_alignment"]))
        if "render_artifacts_exist" in expected:
            artifacts = state.get("renders", [])[-1].get("artifacts", {}) if state.get("renders") else {}
            for name in expected["render_artifacts_exist"]:
                artifact_value = artifacts.get(name)
                artifact_path = Path(artifact_value) if artifact_value else None
                exists = artifact_path is not None and artifact_path.exists()
                passed = exists
                actual: Any = artifact_value
                message = ""
                if exists and artifact_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif"}:
                    passed, actual, message = _image_artifact_status(artifact_path)
                elif exists and artifact_path.suffix.lower() in {".mp4", ".mov", ".avi"}:
                    size = artifact_path.stat().st_size
                    passed = size > _MIN_RENDER_VIDEO_BYTES
                    actual = {"path": str(artifact_path), "bytes": size}
                    message = "" if passed else "video artifact is too small"
                    if passed:
                        decodable, metadata, decode_message = _video_artifact_metadata(artifact_path)
                        passed = decodable
                        actual.update(metadata)
                        message = decode_message
                checks.append(VerificationCheck(name=f"render_artifact:{name}", passed=passed, actual=actual, message=message))
                if name == "storyboard_manifest.json" and exists:
                    checks.extend(self._verify_storyboard_manifest(artifact_path))
        if expected.get("render_preview_camera_required"):
            render = state.get("renders", [])[-1] if state.get("renders") else {}
            preview_camera = render.get("preview_camera")
            checks.append(VerificationCheck(name="render_preview_camera", passed=bool(preview_camera), actual=preview_camera))

        passed = all(c.passed for c in checks)
        diagnostics = {} if passed else {"error_type": "STATE_VERIFICATION_FAILED", "failed_checks": [c.model_dump(mode="json") for c in checks if not c.passed]}
        return VerificationReport(op_id=op.op_id, stage="state", passed=passed, checks=checks, diagnostics=diagnostics)

    def _camera_key_count(self, state: dict[str, Any], camera_name: str, key_name: str) -> int:
        for seq in state.get("sequences", {}).values():
            cam = seq.get("cameras", {}).get(camera_name)
            if cam:
                return len(cam.get(key_name, []))
        return 0

    def _camera_key_range(self, state: dict[str, Any], camera_name: str) -> list[int] | None:
        for seq in state.get("sequences", {}).values():
            cam = seq.get("cameras", {}).get(camera_name)
            if cam:
                keys = cam.get("transform_keys", [])
                if not keys:
                    return None
                return [keys[0]["frame"], keys[-1]["frame"]]
        return None

    def _transform_track_exists(self, state: dict[str, Any], actor: str) -> bool:
        for seq in state.get("sequences", {}).values():
            if actor in seq.get("transform_tracks", {}):
                return True
        return False

    def _animation_track_exists(self, state: dict[str, Any], actor: str) -> bool:
        for seq in state.get("sequences", {}).values():
            if actor in seq.get("animation_tracks", {}):
                return True
        return False

    def _verify_motion_alignment(self, state: dict[str, Any], alignments: list[dict[str, Any]]) -> list[VerificationCheck]:
        checks: list[VerificationCheck] = []
        for item in alignments:
            actor = item["actor"]
            expected_range = [item["start_frame"], item["end_frame"]]
            for path, seq in state.get("sequences", {}).items():
                transform = seq.get("transform_tracks", {}).get(actor)
                animation = seq.get("animation_tracks", {}).get(actor)
                if transform:
                    checks.append(VerificationCheck(name=f"motion_transform_range:{actor}", passed=[transform.get("start_frame"), transform.get("end_frame")] == expected_range, expected=expected_range, actual=[transform.get("start_frame"), transform.get("end_frame")]))
                if animation:
                    checks.append(VerificationCheck(name=f"motion_animation_range:{actor}", passed=[animation.get("start_frame"), animation.get("end_frame")] == expected_range, expected=expected_range, actual=[animation.get("start_frame"), animation.get("end_frame")]))
        return checks

    def _verify_hitchcock_coupling(self, state: dict[str, Any], camera_name: str, tolerance: float) -> VerificationCheck:
        for seq in state.get("sequences", {}).values():
            cam = seq.get("cameras", {}).get(camera_name)
            if not cam:
                continue
            focal = cam.get("focal_length_keys", [])
            focus = cam.get("focus_distance_keys", [])
            if len(focal) < 2 or len(focus) < 2:
                return VerificationCheck(name=f"hitchcock_coupling:{camera_name}", passed=False, actual={"focal": len(focal), "focus": len(focus)})
            ratios = [float(f["focal_length"]) / float(d["focus_distance"]) for f, d in zip(focal, focus) if d.get("focus_distance")]
            if not ratios:
                return VerificationCheck(name=f"hitchcock_coupling:{camera_name}", passed=False, actual="missing_focus_distance")
            base = ratios[0]
            max_error = max(abs(r - base) / max(abs(base), 1e-9) for r in ratios)
            return VerificationCheck(name=f"hitchcock_coupling:{camera_name}", passed=max_error <= tolerance, expected=f"<= {tolerance}", actual=max_error)
        return VerificationCheck(name=f"hitchcock_coupling:{camera_name}", passed=False, actual="camera_missing")

    def _verify_camera_cuts(self, state: dict[str, Any]) -> list[VerificationCheck]:
        checks: list[VerificationCheck] = []
        for path, seq in state.get("sequences", {}).items():
            cuts = sorted(seq.get("camera_cuts", []), key=lambda c: c["start_frame"])
            if not cuts:
                checks.append(VerificationCheck(name=f"camera_cuts_exist:{path}", passed=False))
                continue
            expected_start = seq.get("range", [0, 0])[0]
            end = seq.get("range", [0, 0])[1]
            gap = False
            overlap = False
            cursor = expected_start
            for cut in cuts:
                if cut["start_frame"] > cursor:
                    gap = True
                if cut["start_frame"] < cursor:
                    overlap = True
                cursor = max(cursor, cut["end_frame"])
            if cursor < end:
                gap = True
            checks.append(VerificationCheck(name=f"camera_cut_no_gap:{path}", passed=not gap, actual=cuts))
            checks.append(VerificationCheck(name=f"camera_cut_no_overlap:{path}", passed=not overlap, actual=cuts))
        return checks

    def _verify_storyboard_manifest(self, manifest_path: Path) -> list[VerificationCheck]:
        checks: list[VerificationCheck] = []
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return [VerificationCheck(name="storyboard_manifest_parse", passed=False, actual=str(exc))]
        frames = manifest.get("frames", [])
        for index, frame in enumerate(frames):
            if not isinstance(frame, dict):
                checks.append(VerificationCheck(name=f"storyboard_frame_artifact:storyboard_{index:03d}.png", passed=False, actual="invalid_frame_record"))
                continue
            artifact_name = str(frame.get("artifact_name") or f"storyboard_{index:03d}.png")
            artifact_value = frame.get("artifact")
            artifact_path = Path(str(artifact_value)) if artifact_value else manifest_path.parent / artifact_name
            if not artifact_path.is_absolute():
                artifact_path = manifest_path.parent / artifact_path
            exists = artifact_path.exists()
            if exists:
                passed, actual, message = _image_artifact_status(artifact_path)
            else:
                passed, actual, message = False, {"path": str(artifact_path), "bytes": 0}, "storyboard image artifact is missing"
            checks.append(
                VerificationCheck(
                    name=f"storyboard_frame_artifact:{artifact_name}",
                    passed=passed,
                    actual=actual,
                    message=message.replace("image artifact", "storyboard image artifact"),
                )
            )
        return checks

    def _verify_no_actor_overlap(self, state: dict[str, Any]) -> VerificationCheck:
        actors = [(name, _aabb(actor)) for name, actor in state.get("actors", {}).items() if _is_planned_collision_actor(actor)]
        collisions: list[tuple[str, str]] = []
        valid = [(name, box) for name, box in actors if box is not None]
        for i, (name_a, box_a) in enumerate(valid):
            for name_b, box_b in valid[i + 1:]:
                if _intersects(box_a, box_b):
                    collisions.append((name_a, name_b))
        return VerificationCheck(name="no_actor_overlap", passed=not collisions, actual=collisions)
