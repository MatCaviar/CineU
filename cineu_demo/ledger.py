from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def atomic_write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)


def atomic_write_json(path: Path, data: Any, *, indent: int = 2) -> None:
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=indent, sort_keys=False))


def read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    enriched = {"ts": utc_now_iso(), **record}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(enriched, ensure_ascii=False, sort_keys=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


class FileLedger:
    """Run-centric local ledger.

    The ledger is deliberately append-friendly. status.json is a mutable summary;
    events.jsonl and snapshots are the canonical record.
    """

    def __init__(self, workspace: Path, run_id: str):
        self.workspace = Path(workspace)
        self.run_id = run_id
        self.run_dir = self.workspace / "runs" / run_id
        self.events_path = self.run_dir / "traces" / "events.jsonl"
        self.status_path = self.run_dir / "status.json"
        self.ensure_layout()

    def ensure_layout(self) -> None:
        for rel in [
            "planning",
            "operations",
            "scripts",
            "traces",
            "snapshots",
            "verification",
            "reflection",
            "artifacts",
        ]:
            ensure_dir(self.run_dir / rel)

    def write_json(self, rel: str, data: Any) -> Path:
        path = self.run_dir / rel
        atomic_write_json(path, data)
        return path

    def write_text(self, rel: str, text: str) -> Path:
        path = self.run_dir / rel
        atomic_write_text(path, text)
        return path

    def append_event(self, event: str, **payload: Any) -> None:
        append_jsonl(self.events_path, {"event": event, **payload})

    def append_verification(self, stage: str, report: dict[str, Any]) -> None:
        append_jsonl(self.run_dir / "verification" / f"{stage}.jsonl", report)

    def update_status(self, **fields: Any) -> None:
        current = read_json(self.status_path, default={})
        current.update(fields)
        current["updated_at"] = utc_now_iso()
        atomic_write_json(self.status_path, current)

    def save_snapshot(self, name: str, state: dict[str, Any]) -> Path:
        return self.write_json(f"snapshots/{name}.json", state)


def make_run_id(prefix: str = "run") -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    return f"{prefix}_{stamp}"
