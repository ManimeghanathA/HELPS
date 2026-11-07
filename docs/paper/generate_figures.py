"""Regenerate the HELPS manuscript figures from local geospatial evidence."""
from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import rasterio

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Patch, Rectangle
from rasterio.plot import plotting_extent
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "figures"
PILOT = ROOT / "data/experiments/raichur-geosam-pilot-2026-11-07"
SMOKE = ROOT / ".tmp/raichur-district-worker-smoke/job"
CLASSES = {
    2: ("Woody vegetation", "#005950"),
    3: ("Crops / grass / low vegetation", "#97b976"),
    4: ("Bare / sparse ground", "#e9af57"),
    8: ("Uncertain / mixed", "#cccdd2"),
}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "text.color": "#182431"})


def save(fig, name):
    fig.savefig(OUT / name, dpi=350, bbox_inches="tight", pad_inches=0.09, facecolor="white")
    plt.close(fig)


def architecture():
    fig, ax = plt.subplots(figsize=(8.2, 2.9))
    ax.set(xlim=(0, 100), ylim=(0, 37))
    ax.axis("off")

    def box(x, y, title, body, color="#eaf3f3"):
        ax.add_patch(FancyBboxPatch((x, y), 21, 9, boxstyle="round,pad=0.3,rounding_size=1",
                                    facecolor=color, edgecolor="#37636a", linewidth=0.8))
        ax.text(x + 10.5, y + 5.9, title, ha="center", va="center", weight="bold", fontsize=7.9)
        ax.text(x + 10.5, y + 2.5, body, ha="center", va="center", fontsize=6.55, linespacing=1.2)

    def arrow(start, end):
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=10,
                                     lw=1, color="#37636a", shrinkA=1, shrinkB=1))

    box(1, 24, "Input", "GeoJSON + dated RGB\nValidate dates and coverage")
    box(26.5, 24, "Tiled classification", "SAM ViT-H + original forest\nKeep class 3 and 4 seeds")
    box(52, 24, "Terrain screening", "Stitch; 30 m slope ≤15°\nApply geometry gates")
    box(77.5, 24, "Knowledge package", "Terrain, source provenance\nand screening decisions")
    box(77.5, 6, "Human review", "Inspect preview and evidence\nAccept or reject", "#fff2da")
    box(52, 6, "Selected observation", "Accept → select the package\nReject → retain selection", "#fff2da")
    box(26.5, 6, "Aircraft assessment", "Known hard failures excluded\nRank with evidence states")
    for left, right in [(22.5, 26), (48, 51.5), (73.5, 77)]:
        arrow((left, 28.5), (right, 28.5))
    arrow((88, 23.5), (88, 15.5))
    arrow((77, 10.5), (73.5, 10.5))
    arrow((51.5, 10.5), (48, 10.5))
    ax.text(1, 18.8, "Detached job records tile progress and saves verified outputs.", fontsize=8.2)
    save(fig, "workflow.png")


def setup_map(ax, bounds, label, scale):
    x0, y0, x1, y1 = bounds
    ax.set(xlim=(x0, x1), ylim=(y0, y1), aspect="equal", xticks=[], yticks=[])
    for spine in ax.spines.values():
        spine.set_color("#26313b")
        spine.set_linewidth(0.65)
    ax.set_title(label, loc="left", weight="bold", pad=7)
    ax.annotate("N", (0.93, 0.92), xytext=(0.93, 0.81), xycoords="axes fraction",
                textcoords="axes fraction", ha="center", va="top", weight="bold",
                bbox={"facecolor": "white", "edgecolor": "none", "pad": 1},
                arrowprops={"facecolor": "#17212b", "width": 1.1, "headwidth": 5, "headlength": 5})
    ax.plot([x0 + (x1-x0)*0.06, x0 + (x1-x0)*0.06 + scale], [y0+(y1-y0)*0.06]*2,
            lw=3, color="white", zorder=10, solid_capstyle="butt")
    ax.plot([x0 + (x1-x0)*0.06, x0 + (x1-x0)*0.06 + scale], [y0+(y1-y0)*0.06]*2,
            lw=1.2, color="#14212e", zorder=11, solid_capstyle="butt")
    ax.text(0.06, 0.085, f"{scale} m", transform=ax.transAxes, fontsize=7.3, zorder=12,
            bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.1})


