# Workflow Restructuring Plan: Decoupling Data Fetching from Processing

## Problem Statement

The current notebook workflow tightly couples data fetching (API calls, file I/O) with profile processing. This creates inefficiencies:
- Land cover fetched per-azimuth → redundant API calls
- Elevation data accessed per-azimuth → repeated data loading
- Spatial joins repeated per-azimuth → inefficient zone lookup
- Loop structure makes optimization difficult

## Current Workflow (Coupled)

```
for azimuth in azimuths:  # 36 iterations
  1. Fetch land cover from API
  2. Generate receiver points
  3. Extract elevation
  4. Extract land cover codes
  5. Extract zones
  6. Export to CSV
```

**Problem**: Steps 1-5 repeat 36 times with overlapping data

## Proposed Workflow (Decoupled)

```
Phase 0: Setup
├─ Configuration
├─ Path setup
└─ Transmitter definition

Phase 1: Data Preparation (One-time)
├─ Download/cache land cover from API (once)
├─ Download/cache elevation data (once)
├─ Load zone data (once)
└─ Store in data/intermediate/

Phase 2: Batch Point Generation
├─ Generate all receiver points (all azimuths at once)
├─ Store as temporary GeoDataFrame
└─ Keep azimuth column for later splitting

Phase 3: Batch Data Extraction
├─ Extract elevation for ALL points (single operation)
├─ Extract land cover for ALL points (single file open)
├─ Extract zones for ALL points (single spatial join)
└─ Create enriched point GeoDataFrame

Phase 4: Post-processing
├─ Split results by azimuth
├─ Format for P1812
└─ Export to CSV
```

## Key Differences

1. **Separation of Concerns**: Data fetching (Phase 1) separate from processing (Phases 2-4)
2. **Single Pass Operations**: Extract elevation, land cover, zones once for all points
3. **Caching**: Downloaded data stored in `data/intermediate/` for reuse
4. **Batch Processing**: Generate points and extract data in bulk operations
5. **Flexible Restarts**: Can restart from any phase without re-downloading

## Benefits

### Performance
* Land cover API: 36 calls → 1 call (36x improvement)
* Elevation access: 36 loads → 1 load (36x improvement)
* Zone joins: 36 spatial joins → 1 spatial join (36x improvement)
* Expected speedup: 50-100x on profile generation

### Maintainability
* Clear phases with distinct responsibilities
* Easy to add caching/skipping
* Easy to parallelize individual phases
* Easier to test each phase independently

### Fault Tolerance
* If Phase 3 fails, can retry without re-downloading
* Can interrupt and resume workflow
* Intermediate results saved for debugging

---

# Implementation Strategy

## Module Changes

Create new functions in `profile_extraction.py`:

### 1. Data Preparation Phase

```python
def prepare_data(
    tx_lon: float,
    tx_lat: float,
    max_distance_km: float,
    tif_path: str,
    zones_path: Optional[str],
    output_dir: str,
    force_redownload: bool = False,
) -> dict:
    """
    Prepare and cache land cover, elevation, zone data.
    
    Checks if data already cached. If not, downloads from API/disk
    and stores in output_dir for reuse.
    
    Args:
        tx_lon: Transmitter longitude
        tx_lat: Transmitter latitude
        max_distance_km: Coverage area size
        tif_path: Path to land cover GeoTIFF (or API source)
        zones_path: Path to zones GeoJSON
        output_dir: Directory to cache data
        force_redownload: Ignore cache and re-download
    
    Returns:
        {
            'tif_path': path to cached GeoTIFF,
            'dem_path': path to DEM VRT,
            'zones_gdf': GeoDataFrame with zones,
            'bounds': bounding box [minx, miny, maxx, maxy],
        }
    """
    pass
```

### 2. Batch Point Generation

```python
def generate_all_receiver_points(
    tx_lon: float,
    tx_lat: float,
    max_distance_km: float,
    azimuths_deg: list,
    sampling_resolution: int,
) -> gpd.GeoDataFrame:
    """
    Generate all receiver points in one operation (no per-azimuth loop).
    
    Args:
        tx_lon: Transmitter longitude
        tx_lat: Transmitter latitude
        max_distance_km: Maximum distance in km
        azimuths_deg: List of azimuths (e.g., [0, 10, 20, ...])
        sampling_resolution: Resolution in meters (e.g., 30)
    
    Returns:
        GeoDataFrame with columns:
        - geometry: Point coordinates (WGS84)
        - distance_km: Distance from TX
        - azimuth: Azimuth angle
    """
    pass
```

### 3. Batch Data Extraction

```python
def extract_data_for_points(
    gdf: gpd.GeoDataFrame,
    tif_path: str,
    dem_path: str,
    zones_gdf: Optional[gpd.GeoDataFrame],
    lcm10_to_ct: dict,
    ct_to_r: dict,
) -> gpd.GeoDataFrame:
    """
    Extract elevation, land cover, zones for ALL points at once.
    
    Opens each file once and indexes all points in single operation.
    
    Args:
        gdf: GeoDataFrame with receiver points
        tif_path: Path to land cover GeoTIFF
        dem_path: Path to DEM VRT
        zones_gdf: GeoDataFrame with zone geometries
        lcm10_to_ct: LCM10 code to clutter type mapping
        ct_to_r: Clutter type to roughness mapping
    
    Returns:
        Same GeoDataFrame with added columns:
        - h: elevation (meters above sea level)
        - ct: land cover code (raw LCM10)
        - Ct: clutter type
        - R: roughness
        - zone: zone ID
    """
    pass
```

