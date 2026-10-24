from __future__ import annotations

import ctypes
import hashlib
import json
import math
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import unreal


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)) or default)
    except ValueError:
        return float(default)


def _truthy_env_value(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _production_quality_mode_requested(mode: str, camera_filter: str = "") -> bool:
    text = f"{mode} {camera_filter}".strip().lower()
    return "production2k" in text or "final" in text or "cinematic30" in text or "_cinematic_" in text


def _default_mrq_sample_counts() -> tuple[int, int]:
    if _truthy_env_value(os.environ.get("CINEU_MRQ_LOW_MEMORY")):
        return (1, 1)
    quality = str(RENDER_QUALITY or "").strip().lower()
    if quality == "final":
        return (4, 8)
    if quality in {"cinematic", "film", "production", "high", "hq"} or _production_quality_mode_requested(MODE, CAMERA_FILTER):
        return (2, 8)
    return (1, 1)


def _env_int_or_default(name: str, default: int) -> int:
    value = os.environ.get(name, "").strip()
    if not value:
        return int(default)
    return max(1, int(value))


CINEU_REPO = str(Path(__file__).resolve().parents[2])
CINEU_PLUGIN_PYTHON = str(Path(CINEU_REPO) / "unreal_project/Plugins/CineUDemo/Content/Python")
if CINEU_PLUGIN_PYTHON not in sys.path:
    sys.path.insert(0, CINEU_PLUGIN_PYTHON)
if CINEU_REPO not in sys.path:
    sys.path.insert(0, CINEU_REPO)

from cineu_demo.asset_first_scene_plan import build_hillside_scene_plan  # noqa: E402
from cineu_render_ops import render_preview  # noqa: E402


DIAG_ROOT = Path(os.environ.get("CINEU_DIAGNOSTIC_ROOT", str(Path(CINEU_REPO) / "workspace/diagnostics/hillside_scene19_scene24")))
SUMMARY_PATH = DIAG_ROOT / "latest_build_render_summary.json"
LOCAL_ASSET_INDEX_PATH = Path(os.environ.get("CINEU_ASSET_INDEX", str(Path(CINEU_REPO) / "workspace/asset_index/local_asset_index.json")))
ASSET_ROOT = "/Game/CineU/HillsideScenes"
IN_PLACE_ANIMATION_ROOT = "/Game/CineU/InPlaceAnimations"
DOWNTOWN_WEST_SOURCE_LEVEL_CANDIDATES = [
    "/Game/Downtown_West/Maps/Demo_Environment",
    "/Game/DowntownWest/Maps/Demo_Environment",
    "/Game/DowntownCityPack/Maps/Demo_Environment",
    "/Game/DowntownWest/Maps/DowntownWest",
    "/Game/Downtown_West/Maps/Downtown_West",
    "/Game/PurePolygons_DowntownWest/Maps/DowntownWest",
    "/Game/PurePolygons/DowntownWest/Maps/DowntownWest",
    "/Game/DowntownWest/Maps/Overview",
    "/Game/Downtown_West/Maps/Overview",
]
DOWNTOWN_WEST_LEVEL_MATCH_GROUPS = [
    ["downtown", "west"],
    ["downtowncitypack"],
    ["downtown", "city", "pack"],
    ["purepolygons", "downtown"],
    ["purepolygonsdowntown"],
]
WORLD_TEMPLATE_6_7_SCENE_IDS = {"world_template_6_7_day"}
FPS = int(os.environ.get("CINEU_HILLSIDE_FPS", "24") or "24")
WIDTH = int(os.environ.get("CINEU_HILLSIDE_WIDTH", "1280") or "1280")
HEIGHT = int(os.environ.get("CINEU_HILLSIDE_HEIGHT", "720") or "720")
MODE = os.environ.get("CINEU_HILLSIDE_MODE", "preview").strip() or "preview"
SCENE_ID = os.environ.get("CINEU_HILLSIDE_SCENE", "scene19").strip() or "scene19"
DEFAULT_FRAME_COUNT = "1440" if SCENE_ID in {"scene19", "scene24"} else "144"
FRAME_COUNT = int(os.environ.get("CINEU_HILLSIDE_FRAME_COUNT", DEFAULT_FRAME_COUNT) or DEFAULT_FRAME_COUNT)
CAMERA_FILTER = os.environ.get("CINEU_HILLSIDE_CAMERA", "").strip()
RENDER_BACKEND = os.environ.get("CINEU_HILLSIDE_RENDER_BACKEND", "movie_render_pipeline").strip() or "movie_render_pipeline"
RENDER_QUALITY = os.environ.get("CINEU_HILLSIDE_RENDER_QUALITY", "final" if MODE == "final" else "cinematic").strip() or "cinematic"
EXECUTION_PHASE = os.environ.get("CINEU_HILLSIDE_EXECUTION_PHASE", "build_and_render").strip().lower() or "build_and_render"
DEBUG_ACTORS = os.environ.get("CINEU_HILLSIDE_DEBUG_ACTORS", "").strip().lower() in {"1", "true", "yes"}
CROWD_SOURCE_FILTER = os.environ.get("CINEU_HILLSIDE_CROWD_SOURCE_FILTER", "").strip()
DOWNTOWN_WEST_CITY_SAMPLE_MODULAR_ENABLED = (
    os.environ.get("CINEU_DOWNTOWN_WEST_CITY_SAMPLE_MODULAR", "").strip().lower() in {"1", "true", "yes", "on"}
    or "fab_city_sample_crowds_modular" in {source.strip() for source in CROWD_SOURCE_FILTER.split(",") if source.strip()}
)
EXTRA_RENDER_CVARS = [
    command.strip()
    for command in os.environ.get("CINEU_HILLSIDE_EXTRA_CVARS", "").replace(";", "\n").splitlines()
    if command.strip()
]
CITYPARK_ANIMATED_COUNT = max(1, int(os.environ.get("CINEU_CITYPARK_ANIMATED_COUNT", "28") or "28"))
CITYPARK_STATIC_COUNT = max(0, int(os.environ.get("CINEU_CITYPARK_STATIC_COUNT", "24") or "24"))
DOWNTOWN_WEST_SPAWN_SUPPORT_PROPS = os.environ.get("CINEU_DOWNTOWN_WEST_SPAWN_SUPPORT_PROPS", "1").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
DOWNTOWN_WEST_STREET_PROP_ROLES = {
    "storefront_awning",
    "storefront_sign",
    "storefront_poster",
    "sidewalk_sign",
    "cafe_table",
    "cafe_chair",
    "cafe_umbrella",
    "street_vendor",
    "bench",
    "poster_stand",
    "poster_pillar",
    "streetlight",
    "traffic_light",
    "road_sign",
    "street_bin",
    "planter",
}
PEDESTRIAN_SLOT_MATERIAL_FALLBACK_DEFAULT = "0"
PEDESTRIAN_SLOT_MATERIAL_FALLBACK = os.environ.get(
    "CINEU_PEDESTRIAN_SLOT_MATERIAL_FALLBACK",
    PEDESTRIAN_SLOT_MATERIAL_FALLBACK_DEFAULT,
).strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
PEDESTRIAN_SLOT_MATERIAL_FALLBACK_SOURCES = {
    "fab_aria_blake_game_ready",
    "fab_modern_male_full_complete",
    "fab_free_casual_girl_complete",
    "fab_scanned_3d_people_pack",
}
CITY_SAMPLE_CROWD_BLUEPRINTS_ENABLED = os.environ.get("CINEU_CITY_SAMPLE_CROWD_BLUEPRINTS", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
DEFAULT_ASSET_READY_WAIT_SEC = 14.0 if RENDER_BACKEND in {"scene_capture_sequence", "scene_capture_movie", "sync_scene_capture"} else 4.0
ASSET_READY_WAIT_SEC = max(0.0, _env_float("CINEU_HILLSIDE_ASSET_READY_WAIT_SEC", DEFAULT_ASSET_READY_WAIT_SEC))


def _capture_frame_range() -> tuple[int, int]:
    last_start = max(0, FRAME_COUNT - 1)
    start = max(0, min(last_start, int(os.environ.get("CINEU_HILLSIDE_CAPTURE_START_FRAME", "0") or "0")))
    end = int(os.environ.get("CINEU_HILLSIDE_CAPTURE_END_FRAME", str(FRAME_COUNT)) or str(FRAME_COUNT))
    end = max(start + 1, min(FRAME_COUNT, end))
    return start, end


def _keep_spawnable_source_actors_for_render_backend() -> bool:
    backend = str(RENDER_BACKEND or "").strip().lower()
    return backend in {"scene_capture_sequence", "scene_capture_movie", "sync_scene_capture"}


def _native_windows_path(path: Path) -> str:
    text = str(path)
    if os.name != "nt" or text.startswith("\\\\?\\"):
        return text
    if len(text) >= 248 and len(text) >= 3 and text[1:3] == ":\\":
        return "\\\\?\\" + text
    return text


def _mkdir(path: Path) -> None:
    os.makedirs(_native_windows_path(path), exist_ok=True)


def _write_text(path: Path, text: str) -> None:
    _mkdir(path.parent)
    with open(_native_windows_path(path), "w", encoding="utf-8") as handle:
        handle.write(text)


def _read_json(path: Path) -> dict:
    with open(_native_windows_path(path), "r", encoding="utf-8") as handle:
        return json.load(handle)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(_native_windows_path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _production_cold_reload_verified(
    writer_process_id: int,
    auditor_process_id: int,
    audit_passed: bool,
    written_script_sha256: str,
    audited_script_sha256: str,
) -> bool:
    return bool(
        int(writer_process_id) > 0
        and int(auditor_process_id) > 0
        and int(writer_process_id) != int(auditor_process_id)
        and audit_passed
        and written_script_sha256
        and written_script_sha256 == audited_script_sha256
    )


def _compact_token(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def _asset_text_matches_groups(text: str, match_groups: list[list[str]]) -> bool:
    compact_text = _compact_token(text)
    for group in match_groups:
        if all(token.lower() in text or _compact_token(token) in compact_text for token in group):
            return True
    return False


def _level_asset_score(asset: dict) -> tuple[int, str]:
    text = " ".join(str(asset.get(key, "")) for key in ("name", "ue_path", "source_path", "asset_id")).lower()
    compact = _compact_token(text)
    score = 0
    if "cityparkenv55" in compact:
        score += 100
    if "maps" in compact:
        score += 20
    if "demoenvironment" in compact:
        score += 140
    if "assetshowcase" in compact:
        score -= 120
    if "showcase" in compact:
        score += 80
    if "main" in compact or "demo" in compact or "scene" in compact:
        score += 45
    if "overview" in compact:
        score -= 35
    return score, str(asset.get("ue_path") or "")


def _resolve_level_from_asset_index(candidates: list[str], match_groups: list[list[str]]) -> str:
    if not LOCAL_ASSET_INDEX_PATH.exists():
        return candidates[0]
    try:
        index = json.loads(LOCAL_ASSET_INDEX_PATH.read_text(encoding="utf-8"))
    except Exception:
        return candidates[0]
    assets = index.get("assets") or []
    if isinstance(assets, dict):
        assets = list(assets.values())
    matches = []
    for asset in assets:
        if str(asset.get("type", "")).lower() != "level":
            continue
        text = " ".join(
            str(asset.get(key, ""))
            for key in ("name", "ue_path", "source_path", "asset_id")
        ).lower()
        if _asset_text_matches_groups(text, match_groups):
            ue_path = str(asset.get("ue_path") or "")
            if ue_path:
                matches.append(asset)
    if matches:
        return max(matches, key=_level_asset_score)["ue_path"]
    return candidates[0]


MAN_MESHES = [
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/AdrianCity/SK_AdrianCity",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/AlexCity/SK_AlexCity",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/AmirCity/SK_AmirCity",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/DorianCity/SK_DorianCity",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_reworked/LouisPrice/SK_LouisPrice",
]
MAN_ANIMS = [
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_common/animations/man/AN_man_walking01",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_common/animations/man/AN_man_walking02",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_common/animations/man/AN_man_walk_phoning01",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_common/animations/man/AN_man_idle_phoning01",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_common/animations/man/AN_man_idle_sitting01",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_common/animations/man/AN_man_sport_running01",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_common/animations/man/AN_man_idle_sitting_phone01",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_common/animations/man/AN_man_idle_speaking03",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_common/animations/man/AN_man_walk_bag01",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_common/animations/man/AN_man_walk_suitcase01",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_common/animations/man/AN_man_walk_umbrella01",
]
WOMAN_MESHES = [
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/SanaaCity/SK_SanaaCity",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/IsabelCity/SK_IsabelCity",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_reworked/AsmaCity/SK_AsmaCity",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_reworked/IsabelCity/SK_IsabelCity",
]
WOMAN_ANIMS = [
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_common/animations/womanheels/AN_womanheels_walking01",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_common/animations/womanheels/AN_womanheels_walking02",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_common/animations/womanheels/AN_womanheels_idle01",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_common/animations/womanheels/AN_womanheels_idle_phoning01",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_common/animations/womanheels/AN_womanheels_idle02",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_common/animations/womanheels/AN_womanheels_idle_umbrella01",
]
METAHUMAN_KELLAN_PARTS = [
    ("body", "/Game/MetaHumans/Kellan/Male/Medium/NormalWeight/Body/m_med_nrw_body"),
    ("face", "/Game/MetaHumans/Kellan/Face/Kellan_FaceMesh"),
    ("top", "/Game/MetaHumans/Common/Male/Medium/NormalWeight/Tops/Hoodie/Meshes/m_med_nrw_top_hoodie_nrm_High"),
    ("pants", "/Game/MetaHumans/Common/Male/Medium/NormalWeight/Bottoms/Cargopants/m_med_nrw_btm_cargopants_High"),
    ("shoes", "/Game/MetaHumans/Common/Male/Medium/NormalWeight/Shoes/RunningShoes/m_med_nrw_shs_runningshoes_High"),
]
METAHUMAN_KELLAN_BLUEPRINT = "/Game/Blueprints/RetargetedCharacters/CBP_SandboxCharacter_Metahuman_Kellan"
ARIA_BLAKE_MESH = "/Game/AriaBlake/Meshes/SKM_Ariablake"
ARIA_BLAKE_ANIMS = {
    "idle": "/Game/AriaBlake/Demo/Animation/AS_MF_Idle",
    "walk": "/Game/AriaBlake/Demo/Animation/AS_MF_Walk_Fwd",
    "run": "/Game/AriaBlake/Demo/Animation/AS_MF_Run_Fwd",
}
BANDIT_MESH = "/Game/Bandit/Mesh/BanditUnreal"
BANDIT_MESHES = [
    "/Game/Bandit/Mesh/BanditUnreal",
    "/Game/Bandit/Skins/BanditMaskUp",
    "/Game/Bandit/Skins/BanditMaskUpNoGun",
    "/Game/Bandit/Skins/BanditNoGun",
]
BANDIT_ANIMS = {
    "idle": "/Game/Bandit/Animations/ThirdPersonIdle",
    "walk": "/Game/Bandit/Animations/ThirdPersonWalk",
    "run": "/Game/Bandit/Animations/ThirdPersonRun",
}
CITYPARK_MAN_MESHES = [
    "/Game/Man/Mesh/Full/SK_Man_Full_01",
    "/Game/Man/Mesh/Full/SK_Man_Full_02",
    "/Game/Man/Mesh/Full/SK_Man_Full_03",
    "/Game/Man/Mesh/Full/SK_Man_Full_04",
]
CITYPARK_CLOTHED_MAN_MESHES = [CITYPARK_MAN_MESHES[2], CITYPARK_MAN_MESHES[3]]
CITYPARK_MAN_ANIMS = {
    "idle": "/Game/Man/Demo/Animations/ThirdPersonIdle",
    "walk": "/Game/Man/Demo/Animations/ThirdPersonWalk",
    "run": "/Game/Man/Demo/Animations/ThirdPersonRun",
}
FREE_CASUAL_GIRL_LEGACY_MODULAR_SOURCE = "fab_free_casual_girl_modular"
FREE_CASUAL_GIRL_SOURCE = "fab_free_casual_girl_complete"
FREE_CASUAL_GIRL_MESH = "/Game/Sample/Meshes/SK_Complete"
FREE_CASUAL_GIRL_ANIMS = {
    "idle": "/Game/Sample/Demo/ThirdPersonTemplate/Characters/Mannequins/Animations/Quinn/MF_Idle",
    "walk": "/Game/Sample/Demo/ThirdPersonTemplate/Characters/Mannequins/Animations/Quinn/MF_Walk_Fwd",
    "run": "/Game/Sample/Demo/ThirdPersonTemplate/Characters/Mannequins/Animations/Quinn/MF_Run_Fwd",
}
FREE_CASUAL_GIRL_PARTS = [
    ("top", "/Game/Sample/Meshes/SK_Top_1"),
    ("pants", "/Game/Sample/Meshes/SK_Pants"),
    ("shoes", "/Game/Sample/Meshes/SK_Shoes"),
    ("hair", "/Game/Sample/Meshes/SK_Hair_1"),
]
FREE_CASUAL_GIRL_VARIANTS = [
    FREE_CASUAL_GIRL_PARTS,
    [
        ("top", "/Game/Sample/Meshes/SK_Top_2"),
        ("pants", "/Game/Sample/Meshes/SK_Pants"),
        ("shoes", "/Game/Sample/Meshes/SK_Shoes_Socks"),
        ("hair", "/Game/Sample/Meshes/SK_Hair_2"),
    ],
    [
        ("top", "/Game/Sample/Meshes/SK_Top_3"),
        ("pants", "/Game/Sample/Meshes/SK_Shorts"),
        ("shoes", "/Game/Sample/Meshes/SK_Shoes"),
        ("hair", "/Game/Sample/Meshes/SK_Hair_1"),
    ],
    [
        ("top", "/Game/Sample/Meshes/SK_Top_4"),
        ("pants", "/Game/Sample/Meshes/SK_Pants"),
        ("shoes", "/Game/Sample/Meshes/SK_Shoes_Socks"),
        ("hair", "/Game/Sample/Meshes/SK_Hair_2"),
    ],
]
CITY_SAMPLE_CROWD_ANIMS = {
    "male_walk_in_place": "/Game/CitySampleCrowd/Character/Anims/Loco/MTN_Set/MTN_N_WalkInPlace",
    "male_idle": "/Game/CitySampleCrowd/Character/Anims/Loco/MTN_Set/MTN_N_Idle",
    "male_walk_a": "/Game/CitySampleCrowd/Character/Anims/Loco/MTN_Set/MTN_N_Walk_F_VarB",
    "male_walk_b": "/Game/CitySampleCrowd/Character/Anims/Loco/MTN_Set/MTN_N_Walk_F_VarE",
    "male_phone": "/Game/CitySampleCrowd/Character/Anims/Loco/MTN_Set/MTN_Phone_Talk_A",
    "female_walk_a": "/Game/CitySampleCrowd/Character/Anims/Loco/FTN_Set/FTN_N_Walk_F",
    "female_walk_b": "/Game/CitySampleCrowd/Character/Anims/Loco/FTN_Set/FTN_N_Walk_F_VarB",
    "female_phone": "/Game/CitySampleCrowd/Character/Anims/Loco/FTN_Set/FTN_CellPhoneIdle_1",
    "female_over_walk": "/Game/CitySampleCrowd/Character/Anims/Loco/FTO_Set/FTO_N_Walk_F",
    "female_over_phone": "/Game/CitySampleCrowd/Character/Anims/Loco/FTO_Set/FTO_CellPhoneIdle_1",
    "female_under_walk": "/Game/CitySampleCrowd/Character/Anims/Loco/FTU_Set/FTU_N_Walk_F",
    "female_under_phone": "/Game/CitySampleCrowd/Character/Anims/Loco/FTU_Set/FTU_CellPhoneIdle_1",
}
CITY_SAMPLE_CROWD_BLUEPRINT = "/Game/CitySampleCrowd/Blueprints/BP_CrowdCharacter"
CITY_SAMPLE_CROWD_VARIANTS = [
    {
        "host": "/Game/CitySampleCrowd/Character/Male/NormalWeight/Meshes/m_tal_nrw_body",
        "parts": [
            ("face", "/Game/CitySampleCrowd/Character/Male/m_001/Face/m_001_nrw_FaceMesh"),
            ("top", "/Game/CitySampleCrowd/Character/Male/NormalWeight/Meshes/m_tal_nrw_buttonDown"),
            ("pants", "/Game/CitySampleCrowd/Character/Male/NormalWeight/Meshes/m_tal_nrw_jeans"),
            ("shoes", "/Game/CitySampleCrowd/Character/Male/NormalWeight/Meshes/m_tal_nrw_loafers"),
        ],
    },
    {
        "host": "/Game/CitySampleCrowd/Character/Female/NormalWeight/Meshes/f_tal_nrw_body",
        "parts": [
            ("face", "/Game/CitySampleCrowd/Character/Female/f_001/Face/f_001_nrw_FaceMesh"),
            ("top", "/Game/CitySampleCrowd/Character/Female/NormalWeight/Meshes/f_tal_nrw_buttonOpen"),
            ("pants", "/Game/CitySampleCrowd/Character/Female/NormalWeight/Meshes/f_tal_nrw_jeans"),
            ("shoes", "/Game/CitySampleCrowd/Character/Female/NormalWeight/Meshes/f_tal_nrw_loafers"),
        ],
    },
    {
        "host": "/Game/CitySampleCrowd/Character/Male/NormalWeight/Meshes/m_tal_nrw_body",
        "parts": [
            ("face", "/Game/CitySampleCrowd/Character/Male/m_004/Face/m_004_nrw_FaceMesh"),
            ("top", "/Game/CitySampleCrowd/Character/Male/NormalWeight/Meshes/m_tal_nrw_turtleneck_blazer"),
            ("pants", "/Game/CitySampleCrowd/Character/Male/NormalWeight/Meshes/m_tal_nrw_slacks"),
            ("shoes", "/Game/CitySampleCrowd/Character/Male/NormalWeight/Meshes/m_tal_nrw_oxfords"),
        ],
    },
    {
        "host": "/Game/CitySampleCrowd/Character/Female/NormalWeight/Meshes/f_tal_nrw_body",
        "parts": [
            ("face", "/Game/CitySampleCrowd/Character/Female/f_004/Face/f_004_nrw_FaceMesh"),
            ("top", "/Game/CitySampleCrowd/Character/Female/NormalWeight/Meshes/f_tal_nrw_scoopneck_blazer"),
            ("pants", "/Game/CitySampleCrowd/Character/Female/NormalWeight/Meshes/f_tal_nrw_slacks"),
            ("shoes", "/Game/CitySampleCrowd/Character/Female/NormalWeight/Meshes/f_tal_nrw_oxfords"),
        ],
    },
    {
        "host": "/Game/CitySampleCrowd/Character/Female/NormalWeight/Meshes/f_tal_nrw_body",
        "parts": [
            ("face", "/Game/CitySampleCrowd/Character/Female/f_002/Face/f_002_nrw_FaceMesh"),
            ("top", "/Game/CitySampleCrowd/Character/Female/NormalWeight/Meshes/f_tal_nrw_buttonDown_blazer"),
            ("pants", "/Game/CitySampleCrowd/Character/Female/NormalWeight/Meshes/f_tal_nrw_jeans_belt"),
            ("shoes", "/Game/CitySampleCrowd/Character/Female/NormalWeight/Meshes/f_tal_nrw_dressFlats"),
        ],
    },
    {
        "host": "/Game/CitySampleCrowd/Character/Female/OverWeight/Meshes/f_tal_ovw_body",
        "parts": [
            ("face", "/Game/CitySampleCrowd/Character/Female/f_005/Face/f_005_nrw_FaceMesh"),
            ("top", "/Game/CitySampleCrowd/Character/Female/OverWeight/Meshes/f_tal_ovw_turtleneck_blazer"),
            ("pants", "/Game/CitySampleCrowd/Character/Female/OverWeight/Meshes/f_tal_ovw_slacks_belt"),
            ("shoes", "/Game/CitySampleCrowd/Character/Female/OverWeight/Meshes/f_tal_ovw_oxfords"),
        ],
    },
    {
        "host": "/Game/CitySampleCrowd/Character/Female/UnderWeight/Meshes/f_tal_unw_body",
        "parts": [
            ("face", "/Game/CitySampleCrowd/Character/Female/f_006/Face/f_006_nrw_FaceMesh"),
            ("top", "/Game/CitySampleCrowd/Character/Female/UnderWeight/Meshes/f_tal_unw_scoopneck_croppedJacket"),
            ("pants", "/Game/CitySampleCrowd/Character/Female/UnderWeight/Meshes/f_tal_unw_jeans"),
            ("shoes", "/Game/CitySampleCrowd/Character/Female/UnderWeight/Meshes/f_tal_unw_loafers"),
        ],
    },
    {
        "host": "/Game/CitySampleCrowd/Character/Male/NormalWeight/Meshes/m_tal_nrw_body",
        "parts": [
            ("face", "/Game/CitySampleCrowd/Character/Male/m_002/Face/m_002_nrw_FaceMesh"),
            ("top", "/Game/CitySampleCrowd/Character/Male/NormalWeight/Meshes/m_tal_nrw_buttonOpen_blazer"),
            ("pants", "/Game/CitySampleCrowd/Character/Male/NormalWeight/Meshes/m_tal_nrw_jeansLong_belt"),
            ("shoes", "/Game/CitySampleCrowd/Character/Male/NormalWeight/Meshes/m_tal_nrw_loafers"),
        ],
    },
    {
        "host": "/Game/CitySampleCrowd/Character/Male/NormalWeight/Meshes/m_tal_nrw_body",
        "parts": [
            ("face", "/Game/CitySampleCrowd/Character/Male/m_003/Face/m_003_nrw_FaceMesh"),
            ("top", "/Game/CitySampleCrowd/Character/Male/NormalWeight/Meshes/m_tal_nrw_buttonDown_tie_vest"),
            ("pants", "/Game/CitySampleCrowd/Character/Male/NormalWeight/Meshes/m_tal_nrw_slacks_belt"),
            ("shoes", "/Game/CitySampleCrowd/Character/Male/NormalWeight/Meshes/m_tal_nrw_oxfords"),
        ],
    },
    {
        "host": "/Game/CitySampleCrowd/Character/Male/NormalWeight/Meshes/m_tal_nrw_body",
        "parts": [
            ("face", "/Game/CitySampleCrowd/Character/Male/m_005/Face/m_005_nrw_FaceMesh"),
            ("top", "/Game/CitySampleCrowd/Character/Male/NormalWeight/Meshes/m_tal_nrw_crewneck_blazer"),
            ("pants", "/Game/CitySampleCrowd/Character/Male/NormalWeight/Meshes/m_tal_nrw_jeans_belt"),
            ("shoes", "/Game/CitySampleCrowd/Character/Male/NormalWeight/Meshes/m_tal_nrw_loafers"),
        ],
    },
    {
        "host": "/Game/CitySampleCrowd/Character/Male/NormalWeight/Meshes/m_tal_nrw_body",
        "parts": [
            ("face", "/Game/CitySampleCrowd/Character/Male/m_006/Face/m_006_nrw_FaceMesh"),
            ("top", "/Game/CitySampleCrowd/Character/Male/NormalWeight/Meshes/m_tal_nrw_turtleneck"),
            ("pants", "/Game/CitySampleCrowd/Character/Male/NormalWeight/Meshes/m_tal_nrw_jeansLong"),
            ("shoes", "/Game/CitySampleCrowd/Character/Male/NormalWeight/Meshes/m_tal_nrw_oxfords"),
        ],
    },
    {
        "host": "/Game/CitySampleCrowd/Character/Male/NormalWeight/Meshes/m_tal_nrw_body",
        "parts": [
            ("face", "/Game/CitySampleCrowd/Character/Male/m_001/Face/m_001_nrw_FaceMesh"),
            ("top", "/Game/CitySampleCrowd/Character/Male/NormalWeight/Meshes/m_tal_nrw_buttonDown_tie_blazer"),
            ("pants", "/Game/CitySampleCrowd/Character/Male/NormalWeight/Meshes/m_tal_nrw_slacks"),
            ("shoes", "/Game/CitySampleCrowd/Character/Male/NormalWeight/Meshes/m_tal_nrw_oxfords"),
        ],
    },
]
UNVALIDATED_MODULAR_CHARACTER_SOURCES = {
    FREE_CASUAL_GIRL_LEGACY_MODULAR_SOURCE,
    "fab_city_sample_crowds_modular",
}
FORMAL_VERIFIED_MOVING_CHARACTER_SOURCES = {
    "fab_scanned_3d_people_pack",
    "fab_aria_blake_game_ready",
}
FORMAL_COMPLETE_CHARACTER_ONLY_SCENES = {
    "museum_gallery_day",
    "museum_gallery_night",
    "art_gallery_day",
    "citypark_promenade_day",
    "citypark_promenade_night",
    "warehouse_day",
    "car_dealer_showcase_day",
    "downtown_west_day",
    "downtown_west_evening",
    "world_template_6_7_day",
}
SCANNED_3D_PEOPLE_MESHES = [
    "/Game/Scanned3DPeoplePack/RP_Character/rp_carla_rigged_001_ue4/rp_carla_rigged_001_ue4",
    "/Game/Scanned3DPeoplePack/RP_Character/rp_claudia_rigged_002_ue4/rp_claudia_rigged_002_ue4",
    "/Game/Scanned3DPeoplePack/RP_Character/rp_eric_rigged_001_ue4/rp_eric_rigged_001_ue4",
    "/Game/Scanned3DPeoplePack/RP_Character/rp_manuel_rigged_001_ue4/rp_manuel_rigged_001_ue4",
    "/Game/Scanned3DPeoplePack/RP_Character/rp_nathan_rigged_003_ue4/rp_nathan_rigged_003_ue4",
    "/Game/Scanned3DPeoplePack/RP_Character/rp_sophia_rigged_003_ue4/rp_sophia_rigged_003_ue4",
]
SCANNED_3D_PEOPLE_POSED_STATIC_MESHES = [
    "/Game/Scanned3DPeoplePack/RP_Character/rp_dennis_posed_004_ue4/rp_dennis_posed_004",
    "/Game/Scanned3DPeoplePack/RP_Character/rp_fabienne_percy_posed_001_ue4/rp_fabienne_percy_posed_001",
    "/Game/Scanned3DPeoplePack/RP_Character/rp_mei_posed_001_ue4/rp_mei_posed_001",
]
SCANNED_3D_PEOPLE_ANIMS = {
    "walk": "/Game/Scanned3DPeoplePack/RP_Character/00_Animations/rp_nathan_animated_003_walking_ue4",
    "idle": "/Game/Scanned3DPeoplePack/RP_Character/00_Animations/rp_sophia_animated_003_idling_ue4",
    "dance": "/Game/Scanned3DPeoplePack/RP_Character/00_Animations/rp_manuel_animated_001_dancing_ue4",
}
SCANNED_3D_PEOPLE_RETARGETED_ANIMS = {
    "nathan_phone_talk": "/Game/CineU/RetargetedAnimations/Canary/CineU_MTN_Phone_Talk_A_UE4_Canary",
    "male_walk_b": "/Game/CineU/RetargetedAnimations/PedestrianActions/CineU_MTN_N_Walk_F_VarB_UE4",
    "male_walk_e": "/Game/CineU/RetargetedAnimations/PedestrianActions/CineU_MTN_N_Walk_F_VarE_UE4",
    "male_walk_f": "/Game/CineU/RetargetedAnimations/PedestrianActions/CineU_MTN_N_Walk_F_VarF_UE4",
    "female_walk": "/Game/CineU/RetargetedAnimations/PedestrianActions/CineU_FTN_N_Walk_F_UE4",
    "female_walk_a": "/Game/CineU/RetargetedAnimations/PedestrianActions/CineU_FTN_N_Walk_F_VarA_UE4",
    "female_walk_b": "/Game/CineU/RetargetedAnimations/PedestrianActions/CineU_FTN_N_Walk_F_VarB_UE4",
    "male_idle_b": "/Game/CineU/RetargetedAnimations/PedestrianActions/CineU_MTN_N_Idle_B_UE4",
    "male_idle_c": "/Game/CineU/RetargetedAnimations/PedestrianActions/CineU_MTN_N_Idle_C_UE4",
    "male_idle_d": "/Game/CineU/RetargetedAnimations/PedestrianActions/CineU_MTN_N_Idle_D_UE4",
    "male_idle_e": "/Game/CineU/RetargetedAnimations/PedestrianActions/CineU_MTN_N_Idle_E_UE4",
    "female_idle_a": "/Game/CineU/RetargetedAnimations/PedestrianActions/CineU_FTN_N_Idle_VarA_UE4",
    "female_idle_b": "/Game/CineU/RetargetedAnimations/PedestrianActions/CineU_FTN_N_Idle_VarB_UE4",
    "female_idle_c": "/Game/CineU/RetargetedAnimations/PedestrianActions/CineU_FTN_N_Idle_VarC_UE4",
    "female_idle_d": "/Game/CineU/RetargetedAnimations/PedestrianActions/CineU_FTN_N_Idle_VarD_UE4",
    "male_phone_look": "/Game/CineU/RetargetedAnimations/PedestrianActions/CineU_MTN_Phone_LookAt_A_UE4",
    "female_phone_idle": "/Game/CineU/RetargetedAnimations/PedestrianActions/CineU_FTN_CellPhoneIdle_1_UE4",
}
SCANNED_3D_PEOPLE_RETARGETED_WALKS = [
    SCANNED_3D_PEOPLE_RETARGETED_ANIMS[key]
    for key in ("male_walk_b", "male_walk_e", "male_walk_f", "female_walk", "female_walk_a", "female_walk_b")
]
SCANNED_3D_PEOPLE_RETARGETED_IDLES = [
    SCANNED_3D_PEOPLE_RETARGETED_ANIMS[key]
    for key in (
        "male_idle_b",
        "male_idle_c",
        "male_idle_d",
        "male_idle_e",
        "female_idle_a",
        "female_idle_b",
        "female_idle_c",
        "female_idle_d",
    )
]
SCANNED_3D_PEOPLE_RETARGETED_PHONE_ACTIONS = [
    SCANNED_3D_PEOPLE_RETARGETED_ANIMS[key]
    for key in ("nathan_phone_talk", "male_phone_look", "female_phone_idle")
]
STATIC_PEOPLE = [
    "/Game/ExternalAssets/Twinmotion/Characters/readyposed/Meshes/Child06/SM_Child06",
    "/Game/ExternalAssets/Twinmotion/Characters/readyposed/Meshes/Child07/SM_Child07",
    "/Game/ExternalAssets/Twinmotion/Characters/readyposed/Meshes/Child32/SM_Child32",
    "/Game/ExternalAssets/Twinmotion/Characters/readyposed/Meshes/Child35/SM_Child35",
    "/Game/ExternalAssets/Twinmotion/Characters/readyposed/Meshes/Child37/SM_Child37",
    "/Game/ExternalAssets/Twinmotion/Characters/readyposed/Meshes/Child40/SM_Child40",
    "/Game/ExternalAssets/Twinmotion/Characters/readyposed/Meshes/Couple02/SM_Couple02",
    "/Game/ExternalAssets/Twinmotion/Characters/readyposed/Meshes/Couple03/SM_Couple03",
    "/Game/ExternalAssets/Twinmotion/Characters/readyposed/Meshes/Couple04/SM_Couple04",
    "/Game/ExternalAssets/Twinmotion/Characters/readyposed/Meshes/Couple05/SM_Couple05",
    "/Game/ExternalAssets/Twinmotion/Characters/readyposed/Meshes/Couple15/SM_Couple15",
    "/Game/ExternalAssets/Twinmotion/Characters/readyposed/Meshes/Couple48/SM_Couple48",
    "/Game/ExternalAssets/Twinmotion/Characters/readyposed/Meshes/Man03/SM_Man03",
    "/Game/ExternalAssets/Twinmotion/Characters/readyposed/Meshes/Man19/SM_Man19",
    "/Game/ExternalAssets/Twinmotion/Characters/readyposed/Meshes/Man23/SM_Man23",
    "/Game/ExternalAssets/Twinmotion/Characters/readyposed/Meshes/Man43/SM_Man43",
    "/Game/ExternalAssets/Twinmotion/Characters/readyposed/Meshes/Man56/SM_Man56",
    "/Game/ExternalAssets/Twinmotion/Characters/readyposed/Meshes/Man60/SM_Man60",
    "/Game/ExternalAssets/Twinmotion/Characters/readyposed/Meshes/Woman01/SM_Woman01",
    "/Game/ExternalAssets/Twinmotion/Characters/readyposed/Meshes/Woman02/SM_Woman02",
    "/Game/ExternalAssets/Twinmotion/Characters/readyposed/Meshes/Woman205/SM_Woman205",
    "/Game/ExternalAssets/Twinmotion/Characters/readyposed/Meshes/Woman26/SM_Woman26",
    "/Game/ExternalAssets/Twinmotion/Characters/readyposed/Meshes/Woman32/SM_Woman32",
    "/Game/ExternalAssets/Twinmotion/Characters/readyposed/Meshes/Woman37/SM_Woman37",
]


def _is_downtown_west_scene(scene_id: str) -> bool:
    return scene_id in {"downtown_west_day", "downtown_west_evening"} or scene_id in WORLD_TEMPLATE_6_7_SCENE_IDS


DOWNTOWN_WEST_NATIVE_Y_OFFSET = -4700.0


def _downtown_west_native_location(point: list[float]) -> list[float]:
    location = list(point)
    if len(location) >= 2:
        location[1] = float(location[1]) + DOWNTOWN_WEST_NATIVE_Y_OFFSET
    return location


def _world_template_6_7_native_location(point: list[float]) -> list[float]:
    return _downtown_west_native_location(point)


def _downtown_west_native_routes(routes: list[tuple[list[float], list[float]]]) -> list[tuple[list[float], list[float]]]:
    return [(_downtown_west_native_location(start), _downtown_west_native_location(end)) for start, end in routes]


def _world_template_6_7_native_routes(routes: list[tuple[list[float], list[float]]]) -> list[tuple[list[float], list[float]]]:
    return [(_world_template_6_7_native_location(start), _world_template_6_7_native_location(end)) for start, end in routes]


def _downtown_west_native_support_props(props: list[dict]) -> list[dict]:
    if not DOWNTOWN_WEST_SPAWN_SUPPORT_PROPS:
        return []
    shifted = []
    for prop in props:
        if str(prop.get("role", "")) not in DOWNTOWN_WEST_STREET_PROP_ROLES:
            continue
        item = dict(prop)
        item["location"] = _downtown_west_native_location(list(prop["location"]))
        shifted.append(item)
    return shifted


def _downtown_west_reference_support_props(props: list[dict]) -> list[dict]:
    if not DOWNTOWN_WEST_SPAWN_SUPPORT_PROPS:
        return []
    shifted = []
    for prop in props:
        item = dict(prop)
        item["location"] = _downtown_west_native_location(list(prop["location"]))
        shifted.append(item)
    return shifted


def _world_template_6_7_support_props(props: list[dict]) -> list[dict]:
    if not DOWNTOWN_WEST_SPAWN_SUPPORT_PROPS:
        return []
    shifted = []
    for prop in props:
        item = dict(prop)
        item["location"] = _world_template_6_7_native_location(list(prop["location"]))
        shifted.append(item)
    return shifted


def _v(values: list[float]) -> unreal.Vector:
    return unreal.Vector(float(values[0]), float(values[1]), float(values[2]))


def _r(values: list[float]) -> unreal.Rotator:
    pitch, yaw, roll = [float(v) for v in values]
    return unreal.Rotator(pitch, yaw, roll)


def _look_at_rotation(source: list[float], target: list[float]) -> list[float]:
    dx = float(target[0]) - float(source[0])
    dy = float(target[1]) - float(source[1])
    dz = float(target[2]) - float(source[2])
    yaw = math.degrees(math.atan2(dy, dx))
    horizontal = math.sqrt(dx * dx + dy * dy)
    pitch = math.degrees(math.atan2(dz, horizontal))
    return [pitch, yaw, 0.0]


def _movement_rotation(start: list[float], end: list[float]) -> list[float]:
    return [0.0, math.degrees(math.atan2(end[1] - start[1], end[0] - start[0])), 0.0]


def _xy_distance(start: list[float], end: list[float]) -> float:
    return math.hypot(float(end[0]) - float(start[0]), float(end[1]) - float(start[1]))


def _spacing_samples(count: int = 21) -> tuple[float, ...]:
    sample_count = max(2, int(count))
    return tuple(index / float(sample_count - 1) for index in range(sample_count))


def _xy_at(start: list[float], end: list[float], t: float) -> tuple[float, float]:
    return (
        float(start[0]) + (float(end[0]) - float(start[0])) * t,
        float(start[1]) + (float(end[1]) - float(start[1])) * t,
    )


def _xy_at_route(points: list[list[float]], t: float) -> tuple[float, float]:
    if len(points) < 2:
        point = points[0]
        return (float(point[0]), float(point[1]))
    segments: list[tuple[list[float], list[float], float]] = []
    total_distance = 0.0
    for left, right in zip(points, points[1:]):
        distance = _xy_distance(left, right)
        segments.append((left, right, distance))
        total_distance += distance
    if total_distance <= 0.0:
        point = points[0]
        return (float(point[0]), float(point[1]))
    target_distance = max(0.0, min(1.0, float(t))) * total_distance
    travelled = 0.0
    for left, right, distance in segments:
        if distance <= 0.0:
            continue
        if travelled + distance >= target_distance:
            return _xy_at(left, right, (target_distance - travelled) / distance)
        travelled += distance
    point = points[-1]
    return (float(point[0]), float(point[1]))


def _route_clearance_against_people(start: list[float], end: list[float], people: list[dict], samples: tuple[float, ...] | None = None) -> float:
    samples = samples or _spacing_samples()
    min_distance = float("inf")
    for other in people:
        other_start = other["start"]
        other_end = other["end"]
        other_points = other.get("waypoints") or [other_start, other_end]
        for t in samples:
            left = _xy_at_route([start, end], t)
            right = _xy_at_route(other_points, t)
            min_distance = min(min_distance, math.hypot(left[0] - right[0], left[1] - right[1]))
    return min_distance if min_distance != float("inf") else float("inf")


def _route_spatial_clearance_against_people(start: list[float], end: list[float], people: list[dict], samples: tuple[float, ...] | None = None) -> float:
    samples = samples or _spacing_samples()
    candidate_points = [_xy_at_route([start, end], t) for t in samples]
    min_distance = float("inf")
    for other in people:
        other_points = other.get("waypoints") or [other["start"], other["end"]]
        sampled_other_points = [_xy_at_route(other_points, t) for t in samples]
        for left in candidate_points:
            for right in sampled_other_points:
                min_distance = min(min_distance, math.hypot(left[0] - right[0], left[1] - right[1]))
    return min_distance if min_distance != float("inf") else float("inf")


def _route_offset_candidates(start: list[float], end: list[float]) -> list[tuple[float, float]]:
    dx = float(end[0]) - float(start[0])
    dy = float(end[1]) - float(start[1])
    length = math.hypot(dx, dy)
    if length <= 1e-6:
        offsets = [0.0, 120.0, -120.0, 220.0, -220.0, 360.0, -360.0, 520.0, -520.0, 600.0, -600.0]
        candidates = [(x_offset, y_offset) for x_offset in offsets for y_offset in offsets]
        return sorted(candidates, key=lambda item: (abs(item[0]) + abs(item[1]), abs(item[0]), abs(item[1])))
    forward = (dx / length, dy / length)
    normal = (-forward[1], forward[0])
    normal_offsets = [0.0, 120.0, -120.0, 220.0, -220.0, 360.0, -360.0, 520.0, -520.0]
    phase_offsets = [0.0, 180.0, -180.0, 360.0, -360.0, 600.0, -600.0]
    candidates: list[tuple[float, float]] = []
    for normal_offset in normal_offsets:
        for phase_offset in phase_offsets:
            candidates.append(
                (
                    normal[0] * normal_offset + forward[0] * phase_offset,
                    normal[1] * normal_offset + forward[1] * phase_offset,
                )
            )
    return sorted(candidates, key=lambda item: (math.hypot(item[0], item[1]), abs(item[0]) + abs(item[1])))


def _route_within_scene_bounds(scene_id: str, start: list[float], end: list[float]) -> bool:
    if scene_id.startswith("museum_gallery"):
        return (
            -4325.0 <= start[0] <= -1425.0
            and -890.0 <= start[1] <= 145.0
            and -4325.0 <= end[0] <= -1425.0
            and -890.0 <= end[1] <= 145.0
        )
    if _is_downtown_west_scene(scene_id):
        return _downtown_west_route_on_pedestrian_surface(start, end, scene_id)
    return True


def _downtown_west_surface_y(point: list[float], scene_id: str | None = None) -> float:
    return float(point[1]) - DOWNTOWN_WEST_NATIVE_Y_OFFSET


def _world_template_6_7_route_on_pedestrian_surface(start: list[float], end: list[float]) -> bool:
    def interval(bounds: tuple[float, float, float, float]) -> tuple[float, float] | None:
        enter, leave = 0.0, 1.0
        for axis in range(2):
            delta = float(end[axis]) - float(start[axis])
            if delta == 0.0:
                if not bounds[axis] <= start[axis] <= bounds[axis + 2]:
                    return None
            else:
                times = sorted(((bounds[axis] - start[axis]) / delta, (bounds[axis + 2] - start[axis]) / delta))
                enter, leave = max(enter, times[0]), min(leave, times[1])
        return (enter, leave) if enter <= leave else None

    walkways = ((-5300.0, -1350.0, -250.0, -400.0), (-550.0, -3200.0, -200.0, -1200.0))
    covered = 0.0
    for enter, leave in sorted(hit for bounds in walkways if (hit := interval(bounds)) is not None):
        if enter > covered:
            return False
        covered = max(covered, leave)
    if covered < 1.0:
        return False

    # Native XY bounds rounded outward from downtown_cafe_geometry_report.json.
    # Exclude whole garden enclosures, not just their rails or canopy bounds.
    obstacles = (
        (-1600.0, -872.0, -1300.0, -528.0),  # East garden
        (-2397.0, -872.0, -2102.0, -528.0),
        (-3202.0, -872.0, -2902.0, -528.0),
        (-4000.0, -872.0, -3700.0, -528.0),  # West garden
        (-3295.0, -859.0, -3227.0, -531.0),  # bench_wood_b4
        (-2060.0, -860.0, -1992.0, -531.0),  # bench_wood_b
        (-3680.0, -860.0, -3612.0, -531.0),  # bench_wood_b3
        (-1483.0, -533.0, -1365.0, -508.0),  # LookingStand4
        (-289.0, -755.0, -143.0, -609.0),  # Pot_2
        (-499.0, -2417.0, -361.0, -2279.0),  # Pot_35
        (-452.0, -2239.0, -340.0, -2127.0),  # Pot_36
        (-2547.0, -661.0, -2416.0, -530.0),  # Pot_9
        (-231.0, -987.0, -143.0, -821.0),  # prop_recycle_bin
        (-2380.0, -1583.0, -2063.0, -1266.0),  # prop_table_umbrella_a5
        (-215.0, -986.0, 5.0, -766.0),  # lightpost_light_post_a23
        (-3518.0, -1042.0, -3461.0, -823.0),  # lightpost_light_post_b2
    )
    for x0, y0, x1, y1 in obstacles:
        if interval((x0 - 40.0, y0 - 40.0, x1 + 40.0, y1 + 40.0)) is not None:
            return False
    return _point_to_segment_distance_xy([-2185.7, -753.3], start, end) >= 150.0


def _downtown_west_point_on_pedestrian_surface(point: list[float], scene_id: str | None = None) -> bool:
    x = float(point[0])
    y = _downtown_west_surface_y(point, scene_id)
    if scene_id in WORLD_TEMPLATE_6_7_SCENE_IDS:
        return _world_template_6_7_route_on_pedestrian_surface(point, point)
    if not (250.0 <= x <= 3250.0 and 4150.0 <= y <= 5850.0):
        return False
    sidewalk_spine = 920.0 <= x <= 1320.0 and 4200.0 <= y <= 5850.0
    streetfront_sidewalk = 1500.0 <= x <= 3250.0 and 4150.0 <= y <= 5050.0
    storefront_apron = 1600.0 <= x <= 3200.0 and 5050.0 <= y <= 5550.0
    road_crossings = 280.0 <= x <= 1600.0 and 4200.0 <= y <= 5000.0
    plaza_apron = 900.0 <= x <= 3200.0 and 4700.0 <= y <= 5350.0
    connector = 1200.0 <= x <= 1700.0 and 5050.0 <= y <= 5850.0
    return sidewalk_spine or streetfront_sidewalk or storefront_apron or road_crossings or plaza_apron or connector


def _downtown_west_route_on_pedestrian_surface(start: list[float], end: list[float], scene_id: str | None = None) -> bool:
    if scene_id in WORLD_TEMPLATE_6_7_SCENE_IDS:
        return _world_template_6_7_route_on_pedestrian_surface(start, end)
    for sample in (0.0, 0.25, 0.5, 0.75, 1.0):
        point = [
            float(start[0]) + (float(end[0]) - float(start[0])) * sample,
            float(start[1]) + (float(end[1]) - float(start[1])) * sample,
            float(start[2]) + (float(end[2]) - float(start[2])) * sample,
        ]
        if not _downtown_west_point_on_pedestrian_surface(point, scene_id):
            return False
    return True


def _downtown_west_route_waypoints(start: list[float], end: list[float], index: int, scene_id: str | None = None) -> list[list[float]] | None:
    distance = math.hypot(float(end[0]) - float(start[0]), float(end[1]) - float(start[1]))
    if distance < 250.0:
        return None
    dx = float(end[0]) - float(start[0])
    dy = float(end[1]) - float(start[1])
    length = distance or 1.0
    normal = [-dy / length, dx / length, 0.0]
    bend = [-45.0, 30.0, 40.0, -45.0, 25.0, -30.0][index % 6]
    mid = _lerp(start, end, 0.52)
    mid[0] += normal[0] * bend
    mid[1] += normal[1] * bend
    y_offset = DOWNTOWN_WEST_NATIVE_Y_OFFSET
    if scene_id in WORLD_TEMPLATE_6_7_SCENE_IDS:
        mid[0] = max(-5300.0, min(-200.0, mid[0]))
        mid[1] = max(1500.0 + y_offset, min(4300.0 + y_offset, mid[1]))
    else:
        mid[0] = max(280.0, min(3200.0, mid[0]))
        mid[1] = max(4200.0 + y_offset, min(5820.0 + y_offset, mid[1]))
    if not _downtown_west_point_on_pedestrian_surface(mid, scene_id):
        return [list(start), list(end)]
    return [list(start), mid, list(end)]


def _point_to_segment_distance_xy(point: list[float], start: list[float], end: list[float]) -> float:
    px = float(point[0])
    py = float(point[1])
    sx = float(start[0])
    sy = float(start[1])
    ex = float(end[0])
    ey = float(end[1])
    dx = ex - sx
    dy = ey - sy
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-6:
        return math.hypot(px - sx, py - sy)
    t = max(0.0, min(1.0, ((px - sx) * dx + (py - sy) * dy) / length_sq))
    return math.hypot(px - (sx + dx * t), py - (sy + dy * t))


def _downtown_west_route_clear_of_first_person_camera(start: list[float], end: list[float]) -> bool:
    camera_start = _downtown_west_native_location([3150.0, 4180.0, float(start[2])])
    camera_end = _downtown_west_native_location([1900.0, 4210.0, float(start[2])])
    for sample in (0.0, 0.35, 0.7, 1.0):
        point = [
            float(start[0]) + (float(end[0]) - float(start[0])) * sample,
            float(start[1]) + (float(end[1]) - float(start[1])) * sample,
            float(start[2]) + (float(end[2]) - float(start[2])) * sample,
        ]
        if _point_to_segment_distance_xy(point, camera_start, camera_end) < 185.0:
            return False
    return True


def _downtown_west_naturalized_route(start: list[float], end: list[float], index: int, scene_id: str | None = None) -> tuple[list[float], list[float]]:
    start = [float(value) for value in start]
    end = [float(value) for value in end]
    distance = math.hypot(end[0] - start[0], end[1] - start[1])
    if distance < 250.0:
        static_offsets = [
            (0.0, 0.0),
            (42.0, -34.0),
            (-58.0, 26.0),
            (76.0, 42.0),
            (-32.0, -62.0),
            (118.0, -20.0),
            (-105.0, 48.0),
            (28.0, 88.0),
            (-148.0, -42.0),
            (154.0, 66.0),
            (-74.0, 132.0),
        ]
        for offset_index in range(len(static_offsets)):
            offset_x, offset_y = static_offsets[(index + offset_index) % len(static_offsets)]
            candidate = [start[0] + offset_x, start[1] + offset_y, start[2]]
            if _downtown_west_point_on_pedestrian_surface(candidate, scene_id) and _downtown_west_route_clear_of_first_person_camera(candidate, candidate):
                return candidate, list(candidate)
        return start, end

    dx = end[0] - start[0]
    dy = end[1] - start[1]
    forward = [dx / distance, dy / distance, 0.0]
    normal = [-forward[1], forward[0], 0.0]
    lateral_offsets = [-54.0, 38.0, 72.0, -34.0, 18.0, -82.0, 46.0, -22.0]
    start_phase_offsets = [-130.0, 65.0, 180.0, -75.0, 35.0, -170.0, 95.0, -35.0]
    end_phase_offsets = [90.0, -145.0, 45.0, 165.0, -95.0, 30.0, -135.0, 120.0]
    for attempt in range(len(lateral_offsets)):
        offset_index = (index + attempt) % len(lateral_offsets)
        lateral = lateral_offsets[offset_index]
        start_phase = start_phase_offsets[offset_index]
        end_phase = end_phase_offsets[offset_index]
        candidate_start = [
            start[0] + normal[0] * lateral + forward[0] * start_phase,
            start[1] + normal[1] * lateral + forward[1] * start_phase,
            start[2],
        ]
        candidate_end = [
            end[0] + normal[0] * lateral * 0.55 + forward[0] * end_phase,
            end[1] + normal[1] * lateral * 0.55 + forward[1] * end_phase,
            end[2],
        ]
        if _downtown_west_route_on_pedestrian_surface(candidate_start, candidate_end, scene_id) and _downtown_west_route_clear_of_first_person_camera(candidate_start, candidate_end):
            return candidate_start, candidate_end
    return start, end


def _museum_local_route_candidates(z: float) -> list[tuple[list[float], list[float]]]:
    candidates: list[tuple[list[float], list[float]]] = []
    x_values = [-4200.0, -3900.0, -3600.0, -3300.0, -3000.0, -2700.0, -2400.0, -2100.0, -1800.0, -1500.0]
    y_values = [-840.0, -760.0, -680.0, -600.0, -520.0, -440.0, -360.0, -280.0, -200.0, -120.0, -40.0, 40.0]
    for y in y_values:
        for left_index, x_start in enumerate(x_values):
            for right_index, x_end in enumerate(x_values):
                distance = abs(float(x_end) - float(x_start))
                if 600.0 <= distance <= 1200.0 and abs(left_index - right_index) <= 4:
                    candidates.append(([x_start, y, z], [x_end, y + 20.0, z]))
    return candidates


def _downtown_west_reserved_camera_routes(scene_id: str, z: float) -> list[dict]:
    if not _is_downtown_west_scene(scene_id):
        return []
    try:
        profile = _cinematic_profile(scene_id, z)
        return [
            {
                "start": list(profile["first_start"]),
                "end": list(profile["first_end"]),
                "waypoints": [list(key["location"]) for key in _cinematic_first_person_keys(profile)],
            },
            {
                "start": _downtown_west_native_location([3060.0, 5750.0, z]),
                "end": _downtown_west_native_location([1560.0, 5200.0, z]),
                "waypoints": [
                    _downtown_west_native_location([3060.0, 5750.0, z]),
                    _downtown_west_native_location([2320.0, 5480.0, z]),
                    _downtown_west_native_location([1560.0, 5200.0, z]),
                ],
            },
            {
                "start": list(profile["hitch_start"]),
                "end": list(profile["hitch_end"]),
                "waypoints": [
                    list(profile["hitch_start"]),
                    _lerp(profile["hitch_start"], profile["hitch_end"], 0.5),
                    list(profile["hitch_end"]),
                ],
            },
        ]
    except Exception:
        return []


def _avoid_existing_root_people(start: list[float], end: list[float], people: list[dict], scene_id: str, min_spacing: float = 120.0) -> tuple[list[float], list[float]]:
    reserved_camera_routes = (
        []
        if scene_id in WORLD_TEMPLATE_6_7_SCENE_IDS
        else _downtown_west_reserved_camera_routes(scene_id, float(start[2]) if len(start) > 2 else 0.0)
    )

    def clearances(candidate_start: list[float], candidate_end: list[float]) -> tuple[float, float]:
        people_clearance = _route_clearance_against_people(candidate_start, candidate_end, people) if people else float("inf")
        camera_clearance = (
            _route_spatial_clearance_against_people(candidate_start, candidate_end, reserved_camera_routes)
            if reserved_camera_routes
            else float("inf")
        )
        return people_clearance, camera_clearance

    def has_required_clearance(people_clearance: float, camera_clearance: float) -> bool:
        return people_clearance >= min_spacing and (not reserved_camera_routes or camera_clearance >= 180.0)

    best_start = start
    best_end = end
    best_people_clearance = -1.0
    best_camera_clearance = -1.0
    best_people_safe_start = None
    best_people_safe_end = None
    best_people_safe_camera_clearance = -1.0

    candidates: list[tuple[list[float], list[float]]] = []
    if _route_within_scene_bounds(scene_id, start, end):
        candidates.append((start, end))
    for offset_x, offset_y in _route_offset_candidates(start, end):
        candidate_start = [start[0] + offset_x, start[1] + offset_y, start[2]]
        candidate_end = [end[0] + offset_x, end[1] + offset_y, end[2]]
        if _route_within_scene_bounds(scene_id, candidate_start, candidate_end):
            candidates.append((candidate_start, candidate_end))
    if scene_id.startswith("museum_gallery"):
        candidates.extend(_museum_local_route_candidates(float(start[2])))

    for candidate_start, candidate_end in candidates:
        people_clearance, camera_clearance = clearances(candidate_start, candidate_end)
        if has_required_clearance(people_clearance, camera_clearance):
            return candidate_start, candidate_end
        if people_clearance >= min_spacing and camera_clearance > best_people_safe_camera_clearance:
            best_people_safe_camera_clearance = camera_clearance
            best_people_safe_start = candidate_start
            best_people_safe_end = candidate_end
        if (people_clearance, camera_clearance) > (best_people_clearance, best_camera_clearance):
            best_people_clearance = people_clearance
            best_camera_clearance = camera_clearance
            best_start = candidate_start
            best_end = candidate_end
    if best_people_safe_start is not None and best_people_safe_end is not None:
        return best_people_safe_start, best_people_safe_end
    return best_start, best_end


def _cinematic_30s_requested() -> bool:
    return "cinematic30" in MODE.lower() or "_cinematic_" in CAMERA_FILTER.lower()


def _slow_pedestrian_routes_requested() -> bool:
    mode = MODE.lower()
    return _cinematic_30s_requested() or "production2k" in mode or "final_v4_sync60" in mode


def _production_material_fallback_allowed() -> bool:
    return _truthy_env_value(os.environ.get("CINEU_ALLOW_PRODUCTION_MATERIAL_FALLBACK"))


PRODUCTION_INCOMPLETE_PEDESTRIAN_WARNING_REASONS = {
    "pedestrian_actor_skipped",
    "skeletal_mesh_fallback_used",
    "skeletal_animation_track_failed",
    "skeletal_animation_omitted",
    "skeletal_animation_skeleton_mismatch",
    "skeletal_asset_skeleton_unavailable",
    "host_skeletal_component_missing",
    "skeletal_component_create_failed",
    "modular_part_mesh_load_failed",
    "modular_part_attach_failed",
    "transform_channel_audit_failed",
    "transform_sequence_audit_failed",
    "transform_key_failed_linear_interpolation_failed",
    "focal_length_key_failed_linear_interpolation_failed",
}


def _production_incomplete_pedestrian_issues(warnings: list[dict] | None) -> list[dict]:
    return [
        warning
        for warning in (warnings or [])
        if str(warning.get("reason") or "") in PRODUCTION_INCOMPLETE_PEDESTRIAN_WARNING_REASONS
    ]


def _windows_memory_status():
    if os.name != "nt":
        return None

    class MemoryStatusEx(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatusEx()
    status.dwLength = ctypes.sizeof(MemoryStatusEx)
    try:
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
    except Exception:
        return None
    return status


def _system_commit_snapshot_gib() -> tuple[float | None, float | None]:
    status = _windows_memory_status()
    if status is None:
        return None, None
    gib = float(1024**3)
    return float(status.ullTotalPageFile) / gib, float(status.ullAvailPageFile) / gib


def _production_quality_gate(
    mrq_spatial_samples: int,
    mrq_temporal_samples: int,
    warnings: list[dict] | None = None,
    capture_frame_count: int | None = None,
    production_mode: bool | None = None,
    fps: int | None = None,
) -> dict:
    if production_mode is None:
        production_mode = _production_quality_mode_requested(MODE, CAMERA_FILTER)
    incomplete_pedestrian_issues = _production_incomplete_pedestrian_issues(warnings)
    system_commit_limit_gib, system_available_commit_gib = _system_commit_snapshot_gib()
    system_memory_status_available = (
        system_commit_limit_gib is not None and system_available_commit_gib is not None
    )
    min_required_system_commit_limit_gib = 48.0
    min_required_system_available_commit_gib = 8.0
    long_production_capture = (
        production_mode
        and capture_frame_count is not None
        and int(capture_frame_count) >= max(1, int(fps or FPS) * 5)
    )
    system_commit_limit_required = long_production_capture
    system_commit_limit_passed = (
        system_memory_status_available
        and system_commit_limit_gib >= min_required_system_commit_limit_gib
    )
    system_available_commit_passed = (
        system_memory_status_available
        and system_available_commit_gib >= min_required_system_available_commit_gib
    )
    return {
        "production_mode": production_mode,
        "pedestrian_slot_material_fallback_enabled": bool(PEDESTRIAN_SLOT_MATERIAL_FALLBACK),
        "pedestrian_slot_material_fallback_allowed": _production_material_fallback_allowed(),
        "complete_pedestrians_passed": not production_mode or not incomplete_pedestrian_issues,
        "incomplete_pedestrian_issue_count": len(incomplete_pedestrian_issues),
        "incomplete_pedestrian_issues": incomplete_pedestrian_issues,
        "capture_frame_count": int(capture_frame_count) if capture_frame_count is not None else None,
        "long_production_capture": long_production_capture,
        "system_memory_status_available": system_memory_status_available,
        "system_commit_limit_gib": system_commit_limit_gib,
        "min_required_system_commit_limit_gib": min_required_system_commit_limit_gib,
        "system_commit_limit_required": system_commit_limit_required,
        "system_commit_limit_passed": system_commit_limit_passed,
        "system_available_commit_gib": system_available_commit_gib,
        "min_required_system_available_commit_gib": min_required_system_available_commit_gib,
        "system_available_commit_passed": system_available_commit_passed,
        "mrq_low_memory": _truthy_env_value(os.environ.get("CINEU_MRQ_LOW_MEMORY")),
        "mrq_spatial_samples": int(mrq_spatial_samples),
        "mrq_temporal_samples": int(mrq_temporal_samples),
        "min_required_spatial_samples": 2 if production_mode else 1,
        "min_required_temporal_samples": 8 if production_mode else 1,
    }


def _enforce_production_quality_gate(gate: dict) -> None:
    if (
        gate["production_mode"]
        and gate["pedestrian_slot_material_fallback_enabled"]
        and not gate["pedestrian_slot_material_fallback_allowed"]
    ):
        raise RuntimeError(
            "Production render cannot use CINEU_PEDESTRIAN_SLOT_MATERIAL_FALLBACK=1. "
            "Run preview modes for layout scouting, or set CINEU_ALLOW_PRODUCTION_MATERIAL_FALLBACK=1 only for explicit non-final diagnostics."
        )
    if gate["production_mode"] and not gate.get("complete_pedestrians_passed", True):
        details = []
        for issue in gate.get("incomplete_pedestrian_issues") or []:
            subject = issue.get("actor") or issue.get("part") or issue.get("asset") or "unknown_pedestrian"
            asset = issue.get("mesh") or issue.get("asset") or ""
            details.append(f"{subject}:{issue.get('reason', 'unknown')}:{asset}")
        raise RuntimeError(
            "Production render cannot include incomplete pedestrians "
            f"({gate.get('incomplete_pedestrian_issue_count', len(details))} issue(s)): "
            + "; ".join(details[:12])
        )
    if not gate.get("system_memory_status_available", False):
        raise RuntimeError(
            "Production render system memory status is unavailable. "
            "GlobalMemoryStatusEx must succeed before MRQ can start."
        )
    if (
        gate["production_mode"]
        and gate.get("system_commit_limit_required", gate.get("long_production_capture", False))
        and not gate.get("system_commit_limit_passed", True)
    ):
        raise RuntimeError(
            "Production render system commit limit is too low for a long capture: "
            f"detected {gate.get('system_commit_limit_gib', 0.0):.2f} GiB, "
            f"requires at least {gate.get('min_required_system_commit_limit_gib', 48.0):.2f} GiB. "
            "Increase the Windows pagefile on a drive with sufficient free space and reboot before rendering."
        )
    if not gate.get("system_available_commit_passed", True):
        raise RuntimeError(
            "Production render available system commit is too low to start MRQ: "
            f"detected {gate.get('system_available_commit_gib', 0.0):.2f} GiB, "
            f"requires at least {gate.get('min_required_system_available_commit_gib', 8.0):.2f} GiB. "
            "Close memory-heavy applications or increase the Windows pagefile before rendering."
        )


def _slow_pedestrian_max_route_distance() -> float:
    duration_seconds = float(FRAME_COUNT) / float(FPS or 24)
    return duration_seconds * 85.0


def _clamp_cinematic_route(start: list[float], end: list[float], max_distance: float | None = None) -> tuple[list[float], list[float]]:
    max_distance = _slow_pedestrian_max_route_distance() if max_distance is None else float(max_distance)
    distance = _xy_distance(start, end)
    if distance <= max_distance or distance <= 1e-6:
        return start, end
    scale = float(max_distance) / distance
    return start, [start[0] + (end[0] - start[0]) * scale, start[1] + (end[1] - start[1]) * scale, end[2]]


def _movie_scene_rotation_values(rotation: list[float]) -> list[float]:
    pitch, yaw, roll = [float(v) for v in rotation]
    return [roll, pitch, yaw]


def _try_set_linear_key_interpolation(key, warnings: list[dict], label: str, frame: int, reason: str) -> None:
    if key is None:
        return
    interpolation_candidates = [
        getattr(getattr(unreal, "RichCurveInterpMode", None), "RCIM_LINEAR", None),
        getattr(getattr(unreal, "MovieSceneKeyInterpolation", None), "LINEAR", None),
    ]
    interpolation_candidates = [candidate for candidate in interpolation_candidates if candidate is not None]
    errors = []
    for method_name in ("set_interpolation_mode", "set_interpolation"):
        setter = getattr(key, method_name, None)
        if setter is None:
            continue
        for interpolation_enum in interpolation_candidates:
            try:
                setter(interpolation_enum)
                return
            except Exception as exc:
                errors.append(f"{method_name}:{type(exc).__name__}:{exc}")
    if errors:
        warnings.append(
            {
                "actor": label,
                "frame": int(frame),
                "reason": f"{reason}_linear_interpolation_failed",
                "api": "set_interpolation_mode|set_interpolation",
                "error": ";".join(errors),
            }
        )


def _try_add_channel_key(channel, frame: int, value: float, warnings: list[dict], label: str, reason: str) -> None:
    try:
        key = channel.add_key(unreal.FrameNumber(int(frame)), float(value))
        _try_set_linear_key_interpolation(key, warnings, label, frame, reason)
        return
    except Exception as first_exc:
        try:
            key = channel.add_key(unreal.FrameNumber(int(frame)), float(value), 0.0)
            _try_set_linear_key_interpolation(key, warnings, label, frame, reason)
            return
        except Exception as second_exc:
            warnings.append(
                {
                    "actor": label,
                    "frame": int(frame),
                    "reason": reason,
                    "error": f"{type(first_exc).__name__}:{first_exc};{type(second_exc).__name__}:{second_exc}",
                }
            )


def _channels_for_section(section) -> list:
    getter = getattr(section, "get_channels", None) or getattr(section, "get_all_channels", None)
    if getter is not None:
        return list(getter())
    get_channel = getattr(section, "get_channel", None)
    if get_channel is not None:
        try:
            return [get_channel()]
        except Exception:
            return []
    return []


def _frame_number_value(value) -> int | None:
    if isinstance(value, (int, float)):
        return int(value)
    for attribute in ("frame_number", "value"):
        nested = getattr(value, attribute, None)
        if nested is not None and nested is not value:
            resolved = _frame_number_value(nested)
            if resolved is not None:
                return resolved
    get_editor_property = getattr(value, "get_editor_property", None)
    if callable(get_editor_property):
        for property_name in ("frame_number", "value"):
            try:
                resolved = _frame_number_value(get_editor_property(property_name))
            except Exception:
                continue
            if resolved is not None:
                return resolved
    try:
        return int(value)
    except (TypeError, ValueError):
        pass
    return None


def _transform_channel_values(key: dict) -> list[float]:
    transform = key["transform"]
    return [
        *[float(value) for value in transform["location"]],
        *_movie_scene_rotation_values(transform["rotation"]),
        *[float(value) for value in transform.get("scale", [1.0, 1.0, 1.0])],
    ]


TRANSFORM_CHANNEL_NAMES = [
    "Location.X",
    "Location.Y",
    "Location.Z",
    "Rotation.X",
    "Rotation.Y",
    "Rotation.Z",
    "Scale.X",
    "Scale.Y",
    "Scale.Z",
]


def _transform_channel_name(channel) -> str | None:
    get_name = getattr(channel, "get_name", None)
    candidates = []
    if callable(get_name):
        try:
            candidates.append(str(get_name()))
        except Exception:
            pass
    channel_name = getattr(channel, "channel_name", None)
    if channel_name is not None:
        candidates.append(str(channel_name))
    candidates.append(str(channel))
    for expected_name in TRANSFORM_CHANNEL_NAMES:
        if any(expected_name.lower() in candidate.lower() for candidate in candidates):
            return expected_name
    return None


def _audit_transform_section(section, expected_keys: list[dict], label: str) -> dict:
    channels = _channels_for_section(section)
    issues = []
    if len(channels) < 9:
        issues.append({"reason": "transform_channel_count_mismatch", "actual": len(channels), "expected_min": 9})
    channels_by_name = {}
    for channel in channels:
        name = _transform_channel_name(channel)
        if name is None:
            continue
        if name in channels_by_name:
            issues.append({"reason": "duplicate_transform_channel", "channel_name": name})
            continue
        channels_by_name[name] = channel
    expected_frames = [int(key["frame"]) for key in expected_keys]
    expected_values_by_channel = list(zip(*[_transform_channel_values(key) for key in expected_keys]))
    for channel_index, (channel_name, expected_values) in enumerate(
        zip(TRANSFORM_CHANNEL_NAMES, expected_values_by_channel)
    ):
        channel = channels_by_name.get(channel_name)
        if channel is None:
            issues.append({"reason": "missing_transform_channel", "channel_name": channel_name})
            continue
        get_keys = getattr(channel, "get_keys", None)
        if not callable(get_keys):
            issues.append(
                {
                    "reason": "channel_keys_unavailable",
                    "channel_index": channel_index,
                    "channel_name": channel_name,
                }
            )
            continue
        try:
            actual_keys = list(get_keys())
        except Exception as exc:
            issues.append(
                {
                    "reason": "channel_keys_read_failed",
                    "channel_index": channel_index,
                    "channel_name": channel_name,
                    "error": f"{type(exc).__name__}:{exc}",
                }
            )
            continue
        if len(actual_keys) != len(expected_keys):
            issues.append(
                {
                    "reason": "channel_key_count_mismatch",
                    "channel_index": channel_index,
                    "channel_name": channel_name,
                    "actual": len(actual_keys),
                    "expected": len(expected_keys),
                }
            )
        actual_rows = []
        for actual_key in actual_keys:
            get_time = getattr(actual_key, "get_time", None)
            get_value = getattr(actual_key, "get_value", None)
            if not callable(get_time) or not callable(get_value):
                issues.append(
                    {
                        "reason": "channel_key_read_api_unavailable",
                        "channel_index": channel_index,
                        "channel_name": channel_name,
                    }
                )
                actual_rows = []
                break
            try:
                frame = _frame_number_value(get_time())
                value = float(get_value())
            except Exception as exc:
                issues.append(
                    {
                        "reason": "channel_key_read_failed",
                        "channel_index": channel_index,
                        "channel_name": channel_name,
                        "error": f"{type(exc).__name__}:{exc}",
                    }
                )
                actual_rows = []
                break
            interpolation_getter = getattr(actual_key, "get_interpolation_mode", None) or getattr(
                actual_key, "get_interpolation", None
            )
            if not callable(interpolation_getter):
                issues.append(
                    {
                        "reason": "interpolation_read_api_unavailable",
                        "channel_index": channel_index,
                        "channel_name": channel_name,
                    }
                )
                interpolation = ""
            else:
                try:
                    interpolation = str(interpolation_getter()).lower()
                except Exception as exc:
                    issues.append(
                        {
                            "reason": "interpolation_read_failed",
                            "channel_index": channel_index,
                            "channel_name": channel_name,
                            "error": f"{type(exc).__name__}:{exc}",
                        }
                    )
                    interpolation = ""
            actual_rows.append((frame, value, interpolation))
        if not actual_rows:
            continue
        actual_rows.sort(key=lambda row: (-1 if row[0] is None else row[0]))
        frame_counts = {}
        for frame, _value, _interpolation in actual_rows:
            frame_counts[frame] = frame_counts.get(frame, 0) + 1
        for frame, count in frame_counts.items():
            if count > 1:
                issues.append(
                    {
                        "reason": "duplicate_key_frame",
                        "channel_index": channel_index,
                        "channel_name": channel_name,
                        "frame": frame,
                        "actual_count": count,
                    }
                )
        expected_frame_set = set(expected_frames)
        unexpected_frames = [frame for frame in frame_counts if frame not in expected_frame_set]
        for frame in sorted(unexpected_frames, key=lambda value: (-1 if value is None else value)):
            issues.append(
                {
                    "reason": "unexpected_key_frame",
                    "channel_index": channel_index,
                    "channel_name": channel_name,
                    "frame": frame,
                }
            )
        for frame, _value, interpolation in actual_rows[:-1]:
            if interpolation and "linear" not in interpolation:
                issues.append(
                    {
                        "reason": "non_linear_interpolation",
                        "channel_index": channel_index,
                        "channel_name": channel_name,
                        "frame": frame,
                        "actual": interpolation,
                    }
                )
        rows_by_frame = {frame: value for frame, value, _interpolation in actual_rows}
        for key_index, (expected_frame, expected_value) in enumerate(zip(expected_frames, expected_values)):
            endpoint = key_index in {0, len(expected_frames) - 1}
            if expected_frame not in rows_by_frame:
                issues.append(
                    {
                        "reason": "endpoint_frame_missing" if endpoint else "key_frame_missing",
                        "channel_index": channel_index,
                        "channel_name": channel_name,
                        "key_index": key_index,
                        "expected": expected_frame,
                    }
                )
                continue
            actual_value = rows_by_frame[expected_frame]
            if abs(actual_value - float(expected_value)) > 1e-3:
                issues.append(
                    {
                        "reason": "endpoint_value_mismatch" if endpoint else "key_value_mismatch",
                        "channel_index": channel_index,
                        "channel_name": channel_name,
                        "key_index": key_index,
                        "actual": actual_value,
                        "expected": float(expected_value),
                    }
                )
    return {
        "actor": label,
        "passed": not issues,
        "channel_count": len(channels),
        "expected_key_count": len(expected_keys),
        "issue_count": len(issues),
        "issues": issues,
    }


def _sequence_object_names(value) -> list[str]:
    names = []
    for method_name in ("get_display_name", "get_name"):
        method = getattr(value, method_name, None)
        if not callable(method):
            continue
        try:
            name = str(method())
        except Exception:
            continue
        if name and name not in names:
            names.append(name)
    if not names:
        fallback = str(value)
        if fallback:
            names.append(fallback)
    return names


def _sequence_object_name(value) -> str:
    return _sequence_object_names(value)[0]


def _set_sequence_binding_names(binding, binding_name: str, warnings: list[dict]) -> None:
    extensions = getattr(unreal, "MovieSceneBindingExtensions", None)
    for property_name, extension_method_name, binding_method_name in (
        ("display_name", "set_display_name", "set_display_name"),
        ("internal_name", "set_name", "set_name"),
    ):
        error = None
        extension_method = getattr(extensions, extension_method_name, None)
        if callable(extension_method):
            try:
                extension_method(binding, binding_name)
                continue
            except Exception as exc:
                error = exc
        binding_method = getattr(binding, binding_method_name, None)
        if callable(binding_method):
            try:
                binding_method(binding_name)
                continue
            except Exception as exc:
                error = exc
        warnings.append(
            {
                "actor": binding_name,
                "reason": "sequence_binding_name_failed",
                "property": property_name,
                "error": f"{type(error).__name__}:{error}" if error is not None else "binding_name_api_unavailable",
            }
        )


def _audit_sequence_transform_tracks(sequence, expected_tracks: dict[str, dict]) -> dict:
    issues = []
    binding_audits = []
    get_bindings = getattr(sequence, "get_bindings", None)
    if not callable(get_bindings):
        return {
            "passed": False,
            "expected_binding_count": len(expected_tracks),
            "audited_binding_count": 0,
            "issue_count": 1,
            "issues": [{"reason": "sequence_bindings_api_unavailable"}],
            "binding_audits": [],
        }
    try:
        bindings = list(get_bindings())
    except Exception as exc:
        return {
            "passed": False,
            "expected_binding_count": len(expected_tracks),
            "audited_binding_count": 0,
            "issue_count": 1,
            "issues": [{"reason": "sequence_bindings_read_failed", "error": f"{type(exc).__name__}:{exc}"}],
            "binding_audits": [],
        }
    bindings_by_name = {}
    for binding in bindings:
        for name in _sequence_object_names(binding):
            bindings_by_name.setdefault(name, binding)
    available_binding_names = sorted(bindings_by_name)
    for actor_name, track_record in expected_tracks.items():
        binding = bindings_by_name.get(actor_name)
        if binding is None:
            issues.append({"reason": "missing_sequence_binding", "actor": actor_name})
            continue
        get_tracks = getattr(binding, "get_tracks", None)
        tracks = list(get_tracks()) if callable(get_tracks) else []
        transform_tracks = [
            track
            for track in tracks
            if "moviescene3dtransformtrack" in _sequence_object_name(
                track.get_class() if callable(getattr(track, "get_class", None)) else track
            ).lower()
        ]
        if len(transform_tracks) != 1:
            issues.append(
                {
                    "reason": "transform_track_count_mismatch",
                    "actor": actor_name,
                    "actual": len(transform_tracks),
                    "expected": 1,
                }
            )
            continue
        get_sections = getattr(transform_tracks[0], "get_sections", None)
        sections = list(get_sections()) if callable(get_sections) else []
        if len(sections) != 1:
            issues.append(
                {
                    "reason": "transform_section_count_mismatch",
                    "actor": actor_name,
                    "actual": len(sections),
                    "expected": 1,
                }
            )
            continue
        binding_audits.append(_audit_transform_section(sections[0], list(track_record["keys"]), actor_name))
    binding_issues = [
        issue
        for binding_audit in binding_audits
        for issue in binding_audit["issues"]
    ]
    all_issues = [*issues, *binding_issues]
    return {
        "passed": not all_issues,
        "expected_binding_count": len(expected_tracks),
        "audited_binding_count": len(binding_audits),
        "issue_count": len(all_issues),
        "issues": issues,
        "binding_audits": binding_audits,
        "available_binding_names": available_binding_names,
    }


def _audit_sequence_animation_tracks(sequence, expected_tracks: dict[str, dict]) -> dict:
    issues = []
    binding_audits = []
    get_bindings = getattr(sequence, "get_bindings", None)
    if not callable(get_bindings):
        return {
            "passed": False,
            "expected_binding_count": len(expected_tracks),
            "audited_binding_count": 0,
            "issue_count": 1,
            "issues": [{"reason": "sequence_bindings_api_unavailable"}],
            "binding_audits": [],
        }
    try:
        bindings = list(get_bindings())
    except Exception as exc:
        return {
            "passed": False,
            "expected_binding_count": len(expected_tracks),
            "audited_binding_count": 0,
            "issue_count": 1,
            "issues": [{"reason": "sequence_bindings_read_failed", "error": f"{type(exc).__name__}:{exc}"}],
            "binding_audits": [],
        }

    bindings_by_name = {}
    for binding in bindings:
        for name in _sequence_object_names(binding):
            bindings_by_name.setdefault(name, binding)
    for actor_name, expected in expected_tracks.items():
        binding = bindings_by_name.get(actor_name)
        if binding is None:
            issues.append({"reason": "missing_sequence_binding", "actor": actor_name})
            continue
        get_tracks = getattr(binding, "get_tracks", None)
        tracks = list(get_tracks()) if callable(get_tracks) else []
        animation_tracks = [
            track
            for track in tracks
            if "moviesceneskeletalanimationtrack" in _sequence_object_name(
                track.get_class() if callable(getattr(track, "get_class", None)) else track
            ).lower()
        ]
        if len(animation_tracks) != 1:
            issues.append(
                {
                    "reason": "animation_track_count_mismatch",
                    "actor": actor_name,
                    "actual": len(animation_tracks),
                    "expected": 1,
                }
            )
            continue
        get_sections = getattr(animation_tracks[0], "get_sections", None)
        sections = list(get_sections()) if callable(get_sections) else []
        if len(sections) != 1:
            issues.append(
                {
                    "reason": "animation_section_count_mismatch",
                    "actor": actor_name,
                    "actual": len(sections),
                    "expected": 1,
                }
            )
            continue

        audit_issues = []
        section = sections[0]
        params = _animation_property(section, "params")
        section_animation = _animation_property(params, "animation")
        actual_animation_path = _asset_package_path(_ue_asset_path(section_animation) or "")
        expected_animation_path = _asset_package_path(str(expected.get("animation_path") or ""))
        if actual_animation_path != expected_animation_path:
            audit_issues.append(
                {
                    "reason": "animation_reference_mismatch",
                    "actor": actor_name,
                    "actual": actual_animation_path,
                    "expected": expected_animation_path,
                }
            )

        actual_playback_rate = _movie_scene_play_rate_value(_animation_property(params, "play_rate"))
        expected_playback_rate = float(expected["playback_rate"])
        if actual_playback_rate is None or not math.isclose(
            actual_playback_rate,
            expected_playback_rate,
            rel_tol=1e-5,
            abs_tol=1e-5,
        ):
            audit_issues.append(
                {
                    "reason": "animation_playback_rate_mismatch",
                    "actor": actor_name,
                    "actual": actual_playback_rate,
                    "expected": expected_playback_rate,
                }
            )

        actual_start_frame = int(section.get_start_frame())
        actual_end_frame = int(section.get_end_frame())
        expected_start_frame = int(expected["start_frame"])
        expected_end_frame = int(expected["end_frame"])
        actual_effective_end_frame = (
            actual_end_frame * actual_playback_rate
            if actual_playback_rate is not None
            else None
        )
        end_frame_matches = actual_end_frame == expected_end_frame
        if actual_effective_end_frame is not None:
            end_frame_matches = end_frame_matches or math.isclose(
                actual_effective_end_frame,
                expected_end_frame,
                rel_tol=2e-3,
                abs_tol=1.0,
            )
        if actual_start_frame != expected_start_frame or not end_frame_matches:
            audit_issues.append(
                {
                    "reason": "animation_section_range_mismatch",
                    "actor": actor_name,
                    "actual": [actual_start_frame, actual_end_frame],
                    "actual_effective_end_frame": actual_effective_end_frame,
                    "expected": [expected_start_frame, expected_end_frame],
                    "note": "UE may preserve section content duration by scaling its physical end frame inversely with play rate.",
                }
            )

        actual_start_frame_offset = _frame_number_value(_animation_property(params, "start_frame_offset"))
        expected_start_frame_offset = int(expected["phase_offset_frames"])
        if actual_start_frame_offset != expected_start_frame_offset:
            audit_issues.append(
                {
                    "reason": "animation_start_frame_offset_mismatch",
                    "actor": actor_name,
                    "actual": actual_start_frame_offset,
                    "expected": expected_start_frame_offset,
                }
            )

        actual_swap_root_bone = _swap_root_bone_mode(_animation_property(params, "swap_root_bone"))
        expected_swap_root_bone = str(expected["swap_root_bone"]).strip().lower()
        if actual_swap_root_bone != expected_swap_root_bone:
            audit_issues.append(
                {
                    "reason": "animation_swap_root_bone_mismatch",
                    "actor": actor_name,
                    "actual": actual_swap_root_bone,
                    "expected": expected_swap_root_bone,
                }
            )

        reloaded_animation = _try_load_asset(expected_animation_path)
        if reloaded_animation is None:
            audit_issues.append(
                {
                    "reason": "animation_asset_cold_reload_failed",
                    "actor": actor_name,
                    "animation_path": expected_animation_path,
                }
            )
        in_place_requested = bool(expected.get("in_place_requested"))
        persistent_in_place_verified = False
        if reloaded_animation is not None and in_place_requested:
            force_root_lock = bool(_animation_property(reloaded_animation, "force_root_lock"))
            enable_root_motion = bool(_animation_property(reloaded_animation, "enable_root_motion"))
            if not force_root_lock:
                audit_issues.append(
                    {
                        "reason": "animation_root_lock_not_persisted",
                        "actor": actor_name,
                        "animation_path": expected_animation_path,
                    }
                )
            if enable_root_motion:
                audit_issues.append(
                    {
                        "reason": "animation_root_motion_not_disabled",
                        "actor": actor_name,
                        "animation_path": expected_animation_path,
                    }
                )
            persistent_in_place_verified = force_root_lock and not enable_root_motion

        skeleton_compatibility_verified = False
        mesh_path = _asset_package_path(str(expected.get("mesh_path") or ""))
        if mesh_path and reloaded_animation is not None:
            reloaded_mesh = _try_load_asset(mesh_path)
            compatibility = _skeletal_asset_compatibility(reloaded_mesh, reloaded_animation)
            skeleton_compatibility_verified = bool(compatibility.get("passed"))
            if not skeleton_compatibility_verified:
                audit_issues.append({"actor": actor_name, **compatibility})

        binding_audit = {
            "actor": actor_name,
            "passed": not audit_issues,
            "animation_path": expected_animation_path,
            "actual_animation_path": actual_animation_path,
            "in_place_requested": in_place_requested,
            "persistent_in_place_verified": persistent_in_place_verified,
            "skeleton_compatibility_verified": skeleton_compatibility_verified,
            "section_settings_verified": not any(
                issue["reason"]
                in {
                    "animation_section_range_mismatch",
                    "animation_playback_rate_mismatch",
                    "animation_start_frame_offset_mismatch",
                    "animation_swap_root_bone_mismatch",
                }
                for issue in audit_issues
            ),
            "actual_section_range": [actual_start_frame, actual_end_frame],
            "actual_effective_end_frame": actual_effective_end_frame,
            "actual_playback_rate": actual_playback_rate,
            "actual_start_frame_offset": actual_start_frame_offset,
            "actual_swap_root_bone": actual_swap_root_bone,
            "issue_count": len(audit_issues),
            "issues": audit_issues,
        }
        binding_audits.append(binding_audit)
        issues.extend(audit_issues)
    return {
        "passed": not issues,
        "expected_binding_count": len(expected_tracks),
        "audited_binding_count": len(binding_audits),
        "issue_count": len(issues),
        "issues": issues,
        "binding_audits": binding_audits,
    }


def _set_transform_channels(section, keys: list[dict], label: str, warnings: list[dict]) -> None:
    channels = _channels_for_section(section)
    if not channels:
        warnings.append({"actor": label, "reason": "transform_channels_unavailable"})
        return
    for key in keys:
        transform = key["transform"]
        values = [
            *[float(v) for v in transform["location"]],
            *_movie_scene_rotation_values(transform["rotation"]),
            *[float(v) for v in transform.get("scale", [1.0, 1.0, 1.0])],
        ]
        for channel, value in zip(channels, values):
            _try_add_channel_key(channel, int(key["frame"]), float(value), warnings, label, "transform_key_failed")


def _add_camera_focal_length_track(seq, camera_binding, camera, keys: list[dict], start_frame: int, end_frame: int, warnings: list[dict]) -> None:
    component = camera.get_cine_camera_component() if hasattr(camera, "get_cine_camera_component") else None
    if component is None or not keys:
        return
    focal_values = [float(key["focal_length"]) for key in keys if key.get("focal_length") is not None]
    if not focal_values:
        return
    label = camera.get_actor_label() if hasattr(camera, "get_actor_label") else "camera"
    _try_set_property(component, "current_focal_length", focal_values[0])
    track_type = getattr(unreal, "MovieSceneFloatTrack", None)
    if track_type is None:
        warnings.append({"camera": label, "reason": "movie_scene_float_track_unavailable"})
        return
    try:
        component_binding = seq.add_possessable(component)
        set_parent = getattr(component_binding, "set_parent", None)
        if set_parent is not None:
            set_parent(camera_binding)
        track = component_binding.add_track(track_type)
        set_property = getattr(track, "set_property_name_and_path", None)
        if set_property is not None:
            set_property("CurrentFocalLength", "CurrentFocalLength")
        section = track.add_section()
        section.set_range(int(start_frame), int(end_frame))
        channels = _channels_for_section(section)
        if not channels:
            warnings.append({"camera": label, "reason": "focal_length_channel_unavailable"})
            return
        for key in keys:
            if key.get("focal_length") is not None:
                _try_add_channel_key(channels[0], int(key["frame"]), float(key["focal_length"]), warnings, label, "focal_length_key_failed")
    except Exception as exc:
        warnings.append({"camera": label, "reason": "focal_length_track_failed", "error": str(exc)})


def _binding_id(binding):
    binding_id_class = getattr(unreal, "MovieSceneObjectBindingID", None)
    get_id = getattr(binding, "get_id", None)
    if binding_id_class is not None and get_id is not None:
        try:
            guid = get_id()
            binding_id = binding_id_class()
            guid_export = getattr(guid, "export_text", None)
            import_text = getattr(binding_id, "import_text", None)
            if guid_export is not None and import_text is not None:
                import_text(f"(Guid={guid_export()},SequenceID=0,ResolveParentIndex=-1)")
                return binding_id
            binding_id.set_editor_property("guid", guid)
            binding_id.set_editor_property("sequence_id", 0)
            binding_id.set_editor_property("resolve_parent_index", -1)
            return binding_id
        except Exception:
            pass
    return getattr(binding, "binding_id", None)


def _asset_load_candidates(path: str) -> list[str]:
    candidates = [path]
    if path.startswith("/Game/") and "." not in path.rsplit("/", 1)[-1]:
        candidates.append(f"{path}.{path.rsplit('/', 1)[-1]}")
    return candidates


def _load_asset(path: str):
    asset = None
    for candidate in _asset_load_candidates(path):
        asset = unreal.EditorAssetLibrary.load_asset(candidate)
        if asset is not None:
            break
    if asset is None:
        raise RuntimeError(f"Asset not found: {path}")
    return asset


def _mesh_material_interfaces(mesh_asset) -> list[tuple[int, object]]:
    get_num_materials = getattr(mesh_asset, "get_num_materials", None)
    get_material = getattr(mesh_asset, "get_material", None)
    materials: list[tuple[int, object]] = []
    if callable(get_num_materials) and callable(get_material):
        try:
            material_count = int(get_num_materials())
        except Exception:
            material_count = 0
        for slot_index in range(max(0, material_count)):
            try:
                material = get_material(slot_index)
            except Exception:
                material = None
            if material is not None:
                materials.append((slot_index, material))
        if materials:
            return materials

    try:
        skeletal_materials = mesh_asset.get_editor_property("materials")
    except Exception:
        skeletal_materials = []
    for slot_index, slot in enumerate(skeletal_materials or []):
        material = None
        get_editor_property = getattr(slot, "get_editor_property", None)
        if callable(get_editor_property):
            for property_name in ("material_interface", "material"):
                try:
                    material = get_editor_property(property_name)
                except Exception:
                    material = None
                if material is not None:
                    break
        if material is not None:
            materials.append((slot_index, material))
    return materials


def _apply_mesh_materials(component, mesh_asset) -> None:
    set_material = getattr(component, "set_material", None)
    if not callable(set_material):
        return
    for slot_index, material in _mesh_material_interfaces(mesh_asset):
        try:
            set_material(slot_index, material)
        except Exception:
            continue


def _ue_asset_path(asset) -> str | None:
    if asset is None:
        return None
    get_path_name = getattr(asset, "get_path_name", None)
    if callable(get_path_name):
        try:
            return str(get_path_name())
        except Exception:
            pass
    get_name = getattr(asset, "get_name", None)
    if callable(get_name):
        try:
            return str(get_name())
        except Exception:
            pass
    return str(asset)


def _asset_skeleton(asset):
    if asset is None:
        return None
    get_editor_property = getattr(asset, "get_editor_property", None)
    if callable(get_editor_property):
        try:
            skeleton = get_editor_property("skeleton")
            if skeleton is not None:
                return skeleton
        except Exception:
            pass
    get_skeleton = getattr(asset, "get_skeleton", None)
    if callable(get_skeleton):
        try:
            return get_skeleton()
        except Exception:
            pass
    animation_extensions = getattr(unreal, "AnimationAssetExtensions", None)
    extension_get_skeleton = getattr(animation_extensions, "get_skeleton", None)
    if callable(extension_get_skeleton):
        try:
            return extension_get_skeleton(asset)
        except Exception:
            pass
    return None


def _skeletal_asset_compatibility(mesh_asset, animation_asset) -> dict:
    mesh_skeleton = _asset_skeleton(mesh_asset)
    animation_skeleton = _asset_skeleton(animation_asset)
    mesh_skeleton_path = _ue_asset_path(mesh_skeleton)
    animation_skeleton_path = _ue_asset_path(animation_skeleton)
    if not mesh_skeleton_path or not animation_skeleton_path:
        return {
            "passed": False,
            "reason": "skeletal_asset_skeleton_unavailable",
            "mesh_asset": _ue_asset_path(mesh_asset),
            "animation_asset": _ue_asset_path(animation_asset),
            "mesh_skeleton": mesh_skeleton_path,
            "animation_skeleton": animation_skeleton_path,
        }
    passed = mesh_skeleton_path == animation_skeleton_path
    return {
        "passed": passed,
        "reason": "compatible" if passed else "skeletal_animation_skeleton_mismatch",
        "mesh_asset": _ue_asset_path(mesh_asset),
        "animation_asset": _ue_asset_path(animation_asset),
        "mesh_skeleton": mesh_skeleton_path,
        "animation_skeleton": animation_skeleton_path,
    }


def _stable_variant_index(seed: str, modulo: int) -> int:
    if modulo <= 0:
        return 0
    total = 0
    for index, char in enumerate(str(seed)):
        total += (index + 1) * ord(char)
    return total % modulo


PEDESTRIAN_MATERIAL_PALETTES = {
    "skin": [
        [0.58, 0.39, 0.29],
        [0.46, 0.29, 0.20],
        [0.72, 0.52, 0.39],
        [0.36, 0.22, 0.16],
        [0.64, 0.45, 0.33],
        [0.52, 0.34, 0.24],
    ],
    "hair": [
        [0.04, 0.035, 0.03],
        [0.18, 0.11, 0.065],
        [0.42, 0.30, 0.16],
        [0.62, 0.50, 0.30],
        [0.12, 0.10, 0.09],
    ],
    "top": [
        [0.12, 0.20, 0.32],
        [0.42, 0.12, 0.10],
        [0.16, 0.30, 0.22],
        [0.55, 0.48, 0.38],
        [0.08, 0.08, 0.09],
        [0.72, 0.68, 0.58],
        [0.22, 0.18, 0.36],
    ],
    "bottom": [
        [0.06, 0.08, 0.12],
        [0.08, 0.14, 0.25],
        [0.18, 0.17, 0.15],
        [0.20, 0.23, 0.18],
        [0.30, 0.26, 0.20],
    ],
    "shoe": [
        [0.025, 0.025, 0.025],
        [0.13, 0.08, 0.045],
        [0.42, 0.39, 0.33],
        [0.78, 0.74, 0.66],
    ],
    "accessory": [
        [0.03, 0.03, 0.035],
        [0.32, 0.23, 0.15],
        [0.48, 0.42, 0.32],
        [0.12, 0.16, 0.20],
    ],
    "detail": [
        [0.88, 0.84, 0.76],
        [0.04, 0.04, 0.04],
        [0.30, 0.24, 0.18],
    ],
    "single_outfit": [
        [0.05, 0.07, 0.10],
        [0.08, 0.13, 0.22],
        [0.18, 0.08, 0.12],
        [0.12, 0.18, 0.13],
        [0.16, 0.17, 0.19],
    ],
}
_PEDESTRIAN_SOLID_MATERIAL_CACHE = {}


def _pedestrian_material_role(source: str, mesh_path: str, slot_index: int, material_path: str | None, material_count: int) -> str:
    text = f"{source} {mesh_path} {material_path or ''}".lower()
    if source == "fab_free_casual_girl_complete" and "mi_body" in text:
        return "top"
    if material_count <= 1:
        return "single_outfit"
    if any(token in text for token in ["hair", "scalp", "babyhair", "eyelash", "eyebrow"]):
        return "hair"
    if any(token in text for token in ["eye", "cornea", "tearline", "teeth", "tongue", "nail"]):
        return "detail"
    if any(token in text for token in ["boot", "shoe", "sneaker"]):
        return "shoe"
    if any(token in text for token in ["shirt", "top", "jacket", "hoodie", "cloth_up"]):
        return "top"
    if any(token in text for token in ["pant", "bottom", "short", "cloth_down"]):
        return "bottom"
    if any(token in text for token in ["belt", "holster", "pocket", "bag", "watch"]):
        return "accessory"
    if any(token in text for token in ["skin", "face", "head", "body", "arm", "neck"]):
        return "skin"
    return ["top", "bottom", "accessory", "shoe"][slot_index % 4]


def _pedestrian_material_profile(actor_name: str, role: str, slot_index: int) -> dict:
    palette = PEDESTRIAN_MATERIAL_PALETTES.get(role) or PEDESTRIAN_MATERIAL_PALETTES["single_outfit"]
    palette_index = _stable_variant_index(f"{actor_name}:{role}:{slot_index}", len(palette))
    color = palette[palette_index]
    return {
        "material_label": f"ped_{role}_{palette_index:02d}",
        "color": color,
        "roughness": 0.74 if role in {"skin", "hair"} else 0.66,
        "specular": 0.28 if role == "skin" else 0.18,
        "used_with_skeletal_mesh": True,
        "reuse_existing_if_present": False,
    }


def _solid_pedestrian_material(profile: dict):
    cache_key = (
        str(profile.get("material_label", "")),
        tuple(float(value) for value in profile.get("color", [])),
        float(profile.get("roughness", 0.0) or 0.0),
        float(profile.get("specular", 0.0) or 0.0),
    )
    if cache_key in _PEDESTRIAN_SOLID_MATERIAL_CACHE:
        return _PEDESTRIAN_SOLID_MATERIAL_CACHE[cache_key]
    try:
        from cineu_world_ops import _solid_material_for_profile

        material = _solid_material_for_profile(profile)
        if material is not None:
            _PEDESTRIAN_SOLID_MATERIAL_CACHE[cache_key] = material
        return material
    except Exception:
        return None


def _pedestrian_slot_material_fallback_enabled(person: dict | None) -> bool:
    if not PEDESTRIAN_SLOT_MATERIAL_FALLBACK or not person:
        return False
    source = str(person.get("source", ""))
    if source in PEDESTRIAN_SLOT_MATERIAL_FALLBACK_SOURCES:
        return True
    mesh_path = str(person.get("mesh", ""))
    return mesh_path in {ARIA_BLAKE_MESH, FREE_CASUAL_GIRL_MESH, *CITYPARK_MAN_MESHES, *SCANNED_3D_PEOPLE_MESHES}


def _apply_pedestrian_slot_material_fallback(component, mesh_asset, person: dict | None, warnings: list[dict]) -> list[dict]:
    if not _pedestrian_slot_material_fallback_enabled(person):
        return []
    set_material = getattr(component, "set_material", None)
    if not callable(set_material):
        return []
    material_slots = _mesh_material_interfaces(mesh_asset)
    if not material_slots:
        get_num_materials = getattr(component, "get_num_materials", None)
        get_material = getattr(component, "get_material", None)
        try:
            material_count = int(get_num_materials()) if callable(get_num_materials) else 0
        except Exception:
            material_count = 0
        if material_count <= 0:
            return []
        for slot_index in range(material_count):
            material = None
            if callable(get_material):
                try:
                    material = get_material(slot_index)
                except Exception:
                    material = None
            material_slots.append((slot_index, material))
    material_count = max(slot_index for slot_index, _ in material_slots) + 1
    actor_name = str(person.get("name", "pedestrian")) if person else "pedestrian"
    source = str(person.get("source", "")) if person else ""
    mesh_path = str(person.get("mesh", "")) if person else ""
    overrides = []
    for slot_index, original_material in material_slots:
        original_path = _ue_asset_path(original_material)
        role = _pedestrian_material_role(source, mesh_path, slot_index, original_path, material_count)
        profile = _pedestrian_material_profile(actor_name, role, slot_index)
        replacement_material = _solid_pedestrian_material(profile)
        if replacement_material is None:
            warnings.append(
                {
                    "actor": actor_name,
                    "reason": "pedestrian_slot_material_fallback_failed",
                    "slot": slot_index,
                    "role": role,
                }
            )
            continue
        try:
            set_material(slot_index, replacement_material)
        except Exception as exc:
            warnings.append(
                {
                    "actor": actor_name,
                    "reason": "pedestrian_slot_material_set_failed",
                    "slot": slot_index,
                    "role": role,
                    "error": str(exc),
                }
            )
            continue
        overrides.append(
            {
                "slot": slot_index,
                "role": role,
                "original_material": original_path,
                "replacement_material": _ue_asset_path(replacement_material),
            }
        )
    return overrides


def _prepare_skeletal_component_for_capture(component) -> None:
    for method_name, args in (
        ("set_update_animation_in_editor", (True,)),
        ("set_component_tick_enabled", (True,)),
    ):
        method = getattr(component, method_name, None)
        if not callable(method):
            continue
        try:
            method(*args)
        except Exception:
            continue
    tick_enum = getattr(unreal, "VisibilityBasedAnimTickOption", None)
    if tick_enum is not None:
        for option_name in ("ALWAYS_TICK_POSE_AND_REFRESH_BONES", "ALWAYS_TICK_POSE"):
            option_value = getattr(tick_enum, option_name, None)
            if option_value is not None:
                _try_set_property(component, "visibility_based_anim_tick_option", option_value)
                break


def _set_skeletal_component_mesh(component, mesh_asset) -> None:
    set_skinned_asset = getattr(component, "set_skinned_asset_and_update", None)
    if callable(set_skinned_asset):
        try:
            set_skinned_asset(mesh_asset)
        except TypeError:
            set_skinned_asset(mesh_asset, True)
    else:
        component.set_skeletal_mesh(mesh_asset)
    _apply_mesh_materials(component, mesh_asset)
    _prepare_skeletal_component_for_capture(component)


def _try_load_asset(path: str):
    if not path:
        return None
    for candidate in _asset_load_candidates(path):
        try:
            asset = unreal.EditorAssetLibrary.load_asset(candidate)
            if asset is not None:
                return asset
        except Exception:
            continue
    return None


def _dedupe_paths(paths: list[str]) -> list[str]:
    result = []
    seen = set()
    for path in paths:
        if not path or path in seen:
            continue
        seen.add(path)
        result.append(path)
    return result


def _fallback_skeletal_mesh_candidates(preferred_mesh: str) -> list[str]:
    return _dedupe_paths(
        [
            preferred_mesh,
            *SCANNED_3D_PEOPLE_MESHES,
            ARIA_BLAKE_MESH,
            FREE_CASUAL_GIRL_MESH,
            *MAN_MESHES,
            *WOMAN_MESHES,
        ]
    )


def _scanned_animation_for_motion(motion: str) -> str:
    motion_text = str(motion or "").lower()
    if "idle" in motion_text or "sit" in motion_text or "phone" in motion_text or "talk" in motion_text:
        return SCANNED_3D_PEOPLE_ANIMS["idle"]
    return SCANNED_3D_PEOPLE_ANIMS["walk"]


def _resolve_skeletal_person_assets(person: dict, warnings: list[dict]) -> object:
    preferred_mesh = str(person.get("mesh") or "")
    for mesh_path in _fallback_skeletal_mesh_candidates(preferred_mesh):
        mesh_asset = _try_load_asset(mesh_path)
        if mesh_asset is None:
            continue
        if mesh_path != preferred_mesh:
            warnings.append(
                {
                    "actor": person.get("name"),
                    "reason": "skeletal_mesh_fallback_used",
                    "missing_mesh": preferred_mesh,
                    "replacement_mesh": mesh_path,
                }
            )
            person["mesh"] = mesh_path
            if mesh_path in SCANNED_3D_PEOPLE_MESHES:
                replacement_animation = _scanned_animation_for_motion(str(person.get("motion", "")))
                if person.get("animation") != replacement_animation:
                    warnings.append(
                        {
                            "actor": person.get("name"),
                            "reason": "skeletal_animation_fallback_used",
                            "original_animation": person.get("animation"),
                            "replacement_animation": replacement_animation,
                        }
                    )
                    person["animation"] = replacement_animation
        return mesh_asset
    raise RuntimeError(f"Asset not found: {preferred_mesh}")


def _try_set_property(obj, name: str, value) -> bool:
    try:
        obj.set_editor_property(name, value)
        return True
    except Exception:
        pass
    try:
        setattr(obj, name, value)
        return True
    except Exception:
        return False


def _debug_actor_step(message: str) -> None:
    if not DEBUG_ACTORS:
        return
    logger = getattr(unreal, "log", None)
    if logger is not None:
        logger(f"CINEU_DEBUG_ACTOR {message}")


def _current_world_name() -> str | None:
    try:
        world = unreal.EditorLevelLibrary.get_editor_world()
        if world is not None:
            return str(world.get_path_name())
    except Exception:
        pass
    return None


def _make_generated_level(scene_id: str, source_level: str, warnings: list[dict]) -> str:
    unreal.EditorAssetLibrary.make_directory(ASSET_ROOT)
    current_world = _current_world_name()
    if current_world is None or not current_world.startswith(source_level):
        unreal.EditorLevelLibrary.load_level(source_level)
    warnings.append(
        {
            "reason": "transient_current_world_layout",
            "scene_id": scene_id,
            "source_level": source_level,
            "note": "Avoids duplicating and reloading maps in the same commandlet, which can leave the previous world alive in UE 5.5.",
        }
    )
    return source_level


def _streaming_level_name(level: object) -> str:
    parts: list[str] = [str(level)]
    for method_name in ("get_path_name", "get_outer"):
        method = getattr(level, method_name, None)
        if callable(method):
            try:
                parts.append(str(method()))
            except Exception:
                pass
    for method_name in ("get_world_asset_package_name", "get_world_asset_package_f_name"):
        method = getattr(level, method_name, None)
        if callable(method):
            try:
                parts.append(str(method()))
            except Exception:
                pass
    for property_name in ("world_asset", "package_name_to_load", "editor_path_owner"):
        try:
            parts.append(str(level.get_editor_property(property_name)))
        except Exception:
            pass
    return " ".join(parts)


def _set_streaming_level_flag(level: object, method_name: str, property_name: str, value: bool) -> None:
    method = getattr(level, method_name, None)
    if callable(method):
        method(value)
        return
    _try_set_property(level, property_name, value)


def _configure_streaming_level_visibility(spec: dict, warnings: list[dict]) -> None:
    rules = spec.get("streaming_level_visibility") or []
    if not rules:
        return
    try:
        world = unreal.EditorLevelLibrary.get_editor_world()
        get_streaming_levels = getattr(world, "get_streaming_levels", None)
        if callable(get_streaming_levels):
            streaming_levels = list(get_streaming_levels() or [])
            visibility_api = "streaming_level"
        else:
            streaming_levels = list(unreal.EditorLevelUtils.get_levels(world) or [])
            visibility_api = "editor_level"
    except Exception as exc:
        warnings.append({"reason": "streaming_level_visibility_failed", "error": str(exc)})
        return
    for rule in rules:
        needle = str(rule["contains"]).lower()
        visible = bool(rule.get("visible", True))
        loaded = bool(rule.get("loaded", visible))
        matched = False
        for level in streaming_levels:
            if needle not in _streaming_level_name(level).lower():
                continue
            matched = True
            try:
                if visibility_api == "editor_level":
                    try:
                        unreal.EditorLevelUtils.set_level_visibility(level, visible, True)
                    except TypeError:
                        unreal.EditorLevelUtils.set_level_visibility(level, visible, True, True)
                else:
                    _set_streaming_level_flag(level, "set_should_be_loaded", "should_be_loaded", loaded)
                    _set_streaming_level_flag(level, "set_should_be_visible", "should_be_visible", visible)
            except Exception as exc:
                warnings.append({"reason": "streaming_level_visibility_rule_failed", "level_contains": rule["contains"], "error": str(exc)})
        if not matched:
            warnings.append({"reason": "streaming_level_visibility_rule_unmatched", "level_contains": rule["contains"]})
    try:
        flush = getattr(world, "flush_level_streaming", None)
        if callable(flush):
            flush()
    except Exception as exc:
        warnings.append({"reason": "streaming_level_visibility_flush_failed", "error": str(exc)})


def _add_sequence_level_visibility(
    seq: object,
    rules: list[dict],
    frame_count: int,
    warnings: list[dict],
) -> list[dict]:
    if not rules:
        return []
    track_type = getattr(unreal, "MovieSceneLevelVisibilityTrack", None)
    visibility_enum = getattr(unreal, "LevelVisibility", None)
    if track_type is None or visibility_enum is None:
        warnings.append({"reason": "sequence_level_visibility_api_unavailable"})
        return []
    try:
        add_track = getattr(seq, "add_track", None) or getattr(seq, "add_master_track", None)
        if add_track is None:
            raise RuntimeError("LevelSequence track API unavailable")
        track = add_track(track_type)
        state = []
        for row_index, rule in enumerate(rules):
            level_names = [str(name) for name in rule.get("level_names", []) if str(name)]
            if not level_names:
                continue
            visible = bool(rule.get("visible", True))
            section = track.add_section()
            section.set_range(0, int(frame_count))
            section.set_level_names(level_names)
            section.set_visibility(visibility_enum.VISIBLE if visible else visibility_enum.HIDDEN)
            set_row_index = getattr(section, "set_row_index", None)
            if callable(set_row_index):
                set_row_index(row_index)
            state.append({"level_names": level_names, "visible": visible, "range": [0, int(frame_count)]})
        return state
    except Exception as exc:
        warnings.append({"reason": "sequence_level_visibility_failed", "error": str(exc)})
        return []


def _disable_existing_post_process_volumes(spec: dict, warnings: list[dict]) -> None:
    if not spec.get("disable_existing_post_process"):
        return
    try:
        actors = unreal.EditorLevelLibrary.get_all_level_actors()
    except Exception as exc:
        warnings.append({"reason": "post_process_disable_scan_failed", "error": str(exc)})
        return
    disabled = 0
    for actor in actors:
        try:
            class_name = actor.get_class().get_name()
        except Exception:
            class_name = type(actor).__name__
        if "PostProcess" not in str(class_name):
            continue
        try:
            actor.set_actor_hidden_in_game(True)
        except Exception:
            pass
        for prop, value in [("enabled", False), ("blend_weight", 0.0)]:
            try:
                actor.set_editor_property(prop, value)
            except Exception:
                pass
        try:
            component = actor.get_component_by_class(unreal.PostProcessComponent)
        except Exception:
            component = None
        if component is not None:
            for prop, value in [("enabled", False), ("blend_weight", 0.0)]:
                try:
                    component.set_editor_property(prop, value)
                except Exception as exc:
                    warnings.append({"reason": "post_process_disable_property_failed", "property": prop, "error": str(exc)})
        disabled += 1
    if disabled:
        warnings.append({"reason": "post_process_volumes_disabled", "count": disabled})


def _disable_existing_lights(spec: dict, warnings: list[dict]) -> None:
    if not spec.get("disable_existing_lights"):
        return
    try:
        actors = unreal.EditorLevelLibrary.get_all_level_actors()
    except Exception as exc:
        warnings.append({"reason": "existing_light_disable_scan_failed", "error": str(exc)})
        return
    light_component_classes = [
        getattr(unreal, name, None)
        for name in ["DirectionalLightComponent", "SkyLightComponent", "PointLightComponent", "SpotLightComponent"]
    ]
    light_component_classes = [component_class for component_class in light_component_classes if component_class is not None]
    disabled = 0
    for actor in actors:
        try:
            if str(actor.get_actor_label()).startswith("CineU_"):
                continue
        except Exception:
            pass
        components = []
        for component_class in light_component_classes:
            try:
                component = actor.get_component_by_class(component_class)
            except Exception:
                component = None
            if component is not None:
                components.append(component)
        if not components:
            continue
        try:
            actor.set_actor_hidden_in_game(True)
        except Exception:
            pass
        for component in components:
            for prop, value in [("intensity", 0.0), ("cast_shadows", False)]:
                try:
                    component.set_editor_property(prop, value)
                except Exception:
                    pass
            set_visibility = getattr(component, "set_visibility", None)
            if callable(set_visibility):
                try:
                    set_visibility(False, True)
                except TypeError:
                    set_visibility(False)
        disabled += 1
    if disabled:
        warnings.append({"reason": "existing_lights_disabled", "count": disabled})


def _hide_existing_scene_actors(spec: dict, warnings: list[dict], sequence=None) -> list[dict]:
    exact_labels = {str(label).lower() for label in spec.get("hide_existing_actor_labels", [])}
    label_tokens = [str(token).lower() for token in spec.get("hide_existing_actor_label_contains", [])]
    if not exact_labels and not label_tokens:
        return []
    try:
        actors = unreal.EditorLevelLibrary.get_all_level_actors()
    except Exception as exc:
        warnings.append({"reason": "existing_actor_hide_scan_failed", "error": str(exc)})
        return []
    hidden = []
    visibility_bindings = []
    component_classes = [
        getattr(unreal, name, None)
        for name in ["StaticMeshComponent", "InstancedStaticMeshComponent", "PrimitiveComponent"]
    ]
    component_classes = [component_class for component_class in component_classes if component_class is not None]
    for actor in actors:
        try:
            label = str(actor.get_actor_label())
        except Exception:
            continue
        label_lower = label.lower()
        if label_lower.startswith("cineu_"):
            continue
        if label_lower not in exact_labels and not any(token in label_lower for token in label_tokens):
            continue
        if sequence is not None:
            binding_name = f"CineU_Hidden_{actor.get_name()}_{len(visibility_bindings):03d}"
            binding = sequence.add_possessable(actor)
            _set_sequence_binding_names(binding, binding_name, warnings)
            track = binding.add_track(unreal.MovieSceneVisibilityTrack)
            track.set_property_name_and_path("bHidden", "bHidden")
            section = track.add_section()
            section.set_range(-1, FRAME_COUNT)
            channels = _channels_for_section(section)
            if len(channels) != 1:
                raise RuntimeError(f"Visibility channel unavailable for {label}")
            # UE's visibility curve stores visible, despite the bHidden property name.
            channels[0].set_default(False)
            visibility_bindings.append({"binding": binding_name, "label": label, "actor_path": actor.get_path_name()})
        try:
            actor.set_actor_hidden_in_game(True)
        except Exception:
            pass
        try:
            actor.set_is_temporarily_hidden_in_editor(True)
        except Exception:
            pass
        for component_class in component_classes:
            try:
                components = actor.get_components_by_class(component_class)
            except Exception:
                components = []
            for component in components or []:
                set_visibility = getattr(component, "set_visibility", None)
                if callable(set_visibility):
                    try:
                        set_visibility(False, True)
                    except TypeError:
                        set_visibility(False)
                for prop, value in [("visible", False), ("hidden_in_game", True)]:
                    try:
                        component.set_editor_property(prop, value)
                    except Exception:
                        pass
        hidden.append(label)
    if hidden:
        warnings.append({"reason": "existing_scene_actors_hidden", "labels": hidden})
    return visibility_bindings


def _camera_post_process_snapshot(camera, profile: dict) -> dict:
    component = camera.get_cine_camera_component()
    if component is None:
        component = unreal.find_object(camera, "CameraComponent")
    settings = component.get_editor_property("post_process_settings")
    values = {"post_process_blend_weight": float(component.get_editor_property("post_process_blend_weight"))}
    names = ["local_exposure_method"]
    names.extend(f"local_exposure_{key}" for key in profile if key != "method")
    for name in names:
        for prop in (name, f"override_{name}"):
            value = settings.get_editor_property(prop)
            values[prop] = value if isinstance(value, (bool, int, float, str)) else str(value)
    return values


def _audit_sequence_visual_state(sequence, expected_cameras: dict, expected_visibility: list[dict]) -> dict:
    issues = []
    if not expected_cameras and not expected_visibility:
        return {"passed": True, "issues": [], "camera_count": 0, "hidden_actor_count": 0}
    bindings = {name: binding for binding in sequence.get_bindings() for name in _sequence_object_names(binding)}
    for name, expected in expected_cameras.items():
        try:
            binding = bindings[name]
            camera = unreal.MovieSceneBindingExtensions.get_object_template(binding)
            actual = _camera_post_process_snapshot(camera, expected["profile"])
            for prop, value in expected["properties"].items():
                observed = actual.get(prop)
                equal = math.isclose(observed, value, rel_tol=1e-6, abs_tol=1e-6) if isinstance(value, float) and isinstance(observed, (int, float)) else observed == value
                if not equal:
                    issues.append({"reason": "cold_camera_post_process_mismatch", "camera": name, "property": prop, "expected": value, "actual": observed})
        except Exception as exc:
            issues.append({"reason": "cold_camera_post_process_read_failed", "camera": name, "error": str(exc)})
    for expected in expected_visibility:
        try:
            binding = bindings[expected["binding"]]
            tracks = [track for track in binding.get_tracks() if isinstance(track, unreal.MovieSceneVisibilityTrack)]
            sections = [section for track in tracks for section in track.get_sections()]
            if len(sections) != 1:
                raise RuntimeError("Expected one visibility section")
            section = sections[0]
            channel = _channels_for_section(section)[0]
            if channel.get_keys() or channel.get_default() is not False or section.get_start_frame() > -1 or section.get_end_frame() < FRAME_COUNT:
                raise RuntimeError("Hidden visibility not constant over the whole sequence")
        except Exception as exc:
            issues.append({"reason": "cold_actor_visibility_failed", "actor": expected["label"], "error": str(exc)})
    return {"passed": not issues, "issues": issues, "camera_count": len(expected_cameras), "hidden_actor_count": len(expected_visibility)}


def _save_current_level(warnings: list[dict]) -> None:
    for owner_name in ["EditorLoadingAndSavingUtils", "EditorLevelLibrary"]:
        owner = getattr(unreal, owner_name, None)
        save_current_level = getattr(owner, "save_current_level", None) if owner is not None else None
        if save_current_level is not None:
            try:
                save_current_level()
                return
            except Exception as exc:
                warnings.append({"reason": "save_current_level_failed", "api": owner_name, "error": str(exc)})
    try:
        unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    except Exception as exc:
        warnings.append({"reason": "save_dirty_packages_failed", "error": str(exc)})


def _prime_skeletal_materials_for_capture(warnings: list[dict]) -> tuple[int, int]:
    material_editing = getattr(unreal, "MaterialEditingLibrary", None)
    update_instance = getattr(material_editing, "update_material_instance", None)
    recompile_material = getattr(material_editing, "recompile_material", None)
    component_class = getattr(unreal, "SkeletalMeshComponent", None)
    if component_class is None or not callable(recompile_material):
        return 0, 0
    try:
        actors = list(unreal.EditorLevelLibrary.get_all_level_actors() or [])
    except Exception as exc:
        warnings.append({"reason": "skeletal_material_prime_actor_scan_failed", "error": str(exc)})
        return 0, 0

    updated_instances: set[str] = set()
    recompiled_bases: set[str] = set()
    for actor in actors:
        try:
            component = actor.get_component_by_class(component_class)
        except Exception:
            continue
        if component is None:
            continue
        try:
            material_count = int(component.get_num_materials())
        except Exception:
            continue
        for slot_index in range(material_count):
            try:
                material = component.get_material(slot_index)
            except Exception:
                continue
            if material is None:
                continue
            material_path = _ue_asset_path(material)
            get_base_material = getattr(material, "get_base_material", None)
            try:
                base_material = get_base_material() if callable(get_base_material) else material
            except Exception:
                base_material = material
            base_path = _ue_asset_path(base_material)
            if callable(update_instance) and base_material is not material and material_path not in updated_instances:
                try:
                    update_instance(material)
                    updated_instances.add(material_path)
                except Exception as exc:
                    warnings.append({"reason": "skeletal_material_instance_update_failed", "material": material_path, "error": str(exc)})
            if base_material is not None and base_path not in recompiled_bases:
                try:
                    recompile_material(base_material)
                    recompiled_bases.add(base_path)
                except Exception as exc:
                    warnings.append({"reason": "skeletal_base_material_recompile_failed", "material": base_path, "error": str(exc)})
    return len(updated_instances), len(recompiled_bases)


def _wait_for_render_asset_readiness(warnings: list[dict]) -> None:
    commands_executed: list[str] = []
    compiler_finish_calls: list[str] = []
    world = None
    try:
        get_world = getattr(unreal.EditorLevelLibrary, "get_editor_world", None)
        if callable(get_world):
            world = get_world()
    except Exception as exc:
        warnings.append({"reason": "asset_readiness_world_lookup_failed", "error": str(exc)})
    execute_console_command = getattr(getattr(unreal, "SystemLibrary", None), "execute_console_command", None)
    if callable(execute_console_command):
        for command in [
            "r.TextureStreaming 1",
            "r.Streaming.FullyLoadUsedTextures 1",
            *EXTRA_RENDER_CVARS,
        ]:
            try:
                execute_console_command(world, command)
                commands_executed.append(command)
            except Exception as exc:
                warnings.append({"reason": "asset_readiness_console_command_failed", "command": command, "error": str(exc)})

    updated_material_instances, recompiled_base_materials = _prime_skeletal_materials_for_capture(warnings)

    for owner_name in ("AssetCompilingManager", "ShaderCompilingManager"):
        manager_owner = getattr(unreal, owner_name, None)
        manager_candidates = [manager_owner]
        get_manager = getattr(manager_owner, "get", None) if manager_owner is not None else None
        if callable(get_manager):
            try:
                manager_candidates.insert(0, get_manager())
            except Exception as exc:
                warnings.append({"reason": "asset_compilation_manager_lookup_failed", "manager": owner_name, "error": str(exc)})
        for manager in manager_candidates:
            if manager is None:
                continue
            for method_name in (
                "finish_all_compilations",
                "finish_all_compilation",
                "finish_compilation",
                "finish_all_asset_compilations",
                "finish_all_asset_compilation",
            ):
                finish_all = getattr(manager, method_name, None)
                if not callable(finish_all):
                    continue
                try:
                    finish_all()
                    compiler_finish_calls.append(f"{owner_name}.{method_name}")
                    break
                except Exception as exc:
                    warnings.append({"reason": "asset_compilation_finish_failed", "manager": owner_name, "method": method_name, "error": str(exc)})
            if compiler_finish_calls and compiler_finish_calls[-1].startswith(f"{owner_name}."):
                break

    try:
        unreal.EditorLevelLibrary.editor_invalidate_viewports()
    except Exception:
        pass
    if ASSET_READY_WAIT_SEC > 0.0:
        deadline = time.monotonic() + ASSET_READY_WAIT_SEC
        while time.monotonic() < deadline:
            try:
                unreal.EditorLevelLibrary.editor_invalidate_viewports()
            except Exception:
                pass
            time.sleep(min(0.25, max(0.0, deadline - time.monotonic())))

    warnings.append(
        {
            "reason": "render_asset_readiness_wait",
            "wait_sec": ASSET_READY_WAIT_SEC,
            "commands_executed": commands_executed,
            "compiler_finish_attempted": bool(compiler_finish_calls),
            "compiler_finish_calls": compiler_finish_calls,
            "skeletal_material_instances_updated": updated_material_instances,
            "skeletal_base_materials_recompiled": recompiled_base_materials,
        }
    )


def _delete_sequence(sequence_path: str) -> None:
    if unreal.EditorAssetLibrary.does_asset_exist(sequence_path):
        unreal.EditorAssetLibrary.delete_asset(sequence_path)


def _safe_asset_token(value: str) -> str:
    token = "".join(ch if ch.isalnum() else "_" for ch in str(value))
    return "_".join(part for part in token.split("_") if part)


def _create_sequence(scene_id: str, end_frame: int) -> tuple[str, object]:
    camera_suffix = f"_{_safe_asset_token(CAMERA_FILTER)}" if CAMERA_FILTER else ""
    sequence_path = f"{ASSET_ROOT}/SEQ_CineU_Hillside_{scene_id}_{MODE}{camera_suffix}"
    _delete_sequence(sequence_path)
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    seq = asset_tools.create_asset(
        sequence_path.rsplit("/", 1)[1],
        ASSET_ROOT,
        unreal.LevelSequence,
        unreal.LevelSequenceFactoryNew(),
    )
    seq.set_display_rate(unreal.FrameRate(FPS, 1))
    seq.set_playback_start(0)
    seq.set_playback_end(end_frame)
    return sequence_path, seq


def _spawn_skeletal_actor(name: str, mesh_path: str, start: list[float], rotation: list[float], scale: float, mesh_asset: object | None = None) -> object:
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.SkeletalMeshActor, _v(start), _r(rotation))
    actor.set_actor_label(name)
    actor.set_actor_scale3d(unreal.Vector(scale, scale, scale))
    component = actor.get_component_by_class(unreal.SkeletalMeshComponent)
    resolved_mesh = mesh_asset or _load_asset(mesh_path)
    _set_skeletal_component_mesh(component, resolved_mesh)
    return actor


def _add_modular_skeletal_component(actor, part: dict, warnings: list[dict]) -> None:
    host_component = actor.get_component_by_class(unreal.SkeletalMeshComponent)
    if host_component is None:
        warnings.append({"actor": part.get("host_actor_name"), "part": part.get("actor_name"), "reason": "host_skeletal_component_missing"})
        return
    component = None
    add_component = getattr(actor, "add_component_by_class", None)
    if add_component is not None:
        try:
            component = add_component(unreal.SkeletalMeshComponent, False, unreal.Transform(), False)
        except Exception as exc:
            warnings.append({"part": part.get("actor_name"), "reason": "add_component_by_class_failed", "error": str(exc)})
    if component is None:
        try:
            component = unreal.SkeletalMeshComponent(actor)
            add_instance_component = getattr(actor, "add_instance_component", None)
            if add_instance_component is not None:
                add_instance_component(component)
            register_component = getattr(component, "register_component", None)
            if register_component is not None:
                register_component()
        except Exception as exc:
            warnings.append({"part": part.get("actor_name"), "reason": "skeletal_component_create_failed", "error": str(exc)})
            return
    try:
        component.set_editor_property("component_tags", [str(part.get("actor_name", "modular_part"))])
    except Exception:
        pass
    try:
        resolved_mesh = _load_asset(str(part["mesh_path"]))
        _set_skeletal_component_mesh(component, resolved_mesh)
    except Exception as exc:
        warnings.append({"part": part.get("actor_name"), "reason": "modular_part_mesh_load_failed", "mesh": part.get("mesh_path"), "error": str(exc)})
        return
    for method_name in ("set_leader_pose_component", "set_master_pose_component"):
        method = getattr(component, method_name, None)
        if method is None:
            continue
        try:
            method(host_component)
            break
        except Exception as exc:
            warnings.append({"part": part.get("actor_name"), "reason": f"{method_name}_failed", "error": str(exc)})
    try:
        component.attach_to_component(
            host_component,
            "",
            unreal.AttachmentRule.SNAP_TO_TARGET,
            unreal.AttachmentRule.SNAP_TO_TARGET,
            unreal.AttachmentRule.SNAP_TO_TARGET,
            False,
        )
    except Exception as exc:
        warnings.append({"part": part.get("actor_name"), "reason": "modular_part_attach_failed", "error": str(exc)})


def _spawn_blueprint_actor(name: str, blueprint_path: str, start: list[float], rotation: list[float], scale: float) -> object:
    blueprint = _load_asset(blueprint_path)
    spawn_from_object = getattr(unreal.EditorLevelLibrary, "spawn_actor_from_object", None)
    actor = None
    if spawn_from_object is not None:
        actor = spawn_from_object(blueprint, _v(start), _r(rotation))
    if actor is None:
        actor_class = getattr(blueprint, "generated_class", None)
        if callable(actor_class):
            actor_class = actor_class()
        if actor_class is None:
            try:
                actor_class = blueprint.get_editor_property("generated_class")
            except Exception:
                actor_class = None
        if actor_class is None:
            raise RuntimeError(f"Blueprint generated class not found: {blueprint_path}")
        actor = unreal.EditorLevelLibrary.spawn_actor_from_class(actor_class, _v(start), _r(rotation))
    if actor is None:
        raise RuntimeError(f"Blueprint actor spawn failed: {blueprint_path}")
    actor.set_actor_label(name)
    actor.set_actor_scale3d(unreal.Vector(scale, scale, scale))
    return actor


def _spawn_static_actor(
    name: str,
    mesh_path: str,
    location: list[float],
    rotation: list[float],
    scale: float,
    material_override: str | None = None,
    material_profile: dict | None = None,
    cast_shadow: bool | None = None,
) -> object:
    mesh = _load_asset(mesh_path)
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.StaticMeshActor, _v(location), _r(rotation))
    actor.set_actor_label(name)
    actor.set_actor_scale3d(unreal.Vector(scale, scale, scale))
    component = actor.get_component_by_class(unreal.StaticMeshComponent)
    if component is None:
        raise RuntimeError(f"StaticMeshComponent not found for spawned actor: {name}")
    set_static_mesh = getattr(component, "set_static_mesh", None)
    if set_static_mesh is not None:
        set_static_mesh(mesh)
    else:
        _try_set_property(component, "static_mesh", mesh)
    material = None
    if material_override:
        material = _load_asset(material_override)
    elif material_profile:
        try:
            from cineu_world_ops import _solid_material_for_profile

            material = _solid_material_for_profile(material_profile)
        except Exception:
            material = None
    if material is not None:
        set_material = getattr(component, "set_material", None)
        if set_material is not None:
            get_num_materials = getattr(component, "get_num_materials", None)
            material_count = int(get_num_materials()) if get_num_materials is not None else 1
            for slot in range(max(1, material_count)):
                set_material(slot, material)
    if cast_shadow is not None:
        _try_set_property(component, "cast_shadow", bool(cast_shadow))
    return actor


def _spawn_scene19_daylight(warnings: list[dict]) -> list[dict]:
    lights = []
    try:
        location = [56500.0, -850.0, 9500.0]
        rotation = [-42.0, -30.0, 0.0]
        sun = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.DirectionalLight, _v(location), _r(rotation))
        sun.set_actor_label("CineU_scene19_daylight_key")
        component = sun.get_component_by_class(unreal.DirectionalLightComponent)
        if component is not None:
            _try_set_property(component, "intensity", 12.0)
            _try_set_property(component, "light_color", unreal.LinearColor(1.0, 0.95, 0.86, 1.0))
        lights.append({"name": "CineU_scene19_daylight_key", "actor": sun, "location": location, "rotation": rotation})
    except Exception as exc:
        warnings.append({"reason": "scene19_daylight_spawn_failed", "light": "directional", "error": str(exc)})
    try:
        location = [56500.0, -850.0, 7200.0]
        rotation = [0.0, 0.0, 0.0]
        sky = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.SkyLight, _v(location), _r(rotation))
        sky.set_actor_label("CineU_scene19_daylight_sky")
        component = sky.get_component_by_class(unreal.SkyLightComponent)
        if component is not None:
            _try_set_property(component, "intensity", 2.4)
        lights.append({"name": "CineU_scene19_daylight_sky", "actor": sky, "location": location, "rotation": rotation})
    except Exception as exc:
        warnings.append({"reason": "scene19_daylight_spawn_failed", "light": "sky", "error": str(exc)})
    try:
        sky_atmosphere_class = getattr(unreal, "SkyAtmosphere", None)
        if sky_atmosphere_class is not None:
            location = [56500.0, -850.0, 0.0]
            rotation = [0.0, 0.0, 0.0]
            atmosphere = unreal.EditorLevelLibrary.spawn_actor_from_class(sky_atmosphere_class, _v(location), _r(rotation))
            atmosphere.set_actor_label("CineU_scene19_daylight_sky_atmosphere")
            lights.append({"name": "CineU_scene19_daylight_sky_atmosphere", "actor": atmosphere, "location": location, "rotation": rotation})
        else:
            warnings.append({"reason": "scene19_daylight_spawn_failed", "light": "sky_atmosphere", "error": "SkyAtmosphere class unavailable"})
    except Exception as exc:
        warnings.append({"reason": "scene19_daylight_spawn_failed", "light": "sky_atmosphere", "error": str(exc)})
    return lights


def _scene19_balcony_fill_light_specs() -> list[dict]:
    return [
        {
            "label": "CineU_scene19_fa020_fill_walkway_key",
            "location": [54200.0, -4200.0, 4600.0],
            "intensity": 2600.0,
            "radius": 5200.0,
        },
        {
            "label": "CineU_scene19_fa020_fill_facade_soft",
            "location": [58800.0, -3600.0, 4700.0],
            "intensity": 2200.0,
            "radius": 5200.0,
        },
        {
            "label": "CineU_scene19_fa020_topdown_fill",
            "location": [56500.0, -2600.0, 7600.0],
            "intensity": 3200.0,
            "radius": 5200.0,
        },
    ]


def _spawn_scene19_balcony_fill_lights(warnings: list[dict]) -> list[dict]:
    lights = []
    for spec in _scene19_balcony_fill_light_specs():
        try:
            rotation = [0.0, 0.0, 0.0]
            light = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.PointLight, _v(spec["location"]), _r(rotation))
            light.set_actor_label(spec["label"])
            component = light.get_component_by_class(unreal.PointLightComponent)
            if component is not None:
                _try_set_property(component, "intensity", spec["intensity"])
                _try_set_property(component, "attenuation_radius", spec["radius"])
                _try_set_property(component, "light_color", unreal.LinearColor(1.0, 0.96, 0.88, 1.0))
                _try_set_property(component, "cast_shadows", False)
            lights.append({"name": spec["label"], "actor": light, "location": spec["location"], "rotation": rotation})
        except Exception as exc:
            warnings.append({"reason": "scene19_fill_light_spawn_failed", "light": spec["label"], "error": str(exc)})
    return lights


def _spawn_scene24_interior_lights(warnings: list[dict]) -> list[dict]:
    lights = []
    light_specs = [
        ("CineU_scene24_upper_hall_key", [93270.0, -3050.0, 4960.0], [0.0, 0.0, 0.0], 260.0, 440.0),
        ("CineU_scene24_upper_storage_fill", [93270.0, -3230.0, 4930.0], [0.0, 0.0, 0.0], 150.0, 340.0),
        ("CineU_scene24_upper_plant_fill", [93280.0, -2850.0, 4950.0], [0.0, 0.0, 0.0], 180.0, 380.0),
    ]
    for label, location, rotation, intensity, radius in light_specs:
        try:
            light = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.PointLight, _v(location), _r(rotation))
            light.set_actor_label(label)
            component = light.get_component_by_class(unreal.PointLightComponent)
            if component is not None:
                _try_set_property(component, "intensity", intensity)
                _try_set_property(component, "attenuation_radius", radius)
                _try_set_property(component, "light_color", unreal.LinearColor(1.0, 0.92, 0.82, 1.0))
            lights.append({"name": label, "actor": light, "location": location, "rotation": rotation})
        except Exception as exc:
            warnings.append({"reason": "scene24_interior_light_spawn_failed", "light": label, "error": str(exc)})
    return lights


def _spawn_production_lights(spec: dict, warnings: list[dict]) -> list[dict]:
    lights = []
    for light_spec in spec.get("extra_lights", []):
        light_type = str(light_spec.get("type", "point"))
        label = str(light_spec["label"])
        location = [float(value) for value in light_spec["location"]]
        rotation = [float(value) for value in light_spec.get("rotation", [0.0, 0.0, 0.0])]
        actor_class = {
            "directional": getattr(unreal, "DirectionalLight", None),
            "sky": getattr(unreal, "SkyLight", None),
            "point": getattr(unreal, "PointLight", None),
            "spot": getattr(unreal, "SpotLight", None),
        }.get(light_type)
        if actor_class is None:
            warnings.append({"reason": "production_light_class_unavailable", "light": label, "type": light_type})
            continue
        try:
            actor = unreal.EditorLevelLibrary.spawn_actor_from_class(actor_class, _v(location), _r(rotation))
            actor.set_actor_label(label)
            component = None
            if component is None:
                for component_class_name in ["DirectionalLightComponent", "SkyLightComponent", "PointLightComponent", "SpotLightComponent"]:
                    component_class = getattr(unreal, component_class_name, None)
                    if component_class is None:
                        continue
                    try:
                        component = actor.get_component_by_class(component_class)
                    except Exception:
                        component = None
                    if component is not None:
                        break
            if component is not None:
                for prop, value in [
                    ("intensity", light_spec.get("intensity")),
                    ("attenuation_radius", light_spec.get("radius")),
                    ("inner_cone_angle", light_spec.get("inner_cone_angle")),
                    ("outer_cone_angle", light_spec.get("outer_cone_angle")),
                    ("source_angle", light_spec.get("source_angle")),
                ]:
                    if value is not None:
                        _try_set_property(component, prop, float(value))
                if "cast_shadows" in light_spec:
                    _try_set_property(component, "cast_shadows", bool(light_spec.get("cast_shadows")))
                color = light_spec.get("color")
                if color:
                    _try_set_property(component, "light_color", unreal.LinearColor(float(color[0]), float(color[1]), float(color[2]), 1.0))
            lights.append({"name": label, "actor": actor, "location": location, "rotation": rotation})
        except Exception as exc:
            warnings.append({"reason": "production_light_spawn_failed", "light": label, "error": str(exc)})
    return lights


def _add_actor_transform(seq, actor, actor_name: str, keys: list[dict], warnings: list[dict]):
    add_spawnable = getattr(seq, "add_spawnable_from_instance", None)
    uses_spawnable_copy = False
    if _keep_spawnable_source_actors_for_render_backend():
        binding = seq.add_possessable(actor)
    elif add_spawnable is not None:
        try:
            binding = add_spawnable(actor)
            uses_spawnable_copy = True
        except Exception as exc:
            warnings.append({"actor": actor_name, "reason": "spawnable_binding_failed", "error": str(exc)})
            binding = seq.add_possessable(actor)
    else:
        warnings.append({"actor": actor_name, "reason": "spawnable_binding_api_unavailable"})
        binding = seq.add_possessable(actor)
    _set_sequence_binding_names(binding, actor_name, warnings)
    track = binding.add_track(unreal.MovieScene3DTransformTrack)
    section = track.add_section()
    section.set_range(0, FRAME_COUNT)
    _set_transform_channels(section, keys, actor_name, warnings)
    transform_audit = _audit_transform_section(section, keys, actor_name)
    if not transform_audit["passed"]:
        warnings.append(
            {
                "actor": actor_name,
                "reason": "transform_channel_audit_failed",
                "audit": transform_audit,
            }
        )
    first_transform = keys[0]["transform"]
    actor.set_actor_location(_v(first_transform["location"]), False, False)
    actor.set_actor_rotation(_r(first_transform["rotation"]), False)
    if uses_spawnable_copy and not _keep_spawnable_source_actors_for_render_backend():
        try:
            unreal.EditorLevelLibrary.destroy_actor(actor)
        except Exception as exc:
            warnings.append({"actor": actor_name, "reason": "spawnable_source_actor_destroy_failed", "error": str(exc)})
    return binding


def _static_actor_transform_keys(actor_record: dict) -> list[dict]:
    name = str(actor_record["name"])
    location = [float(value) for value in actor_record["location"]]
    rotation = [float(value) for value in actor_record.get("rotation", [0.0, 0.0, 0.0])]
    scale = float(actor_record.get("scale", 1.0))
    keys = [
        {"frame": 0, "transform": {"location": location, "rotation": rotation, "scale": [scale, scale, scale]}},
        {"frame": FRAME_COUNT, "transform": {"location": location, "rotation": rotation, "scale": [scale, scale, scale]}},
    ]
    return keys


def _add_static_spawnable_actor(seq, actor_record: dict, warnings: list[dict]):
    name = str(actor_record["name"])
    keys = _static_actor_transform_keys(actor_record)
    return _add_actor_transform(seq, actor_record["actor"], name, keys, warnings)


def _person_transform_keys(person: dict) -> list[dict]:
    scale = float(person["scale"])
    waypoints = person.get("waypoints")
    if not waypoints:
        return [
            {"frame": 0, "transform": {"location": person["start"], "rotation": person["rotation"], "scale": [scale] * 3}},
            {"frame": FRAME_COUNT, "transform": {"location": person["end"], "rotation": person["rotation"], "scale": [scale] * 3}},
        ]

    keys = []
    last_index = len(waypoints) - 1
    for index, location in enumerate(waypoints):
        if index < last_index:
            rotation = _movement_rotation(location, waypoints[index + 1])
        elif index > 0:
            rotation = _movement_rotation(waypoints[index - 1], location)
        else:
            rotation = person["rotation"]
        frame = FRAME_COUNT if index == last_index else int(round(FRAME_COUNT * index / last_index))
        keys.append({"frame": frame, "transform": {"location": list(location), "rotation": rotation, "scale": [scale] * 3}})
    return _unwrap_transform_yaw(keys)


def _unwrap_transform_yaw(keys: list[dict]) -> list[dict]:
    result = []
    previous_yaw = None
    for key in keys:
        record = dict(key)
        transform = dict(record["transform"])
        rotation = list(transform["rotation"])
        yaw = float(rotation[1])
        if previous_yaw is not None:
            while yaw - previous_yaw > 180.0:
                yaw -= 360.0
            while yaw - previous_yaw < -180.0:
                yaw += 360.0
        rotation[1] = yaw
        transform["rotation"] = rotation
        record["transform"] = transform
        result.append(record)
        previous_yaw = yaw
    return result


def _skeletal_animation_section_start_frame(start_frame: int) -> int:
    return -1 if int(start_frame) == 0 else int(start_frame)


def _pedestrian_animation_phase_offset(index: int) -> int:
    return (int(index) * 11) % 31


def _pedestrian_animation_play_rate(person: dict) -> float:
    points = person.get("waypoints") or [person["start"], person["end"]]
    route_distance = sum(_xy_distance(left, right) for left, right in zip(points, points[1:]))
    if route_distance <= 1.0:
        return 0.92
    duration_seconds = float(FRAME_COUNT) / float(FPS or 24)
    world_speed = route_distance / max(duration_seconds, 1.0 / float(FPS or 24))
    motion = str(person.get("motion", "")).lower()
    if "run" in motion:
        return max(0.32, min(1.0, world_speed / 250.0))
    return max(0.18, min(0.72, world_speed / 120.0))


def _movie_scene_fixed_play_rate(playback_rate: float):
    value = float(playback_rate)
    variant_type = getattr(unreal, "MovieSceneTimeWarpVariant", None)
    if variant_type is None:
        return value
    for create_variant in (
        lambda: variant_type(fixed_play_rate=value),
        lambda: variant_type(value),
    ):
        try:
            return create_variant()
        except Exception:
            pass
    try:
        variant = variant_type()
        set_fixed_play_rate = getattr(variant, "set_fixed_play_rate", None)
        if callable(set_fixed_play_rate):
            set_fixed_play_rate(value)
            return variant
    except Exception:
        pass
    return value


def _movie_scene_play_rate_value(play_rate) -> float | None:
    if isinstance(play_rate, (int, float)):
        return float(play_rate)
    extensions = getattr(unreal, "MovieSceneTimeWarpExtensions", None)
    for method_name in ("to_fixed_play_rate", "conv_time_warp_variant_to_play_rate"):
        method = getattr(extensions, method_name, None)
        if callable(method):
            try:
                value = float(method(play_rate))
                variant_type = getattr(unreal, "MovieSceneTimeWarpVariant", None)
                if variant_type is not None:
                    try:
                        is_variant = isinstance(play_rate, variant_type)
                    except TypeError:
                        is_variant = False
                    if is_variant:
                        try:
                            type_tag = play_rate.export_text().split("(", 1)[0].strip()
                            if type_tag != "EMovieSceneTimeWarpType::FixedPlayRate":
                                return None
                        except Exception:
                            return None
                return value
            except Exception:
                pass
    method = getattr(play_rate, "get_fixed_play_rate", None)
    if callable(method):
        try:
            return float(method())
        except Exception:
            pass
    try:
        return float(play_rate)
    except (TypeError, ValueError):
        return None


def _swap_root_bone_mode(value) -> str:
    if isinstance(value, int):
        return {0: "component", 1: "actor", 2: "none"}.get(value, f"unknown:{value}")
    enum_name = getattr(value, "name", value)
    normalized = str(enum_name).strip().lower()
    for mode in ("component", "actor", "none"):
        if mode in normalized:
            return mode
    return normalized


def _asset_package_path(path: str) -> str:
    package_path = str(path)
    leaf = package_path.rsplit("/", 1)[-1]
    if "." in leaf:
        package_path = package_path.rsplit(".", 1)[0]
    return package_path


def _in_place_animation_path(source_path: str) -> str:
    package_path = _asset_package_path(source_path)
    source_name = package_path.rsplit("/", 1)[-1]
    safe_name = "".join(character if character.isalnum() or character == "_" else "_" for character in source_name)
    digest = hashlib.sha256(package_path.encode("utf-8")).hexdigest()[:10]
    return f"{IN_PLACE_ANIMATION_ROOT}/{safe_name}_{digest}_InPlace"


def _animation_property(animation, property_name: str):
    get_editor_property = getattr(animation, "get_editor_property", None)
    if callable(get_editor_property):
        return get_editor_property(property_name)
    return getattr(animation, property_name)


def _load_or_create_in_place_animation(source_path: str):
    source_package_path = _asset_package_path(source_path)
    source_animation = _load_asset(source_package_path)
    if source_package_path.startswith("/Game/CineU/RetargetedAnimations/"):
        changed = False
        if bool(_animation_property(source_animation, "force_root_lock")) is not True:
            source_animation.set_editor_property("force_root_lock", True)
            changed = True
        if bool(_animation_property(source_animation, "enable_root_motion")) is not False:
            source_animation.set_editor_property("enable_root_motion", False)
            changed = True
        if changed and not unreal.EditorAssetLibrary.save_asset(source_package_path):
            raise RuntimeError(f"Could not save CineU retargeted animation asset: {source_package_path}")
        if bool(_animation_property(source_animation, "force_root_lock")) is not True:
            raise RuntimeError(f"Root lock did not persist on CineU retargeted animation: {source_package_path}")
        if bool(_animation_property(source_animation, "enable_root_motion")) is not False:
            raise RuntimeError(f"Root motion remained enabled on CineU retargeted animation: {source_package_path}")
        return source_animation, source_package_path

    destination_path = _in_place_animation_path(source_package_path)
    unreal.EditorAssetLibrary.make_directory(IN_PLACE_ANIMATION_ROOT)
    created = False
    if not unreal.EditorAssetLibrary.does_asset_exist(destination_path):
        duplicated = unreal.EditorAssetLibrary.duplicate_asset(source_package_path, destination_path)
        if duplicated is None or duplicated is False:
            raise RuntimeError(f"Could not duplicate animation asset: {source_package_path} -> {destination_path}")
        created = True
    animation = _load_asset(destination_path)
    changed = False
    if bool(_animation_property(animation, "force_root_lock")) is not True:
        animation.set_editor_property("force_root_lock", True)
        changed = True
    if bool(_animation_property(animation, "enable_root_motion")) is not False:
        animation.set_editor_property("enable_root_motion", False)
        changed = True
    if created or changed:
        if not unreal.EditorAssetLibrary.save_asset(destination_path):
            raise RuntimeError(f"Could not save in-place animation asset: {destination_path}")
    if bool(_animation_property(animation, "force_root_lock")) is not True:
        raise RuntimeError(f"Root lock did not persist on animation asset: {destination_path}")
    if bool(_animation_property(animation, "enable_root_motion")) is not False:
        raise RuntimeError(f"Root motion remained enabled on animation asset: {destination_path}")
    return animation, destination_path


def _add_skeletal_animation(
    binding,
    anim_path: str,
    start_frame: int,
    end_frame: int,
    warnings: list[dict],
    phase_offset_frames: int = 0,
    swap_root_bone_mode: str = "none",
    force_root_lock: bool = False,
    playback_rate: float = 1.0,
    mesh_asset=None,
    actor_name: str | None = None,
) -> dict | None:
    anim = _load_asset(anim_path)
    if mesh_asset is not None:
        compatibility = _skeletal_asset_compatibility(mesh_asset, anim)
        if not compatibility["passed"]:
            warnings.append({"actor": actor_name, "animation_path": anim_path, **compatibility})
            return None
    try:
        if force_root_lock:
            anim, prepared_animation_path = _load_or_create_in_place_animation(anim_path)
        else:
            prepared_animation_path = _asset_package_path(anim_path)
        track = binding.add_track(unreal.MovieSceneSkeletalAnimationTrack)
        section = track.add_section()
        section.set_range(_skeletal_animation_section_start_frame(start_frame), int(end_frame))
        params = section.get_editor_property("params")
        params.set_editor_property("animation", anim)
        frame_number = getattr(unreal, "FrameNumber", int)
        params.set_editor_property("start_frame_offset", frame_number(max(0, int(phase_offset_frames))))
        params.set_editor_property("play_rate", _movie_scene_fixed_play_rate(playback_rate))
        root_mode = str(swap_root_bone_mode or "none").strip().lower()
        if root_mode in {"actor", "component"}:
            swap_root_bone = getattr(unreal, "SwapRootBone", None)
            enum_name = "SWAP_ROOT_BONE_ACTOR" if root_mode == "actor" else "SWAP_ROOT_BONE_COMPONENT"
            enum_value = getattr(swap_root_bone, enum_name, None)
            if enum_value is not None:
                params.set_editor_property("swap_root_bone", enum_value)
        section.set_editor_property("params", params)
        return {
            "animation_path": prepared_animation_path,
            "source_animation_path": _asset_package_path(anim_path),
            "in_place_requested": bool(force_root_lock),
            "persistent_in_place_verified": False,
            "playback_rate": float(playback_rate),
        }
    except Exception as exc:
        warnings.append({"animation_path": anim_path, "reason": "skeletal_animation_track_failed", "error": str(exc)})
        return None


def _spawn_camera(
    name: str,
    transform_keys: list[dict],
    focal: float,
    exposure_bias: float | None = None,
    exposure_brightness: float | None = None,
    motion_blur_amount: float | None = None,
    local_exposure: dict | None = None,
) -> object:
    first = transform_keys[0]
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.CineCameraActor, _v(first["location"]), _r(first["rotation"]))
    actor.set_actor_label(name)
    component = actor.get_cine_camera_component()
    component.set_editor_property("current_focal_length", float(focal))
    component.set_editor_property("focus_settings", component.get_editor_property("focus_settings"))
    if exposure_bias is not None or motion_blur_amount is not None or local_exposure:
        try:
            settings = component.get_editor_property("post_process_settings")
            if exposure_bias is not None:
                brightness = float(exposure_brightness) if exposure_brightness is not None else 0.85
                if float(exposure_bias) < 0.0:
                    brightness = max(0.05, min(0.85, 0.85 * (2.0 ** float(exposure_bias))))
                    manual_method = getattr(getattr(unreal, "AutoExposureMethod", None), "AEM_MANUAL", None)
                    if manual_method is not None:
                        _try_set_property(settings, "override_auto_exposure_method", True)
                        _try_set_property(settings, "auto_exposure_method", manual_method)
                    for prop, value in [
                        ("override_auto_exposure_apply_physical_camera_exposure", True),
                        ("auto_exposure_apply_physical_camera_exposure", True),
                        ("override_camera_shutter_speed", True),
                        ("camera_shutter_speed", 60.0),
                        ("override_camera_iso", True),
                        ("camera_iso", 800.0),
                        ("override_depth_of_field_fstop", True),
                        ("depth_of_field_fstop", 2.8),
                    ]:
                        _try_set_property(settings, prop, value)
                for prop, value in [
                    ("override_auto_exposure_min_brightness", True),
                    ("override_auto_exposure_max_brightness", True),
                    ("override_auto_exposure_bias", True),
                    ("override_exposure_compensation", True),
                    ("auto_exposure_min_brightness", brightness),
                    ("auto_exposure_max_brightness", brightness),
                    ("auto_exposure_bias", float(exposure_bias)),
                    ("exposure_compensation", float(exposure_bias)),
                ]:
                    _try_set_property(settings, prop, value)
            if motion_blur_amount is not None:
                _try_set_property(settings, "override_motion_blur_amount", True)
                _try_set_property(settings, "motion_blur_amount", float(motion_blur_amount))
            if local_exposure:
                written_local_properties = []

                def require_local_property(name: str, value) -> None:
                    if not _try_set_property(settings, name, value):
                        raise RuntimeError(f"local exposure property write failed: {name}")
                    written_local_properties.append((name, value))

                method_name = str(local_exposure.get("method", "bilateral")).strip().upper()
                method = getattr(getattr(unreal, "LocalExposureMethod", None), method_name, None)
                if method is None:
                    raise RuntimeError(f"local exposure method unavailable: {method_name}")
                require_local_property("override_local_exposure_method", True)
                require_local_property("local_exposure_method", method)
                for profile_name, property_name in [
                    ("highlight_contrast_scale", "local_exposure_highlight_contrast_scale"),
                    ("shadow_contrast_scale", "local_exposure_shadow_contrast_scale"),
                    ("detail_strength", "local_exposure_detail_strength"),
                    ("blurred_luminance_blend", "local_exposure_blurred_luminance_blend"),
                    ("middle_grey_bias", "local_exposure_middle_grey_bias"),
                ]:
                    if profile_name not in local_exposure:
                        continue
                    require_local_property(f"override_{property_name}", True)
                    require_local_property(property_name, float(local_exposure[profile_name]))
                for property_name, expected_value in written_local_properties:
                    try:
                        actual_value = settings.get_editor_property(property_name)
                    except Exception as exc:
                        raise RuntimeError(
                            f"local exposure property readback failed: {property_name}"
                        ) from exc
                    values_match = actual_value == expected_value
                    if isinstance(expected_value, float):
                        try:
                            values_match = math.isclose(
                                float(actual_value),
                                expected_value,
                                rel_tol=1e-6,
                                abs_tol=1e-6,
                            )
                        except (TypeError, ValueError):
                            values_match = False
                    if not values_match:
                        raise RuntimeError(
                            f"local exposure property readback mismatch: {property_name}"
                        )
            if local_exposure:
                if not _try_set_property(component, "post_process_blend_weight", 1.0):
                    raise RuntimeError("local exposure blend weight write failed")
                if not _try_set_property(component, "post_process_settings", settings):
                    raise RuntimeError("local exposure settings commit failed")
                try:
                    committed_blend_weight = float(
                        component.get_editor_property("post_process_blend_weight")
                    )
                    committed_settings = component.get_editor_property(
                        "post_process_settings"
                    )
                except Exception as exc:
                    raise RuntimeError(
                        "committed local exposure settings readback failed"
                    ) from exc
                if not math.isclose(
                    committed_blend_weight,
                    1.0,
                    rel_tol=1e-6,
                    abs_tol=1e-6,
                ):
                    raise RuntimeError(
                        "committed local exposure blend weight mismatch"
                    )
                for property_name, expected_value in written_local_properties:
                    try:
                        actual_value = committed_settings.get_editor_property(
                            property_name
                        )
                    except Exception as exc:
                        raise RuntimeError(
                            f"committed local exposure property readback failed: {property_name}"
                        ) from exc
                    values_match = actual_value == expected_value
                    if isinstance(expected_value, float):
                        try:
                            values_match = math.isclose(
                                float(actual_value),
                                expected_value,
                                rel_tol=1e-6,
                                abs_tol=1e-6,
                            )
                        except (TypeError, ValueError):
                            values_match = False
                    if not values_match:
                        raise RuntimeError(
                            f"committed local exposure property mismatch: {property_name}"
                        )
            else:
                _try_set_property(component, "post_process_blend_weight", 1.0)
                _try_set_property(component, "post_process_settings", settings)
        except Exception as exc:
            if local_exposure:
                if isinstance(exc, RuntimeError) and "local exposure" in str(exc):
                    raise
                raise RuntimeError(f"local exposure configuration failed: {exc}") from exc
    return actor


def _add_camera(seq, camera, camera_name: str, transform_keys: list[dict], warnings: list[dict]):
    keys = [{"frame": item["frame"], "transform": {"location": item["location"], "rotation": item["rotation"], "scale": [1.0, 1.0, 1.0]}} for item in transform_keys]
    return _add_actor_transform(seq, camera, camera_name, keys, warnings)


def _camera_focal_length_keys(camera_spec: dict) -> list[dict]:
    return [
        {"frame": int(key["frame"]), "focal_length": float(key.get("focal_length", camera_spec["focal"]))}
        for key in camera_spec["keys"]
    ]


def _has_animated_focal_length(focal_keys: list[dict]) -> bool:
    return len({round(float(key["focal_length"]), 4) for key in focal_keys}) > 1


def _add_camera_cuts(seq, cuts: list[dict], camera_bindings: dict[str, object], warnings: list[dict]) -> None:
    track = seq.add_track(unreal.MovieSceneCameraCutTrack)
    for cut in cuts:
        section = track.add_section()
        section.set_range(int(cut["start_frame"]), int(cut["end_frame"]))
        binding = camera_bindings.get(cut["camera_name"])
        binding_id = _binding_id(binding)
        setter = getattr(section, "set_camera_binding_id", None)
        if binding_id is not None and setter is not None:
            try:
                setter(binding_id)
            except Exception as exc:
                warnings.append({"camera_name": cut["camera_name"], "reason": "camera_cut_binding_failed", "error": str(exc)})
        else:
            warnings.append({"camera_name": cut["camera_name"], "reason": "camera_binding_id_unavailable"})


def _lerp(a: list[float], b: list[float], t: float) -> list[float]:
    return [float(a[i]) + (float(b[i]) - float(a[i])) * t for i in range(3)]


def _camera_key(frame: int, location: list[float], target: list[float]) -> dict:
    return {"frame": frame, "location": location, "rotation": _look_at_rotation(location, target)}


def _camera_key_raw(frame: int, location: list[float], rotation: list[float]) -> dict:
    return {"frame": frame, "location": location, "rotation": rotation}


def _camera_key_with_focal(frame: int, location: list[float], target: list[float], focal_length: float) -> dict:
    key = _camera_key(frame, location, target)
    key["focal_length"] = float(focal_length)
    return key


def _freeze_monitor_camera(camera: dict) -> dict:
    camera_type = str(camera.get("type", ""))
    monitor_view = str(camera.get("monitor_view", ""))
    if camera.get("cinematic_role") or camera_type == "first_person":
        return camera
    if camera_type not in {"surveillance_fixed", "surveillance_oblique", "top_down"} and monitor_view not in {
        "original",
        "reverse",
        "side",
        "far",
        "drone_overview",
    }:
        return camera
    keys = list(camera.get("keys") or [])
    if len(keys) < 2:
        return camera
    first_key = dict(keys[0])
    end_key = dict(first_key)
    end_key["frame"] = int(keys[-1].get("frame", FRAME_COUNT))
    frozen = dict(camera)
    frozen["keys"] = [first_key, end_key]
    return frozen


def _normalize_camera_motion(cameras: list[dict]) -> list[dict]:
    return [_freeze_monitor_camera(camera) for camera in cameras]


def _cinematic_frames(count: int) -> list[int]:
    if count <= 1:
        return [0]
    frames = [int(round(FRAME_COUNT * index / (count - 1))) for index in range(count)]
    frames[0] = 0
    frames[-1] = FRAME_COUNT
    return frames


def _cinematic_profile(scene_id: str, people_z: float) -> dict:
    profiles = {
        "museum_gallery_day": {
            "center": [-3000.0, -470.0, people_z],
            "first_start": [-4200.0, -660.0, people_z + 150.0],
            "first_end": [-3600.0, -650.0, people_z + 150.0],
            "drone_radius": 1350.0,
            "drone_height": 1050.0,
            "drone_focal": 20.0,
            "drone_locations": [
                [-4300.0, -760.0, people_z + 425.0],
                [-4050.0, -620.0, people_z + 455.0],
                [-3800.0, -600.0, people_z + 485.0],
                [-3500.0, -660.0, people_z + 505.0],
                [-3300.0, -820.0, people_z + 485.0],
                [-3200.0, -930.0, people_z + 455.0],
            ],
            "drone_targets": [
                [-3450.0, -520.0, people_z + 180.0],
                [-3300.0, -490.0, people_z + 180.0],
                [-3150.0, -470.0, people_z + 180.0],
                [-3000.0, -470.0, people_z + 180.0],
                [-2850.0, -460.0, people_z + 220.0],
                [-2700.0, -500.0, people_z + 180.0],
            ],
            "hitch_start": [-4250.0, -700.0, people_z + 185.0],
            "hitch_end": [-3400.0, -660.0, people_z + 215.0],
            "hitch_target_start": [-3600.0, -470.0, people_z + 150.0],
            "hitch_target_end": [-3000.0, -480.0, people_z + 150.0],
            "hitch_drift": 45.0,
        },
        "museum_gallery_night": {
            "center": [-3000.0, -470.0, people_z],
            "first_start": [-4200.0, -660.0, people_z + 150.0],
            "first_end": [-3600.0, -650.0, people_z + 150.0],
            "drone_radius": 1350.0,
            "drone_height": 1050.0,
            "drone_focal": 20.0,
            "drone_locations": [
                [-4300.0, -760.0, people_z + 425.0],
                [-4050.0, -620.0, people_z + 455.0],
                [-3800.0, -600.0, people_z + 485.0],
                [-3500.0, -660.0, people_z + 505.0],
                [-3300.0, -820.0, people_z + 485.0],
                [-3200.0, -930.0, people_z + 455.0],
            ],
            "drone_targets": [
                [-3450.0, -520.0, people_z + 180.0],
                [-3300.0, -490.0, people_z + 180.0],
                [-3150.0, -470.0, people_z + 180.0],
                [-3000.0, -470.0, people_z + 180.0],
                [-2850.0, -460.0, people_z + 220.0],
                [-2700.0, -500.0, people_z + 180.0],
            ],
            "hitch_start": [-4250.0, -700.0, people_z + 185.0],
            "hitch_end": [-3400.0, -660.0, people_z + 215.0],
            "hitch_target_start": [-3600.0, -470.0, people_z + 150.0],
            "hitch_target_end": [-3000.0, -480.0, people_z + 150.0],
            "hitch_drift": 45.0,
        },
        "citypark_promenade_day": {
            "center": [-33000.0, 11080.0, people_z],
            "first_start": [-34680.0, 10490.0, people_z + 166.0],
            "first_end": [-33200.0, 11420.0, people_z + 166.0],
            "drone_radius": 3600.0,
            "drone_height": 3650.0,
            "drone_arc": 115.0,
            "hitch_start": [-35600.0, 9650.0, people_z + 330.0],
            "hitch_end": [-33100.0, 11980.0, people_z + 420.0],
            "hitch_target_start": [-33800.0, 10850.0, people_z + 120.0],
            "hitch_target_end": [-31900.0, 11480.0, people_z + 120.0],
        },
        "citypark_promenade_night": {
            "center": [-33000.0, 11080.0, people_z],
            "first_start": [-34680.0, 10490.0, people_z + 166.0],
            "first_end": [-33200.0, 11420.0, people_z + 166.0],
            "drone_radius": 3600.0,
            "drone_height": 3650.0,
            "drone_arc": 115.0,
            "hitch_start": [-35600.0, 9650.0, people_z + 330.0],
            "hitch_end": [-33100.0, 11980.0, people_z + 420.0],
            "hitch_target_start": [-33800.0, 10850.0, people_z + 120.0],
            "hitch_target_end": [-31900.0, 11480.0, people_z + 120.0],
        },
        "art_gallery_day": {
            "center": [-400.0, -5700.0, people_z],
            "first_start": [-2700.0, -6900.0, people_z + 150.0],
            "first_end": [-760.0, -6100.0, people_z + 150.0],
            "drone_radius": 2500.0,
            "drone_height": 1220.0,
            "drone_arc": 170.0,
            "hitch_start": [-3300.0, -7000.0, people_z + 175.0],
            "hitch_end": [-650.0, -5000.0, people_z + 230.0],
            "hitch_target_start": [-1600.0, -6100.0, people_z + 135.0],
            "hitch_target_end": [1200.0, -5000.0, people_z + 135.0],
        },
        "warehouse_day": {
            "center": [-1500.0, -4200.0, people_z],
            "first_start": [-3350.0, -4550.0, people_z + 158.0],
            "first_end": [-1450.0, -4350.0, people_z + 158.0],
            "drone_radius": 2550.0,
            "drone_height": 1500.0,
            "drone_focal": 20.0,
            "drone_locations": [
                [-1600.0, -5360.0, people_z + 565.0],
                [-1250.0, -5320.0, people_z + 563.0],
                [-900.0, -5280.0, people_z + 560.0],
                [-550.0, -5240.0, people_z + 555.0],
                [-150.0, -5180.0, people_z + 550.0],
                [250.0, -5120.0, people_z + 540.0],
            ],
            "drone_targets": [
                [-550.0, -4250.0, people_z + 145.0],
                [-250.0, -4250.0, people_z + 145.0],
                [50.0, -4250.0, people_z + 145.0],
                [350.0, -4250.0, people_z + 145.0],
                [650.0, -4250.0, people_z + 145.0],
                [900.0, -4250.0, people_z + 145.0],
            ],
            "hitch_start": [-3600.0, -5450.0, people_z + 430.0],
            "hitch_end": [-350.0, -5220.0, people_z + 470.0],
            "hitch_target_start": [-2450.0, -4450.0, people_z + 135.0],
            "hitch_target_end": [650.0, -4200.0, people_z + 135.0],
        },
        "car_dealer_showcase_day": {
            "center": [250.0, -6100.0, people_z],
            "first_start": [-1350.0, -6400.0, people_z + 158.0],
            "first_end": [760.0, -5920.0, people_z + 158.0],
            "drone_radius": 1850.0,
            "drone_height": 1120.0,
            "drone_start_angle": -45.0,
            "drone_arc": 180.0,
            "drone_locations": [
                [2400.0, -6650.0, people_z + 1220.0],
                [2500.0, -6250.0, people_z + 1220.0],
                [2200.0, -5750.0, people_z + 1180.0],
                [1700.0, -5250.0, people_z + 1140.0],
                [900.0, -4900.0, people_z + 1120.0],
                [-100.0, -4850.0, people_z + 1120.0],
                [-700.0, -5350.0, people_z + 1150.0],
                [-850.0, -6100.0, people_z + 1180.0],
            ],
            "drone_targets": [
                [800.0, -6300.0, people_z + 70.0],
                [620.0, -6200.0, people_z + 70.0],
                [320.0, -6100.0, people_z + 80.0],
                [-120.0, -6020.0, people_z + 85.0],
                [-250.0, -6100.0, people_z + 90.0],
                [40.0, -6220.0, people_z + 90.0],
                [560.0, -6350.0, people_z + 80.0],
                [1050.0, -6400.0, people_z + 70.0],
            ],
            "hitch_start": [-1650.0, -6500.0, people_z + 240.0],
            "hitch_end": [650.0, -5850.0, people_z + 300.0],
            "hitch_target_start": [-350.0, -6200.0, people_z + 135.0],
            "hitch_target_end": [1800.0, -5400.0, people_z + 135.0],
        },
        "downtown_west_day": {
            "center": [2200.0, 4300.0, people_z],
            "first_start": [3150.0, 4180.0, people_z + 158.0],
            "first_end": [1900.0, 4210.0, people_z + 158.0],
            "first_target_start": [2400.0, 4440.0, people_z + 150.0],
            "first_target_end": [980.0, 4480.0, people_z + 148.0],
            "drone_focal": 18.0,
            "drone_locations": [
                [720.0, 5500.0, people_z + 2520.0],
                [1740.0, 5850.0, people_z + 2740.0],
                [2900.0, 5450.0, people_z + 2880.0],
                [3450.0, 4550.0, people_z + 2980.0],
                [2660.0, 3850.0, people_z + 2840.0],
                [1460.0, 3720.0, people_z + 2640.0],
                [620.0, 4420.0, people_z + 2520.0],
            ],
            "drone_targets": [
                [1900.0, 4380.0, people_z + 95.0],
                [2200.0, 4380.0, people_z + 95.0],
                [2500.0, 4300.0, people_z + 95.0],
                [2400.0, 4200.0, people_z + 95.0],
                [2100.0, 4160.0, people_z + 95.0],
                [1800.0, 4240.0, people_z + 95.0],
                [1950.0, 4360.0, people_z + 95.0],
            ],
            "hitch_start": [3220.0, 3900.0, people_z + 560.0],
            "hitch_end": [1880.0, 5350.0, people_z + 620.0],
            "hitch_target_start": [2250.0, 4280.0, people_z + 145.0],
            "hitch_target_end": [920.0, 4440.0, people_z + 145.0],
            "hitch_drift": 90.0,
        },
        "world_template_6_7_day": {
            "center": [-1050.0, 2550.0, people_z],
            "first_start": [-300.0, 1550.0, people_z + 164.0],
            "first_end": [-300.0, 2950.0, people_z + 164.0],
            "first_target_start": [-500.0, 2350.0, people_z + 155.0],
            "first_target_end": [-1050.0, 2900.0, people_z + 150.0],
            "drone_focal": 18.0,
            "drone_locations": [
                [1769.0, 1524.0, people_z + 4000.0],
                [1932.0, 2223.0, people_z + 4100.0],
                [1924.0, 2942.0, people_z + 4200.0],
                [1746.0, 3637.0, people_z + 4300.0],
                [1407.0, 4271.0, people_z + 4400.0],
                [928.0, 4805.0, people_z + 4300.0],
                [335.0, 5211.0, people_z + 4200.0],
                [-337.0, 5464.0, people_z + 4100.0],
                [-1050.0, 5550.0, people_z + 4000.0],
            ],
            "drone_targets": [
                [-850.0, 2450.0, people_z + 120.0],
                [-900.0, 2475.0, people_z + 115.0],
                [-950.0, 2500.0, people_z + 110.0],
                [-1000.0, 2525.0, people_z + 105.0],
                [-1050.0, 2550.0, people_z + 100.0],
                [-1100.0, 2575.0, people_z + 105.0],
                [-1150.0, 2600.0, people_z + 110.0],
                [-1200.0, 2625.0, people_z + 115.0],
                [-1250.0, 2650.0, people_z + 120.0],
            ],
            "hitch_start": [650.0, 1300.0, people_z + 320.0],
            "hitch_end": [250.0, 3500.0, people_z + 420.0],
            "hitch_target_start": [-650.0, 2050.0, people_z + 140.0],
            "hitch_target_end": [-1050.0, 2900.0, people_z + 150.0],
            "hitch_drift": 105.0,
        },
    }
    if scene_id in WORLD_TEMPLATE_6_7_SCENE_IDS:
        return _downtown_west_native_cinematic_profile(profiles[scene_id])
    if _is_downtown_west_scene(scene_id):
        return _downtown_west_native_cinematic_profile(profiles["downtown_west_day"])
    return profiles[scene_id]


def _downtown_west_native_cinematic_profile(profile: dict) -> dict:
    shifted = dict(profile)
    point_keys = {
        "center",
        "first_start",
        "first_end",
        "first_target_start",
        "first_target_end",
        "hitch_start",
        "hitch_end",
        "hitch_target_start",
        "hitch_target_end",
    }
    point_list_keys = {"drone_locations", "drone_targets"}
    for key in point_keys:
        if key in shifted:
            shifted[key] = _downtown_west_native_location(list(shifted[key]))
    for key in point_list_keys:
        if key in shifted:
            shifted[key] = [_downtown_west_native_location(list(point)) for point in shifted[key]]
    return shifted


def _cinematic_first_person_keys(profile: dict) -> list[dict]:
    start = profile["first_start"]
    end = profile["first_end"]
    dx = float(end[0]) - float(start[0])
    dy = float(end[1]) - float(start[1])
    length = math.hypot(dx, dy) or 1.0
    forward = [dx / length, dy / length, 0.0]
    normal = [-forward[1], forward[0], 0.0]
    keys = []
    frames = _cinematic_frames(11)
    for index, frame in enumerate(frames):
        t = index / (len(frames) - 1)
        eased = t * t * (3.0 - 2.0 * t)
        bob = math.sin(t * math.pi * 6.0) * 5.3
        sway = math.sin(t * math.pi * 2.0) * 3.5
        location = _lerp(start, end, eased)
        location[0] += normal[0] * sway
        location[1] += normal[1] * sway
        location[2] = float(start[2]) + bob
        if "first_target_start" in profile and "first_target_end" in profile:
            target = _lerp(profile["first_target_start"], profile["first_target_end"], eased)
            target[2] += math.sin(t * math.pi * 1.5) * 6.0
        else:
            look_sway = math.sin(t * math.pi * 1.5) * 42.0
            target = [
                location[0] + forward[0] * 950.0 + normal[0] * look_sway,
                location[1] + forward[1] * 950.0 + normal[1] * look_sway,
                float(location[2]) - 5.0,
            ]
        focal = 24.0 + math.sin(t * math.pi) * 1.2
        keys.append(_camera_key_with_focal(frame, location, target, focal))
    return _unwrap_camera_yaw(keys)


def _unwrap_camera_yaw(keys: list[dict]) -> list[dict]:
    result = []
    previous_yaw = None
    for key in keys:
        record = dict(key)
        rotation = list(record["rotation"])
        yaw = float(rotation[1])
        if previous_yaw is not None:
            while yaw - previous_yaw > 180.0:
                yaw -= 360.0
            while yaw - previous_yaw < -180.0:
                yaw += 360.0
        rotation[1] = yaw
        record["rotation"] = rotation
        result.append(record)
        previous_yaw = yaw
    return result


def _cinematic_drone_orbit_keys(profile: dict) -> list[dict]:
    manual_locations = profile.get("drone_locations")
    if manual_locations:
        frames = _cinematic_frames(len(manual_locations))
        manual_targets = profile.get("drone_targets") or [[*profile["center"][:2], float(profile["center"][2]) + 90.0] for _ in manual_locations]
        manual_focal = float(profile.get("drone_focal", 26.0))
        keys = []
        for index, (frame, location, target) in enumerate(zip(frames, manual_locations, manual_targets)):
            t = index / float(max(1, len(frames) - 1))
            focal = manual_focal + math.sin(t * math.pi * 2.0) * 1.8
            keys.append(_camera_key_with_focal(frame, [float(value) for value in location], [float(value) for value in target], focal))
        return _unwrap_camera_yaw(keys)
    center = profile["center"]
    radius = float(profile["drone_radius"])
    height = float(profile["drone_height"])
    keys = []
    frames = _cinematic_frames(10)
    start_angle = math.radians(float(profile.get("drone_start_angle", -145.0)))
    arc = math.radians(float(profile.get("drone_arc", 225.0)))
    for index, frame in enumerate(frames):
        t = index / (len(frames) - 1)
        angle = start_angle + arc * t
        location = [
            float(center[0]) + math.cos(angle) * radius,
            float(center[1]) + math.sin(angle) * radius,
            float(center[2]) + height,
        ]
        target = [float(center[0]), float(center[1]), float(center[2]) + 90.0]
        focal = 27.0 + math.sin(t * math.pi) * 3.0
        keys.append(_camera_key_with_focal(frame, location, target, focal))
    return _unwrap_camera_yaw(keys)


def _cinematic_hitchcock_keys(profile: dict) -> list[dict]:
    start = profile["hitch_start"]
    end = profile["hitch_end"]
    target_start = profile["hitch_target_start"]
    target_end = profile["hitch_target_end"]
    dx = float(end[0]) - float(start[0])
    dy = float(end[1]) - float(start[1])
    length = math.hypot(dx, dy) or 1.0
    normal = [-dy / length, dx / length, 0.0]
    focal_values = [20.0, 24.0, 30.0, 38.0, 52.0, 65.0, 54.0, 42.0, 33.0, 27.0, 22.0]
    keys = []
    frames = _cinematic_frames(len(focal_values))
    max_drift = float(profile.get("hitch_drift", 120.0))
    for index, frame in enumerate(frames):
        t = index / (len(frames) - 1)
        eased = t * t * (3.0 - 2.0 * t)
        drift = math.sin(t * math.pi) * max_drift
        location = _lerp(start, end, eased)
        location[0] += normal[0] * drift
        location[1] += normal[1] * drift
        location[2] += math.sin(t * math.pi * 2.0) * 32.0
        target = _lerp(target_start, target_end, eased)
        keys.append(_camera_key_with_focal(frame, location, target, focal_values[index]))
    return _unwrap_camera_yaw(keys)


def _cinematic_30s_cameras(scene_id: str, people_z: float, exposure_bias: float | None = None, exposure_brightness: float | None = None) -> list[dict]:
    if not _cinematic_30s_requested():
        return []
    profile = _cinematic_profile(scene_id, people_z)
    first_person_keys = _cinematic_first_person_keys(profile)
    drone_keys = _cinematic_drone_orbit_keys(profile)
    hitchcock_keys = _cinematic_hitchcock_keys(profile)
    return [
        {
            "name": f"CineU_{scene_id}_cinematic_first_person_walk",
            "shot_id": f"{scene_id}_cinematic_first_person_walk",
            "type": "first_person",
            "cinematic_role": "first_person_walk_bob",
            "focal": first_person_keys[0]["focal_length"],
            "keys": first_person_keys,
            "exposure_bias": exposure_bias,
            "exposure_brightness": exposure_brightness,
            "motion_blur_amount": 0.12,
        },
        {
            "name": f"CineU_{scene_id}_cinematic_drone_orbit",
            "shot_id": f"{scene_id}_cinematic_drone_orbit",
            "type": "top_down",
            "monitor_view": "drone_overview",
            "cinematic_role": "drone_orbit",
            "focal": drone_keys[0]["focal_length"],
            "keys": drone_keys,
            "exposure_bias": exposure_bias,
            "exposure_brightness": exposure_brightness,
            "motion_blur_amount": 0.10,
        },
        {
            "name": f"CineU_{scene_id}_cinematic_hitchcock_glide",
            "shot_id": f"{scene_id}_cinematic_hitchcock_glide",
            "type": "cinematic_motion",
            "cinematic_role": "cinematic_hitchcock_glide",
            "focal": hitchcock_keys[0]["focal_length"],
            "keys": hitchcock_keys,
            "exposure_bias": exposure_bias,
            "exposure_brightness": exposure_brightness,
            "motion_blur_amount": 0.14,
        },
    ]


def _asset_first_plan(scene_id: str) -> dict:
    inventory = json.loads((DIAG_ROOT / "asset_inventory.json").read_text(encoding="utf-8"))
    skeletons = json.loads((DIAG_ROOT / "character_skeletons.json").read_text(encoding="utf-8"))
    local_asset_index = json.loads(LOCAL_ASSET_INDEX_PATH.read_text(encoding="utf-8")) if LOCAL_ASSET_INDEX_PATH.exists() else None
    return build_hillside_scene_plan(scene_id, inventory, skeletons, local_asset_index=local_asset_index)


def _scaled_frame(frame: int, source_end_frame: int) -> int:
    source_end = max(1, int(source_end_frame))
    return int(round(float(frame) * float(FRAME_COUNT) / float(source_end)))


def _camera_from_plan_shot(shot: dict, source_end_frame: int) -> dict:
    start_frame = _scaled_frame(int(shot["start_frame"]), source_end_frame)
    end_frame = _scaled_frame(int(shot["end_frame"]), source_end_frame)
    location = [float(value) for value in shot["location"]]
    end_location = [float(value) for value in shot.get("end_location", location)]
    target = [float(value) for value in shot["target"]]
    if "rotation" in shot:
        rotation = [float(value) for value in shot["rotation"]]
        end_rotation = [float(value) for value in shot.get("end_rotation", rotation)]
        keys = [
            _camera_key_raw(start_frame, location, rotation),
            _camera_key_raw(end_frame, end_location, end_rotation),
        ]
    else:
        keys = [
            _camera_key(start_frame, location, target),
            _camera_key(end_frame, end_location, target),
        ]
    camera = {
        "name": str(shot["camera_name"]),
        "shot_id": str(shot["shot_id"]),
        "type": str(shot["type"]),
        "focal": float(shot["focal_length"]),
        "keys": keys,
    }
    if "exposure_bias" in shot:
        camera["exposure_bias"] = float(shot["exposure_bias"])
    return camera


def _support_props_from_plan(plan: dict) -> list[dict]:
    props = []
    for prop in plan.get("support_props", []):
        record = {
            "name": str(prop["actor_name"]),
            "type": "support_prop",
            "role": str(prop.get("role", "support")),
            "mesh": str(prop["mesh_path"]),
            "location": [float(value) for value in prop["location"]],
            "rotation": [float(value) for value in prop.get("rotation", [0.0, 0.0, 0.0])],
            "scale": float(prop.get("scale", 1.0)),
        }
        if prop.get("material_override"):
            record["material_override"] = str(prop["material_override"])
        if prop.get("material_profile"):
            record["material_profile"] = dict(prop["material_profile"])
        props.append(record)
    return props


def _paths_from_anchor(anchor: dict) -> tuple[list[tuple[list[float], list[float]]], list[list[float]], float, bool]:
    support = anchor["support_surface"]
    x_min, x_max, y_min, y_max = [float(value) for value in support["bounds"]]
    z = float(support["z"])
    character_paths = anchor.get("character_paths") or []
    if character_paths:
        paths = [
            ([float(value) for value in route["start"]], [float(value) for value in route["end"]])
            for route in character_paths
        ]
        rest_points = [[float(value) for value in point] for point in anchor.get("rest_points", [])]
        return paths, rest_points, z, True
    walkline = anchor.get("walkline") or []
    if walkline:
        points = [[float(value) for value in point] for point in walkline]
        paths: list[tuple[list[float], list[float]]] = []
        for left, right in zip(points, points[1:]):
            paths.append((left, right))
        reversed_points = list(reversed(points))
        for left, right in zip(reversed_points, reversed_points[1:]):
            paths.append((left, right))
        rest_points = [[float(value) for value in point] for point in anchor.get("rest_points", [])]
        if not rest_points:
            rest_points = points[:: max(1, len(points) // 4)]
        return paths, rest_points, z, True
    paths = [
        ([x_min, y_min, z], [x_max, y_max, z]),
        ([x_max, y_max, z], [x_min, y_min, z]),
        ([x_min + (x_max - x_min) * 0.2, y_min + (y_max - y_min) * 0.45, z], [x_max - (x_max - x_min) * 0.15, y_max, z]),
        ([x_max - (x_max - x_min) * 0.1, y_max - (y_max - y_min) * 0.15, z], [x_min + (x_max - x_min) * 0.25, y_min + (y_max - y_min) * 0.25, z]),
    ]
    static_zone = (
        [x_min + (x_max - x_min) * 0.12, y_min + (y_max - y_min) * 0.12, z],
        [x_max - (x_max - x_min) * 0.10, y_max - (y_max - y_min) * 0.10, z],
    )
    return paths, [static_zone[0], static_zone[1]], z, False


def _uses_world_translation(binding: dict | None, animation_path: str) -> bool:
    motion = str((binding or {}).get("motion", "")).lower()
    motion_tokens = [token for token in motion.replace("-", "_").split("_") if token]
    animation = animation_path.lower()
    if any(token in {"walk", "walking", "run", "running"} for token in motion_tokens):
        return True
    if any(token in motion_tokens for token in ["idle", "standing", "wait", "pause", "talk", "talking", "look", "looking", "bench"]):
        return False
    return "walk" in animation or "run" in animation


def _animation_loop_reset_risk(animation_path: str) -> bool:
    animation = str(animation_path or "").lower()
    if "citysamplecrowd" in animation and "walk" in animation and "inplace" not in animation:
        return True
    return False


def _citypark_local_complete_movers() -> list[tuple[str, str, str]]:
    return [
        (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["walk"], "fab_aria_blake_game_ready"),
        (CITYPARK_MAN_MESHES[0], CITYPARK_MAN_ANIMS["walk"], "fab_modern_male_full_complete"),
        (CITYPARK_MAN_MESHES[1], CITYPARK_MAN_ANIMS["walk"], "fab_modern_male_full_complete"),
        (CITYPARK_MAN_MESHES[2], CITYPARK_MAN_ANIMS["walk"], "fab_modern_male_full_complete"),
        (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["walk"], "fab_aria_blake_game_ready"),
        (CITYPARK_MAN_MESHES[3], CITYPARK_MAN_ANIMS["walk"], "fab_modern_male_full_complete"),
    ]


def _common_complete_movers() -> list[tuple[str, str, str]]:
    return [
        (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["walk"], "fab_aria_blake_game_ready"),
        (BANDIT_MESHES[0], BANDIT_ANIMS["walk"], "fab_bandit_complete_character"),
        (BANDIT_MESHES[1], BANDIT_ANIMS["walk"], "fab_bandit_complete_character"),
        (BANDIT_MESHES[2], BANDIT_ANIMS["walk"], "fab_bandit_complete_character"),
        (BANDIT_MESHES[3], BANDIT_ANIMS["walk"], "fab_bandit_complete_character"),
    ]


def _stable_moving_character_binding(scene_id: str, moving_index: int) -> tuple[str, str, str] | None:
    if scene_id in {"citypark_promenade_day", "citypark_promenade_night", "warehouse_day", "car_dealer_showcase_day"} or _is_downtown_west_scene(scene_id):
        pool = _citypark_local_complete_movers()
        return pool[moving_index % len(pool)]
    pool = _common_complete_movers()
    if moving_index >= len(pool) * 4:
        return None
    return pool[moving_index % len(pool)]


def _stationary_animation_for_motion(source: str, motion: str) -> tuple[str, str]:
    motion_text = str(motion or "").lower()
    if "phone" in motion_text:
        normalized_motion = "phone_idle"
    elif "talk" in motion_text or "speak" in motion_text:
        normalized_motion = "talking"
    elif "look" in motion_text:
        normalized_motion = "looking_up"
    else:
        normalized_motion = "standing"
    if source == "fab_aria_blake_game_ready":
        return ARIA_BLAKE_ANIMS["idle"], normalized_motion
    if source == "fab_bandit_complete_character":
        return BANDIT_ANIMS["idle"], normalized_motion
    if source in {"fab_modern_male_complete", "fab_modern_male_full_complete"}:
        return CITYPARK_MAN_ANIMS["idle"], normalized_motion
    return SCANNED_3D_PEOPLE_ANIMS["idle"], normalized_motion


def _scene19_visible_walk_route(spec: dict, index: int) -> tuple[list[float], list[float]]:
    support = spec["asset_first_plan"]["anchor"]["support_surface"]
    x_min, x_max, y_min, y_max = [float(value) for value in support["bounds"]]
    z = float(support["z"])
    lanes = [
        y_min + 110.0,
        y_min + 190.0,
        y_min + 270.0,
        y_max - 270.0,
        y_max - 190.0,
        y_max - 110.0,
    ]
    lane_y = lanes[index % len(lanes)]
    left = [x_min + 260.0 + (index % 3) * 35.0, lane_y, z]
    right = [x_max - 260.0 - (index % 3) * 35.0, lane_y + ((index % 2) - 0.5) * 36.0, z]
    return (right, left) if index % 2 else (left, right)


def _scene24_visible_walk_route(spec: dict, index: int) -> tuple[list[float], list[float]]:
    support = spec["asset_first_plan"]["anchor"]["support_surface"]
    z = float(support["z"])
    routes = [
        ([93185.0, -3300.0, z], [93185.0, -3040.0, z]),
        ([93265.0, -3300.0, z], [93265.0, -3040.0, z]),
        ([93185.0, -3210.0, z], [93185.0, -2930.0, z]),
        ([93225.0, -3250.0, z], [93225.0, -3250.0, z]),
        ([93265.0, -3210.0, z], [93265.0, -2950.0, z]),
        ([93265.0, -3130.0, z], [93265.0, -2870.0, z]),
    ]
    start, end = routes[index % len(routes)]
    return (end, start) if index % 2 else (start, end)


def _spec_from_asset_first_plan(scene_id: str) -> dict:
    plan = _asset_first_plan(scene_id)
    paths, static_points, people_z, explicit_static_points = _paths_from_anchor(plan["anchor"])
    render_range = plan.get("render", {}).get("frame_range") or [0, 144]
    source_end_frame = int(render_range[1] if len(render_range) > 1 else 144)
    plan_shots = [dict(shot) for shot in plan["shots"]]
    if CAMERA_FILTER:
        filtered = [
            shot
            for shot in plan_shots
            if CAMERA_FILTER in {str(shot.get("camera_name")), str(shot.get("shot_id")), str(shot.get("type"))}
        ]
        if not filtered:
            raise RuntimeError(f"CINEU_HILLSIDE_CAMERA did not match a {scene_id} camera: {CAMERA_FILTER}")
        plan_shots = filtered
    return {
        "scene_id": scene_id,
        "source_level": plan["environment_asset"]["ue_path"],
        "description": f"Asset-first Hillside {scene_id} reproduction using existing level, characters, animations, and readyposed meshes.",
        "people_z": people_z,
        "support_props": _support_props_from_plan(plan),
        "cameras": [_camera_from_plan_shot(shot, source_end_frame) for shot in plan_shots],
        "cuts": [
            {
                "shot_id": str(shot["shot_id"]),
                "camera_name": str(shot["camera_name"]),
                "start_frame": _scaled_frame(int(shot["start_frame"]), source_end_frame),
                "end_frame": _scaled_frame(int(shot["end_frame"]), source_end_frame),
            }
            for shot in plan_shots
        ],
        "paths": paths,
        "static_points": static_points,
        "explicit_static_points": explicit_static_points,
        "asset_first_plan": plan,
    }


def _scene19_spec() -> dict:
    return _spec_from_asset_first_plan("scene19")


def _scene24_spec() -> dict:
    return _spec_from_asset_first_plan("scene24")


def _scene24_indoor_multiroom_spec() -> dict:
    return _spec_from_asset_first_plan("scene24_indoor_multiroom")


def _city_sample_crowd_bindings(placements: list[tuple[list[float], list[float]]] | None = None) -> list[tuple]:
    base = [
        (CITY_SAMPLE_CROWD_VARIANTS[0]["host"], CITY_SAMPLE_CROWD_ANIMS["male_walk_in_place"], "walking", "fab_city_sample_crowds_modular", 0),
        (CITY_SAMPLE_CROWD_VARIANTS[1]["host"], CITY_SAMPLE_CROWD_ANIMS["female_phone"], "phone_idle", "fab_city_sample_crowds_modular", 1),
        (CITY_SAMPLE_CROWD_VARIANTS[2]["host"], CITY_SAMPLE_CROWD_ANIMS["male_phone"], "phone_idle", "fab_city_sample_crowds_modular", 2),
        (CITY_SAMPLE_CROWD_VARIANTS[3]["host"], CITY_SAMPLE_CROWD_ANIMS["male_walk_in_place"], "walking", "fab_city_sample_crowds_modular", 3),
    ]
    bindings = []
    for index, (mesh, animation, motion, source, variant_index) in enumerate(base):
        start, end = placements[index] if placements is not None else (None, None)
        bindings.append((mesh, animation, motion, source, start, end, variant_index))
    return bindings


def _citypark_new_environment_placements(scene_id: str) -> list[tuple[list[float], list[float]]]:
    if scene_id == "warehouse_day":
        z = 5.0
        return [
            ([-3200.0, -4750.0, z], [-1900.0, -4690.0, z]),
            ([-2800.0, -4450.0, z], [-1500.0, -4490.0, z]),
            ([-2400.0, -4800.0, z], [-1100.0, -4740.0, z]),
            ([-2000.0, -4400.0, z], [-700.0, -4440.0, z]),
            ([-1600.0, -4750.0, z], [-300.0, -4690.0, z]),
            ([-1200.0, -4350.0, z], [100.0, -4390.0, z]),
            ([-800.0, -4700.0, z], [500.0, -4640.0, z]),
            ([-400.0, -4300.0, z], [900.0, -4340.0, z]),
            ([400.0, -4000.0, z], [-900.0, -4000.0, z]),
            ([800.0, -3600.0, z], [-500.0, -3600.0, z]),
            ([1150.0, -3650.0, z], [-3200.0, -3650.0, z]),
            ([1000.0, -3250.0, z], [-3000.0, -3250.0, z]),
            ([-2350.0, -4600.0, z], [-2350.0, -1200.0, z]),
            ([-1850.0, -4500.0, z], [-1850.0, -1100.0, z]),
            ([-1350.0, -4400.0, z], [-1350.0, -1000.0, z]),
            ([-850.0, -4300.0, z], [-850.0, -1100.0, z]),
            ([-350.0, -4200.0, z], [-350.0, -1200.0, z]),
            ([250.0, -4100.0, z], [250.0, -1250.0, z]),
            ([-3700.0, -1450.0, z], [-2350.0, -1450.0, z]),
            ([-3150.0, -1300.0, z], [-1850.0, -1300.0, z]),
            ([-2400.0, -1500.0, z], [-900.0, -1500.0, z]),
            ([-1600.0, -1350.0, z], [100.0, -1350.0, z]),
            ([-3600.0, -2450.0, z], [900.0, -2450.0, z]),
            ([950.0, -2050.0, z], [-3400.0, -2050.0, z]),
        ]
    if scene_id == "car_dealer_showcase_day":
        z = 2.0
        return [
            ([-2600.0, -6500.0, z], [1600.0, -6500.0, z]),
            ([-2400.0, -6250.0, z], [1700.0, -6250.0, z]),
            ([-2200.0, -6000.0, z], [1800.0, -6000.0, z]),
            ([1700.0, -6675.0, z], [-2400.0, -6675.0, z]),
            ([1600.0, -7050.0, z], [-950.0, -7050.0, z]),
            ([1500.0, -6125.0, z], [-2200.0, -6125.0, z]),
            ([-3000.0, -7000.0, z], [-3000.0, -5200.0, z]),
            ([1300.0, -6950.0, z], [-1600.0, -5525.0, z]),
            ([-1100.0, -6900.0, z], [-1100.0, -5250.0, z]),
            ([-450.0, -6900.0, z], [-450.0, -5250.0, z]),
            ([250.0, -6900.0, z], [250.0, -5400.0, z]),
            ([850.0, -6800.0, z], [850.0, -5200.0, z]),
            ([1450.0, -6650.0, z], [1450.0, -5400.0, z]),
            ([-2100.0, -6300.0, z], [500.0, -5450.0, z]),
            ([-700.0, -6050.0, z], [-700.0, -6050.0, z]),
            ([1000.0, -6000.0, z], [1000.0, -6000.0, z]),
            ([250.0, -6400.0, z], [250.0, -6400.0, z]),
            ([-1500.0, -5600.0, z], [1600.0, -5600.0, z]),
            ([50.0, -6325.0, z], [50.0, -6325.0, z]),
            ([850.0, -5850.0, z], [850.0, -5850.0, z]),
            ([-1500.0, -6375.0, z], [-1500.0, -6375.0, z]),
            ([1400.0, -6125.0, z], [1400.0, -6125.0, z]),
            ([-2800.0, -5750.0, z], [1800.0, -5750.0, z]),
            ([1900.0, -5875.0, z], [-2400.0, -5875.0, z]),
        ]
    if scene_id in WORLD_TEMPLATE_6_7_SCENE_IDS:
        z = 2.0
        return _world_template_6_7_native_routes([
            ([-4900.0, 3570.0, z], [-3820.0, 3590.0, z]),
            ([-3680.0, 3550.0, z], [-2600.0, 3520.0, z]),
            ([-2460.0, 3520.0, z], [-1380.0, 3540.0, z]),
            ([-1240.0, 3540.0, z], [-280.0, 3580.0, z]),
            ([-320.0, 3740.0, z], [-1400.0, 3720.0, z]),
            ([-1540.0, 3720.0, z], [-2620.0, 3730.0, z]),
            ([-2760.0, 3730.0, z], [-3340.0, 3760.0, z]),
            ([-3980.0, 3760.0, z], [-5060.0, 3730.0, z]),
            ([-5100.0, 4230.0, z], [-4020.0, 4260.0, z]),
            ([-3880.0, 4250.0, z], [-2800.0, 4220.0, z]),
            ([-2660.0, 4240.0, z], [-1580.0, 4260.0, z]),
            ([-1440.0, 4250.0, z], [-360.0, 4240.0, z]),
            ([-5250.0, 4050.0, z], [-4400.0, 4040.0, z]),
            ([-550.0, 3190.0, z], [-550.0, 1710.0, z]),
            ([-3200.0, 3390.0, z], [-2460.0, 3380.0, z]),
            ([-2000.0, 3380.0, z], [-1050.0, 3400.0, z]),
            ([-3400.0, 3990.0, z], [-3400.0, 3990.0, z]),
            ([-3520.0, 4090.0, z], [-3520.0, 4090.0, z]),
            ([-2840.0, 4020.0, z], [-2840.0, 4020.0, z]),
            ([-2630.0, 3910.0, z], [-2630.0, 3910.0, z]),
            ([-1860.0, 4020.0, z], [-1860.0, 4020.0, z]),
            ([-1670.0, 3950.0, z], [-1670.0, 3950.0, z]),
            ([-1200.0, 3950.0, z], [-1200.0, 3950.0, z]),
            ([-930.0, 3980.0, z], [-930.0, 3980.0, z]),
            ([-670.0, 3990.0, z], [-670.0, 3990.0, z]),
            ([-5000.0, 3400.0, z], [-3800.0, 3380.0, z]),
            ([-3730.0, 3390.0, z], [-2700.0, 3380.0, z]),
            ([-4230.0, 3950.0, z], [-4230.0, 3950.0, z]),
            ([-4450.0, 3900.0, z], [-4450.0, 3900.0, z]),
        ])
    if _is_downtown_west_scene(scene_id):
        z = 2.0
        return _downtown_west_native_routes([
            ([3120.0, 4500.0, z], [1720.0, 4480.0, z]),
            ([1760.0, 4420.0, z], [3140.0, 4460.0, z]),
            ([3000.0, 4580.0, z], [1840.0, 4520.0, z]),
            ([1900.0, 4700.0, z], [3000.0, 4820.0, z]),
            ([1180.0, 4520.0, z], [1140.0, 5820.0, z]),
            ([1240.0, 5800.0, z], [980.0, 4300.0, z]),
            ([1320.0, 5450.0, z], [2350.0, 5350.0, z]),
            ([2380.0, 5320.0, z], [1320.0, 5200.0, z]),
            ([1700.0, 5060.0, z], [3180.0, 5440.0, z]),
            ([3060.0, 5500.0, z], [1720.0, 5160.0, z]),
            ([620.0, 4260.0, z], [1320.0, 4620.0, z]),
            ([1420.0, 4660.0, z], [520.0, 4300.0, z]),
            ([2500.0, 5060.0, z], [3100.0, 5520.0, z]),
            ([1520.0, 4880.0, z], [780.0, 4620.0, z]),
            ([780.0, 4900.0, z], [1500.0, 5200.0, z]),
            ([1500.0, 5200.0, z], [910.0, 4800.0, z]),
            ([1060.0, 4240.0, z], [1060.0, 4240.0, z]),
            ([1260.0, 5600.0, z], [1260.0, 5600.0, z]),
            ([1880.0, 5180.0, z], [1880.0, 5180.0, z]),
            ([2380.0, 5430.0, z], [2380.0, 5430.0, z]),
            ([3020.0, 5040.0, z], [3020.0, 5040.0, z]),
            ([920.0, 4860.0, z], [920.0, 4860.0, z]),
            ([2500.0, 4760.0, z], [2500.0, 4760.0, z]),
            ([3100.0, 5220.0, z], [3100.0, 5220.0, z]),
            ([2800.0, 5050.0, z], [2800.0, 5550.0, z]),
            ([1320.0, 5820.0, z], [1320.0, 5820.0, z]),
            ([2160.0, 4940.0, z], [2160.0, 4940.0, z]),
            ([2150.0, 5320.0, z], [2150.0, 5320.0, z]),
            ([2600.0, 4720.0, z], [2600.0, 4720.0, z]),
            ([320.0, 4560.0, z], [320.0, 4560.0, z]),
            ([850.0, 4320.0, z], [850.0, 4320.0, z]),
            ([3000.0, 5320.0, z], [3000.0, 5320.0, z]),
        ])
    z = 2.0
    return [
        ([-4300.0, -7600.0, z], [2500.0, -7600.0, z]),
        ([-4200.0, -7100.0, z], [3000.0, -7100.0, z]),
        ([-4100.0, -6600.0, z], [3150.0, -6600.0, z]),
        ([-3950.0, -6100.0, z], [3050.0, -6100.0, z]),
        ([-3900.0, -5600.0, z], [2900.0, -5600.0, z]),
        ([-3800.0, -5100.0, z], [2700.0, -5100.0, z]),
        ([-3700.0, -4600.0, z], [-2100.0, -4600.0, z]),
        ([1400.0, -4600.0, z], [3400.0, -4600.0, z]),
        ([3400.0, -7250.0, z], [-3600.0, -7250.0, z]),
        ([3200.0, -6750.0, z], [-3500.0, -6750.0, z]),
        ([3000.0, -6250.0, z], [-3400.0, -6250.0, z]),
        ([2800.0, -5750.0, z], [-3300.0, -5750.0, z]),
        ([-4500.0, -7300.0, z], [-4500.0, -3300.0, z]),
        ([-3450.0, -7350.0, z], [-3450.0, -3000.0, z]),
        ([-2500.0, -7250.0, z], [-2500.0, -3000.0, z]),
        ([1500.0, -7350.0, z], [1500.0, -3100.0, z]),
        ([2500.0, -7200.0, z], [2500.0, -3200.0, z]),
        ([3600.0, -6800.0, z], [3600.0, -3800.0, z]),
        ([-4200.0, -3600.0, z], [-4200.0, -3600.0, z]),
        ([-3000.0, -3900.0, z], [-3000.0, -3900.0, z]),
        ([-1500.0, -7200.0, z], [-1500.0, -7200.0, z]),
        ([500.0, -7200.0, z], [500.0, -7200.0, z]),
        ([-4200.0, -4300.0, z], [3200.0, -4300.0, z]),
        ([3100.0, -3700.0, z], [-3900.0, -3700.0, z]),
    ]


def _complete_free_casual_entry(entry: tuple) -> tuple:
    if len(entry) < 4 or entry[3] != FREE_CASUAL_GIRL_LEGACY_MODULAR_SOURCE:
        return entry

    variant_index = 0
    if len(entry) >= 7 and isinstance(entry[6], int):
        variant_index = int(entry[6])
    elif len(entry) > 4 and isinstance(entry[4], int):
        variant_index = int(entry[4])
    animation = str(entry[1])
    motion = str(entry[2])
    if animation == FREE_CASUAL_GIRL_ANIMS["idle"]:
        animation_kind = "idle"
    elif animation == FREE_CASUAL_GIRL_ANIMS["run"]:
        animation_kind = "run"
    else:
        animation_kind = "walk"

    if variant_index % 4 == 0:
        mesh = FREE_CASUAL_GIRL_MESH
        replacement_animation = animation
        source = FREE_CASUAL_GIRL_SOURCE
        replacement_motion = motion
    elif variant_index % 4 == 1:
        mesh = SCANNED_3D_PEOPLE_MESHES[5]
        replacement_animation = SCANNED_3D_PEOPLE_ANIMS["idle" if animation_kind == "idle" else "walk"]
        source = "fab_scanned_3d_people_pack"
        replacement_motion = _complete_free_casual_replacement_motion(motion, animation_kind, "scanned")
    elif variant_index % 4 == 2:
        mesh = CITYPARK_MAN_MESHES[variant_index % len(CITYPARK_MAN_MESHES)]
        replacement_animation = CITYPARK_MAN_ANIMS["idle" if animation_kind == "idle" else ("run" if animation_kind == "run" else "walk")]
        source = "fab_modern_male_full_complete"
        replacement_motion = _complete_free_casual_replacement_motion(motion, animation_kind, "modern_male")
    else:
        mesh = MAN_MESHES[-1]
        replacement_animation = MAN_ANIMS[7] if animation_kind == "idle" else (MAN_ANIMS[8] if "bag" in motion.lower() else MAN_ANIMS[1])
        source = "existing_twinmotion_rigged_character"
        replacement_motion = _complete_free_casual_replacement_motion(motion, animation_kind, "twinmotion")

    normalized = [mesh, replacement_animation, replacement_motion, source]
    if len(entry) >= 6 and (
        (entry[4] is None or isinstance(entry[4], (list, tuple)))
        and (entry[5] is None or isinstance(entry[5], (list, tuple)))
    ):
        normalized.extend([entry[4], entry[5]])
    return tuple(normalized)


def _complete_free_casual_replacement_motion(motion: str, animation_kind: str, replacement: str) -> str:
    motion_text = motion.lower()
    if animation_kind == "idle":
        if "phone" in motion_text:
            return "phone_idle"
        if "talk" in motion_text:
            return "talking"
        if "look" in motion_text:
            return "looking_up"
        return "standing"
    if animation_kind == "run" and replacement != "modern_male":
        return "walking_slow"
    if "phone" in motion_text:
        return "phone_walk"
    if "bag" in motion_text:
        return "walking_bag"
    if replacement == "scanned":
        return "walking_shift"
    if replacement == "twinmotion":
        return "walking_window_browse"
    return motion


def _production_citypark_new_environment_bindings(scene_id: str, count: int) -> list[dict]:
    if scene_id == "warehouse_day":
        scanned_walk = SCANNED_3D_PEOPLE_ANIMS["walk"]
        scanned_idle = SCANNED_3D_PEOPLE_ANIMS["idle"]
        # The warehouse MRQ pass proved body-only modular crowds visually unsafe here.
        base = [
            (SCANNED_3D_PEOPLE_MESHES[0], scanned_walk, "walking_a", "fab_scanned_3d_people_pack"),
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["walk"], "walking_b", "fab_aria_blake_game_ready"),
            (SCANNED_3D_PEOPLE_MESHES[1], scanned_walk, "walking_slow_a", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[2], scanned_walk, "phone_walk_a", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[3], scanned_walk, "walking_bag_a", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[4], scanned_walk, "walking_shift_a", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[5], scanned_walk, "walking_shift_b", "fab_scanned_3d_people_pack"),
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["walk"], "walking_shift_c", "fab_aria_blake_game_ready"),
            (SCANNED_3D_PEOPLE_MESHES[0], scanned_walk, "walking_lane_a", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[1], scanned_walk, "phone_walk_b", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[2], scanned_walk, "walking_lane_b", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[3], scanned_walk, "talking_walk_a", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[4], scanned_walk, "walking_depth_a", "fab_scanned_3d_people_pack"),
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["walk"], "walking_depth_b", "fab_aria_blake_game_ready"),
            (SCANNED_3D_PEOPLE_MESHES[5], scanned_walk, "walking_depth_c", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[0], scanned_walk, "walking_depth_d", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[1], scanned_walk, "walking_shift_d", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[0], scanned_walk, "walking_shift_e", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[2], scanned_idle, "standing", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[3], scanned_idle, "looking_up", "fab_scanned_3d_people_pack"),
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["walk"], "phone_walk_c", "fab_aria_blake_game_ready"),
            (SCANNED_3D_PEOPLE_MESHES[4], scanned_idle, "talking", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[5], scanned_walk, "walking_lane_c", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[1], scanned_walk, "walking_lane_d", "fab_scanned_3d_people_pack"),
        ]
    elif scene_id == "car_dealer_showcase_day":
        base = [
            (SCANNED_3D_PEOPLE_MESHES[0], SCANNED_3D_PEOPLE_ANIMS["walk"], "walking_a", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[1], SCANNED_3D_PEOPLE_ANIMS["walk"], "walking_b", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[2], SCANNED_3D_PEOPLE_ANIMS["walk"], "walking_c", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[3], SCANNED_3D_PEOPLE_ANIMS["walk"], "walking_d", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[4], SCANNED_3D_PEOPLE_ANIMS["walk"], "walking_e", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[5], SCANNED_3D_PEOPLE_ANIMS["walk"], "walking_f", "fab_scanned_3d_people_pack"),
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["walk"], "walking_g", "fab_aria_blake_game_ready"),
            (SCANNED_3D_PEOPLE_MESHES[5], SCANNED_3D_PEOPLE_ANIMS["walk"], "walking_h", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[0], SCANNED_3D_PEOPLE_ANIMS["walk"], "phone_walk_a", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[1], SCANNED_3D_PEOPLE_ANIMS["walk"], "phone_walk_b", "fab_scanned_3d_people_pack"),
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["walk"], "phone_walk_c", "fab_aria_blake_game_ready"),
            (SCANNED_3D_PEOPLE_MESHES[2], SCANNED_3D_PEOPLE_ANIMS["walk"], "walking_bag_a", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[3], SCANNED_3D_PEOPLE_ANIMS["walk"], "walking_bag_b", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[4], SCANNED_3D_PEOPLE_ANIMS["walk"], "walking_slow_a", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[4], SCANNED_3D_PEOPLE_ANIMS["idle"], "standing_a", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[5], SCANNED_3D_PEOPLE_ANIMS["idle"], "looking_up_a", "fab_scanned_3d_people_pack"),
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["idle"], "phone_idle_a", "fab_aria_blake_game_ready"),
            (SCANNED_3D_PEOPLE_MESHES[0], SCANNED_3D_PEOPLE_ANIMS["walk"], "talking_walk_a", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[1], SCANNED_3D_PEOPLE_ANIMS["dance"], "talking_a", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[2], SCANNED_3D_PEOPLE_ANIMS["idle"], "standing_b", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[5], SCANNED_3D_PEOPLE_ANIMS["idle"], "looking_up_b", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[3], SCANNED_3D_PEOPLE_ANIMS["idle"], "phone_idle_b", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[4], SCANNED_3D_PEOPLE_ANIMS["walk"], "walking_shift_a", "fab_scanned_3d_people_pack"),
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["walk"], "walking_shift_b", "fab_aria_blake_game_ready"),
        ]
    elif scene_id in WORLD_TEMPLATE_6_7_SCENE_IDS:
        routes = _citypark_new_environment_placements(scene_id)
        scanned_walk = SCANNED_3D_PEOPLE_ANIMS["walk"]
        scanned_idle = SCANNED_3D_PEOPLE_ANIMS["idle"]
        base = [
            (SCANNED_3D_PEOPLE_MESHES[0], scanned_walk, "reference_topdown_slow_walk_carla", "fab_scanned_3d_people_pack", *routes[0]),
            (SCANNED_3D_PEOPLE_MESHES[1], scanned_walk, "reference_topdown_slow_walk_claudia", "fab_scanned_3d_people_pack", *routes[1]),
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["walk"], "reference_entry_walk_aria_a", "fab_aria_blake_game_ready", *routes[2]),
            (SCANNED_3D_PEOPLE_MESHES[2], scanned_walk, "reference_cafe_walk_eric", "fab_scanned_3d_people_pack", *routes[3]),
            (SCANNED_3D_PEOPLE_MESHES[3], scanned_walk, "reference_brick_plaza_walk_manuel", "fab_scanned_3d_people_pack", *routes[4]),
            (SCANNED_3D_PEOPLE_MESHES[4], scanned_walk, "reference_curved_curb_walk_nathan", "fab_scanned_3d_people_pack", *routes[5]),
            (SCANNED_3D_PEOPLE_MESHES[5], scanned_walk, "reference_sidewalk_phone_walk_sophia", "fab_scanned_3d_people_pack", *routes[6]),
            (SCANNED_3D_PEOPLE_MESHES[0], scanned_walk, "reference_umbrella_walk_carla", "fab_scanned_3d_people_pack", *routes[7]),
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["walk"], "reference_entrance_cross_walk_aria_b", "fab_aria_blake_game_ready", *routes[8]),
            (SCANNED_3D_PEOPLE_MESHES[1], scanned_walk, "reference_sign_slow_walk_claudia", "fab_scanned_3d_people_pack", *routes[9]),
            (SCANNED_3D_PEOPLE_MESHES[2], scanned_walk, "reference_window_browse_eric", "fab_scanned_3d_people_pack", *routes[10]),
            (SCANNED_3D_PEOPLE_MESHES[3], scanned_walk, "reference_return_walk_manuel", "fab_scanned_3d_people_pack", *routes[11]),
            (SCANNED_3D_PEOPLE_MESHES[4], scanned_walk, "reference_deep_plaza_walk_nathan", "fab_scanned_3d_people_pack", *routes[12]),
            (SCANNED_3D_PEOPLE_MESHES[5], scanned_walk, "reference_deep_return_walk_sophia", "fab_scanned_3d_people_pack", *routes[13]),
            (SCANNED_3D_PEOPLE_MESHES[0], scanned_walk, "reference_slow_streetfront_walk_carla", "fab_scanned_3d_people_pack", *routes[14]),
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["walk"], "reference_cafe_return_walk_aria_c", "fab_aria_blake_game_ready", *routes[15]),
            (SCANNED_3D_PEOPLE_MESHES[1], scanned_idle, "reference_doorway_standing_claudia", "fab_scanned_3d_people_pack", *routes[16]),
            (SCANNED_3D_PEOPLE_MESHES[2], scanned_idle, "reference_table_talking_eric", "fab_scanned_3d_people_pack", *routes[17]),
            (SCANNED_3D_PEOPLE_MESHES[3], scanned_idle, "reference_phone_idle_manuel", "fab_scanned_3d_people_pack", *routes[18]),
            (SCANNED_3D_PEOPLE_MESHES[4], scanned_idle, "reference_umbrella_wait_nathan", "fab_scanned_3d_people_pack", *routes[19]),
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["idle"], "reference_sign_pause_aria_d", "fab_aria_blake_game_ready", *routes[20]),
            (SCANNED_3D_PEOPLE_MESHES[5], scanned_idle, "reference_window_talking_sophia", "fab_scanned_3d_people_pack", *routes[21]),
            (SCANNED_3D_PEOPLE_MESHES[0], scanned_idle, "reference_looking_up_carla", "fab_scanned_3d_people_pack", *routes[22]),
            (SCANNED_3D_PEOPLE_MESHES[1], scanned_idle, "reference_planter_wait_claudia", "fab_scanned_3d_people_pack", *routes[23]),
            (SCANNED_3D_PEOPLE_MESHES[2], scanned_idle, "reference_far_corner_pause_eric", "fab_scanned_3d_people_pack", *routes[24]),
            (SCANNED_3D_PEOPLE_MESHES[3], scanned_walk, "reference_late_entry_walk_manuel", "fab_scanned_3d_people_pack", *routes[25]),
            (SCANNED_3D_PEOPLE_MESHES[4], scanned_walk, "reference_late_return_walk_nathan", "fab_scanned_3d_people_pack", *routes[26]),
            (SCANNED_3D_PEOPLE_MESHES[5], scanned_idle, "reference_far_brick_wait_sophia", "fab_scanned_3d_people_pack", *routes[28]),
        ]
    elif _is_downtown_west_scene(scene_id):
        scanned_walk = SCANNED_3D_PEOPLE_ANIMS["walk"]
        scanned_idle = SCANNED_3D_PEOPLE_ANIMS["idle"]
        base = [
            *(
                _city_sample_crowd_bindings(
                    [
                        (_downtown_west_native_location([1100.0, 4440.0, 2.0]), _downtown_west_native_location([1280.0, 5700.0, 2.0])),
                        (_downtown_west_native_location([1280.0, 5620.0, 2.0]), _downtown_west_native_location([980.0, 4520.0, 2.0])),
                        (_downtown_west_native_location([2460.0, 5440.0, 2.0]), _downtown_west_native_location([2900.0, 5020.0, 2.0])),
                        (_downtown_west_native_location([2820.0, 5160.0, 2.0]), _downtown_west_native_location([2360.0, 5480.0, 2.0])),
                    ]
                )
                if DOWNTOWN_WEST_CITY_SAMPLE_MODULAR_ENABLED
                else []
            ),
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["walk"], "storefront_return_walk_aria", "fab_aria_blake_game_ready"),
            (SCANNED_3D_PEOPLE_MESHES[2], scanned_walk, "businessman_window_walk_a", "fab_scanned_3d_people_pack"),
            (FREE_CASUAL_GIRL_MESH, FREE_CASUAL_GIRL_ANIMS["walk"], "casual_shopfront_walk_a", FREE_CASUAL_GIRL_SOURCE),
            (SCANNED_3D_PEOPLE_MESHES[3], scanned_walk, "commuter_phone_walk_male_b", "fab_scanned_3d_people_pack"),
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["walk"], "aria_cafe_slow_walk_b", "fab_aria_blake_game_ready"),
            (FREE_CASUAL_GIRL_MESH, FREE_CASUAL_GIRL_ANIMS["idle"], "casual_window_wait_a", FREE_CASUAL_GIRL_SOURCE),
            (SCANNED_3D_PEOPLE_MESHES[4], scanned_walk, "window_browse_male_c", "fab_scanned_3d_people_pack"),
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["walk"], "phone_window_walk_aria_b", "fab_aria_blake_game_ready"),
            (SCANNED_3D_PEOPLE_MESHES[0], scanned_walk, "business_window_diagonal_walk_d", "fab_scanned_3d_people_pack", _downtown_west_native_location([2900.0, 5200.0, 2.0]), _downtown_west_native_location([2500.0, 5500.0, 2.0])),
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["idle"], "talking_cafe_reverse_aria_c", "fab_aria_blake_game_ready", _downtown_west_native_location([3200.0, 5550.0, 2.0]), _downtown_west_native_location([3200.0, 5550.0, 2.0])),
            (FREE_CASUAL_GIRL_MESH, FREE_CASUAL_GIRL_ANIMS["walk"], "casual_business_walk_alt", FREE_CASUAL_GIRL_SOURCE),
            (SCANNED_3D_PEOPLE_MESHES[1], scanned_walk, "business_sidewalk_walk_alt", "fab_scanned_3d_people_pack"),
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["walk"], "aria_storefront_slow_walk_a", "fab_aria_blake_game_ready"),
            (FREE_CASUAL_GIRL_MESH, FREE_CASUAL_GIRL_ANIMS["walk"], "casual_crosswalk_walk_late", FREE_CASUAL_GIRL_SOURCE),
            (SCANNED_3D_PEOPLE_MESHES[5], scanned_idle, "standing_sign_male_d", "fab_scanned_3d_people_pack", _downtown_west_native_location([3200.0, 4450.0, 2.0]), _downtown_west_native_location([3200.0, 4450.0, 2.0])),
            (SCANNED_3D_PEOPLE_MESHES[2], scanned_walk, "window_return_slow_walk_male_b", "fab_scanned_3d_people_pack", _downtown_west_native_location([1700.0, 5660.0, 2.0]), _downtown_west_native_location([1700.0, 5180.0, 2.0])),
            (SCANNED_3D_PEOPLE_MESHES[3], scanned_walk, "looking_up_then_walk_store_sign_male_a", "fab_scanned_3d_people_pack"),
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["idle"], "talking_corner_aria_a", "fab_aria_blake_game_ready"),
            (FREE_CASUAL_GIRL_MESH, FREE_CASUAL_GIRL_ANIMS["idle"], "looking_up_window_casual_b", FREE_CASUAL_GIRL_SOURCE),
            (SCANNED_3D_PEOPLE_MESHES[4], scanned_idle, "standing_bench_wait_male_c", "fab_scanned_3d_people_pack"),
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["idle"], "phone_idle_aria", "fab_aria_blake_game_ready"),
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["idle"], "talking_cafe_aria", "fab_aria_blake_game_ready"),
            (SCANNED_3D_PEOPLE_MESHES[5], scanned_walk, "late_crosswalk_male_d", "fab_scanned_3d_people_pack", _downtown_west_native_location([520.0, 4300.0, 2.0]), _downtown_west_native_location([420.0, 4620.0, 2.0])),
            (FREE_CASUAL_GIRL_MESH, FREE_CASUAL_GIRL_ANIMS["idle"], "window_return_wait_casual_b", FREE_CASUAL_GIRL_SOURCE),
            (SCANNED_3D_PEOPLE_MESHES[0], scanned_idle, "vendor_pause_male_a", "fab_scanned_3d_people_pack"),
            (FREE_CASUAL_GIRL_MESH, FREE_CASUAL_GIRL_ANIMS["idle"], "slow_corner_wait_casual_c", FREE_CASUAL_GIRL_SOURCE),
            (SCANNED_3D_PEOPLE_MESHES[1], scanned_idle, "standing_sign_male_b", "fab_scanned_3d_people_pack"),
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["idle"], "talking_shop_aria", "fab_aria_blake_game_ready"),
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["idle"], "aria_crossing_wait_late", "fab_aria_blake_game_ready"),
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["idle"], "aria_window_wait_late", "fab_aria_blake_game_ready"),
            (FREE_CASUAL_GIRL_MESH, FREE_CASUAL_GIRL_ANIMS["walk"], "casual_plaza_return_walk", FREE_CASUAL_GIRL_SOURCE, _downtown_west_native_location([1500.0, 5600.0, 2.0]), _downtown_west_native_location([1680.0, 5800.0, 2.0])),
            (SCANNED_3D_PEOPLE_MESHES[2], scanned_idle, "standing_depth_male_c", "fab_scanned_3d_people_pack", _downtown_west_native_location([2100.0, 5460.0, 2.0]), _downtown_west_native_location([2100.0, 5460.0, 2.0])),
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["walk"], "aria_bistro_window_walk", "fab_aria_blake_game_ready", _downtown_west_native_location([2300.0, 4900.0, 2.0]), _downtown_west_native_location([2800.0, 4400.0, 2.0])),
            (FREE_CASUAL_GIRL_MESH, FREE_CASUAL_GIRL_ANIMS["walk"], "casual_poster_walk", FREE_CASUAL_GIRL_SOURCE),
            (SCANNED_3D_PEOPLE_MESHES[3], scanned_walk, "late_storefront_walk_manuel", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[4], scanned_walk, "late_plaza_return_walk_nathan", "fab_scanned_3d_people_pack"),
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["walk"], "late_cafe_connector_walk_aria", "fab_aria_blake_game_ready"),
        ]
    else:
        base = [
            (SCANNED_3D_PEOPLE_MESHES[0], SCANNED_3D_PEOPLE_ANIMS["walk"], "walking", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[1], SCANNED_3D_PEOPLE_ANIMS["walk"], "walking", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[2], SCANNED_3D_PEOPLE_ANIMS["walk"], "walking", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[3], SCANNED_3D_PEOPLE_ANIMS["walk"], "walking", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[4], SCANNED_3D_PEOPLE_ANIMS["walk"], "walking", "fab_scanned_3d_people_pack"),
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["walk"], "walking", "fab_aria_blake_game_ready"),
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["run"], "walking_slow", "fab_aria_blake_game_ready"),
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["idle"], "looking_up", "fab_aria_blake_game_ready"),
            (FREE_CASUAL_GIRL_MESH, FREE_CASUAL_GIRL_ANIMS["walk"], "walking", "fab_free_casual_girl_modular", 1),
            (FREE_CASUAL_GIRL_MESH, FREE_CASUAL_GIRL_ANIMS["run"], "walking_slow", "fab_free_casual_girl_modular", 1),
            (FREE_CASUAL_GIRL_MESH, FREE_CASUAL_GIRL_ANIMS["idle"], "talking", "fab_free_casual_girl_modular", 3),
            (FREE_CASUAL_GIRL_MESH, FREE_CASUAL_GIRL_ANIMS["walk"], "walking", "fab_free_casual_girl_modular", 3),
            (FREE_CASUAL_GIRL_MESH, FREE_CASUAL_GIRL_ANIMS["idle"], "standing", "fab_free_casual_girl_modular", 1),
            (FREE_CASUAL_GIRL_MESH, FREE_CASUAL_GIRL_ANIMS["run"], "walking_slow", "fab_free_casual_girl_modular", 0),
            (SCANNED_3D_PEOPLE_MESHES[0], SCANNED_3D_PEOPLE_ANIMS["idle"], "standing", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[2], SCANNED_3D_PEOPLE_ANIMS["idle"], "looking_up", "fab_scanned_3d_people_pack"),
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["idle"], "phone_idle", "fab_aria_blake_game_ready"),
            (FREE_CASUAL_GIRL_MESH, FREE_CASUAL_GIRL_ANIMS["walk"], "walking_bag", "fab_free_casual_girl_modular", 1),
            (SCANNED_3D_PEOPLE_MESHES[4], SCANNED_3D_PEOPLE_ANIMS["dance"], "talking", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[3], SCANNED_3D_PEOPLE_ANIMS["idle"], "looking_up", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[1], SCANNED_3D_PEOPLE_ANIMS["dance"], "talking", "fab_scanned_3d_people_pack"),
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["idle"], "standing", "fab_aria_blake_game_ready"),
            (FREE_CASUAL_GIRL_MESH, FREE_CASUAL_GIRL_ANIMS["walk"], "walking", "fab_free_casual_girl_modular", 0),
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["run"], "walking_slow_alt", "fab_aria_blake_game_ready"),
        ]
    base = [_complete_free_casual_entry(entry) for entry in base]
    if scene_id in FORMAL_COMPLETE_CHARACTER_ONLY_SCENES:
        base = [entry for entry in base if entry[3] in FORMAL_VERIFIED_MOVING_CHARACTER_SOURCES]
    if _is_downtown_west_scene(scene_id):
        balanced_base = []
        for index, entry in enumerate(base):
            moving = _uses_world_translation({"motion": entry[2]}, str(entry[1]))
            appearance_index = index % (len(SCANNED_3D_PEOPLE_MESHES) + 1)
            if appearance_index < len(SCANNED_3D_PEOPLE_MESHES):
                mesh = SCANNED_3D_PEOPLE_MESHES[appearance_index]
                action_palette = (
                    [SCANNED_3D_PEOPLE_ANIMS["walk"], *SCANNED_3D_PEOPLE_RETARGETED_WALKS]
                    if moving
                    else [SCANNED_3D_PEOPLE_ANIMS["idle"], *SCANNED_3D_PEOPLE_RETARGETED_IDLES]
                )
                animation = action_palette[index % len(action_palette)]
                source = "fab_scanned_3d_people_pack"
            else:
                mesh = ARIA_BLAKE_MESH
                animation = ARIA_BLAKE_ANIMS["walk" if moving else "idle"]
                source = "fab_aria_blake_game_ready"
            if not moving and "phone" in str(entry[2]).lower():
                phone_mesh_index = appearance_index if appearance_index < len(SCANNED_3D_PEOPLE_MESHES) else 4
                mesh = SCANNED_3D_PEOPLE_MESHES[phone_mesh_index]
                animation = SCANNED_3D_PEOPLE_RETARGETED_PHONE_ACTIONS[index % len(SCANNED_3D_PEOPLE_RETARGETED_PHONE_ACTIONS)]
                source = "fab_scanned_3d_people_pack"
            balanced_base.append((mesh, animation, entry[2], source, *entry[4:]))
        base = balanced_base
    placements = _citypark_new_environment_placements(scene_id)
    bindings = []
    for index, entry in enumerate(base[:count]):
        mesh, animation, motion, source = entry[:4]
        start, end = placements[index % len(placements)]
        explicit_entry_route = False
        if len(entry) >= 6 and isinstance(entry[4], (list, tuple)) and isinstance(entry[5], (list, tuple)):
            start = [float(value) for value in entry[4]]
            end = [float(value) for value in entry[5]]
            explicit_entry_route = True
        if _is_downtown_west_scene(scene_id):
            binding_moves = _uses_world_translation({"motion": motion}, str(animation))
            if binding_moves and _xy_distance(start, end) < 250.0:
                moving_routes = [route for route in placements if _xy_distance(route[0], route[1]) >= 250.0]
                if moving_routes:
                    start, end = moving_routes[(index + 5) % len(moving_routes)]
            if not explicit_entry_route:
                start, end = _downtown_west_naturalized_route(start, end, index, scene_id)
            if not binding_moves and (not explicit_entry_route or scene_id not in WORLD_TEMPLATE_6_7_SCENE_IDS):
                static_safe_points = {
                    5: [1040.0, 1060.0, 2.0],
                    14: [650.0, -480.0, 2.0],
                    17: [1240.0, 760.0, 2.0],
                    28: [340.0, 260.0, 2.0],
                    31: [3140.0, 20.0, 2.0],
                }
                if index in static_safe_points:
                    start = list(static_safe_points[index])
                    end = list(static_safe_points[index])
        if scene_id in WORLD_TEMPLATE_6_7_SCENE_IDS and not explicit_entry_route:
            placed_people = [
                {
                    "start": list(existing["start_location"]),
                    "end": list(existing["end_location"]),
                    "waypoints": existing.get("waypoints"),
                }
                for existing in bindings
            ]
            start, end = _avoid_existing_root_people(list(start), list(end), placed_people, scene_id, min_spacing=180.0)
        if not _uses_world_translation({"motion": motion}, str(animation)):
            end = list(start)
        binding = {
            "actor_name": f"CineU_{scene_id}_skeletal_{index:02d}",
            "mesh_path": mesh,
            "animation_path": animation,
            "motion": motion,
            "source": source,
            "start_location": list(start),
            "end_location": list(end),
        }
        if explicit_entry_route:
            binding["explicit_route"] = True
        if _is_downtown_west_scene(scene_id):
            waypoints = _downtown_west_route_waypoints(list(start), list(end), index, scene_id)
            if waypoints:
                binding["waypoints"] = waypoints
        modular_variant = None
        if len(entry) > 6:
            modular_variant = entry[6]
        elif len(entry) > 4 and not isinstance(entry[4], (list, tuple)):
            modular_variant = entry[4]
        if modular_variant is not None:
            binding["modular_variant"] = int(modular_variant)
        bindings.append(binding)
    return bindings


def _production_animation_bindings(scene_id: str, count: int) -> list[dict]:
    if scene_id in {"warehouse_day", "car_dealer_showcase_day"} or scene_id in WORLD_TEMPLATE_6_7_SCENE_IDS or _is_downtown_west_scene(scene_id):
        return _production_citypark_new_environment_bindings(scene_id, count)
    if scene_id.startswith("museum_gallery"):
        starts = [
            [-4140.0, -700.0, 2.0], [-4000.0, -360.0, 2.0], [-3860.0, -40.0, 2.0],
            [-3640.0, -650.0, 2.0], [-3500.0, -300.0, 2.0], [-3360.0, 50.0, 2.0],
            [-3140.0, -720.0, 2.0], [-3000.0, -390.0, 2.0], [-2860.0, -70.0, 2.0],
            [-2640.0, -650.0, 2.0], [-2500.0, -310.0, 2.0], [-2360.0, 30.0, 2.0],
            [-2140.0, -740.0, 2.0], [-2000.0, -400.0, 2.0], [-1860.0, -80.0, 2.0],
            [-1660.0, -660.0, 2.0], [-1580.0, -300.0, 2.0], [-1480.0, 50.0, 2.0],
            [-4210.0, -120.0, 2.0], [-3800.0, -820.0, 2.0], [-3320.0, -820.0, 2.0],
            [-2780.0, -820.0, 2.0], [-2300.0, -890.0, 2.0], [-1450.0, -860.0, 2.0],
        ]
        mesh_indices = [0, 1, 2, 3, None, 4, 5, 0, 1, 2, None, 3, 4, 5, 0, 1, None, 2, 3, 4, 5, None, 0, 1]
        stationary_motions = ["standing", "looking_up", "phone_idle", "talking", "standing", "looking_up"]
        walking = []
        moving_appearance_counts: dict[tuple[str, str], int] = {}
        for index, start in enumerate(starts):
            mesh_index = mesh_indices[index]
            is_aria = mesh_index is None
            mesh = ARIA_BLAKE_MESH if is_aria else SCANNED_3D_PEOPLE_MESHES[mesh_index]
            source = "fab_aria_blake_game_ready" if is_aria else "fab_scanned_3d_people_pack"
            if index < 18:
                animation = ARIA_BLAKE_ANIMS["walk"] if is_aria else SCANNED_3D_PEOPLE_ANIMS["walk"]
                appearance_key = (source, mesh)
                appearance_index = moving_appearance_counts.get(appearance_key, 0)
                moving_appearance_counts[appearance_key] = appearance_index + 1
                motion, distance = [
                    ("walking_slow", 420.0),
                    ("walking_gallery", 510.0),
                    ("walking_browse", 600.0),
                ][appearance_index % 3]
                direction = distance if index < 9 else -distance
                end = [start[0] + direction, start[1] + ((index % 3) - 1) * 35.0, start[2]]
            else:
                animation = ARIA_BLAKE_ANIMS["idle"] if is_aria else SCANNED_3D_PEOPLE_ANIMS["idle"]
                end = list(start)
                motion = stationary_motions[index - 18]
            walking.append((mesh, animation, motion, source, start, end))
    elif scene_id.startswith("art_gallery"):
        starts = [
            [-3700.0, -4500.0, 2.0], [-3300.0, -4550.0, 2.0], [-2900.0, -4480.0, 2.0],
            [-2500.0, -4600.0, 2.0], [-4050.0, -5200.0, 2.0], [-3600.0, -5250.0, 2.0],
            [-3150.0, -5150.0, 2.0], [-2700.0, -5300.0, 2.0], [-2250.0, -5180.0, 2.0],
            [-4300.0, -6000.0, 2.0], [-3700.0, -6100.0, 2.0], [-3100.0, -5950.0, 2.0],
            [-2500.0, -6150.0, 2.0], [-1900.0, -6020.0, 2.0], [-4200.0, -6900.0, 2.0],
            [-3350.0, -7000.0, 2.0], [-2500.0, -6850.0, 2.0], [-1650.0, -7050.0, 2.0],
            [-3900.0, -5600.0, 2.0], [-3400.0, -5700.0, 2.0], [-3000.0, -5600.0, 2.0],
            [-2300.0, -5750.0, 2.0], [-1750.0, -5600.0, 2.0], [-1000.0, -6400.0, 2.0],
        ]
        mesh_indices = [0, 1, 2, 3, None, 4, 5, 0, 1, 2, None, 3, 4, 5, 0, 1, None, 2, 3, 4, 5, None, 0, 1]
        stationary_motions = ["standing", "looking_up", "phone_idle", "talking", "standing", "looking_up"]
        walking = []
        moving_appearance_counts: dict[tuple[str, str], int] = {}
        for index, start in enumerate(starts):
            mesh_index = mesh_indices[index]
            is_aria = mesh_index is None
            mesh = ARIA_BLAKE_MESH if is_aria else SCANNED_3D_PEOPLE_MESHES[mesh_index]
            source = "fab_aria_blake_game_ready" if is_aria else "fab_scanned_3d_people_pack"
            if index < 18:
                animation = ARIA_BLAKE_ANIMS["walk"] if is_aria else SCANNED_3D_PEOPLE_ANIMS["walk"]
                appearance_key = (source, mesh)
                appearance_index = moving_appearance_counts.get(appearance_key, 0)
                moving_appearance_counts[appearance_key] = appearance_index + 1
                motion, distance = [
                    ("walking_slow", 360.0),
                    ("walking_gallery", 450.0),
                    ("walking_browse", 540.0),
                ][appearance_index % 3]
                direction = distance if index < 9 else -distance
                end = [start[0] + direction, start[1] + ((index % 3) - 1) * 90.0, start[2]]
            else:
                animation = ARIA_BLAKE_ANIMS["idle"] if is_aria else SCANNED_3D_PEOPLE_ANIMS["idle"]
                end = list(start)
                motion = stationary_motions[index - 18]
            walking.append((mesh, animation, motion, source, start, end))
    elif scene_id.startswith("citypark_promenade"):
        walking = (
            [
                (SCANNED_3D_PEOPLE_MESHES[0], SCANNED_3D_PEOPLE_ANIMS["walk"], "walking", "fab_scanned_3d_people_pack"),
                (SCANNED_3D_PEOPLE_MESHES[1], SCANNED_3D_PEOPLE_ANIMS["walk"], "walking", "fab_scanned_3d_people_pack"),
                (SCANNED_3D_PEOPLE_MESHES[2], SCANNED_3D_PEOPLE_ANIMS["walk"], "walking", "fab_scanned_3d_people_pack"),
                (SCANNED_3D_PEOPLE_MESHES[3], SCANNED_3D_PEOPLE_ANIMS["walk"], "walking", "fab_scanned_3d_people_pack"),
                (SCANNED_3D_PEOPLE_MESHES[4], SCANNED_3D_PEOPLE_ANIMS["idle"], "standing", "fab_scanned_3d_people_pack"),
                (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["walk"], "walking", "fab_aria_blake_game_ready"),
                (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["run"], "running", "fab_aria_blake_game_ready"),
                (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["idle"], "talking", "fab_aria_blake_game_ready"),
                (FREE_CASUAL_GIRL_MESH, FREE_CASUAL_GIRL_ANIMS["walk"], "walking", "fab_free_casual_girl_modular", None, None, 0),
                (FREE_CASUAL_GIRL_MESH, FREE_CASUAL_GIRL_ANIMS["run"], "running", "fab_free_casual_girl_modular", None, None, 1),
                (FREE_CASUAL_GIRL_MESH, FREE_CASUAL_GIRL_ANIMS["idle"], "looking_up", "fab_free_casual_girl_modular", None, None, 2),
                (FREE_CASUAL_GIRL_MESH, FREE_CASUAL_GIRL_ANIMS["walk"], "walking", "fab_free_casual_girl_modular", None, None, 3),
                (FREE_CASUAL_GIRL_MESH, FREE_CASUAL_GIRL_ANIMS["idle"], "talking", "fab_free_casual_girl_modular", None, None, 1),
                (FREE_CASUAL_GIRL_MESH, FREE_CASUAL_GIRL_ANIMS["run"], "running", "fab_free_casual_girl_modular", None, None, 0),
                (FREE_CASUAL_GIRL_MESH, FREE_CASUAL_GIRL_ANIMS["walk"], "walking", "fab_free_casual_girl_modular", None, None, 2),
                (FREE_CASUAL_GIRL_MESH, FREE_CASUAL_GIRL_ANIMS["run"], "running", "fab_free_casual_girl_modular", None, None, 3),
                (FREE_CASUAL_GIRL_MESH, FREE_CASUAL_GIRL_ANIMS["idle"], "standing", "fab_free_casual_girl_modular", None, None, 0),
                (FREE_CASUAL_GIRL_MESH, FREE_CASUAL_GIRL_ANIMS["run"], "running", "fab_free_casual_girl_modular", None, None, 2),
                (SCANNED_3D_PEOPLE_MESHES[0], SCANNED_3D_PEOPLE_ANIMS["idle"], "looking_up", "fab_scanned_3d_people_pack"),
                (SCANNED_3D_PEOPLE_MESHES[1], SCANNED_3D_PEOPLE_ANIMS["dance"], "talking", "fab_scanned_3d_people_pack"),
                *_city_sample_crowd_bindings(),
            ]
            + [(mesh, MAN_ANIMS[0], "walking") for mesh in MAN_MESHES]
            + [(mesh, MAN_ANIMS[1], "walking") for mesh in MAN_MESHES]
            + [(mesh, MAN_ANIMS[2], "phone_walk") for mesh in MAN_MESHES]
            + [(mesh, WOMAN_ANIMS[0], "walking") for mesh in WOMAN_MESHES]
            + [(mesh, WOMAN_ANIMS[1], "walking") for mesh in WOMAN_MESHES]
            + [(mesh, WOMAN_ANIMS[3], "phone_idle") for mesh in WOMAN_MESHES[:3]]
            + [
                (MAN_MESHES[0], MAN_ANIMS[5], "running"),
                (MAN_MESHES[2], MAN_ANIMS[6], "sitting_phone"),
            ]
        )
    else:
        walking = [
            (MAN_MESHES[0], MAN_ANIMS[0], "walking"),
            (MAN_MESHES[1], MAN_ANIMS[1], "walking"),
            (MAN_MESHES[2], MAN_ANIMS[2], "phone_walk"),
            (WOMAN_MESHES[0], WOMAN_ANIMS[0], "walking"),
            (WOMAN_MESHES[1], WOMAN_ANIMS[1], "walking"),
            (MAN_MESHES[3], MAN_ANIMS[2], "phone_walk"),
            (WOMAN_MESHES[2], WOMAN_ANIMS[0], "walking"),
            (MAN_MESHES[4], MAN_ANIMS[3], "phone_idle"),
            (WOMAN_MESHES[3], WOMAN_ANIMS[1], "walking"),
            (WOMAN_MESHES[0], WOMAN_ANIMS[3], "phone_idle"),
            (MAN_MESHES[0], MAN_ANIMS[5], "running"),
            (WOMAN_MESHES[1], WOMAN_ANIMS[4], "talking"),
            (WOMAN_MESHES[2], WOMAN_ANIMS[2], "looking_up"),
            (WOMAN_MESHES[3], WOMAN_ANIMS[4], "standing"),
            (MAN_MESHES[3], MAN_ANIMS[8], "walking_bag"),
            (MAN_MESHES[4], MAN_ANIMS[9], "walking_suitcase"),
        ]
        walking = [entry for entry in walking if entry[2] != "running" and "sitting" not in entry[2]]
    walking = [_complete_free_casual_entry(entry) for entry in walking]
    if scene_id.startswith("art_gallery"):
        walking = [
            (entry[0], ARIA_BLAKE_ANIMS["walk"], "walking_slow", *entry[3:])
            if entry[1] == ARIA_BLAKE_ANIMS["run"]
            else entry
            for entry in walking
        ]
    if scene_id in FORMAL_COMPLETE_CHARACTER_ONLY_SCENES:
        walking = [
            entry
            for entry in walking
            if len(entry) >= 4 and entry[3] in FORMAL_VERIFIED_MOVING_CHARACTER_SOURCES
        ]
    if scene_id.startswith("citypark_promenade"):
        walking = [
            *[
                (mesh, SCANNED_3D_PEOPLE_ANIMS["walk"], "walking", "fab_scanned_3d_people_pack")
                for mesh in SCANNED_3D_PEOPLE_MESHES
            ],
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["walk"], "walking", "fab_aria_blake_game_ready"),
            (SCANNED_3D_PEOPLE_MESHES[0], SCANNED_3D_PEOPLE_ANIMS["idle"], "standing", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[1], SCANNED_3D_PEOPLE_ANIMS["idle"], "looking_up", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[4], SCANNED_3D_PEOPLE_RETARGETED_ANIMS["nathan_phone_talk"], "phone_idle", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[3], SCANNED_3D_PEOPLE_ANIMS["dance"], "talking", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[2], SCANNED_3D_PEOPLE_ANIMS["idle"], "standing", "fab_scanned_3d_people_pack"),
            (SCANNED_3D_PEOPLE_MESHES[5], SCANNED_3D_PEOPLE_ANIMS["idle"], "looking_up", "fab_scanned_3d_people_pack"),
            (ARIA_BLAKE_MESH, ARIA_BLAKE_ANIMS["run"], "running", "fab_aria_blake_game_ready"),
        ]
    bindings = []
    citypark_appearance_counts: dict[tuple[str, str, str], int] = {}
    for index in range(count):
        entry = walking[index % len(walking)]
        mesh, animation, motion = entry[:3]
        source = entry[3] if len(entry) > 3 else "existing_twinmotion_rigged_character"
        if scene_id.startswith("citypark_promenade"):
            appearance_key = (str(source), str(mesh), str(animation))
            appearance_index = citypark_appearance_counts.get(appearance_key, 0)
            citypark_appearance_counts[appearance_key] = appearance_index + 1
            behavior_profiles = {
                "walking": ("walking_promenade", "walking_tree_line", "walking_crossing"),
                "walking_slow": ("walking_slow_browse", "walking_slow_garden", "walking_slow_return"),
                "running": ("running_jogger", "running_park_loop", "running_path_return"),
                "standing": ("standing_bench", "standing_map", "standing_tree"),
                "looking_up": ("looking_up_canopy", "looking_up_sign", "looking_up_sky"),
                "talking": ("talking_pair", "phone_idle", "talking_cafe"),
            }
            profiles = behavior_profiles.get(str(motion), (str(motion),))
            motion = profiles[appearance_index % len(profiles)]
            if str(motion) == "phone_idle" and appearance_index > 0:
                animation = SCANNED_3D_PEOPLE_ANIMS["dance"]
                motion = "talking_phone_followup"
        start_location = entry[4] if len(entry) > 4 else None
        end_location = entry[5] if len(entry) > 5 else None
        modular_variant = entry[6] if len(entry) > 6 else None
        binding = {
            "actor_name": f"CineU_{scene_id}_skeletal_{index:02d}",
            "mesh_path": mesh,
            "animation_path": animation,
            "motion": motion,
            "source": source,
            "animation_phase_offset_frames": _pedestrian_animation_phase_offset(index),
        }
        if modular_variant is not None:
            binding["modular_variant"] = int(modular_variant)
        if start_location is not None:
            binding["start_location"] = list(start_location)
        if end_location is not None:
            binding["end_location"] = list(end_location)
        if scene_id.startswith("citypark_promenade") and index == 10:
            binding["start_location"] = [-34330.0, 11380.0, 108.0]
            binding["end_location"] = [-34330.0, 11380.0, 108.0]
        bindings.append(
            binding
        )
    return bindings


def _production_metahuman_parts(scene_id: str, location: list[float], rotation: list[float]) -> list[dict]:
    return [
        {
            "actor_name": f"CineU_{scene_id}_metahuman_kellan_{role}",
            "mesh_path": mesh_path,
            "location": list(location),
            "end_location": list(location),
            "rotation": list(rotation),
            "scale": 1.0,
            "animation_path": "",
            "motion": "standing",
            "source": "existing_metahuman_skeletal_mesh",
        }
        for role, mesh_path in METAHUMAN_KELLAN_PARTS
    ]


def _production_metahuman_blueprints(scene_id: str, location: list[float], rotation: list[float]) -> list[dict]:
    return [
        {
            "actor_name": f"CineU_{scene_id}_metahuman_kellan",
            "blueprint_path": METAHUMAN_KELLAN_BLUEPRINT,
            "location": list(location),
            "end_location": list(location),
            "rotation": list(rotation),
            "scale": 1.0,
            "motion": "standing",
            "source": "existing_metahuman_character_blueprint",
        }
    ]


def _production_city_sample_blueprints(scene_id: str) -> list[dict]:
    if not _is_downtown_west_scene(scene_id):
        return []
    curated_routes = _downtown_west_native_routes(
        [
            ([300.0, 4200.0, 2.0], [300.0, 4200.0, 2.0]),
            ([300.0, 4350.0, 2.0], [300.0, 4350.0, 2.0]),
            ([450.0, 4200.0, 2.0], [450.0, 4200.0, 2.0]),
            ([450.0, 4350.0, 2.0], [450.0, 4350.0, 2.0]),
            ([500.0, 4500.0, 2.0], [500.0, 4500.0, 2.0]),
            ([500.0, 4650.0, 2.0], [500.0, 4650.0, 2.0]),
            ([500.0, 4800.0, 2.0], [500.0, 4800.0, 2.0]),
            ([600.0, 4200.0, 2.0], [600.0, 4200.0, 2.0]),
        ]
    )
    motions = [
        "citysample_blueprint_window_wait",
        "citysample_blueprint_phone_idle",
        "citysample_blueprint_talking_pair",
        "citysample_blueprint_looking_up",
        "citysample_blueprint_storefront_wait",
        "citysample_blueprint_bench_pause",
        "citysample_blueprint_corner_observe",
        "citysample_blueprint_cafe_wait",
    ]
    characters = []
    for index, (start, end) in enumerate(curated_routes):
        characters.append(
            {
                "actor_name": f"CineU_{scene_id}_citysample_bp_{index:02d}",
                "blueprint_path": CITY_SAMPLE_CROWD_BLUEPRINT,
                "location": list(start),
                "end_location": list(end),
                "rotation": [0.0, 35.0 + (index % 6) * 31.0, 0.0],
                "scale": 1.0,
                "motion": motions[index % len(motions)],
                "source": "fab_city_sample_crowds_blueprint",
                "visual_variant": index,
            }
        )
    return characters


def _production_free_casual_modular_parts(animation_bindings: list[dict]) -> list[dict]:
    parts = []
    citypark_free_casual_part_host_count = 0
    citypark_city_sample_part_host_count = 0
    for binding in animation_bindings:
        source = binding.get("source")
        if source == "fab_free_casual_girl_modular":
            variant_index = int(binding.get("modular_variant", 0)) % len(FREE_CASUAL_GIRL_VARIANTS)
            part_source = "fab_free_casual_girl_modular_part"
            part_meshes = FREE_CASUAL_GIRL_VARIANTS[variant_index]
        elif source == "fab_city_sample_crowds_modular":
            variant_index = int(binding.get("modular_variant", 0)) % len(CITY_SAMPLE_CROWD_VARIANTS)
            part_source = "fab_city_sample_crowds_modular_part"
            part_meshes = CITY_SAMPLE_CROWD_VARIANTS[variant_index]["parts"]
        else:
            continue
        if str(binding.get("actor_name", "")).startswith("CineU_citypark_promenade_"):
            if source == "fab_free_casual_girl_modular":
                if citypark_free_casual_part_host_count >= 3:
                    continue
                citypark_free_casual_part_host_count += 1
            if source == "fab_city_sample_crowds_modular":
                if citypark_city_sample_part_host_count >= 4:
                    continue
                citypark_city_sample_part_host_count += 1
        for role, mesh_path in part_meshes:
            parts.append(
                {
                    "actor_name": f"{binding['actor_name']}_{role}",
                    "host_actor_name": binding["actor_name"],
                    "mesh_path": mesh_path,
                    "animation_path": binding["animation_path"],
                    "role": role,
                    "source": part_source,
                    "modular_variant": variant_index,
                }
            )
    return parts


def _production_formal_modular_parts(scene_id: str, animation_bindings: list[dict]) -> list[dict]:
    if _is_downtown_west_scene(scene_id):
        if DOWNTOWN_WEST_CITY_SAMPLE_MODULAR_ENABLED:
            return [
                part
                for part in _production_free_casual_modular_parts(animation_bindings)
                if part.get("source") == "fab_city_sample_crowds_modular_part"
            ]
        return []
    if scene_id in FORMAL_COMPLETE_CHARACTER_ONLY_SCENES:
        return []
    return _production_free_casual_modular_parts(animation_bindings)


def _production_formal_metahuman_parts(scene_id: str, location: list[float], rotation: list[float]) -> list[dict]:
    if scene_id in FORMAL_COMPLETE_CHARACTER_ONLY_SCENES:
        return []
    return _production_metahuman_parts(scene_id, location, rotation)


def _readyposed_static_bindings(count: int | None = None) -> list[dict]:
    target_count = len(STATIC_PEOPLE) if count is None else int(count)
    bindings = []
    for index in range(target_count):
        mesh_path = STATIC_PEOPLE[index % len(STATIC_PEOPLE)]
        if "/Couple" in mesh_path:
            motion = "talking"
        elif index % 5 == 0:
            motion = "sitting"
        elif index % 4 == 0:
            motion = "looking_up"
        else:
            motion = "standing"
        bindings.append({
            "actor_name": f"CineU_readyposed_pool_{index:02d}",
            "mesh_path": mesh_path,
            "source": "existing_twinmotion_readyposed_static_mesh",
            "motion": motion,
        })
    return bindings


def _scanned_posed_static_bindings() -> list[dict]:
    motions = ["standing", "looking_up", "phone_idle"]
    return [
        {
            "mesh_path": mesh_path,
            "source": "fab_scanned_3d_people_pack_posed_static",
            "motion": motions[index],
        }
        for index, mesh_path in enumerate(SCANNED_3D_PEOPLE_POSED_STATIC_MESHES)
    ]


def _filter_custom_cameras(scene_id: str, cameras: list[dict]) -> list[dict]:
    cameras = _normalize_camera_motion(cameras)
    if not CAMERA_FILTER:
        return cameras
    filtered = [
        camera
        for camera in cameras
        if CAMERA_FILTER in {str(camera.get("name")), str(camera.get("shot_id")), str(camera.get("type"))}
    ]
    if not filtered:
        raise RuntimeError(f"CINEU_HILLSIDE_CAMERA did not match a {scene_id} camera: {CAMERA_FILTER}")
    return filtered


def _custom_cuts(cameras: list[dict]) -> list[dict]:
    return [
        {
            "shot_id": str(camera["shot_id"]),
            "camera_name": str(camera["name"]),
            "start_frame": 0,
            "end_frame": FRAME_COUNT,
        }
        for camera in cameras
    ]


def _art_gallery_probe_cameras(people_z: float, eye_z: float) -> list[dict]:
    return [
        {
            "name": "CineU_art_gallery_probe_reverse_lane_a",
            "shot_id": "art_gallery_probe_reverse_lane_a",
            "type": "surveillance_oblique",
            "monitor_view": "reverse_candidate",
            "focal": 20.0,
            "keys": [_camera_key(0, [3300.0, -7250.0, 210.0], [-1450.0, -5850.0, eye_z]), _camera_key(FRAME_COUNT, [3300.0, -7250.0, 210.0], [-1450.0, -5850.0, eye_z])],
            "exposure_bias": 0.0,
            "exposure_brightness": 2.2,
            "motion_blur_amount": 0.02,
        },
        {
            "name": "CineU_art_gallery_probe_reverse_lane_b",
            "shot_id": "art_gallery_probe_reverse_lane_b",
            "type": "surveillance_oblique",
            "monitor_view": "reverse_candidate",
            "focal": 18.0,
            "keys": [_camera_key(0, [3650.0, -5200.0, 220.0], [-2100.0, -6000.0, eye_z]), _camera_key(FRAME_COUNT, [3650.0, -5200.0, 220.0], [-2100.0, -6000.0, eye_z])],
            "exposure_bias": 0.0,
            "exposure_brightness": 2.2,
            "motion_blur_amount": 0.02,
        },
        {
            "name": "CineU_art_gallery_probe_side_lane_a",
            "shot_id": "art_gallery_probe_side_lane_a",
            "type": "surveillance_oblique",
            "monitor_view": "side_candidate",
            "focal": 22.0,
            "keys": [_camera_key(0, [-4200.0, -7350.0, 210.0], [-900.0, -5450.0, eye_z]), _camera_key(FRAME_COUNT, [-4200.0, -7350.0, 210.0], [-900.0, -5450.0, eye_z])],
            "exposure_bias": 0.0,
            "exposure_brightness": 2.2,
            "motion_blur_amount": 0.02,
        },
        {
            "name": "CineU_art_gallery_probe_far_back_a",
            "shot_id": "art_gallery_probe_far_back_a",
            "type": "surveillance_oblique",
            "monitor_view": "far_candidate",
            "focal": 16.0,
            "keys": [_camera_key(0, [3900.0, -2900.0, 235.0], [-1350.0, -6100.0, eye_z]), _camera_key(FRAME_COUNT, [3900.0, -2900.0, 235.0], [-1350.0, -6100.0, eye_z])],
            "exposure_bias": 0.0,
            "exposure_brightness": 2.2,
            "motion_blur_amount": 0.02,
        },
    ]


def _filtered_art_gallery_probe_cameras(people_z: float, eye_z: float) -> list[dict]:
    if not CAMERA_FILTER:
        return []
    return [
        camera
        for camera in _art_gallery_probe_cameras(people_z, eye_z)
        if CAMERA_FILTER in {str(camera.get("name")), str(camera.get("shot_id")), str(camera.get("type"))}
    ]


def _museum_gallery_spec(night: bool = False) -> dict:
    scene_id = "museum_gallery_night" if night else "museum_gallery_day"
    people_z = 2.0
    day_exposure_brightness = None if night else 2.2
    cameras = [
        {
            "name": "CineU_museum_surveillance_wide",
            "shot_id": "museum_surveillance_wide",
            "type": "surveillance_fixed",
            "monitor_view": "original",
            "focal": 24.0,
            "keys": [_camera_key(0, [-4620.0, 40.0, 170.0], [-3100.0, -470.0, 160.0]), _camera_key(FRAME_COUNT, [-4620.0, 40.0, 170.0], [-2350.0, -470.0, 160.0])],
            "exposure_bias": -0.25 if night else 0.0,
            "exposure_brightness": day_exposure_brightness,
        },
        {
            "name": "CineU_museum_surveillance_reverse",
            "shot_id": "museum_surveillance_reverse",
            "type": "surveillance_oblique",
            "monitor_view": "reverse",
            "focal": 22.0,
            "keys": [_camera_key(0, [-1240.0, -110.0, 240.0], [-3350.0, -500.0, 155.0]), _camera_key(FRAME_COUNT, [-1280.0, -120.0, 240.0], [-3950.0, -570.0, 155.0])],
            "exposure_bias": -0.2 if night else 0.0,
            "exposure_brightness": day_exposure_brightness,
        },
        {
            "name": "CineU_museum_gallery_oblique",
            "shot_id": "museum_gallery_oblique",
            "type": "surveillance_oblique",
            "monitor_view": "side",
            "focal": 22.0,
            "keys": [_camera_key(0, [-4620.0, -260.0, 220.0], [-2500.0, -470.0, 155.0]), _camera_key(FRAME_COUNT, [-4200.0, -260.0, 220.0], [-1700.0, -470.0, 155.0])],
            "exposure_bias": -0.2 if night else 0.0,
            "exposure_brightness": day_exposure_brightness,
        },
        {
            "name": "CineU_museum_surveillance_far",
            "shot_id": "museum_surveillance_far",
            "type": "surveillance_oblique",
            "monitor_view": "far",
            "focal": 16.0,
            "keys": [_camera_key(0, [-4620.0, 40.0, 220.0], [-3250.0, -470.0, 150.0]), _camera_key(FRAME_COUNT, [-4620.0, 40.0, 220.0], [-1900.0, -430.0, 150.0])],
            "exposure_bias": -0.2 if night else 0.0,
            "exposure_brightness": day_exposure_brightness,
        },
        {
            "name": "CineU_museum_top_down",
            "shot_id": "museum_top_down",
            "type": "top_down",
            "monitor_view": "drone_overview",
            "focal": 16.0,
            "keys": [
                _camera_key(0, [-3100.0, -470.0, 950.0], [-3100.0, -470.0, people_z]),
                _camera_key(FRAME_COUNT, [-3100.0, -470.0, 950.0], [-3100.0, -470.0, people_z]),
            ],
            "exposure_bias": -0.15 if night else 0.0,
            "exposure_brightness": day_exposure_brightness,
        },
        {
            "name": "CineU_museum_first_person_walk",
            "shot_id": "museum_first_person_walk",
            "type": "first_person",
            "focal": 14.0,
            "keys": [_camera_key(0, [-4650.0, -215.0, 145.0], [-3350.0, -465.0, 160.0]), _camera_key(FRAME_COUNT, [-3120.0, -235.0, 145.0], [-1750.0, -465.0, 155.0])],
            "exposure_bias": -0.05 if night else 0.0,
            "exposure_brightness": day_exposure_brightness,
        },
    ]
    cinematic_exposure_bias = -0.25 if night else 0.0
    cameras.extend(_cinematic_30s_cameras(scene_id, people_z, cinematic_exposure_bias, day_exposure_brightness))
    cameras = _filter_custom_cameras(scene_id, cameras)
    paths = [
        ([-4100.0, -470.0, people_z], [-1500.0, -470.0, people_z]),
        ([-4000.0, -820.0, people_z], [-2300.0, -820.0, people_z]),
        ([-3900.0, 80.0, people_z], [-1800.0, 80.0, people_z]),
        ([-3650.0, -820.0, people_z], [-3650.0, 100.0, people_z]),
        ([-3000.0, -820.0, people_z], [-3000.0, 95.0, people_z]),
        ([-2300.0, -820.0, people_z], [-1600.0, -520.0, people_z]),
        ([-4200.0, -260.0, people_z], [-2450.0, -260.0, people_z]),
        ([-3820.0, -650.0, people_z], [-2100.0, -650.0, people_z]),
        ([-3500.0, -120.0, people_z], [-2050.0, -120.0, people_z]),
        ([-3300.0, -720.0, people_z], [-2220.0, -380.0, people_z]),
        ([-2760.0, -720.0, people_z], [-2760.0, -80.0, people_z]),
        ([-2380.0, -640.0, people_z], [-1720.0, -420.0, people_z]),
    ]
    animation_bindings = _production_animation_bindings(scene_id, 24)
    return {
        "scene_id": scene_id,
        "source_level": "/Game/AIUE5_vol10_01/maps/AIUE_vol10_01",
        "description": "CineU production museum gallery pedestrian scene using linked MuseumGallery level and high-quality local characters.",
        "people_z": people_z,
        "support_props": [],
        "cameras": cameras,
        "cuts": _custom_cuts(cameras),
        "paths": paths,
        "static_points": [[-4215.0, 125.0, people_z], [-2575.0, -285.0, people_z], [-1625.0, -820.0, people_z], [-3365.0, -230.0, people_z]],
        "explicit_static_points": True,
        "lighting_preset": "night" if night else "day",
        "extra_lights": [
            {"type": "point", "label": f"CineU_{scene_id}_warm_art_fill_a", "location": [-3650.0, -760.0, 360.0], "intensity": 2600.0 if night else 420.0, "radius": 980.0, "color": [1.0, 0.86, 0.68]},
            {"type": "point", "label": f"CineU_{scene_id}_warm_art_fill_b", "location": [-2260.0, -130.0, 360.0], "intensity": 2200.0 if night else 330.0, "radius": 930.0, "color": [1.0, 0.9, 0.72]},
        ],
        "asset_first_plan": {
            "crowd": {
                "animation_bindings": animation_bindings,
                "high_detail_modular_parts": _production_formal_modular_parts(scene_id, animation_bindings),
                "metahuman_cinematic_parts": _production_formal_metahuman_parts(scene_id, [-3550.0, -360.0, people_z], [0.0, -25.0, 0.0]),
                "readyposed_static_meshes": _scanned_posed_static_bindings(),
                "lane_offset_width": 32.0,
            }
        },
    }


def _citypark_promenade_spec(night: bool = False) -> dict:
    scene_id = "citypark_promenade_night" if night else "citypark_promenade_day"
    people_z = 108.0
    eye_z = people_z + 95.0
    cameras = [
        {
            "name": "CineU_citypark_surveillance_path",
            "shot_id": "citypark_surveillance_path",
            "type": "surveillance_fixed",
            "monitor_view": "original",
            "focal": 35.0,
            "keys": [_camera_key(0, [-35000.0, 8200.0, 650.0], [-33750.0, 10880.0, eye_z]), _camera_key(FRAME_COUNT, [-35000.0, 8200.0, 650.0], [-31800.0, 11350.0, eye_z])],
            "exposure_bias": -0.15 if night else 0.05,
            "exposure_brightness": None if night else 1.15,
        },
        {
            "name": "CineU_citypark_surveillance_reverse",
            "shot_id": "citypark_surveillance_reverse",
            "type": "surveillance_oblique",
            "monitor_view": "reverse",
            "focal": 34.0,
            "keys": [_camera_key(0, [-31050.0, 15750.0, 1080.0], [-33450.0, 11050.0, eye_z]), _camera_key(FRAME_COUNT, [-30900.0, 15550.0, 1080.0], [-34300.0, 10480.0, eye_z])],
            "exposure_bias": -0.15 if night else 0.05,
            "exposure_brightness": None if night else 1.15,
        },
        {
            "name": "CineU_citypark_wide_overlook",
            "shot_id": "citypark_wide_overlook",
            "type": "surveillance_oblique",
            "monitor_view": "side",
            "focal": 32.0,
            "keys": [_camera_key(0, [-36500.0, 7600.0, 900.0], [-34000.0, 10850.0, eye_z]), _camera_key(FRAME_COUNT, [-36000.0, 7950.0, 900.0], [-31500.0, 11600.0, eye_z])],
            "exposure_bias": -0.1 if night else 0.05,
            "exposure_brightness": None if night else 1.15,
        },
        {
            "name": "CineU_citypark_surveillance_far",
            "shot_id": "citypark_surveillance_far",
            "type": "surveillance_oblique",
            "monitor_view": "far",
            "focal": 24.0,
            "keys": [_camera_key(0, [-38200.0, 7200.0, 1650.0], [-33800.0, 10950.0, eye_z]), _camera_key(FRAME_COUNT, [-38200.0, 7200.0, 1650.0], [-31600.0, 11650.0, eye_z])],
            "exposure_bias": -0.15 if night else 0.05,
            "exposure_brightness": None if night else 1.15,
        },
        {
            "name": "CineU_citypark_top_down",
            "shot_id": "citypark_top_down",
            "type": "top_down",
            "monitor_view": "drone_overview",
            "focal": 20.0,
            "keys": [_camera_key(0, [-33000.0, 11080.0, 3600.0], [-33000.0, 11080.0, people_z]), _camera_key(FRAME_COUNT, [-33000.0, 11080.0, 3600.0], [-33000.0, 11080.0, people_z])],
            "exposure_bias": -0.1 if night else 0.05,
            "exposure_brightness": None if night else 1.15,
        },
        {
            "name": "CineU_citypark_first_person_walk",
            "shot_id": "citypark_first_person_walk",
            "type": "first_person",
            "focal": 14.0,
            "keys": [_camera_key(0, [-34780.0, 10350.0, people_z + 166.0], [-33550.0, 11250.0, eye_z]), _camera_key(FRAME_COUNT, [-33620.0, 11650.0, people_z + 166.0], [-32200.0, 11100.0, eye_z])],
            "exposure_bias": -0.1 if night else 0.05,
            "exposure_brightness": None if night else 1.15,
        },
    ]
    cameras.extend(_cinematic_30s_cameras(scene_id, people_z, -0.1 if night else 0.05, None if night else 1.15))
    cameras = _filter_custom_cameras(scene_id, cameras)
    paths = [
        ([-34580.0, 10520.0, people_z], [-31880.0, 10590.0, people_z]),
        ([-34460.0, 10980.0, people_z], [-31580.0, 11200.0, people_z]),
        ([-34120.0, 11540.0, people_z], [-31320.0, 11680.0, people_z]),
        ([-31820.0, 12080.0, people_z], [-34420.0, 11380.0, people_z]),
        ([-34620.0, 10120.0, people_z], [-32340.0, 11820.0, people_z]),
        ([-33480.0, 10020.0, people_z], [-31080.0, 11180.0, people_z]),
        ([-34500.0, 11880.0, people_z], [-31800.0, 10840.0, people_z]),
        ([-33880.0, 11220.0, people_z], [-31480.0, 10160.0, people_z]),
    ]
    animation_bindings = _production_animation_bindings(scene_id, CITYPARK_ANIMATED_COUNT)
    return {
        "scene_id": scene_id,
        "source_level": "/Game/CityPark/Maps/Showcase",
        "description": "CineU production city park pedestrian promenade using linked CityPark Environment Collection LITE level and high-quality local characters.",
        "people_z": people_z,
        "support_props": [],
        "cameras": cameras,
        "cuts": _custom_cuts(cameras),
        "paths": paths,
        "static_points": [
            [-34580.0, 10480.0, people_z],
            [-34240.0, 10820.0, people_z],
            [-33720.0, 11380.0, people_z],
            [-33320.0, 11800.0, people_z],
            [-32980.0, 10370.0, people_z],
            [-32480.0, 11020.0, people_z],
            [-32120.0, 11600.0, people_z],
            [-31720.0, 9850.0, people_z],
            [-31280.0, 10820.0, people_z],
            [-30940.0, 11920.0, people_z],
            [-33100.0, 10020.0, people_z],
            [-34020.0, 12100.0, people_z],
        ],
        "explicit_static_points": True,
        "lighting_preset": "night" if night else "day",
        "extra_lights": [
            {"type": "directional", "label": f"CineU_{scene_id}_sun_or_moon", "location": [-33000.0, 11000.0, 5000.0], "rotation": [-38.0, -42.0, 0.0], "intensity": 0.32 if night else 8.0, "color": [0.52, 0.64, 1.0] if night else [1.0, 0.94, 0.82]},
            {"type": "point", "label": f"CineU_{scene_id}_entrance_lamp_a", "location": [-34400.0, 10550.0, 520.0], "intensity": 18000.0 if night else 130.0, "radius": 4100.0, "color": [1.0, 0.72, 0.42]},
            {"type": "point", "label": f"CineU_{scene_id}_entrance_lamp_b", "location": [-33400.0, 11250.0, 520.0], "intensity": 17000.0 if night else 120.0, "radius": 3900.0, "color": [1.0, 0.78, 0.5]},
            {"type": "point", "label": f"CineU_{scene_id}_porch_fill", "location": [-32600.0, 10450.0, 420.0], "intensity": 14000.0 if night else 90.0, "radius": 3300.0, "color": [0.82, 0.9, 1.0]},
            {"type": "point", "label": f"CineU_{scene_id}_crosswalk_fill", "location": [-31600.0, 11600.0, 460.0], "intensity": 11000.0 if night else 80.0, "radius": 3000.0, "color": [1.0, 0.84, 0.62]},
        ],
        "asset_first_plan": {
            "crowd": {
                "animation_bindings": animation_bindings,
                "high_detail_modular_parts": _production_formal_modular_parts(scene_id, animation_bindings),
                "metahuman_cinematic_parts": _production_formal_metahuman_parts(scene_id, [-30600.0, 12200.0, people_z], [0.0, 35.0, 0.0]),
                "readyposed_static_meshes": _readyposed_static_bindings(CITYPARK_STATIC_COUNT),
                "sitting_static_points": [
                    [-34540.0, 10420.0, people_z],
                    [-34220.0, 12040.0, people_z],
                    [-33080.0, 10020.0, people_z],
                    [-30640.0, 12180.0, people_z],
                ],
                "lane_offset_width": 46.0,
            }
        },
    }


def _art_gallery_spec() -> dict:
    scene_id = "art_gallery_day"
    people_z = 2.0
    eye_z = people_z + 130.0
    cameras = [
        {
            "name": "CineU_art_gallery_surveillance_wide",
            "shot_id": "art_gallery_surveillance_wide",
            "type": "surveillance_fixed",
            "monitor_view": "original",
            "focal": 24.0,
            "keys": [_camera_key_raw(0, [-3407.878173828125, -3891.265380859375, 231.55906677246094], [-2.3997955322265634, -76.19807434082028, 0.0]), _camera_key_raw(FRAME_COUNT, [-3407.878173828125, -3891.265380859375, 231.55906677246094], [-2.3997955322265634, -76.19807434082028, 0.0])],
            "exposure_bias": 0.0,
            "exposure_brightness": 2.2,
            "motion_blur_amount": 0.02,
        },
        {
            "name": "CineU_art_gallery_reverse",
            "shot_id": "art_gallery_reverse",
            "type": "surveillance_oblique",
            "monitor_view": "reverse",
            "focal": 16.0,
            "keys": [_camera_key(0, [295.0, -7320.0, 178.0], [-1900.0, -5700.0, eye_z]), _camera_key(FRAME_COUNT, [295.0, -7320.0, 178.0], [-1900.0, -5700.0, eye_z])],
            "exposure_bias": 0.0,
            "exposure_brightness": 2.2,
            "motion_blur_amount": 0.02,
        },
        {
            "name": "CineU_art_gallery_side",
            "shot_id": "art_gallery_side",
            "type": "surveillance_oblique",
            "monitor_view": "side",
            "focal": 26.0,
            "keys": [_camera_key_raw(0, [-1665.9891357421875, -5867.79736328125, 140.64527893066406], [-3.79900312423706, -141.19801330566403, 0.0]), _camera_key_raw(FRAME_COUNT, [-1665.9891357421875, -5867.79736328125, 140.64527893066406], [-3.79900312423706, -141.19801330566403, 0.0])],
            "exposure_bias": 0.0,
            "exposure_brightness": 2.2,
            "motion_blur_amount": 0.02,
        },
        {
            "name": "CineU_art_gallery_far",
            "shot_id": "art_gallery_far",
            "type": "surveillance_oblique",
            "monitor_view": "far",
            "focal": 18.0,
            "keys": [_camera_key_raw(0, [-2734.88671875, -6060.8056640625, 137.1529541015625], [-2.1990163326263423, 117.00100708007814, 0.0]), _camera_key_raw(FRAME_COUNT, [-2734.88671875, -6060.8056640625, 137.1529541015625], [-2.1990163326263423, 117.00100708007814, 0.0])],
            "exposure_bias": 0.0,
            "exposure_brightness": 2.2,
            "motion_blur_amount": 0.02,
        },
        {
            "name": "CineU_art_gallery_top_down",
            "shot_id": "art_gallery_top_down",
            "type": "top_down",
            "monitor_view": "drone_overview",
            "focal": 12.0,
            "keys": [_camera_key(0, [295.0, -7320.0, 430.0], [0.0, -5700.0, people_z]), _camera_key(FRAME_COUNT, [295.0, -7320.0, 430.0], [0.0, -5700.0, people_z])],
            "exposure_bias": 0.0,
            "exposure_brightness": 2.2,
            "motion_blur_amount": 0.02,
        },
        {
            "name": "CineU_art_gallery_first_person_walk",
            "shot_id": "art_gallery_first_person_walk",
            "type": "first_person",
            "focal": 14.0,
            "keys": [_camera_key(0, [-3600.0, -7050.0, people_z + 148.0], [-1700.0, -6100.0, eye_z]), _camera_key(FRAME_COUNT, [1800.0, -4800.0, people_z + 148.0], [2900.0, -4200.0, eye_z])],
            "exposure_bias": 0.0,
            "exposure_brightness": 2.2,
            "motion_blur_amount": 0.02,
        },
    ]
    cameras.extend(_filtered_art_gallery_probe_cameras(people_z, eye_z))
    cameras.extend(_cinematic_30s_cameras(scene_id, people_z, 0.0, 2.2))
    cameras = _filter_custom_cameras(scene_id, cameras)
    paths = [
        ([-3650.0, -6900.0, people_z], [3200.0, -6900.0, people_z]),
        ([-3500.0, -5700.0, people_z], [3000.0, -5700.0, people_z]),
        ([-2800.0, -4800.0, people_z], [2600.0, -4800.0, people_z]),
        ([3300.0, -7350.0, people_z], [-3400.0, -7350.0, people_z]),
        ([3300.0, -2850.0, people_z], [-3400.0, -2850.0, people_z]),
        ([-4000.0, -5100.0, people_z], [3700.0, -5100.0, people_z]),
    ]
    animation_bindings = _production_animation_bindings(scene_id, 24)
    return {
        "scene_id": scene_id,
        "source_level": "/Game/Showcase/Maps/ArtGallery",
        "description": "CineU production art gallery pedestrian scene using the existing ArtGallery Showcase map and high-quality linked pedestrian assets.",
        "people_z": people_z,
        "support_props": [],
        "cameras": cameras,
        "cuts": _custom_cuts(cameras),
        "paths": paths,
        "static_points": [[-3600.0, -3200.0, people_z], [-2100.0, -4300.0, people_z], [500.0, -6200.0, people_z], [2500.0, -5100.0, people_z]],
        "explicit_static_points": True,
        "lighting_preset": "day",
        "extra_lights": [
            {"type": "point", "label": f"CineU_{scene_id}_gallery_fill_a", "location": [-1800.0, -5200.0, 420.0], "intensity": 650.0, "radius": 2600.0, "color": [1.0, 0.9, 0.78]},
            {"type": "point", "label": f"CineU_{scene_id}_gallery_fill_b", "location": [1200.0, -6100.0, 420.0], "intensity": 520.0, "radius": 2400.0, "color": [0.85, 0.92, 1.0]},
        ],
        "asset_first_plan": {
            "crowd": {
                "animation_bindings": animation_bindings,
                "high_detail_modular_parts": _production_formal_modular_parts(scene_id, animation_bindings),
                "metahuman_cinematic_parts": _production_formal_metahuman_parts(scene_id, [-850.0, -5200.0, people_z], [0.0, 20.0, 0.0]),
                "readyposed_static_meshes": _scanned_posed_static_bindings(),
                "lane_offset_width": 72.0,
            }
        },
    }


def _warehouse_day_spec() -> dict:
    scene_id = "warehouse_day"
    people_z = 5.0
    eye_z = people_z + 135.0
    exposure_bias = -0.9
    exposure_brightness = 0.52
    cameras = [
        {
            "name": "CineU_warehouse_surveillance_original",
            "shot_id": "warehouse_surveillance_original",
            "type": "surveillance_fixed",
            "monitor_view": "original",
            "focal": 24.0,
            "keys": [_camera_key_raw(0, [407.32188, -752.508208, 700.838543], [-8.242, -140.082, 0.0]), _camera_key_raw(FRAME_COUNT, [407.32188, -752.508208, 700.838543], [-8.242, -140.082, 0.0])],
            "exposure_bias": exposure_bias,
            "exposure_brightness": exposure_brightness,
            "motion_blur_amount": 0.02,
        },
        {
            "name": "CineU_warehouse_surveillance_reverse",
            "shot_id": "warehouse_surveillance_reverse",
            "type": "surveillance_oblique",
            "monitor_view": "reverse",
            "focal": 24.0,
            "keys": [_camera_key_raw(0, [-3697.233, -3856.683, 176.944], [1.558, -0.282, 0.0]), _camera_key_raw(FRAME_COUNT, [-3697.233, -3856.683, 176.944], [1.558, -0.282, 0.0])],
            "exposure_bias": exposure_bias,
            "exposure_brightness": exposure_brightness,
            "motion_blur_amount": 0.02,
        },
        {
            "name": "CineU_warehouse_surveillance_side",
            "shot_id": "warehouse_surveillance_side",
            "type": "surveillance_oblique",
            "monitor_view": "side",
            "focal": 24.0,
            "keys": [_camera_key(0, [-3550.0, -5450.0, 240.0], [-1150.0, -4400.0, eye_z]), _camera_key(FRAME_COUNT, [-3550.0, -5450.0, 240.0], [-1150.0, -4400.0, eye_z])],
            "exposure_bias": exposure_bias,
            "exposure_brightness": exposure_brightness,
            "motion_blur_amount": 0.02,
        },
        {
            "name": "CineU_warehouse_surveillance_far",
            "shot_id": "warehouse_surveillance_far",
            "type": "surveillance_oblique",
            "monitor_view": "far",
            "focal": 20.0,
            "keys": [_camera_key_raw(0, [1703.153, -907.223, 860.164], [-18.042, -130.482, 0.0]), _camera_key_raw(FRAME_COUNT, [1703.153, -907.223, 860.164], [-18.042, -130.482, 0.0])],
            "exposure_bias": exposure_bias,
            "exposure_brightness": exposure_brightness,
            "motion_blur_amount": 0.02,
        },
        {
            "name": "CineU_warehouse_top_down",
            "shot_id": "warehouse_top_down",
            "type": "top_down",
            "monitor_view": "drone_overview",
            "focal": 18.0,
            "keys": [_camera_key(0, [-900.0, -3000.0, 1150.0], [-900.0, -3000.0, people_z]), _camera_key(FRAME_COUNT, [-900.0, -3000.0, 1150.0], [-900.0, -3000.0, people_z])],
            "exposure_bias": exposure_bias,
            "exposure_brightness": exposure_brightness,
            "motion_blur_amount": 0.02,
        },
        {
            "name": "CineU_warehouse_first_person_walk",
            "shot_id": "warehouse_first_person_walk",
            "type": "first_person",
            "focal": 22.0,
            "keys": [_camera_key(0, [-3550.0, -4750.0, people_z + 155.0], [-2550.0, -4300.0, eye_z]), _camera_key(FRAME_COUNT, [700.0, -4750.0, people_z + 155.0], [1450.0, -4300.0, eye_z])],
            "exposure_bias": exposure_bias,
            "exposure_brightness": exposure_brightness,
            "motion_blur_amount": 0.02,
        },
    ]
    cameras.extend(_cinematic_30s_cameras(scene_id, people_z, exposure_bias, exposure_brightness))
    cameras = _filter_custom_cameras(scene_id, cameras)
    paths = [
        ([-3800.0, -4550.0, people_z], [1200.0, -4550.0, people_z]),
        ([-3650.0, -4200.0, people_z], [1450.0, -4200.0, people_z]),
        ([-3300.0, -3400.0, people_z], [1250.0, -3400.0, people_z]),
        ([-2350.0, -4600.0, people_z], [-2350.0, -1200.0, people_z]),
    ]
    animation_bindings = _production_animation_bindings(scene_id, 24)
    return {
        "scene_id": scene_id,
        "source_level": "/Game/Warehouse/Scene/Scene",
        "description": "CineU production warehouse pedestrian scene using the downloaded Warehouse Fab environment inside CityParkEnv55.",
        "people_z": people_z,
        "support_props": [],
        "cameras": cameras,
        "cuts": _custom_cuts(cameras),
        "paths": paths,
        "static_points": [[-3000.0, -4050.0, people_z], [-2100.0, -3800.0, people_z], [-1200.0, -3700.0, people_z], [200.0, -3650.0, people_z]],
        "explicit_static_points": True,
        "lighting_preset": "warehouse_day",
        "extra_lights": [
            {"type": "point", "label": f"CineU_{scene_id}_dock_fill_a", "location": [-3300.0, -4250.0, 520.0], "intensity": 900.0, "radius": 3200.0, "color": [1.0, 0.88, 0.72]},
            {"type": "point", "label": f"CineU_{scene_id}_main_aisle_fill_b", "location": [-1500.0, -4200.0, 560.0], "intensity": 850.0, "radius": 3300.0, "color": [0.92, 0.96, 1.0]},
            {"type": "point", "label": f"CineU_{scene_id}_end_aisle_fill_c", "location": [650.0, -4050.0, 520.0], "intensity": 700.0, "radius": 3000.0, "color": [0.86, 0.93, 1.0]},
            {"type": "point", "label": f"CineU_{scene_id}_floor_fill_d", "location": [-800.0, -4550.0, 320.0], "intensity": 450.0, "radius": 2200.0, "color": [0.9, 0.94, 1.0]},
        ],
        "asset_first_plan": {
            "crowd": {
                "animation_bindings": animation_bindings,
                "high_detail_modular_parts": _production_formal_modular_parts(scene_id, animation_bindings),
                "metahuman_cinematic_parts": [],
                "readyposed_static_meshes": _scanned_posed_static_bindings(),
                "lane_offset_width": 90.0,
            }
        },
    }


def _car_dealer_showcase_day_spec() -> dict:
    scene_id = "car_dealer_showcase_day"
    people_z = 2.0
    eye_z = people_z + 135.0
    exposure_bias = 2.4
    exposure_brightness = 5.2
    cameras = [
        {
            "name": "CineU_car_dealer_surveillance_original",
            "shot_id": "car_dealer_surveillance_original",
            "type": "surveillance_fixed",
            "monitor_view": "original",
            "focal": 24.0,
            "keys": [_camera_key_raw(0, [-539.7562866210938, -5939.96875, 255.45217895507812], [1.8002495765686042, 99.597770690918, 0.0]), _camera_key_raw(FRAME_COUNT, [-539.7562866210938, -5939.96875, 255.45217895507812], [1.8002495765686042, 99.597770690918, 0.0])],
            "exposure_bias": exposure_bias,
            "exposure_brightness": exposure_brightness,
            "motion_blur_amount": 0.02,
        },
        {
            "name": "CineU_car_dealer_surveillance_reverse",
            "shot_id": "car_dealer_surveillance_reverse",
            "type": "surveillance_oblique",
            "monitor_view": "reverse",
            "focal": 22.0,
            "keys": [_camera_key(0, [3100.0, -6850.0, 520.0], [-400.0, -6100.0, eye_z]), _camera_key(FRAME_COUNT, [3100.0, -6850.0, 520.0], [-400.0, -6100.0, eye_z])],
            "exposure_bias": exposure_bias,
            "exposure_brightness": exposure_brightness,
            "motion_blur_amount": 0.02,
        },
        {
            "name": "CineU_car_dealer_surveillance_side",
            "shot_id": "car_dealer_surveillance_side",
            "type": "surveillance_oblique",
            "monitor_view": "side",
            "focal": 18.0,
            "keys": [_camera_key(0, [2400.0, -5950.0, 420.0], [-900.0, -6200.0, eye_z]), _camera_key(FRAME_COUNT, [2400.0, -5950.0, 420.0], [-900.0, -6200.0, eye_z])],
            "exposure_bias": exposure_bias,
            "exposure_brightness": exposure_brightness,
            "motion_blur_amount": 0.02,
        },
        {
            "name": "CineU_car_dealer_surveillance_far",
            "shot_id": "car_dealer_surveillance_far",
            "type": "surveillance_oblique",
            "monitor_view": "far",
            "focal": 18.0,
            "keys": [_camera_key(0, [4100.0, -7350.0, 900.0], [-500.0, -6100.0, eye_z]), _camera_key(FRAME_COUNT, [4100.0, -7350.0, 900.0], [-500.0, -6100.0, eye_z])],
            "exposure_bias": exposure_bias,
            "exposure_brightness": exposure_brightness,
            "motion_blur_amount": 0.02,
        },
        {
            "name": "CineU_car_dealer_top_down",
            "shot_id": "car_dealer_top_down",
            "type": "top_down",
            "monitor_view": "drone_overview",
            "focal": 14.0,
            "keys": [_camera_key(0, [2400.0, -6650.0, 1300.0], [800.0, -6300.0, people_z]), _camera_key(FRAME_COUNT, [2400.0, -6650.0, 1300.0], [800.0, -6300.0, people_z])],
            "exposure_bias": exposure_bias,
            "exposure_brightness": exposure_brightness,
            "motion_blur_amount": 0.02,
        },
        {
            "name": "CineU_car_dealer_first_person_walk",
            "shot_id": "car_dealer_first_person_walk",
            "type": "first_person",
            "focal": 14.0,
            "keys": [_camera_key(0, [-1250.0, -6300.0, people_z + 155.0], [-300.0, -6100.0, eye_z]), _camera_key(FRAME_COUNT, [1800.0, -5500.0, people_z + 155.0], [2500.0, -5300.0, eye_z])],
            "exposure_bias": exposure_bias,
            "exposure_brightness": exposure_brightness,
            "motion_blur_amount": 0.02,
        },
    ]
    cameras.extend(_cinematic_30s_cameras(scene_id, people_z, exposure_bias, exposure_brightness))
    cameras = _filter_custom_cameras(scene_id, cameras)
    paths = [
        ([-4300.0, -7600.0, people_z], [2500.0, -7600.0, people_z]),
        ([-4100.0, -6600.0, people_z], [3150.0, -6600.0, people_z]),
        ([-3900.0, -5600.0, people_z], [2900.0, -5600.0, people_z]),
        ([-2500.0, -7250.0, people_z], [-2500.0, -3000.0, people_z]),
    ]
    animation_bindings = _production_animation_bindings(scene_id, 24)
    return {
        "scene_id": scene_id,
        "source_level": "/Game/Showcase/Maps/CarShowcase",
        "description": "CineU production car dealer pedestrian scene using the downloaded Car Dealer Showcase map inside CityParkEnv55.",
        "people_z": people_z,
        "support_props": [],
        "cameras": cameras,
        "cuts": _custom_cuts(cameras),
        "paths": paths,
        "static_points": [[-4200.0, -3600.0, people_z], [-3000.0, -3900.0, people_z], [3300.0, -6300.0, people_z], [3300.0, -3350.0, people_z]],
        "explicit_static_points": True,
        "lighting_preset": "car_dealer_day",
        "extra_lights": [
            {"type": "point", "label": f"CineU_{scene_id}_showroom_fill_a", "location": [-2100.0, -6200.0, 520.0], "intensity": 15000.0, "radius": 5200.0, "color": [1.0, 0.9, 0.78]},
            {"type": "point", "label": f"CineU_{scene_id}_showroom_fill_b", "location": [2300.0, -4800.0, 520.0], "intensity": 13000.0, "radius": 5000.0, "color": [0.86, 0.93, 1.0]},
            {"type": "point", "label": f"CineU_{scene_id}_foreground_fill_c", "location": [-650.0, -5850.0, 330.0], "intensity": 9000.0, "radius": 2800.0, "color": [0.94, 0.96, 1.0]},
            {"type": "point", "label": f"CineU_{scene_id}_pedestrian_path_fill_d", "location": [820.0, -5550.0, 420.0], "intensity": 18000.0, "radius": 4600.0, "color": [0.88, 0.94, 1.0]},
            {"type": "point", "label": f"CineU_{scene_id}_side_walkway_fill_e", "location": [-1350.0, -6100.0, 380.0], "intensity": 12000.0, "radius": 3400.0, "color": [1.0, 0.88, 0.72]},
        ],
        "asset_first_plan": {
            "crowd": {
                "animation_bindings": animation_bindings,
                "high_detail_modular_parts": _production_formal_modular_parts(scene_id, animation_bindings),
                "metahuman_cinematic_parts": [],
                "readyposed_static_meshes": _scanned_posed_static_bindings(),
                "lane_offset_width": 90.0,
            }
        },
    }


def _downtown_west_day_spec(evening: bool = False) -> dict:
    scene_id = "downtown_west_evening" if evening else "downtown_west_day"
    people_z = 2.0
    eye_z = people_z + 135.0
    exposure_bias = -0.35 if evening else 0.25
    exposure_brightness = 0.62 if evening else 0.95
    source_level = _resolve_level_from_asset_index(DOWNTOWN_WEST_SOURCE_LEVEL_CANDIDATES, DOWNTOWN_WEST_LEVEL_MATCH_GROUPS)
    cameras = [
        {
            "name": "CineU_downtown_west_surveillance_original",
            "shot_id": "downtown_west_surveillance_original",
            "type": "surveillance_fixed",
            "monitor_view": "original",
            "focal": 61.651371002197266,
            "keys": [
                _camera_key_raw(0, [2286.49, -657.55, 182.1], [0.397, 179.036, 0.0]),
                _camera_key_raw(FRAME_COUNT, [2286.49, -657.55, 182.1], [0.397, 179.036, 0.0]),
            ],
            "exposure_bias": exposure_bias,
            "exposure_brightness": exposure_brightness,
            "motion_blur_amount": 0.02,
        },
        {
            "name": "CineU_downtown_west_surveillance_reverse",
            "shot_id": "downtown_west_surveillance_reverse",
            "type": "surveillance_oblique",
            "monitor_view": "reverse",
            "focal": 39.106292724609375,
            "keys": [
                _camera_key_raw(0, [-1069.22, 234.39, 905.52], [-19.798, -94.814, 0.0]),
                _camera_key_raw(FRAME_COUNT, [-1069.22, 234.39, 905.52], [-19.798, -94.814, 0.0]),
            ],
            "exposure_bias": exposure_bias,
            "exposure_brightness": exposure_brightness,
            "motion_blur_amount": 0.02,
        },
        {
            "name": "CineU_downtown_west_surveillance_side",
            "shot_id": "downtown_west_surveillance_side",
            "type": "surveillance_oblique",
            "monitor_view": "side",
            "focal": 50.0,
            "keys": [
                _camera_key_raw(0, [-2374.37, 1385.2, 150.45], [0.8, -35.787, 0.0]),
                _camera_key_raw(FRAME_COUNT, [-2374.37, 1385.2, 150.45], [0.8, -35.787, 0.0]),
            ],
            "exposure_bias": exposure_bias + (0.35 if not evening else 0.0),
            "exposure_brightness": 1.15 if not evening else exposure_brightness,
            "motion_blur_amount": 0.02,
        },
        {
            "name": "CineU_downtown_west_surveillance_far",
            "shot_id": "downtown_west_surveillance_far",
            "type": "surveillance_oblique",
            "monitor_view": "far",
            "focal": 50.0,
            "keys": [
                _camera_key_raw(0, [5063.33, -2895.89, 895.9], [-18.597, -48.802, 0.0]),
                _camera_key_raw(FRAME_COUNT, [5063.33, -2895.89, 895.9], [-18.597, -48.802, 0.0]),
            ],
            "exposure_bias": exposure_bias,
            "exposure_brightness": exposure_brightness,
            "motion_blur_amount": 0.02,
        },
        {
            "name": "CineU_downtown_west_top_down",
            "shot_id": "downtown_west_top_down",
            "type": "top_down",
            "monitor_view": "drone_overview",
            "focal": 16.0,
            "keys": [_camera_key_raw(0, [2200.0, -180.0, 2450.0], [-90.0, 0.0, 0.0]), _camera_key_raw(FRAME_COUNT, [2200.0, -180.0, 2450.0], [-90.0, 0.0, 0.0])],
            "exposure_bias": exposure_bias,
            "exposure_brightness": exposure_brightness,
            "motion_blur_amount": 0.02,
        },
        {
            "name": "CineU_downtown_west_first_person_walk",
            "shot_id": "downtown_west_first_person_walk",
            "type": "first_person",
            "focal": 24.0,
            "keys": [
                _camera_key(0, _downtown_west_native_location([3150.0, 4180.0, people_z + 158.0]), _downtown_west_native_location([2400.0, 4440.0, people_z + 145.0])),
                _camera_key(FRAME_COUNT, _downtown_west_native_location([1900.0, 4210.0, people_z + 158.0]), _downtown_west_native_location([980.0, 4480.0, people_z + 145.0])),
            ],
            "exposure_bias": exposure_bias,
            "exposure_brightness": exposure_brightness,
            "motion_blur_amount": 0.02,
        },
    ]
    cameras.extend(_cinematic_30s_cameras(scene_id, people_z, exposure_bias, exposure_brightness))
    cameras = _filter_custom_cameras(scene_id, cameras)
    paths = _citypark_new_environment_placements(scene_id)
    animation_bindings = _production_animation_bindings(scene_id, 32)
    return {
        "scene_id": scene_id,
        "source_level": source_level,
        "source_level_candidates": [source_level, *DOWNTOWN_WEST_SOURCE_LEVEL_CANDIDATES],
        "environment_requirement_id": "downtown_west",
        "description": "CineU production downtown pedestrian scene prepared for the Downtown West Fab environment inside CityParkEnv55.",
        "people_z": people_z,
        "support_props": _downtown_west_native_support_props([
            {"name": f"CineU_{scene_id}_walkway_a", "mesh": "/Game/Downtown_West/Assets/ground_walkways/SM_ground_mod_walkway_a_concrete", "location": [40.0, 3700.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": 2.0, "role": "walkway"},
            {"name": f"CineU_{scene_id}_walkway_b", "mesh": "/Game/Downtown_West/Assets/ground_walkways/SM_ground_mod_walkway_b_concrete", "location": [40.0, 4320.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": 2.0, "role": "walkway"},
            {"name": f"CineU_{scene_id}_walkway_c", "mesh": "/Game/Downtown_West/Assets/ground_walkways/SM_ground_mod_walkway_a_concrete", "location": [40.0, 4940.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": 2.0, "role": "walkway"},
            {"name": f"CineU_{scene_id}_brick_walk_tile_a", "mesh": "/Game/Downtown_West/Assets/ground_walkways/SM_ground_mod_walk_tile_a_6m_a", "location": [300.0, 3900.0, 1.0], "rotation": [0.0, 0.0, 0.0], "scale": 2.2, "role": "walkway"},
            {"name": f"CineU_{scene_id}_brick_walk_tile_b", "mesh": "/Game/Downtown_West/Assets/ground_walkways/SM_ground_mod_walk_tile_a_6m_b", "location": [300.0, 4520.0, 1.0], "rotation": [0.0, 0.0, 0.0], "scale": 2.2, "role": "walkway"},
            {"name": f"CineU_{scene_id}_west_storefront_a", "mesh": "/Game/Downtown_West/Assets/building_a/SM_build_cafe_a_wall_windows_long", "location": [-900.0, 3720.0, people_z], "rotation": [0.0, 90.0, 0.0], "scale": 1.0, "role": "storefront_module", "material_override": "/Game/Downtown_West/Assets/bricks_large/MI_Bricks_Props_A"},
            {"name": f"CineU_{scene_id}_west_storefront_b", "mesh": "/Game/Downtown_West/Assets/building_a/SM_build_cafe_a_wall_corner_door_entry", "location": [-900.0, 4300.0, people_z], "rotation": [0.0, 90.0, 0.0], "scale": 1.0, "role": "storefront_module", "material_override": "/Game/Downtown_West/Assets/bricks_large/MI_Bricks_Props_C"},
            {"name": f"CineU_{scene_id}_west_storefront_c", "mesh": "/Game/Downtown_West/Assets/building_a/SM_build_cafe_a_mod_windows_long_b", "location": [-900.0, 4880.0, people_z], "rotation": [0.0, 90.0, 0.0], "scale": 1.0, "role": "storefront_module", "material_override": "/Game/Downtown_West/Assets/bricks_large/MI_Bricks_Props_B"},
            {"name": f"CineU_{scene_id}_east_storefront_a", "mesh": "/Game/Downtown_West/Assets/building_a/SM_build_cafe_a_mod_wall_a", "location": [1840.0, 3800.0, people_z], "rotation": [0.0, 90.0, 0.0], "scale": 1.0, "role": "storefront_module", "material_override": "/Game/Downtown_West/Assets/bricks_large/MI_Bricks_Props_D"},
            {"name": f"CineU_{scene_id}_east_storefront_b", "mesh": "/Game/Downtown_West/Assets/building_a/SM_build_cafe_a_mod_windows_long_c", "location": [1840.0, 4380.0, people_z], "rotation": [0.0, 90.0, 0.0], "scale": 1.0, "role": "storefront_module", "material_override": "/Game/Downtown_West/Assets/bricks_large/MI_Bricks_Props_A"},
            {"name": f"CineU_{scene_id}_east_storefront_c", "mesh": "/Game/Downtown_West/Assets/building_a/SM_build_cafe_a_mod_door_b", "location": [1840.0, 4960.0, people_z], "rotation": [0.0, 90.0, 0.0], "scale": 1.0, "role": "storefront_module", "material_override": "/Game/Downtown_West/Assets/bricks_large/MI_Bricks_Props_C"},
            {"name": f"CineU_{scene_id}_west_building_b_store_a", "mesh": "/Game/Downtown_West/Assets/building_b/SM_build_b_mod_lvl1_storefront_a_5m", "location": [-980.0, 3960.0, people_z], "rotation": [0.0, 90.0, 0.0], "scale": 1.0, "role": "storefront_module"},
            {"name": f"CineU_{scene_id}_west_building_b_store_b", "mesh": "/Game/Downtown_West/Assets/building_b/SM_build_b_mod_lvl1_storefront_b_wall5m", "location": [-980.0, 4540.0, people_z], "rotation": [0.0, 90.0, 0.0], "scale": 1.0, "role": "storefront_module"},
            {"name": f"CineU_{scene_id}_east_building_b_corner", "mesh": "/Game/Downtown_West/Assets/building_b/SM_build_b_mod_lvl1_storefront_b_corner_a", "location": [1420.0, 3940.0, people_z], "rotation": [0.0, -90.0, 0.0], "scale": 1.0, "role": "storefront_module"},
            {"name": f"CineU_{scene_id}_east_building_b_store", "mesh": "/Game/Downtown_West/Assets/building_b/SM_build_b_mod_lvl1_storefront_a_3_5m", "location": [1420.0, 4740.0, people_z], "rotation": [0.0, -90.0, 0.0], "scale": 1.0, "role": "storefront_module"},
            {"name": f"CineU_{scene_id}_awning_west_a", "mesh": "/Game/Downtown_West/Assets/awnings/SM_building_awning_a", "location": [-720.0, 3720.0, 410.0], "rotation": [0.0, 90.0, 0.0], "scale": 1.0, "role": "storefront_awning", "material_override": "/Game/Downtown_West/Assets/awnings/awnings_material/MI_building_awning_ab_cloth_red"},
            {"name": f"CineU_{scene_id}_awning_west_b", "mesh": "/Game/Downtown_West/Assets/awnings/SM_building_awning_b", "location": [-720.0, 4300.0, 410.0], "rotation": [0.0, 90.0, 0.0], "scale": 1.0, "role": "storefront_awning", "material_override": "/Game/Downtown_West/Assets/awnings/awnings_material/MI_building_awning_ab_cloth_blue_stripes"},
            {"name": f"CineU_{scene_id}_awning_east_a", "mesh": "/Game/Downtown_West/Assets/awnings/SM_building_awning_a", "location": [1380.0, 4380.0, 410.0], "rotation": [0.0, -90.0, 0.0], "scale": 1.0, "role": "storefront_awning", "material_override": "/Game/Downtown_West/Assets/awnings/awnings_material/MI_building_awning_ab_cloth_green_dark"},
            {"name": f"CineU_{scene_id}_cafe_sign", "mesh": "/Game/Downtown_West/Assets/props/prop_store_signs/SM_signs_sign_cafe", "location": [-650.0, 4300.0, people_z], "rotation": [0.0, 92.0, 0.0], "scale": 1.0, "role": "storefront_sign", "material_override": "/Game/Downtown_West/Assets/props/prop_store_signs/MI_prop_store_signs_color2"},
            {"name": f"CineU_{scene_id}_bistro_sign", "mesh": "/Game/Downtown_West/Assets/props/prop_store_signs/SM_signs_sign_bistro", "location": [1370.0, 4380.0, people_z], "rotation": [0.0, -88.0, 0.0], "scale": 1.0, "role": "storefront_sign", "material_override": "/Game/Downtown_West/Assets/props/prop_store_signs/MI_prop_store_signs_color4"},
            {"name": f"CineU_{scene_id}_cornercafe_poster", "mesh": "/Game/Downtown_West/Assets/props/prop_store_signs/SM_signs_poster_cornercafe", "location": [-705.0, 4160.0, people_z], "rotation": [0.0, 94.0, 0.0], "scale": 1.0, "role": "storefront_poster", "material_override": "/Game/Downtown_West/Assets/props/prop_store_signs/MI_prop_store_signs_color5"},
            {"name": f"CineU_{scene_id}_sale_foldout_sign", "mesh": "/Game/Downtown_West/Assets/props/prop_store_signs/SM_signs_sign_foldout_sale", "location": [1040.0, 4060.0, people_z], "rotation": [0.0, -24.0, 0.0], "scale": 1.0, "role": "sidewalk_sign", "material_override": "/Game/Downtown_West/Assets/props/prop_store_signs/MI_prop_store_signs_color3"},
            {"name": f"CineU_{scene_id}_coffee_table", "mesh": "/Game/Downtown_West/Assets/props/prop_table/SM_prop_dining_table_a", "location": [180.0, 4300.0, people_z], "rotation": [0.0, 12.0, 0.0], "scale": 1.0, "role": "cafe_table"},
            {"name": f"CineU_{scene_id}_coffee_chair_a", "mesh": "/Game/Downtown_West/Assets/props/prop_table/SM_prop_dining_chair_a", "location": [95.0, 4260.0, people_z], "rotation": [0.0, 55.0, 0.0], "scale": 1.0, "role": "cafe_chair"},
            {"name": f"CineU_{scene_id}_coffee_chair_b", "mesh": "/Game/Downtown_West/Assets/props/prop_table/SM_prop_dining_chair_b", "location": [250.0, 4355.0, people_z], "rotation": [0.0, -132.0, 0.0], "scale": 1.0, "role": "cafe_chair"},
            {"name": f"CineU_{scene_id}_umbrella", "mesh": "/Game/Downtown_West/Assets/props/prop_table/SM_prop_table_umbrella_a", "location": [180.0, 4300.0, people_z], "rotation": [0.0, 4.0, 0.0], "scale": 1.0, "role": "cafe_umbrella", "material_override": "/Game/Downtown_West/Assets/props/prop_table/MI_prop_umbrella_yellow"},
            {"name": f"CineU_{scene_id}_hotdog_cart", "mesh": "/Game/Downtown_West/Assets/props/prop_hotdog_cart/SM_food_cart", "location": [930.0, 4520.0, people_z], "rotation": [0.0, -24.0, 0.0], "scale": 1.0, "role": "street_vendor"},
            {"name": f"CineU_{scene_id}_bench", "mesh": "/Game/Downtown_West/Assets/props/prop_bench_wood/SM_bench_wood_a", "location": [1180.0, 4960.0, people_z], "rotation": [0.0, 88.0, 0.0], "scale": 1.0, "role": "bench"},
            {"name": f"CineU_{scene_id}_poster_stand", "mesh": "/Game/Downtown_West/Assets/props/prop_poster_stands/SM_prop_poster_stand", "location": [-620.0, 4000.0, people_z], "rotation": [0.0, 92.0, 0.0], "scale": 1.0, "role": "poster_stand"},
            {"name": f"CineU_{scene_id}_poster_pillar", "mesh": "/Game/Downtown_West/Assets/props/prop_poster_stands/SM_prop_poster_pillar_with_posters", "location": [520.0, 4920.0, people_z], "rotation": [0.0, -18.0, 0.0], "scale": 1.0, "role": "poster_pillar"},
            {"name": f"CineU_{scene_id}_hydrant", "mesh": "/Game/Downtown_West/Assets/props/prop_fire_hydrant/SM_fire_hydrant", "location": [1180.0, 3700.0, people_z], "rotation": [0.0, -18.0, 0.0], "scale": 1.0, "role": "street_hydrant"},
            {"name": f"CineU_{scene_id}_streetlight_a", "mesh": "/Game/Downtown_West/Assets/props/props_streetlight/SM_light_streetlight_complete", "location": [-480.0, 3600.0, people_z], "rotation": [0.0, 0.0, 0.0], "scale": 1.0, "role": "streetlight"},
            {"name": f"CineU_{scene_id}_streetlight_b", "mesh": "/Game/Downtown_West/Assets/props/props_streetlight/SM_light_streetlight_complete", "location": [1180.0, 5080.0, people_z], "rotation": [0.0, 180.0, 0.0], "scale": 1.0, "role": "streetlight"},
            {"name": f"CineU_{scene_id}_banner_lightpost", "mesh": "/Game/Downtown_West/Assets/props/props_light_post/SM_lightpost_light_post_a", "location": [1320.0, 3860.0, people_z], "rotation": [0.0, -18.0, 0.0], "scale": 1.0, "role": "streetlight"},
            {"name": f"CineU_{scene_id}_traffic_light", "mesh": "/Game/CityPark/Meshes/Props/SM_TrafficLight_01", "location": [1480.0, 3640.0, people_z], "rotation": [0.0, 180.0, 0.0], "scale": 0.9, "role": "traffic_light"},
            {"name": f"CineU_{scene_id}_road_sign", "mesh": "/Game/CityPark/Meshes/Props/RoadSigns/SM_RoadSigns12", "location": [-760.0, 5080.0, people_z], "rotation": [0.0, 36.0, 0.0], "scale": 1.0, "role": "road_sign"},
            {"name": f"CineU_{scene_id}_recycle_bin", "mesh": "/Game/Downtown_West/Assets/props/prop_recycle_bin/SM_prop_recycle_bin", "location": [-730.0, 4600.0, people_z], "rotation": [0.0, 18.0, 0.0], "scale": 1.0, "role": "street_bin"},
            {"name": f"CineU_{scene_id}_planter_a", "mesh": "/Game/Downtown_West/Assets/props/prop_pots/SM_pot_c", "location": [-520.0, 4700.0, people_z], "rotation": [0.0, 0.0, 0.0], "scale": 1.0, "role": "planter"},
            {"name": f"CineU_{scene_id}_planter_b", "mesh": "/Game/Downtown_West/Assets/props/prop_pots/SM_pot_d", "location": [1260.0, 4040.0, people_z], "rotation": [0.0, 0.0, 0.0], "scale": 1.0, "role": "planter"},
            {"name": f"CineU_{scene_id}_narrowleaf_tree_a", "mesh": "/Game/Downtown_West/Assets/foliage/tree_narrowleaf/SM_tree_narrowleaf_b", "location": [1490.0, 5060.0, people_z], "rotation": [0.0, -42.0, 0.0], "scale": 0.85, "role": "street_tree"},
        ]),
        "cameras": cameras,
        "cuts": _custom_cuts(cameras),
        "paths": paths,
        "static_points": [
            _downtown_west_native_location(point)
            for point in [[1120.0, 5050.0, people_z], [1260.0, 5600.0, people_z], [1880.0, 5180.0, people_z], [2380.0, 5430.0, people_z], [2880.0, 5430.0, people_z], [920.0, 4860.0, people_z], [1740.0, 5120.0, people_z], [3100.0, 5220.0, people_z]]
        ],
        "explicit_static_points": True,
        "disable_existing_post_process": False,
        "disable_existing_lights": False,
        "scene_capture_source": "final_color_ldr",
        "streaming_level_visibility": (
            [
                {"contains": "/Sub-Levels/Daytime_Lighting", "loaded": False, "visible": False},
                {"contains": "/Sub-Levels/Nightime_Lighting", "loaded": True, "visible": True},
                {"contains": "/Sub-Levels/Night_Lighting", "loaded": True, "visible": True},
            ]
            if evening
            else [
                {"contains": "/Sub-Levels/Daytime_Lighting", "loaded": True, "visible": True},
                {"contains": "/Sub-Levels/Nightime_Lighting", "loaded": False, "visible": False},
                {"contains": "/Sub-Levels/Night_Lighting", "loaded": False, "visible": False},
            ]
        ),
        "lighting_preset": "downtown_blue_hour" if evening else "day",
        "extra_lights": (
            [
                {"type": "point", "label": f"CineU_{scene_id}_warm_storefront_a", "location": _downtown_west_native_location([1680.0, 5170.0, 620.0]), "intensity": 1700.0, "radius": 3000.0, "color": [1.0, 0.76, 0.48], "cast_shadows": False},
                {"type": "point", "label": f"CineU_{scene_id}_warm_storefront_b", "location": _downtown_west_native_location([3000.0, 5430.0, 620.0]), "intensity": 1500.0, "radius": 3000.0, "color": [1.0, 0.82, 0.55], "cast_shadows": False},
                {"type": "point", "label": f"CineU_{scene_id}_cool_crosswalk", "location": _downtown_west_native_location([1050.0, 4860.0, 780.0]), "intensity": 1200.0, "radius": 3200.0, "color": [0.62, 0.74, 1.0], "cast_shadows": False},
                {"type": "point", "label": f"CineU_{scene_id}_street_depth_blue", "location": _downtown_west_native_location([1220.0, 5820.0, 900.0]), "intensity": 950.0, "radius": 3200.0, "color": [0.56, 0.68, 1.0], "cast_shadows": False},
            ]
            if evening
            else [
                {"type": "directional", "label": f"CineU_{scene_id}_sun_key", "location": [0.0, 0.0, 1600.0], "rotation": [-42.0, -38.0, 0.0], "intensity": 0.55, "color": [1.0, 0.94, 0.84], "cast_shadows": False},
                {"type": "sky", "label": f"CineU_{scene_id}_sky_fill", "location": [0.0, 0.0, 1200.0], "intensity": 0.36, "color": [0.82, 0.9, 1.0], "cast_shadows": False},
                {"type": "point", "label": f"CineU_{scene_id}_street_fill_a", "location": _downtown_west_native_location([1220.0, 5820.0, 900.0]), "intensity": 760.0, "radius": 3000.0, "color": [0.9, 0.95, 1.0], "cast_shadows": False},
                {"type": "point", "label": f"CineU_{scene_id}_crosswalk_fill_b", "location": _downtown_west_native_location([1050.0, 4860.0, 740.0]), "intensity": 620.0, "radius": 2850.0, "color": [1.0, 0.92, 0.78], "cast_shadows": False},
                {"type": "point", "label": f"CineU_{scene_id}_storefront_fill_c", "location": _downtown_west_native_location([2600.0, 5430.0, 760.0]), "intensity": 700.0, "radius": 3000.0, "color": [0.86, 0.93, 1.0], "cast_shadows": False},
                {"type": "point", "label": f"CineU_{scene_id}_pedestrian_fill_d", "location": _downtown_west_native_location([1850.0, 4680.0, 540.0]), "intensity": 560.0, "radius": 2500.0, "color": [1.0, 0.88, 0.74], "cast_shadows": False},
                {"type": "point", "label": f"CineU_{scene_id}_camera_side_fill_e", "location": _downtown_west_native_location([760.0, 3660.0, 430.0]), "intensity": 420.0, "radius": 2100.0, "color": [0.92, 0.96, 1.0], "cast_shadows": False},
            ]
        ),
        "asset_first_plan": {
            "crowd": {
                "animation_bindings": animation_bindings,
                "high_detail_modular_parts": _production_formal_modular_parts(scene_id, animation_bindings),
                "metahuman_cinematic_parts": [],
                "metahuman_blueprint_characters": [],
                "blueprint_characters": (
                    _production_city_sample_blueprints(scene_id)
                    if CITY_SAMPLE_CROWD_BLUEPRINTS_ENABLED
                    else []
                ),
                "readyposed_static_meshes": _scanned_posed_static_bindings(),
                "lane_offset_width": 110.0,
            }
        },
    }


def _world_template_6_7_day_spec() -> dict:
    scene_id = "world_template_6_7_day"
    people_z = 2.0
    exposure_bias = 2.0
    exposure_brightness = 4.2
    local_exposure = {
        "method": "bilateral",
        "highlight_contrast_scale": 0.6,
        "shadow_contrast_scale": 0.6,
        "detail_strength": 1.0,
        "blurred_luminance_blend": 0.5,
        "middle_grey_bias": 1.5,
    }
    source_level = _resolve_level_from_asset_index(DOWNTOWN_WEST_SOURCE_LEVEL_CANDIDATES, DOWNTOWN_WEST_LEVEL_MATCH_GROUPS)
    cafe_anchor = _world_template_6_7_native_location([-1050.0, 2250.0, people_z])
    top_location = _world_template_6_7_native_location([-300.0, 5000.0, 2400.0])
    top_target = _world_template_6_7_native_location([-900.0, 3400.0, 20.0])
    oblique_location = _world_template_6_7_native_location([-850.0, 6700.0, 1700.0])
    oblique_target = _world_template_6_7_native_location([-1250.0, 3400.0, 80.0])
    reverse_location = _world_template_6_7_native_location([650.0, 1300.0, 650.0])
    reverse_target = _world_template_6_7_native_location([-1050.0, 2650.0, 100.0])
    side_location = _world_template_6_7_native_location([1200.0, 3000.0, 650.0])
    side_target = _world_template_6_7_native_location([-1000.0, 2400.0, 100.0])
    far_location = _world_template_6_7_native_location([1900.0, 4900.0, 1500.0])
    far_target = _world_template_6_7_native_location([-1050.0, 2500.0, 100.0])
    cameras = [
        {
            "name": "CineU_world_template_6_top_surveillance",
            "shot_id": "world_template_6_top_surveillance",
            "type": "surveillance_oblique",
            "monitor_view": "template_6_top",
            "focal": 32.0,
            "keys": [
                _camera_key(0, top_location, top_target),
                _camera_key(FRAME_COUNT, top_location, top_target),
            ],
            "exposure_bias": exposure_bias,
            "exposure_brightness": exposure_brightness,
            "motion_blur_amount": 0.02,
        },
        {
            "name": "CineU_world_template_7_oblique_branch",
            "shot_id": "world_template_7_oblique_branch",
            "type": "surveillance_oblique",
            "monitor_view": "template_7_oblique",
            "focal": 30.0,
            "keys": [
                _camera_key(0, oblique_location, oblique_target),
                _camera_key(FRAME_COUNT, oblique_location, oblique_target),
            ],
            "exposure_bias": exposure_bias,
            "exposure_brightness": exposure_brightness,
            "motion_blur_amount": 0.02,
        },
        {
            "name": "CineU_world_template_6_7_reverse_surveillance",
            "shot_id": "world_template_6_7_reverse_surveillance",
            "type": "surveillance_oblique",
            "monitor_view": "reverse",
            "focal": 38.0,
            "keys": [
                _camera_key(0, reverse_location, reverse_target),
                _camera_key(FRAME_COUNT, reverse_location, reverse_target),
            ],
            "exposure_bias": exposure_bias,
            "exposure_brightness": exposure_brightness,
            "motion_blur_amount": 0.02,
        },
        {
            "name": "CineU_world_template_6_7_side_surveillance",
            "shot_id": "world_template_6_7_side_surveillance",
            "type": "surveillance_oblique",
            "monitor_view": "side",
            "focal": 40.0,
            "keys": [
                _camera_key(0, side_location, side_target),
                _camera_key(FRAME_COUNT, side_location, side_target),
            ],
            "exposure_bias": exposure_bias,
            "exposure_brightness": exposure_brightness,
            "motion_blur_amount": 0.02,
        },
        {
            "name": "CineU_world_template_6_7_far_surveillance",
            "shot_id": "world_template_6_7_far_surveillance",
            "type": "surveillance_oblique",
            "monitor_view": "far",
            "focal": 45.0,
            "keys": [
                _camera_key(0, far_location, far_target),
                _camera_key(FRAME_COUNT, far_location, far_target),
            ],
            "exposure_bias": exposure_bias,
            "exposure_brightness": exposure_brightness,
            "motion_blur_amount": 0.02,
        },
    ]
    cameras.extend(_cinematic_30s_cameras(scene_id, people_z, exposure_bias, exposure_brightness))
    for camera in cameras:
        camera["local_exposure"] = dict(local_exposure)
    cameras = _filter_custom_cameras(scene_id, cameras)
    animation_bindings = _production_animation_bindings(scene_id, 28)
    blue_umbrella_material = {
        "material_label": "world_template_deep_blue_cafe_umbrella_v2",
        "color": [0.018, 0.07, 0.30],
        "roughness": 0.72,
        "specular": 0.16,
        "metallic": 0.0,
        "reuse_existing_if_present": False,
    }
    red_table_material = {
        "material_label": "world_template_red_cafe_table",
        "color": [0.62, 0.055, 0.035],
        "roughness": 0.48,
        "specular": 0.34,
        "metallic": 0.0,
    }
    red_chair_material = {
        "material_label": "world_template_red_cafe_chair",
        "color": [0.54, 0.045, 0.035],
        "roughness": 0.52,
        "specular": 0.28,
        "metallic": 0.0,
    }
    support_props = _downtown_west_reference_support_props([
        {"name": f"CineU_{scene_id}_red_awning", "mesh": "/Game/Downtown_West/Assets/awnings/SM_building_awning_a", "location": [-1000.0, 1950.0, 522.0], "rotation": [0.0, 90.0, 0.0], "scale": 1.0, "role": "reference_red_awning", "material_override": "/Game/Downtown_West/Assets/awnings/awnings_material/MI_building_awning_ab_cloth_red", "cast_shadow": True},
        {"name": f"CineU_{scene_id}_blue_striped_awning", "mesh": "/Game/Downtown_West/Assets/awnings/SM_building_awning_b", "location": [-1000.0, 2450.0, 522.0], "rotation": [0.0, 90.0, 0.0], "scale": 1.0, "role": "reference_blue_awning", "material_override": "/Game/Downtown_West/Assets/awnings/awnings_material/MI_building_awning_ab_cloth_blue_stripes", "cast_shadow": True},
        {"name": f"CineU_{scene_id}_blue_umbrella_primary", "mesh": "/Game/Downtown_West/Assets/props/prop_table/SM_prop_table_umbrella_a", "location": [-753.0, 2456.0, people_z], "rotation": [0.0, 4.0, 0.0], "scale": 0.64, "role": "reference_blue_umbrella", "material_profile": blue_umbrella_material, "cast_shadow": True},
        {"name": f"CineU_{scene_id}_red_table_primary", "mesh": "/Game/Downtown_West/Assets/props/prop_table/SM_prop_dining_table_a", "location": [-826.0, 1880.0, people_z], "rotation": [0.0, 12.0, 0.0], "scale": 1.0, "role": "reference_red_cafe_table", "material_profile": red_table_material, "cast_shadow": True},
        {"name": f"CineU_{scene_id}_red_chair_primary_a", "mesh": "/Game/Downtown_West/Assets/props/prop_table/SM_prop_dining_chair_a", "location": [-930.0, 1805.0, people_z], "rotation": [0.0, 56.0, 0.0], "scale": 1.0, "role": "reference_red_cafe_chair", "material_profile": red_chair_material, "cast_shadow": True},
        {"name": f"CineU_{scene_id}_red_chair_primary_b", "mesh": "/Game/Downtown_West/Assets/props/prop_table/SM_prop_dining_chair_b", "location": [-700.0, 1980.0, people_z], "rotation": [0.0, -132.0, 0.0], "scale": 1.0, "role": "reference_red_cafe_chair", "material_profile": red_chair_material, "cast_shadow": True},
        {"name": f"CineU_{scene_id}_table_secondary", "mesh": "/Game/Downtown_West/Assets/props/prop_table/SM_prop_dining_table_a", "location": [-1717.0, 3141.0, people_z], "rotation": [0.0, -18.0, 0.0], "scale": 1.0, "role": "reference_cafe_table", "material_override": "/Game/Downtown_West/Assets/props/prop_table/MI_prop_table_c_blue", "cast_shadow": True},
        {"name": f"CineU_{scene_id}_chair_secondary_a", "mesh": "/Game/Downtown_West/Assets/props/prop_table/SM_prop_dining_chair_a", "location": [-1788.0, 3136.0, people_z], "rotation": [0.0, 42.0, 0.0], "scale": 1.0, "role": "reference_cafe_chair", "cast_shadow": True},
        {"name": f"CineU_{scene_id}_cafe_sign", "mesh": "/Game/Downtown_West/Assets/props/prop_store_signs/SM_signs_sign_cafe", "location": [-1775.0, 3020.0, 203.0], "rotation": [0.0, 92.0, 0.0], "scale": 1.0, "role": "reference_cafe_sign", "material_override": "/Game/Downtown_West/Assets/props/prop_store_signs/MI_prop_store_signs_color2", "cast_shadow": True},
        {"name": f"CineU_{scene_id}_cornercafe_poster", "mesh": "/Game/Downtown_West/Assets/props/prop_store_signs/SM_signs_poster_cornercafe", "location": [-1775.0, 3020.0, 185.0], "rotation": [0.0, 94.0, 0.0], "scale": 1.0, "role": "reference_cafe_poster", "material_override": "/Game/Downtown_West/Assets/props/prop_store_signs/MI_prop_store_signs_color5", "cast_shadow": True},
        {"name": f"CineU_{scene_id}_foldout_sign", "mesh": "/Game/Downtown_West/Assets/props/prop_store_signs/SM_signs_sign_foldout_sale", "location": [-1380.0, 2300.0, people_z], "rotation": [0.0, -20.0, 0.0], "scale": 1.0, "role": "reference_foldout_sign", "material_override": "/Game/Downtown_West/Assets/props/prop_store_signs/MI_prop_store_signs_color3", "cast_shadow": True},
        {"name": f"CineU_{scene_id}_planter", "mesh": "/Game/Downtown_West/Assets/props/prop_pots/SM_pot_d", "location": [-1190.0, 2680.0, people_z], "rotation": [0.0, 0.0, 0.0], "scale": 1.0, "role": "reference_planter", "cast_shadow": True},
    ])
    return {
        "scene_id": scene_id,
        "source_level": source_level,
        "source_level_candidates": [source_level, *DOWNTOWN_WEST_SOURCE_LEVEL_CANDIDATES],
        "environment_requirement_id": "world_template_6_7_recreation",
        "description": "CineU recreation of world_template 6.png/7.png using the Downtown West Fab cafe street as the asset-first base: brick walkway, cafe storefront, awnings, blue umbrella, red cafe furniture, lamp posts, daylight shadows, and varied high-quality pedestrians.",
        "people_z": people_z,
        "support_props": support_props,
        "reference_region": {
            "source": "Downtown West Demo Environment cafe street",
            "cafe_anchor": cafe_anchor,
            "cafe_building_mesh": "/Game/Downtown_West/Assets/building_a/SM_build_cafe_a_wall_corner_door_entry",
            "existing_assets": [
                "/Game/Downtown_West/Maps/Demo_Environment",
                "/Game/Downtown_West/Assets/building_a/SM_build_cafe_a_wall_corner_door_entry",
                "/Game/Downtown_West/Assets/ground_walkways/SM_ground_mod_tile_a",
                "/Game/Downtown_West/Assets/ground_walkways/SM_ground_mod_brick_walkway_a_curve",
                "/Game/Downtown_West/Assets/awnings/SM_building_awning_a",
                "/Game/Downtown_West/Assets/awnings/SM_building_awning_b",
                "/Game/Downtown_West/Assets/props/prop_table/SM_prop_table_umbrella_a",
                "/Game/Downtown_West/Assets/props/prop_table/SM_prop_dining_table_a",
                "/Game/Downtown_West/Assets/props/prop_table/SM_prop_dining_chair_a",
                "/Game/Downtown_West/Assets/props/props_streetlight/SM_light_streetlight_complete",
                "/Game/Downtown_West/Assets/foliage/tree_narrowleaf/SM_tree_narrowleaf_a",
            ],
        },
        "cameras": cameras,
        "cuts": _custom_cuts(cameras),
        "paths": _citypark_new_environment_placements(scene_id),
        "static_points": [
            _world_template_6_7_native_location(point)
            for point in [
                [-3050.0, 3850.0, people_z],
                [-2450.0, 4120.0, people_z],
                [-1000.0, 3800.0, people_z],
                [-4500.0, 4100.0, people_z],
                [-3900.0, 3900.0, people_z],
                [-1400.0, 3950.0, people_z],
            ]
        ],
        "explicit_static_points": True,
        "disable_existing_post_process": False,
        "disable_existing_lights": False,
        "hide_existing_actor_labels": [
            "light_streetlight_complete2",
            "prop_table_umbrella_a",
            "prop_table_umbrella_a3",
            "prop_table_umbrella_a4",
            "prop_table_umbrellabase_a",
            "prop_table_umbrellabase_a2",
            "prop_dining_table_a3",
            "prop_dining_chair_a14",
            "prop_dining_chair_a15",
            "prop_dining_chair_a16",
        ],
        "scene_capture_source": "final_color_ldr",
        "streaming_level_visibility": [
            {"contains": "/Sub-Levels/Daytime_Lighting", "loaded": True, "visible": True},
            {"contains": "/Sub-Levels/Nightime_Lighting", "loaded": False, "visible": False},
            {"contains": "/Sub-Levels/Night_Lighting", "loaded": False, "visible": False},
        ],
        "sequencer_level_visibility": [
            {"level_names": ["Daytime_Lighting"], "visible": True},
            {"level_names": ["Nightime_Lighting"], "visible": False},
        ],
        "lighting_preset": "world_template_downtown_cafe_day",
        "extra_lights": [
            {
                "type": "directional",
                "label": f"CineU_{scene_id}_cinematic_bounce_fill",
                "location": [0.0, 0.0, 2400.0],
                "rotation": [-38.0, -48.0, 0.0],
                "intensity": 20.0,
                "source_angle": 6.0,
                "color": [1.0, 0.96, 0.90],
                "cast_shadows": False,
            },
            {
                "type": "sky",
                "label": f"CineU_{scene_id}_cinematic_sky_fill",
                "location": [0.0, -2400.0, 1800.0],
                "rotation": [0.0, 0.0, 0.0],
                "intensity": 1.5,
                "color": [0.80, 0.89, 1.0],
                "cast_shadows": False,
            },
        ],
        "asset_first_plan": {
            "crowd": {
                "animation_bindings": animation_bindings,
                "high_detail_modular_parts": _production_formal_modular_parts(scene_id, animation_bindings),
                "metahuman_cinematic_parts": [],
                "metahuman_blueprint_characters": [],
                "blueprint_characters": [],
                "readyposed_static_meshes": _scanned_posed_static_bindings(),
                "lane_offset_width": 40.0,
            }
        },
    }


def _museum_gallery_day_spec() -> dict:
    return _museum_gallery_spec(night=False)


def _museum_gallery_night_spec() -> dict:
    return _museum_gallery_spec(night=True)


def _citypark_promenade_day_spec() -> dict:
    return _citypark_promenade_spec(night=False)


def _citypark_promenade_night_spec() -> dict:
    return _citypark_promenade_spec(night=True)


def _art_gallery_day_spec() -> dict:
    return _art_gallery_spec()


def _downtown_west_evening_spec() -> dict:
    return _downtown_west_day_spec(evening=True)


SCENES = {
    "scene19": _scene19_spec,
    "scene24": _scene24_spec,
    "scene24_indoor_multiroom": _scene24_indoor_multiroom_spec,
    "museum_gallery_day": _museum_gallery_day_spec,
    "museum_gallery_night": _museum_gallery_night_spec,
    "citypark_promenade_day": _citypark_promenade_day_spec,
    "citypark_promenade_night": _citypark_promenade_night_spec,
    "art_gallery_day": _art_gallery_day_spec,
    "warehouse_day": _warehouse_day_spec,
    "car_dealer_showcase_day": _car_dealer_showcase_day_spec,
    "downtown_west_day": _downtown_west_day_spec,
    "downtown_west_evening": _downtown_west_evening_spec,
    "world_template_6_7_day": _world_template_6_7_day_spec,
}


def _crowd_specs(spec: dict) -> list[dict]:
    people = []
    paths = spec["paths"]
    plan = spec.get("asset_first_plan") or {}
    crowd = plan.get("crowd") or {}
    animation_bindings = crowd.get("animation_bindings") or []
    blueprint_characters = crowd.get("blueprint_characters") or []
    if CROWD_SOURCE_FILTER:
        allowed_sources = {source.strip() for source in CROWD_SOURCE_FILTER.split(",") if source.strip()}
        animation_bindings = [binding for binding in animation_bindings if str(binding.get("source", "")) in allowed_sources]
    skeletal_count = len(animation_bindings) or (0 if blueprint_characters else (18 if spec["scene_id"] == "scene19" else 16))
    stable_moving_replacement_count = 0
    for index in range(skeletal_count):
        start, end = paths[index % len(paths)]
        waypoints = None
        motion = "walking"
        source = "existing_twinmotion_rigged_character"
        animation_phase_offset_frames = _pedestrian_animation_phase_offset(index)
        binding_explicit_route = False
        lane_offset_width = float(crowd.get("lane_offset_width", 28.0 if spec.get("explicit_static_points") else 90.0))
        lane_offset = ((index % 3) - 1) * lane_offset_width
        start = [start[0], start[1] + lane_offset, spec["people_z"]]
        end = [end[0], end[1] - lane_offset * 0.5, spec["people_z"]]
        if spec["scene_id"].startswith("museum_gallery"):
            cycle = index // len(paths)
            start = [start[0] + cycle * 42.0, start[1] + (cycle % 2) * 18.0, start[2]]
            end = [end[0] - cycle * 24.0, end[1] - (cycle % 2) * 12.0, end[2]]
            route_dx = end[0] - start[0]
            route_dy = end[1] - start[1]
            route_length = math.hypot(route_dx, route_dy) or 1.0
            route_staggers = [-120.0, 90.0, 210.0]
            route_stagger = route_staggers[cycle % len(route_staggers)]
            start = [start[0] + route_dx / route_length * route_stagger, start[1] + route_dy / route_length * route_stagger, start[2]]
            end = [end[0] + route_dx / route_length * route_stagger, end[1] + route_dy / route_length * route_stagger, end[2]]
        if spec["scene_id"].startswith("citypark_promenade"):
            cycle = index // len(paths)
            route_dx = end[0] - start[0]
            route_dy = end[1] - start[1]
            route_length = math.hypot(route_dx, route_dy) or 1.0
            route_staggers = [-270.0, -90.0, 90.0, 270.0]
            route_stagger = route_staggers[cycle % len(route_staggers)]
            start = [start[0] + route_dx / route_length * route_stagger, start[1] + route_dy / route_length * route_stagger, start[2]]
            end = [end[0] + route_dx / route_length * route_stagger, end[1] + route_dy / route_length * route_stagger, end[2]]
        if spec["scene_id"].startswith("art_gallery"):
            cycle = index // len(paths)
            route_dx = end[0] - start[0]
            route_dy = end[1] - start[1]
            route_length = math.hypot(route_dx, route_dy) or 1.0
            route_staggers = [-480.0, -160.0, 220.0, 540.0]
            side_offsets = [-150.0, -50.0, 70.0, 180.0]
            route_stagger = route_staggers[cycle % len(route_staggers)]
            side_offset = side_offsets[cycle % len(side_offsets)]
            normal_x = -route_dy / route_length
            normal_y = route_dx / route_length
            start = [
                start[0] + route_dx / route_length * route_stagger + normal_x * side_offset,
                start[1] + route_dy / route_length * route_stagger + normal_y * side_offset,
                start[2],
            ]
            end = [
                end[0] + route_dx / route_length * route_stagger + normal_x * side_offset,
                end[1] + route_dy / route_length * route_stagger + normal_y * side_offset,
                end[2],
            ]
        if animation_bindings:
            binding = animation_bindings[index]
            mesh = binding["mesh_path"]
            anim = binding["animation_path"]
            motion = str(binding.get("motion", motion))
            source = str(binding.get("source", source))
            animation_phase_offset_frames = int(binding.get("animation_phase_offset_frames", animation_phase_offset_frames))
            binding_explicit_route = bool(binding.get("explicit_route"))
            binding_uses_world_translation = _uses_world_translation(binding, anim)
            if binding_uses_world_translation:
                if spec["scene_id"] == "scene19":
                    start, end = _scene19_visible_walk_route(spec, index)
                elif spec["scene_id"] == "scene24":
                    start, end = _scene24_visible_walk_route(spec, index)
                    waypoints = [list(start), list(end)]
            else:
                end = start
            if "start_location" in binding:
                start = [float(value) for value in binding["start_location"]]
            if "end_location" in binding and binding_uses_world_translation:
                end = [float(value) for value in binding["end_location"]]
            elif "start_location" in binding:
                end = list(start)
            if "waypoints" in binding and binding_uses_world_translation:
                waypoints = [[float(value) for value in point] for point in binding["waypoints"]]
        else:
            if index % 7 == 0:
                anim = MAN_ANIMS[4]
                end = start
                motion = "sitting"
            elif index % 6 == 0:
                anim = MAN_ANIMS[5]
                motion = "running"
            elif index % 5 == 0:
                anim = MAN_ANIMS[3]
                end = start
                motion = "phone_idle"
            elif index % 4 == 0:
                anim = WOMAN_ANIMS[index % len(WOMAN_ANIMS)]
                motion = "walking"
            else:
                anim = MAN_ANIMS[index % 3]
                motion = "walking"
            is_woman = anim in WOMAN_ANIMS
            mesh = (WOMAN_MESHES if is_woman else MAN_MESHES)[index % (len(WOMAN_MESHES) if is_woman else len(MAN_MESHES))]
            if _uses_world_translation(None, anim) and spec["scene_id"] == "scene19":
                start, end = _scene19_visible_walk_route(spec, index)
            elif _uses_world_translation(None, anim) and spec["scene_id"] == "scene24":
                start, end = _scene24_visible_walk_route(spec, index)
                waypoints = [list(start), list(end)]
        if spec["scene_id"].startswith("museum_gallery") and source not in {"fab_aria_blake_game_ready", FREE_CASUAL_GIRL_SOURCE}:
            candidate_offsets = [
                (0.0, 0.0),
                (0.0, 96.0),
                (0.0, -96.0),
                (96.0, 0.0),
                (-96.0, 0.0),
                (96.0, 96.0),
                (96.0, -96.0),
                (-96.0, 96.0),
                (-96.0, -96.0),
                (0.0, 160.0),
                (0.0, -160.0),
                (160.0, 0.0),
                (-160.0, 0.0),
                (140.0, 120.0),
                (140.0, -120.0),
                (-140.0, 120.0),
                (-140.0, -120.0),
            ]
            for offset_x, offset_y in candidate_offsets:
                candidate_start = [start[0] + offset_x, start[1] + offset_y, start[2]]
                candidate_end = [end[0] + offset_x, end[1] + offset_y, end[2]]
                if not (-4325.0 <= candidate_start[0] <= -1425.0 and -890.0 <= candidate_start[1] <= 145.0):
                    continue
                if not (-4325.0 <= candidate_end[0] <= -1425.0 and -890.0 <= candidate_end[1] <= 145.0):
                    continue
                has_spacing = True
                for other in people:
                    if other.get("source") in {"fab_free_casual_girl_modular_part", "existing_metahuman_skeletal_mesh"}:
                        continue
                    for t in [0.0, 0.5, 1.0]:
                        candidate_x = candidate_start[0] + (candidate_end[0] - candidate_start[0]) * t
                        candidate_y = candidate_start[1] + (candidate_end[1] - candidate_start[1]) * t
                        other_start = other["start"]
                        other_end = other["end"]
                        other_x = other_start[0] + (other_end[0] - other_start[0]) * t
                        other_y = other_start[1] + (other_end[1] - other_start[1]) * t
                        if math.hypot(candidate_x - other_x, candidate_y - other_y) < 110.0:
                            has_spacing = False
                            break
                    if not has_spacing:
                        break
                if has_spacing:
                    start = candidate_start
                    end = candidate_end
                    break
        if _slow_pedestrian_routes_requested():
            start, end = _clamp_cinematic_route(start, end)
            if waypoints:
                waypoints = [list(start), list(end)]
        if spec["scene_id"] not in {"scene19", "scene24"}:
            if not binding_explicit_route:
                start, end = _avoid_existing_root_people(start, end, people, spec["scene_id"])
            if waypoints and _is_downtown_west_scene(spec["scene_id"]):
                waypoints = _downtown_west_route_waypoints(start, end, index, spec["scene_id"]) or [list(start), list(end)]
            if waypoints and _slow_pedestrian_routes_requested():
                waypoints = [list(start), list(end)]
            if _slow_pedestrian_routes_requested():
                start, end = _clamp_cinematic_route(start, end)
                if waypoints:
                    waypoints = [list(start), list(end)]
        if _xy_distance(start, end) >= 250.0 and _animation_loop_reset_risk(anim):
            replacement = _stable_moving_character_binding(spec["scene_id"], stable_moving_replacement_count)
            if replacement is None:
                anim, motion = _stationary_animation_for_motion(source, motion)
                end = list(start)
                waypoints = None
            else:
                mesh, anim, source = replacement
                if "walk" in str(motion).lower():
                    motion = f"{motion}_safe{stable_moving_replacement_count:02d}"
                stable_moving_replacement_count += 1
        rotation = _movement_rotation(start, end)
        if start == end:
            rotation = [0.0, rotation[1] + (index % 4) * 28.0, 0.0]
        person = {
            "name": f"CineU_{spec['scene_id']}_skeletal_{index:02d}",
            "type": "skeletal",
            "mesh": mesh,
            "animation": anim,
            "start": start,
            "end": end,
            "rotation": rotation,
            "scale": 1.0,
            "motion": motion,
            "source": source,
            "animation_phase_offset_frames": animation_phase_offset_frames,
            "swap_root_bone": "none",
            "force_root_lock": (
                source == "fab_scanned_3d_people_pack"
                or _xy_distance(start, end) > 1.0
                or bool(waypoints and any(_xy_distance(left, right) > 1.0 for left, right in zip(waypoints, waypoints[1:])))
            ),
        }
        if animation_bindings and "modular_variant" in binding and source in UNVALIDATED_MODULAR_CHARACTER_SOURCES:
            person["modular_variant"] = int(binding["modular_variant"])
        if waypoints:
            person["waypoints"] = waypoints
        person["animation_play_rate"] = _pedestrian_animation_play_rate(person)
        people.append(person)
    static_points = spec["static_points"]
    readyposed = crowd.get("readyposed_static_meshes")
    readyposed = readyposed if readyposed is not None else []
    sitting_static_points = crowd.get("sitting_static_points") or []
    static_count = len(readyposed) if "readyposed_static_meshes" in crowd else (10 if spec["scene_id"] == "scene19" else 8)
    for index in range(static_count):
        if spec.get("explicit_static_points"):
            motion = readyposed[index].get("motion", "standing") if readyposed else "standing"
            if "sit" in str(motion) and sitting_static_points:
                loc = list(sitting_static_points[index % len(sitting_static_points)])
            else:
                loc = list(static_points[index % len(static_points)])
            loc[0] += ((index // len(static_points)) % 2) * 180.0
            loc[1] += ((index % 2) - 0.5) * 34.0
        else:
            zone_start, zone_end = static_points
            t = (index + 0.5) / static_count
            loc = _lerp(zone_start, zone_end, t)
            loc[1] += ((index % 3) - 1) * 140.0
        if spec["scene_id"] not in {"scene19", "scene24"}:
            loc, _static_end = _avoid_existing_root_people(loc, loc, people, spec["scene_id"])
        rotation = [0.0, -120.0 + (index * 41.0) % 240.0, 0.0]
        people.append(
            {
                "name": f"CineU_{spec['scene_id']}_readyposed_{index:02d}",
                "type": "static",
                "mesh": readyposed[index]["mesh_path"] if readyposed else STATIC_PEOPLE[index % len(STATIC_PEOPLE)],
                "start": loc,
                "end": loc,
                "rotation": rotation,
                "scale": 1.0,
                "motion": readyposed[index].get("motion", "standing") if readyposed else "standing",
                "source": readyposed[index].get("source", "existing_twinmotion_readyposed_static_mesh") if readyposed else "existing_twinmotion_readyposed_static_mesh",
            }
        )
    people_by_name = {person["name"]: person for person in people}
    for part in crowd.get("high_detail_modular_parts") or []:
        host = people_by_name.get(str(part.get("host_actor_name")))
        if host is None:
            continue
        part_name = str(part["actor_name"])
        role = str(part.get("role") or part_name.rsplit("_", 1)[-1])
        host.setdefault("modular_parts", []).append(
            {
                "name": part_name,
                "host_actor_name": str(part.get("host_actor_name")),
                "mesh": str(part["mesh_path"]),
                "animation": str(part["animation_path"]),
                "role": role,
                "source": str(part.get("source", "high_detail_modular_part")),
            }
        )
    for part in crowd.get("metahuman_cinematic_parts") or []:
        people.append(
            {
                "name": str(part["actor_name"]),
                "type": "skeletal",
                "mesh": str(part["mesh_path"]),
                "animation": str(part.get("animation_path") or ""),
                "start": [float(value) for value in part["location"]],
                "end": [float(value) for value in part.get("end_location", part["location"])],
                "rotation": [float(value) for value in part.get("rotation", [0.0, 0.0, 0.0])],
                "scale": float(part.get("scale", 1.0)),
                "source": str(part.get("source", "existing_metahuman_skeletal_mesh")),
                "motion": str(part.get("motion", "metahuman")),
            }
        )
    for character in crowd.get("metahuman_blueprint_characters") or []:
        people.append(
            {
                "name": str(character["actor_name"]),
                "type": "blueprint",
                "blueprint": str(character["blueprint_path"]),
                "start": [float(value) for value in character["location"]],
                "end": [float(value) for value in character.get("end_location", character["location"])],
                "rotation": [float(value) for value in character.get("rotation", [0.0, 0.0, 0.0])],
                "scale": float(character.get("scale", 1.0)),
                "source": str(character.get("source", "existing_metahuman_character_blueprint")),
                "motion": str(character.get("motion", "metahuman")),
            }
        )
    for character in blueprint_characters:
        person = {
            "name": str(character["actor_name"]),
            "type": "blueprint",
            "blueprint": str(character["blueprint_path"]),
            "start": [float(value) for value in character["location"]],
            "end": [float(value) for value in character.get("end_location", character["location"])],
            "rotation": [float(value) for value in character.get("rotation", [0.0, 0.0, 0.0])],
            "scale": float(character.get("scale", 1.0)),
            "source": str(character.get("source", "existing_blueprint_character")),
            "motion": str(character.get("motion", "blueprint_character")),
        }
        if character.get("visual_variant") is not None:
            person["modular_variant"] = int(character["visual_variant"])
        people.append(person)
    if spec["scene_id"] in WORLD_TEMPLATE_6_7_SCENE_IDS:
        for person in people:
            points = person.get("waypoints") or [person["start"], person["end"]]
            for start, end in zip(points, points[1:]):
                if not _world_template_6_7_route_on_pedestrian_surface(start, end):
                    raise RuntimeError(f"{person['name']} route violates cafe pedestrian clearance: {start} -> {end}")
    return people


def _build_scene(spec: dict, output_dir: Path) -> dict:
    warnings: list[dict] = []
    generated_level = _make_generated_level(spec["scene_id"], spec["source_level"], warnings)
    _configure_streaming_level_visibility(spec, warnings)
    _disable_existing_post_process_volumes(spec, warnings)
    _disable_existing_lights(spec, warnings)
    sequence_path, seq = _create_sequence(spec["scene_id"], FRAME_COUNT)
    visibility_bindings = _hide_existing_scene_actors(spec, warnings, seq)
    level_visibility_sections = _add_sequence_level_visibility(
        seq,
        spec.get("sequencer_level_visibility") or [],
        FRAME_COUNT,
        warnings,
    )
    light_records = []
    if spec["scene_id"] == "scene19":
        light_records.extend(_spawn_scene19_daylight(warnings) or [])
        light_records.extend(_spawn_scene19_balcony_fill_lights(warnings) or [])
    if spec.get("extra_lights"):
        light_records.extend(_spawn_production_lights(spec, warnings) or [])
    for light_record in light_records:
        _add_static_spawnable_actor(seq, light_record, warnings)

    sequence_state = {
        "source_asset_type": "level_sequence",
        "level_path": generated_level,
        "map_path": generated_level,
        "generated_level_path": generated_level,
        "range": [0, FRAME_COUNT],
        "fps": FPS,
        "asset_fps": FPS,
        "ue_sequence_metadata": {"display_rate": {"numerator": FPS, "denominator": 1}},
        "camera_cuts": spec["cuts"],
        "cameras": {},
        "support_props": {},
        "animation_tracks": {},
        "pedestrian_material_overrides": {},
        "transform_tracks": {},
        "level_visibility_sections": level_visibility_sections,
        "hidden_actor_bindings": visibility_bindings,
    }

    actors = []
    for prop in spec.get("support_props", []):
        _debug_actor_step(f"spawn_support_prop {prop['name']} mesh={prop['mesh']} location={prop['location']}")
        actor = _spawn_static_actor(
            prop["name"],
            prop["mesh"],
            prop["location"],
            prop.get("rotation", [0.0, 0.0, 0.0]),
            prop.get("scale", 1.0),
            material_override=prop.get("material_override"),
            material_profile=prop.get("material_profile"),
            cast_shadow=prop.get("cast_shadow"),
        )
        actor_record = {**prop, "actor": actor}
        _add_static_spawnable_actor(seq, actor_record, warnings)
        keys = _static_actor_transform_keys(actor_record)
        sequence_state["support_props"][prop["name"]] = {
            "actor_name": prop["name"],
            "mesh_path": prop["mesh"],
            "role": prop.get("role", "support"),
            "location": prop["location"],
            "rotation": prop.get("rotation", [0.0, 0.0, 0.0]),
            "scale": prop.get("scale", 1.0),
            "material_override": prop.get("material_override"),
            "cast_shadow": prop.get("cast_shadow"),
        }
        sequence_state["transform_tracks"][prop["name"]] = {"keys": keys}
        actors.append({"name": prop["name"], "type": "support_prop", "role": prop.get("role", "support"), "mesh": prop["mesh"]})

    for person in _crowd_specs(spec):
        asset_ref = person.get("mesh") or person.get("blueprint")
        _debug_actor_step(f"begin {person['name']} type={person['type']} start={person['start']} end={person['end']} asset={asset_ref} anim={person.get('animation')}")
        keys = _person_transform_keys(person)
        if person["type"] == "skeletal":
            _debug_actor_step(f"spawn_skeletal {person['name']}")
            try:
                mesh_asset = _resolve_skeletal_person_assets(person, warnings)
                actor = _spawn_skeletal_actor(person["name"], person["mesh"], person["start"], person["rotation"], person["scale"], mesh_asset=mesh_asset)
            except RuntimeError as exc:
                warnings.append({"actor": person["name"], "reason": "pedestrian_actor_skipped", "asset": asset_ref, "error": str(exc)})
                continue
            component = actor.get_component_by_class(unreal.SkeletalMeshComponent)
            material_overrides = _apply_pedestrian_slot_material_fallback(component, mesh_asset, person, warnings)
            if material_overrides:
                sequence_state["pedestrian_material_overrides"][person["name"]] = {
                    "actor_name": person["name"],
                    "source": person.get("source", ""),
                    "mesh_path": person.get("mesh", ""),
                    "slots": material_overrides,
                }
            for part in person.get("modular_parts") or []:
                _add_modular_skeletal_component(
                    actor,
                    {
                        "actor_name": part["name"],
                        "host_actor_name": person["name"],
                        "mesh_path": part["mesh"],
                    },
                    warnings,
                )
            _debug_actor_step(f"add_transform {person['name']}")
            binding = _add_actor_transform(seq, actor, person["name"], keys, warnings)
            if person.get("animation"):
                _debug_actor_step(f"add_animation {person['name']}")
                animation_record = _add_skeletal_animation(
                    binding,
                    person["animation"],
                    0,
                    FRAME_COUNT,
                    warnings,
                    phase_offset_frames=person.get("animation_phase_offset_frames", 0),
                    swap_root_bone_mode=person.get("swap_root_bone", "none"),
                    force_root_lock=bool(person.get("force_root_lock", False)),
                    playback_rate=float(person.get("animation_play_rate", 1.0)),
                    mesh_asset=mesh_asset,
                    actor_name=person["name"],
                )
                _debug_actor_step(f"done_animation {person['name']}")
                if animation_record is not None:
                    sequence_state["animation_tracks"][person["name"]] = {
                        "actor_name": person["name"],
                        **animation_record,
                        "start_frame": _skeletal_animation_section_start_frame(0),
                        "end_frame": FRAME_COUNT,
                        "phase_offset_frames": int(person.get("animation_phase_offset_frames", 0)),
                        "swap_root_bone": str(person.get("swap_root_bone", "none")),
                        "force_root_lock": bool(person.get("force_root_lock", False)),
                        "mesh_path": str(person.get("mesh", "")),
                        "playback_rate": float(person.get("animation_play_rate", 1.0)),
                    }
            else:
                warnings.append({"actor": person["name"], "reason": "skeletal_animation_omitted", "source": person.get("source", "")})
        elif person["type"] == "blueprint":
            _debug_actor_step(f"spawn_blueprint {person['name']}")
            try:
                actor = _spawn_blueprint_actor(person["name"], person["blueprint"], person["start"], person["rotation"], person["scale"])
            except RuntimeError as exc:
                warnings.append({"actor": person["name"], "reason": "pedestrian_actor_skipped", "asset": asset_ref, "error": str(exc)})
                continue
            _debug_actor_step(f"add_transform {person['name']}")
            _add_actor_transform(seq, actor, person["name"], keys, warnings)
            _debug_actor_step(f"done_blueprint {person['name']}")
        else:
            _debug_actor_step(f"spawn_static {person['name']}")
            try:
                actor = _spawn_static_actor(person["name"], person["mesh"], person["start"], person["rotation"], person["scale"])
            except RuntimeError as exc:
                warnings.append({"actor": person["name"], "reason": "pedestrian_actor_skipped", "asset": asset_ref, "error": str(exc)})
                continue
            _debug_actor_step(f"add_transform {person['name']}")
            _add_actor_transform(seq, actor, person["name"], keys, warnings)
            _debug_actor_step(f"done_static {person['name']}")
        sequence_state["transform_tracks"][person["name"]] = {"keys": keys}
        actor_record = {"name": person["name"], "type": person["type"], "motion": person.get("motion")}
        if person.get("source"):
            actor_record["source"] = person["source"]
        if person["type"] == "blueprint":
            actor_record["blueprint"] = person["blueprint"]
        else:
            actor_record["mesh"] = person["mesh"]
            actor_record["animation"] = person.get("animation")
            if person.get("modular_parts"):
                actor_record["modular_parts"] = [
                    {
                        "name": part["name"],
                        "mesh": part["mesh"],
                        "animation": part.get("animation"),
                        "source": part.get("source"),
                    }
                    for part in person["modular_parts"]
                ]
        actors.append(actor_record)

    camera_bindings = {}
    expected_camera_post_process = {}
    for camera_spec in spec["cameras"]:
        camera = _spawn_camera(
            camera_spec["name"],
            camera_spec["keys"],
            camera_spec["focal"],
            camera_spec.get("exposure_bias"),
            camera_spec.get("exposure_brightness"),
            camera_spec.get("motion_blur_amount"),
            camera_spec.get("local_exposure"),
        )
        if camera_spec.get("local_exposure"):
            expected_camera_post_process[camera_spec["name"]] = {
                "profile": camera_spec["local_exposure"],
                "properties": _camera_post_process_snapshot(camera, camera_spec["local_exposure"]),
            }
        binding = _add_camera(seq, camera, camera_spec["name"], camera_spec["keys"], warnings)
        focal_keys = _camera_focal_length_keys(camera_spec)
        if _has_animated_focal_length(focal_keys):
            _add_camera_focal_length_track(seq, binding, camera, focal_keys, 0, FRAME_COUNT, warnings)
        camera_bindings[camera_spec["name"]] = binding
        sequence_state["cameras"][camera_spec["name"]] = {
            "transform_keys": camera_spec["keys"],
            "focal_length_keys": focal_keys,
            "type": camera_spec.get("type"),
            "monitor_view": camera_spec.get("monitor_view"),
            "cinematic_role": camera_spec.get("cinematic_role"),
            "exposure_bias": camera_spec.get("exposure_bias"),
            "exposure_brightness": camera_spec.get("exposure_brightness"),
            "local_exposure": camera_spec.get("local_exposure"),
            "motion_blur_amount": camera_spec.get("motion_blur_amount"),
        }
    _add_camera_cuts(seq, spec["cuts"], camera_bindings, warnings)

    sequence_saved = bool(unreal.EditorAssetLibrary.save_asset(sequence_path))
    reloaded_sequence = _try_load_asset(sequence_path) if sequence_saved else None
    if reloaded_sequence is None:
        transform_sequence_audit = {
            "passed": False,
            "expected_binding_count": len(sequence_state["transform_tracks"]),
            "audited_binding_count": 0,
            "issue_count": 1,
            "issues": [
                {
                    "reason": "saved_sequence_reload_failed",
                    "sequence_path": sequence_path,
                    "save_succeeded": sequence_saved,
                }
            ],
            "binding_audits": [],
        }
    else:
        transform_sequence_audit = _audit_sequence_transform_tracks(
            reloaded_sequence,
            sequence_state["transform_tracks"],
        )
    transform_sequence_audit["reload_mode"] = "in_process_asset_lookup"
    transform_sequence_audit["cold_reload_verified"] = False
    sequence_state["transform_channel_audit"] = transform_sequence_audit
    if not transform_sequence_audit["passed"]:
        warnings.append(
            {
                "reason": "transform_sequence_audit_failed",
                "sequence_path": sequence_path,
                "audit": transform_sequence_audit,
            }
        )

    default_mrq_spatial_samples, default_mrq_temporal_samples = _default_mrq_sample_counts()
    mrq_spatial_samples = _env_int_or_default("CINEU_HILLSIDE_SPATIAL_SAMPLES", default_mrq_spatial_samples)
    mrq_temporal_samples = _env_int_or_default("CINEU_HILLSIDE_TEMPORAL_SAMPLES", default_mrq_temporal_samples)
    capture_start_frame, capture_end_frame = _capture_frame_range()
    production_quality_gate = _production_quality_gate(
        mrq_spatial_samples,
        mrq_temporal_samples,
        warnings=warnings,
        capture_frame_count=capture_end_frame - capture_start_frame,
    )
    sample_quality_ok = (
        (not production_quality_gate["production_mode"])
        or (
            mrq_spatial_samples >= production_quality_gate["min_required_spatial_samples"]
            and mrq_temporal_samples >= production_quality_gate["min_required_temporal_samples"]
        )
    )
    production_quality_gate["sample_quality_passed"] = sample_quality_ok
    if production_quality_gate["production_mode"] and not sample_quality_ok:
        warnings.append(
            {
                "reason": "production_mrq_sample_quality_below_film_target",
                "mrq_spatial_samples": mrq_spatial_samples,
                "mrq_temporal_samples": mrq_temporal_samples,
                "min_required_spatial_samples": production_quality_gate["min_required_spatial_samples"],
                "min_required_temporal_samples": production_quality_gate["min_required_temporal_samples"],
            }
        )
    _enforce_production_quality_gate(production_quality_gate)

    _wait_for_render_asset_readiness(warnings)
    warnings.append({"reason": "base_level_not_saved", "level": generated_level, "note": "CineU actors are stored as sequence spawnables so MRQ can reload the existing base level without losing generated subjects."})

    state = {
        "schema_version": "cineu.world_state.v1",
        "level": generated_level,
        "environment_asset": {"type": "level", "source": "existing_level", "ue_path": generated_level},
        "sequences": {sequence_path: sequence_state},
        "actors": {item["name"]: item for item in actors},
        "warnings": warnings,
    }
    _mkdir(output_dir)
    state_path = output_dir / "world_state_for_render.json"
    _write_text(state_path, json.dumps(state, indent=2))
    summary_base = {
        "scene_id": spec["scene_id"],
        "description": spec["description"],
        "mode": MODE,
        "camera_filter": CAMERA_FILTER or None,
        "source_level": spec["source_level"],
        "generated_level": generated_level,
        "sequence_path": sequence_path,
        "output_dir": str(output_dir),
        "world_state_path": str(state_path),
        "frame_count": FRAME_COUNT,
        "capture_frame_range": [capture_start_frame, capture_end_frame],
        "fps": FPS,
        "resolution": [WIDTH, HEIGHT],
        "actor_count": len(actors),
        "skeletal_actor_count": len([actor for actor in actors if actor["type"] == "skeletal"]),
        "blueprint_actor_count": len([actor for actor in actors if actor["type"] == "blueprint"]),
        "static_actor_count": len([actor for actor in actors if actor["type"] == "static"]),
        "support_prop_count": len([actor for actor in actors if actor["type"] == "support_prop"]),
        "camera_count": len(spec["cameras"]),
        "camera_cuts": spec["cuts"],
        "scene_capture_source": spec.get("scene_capture_source"),
        "asset_ready_wait_sec": ASSET_READY_WAIT_SEC,
        "production_quality_gate": production_quality_gate,
        "warnings": warnings,
    }
    scene_capture_source = str(spec.get("scene_capture_source") or "").strip()
    if scene_capture_source and not os.environ.get("CINEU_SCENE_CAPTURE_SOURCE"):
        os.environ["CINEU_SCENE_CAPTURE_SOURCE"] = scene_capture_source
    render_inputs = {
        "sequence_path": sequence_path,
        "output_dir": str(output_dir),
        "world_state_path": str(state_path),
        "resolution": [WIDTH, HEIGHT],
        "format": "mp4",
        "quality": RENDER_QUALITY,
        "fps": FPS,
        "start_frame": capture_start_frame,
        "end_frame": capture_end_frame,
        "render_backend": RENDER_BACKEND,
        "capture_timeout_sec": int(os.environ.get("CINEU_HILLSIDE_CAPTURE_TIMEOUT", "900") or "900"),
        "warm_up_frame_count": int(os.environ.get("CINEU_HILLSIDE_WARMUP", "8") or "8"),
        "mrq_spatial_samples": mrq_spatial_samples,
        "mrq_temporal_samples": mrq_temporal_samples,
        "mrq_low_memory": os.environ.get("CINEU_MRQ_LOW_MEMORY", ""),
        "mrq_cvars": os.environ.get("CINEU_MRQ_CVARS", ""),
        "completion_summary_path": str(output_dir / "build_render_summary.json"),
        "latest_summary_path": str(SUMMARY_PATH),
        "completion_summary_base": summary_base,
    }
    prepared_render_path = output_dir / "prepared_render.json"
    prepared_render = {
        "schema_version": "cineu.prepared_render.v1",
        "execution_phase": "build",
        "writer_process_id": os.getpid(),
        "written_at": datetime.now().isoformat(timespec="seconds"),
        "build_script_sha256": _file_sha256(Path(__file__).resolve()),
        "sequence_path": sequence_path,
        "expected_transform_tracks": sequence_state["transform_tracks"],
        "expected_animation_tracks": sequence_state["animation_tracks"],
        "expected_camera_post_process": expected_camera_post_process,
        "expected_hidden_actor_bindings": visibility_bindings,
        "render_inputs": render_inputs,
    }
    _write_text(prepared_render_path, json.dumps(prepared_render, indent=2))
    if EXECUTION_PHASE == "build":
        return {
            **summary_base,
            "execution_phase": EXECUTION_PHASE,
            "prepared_render_path": str(prepared_render_path),
            "render_result": {
                "prepared": True,
                "capture_success": False,
                "capture_pending": True,
            },
        }
    render_result = render_preview(render_inputs)
    return {
        **summary_base,
        "execution_phase": EXECUTION_PHASE,
        "prepared_render_path": str(prepared_render_path),
        "render_result": render_result,
    }


def _audit_prepared_sequence_and_render(output_dir: Path) -> dict:
    prepared_render_path = output_dir / "prepared_render.json"
    if not prepared_render_path.is_file():
        raise RuntimeError(f"Prepared render manifest is missing: {prepared_render_path}")
    prepared_render = _read_json(prepared_render_path)
    if prepared_render.get("schema_version") != "cineu.prepared_render.v1":
        raise RuntimeError(f"Unsupported prepared render schema: {prepared_render.get('schema_version')!r}")

    sequence_path = str(prepared_render.get("sequence_path") or "")
    expected_transform_tracks = prepared_render.get("expected_transform_tracks")
    expected_animation_tracks = prepared_render.get("expected_animation_tracks")
    render_inputs = prepared_render.get("render_inputs")
    if (
        not sequence_path
        or not isinstance(expected_transform_tracks, dict)
        or not isinstance(expected_animation_tracks, dict)
        or not isinstance(render_inputs, dict)
    ):
        raise RuntimeError(f"Prepared render manifest is incomplete: {prepared_render_path}")

    writer_process_id = int(prepared_render.get("writer_process_id") or 0)
    auditor_process_id = os.getpid()
    written_script_sha256 = str(prepared_render.get("build_script_sha256") or "")
    audited_script_sha256 = _file_sha256(Path(__file__).resolve())
    reloaded_sequence = _try_load_asset(sequence_path)
    if reloaded_sequence is None:
        transform_sequence_audit = {
            "passed": False,
            "expected_binding_count": len(expected_transform_tracks),
            "audited_binding_count": 0,
            "issue_count": 1,
            "issues": [
                {
                    "reason": "cold_saved_sequence_reload_failed",
                    "sequence_path": sequence_path,
                }
            ],
            "binding_audits": [],
        }
        animation_sequence_audit = {
            "passed": False,
            "expected_binding_count": len(expected_animation_tracks),
            "audited_binding_count": 0,
            "issue_count": 1,
            "issues": [
                {
                    "reason": "cold_saved_sequence_reload_failed",
                    "sequence_path": sequence_path,
                }
            ],
            "binding_audits": [],
        }
    else:
        transform_sequence_audit = _audit_sequence_transform_tracks(
            reloaded_sequence,
            expected_transform_tracks,
        )
        animation_sequence_audit = _audit_sequence_animation_tracks(
            reloaded_sequence,
            expected_animation_tracks,
        )

    transform_track_passed = bool(transform_sequence_audit.get("passed"))
    animation_track_passed = bool(animation_sequence_audit.get("passed"))
    visual_state_audit = _audit_sequence_visual_state(
        reloaded_sequence,
        prepared_render.get("expected_camera_post_process") or {},
        prepared_render.get("expected_hidden_actor_bindings") or [],
    )
    sequence_audit_passed = transform_track_passed and animation_track_passed and visual_state_audit["passed"]
    cold_reload_verified = _production_cold_reload_verified(
        writer_process_id,
        auditor_process_id,
        sequence_audit_passed,
        written_script_sha256,
        audited_script_sha256,
    )
    transform_sequence_audit.update(
        {
            "passed": sequence_audit_passed,
            "transform_track_passed": transform_track_passed,
            "animation_track_passed": animation_track_passed,
            "animation_track_audit": animation_sequence_audit,
            "visual_state_audit": visual_state_audit,
            "issue_count": int(transform_sequence_audit.get("issue_count", 0))
            + int(animation_sequence_audit.get("issue_count", 0))
            + len(visual_state_audit["issues"]),
            "reload_mode": "separate_unreal_editor_process",
            "cold_reload_verified": cold_reload_verified,
            "writer_process_id": writer_process_id,
            "auditor_process_id": auditor_process_id,
            "separate_process_verified": writer_process_id != auditor_process_id,
            "written_at": prepared_render.get("written_at"),
            "audited_at": datetime.now().isoformat(timespec="seconds"),
            "build_script_sha256": written_script_sha256,
            "audited_build_script_sha256": audited_script_sha256,
            "code_hashes_match": written_script_sha256 == audited_script_sha256,
            "sequence_path": sequence_path,
        }
    )
    cold_audit_path = output_dir / "cold_sequence_audit.json"
    _write_text(cold_audit_path, json.dumps(transform_sequence_audit, indent=2))
    if not cold_reload_verified:
        raise RuntimeError(
            "Production Sequence cold reload audit failed before render: "
            f"{cold_audit_path}"
        )

    world_state_path = Path(str(render_inputs.get("world_state_path") or ""))
    world_state = _read_json(world_state_path)
    sequence_state = (world_state.get("sequences") or {}).get(sequence_path)
    if not isinstance(sequence_state, dict):
        raise RuntimeError(f"Sequence state is missing from world state: {sequence_path}")
    sequence_state["transform_channel_audit"] = transform_sequence_audit
    sequence_state["animation_track_audit"] = animation_sequence_audit
    animation_audits_by_actor = {
        audit["actor"]: audit
        for audit in animation_sequence_audit.get("binding_audits", [])
    }
    for actor_name, animation_record in (sequence_state.get("animation_tracks") or {}).items():
        animation_audit = animation_audits_by_actor.get(actor_name) or {}
        animation_record["persistent_in_place_verified"] = bool(
            animation_audit.get("persistent_in_place_verified")
        )
    _write_text(world_state_path, json.dumps(world_state, indent=2))

    summary_base = render_inputs.get("completion_summary_base")
    if not isinstance(summary_base, dict):
        raise RuntimeError("Prepared render completion summary is missing")
    summary_base["execution_phase"] = EXECUTION_PHASE
    summary_base["production_sequence_cold_audit"] = transform_sequence_audit
    summary_base["cold_sequence_audit_path"] = str(cold_audit_path)
    quality_gate = _production_quality_gate(
        int(render_inputs.get("mrq_spatial_samples", 1)),
        int(render_inputs.get("mrq_temporal_samples", 1)),
        warnings=summary_base.get("warnings") or [],
        capture_frame_count=int(render_inputs.get("end_frame", FRAME_COUNT)) - int(render_inputs.get("start_frame", 0)),
        production_mode=bool((summary_base.get("production_quality_gate") or {}).get("production_mode"))
        or _production_quality_mode_requested(str(summary_base.get("mode", MODE)), str(summary_base.get("camera_filter", CAMERA_FILTER))),
        fps=int(render_inputs.get("fps", FPS)),
    )
    summary_base["build_process_quality_gate"] = summary_base.get("production_quality_gate")
    summary_base["production_quality_gate"] = quality_gate
    _write_text(output_dir / "render_process_quality_gate.json", json.dumps(quality_gate, indent=2))
    _enforce_production_quality_gate(quality_gate)
    render_inputs["completion_summary_base"] = summary_base
    render_result = render_preview(render_inputs)
    return {
        **summary_base,
        "prepared_render_path": str(prepared_render_path),
        "render_result": render_result,
    }


def main() -> None:
    if SCENE_ID not in SCENES:
        raise RuntimeError(f"Unknown scene id: {SCENE_ID}")
    if EXECUTION_PHASE not in {"build_and_render", "build", "audit_render"}:
        raise RuntimeError(f"Unknown CINEU_HILLSIDE_EXECUTION_PHASE: {EXECUTION_PHASE!r}")
    if EXECUTION_PHASE == "build_and_render" and _production_quality_mode_requested(MODE, CAMERA_FILTER):
        raise RuntimeError(
            "Production rendering requires two UnrealEditor processes: "
            "CINEU_HILLSIDE_EXECUTION_PHASE=build followed by audit_render"
        )
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_output = DIAG_ROOT / "renders" / f"{SCENE_ID}_{MODE}_{stamp}"
    output_dir = Path(os.environ.get("CINEU_HILLSIDE_OUTPUT_DIR", str(default_output)))
    if EXECUTION_PHASE == "audit_render":
        summary = _audit_prepared_sequence_and_render(output_dir)
    else:
        summary = _build_scene(SCENES[SCENE_ID](), output_dir)
    _mkdir(SUMMARY_PATH.parent)
    _write_text(SUMMARY_PATH, json.dumps(summary, indent=2))
    _write_text(output_dir / "build_render_summary.json", json.dumps(summary, indent=2))
    print(f"CINEU_HILLSIDE_BUILD_RENDER_SUMMARY={output_dir / 'build_render_summary.json'}")


if __name__ == "__main__":
    main()
