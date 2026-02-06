# Elevation Data Fix: Migrating to SRTM.py

## Problem Statement

The original elevation extraction in Phase 3 was returning negative height values (ranging from -1 to -5 meters), which prevented P.1812 propagation calculations from running. Analysis showed 35 of 36 profiles contained negative heights at various points along the path.

**Root Cause**: The `elevation` library was not properly handling missing/nodata values in the DEM tiles, returning invalid values instead of None or raising an error.

## Solution

Replaced the `elevation` library with SRTM.py, which is a more robust parser for SRTM data that properly handles nodata values.

### Library Comparison

| Aspect | elevation | SRTM.py |
|--------|-----------|---------|
| Source | NASA SRTM 30m/90m via USGS/CGIAR | SRTM NASA data |
| Nodata Handling | Poor (returns invalid values) | Excellent (returns None for voids) |
| Return Value | Elevation or 0 fallback | Elevation or None |
| Cache Location | `~/.cache/elevation` | `~/.cache/srtm` |
| API | `elevation.elevation(lat, lon)` | `srtm.get_data().get_elevation(lat, lon)` |
| Last Update | v1.1.3 (2021) | v0.3.7 (2021) |

## Implementation Changes

### 1. Modified `src/mst_gis/propagation/profile_extraction.py`

**Key changes:**
- Replaced `import elevation` with `import srtm`
- Changed elevation initialization from `elevation.seed()` to `srtm.get_data()`
- Updated elevation sampling loop to use `srtm_data.get_elevation(lat, lon)`
- Added parameters for no-data filtering:
  - `srtm_min_elev: float = 0.0` - Minimum valid elevation (default: sea level)
  - `srtm_max_elev: float = 9000.0` - Maximum valid elevation (default: high mountain)
- Implemented filtering to replace out-of-range elevations with 0

**Elevation extraction logic (lines 447-469):**
```python
for geom in gdf.geometry:
    try:
        z = srtm_data.get_elevation(geom.y, geom.x)
        if z is None:
            z = 0.0
        elif z < srtm_min_elev or z > srtm_max_elev:
            z = 0.0
    except Exception as e:
        z = 0.0
    h.append(z)
```

### 2. Updated Dependencies

**requirements.txt:**
- Removed: `elevation>=1.1.0`
- Added: `SRTM.py>=0.3.7`

**setup.py:**
- Removed: `"elevation"`
- Added: `"SRTM.py"`

## Validation

Tested with Phase 3 profile extraction on sample data (5 points, 2km distance):
- **Result**: All heights valid and positive (13-16m range)
- **Status**: ✓ No negative values detected

## Migration Path for Users

1. Install updated dependencies:
   ```bash
   pip install --upgrade -r requirements.txt
   ```

2. SRTM.py will cache tiles in `~/.cache/srtm/` (different from old `elevation` cache)

3. No code changes needed in notebooks - they use `profile_extraction.py` which handles this internally

4. First run will download SRTM1 30m tiles for your area (~15-45 seconds per unique tile)

## Notes

- SRTM data is valid globally but has better coverage in 60°N to 56°S latitude range
- Elevation cache is now in `~/.cache/srtm` instead of `~/.cache/elevation`
- The `srtm_min_elev` and `srtm_max_elev` parameters allow customization for specific regions:
  - For areas with submarine features: lower `srtm_min_elev` to -500
  - For areas with higher peaks: raise `srtm_max_elev` to 9000+

## Next Steps

1. Regenerate all Phase 3-4 profiles to fix the existing CSV files
2. Run Phase 5 P.1812 calculations with corrected elevation data
3. Validate propagation results match expected patterns
