"""Run the verified SAM and GeoSAM classifier in isolated model processes."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter

import geopandas as gpd
import rasterio

from .repository import _atomic_json
from .sources import file_sha256

TIMEOUT = 30 * 60
SAM_SHA256 = 'a7bf3b02f3ebf1267aba913ff637d9a2d5c33d3173bb679e46d9f338c26f262e'
FOREST_SHA256 = '6b20051872b1722fd09ff30b4ac9000eeffab3d61269cc3ffcebcb6a4b5239f8'
SETTINGS = dict(points_per_side=24, points_per_batch=8, pred_iou_thresh=.82,
                stability_score_thresh=.90, crop_n_layers=0, min_mask_region_area=0)


def runtime_config(root):
    from dotenv import dotenv_values

    config = {**dotenv_values(root / '.env'), **os.environ}
    models = root / 'data/models'
    paths = dict(
        sam_repo=Path(config.get('HELPS_RGB_SAM_REPO') or models / 'segment-anything'),
        checkpoint=Path(config.get('HELPS_RGB_SAM_CHECKPOINT') or models / 'sam_vit_h_4b8939.pth'),
        torch_packages=Path(config.get('HELPS_RGB_TORCH_PACKAGES') or models / 'torch-packages'),
        classifier_packages=Path(config.get('HELPS_RGB_CLASSIFIER_PACKAGES') or models / 'classifier-packages'),
        geosam=Path(config.get('HELPS_RGB_GEOSAM_REPO') or root / 'data/reviews/2026-10-20-cv/repository'),
        forest=Path(config.get('HELPS_RGB_FOREST') or models / 'scene_random_forest.joblib'),
        sam_python=Path(config.get('HELPS_RGB_SAM_PYTHON') or sys.executable),
        classifier_python=Path(config.get('HELPS_RGB_CLASSIFIER_PYTHON') or sys.executable),
    )
    paths = {key: (root / path).resolve() for key, path in paths.items()}
    for key in ('sam_repo', 'checkpoint', 'geosam', 'forest', 'sam_python', 'classifier_python'):
        if not paths[key].exists():
            raise ValueError(f'RGB model setup is missing {key}. See the RGB ingestion setup guide.')
    return {key: str(path.resolve()) for key, path in paths.items()}


def run_segmentation(root, folder, log):
    config = runtime_config(root)
    _atomic_json(folder / 'model-inputs.json', config)
    log('GeoSAM: segmenting and classifying RGB (30-minute limit)')
    started = perf_counter()
    try:
        with (folder / 'segmentation.log').open('w', encoding='utf-8') as stream:
            for phase, python, packages in (
                    ('infer', config['sam_python'], config['torch_packages']),
                    ('classify', config['classifier_python'], config['classifier_packages'])):
                env = {**os.environ, 'PYTHONPATH': packages,
                       'MPLCONFIGDIR': str(root / 'data/cache/rgb-matplotlib')}
                if phase == 'classify':
                    log('GeoSAM: composing and classifying segmentation masks')
                command = [python, '-m', 'scripts.knowledge.rgb_model', phase, str(folder)]
                options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
                result = subprocess.run(command, cwd=root, env=env, stdin=subprocess.DEVNULL,
                                        stdout=stream, stderr=subprocess.STDOUT, **options,
                                        timeout=max(.001, TIMEOUT - (perf_counter() - started)))
                if result.returncode:
                    raise ValueError(f'GeoSAM {phase} failed. See {folder}/segmentation.log.')
    except subprocess.TimeoutExpired:
        raise ValueError('Segmentation reached 30 minutes and stopped. Try a smaller crop.') from None
    return json.loads((folder / 'segmentation.json').read_text(encoding='utf-8'))


def infer(folder):
    """Run SAM in a killable subprocess."""
    import numpy as np

    config = json.loads((folder / 'model-inputs.json').read_text(encoding='utf-8'))
    sys.path.insert(0, config['sam_repo'])
    import torch
    from segment_anything import SamAutomaticMaskGenerator, sam_model_registry

    if file_sha256(config['checkpoint']) != SAM_SHA256:
        raise ValueError('SAM weights differ from the pinned checkpoint.')
    with rasterio.open(folder / 'rgb.tif') as src:
        rgb = src.read((1, 2, 3)).transpose(1, 2, 0)
    start = perf_counter()
    torch.set_num_threads(min(6, os.cpu_count() or 1))
    sam = sam_model_registry['vit_h']()
    sam.load_state_dict(torch.load(config['checkpoint'], map_location='cpu', weights_only=True))
    sam.eval()
    loaded = perf_counter()
    with torch.inference_mode():
        masks = SamAutomaticMaskGenerator(sam, **SETTINGS).generate(rgb)
    inferred = perf_counter()
    np.savez_compressed(folder / 'sam-masks.npz',
                        masks=np.array([np.packbits(item['segmentation'].ravel()) for item in masks]),
                        scores=np.array([item['predicted_iou'] for item in masks]))
    _atomic_json(folder / 'sam.json', dict(
        sam='SAM ViT-H', settings=SETTINGS, checkpoint_sha256=SAM_SHA256,
        sam_package_sha256=file_sha256(Path(config['sam_repo']) / 'segment_anything/automatic_mask_generator.py'),
        torch=str(torch.__version__), threads=torch.get_num_threads(), mask_count=len(masks),
        model_load_seconds=round(loaded-start, 2), sam_inference_seconds=round(inferred-loaded, 2),
        image_sha256=file_sha256(folder / 'rgb.tif')))


def classify_masks(folder):
    import numpy as np
    import joblib
    import sklearn

    start = perf_counter()
    config = json.loads((folder / 'model-inputs.json').read_text(encoding='utf-8'))
    sys.path.insert(0, str(Path(config['geosam']) / 'bhadra_highres_batches'))
    from pipeline import classify, compose

    if sklearn.__version__ != '1.8.0':
        raise ValueError('The original forest requires scikit-learn 1.8.0.')
    if file_sha256(config['forest']) != FOREST_SHA256:
        raise ValueError('Classifier weights differ from the pinned GeoSAM model.')
    with rasterio.open(folder / 'rgb.tif') as src:
        rgb = src.read((1, 2, 3)).transpose(1, 2, 0)
        transform, crs = src.transform, src.crs
    sam = json.loads((folder / 'sam.json').read_text(encoding='utf-8'))
    if sam['image_sha256'] != file_sha256(folder / 'rgb.tif'):
        raise ValueError('The mask input changed after SAM inference.')
    proposals = []
    with np.load(folder / 'sam-masks.npz') as bundle:
        height, width = rgb.shape[:2]
        for index, (packed, score) in enumerate(zip(bundle['masks'], bundle['scores'])):
            mask = np.unpackbits(packed, count=height*width).reshape(height,width).astype(bool)
            yy, xx = np.where(mask)
            if len(xx) < 40:
                continue
            x, y, x2, y2 = int(xx.min()), int(yy.min()), int(xx.max())+1, int(yy.max())+1
            proposals.append(dict(bbox=(x, y, x2-x, y2-y), mask=mask[y:y2, x:x2].copy(),
                                  area_px=len(xx), source_key=f'sam_{index}', sam_score=float(score)))
    regions, ids, composition = compose(rgb, transform, proposals, {'footprints': []})
    empty = np.zeros(ids.shape, dtype=np.uint8)
    context = dict(reference=empty, fixed=empty, road_zone=empty, road_distance=np.ones(ids.shape, 'float32'))
    forest = joblib.load(config['forest'])
    regions = classify(rgb, ids, regions, transform, context, forest).set_crs(crs, allow_override=True)
    regions.to_file(folder / 'segmentation.gpkg', layer='classified_segments', index=False)
    _atomic_json(folder / 'segmentation.json', dict(
        **sam, forest_sha256=FOREST_SHA256, scikit_learn=sklearn.__version__,
        geosam_pipeline_sha256=file_sha256(Path(config['geosam']) / 'bhadra_highres_batches/pipeline.py'),
        composition_and_classification_seconds=round(perf_counter()-start, 2),
        segment_count=len(regions), composition=composition,
        class_area_m2=regions.groupby('class_name').area_m2.sum().to_dict(),
        context='No independently verified road, roof, obstacle or restriction coverage'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run the RGB segmentation worker')
    parser.add_argument('phase', choices=('infer','classify'))
    parser.add_argument('folder', type=Path)
    args = parser.parse_args()
    if args.phase == 'infer':
        infer(args.folder)
    else:
        classify_masks(args.folder)
