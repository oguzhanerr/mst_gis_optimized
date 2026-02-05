"""
Formatting module for the radio propagation pipeline.

Handles:
- Formatting enriched receiver data for P.1812-6 model input
- Grouping points by azimuth into profiles
- CSV export with semicolon delimiter
"""

from pathlib import Path
from typing import List, Dict, Any, Tuple

import geopandas as gpd
import pandas as pd
import numpy as np

from mst_gis.utils.logging import Timer, print_success, print_warning
from mst_gis.utils.validation import ValidationError, validate_geodataframe_columns


class ProfileFormatter:
    """Format and export P.1812-6 profiles."""
    
    def __init__(self, receivers_gdf: gpd.GeoDataFrame):
        """
        Initialize formatter.
        
        Args:
            receivers_gdf: Enriched GeoDataFrame with elevation, landcover, zone data
        """
        self.receivers_gdf = receivers_gdf
        self.profiles = []
    
    def format_profiles(
        self,
        frequency_ghz: float,
        time_percentage: int,
        polarization: int,
        htg: float,
        hrg: float,
    ) -> List[Dict[str, Any]]:
        """
        Format receiver points into profiles grouped by azimuth.
        
        Creates one profile per azimuth, with all distance points along that
        azimuth forming a single profile for P.1812-6 processing.
        
        Args:
            frequency_ghz: Frequency in GHz (0.03-6)
            time_percentage: Time percentage (1-50)
            polarization: Polarization (1=horizontal, 2=vertical)
            htg: TX antenna height above ground (m)
            hrg: RX antenna height above ground (m)
            
        Returns:
            List of profile dictionaries with P.1812 format
            
        Raises:
            ValidationError: If inputs are invalid
        """
        # Validate inputs
        if not isinstance(self.receivers_gdf, gpd.GeoDataFrame):
            raise ValidationError("receivers_gdf must be a GeoDataFrame")
        
        required_cols = ["geometry", "azimuth_deg", "distance_km", "h", "Ct", "R", "zone"]
        validate_geodataframe_columns(self.receivers_gdf, required_cols)
        
        if not 0.03 <= frequency_ghz <= 6:
            raise ValidationError(f"Frequency must be 0.03-6 GHz, got {frequency_ghz}")
        
        if not 1 <= time_percentage <= 50:
            raise ValidationError(f"Time percentage must be 1-50%, got {time_percentage}")
        
        if polarization not in (1, 2):
            raise ValidationError(f"Polarization must be 1 or 2, got {polarization}")
        
        profiles = []
        
        # Get unique azimuths (excluding NaN for transmitter point)
        azimuths = sorted(self.receivers_gdf['azimuth_deg'].dropna().unique())
        
        for azimuth in azimuths:
            # Get all points for this azimuth, sorted by distance
            subset = self.receivers_gdf[
                self.receivers_gdf['azimuth_deg'] == azimuth
            ].sort_values('distance_km')
            
            if len(subset) == 0:
                continue
            
            # Extract arrays for this profile
            distances = subset['distance_km'].tolist()
            heights = [int(round(h)) if not pd.isna(h) else 0 for h in subset['h'].tolist()]
            r_values = subset['R'].tolist()
            ct_values = subset['Ct'].tolist()
            zones = subset['zone'].tolist()
            
            # Get TX/RX coordinates (first and last points on the profile)
            geom_0 = subset.geometry.iloc[0]
            geom_last = subset.geometry.iloc[-1]
            
            profile = {
                'f': frequency_ghz,
                'p': time_percentage,
                'd': distances,
                'h': heights,
                'R': r_values,
                'Ct': ct_values,
                'zone': zones,
                'htg': htg,
                'hrg': hrg,
                'pol': polarization,
                'phi_t': float(geom_0.y),
                'phi_r': float(geom_last.y),
                'lam_t': float(geom_0.x),
                'lam_r': float(geom_last.x),
                'azimuth': float(azimuth),
            }
            
            profiles.append(profile)
        
        self.profiles = profiles
        return profiles
    
    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert profiles to DataFrame.
        
        Returns:
            DataFrame with one row per profile
        """
        if not self.profiles:
            raise ValidationError("No profiles formatted yet. Call format_profiles() first.")
        
        return pd.DataFrame(self.profiles)
    
    def export_csv(self, output_path: Path) -> Path:
        """
        Export profiles to semicolon-delimited CSV.
        
        Args:
            output_path: Path to output CSV file
            
        Returns:
            Path to saved file
        """
        if not self.profiles:
            raise ValidationError("No profiles formatted yet. Call format_profiles() first.")
        
        df = self.to_dataframe()
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        df.to_csv(
            output_path,
            sep=';',
            index=False,
            decimal='.',
        )
        
        return output_path


def format_and_export_profiles(
    receivers_gdf: gpd.GeoDataFrame,
    output_path: Path,
    frequency_ghz: float,
    time_percentage: int,
    polarization: int,
    htg: float,
    hrg: float,
    verbose: bool = True,
) -> Tuple[pd.DataFrame, Path]:
    """
    Format enriched receiver data and export to CSV for P.1812-6 processing.
    
    Groups all points by azimuth, creating one profile per azimuth direction.
    Each profile contains all distance points along that azimuth, formatted
    as semicolon-delimited CSV.
    
    Args:
        receivers_gdf: Enriched GeoDataFrame (from Phase 3)
        output_path: Path to output CSV file
        frequency_ghz: Frequency in GHz
        time_percentage: Time percentage (%)
        polarization: Polarization (1=horizontal, 2=vertical)
        htg: TX antenna height above ground (m)
        hrg: RX antenna height above ground (m)
        verbose: Print progress updates
        
    Returns:
        Tuple of (DataFrame with profiles, Path to CSV file)
        
    Raises:
        ValidationError: If inputs are invalid
    """
    if verbose:
        print("\n" + "=" * 60)
        print("PHASE 4: POST-PROCESSING & EXPORT")
        print("=" * 60)
        print(f"\nFormatting {len(receivers_gdf)} points for P.1812...")
    
    formatter = ProfileFormatter(receivers_gdf)
    
    with Timer("Format profiles"):
        profiles = formatter.format_profiles(
            frequency_ghz,
            time_percentage,
            polarization,
            htg,
            hrg,
        )
    
    if verbose:
        azimuths = sorted(receivers_gdf['azimuth_deg'].dropna().unique())
        print(f"\nProcessing {len(azimuths)} azimuths...")
        print(f"✓ Formatted {len(profiles)} profiles")
    
    # Export to CSV
    with Timer("Export to CSV"):
        output_path = formatter.export_csv(output_path)
    
    if verbose:
        file_size = output_path.stat().st_size / 1024
        print(f"\nExporting profiles to CSV...")
        print(f"✓ Saved {len(profiles)} profiles to {output_path}")
        print(f"\nFile size: {file_size:.1f} KB")
        print(f"Columns: {list(formatter.to_dataframe().columns)}")
        
        # Show sample profile
        df_profiles = formatter.to_dataframe()
        sample = df_profiles.iloc[0]
        print(f"\nFirst profile (azimuth {sample['azimuth']:.1f}°):")
        print(f"  TX: ({sample['phi_t']:.4f}, {sample['lam_t']:.4f})")
        print(f"  RX: ({sample['phi_r']:.4f}, {sample['lam_r']:.4f})")
        print(f"  Frequency: {sample['f']} GHz")
        print(f"  Time %: {sample['p']}%")
        print(f"  Antenna heights: TX={sample['htg']}m, RX={sample['hrg']}m")
        print(f"  Distance points: {len(sample['d'])}")
        print(f"  Height range: {min(sample['h'])}-{max(sample['h'])}m")
        print(f"  Ct classes: {set(sample['Ct'])}")
        
        print(f"\n" + "=" * 60)
        print("PHASE 4 COMPLETE: Export ready for batch processing")
        print("=" * 60)
        print(f"\nOutput file: {output_path}")
        print(f"Ready to run: python scripts/run_batch_processor.py")
    
    return formatter.to_dataframe(), output_path


def validate_csv_profiles(csv_path: Path) -> Dict[str, Any]:
    """
    Validate exported CSV profiles.
    
    Args:
        csv_path: Path to CSV file
        
    Returns:
        Dictionary with validation results
    """
    df = pd.read_csv(csv_path, sep=';')
    
    results = {
        'num_profiles': len(df),
        'azimuths': sorted(df['azimuth'].unique()),
        'distance_range': (
            min([len(eval(d)) for d in df['d']]),
            max([len(eval(d)) for d in df['d']]),
        ),
        'frequencies': df['f'].unique(),
        'time_percentages': df['p'].unique(),
        'polarizations': df['pol'].unique(),
        'antenna_heights_tx': df['htg'].unique(),
        'antenna_heights_rx': df['hrg'].unique(),
    }
    
    return results
