from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Vec3(StrictModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def as_list(self) -> list[float]:
        return [self.x, self.y, self.z]

    @classmethod
    def from_list(cls, values: list[float] | tuple[float, float, float]) -> "Vec3":
        if len(values) != 3:
            raise ValueError("Vec3 requires exactly three values")
        return cls(x=float(values[0]), y=float(values[1]), z=float(values[2]))


class Transform(StrictModel):
    location: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0], min_length=3, max_length=3)
    rotation: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0], min_length=3, max_length=3)
    scale: list[float] = Field(default_factory=lambda: [1.0, 1.0, 1.0], min_length=3, max_length=3)

    @field_validator("location", "rotation", "scale")
    @classmethod
    def numbers(cls, values: list[float]) -> list[float]:
        return [float(v) for v in values]


class SceneSpec(StrictModel):
    name: str
    environment: str
    duration_sec: float = Field(gt=0, default=12.0)
    fps: int = Field(gt=0, default=24)
    mood: str = "cinematic"

    @property
    def end_frame(self) -> int:
        return int(round(self.duration_sec * self.fps))


class AssetConstraints(StrictModel):
    asset_type: Literal["static_mesh", "skeletal_mesh", "material", "any"] = "any"
    must_be_animated: bool = False
    required_tags: list[str] = Field(default_factory=list)


class SpatialSpec(StrictModel):
    relation: str = "on_ground"
    target: str | None = None
    approx_location: list[float] | None = None
    start: list[float] | None = None
    end: list[float] | None = None
    height_cm: float | None = None


class EntitySpec(StrictModel):
    id: str
    semantic_type: str
    asset_query: str
    asset_constraints: AssetConstraints = Field(default_factory=AssetConstraints)
    spatial: SpatialSpec = Field(default_factory=SpatialSpec)
    animation: dict[str, Any] | None = None


class ShotSpec(StrictModel):
    id: str
    type: Literal["static_shot", "dolly_in", "dolly_out", "pan", "orbit", "wide_aerial", "hitchcock_zoom"]
    target: str | None = None
    start_time: float = Field(ge=0)
    end_time: float = Field(gt=0)
    focal_length: float | None = None
    focal_length_start: float | None = None
    focal_length_end: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_time(self) -> "ShotSpec":
        if self.end_time <= self.start_time:
            raise ValueError("shot end_time must be greater than start_time")
        return self


class CameraSpec(StrictModel):
    shots: list[ShotSpec]


class RenderSpec(StrictModel):
    resolution: list[int] = Field(default_factory=lambda: [1280, 720], min_length=2, max_length=2)
    format: Literal["png", "mp4", "exr"] = "mp4"
    quality: Literal["mock", "preview", "final"] = "preview"


class TaskSpec(StrictModel):
    schema_version: str = "cineu.task_spec.v1"
    task_id: str
    project_id: str
    intent: Literal["cinematic_scene_generation", "cinematic_scene_editing"] = "cinematic_scene_generation"
    scene: SceneSpec
    entities: list[EntitySpec]
    camera: CameraSpec
    render: RenderSpec = Field(default_factory=RenderSpec)


class DagNode(StrictModel):
    id: str
    agent: str
    status: Literal["pending", "running", "success", "failed", "skipped"] = "pending"


class Dag(StrictModel):
    schema_version: str = "cineu.dag.v1"
    nodes: list[DagNode]
    edges: list[tuple[str, str]] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_graph(self) -> "Dag":
        node_ids = {n.id for n in self.nodes}
        if len(node_ids) != len(self.nodes):
            raise ValueError("DAG node ids must be unique")
        for src, dst in self.edges:
            if src not in node_ids or dst not in node_ids:
                raise ValueError(f"DAG edge references unknown node: {src}->{dst}")
        self.topological_order()
        return self

    def topological_order(self) -> list[str]:
        node_ids = [n.id for n in self.nodes]
        indeg = {n: 0 for n in node_ids}
        outgoing: dict[str, list[str]] = {n: [] for n in node_ids}
        for src, dst in self.edges:
            outgoing[src].append(dst)
            indeg[dst] += 1
        queue = [n for n in node_ids if indeg[n] == 0]
        result: list[str] = []
        while queue:
            n = queue.pop(0)
            result.append(n)
            for m in outgoing[n]:
                indeg[m] -= 1
                if indeg[m] == 0:
                    queue.append(m)
        if len(result) != len(node_ids):
            raise ValueError("DAG contains a cycle")
        return result


class Operation(StrictModel):
    schema_version: str = "cineu.operation.v1"
    op_id: str
    node_id: str
    agent: str
    type: str
    template_id: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    expected: dict[str, Any] = Field(default_factory=dict)
    rollback: dict[str, Any] = Field(default_factory=dict)


class AssetMetadata(StrictModel):
    schema_version: str = "cineu.asset.v1"
    asset_id: str
    name: str
    ue_path: str
    type: Literal["static_mesh", "skeletal_mesh", "material", "animation", "level", "level_sequence", "other"]
    semantic_tags: list[str] = Field(default_factory=list)
    functional_tags: list[str] = Field(default_factory=list)
    bounds_cm: dict[str, list[float]] = Field(default_factory=lambda: {"extent": [50.0, 50.0, 50.0]})
    has_collision: bool = True
    materials: list[str] = Field(default_factory=list)
    animations: list[dict[str, Any]] = Field(default_factory=list)
    ue_versions: list[str] = Field(default_factory=lambda: ["5.5"])
    license: dict[str, Any] = Field(default_factory=dict)
    source_path: str | None = None
    source_type: str = "ue_asset"
    import_required: bool = False
    import_destination: str | None = None
    imported_object_paths: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class TemplateManifest(StrictModel):
    template_id: str
    agent: str
    domain: str
    ue_version: str = "5.5"
    description: str
    operation_type: str
    inputs_schema: dict[str, str] = Field(default_factory=dict)
    preconditions: list[Any] = Field(default_factory=list)
    postconditions: list[Any] = Field(default_factory=list)
    safety: dict[str, Any] = Field(default_factory=dict)
    rollback: dict[str, Any] = Field(default_factory=dict)
    script: str


class VerificationCheck(StrictModel):
    name: str
    passed: bool
    expected: Any | None = None
    actual: Any | None = None
    message: str = ""


class VerificationReport(StrictModel):
    schema_version: str = "cineu.verification_report.v1"
    op_id: str
    stage: Literal["schema", "plan", "precondition", "static", "runtime", "state", "final"]
    passed: bool
    checks: list[VerificationCheck] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class ExecutionResult(StrictModel):
    ok: bool
    op_id: str
    status: Literal["success", "failed"]
    result: dict[str, Any] = Field(default_factory=dict)
    error_type: str | None = None
    error_message: str | None = None
    stdout: str = ""
    stderr: str = ""


class RunManifest(StrictModel):
    schema_version: str = "cineu.run_manifest.v1"
    run_id: str
    project_id: str
    prompt_file: str
    status: Literal["created", "planning", "executing", "success", "failed"] = "created"
    created_at: str
    engine: dict[str, Any] = Field(default_factory=lambda: {"name": "Unreal Engine", "version": "5.5"})
    asset_cache_version: str = "local_asset_cache_v1"
    template_cache_version: str = "template_cache_v1"


class RunnerMode(str, Enum):
    mock = "mock"
    unreal = "unreal"
