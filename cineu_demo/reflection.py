from __future__ import annotations

from copy import deepcopy
from typing import Any

from .schemas import ExecutionResult, Operation, VerificationReport


class MinimalReflection:
    """Small deterministic repair rules for demo operations.

    This is intentionally conservative: only the failing operation may be
    altered, and the patch is recorded by the orchestrator before retry.
    """

    def propose_patch(
        self,
        op: Operation,
        runtime: ExecutionResult | None,
        state_report: VerificationReport | None,
    ) -> Operation | None:
        failed_checks = []
        if state_report and not state_report.passed:
            failed_checks = [c.get("name", "") for c in state_report.diagnostics.get("failed_checks", [])]
        patched = deepcopy(op)

        if op.type == "sequence.camera_cut" and any("camera_cut_no_gap" in x for x in failed_checks):
            cuts = sorted(patched.inputs.get("cuts", []), key=lambda c: c["start_frame"])
            if cuts:
                cursor = cuts[0]["start_frame"]
                for cut in cuts:
                    cut["start_frame"] = cursor
                    cursor = cut["end_frame"]
                return patched

        if op.type.startswith("camera.") and any("camera_transform_keys" in x for x in failed_checks):
            keys = patched.inputs.get("keys", [])
            if len(keys) == 1:
                dup = deepcopy(keys[0])
                dup["frame"] = patched.inputs.get("end_frame", dup.get("frame", 0) + 24)
                keys.append(dup)
                patched.inputs["keys"] = keys
                return patched

        if runtime and runtime.error_type in {"KeyError", "LookupError"} and op.type.startswith("camera."):
            # Fall back to world-origin target and keep the existing trajectory.
            patched.inputs["target_actor"] = "world_origin"
            return patched

        return None
