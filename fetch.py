# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///

"""
Fetch yesterday's US AQI over China, and a province map to draw it on.

    uv run fetch.py

The grid is every 1° inside 18–54°N, 73–135°E. Open-Meteo allows 1000
locations per call and counts each location toward the free limit, so the
calls are batched and paced. Each line of the air-quality file is one raw
HTTP body. The map file is the Aliyun DataV province boundaries, unchanged.
"""

import time
from datetime import date, timedelta
from pathlib import Path

import requests

DAY = (date.today() - timedelta(days=1)).isoformat()
STEP = 1
BATCH = 200
LATS = range(18, 55)
LONS = range(73, 136)

AQI_FILE = f"open-meteo-china-us-aqi-{DAY}.jsonl"
MAP_FILE = "china-provinces.geojson"
MAP_URL = "https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json"
API = "https://air-quality-api.open-meteo.com/v1/air-quality"

HERE = Path(__file__).parent
DATA = HERE / "data"


def grid():
    return [(lat, lon) for lat in LATS for lon in LONS]


def fetch_bytes(session, url, path):
    """Save one raw reply. If path is already in data/, do nothing."""
    if path.exists():
        print(f"data/{path.name} is already here ({path.stat().st_size // 1024} KB). "
              "Delete it to fetch again.")
        return path
    DATA.mkdir(exist_ok=True)
    print(f"asking {url}")
    reply = session.get(url, timeout=120)
    reply.raise_for_status()
    path.write_bytes(reply.content)
    print(f"saved data/{path.name} ({path.stat().st_size // 1024} KB)")
    return path


def fetch_batch(session, points):
    url = (
        f"{API}?latitude={','.join(str(lat) for lat, _ in points)}"
        f"&longitude={','.join(str(lon) for _, lon in points)}"
        f"&hourly=us_aqi&domains=cams_global"
        f"&start_date={DAY}&end_date={DAY}"
        "&cell_selection=nearest&timezone=GMT"
    )
    for attempt in range(4):
        reply = session.get(url, timeout=120)
        if reply.status_code == 429 and attempt < 3:
            time.sleep(60 * (attempt + 1))
            continue
        reply.raise_for_status()
        return reply.content
    raise RuntimeError("rate limited")


def fetch_aqi(session, path):
    if path.exists():
        print(f"data/{path.name} is already here ({path.stat().st_size // 1024} KB). "
              "Delete it to fetch again.")
        return path

    points = grid()
    DATA.mkdir(exist_ok=True)
    partial = path.with_suffix(".partial")
    done = 0
    if partial.exists():
        done = min(sum(1 for line in partial.open("rb") if line.strip()) * BATCH, len(points))
        print(f"resuming at {done}")

    print(f"asking Open-Meteo for {DAY}: {len(points)} locations over China")
    with partial.open("ab") as handle:
        for start in range(done, len(points), BATCH):
            if start > done:
                time.sleep(25)
            body = fetch_batch(session, points[start:start + BATCH])
            handle.write(body.replace(b"\n", b""))
            handle.write(b"\n")
            print(f"  {min(start + BATCH, len(points))}/{len(points)}")

    partial.replace(path)
    print(f"saved data/{path.name} ({path.stat().st_size // 1024} KB). Now: git add data")
    return path


if __name__ == "__main__":
    session = requests.Session()
    session.headers["User-Agent"] = "SD5913 PolyU student"
    fetch_bytes(session, MAP_URL, DATA / MAP_FILE)
    fetch_aqi(session, DATA / AQI_FILE)
