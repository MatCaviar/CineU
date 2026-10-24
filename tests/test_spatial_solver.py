from cineu_demo.schemas import AssetConstraints, AssetMetadata, EntitySpec, SpatialSpec
from cineu_demo.spatial import SpatialSolver


def test_left_wall_art_keeps_panel_flat_against_x_wall():
    entity = EntitySpec(
        id="painting_01",
        semantic_type="painting",
        asset_query="framed modern painting",
        asset_constraints=AssetConstraints(asset_type="static_mesh"),
        spatial=SpatialSpec(relation="on_wall", target="left_wall", approx_location=[-480, 0, 180], height_cm=180),
    )
    asset = AssetMetadata(
        asset_id="asset_gallery_painting_001",
        name="Framed Modern Painting",
        ue_path="/Game/CineU/Assets/Gallery/SM_FramedPainting",
        type="static_mesh",
        bounds_cm={"extent": [6, 70, 45]},
    )

    placement = SpatialSolver().solve([entity], {"painting_01": asset}, "gallery")[0]

    assert placement["transform"]["location"] == [-494.0, 0.0, 180.0]
    assert placement["transform"]["rotation"] == [0.0, 0.0, 0.0]


def test_back_wall_art_uses_mesh_thickness_for_wall_offset():
    entity = EntitySpec(
        id="painting_01",
        semantic_type="painting",
        asset_query="framed modern painting",
        asset_constraints=AssetConstraints(asset_type="static_mesh"),
        spatial=SpatialSpec(relation="on_wall", target="back_wall", approx_location=[0, 480, 180], height_cm=180),
    )
    asset = AssetMetadata(
        asset_id="asset_gallery_painting_001",
        name="Framed Modern Painting",
        ue_path="/Game/CineU/Assets/Gallery/SM_FramedPainting",
        type="static_mesh",
        bounds_cm={"extent": [6, 70, 45]},
    )

    placement = SpatialSolver().solve([entity], {"painting_01": asset}, "gallery")[0]

    assert placement["transform"]["location"] == [0.0, 494.0, 180.0]
    assert placement["transform"]["rotation"] == [0.0, 0.0, -90.0]


def test_on_ground_skeletal_mesh_uses_asset_origin_at_ground():
    entity = EntitySpec(
        id="zebra_01",
        semantic_type="zebra",
        asset_query="zebra animal quadruped",
        asset_constraints=AssetConstraints(asset_type="skeletal_mesh"),
        spatial=SpatialSpec(relation="on_ground", target="park_path", start=[-600, 0, 0], end=[600, 0, 0]),
    )
    asset = AssetMetadata(
        asset_id="asset_zebra",
        name="Zebra",
        ue_path="/Game/AfricanAnimalsPack/Zebra/Meshes/SK_Zebra",
        type="skeletal_mesh",
        bounds_cm={"extent": [115, 35, 85]},
    )

    placement = SpatialSolver().solve([entity], {"zebra_01": asset}, "park")[0]

    assert placement["transform"]["location"] == [-600.0, 0.0, 0.0]
    assert placement["transform"]["rotation"] == [0.0, 0.0, 0.0]


def test_on_ground_skeletal_mesh_uses_explicit_level_ground_height():
    entity = EntitySpec(
        id="zebra_01",
        semantic_type="zebra",
        asset_query="zebra animal quadruped",
        asset_constraints=AssetConstraints(asset_type="skeletal_mesh"),
        spatial=SpatialSpec(relation="on_ground", target="park_path", start=[-87000.0, 16400.0, 600.0], end=[-87000.0, 20600.0, 600.0]),
    )
    asset = AssetMetadata(
        asset_id="asset_zebra",
        name="Zebra",
        ue_path="/Game/AfricanAnimalsPack/Zebra/Meshes/SK_Zebra",
        type="skeletal_mesh",
        bounds_cm={"extent": [115, 35, 85]},
    )

    placement = SpatialSolver().solve([entity], {"zebra_01": asset}, "park")[0]

    assert placement["transform"]["location"] == [-87000.0, 16400.0, 600.0]
    assert placement["transform"]["rotation"] == [0.0, 0.0, 90.0]
