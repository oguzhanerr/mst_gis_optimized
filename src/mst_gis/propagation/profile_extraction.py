"""
Profile extraction utilities for ITU-R P.1812-6 propagation modeling.

This module provides functions to extract terrain profiles from elevation and
land cover data sources.
"""

import math
import os
from typing import Tuple, Optional

import geopandas as gpd
import numpy as np
import rasterio
import requests
from pathlib import Path
from rasterio.io import MemoryFile
from shapely.geometry import Point

# Initialize SRTM data handler (lazy-loaded on first use)
_srtm_data = None
_srtm_cache_dir = None

def set_srtm_cache_dir(cache_dir: str):
    """Set custom SRTM cache directory.
    
    Args:
        cache_dir: Path to directory for caching SRTM HGT files
    """
    global _srtm_cache_dir
    _srtm_cache_dir = cache_dir
    # Clear cached data to force re-initialization with new path
    global _srtm_data
    _srtm_data = None

def _get_srtm_data():
    """Get or initialize SRTM data handler (cached).
    
    Uses custom cache directory if set via set_srtm_cache_dir(),
    otherwise uses SRTM.py default (~/.cache/srtm/).
    """
    global _srtm_data
    if _srtm_data is None:
        try:
            import srtm
            if _srtm_cache_dir:
                # Create cache directory if needed
                Path(_srtm_cache_dir).mkdir(parents=True, exist_ok=True)
                _srtm_data = srtm.get_data(local_cache_dir=_srtm_cache_dir)
            else:
                _srtm_data = srtm.get_data()
        except Exception as e:
            raise RuntimeError(f"Failed to initialize SRTM data: {e}")
    return _srtm_data


def meters_to_deg(lat: float, meters: float) -> Tuple[float, float]:
    """
    Convert meters to lat/lon degrees at given latitude.
    
    Args:
        lat: Latitude in degrees
        meters: Distance in meters
        
    Returns:
        (dlat, dlon) - change in latitude and longitude
    """
    dlat = meters / 111_320.0
    dlon = meters / (111_320.0 * math.cos(math.radians(lat)))
    return dlat, dlon


def get_token(client_id: str, client_secret: str, token_url: str, verbose: bool = False) -> str:
    """
    Get Sentinel Hub OAuth token.
    
    Args:
        client_id: Sentinel Hub client ID
        client_secret: Sentinel Hub client secret
        token_url: Token endpoint URL
        verbose: Print debug information
        
    Returns:
        Access token string
        
    Raises:
        requests.HTTPError: If token request fails
    """
    if verbose:
        print(f"[get_token] Requesting token from {token_url}")
    
    r = requests.post(
        token_url,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=60,
    )
    
    if verbose:
        print(f"[get_token] Response status: {r.status_code}")
    
    try:
        r.raise_for_status()
    except requests.HTTPError as e:
        if verbose:
            print(f"[get_token] Error response: {r.text[:200]}")
        raise
    
    token = r.json()["access_token"]
    if verbose:
        print(f"[get_token] ✓ Got token (length: {len(token)})")
    return token


