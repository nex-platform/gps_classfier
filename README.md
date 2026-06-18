# GPS region classifier

Real-time simulation that classifies a moving 2D GPS-like sensor as
**In A**, **In B**, or **Outside**, based on signed-distance-to-boundary
readings from two configurable, disjoint regions.

## Features

- **Configurable regions**: region A / B shapes (circle, ellipse, polygon)
  and sizes are defined declaratively in `region_config.py` or an external
  JSON file - no logic changes needed to reshape/resize/move a region.
- **Exact geometry via Shapely**: signed distances (negative = inside,
  positive = outside, zero = on boundary) computed with `shapely`, correct
  for circles, ellipses, convex and concave polygons.
- **Realistic motion**: variable speed (sinusoidal drift + jitter) and
  gently-varying heading - not constant velocity.
- **Real-time, no post-processing**: each tick computes position -> sensor
  reads -> classification -> display, and the result is emitted
  immediately.
- **Configurable logging**: set verbosity via `--log-level` or the
  `GPS_SIM_LOG_LEVEL` environment variable.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate         # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .                  # installs the gps-classifier CLI command
```

## Running the simulation

```bash
# Default: INFO-level console output, 60s simulated duration
python -m gps_classifier.main

# Verbose internals (per-tick speed, heading, raw distances)
python -m gps_classifier.main --log-level DEBUG

# Only warnings/errors (e.g. region overlap, speed clipping)
python -m gps_classifier.main --log-level WARNING

# Set the log level via environment variable instead
GPS_SIM_LOG_LEVEL=DEBUG python -m gps_classifier.main

# Custom regions from a JSON file
python -m gps_classifier.main --config configs/regions.example.json

# Live matplotlib visualization alongside console output
python -m gps_classifier.main --plot

# Run as fast as possible (no wall-clock pacing) - useful for testing
python -m gps_classifier.main --no-realtime --duration 5
```

### CLI options

| Flag | Default | Description |
|---|---|---|
| `--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}` | env `GPS_SIM_LOG_LEVEL` or `INFO` | Logging verbosity |
| `--duration <seconds>` | `60` | Total simulated time |
| `--dt <seconds>` | `0.1` | Tick size |
| `--realtime` / `--no-realtime` | `--realtime` | Pace ticks to wall-clock time |
| `--plot` | off | Show live matplotlib view (requires `matplotlib`) |
| `--config <path>` | none | JSON file defining region A / B |
| `--seed <int>` | `42` | Override motion RNG seed |

## Log levels

| Level | Contents |
|---|---|
| `DEBUG` | Per-tick internals: speed, heading, raw signed-distance computations, individual sensor reads |
| `INFO` | Per-tick summary: `t`, position, `dist_a`, `dist_b`, classification |
| `WARNING` | Anomalies: speed clipped to minimum, region overlap detected, geometry auto-repaired |
| `ERROR` | Unrecoverable configuration errors (bad shape type, invalid geometry, malformed config file) |

## Configuring regions

Edit `src/gps_classifier/region_config.py`'s `default_regions()`, or supply
`--config path/to/regions.json` with this shape:

```json
{
  "region_a": {"shape": "circle", "center": [0, 0], "radius": 5},
  "region_b": {"shape": "polygon", "vertices": [[10,0],[20,0],[20,8],[14,12],[10,8]]}
}
```

Supported `shape` values: `circle` (`center`, `radius`), `ellipse`
(`center`, `radii: [rx, ry]`), `polygon` (`vertices: [[x,y], ...]`, >= 3
points).

## Project layout

```
src/gps_classifier/
    region_config.py   # RegionConfig + shape definitions (shapely-backed)
    geometry.py         # signed_distance() via shapely
    motion.py            # MotionSimulator (variable-speed path)
    sensors.py           # SensorModule.get_dist_a() / get_dist_b()
    classifier.py        # classify() -> In A / In B / Outside
    display.py           # ConsoleDisplay / LivePlotDisplay
    logging_config.py    # configurable log levels
    main.py               # CLI entry point / real-time loop
tests/                   # pytest unit + integration tests
configs/regions.example.json
```

## Running tests

```bash
pytest
```

```
gps_region_classifier
├─ configs
│  └─ regions.example.json
├─ docs 
│  ─ System_Design_Document_Template.docx
├─ README.md
├─ requirements.txt
├─ setup.py
├─ src
│  ├─ gps_classifier
│  │  ├─ classifier.py
│  │  ├─ display.py
│  │  ├─ geometry.py
│  │  ├─ logging_config.py
│  │  ├─ main.py
│  │  ├─ motion.py
│  │  ├─ region_config.py
│  │  ├─ sensors.py
│  │  ├─ __init__.py
└─ tests
   ├─ test_classifier.py
   ├─ test_geometry.py
   ├─ test_integration.py
   ├─ test_motion.py  

```