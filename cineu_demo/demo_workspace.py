from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .ledger import atomic_write_json, ensure_dir


DEMO_ASSETS: list[dict[str, Any]] = [
    {
        "schema_version": "cineu.asset.v1",
        "asset_id": "asset_gallery_painting_001",
        "name": "Framed Modern Painting",
        "ue_path": "/Game/CineU/Assets/Gallery/SM_FramedPainting",
        "type": "static_mesh",
        "semantic_tags": ["painting", "art", "framed", "modern", "wall_art"],
        "functional_tags": ["wall_art", "decor", "gallery"],
        "bounds_cm": {"extent": [6, 130, 85]},
        "has_collision": True,
        "materials": ["/Game/CineU/Materials/M_Painting_A"],
        "ue_versions": ["5.5", "5.6"],
        "license": {"source": "local_placeholder", "research_allowed": True, "commercial_allowed": False},
    },
    {
        "schema_version": "cineu.asset.v1",
        "asset_id": "asset_gallery_sculpture_001",
        "name": "White Modern Sculpture",
        "ue_path": "/Game/CineU/Assets/Gallery/SM_WhiteSculpture",
        "type": "static_mesh",
        "semantic_tags": ["sculpture", "white", "modern", "gallery"],
        "functional_tags": ["floor_object", "centerpiece", "gallery"],
        "bounds_cm": {"extent": [42, 42, 88]},
        "has_collision": True,
        "materials": ["/Game/CineU/Materials/M_WhiteMarble"],
        "ue_versions": ["5.5", "5.6"],
        "license": {"source": "local_placeholder", "research_allowed": True, "commercial_allowed": False},
    },
    {
        "schema_version": "cineu.asset.v1",
        "asset_id": "asset_zebra_001",
        "name": "Research Zebra Skeletal Mesh",
        "ue_path": "/Game/CineU/Assets/Animals/Zebra/SK_Zebra",
        "type": "skeletal_mesh",
        "semantic_tags": ["zebra", "animal", "quadruped", "desert", "savanna"],
        "functional_tags": ["run", "walk", "locomotion", "animated"],
        "bounds_cm": {"extent": [115, 35, 85]},
        "has_collision": True,
        "materials": ["/Game/CineU/Materials/M_ZebraStripe"],
        "animations": [
            {"name": "run", "path": "/Game/CineU/Assets/Animals/Zebra/A_Zebra_Run", "root_motion": False, "estimated_speed_cm_s": 450}
        ],
        "ue_versions": ["5.5", "5.6"],
        "license": {"source": "local_placeholder", "research_allowed": True, "commercial_allowed": False},
    },
    {
        "schema_version": "cineu.asset.v1",
        "asset_id": "asset_fallback_cube_001",
        "name": "Fallback Research Cube",
        "ue_path": "/Game/CineU/Assets/Primitives/SM_FallbackCube",
        "type": "static_mesh",
        "semantic_tags": ["fallback", "cube", "primitive"],
        "functional_tags": ["fallback", "primitive"],
        "bounds_cm": {"extent": [50, 50, 50]},
        "has_collision": True,
        "materials": ["/Game/CineU/Materials/M_DebugGray"],
        "ue_versions": ["5.5", "5.6"],
        "license": {"source": "local_placeholder", "research_allowed": True, "commercial_allowed": False},
    },
]


