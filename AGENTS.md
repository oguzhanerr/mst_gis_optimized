# AGENTS.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

This project implements radio propagation prediction using ITU-R P.1812-6 for point-to-area terrestrial services (30 MHz to 6 GHz). It processes terrain path profiles to calculate basic transmission loss and electric field strength, outputting results as GeoJSON for GIS visualization.

## Build & Run Commands

```bash
# Create/activate virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Py1812 from local source (required)
pip install -e ./github_Py1812/Py1812

# Run main batch processor (processes profiles from data/input/profiles/, outputs to data/output/geojson/)
python scripts/run_batch_processor.py

# Generate uniformly distributed receiver points using phyllotaxis pattern
python scripts/generate_receiver_points.py <lat> <lon> <num_points> --scale <meters> --geojson --output <file>
```

## Elevation Data

**CRITICAL**: As of this update, elevation extraction uses **SRTM.py** (replaces old `elevation` library) for proper nodata handling. 

**Phase 0** now:
1. Downloads SRTM1 30m HGT tile for your area (~30-45 sec)
2. Caches to: `data/intermediate/elevation_cache/N09W014.hgt`
3. Pre-loads tile into memory as array for fast Phase 3 access

**Phase 3** uses the pre-loaded array directly (no additional downloads). Elevation values are filtered to [0, 9000] meters (configurable via `srtm_min_elev`, `srtm_max_elev` in `profile_extraction.py`).

## Validation

```bash
# Run P1812 validation tests (requires validation_profiles/ data)
cd github_Py1812/Py1812/tests
python validateP1812.py
```

## Architecture

### Directory Structure
```
.
├── src/mst_gis/              # Main source code
│   ├── propagation/          # P1812 propagation logic
│   │   ├── profile_parser.py    (load/parse profiles)
│   │   ├── batch_processor.py   (main workflow)
│   │   └── point_generator.py   (phyllotaxis generation)
│   └── gis/                  # GeoJSON generation
│       └── geojson_builder.py   (GeoJSON helpers)
├── data/
│   ├── input/                # Input data
│   │   ├── profiles/            (terrain profiles)
│   │   └── reference/           (static data)
│   ├── intermediate/         # Regenerable intermediate data
│   │   ├── api_data/            (cached Sentinel Hub TIFs)
│   │   └── workflow/            (generated during processing)
│   ├── output/               # Final outputs
│   │   ├── geojson/             (P1812 results)
│   │   └── spreadsheets/        (CSV/Excel)
│   └── notebooks/            # Jupyter notebooks
├── scripts/                  # Entry point scripts
│   ├── run_batch_processor.py
│   └── generate_receiver_points.py
├── tests/                    # Unit tests
└── docs/                     # Documentation
```

### Data Flow
```
data/input/profiles/*.csv → scripts/run_batch_processor.py → Py1812.bt_loss() → data/output/geojson/*.geojson
```

### Key Components

- **`scripts/run_batch_processor.py`** - Entry point. Reads semicolon-delimited CSV profiles from `data/input/profiles/`, calls P1812 propagation model, outputs GeoJSON files to `data/output/geojson/`

- **`src/mst_gis/propagation/batch_processor.py`** - Core batch processing logic with smart path handling

- **`src/mst_gis/propagation/profile_parser.py`** - CSV profile parsing and loss parameter processing

- **`src/mst_gis/propagation/point_generator.py`** - Generates uniformly distributed receiver points using golden-angle phyllotaxis pattern

- **`src/mst_gis/gis/geojson_builder.py`** - GeoJSON FeatureCollection generation for transmitter/receiver points, link lines, and coverage polygons

- **`github_Py1812/Py1812/src/Py1812/P1812.py`** - Core propagation model implementing ITU-R P.1812-6. Main function is `bt_loss()` which returns:
  - `Lb`: Basic transmission loss (dB)
  - `Ep`: Electric field strength (dBμV/m)

### Profile CSV Format (semicolon-separated)
Columns: frequency, time_percentage, distances[], heights[], R[], Ct[], zone[], htg, hrg, pol, tx_lat, rx_lat, tx_lon, rx_lon

### Output GeoJSON Files
- `points_<dist>_<timestamp>.geojson` - Transmitter and receiver points with loss/field strength properties
- `lines_<dist>_<timestamp>.geojson` - TX→RX link lines
- `polygon_<dist>_<timestamp>.geojson` - Coverage area polygon

## ITU Digital Maps Setup

The Py1812 library requires ITU digital products (not redistributable). Before first use:

1. Download `DN50.TXT` and `N050.TXT` from ITU-R P.1812 recommendation
2. Place in `github_Py1812/Py1812/src/Py1812/maps/`
3. Run: `python github_Py1812/Py1812/src/Py1812/initiate_digital_maps.py`
4. This generates `P1812.npz` required by the model

## P1812.bt_loss() Key Parameters

| Parameter | Description |
|-----------|-------------|
| `f` | Frequency (GHz), 0.03-6 |
| `p` | Time percentage (%), 1-50 |
| `d` | Distance profile array (km) |
| `h` | Height profile array (m asl) |
| `htg/hrg` | TX/RX antenna height above ground (m) |
| `pol` | Polarization: 1=horizontal, 2=vertical |
| `zone` | Radio-climatic zones: 1=Sea, 3=Coastal, 4=Inland |
