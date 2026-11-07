"""Generate Bhadra thematic figures using saved classification and screening vectors."""
from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
from shapely.geometry import box

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "figures"
VISION = ROOT / "data/probably_final.qgz/probably_final.gpkg"
SEED = ROOT / "data/knowledge/bhadra-cv-20260601-313234b7/refinement-input/candidate_seed.gpkg"
COLORS = {
    1: "#68a8c8", 2: "#477458", 3: "#c2ce83", 4: "#e0ba84",
    5: "#c4513b", 6: "#874b5d", 7: "#63626a", 8: "#c8c5cb",
}
INK = "#243443"
CANDIDATE = "#873777"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "text.color": INK})


def save(fig, name):
    fig.savefig(OUT / name, dpi=320, bbox_inches="tight", pad_inches=0.08, facecolor="white")
    plt.close(fig)


def map_frame(ax, bounds, title, scale):
    left, bottom, right, top = bounds
    ax.set(xlim=(left, right), ylim=(bottom, top), aspect="equal", xticks=[], yticks=[])
    ax.set_title(title, loc="left", weight="bold", fontsize=9, pad=7)
    for spine in ax.spines.values():
        spine.set_color("#86919a")
        spine.set_linewidth(0.6)
    ax.annotate("N", (0.94, 0.94), (0.94, 0.83), xycoords="axes fraction",
                textcoords="axes fraction", ha="center", va="top", weight="bold", fontsize=7.5,
                bbox={"facecolor": "white", "edgecolor": "none", "pad": 1},
                arrowprops={"facecolor": INK, "width": 1.0, "headwidth": 5, "headlength": 5})
    x, y = left + (right-left)*0.05, bottom + (top-bottom)*0.055
    ax.plot([x, x+scale], [y, y], lw=3, color="white", zorder=10, solid_capstyle="butt")
    ax.plot([x, x+scale], [y, y], lw=1.1, color=INK, zorder=11, solid_capstyle="butt")
    label = f"{scale/1000:g} km" if scale >= 1000 else f"{scale:g} m"
    ax.text(0.05, 0.073, label, transform=ax.transAxes, fontsize=7, zorder=12,
            bbox={"facecolor": "white", "edgecolor": "none", "pad": 1})


def candidate_window(additions, size=2000):
    points = additions.representative_point()
    bins = pd.DataFrame({"x": np.floor(points.x/size), "y": np.floor(points.y/size)})
    ix, iy = bins.value_counts().index[0]
    left, bottom = ix*size, iy*size
    return left, bottom, left+size, bottom+size


def detail(additions, bounds):
    frame = gpd.GeoDataFrame(pd.concat([
        gpd.read_file(VISION, layer=layer, bbox=bounds, columns=["class_id"])
        for layer in ("open_regions", "other_regions")
    ], ignore_index=True), crs=32643)
    crop = additions.clip(box(*bounds))
    fig, axes = plt.subplots(1, 2, figsize=(7.7, 4))
    fig.subplots_adjust(wspace=0.09, bottom=0.18)
    for ax in axes:
        for class_id, group in frame.groupby("class_id"):
            group.plot(ax=ax, color=COLORS[class_id], edgecolor="none")
    crop.boundary.plot(ax=axes[1], color="white", linewidth=1.6, zorder=3)
    crop.boundary.plot(ax=axes[1], color=CANDIDATE, linewidth=0.8, zorder=4)
    map_frame(axes[0], bounds, "(a) Predicted classes", 500)
    map_frame(axes[1], bounds, "(b) Qualified footprints", 500)
    names = {1: "Water", 2: "Woody vegetation", 3: "Low vegetation",
             4: "Bare / sparse ground", 8: "Uncertain / mixed"}
    legend = [Patch(color=COLORS[c], label=label) for c, label in names.items()]
    legend += [Line2D([0], [0], color=CANDIDATE, label="Segmentation-derived addition")]
    if frame.class_id.isin([5, 6, 7]).any():
        legend += [Patch(color=COLORS[c], label=label)
                   for c, label in [(5, "Roof"), (6, "Industrial"), (7, "Road")]
                   if (frame.class_id == c).any()]
    fig.legend(handles=legend, loc="lower center", bbox_to_anchor=(0.5, 0.02), ncol=3,
               frameon=False, fontsize=7.6)
    save(fig, "bhadra-segmentation.png")


def overview(additions, boundary, detail_bounds):
    fig, (ax, hist) = plt.subplots(1, 2, figsize=(7.5, 4.4), gridspec_kw={"width_ratios": [1.06, 1]})
    fig.subplots_adjust(wspace=0.26, bottom=0.13)
    west, south, east, north = boundary.total_bounds
    boundary.plot(ax=ax, color="#f0f2ee", edgecolor="#566473", linewidth=0.7)
    groups = {3: ("Low vegetation", "#476f3c"), 4: ("Bare / sparse ground", "#b66d29")}
    handles = []
    for class_id, (label, color) in groups.items():
        points = additions.loc[additions.vision_class_id == class_id].representative_point()
        ax.scatter(points.x, points.y, s=2.1, c=color, alpha=0.75, lw=0)
        handles.append(Line2D([0], [0], marker="o", linestyle="none", color=color,
                              markersize=4, label=label))
    a, b, c, d = detail_bounds
    ax.add_patch(Rectangle((a, b), c-a, d-b, fill=False, edgecolor=CANDIDATE, linewidth=1.1))
    ax.annotate("Detail window", (c, d), xytext=(7, 5), textcoords="offset points",
                fontsize=7, weight="bold", color=CANDIDATE,
                bbox={"facecolor": "white", "edgecolor": "none", "pad": 1})
    map_frame(ax, (west-1000, south-1000, east+1000, north+1000), "(a) Locations of 2,810 additions", 10000)
    ax.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, -0.19), frameon=False, fontsize=7.2)
    hist.hist(additions.new_site_max_slope_deg, bins=np.arange(0, 13, 1),
              color="#596e90", edgecolor="white", linewidth=0.55)
    hist.axvline(12, color=CANDIDATE, linestyle="--", linewidth=1.2, label="12° screen")
    hist.set(xlabel="Maximum 30 m cell slope (degrees)",
             ylabel="Count", xlim=(0, 12.35), xticks=np.arange(0, 13, 2))
    hist.set_title("(b) Maximum slope by footprint", loc="left", weight="bold", fontsize=9, pad=7)
    hist.legend(loc="upper right", frameon=False, fontsize=7.2)
    hist.spines[["top", "right"]].set_visible(False)
    hist.grid(axis="y", alpha=0.2)
    hist.set_axisbelow(True)
    save(fig, "bhadra-additions.png")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    seeds = gpd.read_file(SEED, layer="candidate_seed")
    additions = seeds.loc[seeds.refinement_origin == "vision_addition"]
    boundary = gpd.read_file(SEED, layer="vision_extent")
    assert len(additions) == 2810 and additions.crs.to_epsg() == 32643
    bounds = candidate_window(additions)
    detail(additions, bounds)
    overview(additions, boundary, bounds)
