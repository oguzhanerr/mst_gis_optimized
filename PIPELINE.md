# Production Pipeline Documentation

## Overview

The production pipeline processes radio propagation prediction through 5 phases:

- **Phase 0**: Setup and configuration
- **Phase 1**: Land cover data preparation (Sentinel Hub download)
- **Phase 2**: Batch receiver point generation
- **Phase 3**: Batch data extraction (elevation, land cover, zones) with Optimization A
- **Phase 4**: Formatting and CSV export for P.1812-6 processing

**Key Features:**
- Fully automated end-to-end execution
- Configuration-driven (JSON/YAML)
- Optimization A: 5-8x speedup via pre-loaded raster arrays
- Zone extraction with spatial join + spatial index fallback
- Modular architecture: each phase is independent

## Quick Start

### 1. Run Full Pipeline

```bash
# Use default config
python scripts/run_full_pipeline.py

# With custom config
python scripts/run_full_pipeline.py --config my_config.json

# Skip Phase 1 (land cover download)
python scripts/run_full_pipeline.py --skip-phase1
```

### 2. Run Individual Phases

```bash
# Phase 0: Setup
python scripts/run_phase0_setup.py

# Phase 1: Land cover download
python scripts/run_phase1_dataprep.py --config config.json

# Or access directly in Python
from mst_gis.pipeline.orchestration import PipelineOrchestrator

orchestrator = PipelineOrchestrator(config_path='config.json')
orchestrator.run_phase0_setup()
orchestrator.run_phase1_dataprep()
orchestrator.run_phase2_generation()
orchestrator.run_phase3_extraction()
orchestrator.run_phase4_export()
```

## Configuration

The pipeline is configured via `DEFAULT_CONFIG` in `src/mst_gis/pipeline/config.py` or a custom JSON/YAML file.

### Configuration Structure

```python
{
    "TRANSMITTER": {
        "tx_id": "TX_0001",
        "latitude": 9.345,
        "longitude": -13.40694,
        "antenna_height_tx": 57,  # meters
        "antenna_height_rx": 10,   # meters
    },
    "P1812": {
        "frequency_ghz": 0.9,
        "time_percentage": 50,
        "polarization": 1,  # 1=horizontal, 2=vertical
    },
    "RECEIVER_GENERATION": {
        "max_distance_km": 11.0,
        "distance_step_km": 0.03,
        "num_azimuths": 36,
    },
    "SENTINEL_HUB": {
        "client_id": "...",
        "client_secret": "...",
        # ... other Sentinel Hub config
    },
    "LCM10_TO_CT": {...},  # Land cover code → category mapping
    "CT_TO_R": {...},      # Category → resistance mapping
}
```

## Pipeline Phases

### Phase 0: Setup

Creates directory structure and validates configuration.

**Output:**
- Directory structure in `data/input/`, `data/intermediate/`, `data/output/`

**Python API:**
```python
paths = orchestrator.run_phase0_setup(project_root=None)
```

### Phase 1: Land Cover Data Preparation

Downloads land cover GeoTIFF from Sentinel Hub with caching.

**Requires:**
- Sentinel Hub OAuth credentials in config
- Transmitter location (latitude, longitude)

**Output:**
- Land cover GeoTIFF cached at `data/intermediate/api_data/lcm10_*.tif`

**Python API:**
```python
lc_path = orchestrator.run_phase1_dataprep(landcover_cache_dir=None)
```

### Phase 2: Batch Receiver Point Generation

Generates all receiver points at multiple distances and azimuths around transmitter.

**Uses:**
- Transmitter location and antenna height (from config)
- Distance step and azimuth intervals (from config)

**Output:**
- GeoDataFrame with ~13k points (367 distances × 36 azimuths + 1 TX point)
- Columns: `tx_id`, `rx_id`, `distance_km`, `azimuth_deg`, `geometry`

**Performance:**
- ~5 seconds for 13k points (UTM coordinate transformations)

**Python API:**
```python
receivers_gdf = orchestrator.run_phase2_generation()
```

### Phase 3: Batch Data Extraction

Extracts elevation, land cover codes, and zone data for all points.

**Optimization A:**
- Pre-load raster arrays once (not per-iteration)
- Vectorized spatial joins for zone extraction
- 5-8x speedup vs. per-iteration I/O

**Uses:**
- DEM VRT (automatically found in elevation cache)
- Land cover GeoTIFF (from Phase 1)
- Zone GeoJSON (from reference data)

**Output:**
- Enriched GeoDataFrame with additional columns:
  - `h`: elevation (m)
  - `ct`: land cover code (0-254)
  - `Ct`: land cover category (1-5)
  - `R`: resistance (ohms)
  - `zone`: zone ID (1=Sea, 3=Coastal, 4=Inland)

**Performance:**
- Pre-load: ~4s
- Extraction: ~10-15s for 13k points
- **Total:** ~15-20s (vs. ~170s without optimization)

**Python API:**
```python
enriched_gdf = orchestrator.run_phase3_extraction(dem_path=None)
```

### Phase 4: Formatting and Export

Formats enriched points into P.1812-6 profiles and exports as CSV.

**Workflow:**
- Group points by azimuth
- Create one profile per azimuth (36 profiles)
- Extract distance/height/resistance/zone arrays
- Export as semicolon-delimited CSV

