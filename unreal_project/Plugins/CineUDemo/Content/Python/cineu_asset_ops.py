from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

try:
    import unreal  # type: ignore
except Exception:  # pragma: no cover
    unreal = None


def load_asset_checked(asset_path: str) -> Any:
    if unreal is None:
        raise RuntimeError("This module must be executed inside Unreal Editor Python.")
    asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    if asset is None:
        raise RuntimeError(f"Cannot load asset: {asset_path}")
    return asset


def asset_exists(asset_path: str) -> bool:
    if unreal is None:
        return False
    return bool(unreal.EditorAssetLibrary.does_asset_exist(asset_path))


def _imported_paths_from_task(task: Any) -> list[str]:
    for attr in ("imported_object_paths",):
        try:
            paths = getattr(task, attr)
            if paths:
                return [str(path) for path in paths]
        except Exception:
            pass
        try:
            paths = task.get_editor_property(attr)
            if paths:
                return [str(path) for path in paths]
        except Exception:
            pass
    return []


def _asset_class_name(asset_path: str) -> str:
    if unreal is None or not asset_path:
        return ""
    try:
        asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    except Exception:
        asset = None
    if asset is None:
        return ""
    try:
        return str(asset.get_class().get_name())
    except Exception:
        return ""


def _expected_class_names(asset: dict[str, Any]) -> list[str]:
    asset_type = str(asset.get("type") or asset.get("asset_type") or "").lower()
    if asset_type == "skeletal_mesh":
        return ["SkeletalMesh"]
    if asset_type == "static_mesh":
        return ["StaticMesh"]
    if asset_type in {"animation", "anim_sequence"}:
        return ["AnimSequence"]
    if asset_type == "level_sequence":
        return ["LevelSequence"]
    if asset_type == "material":
        return ["Material", "MaterialInstanceConstant"]
    if asset_type == "texture":
        return ["Texture2D"]
    return []


def _matches_expected_class(asset_path: str, asset: dict[str, Any]) -> bool:
    expected = _expected_class_names(asset)
    if not expected:
        return True
    class_name = _asset_class_name(asset_path)
    return any(class_name == item or item.lower() in class_name.lower() for item in expected)


def _select_primary_imported_path(imported_paths: list[str], asset: dict[str, Any]) -> str | None:
    if not imported_paths:
        return None
    for path in imported_paths:
        if _matches_expected_class(path, asset):
            return path
    return imported_paths[0]


def _imported_animation_paths(imported_paths: list[str]) -> list[str]:
    return [path for path in imported_paths if _asset_class_name(path) == "AnimSequence"]


def _scan_package_asset_paths(package_path: str) -> list[str]:
    if unreal is None:
        return []
    registry_helpers = getattr(unreal, "AssetRegistryHelpers", None)
    if registry_helpers is None:
        return []
    try:
        registry = registry_helpers.get_asset_registry()
        registry.scan_paths_synchronous([package_path], True)
        asset_data = registry.get_assets_by_path(package_path, True)
    except Exception:
        return []
    paths: list[str] = []
    for data in asset_data:
        asset = None
        try:
            asset = data.get_asset()
        except Exception:
            asset = None
        if asset is not None:
            try:
                paths.append(str(asset.get_path_name()))
                continue
            except Exception:
                pass
        for attr in ("object_path",):
            try:
                value = getattr(data, attr)
                if value:
                    paths.append(str(value))
                    break
            except Exception:
                pass
            try:
                value = data.get_editor_property(attr)
                if value:
                    paths.append(str(value))
                    break
            except Exception:
                pass
    return [path for path in paths if path]


def _existing_imported_path_for_asset(asset: dict[str, Any], destination_path: str) -> str | None:
    ue_path = str(asset.get("ue_path") or "")
    if ue_path and asset_exists(ue_path) and _matches_expected_class(ue_path, asset):
        return ue_path
    for path in _scan_package_asset_paths(destination_path):
        if _matches_expected_class(path, asset):
            return path
    return None


def _scan_asset_path(package_path: str) -> None:
    registry_helpers = getattr(unreal, "AssetRegistryHelpers", None)
    if registry_helpers is None:
        return
    try:
        registry = registry_helpers.get_asset_registry()
        registry.scan_paths_synchronous([package_path], True)
    except Exception:
        pass


def _copy_content_tree(content_root: Path, project_content: Path, rel_root: Path, package_path: str) -> bool:
    source = content_root / rel_root
    if not source.exists() or not source.is_dir():
        return False
    shutil.copytree(source, project_content / rel_root, dirs_exist_ok=True)
    _scan_asset_path(package_path)
    return True


def _twinmotion_tree_dependency_roots(content_root: Path, bundle_root: Path) -> list[tuple[Path, str]]:
    try:
        rel_parts = tuple(part.lower() for part in bundle_root.resolve().relative_to(content_root.resolve()).parts)
    except ValueError:
        return []
    if rel_parts[:4] != ("externalassets", "twinmotion", "vegetation", "trees"):
        return []
    return [
        (Path("ExternalAssets") / "Twinmotion" / "Vegetation" / "_common", "/Game/ExternalAssets/Twinmotion/Vegetation/_common"),
        (Path("ExternalAssets") / "Twinmotion" / "_common" / "MasterMaterials", "/Game/ExternalAssets/Twinmotion/_common/MasterMaterials"),
    ]


