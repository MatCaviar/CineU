from __future__ import annotations

from typing import Any
import math
import re
import struct
from pathlib import Path

from cineu_unreal_math import rotator_from_pitch_roll_yaw

try:
    import unreal  # type: ignore
except Exception:  # pragma: no cover - only available inside Unreal Editor
    unreal = None


CITYPARK_PATH_ANCHOR_ACTOR = "InstancedFoliageActor2"
CITYPARK_PATH_Z = -630.004
CITYPARK_PATH_BOUNDS = [5600.0, 6800.0, -12650.0, -11850.0]
CITYPARK_PATH_X = 6241.53
CITYPARK_PATH_CENTER_Y = -12153.676
GENERATED_ZEBRA_STRIPE_TEXTURE_PATH = "/Game/CineU/Generated/Textures/T_CineU_Zebra_Stripes"
PUBLIC_ZEBRA_TEXTURE_ASSET_PATH = "/Game/CineU/Imported/public_free/T_CadNav_Zebra"


def _asset_backed_zebra_base_color_texture_path(spec: dict[str, Any]) -> str | None:
    asset_path = str(spec.get("asset_path") or "").replace("\\", "/")
    if str(spec.get("semantic_type", "")).lower() != "zebra":
        return None
    if not asset_path.endswith("/Meshes/SK_Zebra"):
        return None
    return f"{asset_path.rsplit('/Meshes/', 1)[0]}/Textures/T_Zebra_BaseColor"


def _citypark_path_support_surface(level_backed: bool = False) -> dict[str, Any]:
    surface: dict[str, Any] = {
        "type": "ground",
        "z": CITYPARK_PATH_Z,
        "bounds": list(CITYPARK_PATH_BOUNDS),
        "anchor_actor": CITYPARK_PATH_ANCHOR_ACTOR,
    }
    if level_backed:
        surface["environment_asset_type"] = "level"
    return surface


def _require_unreal():
    if unreal is None:
        raise RuntimeError("This module must be executed inside Unreal Editor Python.")


def _fallback_shape_for_actor(spec: dict[str, Any]) -> str:
    semantic = str(spec.get("semantic_type", "")).lower()
    asset_type = str(spec.get("asset_type", "")).lower()
    if "painting" in semantic:
        return "cube"
    if "sculpture" in semantic:
        return "sphere"
    if asset_type == "skeletal_mesh" or semantic in {"zebra", "wolf", "horse", "deer", "human"}:
        return "capsule"
    return "cube"


def _visual_profile_for_actor(spec: dict[str, Any]) -> dict[str, Any]:
    shape = _fallback_shape_for_actor(spec)
    semantic = str(spec.get("semantic_type", "")).lower()
    asset_type = str(spec.get("asset_type", "")).lower()
    if "painting" in semantic:
        return {"shape": shape, "color": [0.035, 0.032, 0.03], "material_label": "gallery_art_dark", "roughness": 0.42, "specular": 0.55, "metallic": 0.0}
    if "sculpture" in semantic:
        return {"shape": shape, "color": [0.88, 0.86, 0.82], "material_label": "soft_stone", "roughness": 0.34, "specular": 0.38, "metallic": 0.0}
    if semantic == "zebra":
        asset_texture_path = _asset_backed_zebra_base_color_texture_path(spec)
        if asset_texture_path:
            return {
                "shape": shape,
                "color": [0.98, 0.95, 0.86],
                "material_label": "zebra_asset_stripes",
                "texture_path": asset_texture_path,
                "texture_tiling": [1.0, 1.0],
                "emissive_texture": True,
                "used_with_skeletal_mesh": True,
                "roughness": 0.56,
                "specular": 0.24,
                "metallic": 0.0,
            }
        return {
            "shape": shape,
            "color": [0.98, 0.95, 0.86],
            "material_label": "zebra_generated_stripes",
            "texture_path": GENERATED_ZEBRA_STRIPE_TEXTURE_PATH,
            "texture_tiling": [1.0, 1.0],
            "emissive_texture": True,
            "emissive_strength": 0.0,
            "used_with_skeletal_mesh": True,
            "roughness": 0.54,
            "specular": 0.30,
            "metallic": 0.0,
        }
    if asset_type == "skeletal_mesh" or semantic in {"wolf", "horse", "deer", "human"}:
        return {"shape": shape, "color": [0.08, 0.08, 0.07], "material_label": "dark_silhouette", "roughness": 0.5, "specular": 0.3, "metallic": 0.0}
    return {"shape": shape, "color": [0.42, 0.52, 0.62], "material_label": "neutral_blue_gray", "roughness": 0.55, "specular": 0.25, "metallic": 0.0}


def _visual_profile_for_surface(label: str) -> dict[str, Any] | None:
    lowered = label.lower()
    if "gallery_floor" in lowered:
        return {"color": [0.055, 0.052, 0.048], "material_label": "polished_dark_floor", "roughness": 0.16, "specular": 0.78, "metallic": 0.0}
    if "gallery_label" in lowered:
        return {"color": [0.96, 0.94, 0.88], "material_label": "gallery_label_card", "roughness": 0.55, "specular": 0.25, "metallic": 0.0}
    if "gallery_artbrushlight" in lowered or "gallery_art_brush_light" in lowered:
        return {"color": [0.95, 0.92, 0.84], "material_label": "gallery_art_brush_light", "roughness": 0.28, "specular": 0.52, "metallic": 0.0}
    if "gallery_artbrushshadow" in lowered or "gallery_art_brush_shadow" in lowered:
        return {"color": [0.12, 0.105, 0.09], "material_label": "gallery_art_brush_shadow", "roughness": 0.38, "specular": 0.42, "metallic": 0.0}
    if "gallery_artbrushwarm" in lowered or "gallery_art_brush_warm" in lowered:
        return {"color": [0.72, 0.66, 0.54], "material_label": "gallery_art_brush_warm", "roughness": 0.34, "specular": 0.46, "metallic": 0.0}
    if "gallery_artflowlight" in lowered or "gallery_art_flow_light" in lowered:
        return {"color": [0.98, 0.96, 0.88], "material_label": "gallery_art_flow_light", "roughness": 0.24, "specular": 0.55, "metallic": 0.0}
    if "gallery_artflowshadow" in lowered or "gallery_art_flow_shadow" in lowered:
        return {"color": [0.10, 0.09, 0.08], "material_label": "gallery_art_flow_shadow", "roughness": 0.36, "specular": 0.40, "metallic": 0.0}
    if "gallery_herobackdrop" in lowered or "gallery_hero_backdrop" in lowered:
        return {"color": [0.03, 0.028, 0.025], "material_label": "gallery_art_dark", "roughness": 0.36, "specular": 0.58, "metallic": 0.0}
    if "gallery_artstripe" in lowered or "gallery_art_stripe" in lowered:
        return {"color": [0.9, 0.86, 0.76], "material_label": "gallery_art_stripe", "roughness": 0.32, "specular": 0.52, "metallic": 0.0}
    if "gallery_lightpatch" in lowered or "gallery_light_patch" in lowered:
        return {"color": [1.0, 0.92, 0.72], "material_label": "gallery_sun_patch", "roughness": 0.7, "specular": 0.1, "metallic": 0.0, "emissive_strength": 1.8}
    if "gallery_artaccent" in lowered or "gallery_art_accent" in lowered:
        return {"color": [0.78, 0.74, 0.66], "material_label": "gallery_art_accent", "roughness": 0.34, "specular": 0.45, "metallic": 0.0}
    if "gallery_windowpane" in lowered or "gallery_entryglass" in lowered or "gallery_skylightpane" in lowered:
        return {"color": [0.82, 0.92, 0.98], "material_label": "gallery_glass_daylight", "roughness": 0.08, "specular": 0.82, "metallic": 0.0, "emissive_strength": 0.55, "opacity": 0.32}
    if "gallery_windowmullion" in lowered or "gallery_entryframe" in lowered:
        return {"color": [0.96, 0.96, 0.93], "material_label": "painted_white_frame", "roughness": 0.42, "specular": 0.32, "metallic": 0.0}
    if "gallery_ceilingbeam" in lowered:
        return {"color": [0.42, 0.24, 0.105], "material_label": "gallery_roof_timber", "roughness": 0.48, "specular": 0.26, "metallic": 0.0}
    if "gallery_exteriorwalkway" in lowered:
        return {"color": [0.68, 0.66, 0.60], "material_label": "gallery_exterior_walkway", "roughness": 0.68, "specular": 0.18, "metallic": 0.0}
    if "gallery_exteriorlawn" in lowered:
        return {"color": [0.36, 0.52, 0.28], "material_label": "gallery_exterior_lawn", "roughness": 0.82, "specular": 0.08, "metallic": 0.0}
    if "gallery_exteriorfacade" in lowered:
        return {"color": [0.86, 0.85, 0.80], "material_label": "gallery_exterior_facade", "roughness": 0.58, "specular": 0.22, "metallic": 0.0}
    if "gallery" in lowered and ("wall" in lowered or "ceiling" in lowered):
        return {"color": [0.92, 0.9, 0.86], "material_label": "warm_gallery_wall", "roughness": 0.62, "specular": 0.22, "metallic": 0.0}
    if "gallery_bench" in lowered:
        return {"color": [0.52, 0.32, 0.14], "material_label": "gallery_wood_bench", "roughness": 0.38, "specular": 0.35, "metallic": 0.0}
    if "desert_floor" in lowered:
        return {"color": [0.55, 0.42, 0.24], "material_label": "warm_desert_floor", "roughness": 0.72, "specular": 0.15, "metallic": 0.0}
    if "levelpark_pathdecal" in lowered:
        return {"color": [0.40, 0.33, 0.23], "material_label": "park_path_decal", "roughness": 0.82, "specular": 0.04, "metallic": 0.0}
    if "park_path" in lowered:
        return {
            "color": [0.74, 0.72, 0.64],
            "material_label": "park_path_warm_stone",
            "texture_path": "/Game/CityPark/Textures/Road/T_Sidewalk02_D",
            "texture_tiling": [8.0, 24.0],
            "roughness": 0.78,
            "specular": 0.07,
            "metallic": 0.0,
            "emissive_strength": 0.20,
        }
    if "park_skybackdrop" in lowered:
        return {"color": [0.52, 0.72, 0.92], "material_label": "park_clear_sky", "roughness": 0.9, "specular": 0.05, "metallic": 0.0, "emissive_strength": 0.35}
    if "park_grass" in lowered:
        return {
            "color": [0.36, 0.52, 0.20],
            "material_label": "park_grass",
            "texture_path": "/Game/CityPark/Textures/Flora/Grass/T_Grass07_D",
            "texture_tiling": [14.0, 28.0],
            "roughness": 0.92,
            "specular": 0.025,
            "metallic": 0.0,
            "emissive_strength": 0.42,
        }
    if "levelpark_water_" in lowered or "river_water" in lowered:
        return {"color": [0.68, 0.88, 0.96], "material_label": "river_water", "roughness": 0.08, "specular": 0.82, "metallic": 0.0, "opacity": 0.62, "emissive_strength": 0.34}
    if "levelpark_bridgesurface" in lowered or "levelpark_foregroundbridge" in lowered or "levelpark_bridgelattice" in lowered or "levelpark_pathedge" in lowered:
        return {"color": [0.62, 0.52, 0.39], "material_label": "citypark_warm_bridge", "roughness": 0.58, "specular": 0.22, "metallic": 0.0}
    if "levelpark_forestbackdrop" in lowered or "levelpark_canopyframe" in lowered or "levelpark_horizongrove" in lowered:
        return {"color": [0.42, 0.58, 0.28], "material_label": "park_tree_canopy", "roughness": 0.86, "specular": 0.04, "metallic": 0.0, "emissive_strength": 0.24}
    if "levelpark_skybackdrop" in lowered:
        return {"color": [0.50, 0.70, 0.90], "material_label": "park_clear_sky", "roughness": 0.92, "specular": 0.03, "metallic": 0.0, "emissive_strength": 0.25}
    if "levelpark_wirefence" in lowered:
        return {"color": [0.055, 0.060, 0.055], "material_label": "citypark_wire_fence", "roughness": 0.42, "specular": 0.48, "metallic": 0.55}
    if "park_railing" in lowered:
        return {"color": [0.20, 0.17, 0.12], "material_label": "citypark_dark_railing", "roughness": 0.52, "specular": 0.28, "metallic": 0.12}
    if "park_lamp" in lowered and "glow" in lowered:
        return {"color": [1.0, 0.84, 0.46], "material_label": "park_lamp_glow", "roughness": 0.24, "specular": 0.2, "metallic": 0.0, "emissive_strength": 2.4}
    if "park_lamp" in lowered:
        return {"color": [0.08, 0.075, 0.07], "material_label": "park_lamp_black_metal", "roughness": 0.35, "specular": 0.65, "metallic": 0.6}
    if "levelpark_waterlinescreen" in lowered:
        return {"color": [0.34, 0.50, 0.22], "material_label": "park_tree_canopy", "roughness": 0.86, "specular": 0.04, "metallic": 0.0, "emissive_strength": 0.18}
    if "park_tree" in lowered and "canopy" in lowered:
        return {"color": [0.42, 0.58, 0.28], "material_label": "park_tree_canopy", "roughness": 0.85, "specular": 0.04, "metallic": 0.0, "emissive_strength": 0.24}
    if "park_tree" in lowered:
        return {"color": [0.28, 0.16, 0.08], "material_label": "park_tree_bark", "roughness": 0.72, "specular": 0.12, "metallic": 0.0}
    if "river_water" in lowered:
        return {"color": [0.68, 0.88, 0.96], "material_label": "river_water", "roughness": 0.08, "specular": 0.82, "metallic": 0.0, "opacity": 0.62, "emissive_strength": 0.34}
    if "river_bank" in lowered:
        return {"color": [0.50, 0.40, 0.24], "material_label": "river_bank", "roughness": 0.78, "specular": 0.08, "metallic": 0.0}
    if "zebra_stripe" in lowered:
        return {"color": [0.015, 0.014, 0.012], "material_label": "zebra_stripe_black", "roughness": 0.5, "specular": 0.24, "metallic": 0.0}
    if "zebra_assetstripe" in lowered:
        return {"color": [0.012, 0.011, 0.010], "material_label": "zebra_asset_stripe_black", "roughness": 0.48, "specular": 0.22, "metallic": 0.0}
    return None


def _park_level_actor_profile(label: str) -> dict[str, Any] | None:
    lowered = label.lower()
    if any(token in lowered for token in ["parkpath", "asphalt", "road"]):
        return None
    if any(token in lowered for token in ["fence", "lamppost", "lamp"]):
        return {"color": [0.20, 0.19, 0.17], "material_label": "citypark_soft_metal", "roughness": 0.44, "specular": 0.42, "metallic": 0.35}
    if "bridge" in lowered:
        return {"color": [0.62, 0.52, 0.39], "material_label": "citypark_warm_bridge", "roughness": 0.58, "specular": 0.22, "metallic": 0.0}
    if any(token in lowered for token in ["bench", "gazebo", "pergola"]):
        return {"color": [0.38, 0.26, 0.16], "material_label": "citypark_warm_wood", "roughness": 0.52, "specular": 0.24, "metallic": 0.0}
    return None


def _style_loaded_park_level_actors() -> list[str]:
    if unreal is None:
        return []
    try:
        actors = unreal.EditorLevelLibrary.get_all_level_actors()
    except Exception:
        return []
    styled: list[str] = []
    for actor in actors:
        try:
            label = str(actor.get_actor_label())
        except Exception:
            continue
        if label.startswith("CineU_") or label.startswith("CAM_") or label.startswith("zebra_"):
            continue
        profile = _park_level_actor_profile(label)
        if profile is None:
            continue
        _apply_visual_profile(actor, profile)
        styled.append(label)
    return styled


def _use_semantic_proxy_for_actor(spec: dict[str, Any]) -> bool:
    return bool(spec.get("force_proxy"))


def _solid_material_for_profile(profile: dict[str, Any]):
    if unreal is None:
        return None
    label = re.sub(r"[^A-Za-z0-9_]+", "_", str(profile.get("material_label", "solid")).strip()).strip("_") or "solid"
    asset_name = f"M_CineU_{label}"
    package_path = "/Game/CineU/Generated/Materials"
    asset_path = f"{package_path}/{asset_name}"
    try:
        material = unreal.EditorAssetLibrary.load_asset(asset_path)
        if material is not None:
            if bool(profile.get("reuse_existing_if_present", True)):
                return material
            _configure_solid_material(material, profile)
            return material
    except Exception:
        pass
    try:
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(asset_name, package_path, unreal.Material, unreal.MaterialFactoryNew())
        _configure_solid_material(material, profile)
        return material
    except Exception:
        return None


