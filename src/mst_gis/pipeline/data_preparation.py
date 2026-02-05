"""
Data preparation module for the radio propagation pipeline.

Handles:
- Sentinel Hub OAuth authentication
- Land cover GeoTIFF download
- Caching of downloaded data
- Data validation
"""

import os
import time
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
import json

import numpy as np
import rasterio
from rasterio.transform import Affine
import requests

from mst_gis.utils.logging import Timer, print_success, print_warning, print_error
from mst_gis.utils.validation import validate_path_exists


class SentinelHubClient:
    """Client for Sentinel Hub API interactions."""
    
    def __init__(self, client_id: str, client_secret: str, 
                 token_url: str = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
                 process_url: str = "https://sh.dataspace.copernicus.eu/api/v1/process",
                 verbose: bool = False):
        """
        Initialize Sentinel Hub client.
        
        Args:
            client_id: Sentinel Hub client ID
            client_secret: Sentinel Hub client secret
            token_url: Token endpoint URL
            process_url: Processing API endpoint URL
            verbose: Enable debug logging
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self.process_url = process_url
        self.verbose = verbose
        self.token = None
        self.token_expiry = None
    
    def get_token(self) -> str:
        """
        Get or refresh Sentinel Hub OAuth token.
        
        Returns:
            Access token string
            
        Raises:
            requests.HTTPError: If token request fails
        """
        # Reuse token if still valid
        if self.token and self.token_expiry and time.time() < self.token_expiry:
            if self.verbose:
                print(f"Reusing cached token (expires in {self.token_expiry - time.time():.0f}s)")
            return self.token
        
        if self.verbose:
            print(f"Requesting new token from {self.token_url}")
        
        response = requests.post(
            self.token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=60,
        )
        
        response.raise_for_status()
        
        data = response.json()
        self.token = data["access_token"]
        self.token_expiry = time.time() + data.get("expires_in", 3600) - 60  # Refresh 60s before expiry
        
        if self.verbose:
            print(f"✓ Got token (expires in {data.get('expires_in', 3600)}s)")
        
        return self.token
    
    def get_landcover(self, lat: float, lon: float, collection_id: str,
                     year: int = 2020, buffer_m: float = 11000, chip_px: int = 734) -> np.ndarray:
        """
        Fetch land cover GeoTIFF from Sentinel Hub.
        
        Args:
            lat: Point latitude (WGS84)
            lon: Point longitude (WGS84)
            collection_id: BYOC collection ID
            year: Year to query
            buffer_m: Buffer radius in meters
            chip_px: Output chip size in pixels
            
        Returns:
            Raster array (uint8) with land cover codes
            
        Raises:
            requests.HTTPError: If API request fails
        """
        import math
        
        token = self.get_token()
        
        # Calculate bounding box
        dlat = buffer_m / 111_320.0
        dlon = buffer_m / (111_320.0 * math.cos(math.radians(lat)))
        bbox = [lon - dlon, lat - dlat, lon + dlon, lat + dlat]
        
        if self.verbose:
            print(f"Fetching land cover: lat={lat}, lon={lon}, buffer={buffer_m}m")
        
        # Eval script for LCM10 band
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
        
        request_body = {
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
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        
        response = requests.post(
            self.process_url,
            json=request_body,
            headers=headers,
            timeout=300,
        )
        
        response.raise_for_status()
        
        # Parse GeoTIFF from response
        with rasterio.open(rasterio.MemoryFile(response.content).open()) as src:
            array = src.read(1)
        
        if self.verbose:
            print(f"✓ Got landcover array: {array.shape}, min={array.min()}, max={array.max()}")
        
        return array


class LandCoverProcessor:
    """Process and cache land cover data."""
    
    def __init__(self, cache_dir: Path):
        """
        Initialize processor.
        
        Args:
            cache_dir: Directory for cached GeoTIFF files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def get_cache_path(self, lat: float, lon: float, year: int,
                       buffer_m: float, chip_px: int) -> Path:
        """Generate cache file path."""
        filename = f"lcm10_{lat}_{lon}_{year}_buf{int(buffer_m)}m_{chip_px}px.tif"
        return self.cache_dir / filename
    
    def has_cached(self, lat: float, lon: float, year: int,
                   buffer_m: float, chip_px: int) -> bool:
        """Check if data is in cache."""
        cache_path = self.get_cache_path(lat, lon, year, buffer_m, chip_px)
        return cache_path.exists()
    
    def load_cached(self, lat: float, lon: float, year: int,
                    buffer_m: float, chip_px: int) -> np.ndarray:
        """
        Load cached land cover data.
        
        Returns:
            Raster array (uint8)
        """
        cache_path = self.get_cache_path(lat, lon, year, buffer_m, chip_px)
        
        if not cache_path.exists():
            raise FileNotFoundError(f"Cache file not found: {cache_path}")
        
        with rasterio.open(cache_path) as src:
            array = src.read(1)
        
        return array
    
    def save_geotiff(self, array: np.ndarray, lat: float, lon: float,
                     year: int, buffer_m: float, chip_px: int) -> Path:
        """
        Save land cover array as GeoTIFF with proper geotransform.
        
        Args:
            array: Raster array (uint8)
            lat: Center point latitude
            lon: Center point longitude
            year: Year of data
            buffer_m: Buffer radius in meters
            chip_px: Chip size in pixels
            
        Returns:
            Path to saved GeoTIFF
        """
        import math
        
        cache_path = self.get_cache_path(lat, lon, year, buffer_m, chip_px)
        
        # Calculate geotransform
        dlat = buffer_m / 111_320.0
        dlon = buffer_m / (111_320.0 * math.cos(math.radians(lat)))
        
        pixel_width = (2 * dlon) / chip_px
        pixel_height = -(2 * dlat) / chip_px  # Negative because raster y increases downward
        
        transform = Affine(
            pixel_width,
            0,
            lon - dlon,  # Upper left x
            0,
            pixel_height,
            lat + dlat,  # Upper left y
        )
        
        # Write GeoTIFF
        with rasterio.open(
            cache_path,
            'w',
            driver='GTiff',
            height=array.shape[0],
            width=array.shape[1],
            count=1,
            dtype=array.dtype,
            crs='EPSG:4326',
            transform=transform,
        ) as dst:
            dst.write(array, 1)
        
        return cache_path


