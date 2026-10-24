from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .paths import HILLSIDE_PROJECT_ROOT

SCENE19_WHITE_AFRAME_MATERIAL = "/Game/Hillside/MaterialLibrary/MaterialsInstances/Exterior/MI_Brushed_Aluminum_White"
HILLSIDE_PROJECT_CONTENT_ROOT = (HILLSIDE_PROJECT_ROOT / "Content").resolve()
FREE_CASUAL_GIRL_MESH_PATH = "/Game/Sample/Meshes/SK_Complete"
FREE_CASUAL_GIRL_BODY_MESH_PATH = "/Game/Sample/Meshes/SK_Body"
FREE_CASUAL_GIRL_WALK_ANIMATION_PATH = "/Game/Sample/Demo/ThirdPersonTemplate/Characters/Mannequins/Animations/Quinn/MF_Walk_Fwd"
FREE_CASUAL_GIRL_SKELETON_HINT = "/Game/Sample/Demo/ThirdPersonTemplate/Characters/Mannequins/Meshes/SK_Mannequin"
SCENE19_HIGH_DETAIL_CHARACTER_INDEX = 10
FREE_CASUAL_GIRL_MODULAR_PARTS = [
    ("top", "/Game/Sample/Meshes/SK_Top_1"),
    ("pants", "/Game/Sample/Meshes/SK_Pants"),
    ("shoes", "/Game/Sample/Meshes/SK_Shoes"),
    ("hair", "/Game/Sample/Meshes/SK_Hair_1"),
]
FREE_CASUAL_GIRL_SCENE19_VARIANTS = [
    {
        "index": 0,
        "parts": [
            ("top", "/Game/Sample/Meshes/SK_Top_4"),
            ("pants", "/Game/Sample/Meshes/SK_Shorts"),
            ("shoes", "/Game/Sample/Meshes/SK_Shoes_Socks"),
            ("hair", "/Game/Sample/Meshes/SK_Hair_2"),
        ],
    },
    {
        "index": 1,
        "parts": [
            ("top", "/Game/Sample/Meshes/SK_Top_2"),
            ("pants", "/Game/Sample/Meshes/SK_Shorts"),
            ("shoes", "/Game/Sample/Meshes/SK_Shoes_Socks"),
            ("hair", "/Game/Sample/Meshes/SK_Hair_2"),
        ],
    },
    {
        "index": 4,
        "parts": [
            ("top", "/Game/Sample/Meshes/SK_Top_3"),
            ("pants", "/Game/Sample/Meshes/SK_Pants"),
            ("shoes", "/Game/Sample/Meshes/SK_Shoes"),
            ("hair", "/Game/Sample/Meshes/SK_Hair_1"),
        ],
    },
    {
        "index": 10,
        "parts": [
            ("top", "/Game/Sample/Meshes/SK_Top_1"),
            ("pants", "/Game/Sample/Meshes/SK_Pants"),
            ("shoes", "/Game/Sample/Meshes/SK_Shoes"),
            ("hair", "/Game/Sample/Meshes/SK_Hair_1"),
        ],
    },
]
FREE_CASUAL_GIRL_SCENE24_VARIANTS = [
    {
        "index": 0,
        "parts": [
            ("top", "/Game/Sample/Meshes/SK_Top_1"),
            ("pants", "/Game/Sample/Meshes/SK_Pants"),
            ("shoes", "/Game/Sample/Meshes/SK_Shoes"),
            ("hair", "/Game/Sample/Meshes/SK_Hair_1"),
        ],
    },
    {
        "index": 1,
        "parts": [
            ("top", "/Game/Sample/Meshes/SK_Top_2"),
            ("pants", "/Game/Sample/Meshes/SK_Shorts"),
            ("shoes", "/Game/Sample/Meshes/SK_Shoes_Socks"),
            ("hair", "/Game/Sample/Meshes/SK_Hair_2"),
        ],
    },
    {
        "index": 4,
        "parts": [
            ("top", "/Game/Sample/Meshes/SK_Top_4"),
            ("pants", "/Game/Sample/Meshes/SK_Shorts"),
            ("shoes", "/Game/Sample/Meshes/SK_Shoes_Socks"),
            ("hair", "/Game/Sample/Meshes/SK_Hair_2"),
        ],
    },
    {
        "index": 5,
        "parts": [
            ("top", "/Game/Sample/Meshes/SK_Top_3"),
            ("pants", "/Game/Sample/Meshes/SK_Pants"),
            ("shoes", "/Game/Sample/Meshes/SK_Shoes"),
            ("hair", "/Game/Sample/Meshes/SK_Hair_1"),
        ],
    },
]

SCENE19_NATIVE_WHITEBRACE_REFERENCE: dict[str, Any] = {
    "source_level_path": "/Game/Hillside/Maps/SA/LV_Hotel_Update",
    "level_instance_label": "Hotel_Update",
    "source_actor_label": "ISM_AFrame",
    "reuse_policy": "reuse_loaded_level_instance_geometry",
    "diagnostic_evidence_path": (
        "workspace/diagnostics/hillside_scene19_scene24/renders/"
        "scene19_hotel_update_bounds_20260618_223854/hotel_update_bounds_summary.json"
    ),
    "instances": [
        {
            "mesh_path": "/Game/Hillside/Datasmith/SA/Hotel_Update/Geometries/SM_Frame_D_C_01",
            "source_instance_index": 0,
            "source_instance_local_location": [6989.501, 5769.61, 3535.676],
            "source_instance_local_rotation": [0.0, 0.0, 0.0],
        },
        {
            "mesh_path": "/Game/Hillside/Datasmith/SA/Hotel_Update/Geometries/SM_Frame_D_C_01",
            "source_instance_index": 1,
            "source_instance_local_location": [6989.501, 4550.411, 4754.875],
            "source_instance_local_rotation": [0.0, 0.0, 0.0],
        },
        {
            "mesh_path": "/Game/Hillside/Datasmith/SA/Hotel_Update/Geometries/SM_Frame_D_C_01",
            "source_instance_index": 2,
            "source_instance_local_location": [6989.501, 6988.811, 2316.476],
            "source_instance_local_rotation": [0.0, 0.0, 0.0],
        },
        {
            "mesh_path": "/Game/Hillside/Datasmith/SA/Hotel_Update/Geometries/SM_Frame_D_C_01",
            "source_instance_index": 3,
            "source_instance_local_location": [6989.501, 3331.211, 5974.076],
            "source_instance_local_rotation": [0.0, 0.0, 0.0],
        },
        {
            "mesh_path": "/Game/Hillside/Datasmith/SA/Hotel_Update/Geometries/SM_Frame_E_01_L_05",
            "source_instance_index": 0,
            "source_instance_local_location": [6989.502, 5626.741, 4419.595],
            "source_instance_local_rotation": [0.0, 0.0, 0.0],
        },
        {
            "mesh_path": "/Game/Hillside/Datasmith/SA/Hotel_Update/Geometries/SM_Frame_E_01_L_05",
            "source_instance_index": 1,
            "source_instance_local_location": [6989.502, 6845.94, 3200.399],
            "source_instance_local_rotation": [0.0, 0.0, 0.0],
        },
        {
            "mesh_path": "/Game/Hillside/Datasmith/SA/Hotel_Update/Geometries/SM_Frame_E_01_L_05",
            "source_instance_index": 2,
            "source_instance_local_location": [6989.502, 8065.134, 1981.193],
            "source_instance_local_rotation": [0.0, 0.0, 0.0],
        },
        {
            "mesh_path": "/Game/Hillside/Datasmith/SA/Hotel_Update/Geometries/SM_Frame_E_01_L_05",
            "source_instance_index": 3,
            "source_instance_local_location": [6989.5, 3188.338, 6857.998],
            "source_instance_local_rotation": [0.0, 0.0, 0.0],
        },
        {
            "mesh_path": "/Game/Hillside/Datasmith/SA/Hotel_Update/Geometries/SM_Frame_F_01_C_01",
            "source_instance_index": 0,
            "source_instance_local_location": [6989.501, 5406.466, 4449.919],
            "source_instance_local_rotation": [0.0, 0.0, 0.0],
        },
        {
            "mesh_path": "/Game/Hillside/Datasmith/SA/Hotel_Update/Geometries/SM_Frame_F_01_C_01",
            "source_instance_index": 1,
            "source_instance_local_location": [6989.501, 6625.665, 3230.719],
            "source_instance_local_rotation": [0.0, 0.0, 0.0],
        },
        {
            "mesh_path": "/Game/Hillside/Datasmith/SA/Hotel_Update/Geometries/SM_Frame_F_01_C_01",
            "source_instance_index": 2,
            "source_instance_local_location": [6989.501, 2968.066, 6888.319],
            "source_instance_local_rotation": [0.0, 0.0, 0.0],
        },
        {
            "mesh_path": "/Game/Hillside/Datasmith/SA/Hotel_Update/Geometries/SM_Frame_F_01_C_01",
            "source_instance_index": 3,
            "source_instance_local_location": [6989.501, 4187.266, 5669.119],
            "source_instance_local_rotation": [0.0, 0.0, 0.0],
        },
        {
            "mesh_path": "/Game/Hillside/Datasmith/SA/Hotel_Update/Geometries/SM_Railing_G_06",
            "source_instance_index": 0,
            "source_instance_local_location": [6839.646, 4368.956, 5974.076],
            "source_instance_local_rotation": [0.0, 0.0, 0.0],
        },
        {
            "mesh_path": "/Game/Hillside/Datasmith/SA/Hotel_Update/Geometries/SM_Railing_G_06",
            "source_instance_index": 1,
            "source_instance_local_location": [6839.646, 5588.156, 4754.876],
            "source_instance_local_rotation": [0.0, 0.0, 0.0],
        },
        {
            "mesh_path": "/Game/Hillside/Datasmith/SA/Hotel_Update/Geometries/SM_Railing_G_06",
            "source_instance_index": 2,
            "source_instance_local_location": [6839.646, 6807.356, 3535.676],
            "source_instance_local_rotation": [0.0, 0.0, 0.0],
        },
        {
            "mesh_path": "/Game/Hillside/Datasmith/SA/Hotel_Update/Geometries/SM_Railing_G_06",
            "source_instance_index": 3,
            "source_instance_local_location": [6839.646, 8026.557, 2316.476],
            "source_instance_local_rotation": [0.0, 0.0, 0.0],
        },
    ],
}