**Output:**
- CSV file: `data/input/profiles/paths_oneTx_manyRx_11km.csv`
- One row per azimuth (36 rows)
- Columns: `f`, `p`, `d`, `h`, `R`, `Ct`, `zone`, `htg`, `hrg`, `pol`, `phi_t`, `phi_r`, `lam_t`, `lam_r`, `azimuth`

**Python API:**
```python
df_profiles, csv_path = orchestrator.run_phase4_export(output_path=None)
```

## Python API

### Full Pipeline Execution

```python
from mst_gis.pipeline.orchestration import run_pipeline

result = run_pipeline(
    config_path='config.json',
    project_root='/path/to/project',
    skip_phase1=False,
)

print(result['csv_path'])  # Output CSV file
print(result['total_time'])  # Total execution time
```

### Individual Phases

```python
from mst_gis.pipeline.orchestration import PipelineOrchestrator

orchestrator = PipelineOrchestrator(config_path='config.json')

# Each phase returns its outputs
paths = orchestrator.run_phase0_setup()
lc_path = orchestrator.run_phase1_dataprep()
receivers_gdf = orchestrator.run_phase2_generation()
enriched_gdf = orchestrator.run_phase3_extraction()
df_profiles, csv_path = orchestrator.run_phase4_export()
```

### Direct Module Usage

```python
from mst_gis.pipeline.point_generation import generate_receiver_grid, Transmitter

transmitter = Transmitter(
    tx_id='TX_0001',
    lon=-13.40694,
    lat=9.345,
    htg=57,
    f=0.9,
    pol=1,
    p=50,
    hrg=10,
)

receivers_gdf = generate_receiver_grid(
    tx=transmitter,
    max_distance_km=11.0,
    distance_step_km=0.03,
    num_azimuths=36,
)
```

## CLI Commands

### Full Pipeline

```bash
python scripts/run_full_pipeline.py [OPTIONS]

Options:
  --config PATH         Config JSON/YAML file
  --project-root PATH   Project root directory
  --skip-phase1         Skip Phase 1 (land cover download)
  --verbose             Print progress (default)
  -h, --help           Show help
```

**Examples:**
```bash
# Use default config
python scripts/run_full_pipeline.py

# Custom config and project root
python scripts/run_full_pipeline.py --config config.json --project-root /data/mst_gis

# Skip land cover download
python scripts/run_full_pipeline.py --skip-phase1
```

### Phase 0: Setup

```bash
python scripts/run_phase0_setup.py [OPTIONS]

Options:
  --config PATH       Config JSON/YAML file
  --project-root PATH Project root directory
  -h, --help         Show help
```

### Phase 1: Data Preparation

```bash
python scripts/run_phase1_dataprep.py [OPTIONS]

Options:
  --config PATH           Config JSON/YAML file (required)
  --cache-dir PATH        Cache directory for GeoTIFF
  --force-download        Force re-download
  -h, --help             Show help
```

## File Structure

```
project_root/
├── data/
│   ├── input/
│   │   ├── profiles/           # Output: CSV profiles
│   │   └── reference/          # Reference data (zones, etc.)
│   ├── intermediate/
│   │   ├── api_data/           # Phase 1: Land cover cache
│   │   └── workflow/           # Intermediate data
│   └── output/
│       └── geojson/            # P.1812 results
├── scripts/
│   ├── run_full_pipeline.py
│   ├── run_phase0_setup.py
│   └── run_phase1_dataprep.py
└── src/mst_gis/
    ├── utils/
    │   ├── logging.py
    │   └── validation.py
    └── pipeline/
        ├── config.py
        ├── data_preparation.py
        ├── point_generation.py
        ├── data_extraction.py
        ├── formatting.py
        └── orchestration.py
```

## Performance

### Timing Breakdown (13k points)

| Phase | Step | Duration |
|-------|------|----------|
| 0 | Setup | <1s |
| 1 | Sentinel Hub download | ~30-60s (network dependent) |
| 2 | Point generation | ~5s |
| 3 | Pre-load rasters | ~4s |
| 3 | Extract elevation | ~0.6s |
| 3 | Extract land cover | ~0.7s |
| 3 | Extract zones | ~1-2s |
| 4 | Format + export | <1s |
| | **Total** | **~40-75s** |

**Optimization A Impact:**
- Without optimization: ~15-20 minutes
- With optimization: ~40-75 seconds
- **Speedup: 12-20x**

## Troubleshooting

### Phase 1: Sentinel Hub Authentication Failed

```
Error: Sentinel Hub API returned 401
```

**Solution:**
- Verify `client_id` and `client_secret` in config
- Check that credentials have access to Sentinel Hub Processing API
- Ensure tokens are not expired

### Phase 3: DEM Not Found

```
Error: DEM not found at /Users/home/.cache/elevation/SRTM1/SRTM1.vrt
```

**Solution:**
- Run Phase 0 setup: `python scripts/run_phase0_setup.py`
- DEM is auto-cached on first use

### Phase 3: Zone Extraction Slow

If zone extraction takes >30s:
- First execution builds spatial index (slower)
- Subsequent executions are cached
- Verify zones GeoJSON is valid

## Next Steps

After pipeline completes:

1. CSV is ready for P.1812-6 batch processing:
   ```bash
   python scripts/run_batch_processor.py data/input/profiles/paths_oneTx_manyRx_11km.csv
   ```

2. Results are output to `data/output/geojson/` as GeoJSON

## References

- **ITU-R P.1812-6**: Radio propagation model
- **Optimization A**: Pre-load raster arrays for batch processing
- **Zone Extraction**: Vectorized spatial join with spatial index fallback
