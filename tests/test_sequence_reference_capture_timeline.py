from __future__ import annotations

import unittest
from types import SimpleNamespace

from cineu_demo.agents import SeqAgent
from cineu_demo.schemas import AssetMetadata


class SequenceReferenceCaptureTimelineTests(unittest.TestCase):
    def test_existing_reference_sequence_timeline_preserves_full_capture_source_range(self) -> None:
        sequence_asset = AssetMetadata(
            asset_id="asset_citypark_reference_sequence",
            name="AnimalHitchcockZoom",
            ue_path="/Game/AnimalHitchcockZoom",
            type="level_sequence",
            source_path="D:/UnrealAgent/CityParkEnv55/Content/AnimalHitchcockZoom.uasset",
        )
        shot = SimpleNamespace(
            id="shot_001",
            metadata={
                "reference_output_fps": 30,
                "reference_output_end_frame": 166,
                "reference_capture_source": "D:/UnrealAgent/CityParkEnv55/Saved/VideoCaptures/Showcase_(2).avi",
                "reference_capture_start_frame": 10,
                "reference_capture_end_frame": 330,
            },
        )
        ctx = SimpleNamespace(
            task=SimpleNamespace(
                scene=SimpleNamespace(fps=24, end_frame=126),
                camera=SimpleNamespace(shots=[shot]),
            ),
            variables={},
            template_store=SimpleNamespace(retrieve=lambda operation_type, agent: SimpleNamespace(template_id=f"{operation_type}.v1")),
        )

        op = SeqAgent().build_use_existing(ctx, "shot_001", sequence_asset)

        self.assertEqual(op.inputs["fps"], 30)
        self.assertEqual(op.inputs["start_frame"], 0)
        self.assertEqual(op.inputs["end_frame"], 320)
        self.assertEqual(ctx.variables["active_sequence_timeline"], {"fps": 30, "start_frame": 0, "end_frame": 320})


if __name__ == "__main__":
    unittest.main()
