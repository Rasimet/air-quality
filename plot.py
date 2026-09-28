# /// script
# requires-python = ">=3.10"
# dependencies = ["matplotlib", "shapely"]
# ///

"""
Draw yesterday's China air quality on a real province map.

    uv run plot.py

Each API row is one grid cell and 24 hourly US AQI values. The picture keeps
the mean of those hours. Neighbouring cells share an edge and stop at the
provincial outline.
"""

import json
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import PatchCollection
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MplPath
from shapely import make_valid
from shapely.geometry import MultiPoint, Point, shape
from shapely.ops import unary_union, voronoi_diagram
from shapely.strtree import STRtree

PAPER = "#f3efe6"
INK = "#1c1915"
MUTED = "#6d665e"
LINE = "#3f3a34"

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


def country(features):
    """One shape for every province, including islands."""
    parts = []
    for feature in features:
        geom = make_valid(shape(feature["geometry"]))
        if not geom.is_empty:
            parts.append(geom)
    return unary_union(parts)


def polygons_of(geom):
    if geom.is_empty:
        return
    if geom.geom_type == "Polygon":
        yield geom
    elif geom.geom_type == "MultiPolygon":
        yield from geom.geoms
    elif geom.geom_type == "GeometryCollection":
        for piece in geom.geoms:
            yield from polygons_of(piece)


def path_of(polygon):
    """Exterior ring plus holes, so a cell can be clipped by a coastline."""
    vertices = []
    codes = []
    rings = [polygon.exterior, *polygon.interiors]
    for ring in rings:
        coords = np.asarray(ring.coords)
        if len(coords) < 3:
            continue
        vertices.append(coords)
        code = np.full(len(coords), MplPath.LINETO)
        code[0] = MplPath.MOVETO
        codes.append(code)
    return MplPath(np.vstack(vertices), np.concatenate(codes))


def iter_cells(lons, lats, values, land):
    """Voronoi cells of the sample points, cut so they stay inside the map.

    A regular degree grid would tile into rectangles. Nudging each point by a
    fixed offset makes the shared edges irregular without moving the colour.
    """
    rng = np.random.default_rng(7)
    sites = np.column_stack([
        lons + rng.uniform(-0.42, 0.42, len(lons)),
        lats + rng.uniform(-0.42, 0.42, len(lats)),
    ])
    diagram = voronoi_diagram(MultiPoint(sites), envelope=land)
    regions = list(diagram.geoms)
    tree = STRtree(regions)
    for site_lon, site_lat, value in zip(sites[:, 0], sites[:, 1], values):
        hits = tree.query(Point(site_lon, site_lat), predicate="intersects")
        if len(hits) == 0:
            continue
        clipped = regions[int(np.atleast_1d(hits)[0])].intersection(land)
        for polygon in polygons_of(clipped):
            if polygon.area < 1e-4:
                continue
            yield float(value), polygon


def cells(lons, lats, values, land, cmap, norm):
    patches = []
    colours = []
    for value, polygon in iter_cells(lons, lats, values, land):
        rgba = cmap(norm(value))
        # A same-colour edge closes the hairline cracks between neighbours.
        patches.append(PathPatch(path_of(polygon), facecolor=rgba, edgecolor=rgba, linewidth=0.6))
        colours.append(value)
    return patches, np.array(colours)


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

    when = datetime.strptime(day, "%Y-%m-%d")
    pretty = f"{when.day} {when.strftime('%B %Y')}"
    worst = int(round(finite.max()))
    counts = np.bincount(np.digitize(finite, BOUNDS[1:-1]), minlength=len(LABELS))

    cmap = ListedColormap(COLOURS)
    norm = BoundaryNorm(BOUNDS, cmap.N, clip=True)
    fig = plt.figure(figsize=(11.2, 15.4), facecolor=PAPER)

    fig.text(0.08, 0.955, "OPEN-METEO   ·   CAMS GLOBAL", fontsize=10,
             color=MUTED, fontfamily="Segoe UI")
    fig.text(0.08, 0.905, "Air over China", fontsize=46, color=INK, fontfamily="Georgia")
    fig.text(0.08, 0.868, pretty, fontsize=18, color=INK, fontfamily="Georgia", fontstyle="italic")
    fig.text(0.08, 0.832,
             "Neighbouring cells share an edge and stop at the provincial outline.\n"
             f"Colour is the mean of 24 hourly US AQI values. The highest was {worst}.",
             fontsize=12, color=MUTED, fontfamily="Segoe UI", linespacing=1.45)
    fig.add_artist(plt.Line2D([0.08, 0.34], [0.808, 0.808], transform=fig.transFigure,
                              color=INK, linewidth=1.0))

    ax = fig.add_axes([0.06, 0.18, 0.88, 0.60])
    ax.set_facecolor(PAPER)
    shown = np.isfinite(means)
    land = country(provinces)
    patches, _cell_values = cells(lons[shown], lats[shown], means[shown], land, cmap, norm)
    ax.add_collection(PatchCollection(patches, match_original=True, zorder=2))
    for feature in provinces:
        for exterior, _holes in rings(feature["geometry"]):
            xs, ys = zip(*exterior)
            ax.plot(xs, ys, color=LINE, linewidth=0.45, zorder=3, solid_capstyle="round")

    ax.set_xlim(73, 136)
    ax.set_ylim(17, 54)
    # One degree of longitude is shorter than one degree of latitude, so equal
    # degrees make the country look squashed. Stretch latitude to ground scale.
    ax.set_aspect(1 / np.cos(np.deg2rad(35)))
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.text(73.4, 17.55, "73°E", fontsize=8, color=MUTED, fontfamily="Segoe UI")
    ax.text(132.2, 17.55, "135°E", fontsize=8, color=MUTED, fontfamily="Segoe UI", ha="right")
    ax.text(73.4, 53.15, "54°N", fontsize=8, color=MUTED, fontfamily="Segoe UI")

    legend = fig.add_axes([0.08, 0.075, 0.84, 0.09])
    legend.set_xlim(0, len(LABELS))
    legend.set_ylim(0, 1)
    legend.axis("off")
    for i, (colour, label, count) in enumerate(zip(COLOURS, LABELS, counts)):
        legend.scatter([i + 0.18], [0.72], s=120, c=colour, linewidths=0.4,
                       edgecolors=INK, zorder=2)
        legend.text(i + 0.38, 0.72, label, va="center", ha="left", fontsize=9.5,
                    color=INK, fontfamily="Segoe UI")
        legend.text(i + 0.38, 0.34, f"{int(count)} places", va="center", ha="left",
                    fontsize=8.5, color=MUTED, fontfamily="Segoe UI")

    fig.text(0.08, 0.042,
             "US EPA breakpoints. Provincial boundaries from Aliyun DataV. "
             "Hours inside the day are averaged away.",
             fontsize=9, color=MUTED, fontfamily="Segoe UI")

    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT / PICTURE, dpi=180, facecolor=fig.get_facecolor())
    print(f"saved out/{PICTURE}")
    plt.show()


if __name__ == "__main__":
    main()
