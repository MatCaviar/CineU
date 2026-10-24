from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .asset_store import AssetStore
from .camera_math import compute_hitchcock_zoom_keys_for_target_path, linear_camera_keys, orbit_camera_keys, reference_camera_path_keys
from .ledger import FileLedger
from .schemas import AssetMetadata, Operation, TaskSpec, Transform
from .spatial import SpatialSolver, extent_from_asset, yaw_to_face
from .template_store import TemplateStore


@dataclass
class RunContext:
    run_id: str
    workspace: Path
    project_id: str
    project_dir: Path
    knowledge_dir: Path
    ledger: FileLedger
    asset_store: AssetStore
    template_store: TemplateStore
    task: TaskSpec
    variables: dict[str, Any] = field(default_factory=dict)

    @property
    def sequence_path(self) -> str:
        active = self.variables.get("active_sequence_path")
        if active:
            return str(active)
        return f"/Game/CineU/Sequences/SEQ_{self.run_id}"


class BaseAgent:
    name = "BaseAgent"

    def template_for(self, ctx: RunContext, operation_type: str) -> str:
        return ctx.template_store.retrieve(operation_type=operation_type, agent=self.name).template_id


def _native_capture_source_fps(variables: dict[str, Any], default: int = 60) -> int:
    raw_rate = variables.get("active_native_capture_frame_rate")
    if isinstance(raw_rate, dict):
        raw_rate = raw_rate.get("numerator")
    try:
        source_fps = int(raw_rate or default)
    except (TypeError, ValueError):
        source_fps = default
    return max(1, source_fps)


def _mrq_output_frame_rate_for_target(source_count: int, output_count: int, source_fps: int) -> dict[str, int]:
    return {"numerator": max(1, int(output_count)) * max(1, int(source_fps)), "denominator": max(1, int(source_count))}


