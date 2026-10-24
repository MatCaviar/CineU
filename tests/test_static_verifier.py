from cineu_demo.codegen import StaticVerifier
from cineu_demo.schemas import Operation


def op():
    return Operation(op_id="op", node_id="n", agent="EnvAgent", type="env.setup", template_id="env.setup.v1")


def test_static_verifier_allows_wrapper_imports():
    script = "from cineu_world_ops import setup_environment\nPARAMS = {}\nOUTPUT = setup_environment(PARAMS)\n"
    report = StaticVerifier().verify(script, op())
    assert report.passed


def test_static_verifier_rejects_os_import():
    script = "import os\nos.system('echo bad')\n"
    report = StaticVerifier().verify(script, op())
    assert not report.passed
    assert report.diagnostics["error_type"] == "AST_GUARD_VIOLATION"