def _configure_solid_material(material, profile: dict[str, Any]) -> None:
    delete_all_expressions = getattr(unreal.MaterialEditingLibrary, "delete_all_material_expressions", None)
    if delete_all_expressions is not None:
        try:
            delete_all_expressions(material)
        except Exception:
            pass
    r, g, b = [float(v) for v in profile.get("color", [0.5, 0.5, 0.5])]
    color = unreal.LinearColor(r, g, b, 1.0)
    texture_connected = _connect_texture_material_properties(material, profile)
    if not texture_connected:
        expression = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionVectorParameter, -320, 0)
        try:
            expression.set_editor_property("parameter_name", "Color")
            expression.set_editor_property("default_value", color)
        except Exception:
            pass
        try:
            unreal.MaterialEditingLibrary.connect_material_property(expression, "", unreal.MaterialProperty.MP_BASE_COLOR)
        except Exception:
            pass
    emissive_strength = float(profile.get("emissive_strength", 0.0) or 0.0)
    if emissive_strength > 0.0:
        emissive_color = unreal.LinearColor(r * emissive_strength, g * emissive_strength, b * emissive_strength, 1.0)
        emissive_expression = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionVectorParameter, -320, 160)
        try:
            emissive_expression.set_editor_property("parameter_name", "EmissiveColor")
            emissive_expression.set_editor_property("default_value", emissive_color)
        except Exception:
            pass
        emissive_property = getattr(unreal.MaterialProperty, "MP_EMISSIVE_COLOR", None)
        if emissive_property is not None:
            try:
                unreal.MaterialEditingLibrary.connect_material_property(emissive_expression, "", emissive_property)
            except Exception:
                pass
    _connect_scalar_material_property(material, profile, "roughness", "Roughness", "MP_ROUGHNESS", -40)
    _connect_scalar_material_property(material, profile, "specular", "Specular", "MP_SPECULAR", 120)
    _connect_scalar_material_property(material, profile, "metallic", "Metallic", "MP_METALLIC", 280)
    _configure_material_usage(material, profile)
    if "opacity" in profile:
        blend_mode = getattr(getattr(unreal, "BlendMode", None), "BLEND_TRANSLUCENT", None)
        if blend_mode is not None:
            try:
                material.set_editor_property("blend_mode", blend_mode)
            except Exception:
                pass
        _connect_scalar_material_property(material, profile, "opacity", "Opacity", "MP_OPACITY", 440)
    try:
        unreal.MaterialEditingLibrary.recompile_material(material)
    except Exception:
        pass
    try:
        unreal.EditorAssetLibrary.save_loaded_asset(material)
    except Exception:
        pass


def _configure_material_usage(material, profile: dict[str, Any]) -> None:
    if not bool(profile.get("used_with_skeletal_mesh")):
        return
    usage_enum = getattr(getattr(unreal, "MaterialUsage", None), "MATUSAGE_SKELETAL_MESH", None)
    set_usage = getattr(unreal.MaterialEditingLibrary, "set_material_usage", None)
    if usage_enum is not None and set_usage is not None:
        try:
            set_usage(material, usage_enum)
            return
        except Exception:
            pass
    for property_name in ["b_used_with_skeletal_mesh", "used_with_skeletal_mesh", "use_with_skeletal_mesh"]:
        try:
            material.set_editor_property(property_name, True)
            return
        except Exception:
            pass


def _connect_texture_material_properties(material, profile: dict[str, Any]) -> bool:
    texture_path = profile.get("texture_path")
    expression_class = getattr(unreal, "MaterialExpressionTextureSample", None) or getattr(unreal, "MaterialExpressionTextureSampleParameter2D", None)
    if not texture_path or expression_class is None:
        return False
    try:
        texture = unreal.EditorAssetLibrary.load_asset(str(texture_path))
    except Exception:
        return False
    if texture is None and str(texture_path) == GENERATED_ZEBRA_STRIPE_TEXTURE_PATH:
        texture = _ensure_generated_zebra_stripe_texture_asset()
    if texture is None:
        return False
    try:
        expression = unreal.MaterialEditingLibrary.create_material_expression(material, expression_class, -320, 0)
        try:
            expression.set_editor_property("parameter_name", "BaseTexture")
        except Exception:
            pass
        expression.set_editor_property("texture", texture)
        _connect_texture_coordinate_to_sample(material, expression, profile)
        if not _connect_material_property_from_outputs(expression, ["RGB", ""], unreal.MaterialProperty.MP_BASE_COLOR):
            return False
        if bool(profile.get("emissive_texture")):
            emissive_property = getattr(unreal.MaterialProperty, "MP_EMISSIVE_COLOR", None)
            if emissive_property is not None:
                _connect_material_property_from_outputs(expression, ["RGB", ""], emissive_property)
        return True
    except Exception:
        return False


def _connect_material_property_from_outputs(expression: Any, output_names: list[str], material_property: Any) -> bool:
    for output_name in output_names:
        try:
            unreal.MaterialEditingLibrary.connect_material_property(expression, output_name, material_property)
            return True
        except Exception:
            pass
    return False


def _write_generated_zebra_stripe_bmp(path: Path, *, width: int = 1024, height: int = 1024) -> None:
    width = max(8, int(width))
    height = max(8, int(height))
    path.parent.mkdir(parents=True, exist_ok=True)
    row_stride = width * 3
    padding = (4 - (row_stride % 4)) % 4
    image_size = (row_stride + padding) * height
    file_size = 54 + image_size
    header = bytearray()
    header.extend(b"BM")
    header.extend(struct.pack("<IHHI", file_size, 0, 0, 54))
    header.extend(struct.pack("<IiiHHIIiiII", 40, width, height, 1, 24, 0, image_size, 2835, 2835, 0, 0))
    stripe_centers = [0.06, 0.15, 0.24, 0.34, 0.45, 0.57, 0.68, 0.79, 0.90]
    stripe_widths = [0.028, 0.018, 0.035, 0.024, 0.030, 0.020, 0.034, 0.022, 0.030]
    with path.open("wb") as handle:
        handle.write(header)
        for y in range(height - 1, -1, -1):
            v = y / max(1, height - 1)
            wave = 0.035 * math.sin(v * math.pi * 5.5) + 0.018 * math.sin(v * math.pi * 13.0)
            row = bytearray()
            for x in range(width):
                u = (x / max(1, width - 1) + wave) % 1.0
                black = any(abs(u - center) <= width_value for center, width_value in zip(stripe_centers, stripe_widths))
                if black:
                    color = (10, 10, 10)
                else:
                    warm = int(226 + 22 * math.sin((u + v) * math.pi * 2.0))
                    color = (min(255, warm + 8), min(255, warm + 6), min(255, warm))
                row.extend((color[2], color[1], color[0]))
            if padding:
                row.extend(b"\x00" * padding)
            handle.write(row)


def _generated_zebra_stripe_source_file() -> Path:
    if unreal is not None:
        try:
            return Path(str(unreal.Paths.project_saved_dir())) / "CineU" / "Generated" / "T_CineU_Zebra_Stripes.bmp"
        except Exception:
            pass
    return Path("T_CineU_Zebra_Stripes.bmp")


def _unreal_texture_size(texture) -> list[int] | None:
    if texture is None:
        return None
    for width_name, height_name in [("blueprint_get_size_x", "blueprint_get_size_y"), ("get_size_x", "get_size_y")]:
        try:
            return [int(getattr(texture, width_name)()), int(getattr(texture, height_name)())]
        except Exception:
            pass
    return None


def _configure_generated_zebra_texture(texture) -> None:
    if texture is None:
        return
    for property_name, value in [
        ("srgb", True),
        ("max_texture_size", 1024),
    ]:
        try:
            texture.set_editor_property(property_name, value)
        except Exception:
            pass
    for enum_name, member_name, property_name in [
        ("TextureMipGenSettings", "TMGS_NO_MIPMAPS", "mip_gen_settings"),
        ("TextureGroup", "TEXTUREGROUP_Character", "lod_group"),
    ]:
        enum_type = getattr(unreal, enum_name, None)
        enum_value = getattr(enum_type, member_name, None) if enum_type is not None else None
        if enum_value is None:
            continue
        try:
            texture.set_editor_property(property_name, enum_value)
        except Exception:
            pass
    try:
        unreal.EditorAssetLibrary.save_loaded_asset(texture)
    except Exception:
        pass


def _ensure_generated_zebra_stripe_texture_asset():
    if unreal is None:
        return None
    try:
        existing = unreal.EditorAssetLibrary.load_asset(GENERATED_ZEBRA_STRIPE_TEXTURE_PATH)
        if existing is not None and (_unreal_texture_size(existing) or [0, 0])[0] >= 512:
            _configure_generated_zebra_texture(existing)
            return existing
    except Exception:
        pass
    source_file = _generated_zebra_stripe_source_file()
    try:
        _write_generated_zebra_stripe_bmp(source_file)
    except Exception:
        return None
    try:
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", str(source_file))
        task.set_editor_property("destination_path", "/Game/CineU/Generated/Textures")
        task.set_editor_property("destination_name", "T_CineU_Zebra_Stripes")
        task.set_editor_property("replace_existing", True)
        task.set_editor_property("automated", True)
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        texture = unreal.EditorAssetLibrary.load_asset(GENERATED_ZEBRA_STRIPE_TEXTURE_PATH)
        if texture is not None:
            _configure_generated_zebra_texture(texture)
        return texture
    except Exception:
        return None


def _texture_tiling_values(value: Any) -> tuple[float, float] | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        tiling = (float(value), float(value))
    else:
        try:
            values = list(value)
        except TypeError:
            return None
        if not values:
            return None
        tiling = (float(values[0]), float(values[1] if len(values) > 1 else values[0]))
    if tiling[0] <= 0.0 or tiling[1] <= 0.0:
        return None
    return tiling


def _set_expression_property(expression, names: list[str], value: float) -> None:
    for name in names:
        try:
            expression.set_editor_property(name, value)
            return
        except Exception:
            pass


def _connect_texture_coordinate_to_sample(material, texture_expression, profile: dict[str, Any]) -> None:
    tiling = _texture_tiling_values(profile.get("texture_tiling"))
    expression_class = getattr(unreal, "MaterialExpressionTextureCoordinate", None)
    connect_expressions = getattr(unreal.MaterialEditingLibrary, "connect_material_expressions", None)
    if tiling is None or expression_class is None or connect_expressions is None:
        return
    try:
        coordinate_expression = unreal.MaterialEditingLibrary.create_material_expression(material, expression_class, -520, 0)
    except Exception:
        return
    _set_expression_property(coordinate_expression, ["u_tiling", "UTiling"], tiling[0])
    _set_expression_property(coordinate_expression, ["v_tiling", "VTiling"], tiling[1])
    for input_name in ["UVs", "Coordinates"]:
        try:
            connect_expressions(coordinate_expression, "", texture_expression, input_name)
            return
        except Exception:
            pass


def _connect_scalar_material_property(material, profile: dict[str, Any], key: str, parameter_name: str, property_name: str, y: int) -> None:
    if key not in profile:
        return
    expression_class = getattr(unreal, "MaterialExpressionScalarParameter", None)
    material_property = getattr(unreal.MaterialProperty, property_name, None)
    if expression_class is None or material_property is None:
        return
    try:
        expression = unreal.MaterialEditingLibrary.create_material_expression(material, expression_class, 40, y)
        expression.set_editor_property("parameter_name", parameter_name)
        expression.set_editor_property("default_value", float(profile[key]))
        unreal.MaterialEditingLibrary.connect_material_property(expression, "", material_property)
    except Exception:
        pass


def _basic_shape_asset(shape: str):
    _require_unreal()
    mapping = {
        "plane": "/Engine/BasicShapes/Plane",
        "sphere": "/Engine/BasicShapes/Sphere",
        "capsule": "/Engine/BasicShapes/Cylinder",
        "cube": "/Engine/BasicShapes/Cube",
    }
    return unreal.EditorAssetLibrary.load_asset(mapping.get(shape, mapping["cube"]))


def _set_static_mesh(actor, mesh) -> None:
    component = None
    if hasattr(actor, "get_static_mesh_component"):
        component = actor.get_static_mesh_component()
    elif hasattr(actor, "static_mesh_component"):
        component = actor.static_mesh_component
    if component is not None and mesh is not None:
        component.set_static_mesh(mesh)


def _apply_visual_profile(actor, profile: dict[str, Any] | None) -> None:
    if unreal is None or not profile:
        return
    try:
        component = _visual_mesh_component(actor)
        if component is None:
            return
        solid_material = _solid_material_for_profile(profile)
        if solid_material is not None and hasattr(component, "set_material"):
            for slot in range(_component_material_slot_count(component)):
                component.set_material(slot, solid_material)
            return
        parent = None
        try:
            parent = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/BasicShapeMaterial")
        except Exception:
            parent = None
        try:
            material = component.create_dynamic_material_instance(0, parent) if parent is not None else component.create_dynamic_material_instance(0)
        except TypeError:
            material = component.create_dynamic_material_instance(0)
        if material is None:
            return
        r, g, b = [float(v) for v in profile.get("color", [0.5, 0.5, 0.5])]
        color = unreal.LinearColor(r, g, b, 1.0)
        for parameter in ["Color", "BaseColor", "Base Color"]:
            try:
                material.set_vector_parameter_value(parameter, color)
            except Exception:
                pass
    except Exception:
        return


def _visual_mesh_component(actor):
    for method_name in ["get_static_mesh_component"]:
        method = getattr(actor, method_name, None)
        if method is None:
            continue
        try:
            component = method()
            if component is not None:
                return component
        except Exception:
            pass
    for attr in ["static_mesh_component", "skeletal_mesh_component", "mesh"]:
        component = getattr(actor, attr, None)
        if component is not None:
            return component
    for component_class_name in ["SkeletalMeshComponent", "HierarchicalInstancedStaticMeshComponent", "InstancedStaticMeshComponent", "StaticMeshComponent"]:
        component_class = getattr(unreal, component_class_name, None)
        get_component = getattr(actor, "get_component_by_class", None)
        if component_class is None or get_component is None:
            continue
        try:
            component = get_component(component_class)
            if component is not None:
                return component
        except Exception:
            pass
    return None


def _component_material_slot_count(component) -> int:
    try:
        return max(1, int(component.get_num_materials()))
    except Exception:
        return 1


def _native_material_paths_for_spec(spec: dict[str, Any]) -> list[str]:
    explicit_paths = spec.get("native_material_paths")
    if isinstance(explicit_paths, list):
        return [str(path) for path in explicit_paths if path]
    material_paths = spec.get("materials")
    if isinstance(material_paths, list):
        game_paths = [str(path) for path in material_paths if str(path).startswith("/Game/")]
        if game_paths:
            return game_paths
    return []


def _apply_native_asset_materials(actor, spec: dict[str, Any]) -> bool:
    if unreal is None:
        return False
    material_paths = _native_material_paths_for_spec(spec)
    if not material_paths:
        return False
    component = _visual_mesh_component(actor)
    if component is None or not hasattr(component, "set_material"):
        return False
    materials = []
    for path in material_paths:
        try:
            material = unreal.EditorAssetLibrary.load_asset(path)
        except Exception:
            material = None
        if material is None:
            return False
        materials.append(material)
    try:
        for slot in range(_component_material_slot_count(component)):
            component.set_material(slot, materials[min(slot, len(materials) - 1)])
        return True
    except Exception:
        return False


def _is_public_imported_zebra(spec: dict[str, Any]) -> bool:
    if str(spec.get("semantic_type", "")).lower() != "zebra":
        return False
    if str(spec.get("source_type", "")).lower() != "public_free":
        return False
    return "/Game/CineU/Imported/public_free/" in str(spec.get("asset_path", ""))


def _public_zebra_texture_source_file(spec: dict[str, Any]) -> Path | None:
    candidates: list[Path] = []
    source_value = str(spec.get("source_path") or "")
    if source_value:
        source_path = Path(source_value)
        candidates.append(source_path.with_suffix(".png"))
        source_dir = source_path.parent
        for material_name in spec.get("materials", []) if isinstance(spec.get("materials"), list) else []:
            material_path = Path(str(material_name))
            candidates.append(material_path if material_path.is_absolute() else source_dir / material_path)
    for candidate in candidates:
        try:
            if candidate.exists():
                return candidate
        except OSError:
            pass
    return None


def _ensure_public_zebra_texture_asset(spec: dict[str, Any]) -> str | None:
    if unreal is None or not _is_public_imported_zebra(spec):
        return None
    try:
        if unreal.EditorAssetLibrary.does_asset_exist(PUBLIC_ZEBRA_TEXTURE_ASSET_PATH):
            return PUBLIC_ZEBRA_TEXTURE_ASSET_PATH
    except Exception:
        pass
    source_file = _public_zebra_texture_source_file(spec)
    if source_file is None:
        return None
    try:
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", str(source_file))
        task.set_editor_property("destination_path", "/Game/CineU/Imported/public_free")
        task.set_editor_property("destination_name", "T_CadNav_Zebra")
        task.set_editor_property("automated", True)
        task.set_editor_property("save", True)
        task.set_editor_property("replace_existing", False)
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        try:
            unreal.EditorAssetLibrary.save_directory("/Game/CineU/Imported/public_free", only_if_is_dirty=False, recursive=True)
        except Exception:
            pass
    except Exception:
        return None
    try:
        if unreal.EditorAssetLibrary.load_asset(PUBLIC_ZEBRA_TEXTURE_ASSET_PATH) is not None:
            return PUBLIC_ZEBRA_TEXTURE_ASSET_PATH
    except Exception:
        pass
    return None


def _texture_asset_is_usable(texture_path: str | None, min_size: int = 512) -> bool:
    if unreal is None or not texture_path:
        return False
    try:
        texture = unreal.EditorAssetLibrary.load_asset(texture_path)
    except Exception:
        return False
    size = _unreal_texture_size(texture)
    if size is None or len(size) < 2:
        return False
    return int(size[0]) >= min_size and int(size[1]) >= min_size


def _hide_component_material_section(component: Any, material_index: int) -> bool:
    show_section = getattr(component, "show_material_section", None)
    if show_section is None:
        return False
    for args in [(material_index, False, 0), (material_index, False)]:
        try:
            show_section(*args)
            return True
        except Exception:
            pass
    return False


def _apply_public_zebra_transparency_fix(actor, spec: dict[str, Any]) -> None:
    if unreal is None or not _is_public_imported_zebra(spec):
        return
    component = _visual_mesh_component(actor)
    if component is None or not hasattr(component, "set_material"):
        return
    try:
        if _component_material_slot_count(component) < 2:
            return
    except Exception:
        return
    texture_path = _ensure_public_zebra_texture_asset(spec)
    if _texture_asset_is_usable(texture_path):
        body_material = _solid_material_for_profile(
            {
                "color": [1.0, 1.0, 1.0],
                "material_label": "public_zebra_texture",
                "texture_path": texture_path,
                "texture_tiling": [1.0, 1.0],
                "roughness": 0.56,
                "specular": 0.24,
                "metallic": 0.0,
            }
        )
        if body_material is not None:
            try:
                component.set_material(0, body_material)
            except Exception:
                pass
    material = _solid_material_for_profile(
        {
            "color": [0.0, 0.0, 0.0],
            "material_label": "zebra_trs_transparent",
            "opacity": 0.0,
            "roughness": 1.0,
            "specular": 0.0,
            "metallic": 0.0,
        }
    )
    if material is None:
        return
    try:
        component.set_material(1, material)
    except Exception:
        pass
    _hide_component_material_section(component, 1)


