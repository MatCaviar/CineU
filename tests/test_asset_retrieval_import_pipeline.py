from __future__ import annotations

import json
from pathlib import Path

import pytest

from cineu_demo.asset_store import AssetStore
from cineu_demo.agents import AssetAgent, RunContext
from cineu_demo.demo_workspace import create_demo_workspace
from cineu_demo.engine import CineUOrchestrator
from cineu_demo.ledger import FileLedger
from cineu_demo.operation_plan import OperationPlanVerifier
from cineu_demo.preflight import PreconditionVerifier
from cineu_demo.planner import RuleBasedPlanner
from cineu_demo.runner import MockRunner, initial_world_state
from cineu_demo.schemas import Operation
from cineu_demo.template_store import TemplateStore


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_asset_store_discovers_fab_exports_and_prefers_them_over_placeholders(tmp_path: Path):
    workspace = tmp_path / "workspace"
    asset_cache = workspace / "projects" / "demo_project" / "asset_cache"
    source = asset_cache / "fab" / "modern_gallery_painting.fbx"
    source.parent.mkdir(parents=True)
    source.write_text("fbx placeholder bytes", encoding="utf-8")
    source.with_suffix(".cineu_asset.json").write_text(
        json.dumps(
            {
                "name": "Fab Modern Gallery Painting",
                "type": "static_mesh",
                "semantic_tags": ["painting", "gallery", "modern", "wall_art"],
                "functional_tags": ["decor", "wall_art"],
                "bounds_cm": {"extent": [5, 125, 82]},
                "license": {"source": "fab_local_export", "research_allowed": True},
            }
        ),
        encoding="utf-8",
    )
    _write_jsonl(
        asset_cache / "assets.jsonl",
        [
            {
                "schema_version": "cineu.asset.v1",
                "asset_id": "asset_gallery_painting_placeholder",
                "name": "Placeholder Painting",
                "ue_path": "/Game/CineU/Assets/Gallery/SM_FramedPainting",
                "type": "static_mesh",
                "semantic_tags": ["painting", "gallery", "modern", "wall_art"],
                "functional_tags": ["decor", "wall_art"],
                "bounds_cm": {"extent": [6, 130, 85]},
                "license": {"source": "metadata_placeholder", "research_allowed": True},
            }
        ],
    )

    store = AssetStore(asset_cache / "assets.jsonl", source_dirs=[asset_cache])
    match = store.retrieve("modern gallery painting", required_type="static_mesh", required_tags=["wall_art"])

    assert match.source_type == "fab_local"
    assert match.import_required is True
    assert match.source_path == str(source.resolve())
    assert match.ue_path == "/Game/CineU/Imported/fab_local/modern_gallery_painting"
    assert match.import_destination == "/Game/CineU/Imported/fab_local"
    assert match.provenance["catalog"] == "fab"


def test_asset_store_discovers_sources_even_when_asset_index_is_missing(tmp_path: Path):
    asset_cache = tmp_path / "workspace" / "projects" / "demo_project" / "asset_cache"
    source = asset_cache / "fab" / "park_bridge_environment.obj"
    source.parent.mkdir(parents=True)
    source.write_text("o bridge\n", encoding="utf-8")
    source.with_suffix(".cineu_asset.json").write_text(
        json.dumps(
            {
                "name": "Fab Park Bridge Environment",
                "type": "static_mesh",
                "semantic_tags": ["park", "bridge", "environment"],
                "functional_tags": ["set_dressing", "environment"],
                "license": {"source": "fab_local_export", "research_allowed": True},
            }
        ),
        encoding="utf-8",
    )

    store = AssetStore(asset_cache / "assets.jsonl", source_dirs=[asset_cache])
    match = store.retrieve("park bridge environment", required_type="static_mesh", required_tags=["park", "environment"])

    assert match.source_type == "fab_local"
    assert match.source_path == str(source.resolve())


