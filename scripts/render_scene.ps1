param(
    [Parameter(Mandatory = $true)][string]$UnrealEditor,
    [Parameter(Mandatory = $true)][string]$UProject,
    [string]$Scene = 'world_template_6_7_day',
    [string[]]$Cameras = @('CineU_world_template_7_oblique_branch', 'CineU_world_template_6_top_surveillance'),
    [string]$OutputRoot = '',
    [ValidateRange(1, 14400)][int]$FrameCount = 720,
    [ValidateRange(1, 120)][int]$FPS = 24,
    [ValidateRange(0, 14399)][int]$StartFrame = 0,
    [int]$EndFrame = -1,
    [ValidateRange(1, 16)][int]$SpatialSamples = 2,
    [ValidateRange(1, 32)][int]$TemporalSamples = 8,
    [ValidateRange(60, 86400)][int]$TimeoutSeconds = 14400,
    [switch]$PrepareHillsideAssets
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$UnrealEditor = (Resolve-Path -LiteralPath $UnrealEditor).Path
$UProject = (Resolve-Path -LiteralPath $UProject).Path
if ($EndFrame -eq -1) { $EndFrame = $FrameCount }
if ($StartFrame -ge $EndFrame -or $EndFrame -gt $FrameCount) { throw 'Require 0 <= StartFrame < EndFrame <= FrameCount' }
if (-not $Cameras.Count) { throw 'Specify at least one camera name from the scene preset' }
if (-not $OutputRoot) {
    $OutputRoot = Join-Path $repoRoot ('workspace\renders\' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
}
$OutputRoot = [IO.Path]::GetFullPath($OutputRoot)
if (Test-Path -LiteralPath $OutputRoot) { throw "Use a new output directory to preserve previous renders: $OutputRoot" }
New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
$scriptPath = Join-Path $PSScriptRoot 'unreal\build_and_render_hillside_scene.py'
$env:CINEU_HILLSIDE_PROJECT = Split-Path -Parent $UProject
if (-not $env:CINEU_DIAGNOSTIC_ROOT) {
    $env:CINEU_DIAGNOSTIC_ROOT = Join-Path $repoRoot 'workspace\diagnostics\hillside_scene19_scene24'
}
$env:CINEU_HILLSIDE_SCENE = $Scene
$env:CINEU_HILLSIDE_MODE = 'production2k'
$env:CINEU_HILLSIDE_RENDER_QUALITY = 'cinematic'
$env:CINEU_HILLSIDE_RENDER_BACKEND = 'movie_render_pipeline'
$env:CINEU_HILLSIDE_WIDTH = '2560'
$env:CINEU_HILLSIDE_HEIGHT = '1440'
$env:CINEU_HILLSIDE_FRAME_COUNT = [string]$FrameCount
$env:CINEU_HILLSIDE_FPS = [string]$FPS
$env:CINEU_HILLSIDE_CAPTURE_START_FRAME = [string]$StartFrame
$env:CINEU_HILLSIDE_CAPTURE_END_FRAME = [string]$EndFrame
$env:CINEU_HILLSIDE_SPATIAL_SAMPLES = [string]$SpatialSamples
$env:CINEU_HILLSIDE_TEMPORAL_SAMPLES = [string]$TemporalSamples
$env:CINEU_HILLSIDE_WARMUP = '32'
$env:CINEU_HILLSIDE_CAPTURE_TIMEOUT = [string]$TimeoutSeconds
$env:CINEU_MRQ_LOW_MEMORY = '0'
$env:CINEU_MRQ_CVARS = 'r.ScreenPercentage 100', 'r.MipMapLODBias 0', 'r.Streaming.PoolSize 4096', 'r.Nanite.MaxPixelsPerEdge 1', 'foliage.DensityScale 1' -join "`n"

function Invoke-UnrealPython([string]$PythonScript, [string]$LogPath) {
    $arguments = @(
        "`"$UProject`"", '/Engine/Maps/Entry', '-unattended', '-nop4', '-nosplash', '-NoRayTracing',
        '-EnablePlugins=RigLogic', '-ini:Engine:[Blueprints]:bUseSimpleWildcardInference=True',
        "-abslog=`"$LogPath`"", "-ExecutePythonScript=`"$PythonScript`""
    )
    $process = Start-Process -FilePath $UnrealEditor -ArgumentList $arguments -WindowStyle Hidden -PassThru
    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        Stop-Process -Id $process.Id -Force
        throw "Unreal timed out; see $LogPath"
    }
    if ($process.ExitCode -ne 0) { throw "Unreal exit code $($process.ExitCode); see $LogPath" }
    $errors = Select-String -LiteralPath $LogPath -Pattern 'LogPython: Error:|LogBlueprint: Error:|Fatal error:|GPU Crashed|Out of video memory'
    if ($errors) { throw ($errors.Line -join "`n") }
}

if ($PrepareHillsideAssets) {
    foreach ($name in @('query_hillside_capabilities', 'query_hillside_character_skeletons')) {
        Invoke-UnrealPython (Join-Path $PSScriptRoot "unreal\$name.py") (Join-Path $OutputRoot "$name.log")
    }
}
$jobs = @()
foreach ($camera in $Cameras) {
    if ($camera -notmatch '^CineU_[A-Za-z0-9_]+$') { throw "Invalid camera name: $camera" }
    $env:CINEU_HILLSIDE_CAMERA = $camera
    $env:CINEU_HILLSIDE_OUTPUT_DIR = Join-Path $OutputRoot $camera
    New-Item -ItemType Directory -Path $env:CINEU_HILLSIDE_OUTPUT_DIR | Out-Null
    foreach ($phase in @('build', 'audit_render')) {
        $env:CINEU_HILLSIDE_EXECUTION_PHASE = $phase
        Write-Output "$Scene / $camera / $phase"
        Invoke-UnrealPython $scriptPath (Join-Path $env:CINEU_HILLSIDE_OUTPUT_DIR "unreal_$phase.log")
        $summary = Get-Content -LiteralPath (Join-Path $env:CINEU_HILLSIDE_OUTPUT_DIR 'build_render_summary.json') -Raw | ConvertFrom-Json
        if ($summary.execution_phase -ne $phase) { throw "Missing current $phase summary for $camera" }
    }
    if (-not $summary.render_result.capture_success) { throw "Capture failed for $camera" }
    $jobs += @{
        scene = $Scene; camera_name = $camera; output_dir = $env:CINEU_HILLSIDE_OUTPUT_DIR
        frame_count = $EndFrame - $StartFrame; fps = $FPS; resolution = @(2560, 1440)
        start_frame = $StartFrame; end_frame = $EndFrame
    }
    @{schema_version = 'cineu.hillside_render_batch.v1'; jobs = $jobs} |
        ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $OutputRoot 'render_batch_manifest.json') -Encoding UTF8
}
Write-Output "Completed frames and encoding manifest: $OutputRoot"