SCENE19_NATIVE_STH_BUILDING_REFERENCE: dict[str, Any] = {
    "building_id": "scene19_sth_bldggrp_01_b",
    "source_level_path": "/Game/Hillside/Maps/QC/LV_StH_BldgGrp_01_B",
    "source_level_label": "LV_StH_BldgGrp_01_B",
    "geometry_root": "/Game/Hillside/Datasmith/QC/StH_BldgGrp_01_B/Geometries",
    "reuse_policy": "prefer_existing_level_or_datasmith_geometry_before_manual_proxy",
    "visual_match_notes": [
        "white structural linework",
        "dark glass mullions",
        "stacked facade and balcony shell pieces",
    ],
    "key_geometry_assets": [
        "/Game/Hillside/Datasmith/QC/StH_BldgGrp_01_B/Geometries/Shell_Facade",
        "/Game/Hillside/Datasmith/QC/StH_BldgGrp_01_B/Geometries/Mullions_and_glass_Nanite",
        "/Game/Hillside/Datasmith/QC/StH_BldgGrp_01_B/Geometries/Line297",
    ],
}

HIGH_QUALITY_CHARACTER_PACKS: list[dict[str, Any]] = [
    {
        "name": "Renderpeople - Scanned 3D People Pack",
        "fab_listing_id": "2e872a96-686e-4955-8256-82fa19904f92",
        "priority": 1,
        "quality": "photoreal_scanned_people",
        "preferred_use": "close and mid-distance pedestrians when imported into the project",
        "detection_needles": ["Renderpeople", "Scanned 3D People", "Scanned3DPeople", "2e872a96-686e-4955-8256-82fa19904f92"],
    },
]

HIGH_QUALITY_PROJECT_CHARACTER_CANDIDATES: list[dict[str, Any]] = [
    {
        "name": "MetaHuman_Kellan__HillsideProject",
        "priority": 1,
        "quality": "epic_metahuman_cinematic_skeletal_character",
        "preferred_use": "near-field cinematic pedestrian when linked into the target project; static until compatible locomotion is available",
        "source_project": "HillsideProject",
        "project_asset_root": str(HILLSIDE_PROJECT_CONTENT_ROOT / "MetaHumans" / "Kellan"),
        "ue_asset_root": "/Game/MetaHumans/Kellan",
        "asset_glob": "m_med_nrw_body.uasset",
        "minimum_asset_count": 1,
        "detection_needles": ["MetaHumans\\Kellan", "/MetaHumans/Kellan", "m_med_nrw_body"],
        "available_next_action": "use_as_cinematic_high_detail_character",
    },
    {
        "name": "Twinmotion_Rigged_City_Pedestrians__HillsideProject",
        "priority": 2,
        "quality": "project_imported_twinmotion_rigged_pedestrians",
        "preferred_use": "moving mid-distance pedestrians with compatible project-local animations",
        "source_project": "HillsideProject",
        "project_asset_root": str(HILLSIDE_PROJECT_CONTENT_ROOT / "ExternalAssets" / "Twinmotion" / "Characters" / "rigged"),
        "ue_asset_root": "/Game/ExternalAssets/Twinmotion/Characters/rigged",
        "asset_glob": "SK_*.uasset",
        "minimum_asset_count": 6,
        "detection_needles": ["Twinmotion", "Characters\\rigged", "/Characters/rigged", "SK_"],
        "available_next_action": "use_project_assets_for_moving_pedestrians",
    },
    {
        "name": "Twinmotion_Readyposed_Static_People__HillsideProject",
        "priority": 3,
        "quality": "project_imported_twinmotion_readyposed_static_people",
        "preferred_use": "background pedestrians, resting figures, and distant crowd dressing",
        "source_project": "HillsideProject",
        "project_asset_root": str(HILLSIDE_PROJECT_CONTENT_ROOT / "ExternalAssets" / "Twinmotion" / "Characters" / "readyposed" / "Meshes"),
        "ue_asset_root": "/Game/ExternalAssets/Twinmotion/Characters/readyposed/Meshes",
        "asset_glob": "SM_*.uasset",
        "minimum_asset_count": 12,
        "detection_needles": ["Twinmotion", "Characters\\readyposed", "/Characters/readyposed", "SM_"],
        "available_next_action": "use_project_assets_for_background_and_resting_pedestrians",
    },
]

METAHUMAN_KELLAN_CINEMATIC_PARTS: list[tuple[str, str]] = [
    ("body", "/Game/MetaHumans/Kellan/Male/Medium/NormalWeight/Body/m_med_nrw_body"),
    ("top", "/Game/MetaHumans/Common/Male/Medium/NormalWeight/Tops/Hoodie/Meshes/m_med_nrw_top_hoodie_nrm_High"),
    ("pants", "/Game/MetaHumans/Common/Male/Medium/NormalWeight/Bottoms/Cargopants/m_med_nrw_btm_cargopants_High"),
]

HIGH_QUALITY_VAULT_CANDIDATES: list[dict[str, Any]] = [
    {
        "name": "Free_Casual_Girl_Sample__Modular",
        "priority": 2,
        "quality": "modular_high_detail_character",
        "preferred_use": "single high-detail pedestrian after explicit import into the target project",
        "vault_cache_path": r"C:\ProgramData\Epic\EpicGamesLauncher\VaultCache\FreeCasu9958be8bd495V1\data\Content\Sample",
        "project_asset_paths": [
            str(HILLSIDE_PROJECT_CONTENT_ROOT / "Sample" / "Meshes" / "SK_Complete.uasset"),
            str(HILLSIDE_PROJECT_CONTENT_ROOT / "Sample" / "Demo" / "ThirdPersonTemplate" / "Characters" / "Mannequins" / "Animations" / "Quinn" / "MF_Walk_Fwd.uasset"),
        ],
        "detection_needles": ["Free_Casual_Girl", "FreeCasu", "SK_Complete", "SK_Body"],
    },
]


