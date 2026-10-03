# /// script
# requires-python = ">=3.10"
# ///

"""
Save a still of the 3D page into out/plot.png.

The page has to be served first:

    python -m http.server 8765
    uv run shot.py
"""

import subprocess
from pathlib import Path

EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
OUT = Path(__file__).parent / "out" / "plot.png"
URL = "http://127.0.0.1:8765/web/index.html"


def main():
    if not EDGE.exists():
        raise SystemExit(f"Edge not found at {EDGE}")
    OUT.parent.mkdir(exist_ok=True)
    subprocess.run(
        [
            str(EDGE),
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--force-device-scale-factor=1",
            "--window-size=1600,1000",
            "--virtual-time-budget=25000",
            f"--screenshot={OUT}",
            URL,
        ],
        check=True,
    )
    print(f"saved out/{OUT.name} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
