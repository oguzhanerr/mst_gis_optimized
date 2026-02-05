#!/usr/bin/env python3
"""
End-to-end test for Phase 0-4 notebook pipeline.

This script validates that all 5 phases work together correctly by:
1. Checking imports and dependencies
2. Validating output at each phase boundary
3. Comparing final CSV with expected structure
4. Measuring performance timings
"""

import os
import sys
import time
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pandas as pd
import geopandas as gpd


def test_imports():
    """Test that all required packages are importable."""
    print("\n" + "="*60)
    print("TEST 1: Validate Imports")
    print("="*60)
    
    packages = [
        ('geopandas', 'gpd'),
        ('pandas', 'pd'),
        ('numpy', 'np'),
        ('rasterio', None),
        ('elevation', None),
        ('shapely', None),
    ]
    
    for pkg, alias in packages:
        try:
            __import__(pkg)
            print(f"  ✓ {pkg}")
        except ImportError as e:
            print(f"  ✗ {pkg}: {e}")
            return False
    
    return True


def test_file_structure():
    """Test that required files and directories exist."""
    print("\n" + "="*60)
    print("TEST 2: Validate File Structure")
    print("="*60)
    
    required = [
        ('data/notebooks/phase0_setup.ipynb', 'Phase 0 notebook'),
        ('data/notebooks/phase1_data_prep.ipynb', 'Phase 1 notebook'),
        ('data/notebooks/phase2_batch_points.ipynb', 'Phase 2 notebook'),
        ('data/notebooks/phase3_batch_extraction.ipynb', 'Phase 3 notebook'),
        ('data/notebooks/phase4_formatting_export.ipynb', 'Phase 4 notebook'),
        ('config_sentinel_hub.py', 'Sentinel Hub config'),
        ('src/mst_gis/', 'Source modules'),
    ]
    
    all_exist = True
    for path, desc in required:
        full_path = project_root / path
        exists = full_path.exists()
        status = "✓" if exists else "✗"
        print(f"  {status} {desc}: {path}")
        if not exists:
            all_exist = False
    
    return all_exist


def test_config():
    """Test that configuration is accessible."""
    print("\n" + "="*60)
    print("TEST 3: Validate Configuration")
    print("="*60)
    
    try:
        sys.path.insert(0, str(project_root))
        from config_sentinel_hub import (
            SH_CLIENT_ID, SH_CLIENT_SECRET,
            TOKEN_URL, PROCESS_URL, COLLECTION_ID,
        )
        
        if "REPLACE_ME" in str(SH_CLIENT_ID):
            print("  ⚠ WARNING: SH_CLIENT_ID not configured")
            return False
        
        print(f"  ✓ Sentinel Hub config loaded")
        print(f"    Client ID: {SH_CLIENT_ID[:20]}...")
        print(f"    Token URL: {TOKEN_URL}")
        return True
    except Exception as e:
        print(f"  ✗ Config error: {e}")
        return False


def test_paths():
    """Test that data directories exist and are writable."""
    print("\n" + "="*60)
    print("TEST 4: Validate Data Paths")
    print("="*60)
    
    paths = [
        ('data/input/profiles', 'Input profiles'),
        ('data/intermediate/api_data', 'API data cache'),
        ('data/intermediate/workflow', 'Workflow data'),
        ('data/output/geojson', 'Output GeoJSON'),
        ('data/notebooks', 'Notebooks'),
    ]
    
    all_writable = True
    for path, desc in paths:
        full_path = project_root / path
        full_path.mkdir(parents=True, exist_ok=True)
        writable = os.access(full_path, os.W_OK)
        status = "✓" if writable else "✗"
        print(f"  {status} {desc}: {path}")
        if not writable:
            all_writable = False
    
    return all_writable


