from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from .audit import audit_run, audit_workspace
from .index import rebuild_run_index
from .schema_export import export_json_schemas
from .system_report import build_system_report
from .doctor import doctor as run_doctor
from .hillside_render_batch import (
    DEFAULT_HILLSIDE_UPROJECT,
    DEFAULT_RENDER_SCRIPT,
    DEFAULT_UNREAL_EDITOR,
    build_hillside_render_batch,
)
from .hillside_render_postprocess import encode_hillside_render_batch
from .reporting import summarize_run, validate_run, write_run_report
from .demo_workspace import create_demo_workspace
from .engine import CineUOrchestrator, make_runner
from .asset_store import AssetStore
from .local_asset_index import build_local_asset_index, write_local_asset_index
from .ledger import atomic_write_json
from .multicamera_review_packager import (
    package_final_manifest_review,
    package_multicamera_review,
    stabilize_final_manifest_from_quality_report,
)
from .paths import DEFAULT_KNOWLEDGE_DIR, DEFAULT_UNREAL_PROJECT, DEFAULT_WORKSPACE
from .required_asset_evidence import build_required_asset_evidence_report, build_required_asset_user_actions_markdown
from .target_asset_links import apply_target_asset_link_plan, build_target_asset_link_plan
from .unreal_discovery import discover_unreal_editor_cmd

app = typer.Typer(help="CineU local-first research-system demo")


@app.command()
def init(
    workspace: Path = typer.Option(DEFAULT_WORKSPACE, help="Workspace root"),
    project_id: str = typer.Option("demo_project", help="Project id"),
    overwrite: bool = typer.Option(False, help="Overwrite existing demo workspace metadata"),
):
    """Create local demo workspace with curated placeholder metadata."""
    project = create_demo_workspace(workspace, project_id=project_id, overwrite=overwrite)
    typer.echo(f"initialized: {project}")


@app.command()
def run(
    prompt: Optional[str] = typer.Option(None, help="Prompt text"),
    prompt_file: Optional[Path] = typer.Option(None, help="Prompt file"),
    workspace: Path = typer.Option(DEFAULT_WORKSPACE, help="Workspace root"),
    knowledge_dir: Path = typer.Option(DEFAULT_KNOWLEDGE_DIR, help="Knowledge/templates root"),
    project_id: str = typer.Option("demo_project", help="Project id"),
    runner_mode: str = typer.Option("mock", help="mock or unreal"),
    unreal_editor_cmd: Optional[str] = typer.Option(None, help="Path to UnrealEditor-Cmd.exe for runner_mode=unreal"),
    uproject: Path = typer.Option(DEFAULT_UNREAL_PROJECT, help="Unreal project path"),
    unreal_timeout_sec: int = typer.Option(900, help="Timeout per Unreal operation in seconds"),
    max_reflection_iters: int = typer.Option(3, help="Max local reflection iterations per operation"),
):
    """Run a prompt through planning, IR, templates, verification and runner."""
    if prompt_file:
        prompt_text = prompt_file.read_text(encoding="utf-8")
    elif prompt:
        prompt_text = prompt
    else:
        raise typer.BadParameter("Either --prompt or --prompt-file must be provided")
    create_demo_workspace(workspace, project_id=project_id, overwrite=False)
    if runner_mode == "unreal" and unreal_editor_cmd is None:
        unreal_editor_cmd = discover_unreal_editor_cmd()
        if unreal_editor_cmd is None:
            raise typer.BadParameter(
                "runner-mode=unreal requires --unreal-editor-cmd when UnrealEditor-Cmd.exe cannot be discovered"
            )
    runner = make_runner(runner_mode, unreal_editor_cmd=unreal_editor_cmd, uproject=uproject, unreal_timeout_sec=unreal_timeout_sec)
    orchestrator = CineUOrchestrator(workspace=workspace, knowledge_dir=knowledge_dir, runner=runner)
    run_dir = orchestrator.run(prompt_text, project_id=project_id, max_reflection_iters=max_reflection_iters)
    typer.echo(str(run_dir))


