"""
Point generation module for the radio propagation pipeline.

Handles:
- Batch generation of receiver points at multiple distances and azimuths
- Radial distribution around a transmitter
- GeoDataFrame construction with metadata
"""

import math
from pathlib import Path
from typing import List, Tuple, Optional, NamedTuple

import geopandas as gpd
import numpy as np
from shapely.geometry import Point

from mst_gis.utils.logging import Timer, print_success, print_warning
from mst_gis.utils.validation import ValidationError


class Transmitter(NamedTuple):
    """Transmitter specification."""
    tx_id: str
    lon: float
    lat: float
    htg: float  # Height above ground (m)
    f: float    # Frequency (GHz)
    pol: int    # Polarization (1=horizontal, 2=vertical)
    p: int      # Time percentage (%)
    hrg: float  # Receiver height above ground (m)


def generate_receivers_radial_multi(
    tx: Transmitter,
    distances_km: List[float],
    azimuths_deg: List[float],
    include_tx_point: bool = False,
) -> gpd.GeoDataFrame:
    """
    Generate receiver points on multiple rings around transmitter.
    
    Creates uniformly distributed receiver points at each distance × azimuth
    combination, with proper coordinate transformation.
    
    Args:
        tx: Transmitter with lon, lat, tx_id
        distances_km: Array/list of distances in km
        azimuths_deg: Array/list of azimuths in degrees (0-360)
        include_tx_point: If True, include transmitter as rx_id=0
        
    Returns:
        GeoDataFrame with columns: tx_id, rx_id, distance_km, azimuth_deg, geometry
        - CRS: EPSG:4326 (WGS84)
        - Sorted by distance and azimuth
        
    Raises:
        ValidationError: If inputs are invalid
    """
    # Validate inputs
    if not distances_km or not azimuths_deg:
        raise ValidationError("distances_km and azimuths_deg cannot be empty")
    
    if any(d < 0 for d in distances_km):
        raise ValidationError("All distances must be >= 0")
    
    if any(0 > az or az >= 360 for az in azimuths_deg):
        raise ValidationError("All azimuths must be in [0, 360)")
    
    # Create transmitter point and get UTM CRS
    tx_gdf = gpd.GeoDataFrame(
        {"tx_id": [tx.tx_id]},
        geometry=[Point(tx.lon, tx.lat)],
        crs="EPSG:4326",
    )
    utm_crs = tx_gdf.estimate_utm_crs()
    tx_utm = tx_gdf.to_crs(utm_crs)
    tx_pt = tx_utm.geometry.iloc[0]
    
    rows = []
    rx_id = 1
    
    # Optional: add transmitter point at distance=0
    if include_tx_point:
        rows.append({
            "tx_id": tx.tx_id,
            "rx_id": 0,
            "distance_km": 0.0,
            "azimuth_deg": np.nan,
            "geometry": Point(tx.lon, tx.lat),
        })
    
    # Generate receivers at each distance × azimuth combination
    for d_km in distances_km:
        radius_m = float(d_km) * 1000.0
        
        for az in azimuths_deg:
            # Convert azimuth to radians (0° = North, 90° = East)
            theta = math.radians(float(az))
            
            # Calculate offset in UTM
            dx = radius_m * math.sin(theta)
            dy = radius_m * math.cos(theta)
            
            rx_utm = Point(tx_pt.x + dx, tx_pt.y + dy)
            
            # Convert back to WGS84 (EPSG:4326)
            rx_ll = gpd.GeoSeries([rx_utm], crs=utm_crs).to_crs("EPSG:4326").iloc[0]
            
            rows.append({
                "tx_id": tx.tx_id,
                "rx_id": rx_id,
                "distance_km": float(d_km),
                "azimuth_deg": float(az),
                "geometry": rx_ll,
            })
            rx_id += 1
    
    # Create GeoDataFrame with proper column order
    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    
    # Sort by distance, then azimuth
    gdf = gdf.sort_values(["distance_km", "azimuth_deg"]).reset_index(drop=True)
    
    return gdf