def _candidate_records(matches: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for match in matches[:limit]:
        asset = match["asset"]
        records.append(
            {
                "asset_id": asset.asset_id,
                "name": asset.name,
                "type": asset.type,
                "source_type": asset.source_type,
                "source_path": asset.source_path,
                "ue_path": asset.ue_path,
                "import_required": asset.import_required,
                "score": float(match["score"]),
                "breakdown": match.get("breakdown", {}),
            }
        )
    return records


def _retrieve_with_candidates(
    asset_store: AssetStore,
    query: str,
    *,
    required_type: str,
    required_tags: list[str],
) -> tuple[AssetMetadata, list[dict[str, Any]]]:
    matches = asset_store.search(query, required_type=required_type, required_tags=required_tags)
    if not matches:
        raise LookupError(f"No asset candidate for query={query!r}, required_type={required_type!r}")
    asset = _select_reusable_primary_asset(asset_store, matches, query=query, required_type=required_type)
    return asset, _candidate_records(matches)


def _select_reusable_primary_asset(
    asset_store: AssetStore,
    matches: list[dict[str, Any]],
    *,
    query: str,
    required_type: str,
) -> AssetMetadata:
    for match in matches:
        if float(match["score"]) <= 0:
            continue
        asset = asset_store.materialize(match["asset"])
        if asset_store.is_reusable_primary_asset(asset):
            return asset
    raise LookupError(f"No reusable primary asset for query={query!r}, required_type={required_type!r}")


def _prefer_subject_framed_sequence_variants(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def rank(match: dict[str, Any]) -> tuple[float, float]:
        asset = match["asset"]
        text = " ".join(
            str(value)
            for value in [
                asset.name,
                asset.asset_id,
                asset.ue_path,
                Path(str(asset.source_path)).stem if asset.source_path else "",
                *asset.semantic_tags,
                *asset.functional_tags,
            ]
            if value
        ).lower()
        subject_score = 1.0 if "ablation" in text else 0.0
        return subject_score, float(match["score"])

    return sorted(matches, key=rank, reverse=True)


def _select_reference_sequence_asset(
    ctx: RunContext,
    shot_metadata: dict[str, Any],
    matches: list[dict[str, Any]],
    *,
    query: str,
) -> AssetMetadata:
    reference_path = str(shot_metadata.get("reference_sequence_path") or "")
    if reference_path:
        for match in matches:
            if float(match["score"]) <= 0:
                continue
            asset = ctx.asset_store.materialize(match["asset"])
            if asset.ue_path == reference_path and ctx.asset_store.is_reusable_primary_asset(asset):
                return asset
    return _select_reusable_primary_asset(ctx.asset_store, matches, query=query, required_type="level_sequence")


def _content_root_for_source(path: Path) -> Path | None:
    for candidate in [path.parent, *path.parents]:
        if candidate.name.lower() == "content":
            return candidate
    return None


def _resolve_reference_capture_source(shot_metadata: dict[str, Any], sequence_asset: AssetMetadata) -> str | None:
    explicit = shot_metadata.get("reference_capture_source") or shot_metadata.get("reference_capture_source_path")
    if explicit:
        path = Path(str(explicit))
        return str(path.resolve() if path.exists() else path)

    relative_capture = str(shot_metadata.get("reference_capture_path") or "")
    if not relative_capture or not sequence_asset.source_path:
        return None

    source_path = Path(sequence_asset.source_path)
    candidates: list[Path] = []
    content_root = _content_root_for_source(source_path)
    if content_root is not None:
        candidates.append(content_root.parent / relative_capture)

    for parent in source_path.resolve().parents:
        candidates.append(parent / "CityParkEnv55" / relative_capture)

    for candidate in candidates:
        if candidate.exists():
            return str(candidate.resolve())
    return None


class EnvAgent(BaseAgent):
    name = "EnvAgent"

    def build(self, ctx: RunContext) -> Operation:
        environment_asset = ctx.variables.get("environment_asset")
        if not environment_asset:
            raise LookupError(f"Environment setup requires a reusable asset for {ctx.task.scene.environment!r}")
        inputs = {
            "level_name": f"LVL_{ctx.run_id}",
            "environment": ctx.task.scene.environment,
            "mood": ctx.task.scene.mood,
            "duration_sec": ctx.task.scene.duration_sec,
        }
        inputs["environment_asset"] = environment_asset
        dressing_assets = ctx.variables.get("environment_dressing_assets") or []
        if dressing_assets:
            inputs["dressing_assets"] = dressing_assets
        return Operation(
            op_id="env_setup",
            node_id="env.setup",
            agent=self.name,
            type="env.setup",
            template_id=self.template_for(ctx, "env.setup"),
            inputs=inputs,
            expected={"level_exists": True, "support_surfaces_min": 1},
        )


class EntityAgent(BaseAgent):
    name = "EntityAgent"

    def retrieve(self, ctx: RunContext) -> dict[str, AssetMetadata]:
        asset_map: dict[str, AssetMetadata] = {}
        retrieval_records: list[dict[str, Any]] = []
        for entity in ctx.task.entities:
            retrieval_status = "hit"
            candidates: list[dict[str, Any]] = []
            try:
                asset, candidates = _retrieve_with_candidates(
                    ctx.asset_store,
                    entity.asset_query,
                    required_type=entity.asset_constraints.asset_type,
                    required_tags=entity.asset_constraints.required_tags,
                )
            except LookupError as exc:
                retrieval_records.append(
                    {
                        "entity_id": entity.id,
                        "query": entity.asset_query,
                        "status": f"miss:{type(exc).__name__}",
                        "selected_asset_id": None,
                        "asset": None,
                        "candidates": candidates,
                    }
                )
                ctx.ledger.write_json("planning/asset_retrieval.json", {"records": retrieval_records})
                raise
            else:
                retrieval_status = f"hit:{asset.source_type}"
            asset_map[entity.id] = asset
            retrieval_records.append(
                {
                    "entity_id": entity.id,
                    "query": entity.asset_query,
                    "status": retrieval_status,
                    "selected_asset_id": asset.asset_id,
                    "asset": asset.model_dump(mode="json"),
                    "candidates": candidates,
                }
            )
        ctx.variables["assets"] = {k: v.model_dump(mode="json") for k, v in asset_map.items()}
        ctx.ledger.write_json("planning/asset_retrieval.json", {"records": retrieval_records})
        return asset_map

    def build_spawn(self, ctx: RunContext, asset_map: dict[str, AssetMetadata]) -> Operation:
        actors = []
        for entity in ctx.task.entities:
            asset = asset_map[entity.id]
            actors.append(
                {
                    "actor_name": entity.id,
                    **({"reuse_actor_name": str(entity.animation["reuse_actor_name"])} if entity.animation and entity.animation.get("reuse_actor_name") else {}),
                    "semantic_type": entity.semantic_type,
                    "asset_id": asset.asset_id,
                    "asset_path": asset.ue_path,
                    "asset_type": asset.type,
                    "source_path": asset.source_path,
                    "source_type": asset.source_type,
                    "import_required": asset.import_required,
                    "import_destination": asset.import_destination,
                    "imported_object_paths": asset.imported_object_paths,
                    "materials": asset.materials,
                    "bounds_extent": extent_from_asset(asset),
                }
            )
        return Operation(
            op_id="entity_spawn",
            node_id="entity.spawn",
            agent=self.name,
            type="entity.spawn_many",
            template_id=self.template_for(ctx, "entity.spawn_many"),
            inputs={"actors": actors},
            expected={"actors_exist": [a["actor_name"] for a in actors]},
            rollback={"delete_actors": [a["actor_name"] for a in actors]},
        )


class AssetAgent(BaseAgent):
    name = "AssetAgent"

    def retrieve_environment(self, ctx: RunContext) -> AssetMetadata | None:
        environment = ctx.task.scene.environment
        query = f"{environment} environment"
        matches = [
            match
            for match in ctx.asset_store.search(query, required_type="any", required_tags=[environment, "environment"])
            if match["asset"].type in {"level", "static_mesh"}
        ]
        if not matches or float(matches[0]["score"]) <= 0:
            ctx.variables["environment_asset"] = None
            ctx.ledger.write_json(
                "planning/environment_asset_retrieval.json",
                {
                    "query": query,
                    "status": "miss:LookupError",
                    "selected_asset_id": None,
                    "asset": None,
                    "candidates": _candidate_records(matches),
                },
            )
            raise LookupError(f"No reusable environment asset for environment={environment!r}")
        best_type = matches[0]["asset"].type
        try:
            asset = _select_reusable_primary_asset(ctx.asset_store, matches, query=query, required_type=best_type)
        except LookupError as exc:
            ctx.variables["environment_asset"] = None
            ctx.ledger.write_json(
                "planning/environment_asset_retrieval.json",
                {
                    "query": query,
                    "status": f"miss:{type(exc).__name__}",
                    "selected_asset_id": None,
                    "asset": None,
                    "candidates": _candidate_records(matches),
                },
            )
            raise
        ctx.variables["environment_asset"] = asset.model_dump(mode="json")
        ctx.ledger.write_json(
            "planning/environment_asset_retrieval.json",
            {
                "query": query,
                "status": f"hit{'_mesh' if asset.type == 'static_mesh' else ''}:{asset.source_type}",
                "selected_asset_id": asset.asset_id,
                "asset": asset.model_dump(mode="json"),
                "candidates": _candidate_records(matches),
            },
        )
        return asset

    def retrieve_environment_dressing(self, ctx: RunContext) -> list[AssetMetadata]:
        environment = ctx.task.scene.environment.lower()
        if environment != "park":
            ctx.variables["environment_dressing_assets"] = []
            ctx.ledger.write_json("planning/environment_dressing_asset_retrieval.json", {"records": []})
            return []
        query = "citypark flora park tree willow maple elm leafy canopy twinmotion vegetation fab"
        matches = ctx.asset_store.search(query, required_type="static_mesh", required_tags=["tree"])

        def rank(match: dict[str, Any]) -> tuple[float, float, float, float]:
            asset = match["asset"]
            text = " ".join(
                str(value)
                for value in [
                    asset.name,
                    asset.asset_id,
                    asset.ue_path,
                    asset.source_path,
                    *asset.semantic_tags,
                    *asset.functional_tags,
                ]
                if value
            ).lower()
            identity_text = " ".join(
                str(value)
                for value in [
                    asset.name,
                    asset.asset_id,
                    asset.ue_path,
                    *asset.semantic_tags,
                    *asset.functional_tags,
                ]
                if value
            ).lower()
            citypark = 1.0 if "citypark" in text or "/game/citypark/" in text else 0.0
            leafy = 1.0 if {"leafy", "canopy"} & {tag.lower() for tag in asset.semantic_tags} else 0.0
            preferred_species = (
                3.0
                if "weepingwillow" in identity_text
                else 2.5
                if "maple" in identity_text
                else 2.0
                if "elm" in identity_text
                else 1.0
                if "ficusbenjamina" in identity_text or "tiliaamericana" in identity_text
                else 0.0
            )
            reusable = 1.0 if ctx.asset_store.is_reusable_primary_asset(asset) else 0.0
            return citypark, preferred_species, leafy, reusable, float(match["score"])

        ranked = sorted(matches, key=rank, reverse=True)
        selected: list[AssetMetadata] = []
        seen: set[str] = set()
        for match in ranked:
            if float(match["score"]) <= 0:
                continue
            asset = ctx.asset_store.materialize(match["asset"])
            if not ctx.asset_store.is_reusable_primary_asset(asset):
                continue
            text = " ".join([asset.ue_path, asset.source_path or "", *asset.semantic_tags]).lower()
            if not any(token in text for token in ["citypark", "twinmotion", "megascan", "fab"]):
                continue
            if asset.asset_id in seen:
                continue
            selected.append(asset)
            seen.add(asset.asset_id)
            if len(selected) >= 2:
                break

        ctx.variables["environment_dressing_assets"] = [asset.model_dump(mode="json") for asset in selected]
        ctx.ledger.write_json(
            "planning/environment_dressing_asset_retrieval.json",
            {
                "records": [
                    {
                        "environment": environment,
                        "query": query,
                        "status": f"hit:{selected[0].source_type}" if selected else "miss:LookupError",
                        "selected_asset_ids": [asset.asset_id for asset in selected],
                        "assets": [asset.model_dump(mode="json") for asset in selected],
                        "candidates": _candidate_records(ranked, limit=40),
                    }
                ]
            },
        )
        return selected

    def retrieve_animations(self, ctx: RunContext) -> dict[str, AssetMetadata]:
        animation_assets: dict[str, AssetMetadata] = {}
        records: list[dict[str, Any]] = []
        for entity in ctx.task.entities:
            if not entity.animation:
                continue
            animation = entity.animation
            animation_type = str(animation.get("type", "idle"))
            query = str(animation.get("asset_query") or f"{entity.semantic_type} {animation_type} animation")
            required_tags = [str(tag) for tag in animation.get("required_tags", [entity.semantic_type, animation_type, "animation"])]
            candidates: list[dict[str, Any]] = []
            try:
                matches = ctx.asset_store.search(
                    query,
                    required_type="animation",
                    required_tags=required_tags,
                )
                if not matches:
                    raise LookupError(f"No asset candidate for query={query!r}, required_type='animation'")
                preferred_path = str(animation.get("preferred_asset_path") or "")
                asset = None
                for match in matches:
                    candidate = ctx.asset_store.materialize(match["asset"])
                    if float(match["score"]) > 0 and preferred_path and candidate.ue_path == preferred_path and ctx.asset_store.is_reusable_primary_asset(candidate):
                        asset = candidate
                        break
                if asset is None:
                    asset = _select_reusable_primary_asset(
                        ctx.asset_store,
                        matches,
                        query=query,
                        required_type="animation",
                    )
                candidates = _candidate_records(matches)
            except LookupError as exc:
                records.append(
                    {
                        "entity_id": entity.id,
                        "query": query,
                        "status": f"miss:{type(exc).__name__}",
                        "selected_asset_id": None,
                        "asset": None,
                        "candidates": candidates,
                    }
                )
                continue
            animation_assets[entity.id] = asset
            records.append(
                {
                    "entity_id": entity.id,
                    "query": query,
                    "status": f"hit:{asset.source_type}",
                    "selected_asset_id": asset.asset_id,
                    "asset": asset.model_dump(mode="json"),
                    "candidates": candidates,
                }
            )
        ctx.variables["animation_assets"] = {k: v.model_dump(mode="json") for k, v in animation_assets.items()}
        ctx.ledger.write_json("planning/animation_asset_retrieval.json", {"records": records})
        return animation_assets

    def retrieve_sequences(self, ctx: RunContext) -> dict[str, AssetMetadata]:
        sequence_assets: dict[str, AssetMetadata] = {}
        records: list[dict[str, Any]] = []
        for shot in ctx.task.camera.shots:
            if shot.type != "hitchcock_zoom":
                continue
            target = shot.target or (ctx.task.entities[0].id if ctx.task.entities else "")
            entity = next((item for item in ctx.task.entities if item.id == target), None)
            semantic = entity.semantic_type if entity else "animal"
            query = f"{ctx.task.scene.environment} {semantic} animal hitchcock zoom level sequence"
            candidates: list[dict[str, Any]] = []
            try:
                matches = ctx.asset_store.search(query, required_type="level_sequence", required_tags=["hitchcock", "sequence"])
                if ctx.task.scene.environment.lower() == "park" and not (shot.metadata or {}).get("reference_sequence_path"):
                    matches = _prefer_subject_framed_sequence_variants(matches)
                if not matches:
                    raise LookupError(f"No asset candidate for query={query!r}, required_type='level_sequence'")
                asset = _select_reference_sequence_asset(ctx, shot.metadata or {}, matches, query=query)
                candidates = _candidate_records(matches)
            except LookupError as exc:
                records.append(
                    {
                        "shot_id": shot.id,
                        "query": query,
                        "status": f"miss:{type(exc).__name__}",
                        "selected_asset_id": None,
                        "asset": None,
                        "candidates": candidates,
                    }
                )
                continue
            sequence_assets[shot.id] = asset
            records.append(
                {
                    "shot_id": shot.id,
                    "query": query,
                    "status": f"hit:{asset.source_type}",
                    "selected_asset_id": asset.asset_id,
                    "asset": asset.model_dump(mode="json"),
                    "candidates": candidates,
                }
            )
        ctx.variables["sequence_assets"] = {k: v.model_dump(mode="json") for k, v in sequence_assets.items()}
        ctx.ledger.write_json("planning/sequence_asset_retrieval.json", {"records": records})
        return sequence_assets

    def build_import(
        self,
        ctx: RunContext,
        asset_map: dict[str, AssetMetadata],
        environment_asset: AssetMetadata | None = None,
        animation_assets: dict[str, AssetMetadata] | None = None,
        sequence_assets: dict[str, AssetMetadata] | None = None,
        dressing_assets: list[AssetMetadata] | None = None,
    ) -> Operation | None:
        assets = []
        seen: set[str] = set()
        candidates: list[AssetMetadata] = []
        if environment_asset is not None:
            candidates.append(environment_asset)
        candidates.extend(asset_map.values())
        candidates.extend((animation_assets or {}).values())
        candidates.extend((sequence_assets or {}).values())
        candidates.extend(dressing_assets or [])
        for asset in candidates:
            if not asset.import_required or asset.asset_id in seen:
                continue
            assets.append(asset.model_dump(mode="json"))
            seen.add(asset.asset_id)
        if not assets:
            return None
        return Operation(
            op_id="asset_import",
            node_id="asset.import",
            agent=self.name,
            type="asset.import_many",
            template_id=self.template_for(ctx, "asset.import_many"),
            inputs={"assets": assets},
            expected={"assets_imported": [asset["asset_id"] for asset in assets]},
        )


class SpatialAgent(BaseAgent):
    name = "SpatialAgent"

    def build(self, ctx: RunContext, asset_map: dict[str, AssetMetadata]) -> Operation:
        placements = SpatialSolver().solve(ctx.task.entities, asset_map, ctx.task.scene.environment)
        ctx.variables["placements"] = {p["actor_name"]: p for p in placements}
        return Operation(
            op_id="spatial_place",
            node_id="spatial.place",
            agent=self.name,
            type="spatial.apply_transforms",
            template_id=self.template_for(ctx, "spatial.apply_transforms"),
            inputs={"placements": placements},
            expected={
                "actors_transformed": [p["actor_name"] for p in placements],
                "relations": [{"actor": p["actor_name"], "relation": p["relation"], "target": p.get("target")} for p in placements],
                "no_actor_overlap": True,
            },
        )


class SeqAgent(BaseAgent):
    name = "SeqAgent"

    def _timeline_for_existing_sequence(self, ctx: RunContext, shot_id: str) -> dict[str, int]:
        scene = ctx.task.scene
        timeline = {"fps": int(scene.fps), "start_frame": 0, "end_frame": int(scene.end_frame)}
        shot = next((item for item in ctx.task.camera.shots if item.id == shot_id), None)
        metadata = shot.metadata if shot is not None else {}
        if metadata.get("reference_output_fps") and metadata.get("reference_output_end_frame"):
            timeline["fps"] = int(metadata["reference_output_fps"])
            timeline["end_frame"] = int(metadata["reference_output_end_frame"])
        return timeline

    def build_init(self, ctx: RunContext) -> Operation:
        fps = ctx.task.scene.fps
        end_frame = ctx.task.scene.end_frame
        return Operation(
            op_id="sequence_init",
            node_id="seq.init",
            agent=self.name,
            type="sequence.init",
            template_id=self.template_for(ctx, "sequence.init"),
            inputs={
                "sequence_path": ctx.sequence_path,
                "fps": fps,
                "start_frame": 0,
                "end_frame": end_frame,
            },
            expected={"sequence_exists": ctx.sequence_path, "sequence_range": [0, end_frame], "fps": fps},
            rollback={"delete_sequence": ctx.sequence_path},
        )

    def build_use_existing(self, ctx: RunContext, shot_id: str, sequence_asset: AssetMetadata) -> Operation:
        ctx.variables["active_sequence_path"] = sequence_asset.ue_path
        shot = next((item for item in ctx.task.camera.shots if item.id == shot_id), None)
        metadata = shot.metadata if shot is not None else {}
        if metadata.get("reference_capture_start_frame") is not None and metadata.get("reference_capture_end_frame") is not None:
            ctx.variables["active_native_capture_frame_range"] = {
                "start_frame": int(metadata.get("reference_capture_start_frame", 0) or 0),
                "end_frame": int(metadata.get("reference_capture_end_frame", 0) or 0),
            }
        else:
            ctx.variables.pop("active_native_capture_frame_range", None)
        reference_capture_source = _resolve_reference_capture_source(metadata, sequence_asset)
        if reference_capture_source:
            ctx.variables["active_reference_capture"] = {
                "source": reference_capture_source,
                "start_frame": int(metadata.get("reference_capture_start_frame", 0) or 0),
                "end_frame": int(metadata.get("reference_capture_end_frame", 0) or 0),
            }
        else:
            ctx.variables.pop("active_reference_capture", None)
        timeline = self._timeline_for_existing_sequence(ctx, shot_id)
        active_reference_capture = ctx.variables.get("active_reference_capture")
        if active_reference_capture:
            source_start = int(active_reference_capture.get("start_frame", 0) or 0)
            source_end = int(active_reference_capture.get("end_frame", 0) or 0)
            source_count = max(0, source_end - source_start)
            if source_count > max(0, int(timeline["end_frame"]) - int(timeline["start_frame"])):
                timeline["end_frame"] = int(timeline["start_frame"]) + source_count
        ctx.variables["active_sequence_timeline"] = timeline
        fps = timeline["fps"]
        end_frame = timeline["end_frame"]
        return Operation(
            op_id="sequence_use_existing",
            node_id="seq.use_existing",
            agent=self.name,
            type="sequence.use_existing",
            template_id=self.template_for(ctx, "sequence.use_existing"),
            inputs={
                "sequence_path": sequence_asset.ue_path,
                "sequence_asset": sequence_asset.model_dump(mode="json"),
                "shot_id": shot_id,
                "fps": fps,
                "start_frame": 0,
                "end_frame": end_frame,
                "native_camera_name": "NativeSequenceCamera",
            },
            expected={"sequence_exists": sequence_asset.ue_path},
        )

    def build_camera_cut(self, ctx: RunContext, camera_ops: list[Operation]) -> Operation:
        cuts = []
        for op in camera_ops:
            cuts.append(
                {
                    "camera_name": op.inputs["camera_name"],
                    "shot_id": op.inputs["shot_id"],
                    "start_frame": op.inputs["start_frame"],
                    "end_frame": op.inputs["end_frame"],
                }
            )
        return Operation(
            op_id="camera_cut",
            node_id="seq.camera_cut",
            agent=self.name,
            type="sequence.camera_cut",
            template_id=self.template_for(ctx, "sequence.camera_cut"),
            inputs={"sequence_path": ctx.sequence_path, "cuts": cuts},
            expected={"camera_cut_no_gaps": True, "camera_cut_count": len(cuts)},
        )


class CamAgent(BaseAgent):
    name = "CamAgent"

    def build(self, ctx: RunContext) -> list[Operation]:
        ops: list[Operation] = []
        for idx, shot in enumerate(ctx.task.camera.shots, start=1):
            start_frame = int(round(shot.start_time * ctx.task.scene.fps))
            end_frame = int(round(shot.end_time * ctx.task.scene.fps))
            camera_name = f"CAM_{shot.id}"
            target_name = shot.target or (ctx.task.entities[0].id if ctx.task.entities else "world_origin")
            target_start, target_end = self._target_path(ctx, target_name)
            target_location = target_start
            if shot.type == "hitchcock_zoom":
                distance_start = float(shot.metadata.get("distance_start", 900))
                distance_end = float(shot.metadata.get("distance_end", 350))
                focal_start = float(shot.focal_length_start or shot.focal_length or 35)
                reference_path = shot.metadata.get("reference_camera_path")
                if isinstance(reference_path, dict):
                    keys = reference_camera_path_keys(
                        location_start=[float(value) for value in reference_path["location_start"]],
                        location_end=[float(value) for value in reference_path["location_end"]],
                        target_location=[float(value) for value in reference_path.get("target_location", target_start)],
                        focal_start=float(reference_path.get("focal_length_start", focal_start)),
                        focal_end=float(reference_path.get("focal_length_end", focal_start)),
                        start_frame=start_frame,
                        end_frame=end_frame,
                        num_keys=int(reference_path.get("num_keys", 8)),
                        rotation_start=(
                            [float(value) for value in reference_path["rotation_start"]]
                            if "rotation_start" in reference_path
                            else None
                        ),
                        rotation_end=(
                            [float(value) for value in reference_path["rotation_end"]]
                            if "rotation_end" in reference_path
                            else None
                        ),
                    )
                else:
                    direction = shot.metadata.get("direction", [0.0, -1.0, 0.0])
                    keys = compute_hitchcock_zoom_keys_for_target_path(
                        target_start=target_start,
                        target_end=target_end,
                        direction=[float(value) for value in direction],
                        distance_start=distance_start,
                        distance_end=distance_end,
                        focal_start=focal_start,
                        start_frame=start_frame,
                        end_frame=end_frame,
                        num_keys=8,
                    )
                op_type = "camera.hitchcock_zoom"
            elif shot.type == "wide_aerial":
                if "gallery" in ctx.task.scene.environment.lower():
                    y = _clamp(target_location[1] - 500, -420.0, -120.0)
                    loc = [_clamp(target_location[0] - 320, -420.0, 420.0), y, 340.0]
                    end_loc = [_clamp(target_location[0] + 320, -420.0, 420.0), y, 340.0]
                else:
                    loc = [target_location[0] - 80, target_location[1] - 100, target_location[2] + 650]
                    end_loc = [target_location[0] + 80, target_location[1] - 120, target_location[2] + 650]
                keys = linear_camera_keys(loc, end_loc, target_location, start_frame, end_frame, shot.focal_length or 24)
                op_type = "camera.wide_aerial"
            elif shot.type == "orbit":
                keys = orbit_camera_keys(
                    target_location=target_location,
                    radius=float(shot.metadata.get("radius", 560)),
                    height=float(shot.metadata.get("height", 170)),
                    start_angle=float(shot.metadata.get("start_angle", -150)),
                    end_angle=float(shot.metadata.get("end_angle", -30)),
                    start_frame=start_frame,
                    end_frame=end_frame,
                    focal_length=shot.focal_length or 32,
                    num_keys=int(shot.metadata.get("num_keys", 8)),
                )
                op_type = "camera.orbit"
            else:
                start_loc, end_loc = self._linear_shot_locations(ctx, target_location)
                if shot.type == "dolly_out":
                    start_loc, end_loc = end_loc, start_loc
                look_target = self._linear_look_target(ctx, target_location, shot)
                keys = linear_camera_keys(start_loc, end_loc, look_target, start_frame, end_frame, shot.focal_length or 35)
                op_type = "camera.dolly_in" if shot.type in {"dolly_in", "dolly_out"} else "camera.static_shot"
            expected: dict[str, Any] = {
                "cameras_exist": [camera_name],
                "camera_transform_keys_min": {camera_name: 2},
                "focal_length_keys_min": {camera_name: 2 if shot.type == "hitchcock_zoom" else 1},
                "camera_key_range": {camera_name: [start_frame, end_frame]},
            }
            if shot.type == "hitchcock_zoom":
                expected["hitchcock_zoom_coupling"] = {camera_name: {"max_relative_error": 1e-6}}
            ops.append(
                Operation(
                    op_id=f"camera_{shot.id}",
                    node_id="seq.camera",
                    agent=self.name,
                    type=op_type,
                    template_id=self.template_for(ctx, op_type),
                    inputs={
                        "sequence_path": ctx.sequence_path,
                        "shot_id": shot.id,
                        "camera_name": camera_name,
                        "target_actor": target_name,
                        "start_frame": start_frame,
                        "end_frame": end_frame,
                        "keys": keys,
                    },
                    expected=expected,
                    rollback={"delete_actors": [camera_name]},
                )
            )
        return ops

    def _linear_shot_locations(self, ctx: RunContext, target_location: list[float]) -> tuple[list[float], list[float]]:
        if "gallery" in ctx.task.scene.environment.lower():
            if target_location[1] >= 420.0:
                z = _clamp(target_location[2] + 12.0, 160.0, 230.0)
                start_loc = [_clamp(target_location[0] - 45.0, -420.0, 420.0), 150.0, z]
                end_loc = [_clamp(target_location[0] + 45.0, -420.0, 420.0), 285.0, z]
                return start_loc, end_loc
            start_loc = [0.0, -680.0, _clamp(target_location[2] + 52.0, 155.0, 180.0)]
            end_loc = [90.0, -360.0, _clamp(target_location[2] + 36.0, 145.0, 165.0)]
            return start_loc, end_loc
        return (
            [target_location[0] - 650, target_location[1] - 650, target_location[2] + 120],
            [target_location[0] - 160, target_location[1] - 160, target_location[2] + 90],
        )

    def _linear_look_target(self, ctx: RunContext, target_location: list[float], shot: Any | None = None) -> list[float]:
        if "gallery" in ctx.task.scene.environment.lower():
            metadata_target = (shot.metadata or {}).get("look_target") if shot is not None else None
            if isinstance(metadata_target, list) and len(metadata_target) >= 3:
                return [float(metadata_target[0]), float(metadata_target[1]), float(metadata_target[2])]
            if target_location[1] >= 420.0:
                return [target_location[0], target_location[1], _clamp(target_location[2] + 8.0, 155.0, 230.0)]
            return [target_location[0], target_location[1], max(target_location[2] - 40.0, 90.0)]
        return target_location

    def _target_path(self, ctx: RunContext, target_name: str) -> tuple[list[float], list[float]]:
        placement = ctx.variables.get("placements", {}).get(target_name)
        entity = next((e for e in ctx.task.entities if e.id == target_name), None)
        if placement:
            loc = list(placement["transform"]["location"])
            extent = placement.get("bounds_extent", [0, 0, 50])
            start = [loc[0], loc[1], loc[2] + extent[2] * 0.3]
            end = list(start)
            if entity and entity.spatial.end:
                end = [float(entity.spatial.end[0]), float(entity.spatial.end[1]), loc[2] + extent[2] * 0.3]
            return start, end
        return [0.0, 0.0, 100.0], [0.0, 0.0, 100.0]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


class TransAgent(BaseAgent):
    name = "TransAgent"

    def build(self, ctx: RunContext) -> Operation | None:
        tracks: list[dict[str, Any]] = []
        for entity in ctx.task.entities:
            if not (entity.spatial.start and entity.spatial.end):
                continue
            placement = ctx.variables.get("placements", {}).get(entity.id)
            extent = placement.get("bounds_extent", [0, 0, 50]) if placement else [0, 0, 50]
            start_frame = 0
            end_frame = ctx.task.scene.end_frame
            if entity.animation:
                start_frame = int(round(float(entity.animation.get("start_time", 0)) * ctx.task.scene.fps))
                end_frame = int(round(float(entity.animation.get("end_time", ctx.task.scene.duration_sec)) * ctx.task.scene.fps))
            track_z = float((placement or {}).get("transform", {}).get("location", [0.0, 0.0, extent[2]])[2])
            start_loc = [float(entity.spatial.start[0]), float(entity.spatial.start[1]), track_z]
            end_loc = [float(entity.spatial.end[0]), float(entity.spatial.end[1]), track_z]
            yaw = yaw_to_face(start_loc, end_loc)
            if entity.semantic_type == "zebra" and ctx.task.scene.environment.lower() == "park":
                yaw = float((entity.animation or {}).get("reference_yaw", 0.0))
            tracks.append(
                {
                    "actor_name": entity.id,
                    "start_frame": start_frame,
                    "end_frame": end_frame,
                    "keys": [
                        {"frame": start_frame, "transform": Transform(location=start_loc, rotation=[0, 0, yaw], scale=[1, 1, 1]).model_dump(mode="json")},
                        {"frame": end_frame, "transform": Transform(location=end_loc, rotation=[0, 0, yaw], scale=[1, 1, 1]).model_dump(mode="json")},
                    ],
                    "semantic_motion": entity.animation.get("type", "move") if entity.animation else "move",
                }
            )
        if not tracks:
            return None
        return Operation(
            op_id="transform_tracks",
            node_id="seq.transform",
            agent=self.name,
            type="transform.add_tracks",
            template_id=self.template_for(ctx, "transform.add_tracks"),
            inputs={"sequence_path": ctx.sequence_path, "tracks": tracks},
            expected={
                "transform_tracks": [t["actor_name"] for t in tracks],
                "motion_alignment": [{"actor": t["actor_name"], "start_frame": t["start_frame"], "end_frame": t["end_frame"]} for t in tracks],
            },
        )


class AnimAgent(BaseAgent):
    name = "AnimAgent"

    def build(self, ctx: RunContext) -> Operation | None:
        animated = [e for e in ctx.task.entities if e.animation]
        if not animated:
            return None
        clips = []
        animation_assets = ctx.variables.get("animation_assets", {})
        entity_assets = ctx.variables.get("assets", {})
        for entity in animated:
            anim = entity.animation or {}
            animation_type = anim.get("type", "idle")
            clip_asset = animation_assets.get(entity.id)
            fallback_animation_path = anim.get("preferred_asset_path") or self._fallback_animation_path(entity_assets.get(entity.id, {}), animation_type)
            clips.append(
                {
                    "actor_name": entity.id,
                    "animation_type": animation_type,
                    "start_frame": int(round(float(anim.get("start_time", 0)) * ctx.task.scene.fps)),
                    "end_frame": int(round(float(anim.get("end_time", ctx.task.scene.duration_sec)) * ctx.task.scene.fps)),
                    "animation_asset_id": clip_asset.get("asset_id") if clip_asset else None,
                    "animation_path": clip_asset.get("ue_path") if clip_asset else fallback_animation_path,
                    "source_path": clip_asset.get("source_path") if clip_asset else None,
                    "source_type": clip_asset.get("source_type") if clip_asset else None,
                    "import_required": bool(clip_asset.get("import_required")) if clip_asset else False,
                }
            )
        return Operation(
            op_id="animation_tracks",
            node_id="seq.animation",
            agent=self.name,
            type="animation.add_tracks",
            template_id=self.template_for(ctx, "animation.add_tracks"),
            inputs={"sequence_path": ctx.sequence_path, "clips": clips},
            expected={
                "animation_tracks": [c["actor_name"] for c in clips],
                "motion_alignment": [{"actor": c["actor_name"], "start_frame": c["start_frame"], "end_frame": c["end_frame"]} for c in clips],
            },
        )

    def _fallback_animation_path(self, actor_asset: dict[str, Any], animation_type: str) -> str | None:
        for item in actor_asset.get("animations", []):
            if str(item.get("name", "")).lower() == str(animation_type).lower():
                return item.get("path")
        return None


class RenderAgent(BaseAgent):
    name = "RenderAgent"

    def build(self, ctx: RunContext) -> Operation:
        inputs = {
            "sequence_path": ctx.sequence_path,
            "output_dir": str((ctx.ledger.run_dir / "artifacts").resolve()),
            "world_state_path": str((ctx.ledger.run_dir / "snapshots" / "world_current.json").resolve()),
            "resolution": ctx.task.render.resolution,
            "format": ctx.task.render.format,
            "quality": ctx.task.render.quality,
        }
        scene = getattr(ctx.task, "scene", None)
        timeline = getattr(ctx, "variables", {}).get("active_sequence_timeline")
        if timeline:
            inputs.update({"fps": int(timeline["fps"]), "start_frame": int(timeline["start_frame"]), "end_frame": int(timeline["end_frame"])})
        elif scene is not None:
            inputs.update({"fps": scene.fps, "start_frame": 0, "end_frame": scene.end_frame})
        native_capture_range = getattr(ctx, "variables", {}).get("active_native_capture_frame_range")
        if native_capture_range:
            native_start_frame = int(native_capture_range.get("start_frame", 0) or 0)
            native_end_frame = int(native_capture_range.get("end_frame", 0) or 0)
            inputs.update(
                {
                    "native_capture_start_frame": native_start_frame,
                    "native_capture_end_frame": native_end_frame,
                }
            )
            output_count = max(0, int(inputs.get("end_frame", 0) or 0) - int(inputs.get("start_frame", 0) or 0))
            source_count = max(0, native_end_frame - native_start_frame)
            if ctx.task.render.quality == "final" and output_count > 0 and source_count > output_count:
                inputs["render_backend"] = "movie_render_pipeline"
                inputs["mrq_output_frame_rate"] = _mrq_output_frame_rate_for_target(
                    source_count,
                    output_count,
                    _native_capture_source_fps(getattr(ctx, "variables", {})),
                )
        reference_capture = getattr(ctx, "variables", {}).get("active_reference_capture")
        if reference_capture:
            reference_start = int(reference_capture.get("start_frame", 0) or 0)
            reference_end = int(reference_capture.get("end_frame", 0) or 0)
            reference_count = max(0, reference_end - reference_start)
            output_start = int(inputs.get("start_frame", 0) or 0)
            output_end = int(inputs.get("end_frame", output_start) or output_start)
            output_count = max(0, output_end - output_start)
            if reference_count > output_count:
                inputs["end_frame"] = output_start + reference_count
            inputs.update(
                {
                    "reference_capture_source": str(reference_capture["source"]),
                    "reference_capture_start_frame": reference_start,
                    "reference_capture_end_frame": reference_end,
                }
            )
        return Operation(
            op_id="render_preview",
            node_id="render.preview",
            agent=self.name,
            type="render.preview",
            template_id=self.template_for(ctx, "render.preview"),
            inputs=inputs,
            expected={
                "render_artifacts_exist": [
                    "preview_frame.png",
                    "preview_manifest.json",
                    "storyboard_manifest.json",
                    "sequence_preview.gif",
                    *(["sequence_preview.mp4"] if ctx.task.render.format == "mp4" else []),
                ],
                "render_preview_camera_required": True,
            },
        )