@app.command()
def benchmark(
    tasks_file: Path = typer.Option(Path("examples/benchmark_tasks.jsonl"), help="JSONL tasks with prompt field"),
    workspace: Path = typer.Option(DEFAULT_WORKSPACE, help="Workspace root"),
    project_id: str = typer.Option("demo_project", help="Project id"),
):
    """Run a small local benchmark in mock mode."""
    create_demo_workspace(workspace, project_id=project_id, overwrite=False)
    orchestrator = CineUOrchestrator(workspace=workspace, knowledge_dir=DEFAULT_KNOWLEDGE_DIR)
    results = []
    for line in tasks_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        task = json.loads(line)
        run_dir = orchestrator.run(task["prompt"], project_id=project_id)
        report = json.loads((run_dir / "verification" / "final_report.json").read_text(encoding="utf-8"))
        results.append({"name": task.get("name"), "run_dir": str(run_dir), "success": report["success"]})
    out_dir = workspace / "benchmark"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "results.jsonl"
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in results) + "\n", encoding="utf-8")
    success = sum(1 for r in results if r["success"])
    summary = {"schema_version": "cineu.benchmark_summary.v1", "task_count": len(results), "success_count": success, "success_rate": success / len(results) if results else None}
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "summary.csv").write_text("task_count,success_count,success_rate\n" + f"{len(results)},{success},{summary['success_rate']}\n", encoding="utf-8")
    typer.echo(f"benchmark complete: {success}/{len(results)} success; results={out}; summary={out_dir / 'summary.json'}")


@app.command()
def audit(
    run_dir: Optional[Path] = typer.Option(None, help="Specific run directory to audit"),
    workspace: Path = typer.Option(DEFAULT_WORKSPACE, help="Workspace root"),
):
    """Summarize run/workspace ledger, verification and artifact status."""
    report = audit_run(run_dir) if run_dir else audit_workspace(workspace)
    typer.echo(json.dumps(report, ensure_ascii=False, indent=2))


@app.command("rebuild-index")
def rebuild_index(
    workspace: Path = typer.Option(DEFAULT_WORKSPACE, help="Workspace root"),
):
    """Rebuild derived local run index from workspace/runs."""
    summary = rebuild_run_index(workspace)
    typer.echo(json.dumps(summary, ensure_ascii=False, indent=2))


@app.command("rebuild-asset-index")
def rebuild_asset_index(
    workspace: Path = typer.Option(DEFAULT_WORKSPACE, help="Workspace root"),
    project_id: str = typer.Option("demo_project", help="Project id"),
    source_dir: Optional[list[Path]] = typer.Option(None, "--source-dir", help="Explicit asset source or UE Content directory"),
    project_root: Optional[list[Path]] = typer.Option(None, "--project-root", help="UE project root used for grouping assets"),
):
    """Rebuild the local asset-first index from discovered UE/Fab/public assets."""
    asset_cache = workspace / "projects" / project_id / "asset_cache"
    asset_cache.mkdir(parents=True, exist_ok=True)
    assets_jsonl = asset_cache / "assets.jsonl"
    if not assets_jsonl.exists():
        assets_jsonl.write_text("", encoding="utf-8")
    store = AssetStore(assets_jsonl, source_dirs=source_dir, include_global_libraries=True)
    index = build_local_asset_index(store, project_roots=project_root)
    written = write_local_asset_index(index, workspace / "asset_index")
    typer.echo(json.dumps(written, ensure_ascii=False, indent=2))


@app.command("required-asset-evidence")
def required_asset_evidence_cmd(
    asset_index: Path = typer.Option(..., "--asset-index", help="local_asset_index.json to audit"),
    output: Optional[Path] = typer.Option(None, "--output", help="Optional JSON report path"),
    user_actions_markdown: Optional[Path] = typer.Option(None, "--user-actions-markdown", help="Optional Markdown action list path"),
    target_project_root: Optional[Path] = typer.Option(None, "--target-project-root", help="Target UE project root for missing Fab imports"),
    summary_only: bool = typer.Option(False, "--summary-only", help="Print a concise summary while still writing full output files"),
):
    """Audit whether user-required Fab, MetaHuman and Mixamo assets are locally evidenced."""
    index = json.loads(asset_index.read_text(encoding="utf-8"))
    report = build_required_asset_evidence_report(index, target_project_root=target_project_root)
    if output:
        atomic_write_json(output, report)
    if user_actions_markdown:
        user_actions_markdown.parent.mkdir(parents=True, exist_ok=True)
        user_actions_markdown.write_text(build_required_asset_user_actions_markdown(report), encoding="utf-8")
    payload = report
    if summary_only:
        action_plan = report.get("user_action_plan") or {}
        payload = {
            "schema_version": report.get("schema_version"),
            "target_project_root": report.get("target_project_root"),
            "passed": report.get("passed"),
            "summary": report.get("summary"),
            "action_count": action_plan.get("action_count", 0),
            "actions": action_plan.get("actions", []),
        }
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