SCENE_PRESETS: dict[str, dict[str, Any]] = {
    "scene19": {
        "level_path": "/Game/Hillside/Maps/LV_Exterior",
        "anchor": {
            "anchor_id": "scene19_fa020_asset_balcony_walkway",
            "semantic_tags": ["hillside", "exterior", "fa020", "whitebrace", "balcony", "waterfront", "crowd"],
            "support_surface": {"type": "scene19_fa020_existing_asset_walkway", "z": 3180.0, "bounds": [53200.0, 59400.0, -1220.0, -620.0]},
            "target_region": {"center": [56300.0, -900.0, 3350.0], "extent": [3200.0, 360.0, 360.0]},
            "walkline": [
                [53400.0, -1030.0, 3180.0],
                [54800.0, -985.0, 3180.0],
                [56250.0, -930.0, 3180.0],
                [57750.0, -870.0, 3180.0],
                [59100.0, -820.0, 3180.0],
            ],
            "character_paths": [
                {"start": [53400.0, -1050.0, 3180.0], "end": [55050.0, -990.0, 3180.0]},
                {"start": [54320.0, -1012.0, 3180.0], "end": [56020.0, -950.0, 3180.0]},
                {"start": [55380.0, -965.0, 3180.0], "end": [57200.0, -895.0, 3180.0]},
                {"start": [56540.0, -920.0, 3180.0], "end": [56540.0, -920.0, 3180.0]},
                {"start": [57720.0, -875.0, 3180.0], "end": [59020.0, -825.0, 3180.0]},
                {"start": [59080.0, -820.0, 3180.0], "end": [57520.0, -880.0, 3180.0]},
                {"start": [58120.0, -1080.0, 3180.0], "end": [58120.0, -1080.0, 3180.0]},
                {"start": [56680.0, -1095.0, 3180.0], "end": [54850.0, -1038.0, 3180.0]},
                {"start": [55120.0, -1088.0, 3180.0], "end": [53550.0, -1042.0, 3180.0]},
                {"start": [53920.0, -815.0, 3180.0], "end": [53920.0, -815.0, 3180.0]},
                {"start": [55880.0, -800.0, 3180.0], "end": [57480.0, -820.0, 3180.0]},
                {"start": [58620.0, -820.0, 3180.0], "end": [58620.0, -820.0, 3180.0]},
                {"start": [53280.0, -1095.0, 3180.0], "end": [54920.0, -1045.0, 3180.0]},
                {"start": [54180.0, -1068.0, 3180.0], "end": [55920.0, -1015.0, 3180.0]},
                {"start": [55240.0, -1035.0, 3180.0], "end": [57040.0, -978.0, 3180.0]},
                {"start": [56380.0, -1000.0, 3180.0], "end": [56380.0, -1000.0, 3180.0]},
                {"start": [57560.0, -964.0, 3180.0], "end": [59100.0, -915.0, 3180.0]},
                {"start": [59260.0, -880.0, 3180.0], "end": [57620.0, -930.0, 3180.0]},
                {"start": [58160.0, -795.0, 3180.0], "end": [58160.0, -795.0, 3180.0]},
                {"start": [56640.0, -835.0, 3180.0], "end": [54820.0, -875.0, 3180.0]},
                {"start": [55120.0, -790.0, 3180.0], "end": [53550.0, -830.0, 3180.0]},
                {"start": [53980.0, -1085.0, 3180.0], "end": [53980.0, -1085.0, 3180.0]},
                {"start": [55840.0, -800.0, 3180.0], "end": [57420.0, -840.0, 3180.0]},
                {"start": [58620.0, -785.0, 3180.0], "end": [58620.0, -785.0, 3180.0]},
            ],
            "rest_points": [
                [53800.0, -1095.0, 3180.0],
                [55250.0, -1090.0, 3180.0],
                [57250.0, -1070.0, 3180.0],
                [58600.0, -780.0, 3180.0],
                [59200.0, -790.0, 3180.0],
                [56500.0, -800.0, 3180.0],
            ],
        },
        "skeletal_count": 24,
        "readyposed_count": 12,
        "lane_offset_width": 0.0,
        "animation_preferences": ["walking", "walking", "phoning", "idle", "walking", "sitting"],
        "support_props": [
            {
                "actor_name": "CineU_scene19_support_deck_00",
                "role": "walkway_deck",
                "mesh_path": "/Game/Hillside/Datasmith/SA/Site_Hardscape_Update/Geometries/SM_PathFloor_01A",
                "source": "existing_static_mesh",
                "location": [56200.0, -760.0, 3180.0],
                "rotation": [0.0, 4.0, 0.0],
                "scale": 0.12,
            },
            {
                "actor_name": "CineU_scene19_support_sidewalk_deck_00",
                "role": "solid_sidewalk_deck",
                "mesh_path": "/Game/Hillside/Datasmith/QC/Bridge_02/Geometries/SM_Sidewalk_01",
                "source": "existing_static_mesh",
                "location": [56250.0, -1010.0, 3134.0],
                "rotation": [0.0, 4.0, 0.0],
                "scale": 1.28,
            },
            {
                "actor_name": "CineU_scene19_support_sidewalk_deck_01",
                "role": "solid_sidewalk_deck",
                "mesh_path": "/Game/Hillside/Datasmith/QC/Bridge_02/Geometries/SM_Sidewalk_04",
                "source": "existing_static_mesh",
                "location": [56250.0, -850.0, 3134.0],
                "rotation": [0.0, 4.0, 0.0],
                "scale": 1.28,
            },
            {
                "actor_name": "CineU_scene19_support_railing_00",
                "role": "railing",
                "mesh_path": "/Game/Hillside/Datasmith/SA/Hotel_Update/Geometries/SM_Railing_A_05",
                "source": "existing_static_mesh",
                "location": [54600.0, -1390.0, 3195.0],
                "rotation": [0.0, 4.0, 0.0],
                "scale": 0.02,
            },
            {
                "actor_name": "CineU_scene19_support_railing_01",
                "role": "railing",
                "mesh_path": "/Game/Hillside/Datasmith/SA/Hotel_Update/Geometries/SM_Railing_D_01",
                "source": "existing_static_mesh",
                "location": [57600.0, -1330.0, 3195.0],
                "rotation": [0.0, 4.0, 0.0],
                "scale": 0.02,
            },
            {
                "actor_name": "CineU_scene19_support_glass_00",
                "role": "railing",
                "mesh_path": "/Game/Hillside/Datasmith/SA/Hotel_Update/Geometries/SM_Balc_Glass_56",
                "source": "existing_static_mesh",
                "location": [58650.0, -1280.0, 3220.0],
                "rotation": [0.0, 4.0, 0.0],
                "scale": 0.02,
            },
            {
                "actor_name": "CineU_scene19_support_reference_facade_00",
                "role": "facade_backplate",
                "mesh_path": "/Game/Hillside/Datasmith/QC/StH_BldgGrp_01_B/Geometries/Shell_Facade",
                "source": "existing_static_mesh",
                "location": [55800.0, -520.0, 3380.0],
                "rotation": [0.0, 4.0, 0.0],
                "scale": 0.02,
            },
            {
                "actor_name": "CineU_scene19_support_reference_windows_00",
                "role": "window_band",
                "mesh_path": "/Game/Hillside/Datasmith/QC/StH_BldgGrp_01_B/Geometries/Mullions_and_glass_Nanite",
                "source": "existing_static_mesh",
                "location": [55880.0, -505.0, 3600.0],
                "rotation": [0.0, 4.0, 0.0],
                "scale": 0.02,
            },
            {
                "actor_name": "CineU_scene19_support_reference_balcony_00",
                "role": "reference_balcony",
                "mesh_path": "/Game/Hillside/Datasmith/SA/H67_01/Geometries/H67_Balcony_060",
                "source": "existing_static_mesh",
                "location": [58950.0, -635.0, 3600.0],
                "rotation": [0.0, 4.0, 0.0],
                "scale": 0.02,
            },
            {
                "actor_name": "CineU_scene19_support_reference_glass_00",
                "role": "balcony_glass",
                "mesh_path": "/Game/Hillside/Datasmith/SA/H67_Unit_01/Geometries/H67_Unit_GlassPanels_004",
                "source": "existing_static_mesh",
                "location": [57200.0, -1160.0, 3230.0],
                "rotation": [0.0, 4.0, 0.0],
                "scale": 0.02,
            },
            {
                "actor_name": "CineU_scene19_support_reference_aframe_00",
                "role": "reference_aframe_structure",
                "mesh_path": "/Game/Hillside/Datasmith/SA/Hotel_Update/Geometries/SM_Frame_B_02_C_03",
                "source": "existing_static_mesh",
                "source_level_path": "/Game/Hillside/Maps/SA/LV_Hotel_Update",
                "source_actor_label": "ISM_AFrame",
                "source_instance_index": 0,
                "source_instance_local_location": [6989.501, 5520.055, 1402.073],
                "source_instance_local_rotation": [0.0, 0.0, 0.0],
                "location": [55550.0, -610.0, 3180.0],
                "rotation": [0.0, 94.0, 0.0],
                "scale": 0.2,
            },
            {
                "actor_name": "CineU_scene19_support_reference_aframe_01",
                "role": "reference_aframe_structure",
                "mesh_path": "/Game/Hillside/Datasmith/SA/Hotel_Update/Geometries/SM_Frame_L_C_02",
                "source": "existing_static_mesh",
                "source_level_path": "/Game/Hillside/Maps/SA/LV_Hotel_Update",
                "source_actor_label": "ISM_AFrame",
                "source_instance_index": 0,
                "source_instance_local_location": [6989.504, -2225.677, 1158.238],
                "source_instance_local_rotation": [0.0, 180.0, 0.0],
                "location": [57650.0, -610.0, 3180.0],
                "rotation": [0.0, 94.0, 0.0],
                "scale": 0.2,
            },
            {
                "actor_name": "CineU_scene19_support_reference_aframe_02",
                "role": "reference_aframe_structure",
                "mesh_path": "/Game/Hillside/Datasmith/SA/Hotel_Update/Geometries/SM_Frame_B_02_C_03",
                "source": "existing_static_mesh",
                "source_level_path": "/Game/Hillside/Maps/SA/LV_Hotel_Update",
                "source_actor_label": "ISM_AFrame",
                "source_instance_index": 0,
                "source_instance_local_location": [6989.501, 5520.055, 1402.073],
                "source_instance_local_rotation": [0.0, 0.0, 0.0],
                "location": [54250.0, -610.0, 3180.0],
                "rotation": [0.0, 94.0, 0.0],
                "scale": 0.16,
            },
            {
                "actor_name": "CineU_scene19_support_reference_aframe_03",
                "role": "reference_aframe_structure",
                "mesh_path": "/Game/Hillside/Datasmith/SA/Hotel_Update/Geometries/SM_Frame_L_C_02",
                "source": "existing_static_mesh",
                "source_level_path": "/Game/Hillside/Maps/SA/LV_Hotel_Update",
                "source_actor_label": "ISM_AFrame",
                "source_instance_index": 0,
                "source_instance_local_location": [6989.504, -2225.677, 1158.238],
                "source_instance_local_rotation": [0.0, 180.0, 0.0],
                "location": [55050.0, -610.0, 3180.0],
                "rotation": [0.0, 94.0, 0.0],
                "scale": 0.16,
            },
            {
                "actor_name": "CineU_scene19_support_reference_aframe_04",
                "role": "reference_aframe_structure",
                "mesh_path": "/Game/Hillside/Datasmith/SA/Hotel_Update/Geometries/SM_Frame_B_02_C_03",
                "source": "existing_static_mesh",
                "source_level_path": "/Game/Hillside/Maps/SA/LV_Hotel_Update",
                "source_actor_label": "ISM_AFrame",
                "source_instance_index": 0,
                "source_instance_local_location": [6989.501, 5520.055, 1402.073],
                "source_instance_local_rotation": [0.0, 0.0, 0.0],
                "location": [55950.0, -610.0, 3180.0],
                "rotation": [0.0, 94.0, 0.0],
                "scale": 0.16,
            },
            {
                "actor_name": "CineU_scene19_support_reference_aframe_05",
                "role": "reference_aframe_structure",
                "mesh_path": "/Game/Hillside/Datasmith/SA/Hotel_Update/Geometries/SM_Frame_L_C_02",
                "source": "existing_static_mesh",
                "source_level_path": "/Game/Hillside/Maps/SA/LV_Hotel_Update",
                "source_actor_label": "ISM_AFrame",
                "source_instance_index": 0,
                "source_instance_local_location": [6989.504, -2225.677, 1158.238],
                "source_instance_local_rotation": [0.0, 180.0, 0.0],
                "location": [56850.0, -610.0, 3180.0],
                "rotation": [0.0, 94.0, 0.0],
                "scale": 0.16,
            },
            {
                "actor_name": "CineU_scene19_support_reference_aframe_06",
                "role": "reference_aframe_structure",
                "mesh_path": "/Game/Hillside/Datasmith/SA/Hotel_Update/Geometries/SM_Frame_B_02_C_03",
                "source": "existing_static_mesh",
                "source_level_path": "/Game/Hillside/Maps/SA/LV_Hotel_Update",
                "source_actor_label": "ISM_AFrame",
                "source_instance_index": 0,
                "source_instance_local_location": [6989.501, 5520.055, 1402.073],
                "source_instance_local_rotation": [0.0, 0.0, 0.0],
                "location": [58450.0, -610.0, 3180.0],
                "rotation": [0.0, 94.0, 0.0],
                "scale": 0.16,
            },
            {
                "actor_name": "CineU_scene19_support_reference_aframe_07",
                "role": "reference_aframe_structure",
                "mesh_path": "/Game/Hillside/Datasmith/SA/Hotel_Update/Geometries/SM_Frame_L_C_02",
                "source": "existing_static_mesh",
                "source_level_path": "/Game/Hillside/Maps/SA/LV_Hotel_Update",
                "source_actor_label": "ISM_AFrame",
                "source_instance_index": 0,
                "source_instance_local_location": [6989.504, -2225.677, 1158.238],
                "source_instance_local_rotation": [0.0, 180.0, 0.0],
                "location": [57650.0, -610.0, 3180.0],
                "rotation": [0.0, 94.0, 0.0],
                "scale": 0.16,
            },
        ],
        "shots": [
            {
                "shot_id": "scene19_surveillance_fixed",
                "type": "surveillance_fixed",
                "camera_name": "CineU_scene19_surveillance_fixed",
                "start_frame": 0,
                "end_frame": 1440,
                "source_camera_label": "02_FA_020_E_reference_long_lens",
                "location": [50600.0, -2240.0, 3740.0],
                "target": [54850.0, -930.0, 3460.0],
                "rotation": [-1.0, 20.0, 0.0],
                "focal_length": 26.0,
            },
            {
                "shot_id": "scene19_surveillance_oblique",
                "type": "surveillance_oblique",
                "camera_name": "CineU_scene19_surveillance_oblique",
                "start_frame": 0,
                "end_frame": 1440,
                "source_camera_label": "scene19_reference_balcony_close_mid",
                "location": [51850.0, -1840.0, 3520.0],
                "target": [56650.0, -910.0, 3400.0],
                "focal_length": 38.0,
            },
            {
                "shot_id": "scene19_top_down",
                "type": "top_down",
                "camera_name": "CineU_scene19_top_down",
                "start_frame": 0,
                "end_frame": 1440,
                "location": [53700.0, -2550.0, 5800.0],
                "target": [56650.0, -930.0, 3180.0],
                "focal_length": 42.0,
            },
            {
                "shot_id": "scene19_first_person",
                "type": "first_person",
                "camera_name": "CineU_scene19_first_person_walk",
                "start_frame": 0,
                "end_frame": 1440,
                "source_camera_label": "scene19_reference_first_person_along_balcony",
                "location": [53450.0, -1490.0, 3440.0],
                "end_location": [55250.0, -1450.0, 3440.0],
                "target": [56850.0, -545.0, 3580.0],
                "focal_length": 31.0,
            },
        ],
    },
    "scene24": {
        "level_path": "/Game/Hillside/Maps/LV_Interior",
        "anchor": {
            "anchor_id": "scene24_upper_hall",
            "semantic_tags": ["hillside", "interior", "hall", "crowd"],
            "support_surface": {"type": "scene24_upper_hall_floor", "z": 4731.0, "bounds": [93180.0, 93290.0, -3300.0, -2780.0]},
            "target_region": {"center": [93240.0, -3060.0, 4800.0], "extent": [120.0, 320.0, 260.0]},
            "walkline": [
                [93220.0, -3268.0, 4731.0],
                [93265.0, -3180.0, 4731.0],
                [93205.0, -3072.0, 4731.0],
                [93270.0, -3048.0, 4731.0],
                [93220.0, -3000.0, 4731.0],
                [93255.0, -2952.0, 4731.0],
            ],
            "character_paths": [
                {"start": [93185.0, -3300.0, 4731.0], "end": [93185.0, -3040.0, 4731.0]},
                {"start": [93265.0, -3300.0, 4731.0], "end": [93265.0, -3040.0, 4731.0]},
                {"start": [93185.0, -3210.0, 4731.0], "end": [93185.0, -2930.0, 4731.0]},
                {"start": [93225.0, -3250.0, 4731.0], "end": [93225.0, -3250.0, 4731.0]},
                {"start": [93265.0, -3210.0, 4731.0], "end": [93265.0, -2950.0, 4731.0]},
                {"start": [93265.0, -3130.0, 4731.0], "end": [93265.0, -2870.0, 4731.0]},
            ],
            "rest_points": [
                [93200.0, -3270.0, 4731.0],
                [93285.0, -3185.0, 4731.0],
                [93205.0, -3105.0, 4731.0],
                [93285.0, -3060.0, 4731.0],
                [93200.0, -3008.0, 4731.0],
                [93285.0, -2920.0, 4731.0],
            ],
            "interior_expansion_candidates": [
                {
                    "space": "living",
                    "status": "visually_usable_v2",
                    "level_path": "/Game/Hillside/Maps/LV_Interior",
                    "camera_label": "native_02_SU_050_I",
                    "frame": 0,
                    "recommended_use": "lounge establishing and close surveillance-style interior view",
                    "diagnostic_evidence_path": (
                        "workspace/diagnostics/hillside_scene19_scene24/renders/"
                        "scene24_interior_space_grid_20260622_234059/movie_frames/movie_frame_0000.png"
                    ),
                    "visual_review_contact_sheet": (
                        "workspace/visual_feedback/hillside_scene19_scene24/indoor_space_discovery_20260622/"
                        "LV_Interior_complete_room_grid_v2_contact_sheet.png"
                    ),
                },
                {
                    "space": "dining_b",
                    "status": "visually_usable_v2",
                    "level_path": "/Game/Hillside/Maps/LV_Interior",
                    "camera_label": "native_02_FA_080_I",
                    "frame": 1,
                    "recommended_use": "warm dining-table scene with visible chairs and window background",
                    "diagnostic_evidence_path": (
                        "workspace/diagnostics/hillside_scene19_scene24/renders/"
                        "scene24_interior_space_grid_20260622_234059/movie_frames/movie_frame_0001.png"
                    ),
                    "visual_review_contact_sheet": (
                        "workspace/visual_feedback/hillside_scene19_scene24/indoor_space_discovery_20260622/"
                        "LV_Interior_complete_room_grid_v2_contact_sheet.png"
                    ),
                },
                {
                    "space": "dining_a",
                    "status": "visually_usable_v2",
                    "level_path": "/Game/Hillside/Maps/LV_Interior",
                    "camera_label": "native_02_FA_060_I",
                    "frame": 2,
                    "recommended_use": "clean dining-room table view with strong window and lamp contrast",
                    "diagnostic_evidence_path": (
                        "workspace/diagnostics/hillside_scene19_scene24/renders/"
                        "scene24_interior_space_grid_20260622_234059/movie_frames/movie_frame_0002.png"
                    ),
                    "visual_review_contact_sheet": (
                        "workspace/visual_feedback/hillside_scene19_scene24/indoor_space_discovery_20260622/"
                        "LV_Interior_complete_room_grid_v2_contact_sheet.png"
                    ),
                },
                {
                    "space": "kitchen",
                    "status": "visually_usable_v2",
                    "level_path": "/Game/Hillside/Maps/LV_Interior",
                    "camera_label": "kitchen_worktop",
                    "frame": 15,
                    "recommended_use": "compact kitchen detail insert rather than crowd movement area",
                    "diagnostic_evidence_path": (
                        "workspace/diagnostics/hillside_scene19_scene24/renders/"
                        "scene24_interior_space_grid_20260622_234059/movie_frames/movie_frame_0015.png"
                    ),
                    "visual_review_contact_sheet": (
                        "workspace/visual_feedback/hillside_scene19_scene24/indoor_space_discovery_20260622/"
                        "LV_Interior_complete_room_grid_v2_contact_sheet.png"
                    ),
                },
                {
                    "space": "foyer",
                    "status": "usable_with_reframe",
                    "level_path": "/Game/Hillside/Maps/LV_Interior",
                    "camera_label": "foyer_long_axis_a",
                    "frame": 16,
                    "recommended_use": "transitional interior space after rechecking foreground railing occlusion",
                    "diagnostic_evidence_path": (
                        "workspace/diagnostics/hillside_scene19_scene24/renders/"
                        "scene24_interior_space_grid_20260622_234059/movie_frames/movie_frame_0016.png"
                    ),
                    "visual_review_contact_sheet": (
                        "workspace/visual_feedback/hillside_scene19_scene24/indoor_space_discovery_20260622/"
                        "LV_Interior_complete_room_grid_v2_contact_sheet.png"
                    ),
                },
                {
                    "space": "bedroom",
                    "status": "too_dark_for_first_batch",
                    "level_path": "/Game/Hillside/Maps/LV_Interior",
                    "camera_label": "bedroom_wide_a",
                    "frame": 18,
                    "recommended_use": "defer until a brighter bedroom light rig is built",
                    "diagnostic_evidence_path": (
                        "workspace/diagnostics/hillside_scene19_scene24/renders/"
                        "scene24_interior_space_grid_20260622_234059/movie_frames/movie_frame_0018.png"
                    ),
                    "visual_review_contact_sheet": (
                        "workspace/visual_feedback/hillside_scene19_scene24/indoor_space_discovery_20260622/"
                        "LV_Interior_complete_room_grid_v2_contact_sheet.png"
                    ),
                },
            ],
        },
        "skeletal_count": 6,
        "readyposed_count": 0,
        "lane_offset_width": 0.0,
        "animation_preferences": ["walking", "walking", "phoning", "idle", "walking", "walking"],
        "shots": [
            {
                "shot_id": "scene24_surveillance_fixed",
                "type": "surveillance_fixed",
                "camera_name": "CineU_scene24_surveillance_corner",
                "source_camera_label": "v60_upper_hall_surveillance_final_probe",
                "start_frame": 0,
                "end_frame": 1440,
                "location": [93270.0, -2815.0, 4970.0],
                "target": [93240.0, -3285.0, 4695.0],
                "rotation": [-37.133204075349205, -93.63295073948821, 0.0],
                "focal_length": 12.0,
                "exposure_bias": -0.35,
            },
            {
                "shot_id": "scene24_top_down",
                "type": "top_down",
                "camera_name": "CineU_scene24_top_down",
                "source_camera_label": "v61_upper_hall_top_down",
                "start_frame": 0,
                "end_frame": 1440,
                "location": [93270.0, -3050.0, 5010.0],
                "end_location": [93270.0, -3050.0, 5010.0],
                "target": [93270.0, -3050.0, 4731.0],
                "rotation": [-90.0, 0.0, 0.0],
                "focal_length": 10.0,
                "exposure_bias": -0.35,
            },
            {
                "shot_id": "scene24_first_person",
                "type": "first_person",
                "camera_name": "CineU_scene24_first_person",
                "source_camera_label": "v65_upper_hall_first_person_wide_clear",
                "start_frame": 0,
                "end_frame": 1440,
                "location": [93195.0, -2785.0, 4865.0],
                "end_location": [93195.0, -2810.0, 4865.0],
                "target": [93255.0, -3220.0, 4832.0],
                "rotation": [-4.778113639980552, -79.15969454566944, 0.0],
                "end_rotation": [-5.320270553156136, -77.9052429229879, 0.0],
                "focal_length": 12.0,
                "exposure_bias": -0.35,
            },
            {
                "shot_id": "scene24_fixed_doorway",
                "type": "fixed_doorway",
                "camera_name": "CineU_scene24_fixed_doorway",
                "source_camera_label": "v66_upper_hall_fixed_doorway",
                "start_frame": 0,
                "end_frame": 1440,
                "location": [92745.0, -2795.0, 4965.0],
                "target": [93255.0, -3034.0, 4760.0],
                "rotation": [-20.557790732135395, -24.686458042475966, 0.0],
                "focal_length": 16.0,
                "exposure_bias": -0.35,
            },
        ],
    },
    "scene24_indoor_multiroom": {
        "level_path": "/Game/Hillside/Maps/LV_Interior",
        "anchor": {
            "anchor_id": "scene24_indoor_multiroom_living_dining_kitchen",
            "semantic_tags": ["hillside", "interior", "multiroom", "living", "dining", "kitchen", "crowd"],
            "support_surface": {"type": "scene24_indoor_living_dining_floor", "z": 4426.0, "bounds": [92190.0, 93320.0, -4335.0, -2860.0]},
            "target_region": {"center": [92980.0, -3650.0, 4560.0], "extent": [900.0, 720.0, 240.0]},
            "walkline": [
                [92985.0, -3060.0, 4426.0],
                [93025.0, -3260.0, 4426.0],
                [92320.0, -4230.0, 4426.0],
                [92585.0, -3990.0, 4426.0],
                [93040.0, -4305.0, 4426.0],
                [93230.0, -3975.0, 4426.0],
            ],
            "character_paths": [
                {"start": [92985.0, -3060.0, 4426.0], "end": [93025.0, -3260.0, 4426.0]},
                {"start": [92320.0, -4230.0, 4426.0], "end": [92585.0, -3990.0, 4426.0]},
                {"start": [93040.0, -4305.0, 4426.0], "end": [93040.0, -4305.0, 4426.0]},
                {"start": [93120.0, -4250.0, 4426.0], "end": [93230.0, -3975.0, 4426.0]},
            ],
            "rest_points": [
                [93040.0, -4305.0, 4426.0],
                [92720.0, -4180.0, 4426.0],
                [93010.0, -3150.0, 4426.0],
                [93200.0, -4025.0, 4426.0],
            ],
        },
        "skeletal_count": 8,
        "readyposed_count": 4,
        "lane_offset_width": 36.0,
        "animation_preferences": ["walking", "walking", "idle", "walking"],
        "shots": [
            {
                "shot_id": "scene24_indoor_living_fixed",
                "type": "indoor_living_fixed",
                "camera_name": "CineU_scene24_indoor_living_fixed",
                "source_camera_label": "native_02_SU_050_I",
                "start_frame": 0,
                "end_frame": 1440,
                "location": [93025.935, -2941.444, 4470.268],
                "target": [93055.0, -3240.0, 4470.0],
                "rotation": [0.0, 70.412, 0.0],
                "focal_length": 18.0,
                "exposure_bias": -1.1,
            },
            {
                "shot_id": "scene24_indoor_dining_b_fixed",
                "type": "indoor_dining_b_fixed",
                "camera_name": "CineU_scene24_indoor_dining_b_fixed",
                "source_camera_label": "native_02_FA_080_I",
                "start_frame": 0,
                "end_frame": 1440,
                "location": [92197.92, -4193.095, 4518.537],
                "target": [92540.0, -4090.0, 4460.0],
                "rotation": [0.0, 0.0, 0.0],
                "focal_length": 18.0,
                "exposure_bias": -1.1,
            },
            {
                "shot_id": "scene24_indoor_dining_a_fixed",
                "type": "indoor_dining_a_fixed",
                "camera_name": "CineU_scene24_indoor_dining_a_fixed",
                "source_camera_label": "native_02_FA_060_I",
                "start_frame": 0,
                "end_frame": 1440,
                "location": [93096.563, -3870.218, 4528.946],
                "target": [93140.0, -4110.0, 4465.0],
                "rotation": [0.0, -90.0, 0.0],
                "focal_length": 18.0,
                "exposure_bias": -1.1,
            },
            {
                "shot_id": "scene24_indoor_kitchen_insert",
                "type": "indoor_kitchen_insert",
                "camera_name": "CineU_scene24_indoor_kitchen_insert",
                "source_camera_label": "kitchen_worktop",
                "start_frame": 0,
                "end_frame": 1440,
                "location": [92580.0, -4310.0, 4560.0],
                "target": [92800.0, -4090.0, 4480.0],
                "focal_length": 18.0,
                "exposure_bias": -1.25,
            },
        ],
    },
}