def _actor_labels() -> set[str]:
    _require_unreal()
    return {a.get_actor_label() for a in unreal.EditorLevelLibrary.get_all_level_actors()}


def _find_actor_or_none(actor_name: str):
    _require_unreal()
    for actor in unreal.EditorLevelLibrary.get_all_level_actors():
        label = actor.get_actor_label()
        name = actor.get_name() if hasattr(actor, "get_name") else None
        if label == actor_name or name == actor_name:
            return actor
    return None


def _remove_actor_if_exists(actor_name: str) -> bool:
    if unreal is None:
        return False
    try:
        actor = _find_actor_or_none(actor_name)
    except Exception:
        return False
    if actor is None:
        return False
    try:
        unreal.EditorLevelLibrary.destroy_actor(actor)
        return True
    except Exception:
        try:
            actor.destroy_actor()
            return True
        except Exception:
            return False


def _remove_actors_with_label_prefixes(prefixes: list[str]) -> list[str]:
    if unreal is None:
        return []
    removed: list[str] = []
    try:
        actors = list(unreal.EditorLevelLibrary.get_all_level_actors())
    except Exception:
        return removed
    for actor in actors:
        try:
            label = str(actor.get_actor_label())
        except Exception:
            continue
        if not any(label.startswith(prefix) for prefix in prefixes):
            continue
        try:
            unreal.EditorLevelLibrary.destroy_actor(actor)
            removed.append(label)
        except Exception:
            try:
                actor.destroy_actor()
                removed.append(label)
            except Exception:
                pass
    return removed


def _rename_actor(actor, actor_name: str) -> None:
    try:
        actor.set_actor_label(actor_name)
    except Exception:
        try:
            actor.set_name(actor_name)
        except Exception:
            pass


def _reuse_existing_actor_for_spec(actor_name: str, spec: dict[str, Any]):
    reuse_actor_name = str(spec.get("reuse_actor_name") or "").strip()
    if not reuse_actor_name or reuse_actor_name == actor_name:
        return None, None
    actor = _find_actor_or_none(reuse_actor_name)
    if actor is None:
        return None, None
    current = _find_actor_or_none(actor_name)
    if current is not None and current is not actor:
        try:
            unreal.EditorLevelLibrary.destroy_actor(current)
        except Exception:
            try:
                current.destroy_actor()
            except Exception:
                pass
    _rename_actor(actor, actor_name)
    _apply_loaded_actor_materials(actor, {**spec, "actor_name": actor_name, "name": spec.get("name", actor_name)})
    return actor, reuse_actor_name


def _should_remove_default_scene_actor(actor) -> bool:
    try:
        label = actor.get_actor_label()
    except Exception:
        return False
    if label.startswith("CineU_") or label.startswith("CAM_") or re.match(r"^(painting|sculpture|zebra|wolf|horse|deer|human)_", label):
        return False
    default_labels = {
        "DirectionalLight",
        "ExponentialHeightFog",
        "PlayerStart",
        "SkyAtmosphere",
        "SkyLight",
        "SM_SkySphere",
        "VolumetricCloud",
    }
    if label in default_labels:
        return True
    return label == "Landscape" or label.startswith("LandscapeStreamingProxy")


def _remove_default_scene_actors() -> list[str]:
    _require_unreal()
    removed: list[str] = []
    for actor in list(unreal.EditorLevelLibrary.get_all_level_actors()):
        if not _should_remove_default_scene_actor(actor):
            continue
        label = actor.get_actor_label()
        try:
            unreal.EditorLevelLibrary.destroy_actor(actor)
            removed.append(label)
        except Exception:
            try:
                actor.destroy_actor()
                removed.append(label)
            except Exception:
                pass
    return removed


def _spawn_shape(
    label: str,
    shape: str,
    location: list[float],
    scale: list[float],
    rotation: list[float] | None = None,
    profile: dict[str, Any] | None = None,
):
    _require_unreal()
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(*location))
    actor.set_actor_label(label)
    _set_static_mesh(actor, _basic_shape_asset(shape))
    actor.set_actor_scale3d(unreal.Vector(*scale))
    if rotation:
        actor.set_actor_rotation(rotator_from_pitch_roll_yaw(unreal, rotation), False)
    _apply_visual_profile(actor, profile)
    return actor


def _spawn_if_missing(label: str, shape: str, location: list[float], scale: list[float], rotation: list[float] | None = None) -> None:
    _require_unreal()
    profile = _visual_profile_for_surface(label)
    existing = _find_actor_or_none(label)
    if existing is not None:
        _set_static_mesh(existing, _basic_shape_asset(shape))
        existing.set_actor_location(unreal.Vector(*location), False, False)
        if rotation:
            existing.set_actor_rotation(rotator_from_pitch_roll_yaw(unreal, rotation), False)
        existing.set_actor_scale3d(unreal.Vector(*scale))
        _apply_visual_profile(existing, profile)
        return
    _spawn_shape(label, shape, location, scale, rotation, profile=profile)


def _spawn_mesh_asset_if_available(label: str, asset_path: str, location: list[float], scale: list[float], rotation: list[float] | None = None) -> bool:
    if unreal is None:
        return False
    try:
        asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    except Exception:
        asset = None
    if asset is None:
        return False
    try:
        actor = _find_actor_or_none(label)
    except Exception:
        actor = None
    if actor is None:
        try:
            actor = unreal.EditorLevelLibrary.spawn_actor_from_object(asset, unreal.Vector(*location))
        except Exception:
            return False
        if actor is None:
            return False
        try:
            actor.set_actor_label(label)
        except Exception:
            pass
    else:
        _set_static_mesh(actor, asset)
    try:
        actor.set_actor_location(unreal.Vector(*location), False, False)
    except Exception:
        pass
    if rotation:
        try:
            actor.set_actor_rotation(rotator_from_pitch_roll_yaw(unreal, rotation), False)
        except Exception:
            pass
    try:
        actor.set_actor_scale3d(unreal.Vector(*scale))
    except Exception:
        pass
    _apply_visual_profile(actor, _visual_profile_for_surface(label) or _park_level_actor_profile(label))
    return True


def _spawn_asset_or_shape(
    label: str,
    asset_path: str,
    shape: str,
    location: list[float],
    scale: list[float],
    rotation: list[float] | None = None,
    fallback_scale: list[float] | None = None,
) -> None:
    if _spawn_mesh_asset_if_available(label, asset_path, location, scale, rotation):
        return
    _spawn_if_missing(label, shape, location, fallback_scale or scale, rotation)


def _set_actor_hidden(actor, hidden: bool) -> None:
    for method_name in ["set_actor_hidden_in_game", "set_is_temporarily_hidden_in_editor"]:
        method = getattr(actor, method_name, None)
        if method is None:
            continue
        try:
            method(bool(hidden))
        except Exception:
            pass


def _disable_actor_shadows(label: str) -> None:
    if unreal is None:
        return
    try:
        actor = _find_actor_or_none(label)
    except Exception:
        return
    if actor is None:
        return
    for class_name in ["StaticMeshComponent", "InstancedStaticMeshComponent", "HierarchicalInstancedStaticMeshComponent"]:
        component_class = getattr(unreal, class_name, None)
        if component_class is None:
            continue
        try:
            components = list(actor.get_components_by_class(component_class))
        except Exception:
            try:
                component = actor.get_component_by_class(component_class)
                components = [component] if component is not None else []
            except Exception:
                components = []
        for component in components:
            for property_name in ["cast_shadow", "visible_in_ray_tracing"]:
                try:
                    component.set_editor_property(property_name, False)
                except Exception:
                    pass


def _restore_park_level_native_visibility() -> list[str]:
    if unreal is None:
        return []
    restored: list[str] = []
    try:
        actors = unreal.EditorLevelLibrary.get_all_level_actors()
    except Exception:
        return restored
    for actor in actors:
        try:
            label = str(actor.get_actor_label())
        except Exception:
            continue
        lowered = label.lower()
        class_name = _actor_class_name(actor).lower()
        if label.startswith("CineU_") or label.startswith("CAM_") or label.startswith("zebra_"):
            continue
        if any(token in lowered or token in class_name for token in ["worlddatalayers", "worldpartition"]):
            continue
        _set_actor_hidden(actor, False)
        restored.append(label)
    return restored


def _actor_citypark_focus_overlap_state(actor, margin: float = 900.0) -> bool | None:
    try:
        origin, extent = actor.get_actor_bounds(False)
        min_x = float(origin.x) - float(extent.x)
        max_x = float(origin.x) + float(extent.x)
        min_y = float(origin.y) - float(extent.y)
        max_y = float(origin.y) + float(extent.y)
    except Exception:
        return None
    focus_min_x = CITYPARK_PATH_BOUNDS[0] - margin
    focus_max_x = CITYPARK_PATH_BOUNDS[1] + margin
    focus_min_y = CITYPARK_PATH_BOUNDS[2] - margin
    focus_max_y = CITYPARK_PATH_BOUNDS[3] + margin
    return not (max_x < focus_min_x or min_x > focus_max_x or max_y < focus_min_y or min_y > focus_max_y)


def _actor_overlaps_citypark_focus_bounds(actor, margin: float = 900.0) -> bool:
    overlap = _actor_citypark_focus_overlap_state(actor, margin)
    return True if overlap is None else overlap


def _hide_park_level_foliage_occluders() -> list[str]:
    if unreal is None:
        return []
    hidden: list[str] = []
    try:
        actors = unreal.EditorLevelLibrary.get_all_level_actors()
    except Exception:
        return hidden
    for actor in actors:
        try:
            label = str(actor.get_actor_label())
        except Exception:
            continue
        class_name = _actor_class_name(actor).lower()
        lowered = label.lower()
        if label.startswith("CineU_") or label.startswith("CAM_") or label.startswith("zebra_"):
            continue
        if any(token in lowered or token in class_name for token in ["worlddatalayers", "worldpartition"]):
            continue
        is_light = "light" in lowered or "light" in class_name
        if is_light or any(token in lowered or token in class_name for token in ["sky", "fog"]):
            continue
        focus_overlap = _actor_citypark_focus_overlap_state(actor)
        overlaps_focus_bounds = True if focus_overlap is None else focus_overlap
        is_reusable_environment_asset = any(token in lowered for token in ["road", "asphalt", "parkpath", "sidewalk", "parksquare"])
        is_farfield_merged_roadwork = any(
            token in lowered
            for token in ["mergedroad", "roaddecal", "roadblock", "mergedparksquare", "parksquare", "cafechair", "cafetable", "cafetablecloth"]
        )
        is_distant_reusable_environment_asset = is_farfield_merged_roadwork or (
            is_reusable_environment_asset and not overlaps_focus_bounds
        )
        if is_reusable_environment_asset and not is_distant_reusable_environment_asset:
            continue
        is_pathside_citypark_detail = any(token in lowered for token in ["bridge", "fence", "lamp", "bench", "gazebo", "pergola"])
        if is_pathside_citypark_detail and focus_overlap is not False:
            continue
        is_dark_level_clutter = any(
            token in lowered
            for token in ["bridge", "fence", "lamp", "bench", "gazebo", "pergola", "playground", "pavilion", "hut", "house", "cafebuilding"]
        )
        is_showcase_farfield_clutter = any(
            token in lowered
            for token in [
                "baseball",
                "basketball",
                "border",
                "bower",
                "drinkingfountain",
                "field",
                "foodstalls",
                "football",
                "fountain",
                "gate",
                "ground",
                "leak",
                "manhole",
                "newspaper",
                "pier",
                "pool",
                "rock",
                "sidewalk",
                "statue",
                "tennis",
                "trafficbarrel",
                "trashcan",
                "tribune",
                "tunnel",
                "umbrella",
            ]
        ) or (lowered.startswith("cube") and "hisma" in lowered)
        is_vegetation_asset = any(
            token in lowered
            for token in [
                "ivy",
                "amurcork",
                "bush",
                "elm",
                "grass",
                "maple",
                "willow",
                "tree",
                "plant",
                "shrub",
                "flower",
                "leaf",
                "leaves",
                "weed",
                "oak",
                "pine",
                "poplar",
                "spruce",
                "juniper",
                "birch",
            ]
        )
        should_hide = (
            (("foliage" in lowered or "foliage" in class_name or is_vegetation_asset) and focus_overlap is False)
            or is_distant_reusable_environment_asset
            or (is_dark_level_clutter and focus_overlap is not True)
            or is_showcase_farfield_clutter
            or lowered.startswith("plane")
        )
        if not should_hide:
            continue
        _set_actor_hidden(actor, True)
        hidden.append(label)
    return hidden


def _hide_park_level_camera_occluders() -> list[str]:
    if unreal is None:
        return []
    hidden: list[str] = []
    try:
        actors = unreal.EditorLevelLibrary.get_all_level_actors()
    except Exception:
        return hidden
    vegetation_tokens = [
        "foliage",
        "ivy",
        "amurcork",
        "bush",
        "elm",
        "grass",
        "maple",
        "willow",
        "tree",
        "plant",
        "shrub",
        "flower",
        "leaf",
        "leaves",
        "weed",
        "oak",
        "pine",
        "poplar",
        "spruce",
        "juniper",
        "birch",
    ]
    keep_tokens = ["bridge", "fence", "parkpath", "asphalt", "road", "lamp", "light", "sky", "fog", "landscape", "water"]
    dense_clutter_tokens = ["ivy", "amurcork", "bush", "shrub"]
    for actor in actors:
        try:
            label = str(actor.get_actor_label())
        except Exception:
            continue
        lowered = label.lower()
        class_name = _actor_class_name(actor).lower()
        if label.startswith("CineU_") or label.startswith("CAM_") or label.startswith("zebra_"):
            continue
        is_gate_or_fence = "gate" in lowered or "fence" in lowered
        is_low_context_fence = "parkfence" in lowered or "wirefence" in lowered
        if is_gate_or_fence and not is_low_context_fence and _actor_overlaps_citypark_focus_bounds(actor, margin=450.0):
            try:
                _, extent = actor.get_actor_bounds(False)
                extent_z = float(extent.z)
            except Exception:
                extent_z = 0.0
            if "gate" in lowered or "mergedfence" in lowered or extent_z >= 320.0:
                _set_actor_hidden(actor, True)
                hidden.append(label)
                continue
        if any(token in lowered or token in class_name for token in keep_tokens):
            continue
        is_dense_foreground_clutter = any(token in lowered or token in class_name for token in dense_clutter_tokens)
        if is_dense_foreground_clutter and _actor_overlaps_citypark_focus_bounds(actor, margin=450.0):
            _set_actor_hidden(actor, True)
            hidden.append(label)
            continue
        if "(hisma)" in lowered or "instancedfoliageactor" in class_name or "hierarchicalinstanced" in class_name:
            continue
        if not any(token in lowered or token in class_name for token in vegetation_tokens):
            continue
        if not _actor_overlaps_citypark_focus_bounds(actor, margin=250.0):
            continue
        _set_actor_hidden(actor, True)
        hidden.append(label)
    return hidden


def _static_mesh_path_from_component(component: Any) -> str | None:
    for property_name in ["static_mesh", "StaticMesh"]:
        try:
            mesh = component.get_editor_property(property_name)
        except Exception:
            mesh = getattr(component, property_name, None)
        if mesh is None:
            continue
        get_path_name = getattr(mesh, "get_path_name", None)
        if get_path_name is None:
            continue
        try:
            return str(get_path_name()).split(".", 1)[0]
        except Exception:
            return None
    return None


def _component_instance_count(component: Any) -> int:
    for method_name in ["get_instance_count", "get_num_instances"]:
        method = getattr(component, method_name, None)
        if method is None:
            continue
        try:
            return int(method())
        except Exception:
            pass
    return 0


def _instance_transform(component: Any, index: int) -> Any | None:
    for args in [(index, True), (index,)]:
        try:
            return component.get_instance_transform(*args)
        except Exception:
            pass
    return None


def _transform_translation(transform: Any) -> Any | None:
    translation = getattr(transform, "translation", None)
    if translation is not None:
        return translation
    get_location = getattr(transform, "get_location", None)
    if get_location is not None:
        try:
            return get_location()
        except Exception:
            return None
    return None


def _set_transform_translation(transform: Any, location: list[float]) -> bool:
    if unreal is None:
        return False
    vector = unreal.Vector(float(location[0]), float(location[1]), float(location[2]))
    try:
        transform.translation = vector
        return True
    except Exception:
        pass
    try:
        transform.set_editor_property("translation", vector)
        return True
    except Exception:
        return False


def _instance_distance_to_citypark_focus(location: Any) -> float:
    return math.hypot(float(location.x) - CITYPARK_PATH_X, float(location.y) - CITYPARK_PATH_CENTER_Y)


def _is_sparse_focus_tree_asset(mesh_path: str) -> bool:
    lowered = mesh_path.lower()
    return any(
        lowered.endswith(asset)
        for asset in [
            "/sm_elm13",
            "/sm_elm07",
            "/sm_elm11",
            "/sm_amurcork10",
            "/sm_amurcork04",
        ]
    )


