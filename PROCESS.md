# Process

## Tools

Cursor’s agent wrote most of the scripts and the page. I used it to call the Open-Meteo Air Quality API, to clip the samples to China with Shapely, and to draw the map in Three.js. The provincial outlines are the Aliyun DataV China GeoJSON. Microsoft Edge, run headless, saved the still in `out/plot.png`. `uv` ran the Python scripts.

## Kept

The daily mean of the 24 hourly US AQI values. The map can show only one number per place, and the mean is that number: it uses every hour instead of picking a single clock time.

## Rejected

A separate 3D block for every grid cell. The blocks met at hard edges, so the country looked cut apart and cracked. One land shape, with the colour blended across neighbouring points, replaced them.
