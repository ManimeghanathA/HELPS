import geopandas as gpd
import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box
from scripts.pipeline import processing


def test_neha_preserves_original_connected_components_until_subtraction(tmp_path,monkeypatch):
    """Diagonal contacts must reach the historical difference operation intact."""
    transform=from_origin(500000,1500200,10,10)
    image=np.zeros((6,20,20),dtype='float32')
    image[:]=np.array([.1,.1,.2,.28,.3,.2])[:,None,None]
    scl=np.full((1,20,20),6,dtype='uint8')
    scl[0,2:10,2:10]=5;scl[0,10:18,10:18]=5
    for name,data in [('spectral',image),('scl',scl)]:
        with rasterio.open(tmp_path/(name+'.tif'),'w',driver='GTiff',width=20,height=20,
                           count=len(data),dtype=data.dtype,crs=32643,transform=transform) as dst:dst.write(data)
    calls=[];original=processing.subtract_buildings
    def observe(frame,buildings,**kwargs):
        calls.append((len(frame),frame.is_valid.all()))
        return original(frame,buildings,**kwargs)
    monkeypatch.setattr(processing,'subtract_buildings',observe)
    aoi=gpd.GeoDataFrame(geometry=[box(500000,1500000,500200,1500200)],crs=32643)
    buildings=gpd.GeoDataFrame(geometry=[box(500400,1500400,500410,1500410)],crs=32643)
    empty=buildings.iloc[:0].copy()
    result=processing.process_inputs(tmp_path/'spectral.tif',tmp_path/'scl.tif',buildings,
        {'water':empty,'industrial':empty},aoi,tmp_path/'output','test',lambda _:None,
        screening_profile='neha-236c34c')
    assert calls[0]==(1,False)
    assert result['final_zones']==2
    assert result['screening_policy']['source_revision']=='236c34c'
    assert result['audits']['passed']
