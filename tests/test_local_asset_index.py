from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from cineu_demo.asset_store import AssetStore
from cineu_demo.cli import app
from cineu_demo.demo_workspace import create_demo_workspace
from cineu_demo.engine import CineUOrchestrator
from cineu_demo.local_asset_index import build_local_asset_index, write_local_asset_index
from cineu_demo.required_asset_evidence import build_required_asset_evidence_report


class LocalAssetIndexTests(unittest.TestCase):
    def _make_realistic_asset_sources(self, root: Path) -> dict[str, Path]:
        asset_cache = root / "cineu_research_system" / "workspace" / "projects" / "demo_project" / "asset_cache"
        asset_cache.mkdir(parents=True)
        (asset_cache / "assets.jsonl").write_text("", encoding="utf-8")

        citypark = root / "CityParkEnv55"
        citypark.mkdir()
        (citypark / "CityParkEnv55.uproject").write_text("{}", encoding="utf-8")
        citypark_content = citypark / "Content"
        (citypark_content / "CityPark" / "Maps").mkdir(parents=True)
        (citypark_content / "CityPark" / "Meshes" / "Flora" / "Trees").mkdir(parents=True)
        (citypark_content / "CityPark" / "Maps" / "Showcase.umap").write_bytes(b"map")
        (citypark_content / "CityPark" / "Meshes" / "Flora" / "Trees" / "SM_WeepingWillow01.uasset").write_bytes(b"mesh")

        hillside = root / "HillsideProject"
        hillside.mkdir()
        (hillside / "HillsideProject.uproject").write_text("{}", encoding="utf-8")
        hillside_content = hillside / "Content"
        (hillside_content / "Hillside" / "Maps").mkdir(parents=True)
        (hillside_content / "ExternalAssets" / "Twinmotion" / "Characters" / "rigged" / "Adult" / "Meshes").mkdir(parents=True)
        (hillside_content / "ExternalAssets" / "Twinmotion" / "Characters" / "rigged" / "Adult" / "Animations").mkdir(parents=True)
        (hillside_content / "Hillside" / "Maps" / "LV_Exterior.umap").write_bytes(b"map")
        (hillside_content / "ExternalAssets" / "Twinmotion" / "Characters" / "rigged" / "Adult" / "Meshes" / "SK_Adult.uasset").write_bytes(b"mesh")
        (hillside_content / "ExternalAssets" / "Twinmotion" / "Characters" / "rigged" / "Adult" / "Animations" / "A_Adult_Walk.uasset").write_bytes(b"anim")

        return {
            "asset_cache": asset_cache,
            "citypark": citypark,
            "citypark_content": citypark_content,
            "hillside": hillside,
            "hillside_content": hillside_content,
        }

    def test_index_groups_real_unreal_project_assets_before_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self._make_realistic_asset_sources(root)
            store = AssetStore(
                paths["asset_cache"] / "assets.jsonl",
                source_dirs=[paths["citypark_content"], paths["hillside_content"]],
            )

            index = build_local_asset_index(store, project_roots=[paths["citypark"], paths["hillside"]])

            self.assertEqual(index["schema_version"], "cineu.local_asset_index.v1")
            self.assertTrue(index["asset_first_ready"])
            self.assertGreaterEqual(index["asset_count"], 5)
            self.assertEqual(len(index["assets"]), index["asset_count"])
            self.assertEqual(index["counts_by_type"]["level"], 2)
            self.assertGreaterEqual(index["counts_by_type"]["skeletal_mesh"], 1)
            self.assertGreaterEqual(index["counts_by_type"]["animation"], 1)

            project_names = {project["project_name"] for project in index["projects"]}
            self.assertIn("CityParkEnv55", project_names)
            self.assertIn("HillsideProject", project_names)

            env_paths = {asset["ue_path"] for asset in index["environment_candidates"]}
            self.assertIn("/Game/CityPark/Maps/Showcase", env_paths)
            self.assertIn("/Game/Hillside/Maps/LV_Exterior", env_paths)

            character_paths = {asset["ue_path"] for asset in index["character_candidates"]}
            animation_paths = {asset["ue_path"] for asset in index["animation_candidates"]}
            self.assertIn("/Game/ExternalAssets/Twinmotion/Characters/rigged/Adult/Meshes/SK_Adult", character_paths)
            self.assertIn("/Game/ExternalAssets/Twinmotion/Characters/rigged/Adult/Animations/A_Adult_Walk", animation_paths)

            written = write_local_asset_index(index, root / "workspace" / "asset_index")
            self.assertTrue(Path(written["index_file"]).exists())
            self.assertTrue(Path(written["summary_file"]).exists())
            summary = json.loads(Path(written["summary_file"]).read_text(encoding="utf-8"))
            self.assertEqual(summary["schema_version"], "cineu.local_asset_index_summary.v1")
            self.assertEqual(summary["project_count"], 2)
            self.assertEqual(summary["asset_count"], index["asset_count"])

    def test_cli_rebuilds_local_asset_index_from_explicit_source_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self._make_realistic_asset_sources(root)
            workspace = root / "workspace"
            runner = CliRunner()

            result = runner.invoke(
                app,
                [
                    "rebuild-asset-index",
                    "--workspace",
                    str(workspace),
                    "--project-id",
                    "demo_project",
                    "--source-dir",
                    str(paths["citypark_content"]),
                    "--source-dir",
                    str(paths["hillside_content"]),
                    "--project-root",
                    str(paths["citypark"]),
                    "--project-root",
                    str(paths["hillside"]),
                ],
            )

            self.assertEqual(result.exit_code, 0, result.output)
            payload = json.loads(result.output)
            self.assertTrue(Path(payload["index_file"]).exists())
            self.assertTrue(Path(payload["summary_file"]).exists())
            summary = json.loads(Path(payload["summary_file"]).read_text(encoding="utf-8"))
            self.assertTrue(summary["asset_first_ready"])
            self.assertEqual(summary["project_count"], 2)

    def test_cli_rebuild_asset_index_includes_global_fab_library_evidence_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self._make_realistic_asset_sources(root)
            workspace = root / "workspace"
            program_data = root / "ProgramData"
            fab_library = program_data / "Epic" / "EpicGamesLauncher" / "VaultCache" / "FabLibrary"
            downtown_cache = fab_library / "DowntownWestV1" / "unreal-engine" / "Content" / "DowntownWest"
            downtown_cache.mkdir(parents=True)
            (downtown_cache / "Maps").mkdir()
            (downtown_cache / "Maps" / "DowntownWest.umap").write_bytes(b"downtown west map")
            db_path = fab_library / "listings_v1.db"
            connection = sqlite3.connect(db_path)
            try:
                connection.execute("create table catalog (listing_uid text, title text, description text, thumbnail text, namespace text)")
                connection.execute(
                    "create table download_meta (id integer, listing_uid text, format text, quality text, path text, platform_included text, is_converted integer, downloaded_at integer, cache_size integer)"
                )
                connection.execute(
                    "insert into catalog values (?, ?, ?, ?, ?)",
                    (
                        "0faf8b5d-7a5f-4fee-a297-7a8efaba8896",
                        "Downtown West",
                        "Urban pedestrian environment",
                        "",
                        "fab",
                    ),
                )
                connection.execute(
                    "insert into download_meta values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        1,
                        "0faf8b5d-7a5f-4fee-a297-7a8efaba8896",
                        "unreal-engine",
                        "",
                        str(fab_library / "DowntownWestV1"),
                        "",
                        0,
                        0,
                        42,
                    ),
                )
                connection.commit()
            finally:
                connection.close()

            with patch.dict(os.environ, {"ProgramData": str(program_data)}, clear=False):
                result = CliRunner().invoke(
                    app,
                    [
                        "rebuild-asset-index",
                        "--workspace",
                        str(workspace),
                        "--project-id",
                        "demo_project",
                        "--source-dir",
                        str(paths["citypark_content"]),
                        "--project-root",
                        str(paths["citypark"]),
                    ],
                )

            self.assertEqual(result.exit_code, 0, result.output)
            payload = json.loads(result.output)
            index = json.loads(Path(payload["index_file"]).read_text(encoding="utf-8"))
            listing_ids = {item["listing_id"] for item in index["fab_library"]["listings"]}
            self.assertIn("0faf8b5d-7a5f-4fee-a297-7a8efaba8896", listing_ids)
            listing = next(
                item
                for item in index["fab_library"]["listings"]
                if item["listing_id"] == "0faf8b5d-7a5f-4fee-a297-7a8efaba8896"
            )
            self.assertEqual(listing["title"], "Downtown West")
            self.assertEqual(listing["download_status"], "downloaded")
            self.assertTrue(Path(listing["download_path"]).exists())

    def test_scanned_people_animated_clips_are_animation_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset_cache = root / "workspace" / "projects" / "demo_project" / "asset_cache"
            asset_cache.mkdir(parents=True)
            (asset_cache / "assets.jsonl").write_text("", encoding="utf-8")

            museum = root / "MuseumGallery"
            museum.mkdir()
            (museum / "MuseumGallery.uproject").write_text("{}", encoding="utf-8")
            animations = museum / "Content" / "Scanned3DPeoplePack" / "RP_Character" / "00_Animations"
            animations.mkdir(parents=True)
            for name in [
                "rp_nathan_animated_003_walking_ue4.uasset",
                "rp_manuel_animated_001_dancing_ue4.uasset",
                "rp_sophia_animated_003_idling_ue4.uasset",
            ]:
                (animations / name).write_bytes(b"scanned people animation")

            store = AssetStore(asset_cache / "assets.jsonl", source_dirs=[museum / "Content"])
            index = build_local_asset_index(store, project_roots=[museum])

            expected_paths = {
                "/Game/Scanned3DPeoplePack/RP_Character/00_Animations/rp_nathan_animated_003_walking_ue4",
                "/Game/Scanned3DPeoplePack/RP_Character/00_Animations/rp_manuel_animated_001_dancing_ue4",
                "/Game/Scanned3DPeoplePack/RP_Character/00_Animations/rp_sophia_animated_003_idling_ue4",
            }
            assets_by_path = {asset["ue_path"]: asset for asset in index["assets"]}
            animation_paths = {asset["ue_path"] for asset in index["animation_candidates"]}

            self.assertTrue(expected_paths <= set(assets_by_path))
            self.assertTrue(expected_paths <= animation_paths)
            for ue_path in expected_paths:
                self.assertEqual(assets_by_path[ue_path]["type"], "animation")

    def test_index_preserves_target_project_copy_when_game_path_duplicates_legacy_mount(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset_cache = root / "workspace" / "projects" / "demo_project" / "asset_cache"
            asset_cache.mkdir(parents=True)
            (asset_cache / "assets.jsonl").write_text("", encoding="utf-8")

            legacy_project = root / "LegacyCineUProject"
            citypark = root / "CityParkEnv55"
            legacy_content = legacy_project / "Content"
            citypark_content = citypark / "Content"
            for project in [legacy_project, citypark]:
                project.mkdir()
                (project / f"{project.name}.uproject").write_text("{}", encoding="utf-8")
                (project / "Content" / "CityPark" / "Maps").mkdir(parents=True)
                (project / "Content" / "CityPark" / "Maps" / "Showcase.umap").write_bytes(b"city park map")

            store = AssetStore(asset_cache / "assets.jsonl", source_dirs=[legacy_content, citypark_content])
            index = build_local_asset_index(store, project_roots=[legacy_project, citypark])
            citypark_showcase_assets = [
                asset for asset in index["assets"] if asset["ue_path"] == "/Game/CityPark/Maps/Showcase"
            ]

            self.assertEqual(len(citypark_showcase_assets), 2)
            self.assertTrue(
                any(
                    citypark_content.resolve() in Path(str(asset["source_path"])).resolve().parents
                    for asset in citypark_showcase_assets
                )
            )

            report = build_required_asset_evidence_report(index, target_project_root=citypark)
            citypark_lite = next(item for item in report["requirements"] if item["requirement_id"] == "citypark_lite")
            self.assertTrue(citypark_lite["target_project_ready"])
            self.assertFalse(citypark_lite["user_action"]["required"])

    def test_environment_candidates_keep_primary_hillside_levels_when_clipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset_cache = root / "workspace" / "projects" / "demo_project" / "asset_cache"
            asset_cache.mkdir(parents=True)
            (asset_cache / "assets.jsonl").write_text("", encoding="utf-8")

            hillside = root / "HillsideProject"
            hillside.mkdir()
            (hillside / "HillsideProject.uproject").write_text("{}", encoding="utf-8")
            content = hillside / "Content"
            maps = content / "Hillside" / "Maps"
            setdress = maps / "Setdress"
            maps.mkdir(parents=True)
            setdress.mkdir(parents=True)
            (maps / "LV_Exterior.umap").write_bytes(b"map")
            (maps / "LV_Interior.umap").write_bytes(b"map")
            for index in range(12):
                (setdress / f"LV_Grass_SU_{index:03d}.umap").write_bytes(b"map")

            store = AssetStore(asset_cache / "assets.jsonl", source_dirs=[content])
            index = build_local_asset_index(store, project_roots=[hillside], max_candidates=2)

            env_paths = {asset["ue_path"] for asset in index["environment_candidates"]}
            self.assertEqual(env_paths, {"/Game/Hillside/Maps/LV_Exterior", "/Game/Hillside/Maps/LV_Interior"})

    def test_environment_candidates_exclude_character_pack_overview_maps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset_cache = root / "workspace" / "projects" / "demo_project" / "asset_cache"
            asset_cache.mkdir(parents=True)
            (asset_cache / "assets.jsonl").write_text("", encoding="utf-8")

            citypark = root / "CityParkEnv55"
            citypark.mkdir()
            (citypark / "CityParkEnv55.uproject").write_text("{}", encoding="utf-8")
            content = citypark / "Content"
            (content / "CityPark" / "Maps").mkdir(parents=True)
            (content / "AfricanAnimalsPack" / "Zebra" / "Maps").mkdir(parents=True)
            (content / "CityPark" / "Maps" / "Showcase.umap").write_bytes(b"park map")
            (content / "AfricanAnimalsPack" / "Zebra" / "Maps" / "Overview.umap").write_bytes(b"zebra overview map")

            store = AssetStore(asset_cache / "assets.jsonl", source_dirs=[content])
            index = build_local_asset_index(store, project_roots=[citypark])

            all_level_paths = {asset["ue_path"] for asset in index["assets"] if asset["type"] == "level"}
            env_paths = {asset["ue_path"] for asset in index["environment_candidates"]}
            self.assertIn("/Game/AfricanAnimalsPack/Zebra/Maps/Overview", all_level_paths)
            self.assertIn("/Game/CityPark/Maps/Showcase", env_paths)
            self.assertNotIn("/Game/AfricanAnimalsPack/Zebra/Maps/Overview", env_paths)

    def test_index_records_fab_library_listing_and_download_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset_cache = root / "workspace" / "projects" / "demo_project" / "asset_cache"
            asset_cache.mkdir(parents=True)
            (asset_cache / "assets.jsonl").write_text("", encoding="utf-8")

            fab_library = root / "EpicGamesLauncher" / "VaultCache" / "FabLibrary"
            renderpeople_cache = fab_library / "RenderPeopleScannedV1" / "unreal-engine" / "Content" / "Renderpeople"
            renderpeople_cache.mkdir(parents=True)
            (renderpeople_cache / "SK_Renderpeople_Pedestrian.uasset").write_bytes(b"mesh")
            db_path = fab_library / "listings_v1.db"
            connection = sqlite3.connect(db_path)
            try:
                connection.execute("create table catalog (listing_uid text, title text, description text, thumbnail text, namespace text)")
                connection.execute(
                    "create table download_meta (id integer, listing_uid text, format text, quality text, path text, platform_included text, is_converted integer, downloaded_at integer, cache_size integer)"
                )
                connection.execute(
                    "insert into catalog values (?, ?, ?, ?, ?)",
                    (
                        "2e872a96-686e-4955-8256-82fa19904f92",
                        "Renderpeople - Scanned 3D People Pack",
                        "Photoreal scanned pedestrians",
                        "",
                        "fab",
                    ),
                )
                connection.execute(
                    "insert into download_meta values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        1,
                        "2e872a96-686e-4955-8256-82fa19904f92",
                        "unreal-engine",
                        "",
                        str(fab_library / "RenderPeopleScannedV1"),
                        "",
                        0,
                        0,
                        123456,
                    ),
                )
                connection.commit()
            finally:
                connection.close()

            store = AssetStore(asset_cache / "assets.jsonl", source_dirs=[renderpeople_cache])
            index = build_local_asset_index(store)

            fab = index["fab_library"]
            self.assertEqual(fab["schema_version"], "cineu.fab_library_evidence.v1")
            self.assertEqual(fab["listing_count"], 1)
            self.assertEqual(fab["download_count"], 1)
            listing = fab["listings"][0]
            self.assertEqual(listing["listing_id"], "2e872a96-686e-4955-8256-82fa19904f92")
            self.assertEqual(listing["title"], "Renderpeople - Scanned 3D People Pack")
            self.assertEqual(listing["download_status"], "downloaded")
            self.assertTrue(Path(listing["download_path"]).exists())

            written = write_local_asset_index(index, root / "workspace" / "asset_index")
            summary = json.loads(Path(written["summary_file"]).read_text(encoding="utf-8"))
            self.assertEqual(summary["fab_listing_count"], 1)
            self.assertEqual(summary["fab_download_count"], 1)

    def test_index_records_orphan_vault_cache_downloads_not_mapped_in_fab_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset_cache = root / "workspace" / "projects" / "demo_project" / "asset_cache"
            asset_cache.mkdir(parents=True)
            (asset_cache / "assets.jsonl").write_text("", encoding="utf-8")

            program_data = root / "ProgramData"
            vault_cache = program_data / "Epic" / "EpicGamesLauncher" / "VaultCache"
            orphan = vault_cache / "ModularDcffe32471e5fV1"
            (orphan / "stage" / "c").mkdir(parents=True)
            (orphan / "stage" / "m").mkdir(parents=True)
            (orphan / "stage" / "c" / "chunk").write_bytes(b"downtown chunk")
            fab_library = vault_cache / "FabLibrary"
            fab_library.mkdir()
            db_path = fab_library / "listings_v1.db"
            connection = sqlite3.connect(db_path)
            try:
                connection.execute("create table catalog (listing_uid text, title text, description text, thumbnail text, namespace text)")
                connection.commit()
            finally:
                connection.close()

            with patch.dict(os.environ, {"ProgramData": str(program_data)}, clear=False):
                store = AssetStore(asset_cache / "assets.jsonl", include_global_libraries=True)
                index = build_local_asset_index(store)

            fab = index["fab_library"]
            self.assertEqual(fab["orphan_download_count"], 1)
            self.assertEqual(fab["orphan_downloads"][0]["name"], "ModularDcffe32471e5fV1")
            self.assertEqual(fab["orphan_downloads"][0]["path"], str(orphan))
            self.assertGreater(fab["orphan_downloads"][0]["cache_size"], 0)
            self.assertEqual(fab["orphan_downloads"][0]["state"], "staged")

            written = write_local_asset_index(index, root / "workspace" / "asset_index")
            summary = json.loads(Path(written["summary_file"]).read_text(encoding="utf-8"))
            self.assertEqual(summary["fab_orphan_download_count"], 1)

    def test_index_records_nearby_fabcache_vault_orphans_from_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset_cache = root / "workspace" / "projects" / "demo_project" / "asset_cache"
            asset_cache.mkdir(parents=True)
            (asset_cache / "assets.jsonl").write_text("", encoding="utf-8")

            citypark_content = root / "CityParkEnv55" / "Content"
            citypark_content.mkdir(parents=True)
            orphan = root / "FabCache" / "VaultCache" / "ModularDcffe32471e5fV1"
            (orphan / "stage" / "f").mkdir(parents=True)
            (orphan / "stage" / "f" / "chunk").write_bytes(b"downtown west staged bytes")

            store = AssetStore(asset_cache / "assets.jsonl", source_dirs=[citypark_content])
            index = build_local_asset_index(store)

            fab = index["fab_library"]
            self.assertEqual(fab["orphan_download_count"], 1)
            self.assertEqual(fab["orphan_downloads"][0]["path"], str(orphan))
            self.assertGreater(fab["orphan_downloads"][0]["cache_size"], 0)

    def test_orchestrator_writes_run_asset_index_snapshot_before_asset_first_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "cineu_research_system" / "workspace"
            create_demo_workspace(workspace, overwrite=True)

            citypark = root / "CityParkEnv55"
            citypark.mkdir()
            (citypark / "CityParkEnv55.uproject").write_text("{}", encoding="utf-8")
            content = citypark / "Content"
            (content / "CityPark" / "Maps").mkdir(parents=True)
            (content / "AfricanAnimalsPack" / "Zebra" / "Meshes").mkdir(parents=True)
            (content / "AfricanAnimalsPack" / "Zebra" / "Animations").mkdir(parents=True)
            (content / "AfricanAnimalsPack" / "Zebra" / "Materials").mkdir(parents=True)
            (content / "CityPark" / "Maps" / "Showcase.umap").write_bytes(b"showcase")
            (content / "AfricanAnimalsPack" / "Zebra" / "Meshes" / "SK_Zebra.uasset").write_bytes(b"mesh")
            (content / "AfricanAnimalsPack" / "Zebra" / "Animations" / "ANIM_Zebra_WalkTurnR.uasset").write_bytes(b"walk turn anim")
            (content / "AfricanAnimalsPack" / "Zebra" / "Materials" / "M_Zebra.uasset").write_bytes(b"material")
            (content / "AnimalHitchcockZoom.uasset").write_bytes(b"sequence")

            run_dir = CineUOrchestrator(workspace=workspace, knowledge_dir=Path("knowledge")).run(
                "In a park, a zebra is moving forward. The camera focuses on the zebra for Hitchcock zoom."
            )

            snapshot = json.loads((run_dir / "planning" / "local_asset_index_snapshot.json").read_text(encoding="utf-8"))
            env_paths = {asset["ue_path"] for asset in snapshot["environment_candidates"]}
            sequence_paths = {asset["ue_path"] for asset in snapshot["sequence_candidates"]}

            self.assertEqual(snapshot["schema_version"], "cineu.run_asset_index_snapshot.v1")
            self.assertTrue(snapshot["asset_first_ready"])
            self.assertIn("/Game/CityPark/Maps/Showcase", env_paths)
            self.assertIn("/Game/AnimalHitchcockZoom", sequence_paths)

    def test_orchestrator_fails_before_generation_when_target_environment_is_not_indexed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            asset_cache = workspace / "projects" / "demo_project" / "asset_cache"
            gallery = root / "GalleryProject"
            gallery.mkdir()
            (gallery / "GalleryProject.uproject").write_text("{}", encoding="utf-8")
            content = gallery / "Content"
            (content / "Gallery" / "Maps").mkdir(parents=True)
            (content / "Gallery" / "Characters" / "Meshes").mkdir(parents=True)
            (content / "Gallery" / "Characters" / "Animations").mkdir(parents=True)
            (content / "Gallery" / "Maps" / "Showcase.umap").write_bytes(b"map")
            (content / "Gallery" / "Characters" / "Meshes" / "SK_GalleryPerson.uasset").write_bytes(b"mesh")
            (content / "Gallery" / "Characters" / "Animations" / "A_GalleryPerson_Walk.uasset").write_bytes(b"anim")
            store = AssetStore(asset_cache / "assets.jsonl", source_dirs=[content])

            with patch("cineu_demo.engine.AssetStore", return_value=store):
                run_dir = CineUOrchestrator(workspace=workspace, knowledge_dir=Path("knowledge")).run(
                    "In a park, a zebra is moving forward. The camera focuses on the zebra for Hitchcock zoom."
                )

            status = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
            report = json.loads((run_dir / "verification" / "final_report.json").read_text(encoding="utf-8"))
            events = (run_dir / "traces" / "events.jsonl").read_text(encoding="utf-8")
            snapshot = json.loads((run_dir / "planning" / "local_asset_index_snapshot.json").read_text(encoding="utf-8"))

            self.assertEqual(status["status"], "failed")
            self.assertFalse(report["success"])
            self.assertTrue(snapshot["asset_first_ready"])
            self.assertIn("asset_first_preflight_failed", events)
            self.assertNotIn("asset_resolution_failed", events)
            self.assertFalse((run_dir / "planning" / "operations_plan.json").exists())


if __name__ == "__main__":
    unittest.main()