STARTER_SOURCE_ASSETS: list[dict[str, Any]] = [
    {
        "filename": "starter_gallery_environment.obj",
        "text": "o starter_gallery_environment\n",
        "metadata": {
            "name": "Starter Gallery Environment",
            "type": "static_mesh",
            "semantic_tags": ["gallery", "environment", "architecture"],
            "functional_tags": ["environment", "support_floor", "background"],
            "bounds_cm": {"extent": [620, 620, 260]},
            "license": {"source": "local_starter_source", "research_allowed": True, "commercial_allowed": False},
        },
    },
    {
        "filename": "starter_desert_set.obj",
        "text": "o starter_desert_set\n",
        "metadata": {
            "name": "Starter Desert Set",
            "type": "static_mesh",
            "semantic_tags": ["desert", "environment", "sand"],
            "functional_tags": ["environment", "support_floor", "background"],
            "bounds_cm": {"extent": [1200, 1200, 120]},
            "license": {"source": "local_starter_source", "research_allowed": True, "commercial_allowed": False},
        },
    },
    {
        "filename": "starter_park_greenway.obj",
        "text": "o starter_park_greenway\n",
        "metadata": {
            "name": "Starter Greenway",
            "type": "static_mesh",
            "semantic_tags": ["park", "environment", "path"],
            "functional_tags": ["environment", "support_floor", "background"],
            "bounds_cm": {"extent": [900, 1600, 180]},
            "license": {"source": "local_starter_source", "research_allowed": True, "commercial_allowed": False},
        },
    },
    {
        "filename": "starter_large_building.obj",
        "text": "o starter_large_building\n",
        "metadata": {
            "name": "Starter Large Building",
            "type": "static_mesh",
            "semantic_tags": ["large_building", "building", "environment"],
            "functional_tags": ["environment", "architecture", "background"],
            "bounds_cm": {"extent": [1200, 900, 620]},
            "license": {"source": "local_starter_source", "research_allowed": True, "commercial_allowed": False},
        },
    },
    {
        "filename": "starter_city_rooftop.obj",
        "text": "o starter_city_rooftop\n",
        "metadata": {
            "name": "Starter City Rooftop",
            "type": "static_mesh",
            "semantic_tags": ["city_rooftop", "city", "rooftop", "environment"],
            "functional_tags": ["environment", "support_floor", "background"],
            "bounds_cm": {"extent": [900, 900, 260]},
            "license": {"source": "local_starter_source", "research_allowed": True, "commercial_allowed": False},
        },
    },
    {
        "filename": "starter_river_environment.obj",
        "text": "o starter_river_environment\n",
        "metadata": {
            "name": "Starter River Environment",
            "type": "static_mesh",
            "semantic_tags": ["river", "water", "environment"],
            "functional_tags": ["environment", "support_floor", "background"],
            "bounds_cm": {"extent": [1000, 1000, 160]},
            "license": {"source": "local_starter_source", "research_allowed": True, "commercial_allowed": False},
        },
    },
    {
        "filename": "starter_framed_modern_painting.obj",
        "text": "o starter_framed_modern_painting\n",
        "metadata": {
            "name": "Starter Framed Modern Painting",
            "type": "static_mesh",
            "semantic_tags": ["painting", "gallery", "modern", "wall_art"],
            "functional_tags": ["decor", "wall_art"],
            "bounds_cm": {"extent": [5, 125, 82]},
            "license": {"source": "local_starter_source", "research_allowed": True, "commercial_allowed": False},
        },
    },
    {
        "filename": "starter_white_modern_sculpture.obj",
        "text": "o starter_white_modern_sculpture\n",
        "metadata": {
            "name": "Starter White Modern Sculpture",
            "type": "static_mesh",
            "semantic_tags": ["sculpture", "gallery", "modern", "white"],
            "functional_tags": ["floor_object", "centerpiece"],
            "bounds_cm": {"extent": [42, 42, 88]},
            "license": {"source": "local_starter_source", "research_allowed": True, "commercial_allowed": False},
        },
    },
    {
        "filename": "starter_parked_car.obj",
        "text": "o starter_parked_car\n",
        "metadata": {
            "name": "Starter Parked Car",
            "type": "static_mesh",
            "semantic_tags": ["car", "vehicle"],
            "functional_tags": ["floor_object"],
            "bounds_cm": {"extent": [210, 92, 72]},
            "license": {"source": "local_starter_source", "research_allowed": True, "commercial_allowed": False},
        },
    },
    {
        "filename": "starter_classical_statue.obj",
        "text": "o starter_classical_statue\n",
        "metadata": {
            "name": "Starter Classical Statue",
            "type": "static_mesh",
            "semantic_tags": ["statue", "sculpture", "classical"],
            "functional_tags": ["floor_object"],
            "bounds_cm": {"extent": [45, 45, 160]},
            "license": {"source": "local_starter_source", "research_allowed": True, "commercial_allowed": False},
        },
    },
    {
        "filename": "starter_zebra.fbx",
        "text": "FBXHeaderExtension: starter_zebra\n",
        "metadata": {
            "name": "Starter Zebra",
            "type": "skeletal_mesh",
            "semantic_tags": ["zebra", "animal", "quadruped", "textured"],
            "functional_tags": ["animated", "run", "walk"],
            "bounds_cm": {"extent": [115, 35, 85]},
            "animations": [{"name": "run", "path": "/Game/CineU/Imported/local_file/starter_zebra_run", "root_motion": False, "estimated_speed_cm_s": 450}],
            "license": {"source": "local_starter_source", "research_allowed": True, "commercial_allowed": False},
        },
    },
    {
        "filename": "starter_zebra_run.fbx",
        "text": "FBXHeaderExtension: starter_zebra_run\n",
        "metadata": {
            "name": "Starter Zebra Run",
            "type": "animation",
            "semantic_tags": ["zebra", "run", "animation"],
            "functional_tags": ["locomotion", "run"],
            "license": {"source": "local_starter_source", "research_allowed": True, "commercial_allowed": False},
        },
    },
    {
        "filename": "starter_human_phone_actor.fbx",
        "text": "FBXHeaderExtension: starter_human_phone_actor\n",
        "metadata": {
            "name": "Starter Human Phone Actor",
            "type": "skeletal_mesh",
            "semantic_tags": ["human", "phone", "character"],
            "functional_tags": ["animated", "phone_call"],
            "bounds_cm": {"extent": [45, 35, 175]},
            "animations": [{"name": "phone_call", "path": "/Game/CineU/Imported/local_file/starter_human_phone_call", "root_motion": False, "estimated_speed_cm_s": 0}],
            "license": {"source": "local_starter_source", "research_allowed": True, "commercial_allowed": False},
        },
    },
    {
        "filename": "starter_human_phone_call.fbx",
        "text": "FBXHeaderExtension: starter_human_phone_call\n",
        "metadata": {
            "name": "Starter Human Phone Call",
            "type": "animation",
            "semantic_tags": ["human", "phone_call", "animation"],
            "functional_tags": ["phone_call"],
            "license": {"source": "local_starter_source", "research_allowed": True, "commercial_allowed": False},
        },
    },
]



