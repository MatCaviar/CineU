from __future__ import annotations

import json
import importlib
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageStat

from .environment_anchors import citypark_path_support_surface
from .ledger import atomic_write_json, read_json
from .schemas import ExecutionResult, Operation


_STORYBOARD_SAMPLES_PER_CUT = 9
_MAX_STORYBOARD_SAMPLES = 24


def initial_world_state() -> dict[str, Any]:
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


def _storyboard_frame_paths(storyboard_manifest: Path) -> list[Path]:
    if not storyboard_manifest.exists():
        return []
    try:
        manifest = json.loads(storyboard_manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    paths: list[Path] = []
    for index, frame in enumerate(manifest.get("frames", [])):
        if not isinstance(frame, dict):
            continue
        artifact = frame.get("artifact")
        path = Path(str(artifact)) if artifact else storyboard_manifest.parent / str(frame.get("artifact_name") or f"storyboard_{index:03d}.png")
        if not path.is_absolute():
            path = storyboard_manifest.parent / path
        if _image_repair_reason(path) is None:
            paths.append(path)
    return paths


def _image_repair_reason(path: Path, min_bytes: int = 128) -> str | None:
    if not path.exists():
        return "missing"
    size = path.stat().st_size
    if size <= min_bytes:
        return "too_small"
    if path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        return None
    try:
        with Image.open(path) as opened:
            image = opened.convert("RGB")
            thumb = image.resize((min(160, image.width), min(90, image.height)))
            stat = ImageStat.Stat(thumb)
    except Exception:
        return "undecodable"
    mean = stat.mean
    stddev = stat.stddev
    luma = 0.2126 * mean[0] + 0.7152 * mean[1] + 0.0722 * mean[2]
    if luma < 3.0 and max(stddev) < 3.0:
        return "blank_or_black"
    return None


def _prepare_animatic_frame(path: Path, size: tuple[int, int] = (640, 360)) -> Image.Image:
    image = Image.open(path).convert("RGB")
    image.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, (18, 18, 18))
    canvas.paste(image, ((size[0] - image.width) // 2, (size[1] - image.height) // 2))
    return canvas


def _storyboard_sample_frames(start: int, end: int, sample_count: int = _STORYBOARD_SAMPLES_PER_CUT) -> list[int]:
    last_inclusive_frame = max(start, end - 1)
    if last_inclusive_frame == start:
        return [start]
    available = last_inclusive_frame - start + 1
    if available <= sample_count:
        return list(range(start, last_inclusive_frame + 1))
    span = last_inclusive_frame - start
    return sorted({int(round(start + span * (index / (sample_count - 1)))) for index in range(sample_count)})


def _write_sequence_preview_gif(output_dir: Path, storyboard_manifest: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_paths = _storyboard_frame_paths(storyboard_manifest)
    if not source_paths:
        return {"created": False, "reason": "no_storyboard_frames", "artifact_name": "sequence_preview.gif"}
    source_frames: list[Image.Image] = []
    skipped: list[str] = []
    for path in source_paths:
        try:
            source_frames.append(_prepare_animatic_frame(path))
        except Exception:
            skipped.append(str(path))
    if not source_frames:
        return {"created": False, "reason": "no_decodable_storyboard_frames", "artifact_name": "sequence_preview.gif", "skipped": skipped}
    frames: list[Image.Image] = []
    transition_steps = 6
    if len(source_frames) == 1:
        frames = [source_frames[0], source_frames[0].copy()]
    else:
        frames.append(source_frames[0])
        for left, right in zip(source_frames, source_frames[1:]):
            for step in range(1, transition_steps + 1):
                frames.append(Image.blend(left, right, step / transition_steps))
            frames.append(right)
    path = output_dir / "sequence_preview.gif"
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=90, loop=0, optimize=False)
    return {
        "created": path.exists() and path.stat().st_size > 128,
        "artifact": str(path),
        "artifact_name": "sequence_preview.gif",
        "source_frame_count": len(source_frames),
        "animatic_frame_count": len(frames),
        "skipped": skipped,
        "bytes": path.stat().st_size if path.exists() else 0,
    }


def _write_sequence_preview_mp4(output_dir: Path, storyboard_manifest: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_paths = _storyboard_frame_paths(storyboard_manifest)
    if not source_paths:
        return {"created": False, "reason": "no_storyboard_frames", "artifact_name": "sequence_preview.mp4"}
    source_frames: list[Image.Image] = []
    skipped: list[str] = []
    for path in source_paths:
        try:
            source_frames.append(_prepare_animatic_frame(path))
        except Exception:
            skipped.append(str(path))
    if not source_frames:
        return {"created": False, "reason": "no_decodable_storyboard_frames", "artifact_name": "sequence_preview.mp4", "skipped": skipped}
    try:
        imageio = importlib.import_module("imageio.v2")
        numpy = importlib.import_module("numpy")
    except Exception as exc:  # noqa: BLE001
        return {"created": False, "reason": "mp4_encoder_unavailable", "artifact_name": "sequence_preview.mp4", "error": str(exc), "skipped": skipped}
    frames: list[Image.Image] = []
    hold_frames = 4
    transition_steps = 8
    if len(source_frames) == 1:
        frames = [source_frames[0] for _ in range(hold_frames * 2)]
    else:
        frames.extend([source_frames[0]] * hold_frames)
        for left, right in zip(source_frames, source_frames[1:]):
            for step in range(1, transition_steps + 1):
                frames.append(Image.blend(left, right, step / transition_steps))
            frames.extend([right] * hold_frames)
    path = output_dir / "sequence_preview.mp4"
    temp_path = output_dir / "sequence_preview.encoding.mp4"
    if temp_path.exists():
        temp_path.unlink()
    try:
        with imageio.get_writer(str(temp_path), format="FFMPEG", fps=12, codec="libx264", quality=8, macro_block_size=1) as writer:
            for frame in frames:
                writer.append_data(numpy.asarray(frame))
    except Exception as exc:  # noqa: BLE001
        if temp_path.exists():
            temp_path.unlink()
        return {"created": False, "reason": "mp4_encode_failed", "artifact_name": "sequence_preview.mp4", "error": str(exc), "skipped": skipped}
    valid, metadata, reason = _mp4_artifact_metadata(temp_path, expected_frames=len(frames))
    if not valid:
        if temp_path.exists():
            temp_path.unlink()
        return {
            "created": False,
            "reason": "mp4_validation_failed",
            "artifact_name": "sequence_preview.mp4",
            "error": reason,
            "metadata": metadata,
            "skipped": skipped,
        }
    if path.exists():
        path.unlink()
    temp_path.replace(path)
    return {
        "created": path.exists() and path.stat().st_size > 1024,
        "artifact": str(path),
        "artifact_name": "sequence_preview.mp4",
        "source_frame_count": len(source_frames),
        "animatic_frame_count": len(frames),
        "decoded_frame_count": metadata.get("frame_count"),
        "duration": metadata.get("duration"),
        "skipped": skipped,
        "bytes": path.stat().st_size if path.exists() else 0,
    }


def _resample_movie_frame_paths(source_paths: list[Path], output_frame_count: int | None) -> tuple[list[Path], bool]:
    if output_frame_count is None or output_frame_count <= 0 or output_frame_count >= len(source_paths):
        return source_paths, False
    if output_frame_count == 1:
        return [source_paths[0]], True
    last_index = len(source_paths) - 1
    indexes = [int(round(last_index * (index / (output_frame_count - 1)))) for index in range(output_frame_count)]
    return [source_paths[index] for index in indexes], True


def _mp4_reader_frame_count(reader: Any, meta: dict[str, Any]) -> int:
    try:
        frame_count = reader.count_frames()
    except Exception:
        frame_count = meta.get("nframes")
    if frame_count is None or frame_count == float("inf"):
        return 0
    try:
        return int(frame_count)
    except (TypeError, ValueError, OverflowError):
        return 0


def _count_decodable_mp4_frames(imageio: Any, path: Path, expected_frames: int | None) -> int:
    reader = imageio.get_reader(str(path), format="FFMPEG")
    count = 0
    limit = int(expected_frames) + 1 if expected_frames is not None else None
    try:
        for _frame in reader:
            count += 1
            if limit is not None and count > limit:
                break
        return count
    finally:
        try:
            reader.close()
        except Exception:
            pass


def _mp4_artifact_metadata(path: Path, expected_frames: int | None = None) -> tuple[bool, dict[str, Any], str]:
    try:
        imageio = importlib.import_module("imageio.v2")
        reader = imageio.get_reader(str(path), format="FFMPEG")
    except Exception as exc:  # noqa: BLE001
        return False, {}, f"mp4_validation_failed: {exc}"
    try:
        meta = reader.get_meta_data()
        frame_count = _mp4_reader_frame_count(reader, meta)
        if frame_count <= 0:
            reader.close()
            try:
                frame_count = _count_decodable_mp4_frames(imageio, path, expected_frames)
            except Exception as exc:  # noqa: BLE001
                return False, {"frame_count": 0}, f"mp4_validation_failed: {exc}"
            reader = imageio.get_reader(str(path), format="FFMPEG")
            meta = reader.get_meta_data()
        if frame_count <= 0:
            return False, {"frame_count": frame_count}, "mp4_validation_failed: no decodable frames"
        if expected_frames is not None and frame_count != int(expected_frames):
            return False, {"frame_count": frame_count, "expected_frames": int(expected_frames)}, "mp4_validation_failed: frame count mismatch"
        for index in sorted({0, max(0, frame_count // 2), max(0, frame_count - 1)}):
            reader.get_data(index)
        return True, {"frame_count": frame_count, "fps": meta.get("fps"), "duration": meta.get("duration"), "size": meta.get("size")}, ""
    except Exception as exc:  # noqa: BLE001
        return False, {}, f"mp4_validation_failed: {exc}"
    finally:
        try:
            reader.close()
        except Exception:
            pass


def _write_movie_frame_paths_mp4(
    output_dir: Path,
    source_paths: list[Path],
    fps: int,
    *,
    skipped: list[dict[str, Any]] | None = None,
    output_frame_count: int | None = None,
    frame_map_used: bool = False,
) -> dict[str, Any]:
    skipped = skipped or []
    if not source_paths:
        return {"created": False, "reason": "no_movie_frames", "artifact_name": "sequence_preview.mp4", "skipped": skipped}
    input_movie_frame_count = len(source_paths)
    source_paths, resampled = _resample_movie_frame_paths(source_paths, output_frame_count)
    try:
        imageio = importlib.import_module("imageio.v2")
        numpy = importlib.import_module("numpy")
    except Exception as exc:  # noqa: BLE001
        return {"created": False, "reason": "mp4_encoder_unavailable", "artifact_name": "sequence_preview.mp4", "error": str(exc), "skipped": skipped}
    path = output_dir / "sequence_preview.mp4"
    temp_path = output_dir / "sequence_preview.encoding.mp4"
    if temp_path.exists():
        temp_path.unlink()
    try:
        with imageio.get_writer(str(temp_path), format="FFMPEG", fps=max(1, int(fps)), codec="libx264", quality=8, macro_block_size=1) as writer:
            for source_path in source_paths:
                with Image.open(source_path) as image:
                    writer.append_data(numpy.asarray(image.convert("RGB")))
    except Exception as exc:  # noqa: BLE001
        if temp_path.exists():
            temp_path.unlink()
        return {"created": False, "reason": "mp4_encode_failed", "artifact_name": "sequence_preview.mp4", "error": str(exc), "skipped": skipped}
    valid, metadata, reason = _mp4_artifact_metadata(temp_path, expected_frames=len(source_paths))
    if not valid:
        if temp_path.exists():
            temp_path.unlink()
        return {
            "created": False,
            "reason": "mp4_validation_failed",
            "artifact_name": "sequence_preview.mp4",
            "error": reason,
            "metadata": metadata,
            "skipped": skipped,
        }
    if path.exists():
        path.unlink()
    temp_path.replace(path)
    return {
        "created": path.exists() and path.stat().st_size > 1024,
        "artifact": str(path),
        "artifact_name": "sequence_preview.mp4",
        "source_frame_count": len(source_paths),
        "input_movie_frame_count": input_movie_frame_count,
        "resampled": resampled,
        "fps": int(fps),
        "decoded_frame_count": metadata.get("frame_count"),
        "duration": metadata.get("duration"),
        "skipped": skipped,
        "bytes": path.stat().st_size if path.exists() else 0,
        "frame_map_used": frame_map_used,
    }


def _write_movie_frame_sequence_mp4(
    output_dir: Path,
    movie_dir: Path,
    start_frame: int,
    end_frame: int,
    fps: int,
    output_frame_count: int | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_paths: list[Path] = []
    skipped: list[dict[str, Any]] = []
    for frame in range(start_frame, end_frame):
        path = movie_dir / f"movie_frame_{frame:04d}.png"
        reason = _image_repair_reason(path, min_bytes=1)
        if reason is None:
            source_paths.append(path)
        else:
            skipped.append({"frame": frame, "path": str(path), "reason": reason})
    return _write_movie_frame_paths_mp4(output_dir, source_paths, fps, skipped=skipped, output_frame_count=output_frame_count)


def _is_movie_frame_render_backend(value: Any) -> bool:
    return str(value or "") in {"sequencer_movie_capture", "movie_render_pipeline"}


class Runner(ABC):
    @abstractmethod
    def execute(self, op: Operation, script: str, run_dir: Path) -> ExecutionResult:
        raise NotImplementedError

    @abstractmethod
    def load_state(self, run_dir: Path) -> dict[str, Any]:
        raise NotImplementedError

    def restore_state(self, run_dir: Path, state: dict[str, Any]) -> None:
        """Restore a state snapshot after failed transactional execution.

        Real Unreal rollback requires project-specific deletion/restore logic; the
        command runner records the intended state boundary, while MockRunner
        restores it exactly.
        """
        state_path = Path(run_dir) / "snapshots" / "world_current.json"
        atomic_write_json(state_path, state)


class MockRunner(Runner):
    """Deterministic in-process simulation of Unreal side effects.

    This runner is not a renderer. It implements the same operation-level
    contract as the Unreal runner so that planning, code generation,
    verification and file-ledger behavior can be tested without Unreal.
    """

    def state_path(self, run_dir: Path) -> Path:
        return Path(run_dir) / "snapshots" / "world_current.json"

    def load_state(self, run_dir: Path) -> dict[str, Any]:
        return read_json(self.state_path(run_dir), default=initial_world_state())

    def save_state(self, run_dir: Path, state: dict[str, Any]) -> None:
        atomic_write_json(self.state_path(run_dir), state)

    def execute(self, op: Operation, script: str, run_dir: Path) -> ExecutionResult:
        state = self.load_state(run_dir)
        try:
            handler = getattr(self, f"_handle_{op.type.replace('.', '_')}", None)
            if handler is None:
                raise NotImplementedError(f"MockRunner has no handler for {op.type}")
            result = handler(op, state, run_dir)
            self.save_state(run_dir, state)
            return ExecutionResult(ok=True, op_id=op.op_id, status="success", result=result)
        except Exception as exc:  # noqa: BLE001 - diagnostic boundary
            self.save_state(run_dir, state)
            return ExecutionResult(ok=False, op_id=op.op_id, status="failed", error_type=type(exc).__name__, error_message=str(exc))

    def _handle_env_setup(self, op: Operation, state: dict[str, Any], run_dir: Path) -> dict[str, Any]:
        env = op.inputs["environment"]
        level = op.inputs["level_name"]
        state["level"] = level
        environment_asset = op.inputs.get("environment_asset")
        if environment_asset:
            state["environment_asset"] = environment_asset
        env_text = env.lower()
        if "desert" in env_text:
            state["support_surfaces"] = {
                "desert_floor": {"type": "ground", "z": 0.0, "bounds": [-2000, 2000, -2000, 2000]},
            }
            state["lighting"] = {"sun_angle": 12, "mood": op.inputs.get("mood", "warm dusk")}
        elif "park" in env_text:
            level_backed = isinstance(environment_asset, dict) and str(environment_asset.get("type", "")).lower() == "level"
            state["support_surfaces"] = {
                "park_path": citypark_path_support_surface(level_backed=level_backed),
            }
            state["lighting"] = {"sun_angle": 35, "mood": op.inputs.get("mood", "sunlit park")}
        elif "river" in env_text:
            state["support_surfaces"] = {
                "river_shallow": {"type": "ground", "z": 0.0, "bounds": [-300, 300, -500, 500]},
                "river_bed": {"type": "ground", "z": -120.0, "bounds": [-500, 500, -500, 500]},
            }
            state["lighting"] = {"style": "clear_water", "mood": op.inputs.get("mood", "clear water daylight")}
        elif "city" in env_text or "rooftop" in env_text:
            state["support_surfaces"] = {
                "rooftop_floor": {"type": "ground", "z": 0.0, "bounds": [-700, 700, -700, 700]},
            }
            state["lighting"] = {"style": "backlit_skyline", "mood": op.inputs.get("mood", "backlit skyline")}
        elif "building" in env_text:
            state["support_surfaces"] = {
                "building_floor": {"type": "ground", "z": 0.0, "bounds": [-600, 600, -600, 600]},
            }
            state["lighting"] = {"style": "golden_reveal", "mood": op.inputs.get("mood", "golden exterior reveal")}
        else:
            state["support_surfaces"] = {
                "gallery_floor": {"type": "ground", "z": 0.0, "bounds": [-500, 500, -500, 500]},
                "left_wall": {"type": "wall", "x": -500.0, "bounds": [-500, -500, -500, 500, 0, 800]},
                "right_wall": {"type": "wall", "x": 500.0, "bounds": [500, 500, -500, 500, 0, 800]},
                "back_wall": {"type": "wall", "y": 500.0, "bounds": [-500, 500, 500, 500, 0, 800]},
            }
            state["lighting"] = {"style": "soft_gallery", "mood": op.inputs.get("mood", "clean")}
        result = {"level": level, "support_surfaces": list(state["support_surfaces"].keys())}
        if environment_asset:
            result["environment_asset"] = environment_asset
        return result

    def _handle_entity_spawn_many(self, op: Operation, state: dict[str, Any], run_dir: Path) -> dict[str, Any]:
        created = []
        for actor in op.inputs["actors"]:
            name = actor["actor_name"]
            state["actors"][name] = {
                "name": name,
                "semantic_type": actor.get("semantic_type"),
                "asset_id": actor["asset_id"],
                "asset_path": actor["asset_path"],
                "asset_type": actor["asset_type"],
                "source_path": actor.get("source_path"),
                "source_type": actor.get("source_type"),
                "import_required": actor.get("import_required", False),
                "materials": actor.get("materials", []),
                "bounds_extent": actor.get("bounds_extent", [50, 50, 50]),
                "transform": {"location": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            }
            created.append(name)
        return {"created_actors": created}

    def _handle_asset_import_many(self, op: Operation, state: dict[str, Any], run_dir: Path) -> dict[str, Any]:
        imports = state.setdefault("asset_imports", {})
        records = []
        for asset in op.inputs.get("assets", []):
            asset_id = asset["asset_id"]
            source_path = asset.get("source_path")
            if asset.get("import_required") and (not source_path or not Path(str(source_path)).exists()):
                raise FileNotFoundError(f"source asset missing: {asset_id}:{source_path}")
            status = "imported" if asset.get("import_required") else "available"
            record = {
                "asset_id": asset_id,
                "status": status,
                "source_path": source_path,
                "source_type": asset.get("source_type"),
                "ue_path": asset.get("ue_path"),
                "import_destination": asset.get("import_destination"),
                "imported_object_paths": asset.get("imported_object_paths") or ([asset.get("ue_path")] if asset.get("ue_path") else []),
            }
            imports[asset_id] = record
            records.append(record)
        return {"assets": records, "imported_assets": [record["asset_id"] for record in records]}

    def _handle_spatial_apply_transforms(self, op: Operation, state: dict[str, Any], run_dir: Path) -> dict[str, Any]:
        transformed = []
        for placement in op.inputs["placements"]:
            name = placement["actor_name"]
            if name not in state["actors"]:
                raise KeyError(f"actor not found: {name}")
            state["actors"][name]["transform"] = placement["transform"]
            state["actors"][name]["spatial_relation"] = {"relation": placement.get("relation"), "target": placement.get("target")}
            transformed.append(name)
        return {"transformed": transformed}

    def _handle_sequence_init(self, op: Operation, state: dict[str, Any], run_dir: Path) -> dict[str, Any]:
        path = op.inputs["sequence_path"]
        state["sequences"][path] = {
            "sequence_path": path,
            "fps": op.inputs["fps"],
            "range": [op.inputs["start_frame"], op.inputs["end_frame"]],
            "cameras": {},
            "camera_cuts": [],
            "transform_tracks": {},
            "animation_tracks": {},
            "bound_actors": [],
        }
        return {"sequence_path": path}

    def _handle_sequence_use_existing(self, op: Operation, state: dict[str, Any], run_dir: Path) -> dict[str, Any]:
        path = op.inputs["sequence_path"]
        start_frame = int(op.inputs.get("start_frame", 0))
        end_frame = int(op.inputs.get("end_frame", 0))
        fps = int(op.inputs.get("fps", 24))
        camera_name = str(op.inputs.get("native_camera_name") or "NativeSequenceCamera")
        shot_id = str(op.inputs.get("shot_id") or "existing_sequence")
        asset = op.inputs.get("sequence_asset") or {}
        state["actors"][camera_name] = {
            "name": camera_name,
            "semantic_type": "camera",
            "asset_id": "existing_level_sequence_camera",
            "asset_path": "/Script/CinematicCamera.CineCameraActor",
            "asset_type": "camera",
            "bounds_extent": [0, 0, 0],
            "transform": {"location": [0.0, -650.0, 180.0], "rotation": [-8.0, 0.0, 0.0], "scale": [1, 1, 1]},
        }
        state["sequences"][path] = {
            "sequence_path": path,
            "source_asset_id": asset.get("asset_id"),
            "source_asset_type": asset.get("type"),
            "source_path": asset.get("source_path"),
            "fps": fps,
            "range": [start_frame, end_frame],
            "cameras": {
                camera_name: {
                    "shot_id": shot_id,
                    "target_actor": None,
                    "transform_keys": [
                        {"frame": start_frame, "location": [0.0, -650.0, 180.0], "rotation": [-8.0, 0.0, 0.0]},
                        {"frame": end_frame, "location": [0.0, -500.0, 160.0], "rotation": [-8.0, 0.0, 0.0]},
                    ],
                    "focal_length_keys": [
                        {"frame": start_frame, "focal_length": 45.0},
                        {"frame": end_frame, "focal_length": 35.0},
                    ],
                    "focus_distance_keys": [
                        {"frame": start_frame, "focus_distance": 650.0},
                        {"frame": end_frame, "focus_distance": 500.0},
                    ],
                }
            },
            "camera_cuts": [
                {"camera_name": camera_name, "shot_id": shot_id, "start_frame": start_frame, "end_frame": end_frame}
            ],
            "transform_tracks": {},
            "animation_tracks": {},
            "bound_actors": [],
        }
        return {"sequence_path": path, "source_asset_id": asset.get("asset_id")}

    def _handle_camera_dolly_in(self, op: Operation, state: dict[str, Any], run_dir: Path) -> dict[str, Any]:
        return self._create_camera_track(op, state)

    def _handle_camera_static_shot(self, op: Operation, state: dict[str, Any], run_dir: Path) -> dict[str, Any]:
        return self._create_camera_track(op, state)

    def _handle_camera_wide_aerial(self, op: Operation, state: dict[str, Any], run_dir: Path) -> dict[str, Any]:
        return self._create_camera_track(op, state)

    def _handle_camera_orbit(self, op: Operation, state: dict[str, Any], run_dir: Path) -> dict[str, Any]:
        return self._create_camera_track(op, state)

    def _handle_camera_hitchcock_zoom(self, op: Operation, state: dict[str, Any], run_dir: Path) -> dict[str, Any]:
        return self._create_camera_track(op, state)

    def _create_camera_track(self, op: Operation, state: dict[str, Any]) -> dict[str, Any]:
        seq = state["sequences"].get(op.inputs["sequence_path"])
        if seq is None:
            raise KeyError(f"sequence not found: {op.inputs['sequence_path']}")
        camera_name = op.inputs["camera_name"]
        keys = op.inputs["keys"]
        if not keys:
            raise ValueError("camera operation requires at least one key")
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
            "shot_id": op.inputs["shot_id"],
            "target_actor": op.inputs.get("target_actor"),
            "transform_keys": [{k: key[k] for k in ["frame", "location", "rotation"]} for key in keys],
            "focal_length_keys": [{"frame": key["frame"], "focal_length": key["focal_length"]} for key in keys],
            "focus_distance_keys": [{"frame": key["frame"], "focus_distance": key.get("focus_distance")} for key in keys],
        }
        return {"camera_name": camera_name, "key_count": len(keys)}

    def _handle_transform_add_tracks(self, op: Operation, state: dict[str, Any], run_dir: Path) -> dict[str, Any]:
        seq = state["sequences"].get(op.inputs["sequence_path"])
        if seq is None:
            raise KeyError(f"sequence not found: {op.inputs['sequence_path']}")
        tracks = []
        for track in op.inputs["tracks"]:
            actor = track["actor_name"]
            if actor not in state["actors"]:
                raise KeyError(f"actor not found for transform track: {actor}")
            seq.setdefault("transform_tracks", {})[actor] = track
            # Keep the editor world snapshot aligned with the first key until a
            # true sequence evaluator is integrated. The full temporal motion is
            # stored under transform_tracks.
            first_key = track.get("keys", [{}])[0].get("transform")
            if first_key:
                state["actors"][actor]["transform"] = first_key
            tracks.append(actor)
        return {"transform_tracks": tracks}

    def _handle_animation_add_tracks(self, op: Operation, state: dict[str, Any], run_dir: Path) -> dict[str, Any]:
        seq = state["sequences"].get(op.inputs["sequence_path"])
        if seq is None:
            raise KeyError(f"sequence not found: {op.inputs['sequence_path']}")
        tracks = []
        for clip in op.inputs["clips"]:
            actor = clip["actor_name"]
            if actor not in state["actors"]:
                raise KeyError(f"actor not found for animation: {actor}")
            seq["animation_tracks"][actor] = clip
            tracks.append(actor)
        return {"animation_tracks": tracks}

    def _handle_sequence_camera_cut(self, op: Operation, state: dict[str, Any], run_dir: Path) -> dict[str, Any]:
        seq = state["sequences"].get(op.inputs["sequence_path"])
        if seq is None:
            raise KeyError(f"sequence not found: {op.inputs['sequence_path']}")
        seq["camera_cuts"] = sorted(op.inputs["cuts"], key=lambda c: c["start_frame"])
        return {"camera_cuts": seq["camera_cuts"]}

    def _handle_render_preview(self, op: Operation, state: dict[str, Any], run_dir: Path) -> dict[str, Any]:
        out = Path(op.inputs["output_dir"])
        out.mkdir(parents=True, exist_ok=True)
        preview_frame = out / "preview_frame.png"
        preview_manifest = out / "preview_manifest.json"
        storyboard_manifest = out / "storyboard_manifest.json"
        width, height = [int(x) for x in op.inputs.get("resolution", [1280, 720])]
        # Bound image size for CI speed.
        width = min(width, 1280)
        height = min(height, 720)
        img = Image.new("RGB", (width, height), color=(245, 245, 245))
        draw = ImageDraw.Draw(img)
        lines = [
            "CineU Research Mock Preview",
            f"Level: {state.get('level')}",
            f"Actors: {', '.join(list(state.get('actors', {}).keys())[:8])}",
            f"Sequence: {op.inputs['sequence_path']}",
            "Use runner=unreal for Movie Render Queue output.",
        ]
        y = 30
        for line in lines:
            draw.text((30, y), line, fill=(20, 20, 20))
            y += 28
        img.save(preview_frame)
        seq = state.get("sequences", {}).get(op.inputs["sequence_path"], {})
        cuts = sorted(seq.get("camera_cuts", []), key=lambda item: item.get("start_frame", 0))
        first_cut = cuts[0] if cuts else {}
        manifest = {
            "mock": True,
            "sequence_path": op.inputs["sequence_path"],
            "resolution": [width, height],
            "actors": list(state.get("actors", {}).keys()),
            "preview_camera": first_cut.get("camera_name"),
            "preview_shot_id": first_cut.get("shot_id"),
            "preview_frame": first_cut.get("start_frame", 0),
        }
        atomic_write_json(preview_manifest, manifest)
        storyboard_frames = []
        frame_sources = self._mock_storyboard_samples(seq)
        for index, sample in enumerate(frame_sources):
            name = f"storyboard_{index:03d}.png"
            path = out / name
            img = Image.new("RGB", (width, height), color=(238, 238, 238))
            draw = ImageDraw.Draw(img)
            draw.text((30, 30), "CineU Mock Storyboard", fill=(20, 20, 20))
            draw.text((30, 62), f"Shot: {sample.get('shot_id')}", fill=(20, 20, 20))
            draw.text((30, 94), f"Camera: {sample.get('camera_name')}", fill=(20, 20, 20))
            draw.text((30, 126), f"Frame: {sample.get('frame')}", fill=(20, 20, 20))
            img.save(path)
            record = {**sample, "artifact": str(path), "artifact_name": name}
            storyboard_frames.append(record)
        atomic_write_json(
            storyboard_manifest,
            {
                "mock": True,
                "sequence_path": op.inputs["sequence_path"],
                "resolution": [width, height],
                "frames": storyboard_frames,
            },
        )
        sequence_preview = _write_sequence_preview_gif(out, storyboard_manifest)
        sequence_preview_mp4 = _write_sequence_preview_mp4(out, storyboard_manifest) if op.inputs.get("format") == "mp4" else {"created": False, "reason": "not_requested", "artifact_name": "sequence_preview.mp4"}
        artifacts = {"preview_frame.png": str(preview_frame), "preview_manifest.json": str(preview_manifest), "storyboard_manifest.json": str(storyboard_manifest)}
        for frame in storyboard_frames:
            artifacts[frame["artifact_name"]] = frame["artifact"]
        if sequence_preview.get("created"):
            artifacts[sequence_preview["artifact_name"]] = sequence_preview["artifact"]
        if sequence_preview_mp4.get("created"):
            artifacts[sequence_preview_mp4["artifact_name"]] = sequence_preview_mp4["artifact"]
        render_record = {
            "sequence_path": op.inputs["sequence_path"],
            "quality": op.inputs.get("quality"),
            "preview_camera": first_cut.get("camera_name"),
            "preview_shot_id": first_cut.get("shot_id"),
            "preview_frame": first_cut.get("start_frame", 0),
            "storyboard_frames": storyboard_frames,
            "sequence_preview": sequence_preview,
            "sequence_preview_mp4": sequence_preview_mp4,
            "artifacts": artifacts,
        }
        state.setdefault("renders", []).append(render_record)
        return render_record

    def _mock_storyboard_samples(self, seq: dict[str, Any]) -> list[dict[str, Any]]:
        samples: list[dict[str, Any]] = []
        cameras = seq.get("cameras", {})
        for cut in sorted(seq.get("camera_cuts", []), key=lambda item: item.get("start_frame", 0)):
            camera_name = cut.get("camera_name")
            camera = cameras.get(camera_name, {})
            keys = sorted(camera.get("transform_keys", []), key=lambda item: item.get("frame", 0))
            if not keys:
                continue
            start = int(cut.get("start_frame", keys[0].get("frame", 0)))
            end = int(cut.get("end_frame", keys[-1].get("frame", start)))
            sample_frames = _storyboard_sample_frames(start, end)
            for frame in sample_frames:
                key = min(keys, key=lambda item: abs(int(item.get("frame", start)) - frame))
                samples.append(
                    {
                        "camera_name": camera_name,
                        "shot_id": cut.get("shot_id"),
                        "frame": frame,
                        "location": key.get("location"),
                        "rotation": key.get("rotation"),
                    }
                )
        return samples[:_MAX_STORYBOARD_SAMPLES]


class UnrealCommandRunner(Runner):
    """Command-line Unreal runner.

    It expects UnrealEditor-Cmd / UnrealEditor to be available locally and the
    project plugin Python wrappers to be enabled.
    """

    _MIN_STORYBOARD_FRAME_BYTES = 128

    def __init__(self, unreal_editor_cmd: str, uproject: Path, timeout_sec: int = 300):
        self.unreal_editor_cmd = unreal_editor_cmd
        self.uproject = Path(uproject).resolve()
        self.timeout_sec = timeout_sec

    def state_path(self, run_dir: Path) -> Path:
        return Path(run_dir) / "snapshots" / "world_current.json"

    def load_state(self, run_dir: Path) -> dict[str, Any]:
        return read_json(self.state_path(run_dir), default=initial_world_state())

    def _result_path(self, op: Operation, run_dir: Path) -> Path:
        return Path(run_dir) / "traces" / f"{op.op_id}_unreal_result.json"

    def _plugin_python_path(self) -> Path:
        return (self.uproject.parent / "Plugins" / "CineUDemo" / "Content" / "Python").resolve()

    def _unreal_cmd_for_script(self, script_path: Path) -> list[str]:
        return [
            self.unreal_editor_cmd,
            str(self.uproject),
            f"-ExecutePythonScript={script_path}",
            "-unattended",
            "-nop4",
            "-nosplash",
            "-DDC=InstalledNoZenLocalFallback",
        ]

    def _write_executor_bootstrap(self, op: Operation, script_path: Path, run_dir: Path) -> Path:
        run_dir = Path(run_dir).resolve()
        plugin_python = self._plugin_python_path()
        script_path = Path(script_path).resolve()
        world_state_path = self.state_path(run_dir).resolve()
        result_path = self._result_path(op, run_dir).resolve()
        bootstrap_path = (run_dir / "scripts" / f"{op.op_id}_exec.py").resolve()
        bootstrap = (
            "from __future__ import annotations\n"
            "import sys\n"
            f"sys.path.insert(0, {str(plugin_python)!r})\n"
            "from cineu_executor import execute_generated_script\n"
            "execute_generated_script(\n"
            f"    script_path={str(script_path)!r},\n"
            f"    world_state_path={str(world_state_path)!r},\n"
            f"    result_path={str(result_path)!r},\n"
            ")\n"
        )
        bootstrap_path.parent.mkdir(parents=True, exist_ok=True)
        bootstrap_path.write_text(bootstrap, encoding="utf-8")
        return bootstrap_path

    def _read_unreal_result(self, op: Operation, run_dir: Path) -> dict[str, Any] | None:
        result_path = self._result_path(op, run_dir)
        if not result_path.exists():
            return None
        return json.loads(result_path.read_text(encoding="utf-8"))

    def _storyboard_artifact_path(self, frame: dict[str, Any], output_dir: Path, index: int) -> Path:
        artifact = frame.get("artifact")
        if artifact:
            path = Path(str(artifact))
            return path if path.is_absolute() else output_dir / path
        artifact_name = str(frame.get("artifact_name") or f"storyboard_{index:03d}.png")
        return output_dir / artifact_name

    def _native_movie_frame_path(self, movie_dir: Path, frame: int) -> Path:
        return movie_dir / f"movie_frame_{int(frame):04d}.png"

    def _finalize_native_movie_capture_artifacts(self, op: Operation) -> dict[str, Any]:
        if op.type != "render.preview" or not op.inputs.get("output_dir"):
            return {"finalized": False, "reason": "not_render_preview"}
        output_dir = Path(str(op.inputs["output_dir"]))
        storyboard_manifest = output_dir / "storyboard_manifest.json"
        preview_manifest = output_dir / "preview_manifest.json"
        if not storyboard_manifest.exists():
            return {"finalized": False, "reason": "storyboard_manifest_missing"}
        try:
            storyboard = json.loads(storyboard_manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"finalized": False, "reason": "storyboard_manifest_invalid"}
        preview = {}
        if preview_manifest.exists():
            try:
                preview = json.loads(preview_manifest.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                preview = {}
        if not _is_movie_frame_render_backend(storyboard.get("render_backend")) and not _is_movie_frame_render_backend(preview.get("render_backend")):
            return {"finalized": False, "reason": "not_native_movie_capture"}
        movie_dir_value = storyboard.get("movie_frame_dir") or preview.get("movie_frame_dir") or output_dir / "movie_frames"
        movie_dir = Path(str(movie_dir_value))
        if not movie_dir.is_absolute():
            movie_dir = output_dir / movie_dir
        frames = [frame for frame in storyboard.get("frames", []) if isinstance(frame, dict)]
        copied: list[str] = []
        missing: list[dict[str, Any]] = []
        for index, frame in enumerate(frames):
            if frame.get("frame") is None:
                missing.append({"index": index, "reason": "frame_number_missing"})
                continue
            source = self._native_movie_frame_path(movie_dir, int(frame["frame"]))
            target = self._storyboard_artifact_path(frame, output_dir, index)
            reason = _image_repair_reason(source, self._MIN_STORYBOARD_FRAME_BYTES)
            if reason is not None:
                missing.append({"index": index, "frame": frame.get("frame"), "source": str(source), "reason": reason})
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            frame["artifact"] = str(target)
            frame["artifact_name"] = target.name
            copied.append(str(target))
        preview_path = output_dir / "preview_frame.png"
        preview_source = self._storyboard_artifact_path(frames[0], output_dir, 0) if frames else None
        preview_copied = False
        if preview_source is not None and _image_repair_reason(preview_source, self._MIN_STORYBOARD_FRAME_BYTES) is None:
            shutil.copyfile(preview_source, preview_path)
            preview_copied = True
        storyboard["frames"] = frames
        finalized = bool(copied) and preview_copied and not missing
        sequence_path = str(op.inputs.get("sequence_path") or preview.get("sequence_path") or storyboard.get("sequence_path") or "")
        start_frame = op.inputs.get("start_frame", preview.get("start_frame", storyboard.get("start_frame")))
        end_frame = op.inputs.get("end_frame", preview.get("end_frame", storyboard.get("end_frame")))
        fps = op.inputs.get("fps", preview.get("fps", storyboard.get("fps")))
        movie_frame_count = len(list(movie_dir.glob("movie_frame_*.png")))
        frame_count = movie_frame_count
        if start_frame is not None and end_frame is not None:
            frame_count = max(0, int(end_frame) - int(start_frame))
        sequence_state: dict[str, Any] = {}
        world_state_path = op.inputs.get("world_state_path")
        if sequence_path and world_state_path:
            world_state = read_json(Path(str(world_state_path)), default={})
            sequence_state = (world_state.get("sequences") or {}).get(sequence_path, {})
        render_backend = str(storyboard.get("render_backend") or preview.get("render_backend") or "sequencer_movie_capture")
        manifest_metadata = {
            "render_backend": render_backend,
            "sequence_path": sequence_path or None,
            "fps": int(fps) if fps is not None else None,
            "start_frame": int(start_frame) if start_frame is not None else None,
            "end_frame": int(end_frame) if end_frame is not None else None,
            "frame_count": frame_count,
            "movie_frame_count": movie_frame_count,
            "source_asset_id": sequence_state.get("source_asset_id"),
            "source_asset_type": sequence_state.get("source_asset_type"),
        }
        for key, value in manifest_metadata.items():
            if value is not None:
                storyboard[key] = value
        if finalized:
            storyboard["capture_success"] = True
            storyboard["warnings"] = [
                warning
                for warning in storyboard.get("warnings", [])
                if not (isinstance(warning, dict) and warning.get("reason") == "deadline" and warning.get("capture_success") is None)
            ]
        storyboard_manifest.write_text(json.dumps(storyboard, ensure_ascii=False, indent=2), encoding="utf-8")
        if preview:
            artifacts = preview.setdefault("artifacts", {})
            artifacts["preview_frame.png"] = str(preview_path)
            artifacts["storyboard_manifest.json"] = str(storyboard_manifest)
            artifacts["movie_frame_dir"] = str(movie_dir)
            preview["storyboard_frames"] = frames
            for key, value in manifest_metadata.items():
                if value is not None:
                    preview[key] = value
            if finalized:
                preview["capture_success"] = True
                preview["warnings"] = [
                    warning
                    for warning in preview.get("warnings", [])
                    if not (isinstance(warning, dict) and warning.get("reason") == "deadline" and warning.get("capture_success") is None)
                ]
            preview_manifest.write_text(json.dumps(preview, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "finalized": finalized,
            "copied": copied,
            "preview_frame": str(preview_path) if preview_copied else None,
            "missing": missing,
            "movie_frame_dir": str(movie_dir),
        }

    def _storyboard_repairs_needed(self, op: Operation) -> list[dict[str, Any]]:
        if op.type != "render.preview":
            return []
        output_dir_value = op.inputs.get("output_dir")
        if not output_dir_value:
            return []
        output_dir = Path(str(output_dir_value))
        manifest_path = output_dir / "storyboard_manifest.json"
        if not manifest_path.exists():
            return []
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        repairs: list[dict[str, Any]] = []
        for index, frame in enumerate(manifest.get("frames", [])):
            if not isinstance(frame, dict):
                continue
            artifact_path = self._storyboard_artifact_path(frame, output_dir, index)
            size = artifact_path.stat().st_size if artifact_path.exists() else 0
            reason = _image_repair_reason(artifact_path, self._MIN_STORYBOARD_FRAME_BYTES)
            if reason is not None:
                repairs.append({"index": index, "frame": frame, "artifact": str(artifact_path), "before_bytes": size, "reason": reason})
        return repairs

    def _preview_repair_needed(self, op: Operation) -> dict[str, Any] | None:
        if op.type != "render.preview":
            return None
        output_dir_value = op.inputs.get("output_dir")
        if not output_dir_value:
            return None
        output_dir = Path(str(output_dir_value))
        preview_path = output_dir / "preview_frame.png"
        size = preview_path.stat().st_size if preview_path.exists() else 0
        reason = _image_repair_reason(preview_path, self._MIN_STORYBOARD_FRAME_BYTES)
        if reason is None:
            return None
        manifest_path = output_dir / "storyboard_manifest.json"
        if not manifest_path.exists():
            return None
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        frames = [frame for frame in manifest.get("frames", []) if isinstance(frame, dict)]
        if not frames:
            return None
        return {
            "index": "preview",
            "script_suffix": "preview_frame",
            "frame": frames[0],
            "artifact": str(preview_path),
            "before_bytes": size,
            "reason": reason,
        }

    def _write_storyboard_capture_script(self, op: Operation, run_dir: Path, repair: dict[str, Any]) -> Path:
        run_dir = Path(run_dir).resolve()
        world_state_path = Path(str(op.inputs.get("world_state_path") or self.state_path(run_dir))).resolve()
        output_path = Path(str(repair["artifact"])).resolve()
        params = {
            "sample": repair["frame"],
            "output_path": str(output_path),
            "resolution": op.inputs.get("resolution", [1280, 720]),
            "world_state_path": str(world_state_path),
            "sequence_path": op.inputs.get("sequence_path"),
        }
        script_suffix = repair.get("script_suffix") or f"storyboard_{int(repair['index']):03d}"
        script_path = run_dir / "scripts" / f"{op.op_id}_{script_suffix}_capture.py"
        script = (
            "from __future__ import annotations\n"
            "import sys\n"
            f"sys.path.insert(0, {str(self._plugin_python_path())!r})\n"
            "from cineu_executor import _rehydrate_world_state\n"
            "from cineu_render_ops import capture_storyboard_frame_once\n"
            f"_rehydrate_world_state({str(world_state_path)!r})\n"
            f"OUTPUT = capture_storyboard_frame_once({params!r})\n"
        )
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(script, encoding="utf-8")
        return script_path

    def _write_storyboard_batch_capture_script(self, op: Operation, run_dir: Path, repairs: list[dict[str, Any]]) -> Path:
        run_dir = Path(run_dir).resolve()
        world_state_path = Path(str(op.inputs.get("world_state_path") or self.state_path(run_dir))).resolve()
        params = [
            {
                "sample": repair["frame"],
                "output_path": str(Path(str(repair["artifact"])).resolve()),
                "resolution": op.inputs.get("resolution", [1280, 720]),
                "world_state_path": str(world_state_path),
                "sequence_path": op.inputs.get("sequence_path"),
            }
            for repair in repairs
        ]
        script_path = run_dir / "scripts" / f"{op.op_id}_storyboard_batch_capture.py"
        script = (
            "from __future__ import annotations\n"
            "import sys\n"
            f"sys.path.insert(0, {str(self._plugin_python_path())!r})\n"
            "from cineu_executor import _rehydrate_world_state\n"
            "from cineu_render_ops import capture_storyboard_frame_once\n"
            f"_rehydrate_world_state({str(world_state_path)!r})\n"
            f"PARAMS_LIST = {params!r}\n"
            "OUTPUT = [capture_storyboard_frame_once(params) for params in PARAMS_LIST]\n"
        )
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(script, encoding="utf-8")
        return script_path

    def _run_frame_capture_repair(self, op: Operation, run_dir: Path, repair: dict[str, Any]) -> dict[str, Any]:
        script_path = self._write_storyboard_capture_script(op, run_dir, repair)
        cmd = self._unreal_cmd_for_script(script_path)
        record = {**repair, "cmd": cmd, "script_path": str(script_path), "returncode": None, "after_bytes": None, "repaired": False}
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout_sec, check=False)
            artifact_path = Path(str(repair["artifact"]))
            after = artifact_path.stat().st_size if artifact_path.exists() else 0
            after_reason = _image_repair_reason(artifact_path, self._MIN_STORYBOARD_FRAME_BYTES)
            record.update(
                {
                    "returncode": proc.returncode,
                    "after_bytes": after,
                    "after_reason": after_reason,
                    "repaired": proc.returncode == 0 and after_reason is None,
                }
            )
        except subprocess.TimeoutExpired as exc:
            record.update({"error_type": "UE_FRAME_CAPTURE_TIMEOUT", "error_message": str(exc)})
        return record

    def _run_frame_capture_batch_repair(self, op: Operation, run_dir: Path, repairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not repairs:
            return []
        script_path = self._write_storyboard_batch_capture_script(op, run_dir, repairs)
        cmd = self._unreal_cmd_for_script(script_path)
        records = [
            {**repair, "cmd": cmd, "script_path": str(script_path), "returncode": None, "after_bytes": None, "repaired": False}
            for repair in repairs
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout_sec, check=False)
            for record in records:
                artifact_path = Path(str(record["artifact"]))
                after = artifact_path.stat().st_size if artifact_path.exists() else 0
                after_reason = _image_repair_reason(artifact_path, self._MIN_STORYBOARD_FRAME_BYTES)
                record.update(
                    {
                        "returncode": proc.returncode,
                        "after_bytes": after,
                        "after_reason": after_reason,
                        "repaired": proc.returncode == 0 and after_reason is None,
                    }
                )
        except subprocess.TimeoutExpired as exc:
            for record in records:
                record.update({"error_type": "UE_FRAME_CAPTURE_TIMEOUT", "error_message": str(exc)})
        return records

    def _repair_preview_frame(self, op: Operation, run_dir: Path) -> list[dict[str, Any]]:
        repair = self._preview_repair_needed(op)
        if repair is None:
            return []
        copied = self._repair_preview_from_first_storyboard(op, repair)
        if copied is not None:
            return [copied]
        return [self._run_frame_capture_repair(op, run_dir, repair)]

    def _repair_preview_from_first_storyboard(self, op: Operation, repair: dict[str, Any]) -> dict[str, Any] | None:
        output_dir_value = op.inputs.get("output_dir")
        if not output_dir_value:
            return None
        output_dir = Path(str(output_dir_value))
        manifest_path = output_dir / "storyboard_manifest.json"
        if not manifest_path.exists():
            return None
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        frames = [frame for frame in manifest.get("frames", []) if isinstance(frame, dict)]
        if not frames:
            return None
        first_path = self._storyboard_artifact_path(frames[0], output_dir, 0)
        if _image_repair_reason(first_path, self._MIN_STORYBOARD_FRAME_BYTES) is not None:
            return None
        preview_path = Path(str(repair["artifact"]))
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(first_path, preview_path)
        after_reason = _image_repair_reason(preview_path, self._MIN_STORYBOARD_FRAME_BYTES)
        return {
            **repair,
            "source_artifact": str(first_path),
            "after_bytes": preview_path.stat().st_size if preview_path.exists() else 0,
            "after_reason": after_reason,
            "repaired": after_reason is None,
            "method": "copy_first_storyboard_frame",
        }

    def _repair_storyboard_frames(self, op: Operation, run_dir: Path) -> list[dict[str, Any]]:
        repairs = self._storyboard_repairs_needed(op)
        batch_records = self._run_frame_capture_batch_repair(op, run_dir, repairs)
        final_records: list[dict[str, Any]] = []
        for record in batch_records:
            if record.get("repaired"):
                final_records.append(record)
                continue
            fallback_record = self._run_frame_capture_repair(op, run_dir, record)
            fallback_record["batch_attempt"] = {
                "returncode": record.get("returncode"),
                "after_bytes": record.get("after_bytes"),
                "error_type": record.get("error_type"),
                "error_message": record.get("error_message"),
            }
            final_records.append(fallback_record)
        return final_records

    def _build_sequence_preview(self, op: Operation) -> dict[str, Any]:
        if op.type != "render.preview" or not op.inputs.get("output_dir"):
            return {"created": False, "reason": "not_render_preview", "artifact_name": "sequence_preview.gif"}
        output_dir = Path(str(op.inputs["output_dir"]))
        return _write_sequence_preview_gif(output_dir, output_dir / "storyboard_manifest.json")

    def _build_sequence_preview_mp4(self, op: Operation) -> dict[str, Any]:
        if op.type != "render.preview" or not op.inputs.get("output_dir"):
            return {"created": False, "reason": "not_render_preview", "artifact_name": "sequence_preview.mp4"}
        if op.inputs.get("format") != "mp4":
            return {"created": False, "reason": "not_requested", "artifact_name": "sequence_preview.mp4"}
        output_dir = Path(str(op.inputs["output_dir"]))
        storyboard_manifest = output_dir / "storyboard_manifest.json"
        preview_manifest = output_dir / "preview_manifest.json"
        storyboard = read_json(storyboard_manifest, default={}) if storyboard_manifest.exists() else {}
        preview = read_json(preview_manifest, default={}) if preview_manifest.exists() else {}
        if _is_movie_frame_render_backend(storyboard.get("render_backend")) or _is_movie_frame_render_backend(preview.get("render_backend")):
            movie_dir_value = storyboard.get("movie_frame_dir") or preview.get("movie_frame_dir") or output_dir / "movie_frames"
            movie_dir = Path(str(movie_dir_value))
            if not movie_dir.is_absolute():
                movie_dir = output_dir / movie_dir
            fps = op.inputs.get("fps", preview.get("fps", storyboard.get("fps", 12)))
            output_frame_count = None
            output_start = op.inputs.get("start_frame")
            output_end = op.inputs.get("end_frame")
            if output_start is not None and output_end is not None:
                output_frame_count = max(0, int(output_end) - int(output_start))
            output_frame_map = storyboard.get("movie_render_pipeline_output_frame_map") or preview.get("movie_render_pipeline_output_frame_map")
            if isinstance(output_frame_map, list) and output_frame_map:
                source_paths: list[Path] = []
                skipped: list[dict[str, Any]] = []
                for index, item in enumerate(output_frame_map):
                    if not isinstance(item, dict):
                        skipped.append({"index": index, "reason": "frame_map_entry_invalid"})
                        continue
                    file_name = item.get("file_name")
                    output_frame = item.get("output_frame")
                    path = movie_dir / str(file_name) if file_name else self._native_movie_frame_path(movie_dir, int(output_frame))
                    reason = _image_repair_reason(path, min_bytes=1)
                    if reason is None:
                        source_paths.append(path)
                    else:
                        skipped.append({"index": index, "frame": output_frame, "path": str(path), "reason": reason})
                result = _write_movie_frame_paths_mp4(
                    output_dir,
                    source_paths,
                    int(fps),
                    skipped=skipped,
                    output_frame_count=output_frame_count,
                    frame_map_used=True,
                )
                if result.get("created") or result.get("reason") != "no_movie_frames":
                    return result
            frame_range = storyboard.get("native_capture_frame_range") or preview.get("native_capture_frame_range")
            start_frame = frame_range[0] if isinstance(frame_range, list) and len(frame_range) == 2 else op.inputs.get("native_capture_start_frame")
            end_frame = frame_range[1] if isinstance(frame_range, list) and len(frame_range) == 2 else op.inputs.get("native_capture_end_frame")
            if start_frame is None:
                start_frame = preview.get("start_frame", storyboard.get("start_frame"))
            if end_frame is None:
                end_frame = preview.get("end_frame", storyboard.get("end_frame"))
            if start_frame is not None and end_frame is not None:
                result = _write_movie_frame_sequence_mp4(output_dir, movie_dir, int(start_frame), int(end_frame), int(fps), output_frame_count)
                if result.get("created") or result.get("reason") != "no_movie_frames":
                    return result
        return _write_sequence_preview_mp4(output_dir, storyboard_manifest)

    def _sync_render_artifacts_to_state(
        self,
        op: Operation,
        run_dir: Path,
        unreal_result: dict[str, Any] | None,
        extra_artifacts: dict[str, str],
        sequence_preview: dict[str, Any] | None = None,
        sequence_preview_mp4: dict[str, Any] | None = None,
    ) -> None:
        if op.type != "render.preview":
            return
        state = self.load_state(run_dir)
        output = (unreal_result or {}).get("output") or {}
        renders = state.setdefault("renders", [])
        if renders:
            render = renders[-1]
        else:
            render = {
                "sequence_path": op.inputs.get("sequence_path"),
                "quality": op.inputs.get("quality"),
                "preview_camera": output.get("preview_camera"),
                "preview_shot_id": output.get("preview_shot_id"),
                "preview_frame": output.get("preview_frame"),
                "artifacts": {},
            }
            renders.append(render)
        render.setdefault("artifacts", {}).update(output.get("artifacts", {}))
        render["artifacts"].update(extra_artifacts)
        if sequence_preview is not None:
            render["sequence_preview"] = sequence_preview
        if sequence_preview_mp4 is not None:
            render["sequence_preview_mp4"] = sequence_preview_mp4
        if output.get("preview_camera") and not render.get("preview_camera"):
            render["preview_camera"] = output.get("preview_camera")
        if output.get("preview_shot_id") and not render.get("preview_shot_id"):
            render["preview_shot_id"] = output.get("preview_shot_id")
        if output.get("preview_frame") is not None and render.get("preview_frame") is None:
            render["preview_frame"] = output.get("preview_frame")
        atomic_write_json(self.state_path(run_dir), state)

    def _execute_reference_capture_render(self, op: Operation, run_dir: Path) -> ExecutionResult:
        try:
            render_record = self._render_reference_capture_artifacts(op, run_dir)
            result_payload = {"ok": True, "output": render_record}
            atomic_write_json(self._result_path(op, run_dir), result_payload)
            return ExecutionResult(
                ok=True,
                op_id=op.op_id,
                status="success",
                result={
                    "reference_capture": {
                        "source_capture_path": render_record.get("source_capture_path"),
                        "source_frame_range": render_record.get("source_frame_range"),
                        "movie_frame_count": render_record.get("movie_frame_count"),
                    },
                    "sequence_preview": render_record.get("sequence_preview"),
                    "sequence_preview_mp4": render_record.get("sequence_preview_mp4"),
                    "unreal_result": result_payload,
                },
            )
        except Exception as exc:  # noqa: BLE001
            return ExecutionResult(
                ok=False,
                op_id=op.op_id,
                status="failed",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

    def _render_reference_capture_artifacts(self, op: Operation, run_dir: Path) -> dict[str, Any]:
        source = Path(str(op.inputs["reference_capture_source"]))
        if not source.exists():
            raise FileNotFoundError(f"reference capture not found: {source}")
        imageio = importlib.import_module("imageio.v2")

        state = self.load_state(run_dir)
        sequence_path = str(op.inputs["sequence_path"])
        sequence = state.get("sequences", {}).get(sequence_path, {})
        out = Path(str(op.inputs["output_dir"]))
        out.mkdir(parents=True, exist_ok=True)
        movie_dir = out / "movie_frames"
        movie_dir.mkdir(parents=True, exist_ok=True)
        for old in movie_dir.glob("movie_frame_*.png"):
            try:
                old.unlink()
            except OSError:
                pass

        width, height = [int(value) for value in op.inputs.get("resolution", [1280, 720])]
        start_frame = int(op.inputs.get("start_frame", sequence.get("range", [0, 1])[0]) or 0)
        end_frame = int(op.inputs.get("end_frame", sequence.get("range", [start_frame, start_frame + 1])[1]) or start_frame + 1)
        output_count = max(1, end_frame - start_frame)
        source_start = int(op.inputs.get("reference_capture_start_frame", 0) or 0)
        source_end = int(op.inputs.get("reference_capture_end_frame", source_start + output_count - 1) or source_start)
        fps = int(op.inputs.get("fps", sequence.get("fps", 24)) or 24)

        reader = imageio.get_reader(str(source))
        try:
            source_frames = self._reference_capture_source_frames(source_start, source_end, output_count)
            for offset, source_frame in enumerate(source_frames):
                image = Image.fromarray(reader.get_data(int(source_frame))).convert("RGB")
                if image.size != (width, height):
                    image = image.resize((width, height), Image.Resampling.LANCZOS)
                output_frame = start_frame + offset
                image.save(movie_dir / f"movie_frame_{output_frame:04d}.png")
        finally:
            close = getattr(reader, "close", None)
            if close is not None:
                close()

        storyboard_frames = self._reference_capture_storyboard_frames(sequence, out, movie_dir, start_frame, end_frame)
        preview_frame = out / "preview_frame.png"
        if storyboard_frames:
            shutil.copyfile(Path(str(storyboard_frames[0]["artifact"])), preview_frame)
        else:
            shutil.copyfile(movie_dir / f"movie_frame_{start_frame:04d}.png", preview_frame)

        preview_camera = storyboard_frames[0].get("camera_name") if storyboard_frames else None
        preview_shot_id = storyboard_frames[0].get("shot_id") if storyboard_frames else None
        preview_frame_number = int(storyboard_frames[0].get("frame", start_frame)) if storyboard_frames else start_frame
        artifacts = {
            "preview_frame.png": str(preview_frame),
            "preview_manifest.json": str(out / "preview_manifest.json"),
            "storyboard_manifest.json": str(out / "storyboard_manifest.json"),
            "movie_frame_dir": str(movie_dir),
        }
        for frame in storyboard_frames:
            artifacts[str(frame["artifact_name"])] = str(frame["artifact"])

        source_asset_id = sequence.get("source_asset_id")
        source_asset_type = sequence.get("source_asset_type")
        common = {
            "sequence_path": sequence_path,
            "resolution": [width, height],
            "render_backend": "reference_capture_video",
            "source_capture_path": str(source),
            "source_frame_range": [source_start, source_end],
            "fps": fps,
            "start_frame": start_frame,
            "end_frame": end_frame,
            "frame_count": output_count,
            "movie_frame_count": len(list(movie_dir.glob("movie_frame_*.png"))),
            "movie_frame_dir": str(movie_dir),
            "source_asset_id": source_asset_id,
            "source_asset_type": source_asset_type,
            "warnings": [],
        }
        atomic_write_json(
            out / "storyboard_manifest.json",
            {
                **common,
                "frames": storyboard_frames,
            },
        )
        atomic_write_json(
            out / "preview_manifest.json",
            {
                **common,
                "format": op.inputs.get("format", "mp4"),
                "quality": op.inputs.get("quality", "preview"),
                "preview_camera": preview_camera,
                "preview_shot_id": preview_shot_id,
                "preview_frame": preview_frame_number,
                "storyboard_frames": storyboard_frames,
                "artifacts": artifacts,
            },
        )
        sequence_preview = _write_sequence_preview_gif(out, out / "storyboard_manifest.json")
        sequence_preview_mp4 = (
            _write_movie_frame_sequence_mp4(out, movie_dir, start_frame, end_frame, fps)
            if op.inputs.get("format") == "mp4"
            else {"created": False, "reason": "not_requested", "artifact_name": "sequence_preview.mp4"}
        )
        if sequence_preview.get("created"):
            artifacts[sequence_preview["artifact_name"]] = sequence_preview["artifact"]
        if sequence_preview_mp4.get("created"):
            artifacts[sequence_preview_mp4["artifact_name"]] = sequence_preview_mp4["artifact"]
        preview_manifest_path = out / "preview_manifest.json"
        preview_manifest = read_json(preview_manifest_path, default={})
        if preview_manifest:
            preview_manifest["artifacts"] = artifacts
            preview_manifest["sequence_preview"] = sequence_preview
            preview_manifest["sequence_preview_mp4"] = sequence_preview_mp4
            atomic_write_json(preview_manifest_path, preview_manifest)

        render_record = {
            **common,
            "quality": op.inputs.get("quality"),
            "preview_camera": preview_camera,
            "preview_shot_id": preview_shot_id,
            "preview_frame": preview_frame_number,
            "storyboard_frames": storyboard_frames,
            "sequence_preview": sequence_preview,
            "sequence_preview_mp4": sequence_preview_mp4,
            "artifacts": artifacts,
        }
        state.setdefault("renders", []).append(render_record)
        atomic_write_json(self.state_path(run_dir), state)
        return render_record

    def _reference_capture_source_frames(self, source_start: int, source_end: int, output_count: int) -> list[int]:
        if output_count <= 1:
            return [source_start]
        span = source_end - source_start
        return [int(round(source_start + span * (index / (output_count - 1)))) for index in range(output_count)]

    def _reference_capture_storyboard_frames(
        self,
        sequence: dict[str, Any],
        out: Path,
        movie_dir: Path,
        start_frame: int,
        end_frame: int,
    ) -> list[dict[str, Any]]:
        cuts = sorted(sequence.get("camera_cuts", []), key=lambda item: item.get("start_frame", start_frame))
        cut = cuts[0] if cuts else {}
        camera_name = cut.get("camera_name") or "NativeSequenceCamera"
        shot_id = cut.get("shot_id") or "existing_sequence"
        records: list[dict[str, Any]] = []
        for index, frame in enumerate(_storyboard_sample_frames(start_frame, end_frame)[:_MAX_STORYBOARD_SAMPLES]):
            name = f"storyboard_{index:03d}.png"
            source = movie_dir / f"movie_frame_{int(frame):04d}.png"
            destination = out / name
            shutil.copyfile(source, destination)
            records.append(
                {
                    "camera_name": camera_name,
                    "shot_id": shot_id,
                    "frame": int(frame),
                    "artifact": str(destination),
                    "artifact_name": name,
                }
            )
        return records

    def _reference_capture_available(self, op: Operation) -> bool:
        source_value = op.inputs.get("reference_capture_source")
        if not source_value:
            return False
        source = Path(str(source_value))
        if not source.exists():
            return False
        try:
            imageio = importlib.import_module("imageio.v2")
            reader = imageio.get_reader(str(source))
            start = max(0, int(op.inputs.get("reference_capture_start_frame", 0) or 0))
            end = max(start, int(op.inputs.get("reference_capture_end_frame", start) or start))
            reader.get_data(start)
            if end != start:
                reader.get_data(end)
            return True
        except Exception:  # noqa: BLE001
            return False
        finally:
            close = locals().get("reader")
            if close is not None:
                reader_close = getattr(close, "close", None)
                if reader_close is not None:
                    reader_close()

    def _should_use_reference_capture_render(self, op: Operation) -> bool:
        if op.type != "render.preview":
            return False
        requested_backend = str(op.inputs.get("render_backend") or op.inputs.get("capture_backend") or "").strip().lower()
        if requested_backend in {"movie_render_pipeline", "movie_render_queue", "mrq"}:
            return False
        quality = str(op.inputs.get("quality") or "preview").strip().lower()
        if quality == "final":
            return False
        return self._reference_capture_available(op)

    def execute(self, op: Operation, script: str, run_dir: Path) -> ExecutionResult:
        run_dir = Path(run_dir).resolve()
        script_path = run_dir / "scripts" / f"{op.op_id}.py"
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(script, encoding="utf-8")
        if self._should_use_reference_capture_render(op):
            return self._execute_reference_capture_render(op, run_dir)
        bootstrap_path = self._write_executor_bootstrap(op, script_path, run_dir)
        cmd = self._unreal_cmd_for_script(bootstrap_path)
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout_sec, check=False)
            unreal_result = self._read_unreal_result(op, run_dir)
            unreal_ok = bool(unreal_result.get("ok")) if unreal_result is not None else False
            ok = proc.returncode == 0 and unreal_ok
            diagnostics = {"returncode": proc.returncode, "cmd": cmd, "unreal_result": unreal_result}
            if ok:
                native_movie_finalization = self._finalize_native_movie_capture_artifacts(op)
                storyboard_repairs = self._repair_storyboard_frames(op, run_dir)
                preview_repairs = self._repair_preview_frame(op, run_dir)
                sequence_preview = self._build_sequence_preview(op)
                sequence_preview_mp4 = self._build_sequence_preview_mp4(op)
                extra_artifacts = {}
                if sequence_preview.get("created"):
                    extra_artifacts[sequence_preview["artifact_name"]] = sequence_preview["artifact"]
                if sequence_preview_mp4.get("created"):
                    extra_artifacts[sequence_preview_mp4["artifact_name"]] = sequence_preview_mp4["artifact"]
                self._sync_render_artifacts_to_state(op, run_dir, unreal_result, extra_artifacts, sequence_preview, sequence_preview_mp4)
                diagnostics["native_movie_finalization"] = native_movie_finalization
                diagnostics["preview_repairs"] = preview_repairs
                diagnostics["storyboard_repairs"] = storyboard_repairs
                diagnostics["sequence_preview"] = sequence_preview
                diagnostics["sequence_preview_mp4"] = sequence_preview_mp4
                failed_repairs = [record for record in preview_repairs + storyboard_repairs if not record.get("repaired")]
                mp4_required = op.type == "render.preview" and op.inputs.get("format") == "mp4"
                if failed_repairs or (op.type == "render.preview" and not sequence_preview.get("created")) or (mp4_required and not sequence_preview_mp4.get("created")):
                    return ExecutionResult(
                        ok=False,
                        op_id=op.op_id,
                        status="failed",
                        result=diagnostics,
                        error_type="UE_RENDER_ARTIFACT_REPAIR_FAILED",
                        error_message="Unreal frame recapture did not produce valid image files",
                        stdout=proc.stdout,
                        stderr=proc.stderr,
                    )
                return ExecutionResult(ok=True, op_id=op.op_id, status="success", result=diagnostics, stdout=proc.stdout, stderr=proc.stderr)
            error = None
            if unreal_result and unreal_result.get("error"):
                error = unreal_result["error"]
            return ExecutionResult(
                ok=False,
                op_id=op.op_id,
                status="failed",
                result=diagnostics,
                error_type=(error or {}).get("type", "UE_COMMAND_FAILED"),
                error_message=(error or {}).get("message", f"Unreal command returned {proc.returncode}"),
                stdout=proc.stdout,
                stderr=proc.stderr,
            )
        except subprocess.TimeoutExpired as exc:
            return ExecutionResult(ok=False, op_id=op.op_id, status="failed", error_type="UE_EXECUTION_TIMEOUT", error_message=str(exc))
