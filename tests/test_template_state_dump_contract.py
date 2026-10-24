from pathlib import Path

from cineu_demo.codegen import CodeAssembler
from cineu_demo.schemas import Operation
from cineu_demo.template_store import TemplateStore


RUNTIME_TEMPLATE_IDS = [
    "asset.import_many.v1",
    "animation.add_tracks.v1",
    "camera.dolly_in.v1",
    "camera.hitchcock_zoom.v1",
    "camera.static_shot.v1",
    "camera.wide_aerial.v1",
    "entity.spawn_many.v1",
    "env.setup.v1",
    "render.preview.v1",
    "sequence.camera_cut.v1",
    "sequence.init.v1",
    "transform.add_tracks.v1",
    "spatial.apply_transforms.v1",
]


def test_runtime_templates_pass_params_and_output_to_state_dump():
    store = TemplateStore(Path("knowledge/templates"))
    assembler = CodeAssembler()
    for template_id in RUNTIME_TEMPLATE_IDS:
        template = store.get(template_id)
        op = Operation(op_id="op", node_id="node", agent=template.agent, type=template.operation_type, template_id=template_id)
        script = assembler.assemble(template, op, context={"world_state_path": "world.json"})
        assert 'dump_world_state_to_file(PARAMS["context"]["world_state_path"], PARAMS, OUTPUT)' in script
