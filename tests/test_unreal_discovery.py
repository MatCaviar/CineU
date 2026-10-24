from pathlib import Path

from cineu_demo.unreal_discovery import discover_unreal_editor_cmd


def test_discover_unreal_editor_cmd_prefers_ue_55(tmp_path: Path):
    ue55 = tmp_path / "UE_5.5" / "Engine" / "Binaries" / "Win64"
    ue56 = tmp_path / "UE_5.6" / "Engine" / "Binaries" / "Win64"
    ue55.mkdir(parents=True)
    ue56.mkdir(parents=True)
    cmd55 = ue55 / "UnrealEditor-Cmd.exe"
    cmd56 = ue56 / "UnrealEditor-Cmd.exe"
    cmd55.write_text("", encoding="utf-8")
    cmd56.write_text("", encoding="utf-8")

    found = discover_unreal_editor_cmd(search_roots=[tmp_path])

    assert found == str(cmd55)


def test_discover_unreal_editor_cmd_returns_none_when_missing(tmp_path: Path):
    assert discover_unreal_editor_cmd(search_roots=[tmp_path]) is None