def resolve_credentials(
    env_var_id: str = "SH_CLIENT_ID",
    env_var_secret: str = "SH_CLIENT_SECRET",
    fallback_id: Optional[str] = None,
    fallback_secret: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Get Sentinel Hub credentials from environment or fallback.
    
    Priority:
    1) Environment variables
    2) Fallback constants (if provided)
    
    Args:
        env_var_id: Name of env var for client ID
        env_var_secret: Name of env var for client secret
        fallback_id: Fallback client ID
        fallback_secret: Fallback client secret
        
    Returns:
        (client_id, client_secret)
        
    Raises:
        RuntimeError: If credentials not found or contain placeholders
    """
    env_id = os.environ.get(env_var_id, "").strip()
    env_secret = os.environ.get(env_var_secret, "").strip()

    if env_id and env_secret:
        return env_id, env_secret

    const_id = (fallback_id or "").strip()
    const_secret = (fallback_secret or "").strip()

    if not const_id or not const_secret or "REPLACE_ME" in const_id or "REPLACE_ME" in const_secret:
        raise RuntimeError(
            f"Credentials not found. Set {env_var_id} and {env_var_secret} either as env vars "
            f"or provide fallback values."
        )
    return const_id, const_secret


def landcover_at_point(
    client_id: str,
    client_secret: str,
    lat: float,
    lon: float,
    token_url: str,
    process_url: str,
    collection_id: str,
    year: int = 2020,
    buffer_m: float = 1000,
    chip_px: int = 32,
    save_path: Optional[str] = None,
    verbose: bool = False,
) -> Tuple[int, np.ndarray]:
    """
    Fetch land cover data from Sentinel Hub for a point and buffer.
    
    Args:
        client_id: Sentinel Hub client ID
        client_secret: Sentinel Hub client secret
        lat: Point latitude
        lon: Point longitude
        token_url: Sentinel Hub token endpoint
        process_url: Sentinel Hub API endpoint
        collection_id: BYOC collection ID
        year: Year to query (default 2020)
        buffer_m: Buffer radius in meters
        chip_px: Chip size in pixels
        save_path: Optional path to save GeoTIFF
        verbose: Print debug information
        
    Returns:
        (center_code, array) - LCM10 class at center and full array
        
    Raises:
        requests.HTTPError: If API request fails
    """
    if verbose:
        print(f"[landcover_at_point] Fetching for ({lat}, {lon}), buffer={buffer_m}m, year={year}")
    
    token = get_token(client_id, client_secret, token_url, verbose=verbose)

    dlat, dlon = meters_to_deg(lat, buffer_m)
    bbox = [lon - dlon, lat - dlat, lon + dlon, lat + dlat]

    evalscript = """
    //VERSION=3
    function setup() {
      return {
        input: ["LCM10"],
        output: { bands: 1, sampleType: "UINT8" }
      };
    }
    function evaluatePixel(s) {
      return [s.LCM10];
    }
    """

    body = {
        "input": {
            "bounds": {
                "bbox": bbox,
                "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"},
            },
            "data": [{
                "type": f"byoc-{collection_id}",
                "dataFilter": {
                    "timeRange": {
                        "from": f"{year}-01-01T00:00:00Z",
                        "to": f"{year}-12-31T23:59:59Z",
                    }
                },
            }],
        },
        "output": {
            "width": chip_px,
            "height": chip_px,
            "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}],
        },
        "evalscript": evalscript,
    }

    if verbose:
        print(f"[landcover_at_point] Calling API at {process_url}...")
    
    r = requests.post(
        process_url,
        json=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "image/tiff",
        },
        timeout=120,
    )
    
    if verbose:
        print(f"[landcover_at_point] Response status: {r.status_code}")
    
    try:
        r.raise_for_status()
    except requests.HTTPError as e:
        if verbose:
            print(f"[landcover_at_point] Error response: {r.text[:500]}")
        raise

    # Optionally save GeoTIFF to disk
    if save_path:
        with open(save_path, "wb") as f:
            f.write(r.content)
        if verbose:
            print(f"[landcover_at_point] ✓ Saved GeoTIFF: {save_path}")

    # Read GeoTIFF from memory
    with MemoryFile(r.content) as memfile:
        with memfile.open() as ds:
            arr = ds.read(1)  # uint8 codes

    center_code = int(arr[arr.shape[0] // 2, arr.shape[1] // 2])
    if verbose:
        print(f"[landcover_at_point] ✓ Got landcover chip: {arr.shape}, center code: {center_code}")
    return center_code, arr


def generate_profile_points(
    tx_lon: float,
    tx_lat: float,
    max_distance_km: float,
    n_points: int,
    azimuth_deg: float,
    tif_path: str,
    lcm10_to_ct: dict,
    ct_to_r: dict,
    zones_path: Optional[str] = None,
    tif_ds=None,
    dem_ds=None,
    skip_seed: bool = False,
    tif_band_data=None,
    tif_transform=None,
    tif_nodata=None,
    dem_band_data=None,
    dem_transform=None,
    srtm_min_elev: float = 0.0,
    srtm_max_elev: float = 9000.0,
) -> gpd.GeoDataFrame:
    """
    Generate profile points from TX to RX at given azimuth.
    
    Extracts elevation, land cover, and zone information for each point.
    
    Args:
        tx_lon: Transmitter longitude
        tx_lat: Transmitter latitude
        max_distance_km: Maximum distance in km
        n_points: Number of points along profile
        azimuth_deg: Azimuth angle in degrees (0=North, 90=East)
        tif_path: Path to land cover GeoTIFF
        lcm10_to_ct: Mapping from LCM10 codes to clutter types
        ct_to_r: Mapping from clutter types to roughness (R) values
        zones_path: Optional path to zones GeoJSON
        tif_ds: Pre-opened rasterio dataset for tif_path (optional, for performance)
        dem_ds: Pre-opened rasterio dataset for DEM VRT (optional, for performance)
        skip_seed: If True, skip elevation.seed() call (use when seeding done once before loop)
        tif_band_data: Pre-loaded TIF band array (NumPy array, optional for performance)
        tif_transform: Rasterio transform for tif_band_data (required if tif_band_data provided)
        tif_nodata: Nodata value for tif_band_data (optional)
        dem_band_data: Pre-loaded DEM band array (NumPy array, optional for performance)
        dem_transform: Rasterio transform for dem_band_data (required if dem_band_data provided)
        srtm_min_elev: Minimum valid elevation in meters (below this = no-data). Default: 0m
        srtm_max_elev: Maximum valid elevation in meters (above this = no-data). Default: 9000m
        
    Returns:
        GeoDataFrame with profile points and extracted data
        
    Raises:
        ValueError: If n_points < 2
        FileNotFoundError: If tif_path or zones_path don't exist
    """
    try:
        import srtm
    except ImportError:
        raise ImportError("SRTM.py package required for elevation extraction")

    if n_points < 2:
        raise ValueError("n_points must be >= 2")

    # Initialize SRTM elevation data source (auto-downloads tiles as needed)
    # Caches SRTM tiles in ~/.cache/srtm by default
    srtm_data = None
    if not skip_seed:
        try:
            # Get SRTM data handler - will auto-download missing tiles
            srtm_data = srtm.get_data()
        except Exception as seed_err:
            print(f"Warning: Could not initialize SRTM data ({seed_err}), will use fallback")

    # Create transmitter point in WGS84
    tx_gdf = gpd.GeoDataFrame(geometry=[Point(tx_lon, tx_lat)], crs="EPSG:4326")

    # Project to UTM for metric distances
    utm_crs = tx_gdf.estimate_utm_crs()
    tx_utm = tx_gdf.to_crs(utm_crs)
    center = tx_utm.geometry.iloc[0]

    # Compute step distance
    max_m = max_distance_km * 1000.0
    step_m = max_m / (n_points - 1)

    # Direction vector from bearing (clockwise from North)
    theta = math.radians(azimuth_deg)
    dx_unit = math.sin(theta)
    dy_unit = math.cos(theta)

    # Generate points along path in UTM
    points_utm = []
    distances_km = []

    for i in range(n_points):
        d_m = i * step_m
        x = center.x + d_m * dx_unit
        y = center.y + d_m * dy_unit
        points_utm.append(Point(x, y))
        distances_km.append(d_m / 1000.0)

    gdf_utm = gpd.GeoDataFrame(
        {"id": range(n_points), "d": distances_km, "azimuth": azimuth_deg},
        geometry=points_utm,
        crs=utm_crs,
    )

    # Convert back to WGS84 for elevation sampling
    gdf = gdf_utm.to_crs("EPSG:4326")

    # Load zones if available
    if zones_path and Path(zones_path).exists():
        gdf_zones = gpd.read_file(zones_path)
        if gdf_zones.crs != gdf.crs:
            gdf_zones = gdf_zones.to_crs(gdf.crs)

        gdf_joined = gpd.sjoin(
            gdf,
            gdf_zones[["zone_type_id", "geometry"]],
            how="left",
            predicate="intersects"
        )

        # Keep one row per point (drop duplicates from overlapping zones)
        gdf_joined = gdf_joined[~gdf_joined.index.duplicated(keep="first")]
        gdf["zone"] = gdf_joined["zone_type_id"].fillna(0).astype(int).to_numpy()
    else:
        gdf["zone"] = 0  # Default zone if not available

    # Extract land cover codes from GeoTIFF
    ct_codes = []
    if tif_band_data is not None and tif_transform is not None:
        # Use pre-loaded array with transform (fastest path - no file I/O)
        for geom in gdf.geometry:
            row, col = rasterio.transform.rowcol(tif_transform, geom.x, geom.y)
            
            if 0 <= row < tif_band_data.shape[0] and 0 <= col < tif_band_data.shape[1]:
                val = int(tif_band_data[int(row), int(col)])
                if tif_nodata is not None and val == tif_nodata:
                    val = 254
            else:
                val = 254  # outside tile bounds
            
            ct_codes.append(val)
    elif tif_ds is None:
        # Open dataset if not provided
        with rasterio.open(tif_path) as ds:
            band = ds.read(1)  # uint8 codes
            nodata = ds.nodata

            for geom in gdf.geometry:
                row, col = ds.index(geom.x, geom.y)

                if 0 <= row < ds.height and 0 <= col < ds.width:
                    val = int(band[row, col])
                    if nodata is not None and val == nodata:
                        val = 254
                else:
                    val = 254  # outside tile bounds

                ct_codes.append(val)
    else:
        # Use pre-opened dataset
        band = tif_ds.read(1)
        nodata = tif_ds.nodata

        for geom in gdf.geometry:
            row, col = tif_ds.index(geom.x, geom.y)

            if 0 <= row < tif_ds.height and 0 <= col < tif_ds.width:
                val = int(band[row, col])
                if nodata is not None and val == nodata:
                    val = 254
            else:
                val = 254

            ct_codes.append(val)

    gdf["ct"] = ct_codes  # raw land cover codes
    # Convert dict keys from string (JSON) to int for proper lookup
    lcm10_to_ct_int = {int(k): v for k, v in lcm10_to_ct.items()}
    ct_to_r_int = {int(k): v for k, v in ct_to_r.items()}
    gdf["Ct"] = gdf["ct"].map(lambda c: lcm10_to_ct_int.get(c, 2))
    gdf["R"] = gdf["Ct"].map(lambda ct: ct_to_r_int.get(ct, 0)).astype(int)

    # Sample elevation using SRTM.py library
    h = []
    if dem_band_data is not None and dem_transform is not None:
        # Use pre-loaded DEM array (fastest path - no file I/O)
        for geom in gdf.geometry:
            row, col = rasterio.transform.rowcol(dem_transform, geom.x, geom.y)
            if 0 <= row < dem_band_data.shape[0] and 0 <= col < dem_band_data.shape[1]:
                z = float(dem_band_data[int(row), int(col)])
            else:
                z = 0.0
            h.append(z)
    elif dem_ds is not None:
        # Use pre-opened DEM dataset
        dem_band = dem_ds.read(1)
        for geom in gdf.geometry:
            row, col = dem_ds.index(geom.x, geom.y)
            if 0 <= row < dem_ds.height and 0 <= col < dem_ds.width:
                z = float(dem_band[int(row), int(col)])
            else:
                z = 0.0
            h.append(z)
    else:
        # Use SRTM.py library to get elevation at each point
        # This handles missing data properly (returns None for voids)
        try:
            srtm_data = _get_srtm_data()
        except Exception as e:
            print(f"Warning: Could not initialize SRTM data ({e}), using 0 elevation")
            h = [0.0] * len(gdf)
            gdf["h"] = h
            return gdf
        
        for geom in gdf.geometry:
            try:
                # get_elevation returns elevation in meters or None for voids
                z = srtm_data.get_elevation(geom.y, geom.x)
                if z is None:
                    # Handle voids (missing data) - use 0 as fallback
                    z = 0.0
                elif z < srtm_min_elev or z > srtm_max_elev:
                    # Filter out invalid elevations (suspected no-data)
                    z = 0.0
            except Exception as e:
                print(f"Warning: Could not get elevation at ({geom.y:.4f}, {geom.x:.4f}): {e}")
                z = 0.0
            h.append(z)

    gdf["h"] = h
    return gdf
