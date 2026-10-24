from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_state(path: str | None) -> dict[str, Any]:
    if not path:
        return {"schema_version": "cineu.world_state.v1", "level": None, "support_surfaces": {}, "actors": {}, "sequences": {}, "renders": [], "warnings": []}
    p = Path(path)
    if not p.exists():
        return {"schema_version": "cineu.world_state.v1", "level": None, "support_surfaces": {}, "actors": {}, "sequences": {}, "renders": [], "warnings": []}
    return json.loads(p.read_text(encoding="utf-8"))


def save_state(path: str | None, state: dict[str, Any]) -> None:
    if not path:
        return
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)
