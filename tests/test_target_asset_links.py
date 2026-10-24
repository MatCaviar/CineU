from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from typer.testing import CliRunner

from cineu_demo.cli import app
from cineu_demo.target_asset_links import build_target_asset_link_plan


def _available_requirement(requirement_id: str, source_path: Path) -> dict:
    return {
        "requirement_id": requirement_id,
        "status": "available",
        "target_project_ready": False,
        "evidence": {
            "asset_match_count": 1,
            "assets": [
                {
                    "ue_path": "/Game/AIUE5_vol10_01/maps/AIUE_vol10_01",
                    "source_path": str(source_path),
                }
            ],
        },
    }


class TargetAssetLinkTests(unittest.TestCase):
    def test_builds_junction_plan_from_available_content_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_asset = root / "MuseumGallery" / "Content" / "AIUE5_vol10_01" / "maps" / "AIUE_vol10_01.umap"
            source_asset.parent.mkdir(parents=True)
            source_asset.write_text("asset", encoding="utf-8")
            target_project = root / "HillsideProject"
            (target_project / "Content").mkdir(parents=True)

            report = {
                "schema_version": "cineu.required_asset_evidence_report.v1",
                "target_project_root": str(target_project),
                "requirements": [_available_requirement("archinteriors_museum_scene", source_asset)],
            }

            plan = build_target_asset_link_plan(report)

        self.assertEqual(plan["schema_version"], "cineu.target_asset_link_plan.v1")
        self.assertEqual(plan["summary"]["planned"], 1)
        self.assertEqual(plan["links"][0]["content_mount"], "/Game/AIUE5_vol10_01")
        self.assertTrue(plan["links"][0]["source_dir"].endswith("MuseumGallery\\Content\\AIUE5_vol10_01"))
        self.assertTrue(plan["links"][0]["target_dir"].endswith("HillsideProject\\Content\\AIUE5_vol10_01"))

    def test_cli_writes_dry_run_link_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_asset = root / "GameAnimation" / "Content" / "MetaHumans" / "Kellan" / "Body.uasset"
            source_asset.parent.mkdir(parents=True)
            source_asset.write_text("asset", encoding="utf-8")
            target_project = root / "HillsideProject"
            (target_project / "Content").mkdir(parents=True)
            report = {
                "schema_version": "cineu.required_asset_evidence_report.v1",
                "target_project_root": str(target_project),
                "requirements": [_available_requirement("metahuman_epic_games", source_asset)],
            }
            report_path = root / "required_asset_evidence_report.json"
            output = root / "target_asset_link_plan.json"
            report_path.write_text(json.dumps(report), encoding="utf-8")

            result = CliRunner().invoke(
                app,
                [
                    "target-asset-links",
                    "--report",
                    str(report_path),
                    "--output",
                    str(output),
                    "--dry-run",
                ],
            )

            self.assertEqual(result.exit_code, 0, result.output)
            stdout_payload = json.loads(result.output)
            self.assertEqual(stdout_payload, json.loads(output.read_text(encoding="utf-8")))
            self.assertEqual(stdout_payload["summary"]["planned"], 1)
            self.assertFalse((target_project / "Content" / "MetaHumans").exists())


if __name__ == "__main__":
    unittest.main()
