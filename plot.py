# /// script
# requires-python = ">=3.10"
# dependencies = ["matplotlib"]
# ///

"""
Draw yesterday's China air quality on a real province map.

    uv run plot.py

Each API row is one grid cell and 24 hourly US AQI values. The picture keeps
the mean of those hours, and only the cells that fall inside a province.
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import PatchCollection
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Polygon
from matplotlib.path import Path as MplPath

PICTURE = "plot.png"
HERE = Path(__file__).parent
DATA_DIR = HERE / "data"
MAP = DATA_DIR / "china-provinces.geojson"
OUT = HERE / "out"

BOUNDS = [0, 50, 100, 150, 200, 300, 500]
COLOURS = ["#00e400", "#ffff00", "#ff7e00", "#ff0000", "#8f3f97", "#7e0023"]
LABELS = ["Good", "Moderate", "Sensitive", "Unhealthy", "Very unhealthy", "Hazardous"]


def aqi_path():
    files = sorted(DATA_DIR.glob("open-meteo-china-us-aqi-*.jsonl"))
    if not files:
        raise SystemExit("no air-quality file in data/. Run: uv run fetch.py")
    return files[-1]


def rows(path):
    places = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            places.extend(json.loads(line))
    return places


def rings(geometry):
    """Exterior ring, then holes, for every polygon in this geometry."""
    kind = geometry["type"]
    coords = geometry["coordinates"]
    if kind == "Polygon":
        polygons = [coords]
    elif kind == "MultiPolygon":
        polygons = coords
    else:
        return
    for polygon in polygons:
        if polygon and len(polygon[0]) >= 3:
            yield polygon[0], polygon[1:]


def land_mask(lons, lats, features):
    points = np.column_stack([lons, lats])
    inside = np.zeros(len(points), dtype=bool)
    for feature in features:
        for exterior, holes in rings(feature["geometry"]):
            on_land = MplPath(exterior).contains_points(points)
            for hole in holes:
                if len(hole) >= 3:
                    on_land &= ~MplPath(hole).contains_points(points)
            inside |= on_land
    return inside


def main():
    source = aqi_path()
    table = rows(source)
    provinces = json.loads(MAP.read_text(encoding="utf-8"))["features"]
    print(f"{source.name}: {len(table)} cells. The first one: "
          f"{table[0]['latitude']}, {table[0]['longitude']}")

    day = table[0]["hourly"]["time"][0][:10]
    lats = np.array([place["latitude"] for place in table])
    lons = np.array([place["longitude"] for place in table])
    means = []
    for place in table:
        hours = [value for value in place["hourly"]["us_aqi"] if value is not None]
        means.append(sum(hours) / len(hours) if hours else np.nan)
    means = np.array(means)
    on_land = land_mask(lons, lats, provinces)
    means = np.where(on_land, means, np.nan)

    finite = means[np.isfinite(means)]
    print(f"{finite.size} daily means on land, from {finite.min():.0f} to {finite.max():.0f}, on {day}")

    cmap = ListedColormap(COLOURS)
    norm = BoundaryNorm(BOUNDS, cmap.N, clip=True)
    fig, ax = plt.subplots(figsize=(11, 9))
    ax.set_facecolor("#d5e6f2")

    land = []
    for feature in provinces:
        for exterior, _holes in rings(feature["geometry"]):
            land.append(Polygon(exterior, closed=True))
    ax.add_collection(PatchCollection(
        land, facecolor="#f7f4ee", edgecolor="none", zorder=1,
    ))

    shown = np.isfinite(means)
    points = ax.scatter(
        lons[shown], lats[shown], c=means[shown], cmap=cmap, norm=norm,
        s=28, linewidths=0, zorder=2,
    )
    for feature in provinces:
        for exterior, _holes in rings(feature["geometry"]):
            xs, ys = zip(*exterior)
            ax.plot(xs, ys, color="#2c2c2c", linewidth=0.45, zorder=3)

    ax.set_xlim(73, 136)
    ax.set_ylim(17, 54)
    ax.set_aspect("equal")
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    ax.set_title(f"China air quality, {day} (daily mean of hourly US AQI)")
    bar = fig.colorbar(points, ax=ax, fraction=0.03, pad=0.02, ticks=[25, 75, 125, 175, 250, 400])
    bar.ax.set_yticklabels(LABELS)
    bar.set_label("US AQI")
    fig.tight_layout()

    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT / PICTURE, dpi=150)
    print(f"saved out/{PICTURE}")
    plt.show()


if __name__ == "__main__":
    main()
