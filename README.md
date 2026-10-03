# Air Over China

![Yesterday's US air quality over China, drawn as one solid map]out/plot.png

## The phenomenon

Air quality over China changes from hour to hour and from place to place. The number used here is the United States Air Quality Index, a single score that takes the worst of several pollutants. A low score is easier to breathe; a high score means the air is unhealthy. I looked at it because the same country can be clean in one province and poor in another on the same day, and a map shows that contrast more clearly than a list of cities.

## The source

The numbers come from the [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api), using the global CAMS model: `https://air-quality-api.open-meteo.com/v1/air-quality`. The script asks for the day before it is run. It requests hourly `us_aqi` on a 1° grid from 18°N to 54°N and 73°E to 135°E, 2331 locations in all. The saved file is `data/open-meteo-china-us-aqi-YYYY-MM-DD.jsonl`. Each line is one raw API reply. Each location in that reply is one grid point and 24 hourly index values. The unit of `us_aqi` is the US AQI. Provincial outlines come from the [Aliyun DataV China map](https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json), saved as `data/china-provinces.geojson`.

## What the picture shows

The still in `out/plot.png` is the same view as the page: one solid map of China, coloured by yesterday's air, with provincial borders drawn on top. Green-grey is cleaner air and the warmer brown is worse air, often over the north and east. The picture keeps only the mean of the 24 hours, so the rise and fall inside the day is gone. Neighbouring grid points are blended into one continuous surface, so the original 1° blocks and their hard edges are gone too. Points over the sea, and pieces of land too small to keep, are left out.

## Run it

Build yesterday’s air-quality data for the page. “Yesterday” is the day before you run the command. If that file is already in `data/`, it is reused.

```
uv run web.py
```

Serve the page, then open http://127.0.0.1:8765/web/index.html . Drag the map to turn it. After another `uv run web.py`, refresh the page.

```
python -m http.server 8765
```

Save a still of that page to `out/plot.png`. The server has to be running, and the map needs a few seconds to appear.

```
uv run shot.py
```