def _suppress_sparse_focus_tree_instances() -> list[dict[str, Any]]:
    if unreal is None:
        return []
    suppressed: list[dict[str, Any]] = []
    component_classes = [
        getattr(unreal, "HierarchicalInstancedStaticMeshComponent", None),
        getattr(unreal, "InstancedStaticMeshComponent", None),
    ]
    component_classes = [component_class for component_class in component_classes if component_class is not None]
    if not component_classes:
        return suppressed
    try:
        actors = list(unreal.EditorLevelLibrary.get_all_level_actors())
    except Exception:
        return suppressed
    for actor in actors:
        try:
            label = str(actor.get_actor_label())
        except Exception:
            label = ""
        seen_components: set[int] = set()
        for component_class in component_classes:
            try:
                components = list(actor.get_components_by_class(component_class))
            except Exception:
                components = []
            for component in components:
                component_key = id(component)
                if component_key in seen_components:
                    continue
                seen_components.add(component_key)
                mesh_path = _static_mesh_path_from_component(component)
                if not mesh_path or not _is_sparse_focus_tree_asset(mesh_path):
                    continue
                for index in range(_component_instance_count(component)):
                    transform = _instance_transform(component, index)
                    if transform is None:
                        continue
                    translation = _transform_translation(transform)
                    if translation is None or _instance_distance_to_citypark_focus(translation) > 900.0:
                        continue
                    lowered_location = [float(translation.x), float(translation.y), float(translation.z) - 50000.0]
                    if not _set_transform_translation(transform, lowered_location):
                        continue
                    try:
                        component.update_instance_transform(index, transform, True, True, True)
                    except Exception:
                        continue
                    suppressed.append({"actor": label, "mesh": mesh_path, "instance_index": index})
    return suppressed


def _configure_light_actor(actor, properties: dict[str, Any]) -> None:
    candidates = [actor]
    for attr in ["light_component", "point_light_component", "rect_light_component", "directional_light_component", "sky_light_component"]:
        component = getattr(actor, attr, None)
        if component is not None:
            candidates.append(component)
    for target in candidates:
        for name, value in properties.items():
            try:
                target.set_editor_property(name, _coerce_light_property_value(name, value))
            except Exception:
                pass


def _coerce_light_property_value(name: str, value: Any) -> Any:
    return _coerce_linear_color_property(name, value, {"light_color"})


def _coerce_linear_color_property(name: str, value: Any, names: set[str]) -> Any:
    if name not in names or not isinstance(value, (list, tuple)):
        return value
    linear_color = getattr(unreal, "LinearColor", None)
    if linear_color is None:
        return value
    channels = [float(channel) for channel in value[:4]]
    if len(channels) == 3:
        channels.append(1.0)
    if len(channels) != 4:
        return value
    return linear_color(*channels)


def _coerce_vector4_property(name: str, value: Any, names: set[str]) -> Any:
    if name not in names or not isinstance(value, (list, tuple)):
        return value
    vector4 = getattr(unreal, "Vector4", None)
    if vector4 is None:
        return value
    channels = [float(channel) for channel in value[:4]]
    if len(channels) == 3:
        channels.append(1.0)
    if len(channels) != 4:
        return value
    return vector4(*channels)


def _coerce_world_effect_property_value(name: str, value: Any) -> Any:
    value = _coerce_linear_color_property(name, value, {"scene_color_tint", "fog_inscattering_color"})
    return _coerce_vector4_property(
        name,
        value,
        {"color_saturation", "color_contrast", "color_gamma", "color_gain", "color_offset"},
    )


def _set_editor_property_if_possible(target: Any, name: str, value: Any) -> None:
    try:
        target.set_editor_property(name, value)
    except Exception:
        pass


def _enable_post_process_override(settings: Any, name: str) -> None:
    _set_editor_property_if_possible(settings, f"override_{name}", True)
    _set_editor_property_if_possible(settings, f"b_override_{name}", True)


def _configure_post_process_actor(actor, properties: dict[str, Any]) -> None:
    settings = None
    try:
        settings = actor.get_editor_property("settings")
    except Exception:
        settings = getattr(actor, "settings", None)
    for name, value in properties.items():
        if name == "unbound":
            _set_editor_property_if_possible(actor, "unbound", bool(value))
            _set_editor_property_if_possible(actor, "b_unbound", bool(value))
            continue
        if name in {"priority", "blend_weight"}:
            _set_editor_property_if_possible(actor, name, float(value))
            continue
        coerced = _coerce_world_effect_property_value(name, value)
        if settings is not None:
            _set_editor_property_if_possible(settings, name, coerced)
            _enable_post_process_override(settings, name)
        else:
            _set_editor_property_if_possible(actor, name, coerced)
    if settings is not None:
        _set_editor_property_if_possible(actor, "settings", settings)


def _spawn_post_process_if_missing(label: str, location: list[float], scale: list[float], properties: dict[str, Any] | None = None):
    _require_unreal()
    actor_class = getattr(unreal, "PostProcessVolume", None)
    if actor_class is None:
        return None
    actor = _find_actor_or_none(label)
    if actor is None:
        actor = unreal.EditorLevelLibrary.spawn_actor_from_class(actor_class, unreal.Vector(*location))
        actor.set_actor_label(label)
    else:
        try:
            actor.set_actor_location(unreal.Vector(*location), False, False)
        except Exception:
            pass
    try:
        actor.set_actor_scale3d(unreal.Vector(*scale))
    except Exception:
        pass
    _configure_post_process_actor(actor, properties or {})
    return actor


def _configure_fog_actor(actor, properties: dict[str, Any]) -> None:
    candidates = [actor]
    for attr in ["component", "fog_component", "exponential_height_fog_component"]:
        component = getattr(actor, attr, None)
        if component is not None:
            candidates.append(component)
    component_class = getattr(unreal, "ExponentialHeightFogComponent", None)
    get_component_by_class = getattr(actor, "get_component_by_class", None)
    if component_class is not None and get_component_by_class is not None:
        try:
            component = get_component_by_class(component_class)
            if component is not None:
                candidates.append(component)
        except Exception:
            pass
    seen: set[int] = set()
    for target in candidates:
        identity = id(target)
        if identity in seen:
            continue
        seen.add(identity)
        for name, value in properties.items():
            _set_editor_property_if_possible(target, name, _coerce_world_effect_property_value(name, value))


def _spawn_fog_if_missing(label: str, location: list[float], properties: dict[str, Any] | None = None):
    _require_unreal()
    actor_class = getattr(unreal, "ExponentialHeightFog", None)
    if actor_class is None:
        return None
    actor = _find_actor_or_none(label)
    if actor is None:
        actor = unreal.EditorLevelLibrary.spawn_actor_from_class(actor_class, unreal.Vector(*location))
        actor.set_actor_label(label)
    else:
        try:
            actor.set_actor_location(unreal.Vector(*location), False, False)
        except Exception:
            pass
    _configure_fog_actor(actor, properties or {})
    return actor


def _spawn_light_if_missing(
    label: str,
    actor_class_name: str,
    location: list[float],
    rotation: list[float] | None = None,
    properties: dict[str, Any] | None = None,
):
    _require_unreal()
    actor_class = getattr(unreal, actor_class_name, None)
    if actor_class is None:
        return None
    actor = _find_actor_or_none(label)
    if actor is None:
        actor = unreal.EditorLevelLibrary.spawn_actor_from_class(actor_class, unreal.Vector(*location))
        actor.set_actor_label(label)
    else:
        try:
            actor.set_actor_location(unreal.Vector(*location), False, False)
        except Exception:
            pass
    if rotation:
        try:
            actor.set_actor_rotation(rotator_from_pitch_roll_yaw(unreal, rotation), False)
        except Exception:
            pass
    _configure_light_actor(actor, properties or {})
    return actor


def _ensure_base_lighting() -> None:
    _spawn_light_if_missing("CineU_DirectionalLight", "DirectionalLight", [0, -300, 600], [-55, 0, 35], {"intensity": 4.0})
    _spawn_light_if_missing("CineU_SkyLight", "SkyLight", [0, 0, 350], None, {"intensity": 1.5})


def _soften_park_level_native_lights() -> list[str]:
    if unreal is None:
        return []
    try:
        actors = list(unreal.EditorLevelLibrary.get_all_level_actors())
    except Exception:
        return []
    softened: list[str] = []
    for actor in actors:
        try:
            label = str(actor.get_actor_label())
        except Exception:
            continue
        if label.startswith("CineU_"):
            continue
        class_name = _actor_class_name(actor).lower()
        lowered = label.lower()
        if "directionallight" in class_name or "light source" in lowered:
            _configure_light_actor(
                actor,
                {
                    "intensity": 1.65,
                    "source_angle": 6.0,
                    "indirect_lighting_intensity": 1.2,
                    "light_color": [1.0, 0.96, 0.84],
                },
            )
            softened.append(label)
        elif "skylight" in class_name or lowered == "skylight":
            _configure_light_actor(
                actor,
                {
                    "intensity": 2.35,
                    "indirect_lighting_intensity": 1.45,
                    "light_color": [0.86, 0.96, 1.0],
                },
            )
            softened.append(label)
    return softened


def _spawn_level_backed_park_scenic_assets() -> None:
    waterline_bush_assets = [
        "/Game/CityPark/Meshes/Flora/Bushs/SM_Bush3_03",
        "/Game/CityPark/Meshes/Flora/Bushs/SM_Bush5_01",
        "/Game/CityPark/Meshes/Flora/Bushs/SM_Bush2_05",
    ]
    waterline_specs = [
        ("Left", -760.0, 16480.0, 0.28, -18.0),
        ("Right", 780.0, 16840.0, 0.30, 22.0),
        ("Left", -820.0, 17860.0, 0.34, 14.0),
        ("Right", 840.0, 18880.0, 0.32, -26.0),
        ("Left", -790.0, 19980.0, 0.30, 36.0),
        ("Right", 810.0, 20720.0, 0.34, -12.0),
    ]
    for index, (side, x_offset, y, scale, yaw) in enumerate(waterline_specs):
        _spawn_asset_or_shape(
            f"CineU_LevelPark_WaterlineScreen_{side}_{index:02d}",
            waterline_bush_assets[index % len(waterline_bush_assets)],
            "sphere",
            [CITYPARK_PATH_X + x_offset, y, CITYPARK_PATH_Z + 4.0],
            [scale, scale, scale],
            [0.0, 0.0, yaw],
            fallback_scale=[1.35 * scale, 1.35 * scale, 0.88 * scale],
        )

    tree_assets = [
        "/Game/CityPark/Meshes/Flora/Trees/SM_Elm08",
        "/Game/CityPark/Meshes/Flora/Trees/SM_Maple08",
        "/Game/CityPark/Meshes/Flora/Trees/SM_WeepingWillow01",
    ]
    horizon_specs = [
        ("Left", -1180.0, 16680.0, 0.28, -12.0),
        ("Right", 1240.0, 17180.0, 0.26, 18.0),
        ("Left", -1420.0, 18420.0, 0.34, 26.0),
        ("Right", 1460.0, 19320.0, 0.32, -24.0),
        ("Left", -1260.0, 20380.0, 0.30, 8.0),
        ("Right", 1340.0, 20920.0, 0.28, -18.0),
    ]
    for index, (side, x_offset, y, scale, yaw) in enumerate(horizon_specs):
        _spawn_asset_or_shape(
            f"CineU_LevelPark_HorizonGrove_{side}_{index:02d}",
            tree_assets[index % len(tree_assets)],
            "sphere",
            [CITYPARK_PATH_X + x_offset, y, CITYPARK_PATH_Z + 5.0],
            [scale, scale, scale],
            [0.0, 0.0, yaw],
            fallback_scale=[1.45 * scale, 1.45 * scale, 0.95 * scale],
        )

    grass_assets = [
        "/Game/CityPark/Meshes/Flora/Grass/SM_WaterPlant02",
        "/Game/CityPark/Meshes/Flora/Grass/SM_WaterPlant04",
        "/Game/CityPark/Meshes/Flora/Grass/SM_grass07_2",
    ]
    grass_specs = [
        ("Left", -600.0, 16580.0, 0.18, 11.0),
        ("Right", 620.0, 17480.0, 0.20, -17.0),
        ("Left", -650.0, 19080.0, 0.18, 29.0),
        ("Right", 640.0, 20420.0, 0.19, -31.0),
    ]
    for index, (side, x_offset, y, scale, yaw) in enumerate(grass_specs):
        _spawn_asset_or_shape(
            f"CineU_LevelPark_WaterPlant_{side}_{index:02d}",
            grass_assets[index % len(grass_assets)],
            "sphere",
            [CITYPARK_PATH_X + x_offset, y, CITYPARK_PATH_Z + 3.0],
            [scale, scale, scale],
            [0.0, 0.0, yaw],
            fallback_scale=[0.32, 0.32, 0.16],
        )


def _apply_level_backed_park_cinematic_pass() -> dict[str, Any]:
    restored = _restore_park_level_native_visibility()
    hidden = _hide_park_level_camera_occluders()
    softened = _soften_park_level_native_lights()
    _spawn_light_if_missing(
        "CineU_LevelPark_SubjectKeyLight",
        "PointLight",
        [CITYPARK_PATH_X - 280.0, CITYPARK_PATH_CENTER_Y - 980.0, CITYPARK_PATH_Z + 430.0],
        None,
        {"intensity": 1120.0, "attenuation_radius": 4200.0, "light_color": [1.0, 0.90, 0.72]},
    )
    _spawn_light_if_missing(
        "CineU_LevelPark_SoftFillLight",
        "PointLight",
        [CITYPARK_PATH_X + 520.0, CITYPARK_PATH_CENTER_Y + 240.0, CITYPARK_PATH_Z + 520.0],
        None,
        {"intensity": 1120.0, "attenuation_radius": 5200.0, "light_color": [0.86, 0.92, 1.0]},
    )
    _spawn_post_process_if_missing(
        "CineU_LevelPark_CinematicPostProcess",
        [CITYPARK_PATH_X, CITYPARK_PATH_CENTER_Y, CITYPARK_PATH_Z + 260.0],
        [12.0, 12.0, 6.0],
        {
            "unbound": True,
            "auto_exposure_min_brightness": 1.0,
            "auto_exposure_max_brightness": 1.0,
            "auto_exposure_bias": 0.88,
            "exposure_compensation": 0.88,
            "bloom_intensity": 0.14,
            "vignette_intensity": 0.03,
            "scene_color_tint": [1.0, 0.98, 0.90, 1.0],
        },
    )
    return {"restored_native_actors": restored, "hidden_occluders": hidden, "softened_lights": softened}


def _apply_level_backed_park_world_template_grade() -> dict[str, Any]:
    if unreal is None:
        return {"graded_post_process": []}
    try:
        actors = list(unreal.EditorLevelLibrary.get_all_level_actors())
    except Exception:
        return {"graded_post_process": []}
    graded: list[str] = []
    for actor in actors:
        try:
            label = str(actor.get_actor_label())
        except Exception:
            continue
        class_name = _actor_class_name(actor).lower()
        if label != "PostProcessVolumeMAIN" or "postprocess" not in class_name:
            continue
        _configure_post_process_actor(
            actor,
            {
                "unbound": True,
                "priority": 20.0,
                "blend_weight": 1.0,
                "auto_exposure_min_brightness": 1.0,
                "auto_exposure_max_brightness": 1.0,
                "auto_exposure_bias": 0.44,
                "exposure_compensation": 0.44,
                "bloom_intensity": 0.10,
                "vignette_intensity": 0.01,
                "scene_color_tint": [0.99, 1.035, 1.01, 1.0],
                "color_saturation": [1.03, 1.05, 1.03, 1.0],
                "color_gain": [0.98, 1.06, 1.04, 1.0],
                "color_contrast": [1.06, 1.05, 1.04, 1.0],
            },
        )
        graded.append(label)
    return {"graded_post_process": graded}


def _load_environment_level(asset_path: str) -> bool:
    try:
        load_level = getattr(unreal.EditorLevelLibrary, "load_level", None)
        if load_level is not None:
            return bool(load_level(asset_path))
    except Exception:
        pass
    try:
        subsystem_type = getattr(unreal, "LevelEditorSubsystem", None)
        get_subsystem = getattr(unreal, "get_editor_subsystem", None)
        if subsystem_type is None or get_subsystem is None:
            return False
        subsystem = get_subsystem(subsystem_type)
        load_level = getattr(subsystem, "load_level", None)
        if load_level is None:
            return False
        return bool(load_level(asset_path))
    except Exception:
        return False


def _spawn_environment_asset_if_available(environment_asset: dict[str, Any] | None) -> dict[str, Any] | None:
    if not environment_asset:
        return None
    asset_path = environment_asset.get("ue_path")
    asset_id = str(environment_asset.get("asset_id", "environment_asset"))
    if not asset_path:
        return {"asset_id": asset_id, "status": "missing_path"}
    if str(environment_asset.get("type", "")).lower() == "level":
        loaded = _load_environment_level(str(asset_path))
        return {"asset_id": asset_id, "status": "level_loaded" if loaded else "level_load_failed", "asset_path": asset_path}
    try:
        asset = unreal.EditorAssetLibrary.load_asset(str(asset_path))
    except Exception as exc:
        return {"asset_id": asset_id, "status": "load_failed", "asset_path": asset_path, "error": str(exc)}
    if asset is None:
        return {"asset_id": asset_id, "status": "missing_asset", "asset_path": asset_path}
    label = f"CineU_EnvironmentAsset_{asset_id}"
    existing = _find_actor_or_none(label)
    if existing is not None:
        return {"asset_id": asset_id, "status": "already_spawned", "actor_name": label, "asset_path": asset_path}
    try:
        actor = unreal.EditorLevelLibrary.spawn_actor_from_object(asset, unreal.Vector(0.0, 0.0, 0.0))
        actor.set_actor_label(label)
        fit = _fit_large_environment_actor(actor, environment_asset)
        return {"asset_id": asset_id, "status": "spawned", "actor_name": label, "asset_path": asset_path, "fit": fit}
    except Exception as exc:
        return {"asset_id": asset_id, "status": "spawn_failed", "asset_path": asset_path, "error": str(exc)}


def _is_level_environment_asset(environment_asset: dict[str, Any] | None) -> bool:
    return bool(environment_asset) and str(environment_asset.get("type", "")).lower() == "level"


def _is_loaded_level_environment(environment_asset: dict[str, Any] | None, environment_asset_result: dict[str, Any] | None) -> bool:
    return _is_level_environment_asset(environment_asset) and bool(environment_asset_result) and str(environment_asset_result.get("status")) == "level_loaded"


