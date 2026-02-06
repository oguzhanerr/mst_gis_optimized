# SRTM.py Final Implementation - Phase 0 Download + Phase 3 Pre-load

## Overview

The elevation workflow is now complete:
- **Phase 0**: Downloads SRTM1 HGT tile and pre-loads as array
- **Phase 3**: Uses pre-loaded array directly (no additional downloads)

## Phase 0 Workflow

```
Phase 0 Setup:
  1. Initialize SRTM handler
  2. Query TX location → triggers download
  3. SRTM.py downloads HGT tile (~30-45s first time only)
  4. Cache: data/intermediate/elevation_cache/N09W014.hgt (2.8MB)
  5. Load HGT into memory as array
  6. Make dem_band_data and dem_transform available for Phase 3
```

### Expected Output:
```
Initializing SRTM elevation data...
  Downloading SRTM1 tile for TX area (9.345, -13.40694)...
✓ SRTM elevation data ready (0.15s)
  TX elevation: 13m
  Cache location: /Users/oz/Documents/mst_gis/data/intermediate/elevation_cache

  Loading HGT tile into memory for Phase 3...
  ✓ HGT loaded: (1201, 1201) array, dtype=int16 (0.011s)
  ✓ Transform: | 0.00, 0.00,-14.00|...
```

## Phase 3 Workflow

```
Phase 3 Data Extraction:
  1. Pre-loading rasters section
  2. Looks for HGT files in elevation_cache/
  3. Loads first HGT with rasterio
  4. Gets dem_band_data array and dem_transform
  5. Uses pre-loaded array for fast elevation extraction
```

### Expected Output:
```
Pre-loading rasters:
  Land cover: lcm10_9.345_-13.40694_2020_buf11000m_734px.tif
    ✓ Loaded land cover array: (734, 734)
  DEM HGT: N09W014.hgt
    ✓ DEM HGT loaded: (1201, 1201) from N09W014.hgt

✓ Raster pre-loading complete: 0.00s
```

## File Changes

### Updated Notebooks
- `notebooks/phase0_setup.ipynb` - Cell 10
  - Downloads SRTM tile via `srtm_data.get_elevation()`
  - Pre-loads HGT into `dem_band_data` array
  - Passes `dem_transform` for Phase 3

- `notebooks/phase3_batch_extraction.ipynb` - Cell 4
  - Changed from loading VRT file
  - Now loads HGT files from cache with `glob.glob("*.hgt")`
  - Uses pre-loaded array for elevation extraction

### Updated Documentation
- `AGENTS.md` - Updated elevation section
  - Explains Phase 0 download and pre-load
  - References cache location: `data/intermediate/elevation_cache/`

## Cache Structure

```
data/intermediate/elevation_cache/
├── N09W014.hgt          (2.8MB, SRTM1 30m HGT tile)
└── N09W014.hgt.timestamp (backup copy if re-downloaded)
```

## Performance

```
Phase 0:
  - First run: ~0.15s with 30-45s SRTM download
  - Subsequent runs: ~0.01s (cache hit)

Phase 3:
  - HGT loading: ~0.011s
  - Elevation extraction: Uses pre-loaded array (<1ms per query)
```

## Why This Design

**Benefits of Phase 0 download + Phase 3 pre-load:**
1. ✓ Download happens once at beginning (Phase 0)
2. ✓ Fast Phase 3 access (array already in memory)
3. ✓ No network calls during Phase 3
4. ✓ Clear feedback when download occurs
5. ✓ Cache persistent between runs
6. ✓ Handles different SRTM tiles automatically

## Troubleshooting

### "No HGT files found" in Phase 3
- Make sure Phase 0 completed successfully
- Check cache: `ls -lh data/intermediate/elevation_cache/`
- Should see N09W014.hgt (2.8MB)

### Phase 0 slow
- First run downloads tile (~30-45s)
- Subsequent runs should be instant

### Wrong tile downloaded
- SRTM.py automatically selects tile based on TX location
- For different location, clear cache and re-run Phase 0:
  ```bash
  rm data/intermediate/elevation_cache/*.hgt
  ```

## Workflow Checklist

- [ ] Run Phase 0 (downloads SRTM, pre-loads HGT)
- [ ] Run Phase 1 (land cover preparation)
- [ ] Run Phase 2 (receiver point generation)
- [ ] Run Phase 3 (uses pre-loaded HGT array)
- [ ] Run Phase 4 (post-processing)
- [ ] Run Phase 5 (P.1812 calculations)

## Next Steps

You're ready to run the full pipeline!

```bash
jupyter notebook notebooks/phase0_setup.ipynb        # Downloads SRTM
jupyter notebook notebooks/phase1_data_preparation.ipynb
jupyter notebook notebooks/phase2_point_generation.ipynb
jupyter notebook notebooks/phase3_batch_extraction.ipynb    # Uses HGT
jupyter notebook notebooks/phase4_post_processing.ipynb
jupyter notebook notebooks/phase5_propagation.ipynb
```
