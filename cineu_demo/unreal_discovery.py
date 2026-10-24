from __future__ import annotations

from pathlib import Path
from typing import Iterable


DEFAULT_SEARCH_ROOTS = (
    Path("D:/"),
    Path("C:/Program Files/Epic Games"),
    Path("C:/Program Files (x86)/Epic Games"),
)


def _candidate_paths(root: Path) -> list[Path]:
    direct = [
        root / "UE_5.5" / "Engine" / "Binaries" / "Win64" / "UnrealEditor-Cmd.exe",
        root / "UE_5.6" / "Engine" / "Binaries" / "Win64" / "UnrealEditor-Cmd.exe",
    ]
    if root.name.startswith("UE_"):
        direct.insert(0, root / "Engine" / "Binaries" / "Win64" / "UnrealEditor-Cmd.exe")
    return direct


def discover_unreal_editor_cmd(search_roots: Iterable[Path] | None = None) -> str | None:
    roots = [Path(p) for p in (search_roots or DEFAULT_SEARCH_ROOTS)]
    seen: set[Path] = set()
    for root in roots:
        for candidate in _candidate_paths(root):
            normalized = candidate.resolve() if candidate.exists() else candidate
            if normalized in seen:
                continue
            seen.add(normalized)
            if candidate.exists():
                return str(candidate)
    return None
