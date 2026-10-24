from __future__ import annotations

from pathlib import Path
from typing import Any

from .schemas import Operation, TemplateManifest, VerificationCheck, VerificationReport


def _sequence_exists(state: dict[str, Any], sequence_path: str | None) -> bool:
    if not sequence_path:
        return False
    return sequence_path in state.get("sequences", {})


def _actor_exists(state: dict[str, Any], actor_name: str | None) -> bool:
    if not actor_name or actor_name == "world_origin":
        return True
    return actor_name in state.get("actors", {})


class PreconditionVerifier:
    """Verify template preconditions against the current world-state snapshot.

    This catches semantic failures before launching Unreal or mutating the mock
    state. It is intentionally conservative and operation-aware.
    """

    def verify(self, template: TemplateManifest, op: Operation, state: dict[str, Any]) -> VerificationReport:
        checks: list[VerificationCheck] = []
        for precondition in template.preconditions:
            name = str(precondition)
            if name == "sequence_exists":
                seq_path = op.inputs.get("sequence_path")
                checks.append(VerificationCheck(name="pre:sequence_exists", passed=_sequence_exists(state, seq_path), actual=seq_path))
            elif name == "target_actor_exists":
                target = op.inputs.get("target_actor")
                checks.append(VerificationCheck(name="pre:target_actor_exists", passed=_actor_exists(state, target), actual=target))
            elif name == "actors_exist":
                actors = self._actors_referenced_by_operation(op)
                missing = [a for a in actors if not _actor_exists(state, a)]
                checks.append(VerificationCheck(name="pre:actors_exist", passed=not missing, actual={"actors": actors, "missing": missing}))
            elif name == "cameras_exist":
                cameras = [c.get("camera_name") for c in op.inputs.get("cuts", [])]
                missing = [c for c in cameras if not _actor_exists(state, c)]
                checks.append(VerificationCheck(name="pre:cameras_exist", passed=not missing, actual={"cameras": cameras, "missing": missing}))
            elif name == "assets_resolved":
                actors = op.inputs.get("actors", [])
                unresolved = [a.get("actor_name") for a in actors if not a.get("asset_path") or not a.get("asset_id")]
                checks.append(VerificationCheck(name="pre:assets_resolved", passed=not unresolved, actual={"unresolved": unresolved}))
            elif name == "source_assets_exist":
                assets = op.inputs.get("assets", [])
                missing = [
                    asset.get("asset_id")
                    for asset in assets
                    if asset.get("import_required") and (not asset.get("source_path") or not Path(str(asset.get("source_path"))).exists())
                ]
                checks.append(VerificationCheck(name="pre:source_assets_exist", passed=not missing, actual={"missing": missing}))
            elif name == "camera_cut_track_exists":
                seq = state.get("sequences", {}).get(op.inputs.get("sequence_path"), {})
                passed = bool(seq.get("camera_cuts"))
                checks.append(VerificationCheck(name="pre:camera_cut_track_exists", passed=passed, actual=seq.get("camera_cuts", [])))
            else:
                checks.append(VerificationCheck(name=f"pre:unknown:{name}", passed=True, message="Unknown precondition treated as advisory."))
        passed = all(c.passed for c in checks)
        return VerificationReport(
            op_id=op.op_id,
            stage="precondition",
            passed=passed,
            checks=checks,
            diagnostics={} if passed else {"error_type": "PRECONDITION_FAILED", "failed_checks": [c.model_dump(mode="json") for c in checks if not c.passed]},
        )

    def _actors_referenced_by_operation(self, op: Operation) -> list[str]:
        if op.type == "spatial.apply_transforms":
            return [p.get("actor_name") for p in op.inputs.get("placements", []) if p.get("actor_name")]
        if op.type == "animation.add_tracks":
            return [c.get("actor_name") for c in op.inputs.get("clips", []) if c.get("actor_name")]
        if op.type == "transform.add_tracks":
            return [t.get("actor_name") for t in op.inputs.get("tracks", []) if t.get("actor_name")]
        if op.type.startswith("camera."):
            return [op.inputs.get("target_actor")] if op.inputs.get("target_actor") else []
        return []
