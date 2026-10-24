from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from typer.testing import CliRunner

from cineu_demo.cli import app
from cineu_demo.required_asset_evidence import build_required_asset_evidence_report, build_required_asset_user_actions_markdown


REPO_ROOT = Path(__file__).resolve().parents[1]
LOCAL_ASSET_INDEX = REPO_ROOT / "workspace" / "asset_index" / "local_asset_index.json"


def _asset(asset_id: str, name: str, asset_type: str, ue_path: str, source_path: str) -> dict:
    return {
        "asset_id": asset_id,
        "name": name,
        "type": asset_type,
        "ue_path": ue_path,
        "source_type": "ue_project_content",
        "source_path": source_path,
        "import_required": False,
        "semantic_tags": [],
        "functional_tags": [],
    }


class RequiredAssetEvidenceTests(unittest.TestCase):
    def _index_with_some_required_assets(self, root: Path) -> dict:
        hillside = root / "HillsideProject"
        citypark = root / "CityParkEnv55"
        museum = root / "MuseumGallery"
        game_animation = root / "GameAnimation"
        for project in [hillside, citypark, museum, game_animation]:
            (project / "Content").mkdir(parents=True)

        return {
            "schema_version": "cineu.local_asset_index.v1",
            "asset_first_ready": True,
            "asset_count": 6,
            "assets": [
                _asset(
                    "asset_citypark_showcase",
                    "City Park Showcase",
                    "level",
                    "/Game/CityPark/Maps/Showcase",
                    str(citypark / "Content" / "CityPark" / "Maps" / "Showcase.umap"),
                ),
                _asset(
                    "asset_museum_aiue",
                    "AIUE Vol10 Museum Gallery",
                    "level",
                    "/Game/AIUE5_vol10_01/maps/AIUE_vol10_01",
                    str(museum / "Content" / "AIUE5_vol10_01" / "maps" / "AIUE_vol10_01.umap"),
                ),
                _asset(
                    "asset_kellan_body",
                    "MetaHuman Kellan Body",
                    "skeletal_mesh",
                    "/Game/MetaHumans/Kellan/Male/Medium/NormalWeight/Body/m_med_nrw_body",
                    str(
                        game_animation
                        / "Content"
                        / "MetaHumans"
                        / "Kellan"
                        / "Male"
                        / "Medium"
                        / "NormalWeight"
                        / "Body"
                        / "m_med_nrw_body.uasset"
                    ),
                ),
                _asset(
                    "asset_kellan_mocap",
                    "MetaHuman Male Medium Mocap",
                    "animation",
                    "/Game/MetaHumans/Common/Common/Mocap/m_med_nrw_body_mocap",
                    str(game_animation / "Content" / "MetaHumans" / "Common" / "Common" / "Mocap" / "m_med_nrw_body_mocap.uasset"),
                ),
                _asset(
                    "asset_twinmotion_adrian",
                    "Twinmotion Adrian City",
                    "skeletal_mesh",
                    "/Game/ExternalAssets/Twinmotion/Characters/rigged/AdrianCity/SK_AdrianCity",
                    str(
                        hillside
                        / "Content"
                        / "ExternalAssets"
                        / "Twinmotion"
                        / "Characters"
                        / "rigged"
                        / "AdrianCity"
                        / "SK_AdrianCity.uasset"
                    ),
                ),
                _asset(
                    "asset_twinmotion_walk",
                    "Twinmotion Adrian Walk",
                    "animation",
                    "/Game/ExternalAssets/Twinmotion/Characters/rigged/AdrianCity/A_Walk",
                    str(
                        hillside
                        / "Content"
                        / "ExternalAssets"
                        / "Twinmotion"
                        / "Characters"
                        / "rigged"
                        / "AdrianCity"
                        / "A_Walk.uasset"
                    ),
                ),
            ],
            "fab_library": {
                "schema_version": "cineu.fab_library_evidence.v1",
                "listings": [
                    {
                        "listing_id": "e08aa2af-ade4-4b57-9a5d-06ffd6fe0916",
                        "title": "City Park Environment Collection LITE",
                        "download_status": "downloaded",
                        "download_path": str(citypark),
                    },
                    {
                        "listing_id": "4d4f9b35-8df2-4590-8df5-fc265fb4a583",
                        "title": "Archinteriors Museum Scene",
                        "download_status": "downloaded",
                        "download_path": str(museum),
                    },
                ],
            },
        }

    def test_required_asset_evidence_reports_available_and_missing_required_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = build_required_asset_evidence_report(self._index_with_some_required_assets(Path(tmp)))

        self.assertEqual(report["schema_version"], "cineu.required_asset_evidence_report.v1")
        self.assertFalse(report["passed"])
        self.assertGreaterEqual(report["user_action_plan"]["action_count"], report["summary"]["missing"])
        self.assertTrue(all(action["required"] for action in report["user_action_plan"]["actions"]))

        by_listing = {item["listing_id"]: item for item in report["requirements"]}
        self.assertEqual(by_listing["e08aa2af-ade4-4b57-9a5d-06ffd6fe0916"]["status"], "available")
        self.assertEqual(by_listing["4d4f9b35-8df2-4590-8df5-fc265fb4a583"]["status"], "available")
        self.assertEqual(by_listing["903037e9-e1ac-4f41-96e8-1683c6fa7ad4"]["status"], "missing")
        self.assertEqual(by_listing["2e872a96-686e-4955-8256-82fa19904f92"]["status"], "missing")

        citypark_evidence = by_listing["e08aa2af-ade4-4b57-9a5d-06ffd6fe0916"]["evidence"]
        self.assertTrue(any(item["ue_path"] == "/Game/CityPark/Maps/Showcase" for item in citypark_evidence["assets"]))
        self.assertEqual(by_listing["903037e9-e1ac-4f41-96e8-1683c6fa7ad4"]["next_action"], "add_to_hillside_project")

        by_requirement_id = {item["requirement_id"]: item for item in report["requirements"]}
        self.assertEqual(by_requirement_id["metahuman_epic_games"]["status"], "available")
        self.assertTrue(by_requirement_id["metahuman_epic_games"]["evidence"]["assets"])
        self.assertEqual(by_requirement_id["mixamo_city_pedestrian_actions"]["status"], "missing")
        self.assertEqual(by_requirement_id["mixamo_city_pedestrian_actions"]["user_action"]["kind"], "download_mixamo_city_pedestrian_actions")

        renderpeople_action = by_requirement_id["scanned_3d_people"]["user_action"]
        self.assertTrue(renderpeople_action["required"])
        self.assertEqual(renderpeople_action["kind"], "acquire_or_add_fab_listing_to_library")
        self.assertEqual(renderpeople_action["url"], "https://www.fab.com/listings/2e872a96-686e-4955-8256-82fa19904f92")

    def test_required_asset_evidence_distinguishes_downloaded_fab_not_imported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            download_dir = root / "RenderPeopleScannedV1"
            download_dir.mkdir()
            index = {
                "schema_version": "cineu.local_asset_index.v1",
                "assets": [],
                "fab_library": {
                    "schema_version": "cineu.fab_library_evidence.v1",
                    "listings": [
                        {
                            "listing_id": "2e872a96-686e-4955-8256-82fa19904f92",
                            "title": "Renderpeople - Scanned 3D People Pack",
                            "download_status": "downloaded",
                            "download_path": str(download_dir),
                        }
                    ],
                },
            }
            report = build_required_asset_evidence_report(index, target_project_root=root / "HillsideProject")

        renderpeople = next(item for item in report["requirements"] if item["requirement_id"] == "scanned_3d_people")

        self.assertEqual(renderpeople["status"], "available")
        self.assertFalse(renderpeople["target_project_ready"])
        self.assertEqual(renderpeople["user_action"]["kind"], "import_downloaded_fab_pack_to_target_project")
        self.assertEqual(renderpeople["user_action"]["source_path"], str(download_dir))
        self.assertEqual(renderpeople["user_action"]["target_project_root"], str(root / "HillsideProject"))

    def test_required_asset_evidence_distinguishes_acquired_fab_not_downloaded(self) -> None:
        index = {
            "schema_version": "cineu.local_asset_index.v1",
            "assets": [],
            "fab_library": {
                "schema_version": "cineu.fab_library_evidence.v1",
                "listings": [
                    {
                        "listing_id": "903037e9-e1ac-4f41-96e8-1683c6fa7ad4",
                        "title": "City Sample Crowds",
                        "download_status": "not_downloaded",
                        "download_path": "",
                    }
                ],
            },
        }

        report = build_required_asset_evidence_report(index)
        crowds = next(item for item in report["requirements"] if item["requirement_id"] == "city_sample_crowds")

        self.assertEqual(crowds["status"], "missing")
        self.assertEqual(crowds["user_action"]["kind"], "download_fab_listing_to_target_project")
        self.assertEqual(crowds["user_action"]["url"], "https://www.fab.com/listings/903037e9-e1ac-4f41-96e8-1683c6fa7ad4")

    def test_missing_downtown_west_action_includes_local_search_diagnostics(self) -> None:
        index = {
            "schema_version": "cineu.local_asset_index.v1",
            "assets": [],
            "fab_library": {
                "schema_version": "cineu.fab_library_evidence.v1",
                "db_paths": [r"C:\ProgramData\Epic\EpicGamesLauncher\VaultCache\FabLibrary\listings_v1.db"],
                "listings": [],
                "orphan_downloads": [
                    {
                        "name": "ModularDcffe32471e5fV1",
                        "path": r"C:\ProgramData\Epic\EpicGamesLauncher\VaultCache\ModularDcffe32471e5fV1",
                        "state": "staged",
                        "cache_size": 123456,
                    }
                ],
            },
        }

        report = build_required_asset_evidence_report(index, target_project_root=r"D:\UnrealAgent\CityParkEnv55")
        downtown = next(item for item in report["requirements"] if item["requirement_id"] == "downtown_west")
        action = downtown["user_action"]

        self.assertEqual(action["kind"], "acquire_or_add_fab_listing_to_library")
        self.assertEqual(action["diagnostics"]["fab_listing_found"], False)
        self.assertEqual(action["diagnostics"]["fab_download_found"], False)
        self.assertEqual(action["diagnostics"]["local_asset_match_count"], 0)
        self.assertEqual(action["diagnostics"]["searched_asset_tokens"], ["downtownwest", "purepolygonsdowntown", "downtowncitypack"])
        self.assertEqual(action["diagnostics"]["orphan_vault_cache_candidate_count"], 1)
        self.assertEqual(action["diagnostics"]["orphan_vault_cache_candidates"][0]["name"], "ModularDcffe32471e5fV1")
        self.assertIn("local_asset_index.fab_library.listings", action["diagnostics"]["checked_sources"])
        self.assertIn("local_asset_index.fab_library.orphan_downloads", action["diagnostics"]["checked_sources"])
        self.assertIn("Add the Fab listing to your Library", action["diagnostics"]["required_next_launcher_action"])

        markdown = build_required_asset_user_actions_markdown(report)
        self.assertIn("Orphan VaultCache candidates", markdown)
        self.assertIn("ModularDcffe32471e5fV1", markdown)
        self.assertIn("staged", markdown)

    def test_art_gallery_showcase_level_satisfies_art_fashion_automotive_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hillside = root / "HillsideProject"
            (hillside / "Content" / "Showcase" / "Maps").mkdir(parents=True)
            index = {
                "schema_version": "cineu.local_asset_index.v1",
                "assets": [
                    _asset(
                        "asset_showcase_art_gallery",
                        "ArtGallery",
                        "level",
                        "/Game/Showcase/Maps/ArtGallery",
                        str(hillside / "Content" / "Showcase" / "Maps" / "ArtGallery.umap"),
                    )
                ],
                "fab_library": {"schema_version": "cineu.fab_library_evidence.v1", "listings": []},
            }

            report = build_required_asset_evidence_report(index, target_project_root=hillside)

        galleries = next(item for item in report["requirements"] if item["requirement_id"] == "art_fashion_automotive_galleries")
        self.assertEqual(galleries["status"], "available")
        self.assertTrue(galleries["target_project_ready"])
        self.assertFalse(galleries["user_action"]["required"])
        self.assertTrue(
            any(item["ue_path"] == "/Game/Showcase/Maps/ArtGallery" for item in galleries["evidence"]["assets"])
        )

    def test_citypark_warehouse_content_satisfies_warehouse_requirement_without_fab_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            citypark = root / "CityParkEnv55"
            (citypark / "Content" / "Warehouse" / "Scene").mkdir(parents=True)
            index = {
                "schema_version": "cineu.local_asset_index.v1",
                "assets": [
                    _asset(
                        "asset_warehouse_scene",
                        "Scene",
                        "level",
                        "/Game/Warehouse/Scene/Scene",
                        str(citypark / "Content" / "Warehouse" / "Scene" / "Scene.umap"),
                    )
                ],
                "fab_library": {"schema_version": "cineu.fab_library_evidence.v1", "listings": []},
            }

            report = build_required_asset_evidence_report(index, target_project_root=citypark)

        warehouse = next(item for item in report["requirements"] if item["requirement_id"] == "warehouse_pack")
        self.assertEqual(warehouse["status"], "available")
        self.assertTrue(warehouse["target_project_ready"])
        self.assertFalse(warehouse["user_action"]["required"])
        self.assertTrue(any(item["ue_path"] == "/Game/Warehouse/Scene/Scene" for item in warehouse["evidence"]["assets"]))

    def test_citypark_car_showcase_content_satisfies_car_dealer_requirement_without_fab_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            citypark = root / "CityParkEnv55"
            (citypark / "Content" / "Showcase" / "Maps").mkdir(parents=True)
            index = {
                "schema_version": "cineu.local_asset_index.v1",
                "assets": [
                    _asset(
                        "asset_car_showcase",
                        "CarShowcase",
                        "level",
                        "/Game/Showcase/Maps/CarShowcase",
                        str(citypark / "Content" / "Showcase" / "Maps" / "CarShowcase.umap"),
                    )
                ],
                "fab_library": {"schema_version": "cineu.fab_library_evidence.v1", "listings": []},
            }

            report = build_required_asset_evidence_report(index, target_project_root=citypark)

        car_dealer = next(item for item in report["requirements"] if item["requirement_id"] == "car_dealer")
        self.assertEqual(car_dealer["status"], "available")
        self.assertTrue(car_dealer["target_project_ready"])
        self.assertFalse(car_dealer["user_action"]["required"])
        self.assertTrue(any(item["ue_path"] == "/Game/Showcase/Maps/CarShowcase" for item in car_dealer["evidence"]["assets"]))

    @unittest.skipUnless(LOCAL_ASSET_INDEX.exists(), "requires real local CineU asset index")
    def test_real_city_sample_locomotion_assets_cover_city_pedestrian_action_requirement(self) -> None:
        index = json.loads(LOCAL_ASSET_INDEX.read_text(encoding="utf-8"))
        city_sample_walk_assets = [
            asset
            for asset in index.get("assets", [])
            if "/Game/CitySampleCrowd/Character/Anims/Loco/" in str(asset.get("ue_path", ""))
            and "Walk" in str(asset.get("ue_path", ""))
        ]
        self.assertGreaterEqual(len(city_sample_walk_assets), 20)

        report = build_required_asset_evidence_report(index, target_project_root=r"D:\UnrealAgent\HillsideProject")
        mixamo = next(item for item in report["requirements"] if item["requirement_id"] == "mixamo_city_pedestrian_actions")

        self.assertEqual(mixamo["status"], "available")
        self.assertEqual(mixamo["evidence"]["coverage"], "covered_by_city_sample_crowd_locomotion")
        self.assertGreaterEqual(mixamo["evidence"]["asset_match_count"], 20)
        self.assertFalse(mixamo["user_action"]["required"])

    def test_required_asset_evidence_cli_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset_index = root / "local_asset_index.json"
            output = root / "required_asset_evidence_report.json"
            asset_index.write_text(json.dumps(self._index_with_some_required_assets(root)), encoding="utf-8")

            result = CliRunner().invoke(
                app,
                [
                    "required-asset-evidence",
                    "--asset-index",
                    str(asset_index),
                    "--output",
                    str(output),
                ],
            )

            self.assertEqual(result.exit_code, 0, result.output)
            stdout_payload = json.loads(result.output)
            file_payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(stdout_payload, file_payload)
            self.assertEqual(stdout_payload["schema_version"], "cineu.required_asset_evidence_report.v1")
            self.assertFalse(stdout_payload["passed"])

    @unittest.skipUnless(LOCAL_ASSET_INDEX.exists(), "requires real local CineU asset index")
    def test_required_asset_evidence_cli_writes_current_citypark_user_actions_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "required_asset_evidence_report.json"
            markdown = root / "required_asset_user_actions.md"

            result = CliRunner().invoke(
                app,
                [
                    "required-asset-evidence",
                    "--asset-index",
                    str(LOCAL_ASSET_INDEX),
                    "--output",
                    str(output),
                    "--user-actions-markdown",
                    str(markdown),
                    "--target-project-root",
                    r"D:\UnrealAgent\CityParkEnv55",
                ],
            )

            self.assertEqual(result.exit_code, 0, result.output)
            report = json.loads(output.read_text(encoding="utf-8"))
            text = markdown.read_text(encoding="utf-8")
            actions = report["user_action_plan"]["actions"]

            self.assertIn(r"Target project: `D:\UnrealAgent\CityParkEnv55`", text)
            self.assertIn(f"- Still requiring user action: {len(actions)}", text)
            for action in actions:
                self.assertIn(action["name"], text)
                self.assertIn(action["kind"], text)
                self.assertIn(action["url"], text)
            if [action["requirement_id"] for action in actions] == ["downtown_west"]:
                self.assertIn("Downtown West", text)
                self.assertNotIn("Scanned 3D People / Renderpeople", text)
                self.assertNotIn("Download/import city pedestrian locomotion actions", text)

    def test_required_asset_evidence_cli_summary_only_keeps_full_file_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset_index = root / "local_asset_index.json"
            output = root / "required_asset_evidence_report.json"
            asset_index.write_text(json.dumps(self._index_with_some_required_assets(root)), encoding="utf-8")

            result = CliRunner().invoke(
                app,
                [
                    "required-asset-evidence",
                    "--asset-index",
                    str(asset_index),
                    "--output",
                    str(output),
                    "--target-project-root",
                    str(root / "CityParkEnv55"),
                    "--summary-only",
                ],
            )

            self.assertEqual(result.exit_code, 0, result.output)
            stdout_payload = json.loads(result.output)
            file_payload = json.loads(output.read_text(encoding="utf-8"))

            self.assertEqual(stdout_payload["schema_version"], "cineu.required_asset_evidence_report.v1")
            self.assertEqual(stdout_payload["summary"], file_payload["summary"])
            self.assertEqual(stdout_payload["action_count"], file_payload["user_action_plan"]["action_count"])
            self.assertIn("actions", stdout_payload)
            self.assertNotIn("requirements", stdout_payload)
            self.assertIn("requirements", file_payload)
            self.assertEqual(len(file_payload["requirements"]), 10)


if __name__ == "__main__":
    unittest.main()
