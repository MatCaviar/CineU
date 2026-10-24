# CineU

Asset-first scene orchestration and cinematic rendering with Unreal Engine.

This is the core research code, without Unreal/Fab assets or generated videos.
It includes two execution paths:

1. **Prompt pipeline:** task planning, asset retrieval/import, operation IR,
   template-generated UE Python, execution, verification and local reflection.
2. **Curated scene pipeline:** existing environment maps, pedestrian choreography,
   synchronized cameras, Sequencer, native 2560 x 1440 Movie Render Queue capture,
   video encoding and review frames.

The default planner is rule-based. Mock results validate orchestration, not Unreal
visual quality. Native MetaHuman Collections and thousand-person crowds are **not**
implemented in this release. Compatible character assets, animations and UE
environment projects must be installed separately.

## Install

Use a source checkout and editable installation. Python 3.11+ is required; real
rendering targets Windows and UE 5.5. The wheel alone does not include `knowledge/`
or the Unreal project scaffold.

```powershell
git clone https://github.com/MatCaviar/CineU.git
cd CineU
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## Run the Core E2E

```powershell
.\.venv\Scripts\cineu-demo.exe init --workspace workspace
.\.venv\Scripts\cineu-demo.exe run --prompt-file examples/gallery_tour.txt --runner-mode mock
.\.venv\Scripts\cineu-demo.exe benchmark --tasks-file examples/benchmark_tasks.jsonl
.\.venv\Scripts\python.exe -m pytest
```

Runs write plans, operations, scripts, state snapshots and previews to
`workspace/runs/<run_id>/`. Check `verification/final_report.json` for success.
Mock previews are not UE renders.

## Use Existing Assets

Install selected Fab environments and characters into a local UE project. No
third-party content is redistributed. Index the project before asset-first work:

```powershell
.\.venv\Scripts\cineu-demo.exe rebuild-asset-index `
  --source-dir "E:\Projects\CityParkEnv55\Content" `
  --project-root "E:\Projects\CityParkEnv55"
```

For prompt-to-UE execution, copy `unreal_project/Plugins/CineUDemo` into the target
project's `Plugins/` directory. Enable Python Editor Script Plugin, Editor Scripting
Utilities, Sequencer Scripting and Movie Render Queue. Pass `--runner-mode unreal`,
`--unreal-editor-cmd <UnrealEditor-Cmd.exe>` and `--uproject <project.uproject>` to
`cineu-demo run`. Supply real asset metadata and valid UE paths; generated mock
starter files are not production models or animations.

## Render an Existing Scene

`scripts/render_scene.ps1` runs construction and rendering in separate UE
processes using the curated scene presets. It does not download a map or replace
an imported environment with primitive geometry.

Example: two synchronized Downtown West cafe views, 30 seconds at 24 FPS,
native 2560 x 1440, 2 spatial x 8 temporal samples:

```powershell
.\scripts\render_scene.ps1 `
  -UnrealEditor "E:\UE_5.5\Engine\Binaries\Win64\UnrealEditor.exe" `
  -UProject "E:\Projects\CityParkEnv55\CityParkEnv55.uproject" `
  -Scene world_template_6_7_day `
  -OutputRoot "E:\Renders\cafe_day"

.\.venv\Scripts\cineu-demo.exe hillside-encode-batch `
  --manifest "E:\Renders\cafe_day\render_batch_manifest.json" `
  --output-root "E:\Renders\cafe_day\encoded"
```

First capture a short sample with `-StartFrame 120 -EndFrame 192`: three seconds
of the same 30-second timeline. `-Cameras` selects exact camera names from a preset.
All cameras use the same interval and animation schedule. Existing output
directories are rejected to protect earlier renders.

For Hillside `scene19` / `scene24`, pass `-PrepareHillsideAssets` on the first run
and select matching cameras. This regenerates inventory and skeleton metadata
locally. Do not reuse inventory from a different project.

See [Unreal setup and rendering](docs/UNREAL.md) for configuration and limitations.

## Source Layout

| Directory | Contents |
|---|---|
| `cineu_demo/` | Planner, agents, schemas, assets, runners, verification, encoding |
| `knowledge/templates/` | Runtime operation templates and reference catalog |
| `scripts/unreal/` | Curated scene construction/MRQ and local inventory generation |
| `unreal_project/` | UE scaffold and authored Python plugin |
| `tests/` | Portable core, mock E2E and Unreal API contract tests |
| `examples/` | Prompts and mock benchmark inputs |

Workspace state, credentials, caches, engine binaries, third-party assets, renders
and historical machine-specific diagnostics are excluded from Git. Historical
render-dependent tests are not part of this portable source export.
