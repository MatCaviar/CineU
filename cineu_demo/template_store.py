from __future__ import annotations

from pathlib import Path
from typing import Iterable

import yaml

from .schemas import TemplateManifest


class TemplateStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.templates: dict[str, TemplateManifest] = {}
        self.reload()

    def reload(self) -> None:
        self.templates.clear()
        if not self.root.exists():
            return
        for path in self.root.rglob("*.yaml"):
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            tmpl = TemplateManifest.model_validate(data)
            self.templates[tmpl.template_id] = tmpl

    def get(self, template_id: str) -> TemplateManifest:
        try:
            return self.templates[template_id]
        except KeyError as exc:
            raise LookupError(f"Template not found: {template_id}") from exc

    def by_agent(self, agent: str) -> list[TemplateManifest]:
        return [t for t in self.templates.values() if t.agent == agent]

    def retrieve(self, *, operation_type: str, agent: str | None = None) -> TemplateManifest:
        candidates = [t for t in self.templates.values() if t.operation_type == operation_type]
        if agent:
            scoped = [t for t in candidates if t.agent == agent]
            if scoped:
                candidates = scoped
        if not candidates:
            raise LookupError(f"No template for operation_type={operation_type}, agent={agent}")
        candidates.sort(key=lambda t: t.template_id)
        return candidates[-1]

    def manifest(self) -> list[dict]:
        return [t.model_dump(mode="json") for t in sorted(self.templates.values(), key=lambda x: x.template_id)]