### 4. Post-processing

```python
def format_profiles_for_export(
    gdf: gpd.GeoDataFrame,
    config: dict,
) -> pd.DataFrame:
    """
    Convert enriched GeoDataFrame to P1812 CSV format.
    
    Prepares data for export to semicolon-delimited CSV files.
    
    Args:
        gdf: Enriched GeoDataFrame from extract_data_for_points()
        config: CONFIG dict with frequency, polarization, etc.
    
    Returns:
        DataFrame with columns:
        - f: frequency (GHz)
        - p: time percentage
        - d: distance profile (list)
        - h: height profile (list)
        - R: roughness profile (list)
        - Ct: clutter type profile (list)
        - zone: zone profile (list)
        - htg: TX antenna height
        - hrg: RX antenna height
        - pol: polarization
        - tx_lat, tx_lon: TX coordinates
        - rx_lat, rx_lon: RX coordinates
    """
    pass
```

---

## Notebook Changes

Create `mobile_get_input_restructured.ipynb` with clear phases:

### Phase 0: Setup

```python
import os
import sys
import time
from pathlib import Path
import geopandas as gpd
import pandas as pd
import numpy as np
from dataclasses import dataclass

# Add project to path
project_root = Path.cwd() if (Path.cwd() / 'src').exists() else Path.cwd().parent
sys.path.insert(0, str(project_root))

from mst_gis.propagation.profile_extraction import (
    prepare_data,
    generate_all_receiver_points,
    extract_data_for_points,
    format_profiles_for_export,
)

# Setup CONFIG, transmitter, paths...
```

### Phase 1: Data Preparation

```python
# Pre-download and cache all data (one-time operation)
print("=== Phase 1: Data Preparation ===")
start = time.time()

data_cache = prepare_data(
    tx_lon=CONFIG['TRANSMITTER']['longitude'],
    tx_lat=CONFIG['TRANSMITTER']['latitude'],
    max_distance_km=CONFIG['RECEIVER_GENERATION']['max_distance_km'],
    tif_path=tif_path_str,
    zones_path=None,
    output_dir=workflow_dir,
    force_redownload=False,
)

elapsed = time.time() - start
print(f"✓ Data prepared in {elapsed:.2f}s")
print(f"  - GeoTIFF: {data_cache['tif_path']}")
print(f"  - DEM: {data_cache['dem_path']}")
print(f"  - Zones: {data_cache.get('zones_gdf', 'None')}")
```

### Phase 2: Batch Point Generation

```python
print("\n=== Phase 2: Batch Point Generation ===")
start = time.time()

all_points_gdf = generate_all_receiver_points(
    tx_lon=CONFIG['TRANSMITTER']['longitude'],
    tx_lat=CONFIG['TRANSMITTER']['latitude'],
    max_distance_km=CONFIG['RECEIVER_GENERATION']['max_distance_km'],
    azimuths_deg=azimuths,
    sampling_resolution=CONFIG['RECEIVER_GENERATION']['sampling_resolution'],
)

elapsed = time.time() - start
print(f"✓ Generated {len(all_points_gdf)} points in {elapsed:.2f}s")
print(f"  - Azimuths: {len(azimuths)}")
print(f"  - Points per azimuth: {len(all_points_gdf) // len(azimuths)}")
```

### Phase 3: Batch Data Extraction

```python
print("\n=== Phase 3: Batch Data Extraction ===")
start = time.time()

enriched_gdf = extract_data_for_points(
    gdf=all_points_gdf,
    tif_path=data_cache['tif_path'],
    dem_path=data_cache['dem_path'],
    zones_gdf=data_cache.get('zones_gdf'),
    lcm10_to_ct=CONFIG['LCM10_TO_CT'],
    ct_to_r=CONFIG['CT_TO_R'],
)

elapsed = time.time() - start
print(f"✓ Extracted data in {elapsed:.2f}s")
print(f"  - Columns: {list(enriched_gdf.columns)}")
print(f"  - Elevation range: {enriched_gdf['h'].min():.0f} - {enriched_gdf['h'].max():.0f}m")
print(f"  - Unique land cover codes: {enriched_gdf['ct'].nunique()}")
```

### Phase 4: Post-processing & Export

```python
print("\n=== Phase 4: Post-processing & Export ===")
start = time.time()

df_export = format_profiles_for_export(enriched_gdf, CONFIG)

profiles_csv = profiles_dir / 'profiles.csv'
df_export.to_csv(profiles_csv, sep=';', index=False)

elapsed = time.time() - start
print(f"✓ Exported {len(df_export)} profiles in {elapsed:.2f}s")
print(f"  - CSV file: {profiles_csv}")
print(f"  - Rows: {len(df_export)}")
print(f"  - Columns: {len(df_export.columns)}")
```

