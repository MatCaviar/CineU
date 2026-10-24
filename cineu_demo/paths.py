from __future__ import annotations

import os
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent
DEFAULT_WORKSPACE = REPO_ROOT / "workspace"
DEFAULT_KNOWLEDGE_DIR = REPO_ROOT / "knowledge"
DEFAULT_UNREAL_PROJECT = REPO_ROOT / "unreal_project" / "CineU_Demo.uproject"
HILLSIDE_PROJECT_ROOT = Path(os.environ.get("CINEU_HILLSIDE_PROJECT", str(REPO_ROOT.parent / "HillsideProject")))
HILLSIDE_DIAGNOSTIC_ROOT = Path(os.environ.get("CINEU_DIAGNOSTIC_ROOT", str(DEFAULT_WORKSPACE / "diagnostics" / "hillside_scene19_scene24")))


def project_dir(workspace: Path, project_id: str) -> Path:
    return Path(workspace) / "projects" / project_id


def asset_cache_path(workspace: Path, project_id: str) -> Path:
    return project_dir(workspace, project_id) / "asset_cache" / "assets.jsonl"
