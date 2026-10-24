# Unreal Setup and Rendering

## Prerequisites

- Windows, UE 5.5 and an existing project with the selected environment,
  characters, materials and compatible animations.
- Enable PythonScriptPlugin, EditorScriptingUtilities, SequencerScripting and
  MovieRenderPipeline. The generic CLI Unreal runner also needs the supplied
  CineUDemo plugin copied into the target project.
- Keep Fab asset paths intact or adapt the preset. `/Game/...` references are
  dependencies, not assets redistributed by this repository.
- Reserve disk space for PNG frames and encoded video. UE jobs are serialized;
  no previous frames are automatically deleted and no system GPU/pagefile settings
  are changed.

## Presets

The builder includes Hillside, MuseumGallery, CityPark, ArtGallery, Warehouse,
Car Dealer, Downtown West and cafe reference presets. See `SCENES` and the camera
definitions in `scripts/unreal/build_and_render_hillside_scene.py` for exact IDs.
Each requires the matching imported packages; arbitrary downloaded projects are
not automatically choreographed.

`world_template_6_7_day` reuses Downtown West's existing cafe. It is a work-in-progress
reference recreation, not a claim of visual equivalence or final film quality.

## Configuration

| Variable | Purpose |
|---|---|
| `CINEU_HILLSIDE_PROJECT` | Project directory containing Hillside assets |
| `CINEU_DIAGNOSTIC_ROOT` | Generated inventory and skeleton metadata directory |
| `CINEU_ASSET_INDEX` | Asset index consumed by the curated UE script |
| `CINEU_UNREAL_EDITOR` | Default editor for the legacy batch-planning CLI |
| `CINEU_UPROJECT` | Default project file for the legacy batch-planning CLI |
| `CINEU_ASSET_SOURCE_DIRS` | Semicolon-separated explicit asset directories |
| `CINEU_EPIC_VAULT_DIRS` | Additional downloaded Fab/VaultCache directories |

Use `scripts/render_scene.ps1` for production captures. It sets range, FPS,
resolution and MRQ settings explicitly and uses separate build/render processes.
The older `hillside-render-batch` CLI generates plans and a historical
single-process launcher; use the production launcher instead of that script.

`-PrepareHillsideAssets` executes the two `query_hillside_*.py` scripts in the
selected project. These regenerate metadata for the asset families used by the
Hillside presets. No author-machine inventory is shipped.

## Outputs

1. Construction saves CineU-owned maps/sequences inside the selected project.
2. A fresh editor reloads the sequence and renders through MRQ.
3. Each camera receives its own `movie_frames/`, state JSON and logs.
4. `render_batch_manifest.json` records completed jobs and the shared frame range.
5. `cineu-demo hillside-encode-batch` produces MP4s, native sampled frames, contact
   sheets and manifests. Encoding does not upscale frames; PNGs are retained.

Review a short interval before rendering every camera. Inspect full bodies,
foot contact, heading, route intersections and animation loops visually.

## Limitations

- The planner is rule-based. `ModelProvider` is an extension interface, not an
  implemented LLM service integration.
- Mock fixtures and previews validate orchestration, not actual UE visual quality.
- Native City Sample Blueprint mode is opt-in. Appearance assembly does not prove
  simultaneous animated crowds. UE 5.8 MetaHuman Collections are not integrated.
- Routes, cameras and animation compatibility are environment-specific.
- The launcher retains `-NoRayTracing` for GPU stability. It uses raster/Lumen
  rendering, not path tracing.
- Install from a source checkout; the Python wheel is not a standalone bundle of
  templates, scripts and the UE scaffold.
