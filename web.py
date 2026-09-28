# /// script
# requires-python = ">=3.10"
# dependencies = ["matplotlib", "shapely"]
# ///

"""
Write the same air-quality cells the poster uses, for the 3D page.

    uv run web.py

Then open web/index.html from a local server (file:// cannot load the JSON):

    python -m http.server 8765
"""

import json
from datetime import datetime

import numpy as np

from shapely.geometry import box

from plot import (
    BOUNDS,
    COLOURS,
    DATA_DIR,
    LABELS,
    MAP,
    aqi_path,
    country,
    iter_cells,
    land_mask,
    polygons_of,
    rows,
)

HERE_WEB = DATA_DIR.parent / "web"
CELLS = HERE_WEB / "cells.json"
LAND = HERE_WEB / "land.json"


def band(value):
    """Same bins as the poster: 0–50, 50–100, …, 300 and above."""
    return int(np.digitize([value], BOUNDS[1:-1])[0])


def ring(coords):
    return [[round(float(lon), 4), round(float(lat), 4)] for lon, lat in coords]


def main():
    source = aqi_path()
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
    means = np.where(land_mask(lons, lats, provinces), means, np.nan)
    shown = np.isfinite(means)

    frame = box(73, 17, 136, 54)
    full = country(provinces)
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
    HERE_WEB.mkdir(exist_ok=True)
    CELLS.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    LAND.write_text(json.dumps({"polygons": shapes}, separators=(",", ":")), encoding="utf-8")
    print(f"{len(records)} cells, {len(shapes)} land pieces, on {day}")


if __name__ == "__main__":
    main()
