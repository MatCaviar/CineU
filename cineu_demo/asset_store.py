from __future__ import annotations

import json
import os
import re
import shutil
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable

from .schemas import AssetMetadata


IMPORTABLE_EXTENSIONS = {".fbx", ".obj", ".glb", ".gltf", ".abc", ".usd", ".usdz"}
DISCOVERABLE_EXTENSIONS = IMPORTABLE_EXTENSIONS | {".uasset", ".umap"}


def _tokens(text: str) -> set[str]:
    normalized = re.sub(r"[_\\/\-]+", " ", text)
    normalized = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", normalized)
    normalized = re.sub(r"(?<=[A-Za-z])(?=[0-9])", " ", normalized)
    normalized = re.sub(r"(?<=[0-9])(?=[A-Za-z])", " ", normalized)
    return {t.lower() for t in re.findall(r"[a-zA-Z0-9\u4e00-\u9fff]+", normalized)}


def _safe_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_").lower()
    return safe or "asset"


class AssetStore:
    def __init__(
        self,
        assets_jsonl: Path,
        source_dirs: Iterable[Path] | None = None,
        allow_downloads: bool | None = None,
        include_global_libraries: bool | None = None,
    ):
        self.assets_jsonl = Path(assets_jsonl)
        self.include_global_libraries = (
            self._env_flag("CINEU_ENABLE_GLOBAL_ASSET_SCAN") if include_global_libraries is None else bool(include_global_libraries)
        )
        self.source_dirs = [Path(p) for p in source_dirs] if source_dirs is not None else self._default_source_dirs()
        self.allow_downloads = self._env_flag("CINEU_ENABLE_ASSET_DOWNLOADS") if allow_downloads is None else bool(allow_downloads)
        self.assets: list[AssetMetadata] = []
        self.reload()

    def reload(self) -> None:
        self.assets = []
        if self.assets_jsonl.exists():
            for line in self.assets_jsonl.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                self.assets.append(AssetMetadata.model_validate(json.loads(line)))
        self.assets.extend(self._discover_catalog_assets())
        self.assets.extend(self._discover_source_assets())

    def list_assets(self) -> list[AssetMetadata]:
        return list(self.assets)

    def get(self, asset_id: str) -> AssetMetadata | None:
        for a in self.assets:
            if a.asset_id == asset_id:
                return a
        return None

    def retrieve(
        self,
        query: str,
        *,
        required_type: str = "any",
        required_tags: Iterable[str] | None = None,
        ue_version: str = "5.5",
    ) -> AssetMetadata:
        matches = self.search(query, required_type=required_type, required_tags=required_tags, ue_version=ue_version)
        if not matches:
            raise LookupError(f"No asset candidate for query={query!r}, required_type={required_type!r}")
        best_record = matches[0]
        if float(best_record["score"]) <= 0:
            raise LookupError(f"No positive-score asset candidate for query={query!r}")
        return self._materialize_if_needed(best_record["asset"])

    def materialize(self, asset: AssetMetadata) -> AssetMetadata:
        return self._materialize_if_needed(asset)

    def is_reusable_primary_asset(self, asset: AssetMetadata) -> bool:
        if self._is_placeholder(asset):
            return False
        if asset.import_required:
            return bool(asset.source_path and Path(asset.source_path).exists())
        if asset.source_path:
            return Path(asset.source_path).exists()
        return bool(asset.ue_path and asset.source_type not in {"metadata_placeholder", "generated_proxy"})

    def search(
        self,
        query: str,
        *,
        required_type: str = "any",
        required_tags: Iterable[str] | None = None,
        ue_version: str = "5.5",
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        required_tags = [t.lower() for t in (required_tags or [])]
        scored: list[dict[str, Any]] = []
        q_tokens = _tokens(query)
        for asset in self.assets:
            if required_type == "any" and asset.type in {"material", "other"}:
                continue
            if required_type != "any" and asset.type != required_type:
                continue
            tags = [*asset.semantic_tags, *asset.functional_tags, asset.name, asset.asset_id]
            tag_tokens = set()
            for tag in tags:
                tag_tokens |= _tokens(tag)
            keyword = len(q_tokens & tag_tokens) / max(1, len(q_tokens))
            lowered_tags = [x.lower() for x in tags]
            if required_tags and any(t not in lowered_tags for t in required_tags):
                continue
            exact = sum(1 for t in required_tags if t in lowered_tags) / max(1, len(required_tags) or 1)
            type_match = 1.0 if required_type == "any" or asset.type == required_type else 0.0
            compat = 1.0 if ue_version in asset.ue_versions else 0.0
            license_ok = 1.0 if asset.license.get("research_allowed", True) else 0.0
            source_quality = self._source_quality(asset)
            placeholder_penalty = 0.25 if self._is_placeholder(asset) else 0.0
            score = 0.35 * keyword + 0.25 * exact + 0.15 * type_match + 0.10 * compat + 0.05 * license_ok + 0.40 * source_quality - placeholder_penalty
            # Strong fallback if semantic tags directly contain query words.
            if any(query.lower() in str(tag).lower() for tag in tags):
                score += 0.25
            scored.append(
                {
                    "score": score,
                    "asset": asset,
                    "breakdown": {
                        "keyword": keyword,
                        "exact_tags": exact,
                        "type": type_match,
                        "compat": compat,
                        "source_quality": source_quality,
                        "license_ok": license_ok,
                        "placeholder_penalty": placeholder_penalty,
                    },
                }
            )
        scored.sort(key=lambda x: float(x["score"]), reverse=True)
        return scored[:limit] if limit is not None else scored

    def fallback_static_mesh(self) -> AssetMetadata:
        for asset in self.assets:
            if asset.type == "static_mesh" and ("fallback" in asset.functional_tags or "primitive" in asset.semantic_tags):
                return asset
        for asset in self.assets:
            if asset.type == "static_mesh":
                return asset
        raise LookupError("No fallback static mesh asset found")

    def _default_source_dirs(self) -> list[Path]:
        roots = [
            self.assets_jsonl.parent / "sources",
            self.assets_jsonl.parent / "fab",
            self.assets_jsonl.parent / "public",
        ]
        roots.extend(self._nearby_unreal_resource_roots())
        roots.extend(self._epic_asset_library_roots())
        extra = os.environ.get("CINEU_ASSET_SOURCE_DIRS", "")
        for item in extra.split(";"):
            item = item.strip()
            if item:
                roots.append(Path(item))
        deduped: list[Path] = []
        seen: set[str] = set()
        for root in roots:
            key = str(root.resolve()) if root.exists() else str(root)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(root)
        return deduped

    def _nearby_unreal_resource_roots(self) -> list[Path]:
        roots: list[Path] = []
        for parent in self.assets_jsonl.resolve().parents:
            candidates = [
                parent / "RealTimeCompositing" / "UEOL_505_Resources",
                parent / "CityParkEnv55" / "Content",
                parent / "Fab",
                parent / "Marketplace",
                parent / "PublicAssets",
            ]
            for candidate in candidates:
                if candidate.exists() and candidate.is_dir():
                    roots.append(candidate)
            roots.extend(self._unreal_project_content_roots(parent))
        return roots

    def _unreal_project_content_roots(self, parent: Path) -> list[Path]:
        roots: list[Path] = []
        if (parent / "Content").is_dir() and any(parent.glob("*.uproject")):
            roots.append(parent / "Content")
        try:
            children = list(parent.iterdir())
        except OSError:
            return roots
        for child in children:
            content = child / "Content"
            if child.is_dir() and content.is_dir() and any(child.glob("*.uproject")):
                    roots.append(content)
        return roots

    def _epic_asset_library_roots(self) -> list[Path]:
        candidates: list[Path] = []
        extra = os.environ.get("CINEU_EPIC_VAULT_DIRS", "")
        candidates.extend(Path(item.strip()) for item in extra.split(";") if item.strip())
        if not candidates and not self.include_global_libraries:
            return []

        program_data = Path(os.environ.get("ProgramData", r"C:\ProgramData"))
        public_home = Path(os.environ.get("PUBLIC", r"C:\Users\Public"))
        user_home = Path.home()
        candidates.extend(
            [
                program_data / "Epic" / "EpicGamesLauncher" / "VaultCache",
                program_data / "Epic" / "UnrealEngineLauncher" / "VaultCache",
                public_home / "Documents" / "Epic Games" / "VaultCache",
                user_home / "Documents" / "Epic Games" / "VaultCache",
                user_home / "Documents" / "FabLibrary",
            ]
        )

        roots: list[Path] = []
        for candidate in candidates:
            if candidate.exists() and candidate.is_dir():
                roots.extend(self._content_roots_under(candidate))
        return roots

    def _content_roots_under(self, root: Path, max_depth: int = 5) -> list[Path]:
        roots: list[Path] = []
        stack: list[tuple[Path, int]] = [(root, 0)]
        seen: set[str] = set()
        while stack:
            current, depth = stack.pop()
            try:
                resolved = str(current.resolve())
            except OSError:
                continue
            if resolved in seen:
                continue
            seen.add(resolved)
            if current.name.lower() == "content":
                roots.append(current)
                continue
            if depth >= max_depth:
                continue
            try:
                children = list(current.iterdir())
            except OSError:
                continue
            for child in children:
                if child.is_dir():
                    stack.append((child, depth + 1))
        return roots

    def _discover_source_assets(self) -> list[AssetMetadata]:
        discovered: list[AssetMetadata] = []
        seen_sources = {asset.source_path for asset in self.assets if asset.source_path}
        seen_asset_ids = {asset.asset_id for asset in self.assets}
        for root in self.source_dirs:
            if not root.exists():
                continue
            for path in sorted(root.rglob("*")):
                if not path.is_file() or path.suffix.lower() not in DISCOVERABLE_EXTENSIONS:
                    continue
                resolved = str(path.resolve())
                if resolved in seen_sources:
                    continue
                asset = self._metadata_for_source_file(root, path)
                if asset.asset_id in seen_asset_ids:
                    asset = self._with_source_unique_asset_id(asset, root, seen_asset_ids)
                discovered.append(asset)
                seen_sources.add(resolved)
                seen_asset_ids.add(asset.asset_id)
        return discovered

    def _with_source_unique_asset_id(
        self,
        asset: AssetMetadata,
        source_root: Path,
        seen_asset_ids: set[str],
    ) -> AssetMetadata:
        source_label = source_root.parent.name if source_root.name.lower() == "content" else source_root.name
        base = f"{asset.asset_id}__{_safe_name(source_label)}"
        candidate = base
        suffix = 2
        while candidate in seen_asset_ids:
            candidate = f"{base}_{suffix}"
            suffix += 1
        return asset.model_copy(update={"asset_id": candidate})

    def _discover_catalog_assets(self) -> list[AssetMetadata]:
        discovered: list[AssetMetadata] = []
        seen_asset_ids = {asset.asset_id for asset in self.assets}
        catalog_names = {
            "cineu_assets.json",
            "cineu_assets.jsonl",
            "public_assets.json",
            "public_assets.jsonl",
            "fab_assets.json",
            "fab_assets.jsonl",
            "asset_catalog.json",
            "asset_catalog.jsonl",
        }
        for root in self.source_dirs:
            if not root.exists():
                continue
            for catalog in sorted(root.rglob("*")):
                if not catalog.is_file():
                    continue
                if catalog.resolve() == self.assets_jsonl.resolve():
                    continue
                if catalog.name not in catalog_names and not catalog.name.endswith(".cineu_catalog.json"):
                    continue
                for raw in self._read_catalog_records(catalog):
                    record = self._normalize_catalog_record(root, catalog, raw)
                    if record.asset_id in seen_asset_ids:
                        continue
                    discovered.append(record)
                    seen_asset_ids.add(record.asset_id)
        return discovered

    def _read_catalog_records(self, catalog: Path) -> list[dict[str, Any]]:
        if catalog.suffix.lower() == ".jsonl":
            return [json.loads(line) for line in catalog.read_text(encoding="utf-8").splitlines() if line.strip()]
        data = json.loads(catalog.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("assets", [])
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]

    def _normalize_catalog_record(self, root: Path, catalog: Path, raw: dict[str, Any]) -> AssetMetadata:
        source_type = str(raw.get("source_type") or self._source_type_for_path(root, catalog))
        provenance = raw.get("provenance") if isinstance(raw.get("provenance"), dict) else {}
        base = {
            **raw,
            "source_type": source_type,
            "provenance": {
                "catalog": provenance.get("catalog") or self._catalog_for_source_type(source_type),
                "catalog_path": str(catalog.resolve()),
                "source_root": str(root.resolve()),
                "discovered_by": provenance.get("discovered_by") or "asset_catalog_scan",
                **provenance,
            },
        }
        if not base.get("import_destination"):
            base["import_destination"] = f"/Game/CineU/Imported/{source_type}"
        return AssetMetadata.model_validate(base)

    def _metadata_for_source_file(self, root: Path, path: Path) -> AssetMetadata:
        if path.suffix.lower() in {".uasset", ".umap"}:
            content_root = self._content_root_for_path(path)
            if content_root is not None:
                source_type = self._source_type_for_path(root, path)
                if source_type == "local_file":
                    source_type = "ue_project_content"
                return self._metadata_for_unreal_project_content_asset(content_root, path, source_root=root, source_type=source_type)
        source_type = self._source_type_for_path(root, path)
        stem = _safe_name(path.stem)
        import_destination = f"/Game/CineU/Imported/{source_type}"
        semantic_tags = sorted(_tokens(" ".join(path.relative_to(root).parts)) | set(self._inferred_semantic_tags(path)))
        base: dict[str, Any] = {
            "schema_version": "cineu.asset.v1",
            "asset_id": f"asset_{source_type}_{stem}",
            "name": path.stem.replace("_", " ").replace("-", " ").title(),
            "ue_path": f"{import_destination}/{stem}",
            "type": self._infer_type(path),
            "semantic_tags": semantic_tags,
            "functional_tags": [],
            "bounds_cm": {"extent": [50.0, 50.0, 50.0]},
            "has_collision": True,
            "ue_versions": ["5.5"],
            "license": {"source": source_type, "research_allowed": True, "commercial_allowed": False},
            "source_path": str(path.resolve()),
            "source_type": source_type,
            "import_required": True,
            "import_destination": import_destination,
            "imported_object_paths": [],
            "provenance": {
                "catalog": self._catalog_for_source_type(source_type),
                "source_root": str(root.resolve()),
                "discovered_by": "local_file_scan",
                "file_format": path.suffix.lower().lstrip("."),
            },
        }
        sidecar = self._load_sidecar(path)
        for key, value in sidecar.items():
            if key == "provenance" and isinstance(value, dict):
                base["provenance"] = {**base["provenance"], **value}
            else:
                base[key] = value
        if not base.get("import_destination"):
            base["import_destination"] = import_destination
        if not base.get("ue_path"):
            base["ue_path"] = f"{base['import_destination']}/{stem}"
        return AssetMetadata.model_validate(base)

    def _content_root_for_path(self, path: Path) -> Path | None:
        for candidate in [path.parent, *path.parents]:
            if candidate.name.lower() == "content":
                return candidate
        return None

    def _current_project_content_root(self) -> Path | None:
        try:
            parents = self.assets_jsonl.resolve().parents
        except OSError:
            parents = self.assets_jsonl.parents
        for parent in parents:
            candidate = parent / "unreal_project" / "Content"
            if candidate.is_dir() and any(candidate.parent.glob("*.uproject")):
                try:
                    return candidate.resolve()
                except OSError:
                    return candidate
        return None

    def _is_current_project_content_root(self, root: Path) -> bool:
        current = self._current_project_content_root()
        if current is None:
            return False
        try:
            return root.resolve() == current.resolve()
        except OSError:
            return root == current

    def _metadata_for_unreal_project_content_asset(
        self,
        root: Path,
        path: Path,
        *,
        source_root: Path | None = None,
        source_type: str = "ue_project_content",
    ) -> AssetMetadata:
        rel = path.relative_to(root).with_suffix("")
        rel_posix = rel.as_posix()
        stem = _safe_name(rel_posix)
        bundle_root = self._unreal_content_bundle_root(root, path)
        bundle_package_path = self._game_package_path(bundle_root.relative_to(root))
        asset_type = self._infer_type(path)
        tag_set = _tokens(" ".join(rel.parts)) | set(self._inferred_semantic_tags(rel))
        tag_set.update(self._inferred_sibling_tags(path))
        if asset_type == "level_sequence":
            tag_set.update({"sequence", "sequencer", "cinematic"})
        tags = sorted(tag_set)
        source_root = source_root or root
        import_required = not self._is_current_project_content_root(root)
        base: dict[str, Any] = {
            "schema_version": "cineu.asset.v1",
            "asset_id": f"asset_{source_type}_{stem}",
            "name": path.stem.replace("_", " ").replace("-", " ").title(),
            "ue_path": f"/Game/{rel_posix}",
            "type": asset_type,
            "semantic_tags": tags,
            "functional_tags": self._inferred_functional_tags(path),
            "bounds_cm": {"extent": self._inferred_bounds(path, asset_type, tags)},
            "has_collision": True,
            "materials": self._discover_unreal_content_materials(root, bundle_root) if asset_type in {"skeletal_mesh", "static_mesh"} else [],
            "animations": self._discover_unreal_content_animations(root, bundle_root, tags) if asset_type == "skeletal_mesh" else [],
            "ue_versions": ["5.5"],
            "license": {"source": source_type, "research_allowed": True, "commercial_allowed": False},
            "source_path": str(path.resolve()),
            "source_type": source_type,
            "import_required": import_required,
            "import_destination": self._game_package_path(rel.parent),
            "imported_object_paths": [],
            "provenance": {
                "catalog": self._catalog_for_source_type(source_type),
                "source_root": str(source_root.resolve()),
                "ue_content_root": str(root.resolve()),
                "bundle_root": str(bundle_root.resolve()),
                "bundle_package_path": bundle_package_path,
                "discovered_by": "ue_project_content_scan",
                "file_format": path.suffix.lower().lstrip("."),
            },
        }
        return AssetMetadata.model_validate(base)

    def _game_package_path(self, rel: Path) -> str:
        rel_posix = rel.as_posix()
        if rel_posix in {"", "."}:
            return "/Game"
        return f"/Game/{rel_posix}"

    def _unreal_content_bundle_root(self, root: Path, path: Path) -> Path:
        rel_parts = path.relative_to(root).parts
        for marker in ("Maps", "Meshes", "Animations", "Materials", "Textures", "Blueprint"):
            if marker in rel_parts:
                index = rel_parts.index(marker)
                if index > 0:
                    return root.joinpath(*rel_parts[:index])
        return path.parent

    def _discover_unreal_content_animations(self, root: Path, bundle_root: Path, tags: list[str]) -> list[dict[str, Any]]:
        animations_dir = bundle_root / "Animations"
        if not animations_dir.exists():
            return []
        clips = []
        for anim in sorted(animations_dir.glob("*.uasset")):
            lower = anim.stem.lower()
            if not any(token in lower for token in ["gallop", "run", "trot", "walk", "idle"]):
                continue
            rel = anim.relative_to(root).with_suffix("").as_posix()
            if "gallop" in lower or "run" in lower or "trot" in lower:
                name = "run"
                speed = 450
            elif "walk" in lower:
                name = "walk"
                speed = 160
            else:
                name = "idle"
                speed = 0
            clips.append({"name": name, "path": f"/Game/{rel}", "root_motion": lower.endswith("_rm"), "estimated_speed_cm_s": speed})
        priority = {"run": 0, "walk": 1, "idle": 2}
        clips.sort(key=lambda item: (priority.get(str(item["name"]), 99), str(item["path"])))
        return clips

    def _discover_unreal_content_materials(self, root: Path, bundle_root: Path) -> list[str]:
        materials_dir = bundle_root / "Materials"
        if not materials_dir.exists():
            return []
        paths: list[str] = []
        for material in sorted(materials_dir.glob("*.uasset")):
            rel = material.relative_to(root).with_suffix("").as_posix()
            paths.append(f"/Game/{rel}")
        return paths

    def _inferred_sibling_tags(self, path: Path) -> set[str]:
        if path.suffix.lower() != ".uasset" or not path.parent.exists():
            return set()
        try:
            sibling_text = " ".join(item.stem.lower() for item in path.parent.glob("*.uasset"))
        except OSError:
            return set()
        tags: set[str] = set()
        if "leaves" in sibling_text or "leaf" in sibling_text:
            tags.update({"leaf", "leaves", "leafy", "canopy"})
        return tags

    def _inferred_functional_tags(self, path: Path) -> list[str]:
        text = str(path).lower()
        tokens = _tokens(str(path))
        tags: set[str] = set()
        if "showcase" in text:
            tags.add("showcase")
        if tokens & {"anim", "animation", "animations", "animated"}:
            tags.add("animation")
        if any(token in text for token in ["gallop", "run", "trot"]):
            tags.update({"run", "locomotion", "animated"})
        if "walk" in text:
            tags.update({"walk", "locomotion", "animated"})
        if "idle" in text or "idling" in text:
            tags.add("idle")
        if "dance" in text or "dancing" in text:
            tags.update({"dance", "gesture", "animated"})
        return sorted(tags)

    def _inferred_bounds(self, path: Path, asset_type: str, tags: list[str]) -> list[float]:
        tag_set = set(tags)
        if "zebra" in tag_set:
            return [115.0, 35.0, 85.0]
        if asset_type == "skeletal_mesh":
            return [100.0, 35.0, 90.0]
        return [50.0, 50.0, 50.0]

    def _inferred_semantic_tags(self, path: Path) -> list[str]:
        text = str(path).lower()
        tokens = _tokens(str(path))
        tags: set[str] = set()
        if path.suffix.lower() == ".umap":
            tags.update({"level", "map", "environment"})
        if tokens & {"bridge", "path", "road", "tree", "trees", "forest", "grass", "terrain", "landscape", "vegetation", "flora", "foliage", "plant", "plants", "bush", "bushs"}:
            tags.add("environment")
        if tokens & {"tree", "trees"}:
            tags.add("tree")
        if tokens & {"vegetation", "flora"}:
            tags.add("vegetation")
        if "foliage" in tokens:
            tags.add("foliage")
        if tokens & {"leaf", "leaves"}:
            tags.update({"leaf", "leaves", "leafy", "canopy"})
        if "citypark" in text or "cityparkenv" in text:
            tags.update({"city", "park", "environment", "landscape"})
        if "showcase" in text:
            tags.add("showcase")
        if "hillpath" in text:
            tags.update({"hill", "park", "path", "environment", "landscape"})
        if "hillstairs" in text:
            tags.update({"hill", "stairs", "park", "environment", "landscape"})
        if "hillrock" in text:
            tags.update({"hill", "rock", "environment", "landscape"})
        if "mannequin" in text:
            tags.update({"human", "character", "person"})
        if any(token in text for token in ["werewolf", "manny", "quinn"]):
            tags.update({"character", "humanoid"})
        if "werewolf" in text:
            tags.update({"werewolf", "creature"})
        if "africananimalspack" in text:
            tags.update({"animal", "character"})
        if "zebra" in text:
            tags.update({"zebra", "animal", "quadruped"})
        if "hitchcock" in text:
            tags.update({"hitchcock", "zoom", "cinematic"})
        if "sequence" in text or "levelsequence" in text:
            tags.update({"sequence", "sequencer", "cinematic"})
        if tokens & {"anim", "animation", "animations", "animated"}:
            tags.update({"animation", "animated"})
        if "gallop" in text or "run" in text or "trot" in text:
            tags.update({"run", "locomotion", "animated"})
        if "walk" in text:
            tags.update({"walk", "locomotion", "animated"})
        if "idle" in text or "idling" in text:
            tags.update({"idle", "animated"})
        if "dance" in text or "dancing" in text:
            tags.update({"dance", "gesture", "animated"})
        if "camera" in text or re.search(r"\\bcam[_-]", text):
            tags.update({"camera", "trajectory"})
        return sorted(tags)

    def _load_sidecar(self, path: Path) -> dict[str, Any]:
        sidecar = path.with_suffix(".cineu_asset.json")
        if not sidecar.exists():
            return {}
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        allowed = set(AssetMetadata.model_fields)
        return {key: value for key, value in data.items() if key in allowed}

    def _materialize_if_needed(self, asset: AssetMetadata) -> AssetMetadata:
        if asset.source_path and Path(asset.source_path).exists():
            return asset
        if not self.allow_downloads or not asset.import_required:
            return asset
        if not asset.license.get("research_allowed", True):
            return asset
        download_url = str(asset.provenance.get("download_url") or asset.provenance.get("source_url") or "")
        if not download_url:
            return asset
        extension = self._extension_from_download(asset, download_url)
        destination = self.assets_jsonl.parent / "public" / "_downloads" / f"{_safe_name(asset.asset_id)}{extension}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            with urllib.request.urlopen(download_url) as response, destination.open("wb") as output:
                shutil.copyfileobj(response, output)
        updated = asset.model_copy(
            update={
                "source_path": str(destination.resolve()),
                "provenance": {
                    **asset.provenance,
                    "materialized_by": "download_url",
                    "materialized_path": str(destination.resolve()),
                },
            },
            deep=True,
        )
        self._replace_asset(updated)
        return updated

    def _extension_from_download(self, asset: AssetMetadata, download_url: str) -> str:
        parsed = urllib.parse.urlparse(download_url)
        extension = Path(parsed.path).suffix.lower()
        if extension:
            return extension
        file_format = str(asset.provenance.get("file_format") or "").strip(".").lower()
        if file_format:
            return f".{file_format}"
        return ".bin"

    def _replace_asset(self, updated: AssetMetadata) -> None:
        for index, asset in enumerate(self.assets):
            if asset.asset_id == updated.asset_id:
                self.assets[index] = updated
                return
        self.assets.append(updated)

    def _env_flag(self, name: str) -> bool:
        return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}

    def _source_type_for_path(self, root: Path, path: Path) -> str:
        parts = [part.lower() for part in [*root.parts, *path.parts]]
        part_set = set(parts)
        if part_set & {"fab", "fablibrary", "marketplace", "vaultcache", "epicgameslauncher"}:
            return "fab_local"
        if any("vaultcache" in part or "epicgameslauncher" in part for part in parts):
            return "fab_local"
        if part_set & {"public", "publicassets", "polyhaven", "sketchfab", "cc0", "free"}:
            return "public_free"
        if any("polyhaven" in part or "sketchfab" in part for part in parts):
            return "public_free"
        return "local_file"

    def _catalog_for_source_type(self, source_type: str) -> str:
        if source_type == "fab_local":
            return "fab"
        if source_type == "public_free":
            return "public_free"
        return "local"

    def _infer_type(self, path: Path) -> str:
        if path.suffix.lower() == ".umap":
            return "level"
        stem = path.stem.lower()
        parts = {part.lower() for part in path.parts}
        is_unreal_asset = path.suffix.lower() == ".uasset"
        if path.suffix.lower() == ".uasset" and (
            "layerinfo" in stem
            or "foliagetype" in stem
            or stem.endswith("_skeleton")
            or stem.endswith("_physicsasset")
            or stem.startswith(("bp_", "ph_"))
            or parts & {"sound", "sounds", "audio", "blueprints", "blueprint"}
        ):
            return "other"
        if is_unreal_asset and (
            "materials" in parts
            or "mastermaterials" in parts
            or "materialfunctions" in parts
            or stem.startswith(("m_", "mi_", "mf_", "mfattr_"))
            or "material" in stem
        ):
            return "material"
        if is_unreal_asset and ("textures" in parts or stem.startswith("t_") or "texture" in stem):
            return "other"
        tokens = _tokens(str(path))
        if tokens & {"sequence", "sequencer"} or "levelsequence" in stem or "hitchcock" in stem:
            return "level_sequence"
        if tokens & {"camera", "cameras"} or re.search(r"\\bcam[_-]", str(path).lower()):
            return "other"
        if tokens & {"anim", "animation", "animations", "animated", "walk", "walking", "run", "running", "idle", "idling", "dance", "dancing", "clip"}:
            return "animation"
        if stem.startswith("anim_"):
            return "animation"
        if tokens & {"skeletal", "skeleton", "sk"} or stem.startswith("sk_"):
            return "skeletal_mesh"
        if is_unreal_asset and (stem.startswith("sm_") or parts & {"meshes", "mesh", "geometry"}):
            return "static_mesh"
        if is_unreal_asset:
            return "other"
        return "static_mesh"

    def _source_quality(self, asset: AssetMetadata) -> float:
        if self._is_placeholder(asset):
            return 0.0
        source_type = str(asset.source_type or "").lower()
        license_source = str(asset.license.get("source", "")).lower()
        if license_source == "local_starter_source":
            return 0.35
        if source_type == "ue_project_content" and not asset.import_required:
            if asset.type == "level" and ("showcase" in asset.semantic_tags or "showcase" in asset.functional_tags):
                return 1.75
            return 1.6
        if asset.source_path:
            try:
                Path(asset.source_path).resolve().relative_to(self.assets_jsonl.parent.resolve())
                return 1.35 if source_type in {"fab_local", "public_free"} else 1.08
            except (OSError, ValueError):
                pass
        if asset.type == "level" and ("showcase" in asset.semantic_tags or "showcase" in asset.functional_tags):
            return 1.2
        if asset.source_path or asset.import_required or source_type in {"fab_local", "public_free", "local_file", "ue_project_content"}:
            return 1.0
        return 0.65 if asset.ue_path else 0.0

    def _is_placeholder(self, asset: AssetMetadata) -> bool:
        source_type = str(asset.source_type or "").lower()
        license_source = str(asset.license.get("source", "")).lower()
        return source_type in {"metadata_placeholder", "generated_proxy"} or "placeholder" in license_source