def rgb(ax, path, bounds=None):
    with rasterio.open(path) as ds:
        window = from_bounds(*bounds, transform=ds.transform) if bounds is not None else None
        data = np.moveaxis(ds.read([1, 2, 3], window=window), 0, -1)
        ax.imshow(data, extent=plotting_extent(ds, transform=None) if window is None else
                  (bounds[0], bounds[2], bounds[1], bounds[3]), interpolation="nearest")
        return tuple(ds.bounds)


def pilot_map():
    fig, axes = plt.subplots(1, 2, figsize=(7.8, 3.8))
    fig.subplots_adjust(wspace=0.07, bottom=0.17)
    bounds = rgb(axes[0], PILOT / "rgb_050m.tif")
    smoke = gpd.read_file(SMOKE.parent / "aoi.geojson").to_crs("EPSG:32643")
    x0, y0, x1, y1 = smoke.total_bounds
    axes[0].add_patch(Rectangle((x0, y0), x1-x0, y1-y0, edgecolor="white",
                                linewidth=2.6, fill=False))
    axes[0].add_patch(Rectangle((x0, y0), x1-x0, y1-y0, edgecolor="#14212e",
                                linestyle="--", linewidth=1.0, fill=False))
    frame = gpd.read_file(PILOT / "neha-original/raichur_results.gpkg", layer="classified_segments")
    for class_id, (_, color) in CLASSES.items():
        frame[frame.class_id == class_id].plot(ax=axes[1], color=color, edgecolor="none")
    setup_map(axes[0], bounds, "(a) RGB and prototype extent", 100)
    setup_map(axes[1], bounds, "(b) Predicted land cover", 100)
    handles = [Patch(facecolor=color, label=label) for label, color in CLASSES.values()]
    handles.append(Line2D([0], [0], color="#14212e", ls="--", label="128 m crop"))
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.51, 0.018),
               ncol=3, frameon=False, fontsize=8)
    save(fig, "raichur-pilot.png")


def smoke_map():
    fig, axes = plt.subplots(1, 2, figsize=(7.8, 3.85))
    fig.subplots_adjust(wspace=0.07, bottom=0.17)
    frame = gpd.read_file(SMOKE.parent / "aoi.geojson").to_crs("EPSG:32643")
    bounds = tuple(np.round(frame.total_bounds, 3))
    candidates = gpd.read_file(SMOKE / "screening/candidates.gpkg")
    rgb(axes[0], PILOT / "rgb_050m.tif", bounds)
    with rasterio.open(SMOKE / "screening/terrain/slope.tif") as ds:
        slope = ds.read(1, masked=True)
        cmap = matplotlib.colormaps["cividis"].resampled(4)
        norm = BoundaryNorm([0, 5, 10, 15, 90], cmap.N)
        axes[1].imshow(slope, cmap=cmap, norm=norm, extent=plotting_extent(ds),
                       interpolation="nearest")
    for ax in axes:
        candidates.boundary.plot(ax=ax, color="black", linewidth=2.6)
        candidates.boundary.plot(ax=ax, color="#ffffff", linewidth=1.2)
        for row in candidates.itertuples():
            pos = row.geometry.representative_point()
            ax.text(pos.x, pos.y, row.terrain_id, ha="center", va="center", weight="bold",
                    fontsize=7.6, bbox={"facecolor": "white", "edgecolor": "#293441", "pad": 1.8})
    setup_map(axes[0], bounds, "(a) RGB and qualifying polygons", 30)
    setup_map(axes[1], bounds, "(b) Slope and qualifying polygons", 30)
    handles = [Patch(facecolor=cmap(i), label=label)
               for i, label in enumerate(["0 to <5°", "5 to <10°", "10 to <15°", "≥15°"])]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.51, 0.02),
               ncol=4, title="Slope display bins", frameon=False, fontsize=8)
    save(fig, "raichur-screening.png")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    architecture()
    pilot_map()
    smoke_map()