def expanded_demo_assets() -> list[dict[str, Any]]:
    """Return deterministic metadata-only assets for research demos.

    The first four entries are the canonical runtime assets. Remaining entries
    provide a richer local-cache surface for retrieval, audit and ablation.
    Replace ue_path values with real Unreal assets when connecting to UE.
    """
    assets = list(DEMO_ASSETS)
    static_specs = [
        ("gallery_wall", "Gallery Wall Segment", ["gallery", "wall", "architecture"], ["support_wall", "background"], [500, 18, 180]),
        ("gallery_floor", "Polished Gallery Floor", ["gallery", "floor", "architecture"], ["support_floor", "ground"], [600, 600, 8]),
        ("desert_ground", "Desert Sand Ground Plane", ["desert", "sand", "ground"], ["support_floor", "ground"], [1200, 1200, 5]),
        ("desert_rock", "Desert Rock Cluster", ["desert", "rock", "environment"], ["obstacle", "set_dressing"], [80, 60, 45]),
        ("city_rooftop", "City Rooftop Platform", ["city", "rooftop", "platform"], ["support_floor", "urban"], [800, 800, 20]),
        ("studio_cyc", "Studio Cyclorama", ["studio", "backdrop", "white"], ["background", "support_floor"], [650, 650, 260]),
        ("bench", "Minimal Gallery Bench", ["bench", "seat", "gallery"], ["floor_object", "furniture"], [120, 35, 32]),
        ("pedestal", "White Sculpture Pedestal", ["pedestal", "gallery", "white"], ["support_object", "floor_object"], [45, 45, 55]),
        ("spotlight", "Gallery Spotlight", ["light", "spotlight", "gallery"], ["lighting", "ceiling"], [18, 18, 35]),
        ("plant", "Interior Decorative Plant", ["plant", "decor", "interior"], ["floor_object", "decor"], [35, 35, 95]),
        ("vase", "Ceramic Display Vase", ["vase", "ceramic", "gallery"], ["floor_object", "decor"], [28, 28, 60]),
        ("rope", "Museum Barrier Rope", ["barrier", "rope", "gallery"], ["floor_object", "safety"], [90, 8, 45]),
    ]
    for i, (key, name, sem, func, extent) in enumerate(static_specs, start=1):
        assets.append({
            "schema_version": "cineu.asset.v1",
            "asset_id": f"asset_static_{i:03d}_{key}",
            "name": name,
            "ue_path": f"/Game/CineU/Assets/Curated/{key}/SM_{key.title().replace('_', '')}",
            "type": "static_mesh",
            "semantic_tags": sem,
            "functional_tags": func,
            "bounds_cm": {"extent": extent},
            "has_collision": True,
            "materials": ["/Game/CineU/Materials/M_Research_Default"],
            "ue_versions": ["5.5", "5.6"],
            "license": {"source": "metadata_placeholder", "research_allowed": True, "commercial_allowed": False},
        })
    for i in range(1, 21):
        assets.append({
            "schema_version": "cineu.asset.v1",
            "asset_id": f"asset_painting_variant_{i:03d}",
            "name": f"Framed Painting Variant {i:03d}",
            "ue_path": f"/Game/CineU/Assets/Gallery/Paintings/SM_PaintingVariant_{i:03d}",
            "type": "static_mesh",
            "semantic_tags": ["painting", "art", "gallery", "variant"],
            "functional_tags": ["wall_art", "decor"],
            "bounds_cm": {"extent": [6, 55 + (i % 4) * 8, 36 + (i % 3) * 9]},
            "has_collision": True,
            "materials": [f"/Game/CineU/Materials/Paintings/M_Painting_{i:03d}"],
            "ue_versions": ["5.5", "5.6"],
            "license": {"source": "metadata_placeholder", "research_allowed": True, "commercial_allowed": False},
        })
    for i in range(1, 21):
        assets.append({
            "schema_version": "cineu.asset.v1",
            "asset_id": f"asset_sculpture_variant_{i:03d}",
            "name": f"Modern Sculpture Variant {i:03d}",
            "ue_path": f"/Game/CineU/Assets/Gallery/Sculptures/SM_SculptureVariant_{i:03d}",
            "type": "static_mesh",
            "semantic_tags": ["sculpture", "gallery", "modern", "variant"],
            "functional_tags": ["floor_object", "centerpiece"],
            "bounds_cm": {"extent": [42 + (i % 5) * 4, 42 + (i % 5) * 4, 80 + (i % 6) * 10]},
            "has_collision": True,
            "materials": ["/Game/CineU/Materials/M_Research_Default"],
            "ue_versions": ["5.5", "5.6"],
            "license": {"source": "metadata_placeholder", "research_allowed": True, "commercial_allowed": False},
        })
    for i, animal in enumerate(["wolf", "horse", "deer", "human"], start=1):
        assets.append({
            "schema_version": "cineu.asset.v1",
            "asset_id": f"asset_animal_{i:03d}_{animal}",
            "name": f"Research {animal.title()} Skeletal Mesh",
            "ue_path": f"/Game/CineU/Assets/Animals/{animal}/SK_{animal.title()}",
            "type": "skeletal_mesh",
            "semantic_tags": [animal, "animal", "character"],
            "functional_tags": ["walk", "run", "animated"],
            "bounds_cm": {"extent": [100, 35, 90]},
            "has_collision": True,
            "materials": ["/Game/CineU/Materials/M_Research_Default"],
            "animations": [
                {"name": "walk", "path": f"/Game/CineU/Assets/Animals/{animal}/A_{animal.title()}_Walk", "root_motion": False, "estimated_speed_cm_s": 160},
                {"name": "run", "path": f"/Game/CineU/Assets/Animals/{animal}/A_{animal.title()}_Run", "root_motion": False, "estimated_speed_cm_s": 420},
            ],
            "ue_versions": ["5.5", "5.6"],
            "license": {"source": "metadata_placeholder", "research_allowed": True, "commercial_allowed": False},
        })
    return assets


