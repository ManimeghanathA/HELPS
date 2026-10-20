import numpy as np
import pytest
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from shapely.geometry import box,Polygon


def test_vision_source_uses_data_folder_and_supports_legacy_layout(tmp_path):
    from scripts.knowledge.run_vision_refinement import vision_source_path
    legacy=tmp_path/'probably_final.qgz/probably_final.gpkg'
    current=tmp_path/'data/probably_final.qgz/probably_final.gpkg'
    with pytest.raises(FileNotFoundError,match='probably_final.gpkg'):
        vision_source_path(tmp_path)
    legacy.parent.mkdir(parents=True);legacy.touch()
    assert vision_source_path(tmp_path)==legacy
    current.parent.mkdir(parents=True);current.touch()
    assert vision_source_path(tmp_path)==current


def test_strict_geometry_preserves_holes_and_rejects_narrow_fragments():
    from scripts.knowledge.vision_refinement import strict_parts
    obstacle=box(40,40,60,60);candidate=box(0,0,120,120).difference(obstacle)
    result=strict_parts(candidate)
    assert result and all(g.intersection(obstacle).area<1e-8 for g in result)
    assert not strict_parts(box(0,0,200,20))
    invalid=Polygon([(0,0),(100,100),(0,100),(100,0),(0,0)])
    assert not strict_parts(invalid)


def test_open_region_contracts_inward_before_geometry_checks():
    from scripts.knowledge.vision_refinement import contract_open_region
    pieces=contract_open_region(box(0,0,100,100),5)
    assert pieces and all(g.difference(box(5,5,95,95)).area<1e-8 for g in pieces)
    assert not contract_open_region(box(0,0,39,100),5)


@pytest.mark.parametrize('values,geom,passing',[
    ([[12,12],[12,12]],box(0,0,60,60),True),
    ([[12,12.01],[12,12]],box(0,0,60,60),False),
    ([[12,-9999],[12,12]],box(0,0,60,60),False),
    ([[12,12],[12,12]],box(-1,0,60,60),False),
    ([[12,12.01],[12,12]],box(0,0,30,60),True),
])
def test_new_site_slope_is_maximum_with_full_support(values,geom,passing):
    from scripts.knowledge.vision_refinement import slope_qualification
    with MemoryFile() as mem:
        with mem.open(driver='GTiff',width=2,height=2,count=1,dtype='float32',crs=32643,transform=from_origin(0,60,30,30),nodata=-9999) as dst:dst.write(np.array(values,dtype='float32'),1)
        with mem.open() as src:assert slope_qualification(geom,src,12)['passed'] is passing


def test_new_regions_do_not_duplicate_existing_or_earlier_additions():
    from scripts.knowledge.vision_refinement import AcceptedIndex
    index=AcceptedIndex();index.add(box(0,0,100,100))
    remainder=index.subtract(box(50,0,150,100));assert remainder.area==5000
    index.add(remainder);assert index.subtract(box(0,0,150,100)).is_empty


def test_complete_refinement_subtracts_contracts_filters_slope_and_keeps_lineage(tmp_path):
    import geopandas as gpd
    from scripts.knowledge.vision_refinement import prepare_seed
    obstacle=box(40,0,60,120);building=box(240,40,260,60)
    class Vision:
        boundary=box(0,0,500,200);sha256='fixture'
        def obstacles(self,g):return obstacle.intersection(g)
        def open_regions(self):
            for i,g in enumerate([box(0,0,120,120),box(200,0,320,120),box(200,0,320,120),box(350,0,480,120)]):
                yield {'fid':i,'feature_key':str(i),'batch_id':'fixture','class_id':4,'geometry':g}
    parents=gpd.GeoDataFrame({'terrain_id':['original']},geometry=[box(0,0,120,120)],crs=32643)
    exclusions={'buildings':gpd.GeoDataFrame(geometry=[building],crs=32643)}
    values=np.full((8,20),5,dtype='float32');values[:,11:]=13
    with MemoryFile() as mem:
        with mem.open(driver='GTiff',width=20,height=8,count=1,dtype='float32',crs=32643,transform=from_origin(0,240,30,30),nodata=-9999) as dst:dst.write(values,1)
        with mem.open() as slope:frame,path,summary=prepare_seed(parents,Vision(),slope,exclusions,tmp_path,12,lambda _:None)
    assert summary['counts']['retained_refined_fragments']==2
    assert summary['counts']['new_added_fragments']==1
    assert summary['counts']['open_rejected_slope_above_limit']==1
    new=frame[frame.refinement_origin=='vision_addition'];assert len(new)==1
    assert new.iloc[0].geometry.difference(box(205,5,315,115)).area<1e-8
    assert frame.intersection(obstacle.union(building)).area.sum()<1e-8
    assert frame.source_zone_id.is_unique and path.is_file()
    for i,g in enumerate(frame.geometry):
        assert all(g.intersection(other).area<1e-8 for other in frame.geometry.iloc[i+1:])
    assert frame.loc[frame.refinement_origin=='retained_refinement','parent_terrain_id'].tolist()==['original','original']