@app.command("target-asset-links")
def target_asset_links_cmd(
    report: Path = typer.Option(..., "--report", help="required_asset_evidence_report.json"),
    output: Optional[Path] = typer.Option(None, "--output", help="Optional target asset link plan/apply JSON path"),
    target_project_root: Optional[Path] = typer.Option(None, "--target-project-root", help="Override target UE project root"),
    dry_run: bool = typer.Option(True, "--dry-run/--apply", help="Dry-run only unless --apply is provided"),
):
    """Plan or create Content directory junctions for locally available required assets."""
    evidence_report = json.loads(report.read_text(encoding="utf-8"))
    plan = build_target_asset_link_plan(evidence_report, target_project_root=target_project_root)
    payload = plan if dry_run else apply_target_asset_link_plan(plan, dry_run=False)
    if output:
        atomic_write_json(output, payload)
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


@app.command("package-review")
def package_review_cmd(
    scene_dir: list[Path] = typer.Option(..., "--scene-dir", help="Scene review directory containing <scene>_manifest.json"),
    output_dir: Path = typer.Option(..., "--output-dir", help="Output review package directory"),
    expected_fps: float = typer.Option(24.0, help="Expected synchronized video FPS"),
    expected_duration_sec: float = typer.Option(60.0, help="Expected synchronized video duration in seconds"),
    expected_width: int | None = typer.Option(None, "--expected-width", help="Expected synchronized video width; requires --expected-height"),
    expected_height: int | None = typer.Option(None, "--expected-height", help="Expected synchronized video height; requires --expected-width"),
    keyframe_index: list[int] = typer.Option(None, "--keyframe-index", help="Frame index to verify/read in each video; repeat for short validation videos"),
    validate_current_plan: bool = typer.Option(False, "--validate-current-plan", help="Reject sources whose world_state camera does not match the current Hillside asset-first plan"),
):
    """Package validated synchronized scene videos into a flat review folder."""
    try:
        expected_resolution = None
        if expected_width is not None or expected_height is not None:
            if expected_width is None or expected_height is None:
                raise ValueError("--expected-width and --expected-height must be provided together")
            expected_resolution = [expected_width, expected_height]
        summary = package_multicamera_review(
            scene_dir,
            output_dir,
            expected_fps=expected_fps,
            expected_duration_sec=expected_duration_sec,
            expected_resolution=expected_resolution,
            keyframe_indexes=keyframe_index or (0, 720, 1439),
            validate_current_plan=validate_current_plan,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(json.dumps(summary, ensure_ascii=False, indent=2))


@app.command("package-final-manifest")
def package_final_manifest_cmd(
    manifest: Path = typer.Option(..., "--manifest", help="Final candidate manifest containing a videos[] list"),
    output_dir: Path = typer.Option(..., "--output-dir", help="Output unified review package directory"),
    expected_fps: float = typer.Option(24.0, help="Expected synchronized video FPS"),
    expected_duration_sec: float = typer.Option(60.0, help="Expected synchronized video duration in seconds"),
    expected_width: int | None = typer.Option(None, "--expected-width", help="Expected synchronized video width; requires --expected-height"),
    expected_height: int | None = typer.Option(None, "--expected-height", help="Expected synchronized video height; requires --expected-width"),
    validate_current_plan: bool = typer.Option(False, "--validate-current-plan", help="Reject sources whose world_state camera does not match the current Hillside asset-first plan"),
):
    """Package a final candidate manifest into flat videos, manifests, and contact sheets."""
    try:
        expected_resolution = None
        if expected_width is not None or expected_height is not None:
            if expected_width is None or expected_height is None:
                raise ValueError("--expected-width and --expected-height must be provided together")
            expected_resolution = [expected_width, expected_height]
        summary = package_final_manifest_review(
            manifest,
            output_dir,
            expected_fps=expected_fps,
            expected_duration_sec=expected_duration_sec,
            expected_resolution=expected_resolution,
            validate_current_plan=validate_current_plan,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(json.dumps(summary, ensure_ascii=False, indent=2))


@app.command("stabilize-final-manifest")
def stabilize_final_manifest_cmd(
    manifest: Path = typer.Option(..., "--manifest", help="Final candidate manifest containing a videos[] list"),
    quality_report: Path = typer.Option(..., "--quality-report", help="quality_report.json with suggested stable start frames"),
    output_dir: Path = typer.Option(..., "--output-dir", help="Output stabilized review package directory"),
    expected_fps: float = typer.Option(24.0, help="Expected synchronized video FPS"),
    expected_duration_sec: float = typer.Option(60.0, help="Expected synchronized video duration in seconds"),
):
    """Re-time videos flagged by a quality report and package the stabilized final candidate."""
    try:
        summary = stabilize_final_manifest_from_quality_report(
            manifest,
            quality_report,
            output_dir,
            expected_fps=expected_fps,
            expected_duration_sec=expected_duration_sec,
        )
    except (RuntimeError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(json.dumps(summary, ensure_ascii=False, indent=2))


@app.command("hillside-render-batch")
def hillside_render_batch_cmd(
    scene: list[str] = typer.Option(..., "--scene", help="Hillside scene id, repeat for multiple scenes"),
    output_root: Path = typer.Option(..., "--output-root", help="Directory for batch manifest and render script"),
    unreal_editor: Path = typer.Option(DEFAULT_UNREAL_EDITOR, help="UnrealEditor.exe path"),
    uproject: Path = typer.Option(DEFAULT_HILLSIDE_UPROJECT, help="HillsideProject .uproject path"),
    render_script: Path = typer.Option(DEFAULT_RENDER_SCRIPT, help="Hillside build/render Python script"),
    frame_count: int = typer.Option(1440, help="Frames per single-camera video"),
    width: int = typer.Option(1280, help="Render width"),
    height: int = typer.Option(720, help="Render height"),
    mode: str = typer.Option("final_v4_sync60", help="CINEU_HILLSIDE_MODE value"),
    camera: list[str] = typer.Option(None, "--camera", help="Optional camera_name, shot_id, or camera type filter; repeat for multiple cameras"),
):
    """Write a dry-run Hillside multicamera render batch manifest and PowerShell script."""
    summary = build_hillside_render_batch(
        scenes=scene,
        output_root=output_root,
        unreal_editor=unreal_editor,
        uproject=uproject,
        render_script=render_script,
        frame_count=frame_count,
        width=width,
        height=height,
        mode=mode,
        cameras=camera,
    )
    typer.echo(json.dumps(summary, ensure_ascii=False, indent=2))


@app.command("hillside-encode-batch")
def hillside_encode_batch_cmd(
    manifest: Path = typer.Option(..., "--manifest", help="render_batch_manifest.json written by hillside-render-batch"),
    output_root: Path = typer.Option(..., "--output-root", help="Output directory for encoded scene mp4 manifests"),
):
    """Encode completed Hillside render batch movie_frames into per-scene mp4 manifests."""
    summary = encode_hillside_render_batch(manifest, output_root)
    typer.echo(json.dumps(summary, ensure_ascii=False, indent=2))


@app.command("export-schemas")
def export_schemas(
    out_dir: Path = typer.Option(Path("workspace/schemas"), help="Output directory for JSON Schema files"),
):
    """Export Pydantic model JSON Schemas for external validators and ablations."""
    written = export_json_schemas(out_dir)
    typer.echo(json.dumps(written, ensure_ascii=False, indent=2))


@app.command("system-report")
def system_report(
    project_root: Path = typer.Option(Path("."), help="Repository root"),
    workspace: Path = typer.Option(DEFAULT_WORKSPACE, help="Workspace root"),
):
    """Create an inventory report for source, templates, Unreal scaffold and runs."""
    report = build_system_report(project_root=project_root, workspace=workspace)
    typer.echo(json.dumps(report, ensure_ascii=False, indent=2))


@app.command("report")
def report_cmd(
    run_dir: Path = typer.Argument(..., help="Run directory"),
):
    """Generate reports/run_report.md, run_summary.json and run_validation.json."""
    typer.echo(str(write_run_report(run_dir)))


@app.command("validate-run")
def validate_run_cmd(
    run_dir: Path = typer.Argument(..., help="Run directory"),
):
    """Validate run ledger completeness and consistency."""
    typer.echo(json.dumps(validate_run(run_dir), ensure_ascii=False, indent=2))


@app.command("summarize-run")
def summarize_run_cmd(
    run_dir: Path = typer.Argument(..., help="Run directory"),
):
    """Print a deterministic summary of one run ledger."""
    typer.echo(json.dumps(summarize_run(run_dir), ensure_ascii=False, indent=2))


@app.command("doctor")
def doctor_cmd(
    workspace: Path = typer.Option(DEFAULT_WORKSPACE, help="Workspace root"),
    knowledge_dir: Path = typer.Option(DEFAULT_KNOWLEDGE_DIR, help="Knowledge/templates root"),
    uproject: Path = typer.Option(DEFAULT_UNREAL_PROJECT, help="Unreal project path"),
):
    """Check local research-system readiness."""
    typer.echo(json.dumps(run_doctor(workspace, knowledge_dir, uproject), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    app()
