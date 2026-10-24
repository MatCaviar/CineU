from __future__ import annotations

from dataclasses import dataclass
from math import atan2, degrees, sqrt
from typing import Any

from .schemas import AssetMetadata, EntitySpec, Transform


@dataclass(frozen=True)
class AABB:
    center: tuple[float, float, float]
    extent: tuple[float, float, float]

    def intersects(self, other: "AABB") -> bool:
        return all(abs(self.center[i] - other.center[i]) <= (self.extent[i] + other.extent[i]) for i in range(3))


def extent_from_asset(asset: AssetMetadata) -> list[float]:
    extent = asset.bounds_cm.get("extent", [50.0, 50.0, 50.0])
    if len(extent) != 3:
        return [50.0, 50.0, 50.0]
    return [float(x) for x in extent]


def yaw_to_face(src: list[float], dst: list[float]) -> float:
    dx, dy = dst[0] - src[0], dst[1] - src[1]
    return degrees(atan2(dy, dx))


class SpatialSolver:
    """Deterministic AABB placement solver for the demo asset set."""

    def solve(self, entities: list[EntitySpec], asset_map: dict[str, AssetMetadata], environment: str) -> list[dict[str, Any]]:
        placements: list[dict[str, Any]] = []
        occupied: list[AABB] = []
        for entity in entities:
            asset = asset_map[entity.id]
            extent = extent_from_asset(asset)
            spatial = entity.spatial
            loc = list(spatial.approx_location or [0.0, 0.0, 0.0])
            rot = [0.0, 0.0, 0.0]
            scale = [1.0, 1.0, 1.0]

            if spatial.relation == "on_wall":
                wall = spatial.target or "left_wall"
                height = spatial.height_cm if spatial.height_cm is not None else 180.0
                if wall == "left_wall":
                    loc = [-500.0 + extent[0], loc[1], height]
                    rot = [0.0, 0.0, 0.0]
                elif wall == "right_wall":
                    loc = [500.0 - extent[0], loc[1], height]
                    rot = [0.0, 0.0, 180.0]
                else:
                    loc = [loc[0], 500.0 - extent[0], height]
                    rot = [0.0, 0.0, -90.0]
            elif spatial.relation == "on_ground":
                # UE actor origins vary by asset. For this research system, we use
                # center-based bounds for static meshes; skeletal characters usually
                # have a root near the feet and should keep that origin on ground.
                if spatial.start:
                    loc = list(spatial.start)
                ground_z = float(loc[2]) if len(loc) > 2 else 0.0
                loc[2] = ground_z if asset.type == "skeletal_mesh" else ground_z + extent[2]
                if spatial.end:
                    rot[2] = yaw_to_face(loc, spatial.end)
            else:
                loc[2] = max(loc[2], extent[2])

            box = AABB(center=(loc[0], loc[1], loc[2]), extent=(extent[0], extent[1], extent[2]))
            # Lightweight relaxation: shift along Y until no AABB intersection.
            relax_steps = 0
            while any(box.intersects(o) for o in occupied) and relax_steps < 20:
                loc[1] += extent[1] * 2.2
                box = AABB(center=(loc[0], loc[1], loc[2]), extent=(extent[0], extent[1], extent[2]))
                relax_steps += 1
            occupied.append(box)
            placements.append(
                {
                    "actor_name": entity.id,
                    "transform": Transform(location=loc, rotation=rot, scale=scale).model_dump(mode="json"),
                    "relation": spatial.relation,
                    "target": spatial.target,
                    "bounds_extent": extent,
                    "relax_steps": relax_steps,
                }
            )
        return placements
