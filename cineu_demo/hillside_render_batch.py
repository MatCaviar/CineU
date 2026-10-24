from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .asset_first_scene_plan import build_hillside_scene_plan
from .paths import HILLSIDE_DIAGNOSTIC_ROOT, HILLSIDE_PROJECT_ROOT


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIAGNOSTIC_ROOT = HILLSIDE_DIAGNOSTIC_ROOT
DEFAULT_RENDER_SCRIPT = REPO_ROOT / "scripts" / "unreal" / "build_and_render_hillside_scene.py"
DEFAULT_UNREAL_EDITOR = Path(os.environ.get("CINEU_UNREAL_EDITOR", "UnrealEditor.exe"))
DEFAULT_HILLSIDE_UPROJECT = Path(os.environ.get("CINEU_UPROJECT", str(HILLSIDE_PROJECT_ROOT / "HillsideProject.uproject")))
DEFAULT_LOCAL_ASSET_INDEX = REPO_ROOT / "workspace" / "asset_index" / "local_asset_index.json"


def _safe_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return token.strip("._") or "item"


def _normalize_camera(value: object) -> str:
    token = str(value or "").strip().lower()
    if token.startswith("cineu_"):
        token = token[len("cineu_") :]
    return token


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_local_asset_index(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Local asset index not found: {path}")
    return _load_json(path)


def _scene_plan(scene: str, diagnostic_root: Path, local_asset_index: dict[str, Any] | None) -> dict[str, Any]:
    inventory = _load_json(diagnostic_root / "asset_inventory.json")
    skeletons = _load_json(diagnostic_root / "character_skeletons.json")
    return build_hillside_scene_plan(scene, inventory, skeletons, local_asset_index=local_asset_index)


def _scene_asset_first_evidence(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "scene_id": plan["scene_id"],
        "source_project": plan["source_project"],
        "requirements": plan["requirements"],
        "environment_asset": plan["environment_asset"],
        "asset_index_evidence": plan.get("asset_index_evidence"),
    }


def _powershell_quote(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _write_render_script(path: Path, jobs: list[dict[str, Any]], unreal_editor: Path, uproject: Path, render_script: Path) -> None:
    job_json = json.dumps(jobs, ensure_ascii=False, indent=2)
    lines = [
        "$ErrorActionPreference = 'Stop'",
        f"$unrealEditor = {_powershell_quote(unreal_editor)}",
        f"$uproject = {_powershell_quote(uproject)}",
        f"$renderScript = {_powershell_quote(render_script)}",
        f"$jobs = @'\n{job_json}\n'@ | ConvertFrom-Json",
        "foreach ($job in $jobs) {",
        "  New-Item -ItemType Directory -Path $job.output_dir -Force | Out-Null",
        "  $env:CINEU_HILLSIDE_SCENE = $job.scene",
        "  $env:CINEU_HILLSIDE_CAMERA = $job.camera_name",
        "  $env:CINEU_HILLSIDE_FRAME_COUNT = [string]$job.frame_count",
        "  $env:CINEU_HILLSIDE_WIDTH = [string]$job.resolution[0]",
        "  $env:CINEU_HILLSIDE_HEIGHT = [string]$job.resolution[1]",
        "  $env:CINEU_HILLSIDE_MODE = $job.mode",
        "  $env:CINEU_HILLSIDE_RENDER_QUALITY = $job.render_quality",
        "  $env:CINEU_HILLSIDE_CAPTURE_TIMEOUT = [string]$job.capture_timeout_sec",
        "  $env:CINEU_HILLSIDE_WARMUP = [string]$job.warmup_frames",
        "  $env:CINEU_HILLSIDE_OUTPUT_DIR = $job.output_dir",
        "  $env:CINEU_HILLSIDE_RENDER_BACKEND = $job.render_backend",
        "  Write-Host \"Rendering $($job.scene) / $($job.camera_name) -> $($job.output_dir)\"",
        "  $process = Start-Process -FilePath $unrealEditor -ArgumentList @($uproject, '-unattended', '-nop4', '-nosplash', '-log', \"-ExecutePythonScript=$renderScript\") -WindowStyle Hidden -PassThru",
        "  $frameDir = Join-Path $job.output_dir 'movie_frames'",
        "  $summaryPath = Join-Path $job.output_dir 'build_render_summary.json'",
        "  $deadline = (Get-Date).AddSeconds([double]$job.capture_timeout_sec)",
        "  $frameCount = 0",
        "  $summaryCaptureSuccess = $false",
        "  $summaryCapturePending = $true",
        "  $successSeenAt = $null",
        "  $exitGraceSec = 180",
        "  while ((Get-Date) -lt $deadline) {",
        "    if (Test-Path -LiteralPath $frameDir) {",
        "      $frameCount = @(Get-ChildItem -LiteralPath $frameDir -Filter 'movie_frame_*.png' -ErrorAction SilentlyContinue).Count",
        "    }",
        "    if (Test-Path -LiteralPath $summaryPath) {",
        "      try {",
        "        $summary = Get-Content -LiteralPath $summaryPath -Raw | ConvertFrom-Json",
        "        if ($null -ne $summary.capture_success) { $summaryCaptureSuccess = [bool]$summary.capture_success }",
        "        if ($null -ne $summary.capture_pending) { $summaryCapturePending = [bool]$summary.capture_pending }",
        "        if ($null -ne $summary.render_result) {",
        "          if ($null -ne $summary.render_result.capture_success) { $summaryCaptureSuccess = [bool]$summary.render_result.capture_success }",
        "          if ($null -ne $summary.render_result.capture_pending) { $summaryCapturePending = [bool]$summary.render_result.capture_pending }",
        "        }",
        "      } catch {",
        "        $summaryCaptureSuccess = $false",
        "        $summaryCapturePending = $true",
        "      }",
        "    }",
        "    $process.Refresh()",
        "    if ($frameCount -ge [int]$job.frame_count -and $summaryCaptureSuccess -eq $true -and $summaryCapturePending -eq $false) {",
        "      if ($process.HasExited) { break }",
        "      if ($null -eq $successSeenAt) { $successSeenAt = Get-Date }",
        "      if ((Get-Date) -gt $successSeenAt.AddSeconds($exitGraceSec)) {",
        "        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue",
        "        throw \"UnrealEditor did not exit after successful MRQ summary for $($job.camera_name)\"",
        "      }",
        "    } elseif ($process.HasExited) {",
        "      throw \"UnrealEditor exited before successful MRQ summary for $($job.camera_name): frames $frameCount/$($job.frame_count), capture_success=$summaryCaptureSuccess, capture_pending=$summaryCapturePending\"",
        "    }",
        "    Start-Sleep -Seconds 5",
        "  }",
        "  $process.Refresh()",
        "  if ($frameCount -lt [int]$job.frame_count -or $summaryCaptureSuccess -ne $true -or $summaryCapturePending -ne $false -or -not $process.HasExited) {",
        "    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue",
        "    throw \"Timed out waiting for successful MRQ summary for $($job.camera_name): frames $frameCount/$($job.frame_count), capture_success=$summaryCaptureSuccess, capture_pending=$summaryCapturePending\"",
        "  }",
        "}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def build_hillside_render_batch(
    *,
    scenes: Iterable[str],
    output_root: Path,
    unreal_editor: Path = DEFAULT_UNREAL_EDITOR,
    uproject: Path = DEFAULT_HILLSIDE_UPROJECT,
    render_script: Path = DEFAULT_RENDER_SCRIPT,
    diagnostic_root: Path = DEFAULT_DIAGNOSTIC_ROOT,
    frame_count: int = 1440,
    width: int = 1280,
    height: int = 720,
    mode: str = "final_v4_sync60",
    render_backend: str = "movie_render_pipeline",
    render_quality: str = "cinematic",
    capture_timeout_sec: int = 7200,
    warmup_frames: int = 4,
    local_asset_index_path: Path | None = DEFAULT_LOCAL_ASSET_INDEX,
    cameras: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Write a dry-run render batch manifest and PowerShell script for Hillside scenes."""
    scene_list = [scene.strip().lower() for scene in scenes if scene.strip()]
    if not scene_list:
        raise ValueError("At least one scene is required")
    requested_cameras = {_normalize_camera(camera) for camera in (cameras or []) if str(camera).strip()}
    matched_cameras: set[str] = set()
    local_asset_index = _load_local_asset_index(local_asset_index_path)
    output_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    jobs: list[dict[str, Any]] = []
    scene_evidence: dict[str, Any] = {}
    for scene in scene_list:
        plan = _scene_plan(scene, diagnostic_root, local_asset_index)
        scene_evidence[scene] = _scene_asset_first_evidence(plan)
        for shot in plan["shots"]:
            camera_name = str(shot["camera_name"])
            camera_keys = {
                _normalize_camera(camera_name),
                _normalize_camera(shot.get("shot_id")),
                _normalize_camera(shot.get("type")),
            }
            if requested_cameras and not (camera_keys & requested_cameras):
                continue
            matched_cameras.update(camera_keys & requested_cameras)
            job_output = output_root / f"{scene}_{_safe_token(camera_name)}_{stamp}"
            jobs.append(
                {
                    "scene": scene,
                    "shot_id": str(shot["shot_id"]),
                    "camera_name": camera_name,
                    "camera_type": str(shot["type"]),
                    "output_dir": str(job_output.resolve()),
                    "frame_count": int(frame_count),
                    "fps": int(plan["render"]["fps"]),
                    "resolution": [int(width), int(height)],
                    "mode": mode,
                    "render_backend": render_backend,
                    "render_quality": render_quality,
                    "capture_timeout_sec": int(capture_timeout_sec),
                    "warmup_frames": int(warmup_frames),
                }
            )
    if requested_cameras and not jobs:
        raise ValueError(f"No Hillside render cameras matched: {sorted(requested_cameras)}")
    missing_cameras = requested_cameras - matched_cameras
    if missing_cameras:
        raise ValueError(f"No Hillside render cameras matched: {sorted(missing_cameras)}")
    manifest = {
        "schema_version": "cineu.hillside_render_batch.v1",
        "created_at": stamp,
        "scenes": scene_list,
        "camera_filter": sorted(requested_cameras),
        "job_count": len(jobs),
        "unreal_editor": str(Path(unreal_editor).resolve()),
        "uproject": str(Path(uproject).resolve()),
        "render_script": str(Path(render_script).resolve()),
        "asset_first_evidence": {
            "schema_version": "cineu.hillside_render_batch_asset_first_evidence.v1",
            "local_asset_index": str(Path(local_asset_index_path).resolve()) if local_asset_index_path is not None else None,
            "scenes": scene_evidence,
        },
        "jobs": jobs,
    }
    manifest_path = output_root / "render_batch_manifest.json"
    script_path = output_root / "render_all_hillside.ps1"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_render_script(script_path, jobs, Path(unreal_editor).resolve(), Path(uproject).resolve(), Path(render_script).resolve())
    return {
        "output_root": str(output_root.resolve()),
        "manifest": str(manifest_path.resolve()),
        "script": str(script_path.resolve()),
        "job_count": len(jobs),
        "scenes": scene_list,
    }