def _is_spawned_environment_asset(environment_asset: dict[str, Any] | None, environment_asset_result: dict[str, Any] | None) -> bool:
    if not environment_asset or not environment_asset_result:
        return False
    return str(environment_asset_result.get("status")) in {"spawned", "already_spawned"}


def _asset_backed_park_support_surface(environment_asset: dict[str, Any] | None) -> dict[str, Any]:
    extent = ((environment_asset or {}).get("bounds_cm") or {}).get("extent") or [900.0, 900.0, 120.0]
    x_extent = max(float(extent[0]), 220.0)
    y_extent = max(float(extent[1]), 900.0)
    return {
        "type": "ground",
        "z": 0.0,
        "bounds": [-x_extent, x_extent, -y_extent, y_extent],
        "environment_asset_type": str((environment_asset or {}).get("type") or "asset"),
    }


def _fit_large_environment_actor(actor, environment_asset: dict[str, Any] | None = None) -> dict[str, Any] | None:
    tags = {str(tag).lower() for tag in (environment_asset or {}).get("semantic_tags", [])}
    if (environment_asset or {}).get("type") == "static_mesh" and "environment" in tags:
        scale = 0.3
        z_offset = -220.0
        try:
            actor.set_actor_scale3d(unreal.Vector(scale, scale, scale))
        except Exception:
            pass
        try:
            actor.set_actor_location(unreal.Vector(0.0, 0.0, z_offset), False, False)
        except Exception:
            pass
        return {"method": "semantic_environment_background", "scale": scale, "z_offset": z_offset}
    try:
        _origin, extent = actor.get_actor_bounds(False)
        extent = [float(value) for value in extent]
    except Exception:
        return None
    max_xy = max(abs(extent[0]), abs(extent[1]), 1.0)
    scale = min(1.0, 1200.0 / max_xy)
    if scale >= 0.99 and abs(extent[2]) <= 300.0:
        return {"scale": 1.0, "z_offset": 0.0}
    z_offset = -abs(extent[2]) * scale + 4.0
    try:
        actor.set_actor_scale3d(unreal.Vector(scale, scale, scale))
    except Exception:
        pass
    try:
        actor.set_actor_location(unreal.Vector(0.0, 0.0, z_offset), False, False)
    except Exception:
        pass
    return {"scale": scale, "z_offset": z_offset, "original_extent": extent}


def _scale_from_extent(extent: list[float]) -> list[float]:
    return [
        max(float(extent[0]) / 50.0, 0.1),
        max(float(extent[1]) / 50.0, 0.1),
        max(float(extent[2]) / 50.0, 0.1),
    ]


def _placement_scale(placement: dict[str, Any]) -> list[float]:
    transform = placement.get("transform", {})
    scale = transform.get("scale") or [1, 1, 1]
    if "bounds_extent" in placement and all(abs(float(value) - 1.0) < 1e-6 for value in scale):
        return _scale_from_extent(placement.get("bounds_extent", [50, 50, 50]))
    return [float(value) for value in scale]


def _actor_class_name(actor) -> str:
    try:
        actor_class = actor.get_class()
        return str(actor_class.get_name())
    except Exception:
        return ""


def _is_real_skeletal_actor(actor, spec: dict[str, Any]) -> bool:
    if spec.get("force_proxy"):
        return False
    asset_type = str(spec.get("asset_type", "")).lower()
    if asset_type and asset_type != "skeletal_mesh":
        return False
    return "skeletal" in _actor_class_name(actor).lower()


def _scale_for_actor_placement(actor, placement: dict[str, Any]) -> list[float]:
    transform = placement.get("transform", {})
    scale = transform.get("scale") or [1, 1, 1]
    if _is_real_skeletal_actor(actor, placement):
        return [float(value) for value in scale]
    return _placement_scale(placement)


def _rotation_for_actor_placement(actor, placement: dict[str, Any]) -> list[float]:
    transform = placement.get("transform", {})
    rotation = [float(value) for value in transform.get("rotation", [0, 0, 0])[:3]]
    while len(rotation) < 3:
        rotation.append(0.0)
    if str(placement.get("actor_name", "")).startswith("zebra_") and _is_real_skeletal_actor(actor, placement):
        rotation[2] -= 90.0
    return rotation


def _apply_actor_transform(actor, placement: dict[str, Any]) -> None:
    transform = placement.get("transform", {})
    actor.set_actor_location(unreal.Vector(*transform.get("location", [0, 0, 0])), False, False)
    actor.set_actor_rotation(rotator_from_pitch_roll_yaw(unreal, _rotation_for_actor_placement(actor, placement)), False)
    actor.set_actor_scale3d(unreal.Vector(*_scale_for_actor_placement(actor, placement)))


def _should_add_zebra_proxy_details(actor, placement: dict[str, Any]) -> bool:
    actor_name = str(placement.get("actor_name", ""))
    if not actor_name.startswith("zebra_"):
        return False
    return not _is_real_skeletal_actor(actor, placement)


def _should_add_zebra_asset_enhancement_details(actor, placement: dict[str, Any]) -> bool:
    return False


def _remove_zebra_proxy_details(actor_name: str) -> list[str]:
    if unreal is None:
        return []
    prefixes = [
        f"CineU_Zebra_Stripe_{actor_name}_",
        f"CineU_Zebra_AssetStripe_{actor_name}_",
    ]
    removed: list[str] = []
    try:
        actors = list(unreal.EditorLevelLibrary.get_all_level_actors())
    except Exception:
        return removed
    for actor in actors:
        try:
            label = str(actor.get_actor_label())
        except Exception:
            continue
        if not any(label.startswith(prefix) for prefix in prefixes):
            continue
        try:
            unreal.EditorLevelLibrary.destroy_actor(actor)
            removed.append(label)
        except Exception:
            try:
                actor.destroy_actor()
                removed.append(label)
            except Exception:
                pass
    return removed


def _painting_detail_rotation(rotation: list[float], roll_offset: float) -> list[float]:
    result = [float(value) for value in rotation[:3]]
    while len(result) < 3:
        result.append(0.0)
    result[2] += float(roll_offset)
    return result


def _spawn_hero_flow_strokes(actor_name: str, location: list[float], rotation: list[float], art_extent_y: float, art_extent_z: float, wall_front_y: float) -> None:
    curves = [
        ("Light", 0, 0.02, 0.24, 0.0),
        ("Light", 1, -0.16, 0.18, 1.35),
        ("Shadow", 2, 0.10, 0.14, 2.05),
    ]
    segment_count = 16
    for tone, curve_index, z_center, amplitude, phase in curves:
        for segment in range(segment_count):
            progress = segment / float(segment_count - 1)
            x_factor = -0.48 + 0.96 * progress
            wave = math.sin(progress * math.pi * 2.0 + phase)
            z_factor = z_center + amplitude * wave
            slope = math.cos(progress * math.pi * 2.0 + phase) * amplitude
            roll_offset = max(-32.0, min(32.0, slope * 115.0))
            width = 0.22 + 0.04 * math.sin(progress * math.pi)
            height = 0.055 if tone == "Light" else 0.040
            _spawn_if_missing(
                f"CineU_Gallery_ArtFlow{tone}_{actor_name}_{curve_index:02d}_{segment:02d}",
                "cube",
                [location[0] + art_extent_y * x_factor, wall_front_y - 7.0 - curve_index * 0.55 - segment * 0.025, location[2] + art_extent_z * z_factor],
                [0.014, width, height],
                rotation=_painting_detail_rotation(rotation, roll_offset),
            )


def _spawn_painting_wall_details(placement: dict[str, Any]) -> None:
    actor_name = str(placement.get("actor_name", ""))
    if not actor_name.startswith("painting_"):
        return
    transform = placement.get("transform", {})
    location = [float(v) for v in transform.get("location", [0, 0, 0])]
    rotation = [float(v) for v in transform.get("rotation", [0, 0, 0])]
    extent = [float(v) for v in placement.get("bounds_extent", [6, 120, 80])]
    art_extent_y = extent[1] * (1.35 if actor_name == "painting_02" else 1.0)
    art_extent_z = extent[2] * (1.18 if actor_name == "painting_02" else 1.0)
    wall_front_y = location[1] - 8.0
    if actor_name == "painting_02":
        _spawn_if_missing(
            f"CineU_Gallery_HeroBackdrop_{actor_name}",
            "cube",
            [location[0], wall_front_y - 2.6, location[2] + 8.0],
            [0.018, 3.7, 2.05],
            rotation=rotation,
        )
    label_x = location[0] - extent[1] * 0.35
    label_z = max(60.0, location[2] - extent[2] - 18.0)
    _spawn_if_missing(
        f"CineU_Gallery_Label_{actor_name}",
        "cube",
        [label_x, wall_front_y - 1.0, label_z],
        [0.03, 0.55, 0.26],
        rotation=rotation,
    )
    accent_x = location[0] - extent[1] * 0.18
    accent_z = location[2] + extent[2] * 0.02
    _spawn_if_missing(
        f"CineU_Gallery_ArtAccent_{actor_name}",
        "cube",
        [accent_x, wall_front_y - 2.0, accent_z],
        [0.025, 0.95, 0.45],
        rotation=rotation,
    )
    stripe_specs = [
        (-0.42, 0.30, 0.36, 0.11),
        (-0.20, -0.18, 0.30, 0.09),
        (0.06, 0.22, 0.42, 0.08),
        (0.32, -0.10, 0.34, 0.10),
    ]
    for index, (x_factor, z_factor, width_scale, height_scale) in enumerate(stripe_specs):
        _spawn_if_missing(
            f"CineU_Gallery_ArtStripe_{actor_name}_{index:02d}",
            "cube",
            [location[0] + art_extent_y * x_factor, wall_front_y - 3.0 - index * 0.2, location[2] + art_extent_z * z_factor],
            [0.02, width_scale, height_scale],
            rotation=rotation,
        )
    brush_specs = [
        ("Light", -0.36, 0.30, 0.58, 0.105, -18.0),
        ("Warm", -0.28, 0.08, 0.42, 0.075, 8.0),
        ("Light", -0.18, -0.18, 0.54, 0.095, 20.0),
        ("Shadow", -0.08, 0.24, 0.46, 0.06, -8.0),
        ("Light", 0.03, 0.02, 0.62, 0.12, 0.0),
        ("Warm", 0.12, -0.25, 0.40, 0.08, -20.0),
        ("Light", 0.22, 0.30, 0.52, 0.09, 16.0),
        ("Shadow", 0.30, 0.03, 0.44, 0.055, 6.0),
        ("Light", 0.39, -0.16, 0.50, 0.085, -14.0),
        ("Warm", 0.46, 0.18, 0.36, 0.07, 22.0),
        ("Light", -0.33, -0.03, 0.12, 0.32, -6.0),
        ("Shadow", -0.23, 0.17, 0.10, 0.28, 4.0),
        ("Light", -0.12, 0.02, 0.14, 0.36, 10.0),
        ("Warm", -0.01, -0.12, 0.12, 0.30, -12.0),
        ("Light", 0.10, 0.15, 0.16, 0.34, 14.0),
        ("Shadow", 0.19, -0.06, 0.10, 0.27, -4.0),
        ("Light", 0.28, 0.08, 0.14, 0.35, 8.0),
        ("Warm", 0.36, -0.18, 0.12, 0.29, -16.0),
        ("Light", -0.03, 0.33, 0.18, 0.26, 18.0),
        ("Shadow", 0.17, -0.31, 0.11, 0.25, -20.0),
    ]
    for index, (tone, x_factor, z_factor, width_scale, height_scale, roll_offset) in enumerate(brush_specs):
        _spawn_if_missing(
            f"CineU_Gallery_ArtBrush{tone}_{actor_name}_{index:02d}",
            "cube",
            [location[0] + art_extent_y * x_factor, wall_front_y - 4.2 - index * 0.12, location[2] + art_extent_z * z_factor],
            [0.018, width_scale, height_scale],
            rotation=_painting_detail_rotation(rotation, roll_offset),
        )
    if actor_name == "painting_02":
        _spawn_hero_flow_strokes(actor_name, location, rotation, art_extent_y, art_extent_z, wall_front_y)


def _spawn_zebra_proxy_details(placement: dict[str, Any]) -> None:
    actor_name = str(placement.get("actor_name", ""))
    if not actor_name.startswith("zebra_"):
        return
    transform = placement.get("transform", {})
    location = [float(v) for v in transform.get("location", [0, 0, 0])]
    rotation = [float(v) for v in transform.get("rotation", [0, 0, 0])]
    extent = [float(v) for v in placement.get("bounds_extent", [115, 35, 85])]
    yaw = rotation[2] if len(rotation) >= 3 else 0.0
    root_at_ground = location[2] <= extent[2] * 0.25
    body_z = location[2] + extent[2] * (0.98 if root_at_ground else 0.08)
    leg_z = max(location[2] + 18.0, location[2] - extent[2] * 0.55)
    side_offset = extent[1] * 0.52
    stripe_offsets = [-0.42, -0.28, -0.13, 0.03, 0.19, 0.35, 0.50]
    for index, x_factor in enumerate(stripe_offsets):
        roll = -18.0 if index % 2 == 0 else 16.0
        stripe_location = _local_zebra_detail_location(location, yaw, extent[0] * x_factor, side_offset, body_z)
        _spawn_if_missing(
            f"CineU_Zebra_Stripe_{actor_name}_{index:02d}",
            "cube",
            stripe_location,
            [0.018, 0.08, 0.38],
            rotation=[rotation[0], rotation[1], rotation[2] + roll],
        )
    for index, x_factor in enumerate([-0.30, 0.08, 0.42]):
        stripe_location = _local_zebra_detail_location(location, yaw, extent[0] * x_factor, side_offset * 0.85, leg_z)
        _spawn_if_missing(
            f"CineU_Zebra_Stripe_{actor_name}_leg_{index:02d}",
            "cube",
            stripe_location,
            [0.016, 0.06, 0.28],
            rotation=[rotation[0], rotation[1], rotation[2] - 8.0],
        )


def _spawn_zebra_asset_enhancement_details(placement: dict[str, Any]) -> None:
    actor_name = str(placement.get("actor_name", ""))
    if not actor_name.startswith("zebra_"):
        return
    transform = placement.get("transform", {})
    location = [float(v) for v in transform.get("location", [0, 0, 0])]
    rotation = [float(v) for v in transform.get("rotation", [0, 0, 0])]
    extent = [float(v) for v in placement.get("bounds_extent", [115, 35, 85])]
    while len(rotation) < 3:
        rotation.append(0.0)
    yaw = rotation[2]
    body_z = location[2] + extent[2] * 0.74
    neck_z = location[2] + extent[2] * 1.12
    leg_z = location[2] + extent[2] * 0.34
    side_offset = extent[1] * 0.72
    body_stripes = [
        (-0.46, 0.34, -24.0),
        (-0.32, 0.43, 18.0),
        (-0.18, 0.38, -16.0),
        (-0.03, 0.46, 22.0),
        (0.14, 0.40, -14.0),
        (0.30, 0.34, 16.0),
    ]
    for index, (x_factor, height, roll) in enumerate(body_stripes):
        _spawn_if_missing(
            f"CineU_Zebra_AssetStripe_{actor_name}_{index:02d}",
            "cube",
            _local_zebra_detail_location(location, yaw, extent[0] * x_factor, side_offset, body_z),
            [0.012, 0.070, height],
            rotation=[rotation[0], rotation[1], rotation[2] + roll],
        )
    for index, (x_factor, z, roll) in enumerate([(0.44, neck_z, -22.0), (0.55, neck_z + 20.0, 16.0)]):
        _spawn_if_missing(
            f"CineU_Zebra_AssetStripe_{actor_name}_neck_{index:02d}",
            "cube",
            _local_zebra_detail_location(location, yaw, extent[0] * x_factor, side_offset * 0.82, z),
            [0.010, 0.060, 0.30],
            rotation=[rotation[0], rotation[1], rotation[2] + roll],
        )
    for index, x_factor in enumerate([-0.34, 0.08, 0.39]):
        _spawn_if_missing(
            f"CineU_Zebra_AssetStripe_{actor_name}_leg_{index:02d}",
            "cube",
            _local_zebra_detail_location(location, yaw, extent[0] * x_factor, side_offset * 0.78, leg_z),
            [0.010, 0.050, 0.26],
            rotation=[rotation[0], rotation[1], rotation[2] - 6.0],
        )


def _local_zebra_detail_location(location: list[float], yaw_degrees: float, forward: float, right: float, z: float) -> list[float]:
    yaw = math.radians(float(yaw_degrees))
    return [
        location[0] + forward * math.cos(yaw) - right * math.sin(yaw),
        location[1] + forward * math.sin(yaw) + right * math.cos(yaw),
        z,
    ]


def _spawn_gallery_entry_structure() -> None:
    for index, x in enumerate([-180.0, 0.0, 180.0]):
        _spawn_if_missing(f"CineU_Gallery_EntryGlass_{index:02d}", "cube", [x, -498.0, 260.0], [1.6, 0.02, 2.85])
    for label, x in [
        ("CineU_Gallery_EntryFrame_Left", -280.0),
        ("CineU_Gallery_EntryFrame_MidLeft", -92.0),
        ("CineU_Gallery_EntryFrame_MidRight", 92.0),
        ("CineU_Gallery_EntryFrame_Right", 280.0),
    ]:
        _spawn_if_missing(label, "cube", [x, -506.0, 285.0], [0.08, 0.10, 3.35])
    _spawn_if_missing("CineU_Gallery_EntryFrame_Top", "cube", [0.0, -506.0, 565.0], [5.75, 0.10, 0.08])
    _spawn_if_missing("CineU_Gallery_EntryFrame_Sill", "cube", [0.0, -506.0, 24.0], [5.75, 0.12, 0.10])


