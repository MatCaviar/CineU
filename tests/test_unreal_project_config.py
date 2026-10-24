from pathlib import Path


def test_cineu_project_preserves_citypark_renderer_settings():
    config = Path("unreal_project/Config/DefaultEngine.ini").read_text(encoding="utf-8")

    assert "[/Script/Engine.RendererSettings]" in config
    for line in [
        "r.GenerateMeshDistanceFields=True",
        "r.EarlyZPass=3",
        "r.AllowGlobalClipPlane=True",
        "r.LightPropagationVolume=True",
        "r.SeparateTranslucency=False",
        "r.DefaultFeature.AntiAliasing=2",
    ]:
        assert line in config