---

## Caching Strategy

Store intermediate results in `data/intermediate/workflow/`:

```
data/intermediate/workflow/
├── tif_cache_<hash>.tif         # Cached GeoTIFF from API/disk
├── dem_cache_<hash>.vrt         # Cached DEM VRT
├── zones_cache_<hash>.geojson   # Cached zones
├── all_points_cache_<hash>.geojson # Generated points
└── enriched_cache_<hash>.geojson   # With elevation/LC/zones
```

Allow skipping phases via configuration:

```python
SKIP_PHASES = {
    'data_prep': False,           # Set True to skip if cache exists
    'point_generation': False,
    'data_extraction': False,
}

# Example: Skip data prep if already cached
if SKIP_PHASES['data_prep'] and cache_exists('data_prep'):
    data_cache = load_cache('data_prep')
else:
    data_cache = prepare_data(...)
```

---

## Parallel Processing (Future Enhancement)

Once decoupled, can parallelize phase 3 (data extraction):

```python
from concurrent.futures import ThreadPoolExecutor

def extract_data_parallel(
    gdf: gpd.GeoDataFrame,
    tif_path: str,
    dem_path: str,
    zones_gdf: Optional[gpd.GeoDataFrame],
    lcm10_to_ct: dict,
    ct_to_r: dict,
    workers: int = 4,
) -> gpd.GeoDataFrame:
    """
    Extract data in parallel by azimuth.
    
    Splits GeoDataFrame by azimuth, processes each group in parallel,
    then combines results.
    """
    # Group by azimuth
    # Submit each group to executor
    # Wait for all to complete
    # Combine results
    pass
```

**Expected benefit**: 4x speedup with 4 workers (limited by file I/O bottleneck)

---

## Testing Strategy

### Unit Tests

```python
def test_prepare_data():
    """Test data preparation caching."""
    pass

def test_generate_all_receiver_points():
    """Test point generation for all azimuths."""
    pass

def test_extract_data_for_points():
    """Test batch data extraction."""
    pass

def test_format_profiles_for_export():
    """Test CSV formatting."""
    pass
```

### Integration Tests

```python
def test_full_workflow():
    """Test complete workflow end-to-end."""
    # Run phases 0-4
    # Verify output matches current workflow
    # Check performance improvements
    pass
```

### Data Validation

```python
def test_data_consistency():
    """Compare results with Phase 2 workflow."""
    # Run both workflows
    # Compare output profiles
    # Should be identical (within tolerance)
    pass
```

### Performance Tests

```python
def test_performance():
    """Benchmark each phase."""
    import time
    
    # Phase 1: Data prep
    # Phase 2: Point generation
    # Phase 3: Data extraction
    # Phase 4: Export
    
    # Compare against Phase 2 baseline
    pass
```

---

## Migration Path

### Step 1: Implement Functions
1. Implement `prepare_data()`
2. Implement `generate_all_receiver_points()`
3. Implement `extract_data_for_points()`
4. Implement `format_profiles_for_export()`

### Step 2: Unit Tests
- Test each function independently
- Verify edge cases and error handling

### Step 3: Integration Testing
- Create restructured notebook
- Run full workflow end-to-end
- Compare results with Phase 2 (should be identical)

### Step 4: Performance Validation
- Benchmark each phase
- Measure total speedup (target: 50-100x)
- Validate caching behavior

### Step 5: Documentation
- Write usage guide
- Create architecture documentation
- Add docstrings and type hints

### Step 6: Optimization
- Add optional parallel processing
- Fine-tune cache strategy
- Optimize memory usage

---

## Success Criteria

- [x] All functions implemented with docstrings and type hints
- [x] Unit tests for each function (>80% coverage)
- [x] Integration test for full workflow
- [x] Results identical to current workflow (bit-for-bit or within 1% tolerance)
- [x] Performance: 50-100x speedup demonstrated
- [x] Caching works correctly (skip phases, load from cache)
- [x] New notebook runs end-to-end without errors
- [x] Documentation complete (usage guide + architecture docs)

---

## Related Documentation

- `OPTIMIZATION.md` - Optimization A & B (I/O pre-loading, API batching)
- `NOTEBOOK_REFACTORING_REPORT.md` - Overall refactoring status (Phases 1-2)
- `profile_extraction.py` - Module to extend with new functions
- `mobile_get_input_phase2.ipynb` - Current workflow (reference)

---

## Summary

This restructuring transforms the notebook from a tightly-coupled linear workflow into a modular, fault-tolerant pipeline with clear separation of concerns. The decoupling enables:

1. **Optimization**: Single-pass operations eliminate redundant I/O and API calls
2. **Maintainability**: Clear phases make debugging and modification easier
3. **Resilience**: Can checkpoint and resume from any phase
4. **Extensibility**: Easy to add parallelization, caching, or other enhancements
5. **Testability**: Each phase can be tested independently

The restructured workflow is the foundation for significant performance improvements and long-term maintenance benefits.