def _spawn_gallery_window_structure() -> None:
    right_window_ys = [-270.0, -90.0, 90.0, 270.0]
    for index, y in enumerate(right_window_ys):
        _spawn_if_missing(f"CineU_Gallery_WindowPane_Right_{index:02d}", "cube", [492.0, y, 320.0], [0.025, 0.72, 1.25])
    for index, y in enumerate([-360.0, -180.0, 0.0, 180.0, 360.0]):
        _spawn_if_missing(f"CineU_Gallery_WindowMullion_Right_{index:02d}", "cube", [490.0, y, 320.0], [0.035, 0.035, 1.35])
    for index, z in enumerate([195.0, 445.0]):
        _spawn_if_missing(f"CineU_Gallery_WindowMullion_Right_H{index:02d}", "cube", [490.0, 0.0, z], [0.035, 3.7, 0.035])
    for index, x in enumerate([-300.0, 0.0, 300.0]):
        _spawn_if_missing(f"CineU_Gallery_WindowPane_BackUpper_{index:02d}", "cube", [x, 492.0, 560.0], [1.2, 0.025, 0.72])
        _spawn_if_missing(f"CineU_Gallery_WindowMullion_BackUpper_{index:02d}", "cube", [x + 74.0, 490.0, 560.0], [0.035, 0.035, 0.84])


def _spawn_gallery_ceiling_structure() -> None:
    for index, x in enumerate([-390.0, -195.0, 0.0, 195.0, 390.0]):
        _spawn_if_missing(f"CineU_Gallery_CeilingBeam_Long_{index:02d}", "cube", [x, 0.0, 760.0], [0.08, 10.2, 0.09])
    for index, y in enumerate([-390.0, -130.0, 130.0, 390.0]):
        _spawn_if_missing(f"CineU_Gallery_CeilingBeam_Cross_{index:02d}", "cube", [0.0, y, 742.0], [10.2, 0.08, 0.08])
    for index, x in enumerate([-230.0, 0.0, 230.0]):
        _spawn_if_missing(f"CineU_Gallery_SkylightPane_{index:02d}", "cube", [x, -40.0, 752.0], [1.35, 2.85, 0.025])


def _spawn_gallery_exterior_courtyard() -> None:
    _spawn_if_missing("CineU_Gallery_ExteriorWalkway", "plane", [0.0, -900.0, 0.8], [3.1, 5.2, 1.0])
    _spawn_if_missing("CineU_Gallery_ExteriorLawn_Left", "plane", [-360.0, -900.0, 0.6], [3.1, 5.4, 1.0])
    _spawn_if_missing("CineU_Gallery_ExteriorLawn_Right", "plane", [360.0, -900.0, 0.6], [3.1, 5.4, 1.0])
    _spawn_if_missing("CineU_Gallery_ExteriorFacade_Left", "cube", [-455.0, -1040.0, 210.0], [0.16, 2.7, 4.2])
    _spawn_if_missing("CineU_Gallery_ExteriorFacade_Right", "cube", [455.0, -1040.0, 210.0], [0.16, 2.7, 4.2])
    _spawn_if_missing("CineU_Gallery_ExteriorFacade_Back", "cube", [0.0, -1180.0, 210.0], [9.0, 0.12, 4.2])
    for index, y in enumerate([-1040.0, -930.0, -820.0, -710.0]):
        _spawn_if_missing(f"CineU_Gallery_ExteriorWalkwayJoint_{index:02d}", "cube", [0.0, y, 1.8], [3.0, 0.025, 0.012])


def _ensure_gallery_dressing() -> None:
    _remove_actor_if_exists("CineU_Gallery_Ceiling")
    _spawn_light_if_missing(
        "CineU_Gallery_KeyLight",
        "PointLight",
        [0, -120, 420],
        None,
        {"intensity": 350.0, "attenuation_radius": 900.0, "source_radius": 180.0},
    )
    _spawn_light_if_missing(
        "CineU_Gallery_WallWashLight",
        "PointLight",
        [0, 300, 360],
        None,
        {"intensity": 180.0, "attenuation_radius": 700.0, "source_radius": 160.0},
    )
    _spawn_if_missing("CineU_Gallery_Bench", "cube", [-40, -130, 48], [2.2, 0.42, 0.22])
    _spawn_if_missing("CineU_Gallery_Bench_LegLeft", "cube", [-110, -130, 22], [0.16, 0.32, 0.38])
    _spawn_if_missing("CineU_Gallery_Bench_LegRight", "cube", [30, -130, 22], [0.16, 0.32, 0.38])
    _spawn_if_missing("CineU_Gallery_CeilingPanel", "cube", [0, 0, 805], [10, 10, 0.04])
    _spawn_gallery_entry_structure()
    _spawn_gallery_window_structure()
    _spawn_gallery_ceiling_structure()
    _spawn_gallery_exterior_courtyard()
    light_patches = [
        ("CineU_Gallery_LightPatch_00", [492, 170, 325], [0.025, 1.0, 0.34]),
        ("CineU_Gallery_LightPatch_01", [492, 270, 265], [0.025, 0.86, 0.30]),
        ("CineU_Gallery_LightPatch_02", [492, 350, 380], [0.025, 0.72, 0.26]),
    ]
    for label, location, scale in light_patches:
        _spawn_if_missing(label, "cube", location, scale)


def _park_surface_primitives(level_backed: bool = False) -> list[tuple[str, str, list[float], list[float]]]:
    if level_backed:
        return []
    return [
        ("CineU_Park_Path", "plane", [0, 0, 1.0], [3.4, 13.0, 1.0]),
        ("CineU_Park_Grass_Left", "plane", [-430, 0, 0.6], [5.2, 13.0, 1.0]),
        ("CineU_Park_Grass_Right", "plane", [430, 0, 0.6], [5.2, 13.0, 1.0]),
    ]


def _spawn_park_surface_primitives(level_backed: bool = False) -> None:
    if level_backed:
        return
    for label, shape, location, scale in _park_surface_primitives(level_backed=level_backed):
        _spawn_if_missing(label, shape, location, scale)


def _park_dressing_scale_for_asset(asset_path: str, index: int, fallback: list[float]) -> list[float]:
    lower = asset_path.lower()
    if "/game/citypark/" not in lower:
        return fallback
    value = 0.105 if index == 0 else 0.085
    return [value, value, value]


def _spawn_level_backed_park_asset_accents(dressing_assets: list[dict[str, Any]] | None = None) -> dict[str, list[str]]:
    willow_asset = "/Game/CityPark/Meshes/Flora/Trees/SM_WeepingWillow01"
    willow_specs = [
        (
            "CineU_LevelPark_ForegroundWillow_Right_00",
            [CITYPARK_PATH_X + 880.0, CITYPARK_PATH_CENTER_Y - 80.0, CITYPARK_PATH_Z + 2.0],
            [0.14, 0.14, 0.14],
            [0.0, 0.0, -40.0],
        ),
        (
            "CineU_LevelPark_ForegroundWillow_Right_01",
            [CITYPARK_PATH_X + 1220.0, CITYPARK_PATH_CENTER_Y + 260.0, CITYPARK_PATH_Z + 2.0],
            [0.12, 0.12, 0.12],
            [0.0, 0.0, 12.0],
        ),
        (
            "CineU_LevelPark_CanopyWillow_Right_00",
            [CITYPARK_PATH_X + 500.0, CITYPARK_PATH_CENTER_Y - 260.0, CITYPARK_PATH_Z + 2.0],
            [0.12, 0.12, 0.12],
            [0.0, 0.0, -28.0],
        ),
    ]
    spawned: list[str] = []
    for label, location, scale, rotation in willow_specs:
        if _spawn_mesh_asset_if_available(label, willow_asset, location, scale, rotation):
            _disable_actor_shadows(label)
            spawned.append(label)
    hanging_ivy_specs = [
        (
            "CineU_LevelPark_HangingIvy_Right_00",
            "/Game/CityPark/Meshes/Flora/Ivy/SM_Ivy2_06",
            [CITYPARK_PATH_X + 920.0, CITYPARK_PATH_CENTER_Y - 330.0, CITYPARK_PATH_Z - 180.0],
            [0.42, 0.42, 0.42],
            [0.0, 0.0, -18.0],
        ),
        (
            "CineU_LevelPark_HangingIvy_Right_01",
            "/Game/CityPark/Meshes/Flora/Ivy/SM_Ivy2_03",
            [CITYPARK_PATH_X + 1130.0, CITYPARK_PATH_CENTER_Y - 40.0, CITYPARK_PATH_Z - 190.0],
            [0.34, 0.34, 0.34],
            [0.0, 0.0, 8.0],
        ),
    ]
    for label, asset_path, location, scale, rotation in hanging_ivy_specs:
        if _spawn_mesh_asset_if_available(label, asset_path, location, scale, rotation):
            _disable_actor_shadows(label)
            spawned.append(label)
    reserved_canopy_assets = {willow_asset.lower()}
    canopy_assets: list[str] = []
    seen_canopy_assets: set[str] = set(reserved_canopy_assets)
    for asset in dressing_assets or []:
        asset_path = str(asset.get("ue_path") or "")
        if not asset_path:
            continue
        key = asset_path.lower()
        if key in seen_canopy_assets:
            continue
        seen_canopy_assets.add(key)
        canopy_assets.append(asset_path)
    canopy_specs = [
        (
            "CineU_LevelPark_ImportedCanopy_Left_00",
            [CITYPARK_PATH_X - 440.0, CITYPARK_PATH_CENTER_Y - 320.0, CITYPARK_PATH_Z + 2.0],
            [0.95, 0.95, 0.95],
            [0.0, 0.0, 34.0],
        ),
        (
            "CineU_LevelPark_ImportedCanopy_Left_01",
            [CITYPARK_PATH_X + 30.0, CITYPARK_PATH_CENTER_Y - 55.0, CITYPARK_PATH_Z + 2.0],
            [0.62, 0.62, 0.62],
            [0.0, 0.0, -22.0],
        ),
    ]
    for index, (label, location, scale, rotation) in enumerate(canopy_specs):
        if index >= len(canopy_assets):
            break
        asset_path = canopy_assets[index]
        asset_scale = _park_dressing_scale_for_asset(asset_path, index, scale)
        if _spawn_mesh_asset_if_available(label, asset_path, location, asset_scale, rotation):
            _disable_actor_shadows(label)
            spawned.append(label)
    return {"spawned_asset_accents": spawned}