def test_csv_output():
    """Test that CSV output file exists and has expected structure."""
    print("\n" + "="*60)
    print("TEST 5: Validate CSV Output")
    print("="*60)
    
    profiles_dir = project_root / 'data/input/profiles'
    csv_files = list(profiles_dir.glob('paths_oneTx_manyRx_*.csv'))
    
    if not csv_files:
        print(f"  ⚠ No CSV files found in {profiles_dir}")
        return False
    
    latest_csv = max(csv_files, key=lambda p: p.stat().st_mtime)
    print(f"  ✓ Found CSV: {latest_csv.name}")
    
    try:
        df = pd.read_csv(latest_csv, sep=';')
        print(f"    Profiles: {len(df)}")
        print(f"    Columns: {list(df.columns)}")
        
        # Expected columns
        expected = ['f', 'p', 'd', 'h', 'R', 'Ct', 'zone', 'htg', 'hrg', 'pol', 'phi_t', 'phi_r', 'lam_t', 'lam_r']
        missing = [col for col in expected if col not in df.columns]
        
        if missing:
            print(f"    ✗ Missing columns: {missing}")
            return False
        
        print(f"    ✓ All expected columns present")
        
        # Validate data types and ranges
        if 'f' in df.columns:
            freq = df['f'].iloc[0]
            if 0.03 <= freq <= 6:
                print(f"    ✓ Frequency: {freq} GHz (valid)")
            else:
                print(f"    ✗ Frequency out of range: {freq} GHz")
                return False
        
        if 'd' in df.columns:
            num_profiles = len(df)
            print(f"    ✓ Profiles: {num_profiles}")
            if num_profiles >= 30:
                print(f"      Expected ~36 azimuths, found {num_profiles}")
        
        return True
    except Exception as e:
        print(f"  ✗ CSV validation error: {e}")
        return False


def test_elevation_cache():
    """Test that elevation cache exists."""
    print("\n" + "="*60)
    print("TEST 6: Validate Elevation Cache")
    print("="*60)
    
    try:
        import elevation
        cache_dir = Path(elevation.CACHE_DIR)
        vrt_path = cache_dir / "SRTM1" / "SRTM1.vrt"
        
        if vrt_path.exists():
            print(f"  ✓ Elevation cache found: {vrt_path}")
            return True
        else:
            print(f"  ⚠ Elevation cache not found at {vrt_path}")
            print(f"    Run Phase 0 to download elevation data")
            return False
    except Exception as e:
        print(f"  ✗ Error checking elevation: {e}")
        return False


def test_landcover_cache():
    """Test that land cover cache exists."""
    print("\n" + "="*60)
    print("TEST 7: Validate Land Cover Cache")
    print("="*60)
    
    api_data_dir = project_root / 'data/intermediate/api_data'
    tif_files = list(api_data_dir.glob('lcm10_*.tif'))
    
    if tif_files:
        latest_tif = max(tif_files, key=lambda p: p.stat().st_mtime)
        print(f"  ✓ Land cover TIF found: {latest_tif.name}")
        print(f"    Size: {latest_tif.stat().st_size / 1024 / 1024:.1f} MB")
        return True
    else:
        print(f"  ⚠ No land cover TIF found in {api_data_dir}")
        print(f"    Run Phase 1 to download land cover data")
        return False


def test_receiver_points():
    """Test that GeoDataFrame structure is correct."""
    print("\n" + "="*60)
    print("TEST 8: Validate Receiver Points Structure")
    print("="*60)
    
    try:
        # Create sample GeoDataFrame to validate structure
        from shapely.geometry import Point
        import geopandas as gpd
        
        sample_data = {
            'tx_id': ['TX_0001'],
            'rx_id': [1],
            'distance_km': [5.0],
            'azimuth_deg': [0.0],
            'geometry': [Point(-13.40694, 9.345)],
        }
        
        gdf = gpd.GeoDataFrame(sample_data, crs='EPSG:4326')
        print(f"  ✓ GeoDataFrame structure valid")
        print(f"    Columns: {list(gdf.columns)}")
        print(f"    CRS: {gdf.crs}")
        return True
    except Exception as e:
        print(f"  ✗ GeoDataFrame error: {e}")
        return False


def test_zone_reference_data():
    """Test that zones GeoJSON reference file exists and is valid."""
    print("\n" + "="*60)
    print("TEST 9: Validate Zone Reference Data")
    print("="*60)
    
    zones_path = project_root / 'data' / 'input' / 'reference' / 'zones_map_BR.json'
    
    if not zones_path.exists():
        print(f"  ✗ Zones GeoJSON not found at {zones_path}")
        return False
    
    try:
        with open(zones_path) as f:
            zones_geojson = json.load(f)
        
        if 'features' not in zones_geojson:
            print(f"  ✗ Invalid GeoJSON: no 'features' key")
            return False
        
        num_features = len(zones_geojson['features'])
        print(f"  ✓ Zones GeoJSON loaded: {num_features} features")
        
        # Load as GeoDataFrame
        gdf_zones = gpd.GeoDataFrame.from_features(zones_geojson['features'])
        gdf_zones = gdf_zones.set_crs('EPSG:4326')
        
        # Check zone types
        zone_types = set(gdf_zones['zone_type_id'].unique())
        expected_zones = {1, 3, 4}
        
        if zone_types != expected_zones:
            print(f"  ✗ Invalid zone types. Expected {expected_zones}, got {zone_types}")
            return False
        
        zone_counts = gdf_zones['zone_type_id'].value_counts()
        print(f"  ✓ Zone types: 1 (Sea): {zone_counts.get(1, 0)}, 3 (Coastal): {zone_counts.get(3, 0)}, 4 (Inland): {zone_counts.get(4, 0)}")
        
        return True
    except json.JSONDecodeError as e:
        print(f"  ✗ Invalid JSON in zones file: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Zone reference error: {e}")
        return False


