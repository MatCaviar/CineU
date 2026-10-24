from cineu_demo.planner import RuleBasedPlanner


def test_world_template_planner_routes_reference_scenarios():
    planner = RuleBasedPlanner()

    building, _, _ = planner.plan("Large building. External wide shot to push-in, revealing a car parked inside.", "demo_project")
    assert building.scene.environment == "large_building"
    assert [entity.semantic_type for entity in building.entities] == ["car"]
    assert [shot.type for shot in building.camera.shots] == ["wide_aerial", "dolly_in"]

    rooftop, dag, _ = planner.plan("Cityscape. Man on a rooftop is on the phone. Hitchcock zoom, followed by an orbit shot.", "demo_project")
    assert rooftop.scene.environment == "city_rooftop"
    assert rooftop.entities[0].semantic_type == "human"
    assert [shot.type for shot in rooftop.camera.shots] == ["hitchcock_zoom", "orbit"]
    assert any(node.id == "seq.animation" for node in dag.nodes)

    river, _, _ = planner.plan("River scene and two statue. Focus: one statue above water, then the other underwater.", "demo_project")
    assert river.scene.environment == "river"
    assert [entity.semantic_type for entity in river.entities] == ["statue", "statue"]
    assert [shot.target for shot in river.camera.shots] == ["statue_above_water", "statue_underwater"]

    park, _, _ = planner.plan("In a park, a zebra is moving forward. The camera focuses on the zebra for Hitchcock zoom.", "demo_project")
    assert park.scene.environment == "park"
    assert park.scene.duration_sec == 5.25
    assert park.entities[0].semantic_type == "zebra"
    assert "textured" in park.entities[0].asset_query
    assert park.entities[0].animation["type"] == "walk"
    assert park.entities[0].animation["asset_query"] == "zebra walk turn animation"
    assert park.entities[0].animation["preferred_asset_path"] == "/Game/AfricanAnimalsPack/Zebra/Animations/ANIM_Zebra_WalkTurnR"
    assert park.entities[0].animation["reference_yaw"] == 0.0
    assert park.entities[0].animation["end_time"] == 5.25
    assert park.entities[0].spatial.start == [6241.53, -12053.676, -630.004]
    assert park.entities[0].spatial.end == [6241.53, -12303.676, -630.004]
    assert park.camera.shots[0].type == "hitchcock_zoom"
    assert park.camera.shots[0].metadata["reference_sequence_path"] == "/Game/AnimalHitchcockZoom"
    assert park.camera.shots[0].metadata["reference_capture_path"] == "Saved/VideoCaptures/Showcase_(2).avi"
    assert park.camera.shots[0].metadata["reference_capture_start_frame"] == 10
    assert park.camera.shots[0].metadata["reference_capture_end_frame"] == 330
    assert park.camera.shots[0].metadata["reference_output_fps"] == 30
    assert park.camera.shots[0].metadata["reference_output_end_frame"] == 166
    reference_path = park.camera.shots[0].metadata["reference_camera_path"]
    assert reference_path["source_frame_range"] == [0, 144]
    assert reference_path["location_start"] == [5790.256, -13167.531, -491.342]
    assert reference_path["rotation_start"] == [-0.000002, 0.399902, 67.641907]
    assert reference_path["rotation_end"] == [-0.000002, 0.399902, 67.641907]
    assert reference_path["focal_length_start"] == 35.0
    assert 23.0 <= reference_path["focal_length_end"] <= 25.0