def _spawn_level_backed_park_supplement() -> None:
    y_values = [25080.0, 26080.0, 27080.0, 28080.0, 29080.0, 30080.0]
    for side, x in [("Left", CITYPARK_PATH_X - 300.0), ("Right", CITYPARK_PATH_X + 300.0)]:
        for index, y in enumerate(y_values):
            _spawn_if_missing(f"CineU_LevelPark_Railing_{side}_{index:02d}", "cube", [x, y, CITYPARK_PATH_Z + 74.0], [0.055, 4.5, 0.07])
            _spawn_if_missing(f"CineU_LevelPark_RailingPost_{side}_{index:02d}", "cube", [x, y - 225.0, CITYPARK_PATH_Z + 54.0], [0.075, 0.075, 1.08])
    for index, (x_offset, y) in enumerate([(-470.0, 25560.0), (470.0, 27080.0), (-470.0, 28780.0), (470.0, 30320.0)]):
        x = CITYPARK_PATH_X + x_offset
        _spawn_if_missing(f"CineU_LevelPark_Lamp_{index:02d}_Post", "cube", [x, y, CITYPARK_PATH_Z + 145.0], [0.065, 0.065, 2.9])
        _spawn_if_missing(f"CineU_LevelPark_Lamp_{index:02d}_Head", "cube", [x, y, CITYPARK_PATH_Z + 300.0], [0.22, 0.22, 0.24])
        _spawn_if_missing(f"CineU_LevelPark_Lamp_{index:02d}_Glow", "sphere", [x, y, CITYPARK_PATH_Z + 286.0], [0.24, 0.24, 0.24])
        _spawn_asset_or_shape(
            f"CineU_LevelPark_AssetLamp_{'Left' if x_offset < 0 else 'Right'}_{index:02d}",
            "/Game/CityPark/Meshes/Props/SM_LampPost02_1",
            "cube",
            [x, y, CITYPARK_PATH_Z + 4.0],
            [0.34, 0.34, 0.34],
            [0.0, 0.0, 0.0],
            fallback_scale=[0.08, 0.08, 3.0],
        )
    fence_specs = [
        ("Left", CITYPARK_PATH_X - 435.0, 25120.0, 92.0, "/Game/CityPark/Meshes/Props/SM_ParkFence02_1"),
        ("Left", CITYPARK_PATH_X - 435.0, 25920.0, 92.0, "/Game/CityPark/Meshes/Props/SM_ParkFence02_2"),
        ("Right", CITYPARK_PATH_X + 435.0, 25120.0, -88.0, "/Game/CityPark/Meshes/Props/SM_ParkFence03_1"),
        ("Right", CITYPARK_PATH_X + 435.0, 25920.0, -88.0, "/Game/CityPark/Meshes/Props/SM_ParkFence03_2"),
        ("Right", CITYPARK_PATH_X + 435.0, 27320.0, -88.0, "/Game/CityPark/Meshes/Props/SM_ParkFence03_1"),
        ("Right", CITYPARK_PATH_X + 435.0, 28720.0, -88.0, "/Game/CityPark/Meshes/Props/SM_ParkFence03_2"),
        ("Right", CITYPARK_PATH_X + 435.0, 30120.0, -88.0, "/Game/CityPark/Meshes/Props/SM_ParkFence03_1"),
        ("Right", CITYPARK_PATH_X + 435.0, 31520.0, -88.0, "/Game/CityPark/Meshes/Props/SM_ParkFence03_2"),
    ]
    for index, (side, x, y, yaw, asset_path) in enumerate(fence_specs):
        _spawn_asset_or_shape(
            f"CineU_LevelPark_AssetFence_{side}_{index:02d}",
            asset_path,
            "cube",
            [x, y, CITYPARK_PATH_Z + 2.0],
            [0.42, 0.42, 0.42],
            [0.0, 0.0, yaw],
            fallback_scale=[0.05, 2.8, 0.42],
        )
    wire_x = CITYPARK_PATH_X + 560.0
    for index, y in enumerate([25000.0, 25800.0, 26600.0, 27400.0, 28200.0, 29000.0, 29800.0, 30600.0, 31400.0]):
        _spawn_if_missing(
            f"CineU_LevelPark_WireFence_Right_Post_{index:02d}",
            "cube",
            [wire_x, y, CITYPARK_PATH_Z + 70.0],
            [0.030, 0.030, 0.86],
        )
    for index, (y, z_offset) in enumerate([(28200.0, 66.0), (28200.0, 96.0), (28200.0, 126.0), (28200.0, 156.0)]):
        _spawn_if_missing(
            f"CineU_LevelPark_WireFence_Right_Rail_{index:02d}",
            "cube",
            [wire_x, y, CITYPARK_PATH_Z + z_offset],
            [0.018, 31.0, 0.012],
        )
    for index, y in enumerate([25350.0, 25750.0, 26150.0, 26550.0, 26950.0, 27350.0, 27750.0, 28150.0, 28550.0, 28950.0, 29350.0, 29750.0, 30150.0, 30550.0, 30950.0, 31350.0]):
        _spawn_if_missing(
            f"CineU_LevelPark_WireFence_Right_Vertical_{index:02d}",
            "cube",
            [wire_x, y, CITYPARK_PATH_Z + 111.0],
            [0.014, 0.014, 0.52],
        )
    foreground_bridge_specs = [
        ("Near_00", "/Game/CityPark/Meshes/Road/SM_Bridge03_1", -640.0, 28680.0, 0.18, 89.0),
        ("Near_01", "/Game/CityPark/Meshes/Road/SM_Bridge03_2", -670.0, 29480.0, 0.16, 89.0),
        ("Left_00", "/Game/CityPark/Meshes/Road/SM_Bridge03_1", -620.0, 30980.0, 0.18, 89.0),
        ("Left_01", "/Game/CityPark/Meshes/Road/SM_Bridge03_2", -650.0, 31840.0, 0.16, 89.0),
    ]
    for suffix, asset_path, x_offset, y, scale, yaw in foreground_bridge_specs:
        _spawn_asset_or_shape(
            f"CineU_LevelPark_ForegroundBridge_{suffix}",
            asset_path,
            "cube",
            [CITYPARK_PATH_X + x_offset, y, CITYPARK_PATH_Z + 18.0],
            [scale, scale, scale],
            [0.0, 0.0, yaw],
            fallback_scale=[0.72, 5.4, 0.32],
        )
    lattice_x = CITYPARK_PATH_X - 390.0
    for index, y in enumerate([28680.0, 29240.0, 29800.0, 30360.0]):
        _spawn_if_missing(
            f"CineU_LevelPark_BridgeLattice_Left_Post_{index:02d}",
            "cube",
            [lattice_x, y, CITYPARK_PATH_Z + 80.0],
            [0.070, 0.070, 0.92],
        )
        _spawn_if_missing(
            f"CineU_LevelPark_BridgeLattice_Left_TopRail_{index:02d}",
            "cube",
            [lattice_x, y + 180.0, CITYPARK_PATH_Z + 154.0],
            [0.045, 1.34, 0.060],
        )
        _spawn_if_missing(
            f"CineU_LevelPark_BridgeLattice_Left_CrossA_{index:02d}",
            "cube",
            [lattice_x, y + 180.0, CITYPARK_PATH_Z + 102.0],
            [0.035, 0.96, 0.035],
            [34.0, 0.0, 0.0],
        )
        _spawn_if_missing(
            f"CineU_LevelPark_BridgeLattice_Left_CrossB_{index:02d}",
            "cube",
            [lattice_x, y + 180.0, CITYPARK_PATH_Z + 102.0],
            [0.035, 0.96, 0.035],
            [-34.0, 0.0, 0.0],
        )
    _spawn_asset_or_shape(
        "CineU_LevelPark_Water_Right",
        "/Game/CityPark/Meshes/Ground/SM_WaterPlane",
        "plane",
        [CITYPARK_PATH_X + 1760.0, CITYPARK_PATH_CENTER_Y + 80.0, CITYPARK_PATH_Z - 4.5],
        [4.4, 24.0, 0.035],
        [0.0, 0.0, 0.0],
        fallback_scale=[4.4, 24.0, 0.035],
    )
    _spawn_asset_or_shape(
        "CineU_LevelPark_Water_ChannelNear",
        "/Game/CityPark/Meshes/Ground/SM_WaterPlane",
        "plane",
        [CITYPARK_PATH_X + 720.0, CITYPARK_PATH_CENTER_Y + 980.0, CITYPARK_PATH_Z + 0.6],
        [4.0, 84.0, 0.035],
        [0.0, 0.0, 0.0],
        fallback_scale=[4.0, 84.0, 0.035],
    )
    bridge_specs = [
        ("00", "/Game/CityPark/Meshes/Road/SM_Bridge01_1", 25360.0, 0.20, 90.0),
        ("01", "/Game/CityPark/Meshes/Road/SM_Bridge02_1", 26680.0, 0.18, 90.0),
    ]
    for suffix, asset_path, y, scale, yaw in bridge_specs:
        _spawn_asset_or_shape(
            f"CineU_LevelPark_BridgeSurface_{suffix}",
            asset_path,
            "cube",
            [CITYPARK_PATH_X + 1220.0, y, CITYPARK_PATH_Z + 1.2],
            [scale, scale, scale],
            [0.0, 0.0, yaw],
            fallback_scale=[2.8, 2.4, 0.10],
        )
    for side, x in [("Left", CITYPARK_PATH_X - 255.0), ("Right", CITYPARK_PATH_X + 255.0)]:
        _spawn_if_missing(
            f"CineU_LevelPark_PathEdge_{side}_00",
            "cube",
            [x, CITYPARK_PATH_CENTER_Y - 1750.0, CITYPARK_PATH_Z + 7.0],
            [0.045, 18.0, 0.07],
        )
    water_plant_assets = [
        "/Game/CityPark/Meshes/Flora/Grass/SM_WaterPlant02",
        "/Game/CityPark/Meshes/Flora/Grass/SM_WaterPlant04",
    ]
    for index, y in enumerate([24880.0, 25360.0, 26040.0, 26920.0, 28160.0, 29520.0]):
        x = CITYPARK_PATH_X + 980.0 + 95.0 * (index % 3)
        _spawn_asset_or_shape(
            f"CineU_LevelPark_WaterPlant_{index:02d}",
            water_plant_assets[index % len(water_plant_assets)],
            "sphere",
            [x, y, CITYPARK_PATH_Z + 3.0],
            [0.26, 0.26, 0.26],
            [0.0, 0.0, -18.0 * index],
            fallback_scale=[0.42, 0.42, 0.18],
        )
    _spawn_asset_or_shape(
        "CineU_LevelPark_WaterWillow_00",
        "/Game/CityPark/Meshes/Flora/Trees/SM_WeepingWillow01",
        "sphere",
        [CITYPARK_PATH_X + 1320.0, 24830.0, CITYPARK_PATH_Z + 2.0],
        [0.30, 0.30, 0.30],
        [0.0, 0.0, -24.0],
        fallback_scale=[1.25, 1.25, 0.95],
    )
    tree_assets = [
        "/Game/CityPark/Meshes/Flora/Trees/SM_WeepingWillow01",
        "/Game/CityPark/Meshes/Flora/Trees/SM_Elm08",
        "/Game/CityPark/Meshes/Flora/Trees/SM_Maple08",
    ]
    backdrop_tree_assets = [
        "/Game/CityPark/Meshes/Flora/Trees/SM_Elm08",
        "/Game/CityPark/Meshes/Flora/Trees/SM_Maple08",
    ]
    background_tree_specs = [
        (-920.0, 24420.0, 0.42),
        (-520.0, 24380.0, 0.36),
        (520.0, 24480.0, 0.40),
        (920.0, 24410.0, 0.34),
    ]
    for index, (x_offset, y, scale) in enumerate(background_tree_specs):
        x = CITYPARK_PATH_X + x_offset
        _spawn_asset_or_shape(
            f"CineU_LevelPark_Park_TreeBackdrop_{index:02d}",
            backdrop_tree_assets[index % len(backdrop_tree_assets)],
            "sphere",
            [x, y, CITYPARK_PATH_Z + 4.0],
            [0.34 * scale, 0.34 * scale, 0.34 * scale],
            [0.0, 0.0, 22.0 * index],
            fallback_scale=[1.25 * scale, 1.25 * scale, 0.95 * scale],
        )
    waterline_tree_assets = [
        "/Game/CityPark/Meshes/Flora/Trees/SM_Elm08",
        "/Game/CityPark/Meshes/Flora/Trees/SM_Maple08",
        "/Game/CityPark/Meshes/Flora/Trees/SM_WeepingWillow01",
    ]
    waterline_bush_assets = [
        "/Game/CityPark/Meshes/Flora/Bushs/SM_Bush3_03",
        "/Game/CityPark/Meshes/Flora/Bushs/SM_Bush5_01",
        "/Game/CityPark/Meshes/Flora/Bushs/SM_Bush2_05",
    ]
    waterline_specs = [
        ("Tree", 1340.0, 25240.0, 0.34, -12.0),
        ("Bush", 1040.0, 25840.0, 0.36, 18.0),
        ("Tree", 1480.0, 26680.0, 0.30, 32.0),
        ("Bush", 1120.0, 27480.0, 0.40, -24.0),
        ("Tree", 1580.0, 28640.0, 0.36, 14.0),
        ("Bush", 1060.0, 29280.0, 0.42, 42.0),
        ("Tree", 1420.0, 30140.0, 0.32, -34.0),
        ("Bush", 1180.0, 30980.0, 0.38, 26.0),
        ("Tree", 1640.0, 31680.0, 0.30, 8.0),
        ("Bush", 1280.0, 32240.0, 0.34, -18.0),
        ("Tree", 1520.0, 32980.0, 0.31, 36.0),
        ("Bush", 1100.0, 33520.0, 0.36, -38.0),
    ]
    for index, (kind, x_offset, y, scale, yaw) in enumerate(waterline_specs):
        assets = waterline_tree_assets if kind == "Tree" else waterline_bush_assets
        _spawn_asset_or_shape(
            f"CineU_LevelPark_WaterlineScreen_{kind}_{index:02d}",
            assets[index % len(assets)],
            "sphere",
            [CITYPARK_PATH_X + x_offset, y, CITYPARK_PATH_Z + 4.0],
            [scale, scale, scale],
            [0.0, 0.0, yaw],
            fallback_scale=[1.45 * scale, 1.45 * scale, 0.95 * scale],
        )
    horizon_grove_specs = [
        ("Tree", 1760.0, 25280.0, 0.40, -8.0),
        ("Bush", 1560.0, 25880.0, 0.44, 21.0),
        ("Tree", 1880.0, 26640.0, 0.36, 28.0),
        ("Bush", 1640.0, 27440.0, 0.42, -19.0),
        ("Tree", 1980.0, 28480.0, 0.38, 11.0),
        ("Bush", 1580.0, 29240.0, 0.46, 35.0),
        ("Tree", 1840.0, 30120.0, 0.37, -31.0),
        ("Bush", 1660.0, 30960.0, 0.42, 18.0),
        ("Tree", 2020.0, 31780.0, 0.36, 7.0),
        ("Bush", 1700.0, 32620.0, 0.40, -23.0),
        ("Tree", 1900.0, 33420.0, 0.34, 32.0),
        ("Bush", 1600.0, 34120.0, 0.38, -37.0),
    ]
    for index, (kind, x_offset, y, scale, yaw) in enumerate(horizon_grove_specs):
        assets = waterline_tree_assets if kind == "Tree" else waterline_bush_assets
        _spawn_asset_or_shape(
            f"CineU_LevelPark_HorizonGrove_{kind}_{index:02d}",
            assets[index % len(assets)],
            "sphere",
            [CITYPARK_PATH_X + x_offset, y, CITYPARK_PATH_Z + 3.0],
            [scale, scale, scale],
            [0.0, 0.0, yaw],
            fallback_scale=[1.55 * scale, 1.55 * scale, 1.02 * scale],
        )
    canopy_frame_specs = [
        ("Left", -1180.0, 25520.0, 0.52, -18.0),
        ("Right", 1160.0, 25880.0, 0.50, 16.0),
        ("Left", -1260.0, 27040.0, 0.58, 28.0),
        ("Right", 1240.0, 27480.0, 0.56, -24.0),
        ("Left", -1180.0, 29040.0, 0.54, 42.0),
        ("Right", 1160.0, 29620.0, 0.60, -32.0),
        ("Left", -1240.0, 30960.0, 0.50, 10.0),
        ("Right", 1220.0, 31680.0, 0.55, -12.0),
    ]
    for index, (side, x_offset, y, scale, yaw) in enumerate(canopy_frame_specs):
        _spawn_asset_or_shape(
            f"CineU_LevelPark_CanopyFrame_{side}_{index:02d}",
            tree_assets[index % len(tree_assets)],
            "sphere",
            [CITYPARK_PATH_X + x_offset, y, CITYPARK_PATH_Z + 10.0],
            [0.46 * scale, 0.46 * scale, 0.46 * scale],
            [0.0, 0.0, yaw],
            fallback_scale=[1.8 * scale, 1.8 * scale, 1.22 * scale],
        )
    shrub_assets = [
        "/Game/CityPark/Meshes/Flora/Bushs/SM_Bush3_03",
        "/Game/CityPark/Meshes/Flora/Bushs/SM_Bush5_01",
        "/Game/CityPark/Meshes/Flora/Bushs/SM_Bush2_05",
    ]
    grass_assets = [
        "/Game/CityPark/Meshes/Flora/Grass/SM_grass07_2",
        "/Game/CityPark/Meshes/Flora/Grass/SM_Grass10_5",
        "/Game/CityPark/Meshes/Flora/Grass/SM_SmallBush1_01",
    ]
    leaf_assets = [
        "/Game/CityPark/Meshes/Ground/SM_DryLeaves02",
        "/Game/CityPark/Meshes/Ground/SM_DryLeaves05",
        "/Game/CityPark/Meshes/Ground/SM_DryLeaves06",
        "/Game/CityPark/Meshes/Ground/SM_DryLeaves07",
    ]
    for index, y in enumerate([24740.0, 25260.0, 25880.0, 26680.0, 27640.0, 28680.0, 29880.0, 30760.0]):
        left_x = CITYPARK_PATH_X - 610.0 - 55.0 * (index % 2)
        right_x = CITYPARK_PATH_X + 610.0 + 45.0 * ((index + 1) % 2)
        _spawn_asset_or_shape(
            f"CineU_LevelPark_PathShrub_Left_{index:02d}",
            shrub_assets[index % len(shrub_assets)],
            "sphere",
            [left_x, y, CITYPARK_PATH_Z + 5.0],
            [0.38, 0.38, 0.38],
            [0.0, 0.0, 31.0 * index],
            fallback_scale=[0.75, 0.75, 0.45],
        )
        _spawn_asset_or_shape(
            f"CineU_LevelPark_PathShrub_Right_{index:02d}",
            shrub_assets[(index + 1) % len(shrub_assets)],
            "sphere",
            [right_x, y + 90.0, CITYPARK_PATH_Z + 5.0],
            [0.34, 0.34, 0.34],
            [0.0, 0.0, -27.0 * index],
            fallback_scale=[0.68, 0.68, 0.42],
        )
    for index, y in enumerate([24840.0, 25520.0, 26340.0, 27220.0, 28240.0, 29320.0, 30440.0]):
        side = "Left" if index % 2 == 0 else "Right"
        x = CITYPARK_PATH_X + (-520.0 if side == "Left" else 520.0)
        _spawn_asset_or_shape(
            f"CineU_LevelPark_PathGrass_{side}_{index:02d}",
            grass_assets[index % len(grass_assets)],
            "sphere",
            [x, y, CITYPARK_PATH_Z + 2.0],
            [0.28, 0.28, 0.28],
            [0.0, 0.0, 19.0 * index],
            fallback_scale=[0.38, 0.38, 0.20],
        )
    leaf_specs = [
        (-160.0, 24880.0, 0.22, 0.0),
        (155.0, 25080.0, 0.18, 37.0),
        (-95.0, 25320.0, 0.16, -24.0),
        (120.0, 25470.0, 0.15, 68.0),
        (-175.0, 25960.0, 0.18, 12.0),
        (165.0, 26340.0, 0.16, -48.0),
        (-130.0, 30240.0, 0.17, 28.0),
        (105.0, 31080.0, 0.15, -42.0),
        (-65.0, 32060.0, 0.14, 64.0),
    ]
    for index, (x_offset, y, scale, yaw) in enumerate(leaf_specs):
        _spawn_asset_or_shape(
            f"CineU_LevelPark_PathLeaves_{index:02d}",
            leaf_assets[index % len(leaf_assets)],
            "plane",
            [CITYPARK_PATH_X + x_offset, y, CITYPARK_PATH_Z + 4.0],
            [scale, scale, 0.035],
            [0.0, 0.0, yaw],
            fallback_scale=[scale, scale, 0.035],
        )
    path_decal_specs = [
        ("/Game/CityPark/Meshes/Road/SM_RoadDecal01", -245.0, 25220.0, 0.055, 8.0),
        ("/Game/CityPark/Meshes/Road/SM_LeakDecal01", 250.0, 26880.0, 0.050, -16.0),
        ("/Game/CityPark/Meshes/Road/SM_RoadDecal05", -255.0, 28640.0, 0.055, 26.0),
        ("/Game/CityPark/Meshes/Road/SM_LeakDecal02", 235.0, 30480.0, 0.045, -34.0),
        ("/Game/CityPark/Meshes/Road/SM_RoadDecal08", -240.0, 32280.0, 0.050, 18.0),
    ]
    for index, (asset_path, x_offset, y, scale, yaw) in enumerate(path_decal_specs):
        _spawn_asset_or_shape(
            f"CineU_LevelPark_PathDecal_{index:02d}",
            asset_path,
            "plane",
            [CITYPARK_PATH_X + x_offset, y, CITYPARK_PATH_Z + 4.4],
            [scale, scale, 0.025],
            [0.0, 0.0, yaw],
            fallback_scale=[scale, scale, 0.025],
        )
    center_path_decal_specs = [
        ("/Game/CityPark/Meshes/Road/SM_RoadDecal01", -80.0, 25120.0, 0.038, -6.0),
        ("/Game/CityPark/Meshes/Road/SM_RoadDecal05", 72.0, 25880.0, 0.036, 18.0),
        ("/Game/CityPark/Meshes/Road/SM_RoadDecal08", -55.0, 26880.0, 0.040, -22.0),
        ("/Game/CityPark/Meshes/Road/SM_DryLeaves02", 95.0, 28280.0, 0.034, 36.0),
        ("/Game/CityPark/Meshes/Road/SM_RoadDecal01", -90.0, 29680.0, 0.036, 8.0),
        ("/Game/CityPark/Meshes/Road/SM_RoadDecal05", 60.0, 31080.0, 0.038, -30.0),
        ("/Game/CityPark/Meshes/Road/SM_RoadDecal08", -48.0, 32380.0, 0.034, 24.0),
    ]
    for index, (asset_path, x_offset, y, scale, yaw) in enumerate(center_path_decal_specs):
        _spawn_asset_or_shape(
            f"CineU_LevelPark_PathDecalCenter_{index:02d}",
            asset_path,
            "plane",
            [CITYPARK_PATH_X + x_offset, y, CITYPARK_PATH_Z + 4.7],
            [scale, scale, 0.022],
            [0.0, 0.0, yaw],
            fallback_scale=[scale, scale, 0.022],
        )
    tree_specs = [
        (-760.0, 24760.0, 1.04),
        (820.0, 24820.0, 0.92),
        (-930.0, 25420.0, 1.05),
        (930.0, 25980.0, 0.95),
        (-980.0, 27620.0, 1.10),
        (980.0, 29260.0, 1.0),
        (-900.0, 30620.0, 0.96),
    ]
    for index, (x_offset, y, scale) in enumerate(tree_specs):
        x = CITYPARK_PATH_X + x_offset
        _spawn_if_missing(f"CineU_LevelPark_Tree_{index:02d}_Trunk", "cube", [x, y, CITYPARK_PATH_Z + 95.0], [0.18, 0.18, 1.9])
        _spawn_asset_or_shape(
            f"CineU_LevelPark_Tree_CanopyMesh_{index:02d}",
            tree_assets[index % len(tree_assets)],
            "sphere",
            [x, y, CITYPARK_PATH_Z],
            [0.42 * scale, 0.42 * scale, 0.42 * scale],
            [0.0, 0.0, 35.0 * index],
            fallback_scale=[1.75 * scale, 1.75 * scale, 1.25 * scale],
        )


