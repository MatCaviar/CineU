from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import warnings
from pathlib import Path
from typing import Any, Iterable

import imageio.v2 as imageio
import imageio_ffmpeg
import numpy
from PIL import Image, ImageDraw, ImageFont

from .asset_first_scene_plan import build_hillside_scene_plan
from .paths import HILLSIDE_DIAGNOSTIC_ROOT


REPO_ROOT = Path(__file__).resolve().parents[1]
HILLSIDE_DIAG_ROOT = HILLSIDE_DIAGNOSTIC_ROOT


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _scene_manifest_path(scene_dir: Path) -> Path:
    preferred = scene_dir / f"{scene_dir.name}_manifest.json"
    if preferred.exists():
        return preferred
    candidates = sorted(scene_dir.glob("*_manifest.json"))
    for candidate in candidates:
        data = _read_json(candidate)
        if isinstance(data, list):
            return candidate
    raise FileNotFoundError(f"No scene manifest found in {scene_dir}")


def _manifest_rows(scene_dir: Path) -> list[dict[str, Any]]:
    data = _read_json(_scene_manifest_path(scene_dir))
    rows = data if isinstance(data, list) else [data]
    if not rows:
        raise ValueError(f"Empty scene manifest in {scene_dir}")
    return [dict(row) for row in rows]


def _validate_mp4(path: Path, keyframe_indexes: Iterable[int]) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size <= 1024:
        raise FileNotFoundError(f"Missing or tiny mp4: {path}")
    reader = imageio.get_reader(str(path), format="FFMPEG")
    try:
        meta = reader.get_meta_data()
        for index in keyframe_indexes:
            reader.get_data(int(index))
        return {"fps": meta.get("fps"), "duration": meta.get("duration"), "size": meta.get("size")}
    finally:
        reader.close()


def _coerce_resolution(value: Any) -> list[int] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"Expected resolution must be [width, height], got {value!r}")
    width, height = int(value[0]), int(value[1])
    if width <= 0 or height <= 0:
        raise ValueError(f"Expected resolution must be positive, got {value!r}")
    return [width, height]


def _metadata_resolution(metadata: dict[str, Any]) -> list[int]:
    size = metadata.get("size") or []
    if not isinstance(size, (list, tuple)) or len(size) != 2:
        raise ValueError(f"Cannot read mp4 resolution from metadata: {metadata}")
    return [int(size[0]), int(size[1])]


def _validate_expected_video_metadata(
    source: Path,
    metadata: dict[str, Any],
    *,
    expected_fps: float,
    expected_duration_sec: float,
    expected_resolution: list[int] | None,
) -> tuple[float, float, list[int]]:
    fps = float(metadata.get("fps") or 0.0)
    duration = float(metadata.get("duration") or 0.0)
    resolution = _metadata_resolution(metadata)
    if abs(fps - expected_fps) > 0.01:
        raise ValueError(f"{source} fps {fps} != expected {expected_fps}")
    if abs(duration - expected_duration_sec) > 0.05:
        raise ValueError(f"{source} duration {duration} != expected {expected_duration_sec}")
    if expected_resolution is not None and resolution != expected_resolution:
        raise ValueError(f"{source} resolution {resolution} != expected {expected_resolution}")
    return fps, duration, resolution


def _link_or_copy(source: Path, dest: Path) -> str:
    if dest.exists():
        dest.unlink()
    try:
        os.link(source, dest)
        return "hardlink"
    except OSError:
        shutil.copy2(source, dest)
        return "copy"


def _safe_file_token(value: object) -> str:
    token = _normalize_camera_token(value).replace(" ", "_")
    keep = []
    for char in token:
        keep.append(char if char.isalnum() or char in "._-" else "_")
    return "".join(keep).strip("._") or "video"


def _normalize_camera_token(value: object) -> str:
    token = str(value or "").strip()
    if token.startswith("CineU_"):
        token = token[len("CineU_") :]
    return token