def build_hillside_scene_plan(
    scene_id: str,
    asset_inventory: dict[str, Any],
    character_skeletons: dict[str, Any] | None = None,
    local_asset_index: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a reusable asset-first plan from discovered Hillside assets."""
    scene_key = scene_id.lower().strip()
    if scene_key not in SCENE_PRESETS:
        raise ValueError(f"Unsupported Hillside scene id: {scene_id!r}")

    preset = SCENE_PRESETS[scene_key]
    level_path = str(preset["level_path"])
    level_asset = _require_inventory_package(asset_inventory, "maps", level_path)
    skeleton_data = character_skeletons or {}
    skeletal_characters, animation_bindings = _build_skeletal_crowd(
        scene_key,
        preset,
        asset_inventory,
        skeleton_data,
    )
    high_detail_modular_parts: list[dict[str, Any]] = []
    if scene_key == "scene19":
        high_detail_modular_parts = _apply_high_detail_characters(
            skeletal_characters,
            animation_bindings,
            FREE_CASUAL_GIRL_SCENE19_VARIANTS,
        )
    elif scene_key in {"scene24", "scene24_indoor_multiroom"}:
        high_detail_modular_parts = _apply_high_detail_characters(
            skeletal_characters,
            animation_bindings,
            FREE_CASUAL_GIRL_SCENE24_VARIANTS,
        )
    readyposed_count = int(preset["readyposed_count"])
    readyposed = _cycle_assets(_package_paths(asset_inventory.get("readyposed_static_meshes", [])), readyposed_count)
    if readyposed_count > 0 and not readyposed:
        raise LookupError("Hillside readyposed static mesh inventory is empty")
    required_assets = ["level", "skeletal_mesh", "animation"]
    if readyposed_count > 0:
        required_assets.append("readyposed_static_mesh")
    support_props = [dict(prop) for prop in preset.get("support_props", [])]
    if scene_key == "scene19":
        for prop in support_props:
            if prop.get("role") == "reference_aframe_structure":
                prop.setdefault("material_override", SCENE19_WHITE_AFRAME_MATERIAL)
    if support_props:
        required_assets.append("support_static_mesh")
    anchor = deepcopy(preset["anchor"])
    if scene_key == "scene19":
        anchor["native_reference"] = deepcopy(SCENE19_NATIVE_WHITEBRACE_REFERENCE)
        anchor["native_building_reference"] = deepcopy(SCENE19_NATIVE_STH_BUILDING_REFERENCE)
    elif scene_key == "scene24_indoor_multiroom":
        anchor["interior_expansion_candidates"] = deepcopy(SCENE_PRESETS["scene24"]["anchor"]["interior_expansion_candidates"])

    plan = {
        "schema_version": "cineu.asset_first_scene_plan.v1",
        "scene_id": scene_key,
        "source_project": _source_project(asset_inventory),
        "requirements": {
            "asset_first": True,
            "generated_world_allowed": False,
            "requires_existing_assets": required_assets,
        },
        "environment_asset": {
            "asset_id": f"asset_hillside_{level_asset['asset_name'].lower()}",
            "name": level_asset["asset_name"],
            "ue_path": level_path,
            "type": "level",
            "source": "existing_level",
            "object_path": level_asset.get("object_path"),
        },
        "anchor": anchor,
        "support_props": support_props,
        "crowd": {
            "policy": "reuse_existing_twinmotion_characters",
            "skeletal_characters": skeletal_characters,
            "readyposed_static_meshes": [
                {
                    "actor_name": f"CineU_{scene_key}_readyposed_{index:02d}",
                    "mesh_path": path,
                    "source": "existing_static_mesh",
                }
                for index, path in enumerate(readyposed)
            ],
            "animation_bindings": animation_bindings,
            "animation_mix": _animation_mix(animation_bindings),
            "lane_offset_width": float(preset.get("lane_offset_width", 28.0)),
            "character_quality_policy": "prefer_imported_scanned_or_high_detail_characters_before_twinmotion_fallback",
            "high_quality_character_sources": _high_quality_character_sources(local_asset_index),
            "high_detail_modular_parts": high_detail_modular_parts,
            "metahuman_cinematic_parts": _metahuman_cinematic_parts(scene_key, preset),
        },
        "shots": [dict(shot) for shot in preset["shots"]],
        "render": {
            "duration_sec": 60.0,
            "fps": 24,
            "frame_range": [0, 1440],
            "resolution": [1280, 720],
            "format": "mp4",
        },
    }
    if local_asset_index is not None:
        plan["asset_index_evidence"] = _asset_index_evidence(
            local_asset_index,
            level_path=level_path,
            support_props=support_props,
            skeletal_characters=skeletal_characters,
            animation_bindings=animation_bindings,
            readyposed_static_meshes=plan["crowd"]["readyposed_static_meshes"],
            native_building_reference=anchor.get("native_building_reference"),
        )
    return plan


def _metahuman_cinematic_parts(scene_key: str, preset: dict[str, Any]) -> list[dict[str, Any]]:
    available_parts = [
        (role, mesh_path)
        for role, mesh_path in METAHUMAN_KELLAN_CINEMATIC_PARTS
        if _project_package_exists(mesh_path)
    ]
    if len(available_parts) < len(METAHUMAN_KELLAN_CINEMATIC_PARTS):
        return []

    rest_points = preset["anchor"].get("rest_points") or []
    if scene_key == "scene24":
        location = [93220.0, -3250.0, float(preset["anchor"]["support_surface"]["z"])]
        rotation = [0.0, -90.0, 0.0]
    elif rest_points:
        location = [float(value) for value in rest_points[min(2, len(rest_points) - 1)]]
        rotation = [0.0, -25.0, 0.0]
    else:
        center = preset["anchor"]["target_region"]["center"]
        location = [float(center[0]), float(center[1]), float(preset["anchor"]["support_surface"]["z"])]
        rotation = [0.0, -25.0, 0.0]

    return [
        {
            "actor_name": f"CineU_{scene_key}_metahuman_kellan_{role}",
            "mesh_path": mesh_path,
            "location": list(location),
            "end_location": list(location),
            "rotation": list(rotation),
            "scale": 1.0,
            "animation_path": "",
            "motion": "static",
            "source": "existing_metahuman_skeletal_mesh",
        }
        for role, mesh_path in available_parts
    ]


def _source_project(asset_inventory: dict[str, Any]) -> str:
    project = asset_inventory.get("project")
    if isinstance(project, dict):
        return str(project.get("name") or project.get("project_name") or "HillsideProject")
    return "HillsideProject"


def _apply_high_detail_characters(
    skeletal_characters: list[dict[str, Any]],
    animation_bindings: list[dict[str, Any]],
    variants: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    required_paths = [
        FREE_CASUAL_GIRL_BODY_MESH_PATH,
        FREE_CASUAL_GIRL_WALK_ANIMATION_PATH,
        *[mesh for variant in variants for _role, mesh in variant["parts"]],
    ]
    if any(not _project_package_exists(path) for path in required_paths):
        return []

    modular_parts: list[dict[str, Any]] = []
    for variant in variants:
        index = int(variant["index"])
        if len(skeletal_characters) <= index or len(animation_bindings) <= index:
            continue
        actor_name = skeletal_characters[index]["actor_name"]
        skeletal_characters[index] = {
            "actor_name": actor_name,
            "mesh_path": FREE_CASUAL_GIRL_BODY_MESH_PATH,
            "mesh_skeleton": FREE_CASUAL_GIRL_SKELETON_HINT,
            "source": "existing_high_detail_skeletal_mesh",
        }
        animation_bindings[index] = {
            "actor_name": actor_name,
            "mesh_path": FREE_CASUAL_GIRL_BODY_MESH_PATH,
            "animation_path": FREE_CASUAL_GIRL_WALK_ANIMATION_PATH,
            "mesh_skeleton": FREE_CASUAL_GIRL_SKELETON_HINT,
            "animation_skeleton": FREE_CASUAL_GIRL_SKELETON_HINT,
            "motion": "walking",
            "source": "existing_high_detail_animation",
        }
        for role, mesh_path in variant["parts"]:
            modular_parts.append(
                {
                    "actor_name": f"{actor_name}_{role}",
                    "host_actor_name": actor_name,
                    "mesh_path": mesh_path,
                    "animation_path": FREE_CASUAL_GIRL_WALK_ANIMATION_PATH,
                    "mesh_skeleton": FREE_CASUAL_GIRL_SKELETON_HINT,
                    "animation_skeleton": FREE_CASUAL_GIRL_SKELETON_HINT,
                    "motion": "walking",
                    "source": "existing_high_detail_modular_skeletal_mesh",
                }
            )
    return modular_parts


def _project_package_exists(package_path: str) -> bool:
    relative = package_path.removeprefix("/Game/").strip("/")
    if not relative:
        return False
    return (HILLSIDE_PROJECT_CONTENT_ROOT / Path(relative).with_suffix(".uasset")).exists()


def _high_quality_character_sources(local_asset_index: dict[str, Any] | None) -> list[dict[str, Any]]:
    sources = []
    for pack in HIGH_QUALITY_CHARACTER_PACKS:
        source = dict(pack)
        fab_listing = _fab_library_listing(local_asset_index, pack)
        if _asset_index_matches(local_asset_index, pack["detection_needles"], source_root=HILLSIDE_PROJECT_CONTENT_ROOT):
            source["local_status"] = "available_in_project"
            source["fab_status"] = "project_imported"
            source["download_status"] = str((fab_listing or {}).get("download_status") or "")
            source["download_path"] = str((fab_listing or {}).get("download_path") or "")
            source["next_action"] = "use_project_imported_assets"
        elif fab_listing is not None and fab_listing.get("download_status") == "downloaded":
            source["local_status"] = "available_in_fab_library"
            source["fab_status"] = "downloaded_not_imported"
            source["download_status"] = "downloaded_not_imported"
            source["download_path"] = str(fab_listing.get("download_path") or "")
            source["next_action"] = "import_fab_library_pack_into_hillside_project"
            source["fab_library_listing"] = fab_listing
        elif fab_listing is not None:
            source["local_status"] = "missing_from_project"
            source["fab_status"] = "not_downloaded"
            source["download_status"] = "not_downloaded"
            source["download_path"] = str(fab_listing.get("download_path") or "")
            source["next_action"] = "download_from_fab_library"
            source["fab_library_listing"] = fab_listing
        else:
            source["local_status"] = "missing_from_project"
            source["fab_status"] = "missing_from_fab_library"
            source["download_status"] = ""
            source["download_path"] = ""
            source["next_action"] = "acquire_or_add_to_fab_library"
        sources.append(source)
    for candidate in HIGH_QUALITY_PROJECT_CHARACTER_CANDIDATES:
        sources.append(_project_character_candidate_source(candidate, local_asset_index))
    for candidate in HIGH_QUALITY_VAULT_CANDIDATES:
        source = dict(candidate)
        if any(Path(path).exists() for path in candidate.get("project_asset_paths", [])):
            source["local_status"] = "available_in_project"
        elif _asset_index_matches(local_asset_index, candidate["detection_needles"], source_root=HILLSIDE_PROJECT_CONTENT_ROOT):
            source["local_status"] = "available_in_project"
        else:
            source["local_status"] = "available_in_vault_cache" if Path(str(candidate["vault_cache_path"])).exists() else "missing_from_vault_cache"
        sources.append(source)
    return sources


def _project_character_candidate_source(candidate: dict[str, Any], local_asset_index: dict[str, Any] | None) -> dict[str, Any]:
    source = dict(candidate)
    asset_root = Path(str(candidate["project_asset_root"]))
    asset_glob = str(candidate.get("asset_glob") or "*.uasset")
    asset_paths = sorted(asset_root.rglob(asset_glob)) if asset_root.exists() else []
    has_index_match = _asset_index_matches(local_asset_index, list(candidate["detection_needles"]), source_root=asset_root)
    minimum_asset_count = int(candidate.get("minimum_asset_count") or 1)

    source["project_asset_root"] = str(asset_root)
    source["asset_evidence_count"] = len(asset_paths)
    source["sample_project_asset_paths"] = [str(path) for path in asset_paths[:8]]
    if len(asset_paths) >= minimum_asset_count or has_index_match:
        source["local_status"] = "available_in_project"
        source["next_action"] = str(candidate["available_next_action"])
    else:
        source["local_status"] = "missing_from_project"
        source["next_action"] = "locate_or_import_project_assets"
    source.pop("available_next_action", None)
    return source


def _fab_library_listing(local_asset_index: dict[str, Any] | None, pack: dict[str, Any]) -> dict[str, Any] | None:
    if not local_asset_index:
        return None
    listing_id = str(pack.get("fab_listing_id") or "").lower()
    lowered_needles = [needle.lower() for needle in pack.get("detection_needles", [])]
    fab_library = local_asset_index.get("fab_library") or {}
    for listing in fab_library.get("listings", []):
        text = " ".join(str(listing.get(field, "")) for field in ["listing_id", "listing_uid", "listing_url", "title", "download_path"]).lower()
        if listing_id and listing_id in text:
            return dict(listing)
        if any(needle in text for needle in lowered_needles):
            return dict(listing)
    return None


def _asset_index_matches(local_asset_index: dict[str, Any] | None, needles: list[str], *, source_root: Path | None = None) -> bool:
    if not local_asset_index:
        return False
    lowered_needles = [needle.lower() for needle in needles]
    root_text = str(source_root).lower() if source_root is not None else ""
    for asset in local_asset_index.get("assets", []):
        text = " ".join(
            str(asset.get(field, ""))
            for field in ["asset_id", "name", "type", "ue_path", "source_path", "source_type"]
        ).lower()
        if any(needle in text for needle in lowered_needles) and (
            source_root is None or str(asset.get("source_path", "")).lower().startswith(root_text)
        ):
            return True
    return False


def _asset_index_evidence(
    local_asset_index: dict[str, Any],
    *,
    level_path: str,
    support_props: list[dict[str, Any]],
    skeletal_characters: list[dict[str, Any]],
    animation_bindings: list[dict[str, Any]],
    readyposed_static_meshes: list[dict[str, Any]],
    native_building_reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    by_path = {str(asset.get("ue_path")): asset for asset in local_asset_index.get("assets", []) if asset.get("ue_path")}
    environment_asset = _require_index_asset(by_path, level_path, "level")
    support_records = [_require_index_asset(by_path, str(prop["mesh_path"]), "support static mesh") for prop in support_props]
    skeletal_records = [_require_index_asset(by_path, str(item["mesh_path"]), "skeletal mesh") for item in skeletal_characters]
    animation_records = [_require_index_asset(by_path, str(item["animation_path"]), "animation") for item in animation_bindings]
    readyposed_records = [_require_index_asset(by_path, str(item["mesh_path"]), "readyposed static mesh") for item in readyposed_static_meshes]
    evidence = {
        "source_schema_version": local_asset_index.get("schema_version"),
        "asset_first_ready": bool(local_asset_index.get("asset_first_ready")),
        "asset_count": int(local_asset_index.get("asset_count", 0)),
        "environment_asset": _index_asset_record(environment_asset),
        "support_props": [_index_asset_record(asset) for asset in support_records],
        "support_prop_match_count": len(support_records),
        "skeletal_mesh_match_count": len(skeletal_records),
        "animation_match_count": len(animation_records),
        "readyposed_static_mesh_match_count": len(readyposed_records),
    }
    if native_building_reference:
        evidence["native_building_reference"] = _native_building_index_evidence(by_path, native_building_reference)
    return evidence


def _native_building_index_evidence(by_path: dict[str, dict[str, Any]], reference: dict[str, Any]) -> dict[str, Any]:
    source_level = _require_index_asset(by_path, str(reference["source_level_path"]), "native scene19 building level")
    key_geometry = [
        _require_index_asset(by_path, str(path), "native scene19 building geometry")
        for path in reference.get("key_geometry_assets", [])
    ]
    return {
        "building_id": reference.get("building_id"),
        "source_level": _index_asset_record(source_level),
        "key_geometry_assets": [_index_asset_record(asset) for asset in key_geometry],
        "key_geometry_match_count": len(key_geometry),
    }


def _require_index_asset(by_path: dict[str, dict[str, Any]], ue_path: str, role: str) -> dict[str, Any]:
    asset = by_path.get(ue_path)
    if asset is None:
        raise LookupError(f"Required Hillside {role} is not indexed in local asset index: {ue_path}")
    return asset


def _index_asset_record(asset: dict[str, Any]) -> dict[str, Any]:
    return {
        "asset_id": asset.get("asset_id"),
        "name": asset.get("name"),
        "type": asset.get("type"),
        "ue_path": asset.get("ue_path"),
        "source_type": asset.get("source_type"),
        "source_path": asset.get("source_path"),
        "import_required": asset.get("import_required"),
    }


def _require_inventory_package(asset_inventory: dict[str, Any], section: str, package_name: str) -> dict[str, Any]:
    for item in asset_inventory.get(section, []):
        if str(item.get("package_name")) == package_name:
            return item
    raise LookupError(f"Required Hillside asset not found in {section}: {package_name}")


def _package_paths(items: list[dict[str, Any]]) -> list[str]:
    paths = [str(item.get("package_name")) for item in items if item.get("package_name")]
    return sorted(dict.fromkeys(paths))


def _build_skeletal_crowd(
    scene_key: str,
    preset: dict[str, Any],
    asset_inventory: dict[str, Any],
    character_skeletons: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    mesh_skeletons = {
        str(item.get("path")): str(item.get("skeleton"))
        for item in character_skeletons.get("meshes", [])
        if item.get("path") and item.get("skeleton") and item.get("loaded", True)
    }
    animation_skeletons = {
        str(item.get("path")): str(item.get("skeleton"))
        for item in character_skeletons.get("animations", [])
        if item.get("path") and item.get("skeleton") and item.get("loaded", True)
    }
    animated_skeletons = set(animation_skeletons.values())
    mesh_paths = [
        path
        for path in _package_paths(asset_inventory.get("rigged_skeletal_meshes", []))
        if path in mesh_skeletons and mesh_skeletons[path] in animated_skeletons
    ]
    if not mesh_paths:
        mesh_paths = _package_paths(asset_inventory.get("rigged_skeletal_meshes", []))
    if not mesh_paths:
        raise LookupError("Hillside rigged skeletal mesh inventory is empty")
    if not animation_skeletons:
        raise LookupError("Hillside compatible animation skeleton inventory is empty")

    count = int(preset["skeletal_count"])
    preferred_motion = list(preset["animation_preferences"])
    skeletal_characters: list[dict[str, Any]] = []
    animation_bindings: list[dict[str, Any]] = []
    for index in range(count):
        mesh_path = mesh_paths[index % len(mesh_paths)]
        mesh_skeleton = mesh_skeletons.get(mesh_path, "")
        preference = preferred_motion[index % len(preferred_motion)]
        animation_path = _select_animation(animation_skeletons, mesh_skeleton, preference)
        animation_skeleton = animation_skeletons[animation_path]
        actor_name = f"CineU_{scene_key}_skeletal_{index:02d}"
        skeletal_characters.append(
            {
                "actor_name": actor_name,
                "mesh_path": mesh_path,
                "mesh_skeleton": mesh_skeleton,
                "source": "existing_skeletal_mesh",
            }
        )
        animation_bindings.append(
            {
                "actor_name": actor_name,
                "mesh_path": mesh_path,
                "animation_path": animation_path,
                "mesh_skeleton": mesh_skeleton,
                "animation_skeleton": animation_skeleton,
                "motion": _motion_label(animation_path),
            }
        )
    return skeletal_characters, animation_bindings


def _select_animation(animation_skeletons: dict[str, str], mesh_skeleton: str, preference: str) -> str:
    compatible = [path for path, skeleton in animation_skeletons.items() if skeleton == mesh_skeleton]
    if not compatible:
        raise LookupError(f"No compatible Hillside animation for skeleton: {mesh_skeleton}")
    lowered_preference = preference.lower()
    for path in compatible:
        if lowered_preference in path.lower():
            return path
    if lowered_preference == "phoning":
        for path in compatible:
            if "phone" in path.lower():
                return path
    if lowered_preference == "sitting":
        for path in compatible:
            if "sit" in path.lower():
                return path
    for path in compatible:
        if "walk" in path.lower():
            return path
    return compatible[0]


def _cycle_assets(paths: list[str], count: int) -> list[str]:
    if not paths:
        return []
    return [paths[index % len(paths)] for index in range(count)]


def _animation_mix(bindings: list[dict[str, Any]]) -> list[str]:
    return sorted({str(binding["motion"]) for binding in bindings})


def _motion_label(animation_path: str) -> str:
    text = animation_path.lower()
    if "phone" in text or "phoning" in text:
        return "phone"
    if "run" in text:
        return "running"
    if "walk" in text:
        return "walking"
    if "sit" in text:
        return "sitting"
    if "idle" in text:
        return "idle"
    return "animated"
