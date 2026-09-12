param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$workspaceRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$manifestPath = Join-Path $workspaceRoot 'docs/cleanup-manifest.json'
if (Test-Path -LiteralPath $manifestPath) { throw 'Cleanup manifest already exists; cleanup is a one-time migration.' }
$actions = [Collections.Generic.List[object]]::new()
function Add-Move([string]$source, [string]$destination) {
    $actions.Add([pscustomobject]@{action='archive';source=$source;destination=$destination})
}
$active = @('open_land_detector.py','candidate_polygonization.py','building_subtraction.py','candidate_geometry_filter.py','clearance_analysis.py','operational_zone_extraction.py','maximum_clearance.py','candidate_cloud_audit.py','__init__.py','organize_workspace.ps1')
Get-ChildItem -LiteralPath (Join-Path $workspaceRoot 'scripts') -Recurse -File | Where-Object {
    $_.FullName -notmatch '[\\/](archive|pipeline|ui|__pycache__)[\\/]' -and $_.Name -notin $active
} | ForEach-Object {
    $relative = [IO.Path]::GetRelativePath($workspaceRoot, $_.FullName)
    Add-Move $relative (Join-Path 'scripts/archive' ([IO.Path]::GetRelativePath((Join-Path $workspaceRoot 'scripts'), $_.FullName)))
}
Add-Move 'tests/test_osm_obstacle_filter.py' 'scripts/archive/tests/test_osm_obstacle_filter.py'
Get-ChildItem -LiteralPath (Join-Path $workspaceRoot 'data/raw/Bhadra') -File | Where-Object { $_.Name -ne 'bhadra_entire_region.geojson' } | ForEach-Object {
    $relative = [IO.Path]::GetRelativePath($workspaceRoot, $_.FullName)
    Add-Move $relative (Join-Path 'data/raw/Bhadra/archive' $_.Name)
}
$imagery = 'data/processed/Bhadra/sentinel2/2026-06-01'
$keep = @('bhadra_spectral.tif','bhadra_scl.tif','bhadra_possible_open_mask_v2.tif','bhadra_final_open_land_zones.gpkg','bhadra_final_open_land_zones.png','bhadra_rejection_reason_map.png','bhadra_rgb_preview.png')
$delete = @('Baseline_1.png','bhadra_empty_land_mask.tif','bhadra_empty_land_mask_osm_overture.tif','bhadra_empty_land_overlay.png','bhadra_open_mask.tif','bhadra_osm_obstacle_mask.tif','bhadra_overture_building_mask.tif','bhadra_refined_empty_land_overlay.png','bhadra_overture_building_overlay.png','bhadra_v1_v2_comparison.png','bhadra_final_candidate_borders.png','bhadra_open_land_before_after_buildings.png')
Get-ChildItem -LiteralPath (Join-Path $workspaceRoot $imagery) -File | Where-Object { $_.Name -notin $keep } | ForEach-Object {
    $relative = [IO.Path]::GetRelativePath($workspaceRoot,$_.FullName)
    if ($_.Name -in $delete) {
        $actions.Add([pscustomobject]@{action='delete-generated';source=$relative;destination=$null})
    } else { Add-Move $relative (Join-Path (Join-Path $imagery 'archive') $_.Name) }
}
foreach ($file in @('bhadra_overture_buildings_bbox.geojson','bhadra_overture_buildings_bbox.geojson.state','bhadra_overture_buildings_in_possible_open.geojson')) {
    Add-Move "data/processed/Bhadra/buildings/$file" "data/processed/Bhadra/buildings/archive/$file"
}
Add-Move 'data/processed/Bhadra/dem/bhadra_srtm_clipped.tif' 'data/processed/Bhadra/dem/archive/bhadra_srtm_clipped.tif'
Get-ChildItem -LiteralPath (Join-Path $workspaceRoot 'docs') -File | Where-Object { $_.Extension -ne '.md' } | ForEach-Object { Add-Move "docs/$($_.Name)" "docs/archive/$($_.Name)" }
Add-Move 'PAPERS' 'docs/archive/PAPERS'
foreach ($file in @('Bhadra_boundry.qgz','HELPS.txt','project context.txt','Screenshot 2026-07-28 001235.png','Screenshot 2026-07-28 001802.png','Vishnu_Annotation_Preparation.qgz','Vishnu_Annotation_Sample_01.qgz')) {
    Add-Move $file "archive/$file"
}
Add-Move 'Vishnu_Annotation_Package_2026-06-01' 'data/validation/archive/Vishnu_Annotation_Package_2026-06-01'
Add-Move 'Vishnu_Annotation_Package_2026-06-01.zip' 'data/validation/archive/Vishnu_Annotation_Package_2026-06-01.zip'
# Resolve every target before moving any file or directory.
foreach ($item in $actions) {
    foreach ($relative in @($item.source,$item.destination)) {
        if (-not $relative) { continue }
        $full = [IO.Path]::GetFullPath((Join-Path $workspaceRoot $relative))
        if (-not $full.StartsWith($workspaceRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw "Outside workspace: $full" }
    }
    if (-not (Test-Path -LiteralPath (Join-Path $workspaceRoot $item.source))) { throw "Missing source: $($item.source)" }
    if ($item.destination -and (Test-Path -LiteralPath (Join-Path $workspaceRoot $item.destination))) { throw "Destination exists: $($item.destination)" }
}
if (-not $Apply) { $actions | Format-Table -AutoSize; return }
foreach ($item in $actions) {
    $source = Join-Path $workspaceRoot $item.source
    if ($item.action -eq 'delete-generated') { Remove-Item -LiteralPath $source }
    else {
        $destination = Join-Path $workspaceRoot $item.destination
        New-Item -ItemType Directory -Force -Path (Split-Path $destination) | Out-Null
        Move-Item -LiteralPath $source -Destination $destination
    }
}
$dataDirs = @((Get-Item -LiteralPath (Join-Path $workspaceRoot 'data'))) + @(Get-ChildItem -LiteralPath (Join-Path $workspaceRoot 'data') -Recurse -Directory | Where-Object { $_.FullName -notmatch '[\\/]archive([\\/]|$)' })
foreach ($directory in $dataDirs) {
    New-Item -ItemType Directory -Force -Path (Join-Path $directory.FullName 'archive') | Out-Null
}
$actions | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifestPath -Encoding utf8
Write-Output "Completed $($actions.Count) cleanup actions. Manifest: $manifestPath"