def _ensure_park_dressing(level_backed: bool = False, dressing_assets: list[dict[str, Any]] | None = None) -> None:
    if level_backed:
        _remove_actors_with_label_prefixes([
            "CineU_DirectionalLight",
            "CineU_SkyLight",
            "CineU_Park_FillLight",
            "CineU_Park_EndFillLight",
            "CineU_Park_PostProcess",
            "CineU_LevelPark_SubjectKeyLight",
            "CineU_LevelPark_SoftFillLight",
            "CineU_LevelPark_CinematicPostProcess",
            "CineU_Park_Path",
            "CineU_Park_Grass_",
            "CineU_LevelPark_GrassFill",
            "CineU_Park_Railing_",
            "CineU_Park_RailingPost_",
            "CineU_Park_Lamp_",
            "CineU_Park_Tree_",
            "CineU_Park_SubjectFillLight",
            "CineU_LevelPark_Railing_",
            "CineU_LevelPark_RailingPost_",
            "CineU_LevelPark_Lamp_",
            "CineU_LevelPark_BridgeRail_",
            "CineU_LevelPark_BridgeLattice_",
            "CineU_LevelPark_BridgeSurface_",
            "CineU_LevelPark_ForegroundBridge_",
            "CineU_LevelPark_Water_",
            "CineU_LevelPark_WaterlineScreen_",
            "CineU_LevelPark_WaterPlant_",
            "CineU_LevelPark_WaterWillow_",
            "CineU_LevelPark_ForegroundWillow_",
            "CineU_LevelPark_CanopyWillow_",
            "CineU_LevelPark_HangingIvy_",
            "CineU_LevelPark_ImportedCanopy_",
            "CineU_LevelPark_HorizonGrove_",
            "CineU_LevelPark_PathEdge_",
            "CineU_LevelPark_PathDecal_",
            "CineU_LevelPark_PathDecalCenter_",
            "CineU_LevelPark_CanopyFrame_",
            "CineU_LevelPark_AtmosphericFog",
            "CineU_LevelPark_SurfaceDetail_",
            "CineU_LevelPark_NativePathTile_",
            "CineU_LevelPark_PathShrub_",
            "CineU_LevelPark_PathGrass_",
            "CineU_LevelPark_PathLeaves_",
            "CineU_LevelPark_AssetFence_",
            "CineU_LevelPark_WireFence_",
            "CineU_LevelPark_AssetLamp_",
            "CineU_LevelPark_Tree_",
            "CineU_LevelPark_Park_TreeBackdrop_",
            "CineU_LevelPark_ForestBackdrop",
            "CineU_LevelPark_SkyBackdrop",
            "CineU_CityPark_Bridge_",
            "CineU_CityPark_Fence_",
        ])
        _restore_park_level_native_visibility()
        _hide_park_level_camera_occluders()
        _suppress_sparse_focus_tree_instances()
        if dressing_assets:
            _spawn_level_backed_park_asset_accents(dressing_assets=dressing_assets)
        else:
            _spawn_level_backed_park_asset_accents()
        _apply_level_backed_park_world_template_grade()
        return
    _spawn_if_missing("CineU_Park_SkyBackdrop", "cube", [0.0, -1550.0, 520.0], [42.0, 0.08, 14.0])
    _spawn_light_if_missing("CineU_Park_FillLight", "PointLight", [0.0, 120.0, 420.0], None, {"intensity": 1200.0, "attenuation_radius": 2200.0})
    for side, x in [("Left", -205.0), ("Right", 205.0)]:
        for index, y in enumerate([-620.0, -360.0, -100.0, 160.0, 420.0, 680.0]):
            _spawn_if_missing(f"CineU_Park_Railing_{side}_{index:02d}", "cube", [x, y, 74.0], [0.055, 1.65, 0.07])
            _spawn_if_missing(f"CineU_Park_RailingPost_{side}_{index:02d}", "cube", [x, y - 82.0, 54.0], [0.075, 0.075, 1.08])
    for index, y in enumerate([-420.0, 120.0, 600.0]):
        x = -265.0 if index % 2 == 0 else 265.0
        _spawn_if_missing(f"CineU_Park_Lamp_{index:02d}_Post", "cube", [x, y, 145.0], [0.065, 0.065, 2.9])
        _spawn_if_missing(f"CineU_Park_Lamp_{index:02d}_Head", "cube", [x, y, 300.0], [0.22, 0.22, 0.24])
        _spawn_if_missing(f"CineU_Park_Lamp_{index:02d}_Glow", "sphere", [x, y, 286.0], [0.24, 0.24, 0.24])
    tree_specs = [
        (-720.0, -680.0, 0.88),
        (720.0, -520.0, 0.96),
        (-760.0, -80.0, 1.02),
        (760.0, 220.0, 0.92),
        (-700.0, 790.0, 0.95),
        (700.0, 860.0, 0.9),
    ]
    for index, (x, y, scale) in enumerate(tree_specs):
        _spawn_if_missing(f"CineU_Park_Tree_{index:02d}_Trunk", "cube", [x, y, 95.0], [0.18, 0.18, 1.9])
        _spawn_if_missing(f"CineU_Park_Tree_{index:02d}_Canopy", "sphere", [x, y, 255.0], [0.95 * scale, 0.95 * scale, 0.72 * scale])


def _spawn_fallback_actor(spec: dict[str, Any]):
    profile = _visual_profile_for_actor(spec)
    shape = profile["shape"]
    extent = spec.get("bounds_extent", [50, 50, 50])
    scale = _scale_from_extent(extent)
    return _spawn_shape(spec["actor_name"], shape, [0, 0, 0], scale, profile=profile)


def _should_apply_visual_profile_to_loaded_actor(actor, spec: dict[str, Any]) -> bool:
    if _is_real_skeletal_actor(actor, spec) and str(spec.get("semantic_type", "")).lower() == "zebra":
        return True
    return not _is_real_skeletal_actor(actor, spec)


def _should_apply_native_materials_to_loaded_actor(actor, spec: dict[str, Any]) -> bool:
    if str(spec.get("semantic_type", "")).lower() == "zebra":
        return _is_real_skeletal_actor(actor, spec) and bool(_native_material_paths_for_spec(spec))
    return _is_real_skeletal_actor(actor, spec) and bool(_native_material_paths_for_spec(spec))


def _apply_loaded_actor_materials(actor, spec: dict[str, Any]) -> None:
    if _should_apply_native_materials_to_loaded_actor(actor, spec) and _apply_native_asset_materials(actor, spec):
        _apply_public_zebra_transparency_fix(actor, spec)
        return
    if _should_apply_visual_profile_to_loaded_actor(actor, spec) or _should_apply_native_materials_to_loaded_actor(actor, spec):
        _apply_visual_profile(actor, _visual_profile_for_actor(spec))
    _apply_public_zebra_transparency_fix(actor, spec)


def _spawn_loaded_actor(label: str, spec: dict[str, Any], asset):
    actor = unreal.EditorLevelLibrary.spawn_actor_from_object(asset, unreal.Vector(0, 0, 0))
    if actor is None:
        return None
    actor.set_actor_label(label)
    _apply_loaded_actor_materials(actor, spec)
    return actor


def _spawn_actor_from_spec(label: str, spec: dict[str, Any]):
    spawn_spec = {**spec, "actor_name": label, "name": spec.get("name", label)}
    if _use_semantic_proxy_for_actor(spawn_spec):
        return _spawn_fallback_actor(spawn_spec), "semantic_proxy"
    asset_path = spawn_spec.get("asset_path")
    if asset_path:
        try:
            asset = unreal.EditorAssetLibrary.load_asset(str(asset_path))
        except Exception:
            asset = None
        if asset is not None:
            actor = _spawn_loaded_actor(label, spawn_spec, asset)
            if actor is not None:
                return actor, None
    return _spawn_fallback_actor(spawn_spec), "asset_missing"


def ensure_support_surfaces(surfaces: dict[str, Any]) -> None:
    _require_unreal()
    park_surface = surfaces.get("park_path", {}) if isinstance(surfaces.get("park_path", {}), dict) else {}
    level_backed_park = "park_path" in surfaces and str(park_surface.get("environment_asset_type", "")).lower() == "level"
    if not level_backed_park:
        _remove_default_scene_actors()
        _ensure_base_lighting()
    if "desert_floor" in surfaces:
        _spawn_if_missing("CineU_Desert_Floor", "plane", [0, 0, 0], [40, 40, 1])
    if "park_path" in surfaces:
        _spawn_park_surface_primitives(level_backed=level_backed_park)
        _ensure_park_dressing(level_backed=level_backed_park)
    if "river_shallow" in surfaces or "river_bed" in surfaces:
        _spawn_if_missing("CineU_River_Water", "plane", [0, 0, 2.0], [16.0, 7.0, 1.0])
        _spawn_if_missing("CineU_River_Bank_Left", "plane", [-640, 0, 1.0], [4.0, 7.0, 1.0])
        _spawn_if_missing("CineU_River_Bank_Right", "plane", [640, 0, 1.0], [4.0, 7.0, 1.0])
    if "rooftop_floor" in surfaces:
        _spawn_if_missing("CineU_Rooftop_Floor", "cube", [0, 0, -10], [9.0, 9.0, 0.2])
        for index, x in enumerate([-900, -600, -260, 350, 760, 1060]):
            _spawn_if_missing(f"CineU_City_Skyline_{index:02d}", "cube", [x, 920, 220 + (index % 3) * 70], [1.1, 0.85, 4.0 + (index % 3)])
    if "building_floor" in surfaces:
        _spawn_if_missing("CineU_Building_Floor", "plane", [0, 0, 0], [12.0, 12.0, 1.0])
        _spawn_if_missing("CineU_Building_BackWall", "cube", [0, 560, 260], [12.0, 0.18, 5.2])
        _spawn_if_missing("CineU_Building_LeftWall", "cube", [-600, 0, 260], [0.18, 12.0, 5.2])
        _spawn_if_missing("CineU_Building_RightWall", "cube", [600, 0, 260], [0.18, 12.0, 5.2])
    if "gallery_floor" in surfaces:
        _spawn_if_missing("CineU_Gallery_Floor", "plane", [0, 0, 0], [10, 10, 1])
    if "left_wall" in surfaces:
        _spawn_if_missing("CineU_Gallery_LeftWall", "cube", [-500, 0, 400], [0.1, 10, 8])
    if "right_wall" in surfaces:
        _spawn_if_missing("CineU_Gallery_RightWall", "cube", [500, 0, 400], [0.1, 10, 8])
    if "back_wall" in surfaces:
        _spawn_if_missing("CineU_Gallery_BackWall", "cube", [0, 500, 400], [10, 0.1, 8])
    if "gallery_floor" in surfaces:
        _ensure_gallery_dressing()


def ensure_actor_from_state(actor_name: str, spec: dict[str, Any]):
    _require_unreal()
    existing = _find_actor_or_none(actor_name)
    actor_spec = {**spec, "actor_name": actor_name, "name": spec.get("name", actor_name)}
    actor = existing
    actor_was_existing = actor is not None
    if actor is None:
        actor, reused_from = _reuse_existing_actor_for_spec(actor_name, actor_spec)
        actor_was_existing = actor is not None
    surface_profile = _visual_profile_for_surface(actor_name)
    if actor is None and surface_profile and not actor_spec.get("asset_path"):
        transform = actor_spec.get("transform", {})
        scale = transform.get("scale")
        if scale is None:
            scale = _scale_from_extent(actor_spec.get("bounds_extent", [50, 50, 50]))
        return _spawn_shape(
            actor_name,
            surface_profile.get("shape", "cube"),
            transform.get("location", [0, 0, 0]),
            scale,
            transform.get("rotation", [0, 0, 0]),
            profile=surface_profile,
        )
    if actor is None:
        actor, _reason = _spawn_actor_from_spec(actor_name, actor_spec)
    if actor_was_existing:
        _apply_loaded_actor_materials(actor, actor_spec)
    _apply_actor_transform(actor, actor_spec)
    if _should_add_zebra_proxy_details(actor, actor_spec):
        _spawn_zebra_proxy_details(actor_spec)
    elif actor_name.startswith("zebra_"):
        _remove_zebra_proxy_details(actor_name)
        if _should_add_zebra_asset_enhancement_details(actor, actor_spec):
            _spawn_zebra_asset_enhancement_details(actor_spec)
    return actor


def setup_environment(inputs: dict[str, Any]) -> dict[str, Any]:
    _require_unreal()
    level_name = inputs["level_name"]
    environment = inputs.get("environment", "gallery")
    # Minimal, robust editor-side setup. In a production version this function
    # can load curated maps; here it creates empty support context and lighting.
    world = unreal.EditorLevelLibrary.get_editor_world()
    environment_asset = inputs.get("environment_asset")
    dressing_assets = inputs.get("dressing_assets") or []
    environment_asset_result = None
    _remove_default_scene_actors()
    if environment_asset:
        environment_asset_result = _spawn_environment_asset_if_available(environment_asset)
    level_backed_environment = _is_loaded_level_environment(environment_asset, environment_asset_result)
    asset_backed_environment = level_backed_environment or _is_spawned_environment_asset(environment_asset, environment_asset_result)
    if not level_backed_environment:
        _ensure_base_lighting()
    environment_text = str(environment).lower()
    if "desert" in environment_text:
        _spawn_if_missing("CineU_Desert_Floor", "plane", [0, 0, 0], [40, 40, 1])
        support_surfaces = {"desert_floor": {"type": "ground", "z": 0.0, "bounds": [-2000, 2000, -2000, 2000]}}
    elif "park" in environment_text:
        level_backed = level_backed_environment
        if not asset_backed_environment:
            status = "missing_environment_asset"
            if environment_asset_result:
                status = str(environment_asset_result.get("status", status))
            elif environment_asset:
                status = str(environment_asset.get("type", "unsupported_environment_asset"))
            raise RuntimeError(f"Park scenes require an asset-first environment asset loaded successfully; status={status}")
        if level_backed:
            _spawn_park_surface_primitives(level_backed=True)
            _ensure_park_dressing(level_backed=True, dressing_assets=dressing_assets)
            support_surface = _citypark_path_support_surface(level_backed=True)
        else:
            support_surface = _asset_backed_park_support_surface(environment_asset)
        support_surfaces = {"park_path": support_surface}
    elif "river" in environment_text:
        _spawn_if_missing("CineU_River_Water", "plane", [0, 0, 2.0], [16.0, 7.0, 1.0])
        _spawn_if_missing("CineU_River_Bank_Left", "plane", [-640, 0, 1.0], [4.0, 7.0, 1.0])
        _spawn_if_missing("CineU_River_Bank_Right", "plane", [640, 0, 1.0], [4.0, 7.0, 1.0])
        support_surfaces = {
            "river_shallow": {"type": "ground", "z": 0.0, "bounds": [-300, 300, -500, 500]},
            "river_bed": {"type": "ground", "z": -120.0, "bounds": [-500, 500, -500, 500]},
        }
    elif "city" in environment_text or "rooftop" in environment_text:
        _spawn_if_missing("CineU_Rooftop_Floor", "cube", [0, 0, -10], [9.0, 9.0, 0.2])
        for index, x in enumerate([-900, -600, -260, 350, 760, 1060]):
            _spawn_if_missing(f"CineU_City_Skyline_{index:02d}", "cube", [x, 920, 220 + (index % 3) * 70], [1.1, 0.85, 4.0 + (index % 3)])
        support_surfaces = {"rooftop_floor": {"type": "ground", "z": 0.0, "bounds": [-700, 700, -700, 700]}}
    elif "building" in environment_text:
        _spawn_if_missing("CineU_Building_Floor", "plane", [0, 0, 0], [12.0, 12.0, 1.0])
        _spawn_if_missing("CineU_Building_BackWall", "cube", [0, 560, 260], [12.0, 0.18, 5.2])
        _spawn_if_missing("CineU_Building_LeftWall", "cube", [-600, 0, 260], [0.18, 12.0, 5.2])
        _spawn_if_missing("CineU_Building_RightWall", "cube", [600, 0, 260], [0.18, 12.0, 5.2])
        support_surfaces = {"building_floor": {"type": "ground", "z": 0.0, "bounds": [-600, 600, -600, 600]}}
    else:
        _spawn_if_missing("CineU_Gallery_Floor", "plane", [0, 0, 0], [10, 10, 1])
        _spawn_if_missing("CineU_Gallery_LeftWall", "cube", [-500, 0, 400], [0.1, 10, 8])
        _spawn_if_missing("CineU_Gallery_RightWall", "cube", [500, 0, 400], [0.1, 10, 8])
        _spawn_if_missing("CineU_Gallery_BackWall", "cube", [0, 500, 400], [10, 0.1, 8])
        _ensure_gallery_dressing()
        support_surfaces = {
            "gallery_floor": {"type": "ground", "z": 0.0, "bounds": [-500, 500, -500, 500]},
            "left_wall": {"type": "wall", "x": -500.0, "bounds": [-500, -500, -500, 500, 0, 800]},
            "right_wall": {"type": "wall", "x": 500.0, "bounds": [500, 500, -500, 500, 0, 800]},
            "back_wall": {"type": "wall", "y": 500.0, "bounds": [-500, 500, 500, 500, 0, 800]},
        }
    result = {"level": level_name, "environment": environment, "support_surfaces": support_surfaces}
    if environment_asset:
        result["environment_asset"] = environment_asset
    if dressing_assets:
        result["dressing_assets"] = dressing_assets
    if environment_asset_result:
        result["environment_asset_result"] = environment_asset_result
    return result


def spawn_many_actors(actors: list[dict[str, Any]]) -> dict[str, Any]:
    _require_unreal()
    created = []
    reused = []
    warnings = []
    for spec in actors:
        actor_name = spec["actor_name"]
        actor, reused_from = _reuse_existing_actor_for_spec(actor_name, spec)
        if actor is not None:
            created.append(actor_name)
            reused.append({"actor": actor_name, "source": reused_from})
            continue
        _actor, reason = _spawn_actor_from_spec(spec["actor_name"], spec)
        if reason:
            warnings.append({"actor": spec["actor_name"], "reason": reason, "asset_path": spec.get("asset_path")})
        created.append(spec["actor_name"])
    return {"created_actors": created, "reused_actors": reused, "warnings": warnings}


def _find_actor(actor_name: str):
    actor = _find_actor_or_none(actor_name)
    if actor is not None:
        return actor
    raise RuntimeError(f"Actor not found: {actor_name}")


def apply_actor_transforms(placements: list[dict[str, Any]]) -> dict[str, Any]:
    _require_unreal()
    transformed = []
    for placement in placements:
        actor = _find_actor(placement["actor_name"])
        _apply_actor_transform(actor, placement)
        _spawn_painting_wall_details(placement)
        if _should_add_zebra_proxy_details(actor, placement):
            _spawn_zebra_proxy_details(placement)
        elif str(placement.get("actor_name", "")).startswith("zebra_"):
            _remove_zebra_proxy_details(str(placement.get("actor_name", "")))
            if _should_add_zebra_asset_enhancement_details(actor, placement):
                _spawn_zebra_asset_enhancement_details(placement)
        transformed.append(placement["actor_name"])
    return {"transformed": transformed}
