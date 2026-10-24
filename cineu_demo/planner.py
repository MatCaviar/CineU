from __future__ import annotations

import hashlib
import re
from typing import Any

from .environment_anchors import (
    CITYPARK_PATH_END,
    CITYPARK_PATH_START,
    CITYPARK_REFERENCE_CAPTURE_END_FRAME,
    CITYPARK_REFERENCE_CAPTURE_PATH,
    CITYPARK_REFERENCE_CAPTURE_START_FRAME,
    CITYPARK_REFERENCE_CAMERA_PATH,
    CITYPARK_REFERENCE_SEQUENCE_PATH,
)
from .schemas import (
    AssetConstraints,
    CameraSpec,
    Dag,
    DagNode,
    EntitySpec,
    RenderSpec,
    SceneSpec,
    ShotSpec,
    SpatialSpec,
    TaskSpec,
)


def stable_task_id(prompt: str, prefix: str = "task") -> str:
    digest = hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"


class RuleBasedPlanner:
    """Deterministic planner for research demos.

    It intentionally avoids relying on a remote model so the repository is
    executable immediately. A real ModelProvider can replace this class while
    preserving the same TaskSpec/DAG schemas.
    """

    def plan(self, prompt: str, project_id: str = "demo_project") -> tuple[TaskSpec, Dag, list[dict[str, Any]]]:
        lowered = prompt.lower()
        if any(key in lowered for key in ["building", "car parked", "large building", "建筑", "汽车"]):
            return self._plan_large_building(prompt, project_id)
        if any(key in lowered for key in ["cityscape", "rooftop", "on the phone", "屋顶", "城市"]):
            return self._plan_city_rooftop(prompt, project_id)
        if any(key in lowered for key in ["river", "statue", "underwater", "河", "雕像", "水下"]):
            return self._plan_river_statues(prompt, project_id)
        if any(key in lowered for key in ["zebra", "斑马", "hitchcock", "希区"]):
            return self._plan_zebra(prompt, project_id)
        return self._plan_gallery(prompt, project_id)

    def _plan_gallery(self, prompt: str, project_id: str) -> tuple[TaskSpec, Dag, list[dict[str, Any]]]:
        entities = [
            EntitySpec(
                id="painting_01",
                semantic_type="painting",
                asset_query="framed modern painting",
                asset_constraints=AssetConstraints(asset_type="static_mesh", required_tags=["painting", "wall_art"]),
                spatial=SpatialSpec(relation="on_wall", target="back_wall", approx_location=[-320, 480, 180], height_cm=180),
            ),
            EntitySpec(
                id="painting_02",
                semantic_type="painting",
                asset_query="framed modern painting",
                asset_constraints=AssetConstraints(asset_type="static_mesh", required_tags=["painting", "wall_art"]),
                spatial=SpatialSpec(relation="on_wall", target="back_wall", approx_location=[0, 480, 180], height_cm=180),
            ),
            EntitySpec(
                id="painting_03",
                semantic_type="painting",
                asset_query="framed modern painting",
                asset_constraints=AssetConstraints(asset_type="static_mesh", required_tags=["painting", "wall_art"]),
                spatial=SpatialSpec(relation="on_wall", target="back_wall", approx_location=[320, 480, 180], height_cm=180),
            ),
            EntitySpec(
                id="sculpture_01",
                semantic_type="sculpture",
                asset_query="white modern sculpture",
                asset_constraints=AssetConstraints(asset_type="static_mesh", required_tags=["sculpture", "gallery"]),
                spatial=SpatialSpec(relation="on_ground", target="gallery_floor", approx_location=[0, 220, 0]),
            ),
        ]
        shots = [
            ShotSpec(id="shot_001", type="dolly_in", target="sculpture_01", start_time=0, end_time=4, focal_length=24),
            ShotSpec(id="shot_002", type="static_shot", target="painting_02", start_time=4, end_time=7, focal_length=35),
            ShotSpec(id="shot_003", type="wide_aerial", target="sculpture_01", start_time=7, end_time=10, focal_length=22),
            ShotSpec(
                id="shot_004",
                type="dolly_out",
                target="sculpture_01",
                start_time=10,
                end_time=12,
                focal_length=24,
            ),
        ]
        task = TaskSpec(
            task_id=stable_task_id(prompt, "task_gallery"),
            project_id=project_id,
            scene=SceneSpec(name="modern_gallery_tour", environment="gallery", duration_sec=12, fps=24, mood="clean cinematic"),
            entities=entities,
            camera=CameraSpec(shots=shots),
            render=RenderSpec(resolution=[1280, 720], format="mp4", quality="preview"),
        )
        dag = self._common_dag(include_animation=False)
        risks = [
            {"type": "mvp_scope", "message": "Gallery demo uses curated local static assets and mock/UE wrapper execution."}
        ]
        return task, dag, risks

    def _plan_zebra(self, prompt: str, project_id: str) -> tuple[TaskSpec, Dag, list[dict[str, Any]]]:
        lowered = prompt.lower()
        environment = "park" if any(key in lowered for key in ["park", "公园"]) else "desert"
        floor_target = "park_path" if environment == "park" else "desert_floor"
        path_start = list(CITYPARK_PATH_START) if environment == "park" else [-600, 0, 0]
        path_end = list(CITYPARK_PATH_END) if environment == "park" else [600, 0, 0]
        camera_direction = [0.18, -1.0, -0.10] if environment == "park" else [0.8, -1.0, -0.24]
        duration = 5.25 if environment == "park" else 8
        animation = (
            {
                "type": "walk",
                "asset_query": "zebra walk turn animation",
                "preferred_asset_path": "/Game/AfricanAnimalsPack/Zebra/Animations/ANIM_Zebra_WalkTurnR",
                "reuse_actor_name": "ANIM_Zebra_WalkTurnR",
                "reference_yaw": 0.0,
                "start_time": 0,
                "end_time": duration,
            }
            if environment == "park"
            else {"type": "run", "start_time": 0, "end_time": duration}
        )
        entity = EntitySpec(
            id="zebra_01",
            semantic_type="zebra",
            asset_query="zebra animal quadruped textured",
            asset_constraints=AssetConstraints(asset_type="skeletal_mesh", must_be_animated=True, required_tags=["zebra", "animal"]),
            spatial=SpatialSpec(relation="on_ground", target=floor_target, start=path_start, end=path_end, approx_location=path_start),
            animation=animation,
        )
        shot = ShotSpec(
            id="shot_001",
            type="hitchcock_zoom",
            target="zebra_01",
            start_time=0,
            end_time=duration,
            focal_length_start=45 if environment == "park" else 32,
            metadata={
                "distance_start": 2000,
                "distance_end": 1350,
                "direction": camera_direction,
                "reference_sequence_path": CITYPARK_REFERENCE_SEQUENCE_PATH,
                "reference_capture_path": CITYPARK_REFERENCE_CAPTURE_PATH,
                "reference_capture_start_frame": CITYPARK_REFERENCE_CAPTURE_START_FRAME,
                "reference_capture_end_frame": CITYPARK_REFERENCE_CAPTURE_END_FRAME,
                "reference_output_fps": 30,
                "reference_output_end_frame": 166,
                "reference_camera_path": dict(CITYPARK_REFERENCE_CAMERA_PATH),
            }
            if environment == "park"
            else {"distance_start": 1150, "distance_end": 720, "direction": camera_direction},
        )
        task = TaskSpec(
            task_id=stable_task_id(prompt, "task_zebra"),
            project_id=project_id,
            scene=SceneSpec(name=f"{environment}_zebra_hitchcock", environment=environment, duration_sec=duration, fps=24, mood="sunlit park" if environment == "park" else "warm dusk"),
            entities=[entity],
            camera=CameraSpec(shots=[shot]),
            render=RenderSpec(resolution=[1280, 720], format="mp4", quality="preview"),
        )
        dag = self._common_dag(include_animation=True, include_transform=True)
        risks = [{"type": "animation_scope", "message": "Skeletal animation is represented in IR; mock mode verifies timeline structure."}]
        return task, dag, risks

    def _plan_large_building(self, prompt: str, project_id: str) -> tuple[TaskSpec, Dag, list[dict[str, Any]]]:
        car = EntitySpec(
            id="car_01",
            semantic_type="car",
            asset_query="parked car vehicle",
            asset_constraints=AssetConstraints(asset_type="static_mesh", required_tags=["car", "vehicle"]),
            spatial=SpatialSpec(relation="on_ground", target="building_floor", approx_location=[0, 120, 0]),
        )
        shots = [
            ShotSpec(id="shot_001", type="wide_aerial", target="car_01", start_time=0, end_time=4, focal_length=24),
            ShotSpec(id="shot_002", type="dolly_in", target="car_01", start_time=4, end_time=9, focal_length=30),
        ]
        task = TaskSpec(
            task_id=stable_task_id(prompt, "task_building"),
            project_id=project_id,
            scene=SceneSpec(name="large_building_push_in", environment="large_building", duration_sec=9, fps=24, mood="golden exterior reveal"),
            entities=[car],
            camera=CameraSpec(shots=shots),
            render=RenderSpec(resolution=[1280, 720], format="mp4", quality="preview"),
        )
        return task, self._common_dag(), [{"type": "asset_need", "message": "Requires a vehicle asset and a large building or hall environment asset."}]

    def _plan_city_rooftop(self, prompt: str, project_id: str) -> tuple[TaskSpec, Dag, list[dict[str, Any]]]:
        human = EntitySpec(
            id="phone_actor_01",
            semantic_type="human",
            asset_query="human person phone call",
            asset_constraints=AssetConstraints(asset_type="skeletal_mesh", must_be_animated=True, required_tags=["human", "phone"]),
            spatial=SpatialSpec(relation="on_ground", target="rooftop_floor", approx_location=[80, 40, 0]),
            animation={"type": "phone_call", "start_time": 0, "end_time": 10},
        )
        shots = [
            ShotSpec(
                id="shot_001",
                type="hitchcock_zoom",
                target="phone_actor_01",
                start_time=0,
                end_time=5,
                focal_length_start=35,
                metadata={"distance_start": 850, "distance_end": 320},
            ),
            ShotSpec(
                id="shot_002",
                type="orbit",
                target="phone_actor_01",
                start_time=5,
                end_time=10,
                focal_length=32,
                metadata={"radius": 560, "height": 170, "start_angle": -145, "end_angle": -35},
            ),
        ]
        task = TaskSpec(
            task_id=stable_task_id(prompt, "task_city_rooftop"),
            project_id=project_id,
            scene=SceneSpec(name="city_rooftop_phone_orbit", environment="city_rooftop", duration_sec=10, fps=24, mood="backlit skyline"),
            entities=[human],
            camera=CameraSpec(shots=shots),
            render=RenderSpec(resolution=[1280, 720], format="mp4", quality="preview"),
        )
        return task, self._common_dag(include_animation=True), [{"type": "shot_complexity", "message": "Combines Hitchcock zoom with an orbit shot around a rooftop subject."}]

    def _plan_river_statues(self, prompt: str, project_id: str) -> tuple[TaskSpec, Dag, list[dict[str, Any]]]:
        entities = [
            EntitySpec(
                id="statue_above_water",
                semantic_type="statue",
                asset_query="classical statue",
                asset_constraints=AssetConstraints(asset_type="static_mesh", required_tags=["statue", "sculpture"]),
                spatial=SpatialSpec(relation="on_ground", target="river_shallow", approx_location=[-120, 40, 0]),
            ),
            EntitySpec(
                id="statue_underwater",
                semantic_type="statue",
                asset_query="classical statue underwater",
                asset_constraints=AssetConstraints(asset_type="static_mesh", required_tags=["statue", "sculpture"]),
                spatial=SpatialSpec(relation="underwater", target="river_bed", approx_location=[190, 80, -80]),
            ),
        ]
        shots = [
            ShotSpec(id="shot_001", type="static_shot", target="statue_above_water", start_time=0, end_time=5, focal_length=35, metadata={"focus_role": "above_water"}),
            ShotSpec(id="shot_002", type="dolly_in", target="statue_underwater", start_time=5, end_time=10, focal_length=28, metadata={"focus_role": "underwater"}),
        ]
        task = TaskSpec(
            task_id=stable_task_id(prompt, "task_river"),
            project_id=project_id,
            scene=SceneSpec(name="river_statue_focus_transition", environment="river", duration_sec=10, fps=24, mood="clear water daylight"),
            entities=entities,
            camera=CameraSpec(shots=shots),
            render=RenderSpec(resolution=[1280, 720], format="mp4", quality="preview"),
        )
        return task, self._common_dag(), [{"type": "focus_transition", "message": "Focus transition is represented by ordered shots and target metadata in this stage."}]

    def _common_dag(self, include_animation: bool = False, include_transform: bool = False) -> Dag:
        nodes = [
            DagNode(id="env.setup", agent="EnvAgent"),
            DagNode(id="asset.retrieve", agent="EntityAgent"),
            DagNode(id="entity.spawn", agent="EntityAgent"),
            DagNode(id="spatial.place", agent="SpatialAgent"),
            DagNode(id="seq.init", agent="SeqAgent"),
            DagNode(id="seq.camera", agent="CamAgent"),
            DagNode(id="seq.camera_cut", agent="SeqAgent"),
            DagNode(id="render.preview", agent="RenderAgent"),
        ]
        edges: list[tuple[str, str]] = [
            ("asset.retrieve", "env.setup"),
            ("asset.retrieve", "entity.spawn"),
            ("env.setup", "entity.spawn"),
            ("entity.spawn", "spatial.place"),
            ("spatial.place", "seq.init"),
            ("seq.init", "seq.camera"),
            ("seq.camera", "seq.camera_cut"),
            ("seq.camera_cut", "render.preview"),
        ]
        if include_transform:
            nodes.insert(6, DagNode(id="seq.transform", agent="TransAgent"))
            edges.append(("seq.init", "seq.transform"))
            edges.append(("seq.transform", "seq.camera"))
            edges.append(("seq.transform", "seq.camera_cut"))
        if include_animation:
            insert_at = 7 if include_transform else 6
            nodes.insert(insert_at, DagNode(id="seq.animation", agent="AnimAgent"))
            edges.append(("seq.init", "seq.animation"))
            edges.append(("seq.animation", "seq.camera_cut"))
            if include_transform:
                edges.append(("seq.transform", "seq.animation"))
        return Dag(nodes=nodes, edges=edges)
