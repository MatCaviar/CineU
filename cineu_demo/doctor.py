from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from .paths import DEFAULT_KNOWLEDGE_DIR, DEFAULT_UNREAL_PROJECT, DEFAULT_WORKSPACE
from .template_store import TemplateStore


def _jsonl_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def doctor(workspace: Path = DEFAULT_WORKSPACE, knowledge_dir: Path = DEFAULT_KNOWLEDGE_DIR, unreal_project: Path = DEFAULT_UNREAL_PROJECT) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: Any = None) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    workspace = Path(workspace)
    knowledge_dir = Path(knowledge_dir)
    unreal_project = Path(unreal_project)
    add("python_version>=3.11", sys.version_info >= (3, 11), sys.version)
    add("workspace_exists", workspace.exists(), str(workspace))
    add("projects_dir_exists", (workspace / "projects").exists(), str(workspace / "projects"))
    add("runs_dir_exists", (workspace / "runs").exists(), str(workspace / "runs"))
    asset_path = workspace / "projects" / "demo_project" / "asset_cache" / "assets.jsonl"
    asset_count = _jsonl_count(asset_path)
    add("demo_asset_cache_exists", asset_path.exists(), str(asset_path))
    add("demo_asset_count>=4", asset_count >= 4, asset_count)
    try:
        store = TemplateStore(knowledge_dir / "templates")
        add("template_store_loadable", True, len(store.templates))
        add("runtime_template_count>=10", len(store.templates) >= 10, len(store.templates))
        required = [
            "asset.import_many.v1",
            "env.setup.v1",
            "entity.spawn_many.v1",
            "spatial.apply_transforms.v1",
            "sequence.init.v1",
            "transform.add_tracks.v1",
            "camera.dolly_in.v1",
            "camera.wide_aerial.v1",
            "camera.hitchcock_zoom.v1",
            "animation.add_tracks.v1",
            "sequence.camera_cut.v1",
            "render.preview.v1",
        ]
        missing = [x for x in required if x not in store.templates]
        add("required_runtime_templates_present", not missing, missing)
    except Exception as exc:  # pragma: no cover
        add("template_store_loadable", False, repr(exc))
    add("unreal_project_scaffold_exists", unreal_project.exists(), str(unreal_project))
    wrappers_dir = unreal_project.parent / "Plugins" / "CineUDemo" / "Content" / "Python"
    add("unreal_python_wrappers_exist", wrappers_dir.exists(), str(wrappers_dir))
    return {"schema_version": "cineu.doctor.v3", "passed": all(c["passed"] for c in checks), "checks": checks}
