from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ModelProvider(ABC):
    """Minimal provider abstraction for replacing the rule-based planner.

    The research baseline defaults to RuleBasedPlanner for deterministic tests.
    A real LLM-backed planner can implement this interface and still emit the
    same TaskSpec/DAG/Operation IR files, preserving the rest of the pipeline.
    """

    @abstractmethod
    def complete_json(self, prompt: str, schema: dict[str, Any], *, context: dict[str, Any] | None = None) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def complete_text(self, prompt: str, *, context: dict[str, Any] | None = None) -> str:
        raise NotImplementedError

    def embed(self, texts: list[str]) -> list[list[float]]:
        # Optional for small local demos; template/asset retrieval can start with lexical matching.
        raise NotImplementedError("Embedding is optional in the local research baseline")


class EchoModelProvider(ModelProvider):
    """Deterministic stub for tests and integration wiring."""

    def complete_json(self, prompt: str, schema: dict[str, Any], *, context: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"prompt": prompt, "schema_title": schema.get("title"), "context_keys": sorted((context or {}).keys())}

    def complete_text(self, prompt: str, *, context: dict[str, Any] | None = None) -> str:
        return prompt
