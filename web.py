# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "requests", "shapely"]
# ///

"""
Build the land outline and air-quality samples for the 3D page.

    uv run web.py

Then open web/index.html from a local server (file:// cannot load the JSON):

    python -m http.server 8765
"""

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import requests

import fetch
from shapely import contains_xy, make_valid
from shapely.geometry import MultiPoint, Point, box, shape
from shapely.ops import unary_union, voronoi_diagram
from shapely.strtree import STRtree

HERE = Path(__file__).parent
DATA = HERE / "data"
MAP = DATA / "china-provinces.geojson"
WEB = HERE / "web"
CELLS = WEB / "cells.json"
LAND = WEB / "land.json"

BOUNDS = [0, 50, 100, 150, 200, 300, 500]
COLOURS = ["#6f9e99", "#84959b", "#a89878", "#a48474", "#9a727a", "#8d636c"]
LABELS = ["Good", "Moderate", "Sensitive", "Unhealthy", "Very unhealthy", "Hazardous"]


def aqi_path():
    """Yesterday, counted from the day this script is run."""
    path = DATA / fetch.AQI_FILE
    if path.exists():
        return path
    session = requests.Session()
    session.headers["User-Agent"] = "SD5913 PolyU student"
    fetch.fetch_bytes(session, fetch.MAP_URL, DATA / fetch.MAP_FILE)
    return fetch.fetch_aqi(session, path)


def rows(path):
    places = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            places.extend(json.loads(line))
    return places


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


def iter_cells(lons, lats, values, land):
    """One polygon per sample point, clipped to the country."""
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


def band(value):
    return int(np.digitize([value], BOUNDS[1:-1])[0])


def ring(coords):
    return [[round(float(lon), 4), round(float(lat), 4)] for lon, lat in coords]


def main():
    source = aqi_path()
    print(f"using {source.name} for {fetch.DAY}, the day before this run")
    table = rows(source)
    provinces = json.loads(MAP.read_text(encoding="utf-8"))["features"]
    day = table[0]["hourly"]["time"][0][:10]
    lats = np.array([place["latitude"] for place in table])
    lons = np.array([place["longitude"] for place in table])
    means = []
    for place in table:
        hours = [value for value in place["hourly"]["us_aqi"] if value is not None]
        means.append(sum(hours) / len(hours) if hours else np.nan)
    means = np.array(means)

    frame = box(73, 17, 136, 54)
    full = country(provinces)
    means = np.where(contains_xy(full, lons, lats), means, np.nan)
    shown = np.isfinite(means)

    shapes = []
    for piece in polygons_of(full.intersection(frame).simplify(0.04, preserve_topology=True)):
        if piece.is_empty or piece.area < 0.08 or piece.exterior is None:
            continue
        holes = [ring(hole.coords) for hole in piece.interiors if len(hole.coords) >= 4]
        shapes.append([ring(piece.exterior.coords), *holes])

    records = []
    for value, polygon in iter_cells(lons[shown], lats[shown], means[shown], full):
        clipped = polygon.intersection(frame)
        for piece in polygons_of(clipped):
            piece = piece.simplify(0.02, preserve_topology=True)
            if piece.is_empty or piece.exterior is None or len(piece.exterior.coords) < 4:
                continue
            minx, miny, maxx, maxy = piece.bounds
            if piece.area < 0.02 or min(maxx - minx, maxy - miny) < 0.08:
                continue
            holes = [ring(hole.coords) for hole in piece.interiors if len(hole.coords) >= 4]
            records.append({
                "aqi": round(value, 1),
                "band": band(value),
                "rings": [ring(piece.exterior.coords), *holes],
            })

    when = datetime.strptime(day, "%Y-%m-%d")
    payload = {
        "date": day,
        "pretty": f"{when.day} {when.strftime('%B %Y')}",
        "bounds": BOUNDS,
        "colours": COLOURS,
        "labels": LABELS,
        "cells": records,
    }
    WEB.mkdir(exist_ok=True)
    CELLS.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    LAND.write_text(json.dumps({"polygons": shapes}, separators=(",", ":")), encoding="utf-8")
    print(f"{len(records)} cells, {len(shapes)} land pieces, on {day}")


if __name__ == "__main__":
    main()
