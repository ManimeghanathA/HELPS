# Raichur district pipeline

Start with a district GeoJSON and a dated, georeferenced RGB GeoTIFF. Use one scene or a same-date mosaic that covers the full boundary. The Raichur pilot drone image covers a small part of the district.

The workspace boundary is `data/raw/Raichur/raichur-district.geojson`, a simplified 2021 Raichur feature extracted from geoBoundaries India ADM2 (ODbL 1.0). In UTM zone 43N that geometry measures 8,450.99 km². The original drone raster's footprint intersects it over 1.54 km². The coverage check is based on this particular boundary geometry and reports the image footprint before checking pixel validity. [geoBoundaries India metadata and attribution](https://www.geoboundaries.org/api/current/gbOpen/IND/ADM2/)

## Part 1. Inspect and plan

Run from the HELPS folder. Use the actual local capture date and choose a working resolution from 0.5 to 2 metres. The preflight rejects upsampling, known date conflicts and incomplete image extent. It reports covered area and the number of segmentation tiles. The worker checks valid RGB pixels inside each tile as it reads them. Use 8-bit RGB with optional alpha.

```powershell
.venv/Scripts/python.exe -m scripts.knowledge.raichur_district inspect "path/to/raichur.geojson" "path/to/raichur_rgb.tif" 2025-09-01 --metres 1
.venv/Scripts/python.exe -m scripts.knowledge.raichur_district plan "path/to/raichur.geojson" "path/to/raichur_rgb.tif" 2025-09-01 --metres 1 --job data/runs/raichur-district
```

Exit code 2 indicates incomplete coverage. A plan with insufficient coverage does not create a job. A successful plan records input paths and SHA-256 checksums. Keep the source files in place while processing.

## Part 2. Segment in the background

```powershell
./launch-raichur-district.ps1 -Job data/runs/raichur-district
Get-Content data/runs/raichur-district/status.json
```

The launcher starts a separate Windows process with its own logs. Run it from regular PowerShell. The worker does not depend on the browser or Flask. Keep Windows awake while processing. After a shutdown or interruption, use the same launcher and job folder to reuse verified completed tiles. Model setup is shared with the [Raichur RGB prototype](raichur-rgb.md).

The worker reads image tiles with overlap, runs GeoSAM, clips classified polygons to the tile core and the GeoJSON boundary, and saves one GeoPackage per tile. Each polygon has its original class and an initial seed flag. Crops, grass and low vegetation (class 3) and bare soil, rock and sparse ground (class 4) enter the seed mask. The existing 30 minute limit applies to each tile's model stages. District processing time scales with the number of tiles.

## Part 3. Screen the polygons

Supply a metre-based elevation GeoTIFF at approximately 30 m or finer, covering the district plus the slope calculation halo. The screen command joins eligible polygons across tile seams, calculates a 30 m slope raster and clips the polygons to valid measured cells at 15° or less. The shared HELPS area, width, length and clearance gates then run on the clipped pieces.

    .venv/Scripts/python.exe -m scripts.knowledge.raichur_district screen data/runs/raichur-district --dem "path/to/elevation.tif"

The resulting GeoPackage, slope raster and screening audit go in the job's screening folder. Obtaining and mosaicking a district elevation source automatically and loading the screened district package into the application are the remaining integration steps.
