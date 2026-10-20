"""Read official WorldCover COG windows; diagnostic only, never certify terrain."""
import json
from pathlib import Path
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds
from shapely.geometry import shape

OUT = Path(__file__).parent
LABELS = {0:'no_data',10:'trees',20:'shrubland',30:'grassland',40:'cropland',
          50:'built_up',60:'bare_sparse',70:'snow_ice',80:'water',90:'wetland',
          95:'mangroves',100:'moss_lichen'}


def main():
    url = (OUT/'worldcover-source-url.txt').read_text().strip()
    failures = json.loads((OUT/'reported-failures-batch.json').read_text())
    rows = []
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',
                      CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif',
                      GDAL_HTTP_CONNECTTIMEOUT='10',GDAL_HTTP_TIMEOUT='30',
                      GDAL_HTTP_MAX_RETRY='1'):
        with rasterio.open(url) as src:
            if src.crs.to_epsg() != 4326:
                raise ValueError('Unexpected reference CRS')
            for failure in failures:
                zone_id = failure['zone_id']
                evidence = json.loads((OUT/f'{zone_id}-evidence.json').read_text())
                geom = shape(evidence['geometry_wgs84'])
                window = from_bounds(*geom.bounds,transform=src.transform).round_offsets().round_lengths()
                data = src.read(1,window=window)
                inside = geometry_mask([geom],out_shape=data.shape,
                                       transform=src.window_transform(window),invert=True)
                values, counts = np.unique(data[inside],return_counts=True)
                histogram = {LABELS.get(int(v),str(v)):int(n) for v,n in zip(values,counts)}
                row = {'zone_id':zone_id,'reference_pixel_centres':int(inside.sum()),
                       'worldcover_2021_classes':histogram}
                rows.append(row)
                print(json.dumps(row),flush=True)
    result = {'source_url':url,'reference_year':2021,'candidate_source_date':'2026-06-01',
              'purpose':'Supplementary exclusion evidence; not current ground truth',
              'samples':rows,'accuracy_measured':False}
    (OUT/'worldcover-reported-sites-evidence.json').write_text(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