def _run_ffmpeg_stabilize(
    source: Path,
    dest: Path,
    *,
    stable_start_frame: int,
    output_frame_count: int,
    fps: float,
) -> None:
    if dest.exists():
        dest.unlink()
    dest.parent.mkdir(parents=True, exist_ok=True)
    remaining_frames = max(1, output_frame_count - int(stable_start_frame))
    stretch = float(output_frame_count) / float(remaining_frames)
    vf = f"trim=start_frame={int(stable_start_frame)},setpts={stretch:.12f}*(PTS-STARTPTS),fps=fps={float(fps):.6f},format=yuv420p"
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source),
        "-vf",
        vf,
        "-an",
        "-frames:v",
        str(int(output_frame_count)),
        "-c:v",
        "libx264",
        "-crf",
        "18",
        "-preset",
        "medium",
        "-movflags",
        "+faststart",
        str(dest),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg stabilize failed for {source}: {result.stderr.strip()}")


def _close_values(left: list[float], right: list[float], tolerance: float = 1.0) -> bool:
    return len(left) == len(right) and all(abs(float(a) - float(b)) <= tolerance for a, b in zip(left, right))


def _current_hillside_plan(scene: str) -> dict[str, Any]:
    inventory = _read_json(HILLSIDE_DIAG_ROOT / "asset_inventory.json")
    skeletons = _read_json(HILLSIDE_DIAG_ROOT / "character_skeletons.json")
    return build_hillside_scene_plan(scene, inventory, skeletons)


