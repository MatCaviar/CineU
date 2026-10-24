from cineu_demo.schemas import Operation
from cineu_demo.state_verifier import StateVerifier
from PIL import Image


def test_no_actor_overlap_ignores_unplanned_unreal_world_actors():
    op = Operation(
        op_id="0003_spatial_place",
        node_id="spatial",
        agent="LayoutAgent",
        type="spatial.apply_transforms",
        template_id="spatial.apply_transforms.v1",
        expected={"no_actor_overlap": True},
    )
    state = {
        "actors": {
            "SM_SkySphere": {
                "asset_type": "StaticMeshActor",
                "bounds_extent": [1000000, 1000000, 1000000],
                "transform": {"location": [0, 0, 0]},
            },
            "CineU_Gallery_Floor": {
                "asset_type": "StaticMeshActor",
                "bounds_extent": [500, 500, 0],
                "transform": {"location": [0, 0, 0]},
            },
            "painting_01": {
                "semantic_type": "painting",
                "asset_id": "asset_gallery_painting_001",
                "asset_type": "static_mesh",
                "bounds_extent": [6, 70, 45],
                "transform": {"location": [-494, -180, 180]},
            },
            "painting_02": {
                "semantic_type": "painting",
                "asset_id": "asset_gallery_painting_001",
                "asset_type": "static_mesh",
                "bounds_extent": [6, 70, 45],
                "transform": {"location": [-494, 0, 180]},
            },
        }
    }

    report = StateVerifier().verify(op, state)

    assert report.passed


def test_render_preview_camera_required_checks_last_render_metadata():
    op = Operation(
        op_id="0008_render_preview",
        node_id="render.preview",
        agent="RenderAgent",
        type="render.preview",
        template_id="render.preview.v1",
        expected={"render_preview_camera_required": True},
    )
    state = {"renders": [{"preview_camera": "CAM_shot_001", "preview_shot_id": "shot_001", "preview_frame": 0}]}

    report = StateVerifier().verify(op, state)

    assert report.passed


def test_on_ground_relation_accepts_skeletal_mesh_root_on_ground():
    op = Operation(
        op_id="0003_spatial_place",
        node_id="spatial",
        agent="LayoutAgent",
        type="spatial.apply_transforms",
        template_id="spatial.apply_transforms.v1",
        expected={"relations": [{"actor": "zebra_01", "relation": "on_ground", "target": "park_path"}]},
    )
    state = {
        "actors": {
            "zebra_01": {
                "semantic_type": "zebra",
                "asset_type": "skeletal_mesh",
                "bounds_extent": [115, 35, 85],
                "transform": {"location": [-600, 0, 0]},
            }
        }
    }

    report = StateVerifier().verify(op, state)

    assert report.passed


def test_on_ground_relation_accepts_level_surface_height():
    op = Operation(
        op_id="0003_spatial_place",
        node_id="spatial",
        agent="LayoutAgent",
        type="spatial.apply_transforms",
        template_id="spatial.apply_transforms.v1",
        expected={"relations": [{"actor": "zebra_01", "relation": "on_ground", "target": "park_path"}]},
    )
    state = {
        "support_surfaces": {
            "park_path": {"type": "ground", "z": 600.0, "bounds": [-87550.0, -86450.0, 15800.0, 21100.0]},
        },
        "actors": {
            "zebra_01": {
                "semantic_type": "zebra",
                "asset_type": "skeletal_mesh",
                "bounds_extent": [115, 35, 85],
                "transform": {"location": [-87000.0, 16400.0, 600.0]},
            }
        },
    }

    report = StateVerifier().verify(op, state)

    assert report.passed


def test_render_preview_camera_required_fails_when_missing():
    op = Operation(
        op_id="0008_render_preview",
        node_id="render.preview",
        agent="RenderAgent",
        type="render.preview",
        template_id="render.preview.v1",
        expected={"render_preview_camera_required": True},
    )
    state = {"renders": [{"artifacts": {"preview_frame.png": "frame.png"}}]}

    report = StateVerifier().verify(op, state)

    assert not report.passed
    assert report.diagnostics["failed_checks"][0]["name"] == "render_preview_camera"


def test_render_artifact_check_rejects_tiny_png(tmp_path):
    preview = tmp_path / "preview_frame.png"
    manifest = tmp_path / "preview_manifest.json"
    preview.write_bytes(b"x")
    manifest.write_text("{}", encoding="utf-8")
    op = Operation(
        op_id="0008_render_preview",
        node_id="render.preview",
        agent="RenderAgent",
        type="render.preview",
        template_id="render.preview.v1",
        expected={"render_artifacts_exist": ["preview_frame.png", "preview_manifest.json"]},
    )
    state = {"renders": [{"artifacts": {"preview_frame.png": str(preview), "preview_manifest.json": str(manifest)}}]}

    report = StateVerifier().verify(op, state)

    assert not report.passed
    assert any(check["name"] == "render_artifact:preview_frame.png" for check in report.diagnostics["failed_checks"])