def test_asset_store_auto_discovers_nearby_unreal_resource_roots(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(AssetStore, "_unreal_project_content_roots", lambda self, parent: [])
    asset_cache = tmp_path / "workspace" / "projects" / "demo_project" / "asset_cache"
    resource_root = tmp_path / "RealTimeCompositing" / "UEOL_505_Resources"
    source = resource_root / "HillPath" / "CG Assets" / "park_path_environment.fbx"
    source.parent.mkdir(parents=True)
    source.write_text("fbx placeholder bytes", encoding="utf-8")
    source.with_suffix(".cineu_asset.json").write_text(
        json.dumps(
            {
                "type": "static_mesh",
                "semantic_tags": ["park", "path", "environment"],
                "functional_tags": ["environment", "set"],
                "license": {"source": "local_unreal_resource", "research_allowed": True},
            }
        ),
        encoding="utf-8",
    )
    _write_jsonl(asset_cache / "assets.jsonl", [])

    store = AssetStore(asset_cache / "assets.jsonl")
    match = store.retrieve("park environment", required_type="static_mesh", required_tags=["park", "environment"])

    assert match.source_path == str(source.resolve())
    assert match.source_type == "local_file"
    assert match.provenance["source_root"] == str(resource_root.resolve())


def test_asset_store_auto_discovers_sibling_unreal_project_content_roots(tmp_path: Path):
    asset_cache = tmp_path / "cineu_research_system" / "workspace" / "projects" / "demo_project" / "asset_cache"
    _write_jsonl(asset_cache / "assets.jsonl", [])
    sibling_project = tmp_path / "GameAnimation"
    sibling_project.mkdir()
    (sibling_project / "GameAnimation.uproject").write_text("{}", encoding="utf-8")
    anim_dir = sibling_project / "Content" / "Characters" / "Mannequins" / "Animations"
    anim_dir.mkdir(parents=True)
    (anim_dir / "ANIM_Mannequin_Run.uasset").write_bytes(b"anim")

    store = AssetStore(asset_cache / "assets.jsonl")
    match = store.retrieve("human run animation", required_type="animation", required_tags=["human", "run"])

    assert match.source_type == "ue_project_content"
    assert match.source_path == str((anim_dir / "ANIM_Mannequin_Run.uasset").resolve())
    assert match.ue_path == "/Game/Characters/Mannequins/Animations/ANIM_Mannequin_Run"
    assert match.provenance["ue_content_root"] == str((sibling_project / "Content").resolve())


def test_asset_store_materializes_public_free_catalog_asset_before_retrieval(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(AssetStore, "_unreal_project_content_roots", lambda self, parent: [])
    asset_cache = tmp_path / "workspace" / "projects" / "demo_project" / "asset_cache"
    public_dir = asset_cache / "public"
    public_dir.mkdir(parents=True)
    source = tmp_path / "downloads" / "park_tree.obj"
    source.parent.mkdir()
    source.write_text("o tree\n", encoding="utf-8")
    (public_dir / "public_assets.json").write_text(
        json.dumps(
            [
                {
                    "schema_version": "cineu.asset.v1",
                    "asset_id": "asset_public_free_park_tree",
                    "name": "Public Free Park Tree",
                    "ue_path": "/Game/CineU/Imported/public_free/park_tree",
                    "type": "static_mesh",
                    "semantic_tags": ["park", "tree", "environment"],
                    "functional_tags": ["set_dressing"],
                    "bounds_cm": {"extent": [80, 80, 260]},
                    "license": {"source": "cc0", "research_allowed": True, "commercial_allowed": True},
                    "source_type": "public_free",
                    "import_required": True,
                    "import_destination": "/Game/CineU/Imported/public_free",
                    "provenance": {"catalog": "public_free", "download_url": source.as_uri(), "file_format": "obj"},
                }
            ]
        ),
        encoding="utf-8",
    )
    _write_jsonl(asset_cache / "assets.jsonl", [])

    store = AssetStore(asset_cache / "assets.jsonl", allow_downloads=True)
    match = store.retrieve("park tree environment", required_type="static_mesh", required_tags=["park", "environment"])

    assert match.source_type == "public_free"
    assert match.source_path is not None
    assert Path(match.source_path).read_text(encoding="utf-8") == "o tree\n"
    assert Path(match.source_path).is_relative_to(asset_cache / "public" / "_downloads")
    assert match.provenance["materialized_by"] == "download_url"


def test_asset_store_infers_environment_tags_from_known_local_resource_names(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(AssetStore, "_unreal_project_content_roots", lambda self, parent: [])
    asset_cache = tmp_path / "workspace" / "projects" / "demo_project" / "asset_cache"
    resource_root = tmp_path / "RealTimeCompositing" / "UEOL_505_Resources"
    source = resource_root / "HillPath" / "CG Assets" / "HillPath_Lo.fbx"
    source.parent.mkdir(parents=True)
    source.write_text("fbx placeholder bytes", encoding="utf-8")
    _write_jsonl(asset_cache / "assets.jsonl", [])

    store = AssetStore(asset_cache / "assets.jsonl")
    match = store.retrieve("park path environment", required_type="static_mesh", required_tags=["park", "environment"])

    assert match.source_path == str(source.resolve())
    assert {"park", "path", "environment"}.issubset(set(match.semantic_tags))


def test_asset_store_discovers_nearby_unreal_project_zebra_content(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(AssetStore, "_unreal_project_content_roots", lambda self, parent: [])
    asset_cache = tmp_path / "cineu_research_system" / "workspace" / "projects" / "demo_project" / "asset_cache"
    _write_jsonl(
        asset_cache / "assets.jsonl",
        [
            {
                "schema_version": "cineu.asset.v1",
                "asset_id": "asset_zebra_placeholder",
                "name": "Placeholder Zebra",
                "ue_path": "/Game/CineU/Assets/Animals/Zebra/SK_Zebra",
                "type": "skeletal_mesh",
                "semantic_tags": ["zebra", "animal"],
                "functional_tags": ["run"],
                "bounds_cm": {"extent": [115, 35, 85]},
                "license": {"source": "local_placeholder", "research_allowed": True},
            }
        ],
    )
    zebra_root = tmp_path / "CityParkEnv55" / "Content" / "AfricanAnimalsPack" / "Zebra"
    (zebra_root / "Meshes").mkdir(parents=True)
    (zebra_root / "Animations").mkdir(parents=True)
    (zebra_root / "Meshes" / "SK_Zebra.uasset").write_bytes(b"mesh")
    (zebra_root / "Animations" / "ANIM_Zebra_Gallop.uasset").write_bytes(b"anim")

    store = AssetStore(asset_cache / "assets.jsonl")
    match = store.retrieve("zebra animal quadruped", required_type="skeletal_mesh", required_tags=["zebra", "animal"])

    assert match.source_type == "ue_project_content"
    assert match.import_required is True
    assert match.ue_path == "/Game/AfricanAnimalsPack/Zebra/Meshes/SK_Zebra"
    assert match.animations[0]["path"] == "/Game/AfricanAnimalsPack/Zebra/Animations/ANIM_Zebra_Gallop"
    assert match.license["source"] == "ue_project_content"


def test_asset_store_marks_current_project_content_as_available_not_importable(tmp_path: Path):
    asset_cache = tmp_path / "cineu_research_system" / "workspace" / "projects" / "demo_project" / "asset_cache"
    _write_jsonl(asset_cache / "assets.jsonl", [])
    project = tmp_path / "cineu_research_system" / "unreal_project"
    project.mkdir(parents=True)
    (project / "CineU_Demo.uproject").write_text("{}", encoding="utf-8")
    zebra_root = project / "Content" / "AfricanAnimalsPack" / "Zebra"
    (zebra_root / "Meshes").mkdir(parents=True)
    (zebra_root / "Animations").mkdir(parents=True)
    (zebra_root / "Materials").mkdir(parents=True)
    (zebra_root / "Meshes" / "SK_Zebra.uasset").write_bytes(b"mesh")
    (zebra_root / "Animations" / "ANIM_Zebra_Gallop.uasset").write_bytes(b"anim")
    (zebra_root / "Materials" / "M_Zebra.uasset").write_bytes(b"material")

    store = AssetStore(asset_cache / "assets.jsonl")
    match = store.retrieve("zebra animal quadruped", required_type="skeletal_mesh", required_tags=["zebra", "animal"])

    assert match.source_type == "ue_project_content"
    assert match.import_required is False
    assert match.ue_path == "/Game/AfricanAnimalsPack/Zebra/Meshes/SK_Zebra"
    assert match.materials == ["/Game/AfricanAnimalsPack/Zebra/Materials/M_Zebra"]


def test_asset_store_prefers_semantic_vault_character_over_generic_project_character(tmp_path: Path):
    asset_cache = tmp_path / "cineu_research_system" / "workspace" / "projects" / "demo_project" / "asset_cache"
    _write_jsonl(asset_cache / "assets.jsonl", [])
    project = tmp_path / "cineu_research_system" / "unreal_project"
    project.mkdir(parents=True)
    (project / "CineU_Demo.uproject").write_text("{}", encoding="utf-8")
    zebra_meshes = project / "Content" / "AfricanAnimalsPack" / "Zebra" / "Meshes"
    zebra_meshes.mkdir(parents=True)
    (zebra_meshes / "SK_Zebra.uasset").write_bytes(b"mesh")
    vault_content = tmp_path / "EpicGamesLauncher" / "VaultCache" / "WerewolfPackV1" / "data" / "Content"
    werewolf_meshes = vault_content / "Werewolf" / "Mesh" / "Full"
    werewolf_meshes.mkdir(parents=True)
    (werewolf_meshes / "SK_Werewolf_Full1.uasset").write_bytes(b"mesh")

    store = AssetStore(asset_cache / "assets.jsonl", source_dirs=[project / "Content", vault_content])
    match = store.retrieve("werewolf character", required_type="skeletal_mesh", required_tags=["werewolf", "character"])

    assert match.source_type == "fab_local"
    assert match.import_required is True
    assert match.ue_path == "/Game/Werewolf/Mesh/Full/SK_Werewolf_Full1"


def test_asset_store_prefers_current_project_asset_over_duplicate_vault_asset(tmp_path: Path):
    asset_cache = tmp_path / "cineu_research_system" / "workspace" / "projects" / "demo_project" / "asset_cache"
    _write_jsonl(asset_cache / "assets.jsonl", [])
    project = tmp_path / "cineu_research_system" / "unreal_project"
    project.mkdir(parents=True)
    (project / "CineU_Demo.uproject").write_text("{}", encoding="utf-8")
    project_meshes = project / "Content" / "AfricanAnimalsPack" / "Zebra" / "Meshes"
    project_meshes.mkdir(parents=True)
    (project_meshes / "SK_Zebra.uasset").write_bytes(b"project mesh")
    vault_content = tmp_path / "EpicGamesLauncher" / "VaultCache" / "AfricanAnimalsPackV1" / "data" / "Content"
    vault_meshes = vault_content / "AfricanAnimalsPack" / "Zebra" / "Meshes"
    vault_meshes.mkdir(parents=True)
    (vault_meshes / "SK_Zebra.uasset").write_bytes(b"vault mesh")

    store = AssetStore(asset_cache / "assets.jsonl", source_dirs=[vault_content, project / "Content"])
    match = store.retrieve("zebra animal quadruped", required_type="skeletal_mesh", required_tags=["zebra", "animal"])

    assert match.source_path == str((project_meshes / "SK_Zebra.uasset").resolve())
    assert match.import_required is False


def test_asset_store_prefers_current_project_showcase_level_for_environment(tmp_path: Path):
    asset_cache = tmp_path / "cineu_research_system" / "workspace" / "projects" / "demo_project" / "asset_cache"
    _write_jsonl(asset_cache / "assets.jsonl", [])
    project = tmp_path / "cineu_research_system" / "unreal_project"
    project.mkdir(parents=True)
    (project / "CineU_Demo.uproject").write_text("{}", encoding="utf-8")
    maps = project / "Content" / "CityPark" / "Maps"
    maps.mkdir(parents=True)
    (maps / "Overview.umap").write_bytes(b"overview")
    (maps / "Showcase.umap").write_bytes(b"showcase")

    store = AssetStore(asset_cache / "assets.jsonl", source_dirs=[project / "Content"])
    match = store.retrieve("park environment", required_type="level", required_tags=["park", "environment"])

    assert match.ue_path == "/Game/CityPark/Maps/Showcase"
    assert match.import_required is False


def test_asset_store_discovers_nearby_unreal_project_park_level(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(AssetStore, "_unreal_project_content_roots", lambda self, parent: [])
    asset_cache = tmp_path / "cineu_research_system" / "workspace" / "projects" / "demo_project" / "asset_cache"
    _write_jsonl(asset_cache / "assets.jsonl", [])
    citypark = tmp_path / "CityParkEnv55" / "Content" / "CityPark"
    maps = citypark / "Maps"
    meshes = citypark / "Meshes" / "Road"
    maps.mkdir(parents=True)
    meshes.mkdir(parents=True)
    (maps / "Overview.umap").write_bytes(b"map")
    (maps / "Showcase.umap").write_bytes(b"map")
    (meshes / "SM_ParkPath1_1.uasset").write_bytes(b"mesh")

    store = AssetStore(asset_cache / "assets.jsonl")
    match = store.retrieve("park environment", required_type="level", required_tags=["park", "environment"])

    assert match.type == "level"
    assert match.source_type == "ue_project_content"
    assert match.ue_path == "/Game/CityPark/Maps/Showcase"
    assert "park" in match.semantic_tags
    assert "environment" in match.semantic_tags
    assert match.provenance["bundle_root"].endswith(str(Path("CityPark")))
    assert match.provenance["bundle_package_path"] == "/Game/CityPark"


def test_asset_store_discovers_citypark_hitchcock_level_sequence(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(AssetStore, "_unreal_project_content_roots", lambda self, parent: [])
    asset_cache = tmp_path / "cineu_research_system" / "workspace" / "projects" / "demo_project" / "asset_cache"
    _write_jsonl(asset_cache / "assets.jsonl", [])
    content = tmp_path / "CityParkEnv55" / "Content"
    content.mkdir(parents=True)
    sequence = content / "AnimalHitchcockZoom.uasset"
    sequence.write_bytes(b"sequence")

    store = AssetStore(asset_cache / "assets.jsonl")
    match = store.retrieve(
        "park zebra animal hitchcock zoom level sequence",
        required_type="level_sequence",
        required_tags=["animal", "hitchcock", "sequence"],
    )

    assert match.type == "level_sequence"
    assert match.source_type == "ue_project_content"
    assert match.source_path == str(sequence.resolve())
    assert match.ue_path == "/Game/AnimalHitchcockZoom"
    assert match.import_required is True
    assert {"animal", "hitchcock", "sequence"}.issubset(set(match.semantic_tags))


def test_pipeline_generates_citypark_hitchcock_sequence_from_assets(tmp_path: Path):
    workspace = tmp_path / "cineu_research_system" / "workspace"
    create_demo_workspace(workspace, overwrite=True)
    content = tmp_path / "CityParkEnv55" / "Content"
    (content / "CityPark" / "Maps").mkdir(parents=True)
    (content / "AfricanAnimalsPack" / "Zebra" / "Meshes").mkdir(parents=True)
    (content / "AfricanAnimalsPack" / "Zebra" / "Animations").mkdir(parents=True)
    (content / "AfricanAnimalsPack" / "Zebra" / "Materials").mkdir(parents=True)
    (content / "CityPark" / "Maps" / "Showcase.umap").write_bytes(b"showcase")
    (content / "AfricanAnimalsPack" / "Zebra" / "Meshes" / "SK_Zebra.uasset").write_bytes(b"mesh")
    (content / "AfricanAnimalsPack" / "Zebra" / "Animations" / "ANIM_Zebra_Gallop.uasset").write_bytes(b"anim")
    (content / "AfricanAnimalsPack" / "Zebra" / "Animations" / "ANIM_Zebra_WalkTurnR.uasset").write_bytes(b"walk turn anim")
    (content / "AfricanAnimalsPack" / "Zebra" / "Materials" / "M_Zebra.uasset").write_bytes(b"material")
    (content / "AnimalHitchcockZoom.uasset").write_bytes(b"sequence")
    (content / "AnimalHitchcockZoom_ablation.uasset").write_bytes(b"subject framed sequence")
    capture = tmp_path / "CityParkEnv55" / "Saved" / "VideoCaptures" / "Showcase_(2).avi"
    capture.parent.mkdir(parents=True)
    capture.write_bytes(b"existing citypark capture")

    run_dir = CineUOrchestrator(workspace=workspace, knowledge_dir=Path("knowledge")).run(
        "In a park, a zebra is moving forward. The camera focuses on the zebra for Hitchcock zoom."
    )

    plan = json.loads((run_dir / "planning" / "operations_plan.json").read_text(encoding="utf-8"))
    op_types = [op["type"] for op in plan["operations"]]
    render_op = next(op for op in plan["operations"] if op["type"] == "render.preview")
    seq_op = next(op for op in plan["operations"] if op["type"] == "sequence.use_existing")
    task_spec = json.loads((run_dir / "planning" / "task_spec.json").read_text(encoding="utf-8"))
    sequence_retrieval = json.loads((run_dir / "planning" / "sequence_asset_retrieval.json").read_text(encoding="utf-8"))
    animation_retrieval = json.loads((run_dir / "planning" / "animation_asset_retrieval.json").read_text(encoding="utf-8"))
    state = json.loads((run_dir / "snapshots" / "world_final.json").read_text(encoding="utf-8"))

    shot_metadata = task_spec["camera"]["shots"][0]["metadata"]
    assert shot_metadata["reference_sequence_path"] == "/Game/AnimalHitchcockZoom"
    assert shot_metadata["reference_capture_path"] == "Saved/VideoCaptures/Showcase_(2).avi"
    assert shot_metadata["reference_capture_start_frame"] == 10
    assert shot_metadata["reference_capture_end_frame"] == 330
    assert shot_metadata["reference_output_fps"] == 30
    assert shot_metadata["reference_output_end_frame"] == 166
    assert sequence_retrieval["records"][0]["selected_asset_id"] == "asset_ue_project_content_animalhitchcockzoom"
    assert animation_retrieval["records"][0]["query"] == "zebra walk turn animation"
    assert animation_retrieval["records"][0]["selected_asset_id"] == "asset_ue_project_content_africananimalspack_zebra_animations_anim_zebra_walkturnr"
    assert seq_op["inputs"]["sequence_path"] == "/Game/AnimalHitchcockZoom"
    assert seq_op["inputs"]["sequence_asset"]["asset_id"] == "asset_ue_project_content_animalhitchcockzoom"
    assert "sequence.use_existing" in op_types
    assert "sequence.init" not in op_types
    assert "entity.spawn_many" not in op_types
    assert "camera.hitchcock_zoom" not in op_types
    assert "animation.add_tracks" not in op_types
    assert "sequence.camera_cut" not in op_types
    assert render_op["inputs"]["start_frame"] == 0
    assert render_op["inputs"]["end_frame"] == 320
    assert render_op["inputs"]["fps"] == 30
    assert render_op["inputs"]["reference_capture_source"] == str(capture.resolve())
    assert render_op["inputs"]["reference_capture_start_frame"] == 10
    assert render_op["inputs"]["reference_capture_end_frame"] == 330
    assert render_op["inputs"]["native_capture_start_frame"] == 10
    assert render_op["inputs"]["native_capture_end_frame"] == 330
    assert render_op["inputs"]["sequence_path"] == "/Game/AnimalHitchcockZoom"
    assert "/Game/AnimalHitchcockZoom" in state["sequences"]
    seq = state["sequences"]["/Game/AnimalHitchcockZoom"]
    assert seq["source_asset_id"] == "asset_ue_project_content_animalhitchcockzoom"
    assert seq["camera_cuts"] == [{"camera_name": "NativeSequenceCamera", "shot_id": "shot_001", "start_frame": 0, "end_frame": 320}]


def test_pipeline_imports_external_park_dressing_assets_before_environment_setup(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "cineu_research_system" / "workspace"
    create_demo_workspace(workspace, overwrite=True)
    content = tmp_path / "CityParkEnv55" / "Content"
    (content / "CityPark" / "Maps").mkdir(parents=True)
    (content / "AfricanAnimalsPack" / "Zebra" / "Meshes").mkdir(parents=True)
    (content / "AfricanAnimalsPack" / "Zebra" / "Animations").mkdir(parents=True)
    (content / "CityPark" / "Maps" / "Showcase.umap").write_bytes(b"showcase")
    (content / "AfricanAnimalsPack" / "Zebra" / "Meshes" / "SK_Zebra.uasset").write_bytes(b"mesh")
    (content / "AfricanAnimalsPack" / "Zebra" / "Animations" / "ANIM_Zebra_Gallop.uasset").write_bytes(b"anim")
    (content / "AnimalHitchcockZoom_ablation.uasset").write_bytes(b"sequence")
    hillside = tmp_path / "HillsideProject"
    hillside.mkdir()
    (hillside / "HillsideProject.uproject").write_text("{}", encoding="utf-8")
    tree_root = hillside / "Content" / "ExternalAssets" / "Twinmotion" / "Vegetation" / "Trees" / "XF_FicusBenjamina"
    tree_root.mkdir(parents=True)
    (tree_root / "SM_A_FicusBenjamina_LOD0.uasset").write_bytes(b"tree mesh")
    (tree_root / "MI_Leaves.uasset").write_bytes(b"leaves material")
    (tree_root / "textures").mkdir()
    (tree_root / "textures" / "T_FicusBenjaminaLeaf01_BC.uasset").write_bytes(b"leaf texture")
    from cineu_demo import engine as engine_module

    real_asset_store = engine_module.AssetStore
    monkeypatch.setattr(
        engine_module,
        "AssetStore",
        lambda assets_path, include_global_libraries=True: real_asset_store(
            assets_path,
            source_dirs=[content, hillside / "Content"],
            include_global_libraries=False,
        ),
    )

    run_dir = CineUOrchestrator(workspace=workspace, knowledge_dir=Path("knowledge")).run(
        "In a park, a zebra is moving forward. The camera focuses on the zebra for Hitchcock zoom."
    )

    plan = json.loads((run_dir / "planning" / "operations_plan.json").read_text(encoding="utf-8"))
    op_types = [op["type"] for op in plan["operations"]]
    import_op = plan["operations"][op_types.index("asset.import_many")]
    env_op = plan["operations"][op_types.index("env.setup")]
    dressing_retrieval = json.loads((run_dir / "planning" / "environment_dressing_asset_retrieval.json").read_text(encoding="utf-8"))
    state = json.loads((run_dir / "snapshots" / "world_final.json").read_text(encoding="utf-8"))

    assert op_types.index("asset.import_many") < op_types.index("env.setup")
    assert env_op["inputs"]["dressing_assets"][0]["ue_path"] == "/Game/ExternalAssets/Twinmotion/Vegetation/Trees/XF_FicusBenjamina/SM_A_FicusBenjamina_LOD0"
    assert env_op["inputs"]["dressing_assets"][0]["import_required"] is True
    assert any(asset["asset_id"] == env_op["inputs"]["dressing_assets"][0]["asset_id"] for asset in import_op["inputs"]["assets"])
    assert dressing_retrieval["records"][0]["status"] == "hit:ue_project_content"
    assert dressing_retrieval["records"][0]["selected_asset_ids"] == [env_op["inputs"]["dressing_assets"][0]["asset_id"]]
    assert state["asset_imports"][env_op["inputs"]["dressing_assets"][0]["asset_id"]]["status"] == "imported"


def test_environment_dressing_reuses_preferred_canopy_assets_already_in_project_before_new_imports(tmp_path: Path):
    project_root = tmp_path / "cineu_research_system"
    workspace = project_root / "workspace"
    create_demo_workspace(workspace, overwrite=True)
    current_content = project_root / "unreal_project" / "Content"
    current_content.mkdir(parents=True)
    (project_root / "unreal_project" / "CineU_Demo.uproject").write_text("{}", encoding="utf-8")
    for species in ["XF_FicusBenjamina", "XF_TiliaAmericana"]:
        tree_root = current_content / "ExternalAssets" / "Twinmotion" / "Vegetation" / "Trees" / species
        tree_root.mkdir(parents=True)
        mesh_name = "SM_A_FicusBenjamina_LOD0.uasset" if species == "XF_FicusBenjamina" else "SM_A_TiliaAmericana_LOD0.uasset"
        (tree_root / mesh_name).write_bytes(b"already imported tree mesh")
        (tree_root / "MI_Leaves.uasset").write_bytes(b"leaf material")
        (tree_root / "T_Leaf_BC.uasset").write_bytes(b"leaf texture")
    hillside_content = tmp_path / "HillsideProject" / "Content"
    for species, mesh_name in [
        ("USA_Pack/XF_BetulaPapyrifera", "SM_BetulaPapyrifera_A_LOD0.uasset"),
        ("USA_Pack/XF_CalocedrusDecurrens", "SM_Y_CalocedrusDecurrens_LOD0.uasset"),
    ]:
        tree_root = hillside_content / "ExternalAssets" / "Twinmotion" / "Vegetation" / "Trees" / species
        tree_root.mkdir(parents=True)
        (tree_root / mesh_name).write_bytes(b"external tree mesh")
        (tree_root / "MI_Leaves.uasset").write_bytes(b"leaf material")
        (tree_root / "T_Leaf_BC.uasset").write_bytes(b"leaf texture")

    task, _, _ = RuleBasedPlanner().plan(
        "In a park, a zebra is moving forward. The camera focuses on the zebra for Hitchcock zoom."
    )
    asset_store = AssetStore(
        workspace / "projects" / "demo_project" / "asset_cache" / "assets.jsonl",
        source_dirs=[current_content, hillside_content],
        include_global_libraries=False,
    )
    ctx = RunContext(
        run_id="run_test_asset_reuse",
        workspace=workspace,
        project_id="demo_project",
        project_dir=workspace / "projects" / "demo_project",
        knowledge_dir=Path("knowledge"),
        ledger=FileLedger(workspace, "run_test_asset_reuse"),
        asset_store=asset_store,
        template_store=TemplateStore(Path("knowledge/templates")),
        task=task,
    )

    selected = AssetAgent().retrieve_environment_dressing(ctx)

    selected_paths = [asset.ue_path for asset in selected]
    assert selected_paths == [
        "/Game/ExternalAssets/Twinmotion/Vegetation/Trees/XF_FicusBenjamina/SM_A_FicusBenjamina_LOD0",
        "/Game/ExternalAssets/Twinmotion/Vegetation/Trees/XF_TiliaAmericana/SM_A_TiliaAmericana_LOD0",
    ]
    assert [asset.import_required for asset in selected] == [False, False]


def test_environment_dressing_prefers_citypark_collection_trees_over_twinmotion_canopies(tmp_path: Path):
    project_root = tmp_path / "cineu_research_system"
    workspace = project_root / "workspace"
    create_demo_workspace(workspace, overwrite=True)
    current_content = project_root / "unreal_project" / "Content"
    current_content.mkdir(parents=True)
    (project_root / "unreal_project" / "CineU_Demo.uproject").write_text("{}", encoding="utf-8")
    for mesh_name in ["SM_WeepingWillow01.uasset", "SM_Elm02.uasset", "SM_Maple08.uasset"]:
        tree_root = current_content / "CityPark" / "Meshes" / "Flora" / "Trees"
        tree_root.mkdir(parents=True, exist_ok=True)
        (tree_root / mesh_name).write_bytes(b"city park collection tree mesh")
    for species in ["XF_FicusBenjamina", "XF_TiliaAmericana"]:
        tree_root = current_content / "ExternalAssets" / "Twinmotion" / "Vegetation" / "Trees" / species
        tree_root.mkdir(parents=True)
        mesh_name = "SM_A_FicusBenjamina_LOD0.uasset" if species == "XF_FicusBenjamina" else "SM_A_TiliaAmericana_LOD0.uasset"
        (tree_root / mesh_name).write_bytes(b"already imported twinmotion tree mesh")

    task, _, _ = RuleBasedPlanner().plan(
        "In a park, a zebra is moving forward. The camera focuses on the zebra for Hitchcock zoom."
    )
    asset_store = AssetStore(
        workspace / "projects" / "demo_project" / "asset_cache" / "assets.jsonl",
        source_dirs=[current_content],
        include_global_libraries=False,
    )
    ctx = RunContext(
        run_id="run_test_citypark_dressing",
        workspace=workspace,
        project_id="demo_project",
        project_dir=workspace / "projects" / "demo_project",
        knowledge_dir=Path("knowledge"),
        ledger=FileLedger(workspace, "run_test_citypark_dressing"),
        asset_store=asset_store,
        template_store=TemplateStore(Path("knowledge/templates")),
        task=task,
    )

    selected = AssetAgent().retrieve_environment_dressing(ctx)

    selected_paths = [asset.ue_path for asset in selected]
    assert selected_paths == [
        "/Game/CityPark/Meshes/Flora/Trees/SM_WeepingWillow01",
        "/Game/CityPark/Meshes/Flora/Trees/SM_Maple08",
    ]
    assert [asset.import_required for asset in selected] == [False, False]


def test_asset_store_rejects_unrelated_content_even_when_source_root_mentions_park(tmp_path: Path):
    asset_cache = tmp_path / "cineu_research_system" / "workspace" / "projects" / "demo_project" / "asset_cache"
    _write_jsonl(asset_cache / "assets.jsonl", [])
    animal_maps = tmp_path / "CityParkEnv55" / "Content" / "AfricanAnimalsPack" / "Zebra" / "Maps"
    animal_maps.mkdir(parents=True)
    (animal_maps / "Overview.umap").write_bytes(b"animal map")

    store = AssetStore(asset_cache / "assets.jsonl", source_dirs=[tmp_path / "CityParkEnv55" / "Content"])

    with pytest.raises(LookupError):
        store.retrieve("park environment", required_type="level", required_tags=["park", "environment"])


def test_asset_store_ranks_specific_query_terms_over_generic_environment_matches(tmp_path: Path):
    asset_cache = tmp_path / "cineu_research_system" / "workspace" / "projects" / "demo_project" / "asset_cache"
    _write_jsonl(asset_cache / "assets.jsonl", [])
    project = tmp_path / "cineu_research_system" / "unreal_project"
    project.mkdir(parents=True)
    (project / "CineU_Demo.uproject").write_text("{}", encoding="utf-8")
    content = project / "Content"
    buildings = content / "CityPark" / "Meshes" / "Buildings"
    roads = content / "CityPark" / "Meshes" / "Road"
    buildings.mkdir(parents=True)
    roads.mkdir(parents=True)
    (buildings / "SM_CafeBuilding01.uasset").write_bytes(b"building")
    (roads / "SM_Bridge03_1.uasset").write_bytes(b"bridge")

    store = AssetStore(asset_cache / "assets.jsonl", source_dirs=[content])
    match = store.retrieve("park bridge environment", required_type="static_mesh", required_tags=["park", "environment"])

    assert match.ue_path == "/Game/CityPark/Meshes/Road/SM_Bridge03_1"


def test_asset_store_discovers_epic_vaultcache_content_roots_from_environment(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(AssetStore, "_nearby_unreal_resource_roots", lambda self: [])
    asset_cache = tmp_path / "cineu_research_system" / "workspace" / "projects" / "demo_project" / "asset_cache"
    _write_jsonl(asset_cache / "assets.jsonl", [])
    vault = tmp_path / "EpicGamesLauncher" / "VaultCache"
    citypark_content = vault / "CityParkPackV1" / "data" / "Content"
    maps = citypark_content / "CityPark" / "Maps"
    maps.mkdir(parents=True)
    (maps / "Showcase.umap").write_bytes(b"map")
    monkeypatch.setenv("CINEU_EPIC_VAULT_DIRS", str(vault))

    store = AssetStore(asset_cache / "assets.jsonl")
    match = store.retrieve("park environment", required_type="level", required_tags=["park", "environment"])

    assert match.source_type == "fab_local"
    assert match.source_path == str((maps / "Showcase.umap").resolve())
    assert match.ue_path == "/Game/CityPark/Maps/Showcase"
    assert match.import_required is True
    assert match.provenance["catalog"] == "fab"
    assert match.provenance["ue_content_root"] == str(citypark_content.resolve())
    assert match.provenance["source_root"] == str(citypark_content.resolve())


def test_asset_store_can_enable_global_epic_vaultcache_scan_without_env_flag(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(AssetStore, "_nearby_unreal_resource_roots", lambda self: [])
    asset_cache = tmp_path / "workspace" / "projects" / "demo_project" / "asset_cache"
    _write_jsonl(asset_cache / "assets.jsonl", [])
    program_data = tmp_path / "ProgramData"
    content = program_data / "Epic" / "EpicGamesLauncher" / "VaultCache" / "ParkPackV1" / "data" / "Content"
    meshes = content / "ParkPack" / "Meshes"
    meshes.mkdir(parents=True)
    (meshes / "SM_ParkBridge.uasset").write_bytes(b"mesh")
    monkeypatch.setenv("ProgramData", str(program_data))
    monkeypatch.delenv("CINEU_ENABLE_GLOBAL_ASSET_SCAN", raising=False)
    monkeypatch.delenv("CINEU_EPIC_VAULT_DIRS", raising=False)

    isolated = AssetStore(asset_cache / "assets.jsonl")
    assert not any(asset.source_type == "fab_local" for asset in isolated.list_assets())

    store = AssetStore(asset_cache / "assets.jsonl", include_global_libraries=True)
    match = store.retrieve("park bridge environment", required_type="static_mesh", required_tags=["park", "environment"])

    assert match.source_type == "fab_local"
    assert match.ue_path == "/Game/ParkPack/Meshes/SM_ParkBridge"


def test_asset_store_discovers_epic_vaultcache_entity_and_animation_packages(tmp_path: Path):
    asset_cache = tmp_path / "cineu_research_system" / "workspace" / "projects" / "demo_project" / "asset_cache"
    _write_jsonl(asset_cache / "assets.jsonl", [])
    content = tmp_path / "EpicGamesLauncher" / "VaultCache" / "AfricanAnimalsPackV1" / "data" / "Content"
    zebra_root = content / "AfricanAnimalsPack" / "Zebra"
    (zebra_root / "Meshes").mkdir(parents=True)
    (zebra_root / "Animations").mkdir(parents=True)
    mesh = zebra_root / "Meshes" / "SK_Zebra.uasset"
    anim = zebra_root / "Animations" / "ANIM_Zebra_Gallop.uasset"
    mesh.write_bytes(b"mesh")
    anim.write_bytes(b"anim")

    store = AssetStore(asset_cache / "assets.jsonl", source_dirs=[content])
    mesh_match = store.retrieve("zebra animal quadruped", required_type="skeletal_mesh", required_tags=["zebra", "animal"])
    anim_match = store.retrieve("zebra run animation", required_type="animation", required_tags=["zebra", "run"])

    assert mesh_match.source_type == "fab_local"
    assert mesh_match.ue_path == "/Game/AfricanAnimalsPack/Zebra/Meshes/SK_Zebra"
    assert mesh_match.animations[0]["path"] == "/Game/AfricanAnimalsPack/Zebra/Animations/ANIM_Zebra_Gallop"
    assert mesh_match.provenance["bundle_package_path"] == "/Game/AfricanAnimalsPack/Zebra"
    assert anim_match.source_type == "fab_local"
    assert anim_match.source_path == str(anim.resolve())
    assert anim_match.ue_path == "/Game/AfricanAnimalsPack/Zebra/Animations/ANIM_Zebra_Gallop"


def test_asset_store_tags_unreal_animation_assets_for_strict_animation_retrieval(tmp_path: Path):
    asset_cache = tmp_path / "cineu_research_system" / "workspace" / "projects" / "demo_project" / "asset_cache"
    _write_jsonl(asset_cache / "assets.jsonl", [])
    project = tmp_path / "cineu_research_system" / "unreal_project"
    project.mkdir(parents=True)
    (project / "CineU_Demo.uproject").write_text("{}", encoding="utf-8")
    anim_dir = project / "Content" / "AfricanAnimalsPack" / "Zebra" / "Animations"
    anim_dir.mkdir(parents=True)
    anim = anim_dir / "ANIM_Zebra_Gallop.uasset"
    anim.write_bytes(b"anim")

    store = AssetStore(asset_cache / "assets.jsonl")
    match = store.retrieve("zebra run animation", required_type="animation", required_tags=["zebra", "run", "animation"])

    assert match.source_type == "ue_project_content"
    assert match.import_required is False
    assert match.ue_path == "/Game/AfricanAnimalsPack/Zebra/Animations/ANIM_Zebra_Gallop"


def test_asset_store_ranks_specific_unreal_animation_motion_over_generic_locomotion(tmp_path: Path):
    asset_cache = tmp_path / "cineu_research_system" / "workspace" / "projects" / "demo_project" / "asset_cache"
    _write_jsonl(asset_cache / "assets.jsonl", [])
    project = tmp_path / "cineu_research_system" / "unreal_project"
    project.mkdir(parents=True)
    (project / "CineU_Demo.uproject").write_text("{}", encoding="utf-8")
    anim_dir = project / "Content" / "AfricanAnimalsPack" / "Zebra" / "Animations"
    anim_dir.mkdir(parents=True)
    (anim_dir / "ANIM_Zebra_Gallop.uasset").write_bytes(b"gallop")
    (anim_dir / "ANIM_Zebra_Walk.uasset").write_bytes(b"walk")

    store = AssetStore(asset_cache / "assets.jsonl")
    match = store.retrieve("zebra walk animation", required_type="animation", required_tags=["zebra", "walk", "animation"])

    assert match.ue_path == "/Game/AfricanAnimalsPack/Zebra/Animations/ANIM_Zebra_Walk"


def test_asset_store_prefers_installed_project_zebra_over_importable_public_zebra(tmp_path: Path):
    asset_cache = tmp_path / "cineu_research_system" / "workspace" / "projects" / "demo_project" / "asset_cache"
    _write_jsonl(asset_cache / "assets.jsonl", [])
    project = tmp_path / "cineu_research_system" / "unreal_project"
    project.mkdir(parents=True)
    (project / "CineU_Demo.uproject").write_text("{}", encoding="utf-8")
    project_meshes = project / "Content" / "AfricanAnimalsPack" / "Zebra" / "Meshes"
    project_meshes.mkdir(parents=True)
    (project_meshes / "SK_Zebra.uasset").write_bytes(b"project mesh")
    project_anims = project / "Content" / "AfricanAnimalsPack" / "Zebra" / "Animations"
    project_anims.mkdir(parents=True)
    (project_anims / "ANIM_Zebra_Gallop.uasset").write_bytes(b"project animation")
    public = asset_cache / "public" / "cadnav_animated_zebra"
    public.mkdir(parents=True)
    fbx = public / "Zebra.fbx"
    fbx.write_bytes(b"fbx")
    fbx.with_suffix(".cineu_asset.json").write_text(
        json.dumps(
            {
                "name": "CadNav Animated Textured Zebra",
                "type": "skeletal_mesh",
                "semantic_tags": ["zebra", "animal", "quadruped", "textured", "high_detail"],
                "functional_tags": ["animated", "run", "walk", "textured"],
                "materials": ["Zebra.png"],
                "license": {"source": "cadnav_free_noncommercial", "research_allowed": True, "commercial_allowed": False},
            }
        ),
        encoding="utf-8",
    )

    store = AssetStore(asset_cache / "assets.jsonl", source_dirs=[project / "Content", asset_cache / "public"])
    match = store.retrieve("zebra animal quadruped textured", required_type="skeletal_mesh", required_tags=["zebra", "animal"])

    assert match.source_type == "ue_project_content"
    assert match.import_required is False
    assert match.source_path == str((project_meshes / "SK_Zebra.uasset").resolve())
    assert match.ue_path == "/Game/AfricanAnimalsPack/Zebra/Meshes/SK_Zebra"
    assert match.animations[0]["path"] == "/Game/AfricanAnimalsPack/Zebra/Animations/ANIM_Zebra_Gallop"


def test_asset_store_filters_unspawnable_unreal_auxiliary_assets(tmp_path: Path):
    asset_cache = tmp_path / "cineu_research_system" / "workspace" / "projects" / "demo_project" / "asset_cache"
    _write_jsonl(asset_cache / "assets.jsonl", [])
    content = tmp_path / "CityParkEnv55" / "Content"
    park = content / "CityPark"
    (park / "Meshes" / "Road").mkdir(parents=True)
    (park / "Maps" / "Showcase_sharedassets").mkdir(parents=True)
    (park / "Materials" / "BaseMaterial").mkdir(parents=True)
    (park / "Meshes" / "Road" / "SM_ParkPath1_1.uasset").write_bytes(b"mesh")
    (park / "Maps" / "Showcase_sharedassets" / "1_LayerInfo.uasset").write_bytes(b"layer")
    (park / "Materials" / "BaseMaterial" / "M_ParkPath.uasset").write_bytes(b"material")
    zebra_meshes = content / "AfricanAnimalsPack" / "Zebra" / "Meshes"
    zebra_meshes.mkdir(parents=True)
    (zebra_meshes / "SK_Zebra.uasset").write_bytes(b"mesh")
    (zebra_meshes / "SK_Zebra_Skeleton.uasset").write_bytes(b"skeleton")
    (zebra_meshes / "SK_Zebra_PhysicsAsset.uasset").write_bytes(b"physics")

    store = AssetStore(asset_cache / "assets.jsonl", source_dirs=[content])
    any_candidates = store.search("park path environment", required_type="any", required_tags=["park", "environment"])
    static_candidates = store.search("park path environment", required_type="static_mesh", required_tags=["park", "environment"])
    skeletal_candidates = store.search("zebra animal quadruped", required_type="skeletal_mesh", required_tags=["zebra", "animal"])
    material_candidates = store.search("park path material", required_type="material", required_tags=["park"])
    other_candidates = store.search("layer info", required_type="other")

    assert all(item["asset"].type not in {"material", "other"} for item in any_candidates)
    assert any(item["asset"].ue_path == "/Game/CityPark/Meshes/Road/SM_ParkPath1_1" for item in static_candidates)
    assert all("LayerInfo" not in item["asset"].ue_path for item in static_candidates)
    assert [item["asset"].ue_path for item in skeletal_candidates] == ["/Game/AfricanAnimalsPack/Zebra/Meshes/SK_Zebra"]
    assert [item["asset"].ue_path for item in material_candidates] == ["/Game/CityPark/Materials/BaseMaterial/M_ParkPath"]
    assert any("LayerInfo" in item["asset"].ue_path for item in other_candidates)


def test_asset_store_retrieves_twinmotion_tree_mesh_without_auxiliary_assets(tmp_path: Path):
    asset_cache = tmp_path / "cineu_research_system" / "workspace" / "projects" / "demo_project" / "asset_cache"
    _write_jsonl(asset_cache / "assets.jsonl", [])
    content = tmp_path / "HillsideProject" / "Content"
    tree_root = content / "ExternalAssets" / "Twinmotion" / "Vegetation" / "Trees" / "XF_FicusBenjamina"
    common_root = content / "ExternalAssets" / "Twinmotion" / "_common" / "MasterMaterials" / "_common" / "MaterialFunctions"
    citypark_grass = content / "CityPark" / "Meshes" / "Flora" / "Grass" / "GrassFoliageType"
    sound_root = content / "CityPark" / "Sound"
    blueprint_root = content / "CityPark" / "Blueprints"
    tree_root.mkdir(parents=True)
    common_root.mkdir(parents=True)
    citypark_grass.mkdir(parents=True)
    sound_root.mkdir(parents=True)
    blueprint_root.mkdir(parents=True)
    (tree_root / "SM_A_FicusBenjamina_LOD0.uasset").write_bytes(b"mesh")
    (tree_root / "SM_A_FicusBenjamina_LOD0_FoliageType.uasset").write_bytes(b"foliage type")
    (tree_root / "MI_Leaves.uasset").write_bytes(b"material")
    (common_root / "MF_BaseColor.uasset").write_bytes(b"material function")
    (citypark_grass / "SM_grass03_FoliageType.uasset").write_bytes(b"foliage type")
    (sound_root / "S_231537__vkproduktion__forest-birds-loop-02.uasset").write_bytes(b"sound")
    (blueprint_root / "BP_SplineMeshes.uasset").write_bytes(b"blueprint")

    store = AssetStore(asset_cache / "assets.jsonl", source_dirs=[content])
    match = store.retrieve(
        "twinmotion vegetation leafy tree canopy",
        required_type="static_mesh",
        required_tags=["tree", "vegetation"],
    )
    static_candidates = store.search("foliage material function sound blueprint", required_type="static_mesh")

    assert match.ue_path == "/Game/ExternalAssets/Twinmotion/Vegetation/Trees/XF_FicusBenjamina/SM_A_FicusBenjamina_LOD0"
    assert match.import_required is True
    assert match.provenance["bundle_root"].endswith(str(Path("XF_FicusBenjamina")))
    assert {"tree", "vegetation", "leafy", "canopy"}.issubset(set(match.semantic_tags))
    assert all("FoliageType" not in item["asset"].ue_path for item in static_candidates)
    assert all("/MaterialFunctions/" not in item["asset"].ue_path for item in static_candidates)
    assert all("/Sound/" not in item["asset"].ue_path for item in static_candidates)
    assert all("/Blueprints/" not in item["asset"].ue_path for item in static_candidates)


def test_asset_store_does_not_return_camera_fbx_as_environment_mesh(tmp_path: Path):
    asset_cache = tmp_path / "workspace" / "projects" / "demo_project" / "asset_cache"
    resource_root = tmp_path / "RealTimeCompositing" / "UEOL_505_Resources"
    camera_source = resource_root / "HillPath" / "CG Assets" / "Cameras" / "CAM_A.fbx"
    mesh_source = resource_root / "HillPath" / "CG Assets" / "HillPath_Lo.fbx"
    camera_source.parent.mkdir(parents=True)
    mesh_source.write_text("fbx placeholder bytes", encoding="utf-8")
    camera_source.write_text("fbx placeholder bytes", encoding="utf-8")
    _write_jsonl(asset_cache / "assets.jsonl", [])

    store = AssetStore(asset_cache / "assets.jsonl", source_dirs=[resource_root])
    match = store.retrieve("park path environment", required_type="static_mesh", required_tags=["park", "environment"])

    assert match.source_path == str(mesh_source.resolve())


def test_pipeline_inserts_asset_import_before_spawn_for_file_backed_assets(tmp_path: Path):
    workspace = tmp_path / "workspace"
    create_demo_workspace(workspace, overwrite=True)
    source = workspace / "projects" / "demo_project" / "asset_cache" / "fab" / "modern_gallery_painting.fbx"
    source.parent.mkdir(parents=True)
    source.write_text("fbx placeholder bytes", encoding="utf-8")
    source.with_suffix(".cineu_asset.json").write_text(
        json.dumps(
            {
                "semantic_tags": ["painting", "gallery", "modern", "wall_art"],
                "functional_tags": ["decor", "wall_art"],
                "bounds_cm": {"extent": [5, 125, 82]},
                "license": {"source": "fab_local_export", "research_allowed": True},
            }
        ),
        encoding="utf-8",
    )

    run_dir = CineUOrchestrator(workspace=workspace, knowledge_dir=Path("knowledge")).run("现代画廊，三幅画和一个雕塑，镜头推进")
    plan = json.loads((run_dir / "planning" / "operations_plan.json").read_text(encoding="utf-8"))
    op_types = [op["type"] for op in plan["operations"]]
    asset_import_index = op_types.index("asset.import_many")
    spawn_index = op_types.index("entity.spawn_many")
    import_op = plan["operations"][asset_import_index]
    spawn_op = plan["operations"][spawn_index]

    assert asset_import_index < spawn_index
    assert any(asset["import_required"] for asset in import_op["inputs"]["assets"])
    assert any(actor["source_type"] == "fab_local" for actor in spawn_op["inputs"]["actors"])
    assert any(actor["asset_path"].startswith("/Game/CineU/Imported/fab_local/") for actor in spawn_op["inputs"]["actors"])

    retrieval = json.loads((run_dir / "planning" / "asset_retrieval.json").read_text(encoding="utf-8"))
    assert any(record["asset"]["source_type"] == "fab_local" for record in retrieval["records"])


def test_pipeline_records_asset_search_candidates_before_selection(tmp_path: Path):
    workspace = tmp_path / "workspace"
    create_demo_workspace(workspace, overwrite=True)
    source = workspace / "projects" / "demo_project" / "asset_cache" / "fab" / "modern_gallery_painting.fbx"
    source.parent.mkdir(parents=True)
    source.write_text("fbx placeholder bytes", encoding="utf-8")
    source.with_suffix(".cineu_asset.json").write_text(
        json.dumps(
            {
                "semantic_tags": ["painting", "gallery", "modern", "wall_art"],
                "functional_tags": ["decor", "wall_art"],
                "license": {"source": "fab_local_export", "research_allowed": True},
            }
        ),
        encoding="utf-8",
    )

    run_dir = CineUOrchestrator(workspace=workspace, knowledge_dir=Path("knowledge")).run("modern gallery with paintings")
    retrieval = json.loads((run_dir / "planning" / "asset_retrieval.json").read_text(encoding="utf-8"))
    record = next(item for item in retrieval["records"] if item["entity_id"] == "painting_01")

    assert record["selected_asset_id"] == record["asset"]["asset_id"]
    assert record["candidates"][0]["asset_id"] == record["selected_asset_id"]
    assert record["candidates"][0]["source_type"] == "fab_local"
    assert isinstance(record["candidates"][0]["score"], float)
    assert "breakdown" in record["candidates"][0]


def test_pipeline_retrieves_environment_and_animation_assets_before_scene_setup(tmp_path: Path):
    workspace = tmp_path / "workspace"
    create_demo_workspace(workspace, overwrite=True)
    fab = workspace / "projects" / "demo_project" / "asset_cache" / "fab"
    fab.mkdir(parents=True)
    desert_env = fab / "desert_canyon_environment.fbx"
    desert_env.write_text("fbx placeholder bytes", encoding="utf-8")
    desert_env.with_suffix(".cineu_asset.json").write_text(
        json.dumps(
            {
                "name": "Fab Desert Canyon Environment",
                "type": "level",
                "semantic_tags": ["desert", "canyon", "environment"],
                "functional_tags": ["environment", "set", "background"],
                "license": {"source": "fab_local_export", "research_allowed": True},
            }
        ),
        encoding="utf-8",
    )
    zebra_run = fab / "zebra_run_animation.fbx"
    zebra_run.write_text("fbx placeholder bytes", encoding="utf-8")
    zebra_run.with_suffix(".cineu_asset.json").write_text(
        json.dumps(
            {
                "name": "Fab Zebra Run Animation",
                "type": "animation",
                "semantic_tags": ["zebra", "run", "animation"],
                "functional_tags": ["locomotion", "run"],
                "license": {"source": "fab_local_export", "research_allowed": True},
            }
        ),
        encoding="utf-8",
    )

    run_dir = CineUOrchestrator(workspace=workspace, knowledge_dir=Path("knowledge")).run("斑马 Hitchcock zoom")
    plan = json.loads((run_dir / "planning" / "operations_plan.json").read_text(encoding="utf-8"))
    op_types = [op["type"] for op in plan["operations"]]
    import_op = plan["operations"][op_types.index("asset.import_many")]
    env_op = plan["operations"][op_types.index("env.setup")]
    anim_op = plan["operations"][op_types.index("animation.add_tracks")]
    imported_ids = {asset["asset_id"] for asset in import_op["inputs"]["assets"]}

    assert op_types.index("asset.import_many") < op_types.index("env.setup")
    assert "asset_fab_local_desert_canyon_environment" in imported_ids
    assert "asset_fab_local_zebra_run_animation" in imported_ids
    assert env_op["inputs"]["environment_asset"]["asset_id"] == "asset_fab_local_desert_canyon_environment"
    assert anim_op["inputs"]["clips"][0]["animation_asset_id"] == "asset_fab_local_zebra_run_animation"
    assert anim_op["inputs"]["clips"][0]["animation_path"].startswith("/Game/CineU/Imported/fab_local/")

    state = json.loads((run_dir / "snapshots" / "world_final.json").read_text(encoding="utf-8"))
    assert state["asset_imports"]["asset_fab_local_desert_canyon_environment"]["status"] == "imported"
    assert state["asset_imports"]["asset_fab_local_zebra_run_animation"]["status"] == "imported"
    assert state["sequences"][next(iter(state["sequences"]))]["animation_tracks"]["zebra_01"]["animation_asset_id"] == "asset_fab_local_zebra_run_animation"


def test_environment_retrieval_accepts_importable_environment_mesh(tmp_path: Path, monkeypatch):
    from cineu_demo import engine as engine_module

    real_asset_store = engine_module.AssetStore
    monkeypatch.setattr(
        engine_module,
        "AssetStore",
        lambda assets_path, include_global_libraries=True: real_asset_store(
            assets_path,
            source_dirs=[assets_path.parent / "sources", assets_path.parent / "fab", assets_path.parent / "public"],
            include_global_libraries=False,
        ),
    )
    workspace = tmp_path / "workspace"
    create_demo_workspace(workspace, overwrite=True)
    fab = workspace / "projects" / "demo_project" / "asset_cache" / "fab"
    fab.mkdir(parents=True)
    park_mesh = fab / "park_path_environment.fbx"
    park_mesh.write_text("fbx placeholder bytes", encoding="utf-8")
    park_mesh.with_suffix(".cineu_asset.json").write_text(
        json.dumps(
            {
                "name": "Fab Park Path Environment Mesh",
                "type": "static_mesh",
                "semantic_tags": ["park", "path", "environment"],
                "functional_tags": ["environment", "set", "background"],
                "license": {"source": "fab_local_export", "research_allowed": True},
            }
        ),
        encoding="utf-8",
    )

    run_dir = CineUOrchestrator(workspace=workspace, knowledge_dir=Path("knowledge")).run("In a park, a zebra is moving forward. Hitchcock zoom.")
    plan = json.loads((run_dir / "planning" / "operations_plan.json").read_text(encoding="utf-8"))
    import_op = next(op for op in plan["operations"] if op["type"] == "asset.import_many")
    env_op = next(op for op in plan["operations"] if op["type"] == "env.setup")

    assert any(asset["asset_id"] == "asset_fab_local_park_path_environment" for asset in import_op["inputs"]["assets"])
    assert env_op["inputs"]["environment_asset"]["type"] == "static_mesh"
    assert env_op["inputs"]["environment_asset"]["ue_path"] == "/Game/CineU/Imported/fab_local/park_path_environment"


def test_asset_import_operation_contract_verifies_sources_and_updates_mock_state(tmp_path: Path):
    source = tmp_path / "sculpture.obj"
    source.write_text("o sculpture\n", encoding="utf-8")
    template = TemplateStore(Path("knowledge/templates")).retrieve(operation_type="asset.import_many", agent="AssetAgent")
    op = Operation(
        op_id="asset_import",
        node_id="asset.import",
        agent="AssetAgent",
        type="asset.import_many",
        template_id=template.template_id,
        inputs={
            "assets": [
                {
                    "asset_id": "asset_local_sculpture",
                    "name": "Local Sculpture",
                    "source_path": str(source),
                    "source_type": "local_file",
                    "import_required": True,
                    "import_destination": "/Game/CineU/Imported/local_file",
                    "ue_path": "/Game/CineU/Imported/local_file/sculpture",
                    "type": "static_mesh",
                }
            ]
        },
        expected={"assets_imported": ["asset_local_sculpture"]},
    )

    preflight = PreconditionVerifier().verify(template, op, initial_world_state())
    assert preflight.passed is True

    runner = MockRunner()
    run_dir = tmp_path / "run"
    runner.save_state(run_dir, initial_world_state())
    result = runner.execute(op, "unused", run_dir)
    state = runner.load_state(run_dir)

    assert result.ok is True
    assert state["asset_imports"]["asset_local_sculpture"]["status"] == "imported"
    assert state["asset_imports"]["asset_local_sculpture"]["ue_path"] == "/Game/CineU/Imported/local_file/sculpture"


def test_operation_plan_enforces_asset_import_before_spawn():
    ops = [
        Operation(op_id="1", node_id="env", agent="EnvAgent", type="env.setup", template_id="env.setup.v1"),
        Operation(op_id="2", node_id="spawn", agent="EntityAgent", type="entity.spawn_many", template_id="entity.spawn_many.v1"),
        Operation(op_id="3", node_id="asset", agent="AssetAgent", type="asset.import_many", template_id="asset.import_many.v1"),
    ]

    report = OperationPlanVerifier().verify(ops)

    assert report.passed is False
    assert any(check.name == "order:asset.import_many<=entity.spawn_many" for check in report.checks)


def test_operation_plan_rejects_environment_setup_without_reusable_asset():
    ops = [
        Operation(op_id="1", node_id="env", agent="EnvAgent", type="env.setup", template_id="env.setup.v1"),
        Operation(
            op_id="2",
            node_id="spawn",
            agent="EntityAgent",
            type="entity.spawn_many",
            template_id="entity.spawn_many.v1",
            inputs={"actors": [{"actor_name": "car_01", "asset_id": "asset_fab_car", "asset_path": "/Game/CineU/Imported/fab/car"}]},
        ),
    ]

    report = OperationPlanVerifier().verify(ops)

    assert report.passed is False
    assert any(check.name == "env_setup:environment_asset_required" for check in report.checks)


def test_pipeline_fails_at_asset_first_preflight_when_primary_environment_asset_is_missing(tmp_path: Path, monkeypatch):
    from cineu_demo import engine as engine_module

    real_asset_store = engine_module.AssetStore
    monkeypatch.setattr(
        engine_module,
        "AssetStore",
        lambda assets_path, include_global_libraries=True: real_asset_store(
            assets_path, source_dirs=[], include_global_libraries=False
        ),
    )
    workspace = tmp_path / "workspace"
    asset_cache = workspace / "projects" / "demo_project" / "asset_cache"
    _write_jsonl(asset_cache / "assets.jsonl", [])

    run_dir = CineUOrchestrator(workspace=workspace, knowledge_dir=Path("knowledge")).run(
        "In a park, a zebra is moving forward. Hitchcock zoom."
    )

    report = json.loads((run_dir / "verification" / "final_report.json").read_text(encoding="utf-8"))
    events = (run_dir / "traces" / "events.jsonl").read_text(encoding="utf-8")
    preflight = json.loads((run_dir / "planning" / "asset_first_preflight.json").read_text(encoding="utf-8"))
    assert report["success"] is False
    assert "asset_first_preflight_failed" in events
    assert "asset_resolution_failed" not in events
    assert preflight["passed"] is False
    assert preflight["checks"][1]["name"] == "target_environment_candidate_available"
    assert preflight["checks"][1]["passed"] is False
    assert not (run_dir / "planning" / "environment_asset_retrieval.json").exists()


def test_pipeline_fails_when_primary_entity_asset_is_missing_instead_of_fallback(tmp_path: Path, monkeypatch):
    from cineu_demo import engine as engine_module

    real_asset_store = engine_module.AssetStore
    monkeypatch.setattr(
        engine_module,
        "AssetStore",
        lambda assets_path, include_global_libraries=True: real_asset_store(
            assets_path, source_dirs=[], include_global_libraries=False
        ),
    )
    workspace = tmp_path / "workspace"
    asset_cache = workspace / "projects" / "demo_project" / "asset_cache"
    source = asset_cache / "sources" / "large_building_environment.obj"
    human_source = asset_cache / "sources" / "reference_human.fbx"
    source.parent.mkdir(parents=True)
    source.write_text("o large_building_environment\n", encoding="utf-8")
    human_source.write_text("reference human mesh\n", encoding="utf-8")
    _write_jsonl(
        asset_cache / "assets.jsonl",
        [
            {
                "schema_version": "cineu.asset.v1",
                "asset_id": "asset_local_large_building_environment",
                "name": "Local Large Building Environment",
                "ue_path": "/Game/CineU/Imported/local_file/large_building_environment",
                "type": "static_mesh",
                "semantic_tags": ["large_building", "building", "environment"],
                "functional_tags": ["environment"],
                "bounds_cm": {"extent": [1000, 900, 600]},
                "license": {"source": "local_source", "research_allowed": True},
                "source_path": str(source.resolve()),
                "source_type": "local_file",
                "import_required": True,
                "import_destination": "/Game/CineU/Imported/local_file",
            },
            {
                "schema_version": "cineu.asset.v1",
                "asset_id": "asset_local_reference_human",
                "name": "Reference Human Character",
                "ue_path": "/Game/CineU/Imported/local_file/reference_human",
                "type": "skeletal_mesh",
                "semantic_tags": ["human", "character"],
                "functional_tags": ["animated"],
                "bounds_cm": {"extent": [45, 45, 180]},
                "license": {"source": "local_source", "research_allowed": True},
                "source_path": str(human_source.resolve()),
                "source_type": "local_file",
                "import_required": True,
                "import_destination": "/Game/CineU/Imported/local_file",
            }
        ],
    )

    run_dir = CineUOrchestrator(workspace=workspace, knowledge_dir=Path("knowledge")).run(
        "Large building. External wide shot to push-in, revealing a car parked inside."
    )

    report = json.loads((run_dir / "verification" / "final_report.json").read_text(encoding="utf-8"))
    entity_retrieval = json.loads((run_dir / "planning" / "asset_retrieval.json").read_text(encoding="utf-8"))
    assert report["success"] is False
    assert entity_retrieval["records"][0]["status"].startswith("miss:")
    assert entity_retrieval["records"][0]["selected_asset_id"] is None
