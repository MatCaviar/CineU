from __future__ import annotations

import csv
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

import imageio.v2 as imageio
import numpy
from PIL import Image, ImageDraw, ImageFont


def _safe_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return token.strip("._") or "item"


def _movie_frames(frame_dir: Path) -> list[Path]:
    return sorted(frame_dir.glob("movie_frame_*.png"))


def _windows_long_path(path: Path) -> str:
    value = str(path)
    if os.name != "nt" or value.startswith("\\\\?\\") or len(value) < 248:
        return value
    if value.startswith("\\\\"):
        return "\\\\?\\UNC\\" + value[2:]
    return "\\\\?\\" + value


def _compact_camera_token(camera_token: str, job_index: int) -> str:
    token = _safe_token(camera_token)
    replacements = [
        ("CineU_", ""),
        ("car_dealer", "cd"),
        ("warehouse", "wh"),
        ("surveillance", "surv"),
        ("first_person_walk", "fp"),
        ("top_down", "top"),
        ("original", "orig"),
        ("reverse", "rev"),
    ]
    for old, new in replacements:
        token = token.replace(old, new)
    token = re.sub(r"_+", "_", token).strip("_")
    if len(token) > 40:
        token = token[:40].rstrip("_")
    return token or f"v{int(job_index):03d}"


def _keyframe_file_name(job_index: int, frame_index: int, camera_token: str | None = None) -> str:
    prefix = _compact_camera_token(camera_token, job_index) if camera_token else f"v{int(job_index):03d}"
    return f"{prefix}_f{int(frame_index):04d}.png"


def _validate_mp4(path: Path, keyframes: list[int]) -> dict[str, Any]:
    reader = imageio.get_reader(_windows_long_path(path), format="FFMPEG")
    try:
        metadata = reader.get_meta_data()
        for index in keyframes:
            reader.get_data(index)
        return metadata
    finally:
        reader.close()


