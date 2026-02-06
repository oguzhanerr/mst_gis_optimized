# Regenerating Profiles with Fixed Elevation Data

After updating to SRTM.py for elevation extraction, you need to regenerate the profiles to fix the negative height values that were preventing P.1812 calculations.

## Quick Start

```bash
cd /Users/oz/Documents/mst_gis
source .venv/bin/activate

# Regenerate profiles
jupyter notebook notebooks/phase3_batch_extraction.ipynb
# Then run: phase4_post_processing.ipynb
```

## What Changed

- **Phase 3** (`phase3_batch_extraction.ipynb`): Now uses SRTM.py instead of `elevation` library for DEM sampling
- **Elevation Quality**: All heights will be >= 0m (validated against [0, 9000] range)
- **Cache Location**: SRTM tiles cached in `~/.cache/srtm/` instead of `~/.cache/elevation/`

## Step-by-Step Regeneration

### 1. Run Phase 0 (Setup)
Opens `notebooks/phase0_setup.ipynb` - loads CONFIG and seeds SRTM elevation cache

### 2. Run Phase 1 (Land Cover Preparation)
Opens `notebooks/phase1_data_preparation.ipynb` - downloads/caches Sentinel Hub land cover GeoTIFF

### 3. Run Phase 2 (Receiver Generation)
Opens `notebooks/phase2_point_generation.ipynb` - generates ~13k receiver points in radial pattern

### 4. Run Phase 3 (Data Extraction) ⭐ UPDATED
Opens `notebooks/phase3_batch_extraction.ipynb`:
- **Now uses SRTM.py** for elevation sampling (was: elevation library)
- Extracts elevation, land cover, and zones
- Output: Enriched GeoDataFrame saved to pickle file
- **All heights will now be valid** (no more negative values)

### 5. Run Phase 4 (Post-processing & Export)
Opens `notebooks/phase4_post_processing.ipynb`:
- Splits by azimuth
- Formats for P.1812
- Exports CSV to `data/input/profiles/paths_oneTx_manyRx_11km.csv`

### 6. Run Phase 5 (P.1812 Propagation)
Opens `notebooks/phase5_propagation.ipynb`:
- Loads profiles from regenerated CSV
- Calls P.1812.bt_loss() with valid elevation data
- **Will now complete successfully** without elevation-related errors

## Validation Checklist

After regeneration, verify:

- [ ] Phase 3 output shows all heights >= 0
- [ ] Phase 4 CSV file `data/input/profiles/paths_oneTx_manyRx_11km.csv` has valid heights
- [ ] Phase 5 P.1812 calculations complete without errors
- [ ] GeoJSON output files generated in `data/output/geojson/`

## Troubleshooting

### Issue: "SRTM.py module not found"
```bash
pip install SRTM.py
```

### Issue: Slow first run
SRTM.py downloads ~2-4 tiles (~30-45 seconds per tile) on first run for your area. This is normal and cached for future runs.

### Issue: Still seeing negative heights
- Clear old elevation cache: `rm -rf ~/.cache/elevation`
- Ensure you're using latest code: `git pull`
- Restart Jupyter kernel and re-run Phase 3

## Expected Elevation Range for Your Area

For transmitter at (9.345°N, -13.407°W, West Africa):
- **Typical range**: 0-500m elevation
- **Min/max filter**: [0, 9000] meters (configured in `profile_extraction.py`)
- If you have submarine points or require different range, adjust `srtm_min_elev` and `srtm_max_elev` parameters

## References

- SRTM.py documentation: https://github.com/tkrajina/srtm.py
- Fix documentation: `docs/ELEVATION_DATA_FIX.md`
- Original issue: Negative heights in `paths_oneTx_manyRx_11km.csv` prevented P.1812 calculations