def create_demo_workspace(workspace: Path, project_id: str = "demo_project", overwrite: bool = False) -> Path:
    workspace = Path(workspace)
    project = workspace / "projects" / project_id
    asset_dir = project / "asset_cache"
    ensure_dir(asset_dir)
    ensure_dir(workspace / "runs")
    project_json = project / "project.json"
    if overwrite or not project_json.exists():
        atomic_write_json(
            project_json,
            {
                "schema_version": "cineu.project.v1",
                "project_id": project_id,
                "name": "CineU Research Demo Project",
                "ue_version": "5.5",
                "asset_cache": "asset_cache/assets.jsonl",
            },
        )
    assets_jsonl = asset_dir / "assets.jsonl"
    if overwrite or not assets_jsonl.exists():
        with assets_jsonl.open("w", encoding="utf-8") as f:
            for asset in expanded_demo_assets():
                f.write(json.dumps(asset, ensure_ascii=False) + "\n")
    _write_starter_source_assets(asset_dir, overwrite=overwrite)
    return project


def _write_starter_source_assets(asset_dir: Path, *, overwrite: bool = False) -> None:
    source_dir = asset_dir / "sources" / "starter"
    ensure_dir(source_dir)
    for item in STARTER_SOURCE_ASSETS:
        source = source_dir / item["filename"]
        sidecar = source.with_suffix(".cineu_asset.json")
        if overwrite or not source.exists():
            source.write_text(str(item["text"]), encoding="utf-8")
        if overwrite or not sidecar.exists():
            sidecar.write_text(json.dumps(item["metadata"], ensure_ascii=False, indent=2), encoding="utf-8")