def generate_distance_array(
    min_km: float = 0.0,
    max_km: float = 11.0,
    step_km: float = 0.03,
) -> np.ndarray:
    """
    Generate array of distances.
    
    Args:
        min_km: Minimum distance (km)
        max_km: Maximum distance (km)
        step_km: Distance step (km)
        
    Returns:
        Array of distances in km
        
    Raises:
        ValidationError: If inputs are invalid
    """
    if min_km < 0 or max_km < 0:
        raise ValidationError("Distances must be non-negative")
    
    if min_km > max_km:
        raise ValidationError("min_km must be <= max_km")
    
    if step_km <= 0:
        raise ValidationError("step_km must be > 0")
    
    # Use numpy arange with small epsilon to handle floating point
    distances = np.arange(min_km, max_km + step_km/2, step_km)
    
    # Ensure we don't exceed max_km due to floating point errors
    distances = distances[distances <= max_km + 1e-6]
    
    return distances


def generate_azimuth_array(
    num_azimuths: int = 36,
    start_deg: float = 0.0,
) -> np.ndarray:
    """
    Generate array of azimuths.
    
    Args:
        num_azimuths: Number of azimuth angles (e.g., 36 = 10° spacing)
        start_deg: Starting azimuth in degrees
        
    Returns:
        Array of azimuths in degrees [0, 360)
        
    Raises:
        ValidationError: If inputs are invalid
    """
    if num_azimuths <= 0:
        raise ValidationError("num_azimuths must be > 0")
    
    if not 0 <= start_deg < 360:
        raise ValidationError("start_deg must be in [0, 360)")
    
    azimuths = np.linspace(start_deg, 360 + start_deg - (360 / num_azimuths), num_azimuths)
    
    # Ensure all azimuths are in [0, 360)
    azimuths = azimuths % 360
    
    return azimuths


def generate_receiver_grid(
    tx: Transmitter,
    max_distance_km: float = 11.0,
    distance_step_km: float = 0.03,
    num_azimuths: int = 36,
    include_tx_point: bool = True,
) -> gpd.GeoDataFrame:
    """
    Generate complete receiver grid around transmitter.
    
    Convenience function that generates both distance and azimuth arrays,
    then creates receiver points.
    
    Args:
        tx: Transmitter specification
        max_distance_km: Maximum distance in km
        distance_step_km: Distance step in km
        num_azimuths: Number of azimuth angles
        include_tx_point: Include transmitter as rx_id=0
        
    Returns:
        GeoDataFrame with all receiver points
        
    Raises:
        ValidationError: If inputs are invalid
    """
    distances = generate_distance_array(
        min_km=0.0,
        max_km=max_distance_km,
        step_km=distance_step_km,
    )
    
    azimuths = generate_azimuth_array(num_azimuths=num_azimuths)
    
    return generate_receivers_radial_multi(
        tx,
        distances.tolist(),
        azimuths.tolist(),
        include_tx_point=include_tx_point,
    )


def print_generation_summary(
    tx: Transmitter,
    receivers_gdf: gpd.GeoDataFrame,
    max_distance_km: float,
    distance_step_km: float,
    num_azimuths: int,
    elapsed_s: float,
) -> None:
    """Print summary of point generation."""
    print("\n" + "=" * 60)
    print("PHASE 2: BATCH POINT GENERATION")
    print("=" * 60)
    
    print(f"\nGenerating receiver points:")
    print(f"  Transmitter: ({tx.lat}, {tx.lon})")
    print(f"  Max distance: {max_distance_km} km")
    
    num_distances = len(generate_distance_array(0, max_distance_km, distance_step_km))
    print(f"  Distances: {num_distances} points @ {distance_step_km} km spacing")
    print(f"  Azimuths: {num_azimuths} angles @ {360/num_azimuths}° spacing")
    print(f"  Expected points: ~{num_distances * num_azimuths + 1}")
    
    print(f"\n✓ Generated {len(receivers_gdf)} receiver points in {elapsed_s:.3f}s")
    
    print(f"\nGeoDataFrame structure:")
    print(f"  Columns: {list(receivers_gdf.columns)}")
    print(f"  CRS: {receivers_gdf.crs}")
    
    print(f"\nFirst 5 points:")
    print(receivers_gdf.head())
    print(f"\nLast 5 points:")
    print(receivers_gdf.tail())
