from cineu_demo.planner import RuleBasedPlanner


def test_gallery_planner_produces_valid_task_and_dag():
    task, dag, risks = RuleBasedPlanner().plan("创建现代画廊，三幅画和一个雕塑", "demo_project")
    assert task.scene.environment == "gallery"
    assert len(task.entities) == 4
    assert [shot.type for shot in task.camera.shots] == ["dolly_in", "static_shot", "wide_aerial", "dolly_out"]
    assert task.camera.shots[1].target == "painting_02"
    assert "look_target" not in task.camera.shots[3].metadata
    order = dag.topological_order()
    assert "env.setup" in order
    assert order.index("asset.retrieve") < order.index("env.setup")
    assert risks


def test_zebra_planner_produces_hitchcock_shot():
    task, dag, risks = RuleBasedPlanner().plan("斑马 Hitchcock zoom", "demo_project")
    assert task.scene.environment == "desert"
    assert task.camera.shots[0].type == "hitchcock_zoom"
    assert any(node.id == "seq.animation" for node in dag.nodes)
