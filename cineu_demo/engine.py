from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agents import AnimAgent, AssetAgent, CamAgent, EntityAgent, EnvAgent, RenderAgent, RunContext, SeqAgent, SpatialAgent, TransAgent
from .asset_store import AssetStore
from .codegen import CodeAssembler, StaticVerifier
from .ledger import FileLedger, atomic_write_json, make_run_id, utc_now_iso
from .local_asset_index import asset_first_preflight_report, build_run_asset_index_snapshot
from .operation_plan import OperationPlanVerifier, renumber_operations
from .paths import DEFAULT_KNOWLEDGE_DIR, DEFAULT_WORKSPACE, asset_cache_path, project_dir
from .planner import RuleBasedPlanner
from .preflight import PreconditionVerifier
from .reflection import MinimalReflection
from .runner import MockRunner, Runner, UnrealCommandRunner, initial_world_state
from .schemas import AssetMetadata, ExecutionResult, Operation, RunManifest, RunnerMode, VerificationReport
from .state_verifier import StateVerifier
from .template_store import TemplateStore


class CineUOrchestrator:
    def __init__(
        self,
        workspace: Path = DEFAULT_WORKSPACE,
        knowledge_dir: Path = DEFAULT_KNOWLEDGE_DIR,
        runner: Runner | None = None,
    ):
        self.workspace = Path(workspace)
        self.knowledge_dir = Path(knowledge_dir)
        self.runner = runner or MockRunner()
        self.planner = RuleBasedPlanner()
        self.assembler = CodeAssembler()
        self.static_verifier = StaticVerifier()
        self.precondition_verifier = PreconditionVerifier()
        self.operation_plan_verifier = OperationPlanVerifier()
        self.state_verifier = StateVerifier()
        self.reflection = MinimalReflection()

    def run(self, prompt: str, project_id: str = "demo_project", max_reflection_iters: int = 3) -> Path:
        run_id = make_run_id()
        ledger = FileLedger(self.workspace, run_id)
        ledger.append_event("run_created", run_id=run_id, project_id=project_id)
        ledger.update_status(run_id=run_id, project_id=project_id, status="created", progress=0.0)
        ledger.write_text("prompt.txt", prompt)
        manifest = RunManifest(run_id=run_id, project_id=project_id, prompt_file="prompt.txt", created_at=utc_now_iso())
        ledger.write_json("manifest.json", manifest.model_dump(mode="json"))

        task, dag, risks = self.planner.plan(prompt, project_id=project_id)
        ledger.update_status(status="planning", progress=0.05)
        ledger.write_json("planning/task_spec.json", task.model_dump(mode="json"))
        ledger.write_json("planning/dag.json", dag.model_dump(mode="json"))
        ledger.write_json("planning/risks.json", {"risks": risks})
        ledger.append_event("planning_complete", task_id=task.task_id, dag_nodes=len(dag.nodes))

        assets_path = asset_cache_path(self.workspace, project_id)
        asset_store = AssetStore(assets_path, include_global_libraries=True)
        template_store = TemplateStore(self.knowledge_dir / "templates")
        ctx = RunContext(
            run_id=run_id,
            workspace=self.workspace,
            project_id=project_id,
            project_dir=project_dir(self.workspace, project_id),
            knowledge_dir=self.knowledge_dir,
            ledger=ledger,
            asset_store=asset_store,
            template_store=template_store,
            task=task,
        )
        snapshot = self._write_asset_index_snapshot(ctx)
        preflight = self._write_asset_first_preflight(ctx, snapshot)
        if not preflight["passed"]:
            ledger.update_status(status="failed", progress=1.0)
            ledger.append_event("asset_first_preflight_failed", diagnostics=preflight["diagnostics"], checks=preflight["checks"])
            self._write_final_report(ledger, success=False)
            return ledger.run_dir

        try:
            operations = self._build_operations(ctx)
        except LookupError as exc:
            ledger.update_status(status="failed", progress=1.0)
            ledger.append_event("asset_resolution_failed", error_type=type(exc).__name__, message=str(exc))
            self._write_final_report(ledger, success=False)
            return ledger.run_dir
        plan_report = self.operation_plan_verifier.verify(operations)
        ledger.append_verification("plan", plan_report.model_dump(mode="json"))
        ledger.write_json("planning/operations_plan.json", {"operations": [op.model_dump(mode="json") for op in operations]})
        if not plan_report.passed:
            ledger.update_status(status="failed", progress=1.0)
            ledger.append_event("operation_plan_failed", diagnostics=plan_report.diagnostics)
            self._write_final_report(ledger, success=False)
            return ledger.run_dir

        ledger.update_status(status="executing", total_operations=len(operations), progress=0.10)

        atomic_write_json(ledger.run_dir / "snapshots" / "world_current.json", initial_world_state())
        completed = 0
        for op in operations:
            ok = self._execute_with_reflection(op, ctx, max_reflection_iters=max_reflection_iters)
            completed += 1
            ledger.update_status(current_op=op.op_id, completed_operations=completed, progress=0.10 + 0.85 * completed / max(1, len(operations)))
            if not ok:
                final = self.runner.load_state(ledger.run_dir)
                ledger.save_snapshot("world_final", final)
                ledger.update_status(status="failed", progress=1.0)
                ledger.append_event("run_failed", failed_op=op.op_id)
                self._write_final_report(ledger, success=False)
                return ledger.run_dir

        final_state = self.runner.load_state(ledger.run_dir)
        ledger.save_snapshot("world_final", final_state)
        ledger.update_status(status="success", progress=1.0)
        ledger.append_event("run_success", run_id=run_id)
        self._write_final_report(ledger, success=True)
        return ledger.run_dir

    def _build_operations(self, ctx: RunContext) -> list[Operation]:
        asset_agent = AssetAgent()
        environment_asset = asset_agent.retrieve_environment(ctx)
        dressing_assets = asset_agent.retrieve_environment_dressing(ctx)
        entity_agent = EntityAgent()
        asset_map = entity_agent.retrieve(ctx)
        animation_assets = asset_agent.retrieve_animations(ctx)
        sequence_assets = asset_agent.retrieve_sequences(ctx)
        reference_sequence = self._reference_sequence_for_task(ctx, sequence_assets)
        asset_import = asset_agent.build_import(ctx, asset_map, environment_asset, animation_assets, sequence_assets, dressing_assets)
        env = EnvAgent().build(ctx)
        if reference_sequence is not None:
            shot_id, sequence_asset = reference_sequence
            seq_use = SeqAgent().build_use_existing(ctx, shot_id, sequence_asset)
            render = RenderAgent().build(ctx)
            ops = []
            if asset_import is not None:
                ops.append(asset_import)
            ops.extend([env, seq_use, render])
            return renumber_operations(ops)
        spawn = entity_agent.build_spawn(ctx, asset_map)
        spatial = SpatialAgent().build(ctx, asset_map)
        seq_init = SeqAgent().build_init(ctx)
        transform_op = TransAgent().build(ctx)
        camera_ops = CamAgent().build(ctx)
        anim_op = AnimAgent().build(ctx)
        cut = SeqAgent().build_camera_cut(ctx, camera_ops)
        render = RenderAgent().build(ctx)
        ops = []
        if asset_import is not None:
            ops.append(asset_import)
        ops.append(env)
        ops.extend([spawn, spatial, seq_init])
        if transform_op is not None:
            ops.append(transform_op)
        ops.extend(camera_ops)
        if anim_op is not None:
            ops.append(anim_op)
        ops.extend([cut, render])
        return renumber_operations(ops)

    def _write_asset_index_snapshot(self, ctx: RunContext) -> dict[str, Any]:
        snapshot = build_run_asset_index_snapshot(ctx.asset_store)
        ctx.ledger.write_json("planning/local_asset_index_snapshot.json", snapshot)
        ctx.ledger.append_event(
            "asset_index_snapshot_written",
            asset_count=snapshot["asset_count"],
            asset_first_ready=snapshot["asset_first_ready"],
        )
        return snapshot

    def _write_asset_first_preflight(self, ctx: RunContext, snapshot: dict[str, Any]) -> dict[str, Any]:
        report = asset_first_preflight_report(snapshot, ctx.task.scene.environment)
        ctx.ledger.write_json("planning/asset_first_preflight.json", report)
        ctx.ledger.append_event(
            "asset_first_preflight_passed" if report["passed"] else "asset_first_preflight_checked",
            target_environment=report["target_environment"],
            matched_environment_candidate_count=len(report["matched_environment_candidates"]),
        )
        return report

    def _reference_sequence_for_task(
        self,
        ctx: RunContext,
        sequence_assets: dict[str, AssetMetadata],
    ) -> tuple[str, AssetMetadata] | None:
        if ctx.task.scene.environment.lower() != "park":
            return None
        for shot in ctx.task.camera.shots:
            if shot.type != "hitchcock_zoom":
                continue
            reference_path = str((shot.metadata or {}).get("reference_sequence_path") or "")
            if not reference_path:
                continue
            sequence_asset = sequence_assets.get(shot.id)
            if sequence_asset is not None and sequence_asset.ue_path == reference_path:
                return shot.id, sequence_asset
        return None

    def _execute_with_reflection(self, op: Operation, ctx: RunContext, max_reflection_iters: int) -> bool:
        current_op = op
        for iteration in range(max_reflection_iters + 1):
            ctx.ledger.append_event("operation_started", op_id=current_op.op_id, op_type=current_op.type, iteration=iteration)
            ctx.ledger.write_json(f"operations/{current_op.op_id}.json", current_op.model_dump(mode="json"))
            template = ctx.template_store.get(current_op.template_id)
            run_dir = ctx.ledger.run_dir.resolve()
            script = self.assembler.assemble(
                template,
                current_op,
                context={
                    "run_id": ctx.run_id,
                    "project_id": ctx.project_id,
                    "run_dir": str(run_dir),
                    "world_state_path": str(run_dir / "snapshots" / "world_current.json"),
                },
            )
            ctx.ledger.write_text(f"scripts/{current_op.op_id}.py", script)

            static_report = self.static_verifier.verify(script, current_op, template=template)
            ctx.ledger.append_verification("static", static_report.model_dump(mode="json"))
            if not static_report.passed:
                ctx.ledger.append_event("static_verification_failed", op_id=current_op.op_id, diagnostics=static_report.diagnostics)
                patch = self.reflection.propose_patch(current_op, None, static_report)
                if patch is None or iteration >= max_reflection_iters:
                    return False
                self._record_patch(ctx, current_op, patch, iteration, static_report)
                current_op = patch
                continue

            before = self.runner.load_state(ctx.ledger.run_dir)
            pre_report = self.precondition_verifier.verify(template, current_op, before)
            ctx.ledger.append_verification("precondition", pre_report.model_dump(mode="json"))
            if not pre_report.passed:
                ctx.ledger.append_event("precondition_failed", op_id=current_op.op_id, diagnostics=pre_report.diagnostics)
                patch = self.reflection.propose_patch(current_op, None, pre_report)
                if patch is None or iteration >= max_reflection_iters:
                    return False
                self._record_patch(ctx, current_op, patch, iteration, pre_report)
                current_op = patch
                continue

            ctx.ledger.save_snapshot(f"world_before_{current_op.op_id}_iter{iteration}", before)
            result = self.runner.execute(current_op, script, ctx.ledger.run_dir)
            ctx.ledger.write_json(f"traces/{current_op.op_id}_iter{iteration}_runtime.json", result.model_dump(mode="json"))
            runtime_report = VerificationReport(
                op_id=current_op.op_id,
                stage="runtime",
                passed=result.ok,
                checks=[],
                diagnostics={} if result.ok else {"error_type": result.error_type, "message": result.error_message},
            )
            ctx.ledger.append_verification("runtime", runtime_report.model_dump(mode="json"))
            after = self.runner.load_state(ctx.ledger.run_dir)
            ctx.ledger.save_snapshot(f"world_after_{current_op.op_id}_iter{iteration}", after)
            state_report = self.state_verifier.verify(current_op, after)
            ctx.ledger.append_verification("state", state_report.model_dump(mode="json"))

            if result.ok and state_report.passed:
                ctx.ledger.append_event("operation_success", op_id=current_op.op_id, iteration=iteration)
                return True

            # Restore the last known good snapshot before local patching. This
            # is exact for MockRunner and records the intended transaction
            # boundary for Unreal runner implementations.
            self.runner.restore_state(ctx.ledger.run_dir, before)
            ctx.ledger.append_event(
                "operation_failed",
                op_id=current_op.op_id,
                iteration=iteration,
                runtime_ok=result.ok,
                state_ok=state_report.passed,
                rollback="restored_world_before_snapshot",
                diagnostics={"runtime": runtime_report.diagnostics, "state": state_report.diagnostics},
            )
            if iteration >= max_reflection_iters:
                return False
            patch = self.reflection.propose_patch(current_op, result, state_report)
            if patch is None:
                return False
            self._record_patch(ctx, current_op, patch, iteration, state_report)
            current_op = patch
        return False

    def _record_patch(self, ctx: RunContext, before: Operation, after: Operation, iteration: int, report: VerificationReport) -> None:
        rel = f"reflection/iter_{iteration + 1:03d}"
        ctx.ledger.write_json(f"{rel}/diagnostics.json", report.model_dump(mode="json"))
        ctx.ledger.write_json(f"{rel}/patched_operation.json", after.model_dump(mode="json"))
        diff = {
            "op_id": before.op_id,
            "before": before.model_dump(mode="json"),
            "after": after.model_dump(mode="json"),
        }
        ctx.ledger.write_text(f"{rel}/patch.diff", json.dumps(diff, ensure_ascii=False, indent=2))
        ctx.ledger.append_event("operation_patched", op_id=before.op_id, iteration=iteration)

    def _write_final_report(self, ledger: FileLedger, success: bool) -> None:
        status = json.loads((ledger.run_dir / "status.json").read_text(encoding="utf-8")) if (ledger.run_dir / "status.json").exists() else {}
        final_state_path = ledger.run_dir / "snapshots" / "world_final.json"
        artifacts = sorted(str(p.relative_to(ledger.run_dir)) for p in (ledger.run_dir / "artifacts").glob("*"))
        metrics = self._summarize_run(ledger)
        report = {
            "schema_version": "cineu.final_report.v2",
            "success": success,
            "run_id": ledger.run_id,
            "status": status,
            "metrics": metrics,
            "final_state": str(final_state_path.relative_to(ledger.run_dir)) if final_state_path.exists() else None,
            "artifacts": artifacts,
        }
        ledger.write_json("verification/final_report.json", report)
        try:
            from .reporting import write_run_report

            report_path = write_run_report(ledger.run_dir)
            ledger.append_event("run_report_written", report_path=str(report_path.relative_to(ledger.run_dir)))
        except Exception as exc:  # pragma: no cover - reporting must never mask run status
            ledger.append_event("run_report_failed", error=repr(exc))

    def _summarize_run(self, ledger: FileLedger) -> dict[str, Any]:
        events_path = ledger.run_dir / "traces" / "events.jsonl"
        events = []
        if events_path.exists():
            events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        operation_success = sum(1 for e in events if e.get("event") == "operation_success")
        operation_failed = sum(1 for e in events if e.get("event") == "operation_failed")
        patches = sum(1 for e in events if e.get("event") == "operation_patched")
        return {
            "operation_success_count": operation_success,
            "operation_failed_count": operation_failed,
            "reflection_patch_count": patches,
            "event_count": len(events),
        }


def make_runner(
    mode: str = "mock",
    *,
    unreal_editor_cmd: str | None = None,
    uproject: Path | None = None,
    unreal_timeout_sec: int = 300,
) -> Runner:
    if mode == RunnerMode.mock.value:
        return MockRunner()
    if mode == RunnerMode.unreal.value:
        if not unreal_editor_cmd or not uproject:
            raise ValueError("unreal runner requires unreal_editor_cmd and uproject")
        return UnrealCommandRunner(unreal_editor_cmd=unreal_editor_cmd, uproject=uproject, timeout_sec=unreal_timeout_sec)
    raise ValueError(f"Unknown runner mode: {mode}")