def test_storyboard_manifest_requires_non_tiny_frame_artifacts(tmp_path):
    storyboard = tmp_path / "storyboard_manifest.json"
    frame = tmp_path / "storyboard_000.png"
    frame.write_bytes(b"x")
    storyboard.write_text(
        '{"frames": [{"artifact": "' + str(frame).replace("\\", "\\\\") + '", "artifact_name": "storyboard_000.png"}]}',
        encoding="utf-8",
    )
    op = Operation(
        op_id="0008_render_preview",
        node_id="render.preview",
        agent="RenderAgent",
        type="render.preview",
        template_id="render.preview.v1",
        expected={"render_artifacts_exist": ["storyboard_manifest.json"]},
    )
    state = {"renders": [{"artifacts": {"storyboard_manifest.json": str(storyboard)}}]}

    report = StateVerifier().verify(op, state)

    assert not report.passed
    assert any(check["name"] == "storyboard_frame_artifact:storyboard_000.png" for check in report.diagnostics["failed_checks"])


def test_storyboard_manifest_rejects_black_frame_artifacts(tmp_path):
    storyboard = tmp_path / "storyboard_manifest.json"
    frame = tmp_path / "storyboard_000.png"
    Image.new("RGB", (1280, 720), color=(0, 0, 0)).save(frame)
    storyboard.write_text(
        '{"frames": [{"artifact": "' + str(frame).replace("\\", "\\\\") + '", "artifact_name": "storyboard_000.png"}]}',
        encoding="utf-8",
    )
    op = Operation(
        op_id="0008_render_preview",
        node_id="render.preview",
        agent="RenderAgent",
        type="render.preview",
        template_id="render.preview.v1",
        expected={"render_artifacts_exist": ["storyboard_manifest.json"]},
    )
    state = {"renders": [{"artifacts": {"storyboard_manifest.json": str(storyboard)}}]}

    report = StateVerifier().verify(op, state)

    assert not report.passed
    failed = next(check for check in report.diagnostics["failed_checks"] if check["name"] == "storyboard_frame_artifact:storyboard_000.png")
    assert "blank" in failed["message"]


def test_render_artifact_check_accepts_non_tiny_gif(tmp_path):
    gif = tmp_path / "sequence_preview.gif"
    gif.write_bytes(b"GIF89a" + (b"x" * 200))
    op = Operation(
        op_id="0008_render_preview",
        node_id="render.preview",
        agent="RenderAgent",
        type="render.preview",
        template_id="render.preview.v1",
        expected={"render_artifacts_exist": ["sequence_preview.gif"]},
    )
    state = {"renders": [{"artifacts": {"sequence_preview.gif": str(gif)}}]}

    report = StateVerifier().verify(op, state)

    assert report.passed


def test_render_artifact_check_rejects_tiny_mp4(tmp_path):
    mp4 = tmp_path / "sequence_preview.mp4"
    mp4.write_bytes(b"x")
    op = Operation(
        op_id="0008_render_preview",
        node_id="render.preview",
        agent="RenderAgent",
        type="render.preview",
        template_id="render.preview.v1",
        expected={"render_artifacts_exist": ["sequence_preview.mp4"]},
    )
    state = {"renders": [{"artifacts": {"sequence_preview.mp4": str(mp4)}}]}

    report = StateVerifier().verify(op, state)

    assert not report.passed
    assert any(check["name"] == "render_artifact:sequence_preview.mp4" for check in report.diagnostics["failed_checks"])


def test_render_artifact_check_rejects_undecodable_mp4(tmp_path):
    mp4 = tmp_path / "sequence_preview.mp4"
    mp4.write_bytes(b"not-a-real-mp4" * 200)
    op = Operation(
        op_id="0008_render_preview",
        node_id="render.preview",
        agent="RenderAgent",
        type="render.preview",
        template_id="render.preview.v1",
        expected={"render_artifacts_exist": ["sequence_preview.mp4"]},
    )
    state = {"renders": [{"artifacts": {"sequence_preview.mp4": str(mp4)}}]}

    report = StateVerifier().verify(op, state)

    assert not report.passed
    failed = next(check for check in report.diagnostics["failed_checks"] if check["name"] == "render_artifact:sequence_preview.mp4")
    assert "decodable" in failed["message"]
