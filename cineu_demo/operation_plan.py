from __future__ import annotations

from collections import Counter
from typing import Iterable

from .schemas import Operation, VerificationCheck, VerificationReport


def _slug(op: Operation) -> str:
    if op.type.startswith("camera."):
        return f"camera_{op.inputs.get('shot_id', 'shot')}"
    mapping = {
        "env.setup": "env_setup",
        "asset.import_many": "asset_import",
        "entity.spawn_many": "entity_spawn",
        "spatial.apply_transforms": "spatial_place",
        "sequence.init": "sequence_init",
        "sequence.use_existing": "sequence_use_existing",
        "transform.add_tracks": "transform_tracks",
        "animation.add_tracks": "animation_tracks",
        "sequence.camera_cut": "camera_cut",
        "render.preview": "render_preview",
    }
    return mapping.get(op.type, op.type.replace(".", "_"))


def renumber_operations(ops: Iterable[Operation]) -> list[Operation]:
    """Assign stable sequential operation ids after planning.

    Agents produce logical operations independently. This final pass prevents id
    collisions when the number of shots or optional transform/animation tracks
    changes. It preserves all operation semantics and only rewrites op_id.
    """
    result: list[Operation] = []
    seen_slugs: Counter[str] = Counter()
    for idx, op in enumerate(ops, start=1):
        patched = op.model_copy(deep=True)
        base = _slug(patched)
        seen_slugs[base] += 1
        suffix = base if seen_slugs[base] == 1 else f"{base}_{seen_slugs[base]}"
        patched.op_id = f"{idx:04d}_{suffix}"
        result.append(patched)
    return result


class OperationPlanVerifier:
    """Deterministic linting for operation plans before execution."""

    def verify(self, ops: list[Operation]) -> VerificationReport:
        checks: list[VerificationCheck] = []
        ids = [op.op_id for op in ops]
        unique_ids = len(ids) == len(set(ids))
        checks.append(
            VerificationCheck(
                name="operation_ids_unique",
                passed=unique_ids,
                expected=len(ids),
                actual=len(set(ids)),
            )
        )
        checks.append(
            VerificationCheck(
                name="operation_count_positive",
                passed=len(ops) > 0,
                actual=len(ops),
            )
        )
        # Coarse ordering invariants. These are independent of op ids.
        type_index = {op.type: i for i, op in enumerate(ops)}
        ordering = [
            ("asset.import_many", "env.setup"),
            ("asset.import_many", "entity.spawn_many"),
            ("env.setup", "entity.spawn_many"),
            ("entity.spawn_many", "spatial.apply_transforms"),
            ("spatial.apply_transforms", "sequence.init"),
            ("env.setup", "sequence.use_existing"),
            ("sequence.use_existing", "render.preview"),
            ("sequence.init", "sequence.camera_cut"),
            ("sequence.camera_cut", "render.preview"),
        ]
        for before, after in ordering:
            if before in type_index and after in type_index:
                checks.append(
                    VerificationCheck(
                        name=f"order:{before}<={after}",
                        passed=type_index[before] < type_index[after],
                        actual=[type_index[before], type_index[after]],
                    )
                )
        env_ops = [op for op in ops if op.type == "env.setup"]
        for op in env_ops:
            environment_asset = op.inputs.get("environment_asset")
            checks.append(
                VerificationCheck(
                    name="env_setup:environment_asset_required",
                    passed=bool(
                        isinstance(environment_asset, dict)
                        and environment_asset.get("asset_id")
                        and environment_asset.get("ue_path")
                    ),
                    actual=environment_asset,
                )
            )
        spawn_ops = [op for op in ops if op.type == "entity.spawn_many"]
        for op in spawn_ops:
            actors = op.inputs.get("actors", [])
            unresolved = [
                actor.get("actor_name")
                for actor in actors
                if not actor.get("asset_id") or not actor.get("asset_path")
            ]
            placeholder = [
                actor.get("actor_name")
                for actor in actors
                if str(actor.get("source_type", "")).lower() in {"metadata_placeholder", "generated_proxy"}
                or "fallback" in str(actor.get("asset_id", "")).lower()
            ]
            checks.append(
                VerificationCheck(
                    name="entity_spawn:primary_assets_required",
                    passed=not unresolved and not placeholder,
                    actual={"unresolved": unresolved, "placeholder": placeholder},
                )
            )
        # Optional temporal tracks must be after sequence initialization and before camera cuts.
        for optional in ("transform.add_tracks", "animation.add_tracks"):
            if optional in type_index:
                checks.append(
                    VerificationCheck(
                        name=f"order:sequence.init<={optional}",
                        passed=type_index.get("sequence.init", -1) < type_index[optional],
                        actual=[type_index.get("sequence.init"), type_index[optional]],
                    )
                )
                checks.append(
                    VerificationCheck(
                        name=f"order:{optional}<=sequence.camera_cut",
                        passed=type_index[optional] < type_index.get("sequence.camera_cut", 10**9),
                        actual=[type_index[optional], type_index.get("sequence.camera_cut")],
                    )
                )
        passed = all(c.passed for c in checks)
        return VerificationReport(
            op_id="operation_plan",
            stage="plan",
            passed=passed,
            checks=checks,
            diagnostics={} if passed else {"error_type": "OPERATION_PLAN_INVALID", "failed_checks": [c.model_dump(mode="json") for c in checks if not c.passed]},
        )