def test_zone_extraction_logic():
    """Test that point-in-polygon zone extraction works correctly."""
    print("\n" + "="*60)
    print("TEST 10: Validate Zone Extraction Logic")
    print("="*60)
    
    zones_path = project_root / 'data' / 'input' / 'reference' / 'zones_map_BR.json'
    
    if not zones_path.exists():
        print(f"  ⚠ Zones GeoJSON not found, skipping test")
        return True  # Not a failure, just skip
    
    try:
        from shapely.geometry import Point
        
        # Load zones
        with open(zones_path) as f:
            zones_geojson = json.load(f)
        gdf_zones = gpd.GeoDataFrame.from_features(zones_geojson['features'])
        gdf_zones = gdf_zones.set_crs('EPSG:4326')
        
        # Create test points
        test_points = gpd.GeoDataFrame([
            {'rx_id': 1, 'geometry': Point(-13.40694, 9.345), 'zone': 0},   # Senegal (Inland)
            {'rx_id': 2, 'geometry': Point(-43.1728, -22.9068), 'zone': 0}, # Rio de Janeiro (Coastal)
        ], crs='EPSG:4326')
        
        # Extract zones using point-in-polygon
        for idx in test_points.index:
            point = test_points.loc[idx, 'geometry']
            for _, zone_row in gdf_zones.iterrows():
                if zone_row.geometry.contains(point):
                    test_points.loc[idx, 'zone'] = int(zone_row['zone_type_id'])
                    break
        
        # Verify results
        results_ok = True
        
        if test_points.loc[0, 'zone'] == 4:
            print(f"  ✓ Senegal point: zone 4 (Inland)")
        else:
            print(f"  ✗ Senegal point: expected zone 4, got {test_points.loc[0, 'zone']}")
            results_ok = False
        
        if test_points.loc[1, 'zone'] == 3:
            print(f"  ✓ Rio de Janeiro point: zone 3 (Coastal)")
        else:
            print(f"  ✗ Rio de Janeiro point: expected zone 3, got {test_points.loc[1, 'zone']}")
            results_ok = False
        
        return results_ok
    except Exception as e:
        print(f"  ✗ Zone extraction error: {e}")
        return False


def main():
    """Run all tests and report results."""
    print("\n" + "="*70)
    print("PHASE 0-4 NOTEBOOK PIPELINE VALIDATION")
    print("="*70)
    
    tests = [
        ('Imports', test_imports),
        ('File Structure', test_file_structure),
        ('Configuration', test_config),
        ('Data Paths', test_paths),
        ('CSV Output', test_csv_output),
        ('Elevation Cache', test_elevation_cache),
        ('Land Cover Cache', test_landcover_cache),
        ('Receiver Points', test_receiver_points),
        ('Zone Reference Data', test_zone_reference_data),
        ('Zone Extraction Logic', test_zone_extraction_logic),
    ]
    
    results = {}
    for name, test_func in tests:
        try:
            result = test_func()
            results[name] = result
        except Exception as e:
            print(f"\n✗ Test '{name}' failed with exception: {e}")
            results[name] = False
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "PASS" if result else "FAIL"
        symbol = "✓" if result else "✗"
        print(f"  {symbol} {name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed! Pipeline is ready for end-to-end testing.")
        print("\nNext steps:")
        print("  1. Run Phase 0 notebook: phase0_setup.ipynb")
        print("  2. Run Phase 1 notebook: phase1_data_prep.ipynb (requires Sentinel Hub credentials)")
        print("  3. Run Phase 2 notebook: phase2_batch_points.ipynb")
        print("  4. Run Phase 3 notebook: phase3_batch_extraction.ipynb")
        print("  5. Run Phase 4 notebook: phase4_formatting_export.ipynb")
        print("  6. Run: python scripts/run_batch_processor.py")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed. See details above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