def _copy_unreal_project_content_bundle(asset: dict[str, Any], source_path: Path, record: dict[str, Any], warnings: list[dict[str, Any]]) -> None:
    provenance = asset.get("provenance") if isinstance(asset.get("provenance"), dict) else {}
    ue_path = str(asset.get("ue_path") or "")
    content_root = Path(str(provenance.get("ue_content_root") or source_path.parents[2]))
    bundle_root = Path(str(provenance.get("bundle_root") or source_path.parent))
    package_path = str(provenance.get("bundle_package_path") or asset.get("import_destination") or "/Game")
    project_content = Path(str(unreal.Paths.project_content_dir()))
    try:
        rel_bundle = bundle_root.resolve().relative_to(content_root.resolve())
    except ValueError:
        rel_bundle = Path(bundle_root.name)
    destination_bundle = project_content / rel_bundle
    try:
        if rel_bundle == Path("."):
            destination_bundle.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination_bundle / source_path.name)
        else:
            shutil.copytree(bundle_root, destination_bundle, dirs_exist_ok=True)
        _scan_asset_path(package_path)
        copied_dependencies = []
        for rel_dependency, dependency_package_path in _twinmotion_tree_dependency_roots(content_root, bundle_root):
            if _copy_content_tree(content_root, project_content, rel_dependency, dependency_package_path):
                copied_dependencies.append(dependency_package_path)
        if copied_dependencies:
            record["copied_dependency_package_paths"] = copied_dependencies
        record["imported_object_paths"] = [ue_path] if ue_path else []
        record["status"] = "imported" if (not ue_path or asset_exists(ue_path)) else "import_failed"
        if record["status"] == "import_failed":
            warnings.append({"asset_id": record.get("asset_id"), "reason": "uasset_copy_not_registered", "ue_path": ue_path})
    except Exception as exc:  # noqa: BLE001
        record["status"] = "import_failed"
        record["error"] = {"type": type(exc).__name__, "message": str(exc)}
        warnings.append({"asset_id": record.get("asset_id"), "reason": "uasset_copy_failed", "error": record["error"]})


def import_assets(assets: list[dict[str, Any]]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for asset in assets:
        asset_id = str(asset.get("asset_id") or "")
        ue_path = str(asset.get("ue_path") or "")
        import_required = bool(asset.get("import_required"))
        record: dict[str, Any] = {
            "asset_id": asset_id,
            "source_path": asset.get("source_path"),
            "source_type": asset.get("source_type"),
            "import_required": import_required,
            "import_destination": asset.get("import_destination"),
            "ue_path": ue_path,
            "imported_object_paths": [],
            "status": "pending",
        }
        if not import_required:
            record["status"] = "available"
            record["imported_object_paths"] = [ue_path] if ue_path else []
            records.append(record)
            continue
        source_path = Path(str(asset.get("source_path") or ""))
        if not source_path.exists():
            record["status"] = "missing_source"
            warnings.append({"asset_id": asset_id, "reason": "missing_source", "source_path": str(source_path)})
            records.append(record)
            continue
        if unreal is None:
            record["status"] = "unreal_unavailable"
            warnings.append({"asset_id": asset_id, "reason": "unreal_unavailable"})
            records.append(record)
            continue
        if source_path.suffix.lower() == ".uasset" or str(asset.get("source_type")) == "ue_project_content":
            _copy_unreal_project_content_bundle(asset, source_path, record, warnings)
            records.append(record)
            continue
        destination_path = str(asset.get("import_destination") or "/Game/CineU/Imported")
        destination_name = Path(ue_path).name if ue_path else source_path.stem
        existing_path = _existing_imported_path_for_asset(asset, destination_path)
        if existing_path:
            package_paths = _scan_package_asset_paths(destination_path)
            imported_paths = [existing_path] + [path for path in package_paths if path != existing_path]
            record["status"] = "already_exists"
            record["ue_path"] = existing_path
            record["imported_object_paths"] = imported_paths
            record["imported_animation_paths"] = _imported_animation_paths(imported_paths)
            records.append(record)
            continue
        try:
            task = unreal.AssetImportTask()
            task.set_editor_property("filename", str(source_path))
            task.set_editor_property("destination_path", destination_path)
            task.set_editor_property("destination_name", destination_name)
            task.set_editor_property("automated", True)
            task.set_editor_property("save", True)
            task.set_editor_property("replace_existing", False)
            unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
            imported_paths = _imported_paths_from_task(task)
            primary_path = _select_primary_imported_path(imported_paths, asset)
            if not primary_path and ue_path and asset_exists(ue_path) and _matches_expected_class(ue_path, asset):
                primary_path = ue_path
                imported_paths = [ue_path]
            if primary_path and imported_paths and primary_path in imported_paths:
                imported_paths = [primary_path] + [path for path in imported_paths if path != primary_path]
            record["imported_object_paths"] = imported_paths
            record["imported_animation_paths"] = _imported_animation_paths(imported_paths)
            record["ue_path"] = primary_path or ue_path
            record["status"] = "imported" if imported_paths else "import_failed"
            try:
                unreal.EditorAssetLibrary.save_directory(destination_path, only_if_is_dirty=False, recursive=True)
            except Exception:
                pass
        except Exception as exc:  # noqa: BLE001
            record["status"] = "import_failed"
            record["error"] = {"type": type(exc).__name__, "message": str(exc)}
            warnings.append({"asset_id": asset_id, "reason": "import_failed", "error": record["error"]})
        records.append(record)
    return {"assets": records, "imported_assets": [record["asset_id"] for record in records if record.get("status") in {"imported", "already_exists", "available"}], "warnings": warnings}
