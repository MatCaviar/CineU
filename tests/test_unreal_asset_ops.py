from __future__ import annotations

from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1] / "unreal_project" / "Plugins" / "CineUDemo" / "Content" / "Python"


def test_asset_ops_imports_outside_unreal(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_asset_ops

    assert cineu_asset_ops.unreal is None
    assert cineu_asset_ops.asset_exists("/Game/Missing") is False


def test_import_assets_uses_unreal_asset_import_task(monkeypatch, tmp_path: Path):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_asset_ops

    source = tmp_path / "sculpture.obj"
    source.write_text("o sculpture\n", encoding="utf-8")
    calls = []

    class FakeTask:
        def __init__(self):
            self.props = {}
            self.imported_object_paths = []

        def set_editor_property(self, name, value):
            self.props[name] = value

    class FakeAssetTools:
        def import_asset_tasks(self, tasks):
            task = tasks[0]
            calls.append(("import", task.props.copy()))
            task.imported_object_paths = [f"{task.props['destination_path']}/{task.props['destination_name']}"]

    class FakeAssetToolsHelpers:
        @staticmethod
        def get_asset_tools():
            return FakeAssetTools()

    class FakeEditorAssetLibrary:
        @staticmethod
        def does_asset_exist(path):
            return False

        @staticmethod
        def save_directory(path, only_if_is_dirty=False, recursive=True):
            calls.append(("save_directory", path, only_if_is_dirty, recursive))

    class FakeUnreal:
        AssetImportTask = FakeTask
        AssetToolsHelpers = FakeAssetToolsHelpers
        EditorAssetLibrary = FakeEditorAssetLibrary

    monkeypatch.setattr(cineu_asset_ops, "unreal", FakeUnreal)

    result = cineu_asset_ops.import_assets(
        [
            {
                "asset_id": "asset_local_sculpture",
                "source_path": str(source),
                "source_type": "local_file",
                "import_required": True,
                "import_destination": "/Game/CineU/Imported/local_file",
                "ue_path": "/Game/CineU/Imported/local_file/sculpture",
            }
        ]
    )

    assert result["assets"][0]["status"] == "imported"
    assert result["assets"][0]["imported_object_paths"] == ["/Game/CineU/Imported/local_file/sculpture"]
    assert calls[0][0] == "import"
    assert calls[0][1]["filename"] == str(source)
    assert calls[0][1]["destination_path"] == "/Game/CineU/Imported/local_file"
    assert calls[0][1]["destination_name"] == "sculpture"


def test_import_assets_selects_expected_skeletal_mesh_from_fbx_outputs(monkeypatch, tmp_path: Path):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_asset_ops

    source = tmp_path / "Zebra.fbx"
    source.write_bytes(b"fbx")

    class FakeTask:
        def __init__(self):
            self.props = {}
            self.imported_object_paths = []

        def set_editor_property(self, name, value):
            self.props[name] = value

    class FakeUnrealObject:
        def __init__(self, class_name):
            self.class_name = class_name

        def get_class(self):
            return self

        def get_name(self):
            return self.class_name

    class FakeAssetTools:
        def import_asset_tasks(self, tasks):
            tasks[0].imported_object_paths = [
                "/Game/CineU/Imported/public_free/Zebra.Zebra",
                "/Game/CineU/Imported/public_free/zebra_Skeleton.zebra_Skeleton",
                "/Game/CineU/Imported/public_free/zebra1.zebra1",
                "/Game/CineU/Imported/public_free/zebra_Anim.zebra_Anim",
            ]

    class FakeAssetToolsHelpers:
        @staticmethod
        def get_asset_tools():
            return FakeAssetTools()

    class FakeEditorAssetLibrary:
        classes = {
            "/Game/CineU/Imported/public_free/Zebra.Zebra": "Material",
            "/Game/CineU/Imported/public_free/zebra_Skeleton.zebra_Skeleton": "Skeleton",
            "/Game/CineU/Imported/public_free/zebra1.zebra1": "SkeletalMesh",
            "/Game/CineU/Imported/public_free/zebra_Anim.zebra_Anim": "AnimSequence",
        }

        @staticmethod
        def does_asset_exist(path):
            return False

        @staticmethod
        def load_asset(path):
            class_name = FakeEditorAssetLibrary.classes.get(path)
            return FakeUnrealObject(class_name) if class_name else None

        @staticmethod
        def save_directory(path, only_if_is_dirty=False, recursive=True):
            return None

    class FakeUnreal:
        AssetImportTask = FakeTask
        AssetToolsHelpers = FakeAssetToolsHelpers
        EditorAssetLibrary = FakeEditorAssetLibrary

    monkeypatch.setattr(cineu_asset_ops, "unreal", FakeUnreal)

    result = cineu_asset_ops.import_assets(
        [
            {
                "asset_id": "asset_public_free_zebra",
                "source_path": str(source),
                "source_type": "public_free",
                "type": "skeletal_mesh",
                "import_required": True,
                "import_destination": "/Game/CineU/Imported/public_free",
                "ue_path": "/Game/CineU/Imported/public_free/zebra",
            }
        ]
    )

    assert result["assets"][0]["status"] == "imported"
    assert result["assets"][0]["ue_path"] == "/Game/CineU/Imported/public_free/zebra1.zebra1"
    assert result["assets"][0]["imported_object_paths"][0] == "/Game/CineU/Imported/public_free/zebra1.zebra1"
    assert result["assets"][0]["imported_animation_paths"] == ["/Game/CineU/Imported/public_free/zebra_Anim.zebra_Anim"]


def test_import_assets_copies_unreal_project_content_bundle(monkeypatch, tmp_path: Path):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_asset_ops

    source_root = tmp_path / "CityParkEnv55" / "Content"
    bundle_root = source_root / "AfricanAnimalsPack" / "Zebra"
    (bundle_root / "Meshes").mkdir(parents=True)
    (bundle_root / "Animations").mkdir(parents=True)
    source = bundle_root / "Meshes" / "SK_Zebra.uasset"
    source.write_bytes(b"mesh")
    (bundle_root / "Animations" / "ANIM_Zebra_Gallop.uasset").write_bytes(b"anim")
    project_content = tmp_path / "CineU_Demo" / "Content"
    scans = []

    class FakePaths:
        @staticmethod
        def project_content_dir():
            return str(project_content)

    class FakeEditorAssetLibrary:
        @staticmethod
        def does_asset_exist(path):
            rel = path.removeprefix("/Game/") + ".uasset"
            return (project_content / Path(rel.replace("/", "\\"))).exists()

        @staticmethod
        def save_directory(path, only_if_is_dirty=False, recursive=True):
            return None

    class FakeAssetRegistry:
        def scan_paths_synchronous(self, paths, force_rescan=True):
            scans.extend(paths)

    class FakeAssetRegistryHelpers:
        @staticmethod
        def get_asset_registry():
            return FakeAssetRegistry()

    class FakeUnreal:
        Paths = FakePaths
        EditorAssetLibrary = FakeEditorAssetLibrary
        AssetRegistryHelpers = FakeAssetRegistryHelpers

    monkeypatch.setattr(cineu_asset_ops, "unreal", FakeUnreal)

    result = cineu_asset_ops.import_assets(
        [
            {
                "asset_id": "asset_ue_project_content_african_zebra",
                "source_path": str(source),
                "source_type": "ue_project_content",
                "import_required": True,
                "import_destination": "/Game/AfricanAnimalsPack/Zebra/Meshes",
                "ue_path": "/Game/AfricanAnimalsPack/Zebra/Meshes/SK_Zebra",
                "provenance": {
                    "ue_content_root": str(source_root),
                    "bundle_root": str(bundle_root),
                    "bundle_package_path": "/Game/AfricanAnimalsPack/Zebra",
                },
            }
        ]
    )

    assert result["assets"][0]["status"] == "imported"
    assert (project_content / "AfricanAnimalsPack" / "Zebra" / "Meshes" / "SK_Zebra.uasset").exists()
    assert (project_content / "AfricanAnimalsPack" / "Zebra" / "Animations" / "ANIM_Zebra_Gallop.uasset").exists()
    assert "/Game/AfricanAnimalsPack/Zebra" in scans


def test_import_assets_copies_twinmotion_tree_shared_dependencies(monkeypatch, tmp_path: Path):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_asset_ops

    source_root = tmp_path / "HillsideProject" / "Content"
    tree_root = source_root / "ExternalAssets" / "Twinmotion" / "Vegetation" / "Trees" / "XF_FicusBenjamina"
    vegetation_common = source_root / "ExternalAssets" / "Twinmotion" / "Vegetation" / "_common" / "VegetationXF"
    master_materials = source_root / "ExternalAssets" / "Twinmotion" / "_common" / "MasterMaterials"
    tree_root.mkdir(parents=True)
    vegetation_common.mkdir(parents=True)
    master_materials.mkdir(parents=True)
    source = tree_root / "SM_A_FicusBenjamina_LOD0.uasset"
    source.write_bytes(b"tree")
    (tree_root / "MI_Leaves.uasset").write_bytes(b"leaves instance")
    (vegetation_common / "M_Leaves.uasset").write_bytes(b"shared leaves material")
    (master_materials / "MI_StdOpaque.uasset").write_bytes(b"shared master material")
    project_content = tmp_path / "CineU_Demo" / "Content"
    scans = []

    class FakePaths:
        @staticmethod
        def project_content_dir():
            return str(project_content)

    class FakeEditorAssetLibrary:
        @staticmethod
        def does_asset_exist(path):
            rel = path.removeprefix("/Game/") + ".uasset"
            return (project_content / Path(rel.replace("/", "\\"))).exists()

    class FakeAssetRegistry:
        def scan_paths_synchronous(self, paths, force_rescan=True):
            scans.extend(paths)

    class FakeAssetRegistryHelpers:
        @staticmethod
        def get_asset_registry():
            return FakeAssetRegistry()

    class FakeUnreal:
        Paths = FakePaths
        EditorAssetLibrary = FakeEditorAssetLibrary
        AssetRegistryHelpers = FakeAssetRegistryHelpers

    monkeypatch.setattr(cineu_asset_ops, "unreal", FakeUnreal)

    result = cineu_asset_ops.import_assets(
        [
            {
                "asset_id": "asset_ue_project_content_externalassets_twinmotion_vegetation_trees_xf_ficusbenjamina_sm_a_ficusbenjamina_lod0",
                "source_path": str(source),
                "source_type": "ue_project_content",
                "type": "static_mesh",
                "import_required": True,
                "import_destination": "/Game/ExternalAssets/Twinmotion/Vegetation/Trees/XF_FicusBenjamina",
                "ue_path": "/Game/ExternalAssets/Twinmotion/Vegetation/Trees/XF_FicusBenjamina/SM_A_FicusBenjamina_LOD0",
                "provenance": {
                    "ue_content_root": str(source_root),
                    "bundle_root": str(tree_root),
                    "bundle_package_path": "/Game/ExternalAssets/Twinmotion/Vegetation/Trees/XF_FicusBenjamina",
                },
            }
        ]
    )

    assert result["assets"][0]["status"] == "imported"
    assert (project_content / "ExternalAssets" / "Twinmotion" / "Vegetation" / "Trees" / "XF_FicusBenjamina" / "SM_A_FicusBenjamina_LOD0.uasset").exists()
    assert (project_content / "ExternalAssets" / "Twinmotion" / "Vegetation" / "_common" / "VegetationXF" / "M_Leaves.uasset").exists()
    assert (project_content / "ExternalAssets" / "Twinmotion" / "_common" / "MasterMaterials" / "MI_StdOpaque.uasset").exists()
    assert "/Game/ExternalAssets/Twinmotion/Vegetation/Trees/XF_FicusBenjamina" in scans
    assert "/Game/ExternalAssets/Twinmotion/Vegetation/_common" in scans
    assert "/Game/ExternalAssets/Twinmotion/_common/MasterMaterials" in scans
