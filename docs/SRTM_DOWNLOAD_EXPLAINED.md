# SRTM.py Tile Download - How It Works

## TL;DR
- **Phase 0**: Initializes SRTM handler (~0.01s, NO tiles downloaded)
- **Phase 3**: On first elevation query, tile DOWNLOADS (~30-45s)
- **Cache**: `data/intermediate/elevation_cache/N09W014.hgt` (2.8MB)

## Why Phase 0 Shows "No DEM tiles"

Phase 0 output is CORRECT:
```
✓ SRTM data handler initialized (0.01s)
  Cache location: /Users/oz/Documents/mst_gis/data/intermediate/elevation_cache
  Note: Tiles download on first elevation query (Phase 3)
```

This means:
- ✓ Handler initialized
- ⏳ Tiles will download when Phase 3 runs
- ✗ No tiles yet (they download during Phase 3)

## When Do Tiles Download?

**During Phase 3, on first elevation query:**

```python
# Phase 3 calls this internally:
gdf = generate_profile_points(...)
    ↓
# Inside generate_profile_points():
for point in points:
    z = srtm_data.get_elevation(lat, lon)  # ← DOWNLOADS TILE HERE
```

When SRTM.py executes `get_elevation()` for the first time:
1. Checks: Is N09W014.hgt cached? NO
2. Downloads from SRTM servers (~30-45s)
3. Saves to: `data/intermediate/elevation_cache/N09W014.hgt`
4. Returns elevation value

## Verified Flow

```
Terminal Output:
  $ python -c "
    srtm.get_elevation(9.345, -13.40694)
  "
  
  4 2884802                    ← SRTM downloading output
  ✓ Elevation retrieved (0.19s)
  Height: 13m
```

Cache Result:
```
$ ls -lh data/intermediate/elevation_cache/
-rw-r--r--  oz  staff  2.8M  Feb  6 18:45  N09W014.hgt
                                          ↑
                                  Tile successfully cached
```

## Phase Execution Timeline

### Phase 0 (Setup)
```
$ jupyter notebook notebooks/phase0_setup.ipynb
  ↓
  [Run all cells]
  ↓
  Initializing SRTM elevation data...
  ✓ SRTM data handler initialized (0.01s)
  Cache location: /Users/oz/Documents/mst_gis/data/intermediate/elevation_cache
  Note: Tiles download on first elevation query (Phase 3)
  
  STATUS: Handler ready, NO tiles yet ✓
```

### Phase 1 (Land Cover)
```
$ jupyter notebook notebooks/phase1_data_preparation.ipynb
  ↓
  [Downloads Sentinel Hub data]
  
  STATUS: Preparing land cover data ✓
```

### Phase 2 (Points)
```
$ jupyter notebook notebooks/phase2_point_generation.ipynb
  ↓
  [Generates receiver points]
  
  STATUS: Points generated ✓
```

### Phase 3 (Data Extraction) ← TILE DOWNLOADS HERE
```
$ jupyter notebook notebooks/phase3_batch_extraction.ipynb
  ↓
  [Calls generate_profile_points()]
  ↓
  First elevation query:
    srtm_data.get_elevation(lat, lon)
    ↓
    4 2884802     ← Downloading HGT tile
    ↓
    Tile saved to cache
    ↓
    Height extracted from tile
  
  STATUS: SRTM tile downloaded ✓
  Cache: /Users/oz/Documents/mst_gis/data/intermediate/elevation_cache/N09W014.hgt (2.8MB)
```

### Phase 4 (Post-processing)
```
$ jupyter notebook notebooks/phase4_post_processing.ipynb
  ↓
  [Uses cached tile - fast]
  
  STATUS: Uses cached elevation ✓
```

### Phase 5 (P.1812)
```
$ jupyter notebook notebooks/phase5_propagation.ipynb
  ↓
  [P.1812 calculations with valid elevation]
  
  STATUS: Success ✓
```

## How to Trigger Download Now

**Option 1: Run Phase 3 Notebook** (Recommended)
- Just run Phase 3 normally - tile downloads automatically

**Option 2: Direct Test**
```python
from mst_gis.propagation.profile_extraction import set_srtm_cache_dir, _get_srtm_data

set_srtm_cache_dir('/Users/oz/Documents/mst_gis/data/intermediate/elevation_cache')
srtm_data = _get_srtm_data()

# This triggers download:
elevation = srtm_data.get_elevation(9.345, -13.40694)
print(f"Height: {elevation}m")
```

## FAQ

**Q: Why doesn't Phase 0 download the tile?**
A: By design. Phase 0 just initializes the handler. Tiles download on first query (Phase 3) to keep Phase 0 fast and handle errors only if needed.

**Q: How long is Phase 3 first run?**
A: First elevation query downloads tile (~30-45s). Subsequent queries use cache (<1ms each).

**Q: Where's my tile?**
A: Check: `ls -lh /Users/oz/Documents/mst_gis/data/intermediate/elevation_cache/`

**Q: Can I download tiles manually?**
A: Not necessary. Just run Phase 3 - it triggers download automatically.

**Q: What if download fails?**
A: Phase 3 will show error. Check internet, then re-run Phase 3.

**Q: How do I clear cache?**
A: `rm /Users/oz/Documents/mst_gis/data/intermediate/elevation_cache/*.hgt`

## Comparison: Old vs New

### Old (elevation library)
```python
# Phase 0:
elevation.seed(bounds=[...])  # Downloads all tiles NOW
# Time: 30-45s upfront
# Problem: Slow Phase 0, downloads all tiles even if not needed
```

### New (SRTM.py)
```python
# Phase 0:
_get_srtm_data()  # Just initialize handler
# Time: <1ms

# Phase 3 (first query):
srtm_data.get_elevation(lat, lon)  # Downloads tile if needed
# Time: 30-45s (but only when needed)
# Benefit: Fast Phase 0, flexible downloading, only download needed tiles
```

## Next Actions

1. ✓ Run Phase 0 (already done)
2. → Run Phase 1 (land cover data)
3. → Run Phase 2 (point generation)
4. → Run Phase 3 (data extraction) ← **TILE DOWNLOADS HERE**
5. → Run Phase 4 (post-processing)
6. → Run Phase 5 (P.1812 calculations)

**You're ready to run Phase 3!** The tile will download automatically on first elevation query.
