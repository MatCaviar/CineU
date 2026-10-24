from pathlib import Path

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[1] / "unreal_project" / "Plugins" / "CineUDemo" / "Content" / "Python"


def test_world_ops_imports_outside_unreal(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    assert cineu_world_ops.unreal is None
    assert cineu_world_ops._fallback_shape_for_actor({"semantic_type": "painting", "asset_type": "static_mesh"}) == "cube"
    assert cineu_world_ops._fallback_shape_for_actor({"semantic_type": "sculpture", "asset_type": "static_mesh"}) == "sphere"
    assert cineu_world_ops._fallback_shape_for_actor({"semantic_type": "zebra", "asset_type": "skeletal_mesh"}) == "capsule"


def test_visual_profile_for_fallback_actor_semantics(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    painting = cineu_world_ops._visual_profile_for_actor({"semantic_type": "painting", "asset_type": "static_mesh"})
    sculpture = cineu_world_ops._visual_profile_for_actor({"semantic_type": "sculpture", "asset_type": "static_mesh"})
    zebra = cineu_world_ops._visual_profile_for_actor({"semantic_type": "zebra", "asset_type": "skeletal_mesh"})

    assert painting["shape"] == "cube"
    assert painting["color"] == [0.035, 0.032, 0.03]
    assert painting["roughness"] <= 0.45
    assert sculpture["shape"] == "sphere"
    assert sculpture["color"] == [0.88, 0.86, 0.82]
    assert zebra["shape"] == "capsule"
    assert zebra["color"] == [0.98, 0.95, 0.86]
    assert zebra["material_label"] == "zebra_generated_stripes"
    assert zebra["texture_path"] == "/Game/CineU/Generated/Textures/T_CineU_Zebra_Stripes"
    assert zebra["texture_tiling"] == [1.0, 1.0]
    assert zebra["emissive_texture"] is True
    assert zebra["emissive_strength"] == 0.0
    assert zebra["used_with_skeletal_mesh"] is True
    assert cineu_world_ops._native_material_paths_for_spec({"semantic_type": "zebra"}) == []
    asset_zebra = cineu_world_ops._visual_profile_for_actor(
        {
            "semantic_type": "zebra",
            "asset_path": "/Game/AfricanAnimalsPack/Zebra/Meshes/SK_Zebra",
            "source_type": "ue_project_content",
            "asset_type": "skeletal_mesh",
        }
    )
    assert asset_zebra["material_label"] == "zebra_asset_stripes"
    assert asset_zebra["texture_path"] == "/Game/AfricanAnimalsPack/Zebra/Textures/T_Zebra_BaseColor"
    assert asset_zebra["emissive_texture"] is True
    assert asset_zebra["used_with_skeletal_mesh"] is True
    assert cineu_world_ops._native_material_paths_for_spec(
        {
            "semantic_type": "zebra",
            "asset_path": "/Game/AfricanAnimalsPack/Zebra/Meshes/SK_Zebra",
            "source_type": "ue_project_content",
        }
    ) == []


def test_generated_zebra_stripe_bmp_is_high_contrast_nonuniform(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    target = tmp_path / "zebra_stripes.bmp"
    cineu_world_ops._write_generated_zebra_stripe_bmp(target, width=96, height=64)
    data = target.read_bytes()

    assert data[:2] == b"BM"
    pixel_data = data[54:]
    assert min(pixel_data) <= 12
    assert max(pixel_data) >= 230


def test_gallery_surface_profiles_match_template_style(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    floor = cineu_world_ops._visual_profile_for_surface("CineU_Gallery_Floor")
    wall = cineu_world_ops._visual_profile_for_surface("CineU_Gallery_BackWall")

    assert floor["color"] == [0.055, 0.052, 0.048]
    assert floor["material_label"] == "polished_dark_floor"
    assert floor["roughness"] <= 0.22
    assert floor["specular"] >= 0.65
    assert wall["color"] == [0.92, 0.9, 0.86]
    assert wall["material_label"] == "warm_gallery_wall"
    assert wall.get("emissive_strength", 0.0) == 0.0
    ceiling = cineu_world_ops._visual_profile_for_surface("CineU_Gallery_Ceiling")
    assert ceiling["material_label"] == "warm_gallery_wall"
    stripe = cineu_world_ops._visual_profile_for_surface("CineU_Gallery_ArtStripe_painting_01_00")
    assert stripe["material_label"] == "gallery_art_stripe"
    brush_light = cineu_world_ops._visual_profile_for_surface("CineU_Gallery_ArtBrushLight_painting_01_00")
    brush_shadow = cineu_world_ops._visual_profile_for_surface("CineU_Gallery_ArtBrushShadow_painting_01_00")
    brush_warm = cineu_world_ops._visual_profile_for_surface("CineU_Gallery_ArtBrushWarm_painting_01_00")
    flow_light = cineu_world_ops._visual_profile_for_surface("CineU_Gallery_ArtFlowLight_painting_02_00")
    flow_shadow = cineu_world_ops._visual_profile_for_surface("CineU_Gallery_ArtFlowShadow_painting_02_00")
    assert brush_light["material_label"] == "gallery_art_brush_light"
    assert brush_light["color"][0] >= 0.92
    assert brush_shadow["material_label"] == "gallery_art_brush_shadow"
    assert brush_shadow["color"][0] <= 0.18
    assert brush_warm["material_label"] == "gallery_art_brush_warm"
    assert flow_light["material_label"] == "gallery_art_flow_light"
    assert flow_light["color"][0] >= 0.96
    assert flow_shadow["material_label"] == "gallery_art_flow_shadow"
    hero_backdrop = cineu_world_ops._visual_profile_for_surface("CineU_Gallery_HeroBackdrop_painting_02")
    assert hero_backdrop["material_label"] == "gallery_art_dark"
    sun_patch = cineu_world_ops._visual_profile_for_surface("CineU_Gallery_LightPatch_00")
    assert sun_patch["material_label"] == "gallery_sun_patch"
    assert sun_patch["emissive_strength"] >= 1.5
    bench = cineu_world_ops._visual_profile_for_surface("CineU_Gallery_Bench")
    assert bench["material_label"] == "gallery_wood_bench"
    assert bench["color"] == [0.52, 0.32, 0.14]
    glass = cineu_world_ops._visual_profile_for_surface("CineU_Gallery_WindowPane_Right_00")
    assert glass["material_label"] == "gallery_glass_daylight"
    assert glass["specular"] >= 0.7
    assert glass["emissive_strength"] >= 0.4
    assert 0.2 <= glass["opacity"] <= 0.45
    frame = cineu_world_ops._visual_profile_for_surface("CineU_Gallery_EntryFrame_Left")
    assert frame["material_label"] == "painted_white_frame"
    timber = cineu_world_ops._visual_profile_for_surface("CineU_Gallery_CeilingBeam_Long_00")
    assert timber["material_label"] == "gallery_roof_timber"
    walkway = cineu_world_ops._visual_profile_for_surface("CineU_Gallery_ExteriorWalkway")
    lawn = cineu_world_ops._visual_profile_for_surface("CineU_Gallery_ExteriorLawn_Left")
    facade = cineu_world_ops._visual_profile_for_surface("CineU_Gallery_ExteriorFacade_Left")
    assert walkway["material_label"] == "gallery_exterior_walkway"
    assert lawn["material_label"] == "gallery_exterior_lawn"
    assert facade["material_label"] == "gallery_exterior_facade"


def test_park_surface_profiles_use_controlled_preview_emissive_without_neon(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    path = cineu_world_ops._visual_profile_for_surface("CineU_Park_Path")
    grass = cineu_world_ops._visual_profile_for_surface("CineU_LevelPark_GrassFill")
    water = cineu_world_ops._visual_profile_for_surface("CineU_LevelPark_Water_Right")
    bridge = cineu_world_ops._park_level_actor_profile("CineU_LevelPark_BridgeSurface_00")
    decal = cineu_world_ops._visual_profile_for_surface("CineU_LevelPark_PathDecal_00")
    loaded_path = cineu_world_ops._park_level_actor_profile("SM_ParkPath1_2 (HISMA)")
    forest = cineu_world_ops._visual_profile_for_surface("CineU_LevelPark_ForestBackdrop")
    canopy = cineu_world_ops._visual_profile_for_surface("CineU_LevelPark_Tree_CanopyMesh_00")
    railing = cineu_world_ops._visual_profile_for_surface("CineU_LevelPark_Railing_Left_00")

    assert path["material_label"] == "park_path_warm_stone"
    assert path["color"][0] >= 0.70
    assert path["texture_path"] == "/Game/CityPark/Textures/Road/T_Sidewalk02_D"
    assert path["texture_tiling"] == [8.0, 24.0]
    assert path["specular"] <= 0.12
    assert 0.18 <= path.get("emissive_strength", 0.0) <= 0.30
    assert grass["material_label"] == "park_grass"
    assert grass["color"][1] >= 0.48
    assert grass["texture_path"] == "/Game/CityPark/Textures/Flora/Grass/T_Grass07_D"
    assert grass["texture_tiling"] == [14.0, 28.0]
    assert grass["specular"] <= 0.04
    assert 0.34 <= grass.get("emissive_strength", 0.0) <= 0.50
    assert forest["material_label"] == "park_tree_canopy"
    assert forest["color"][1] >= 0.52
    assert 0.18 <= forest.get("emissive_strength", 0.0) <= 0.32
    assert canopy["material_label"] == "park_tree_canopy"
    assert canopy["color"][1] >= 0.52
    assert 0.18 <= canopy.get("emissive_strength", 0.0) <= 0.32
    assert water["material_label"] == "river_water"
    assert water["specular"] >= 0.65
    assert water["color"][2] >= 0.94
    assert 0.55 <= water["opacity"] <= 0.7
    assert 0.25 <= water["emissive_strength"] <= 0.42
    assert bridge["material_label"] == "citypark_warm_bridge"
    assert bridge["roughness"] >= 0.5
    assert railing["material_label"] == "citypark_dark_railing"
    assert railing["color"][0] <= 0.24
    assert railing["metallic"] <= 0.20
    assert decal["material_label"] == "park_path_decal"
    assert decal["color"][0] < path["color"][0]
    assert loaded_path is None


def test_gallery_environment_adds_template_bench(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    spawned = {}

    class Actor:
        def __init__(self, label=""):
            self.label = label

        def get_actor_label(self):
            return self.label

        def set_actor_label(self, label):
            self.label = label

    class FakeLevelLibrary:
        @staticmethod
        def get_editor_world():
            return object()

        @staticmethod
        def get_all_level_actors():
            return []

        @staticmethod
        def spawn_actor_from_class(actor_class, vector):
            return Actor()

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary
        DirectionalLight = object
        SkyLight = object

        @staticmethod
        def Vector(*values):
            return values

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_world_ops, "_spawn_if_missing", lambda label, shape, location, scale, rotation=None: spawned.setdefault(label, {"location": location, "scale": scale}))

    cineu_world_ops.setup_environment({"level_name": "LVL_test", "environment": "gallery"})

    assert "CineU_Gallery_Bench" in spawned
    assert "CineU_Gallery_Ceiling" not in spawned
    assert "CineU_Gallery_CeilingPanel" in spawned
    assert "CineU_Gallery_LightPatch_00" in spawned
    assert "CineU_Gallery_LightPatch_01" in spawned
    assert spawned["CineU_Gallery_LightPatch_00"]["scale"][1] >= 0.8
    assert spawned["CineU_Gallery_LightPatch_00"]["scale"][2] >= 0.25
    assert "CineU_Gallery_Bench_LegLeft" in spawned
    assert "CineU_Gallery_Bench_LegRight" in spawned
    assert -160 <= spawned["CineU_Gallery_Bench"]["location"][1] <= -100
    assert 2.0 <= spawned["CineU_Gallery_Bench"]["scale"][0] <= 2.4
    assert spawned["CineU_Gallery_BackWall"]["location"][2] >= 400
    assert spawned["CineU_Gallery_BackWall"]["scale"][2] >= 8


def test_gallery_environment_adds_world_template_architecture(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    spawned = {}

    class Actor:
        def __init__(self, label=""):
            self.label = label

        def get_actor_label(self):
            return self.label

        def set_actor_label(self, label):
            self.label = label

    class FakeLevelLibrary:
        @staticmethod
        def get_editor_world():
            return object()

        @staticmethod
        def get_all_level_actors():
            return []

        @staticmethod
        def spawn_actor_from_class(actor_class, vector):
            return Actor()

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary
        DirectionalLight = object
        SkyLight = object

        @staticmethod
        def Vector(*values):
            return values

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(
        cineu_world_ops,
        "_spawn_if_missing",
        lambda label, shape, location, scale, rotation=None: spawned.setdefault(label, {"location": location, "scale": scale, "rotation": rotation}),
    )

    cineu_world_ops.setup_environment({"level_name": "LVL_test", "environment": "gallery"})

    assert "CineU_Gallery_EntryGlass_00" in spawned
    assert "CineU_Gallery_EntryFrame_Left" in spawned
    assert "CineU_Gallery_EntryFrame_Right" in spawned
    assert "CineU_Gallery_SkylightPane_00" in spawned
    assert "CineU_Gallery_ExteriorWalkway" in spawned
    assert "CineU_Gallery_ExteriorLawn_Left" in spawned
    assert "CineU_Gallery_ExteriorFacade_Left" in spawned
    ceiling_beams = [label for label in spawned if label.startswith("CineU_Gallery_CeilingBeam_")]
    window_panes = [label for label in spawned if label.startswith("CineU_Gallery_WindowPane_")]
    window_mullions = [label for label in spawned if label.startswith("CineU_Gallery_WindowMullion_")]
    assert len(ceiling_beams) >= 8
    assert len(window_panes) >= 5
    assert len(window_mullions) >= 6
    assert spawned["CineU_Gallery_CeilingBeam_Long_00"]["location"][2] >= 720
    assert max(spawned["CineU_Gallery_CeilingBeam_Long_00"]["scale"]) >= 8.0
    assert spawned["CineU_Gallery_WindowPane_Right_00"]["location"][0] > 480
    assert spawned["CineU_Gallery_EntryGlass_00"]["location"][1] < -480
    assert spawned["CineU_Gallery_ExteriorWalkway"]["location"][1] < -760
    assert spawned["CineU_Gallery_ExteriorLawn_Left"]["location"][0] < -250


def test_environment_setup_spawns_imported_environment_mesh(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    spawned_objects = []

    class Actor:
        def __init__(self):
            self.label = ""

        def set_actor_label(self, label):
            self.label = label

        def set_actor_scale3d(self, scale):
            self.scale = scale

    class FakeLevelLibrary:
        @staticmethod
        def get_editor_world():
            return object()

        @staticmethod
        def get_all_level_actors():
            return []

        @staticmethod
        def spawn_actor_from_object(asset, vector):
            actor = Actor()
            spawned_objects.append({"asset": asset, "location": vector, "actor": actor})
            return actor

    class FakeAssetLibrary:
        @staticmethod
        def load_asset(path):
            if path == "/Game/CineU/Imported/fab_local/park_path_environment":
                return {"asset_path": path}
            return None

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary
        EditorAssetLibrary = FakeAssetLibrary

        @staticmethod
        def Vector(*values):
            return values

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)
    spawned_labels = []
    monkeypatch.setattr(cineu_world_ops, "_spawn_if_missing", lambda label, *args, **kwargs: spawned_labels.append(label))
    monkeypatch.setattr(cineu_world_ops, "_spawn_light_if_missing", lambda *args, **kwargs: None)

    result = cineu_world_ops.setup_environment(
        {
            "level_name": "LVL_test",
            "environment": "park",
            "environment_asset": {
                "asset_id": "asset_fab_local_park_path_environment",
                "ue_path": "/Game/CineU/Imported/fab_local/park_path_environment",
                "bounds_cm": {"extent": [900, 900, 120]},
            },
        }
    )

    assert spawned_objects
    assert spawned_objects[0]["actor"].label == "CineU_EnvironmentAsset_asset_fab_local_park_path_environment"
    assert result["environment_asset"]["asset_id"] == "asset_fab_local_park_path_environment"
    assert result["support_surfaces"]["park_path"]["environment_asset_type"] == "asset"
    assert not any(label.startswith("CineU_Park_") for label in spawned_labels)


def test_environment_asset_spawn_fits_large_mesh_as_background(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    class Actor:
        def __init__(self):
            self.label = ""
            self.scale = None
            self.location = None

        def set_actor_label(self, label):
            self.label = label

        def set_actor_scale3d(self, scale):
            self.scale = scale

        def set_actor_location(self, vector, sweep, teleport):
            self.location = vector

        def get_actor_bounds(self, only_colliding_components=False):
            return ([0, 0, 0], [1715.0, 3905.0, 757.0])

    actor = Actor()

    class FakeLevelLibrary:
        @staticmethod
        def get_all_level_actors():
            return []

        @staticmethod
        def spawn_actor_from_object(asset, vector):
            return actor

    class FakeAssetLibrary:
        @staticmethod
        def load_asset(path):
            return object()

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary
        EditorAssetLibrary = FakeAssetLibrary

        @staticmethod
        def Vector(*values):
            return list(values)

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)

    result = cineu_world_ops._spawn_environment_asset_if_available(
        {
            "asset_id": "asset_local_file_hillpath_lo",
            "ue_path": "/Game/CineU/Imported/local_file/hillpath_lo",
            "type": "static_mesh",
            "semantic_tags": ["park", "environment"],
        }
    )

    assert result["status"] == "spawned"
    assert actor.scale[0] < 0.4
    assert actor.location[2] < -150


def test_environment_asset_level_loads_unreal_map(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    loaded = []

    class FakeLevelLibrary:
        @staticmethod
        def load_level(path):
            loaded.append(path)
            return True

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)

    result = cineu_world_ops._spawn_environment_asset_if_available(
        {
            "asset_id": "asset_ue_project_content_citypark_maps_showcase",
            "ue_path": "/Game/CityPark/Maps/Showcase",
            "type": "level",
            "semantic_tags": ["park", "environment"],
        }
    )

    assert loaded == ["/Game/CityPark/Maps/Showcase"]
    assert result["status"] == "level_loaded"
    assert result["asset_path"] == "/Game/CityPark/Maps/Showcase"


def test_environment_asset_spawn_applies_background_fit_without_bounds_api(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    class Actor:
        def __init__(self):
            self.scale = None
            self.location = None

        def set_actor_label(self, label):
            self.label = label

        def set_actor_scale3d(self, scale):
            self.scale = scale

        def set_actor_location(self, vector, sweep, teleport):
            self.location = vector

    actor = Actor()

    class FakeLevelLibrary:
        @staticmethod
        def get_all_level_actors():
            return []

        @staticmethod
        def spawn_actor_from_object(asset, vector):
            return actor

    class FakeAssetLibrary:
        @staticmethod
        def load_asset(path):
            return object()

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary
        EditorAssetLibrary = FakeAssetLibrary

        @staticmethod
        def Vector(*values):
            return list(values)

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)

    result = cineu_world_ops._spawn_environment_asset_if_available(
        {
            "asset_id": "asset_local_file_hillpath_lo",
            "ue_path": "/Game/CineU/Imported/local_file/hillpath_lo",
            "type": "static_mesh",
            "semantic_tags": ["park", "environment"],
        }
    )

    assert result["fit"]["method"] == "semantic_environment_background"
    assert actor.scale == [0.3, 0.3, 0.3]
    assert actor.location == [0.0, 0.0, -220.0]


def test_park_environment_requires_loaded_asset_first_level(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    spawned = {}

    class FakeLevelLibrary:
        @staticmethod
        def get_editor_world():
            return object()

        @staticmethod
        def get_all_level_actors():
            return []

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(
        cineu_world_ops,
        "_spawn_if_missing",
        lambda label, shape, location, scale, rotation=None: spawned.setdefault(label, {"shape": shape, "location": location, "scale": scale, "rotation": rotation}),
    )
    monkeypatch.setattr(cineu_world_ops, "_spawn_light_if_missing", lambda *args, **kwargs: None)
    monkeypatch.setattr(cineu_world_ops, "_spawn_environment_asset_if_available", lambda asset: None)

    with pytest.raises(RuntimeError, match="asset-first environment asset"):
        cineu_world_ops.setup_environment({"level_name": "LVL_test", "environment": "park"})

    assert spawned == {}


def test_park_level_environment_load_failure_does_not_fallback_to_generated_park(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    spawned = []

    class FakeLevelLibrary:
        @staticmethod
        def get_editor_world():
            return object()

        @staticmethod
        def get_all_level_actors():
            return []

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_world_ops, "_spawn_if_missing", lambda label, *args, **kwargs: spawned.append(label))
    monkeypatch.setattr(cineu_world_ops, "_spawn_light_if_missing", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        cineu_world_ops,
        "_spawn_environment_asset_if_available",
        lambda asset: {"status": "level_load_failed", "asset_path": asset["ue_path"]},
    )

    with pytest.raises(RuntimeError, match="level_load_failed"):
        cineu_world_ops.setup_environment(
            {
                "level_name": "LVL_test",
                "environment": "park",
                "environment_asset": {
                    "asset_id": "asset_ue_project_content_citypark_maps_showcase",
                    "ue_path": "/Game/CityPark/Maps/Showcase",
                    "type": "level",
                },
            }
        )

    assert not any(label.startswith("CineU_Park_") for label in spawned)


def test_park_level_environment_loads_before_world_template_path_dressing(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    events = []

    class FakeLevelLibrary:
        @staticmethod
        def get_editor_world():
            return object()

        @staticmethod
        def get_all_level_actors():
            return []

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_world_ops, "_spawn_if_missing", lambda label, *args, **kwargs: events.append(("spawn", label)))
    monkeypatch.setattr(cineu_world_ops, "_spawn_light_if_missing", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        cineu_world_ops,
        "_spawn_environment_asset_if_available",
        lambda asset: events.append(("load", asset["ue_path"])) or {"status": "level_loaded", "asset_path": asset["ue_path"]},
    )

    result = cineu_world_ops.setup_environment(
        {
            "level_name": "LVL_test",
            "environment": "park",
            "environment_asset": {
                "asset_id": "asset_ue_project_content_citypark_maps_showcase",
                "ue_path": "/Game/CityPark/Maps/Showcase",
                "type": "level",
            },
        }
    )

    assert result["environment_asset_result"]["status"] == "level_loaded"
    park_path = result["support_surfaces"]["park_path"]
    assert park_path["environment_asset_type"] == "level"
    assert park_path["anchor_actor"] == "InstancedFoliageActor2"
    assert park_path["z"] == -630.004
    assert park_path["bounds"] == [5600.0, 6800.0, -12650.0, -11850.0]
    assert events == [("load", "/Game/CityPark/Maps/Showcase")]


def test_park_level_environment_passes_dressing_assets_to_level_backed_dressing(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    captured = []
    dressing_assets = [
        {
            "asset_id": "asset_ue_project_content_externalassets_twinmotion_vegetation_trees_xf_ficusbenjamina_sm_a_ficusbenjamina_lod0",
            "ue_path": "/Game/ExternalAssets/Twinmotion/Vegetation/Trees/XF_FicusBenjamina/SM_A_FicusBenjamina_LOD0",
        }
    ]

    class FakeLevelLibrary:
        @staticmethod
        def get_editor_world():
            return object()

        @staticmethod
        def get_all_level_actors():
            return []

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(
        cineu_world_ops,
        "_spawn_environment_asset_if_available",
        lambda asset: {"status": "level_loaded", "asset_path": asset["ue_path"]},
    )
    monkeypatch.setattr(
        cineu_world_ops,
        "_ensure_park_dressing",
        lambda level_backed=False, dressing_assets=None: captured.append((level_backed, dressing_assets)),
    )

    result = cineu_world_ops.setup_environment(
        {
            "level_name": "LVL_test",
            "environment": "park",
            "environment_asset": {
                "asset_id": "asset_ue_project_content_citypark_maps_showcase",
                "ue_path": "/Game/CityPark/Maps/Showcase",
                "type": "level",
            },
            "dressing_assets": dressing_assets,
        }
    )

    assert result["dressing_assets"] == dressing_assets
    assert captured == [(True, dressing_assets)]


def test_level_backed_park_dressing_skips_sky_backdrop(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    spawned = []
    lights = []
    removed_prefixes = []
    removed_defaults = []
    base_lighting = []
    cinematic_pass = []
    world_template_grade = []
    camera_clearance = []
    asset_accents = []

    monkeypatch.setattr(cineu_world_ops, "unreal", object())
    monkeypatch.setattr(cineu_world_ops, "_remove_default_scene_actors", lambda: removed_defaults.append("called"))
    monkeypatch.setattr(cineu_world_ops, "_ensure_base_lighting", lambda: base_lighting.append("called"))
    monkeypatch.setattr(cineu_world_ops, "_spawn_if_missing", lambda label, *args, **kwargs: spawned.append(label))
    monkeypatch.setattr(cineu_world_ops, "_spawn_light_if_missing", lambda label, *args, **kwargs: lights.append(label))
    monkeypatch.setattr(cineu_world_ops, "_remove_actors_with_label_prefixes", lambda prefixes: removed_prefixes.extend(prefixes) or [])
    monkeypatch.setattr(cineu_world_ops, "_hide_park_level_camera_occluders", lambda: camera_clearance.append("called") or ["SM_Bush1_03 (HISMA)"], raising=False)
    monkeypatch.setattr(cineu_world_ops, "_apply_level_backed_park_cinematic_pass", lambda: cinematic_pass.append("called") or {}, raising=False)
    monkeypatch.setattr(cineu_world_ops, "_spawn_level_backed_park_asset_accents", lambda: asset_accents.append("called"), raising=False)
    monkeypatch.setattr(
        cineu_world_ops,
        "_apply_level_backed_park_world_template_grade",
        lambda: world_template_grade.append("called") or {},
        raising=False,
    )
    monkeypatch.setattr(
        cineu_world_ops,
        "_style_loaded_park_level_actors",
        lambda: (_ for _ in ()).throw(AssertionError("level-backed park should not restyle native geometry")),
    )
    monkeypatch.setattr(
        cineu_world_ops,
        "_spawn_level_backed_park_supplement",
        lambda: (_ for _ in ()).throw(AssertionError("level-backed park should not spawn procedural supplements")),
    )
    monkeypatch.setattr(
        cineu_world_ops,
        "_spawn_level_backed_park_scenic_assets",
        lambda: (_ for _ in ()).throw(AssertionError("level-backed park should not spawn scenic fallback assets")),
    )

    cineu_world_ops.ensure_support_surfaces({"park_path": {"type": "ground", "environment_asset_type": "level"}})

    assert spawned == []
    assert lights == []
    assert removed_defaults == []
    assert base_lighting == []
    assert cinematic_pass == []
    assert camera_clearance == ["called"]
    assert asset_accents == ["called"]
    assert world_template_grade == ["called"]
    assert "CineU_Park_Path" in removed_prefixes
    assert "CineU_LevelPark_PathShrub_" in removed_prefixes
    assert "CineU_LevelPark_ForegroundWillow_" in removed_prefixes


def test_level_backed_park_world_template_grade_reuses_native_postprocess(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    class Settings:
        def __init__(self):
            self.properties = {}

        def set_editor_property(self, name, value):
            self.properties[name] = value

    class Actor:
        def __init__(self, label, class_name="PostProcessVolume"):
            self.label = label
            self.class_name = class_name
            self.settings = Settings()
            self.properties = {}

        def get_actor_label(self):
            return self.label

        def get_class(self):
            return type("ActorClass", (), {"get_name": lambda _self: self.class_name})()

        def get_editor_property(self, name):
            if name == "settings":
                return self.settings
            raise AttributeError(name)

        def set_editor_property(self, name, value):
            self.properties[name] = value

    native_postprocess = Actor("PostProcessVolumeMAIN")
    unrelated_postprocess = Actor("PostProcessVolumeFarField")
    light = Actor("Light Source", "DirectionalLight")

    class LinearColor:
        def __init__(self, r, g, b, a):
            self.values = (r, g, b, a)

    class Vector4:
        def __init__(self, x, y, z, w):
            self.values = (x, y, z, w)

    class FakeLevelLibrary:
        @staticmethod
        def get_all_level_actors():
            return [native_postprocess, unrelated_postprocess, light]

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary

    FakeUnreal.LinearColor = LinearColor
    FakeUnreal.Vector4 = Vector4

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)

    result = cineu_world_ops._apply_level_backed_park_world_template_grade()

    assert result == {"graded_post_process": ["PostProcessVolumeMAIN"]}
    assert native_postprocess.properties["unbound"] is True
    assert native_postprocess.properties["b_unbound"] is True
    assert native_postprocess.properties["priority"] == 20.0
    assert native_postprocess.properties["blend_weight"] == 1.0
    assert native_postprocess.settings.properties["auto_exposure_min_brightness"] == 1.0
    assert native_postprocess.settings.properties["auto_exposure_max_brightness"] == 1.0
    assert native_postprocess.settings.properties["auto_exposure_bias"] == 0.44
    assert native_postprocess.settings.properties["exposure_compensation"] == 0.44
    assert native_postprocess.settings.properties["bloom_intensity"] == 0.10
    assert native_postprocess.settings.properties["vignette_intensity"] == 0.01
    assert native_postprocess.settings.properties["scene_color_tint"].values == (0.99, 1.035, 1.01, 1.0)
    assert native_postprocess.settings.properties["color_saturation"].values == (1.03, 1.05, 1.03, 1.0)
    assert native_postprocess.settings.properties["color_gain"].values == (0.98, 1.06, 1.04, 1.0)
    assert native_postprocess.settings.properties["color_contrast"].values == (1.06, 1.05, 1.04, 1.0)
    assert native_postprocess.settings.properties["override_auto_exposure_bias"] is True
    assert native_postprocess.settings.properties["b_override_auto_exposure_bias"] is True
    assert native_postprocess.settings.properties["override_scene_color_tint"] is True
    assert native_postprocess.settings.properties["override_color_gain"] is True
    assert native_postprocess.settings.properties["override_color_contrast"] is True
    assert "priority" not in native_postprocess.settings.properties
    assert "blend_weight" not in native_postprocess.settings.properties
    assert "auto_exposure_bias" not in unrelated_postprocess.settings.properties


def test_level_backed_park_asset_accents_use_citypark_meshes_without_fallback(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    spawned_assets = []

    monkeypatch.setattr(cineu_world_ops, "unreal", object())
    monkeypatch.setattr(
        cineu_world_ops,
        "_spawn_mesh_asset_if_available",
        lambda label, asset_path, location, scale, rotation=None: spawned_assets.append((label, asset_path, location, scale, rotation)) or True,
    )
    monkeypatch.setattr(
        cineu_world_ops,
        "_spawn_if_missing",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("level-backed accents must not fall back to generated shapes")),
    )

    result = cineu_world_ops._spawn_level_backed_park_asset_accents()

    assert result == {
        "spawned_asset_accents": [
            "CineU_LevelPark_ForegroundWillow_Right_00",
            "CineU_LevelPark_ForegroundWillow_Right_01",
            "CineU_LevelPark_CanopyWillow_Right_00",
            "CineU_LevelPark_HangingIvy_Right_00",
            "CineU_LevelPark_HangingIvy_Right_01",
        ]
    }
    willow_assets = [(label, asset_path, scale) for label, asset_path, _, scale, _ in spawned_assets if "Willow" in label]
    assert all(asset_path == "/Game/CityPark/Meshes/Flora/Trees/SM_WeepingWillow01" for _, asset_path, _ in willow_assets)
    assert all(label.startswith(("CineU_LevelPark_ForegroundWillow_", "CineU_LevelPark_CanopyWillow_", "CineU_LevelPark_HangingIvy_")) for label, *_ in spawned_assets)
    right_side = [item for item in spawned_assets if item[0].startswith("CineU_LevelPark_ForegroundWillow_")]
    assert all(location[0] >= cineu_world_ops.CITYPARK_PATH_X + 800.0 for _, _, location, _, _ in right_side)
    assert all(location[1] <= -11800.0 for _, _, location, _, _ in right_side)
    assert all(0.12 <= scale[0] <= 0.16 for _, _, _, scale, _ in right_side)
    canopy = [item for item in spawned_assets if item[0] == "CineU_LevelPark_CanopyWillow_Right_00"]
    assert canopy
    assert cineu_world_ops.CITYPARK_PATH_X + 380.0 <= canopy[0][2][0] <= cineu_world_ops.CITYPARK_PATH_X + 620.0
    assert cineu_world_ops.CITYPARK_PATH_CENTER_Y - 480.0 <= canopy[0][2][1] <= cineu_world_ops.CITYPARK_PATH_CENTER_Y - 160.0
    assert 0.08 <= canopy[0][3][0] <= 0.18
    hanging_ivy = [item for item in spawned_assets if item[0].startswith("CineU_LevelPark_HangingIvy_")]
    assert [asset_path for _, asset_path, _, _, _ in hanging_ivy] == [
        "/Game/CityPark/Meshes/Flora/Ivy/SM_Ivy2_06",
        "/Game/CityPark/Meshes/Flora/Ivy/SM_Ivy2_03",
    ]
    assert all(cineu_world_ops.CITYPARK_PATH_X + 620.0 <= location[0] <= cineu_world_ops.CITYPARK_PATH_X + 1280.0 for _, _, location, _, _ in hanging_ivy)
    assert all(cineu_world_ops.CITYPARK_PATH_CENTER_Y - 520.0 <= location[1] <= cineu_world_ops.CITYPARK_PATH_CENTER_Y + 80.0 for _, _, location, _, _ in hanging_ivy)
    assert all(location[2] <= cineu_world_ops.CITYPARK_PATH_Z - 80.0 for _, _, location, _, _ in hanging_ivy)
    assert all(0.28 <= scale[0] <= 0.52 for _, _, _, scale, _ in hanging_ivy)
    assert not any("_Canopy_Left_" in label for label, *_ in spawned_assets)


def test_level_backed_park_asset_accents_use_imported_canopy_assets_without_fallback(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    spawned_assets = []

    dressing_assets = [
        {
            "asset_id": "asset_ue_project_content_externalassets_twinmotion_vegetation_trees_xf_ficusbenjamina_sm_a_ficusbenjamina_lod0",
            "ue_path": "/Game/ExternalAssets/Twinmotion/Vegetation/Trees/XF_FicusBenjamina/SM_A_FicusBenjamina_LOD0",
        },
        {
            "asset_id": "asset_ue_project_content_externalassets_twinmotion_vegetation_trees_xf_tiliaamericana_sm_a_tiliaamericana_lod0",
            "ue_path": "/Game/ExternalAssets/Twinmotion/Vegetation/Trees/XF_TiliaAmericana/SM_A_TiliaAmericana_LOD0",
        },
    ]

    monkeypatch.setattr(cineu_world_ops, "unreal", object())
    monkeypatch.setattr(
        cineu_world_ops,
        "_spawn_mesh_asset_if_available",
        lambda label, asset_path, location, scale, rotation=None: spawned_assets.append((label, asset_path, location, scale, rotation)) or True,
    )
    monkeypatch.setattr(
        cineu_world_ops,
        "_spawn_if_missing",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("imported canopy accents must not fall back to generated shapes")),
    )

    result = cineu_world_ops._spawn_level_backed_park_asset_accents(dressing_assets=dressing_assets)

    imported_canopies = [
        (label, asset_path, location, scale, rotation)
        for label, asset_path, location, scale, rotation in spawned_assets
        if label.startswith("CineU_LevelPark_ImportedCanopy_")
    ]
    assert result["spawned_asset_accents"] == [
        "CineU_LevelPark_ForegroundWillow_Right_00",
        "CineU_LevelPark_ForegroundWillow_Right_01",
        "CineU_LevelPark_CanopyWillow_Right_00",
        "CineU_LevelPark_HangingIvy_Right_00",
        "CineU_LevelPark_HangingIvy_Right_01",
        "CineU_LevelPark_ImportedCanopy_Left_00",
        "CineU_LevelPark_ImportedCanopy_Left_01",
    ]
    assert [asset_path for _, asset_path, _, _, _ in imported_canopies] == [asset["ue_path"] for asset in dressing_assets]
    assert cineu_world_ops.CITYPARK_PATH_X - 520.0 <= imported_canopies[0][2][0] <= cineu_world_ops.CITYPARK_PATH_X - 320.0
    assert cineu_world_ops.CITYPARK_PATH_CENTER_Y - 380.0 <= imported_canopies[0][2][1] <= cineu_world_ops.CITYPARK_PATH_CENTER_Y - 250.0
    assert 0.75 <= imported_canopies[0][3][0] <= 1.10
    assert cineu_world_ops.CITYPARK_PATH_X - 80.0 <= imported_canopies[1][2][0] <= cineu_world_ops.CITYPARK_PATH_X + 160.0
    assert cineu_world_ops.CITYPARK_PATH_CENTER_Y - 110.0 <= imported_canopies[1][2][1] <= cineu_world_ops.CITYPARK_PATH_CENTER_Y + 80.0
    assert 0.45 <= imported_canopies[1][3][0] <= 0.80


def test_level_backed_park_asset_accents_scale_citypark_dressing_assets_like_native_scene(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    spawned_assets = []
    dressing_assets = [
        {"asset_id": "asset_citypark_maple", "ue_path": "/Game/CityPark/Meshes/Flora/Trees/SM_Maple08"},
        {"asset_id": "asset_citypark_elm", "ue_path": "/Game/CityPark/Meshes/Flora/Trees/SM_Elm08"},
    ]

    monkeypatch.setattr(cineu_world_ops, "unreal", object())
    monkeypatch.setattr(
        cineu_world_ops,
        "_spawn_mesh_asset_if_available",
        lambda label, asset_path, location, scale, rotation=None: spawned_assets.append((label, asset_path, location, scale, rotation)) or True,
    )
    monkeypatch.setattr(
        cineu_world_ops,
        "_spawn_if_missing",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("CityPark dressing must reuse native scene assets")),
    )

    cineu_world_ops._spawn_level_backed_park_asset_accents(dressing_assets=dressing_assets)

    citypark_canopies = [
        (label, asset_path, location, scale, rotation)
        for label, asset_path, location, scale, rotation in spawned_assets
        if label.startswith("CineU_LevelPark_ImportedCanopy_")
    ]
    assert [asset_path for _, asset_path, _, _, _ in citypark_canopies] == [asset["ue_path"] for asset in dressing_assets]
    assert all(0.07 <= scale[0] <= 0.12 for _, _, _, scale, _ in citypark_canopies)
    assert citypark_canopies[0][2][0] < cineu_world_ops.CITYPARK_PATH_X
    assert citypark_canopies[0][2][1] < cineu_world_ops.CITYPARK_PATH_CENTER_Y


def test_level_backed_park_asset_accents_do_not_duplicate_native_foreground_willow(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    spawned_assets = []
    dressing_assets = [
        {"asset_id": "asset_citypark_willow", "ue_path": "/Game/CityPark/Meshes/Flora/Trees/SM_WeepingWillow01"},
        {"asset_id": "asset_citypark_maple", "ue_path": "/Game/CityPark/Meshes/Flora/Trees/SM_Maple08"},
    ]

    monkeypatch.setattr(cineu_world_ops, "unreal", object())
    monkeypatch.setattr(
        cineu_world_ops,
        "_spawn_mesh_asset_if_available",
        lambda label, asset_path, location, scale, rotation=None: spawned_assets.append((label, asset_path, location, scale, rotation)) or True,
    )

    cineu_world_ops._spawn_level_backed_park_asset_accents(dressing_assets=dressing_assets)

    imported_canopies = [
        (label, asset_path, location, scale, rotation)
        for label, asset_path, location, scale, rotation in spawned_assets
        if label.startswith("CineU_LevelPark_ImportedCanopy_")
    ]
    assert [asset_path for _, asset_path, _, _, _ in imported_canopies] == [
        "/Game/CityPark/Meshes/Flora/Trees/SM_Maple08"
    ]
    willow_labels = [
        label
        for label, asset_path, *_ in spawned_assets
        if asset_path == "/Game/CityPark/Meshes/Flora/Trees/SM_WeepingWillow01"
    ]
    assert willow_labels == [
        "CineU_LevelPark_ForegroundWillow_Right_00",
        "CineU_LevelPark_ForegroundWillow_Right_01",
        "CineU_LevelPark_CanopyWillow_Right_00",
    ]


def test_level_backed_park_asset_accents_disable_foreground_willow_shadows(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    shadowless = []

    monkeypatch.setattr(cineu_world_ops, "unreal", object())
    monkeypatch.setattr(cineu_world_ops, "_spawn_mesh_asset_if_available", lambda *args, **kwargs: True)
    monkeypatch.setattr(cineu_world_ops, "_disable_actor_shadows", lambda label: shadowless.append(label))

    result = cineu_world_ops._spawn_level_backed_park_asset_accents()

    assert shadowless == result["spawned_asset_accents"]


def test_disable_actor_shadows_turns_off_static_mesh_components(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    class Component:
        def __init__(self):
            self.properties = {}

        def set_editor_property(self, name, value):
            self.properties[name] = value

    class Actor:
        def __init__(self):
            self.components = [Component(), Component()]

        def get_components_by_class(self, component_class):
            return self.components

    class FakeUnreal:
        StaticMeshComponent = object
        InstancedStaticMeshComponent = object
        HierarchicalInstancedStaticMeshComponent = object

    actor = Actor()
    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_world_ops, "_find_actor_or_none", lambda label: actor)

    cineu_world_ops._disable_actor_shadows("CineU_LevelPark_ForegroundWillow_Canopy_Left_00")

    assert all(component.properties["cast_shadow"] is False for component in actor.components)
    assert all(component.properties["visible_in_ray_tracing"] is False for component in actor.components)


def test_level_backed_park_asset_accents_skip_missing_citypark_mesh_without_fallback(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    attempted_assets = []

    monkeypatch.setattr(cineu_world_ops, "unreal", object())
    monkeypatch.setattr(
        cineu_world_ops,
        "_spawn_mesh_asset_if_available",
        lambda label, asset_path, location, scale, rotation=None: attempted_assets.append((label, asset_path)) or False,
    )
    monkeypatch.setattr(
        cineu_world_ops,
        "_spawn_if_missing",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("missing CityPark willow must not fall back to generated shapes")),
    )
    monkeypatch.setattr(
        cineu_world_ops,
        "_spawn_asset_or_shape",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("missing CityPark willow must not use asset-or-shape fallback")),
    )

    result = cineu_world_ops._spawn_level_backed_park_asset_accents()

    assert result == {"spawned_asset_accents": []}
    assert attempted_assets == [
        ("CineU_LevelPark_ForegroundWillow_Right_00", "/Game/CityPark/Meshes/Flora/Trees/SM_WeepingWillow01"),
        ("CineU_LevelPark_ForegroundWillow_Right_01", "/Game/CityPark/Meshes/Flora/Trees/SM_WeepingWillow01"),
        ("CineU_LevelPark_CanopyWillow_Right_00", "/Game/CityPark/Meshes/Flora/Trees/SM_WeepingWillow01"),
        ("CineU_LevelPark_HangingIvy_Right_00", "/Game/CityPark/Meshes/Flora/Ivy/SM_Ivy2_06"),
        ("CineU_LevelPark_HangingIvy_Right_01", "/Game/CityPark/Meshes/Flora/Ivy/SM_Ivy2_03"),
    ]


def test_level_backed_park_support_surface_uses_citypark_anchor_geometry(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    surface = cineu_world_ops._citypark_path_support_surface(level_backed=True)

    assert surface == {
        "type": "ground",
        "z": -630.004,
        "bounds": [5600.0, 6800.0, -12650.0, -11850.0],
        "anchor_actor": "InstancedFoliageActor2",
        "environment_asset_type": "level",
    }
    assert cineu_world_ops._park_surface_primitives(level_backed=True) == []


def test_level_backed_park_dressing_removes_stale_procedural_details(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    class Actor:
        def __init__(self, label):
            self.label = label

        def get_actor_label(self):
            return self.label

    stale_railing = Actor("CineU_Park_Railing_Left_00")
    stale_lamp = Actor("CineU_Park_Lamp_00_Post")
    stale_tree = Actor("CineU_Park_Tree_00_Canopy")
    stale_forest = Actor("CineU_LevelPark_ForestBackdrop")
    stale_sky = Actor("CineU_LevelPark_SkyBackdrop")
    stale_backdrop_tree = Actor("CineU_LevelPark_Park_TreeBackdrop_00")
    stale_subject_fill = Actor("CineU_Park_SubjectFillLight")
    stale_shrub = Actor("CineU_LevelPark_PathShrub_Left_00")
    stale_grass = Actor("CineU_LevelPark_PathGrass_Right_00")
    stale_leaves = Actor("CineU_LevelPark_PathLeaves_00")
    stale_asset_fence = Actor("CineU_LevelPark_AssetFence_Right_00")
    stale_asset_lamp = Actor("CineU_LevelPark_AssetLamp_Left_00")
    stale_water = Actor("CineU_LevelPark_Water_Right")
    stale_bridge = Actor("CineU_LevelPark_BridgeSurface_00")
    stale_water_plant = Actor("CineU_LevelPark_WaterPlant_00")
    stale_path_edge = Actor("CineU_LevelPark_PathEdge_Right_00")
    stale_path_decal = Actor("CineU_LevelPark_PathDecal_00")
    stale_path_decal_center = Actor("CineU_LevelPark_PathDecalCenter_00")
    stale_horizon_grove = Actor("CineU_LevelPark_HorizonGrove_Tree_00")
    stale_waterline_screen = Actor("CineU_LevelPark_WaterlineScreen_Tree_00")
    stale_park_path = Actor("CineU_Park_Path")
    stale_park_grass = Actor("CineU_Park_Grass_Left")
    stale_grass_fill = Actor("CineU_LevelPark_GrassFill")
    native_path = Actor("SM_ParkPath1_2 (HISMA)")
    native_tree = Actor("SM_Elm02 (HISMA)")
    destroyed = []

    class FakeLevelLibrary:
        @staticmethod
        def get_all_level_actors():
            return [
                stale_railing,
                stale_lamp,
                stale_tree,
                stale_forest,
                stale_sky,
                stale_backdrop_tree,
                stale_subject_fill,
                stale_shrub,
                stale_grass,
                stale_leaves,
                stale_asset_fence,
                stale_asset_lamp,
                stale_water,
                stale_bridge,
                stale_water_plant,
                stale_path_edge,
                stale_path_decal,
                stale_path_decal_center,
                stale_horizon_grove,
                stale_waterline_screen,
                stale_park_path,
                stale_park_grass,
                stale_grass_fill,
                native_path,
                native_tree,
            ]

        @staticmethod
        def destroy_actor(actor):
            destroyed.append(actor.get_actor_label())

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_world_ops, "_hide_park_level_foliage_occluders", lambda: [])
    monkeypatch.setattr(cineu_world_ops, "_style_loaded_park_level_actors", lambda: [])
    monkeypatch.setattr(cineu_world_ops, "_spawn_if_missing", lambda *args, **kwargs: None)
    monkeypatch.setattr(cineu_world_ops, "_spawn_light_if_missing", lambda *args, **kwargs: None)

    cineu_world_ops._ensure_park_dressing(level_backed=True)

    assert destroyed == [
        "CineU_Park_Railing_Left_00",
        "CineU_Park_Lamp_00_Post",
        "CineU_Park_Tree_00_Canopy",
        "CineU_LevelPark_ForestBackdrop",
        "CineU_LevelPark_SkyBackdrop",
        "CineU_LevelPark_Park_TreeBackdrop_00",
        "CineU_Park_SubjectFillLight",
        "CineU_LevelPark_PathShrub_Left_00",
        "CineU_LevelPark_PathGrass_Right_00",
        "CineU_LevelPark_PathLeaves_00",
        "CineU_LevelPark_AssetFence_Right_00",
        "CineU_LevelPark_AssetLamp_Left_00",
        "CineU_LevelPark_Water_Right",
        "CineU_LevelPark_BridgeSurface_00",
        "CineU_LevelPark_WaterPlant_00",
        "CineU_LevelPark_PathEdge_Right_00",
        "CineU_LevelPark_PathDecal_00",
        "CineU_LevelPark_PathDecalCenter_00",
        "CineU_LevelPark_HorizonGrove_Tree_00",
        "CineU_LevelPark_WaterlineScreen_Tree_00",
        "CineU_Park_Path",
        "CineU_Park_Grass_Left",
        "CineU_LevelPark_GrassFill",
    ]
    assert "SM_ParkPath1_2 (HISMA)" not in destroyed
    assert "SM_Elm02 (HISMA)" not in destroyed


def test_level_backed_park_styles_reused_citypark_geometry(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    class Actor:
        def __init__(self, label):
            self.label = label

        def get_actor_label(self):
            return self.label

        def get_class(self):
            return type("ActorClass", (), {"get_name": lambda _self: "Actor"})()

    park_path = Actor("SM_ParkPath1_2 (HISMA)")
    asphalt = Actor("SM_Asphalt01_1 (HISMA)")
    fence = Actor("SM_Fence03_4 (HISMA)")
    lamp = Actor("SM_LampPost02_1 (HISMA)")
    unrelated = Actor("BP_PlayerStart")
    styled = []

    class FakeLevelLibrary:
        @staticmethod
        def get_all_level_actors():
            return [park_path, asphalt, fence, lamp, unrelated]

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_world_ops, "_apply_visual_profile", lambda actor, profile: styled.append((actor.get_actor_label(), profile["material_label"])))

    result = cineu_world_ops._style_loaded_park_level_actors()

    assert result == ["SM_Fence03_4 (HISMA)", "SM_LampPost02_1 (HISMA)"]
    assert styled == [
        ("SM_Fence03_4 (HISMA)", "citypark_soft_metal"),
        ("SM_LampPost02_1 (HISMA)", "citypark_soft_metal"),
    ]


def test_level_backed_park_supplement_prefers_citypark_tree_meshes(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    spawned_assets = []
    spawned_shapes = []

    monkeypatch.setattr(cineu_world_ops, "unreal", object())
    monkeypatch.setattr(
        cineu_world_ops,
        "_spawn_if_missing",
        lambda label, shape, location, scale, rotation=None: spawned_shapes.append((label, shape, location, scale)),
    )
    monkeypatch.setattr(
        cineu_world_ops,
        "_spawn_asset_or_shape",
        lambda label, asset_path, shape, location, scale, rotation=None, fallback_scale=None: spawned_assets.append((label, asset_path, shape, location, scale)),
    )

    cineu_world_ops._spawn_level_backed_park_supplement()

    assert any(asset_path == "/Game/CityPark/Meshes/Flora/Trees/SM_WeepingWillow01" for _, asset_path, _, _, _ in spawned_assets)
    assert all(label.startswith("CineU_LevelPark_") for label, _, _, _, _ in spawned_assets)
    assert min(location[1] for _, _, _, location, _ in spawned_assets) <= 24850.0
    assert any(label.startswith("CineU_LevelPark_Park_TreeBackdrop_") for label, _, _, _, _ in spawned_assets)
    assert min(location[1] for _, _, _, location, _ in spawned_assets) <= 24480.0
    assert not any(label == "CineU_LevelPark_SkyBackdrop" for label, _, _, _ in spawned_shapes)
    assert not any(label == "CineU_LevelPark_ForestBackdrop" for label, _, _, _ in spawned_shapes)
    assert not any(label.startswith("CineU_LevelPark_BridgeRail_") for label, _, _, _ in spawned_shapes)
    assert any(
        label.startswith("CineU_LevelPark_PathShrub_") and asset_path.startswith("/Game/CityPark/Meshes/Flora/Bushs/")
        for label, asset_path, _, _, _ in spawned_assets
    )
    assert any(
        label.startswith("CineU_LevelPark_PathGrass_") and asset_path.startswith("/Game/CityPark/Meshes/Flora/Grass/")
        for label, asset_path, _, _, _ in spawned_assets
    )
    leaf_assets = [
        (label, asset_path, location, scale)
        for label, asset_path, _, location, scale in spawned_assets
        if label.startswith("CineU_LevelPark_PathLeaves_")
    ]
    assert any(asset_path.startswith("/Game/CityPark/Meshes/Ground/SM_DryLeaves") for _, asset_path, _, _ in leaf_assets)
    assert any(24800.0 <= location[1] <= 25480.0 for _, _, location, _ in leaf_assets)
    assert any(location[1] >= 30000.0 for _, _, location, _ in leaf_assets)
    assert all(abs(location[0] - cineu_world_ops.CITYPARK_PATH_X) <= 215.0 for _, _, location, _ in leaf_assets)
    assert all(scale[2] <= 0.08 for _, _, _, scale in leaf_assets)
    path_decals = [
        (label, asset_path, location, scale)
        for label, asset_path, _, location, scale in spawned_assets
        if label.startswith("CineU_LevelPark_PathDecal_")
    ]
    assert any(asset_path.startswith("/Game/CityPark/Meshes/Road/SM_RoadDecal") for _, asset_path, _, _ in path_decals)
    assert any(asset_path.startswith("/Game/CityPark/Meshes/Road/SM_LeakDecal") for _, asset_path, _, _ in path_decals)
    assert any(location[1] >= 30400.0 for _, _, location, _ in path_decals)
    assert all(abs(location[0] - cineu_world_ops.CITYPARK_PATH_X) >= 220.0 for _, _, location, _ in path_decals)
    assert all(scale[0] <= 0.06 for _, _, _, scale in path_decals)
    center_path_decals = [
        (label, asset_path, location, scale)
        for label, asset_path, _, location, scale in spawned_assets
        if label.startswith("CineU_LevelPark_PathDecalCenter_")
    ]
    assert len(center_path_decals) >= 6
    assert any(asset_path.startswith("/Game/CityPark/Meshes/Road/SM_RoadDecal") for _, asset_path, _, _ in center_path_decals)
    assert all(abs(location[0] - cineu_world_ops.CITYPARK_PATH_X) <= 140.0 for _, _, location, _ in center_path_decals)
    assert all(scale[0] <= 0.045 for _, _, _, scale in center_path_decals)
    assert any(
        label.startswith("CineU_LevelPark_AssetFence_") and asset_path.startswith("/Game/CityPark/Meshes/Props/SM_ParkFence")
        for label, asset_path, _, _, _ in spawned_assets
    )
    wire_fence_shapes = [
        (label, location, scale)
        for label, _, location, scale in spawned_shapes
        if label.startswith("CineU_LevelPark_WireFence_Right_")
    ]
    assert any(label.startswith("CineU_LevelPark_WireFence_Right_Rail_") and location[0] > cineu_world_ops.CITYPARK_PATH_X + 500.0 and scale[1] >= 7.0 for label, location, scale in wire_fence_shapes)
    assert sum(1 for label, _, _ in wire_fence_shapes if "_Post_" in label) >= 6
    assert sum(1 for label, _, _ in wire_fence_shapes if "_Vertical_" in label) >= 8
    right_fences = [
        (label, asset_path, location)
        for label, asset_path, _, location, _ in spawned_assets
        if label.startswith("CineU_LevelPark_AssetFence_Right_")
    ]
    assert any(location[1] >= 30000.0 for _, _, location in right_fences)
    assert all(asset_path.startswith("/Game/CityPark/Meshes/Props/SM_ParkFence") for _, asset_path, _ in right_fences)
    assert any(
        label.startswith("CineU_LevelPark_AssetLamp_") and asset_path.startswith("/Game/CityPark/Meshes/Props/SM_LampPost")
        for label, asset_path, _, _, _ in spawned_assets
    )
    water_assets = [
        (label, asset_path, location, scale)
        for label, asset_path, _, location, scale in spawned_assets
        if label.startswith("CineU_LevelPark_Water_")
    ]
    assert any(asset_path == "/Game/CityPark/Meshes/Ground/SM_WaterPlane" for _, asset_path, _, _ in water_assets)
    assert all(location[0] >= cineu_world_ops.CITYPARK_PATH_X + 540.0 for _, _, location, _ in water_assets)
    assert any(location[0] <= cineu_world_ops.CITYPARK_PATH_X + 850.0 and scale[1] >= 70.0 for _, _, location, scale in water_assets)
    assert all(scale[0] <= 5.0 for _, _, _, scale in water_assets)
    bridge_assets = [
        (label, asset_path, location, scale)
        for label, asset_path, _, location, scale in spawned_assets
        if label.startswith("CineU_LevelPark_BridgeSurface_")
    ]
    assert any(asset_path.startswith("/Game/CityPark/Meshes/Road/SM_Bridge") for _, asset_path, _, _ in bridge_assets)
    assert all(location[0] >= cineu_world_ops.CITYPARK_PATH_X + 780.0 for _, _, location, _ in bridge_assets)
    assert any(24780.0 <= location[1] <= 26880.0 for _, _, location, _ in bridge_assets)
    foreground_bridges = [
        (label, asset_path, location, scale)
        for label, asset_path, _, location, scale in spawned_assets
        if label.startswith("CineU_LevelPark_ForegroundBridge_")
    ]
    assert any(asset_path.startswith("/Game/CityPark/Meshes/Road/SM_Bridge03_") for _, asset_path, _, _ in foreground_bridges)
    assert any(location[1] >= 30900.0 for _, _, location, _ in foreground_bridges)
    assert any(28100.0 <= location[1] <= 29600.0 for _, _, location, _ in foreground_bridges)
    assert all(location[0] <= cineu_world_ops.CITYPARK_PATH_X - 560.0 for _, _, location, _ in foreground_bridges)
    bridge_lattice_shapes = [
        (label, location, scale)
        for label, _, location, scale in spawned_shapes
        if label.startswith("CineU_LevelPark_BridgeLattice_Left_")
    ]
    assert len(bridge_lattice_shapes) >= 12
    assert any(28600.0 <= location[1] <= 30450.0 for _, location, _ in bridge_lattice_shapes)
    assert all(cineu_world_ops.CITYPARK_PATH_X - 430.0 <= location[0] <= cineu_world_ops.CITYPARK_PATH_X - 320.0 for _, location, _ in bridge_lattice_shapes)
    assert all(scale[1] <= 1.45 for label, _, scale in bridge_lattice_shapes if "TopRail" in label or "Cross" in label)
    canopy_frames = [
        (label, asset_path, location, scale)
        for label, asset_path, _, location, scale in spawned_assets
        if label.startswith("CineU_LevelPark_CanopyFrame_")
    ]
    assert len(canopy_frames) >= 8
    assert any(asset_path.startswith("/Game/CityPark/Meshes/Flora/Trees/SM_") for _, asset_path, _, _ in canopy_frames)
    assert any(location[1] >= 30000.0 and location[2] >= cineu_world_ops.CITYPARK_PATH_Z for _, _, location, _ in canopy_frames)
    assert all(abs(location[0] - cineu_world_ops.CITYPARK_PATH_X) >= 680.0 for _, _, location, _ in canopy_frames)
    water_plants = [
        (label, asset_path, location, scale)
        for label, asset_path, _, location, scale in spawned_assets
        if label.startswith("CineU_LevelPark_WaterPlant_")
    ]
    assert any(asset_path.startswith("/Game/CityPark/Meshes/Flora/Grass/SM_WaterPlant") for _, asset_path, _, _ in water_plants)
    assert all(location[0] >= cineu_world_ops.CITYPARK_PATH_X + 780.0 for _, _, location, _ in water_plants)
    waterline_screen = [
        (label, asset_path, location, scale)
        for label, asset_path, _, location, scale in spawned_assets
        if label.startswith("CineU_LevelPark_WaterlineScreen_")
    ]
    assert len(waterline_screen) >= 10
    assert any(asset_path.startswith("/Game/CityPark/Meshes/Flora/Trees/SM_") for _, asset_path, _, _ in waterline_screen)
    assert any(asset_path.startswith("/Game/CityPark/Meshes/Flora/Bushs/SM_") for _, asset_path, _, _ in waterline_screen)
    assert all(location[0] >= cineu_world_ops.CITYPARK_PATH_X + 820.0 for _, _, location, _ in waterline_screen)
    assert any(28600.0 <= location[1] <= 31400.0 for _, _, location, _ in waterline_screen)
    assert any(scale[0] >= 0.30 for _, _, _, scale in waterline_screen)
    horizon_grove = [
        (label, asset_path, location, scale)
        for label, asset_path, _, location, scale in spawned_assets
        if label.startswith("CineU_LevelPark_HorizonGrove_")
    ]
    assert len(horizon_grove) >= 10
    assert any(asset_path.startswith("/Game/CityPark/Meshes/Flora/Trees/SM_") for _, asset_path, _, _ in horizon_grove)
    assert any(asset_path.startswith("/Game/CityPark/Meshes/Flora/Bushs/SM_") for _, asset_path, _, _ in horizon_grove)
    assert all(location[0] >= cineu_world_ops.CITYPARK_PATH_X + 1450.0 for _, _, location, _ in horizon_grove)
    assert any(28600.0 <= location[1] <= 31400.0 for _, _, location, _ in horizon_grove)
    assert all(
        asset_path != "/Game/CityPark/Meshes/Flora/Trees/SM_WeepingWillow01"
        for label, asset_path, _, _, _ in spawned_assets
        if label.startswith("CineU_LevelPark_Park_TreeBackdrop_")
    )


def test_spawn_mesh_asset_if_available_uses_citypark_static_mesh(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    calls = []

    class Actor:
        def set_actor_label(self, label):
            calls.append(("label", label))

        def set_actor_location(self, vector, sweep, teleport):
            calls.append(("location", vector))

        def set_actor_rotation(self, rotator, teleport):
            calls.append(("rotation", rotator))

        def set_actor_scale3d(self, vector):
            calls.append(("scale", vector))

    class FakeAssetLibrary:
        @staticmethod
        def load_asset(path):
            calls.append(("load", path))
            if path == "/Game/CityPark/Meshes/Road/SM_ParkPath1_2":
                return "ParkPathMesh"
            return None

    class FakeLevelLibrary:
        @staticmethod
        def get_all_level_actors():
            return []

        @staticmethod
        def spawn_actor_from_object(asset, vector):
            calls.append(("spawn", asset, vector))
            return Actor()

    class FakeUnreal:
        EditorAssetLibrary = FakeAssetLibrary
        EditorLevelLibrary = FakeLevelLibrary

        @staticmethod
        def Vector(*values):
            return list(values)

        @staticmethod
        def Rotator(*values):
            return list(values)

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)

    created = cineu_world_ops._spawn_mesh_asset_if_available(
        "CineU_Park_Path",
        "/Game/CityPark/Meshes/Road/SM_ParkPath1_2",
        [0.0, 0.0, 1.0],
        [0.08, 0.28, 1.0],
        [0.0, 0.0, 0.0],
    )

    assert created is True
    assert ("load", "/Game/CityPark/Meshes/Road/SM_ParkPath1_2") in calls
    assert ("spawn", "ParkPathMesh", [0.0, 0.0, 1.0]) in calls
    assert ("label", "CineU_Park_Path") in calls
    assert ("scale", [0.08, 0.28, 1.0]) in calls


def test_level_backed_park_cinematic_pass_adds_fill_without_rebuilding_world(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    events = []
    lights = {}
    postprocess = {}
    fog = {}

    monkeypatch.setattr(cineu_world_ops, "unreal", object())
    monkeypatch.setattr(cineu_world_ops, "_restore_park_level_native_visibility", lambda: events.append("restore") or ["Water1_1"], raising=False)
    monkeypatch.setattr(cineu_world_ops, "_hide_park_level_camera_occluders", lambda: events.append("hide") or ["SM_Elm02 (HISMA)"], raising=False)
    monkeypatch.setattr(cineu_world_ops, "_soften_park_level_native_lights", lambda: events.append("lights") or ["Light Source"], raising=False)
    monkeypatch.setattr(
        cineu_world_ops,
        "_spawn_level_backed_park_scenic_assets",
        lambda: (_ for _ in ()).throw(AssertionError("level-backed CityPark should reuse native scene assets")),
        raising=False,
    )
    monkeypatch.setattr(
        cineu_world_ops,
        "_spawn_light_if_missing",
        lambda label, actor_class, location, rotation=None, properties=None: lights.setdefault(label, {"location": location, "properties": properties or {}}),
    )
    monkeypatch.setattr(
        cineu_world_ops,
        "_spawn_post_process_if_missing",
        lambda label, location, scale, properties=None: postprocess.setdefault(label, {"location": location, "scale": scale, "properties": properties or {}}),
        raising=False,
    )
    monkeypatch.setattr(
        cineu_world_ops,
        "_spawn_fog_if_missing",
        lambda label, location, properties=None: fog.setdefault(label, {"location": location, "properties": properties or {}}),
        raising=False,
    )

    result = cineu_world_ops._apply_level_backed_park_cinematic_pass()

    assert result["restored_native_actors"] == ["Water1_1"]
    assert result["hidden_occluders"] == ["SM_Elm02 (HISMA)"]
    assert events == ["restore", "hide", "lights"]
    assert "CineU_LevelPark_SubjectKeyLight" in lights
    assert "CineU_LevelPark_SoftFillLight" in lights
    assert 900.0 <= lights["CineU_LevelPark_SubjectKeyLight"]["properties"]["intensity"] <= 1250.0
    assert 950.0 <= lights["CineU_LevelPark_SoftFillLight"]["properties"]["intensity"] <= 1250.0
    assert "CineU_LevelPark_CinematicPostProcess" in postprocess
    assert postprocess["CineU_LevelPark_CinematicPostProcess"]["properties"]["unbound"] is True
    assert 0.78 <= postprocess["CineU_LevelPark_CinematicPostProcess"]["properties"]["exposure_compensation"] <= 0.98
    assert postprocess["CineU_LevelPark_CinematicPostProcess"]["properties"]["vignette_intensity"] <= 0.05
    assert fog == {}


def test_level_backed_park_softens_native_citypark_lights(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    class Actor:
        def __init__(self, label, class_name):
            self.label = label
            self.class_name = class_name

        def get_actor_label(self):
            return self.label

        def get_class(self):
            return type("ActorClass", (), {"get_name": lambda _self: self.class_name})()

    sun = Actor("Light Source", "DirectionalLight")
    sky = Actor("SkyLight", "SkyLight")
    cineu_key = Actor("CineU_LevelPark_SubjectKeyLight", "PointLight")
    lamp = Actor("SM_LampPost02_1", "StaticMeshActor")
    configured = []

    class FakeLevelLibrary:
        @staticmethod
        def get_all_level_actors():
            return [sun, sky, cineu_key, lamp]

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_world_ops, "_configure_light_actor", lambda actor, props: configured.append((actor.get_actor_label(), props)))

    softened = cineu_world_ops._soften_park_level_native_lights()

    assert softened == ["Light Source", "SkyLight"]
    assert (
        "Light Source",
        {
            "intensity": 1.65,
            "source_angle": 6.0,
            "indirect_lighting_intensity": 1.2,
            "light_color": [1.0, 0.96, 0.84],
        },
    ) in configured
    assert (
        "SkyLight",
        {
            "intensity": 2.35,
            "indirect_lighting_intensity": 1.45,
            "light_color": [0.86, 0.96, 1.0],
        },
    ) in configured
    assert all(label != "CineU_LevelPark_SubjectKeyLight" for label, _ in configured)


def test_level_backed_camera_occluder_pass_keeps_citypark_bridge_sky_and_lights(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    class Vec:
        def __init__(self, x, y, z):
            self.x = x
            self.y = y
            self.z = z

    class Actor:
        def __init__(self, label, class_name="Actor", origin=None, extent=None):
            self.label = label
            self.class_name = class_name
            self.origin = origin or Vec(-89000.0, 12000.0, 600.0)
            self.extent = extent or Vec(80.0, 80.0, 80.0)
            self.hidden_in_game = None
            self.hidden_in_editor = None

        def get_actor_label(self):
            return self.label

        def get_class(self):
            return type("ActorClass", (), {"get_name": lambda _self: self.class_name})()

        def get_actor_bounds(self, only_colliding_components):
            return self.origin, self.extent

        def set_actor_hidden_in_game(self, hidden):
            self.hidden_in_game = hidden

        def set_is_temporarily_hidden_in_editor(self, hidden):
            self.hidden_in_editor = hidden

    close_willow = Actor("SM_WeepingWillow01 (HISMA)", origin=Vec(6240.0, -12150.0, -600.0), extent=Vec(150.0, 150.0, 120.0))
    close_bush = Actor("SM_Bush1_03 (HISMA)", origin=Vec(6240.0, -12150.0, -600.0), extent=Vec(150.0, 150.0, 120.0))
    close_ivy = Actor("Ivy1_01 (HISMA)", origin=Vec(6240.0, -12150.0, -600.0), extent=Vec(150.0, 150.0, 120.0))
    close_non_instanced_tree = Actor("SM_StandaloneTree", origin=Vec(6240.0, -12150.0, -600.0), extent=Vec(150.0, 150.0, 120.0))
    high_fence = Actor("SM_Fence06_1 (HISMA)", origin=Vec(6240.0, -12150.0, -600.0), extent=Vec(180.0, 180.0, 380.0))
    merged_high_fence = Actor("MergedFence04", "StaticMeshActor", origin=Vec(6240.0, -12150.0, -600.0), extent=Vec(180.0, 180.0, 560.0))
    gate = Actor("SM_BaseballGate (HISMA)", origin=Vec(6240.0, -12150.0, -600.0), extent=Vec(180.0, 180.0, 460.0))
    low_fence = Actor("SM_Fence01_2 (HISMA)", origin=Vec(6240.0, -12150.0, -600.0), extent=Vec(180.0, 180.0, 180.0))
    distant_foliage = Actor("InstancedFoliageActor2", "InstancedFoliageActor")
    distant_grass = Actor("SM_grass07_2 (HISMA)")
    bridge = Actor("SM_Bridge02_2 (HISMA)")
    fence = Actor("SM_Fence03_4 (HISMA)")
    path = Actor("SM_ParkPath1_2 (HISMA)")
    water = Actor("Water1_1")
    fountain = Actor("Fountain1")
    light = Actor("Light Source", "DirectionalLight")
    sky = Actor("SkySphereBlueprint", "BP_Sky_Sphere_C")

    class FakeLevelLibrary:
        @staticmethod
        def get_all_level_actors():
            return [
                close_willow,
                close_bush,
                close_ivy,
                close_non_instanced_tree,
                high_fence,
                merged_high_fence,
                gate,
                low_fence,
                distant_foliage,
                distant_grass,
                bridge,
                fence,
                path,
                water,
                fountain,
                light,
                sky,
            ]

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)

    hidden = cineu_world_ops._hide_park_level_camera_occluders()

    assert hidden == [
        "SM_Bush1_03 (HISMA)",
        "Ivy1_01 (HISMA)",
        "SM_StandaloneTree",
        "SM_Fence06_1 (HISMA)",
        "MergedFence04",
        "SM_BaseballGate (HISMA)",
    ]
    assert close_willow.hidden_in_game is None
    assert close_bush.hidden_in_game is True
    assert close_ivy.hidden_in_game is True
    assert close_non_instanced_tree.hidden_in_game is True
    assert high_fence.hidden_in_game is True
    assert merged_high_fence.hidden_in_game is True
    assert gate.hidden_in_game is True
    assert low_fence.hidden_in_game is None
    assert distant_foliage.hidden_in_editor is None
    assert distant_grass.hidden_in_game is None
    assert bridge.hidden_in_game is None
    assert fence.hidden_in_game is None
    assert path.hidden_in_game is None
    assert water.hidden_in_game is None
    assert fountain.hidden_in_game is None
    assert light.hidden_in_game is None
    assert sky.hidden_in_game is None


def test_sparse_focus_tree_instance_suppression_moves_only_close_elm_instances(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    class Vec:
        def __init__(self, x, y, z):
            self.x = x
            self.y = y
            self.z = z

    class Mesh:
        def __init__(self, path):
            self.path = path

        def get_path_name(self):
            return self.path + "." + self.path.rsplit("/", 1)[-1]

    class Transform:
        def __init__(self, location):
            self.translation = Vec(*location)

    class Component:
        def __init__(self, mesh_path, locations):
            self.mesh = Mesh(mesh_path)
            self.transforms = [Transform(location) for location in locations]
            self.updated = []

        def get_editor_property(self, name):
            if name == "static_mesh":
                return self.mesh
            raise AttributeError(name)

        def get_instance_count(self):
            return len(self.transforms)

        def get_instance_transform(self, index, world_space=True):
            return self.transforms[index]

        def update_instance_transform(self, index, transform, world_space=True, mark_render_state_dirty=True, teleport=True):
            self.updated.append((index, transform.translation.z, world_space, mark_render_state_dirty, teleport))
            return True

    close_elm = Component(
        "/Game/CityPark/Meshes/Flora/Trees/SM_Elm13",
        [
            [6513.1, -12367.4, -582.1],
            [12000.0, -19000.0, -400.0],
        ],
    )
    close_willow = Component(
        "/Game/CityPark/Meshes/Flora/Trees/SM_WeepingWillow01",
        [[6513.1, -12367.4, -582.1]],
    )
    close_bush = Component(
        "/Game/CityPark/Meshes/Flora/Bushs/SM_Bush1_03",
        [[6373.5, -12774.1, -560.7]],
    )

    class Actor:
        def __init__(self, label, components):
            self.label = label
            self.components = components

        def get_actor_label(self):
            return self.label

        def get_components_by_class(self, _component_class):
            return self.components

    class FakeLevelLibrary:
        @staticmethod
        def get_all_level_actors():
            return [
                Actor("SM_Elm13 (HISMA)", [close_elm]),
                Actor("SM_WeepingWillow01 (HISMA)", [close_willow]),
                Actor("SM_Bush1_03 (HISMA)", [close_bush]),
            ]

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary
        HierarchicalInstancedStaticMeshComponent = object
        InstancedStaticMeshComponent = object

        @staticmethod
        def Vector(x, y, z):
            return Vec(x, y, z)

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)

    suppressed = cineu_world_ops._suppress_sparse_focus_tree_instances()

    assert suppressed == [
        {
            "actor": "SM_Elm13 (HISMA)",
            "mesh": "/Game/CityPark/Meshes/Flora/Trees/SM_Elm13",
            "instance_index": 0,
        }
    ]
    assert close_elm.updated == [(0, -50582.1, True, True, True)]
    assert close_willow.updated == []
    assert close_bush.updated == []


def test_level_backed_park_restores_native_citypark_visibility(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    class Actor:
        def __init__(self, label, class_name="Actor"):
            self.label = label
            self.class_name = class_name
            self.hidden_in_game = True
            self.hidden_in_editor = True

        def get_actor_label(self):
            return self.label

        def get_class(self):
            return type("ActorClass", (), {"get_name": lambda _self: self.class_name})()

        def set_actor_hidden_in_game(self, hidden):
            self.hidden_in_game = hidden

        def set_is_temporarily_hidden_in_editor(self, hidden):
            self.hidden_in_editor = hidden

    native_water = Actor("Water1_1")
    native_fountain = Actor("Fountain1")
    native_tree = Actor("SM_WeepingWillow01 (HISMA)")
    cineu_water = Actor("CineU_LevelPark_Water_Left")
    camera = Actor("CAM_shot_001", "CineCameraActor")
    zebra = Actor("zebra_01", "SkeletalMeshActor")
    world_partition = Actor("WorldDataLayers-1", "WorldDataLayers")

    class FakeLevelLibrary:
        @staticmethod
        def get_all_level_actors():
            return [native_water, native_fountain, native_tree, cineu_water, camera, zebra, world_partition]

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)

    restored = cineu_world_ops._restore_park_level_native_visibility()

    assert restored == ["Water1_1", "Fountain1", "SM_WeepingWillow01 (HISMA)"]
    assert native_water.hidden_in_game is False
    assert native_fountain.hidden_in_editor is False
    assert native_tree.hidden_in_game is False
    assert cineu_water.hidden_in_game is True
    assert camera.hidden_in_game is True
    assert zebra.hidden_in_game is True
    assert world_partition.hidden_in_game is True


def test_level_backed_park_scenic_assets_use_citypark_assets_near_bridge_anchor(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    spawned = []

    monkeypatch.setattr(cineu_world_ops, "unreal", object())
    monkeypatch.setattr(
        cineu_world_ops,
        "_spawn_asset_or_shape",
        lambda label, asset_path, shape, location, scale, rotation=None, fallback_scale=None: spawned.append(
            (label, asset_path, shape, location, scale, rotation)
        ),
    )

    cineu_world_ops._spawn_level_backed_park_scenic_assets()

    assert not any(label.startswith("CineU_LevelPark_Water_") for label, *_ in spawned)
    assert any(label.startswith("CineU_LevelPark_HorizonGrove_") and "/Game/CityPark/Meshes/Flora/Trees/" in asset_path for label, asset_path, *_ in spawned)
    assert any(label.startswith("CineU_LevelPark_WaterlineScreen_") and "/Game/CityPark/Meshes/Flora/Bushs/" in asset_path for label, asset_path, *_ in spawned)
    assert all(16200.0 <= location[1] <= 21100.0 for _, _, _, location, _, _ in spawned)
    horizon_locations = [location for label, _, _, location, _, _ in spawned if label.startswith("CineU_LevelPark_HorizonGrove_")]
    assert horizon_locations
    assert all(abs(location[0] - cineu_world_ops.CITYPARK_PATH_X) >= 760.0 for location in horizon_locations)


def test_configure_light_actor_converts_light_color_to_unreal_linear_color(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    class LightComponent:
        def __init__(self):
            self.properties = {}

        def set_editor_property(self, name, value):
            self.properties[name] = value

    class Actor:
        def __init__(self):
            self.properties = {}
            self.light_component = LightComponent()

        def set_editor_property(self, name, value):
            self.properties[name] = value

    class FakeUnreal:
        @staticmethod
        def LinearColor(*values):
            return ("LinearColor", values)

    actor = Actor()
    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)

    cineu_world_ops._configure_light_actor(actor, {"light_color": [1.0, 0.86, 0.68], "intensity": 2.0})

    assert actor.properties["light_color"] == ("LinearColor", (1.0, 0.86, 0.68, 1.0))
    assert actor.light_component.properties["light_color"] == ("LinearColor", (1.0, 0.86, 0.68, 1.0))
    assert actor.light_component.properties["intensity"] == 2.0


def test_configure_fog_actor_uses_unreal_exponential_height_fog_component(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    class FogComponent:
        def __init__(self):
            self.properties = {}

        def set_editor_property(self, name, value):
            self.properties[name] = value

    class Actor:
        def __init__(self):
            self._component = FogComponent()

        def get_component_by_class(self, component_class):
            return self._component if component_class == "FogComponentClass" else None

    class FakeUnreal:
        ExponentialHeightFogComponent = "FogComponentClass"

        @staticmethod
        def LinearColor(*values):
            return ("LinearColor", values)

    actor = Actor()
    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)

    cineu_world_ops._configure_fog_actor(actor, {"fog_density": 0.0024, "fog_inscattering_color": [0.92, 0.96, 1.0]})

    assert actor._component.properties["fog_density"] == 0.0024
    assert actor._component.properties["fog_inscattering_color"] == ("LinearColor", (0.92, 0.96, 1.0, 1.0))


def test_loaded_park_level_hides_foliage_occluders(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    class Vec:
        def __init__(self, x, y, z):
            self.x = x
            self.y = y
            self.z = z

    class Actor:
        def __init__(self, label, class_name, origin=None, extent=None):
            self.label = label
            self.class_name = class_name
            self.origin = origin
            self.extent = extent
            self.rotation = None
            self.hidden_in_game = None
            self.hidden_in_editor = None

        def get_actor_label(self):
            return self.label

        def get_class(self):
            return type("ActorClass", (), {"get_name": lambda _self: self.class_name})()

        def get_actor_bounds(self, only_colliding_components):
            if self.origin is None or self.extent is None:
                raise RuntimeError("bounds unavailable")
            return self.origin, self.extent

        def set_actor_hidden_in_game(self, hidden):
            self.hidden_in_game = hidden

        def set_is_temporarily_hidden_in_editor(self, hidden):
            self.hidden_in_editor = hidden

    foliage = Actor("InstancedFoliageActor2", "InstancedFoliageActor")
    ivy = Actor("Ivy1_01 (HISMA)", "Actor")
    amur_cork = Actor("SM_AmurCork01 (HISMA)", "Actor")
    bush = Actor("SM_Bush1_03 (HISMA)", "Actor")
    elm = Actor("SM_Elm02 (HISMA)", "Actor")
    far_elm = Actor("SM_Elm02_far (HISMA)", "Actor", origin=Vec(-72000.0, 12000.0, 600.0), extent=Vec(80.0, 80.0, 80.0))
    grass = Actor("SM_grass07_2 (HISMA)", "Actor")
    merged_bridge = Actor("MergedBridge01", "StaticMeshActor")
    merged_road = Actor("MergedRoad01", "StaticMeshActor")
    merged_fence = Actor("MergedFence04", "StaticMeshActor")
    house = Actor("House01 (HISMA)", "Actor")
    cafe = Actor("SM_CafeBuilding01 (HISMA)", "Actor")
    instanced_bridge = Actor("SM_Bridge02_1 (HISMA)", "HierarchicalInstancedStaticMeshActor")
    instanced_asphalt = Actor("SM_Asphalt01_1 (HISMA)", "Actor")
    instanced_fence = Actor("SM_Fence01_2 (HISMA)", "Actor")
    instanced_path = Actor("SM_ParkPath1_2 (HISMA)", "Actor")
    basketball_field = Actor("SM_BasketballField (HISMA)", "Actor")
    pool = Actor("SM_Pool (HISMA)", "Actor")
    pier = Actor("SM_Pier01 (HISMA)", "Actor")
    sidewalk = Actor("SM_Sidewalk01 (HISMA)", "Actor", origin=Vec(-23000.0, 21000.0, 90.0), extent=Vec(720.0, 640.0, 18.0))
    generic_cube = Actor("Cube (HISMA)", "Actor")
    cineu_path = Actor("CineU_Park_Path", "StaticMeshActor")
    light = Actor("Light Source", "DirectionalLight")
    skylight = Actor("SkyLight", "SkyLight")
    sky = Actor("SkySphereBlueprint", "BP_Sky_Sphere_C")
    plane = Actor("Plane3", "StaticMeshActor")
    landscape = Actor("LandscapeStreamingProxy_0_0_0", "LandscapeStreamingProxy")

    class FakeLevelLibrary:
        @staticmethod
        def get_all_level_actors():
            return [
                foliage,
                ivy,
                amur_cork,
                bush,
                elm,
                far_elm,
                grass,
                merged_bridge,
                merged_road,
                merged_fence,
                house,
                cafe,
                instanced_bridge,
                instanced_asphalt,
                instanced_fence,
                instanced_path,
                basketball_field,
                pool,
                pier,
                sidewalk,
                generic_cube,
                cineu_path,
                light,
                skylight,
                sky,
                plane,
                landscape,
            ]

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)

    hidden = cineu_world_ops._hide_park_level_foliage_occluders()

    assert hidden == [
        "SM_Elm02_far (HISMA)",
        "MergedRoad01",
        "House01 (HISMA)",
        "SM_CafeBuilding01 (HISMA)",
        "SM_BasketballField (HISMA)",
        "SM_Pool (HISMA)",
        "SM_Pier01 (HISMA)",
        "SM_Sidewalk01 (HISMA)",
        "Cube (HISMA)",
        "Plane3",
    ]
    assert foliage.hidden_in_game is None
    assert foliage.hidden_in_editor is None
    assert ivy.hidden_in_game is None
    assert amur_cork.hidden_in_game is None
    assert bush.hidden_in_game is None
    assert elm.hidden_in_game is None
    assert far_elm.hidden_in_game is True
    assert grass.hidden_in_game is None
    assert merged_bridge.hidden_in_game is None
    assert merged_road.hidden_in_game is True
    assert merged_fence.hidden_in_game is None
    assert house.hidden_in_game is True
    assert cafe.hidden_in_game is True
    assert instanced_bridge.hidden_in_game is None
    assert instanced_asphalt.hidden_in_game is None
    assert instanced_fence.hidden_in_game is None
    assert instanced_path.hidden_in_game is None
    assert basketball_field.hidden_in_game is True
    assert pool.hidden_in_game is True
    assert pier.hidden_in_game is True
    assert sidewalk.hidden_in_game is True
    assert generic_cube.hidden_in_game is True
    assert light.hidden_in_game is None
    assert skylight.hidden_in_game is None
    assert plane.hidden_in_game is True
    assert landscape.hidden_in_game is None
    assert cineu_path.hidden_in_game is None
    assert sky.hidden_in_game is None


def test_loaded_park_level_hides_distant_reusable_road_geometry(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    class Vector:
        def __init__(self, x, y, z):
            self.x = x
            self.y = y
            self.z = z

    class Actor:
        def __init__(self, label, origin, extent):
            self.label = label
            self.origin = Vector(*origin)
            self.extent = Vector(*extent)
            self.hidden_in_game = None

        def get_actor_label(self):
            return self.label

        def get_class(self):
            return type("ActorClass", (), {"get_name": lambda _self: "StaticMeshActor"})()

        def get_actor_bounds(self, only_colliding_components):
            return self.origin, self.extent

        def set_actor_hidden_in_game(self, hidden):
            self.hidden_in_game = hidden

        def set_is_temporarily_hidden_in_editor(self, hidden):
            pass

    anchor_path = Actor("InstancedFoliageActor2", [6241.53, -12153.676, -630.004], [600.0, 400.0, 20.0])
    distant_road = Actor("SM_RoadDistant_09 (HISMA)", [-23000.0, 21000.0, 90.0], [950.0, 700.0, 18.0])
    distant_asphalt = Actor("SM_AsphaltFar_02 (HISMA)", [-34200.0, 35000.0, 90.0], [720.0, 640.0, 18.0])

    class FakeLevelLibrary:
        @staticmethod
        def get_all_level_actors():
            return [anchor_path, distant_road, distant_asphalt]

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)

    hidden = cineu_world_ops._hide_park_level_foliage_occluders()

    assert hidden == ["SM_RoadDistant_09 (HISMA)", "SM_AsphaltFar_02 (HISMA)"]
    assert anchor_path.hidden_in_game is None
    assert distant_road.hidden_in_game is True
    assert distant_asphalt.hidden_in_game is True


def test_ensure_support_surfaces_rehydrates_park_scene_for_render(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    spawned = []
    lights = []

    monkeypatch.setattr(cineu_world_ops, "unreal", object())
    monkeypatch.setattr(cineu_world_ops, "_remove_default_scene_actors", lambda: [])
    monkeypatch.setattr(cineu_world_ops, "_spawn_if_missing", lambda label, *args, **kwargs: spawned.append(label))
    monkeypatch.setattr(cineu_world_ops, "_spawn_light_if_missing", lambda label, *args, **kwargs: lights.append(label))

    cineu_world_ops.ensure_support_surfaces({"park_path": {"type": "ground"}})

    assert "CineU_Park_Path" in spawned
    assert "CineU_Park_SkyBackdrop" in spawned
    assert "CineU_Park_Railing_Left_00" in spawned
    assert "CineU_Park_Tree_00_Canopy" in spawned
    assert "CineU_DirectionalLight" in lights
    assert "CineU_SkyLight" in lights
    assert "CineU_Park_FillLight" in lights


def test_gallery_environment_removes_obsolete_visible_ceiling(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    destroyed = []

    class Actor:
        def __init__(self, label=""):
            self.label = label

        def get_actor_label(self):
            return self.label

        def set_actor_label(self, label):
            self.label = label

    ceiling = Actor("CineU_Gallery_Ceiling")

    class FakeLevelLibrary:
        @staticmethod
        def get_editor_world():
            return object()

        @staticmethod
        def get_all_level_actors():
            return [ceiling]

        @staticmethod
        def spawn_actor_from_class(actor_class, vector):
            return Actor()

        @staticmethod
        def destroy_actor(actor):
            destroyed.append(actor.get_actor_label())

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary
        DirectionalLight = object
        SkyLight = object

        @staticmethod
        def Vector(*values):
            return values

        @staticmethod
        def Rotator(*values):
            return values

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_world_ops, "_spawn_if_missing", lambda *args, **kwargs: None)

    cineu_world_ops.setup_environment({"level_name": "LVL_test", "environment": "gallery"})

    assert "CineU_Gallery_Ceiling" in destroyed


def test_gallery_environment_removes_default_world_geometry(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    class Actor:
        def __init__(self, label):
            self.label = label

        def get_actor_label(self):
            return self.label

        def set_actor_label(self, label):
            self.label = label

    actors = [
        Actor("LandscapeStreamingProxy_0_0_0"),
        Actor("SM_SkySphere"),
        Actor("VolumetricCloud"),
        Actor("DirectionalLight"),
        Actor("CineU_Gallery_Floor"),
        Actor("painting_01"),
    ]
    destroyed = []

    class FakeLevelLibrary:
        @staticmethod
        def get_editor_world():
            return object()

        @staticmethod
        def get_all_level_actors():
            return actors

        @staticmethod
        def spawn_actor_from_class(actor_class, vector):
            return Actor("")

        @staticmethod
        def destroy_actor(actor):
            destroyed.append(actor.get_actor_label())

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary
        DirectionalLight = object
        SkyLight = object

        @staticmethod
        def Vector(*values):
            return values

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_world_ops, "_spawn_if_missing", lambda *args, **kwargs: None)

    cineu_world_ops.setup_environment({"level_name": "LVL_test", "environment": "gallery"})

    assert "LandscapeStreamingProxy_0_0_0" in destroyed
    assert "SM_SkySphere" in destroyed
    assert "VolumetricCloud" in destroyed
    assert "DirectionalLight" in destroyed
    assert "CineU_Gallery_Floor" not in destroyed
    assert "painting_01" not in destroyed


def test_gallery_environment_adds_interior_lights(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    class Actor:
        def __init__(self, label=""):
            self.label = label
            self.properties = {}

        def get_actor_label(self):
            return self.label

        def set_actor_label(self, label):
            self.label = label

        def set_actor_location(self, vector, sweep, teleport):
            self.location = vector

        def set_actor_rotation(self, rotator, teleport):
            self.rotation = rotator

        def set_editor_property(self, name, value):
            self.properties[name] = value

    spawned = []

    class FakeLevelLibrary:
        @staticmethod
        def get_editor_world():
            return object()

        @staticmethod
        def get_all_level_actors():
            return []

        @staticmethod
        def spawn_actor_from_class(actor_class, vector):
            actor = Actor()
            spawned.append((actor_class, actor, vector))
            return actor

        @staticmethod
        def destroy_actor(actor):
            return None

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary
        DirectionalLight = "DirectionalLight"
        PointLight = "PointLight"
        SkyLight = "SkyLight"

        @staticmethod
        def Vector(*values):
            return list(values)

        @staticmethod
        def Rotator(*values):
            return list(values)

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_world_ops, "_spawn_if_missing", lambda *args, **kwargs: None)

    cineu_world_ops.setup_environment({"level_name": "LVL_test", "environment": "gallery"})

    labels = [actor.get_actor_label() for _, actor, _ in spawned]
    assert "CineU_Gallery_KeyLight" in labels
    assert "CineU_Gallery_WallWashLight" in labels
    key = next(actor for _, actor, _ in spawned if actor.get_actor_label() == "CineU_Gallery_KeyLight")
    assert 100 <= key.properties["intensity"] <= 600


def test_support_surface_rehydration_removes_default_world_geometry(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    removed = []
    spawned = []
    lights = []

    monkeypatch.setattr(cineu_world_ops, "unreal", object())
    monkeypatch.setattr(cineu_world_ops, "_remove_default_scene_actors", lambda: removed.append("called"))
    monkeypatch.setattr(cineu_world_ops, "_spawn_if_missing", lambda label, *args, **kwargs: spawned.append(label))
    monkeypatch.setattr(cineu_world_ops, "_spawn_light_if_missing", lambda label, *args, **kwargs: lights.append(label))

    cineu_world_ops.ensure_support_surfaces({"gallery_floor": {}, "back_wall": {}})

    assert removed == ["called"]
    assert "CineU_Gallery_Floor" in spawned
    assert "CineU_Gallery_BackWall" in spawned
    assert "CineU_Gallery_Bench" in spawned
    assert "CineU_Gallery_Ceiling" not in spawned
    assert "CineU_Gallery_CeilingPanel" in spawned
    assert "CineU_Gallery_KeyLight" in lights


def test_spawn_many_applies_visual_profile_to_loaded_assets(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    class Actor:
        def set_actor_label(self, label):
            self.label = label

    actor = Actor()

    class FakeAssetLibrary:
        @staticmethod
        def load_asset(path):
            return object()

    class FakeLevelLibrary:
        @staticmethod
        def spawn_actor_from_object(asset, vector):
            return actor

    class FakeUnreal:
        EditorAssetLibrary = FakeAssetLibrary
        EditorLevelLibrary = FakeLevelLibrary

        @staticmethod
        def Vector(*values):
            return values

    profiles = []
    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_world_ops, "_apply_visual_profile", lambda spawned_actor, profile: profiles.append(profile))

    result = cineu_world_ops.spawn_many_actors(
        [
            {
                "actor_name": "sculpture_01",
                "semantic_type": "sculpture",
                "asset_type": "static_mesh",
                "asset_path": "/Game/CineU/Assets/Gallery/SM_WhiteSculpture",
            }
        ]
    )

    assert result["warnings"] == []
    assert actor.label == "sculpture_01"
    assert profiles[0]["material_label"] == "soft_stone"


def test_spawn_many_uses_loaded_painting_asset_when_available(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    class Actor:
        def set_actor_label(self, label):
            self.label = label

    actor = Actor()

    class FakeAssetLibrary:
        @staticmethod
        def load_asset(path):
            return object()

    class FakeLevelLibrary:
        @staticmethod
        def spawn_actor_from_object(asset, vector):
            return actor

    class FakeUnreal:
        EditorAssetLibrary = FakeAssetLibrary
        EditorLevelLibrary = FakeLevelLibrary

        @staticmethod
        def Vector(*values):
            return values

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_world_ops, "_apply_visual_profile", lambda spawned_actor, profile: None)

    result = cineu_world_ops.spawn_many_actors(
        [
            {
                "actor_name": "painting_01",
                "semantic_type": "painting",
                "asset_type": "static_mesh",
                "asset_path": "/Game/CineU/Assets/Gallery/SM_FramedPainting",
                "bounds_extent": [6, 70, 45],
            }
        ]
    )

    assert result["created_actors"] == ["painting_01"]
    assert result["warnings"] == []
    assert actor.label == "painting_01"


def test_spawn_many_reuses_existing_citypark_zebra_actor(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    class Actor:
        def __init__(self, label):
            self.label = label

        def get_actor_label(self):
            return self.label

        def set_actor_label(self, label):
            self.label = label

    existing = Actor("ANIM_Zebra_WalkTurnR")

    class FakeLevelLibrary:
        @staticmethod
        def spawn_actor_from_object(asset, vector):
            raise AssertionError("existing CityPark zebra should be reused instead of spawning another actor")

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(
        cineu_world_ops,
        "_find_actor_or_none",
        lambda actor_name: existing if actor_name == "ANIM_Zebra_WalkTurnR" else None,
    )
    monkeypatch.setattr(cineu_world_ops, "_apply_loaded_actor_materials", lambda actor, spec: None)

    result = cineu_world_ops.spawn_many_actors(
        [
            {
                "actor_name": "zebra_01",
                "reuse_actor_name": "ANIM_Zebra_WalkTurnR",
                "semantic_type": "zebra",
                "asset_type": "skeletal_mesh",
                "asset_path": "/Game/AfricanAnimalsPack/Zebra/Meshes/SK_Zebra",
                "materials": ["/Game/AfricanAnimalsPack/Zebra/Materials/M_Zebra"],
            }
        ]
    )

    assert existing.label == "zebra_01"
    assert result["created_actors"] == ["zebra_01"]
    assert result["reused_actors"] == [{"actor": "zebra_01", "source": "ANIM_Zebra_WalkTurnR"}]
    assert result["warnings"] == []


def test_spawn_many_uses_visible_proxy_when_painting_asset_is_missing(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    class FakeAssetLibrary:
        @staticmethod
        def load_asset(path):
            return None

    class FakeUnreal:
        EditorAssetLibrary = FakeAssetLibrary

    proxies = []
    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_world_ops, "_spawn_fallback_actor", lambda spec: proxies.append(spec) or object())

    result = cineu_world_ops.spawn_many_actors(
        [
            {
                "actor_name": "painting_01",
                "semantic_type": "painting",
                "asset_type": "static_mesh",
                "asset_path": "/Game/CineU/Assets/Gallery/SM_FramedPainting",
                "bounds_extent": [6, 70, 45],
            }
        ]
    )

    assert result["created_actors"] == ["painting_01"]
    assert result["warnings"][0]["reason"] == "asset_missing"
    assert proxies[0]["actor_name"] == "painting_01"


def test_ensure_actor_from_state_rehydrates_loaded_skeletal_asset(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    class ActorClass:
        @staticmethod
        def get_name():
            return "SkeletalMeshActor"

    class Actor:
        def __init__(self):
            self.label = None
            self.location = None
            self.rotation = None
            self.scale = None

        def get_class(self):
            return ActorClass()

        def set_actor_label(self, label):
            self.label = label

        def set_actor_location(self, vector, sweep, teleport):
            self.location = vector

        def set_actor_rotation(self, rotator, teleport):
            self.rotation = rotator

        def set_actor_scale3d(self, vector):
            self.scale = vector

    loaded_asset = object()
    actor = Actor()
    fallback_calls = []
    native_material_calls = []
    profiles = []

    class FakeAssetLibrary:
        @staticmethod
        def load_asset(path):
            return loaded_asset

    class FakeLevelLibrary:
        @staticmethod
        def spawn_actor_from_object(asset, vector):
            assert asset is loaded_asset
            return actor

    class FakeUnreal:
        EditorAssetLibrary = FakeAssetLibrary
        EditorLevelLibrary = FakeLevelLibrary

        @staticmethod
        def Vector(*values):
            return list(values)

        @staticmethod
        def Rotator(*values):
            return list(values)

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_world_ops, "_find_actor_or_none", lambda actor_name: None)
    monkeypatch.setattr(cineu_world_ops, "_spawn_fallback_actor", lambda spec: fallback_calls.append(spec) or Actor())
    monkeypatch.setattr(
        cineu_world_ops,
        "_apply_native_asset_materials",
        lambda spawned_actor, spec: native_material_calls.append((spawned_actor, spec["semantic_type"])) or True,
        raising=False,
    )
    monkeypatch.setattr(cineu_world_ops, "_apply_visual_profile", lambda spawned_actor, profile: profiles.append(profile))

    result = cineu_world_ops.ensure_actor_from_state(
        "zebra_01",
        {
            "name": "zebra_01",
            "semantic_type": "zebra",
            "asset_type": "skeletal_mesh",
            "source_type": "ue_project_content",
            "asset_path": "/Game/AfricanAnimalsPack/Zebra/Meshes/SK_Zebra",
            "materials": ["/Game/AfricanAnimalsPack/Zebra/Materials/M_Zebra"],
            "bounds_extent": [115, 35, 85],
            "transform": {"location": [10, 20, 85], "rotation": [0, 0, 90], "scale": [1, 1, 1]},
        },
    )

    assert result is actor
    assert actor.label == "zebra_01"
    assert actor.location == [10, 20, 85]
    assert actor.scale == [1, 1, 1]
    assert fallback_calls == []
    assert native_material_calls == [(actor, "zebra")]
    assert profiles == []


def test_ensure_actor_from_state_removes_stale_zebra_proxy_details(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    class Actor:
        def __init__(self, label, class_name):
            self.label = label
            self.class_name = class_name

        def get_actor_label(self):
            return self.label

        def get_name(self):
            return self.label

        def get_class(self):
            return type("ActorClass", (), {"get_name": lambda _self: self.class_name})()

        def set_actor_location(self, vector, sweep, teleport):
            pass

        def set_actor_rotation(self, rotator, teleport):
            self.rotation = rotator

        def set_actor_scale3d(self, vector):
            pass

    actor = Actor("zebra_01", "SkeletalMeshActor")
    stale_stripe = Actor("CineU_Zebra_Stripe_zebra_01_00", "StaticMeshActor")
    stale_asset_stripe = Actor("CineU_Zebra_AssetStripe_zebra_01_00", "StaticMeshActor")
    other_stripe = Actor("CineU_Zebra_Stripe_zebra_02_00", "StaticMeshActor")
    destroyed = []
    native_material_calls = []
    profiles = []

    class FakeLevelLibrary:
        @staticmethod
        def get_all_level_actors():
            return [actor, stale_stripe, stale_asset_stripe, other_stripe]

        @staticmethod
        def destroy_actor(actor_to_destroy):
            destroyed.append(actor_to_destroy.get_actor_label())

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary

        @staticmethod
        def Vector(*values):
            return list(values)

        @staticmethod
        def Rotator(*values):
            return list(values)

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(
        cineu_world_ops,
        "_apply_native_asset_materials",
        lambda spawned_actor, spec: native_material_calls.append((spawned_actor, spec["semantic_type"])) or True,
        raising=False,
    )
    monkeypatch.setattr(cineu_world_ops, "_apply_visual_profile", lambda spawned_actor, profile: profiles.append(profile))

    result = cineu_world_ops.ensure_actor_from_state(
        "zebra_01",
        {
            "name": "zebra_01",
            "semantic_type": "zebra",
            "asset_type": "skeletal_mesh",
            "asset_path": "/Game/AfricanAnimalsPack/Zebra/Meshes/SK_Zebra",
            "bounds_extent": [115, 35, 85],
            "transform": {"location": [0, 620, 0], "rotation": [0, 0, 90], "scale": [1, 1, 1]},
        },
    )

    assert result is actor
    assert native_material_calls == []
    assert [profile["material_label"] for profile in profiles] == ["zebra_asset_stripes"]
    assert destroyed == ["CineU_Zebra_Stripe_zebra_01_00", "CineU_Zebra_AssetStripe_zebra_01_00"]


def test_public_zebra_transparency_fix_hides_secondary_trs_slot(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    calls = []

    class Component:
        def get_num_materials(self):
            return 2

        def set_material(self, slot, material):
            calls.append(("set_material", slot, material))

        def show_material_section(self, slot, show, lod_index):
            calls.append(("show_material_section", slot, show, lod_index))

    class Actor:
        pass

    class FakeUnreal:
        pass

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_world_ops, "_visual_mesh_component", lambda actor: Component())
    monkeypatch.setattr(cineu_world_ops, "_ensure_public_zebra_texture_asset", lambda spec: "/Game/CineU/Imported/public_free/T_CadNav_Zebra")
    monkeypatch.setattr(cineu_world_ops, "_texture_asset_is_usable", lambda texture_path: True)
    monkeypatch.setattr(cineu_world_ops, "_solid_material_for_profile", lambda profile: calls.append(("profile", profile)) or f"Material:{profile['material_label']}")

    cineu_world_ops._apply_public_zebra_transparency_fix(
        Actor(),
        {
            "semantic_type": "zebra",
            "source_type": "public_free",
            "asset_path": "/Game/CineU/Imported/public_free/zebra1.zebra1",
        },
    )

    profiles = [call[1] for call in calls if call[0] == "profile"]
    assert [profile["material_label"] for profile in profiles] == ["public_zebra_texture", "zebra_trs_transparent"]
    assert profiles[0]["texture_path"] == "/Game/CineU/Imported/public_free/T_CadNav_Zebra"
    assert profiles[1]["opacity"] == 0.0
    assert ("set_material", 0, "Material:public_zebra_texture") in calls
    assert ("set_material", 1, "Material:zebra_trs_transparent") in calls
    assert ("show_material_section", 1, False, 0) in calls


def test_public_zebra_transparency_fix_skips_tiny_body_texture(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    calls = []

    class Component:
        def get_num_materials(self):
            return 2

        def set_material(self, slot, material):
            calls.append(("set_material", slot, material))

        def show_material_section(self, slot, show, lod_index):
            calls.append(("show_material_section", slot, show, lod_index))

    class Actor:
        pass

    class FakeUnreal:
        pass

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_world_ops, "_visual_mesh_component", lambda actor: Component())
    monkeypatch.setattr(cineu_world_ops, "_ensure_public_zebra_texture_asset", lambda spec: "/Game/CineU/Imported/public_free/T_CadNav_Zebra")
    monkeypatch.setattr(cineu_world_ops, "_texture_asset_is_usable", lambda texture_path: False)
    monkeypatch.setattr(cineu_world_ops, "_solid_material_for_profile", lambda profile: calls.append(("profile", profile)) or f"Material:{profile['material_label']}")

    cineu_world_ops._apply_public_zebra_transparency_fix(
        Actor(),
        {
            "semantic_type": "zebra",
            "source_type": "public_free",
            "asset_path": "/Game/CineU/Imported/public_free/zebra1.zebra1",
        },
    )

    profiles = [call[1] for call in calls if call[0] == "profile"]
    assert [profile["material_label"] for profile in profiles] == ["zebra_trs_transparent"]
    assert ("set_material", 0, "Material:public_zebra_texture") not in calls
    assert ("set_material", 1, "Material:zebra_trs_transparent") in calls
    assert ("show_material_section", 1, False, 0) in calls


def test_hide_component_material_section_supports_two_arg_unreal_api(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    calls = []

    class Component:
        def show_material_section(self, *args):
            calls.append(args)
            if len(args) == 3:
                raise TypeError("two-arg API")

    assert cineu_world_ops._hide_component_material_section(Component(), 1) is True
    assert calls == [(1, False, 0), (1, False)]


def test_apply_actor_transforms_preserves_bounds_driven_proxy_scale(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    class Actor:
        def __init__(self):
            self.location = None
            self.rotation = None
            self.scale = None

        def set_actor_location(self, vector, sweep, teleport):
            self.location = vector

        def set_actor_rotation(self, rotator, teleport):
            self.rotation = rotator

        def set_actor_scale3d(self, vector):
            self.scale = vector

    class FakeUnreal:
        @staticmethod
        def Vector(*values):
            return list(values)

        @staticmethod
        def Rotator(*values):
            return list(values)

    actor = Actor()
    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_world_ops, "_find_actor", lambda actor_name: actor)
    monkeypatch.setattr(cineu_world_ops, "_spawn_if_missing", lambda *args, **kwargs: None)

    cineu_world_ops.apply_actor_transforms(
        [
            {
                "actor_name": "painting_01",
                "bounds_extent": [6, 130, 85],
                "transform": {
                    "location": [0, 494, 180],
                    "rotation": [0, 0, -90],
                    "scale": [1, 1, 1],
                },
            }
        ]
    )

    assert actor.scale == [0.12, 2.6, 1.7]


def test_apply_actor_transforms_keeps_real_skeletal_asset_scale(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    class ActorClass:
        @staticmethod
        def get_name():
            return "SkeletalMeshActor"

    class Actor:
        def __init__(self):
            self.location = None
            self.rotation = None
            self.scale = None

        def get_class(self):
            return ActorClass()

        def set_actor_location(self, vector, sweep, teleport):
            self.location = vector

        def set_actor_rotation(self, rotator, teleport):
            self.rotation = rotator

        def set_actor_scale3d(self, vector):
            self.scale = vector

    spawned = []

    class FakeUnreal:
        @staticmethod
        def Vector(*values):
            return list(values)

        @staticmethod
        def Rotator(*values):
            return list(values)

    actor = Actor()
    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_world_ops, "_find_actor", lambda actor_name: actor)
    monkeypatch.setattr(cineu_world_ops, "_spawn_if_missing", lambda *args, **kwargs: spawned.append(args))

    cineu_world_ops.apply_actor_transforms(
        [
            {
                "actor_name": "zebra_01",
                "bounds_extent": [115, 35, 85],
                "transform": {
                    "location": [0, 0, 85],
                    "rotation": [0, 0, 0],
                    "scale": [1, 1, 1],
                },
            }
        ]
    )

    assert actor.scale == [1, 1, 1]
    assert not any(item[0].startswith("CineU_Zebra_Stripe_zebra_01_") for item in spawned)


def test_apply_actor_transforms_adds_gallery_painting_wall_details(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    class Actor:
        def set_actor_location(self, vector, sweep, teleport):
            pass

        def set_actor_rotation(self, rotator, teleport):
            pass

        def set_actor_scale3d(self, vector):
            pass

    spawned = []

    class FakeUnreal:
        @staticmethod
        def Vector(*values):
            return list(values)

        @staticmethod
        def Rotator(*values):
            return list(values)

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_world_ops, "_find_actor", lambda actor_name: Actor())
    monkeypatch.setattr(cineu_world_ops, "_spawn_if_missing", lambda label, shape, location, scale, rotation=None: spawned.append((label, location, scale, rotation)))

    cineu_world_ops.apply_actor_transforms(
        [
            {
                "actor_name": "painting_01",
                "target": "back_wall",
                "bounds_extent": [6, 130, 85],
                "transform": {
                    "location": [0, 494, 180],
                    "rotation": [0, 0, -90],
                    "scale": [1, 1, 1],
                },
            }
        ]
    )

    labels = [item[0] for item in spawned]
    assert "CineU_Gallery_Label_painting_01" in labels
    assert "CineU_Gallery_ArtAccent_painting_01" in labels
    stripe_labels = [label for label in labels if label.startswith("CineU_Gallery_ArtStripe_painting_01_")]
    assert len(stripe_labels) >= 4
    brush_labels = [label for label in labels if label.startswith("CineU_Gallery_ArtBrush")]
    assert len(brush_labels) >= 20
    assert any("ArtBrushLight" in label for label in brush_labels)
    assert any("ArtBrushShadow" in label for label in brush_labels)
    assert any("ArtBrushWarm" in label for label in brush_labels)
    label = next(item for item in spawned if item[0] == "CineU_Gallery_Label_painting_01")
    accent = next(item for item in spawned if item[0] == "CineU_Gallery_ArtAccent_painting_01")
    assert label[1][1] < 494
    assert label[1][2] < 120
    assert label[2][1] >= 0.5
    assert accent[2][1] >= 0.9
    assert accent[2][2] >= 0.4
    stripe = next(item for item in spawned if item[0] == "CineU_Gallery_ArtStripe_painting_01_00")
    assert stripe[1][1] < 494
    assert stripe[2][1] >= 0.2
    brush = next(item for item in spawned if item[0] == "CineU_Gallery_ArtBrushLight_painting_01_00")
    assert brush[1][1] < stripe[1][1]
    assert brush[2][1] >= 0.4
    vertical_brushes = [item for item in spawned if item[0].startswith("CineU_Gallery_ArtBrush") and item[2][2] >= 0.25 and item[2][1] <= 0.18]
    assert len(vertical_brushes) >= 3
    brush_rotations = {tuple(item[3]) for item in spawned if item[0].startswith("CineU_Gallery_ArtBrush")}
    assert len(brush_rotations) >= 3


def test_apply_actor_transforms_adds_zebra_stripe_proxy_details(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    class Actor:
        def set_actor_location(self, vector, sweep, teleport):
            pass

        def set_actor_rotation(self, rotator, teleport):
            pass

        def set_actor_scale3d(self, vector):
            pass

    spawned = []

    class FakeUnreal:
        @staticmethod
        def Vector(*values):
            return list(values)

        @staticmethod
        def Rotator(*values):
            return list(values)

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_world_ops, "_find_actor", lambda actor_name: Actor())
    monkeypatch.setattr(cineu_world_ops, "_spawn_if_missing", lambda label, shape, location, scale, rotation=None: spawned.append((label, shape, location, scale, rotation)))

    cineu_world_ops.apply_actor_transforms(
        [
            {
                "actor_name": "zebra_01",
                "bounds_extent": [115, 35, 85],
                "transform": {
                    "location": [0, 0, 85],
                    "rotation": [0, 0, 0],
                    "scale": [1, 1, 1],
                },
            }
        ]
    )

    stripe_labels = [item[0] for item in spawned if item[0].startswith("CineU_Zebra_Stripe_zebra_01_")]
    assert len(stripe_labels) >= 6
    assert all(item[1] == "cube" for item in spawned if item[0].startswith("CineU_Zebra_Stripe_zebra_01_"))
    assert any(item[4][2] != 0 for item in spawned if item[0].startswith("CineU_Zebra_Stripe_zebra_01_"))


def test_apply_actor_transforms_preserves_real_skeletal_zebra_details(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    class Actor:
        def __init__(self, label, class_name):
            self.label = label
            self.class_name = class_name
            self.rotation = None

        def get_actor_label(self):
            return self.label

        def get_name(self):
            return self.label

        def get_class(self):
            return type("ActorClass", (), {"get_name": lambda _self: self.class_name})()

        def set_actor_location(self, vector, sweep, teleport):
            pass

        def set_actor_rotation(self, rotator, teleport):
            self.rotation = rotator

        def set_actor_scale3d(self, vector):
            pass

    spawned = []
    destroyed = []
    actor = Actor("zebra_01", "SkeletalMeshActor")
    stale_body_stripe = Actor("CineU_Zebra_Stripe_zebra_01_00", "StaticMeshActor")
    stale_leg_stripe = Actor("CineU_Zebra_Stripe_zebra_01_leg_00", "StaticMeshActor")
    other_stripe = Actor("CineU_Zebra_Stripe_zebra_02_00", "StaticMeshActor")

    class FakeLevelLibrary:
        @staticmethod
        def get_all_level_actors():
            return [actor, stale_body_stripe, stale_leg_stripe, other_stripe]

        @staticmethod
        def destroy_actor(actor_to_destroy):
            destroyed.append(actor_to_destroy.get_actor_label())

    class FakeUnreal:
        EditorLevelLibrary = FakeLevelLibrary

        @staticmethod
        def Vector(*values):
            return list(values)

        @staticmethod
        def Rotator(*values):
            return list(values)

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_world_ops, "_spawn_if_missing", lambda label, shape, location, scale, rotation=None: spawned.append((label, shape, location, scale, rotation)))

    cineu_world_ops.apply_actor_transforms(
        [
            {
                "actor_name": "zebra_01",
                "asset_type": "skeletal_mesh",
                "bounds_extent": [115, 35, 85],
                "transform": {
                    "location": [0, 620, 0],
                    "rotation": [0, 0, 90],
                    "scale": [1, 1, 1],
                },
            }
        ]
    )

    stripe_labels = [item[0] for item in spawned if item[0].startswith("CineU_Zebra_Stripe_zebra_01_")]
    assert stripe_labels == []
    assert not any(item[0].startswith("CineU_Zebra_AssetStripe_zebra_01_") for item in spawned)
    assert destroyed == ["CineU_Zebra_Stripe_zebra_01_00", "CineU_Zebra_Stripe_zebra_01_leg_00"]
    assert actor.rotation[2] == 0.0


def test_apply_actor_transforms_emphasizes_center_gallery_painting(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    class Actor:
        def set_actor_location(self, vector, sweep, teleport):
            pass

        def set_actor_rotation(self, rotator, teleport):
            pass

        def set_actor_scale3d(self, vector):
            pass

    spawned = []

    class FakeUnreal:
        @staticmethod
        def Vector(*values):
            return list(values)

        @staticmethod
        def Rotator(*values):
            return list(values)

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_world_ops, "_find_actor", lambda actor_name: Actor())
    monkeypatch.setattr(cineu_world_ops, "_spawn_if_missing", lambda label, shape, location, scale, rotation=None: spawned.append((label, location, scale, rotation)))

    cineu_world_ops.apply_actor_transforms(
        [
            {
                "actor_name": "painting_02",
                "target": "back_wall",
                "bounds_extent": [6, 130, 85],
                "transform": {"location": [0, 494, 180], "rotation": [0, 0, -90], "scale": [1, 1, 1]},
            }
        ]
    )

    hero = next(item for item in spawned if item[0] == "CineU_Gallery_HeroBackdrop_painting_02")
    assert hero[2][1] >= 3.5
    assert hero[2][2] >= 2.0
    brush = next(item for item in spawned if item[0] == "CineU_Gallery_ArtBrushLight_painting_02_00")
    assert abs(brush[1][0]) >= 55.0
    flow_labels = [item[0] for item in spawned if item[0].startswith("CineU_Gallery_ArtFlow")]
    assert len(flow_labels) >= 36
    assert any("ArtFlowLight" in label for label in flow_labels)
    assert any("ArtFlowShadow" in label for label in flow_labels)
    flow_segments = [item for item in spawned if item[0].startswith("CineU_Gallery_ArtFlowLight")]
    flow_xs = [item[1][0] for item in flow_segments]
    flow_zs = [item[1][2] for item in flow_segments]
    assert max(flow_xs) - min(flow_xs) >= 110.0
    assert max(flow_zs) - min(flow_zs) >= 45.0
    assert len({tuple(item[3]) for item in flow_segments}) >= 8


def test_ensure_actor_from_state_uses_surface_profile_for_gallery_details(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    spawned = {}

    monkeypatch.setattr(cineu_world_ops, "unreal", object())
    monkeypatch.setattr(cineu_world_ops, "_find_actor_or_none", lambda actor_name: None)
    monkeypatch.setattr(
        cineu_world_ops,
        "_spawn_shape",
        lambda label, shape, location, scale, rotation=None, profile=None: spawned.setdefault(label, profile),
    )

    cineu_world_ops.ensure_actor_from_state(
        "CineU_Gallery_Label_painting_01",
        {
            "name": "CineU_Gallery_Label_painting_01",
            "transform": {"location": [0, 480, 80], "rotation": [0, 0, -90], "scale": [0.03, 0.55, 0.26]},
            "bounds_extent": [27.5, 1.5, 13],
        },
    )

    assert spawned["CineU_Gallery_Label_painting_01"]["material_label"] == "gallery_label_card"


def test_visual_profile_falls_back_to_basic_shape_material_parent(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    calls = []

    class FakeMaterial:
        def set_vector_parameter_value(self, parameter, color):
            calls.append(("param", parameter, color))

    class FakeComponent:
        def create_dynamic_material_instance(self, slot, parent=None):
            calls.append(("parent", parent))
            return FakeMaterial()

    class FakeActor:
        def get_static_mesh_component(self):
            return FakeComponent()

    class FakeAssetLibrary:
        @staticmethod
        def load_asset(path):
            calls.append(("load", path))
            return "BasicShapeMaterial"

    class FakeUnreal:
        EditorAssetLibrary = FakeAssetLibrary

        class LinearColor:
            def __init__(self, r, g, b, a):
                self.values = [r, g, b, a]

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_world_ops, "_solid_material_for_profile", lambda profile: None)

    cineu_world_ops._apply_visual_profile(FakeActor(), {"color": [0.1, 0.2, 0.3]})

    assert ("load", "/Engine/BasicShapes/BasicShapeMaterial") in calls
    assert ("parent", "BasicShapeMaterial") in calls
    assert any(call[0] == "param" and call[1] == "Color" for call in calls)


def test_visual_profile_assigns_generated_solid_material(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    calls = []

    class FakeComponent:
        def set_material(self, slot, material):
            calls.append(("set", slot, material))

        def create_dynamic_material_instance(self, slot, parent=None):
            calls.append(("dynamic", parent))
            return None

    class FakeActor:
        def get_static_mesh_component(self):
            return FakeComponent()

    class FakeAssetLibrary:
        @staticmethod
        def load_asset(path):
            calls.append(("load", path))
            return None

        @staticmethod
        def save_loaded_asset(asset):
            calls.append(("save", asset))

    class FakeAssetTools:
        def create_asset(self, name, package_path, asset_class, factory):
            calls.append(("create", name, package_path))
            return "CreatedMaterial"

    class FakeAssetToolsHelpers:
        @staticmethod
        def get_asset_tools():
            return FakeAssetTools()

    class FakeMaterialEditingLibrary:
        @staticmethod
        def create_material_expression(material, expression_class, x, y):
            return object()

        @staticmethod
        def connect_material_property(expression, output_name, material_property):
            calls.append(("connect", material_property))

        @staticmethod
        def recompile_material(material):
            calls.append(("recompile", material))

    class FakeUnreal:
        EditorAssetLibrary = FakeAssetLibrary
        AssetToolsHelpers = FakeAssetToolsHelpers
        MaterialEditingLibrary = FakeMaterialEditingLibrary
        Material = object
        MaterialFactoryNew = object
        MaterialExpressionVectorParameter = object

        class MaterialProperty:
            MP_BASE_COLOR = "base_color"

        class LinearColor:
            def __init__(self, r, g, b, a):
                self.values = [r, g, b, a]

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)

    cineu_world_ops._apply_visual_profile(FakeActor(), {"material_label": "test_mat", "color": [0.1, 0.2, 0.3]})

    assert ("create", "M_CineU_test_mat", "/Game/CineU/Generated/Materials") in calls
    assert ("set", 0, "CreatedMaterial") in calls
    assert not any(call[0] == "dynamic" for call in calls)


def test_visual_profile_assigns_generated_solid_material_to_skeletal_component(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    calls = []

    class FakeComponent:
        def set_material(self, slot, material):
            calls.append(("set", slot, material))

        def create_dynamic_material_instance(self, slot, parent=None):
            calls.append(("dynamic", parent))
            return None

    class FakeActor:
        def get_component_by_class(self, component_class):
            calls.append(("component", component_class))
            return FakeComponent()

    class FakeUnreal:
        SkeletalMeshComponent = "SkeletalMeshComponent"

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)
    monkeypatch.setattr(cineu_world_ops, "_solid_material_for_profile", lambda profile: "GeneratedMaterial")

    cineu_world_ops._apply_visual_profile(FakeActor(), {"color": [0.92, 0.9, 0.84]})

    assert ("component", "SkeletalMeshComponent") in calls
    assert ("set", 0, "GeneratedMaterial") in calls
    assert not any(call[0] == "dynamic" for call in calls)


def test_existing_generated_material_is_reused_by_default(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    existing = object()

    class FakeAssetLibrary:
        @staticmethod
        def load_asset(path):
            assert path == "/Game/CineU/Generated/Materials/M_CineU_cafe_brick"
            return existing

    class FakeUnreal:
        EditorAssetLibrary = FakeAssetLibrary

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)
    assert cineu_world_ops._solid_material_for_profile({"material_label": "cafe_brick"}) is existing


def test_existing_generated_material_is_reconfigured(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    calls = []

    class FakeExpression:
        def set_editor_property(self, name, value):
            calls.append(("expr_prop", name))

    class FakeAssetLibrary:
        @staticmethod
        def load_asset(path):
            calls.append(("load", path))
            return "ExistingMaterial"

        @staticmethod
        def save_loaded_asset(asset):
            calls.append(("save", asset))

    class FakeMaterialEditingLibrary:
        @staticmethod
        def delete_all_material_expressions(material):
            calls.append(("delete_all_expr", material))

        @staticmethod
        def create_material_expression(material, expression_class, x, y):
            calls.append(("create_expr", material))
            return FakeExpression()

        @staticmethod
        def connect_material_property(expression, output_name, material_property):
            calls.append(("connect", material_property))

        @staticmethod
        def recompile_material(material):
            calls.append(("recompile", material))

    class FakeUnreal:
        EditorAssetLibrary = FakeAssetLibrary
        MaterialEditingLibrary = FakeMaterialEditingLibrary
        MaterialExpressionVectorParameter = object

        class MaterialProperty:
            MP_BASE_COLOR = "base_color"
            MP_EMISSIVE_COLOR = "emissive"

        class LinearColor:
            def __init__(self, r, g, b, a):
                self.values = [r, g, b, a]

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)

    material = cineu_world_ops._solid_material_for_profile({"material_label": "test_mat", "color": [0.1, 0.2, 0.3], "reuse_existing_if_present": False})

    assert material == "ExistingMaterial"
    assert ("delete_all_expr", "ExistingMaterial") in calls
    assert calls.index(("delete_all_expr", "ExistingMaterial")) < calls.index(("create_expr", "ExistingMaterial"))
    assert ("create_expr", "ExistingMaterial") in calls
    assert ("connect", "base_color") in calls
    assert ("connect", "emissive") not in calls


def test_generated_material_connects_surface_scalar_properties(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    calls = []

    class FakeExpression:
        def __init__(self, expression_class):
            self.expression_class = expression_class

        def set_editor_property(self, name, value):
            if self.expression_class == "texture" and name == "parameter_name":
                raise RuntimeError("plain texture sample has no parameter name")
            calls.append(("expr_prop", name, value))

    class FakeAssetLibrary:
        @staticmethod
        def load_asset(path):
            return "ExistingMaterial"

        @staticmethod
        def save_loaded_asset(asset):
            calls.append(("save", asset))

    class FakeMaterialEditingLibrary:
        @staticmethod
        def create_material_expression(material, expression_class, x, y):
            calls.append(("create_expr", expression_class, x, y))
            return FakeExpression(expression_class)

        @staticmethod
        def connect_material_property(expression, output_name, material_property):
            calls.append(("connect", expression.expression_class, output_name, material_property))
            if expression.expression_class == "texture" and output_name == "":
                raise RuntimeError("texture sample output must be explicit")

        @staticmethod
        def recompile_material(material):
            calls.append(("recompile", material))

    class FakeUnreal:
        EditorAssetLibrary = FakeAssetLibrary
        MaterialEditingLibrary = FakeMaterialEditingLibrary
        MaterialExpressionVectorParameter = "vector"
        MaterialExpressionScalarParameter = "scalar"

        class MaterialProperty:
            MP_BASE_COLOR = "base_color"
            MP_ROUGHNESS = "roughness"
            MP_SPECULAR = "specular"
            MP_METALLIC = "metallic"

        class LinearColor:
            def __init__(self, r, g, b, a):
                self.values = [r, g, b, a]

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)

    cineu_world_ops._solid_material_for_profile(
        {"material_label": "polished_dark_floor", "color": [0.08, 0.075, 0.07], "roughness": 0.18, "specular": 0.8, "metallic": 0.0, "reuse_existing_if_present": False}
    )

    assert ("connect", "vector", "", "base_color") in calls
    assert ("connect", "scalar", "", "roughness") in calls
    assert ("connect", "scalar", "", "specular") in calls
    assert ("connect", "scalar", "", "metallic") in calls
    assert ("expr_prop", "parameter_name", "Roughness") in calls
    assert ("expr_prop", "parameter_name", "Specular") in calls


def test_generated_material_connects_emissive_only_when_requested(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    calls = []

    class FakeExpression:
        def set_editor_property(self, name, value):
            calls.append(("expr_prop", name, value))

    class FakeAssetLibrary:
        @staticmethod
        def load_asset(path):
            return "ExistingMaterial"

        @staticmethod
        def save_loaded_asset(asset):
            return None

    class FakeMaterialEditingLibrary:
        @staticmethod
        def create_material_expression(material, expression_class, x, y):
            return FakeExpression()

        @staticmethod
        def connect_material_property(expression, output_name, material_property):
            calls.append(("connect", material_property))

        @staticmethod
        def recompile_material(material):
            return None

    class FakeUnreal:
        EditorAssetLibrary = FakeAssetLibrary
        MaterialEditingLibrary = FakeMaterialEditingLibrary
        MaterialExpressionVectorParameter = object
        MaterialExpressionScalarParameter = object

        class MaterialProperty:
            MP_BASE_COLOR = "base_color"
            MP_EMISSIVE_COLOR = "emissive"

        class LinearColor:
            def __init__(self, r, g, b, a):
                self.values = [r, g, b, a]

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)

    cineu_world_ops._solid_material_for_profile({"material_label": "sun_patch", "color": [1.0, 0.9, 0.7], "emissive_strength": 2.0, "reuse_existing_if_present": False})

    assert ("connect", "base_color") in calls
    assert ("connect", "emissive") in calls


def test_generated_material_connects_zebra_asset_texture(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    calls = []

    class FakeExpression:
        def __init__(self, expression_class):
            self.expression_class = expression_class

        def set_editor_property(self, name, value):
            if self.expression_class == "texture" and name == "parameter_name":
                raise RuntimeError("plain texture sample has no parameter name")
            calls.append(("expr_prop", name, value))

    class FakeAssetLibrary:
        @staticmethod
        def load_asset(path):
            calls.append(("load", path))
            if path == "/Game/CineU/Generated/Materials/M_CineU_zebra_asset_stripes":
                return "ExistingMaterial"
            if path == "/Game/AfricanAnimalsPack/Zebra/Textures/T_Zebra_BaseColor":
                return "ZebraBaseColorTexture"
            return None

        @staticmethod
        def save_loaded_asset(asset):
            return None

    class FakeMaterialEditingLibrary:
        @staticmethod
        def create_material_expression(material, expression_class, x, y):
            calls.append(("create_expr", expression_class, x, y))
            return FakeExpression(expression_class)

        @staticmethod
        def connect_material_property(expression, output_name, material_property):
            calls.append(("connect", expression.expression_class, output_name, material_property))
            if expression.expression_class == "texture" and output_name == "":
                raise RuntimeError("texture sample output must be explicit")

        @staticmethod
        def set_material_usage(material, usage):
            calls.append(("usage", material, usage))
            return True

        @staticmethod
        def recompile_material(material):
            return None

    class FakeUnreal:
        EditorAssetLibrary = FakeAssetLibrary
        MaterialEditingLibrary = FakeMaterialEditingLibrary
        MaterialExpressionVectorParameter = "vector"
        MaterialExpressionTextureSample = "texture"
        MaterialExpressionTextureSampleParameter2D = "texture_parameter"
        MaterialExpressionScalarParameter = "scalar"

        class MaterialProperty:
            MP_BASE_COLOR = "base_color"
            MP_EMISSIVE_COLOR = "emissive"

        class MaterialUsage:
            MATUSAGE_SKELETAL_MESH = "skeletal_mesh"

        class LinearColor:
            def __init__(self, r, g, b, a):
                self.values = [r, g, b, a]

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)

    cineu_world_ops._solid_material_for_profile(
        {
            "material_label": "zebra_asset_stripes",
            "reuse_existing_if_present": False,
            "color": [0.98, 0.95, 0.86],
            "texture_path": "/Game/AfricanAnimalsPack/Zebra/Textures/T_Zebra_BaseColor",
            "emissive_texture": True,
            "used_with_skeletal_mesh": True,
        }
    )

    assert ("load", "/Game/AfricanAnimalsPack/Zebra/Textures/T_Zebra_BaseColor") in calls
    assert ("create_expr", "texture", -320, 0) in calls
    assert ("expr_prop", "texture", "ZebraBaseColorTexture") in calls
    assert ("connect", "texture", "RGB", "base_color") in calls
    assert ("connect", "texture", "RGB", "emissive") in calls
    assert ("usage", "ExistingMaterial", "skeletal_mesh") in calls


def test_generated_material_connects_texture_coordinate_tiling(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    calls = []

    class FakeExpression:
        def __init__(self, expression_class):
            self.expression_class = expression_class

        def set_editor_property(self, name, value):
            calls.append(("expr_prop", self.expression_class, name, value))

    class FakeAssetLibrary:
        @staticmethod
        def load_asset(path):
            calls.append(("load", path))
            if path == "/Game/CineU/Generated/Materials/M_CineU_park_path_warm_stone":
                return "ExistingMaterial"
            if path == "/Game/CityPark/Textures/Road/T_Sidewalk02_D":
                return "ParkPathTexture"
            return None

        @staticmethod
        def save_loaded_asset(asset):
            return None

    class FakeMaterialEditingLibrary:
        @staticmethod
        def create_material_expression(material, expression_class, x, y):
            calls.append(("create_expr", expression_class, x, y))
            return FakeExpression(expression_class)

        @staticmethod
        def connect_material_expressions(from_expression, from_output_name, to_expression, to_input_name):
            calls.append(("connect_expr", from_expression.expression_class, from_output_name, to_expression.expression_class, to_input_name))

        @staticmethod
        def connect_material_property(expression, output_name, material_property):
            calls.append(("connect", material_property))

        @staticmethod
        def recompile_material(material):
            return None

    class FakeUnreal:
        EditorAssetLibrary = FakeAssetLibrary
        MaterialEditingLibrary = FakeMaterialEditingLibrary
        MaterialExpressionVectorParameter = "vector"
        MaterialExpressionTextureSampleParameter2D = "texture"
        MaterialExpressionTextureCoordinate = "texcoord"
        MaterialExpressionScalarParameter = "scalar"

        class MaterialProperty:
            MP_BASE_COLOR = "base_color"

        class LinearColor:
            def __init__(self, r, g, b, a):
                self.values = [r, g, b, a]

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)

    cineu_world_ops._solid_material_for_profile(
        {
            "material_label": "park_path_warm_stone",
            "reuse_existing_if_present": False,
            "color": [0.74, 0.72, 0.64],
            "texture_path": "/Game/CityPark/Textures/Road/T_Sidewalk02_D",
            "texture_tiling": [8.0, 24.0],
        }
    )

    assert ("create_expr", "texcoord", -520, 0) in calls
    assert ("expr_prop", "texcoord", "u_tiling", 8.0) in calls
    assert ("expr_prop", "texcoord", "v_tiling", 24.0) in calls
    assert ("connect_expr", "texcoord", "", "texture", "UVs") in calls
    assert ("connect", "base_color") in calls


def test_generated_material_connects_opacity_for_translucent_glass(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    import cineu_world_ops

    calls = []

    class FakeMaterial:
        def set_editor_property(self, name, value):
            calls.append(("material_prop", name, value))

    class FakeExpression:
        def set_editor_property(self, name, value):
            calls.append(("expr_prop", name, value))

    class FakeAssetLibrary:
        @staticmethod
        def load_asset(path):
            return FakeMaterial()

        @staticmethod
        def save_loaded_asset(asset):
            return None

    class FakeMaterialEditingLibrary:
        @staticmethod
        def create_material_expression(material, expression_class, x, y):
            calls.append(("create_expr", expression_class, x, y))
            return FakeExpression()

        @staticmethod
        def connect_material_property(expression, output_name, material_property):
            calls.append(("connect", material_property))

        @staticmethod
        def recompile_material(material):
            return None

    class FakeUnreal:
        EditorAssetLibrary = FakeAssetLibrary
        MaterialEditingLibrary = FakeMaterialEditingLibrary
        MaterialExpressionVectorParameter = "vector"
        MaterialExpressionScalarParameter = "scalar"

        class BlendMode:
            BLEND_TRANSLUCENT = "translucent"

        class MaterialProperty:
            MP_BASE_COLOR = "base_color"
            MP_OPACITY = "opacity"

        class LinearColor:
            def __init__(self, r, g, b, a):
                self.values = [r, g, b, a]

    monkeypatch.setattr(cineu_world_ops, "unreal", FakeUnreal)

    cineu_world_ops._solid_material_for_profile({"material_label": "gallery_glass_daylight", "color": [0.8, 0.9, 1.0], "opacity": 0.32, "reuse_existing_if_present": False})

    assert ("material_prop", "blend_mode", "translucent") in calls
    assert ("connect", "opacity") in calls
    assert ("expr_prop", "parameter_name", "Opacity") in calls
