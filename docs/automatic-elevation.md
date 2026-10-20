# Automatic elevation acquisition

`scripts.pipeline.elevation.acquire_dem(aoi, root, log=print)` takes a GeoDataFrame
with CRS and the project root, and returns a `scripts.knowledge.contracts.SourceAsset`.
The returned asset is a raster with `units='m'`, `coverage_state='verified'`,
SHA-256, metric CRS and explicit product provenance. `date` remains unknown;
acquisition time never stands in for the satellite observation date.

For an explicitly selected source, `verify_dem_coverage(asset, aoi)` performs a
read-only preflight using the same grid and halo. It returns `None` on success and
raises `ValueError` for missing/unsupported units, checksum mismatch, missing CRS,
unreadable rasters or incomplete/nodata coverage. Metre and foot units are accepted;
the terrain builder remains responsible for converting elevations supplied in
feet. This helper does not certify user-supplied product metadata.

The output grid uses the terrain builder's metric CRS selection, 30 metre
alignment, and a three-cell (90 metre) halo around the AOI bounding rectangle.
Every cell must have finite elevation supported by valid source cells. Missing
ocean tiles, unreleased tiles, nodata and provider errors fail acquisition; none
are silently filled with zero. This conservative rectangle requirement can reject
an irregular AOI whose bounding rectangle contains unsupported terrain.

## Product selection

The retained `data/raw/DEM/FABDEM_N13E075.tif` is preferred when its SHA-256 matches
the known retained source identity and its raster covers the entire processing
rectangle with valid data. Its original product, noncommercial licence,
attribution and unknown vertical-datum/date status are retained. A filename alone
cannot identify an arbitrary raster as FABDEM. A different local raster can still
be selected manually through the normal source workflow; automatic acquisition
does not invent its metadata.

Otherwise acquisition reads native windows from anonymous HTTPS Copernicus
GLO-30 Public Cloud Optimized GeoTIFFs on AWS. The documented endpoint pattern is:

```
https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N13_00_E075_00_DEM/Copernicus_DSM_COG_10_N13_00_E075_00_DEM.tif
```

GLO-30 is a **digital surface model**, including vegetation, buildings and
infrastructure. It is not measured bare-earth or surveyed landing terrain. The
output preserves `surface_type='DSM'`, EGM2008 vertical datum, source URLs,
projected-window hashes, attribution, licence and uncertainty. The product's
one-arcsecond latitude spacing is approximately 30 metres; longitude spacing
varies with latitude. Resampling onto a 30 metre grid does not improve its native
accuracy. The automatic provider is not FABDEM.

## Bounds and cache validation

- Maximum 4 million output pixels, 8 million pixels in each native source window,
  and 16 source tiles; supported AOIs span at most six longitude degrees and lie
  between 80 degrees south and 84 degrees north. Use smaller AOIs outside limits.
- GDAL `/vsicurl/` performs bounded-window HTTP range reads. Directory/sibling
  discovery is disabled; connection timeout is 5 seconds and each HTTP request
  times out after 20 seconds with one retry. These are per-request limits, not a
  guaranteed total job deadline or a hard network-byte budget. Compressed COG
  blocks can exceed the exact requested window. No credentials are requested.
- Each output file is capped at 32 MB, with a 64 MB free-disk preflight. Temporary
  files use a private staging directory and are removed on errors. Cache growth
  across multiple requests is not automatically pruned.
- `data/cache/elevation/<grid-hash>/dem.tif` is reusable only with matching
  `manifest.json`, output SHA-256, actual CRS/grid/shape/metre band unit, complete
  nodata-free data, known product metadata and expected source tile identities.
  Partial/failed acquisition never publishes a completion manifest.
- The cache manifest and local file hash establish integrity within this project;
  they do not constitute a provider signature or verified full-source checksum.
  Source windows record their projected content hashes without downloading whole
  tiles. Source HTTP exceptions are replaced with a credential-free error.

The module does not publish, build or activate knowledge packages. Caller review
and activation rules remain necessary after a successful source acquisition.
Acquisitions for the same grid should be serialized by the caller; simultaneous
writes have no cross-process locking guarantee.

## Primary references (checked 17 October 2026)

- [Provider readme: tile format, COG grids and DSM coverage](https://copernicus-dem-30m.s3.amazonaws.com/readme.html).
- [AWS Open Data registry: public access and 2021 release](https://registry.opendata.aws/copernicus-dem/).
- [Copernicus product description: EGM2008 datum and product limitations](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM).
- [Copernicus GLO-30 licence](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/DEM/resources/license/License-COPDEM-30.pdf).

Verification uses small real GeoTIFFs behind a mocked remote opener; it does not
download live DEM tiles. Run `.venv/Scripts/python.exe -m pytest
tests/test_elevation_acquisition.py --basetemp data/validation/<unique-name>`.
