from __future__ import annotations

import json
import os
from pathlib import Path

import unreal


OUTPUT_PATH = Path(os.environ.get("CINEU_DIAGNOSTIC_ROOT", str(Path(__file__).resolve().parents[2] / "workspace/diagnostics/hillside_scene19_scene24"))) / "asset_inventory.json"


def _asset_data_to_record(asset_data):
    package_name = str(asset_data.package_name)
    asset_name = str(asset_data.asset_name)
    asset_class = str(asset_data.asset_class_path.asset_name)
    return {
        "package_name": package_name,
        "asset_name": asset_name,
        "asset_class": asset_class,
        "object_path": f"{package_name}.{asset_name}",
    }


def _query_assets(prefix: str, class_names: set[str], limit: int = 200) -> list[dict]:
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    records: list[dict] = []
    for asset_data in registry.get_assets_by_path(prefix, recursive=True):
        record = _asset_data_to_record(asset_data)
        if record["asset_class"] in class_names:
            records.append(record)
    records.sort(key=lambda item: item["package_name"])
    return records[:limit]


def _has_unreal_attr(name: str) -> bool:
    return hasattr(unreal, name)


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "project": unreal.Paths.get_project_file_path(),
        "unreal_classes": {
            name: _has_unreal_attr(name)
            for name in [
                "LevelSequence",
                "LevelSequenceFactoryNew",
                "MovieSceneCameraCutTrack",
                "MovieSceneSkeletalAnimationTrack",
                "MovieScene3DTransformTrack",
                "MoviePipelineQueueSubsystem",
                "MoviePipelinePIEExecutor",
                "MoviePipelineOutputSetting",
                "CineCameraActor",
                "SkeletalMeshActor",
            ]
        },
        "maps": _query_assets("/Game/Hillside/Maps", {"World"}, limit=300),
        "cinematics": _query_assets("/Game/Cinematics", {"LevelSequence", "MoviePipelineMasterConfig"}, limit=100),
        "rigged_blueprints": _query_assets(
            "/Game/ExternalAssets/Twinmotion/Characters/rigged",
            {"Blueprint"},
            limit=80,
        ),
        "rigged_skeletal_meshes": _query_assets(
            "/Game/ExternalAssets/Twinmotion/Characters/rigged",
            {"SkeletalMesh"},
            limit=120,
        ),
        "rigged_animations": _query_assets(
            "/Game/ExternalAssets/Twinmotion/Characters/rigged",
            {"AnimSequence"},
            limit=200,
        ),
        "readyposed_static_meshes": _query_assets(
            "/Game/ExternalAssets/Twinmotion/Characters/readyposed/Meshes",
            {"StaticMesh"},
            limit=120,
        ),
    }
    OUTPUT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"CINEU_HILLSIDE_CAPABILITIES={OUTPUT_PATH}")


if __name__ == "__main__":
    main()
