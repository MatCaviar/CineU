from __future__ import annotations

import json
import os
from pathlib import Path

import unreal


OUTPUT_PATH = Path(os.environ.get("CINEU_DIAGNOSTIC_ROOT", str(Path(__file__).resolve().parents[2] / "workspace/diagnostics/hillside_scene19_scene24"))) / "character_skeletons.json"

MESH_PATHS = [
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/AdrianCity/SK_AdrianCity",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/AlexCity/SK_AlexCity",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/AmirCity/SK_AmirCity",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/DorianCity/SK_DorianCity",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/IsabelCity/SK_IsabelCity",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/SanaaCity/SK_SanaaCity",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_reworked/AsmaCity/SK_AsmaCity",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_reworked/IsabelCity/SK_IsabelCity",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_reworked/LouisPrice/SK_LouisPrice",
]

ANIM_PATHS = [
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_common/animations/man/AN_man_walking01",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_common/animations/man/AN_man_walking02",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_common/animations/man/AN_man_walk_phoning01",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_common/animations/man/AN_man_idle_phoning01",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_common/animations/man/AN_man_idle_sitting01",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_common/animations/man/AN_man_sport_running01",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_common/animations/womanheels/AN_womanheels_walking01",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_common/animations/womanheels/AN_womanheels_walking02",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_common/animations/womanheels/AN_womanheels_idle01",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_common/animations/womanheels/AN_womanheels_idle_phoning01",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_reworked/Animations/A_Male_Walk_01",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_reworked/Animations/A_Male_Walk_02",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_reworked/Animations/A_Male_Walk_Fast",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_reworked/Animations/A_FemaleHeels_Walk_Generic",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_reworked/Animations/A_FemaleHeels_Walk_Phone",
    "/Game/ExternalAssets/Twinmotion/Characters/rigged/_reworked/Animations/A_FemaleHeels_Idle",
]


def _object_path(obj) -> str | None:
    if obj is None:
        return None
    try:
        return str(obj.get_path_name()).split(".", 1)[0]
    except Exception:
        return str(obj)


def _load(path: str):
    return unreal.EditorAssetLibrary.load_asset(path)


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    meshes = []
    for path in MESH_PATHS:
        mesh = _load(path)
        skeleton = None
        if mesh is not None:
            try:
                skeleton = mesh.get_editor_property("skeleton")
            except Exception:
                skeleton = None
        meshes.append({"path": path, "loaded": mesh is not None, "skeleton": _object_path(skeleton)})
    animations = []
    for path in ANIM_PATHS:
        anim = _load(path)
        skeleton = None
        length = None
        if anim is not None:
            try:
                skeleton = anim.get_editor_property("skeleton")
            except Exception:
                skeleton = None
            for prop in ["sequence_length", "play_length"]:
                try:
                    value = anim.get_editor_property(prop)
                    if value:
                        length = float(value)
                        break
                except Exception:
                    pass
        animations.append({"path": path, "loaded": anim is not None, "skeleton": _object_path(skeleton), "length_seconds": length})
    OUTPUT_PATH.write_text(json.dumps({"meshes": meshes, "animations": animations}, indent=2), encoding="utf-8")
    print(f"CINEU_HILLSIDE_CHARACTER_SKELETONS={OUTPUT_PATH}")


if __name__ == "__main__":
    main()