def prepare_landcover(lat: float, lon: float, cache_dir: Path,
                      client_id: str, client_secret: str,
                      token_url: str, process_url: str,
                      collection_id: str,
                      year: int = 2020,
                      buffer_m: float = 11000,
                      chip_px: int = 734,
                      force_download: bool = False,
                      verbose: bool = False) -> Path:
    """
    Prepare land cover GeoTIFF (download if needed, or load from cache).
    
    Args:
        lat: Point latitude
        lon: Point longitude
        cache_dir: Cache directory for GeoTIFF files
        client_id: Sentinel Hub client ID
        client_secret: Sentinel Hub client secret
        token_url: Token endpoint URL
        process_url: Processing endpoint URL
        collection_id: BYOC collection ID
        year: Year to query
        buffer_m: Buffer radius in meters
        chip_px: Chip size in pixels
        force_download: Force re-download even if cached
        verbose: Enable debug logging
        
    Returns:
        Path to GeoTIFF file
    """
    processor = LandCoverProcessor(cache_dir)
    cache_path = processor.get_cache_path(lat, lon, year, buffer_m, chip_px)
    
    # Check cache
    if not force_download and processor.has_cached(lat, lon, year, buffer_m, chip_px):
        if verbose:
            print(f"Using cached landcover: {cache_path.name}")
        return cache_path
    
    # Download from Sentinel Hub
    with Timer(f"Download landcover for ({lat}, {lon})"):
        client = SentinelHubClient(
            client_id, client_secret,
            token_url=token_url,
            process_url=process_url,
            verbose=verbose
        )
        
        array = client.get_landcover(
            lat, lon, collection_id,
            year=year,
            buffer_m=buffer_m,
            chip_px=chip_px
        )
    
    # Save to cache
    cache_path = processor.save_geotiff(array, lat, lon, year, buffer_m, chip_px)
    
    if verbose:
        print(f"✓ Saved to cache: {cache_path.name}")
    
    return cache_path