def _write_mp4(source_paths: list[Path], output_path: Path, fps: int) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(".encoding.mp4")
    if temp_path.exists():
        temp_path.unlink()
    if output_path.exists():
        output_path.unlink()
    with imageio.get_writer(
        str(temp_path),
        format="FFMPEG",
        fps=max(1, int(fps)),
        codec="libx264",
        quality=8,
        macro_block_size=1,
    ) as writer:
        for source in source_paths:
            with Image.open(_windows_long_path(source)) as image:
                writer.append_data(numpy.asarray(image.convert("RGB")))
    keyframes = sorted({0, len(source_paths) // 2, len(source_paths) - 1})
    metadata = _validate_mp4(temp_path, keyframes)
    os.replace(_windows_long_path(temp_path), _windows_long_path(output_path))
    return metadata


def _write_scene_manifest(scene_dir: Path, rows: list[dict[str, Any]]) -> None:
    scene = str(rows[0]["scene"])
    (scene_dir / f"{scene}_manifest.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    fieldnames = sorted({key for row in rows for key in row})
    with (scene_dir / f"{scene}_manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _short_label(value: str, limit: int = 34) -> str:
    return value if len(value) <= limit else value[: limit - 3] + "..."


def _write_contact_sheet(scene_dir: Path, scene: str, rows: list[dict[str, Any]]) -> Path:
    cell_width = 340
    cell_height = 220
    label_width = 270
    header_height = 34
    padding = 12
    thumb_max = (cell_width - padding * 2, cell_height - 44)
    font = ImageFont.load_default()
    rows = sorted(rows, key=lambda row: str(row.get("camera", "")))
    columns = max(len(row.get("keyframe_paths", [])) for row in rows)
    width = label_width + columns * cell_width + padding * 2
    height = header_height + len(rows) * cell_height + padding * 2
    sheet = Image.new("RGB", (width, height), (245, 245, 241))
    draw = ImageDraw.Draw(sheet)
    draw.text((padding, padding), scene, fill=(20, 20, 20), font=font)
    first_frames = str(rows[0].get("verified_keyframes_read", "")).split(",")
    for column in range(columns):
        label = first_frames[column] if column < len(first_frames) else str(column + 1)
        x = label_width + column * cell_width + padding
        draw.text((x, padding), f"frame {label}", fill=(45, 45, 45), font=font)

    resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
    for row_index, row in enumerate(rows):
        y = header_height + padding + row_index * cell_height
        draw.rectangle((padding, y, width - padding, y + cell_height - padding), outline=(210, 210, 204))
        label = _short_label(str(row.get("camera_name") or row.get("camera") or "camera"))
        draw.text((padding * 2, y + padding), label, fill=(20, 20, 20), font=font)
        draw.text((padding * 2, y + padding + 18), str(row.get("camera_type", "")), fill=(80, 80, 80), font=font)
        for column, keyframe_path in enumerate(row.get("keyframe_paths", [])):
            x = label_width + column * cell_width + padding
            frame_box = (x, y + padding + 20, x + cell_width - padding, y + cell_height - padding)
            draw.rectangle(frame_box, fill=(30, 32, 34))
            with Image.open(_windows_long_path(keyframe_path)) as frame:
                thumb = frame.convert("RGB")
                thumb.thumbnail(thumb_max, resample)
                paste_x = frame_box[0] + ((frame_box[2] - frame_box[0]) - thumb.width) // 2
                paste_y = frame_box[1] + ((frame_box[3] - frame_box[1]) - thumb.height) // 2
                sheet.paste(thumb, (paste_x, paste_y))

    output_path = scene_dir / f"{scene}_contact_sheet.jpg"
    sheet.save(_windows_long_path(output_path), quality=90)
    return output_path


def encode_hillside_render_batch(manifest_path: Path, output_root: Path) -> dict[str, Any]:
    """Encode completed Hillside render batch movie_frames into per-scene mp4 manifests."""
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8-sig"))
    jobs = [dict(job) for job in manifest.get("jobs", [])]
    if not jobs:
        raise ValueError(f"No jobs found in render batch manifest: {manifest_path}")
    output_root.mkdir(parents=True, exist_ok=True)

    scene_rows: dict[str, list[dict[str, Any]]] = {}
    for job_index, job in enumerate(jobs, start=1):
        scene = str(job["scene"])
        source_dir = Path(str(job["output_dir"]))
        frame_dir = source_dir / "movie_frames"
        frames = _movie_frames(frame_dir)
        expected_frames = int(job["frame_count"])
        if len(frames) != expected_frames:
            raise ValueError(f"{source_dir} has {len(frames)} movie frames, expected {expected_frames}")
        fps = int(job.get("fps") or 24)
        scene_dir = output_root / scene
        keyframe_dir = scene_dir / "keyframes"
        keyframe_dir.mkdir(parents=True, exist_ok=True)
        camera_token = _safe_token(str(job["camera_name"]))
        mp4_path = scene_dir / f"{scene}_{camera_token}_sync{expected_frames}f.mp4"
        metadata = _write_mp4(frames, mp4_path, fps)
        expected_resolution = [int(value) for value in job.get("resolution", [])]
        metadata_size = [int(value) for value in metadata.get("size", [])]
        keyframes = sorted({0, expected_frames // 2, expected_frames - 1})
        keyframe_paths = []
        for index in keyframes:
            keyframe_path = keyframe_dir / _keyframe_file_name(job_index, index, camera_token)
            shutil.copy2(_windows_long_path(frames[index]), _windows_long_path(keyframe_path))
            keyframe_paths.append(str(keyframe_path))
        row = {
            "scene": scene,
            "shot_id": str(job.get("shot_id", "")),
            "camera": camera_token,
            "camera_name": str(job["camera_name"]),
            "camera_type": str(job.get("camera_type", "")),
            "source_dir": str(source_dir),
            "source_frame_dir": str(frame_dir),
            "frame_count": expected_frames,
            "fps": fps,
            "expected_duration_sec": expected_frames / float(fps),
            "mp4": str(mp4_path),
            "mp4_bytes": mp4_path.stat().st_size,
            "metadata_fps": metadata.get("fps"),
            "metadata_duration": metadata.get("duration"),
            "expected_width": expected_resolution[0] if len(expected_resolution) == 2 else None,
            "expected_height": expected_resolution[1] if len(expected_resolution) == 2 else None,
            "metadata_width": metadata_size[0] if len(metadata_size) == 2 else None,
            "metadata_height": metadata_size[1] if len(metadata_size) == 2 else None,
            "verified_keyframes_read": ",".join(str(index) for index in keyframes),
            "keyframe_paths": keyframe_paths,
        }
        scene_rows.setdefault(scene, []).append(row)

    contact_sheets = []
    for scene, rows in scene_rows.items():
        contact_sheet = _write_contact_sheet(output_root / scene, scene, rows)
        for row in rows:
            row["contact_sheet"] = str(contact_sheet)
        contact_sheets.append(str(contact_sheet))
        _write_scene_manifest(output_root / scene, rows)
    return {
        "output_root": str(output_root),
        "scene_dirs": [str(output_root / scene) for scene in scene_rows],
        "video_count": sum(len(rows) for rows in scene_rows.values()),
        "scenes": sorted(scene_rows),
        "contact_sheets": contact_sheets,
    }
