from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from cineu_demo.agents import RenderAgent


class RenderAgentReferenceCaptureTests(unittest.TestCase):
    def test_reference_capture_preview_preserves_full_source_frame_range_for_long_world4_feedback(self) -> None:
        ctx = SimpleNamespace(
            task=SimpleNamespace(render=SimpleNamespace(resolution=[1280, 720], format="mp4", quality="preview")),
            sequence_path="/Game/AnimalHitchcockZoom",
            ledger=SimpleNamespace(run_dir=Path("workspace/runs/run_x")),
            variables={
                "active_sequence_timeline": {"fps": 30, "start_frame": 0, "end_frame": 166},
                "active_native_capture_frame_range": {"start_frame": 10, "end_frame": 330},
                "active_reference_capture": {"source": "D:/UnrealAgent/CityParkEnv55/Saved/VideoCaptures/Showcase_(2).avi", "start_frame": 10, "end_frame": 330},
            },
            template_store=SimpleNamespace(retrieve=lambda operation_type, agent: SimpleNamespace(template_id=f"{operation_type}.v1")),
        )

        op = RenderAgent().build(ctx)

        self.assertEqual(op.inputs["fps"], 30)
        self.assertEqual(op.inputs["start_frame"], 0)
        self.assertEqual(op.inputs["end_frame"], 320)
        self.assertEqual(op.inputs["reference_capture_start_frame"], 10)
        self.assertEqual(op.inputs["reference_capture_end_frame"], 330)
        self.assertEqual(op.inputs["native_capture_start_frame"], 10)
        self.assertEqual(op.inputs["native_capture_end_frame"], 330)

    def test_native_fallback_keeps_task_timeline_when_reference_capture_is_missing(self) -> None:
        ctx = SimpleNamespace(
            task=SimpleNamespace(render=SimpleNamespace(resolution=[1280, 720], format="mp4", quality="preview")),
            sequence_path="/Game/AnimalHitchcockZoom",
            ledger=SimpleNamespace(run_dir=Path("workspace/runs/run_x")),
            variables={
                "active_sequence_timeline": {"fps": 30, "start_frame": 0, "end_frame": 166},
                "active_native_capture_frame_range": {"start_frame": 10, "end_frame": 330},
            },
            template_store=SimpleNamespace(retrieve=lambda operation_type, agent: SimpleNamespace(template_id=f"{operation_type}.v1")),
        )

        op = RenderAgent().build(ctx)

        self.assertEqual(op.inputs["end_frame"], 166)
        self.assertNotIn("reference_capture_source", op.inputs)


if __name__ == "__main__":
    unittest.main()
