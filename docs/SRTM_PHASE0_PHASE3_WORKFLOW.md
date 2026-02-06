# SRTM.py Phase 0 + Phase 3 Workflow

## Overview

SRTM elevation tiles are downloaded **lazily on first query during Phase 3**, not during Phase 0 setup. This design is optimal because:
- Phase 0 is fast (just initialization, <1ms)
- Tiles are only downloaded for areas actually needed
- Network errors don't block Phase 0 setup

## Workflow Timeline

```
Phase 0 (Setup)
  ↓
  • Import srtm library
  • Call set_srtm_cache_dir() → sets cache path
  • Call _get_srtm_data() → initializes handler (fast, no downloads)
  • Time: ~0.01s
  ↓
Phase 3 (Data Extraction)
  ↓
  • generate_profile_points() called
  • First elevation query made
  • SRTM.py checks: is tile cached? NO
  • Downloads HGT tile (~30-45s, first time only)
  • Subsequent queries use cached tile (<1ms each)
  • Time: 30-45s for first tile, <1ms thereafter
  ↓
Cache
  Location: /Users/oz/Documents/mst_gis/data/intermediate/elevation_cache/
  Stored: HGT files (binary SRTM format, ~2.8MB each)
```

## Phase 0 Code (Updated)

```python
# KEY OPTIMIZATION: Initialize SRTM data handler
# This configures elevation caching and prepares for Phase 3 extraction
print("\nInitializing SRTM elevation data...")
init_start = time.time()

try:
    # Set SRTM cache to project directory
    from mst_gis.propagation.profile_extraction import set_srtm_cache_dir, _get_srtm_data
    srtm_cache = project_root / "data" / "intermediate" / "elevation_cache"
    set_srtm_cache_dir(str(srtm_cache))
    
    # Initialize SRTM data handler (lazy loads on first query)
    srtm_data = _get_srtm_data()
    
    init_time = time.time() - init_start
    print(f"✓ SRTM data handler initialized ({init_time:.2f}s)")
    print(f"  Cache location: {srtm_cache}")
    print(f"  Note: Tiles download on first elevation query (Phase 3)")
    print(f"  Expected: 30-45s per tile, ~2.8MB each")
    
except Exception as e:
    import traceback
    print(f"✗ Error initializing SRTM: {e}")
    traceback.print_exc()
    srtm_data = None
```

## What "Seeding" Means in New Workflow

Old (elevation library):
```python
elevation.seed(bounds=[...])  # Pre-downloads all tiles in bounds
# Time: 30-45s upfront
```

New (SRTM.py):
```python
_get_srtm_data()  # Just initializes handler
# Time: <1ms
# Tiles download on first query during Phase 3
```

## Verification

Test results with Phase 0 + Phase 3:

```
Phase 0 initialization: ✓ 0.00s (handler initialized)
Phase 3 extraction: ✓ 0.17s (tile cached from earlier run)
Cache directory: ✓ /Users/oz/Documents/mst_gis/data/intermediate/elevation_cache
Cached tiles: ✓ 1 tile (N09W014.hgt, 2.8MB)
Heights extracted: ✓ 8-16m (valid, no negatives)
```

## Why This is Better

| Aspect | Old elevation.seed() | New SRTM.py lazy |
|--------|-------------------|------------------|
| Phase 0 time | 30-45s per tile | <1ms |
| User feedback | Long wait with no progress | Quick setup, clear Phase 3 timing |
| Flexibility | Pre-downloads all tiles (wasteful) | Downloads only needed tiles |
| Error handling | Fails Phase 0 if network issues | Fails only if Phase 3 needs tile |

## Usage in Other Phases

If you call `generate_profile_points()` from non-notebook code:

```python
import sys
sys.path.insert(0, 'src')
from pathlib import Path
from mst_gis.propagation.profile_extraction import set_srtm_cache_dir, generate_profile_points

# Set custom cache (optional, defaults to ~/.cache/srtm/)
project_root = Path('/Users/oz/Documents/mst_gis')
cache = project_root / 'data' / 'intermediate' / 'elevation_cache'
set_srtm_cache_dir(str(cache))

# Use normally - tiles download automatically on first query
gdf = generate_profile_points(...)
```

## Troubleshooting

### "No DEM tiles in cache after Phase 0"
This is NORMAL. Tiles download during Phase 3, not Phase 0.

### Phase 3 slow on first run
First elevation query downloads tile (~30-45s). Subsequent runs use cache (<1ms per query).

### Tile not found for your area
SRTM data is available 60°N to 56°S. Outside this range, elevation falls back to 0m.

### How to force re-download
```bash
rm /Users/oz/Documents/mst_gis/data/intermediate/elevation_cache/*.hgt
```

## Next Steps

1. **Run Phase 0**: Sets up SRTM handler (fast)
2. **Run Phase 1**: Land cover preparation (unchanged)
3. **Run Phase 2**: Point generation (unchanged)
4. **Run Phase 3**: Data extraction → **downloads SRTM tile** (~30-45s first time)
5. **Run Phase 4**: Post-processing with valid elevation data
6. **Run Phase 5**: P.1812 calculations