def _matching_plan_shot(plan: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    wanted = {
        _normalize_camera_token(row.get("camera")),
        _normalize_camera_token(row.get("camera_name")),
        _normalize_camera_token(row.get("shot_id")),
    }
    for shot in plan["shots"]:
        candidates = {
            _normalize_camera_token(shot.get("camera_name")),
            _normalize_camera_token(shot.get("shot_id")),
            _normalize_camera_token(shot.get("type")),
        }
        if wanted & candidates:
            return dict(shot)
    raise ValueError(f"No current {plan['scene_id']} plan shot matches review row camera={row.get('camera')!r}")


def _source_world_state(row: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    source_candidates = []
    if row.get("source_dir"):
        source_dir = Path(str(row["source_dir"]))
        source_candidates.append(source_dir / "world_state_for_render.json")
    if row.get("source_path"):
        source_path = Path(str(row["source_path"]))
        source_candidates.append(source_path / "world_state_for_render.json")
        source_candidates.append(source_path.parent / "world_state_for_render.json")
    if row.get("source_mp4"):
        source_mp4_path = Path(str(row["source_mp4"]))
        source_candidates.append(source_mp4_path.parent / "world_state_for_render.json")
    if row.get("mp4"):
        mp4_path = Path(str(row["mp4"]))
        source_candidates.append(mp4_path.parent / "world_state_for_render.json")
    state_path = next((candidate for candidate in source_candidates if candidate.exists()), source_candidates[0])
    if not state_path.exists():
        raise ValueError(f"Cannot validate source world state because it is missing: {state_path}")
    return state_path, _read_json(state_path)


def _source_camera_state(row: dict[str, Any], state_path: Path, state: dict[str, Any]) -> dict[str, Any]:
    sequence = next(iter(state.get("sequences", {}).values()), {})
    cameras = sequence.get("cameras", {})
    if len(cameras) == 1:
        return dict(next(iter(cameras.values())))
    wanted = {
        _normalize_camera_token(row.get("camera")),
        _normalize_camera_token(row.get("camera_name")),
        _normalize_camera_token(row.get("shot_id")),
    }
    for name, camera in cameras.items():
        if _normalize_camera_token(name) in wanted:
            return dict(camera)
    raise ValueError(f"No source world_state camera matches review row camera={row.get('camera')!r} in {state_path}")


def _validate_source_support_props(
    scene: str,
    row: dict[str, Any],
    plan: dict[str, Any],
    state_path: Path,
    state: dict[str, Any],
) -> None:
    expected_props = list(plan.get("support_props") or [])
    if not expected_props:
        return
    sequence = next(iter(state.get("sequences", {}).values()), {})
    source_props = sequence.get("support_props") or {}
    if not isinstance(source_props, dict):
        raise ValueError(f"Source support props for {scene} {row.get('camera')} are malformed in {state_path}")
    for expected in expected_props:
        actor_name = str(expected["actor_name"])
        actual = source_props.get(actor_name)
        if not actual:
            raise ValueError(
                f"Source does not match current {scene} plan: support prop {actor_name} "
                f"is missing in {state_path}"
            )
        if str(actual.get("mesh_path") or "") != str(expected.get("mesh_path") or ""):
            raise ValueError(
                f"Source does not match current {scene} plan: support prop {actor_name} "
                f"mesh_path={actual.get('mesh_path')!r} expected_mesh_path={expected.get('mesh_path')!r}"
            )
        if str(actual.get("role") or "") != str(expected.get("role") or ""):
            raise ValueError(
                f"Source does not match current {scene} plan: support prop {actor_name} "
                f"role={actual.get('role')!r} expected_role={expected.get('role')!r}"
            )
        if not _close_values([float(value) for value in actual.get("location", [])], [float(value) for value in expected["location"]]):
            raise ValueError(
                f"Source does not match current {scene} plan: support prop {actor_name} "
                f"location={actual.get('location')} expected_location={expected['location']}"
            )
        if not _close_values([float(value) for value in actual.get("rotation", [])], [float(value) for value in expected["rotation"]], tolerance=0.1):
            raise ValueError(
                f"Source does not match current {scene} plan: support prop {actor_name} "
                f"rotation={actual.get('rotation')} expected_rotation={expected['rotation']}"
            )
        if abs(float(actual.get("scale", 0.0)) - float(expected["scale"])) > 0.01:
            raise ValueError(
                f"Source does not match current {scene} plan: support prop {actor_name} "
                f"scale={actual.get('scale')} expected_scale={expected['scale']}"
            )


def _validate_current_plan_source(row: dict[str, Any], plan_cache: dict[str, dict[str, Any]]) -> None:
    scene = str(row.get("scene") or "")
    plan = plan_cache.setdefault(scene, _current_hillside_plan(scene))
    shot = _matching_plan_shot(plan, row)
    state_path, state = _source_world_state(row)
    _validate_source_support_props(scene, row, plan, state_path, state)
    source_camera = _source_camera_state(row, state_path, state)
    keys = list(source_camera.get("transform_keys") or [])
    if len(keys) < 2:
        raise ValueError(f"Source camera state for {scene} {row.get('camera')} has fewer than 2 transform keys")
    expected_start = [float(value) for value in shot["location"]]
    expected_end = [float(value) for value in shot.get("end_location", shot["location"])]
    actual_start = [float(value) for value in keys[0]["location"]]
    actual_end = [float(value) for value in keys[-1]["location"]]
    expected_focal = float(shot["focal_length"])
    focal_keys = list(source_camera.get("focal_length_keys") or [])
    actual_focal = float(focal_keys[0]["focal_length"]) if focal_keys else expected_focal
    expected_start_rotation = [float(value) for value in shot.get("rotation", [])]
    expected_end_rotation = [float(value) for value in shot.get("end_rotation", expected_start_rotation)]
    actual_start_rotation = [float(value) for value in keys[0].get("rotation", [])]
    actual_end_rotation = [float(value) for value in keys[-1].get("rotation", [])]
    rotation_matches = True
    if expected_start_rotation:
        rotation_matches = _close_values(actual_start_rotation, expected_start_rotation, tolerance=0.1) and _close_values(
            actual_end_rotation,
            expected_end_rotation,
            tolerance=0.1,
        )
    if (
        not _close_values(actual_start, expected_start)
        or not _close_values(actual_end, expected_end)
        or abs(actual_focal - expected_focal) > 0.01
        or not rotation_matches
    ):
        raise ValueError(
            f"Source camera {row.get('camera')} does not match current {scene} plan: "
            f"start={actual_start} expected_start={expected_start}; "
            f"end={actual_end} expected_end={expected_end}; focal={actual_focal} expected_focal={expected_focal}; "
            f"rotation={actual_start_rotation}->{actual_end_rotation} expected_rotation={expected_start_rotation}->{expected_end_rotation}"
        )


def _short_label(value: str, limit: int = 34) -> str:
    return value if len(value) <= limit else value[: limit - 3] + "..."


def _write_review_contact_sheet(
    scene: str,
    rows: list[dict[str, Any]],
    output_dir: Path,
    keyframes: list[int],
) -> Path:
    contact_dir = output_dir / "contact_sheets"
    contact_dir.mkdir(parents=True, exist_ok=True)
    cell_width = 340
    cell_height = 220
    label_width = 270
    header_height = 34
    padding = 12
    thumb_max = (cell_width - padding * 2, cell_height - 44)
    font = ImageFont.load_default()
    ordered_rows = sorted(rows, key=lambda row: str(row.get("camera_name") or row.get("camera") or ""))
    width = label_width + len(keyframes) * cell_width + padding * 2
    height = header_height + len(ordered_rows) * cell_height + padding * 2
    sheet = Image.new("RGB", (width, height), (245, 245, 241))
    draw = ImageDraw.Draw(sheet)
    draw.text((padding, padding), scene, fill=(20, 20, 20), font=font)
    for column, frame_index in enumerate(keyframes):
        x = label_width + column * cell_width + padding
        draw.text((x, padding), f"frame {frame_index}", fill=(45, 45, 45), font=font)

    resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
    for row_index, row in enumerate(ordered_rows):
        y = header_height + padding + row_index * cell_height
        draw.rectangle((padding, y, width - padding, y + cell_height - padding), outline=(210, 210, 204))
        label = _short_label(str(row.get("camera_name") or row.get("camera") or "camera"))
        draw.text((padding * 2, y + padding), label, fill=(20, 20, 20), font=font)
        draw.text((padding * 2, y + padding + 18), str(row.get("camera_type", "")), fill=(80, 80, 80), font=font)
        reader = imageio.get_reader(str(row["flat_review_video"]), format="FFMPEG")
        try:
            for column, frame_index in enumerate(keyframes):
                x = label_width + column * cell_width + padding
                frame_box = (x, y + padding + 20, x + cell_width - padding, y + cell_height - padding)
                draw.rectangle(frame_box, fill=(30, 32, 34))
                frame = Image.fromarray(reader.get_data(frame_index)).convert("RGB")
                frame.thumbnail(thumb_max, resample)
                paste_x = frame_box[0] + ((frame_box[2] - frame_box[0]) - frame.width) // 2
                paste_y = frame_box[1] + ((frame_box[3] - frame_box[1]) - frame.height) // 2
                sheet.paste(frame, (paste_x, paste_y))
        finally:
            reader.close()

    output_path = contact_dir / f"{scene}_review_contact_sheet.jpg"
    sheet.save(output_path, quality=90)
    return output_path


def _write_review_package_files(
    output_dir: Path,
    flat_dir: Path,
    packaged: list[dict[str, Any]],
    scene_rows: dict[str, list[dict[str, Any]]],
    scenes: list[str],
    keyframes: list[int],
    readme: str,
) -> list[str]:
    contact_sheets = []
    for scene in scenes:
        contact_sheet = _write_review_contact_sheet(scene, scene_rows[scene], output_dir, keyframes)
        contact_sheets.append(str(contact_sheet))
        for row in scene_rows[scene]:
            row["contact_sheet"] = str(contact_sheet)

    fieldnames = sorted({key for row in packaged for key in row})
    with (output_dir / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(packaged)
    (output_dir / "manifest.json").write_text(json.dumps(packaged, indent=2, ensure_ascii=False), encoding="utf-8")
    (output_dir / "README.txt").write_text(readme, encoding="utf-8")
    return contact_sheets


def _frame_quality(frame: numpy.ndarray) -> dict[str, float]:
    rgb = numpy.asarray(frame, dtype=numpy.float32)
    luminance = rgb[:, :, 0] * 0.2126 + rgb[:, :, 1] * 0.7152 + rgb[:, :, 2] * 0.0722
    return {
        "mean_luminance": float(luminance.mean()),
        "p95_luminance": float(numpy.percentile(luminance, 95)),
        "bright_235_ratio": float((luminance >= 235.0).mean()),
        "highlight_245_ratio": float((luminance >= 245.0).mean()),
    }


def _video_quality_row(row: dict[str, Any], keyframes: list[int]) -> dict[str, Any]:
    last_frame = max(keyframes)
    sample_frames = sorted({0, min(24, last_frame), min(60, last_frame), min(120, last_frame), last_frame // 2, last_frame})
    reader = imageio.get_reader(str(row["mp4"]), format="FFMPEG")
    samples = []
    try:
        for frame_index in sample_frames:
            samples.append({"frame": frame_index, **_frame_quality(reader.get_data(frame_index))})
    finally:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            reader.close()
    first = samples[0]
    stable_candidates = [
        sample
        for sample in samples
        if sample["frame"] >= 60
        and sample["bright_235_ratio"] <= 0.05
        and sample["highlight_245_ratio"] <= 0.03
    ]
    quality_warnings = []
    suggested_stable_start_frame = None
    if (
        first["highlight_245_ratio"] >= 0.05
        or first["bright_235_ratio"] >= 0.10
        or first["p95_luminance"] >= 245.0
    ) and stable_candidates:
        quality_warnings.append("early_highlight_transient")
        suggested_stable_start_frame = int(stable_candidates[0]["frame"])
    return {
        "scene": row["scene"],
        "camera": row["camera"],
        "mp4": row["mp4"],
        "samples": samples,
        "warnings": quality_warnings,
        "suggested_stable_start_frame": suggested_stable_start_frame,
    }


def _write_quality_report(output_dir: Path, packaged: list[dict[str, Any]], keyframes: list[int]) -> Path:
    videos = [_video_quality_row(row, keyframes) for row in packaged]
    report = {
        "schema_version": "cineu.video_quality_report.v1",
        "sampled_frame_policy": "frames 0,24,60,120,mid,last clipped to video range",
        "videos": videos,
        "warning_counts": {
            "early_highlight_transient": sum("early_highlight_transient" in row["warnings"] for row in videos),
        },
    }
    path = output_dir / "quality_report.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _write_asset_first_evidence(
    output_dir: Path,
    packaged: list[dict[str, Any]],
    evidence: dict[str, Any] | None,
) -> Path | None:
    if not evidence:
        return None
    path = output_dir / "asset_first_evidence.json"
    path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
    scene_evidence = evidence.get("scenes", {}) if isinstance(evidence.get("scenes"), dict) else {}
    for row in packaged:
        row["asset_first_evidence_file"] = str(path)
        scene = str(row.get("scene") or "")
        scene_record = scene_evidence.get(scene, {}) if isinstance(scene_evidence.get(scene), dict) else {}
        environment = scene_record.get("environment_asset", {}) if isinstance(scene_record.get("environment_asset"), dict) else {}
        if environment.get("ue_path"):
            row["asset_first_scene_environment_asset"] = str(environment["ue_path"])
    return path


def package_multicamera_review(
    scene_dirs: Iterable[Path],
    output_dir: Path,
    *,
    expected_fps: float = 24.0,
    expected_duration_sec: float = 60.0,
    expected_resolution: Iterable[int] | None = None,
    keyframe_indexes: Iterable[int] = (0, 720, 1439),
    validate_current_plan: bool = False,
) -> dict[str, Any]:
    """Package validated per-camera scene videos into a flat review directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    flat_dir = output_dir / "videos_flat"
    flat_dir.mkdir(parents=True, exist_ok=True)
    keyframes = [int(index) for index in keyframe_indexes]
    required_resolution = _coerce_resolution(expected_resolution)

    packaged: list[dict[str, Any]] = []
    scene_rows: dict[str, list[dict[str, Any]]] = {}
    plan_cache: dict[str, dict[str, Any]] = {}
    scenes: list[str] = []
    for scene_dir in scene_dirs:
        scene_dir = Path(scene_dir)
        rows = _manifest_rows(scene_dir)
        scene = str(rows[0].get("scene") or scene_dir.name)
        scenes.append(scene)
        for row in rows:
            if validate_current_plan:
                _validate_current_plan_source(row, plan_cache)
            source = Path(str(row["mp4"]))
            metadata = _validate_mp4(source, keyframes)
            fps, duration, resolution = _validate_expected_video_metadata(
                source,
                metadata,
                expected_fps=expected_fps,
                expected_duration_sec=expected_duration_sec,
                expected_resolution=required_resolution,
            )
            dest = flat_dir / f"{scene}__{source.name}"
            link_type = _link_or_copy(source, dest)
            packaged_row = dict(row)
            packaged_row.update(
                {
                    "source_mp4": str(source),
                    "mp4": str(dest),
                    "flat_review_video": str(dest),
                    "flat_review_link_type": link_type,
                    "verified_metadata_fps": fps,
                    "verified_metadata_duration": duration,
                    "verified_metadata_width": resolution[0],
                    "verified_metadata_height": resolution[1],
                    "verified_keyframes_read": ",".join(str(index) for index in keyframes),
                    "source_current_plan_validated": bool(validate_current_plan),
                }
            )
            packaged.append(packaged_row)
            scene_rows.setdefault(scene, []).append(packaged_row)

    contact_sheets = _write_review_package_files(
        output_dir,
        flat_dir,
        packaged,
        scene_rows,
        scenes,
        keyframes,
        "Multicamera review package. videos_flat contains one mp4 per synchronized camera; "
        "manifest.json uses mp4 for the packaged review video and source_mp4 for the original source path.\n",
    )
    return {
        "output_dir": str(output_dir),
        "videos_flat": str(flat_dir),
        "video_count": len(packaged),
        "scenes": scenes,
        "expected_fps": float(expected_fps),
        "expected_duration_sec": float(expected_duration_sec),
        "expected_resolution": required_resolution,
        "contact_sheets": contact_sheets,
    }


def package_final_manifest_review(
    manifest_path: Path,
    output_dir: Path,
    *,
    expected_fps: float = 24.0,
    expected_duration_sec: float = 60.0,
    expected_resolution: Iterable[int] | None = None,
    keyframe_indexes: Iterable[int] = (0, 720, 1439),
    validate_current_plan: bool = False,
) -> dict[str, Any]:
    """Package a final candidate manifest with videos[] into a unified review directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    flat_dir = output_dir / "videos_flat"
    flat_dir.mkdir(parents=True, exist_ok=True)
    keyframes = [int(index) for index in keyframe_indexes]
    source_manifest = Path(manifest_path)
    data = _read_json(source_manifest)
    videos = [dict(video) for video in data.get("videos", [])]
    if not videos:
        raise ValueError(f"No videos found in final manifest: {source_manifest}")
    required_resolution = _coerce_resolution(expected_resolution or data.get("requirements", {}).get("resolution"))
    asset_first_evidence = data.get("asset_first_evidence") if isinstance(data.get("asset_first_evidence"), dict) else None

    packaged: list[dict[str, Any]] = []
    scene_rows: dict[str, list[dict[str, Any]]] = {}
    plan_cache: dict[str, dict[str, Any]] = {}
    scenes: list[str] = []
    for video in videos:
        scene = str(video.get("scene") or "").strip()
        if not scene:
            raise ValueError(f"Final manifest video is missing scene: {video}")
        if scene not in scene_rows:
            scenes.append(scene)
            scene_rows[scene] = []
        source = Path(str(video["path"]))
        metadata = _validate_mp4(source, keyframes)
        fps, duration, resolution = _validate_expected_video_metadata(
            source,
            metadata,
            expected_fps=expected_fps,
            expected_duration_sec=expected_duration_sec,
            expected_resolution=required_resolution,
        )
        dest = flat_dir / f"{scene}__{source.name}"
        link_type = _link_or_copy(source, dest)
        row = {
            "scene": scene,
            "camera": str(video.get("camera") or source.stem),
            "camera_name": str(video.get("camera") or source.stem),
            "camera_type": str(video.get("kind") or ""),
            "source_manifest": str(source_manifest),
            "source_path": str(video.get("source_path") or ""),
            "source_mp4": str(source),
            "mp4": str(dest),
            "flat_review_video": str(dest),
            "flat_review_link_type": link_type,
            "verified_metadata_fps": fps,
            "verified_metadata_duration": duration,
            "verified_metadata_width": resolution[0],
            "verified_metadata_height": resolution[1],
            "verified_keyframes_read": ",".join(str(index) for index in keyframes),
            "source_current_plan_validated": bool(validate_current_plan),
        }
        if validate_current_plan:
            _validate_current_plan_source(row, plan_cache)
        packaged.append(row)
        scene_rows[scene].append(row)

    asset_first_evidence_path = _write_asset_first_evidence(output_dir, packaged, asset_first_evidence)
    contact_sheets = _write_review_package_files(
        output_dir,
        flat_dir,
        packaged,
        scene_rows,
        scenes,
        keyframes,
        "Final manifest review package. videos_flat contains one mp4 per synchronized camera; "
        "manifest.json uses mp4 for the packaged review video and source_mp4 for the final-manifest source path.\n",
    )
    quality_report = _write_quality_report(output_dir, packaged, keyframes)
    summary = {
        "output_dir": str(output_dir),
        "videos_flat": str(flat_dir),
        "video_count": len(packaged),
        "scenes": scenes,
        "expected_fps": float(expected_fps),
        "expected_duration_sec": float(expected_duration_sec),
        "expected_resolution": required_resolution,
        "source_manifest": str(source_manifest),
        "contact_sheets": contact_sheets,
        "quality_report": str(quality_report),
    }
    if asset_first_evidence_path is not None:
        summary["asset_first_evidence"] = str(asset_first_evidence_path)
    return summary


def stabilize_final_manifest_from_quality_report(
    manifest_path: Path,
    quality_report_path: Path,
    output_dir: Path,
    *,
    expected_fps: float = 24.0,
    expected_duration_sec: float = 60.0,
    keyframe_indexes: Iterable[int] = (0, 720, 1439),
) -> dict[str, Any]:
    """Create a stabilized final review by re-timing videos flagged by quality_report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    stabilized_dir = output_dir / "stabilized_videos"
    stabilized_dir.mkdir(parents=True, exist_ok=True)
    source_manifest = Path(manifest_path)
    source_quality_report = Path(quality_report_path)
    manifest = _read_json(source_manifest)
    quality = _read_json(source_quality_report)
    stable_starts = {
        (str(row["scene"]), str(row["camera"])): int(row["suggested_stable_start_frame"])
        for row in quality.get("videos", [])
        if "early_highlight_transient" in row.get("warnings", [])
        and row.get("suggested_stable_start_frame") is not None
    }
    output_frame_count = int(round(float(expected_fps) * float(expected_duration_sec)))
    stabilized_videos = []
    reencoded_count = 0
    linked_count = 0
    for video in manifest.get("videos", []):
        scene = str(video["scene"])
        camera = str(video["camera"])
        source = Path(str(video["path"]))
        stable_start = int(stable_starts.get((scene, camera), 0))
        camera_token = _safe_file_token(camera)
        dest = stabilized_dir / f"{scene}__{camera_token}__stable_f{stable_start}.mp4"
        if stable_start > 0:
            _run_ffmpeg_stabilize(
                source,
                dest,
                stable_start_frame=stable_start,
                output_frame_count=output_frame_count,
                fps=expected_fps,
            )
            method = "ffmpeg_trim_stretch"
            reencoded_count += 1
        else:
            _link_or_copy(source, dest)
            method = "hardlink_or_copy"
            linked_count += 1
        stable_video = dict(video)
        stable_video.update(
            {
                "path": str(dest),
                "stabilized_from": str(source),
                "stable_start_frame": stable_start,
                "stabilization_method": method,
            }
        )
        stabilized_videos.append(stable_video)

    stabilized_manifest = {
        "schema_version": "cineu.final_manifest.stabilized.v1",
        "source_manifest": str(source_manifest),
        "source_quality_report": str(source_quality_report),
        "requirements": manifest.get("requirements", {}),
        "videos": stabilized_videos,
    }
    stabilized_manifest_path = output_dir / "stabilized_manifest.json"
    stabilized_manifest_path.write_text(json.dumps(stabilized_manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = package_final_manifest_review(
        stabilized_manifest_path,
        output_dir,
        expected_fps=expected_fps,
        expected_duration_sec=expected_duration_sec,
        keyframe_indexes=keyframe_indexes,
    )
    summary.update(
        {
            "stabilized_manifest": str(stabilized_manifest_path),
            "source_manifest": str(source_manifest),
            "source_quality_report": str(source_quality_report),
            "reencoded_video_count": reencoded_count,
            "linked_video_count": linked_count,
        }
    )
    return summary
