"""
Orchestration module for the radio propagation pipeline.

Coordinates execution of all pipeline phases (0-4):
- Phase 0: Setup and configuration
- Phase 1: Land cover data preparation
- Phase 2: Batch receiver point generation
- Phase 3: Batch data extraction (elevation, landcover, zones)
- Phase 4: Formatting and CSV export

Provides a unified entry point for running the complete workflow.
"""

import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import geopandas as gpd
import pandas as pd

from mst_gis.pipeline.config import ConfigManager
from mst_gis.pipeline.data_preparation import prepare_landcover
from mst_gis.pipeline.point_generation import (
    Transmitter,
    generate_receiver_grid,
)
from mst_gis.pipeline.data_extraction import extract_data_for_receivers
from mst_gis.pipeline.formatting import format_and_export_profiles

from mst_gis.utils.logging import Timer, ProgressTracker, print_success, print_warning
from mst_gis.utils.validation import ValidationError


class PipelineOrchestrator:
    """Orchestrate execution of all pipeline phases."""
    
    def __init__(self, config_path: Optional[Path] = None, config_dict: Optional[Dict] = None):
        """
        Initialize orchestrator.
        
        Args:
            config_path: Path to config JSON/YAML file
            config_dict: Config dictionary (overrides config_path if provided)
        """
        self.config_manager = ConfigManager()
        
        if config_dict:
            self.config_manager.config = config_dict
            self.config_manager.validate()
        elif config_path:
            self.config_manager.load(config_path)
        
        self.config = self.config_manager.config
        
        # Track execution state
        self.state = {
            'phase0_complete': False,
            'phase1_complete': False,
            'phase2_complete': False,
            'phase3_complete': False,
            'phase4_complete': False,
        }
        
        # Store phase outputs
        self.phase0_paths = None
        self.phase1_landcover_path = None
        self.phase2_receivers_gdf = None
        self.phase3_enriched_gdf = None
        self.phase4_profiles_df = None
        self.phase4_csv_path = None
    
    def run_phase0_setup(
        self,
        project_root: Optional[Path] = None,
    ) -> Dict[str, Path]:
        """
        Phase 0: Setup and validate configuration.
        
        Args:
            project_root: Project root directory (auto-detected if None)
            
        Returns:
            Dictionary with setup paths
        """
        if not project_root:
            project_root = Path.cwd()
        
        print("\n" + "=" * 60)
        print("PHASE 0: SETUP & CONFIGURATION")
        print("=" * 60)
        
        # Create necessary directories
        with Timer("Create directories"):
            paths = {
                'project_root': project_root,
                'input_dir': project_root / 'data' / 'input',
                'intermediate_dir': project_root / 'data' / 'intermediate',
                'output_dir': project_root / 'data' / 'output',
                'api_data_dir': project_root / 'data' / 'intermediate' / 'api_data',
                'workflow_dir': project_root / 'data' / 'intermediate' / 'workflow',
                'profiles_dir': project_root / 'data' / 'input' / 'profiles',
                'reference_dir': project_root / 'data' / 'input' / 'reference',
            }
            
            for key, path in paths.items():
                if key != 'project_root':
                    path.mkdir(parents=True, exist_ok=True)
        
        print_success("Setup complete")
        print(f"  Project root: {paths['project_root']}")
        
        self.phase0_paths = paths
        self.state['phase0_complete'] = True
        
        return paths
    
    def run_phase1_dataprep(
        self,
        landcover_cache_dir: Optional[Path] = None,
    ) -> Path:
        """
        Phase 1: Prepare land cover data from Sentinel Hub.
        
        Args:
            landcover_cache_dir: Cache directory for GeoTIFFs (optional)
            
        Returns:
            Path to cached land cover GeoTIFF
        """
        if not self.state['phase0_complete']:
            raise ValidationError("Phase 0 must complete before Phase 1")
        
        print("\n" + "=" * 60)
        print("PHASE 1: LAND COVER DATA PREPARATION")
        print("=" * 60)
        
        if not landcover_cache_dir:
            landcover_cache_dir = self.phase0_paths['api_data_dir']
        
        # Get Sentinel Hub credentials from config
        sentinel_config = self.config['SENTINEL_HUB']
        transmitter_config = self.config['TRANSMITTER']
        
        try:
            lc_path = prepare_landcover(
                lat=transmitter_config['latitude'],
                lon=transmitter_config['longitude'],
                cache_dir=landcover_cache_dir,
                client_id=sentinel_config['client_id'],
                client_secret=sentinel_config['client_secret'],
                token_url=sentinel_config['token_url'],
                process_url=sentinel_config['process_url'],
                collection_id=sentinel_config['collection_id'],
                year=sentinel_config['year'],
                buffer_m=sentinel_config['buffer_m'],
                chip_px=sentinel_config['chip_px'],
                verbose=True,
            )
            
            self.phase1_landcover_path = lc_path
            self.state['phase1_complete'] = True
            print_success("Land cover preparation complete")
            
            return lc_path
        
        except Exception as e:
            print_warning(f"Phase 1 failed: {e}")
            raise
    
    def run_phase2_generation(self) -> gpd.GeoDataFrame:
        """
        Phase 2: Generate receiver points.
        
        Returns:
            GeoDataFrame with receiver points
        """
        if not self.state['phase0_complete']:
            raise ValidationError("Phase 0 must complete before Phase 2")
        
        print("\n" + "=" * 60)
        print("PHASE 2: BATCH POINT GENERATION")
        print("=" * 60)
        
        # Get configuration
        tx_config = self.config['TRANSMITTER']
        rx_config = self.config['RECEIVER_GENERATION']
        
        # Create transmitter
        transmitter = Transmitter(
            tx_id=tx_config['tx_id'],
            lon=tx_config['longitude'],
            lat=tx_config['latitude'],
            htg=tx_config['antenna_height_tx'],
            f=self.config['P1812']['frequency_ghz'],
            pol=self.config['P1812']['polarization'],
            p=self.config['P1812']['time_percentage'],
            hrg=tx_config['antenna_height_rx'],
        )
        
        with Timer("Generate receiver grid"):
            receivers_gdf = generate_receiver_grid(
                tx=transmitter,
                max_distance_km=rx_config['max_distance_km'],
                distance_step_km=rx_config['distance_step_km'],
                num_azimuths=rx_config['num_azimuths'],
                include_tx_point=True,
            )
        
        print(f"\n✓ Generated {len(receivers_gdf)} receiver points")
        
        self.phase2_receivers_gdf = receivers_gdf
        self.state['phase2_complete'] = True
        
        return receivers_gdf
    
    def run_phase3_extraction(self, dem_path: Optional[Path] = None) -> gpd.GeoDataFrame:
        """
        Phase 3: Extract elevation, land cover, and zone data.
        
        Args:
            dem_path: Path to DEM VRT (auto-detected in cache if None)
            
        Returns:
            Enriched GeoDataFrame with extracted data
        """
        if not self.state['phase2_complete']:
            raise ValidationError("Phase 2 must complete before Phase 3")
        
        print("\n" + "=" * 60)
        print("PHASE 3: BATCH DATA EXTRACTION")
        print("=" * 60)
        
        # Locate DEM
        if not dem_path:
            cache_dir = Path.home() / '.cache' / 'elevation'
            dem_path = cache_dir / 'SRTM1' / 'SRTM1.vrt'
        
        # Use Phase 1 landcover if available
        landcover_path = self.phase1_landcover_path
        if not landcover_path:
            print_warning("Phase 1 not complete; attempting to locate cached landcover")
            # Auto-detect from cache
            tx_config = self.config['TRANSMITTER']
            sh_config = self.config['SENTINEL_HUB']
            lat = tx_config['latitude']
            lon = tx_config['longitude']
            year = sh_config['year']
            buffer_m = sh_config['buffer_m']
            chip_px = sh_config['chip_px']
            landcover_path = self.phase0_paths['api_data_dir'] / (
                f"lcm10_{lat}_{lon}_{year}_buf{buffer_m}m_{chip_px}px.tif"
            )
        
        # Get zones path
        zones_path = self.phase0_paths['reference_dir'] / 'zones_map_BR.json'
        
        # Extract data
        enriched_gdf = extract_data_for_receivers(
            receivers_gdf=self.phase2_receivers_gdf,
            dem_path=dem_path,
            landcover_path=landcover_path,
            zones_path=zones_path,
            lcm10_to_ct=self.config['LCM10_TO_CT'],
            ct_to_r=self.config['CT_TO_R'],
            verbose=True,
        )
        
        self.phase3_enriched_gdf = enriched_gdf
        self.state['phase3_complete'] = True
        
        return enriched_gdf
    
    def run_phase4_export(self, output_path: Optional[Path] = None) -> Tuple[pd.DataFrame, Path]:
        """
        Phase 4: Format and export to CSV for P.1812 processing.
        
        Args:
            output_path: Path to output CSV (auto-generated if None)
            
        Returns:
            Tuple of (profiles DataFrame, path to CSV file)
        """
        if not self.state['phase3_complete']:
            raise ValidationError("Phase 3 must complete before Phase 4")
        
        print("\n" + "=" * 60)
        print("PHASE 4: POST-PROCESSING & EXPORT")
        print("=" * 60)
        
        if not output_path:
            max_dist = self.config['RECEIVER_GENERATION']['max_distance_km']
            output_path = self.phase0_paths['profiles_dir'] / f"paths_oneTx_manyRx_{max_dist}km.csv"
        
        df_profiles, csv_path = format_and_export_profiles(
            receivers_gdf=self.phase3_enriched_gdf,
            output_path=output_path,
            frequency_ghz=self.config['P1812']['frequency_ghz'],
            time_percentage=self.config['P1812']['time_percentage'],
            polarization=self.config['P1812']['polarization'],
            htg=self.config['TRANSMITTER']['antenna_height_tx'],
            hrg=self.config['TRANSMITTER']['antenna_height_rx'],
            verbose=True,
        )
        
        self.phase4_profiles_df = df_profiles
        self.phase4_csv_path = csv_path
        self.state['phase4_complete'] = True
        
        return df_profiles, csv_path
    
    def run_full_pipeline(
        self,
        project_root: Optional[Path] = None,
        skip_phase1: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute full pipeline (Phases 0-4).
        
        Args:
            project_root: Project root directory
            skip_phase1: Skip Phase 1 (land cover download) if True
            
        Returns:
            Dictionary with all phase outputs and timing info
        """
        start_time = time.time()
        
        print("\n" + "=" * 70)
        print("FULL PIPELINE EXECUTION")
        print("=" * 70)
        
        try:
            # Phase 0: Setup
            paths = self.run_phase0_setup(project_root)
            
            # Phase 1: Data preparation (optional)
            if not skip_phase1:
                self.run_phase1_dataprep()
            else:
                print("\n(Skipping Phase 1)")
                self.state['phase1_complete'] = True
            
            # Phase 2: Generate points
            self.run_phase2_generation()
            
            # Phase 3: Extract data
            self.run_phase3_extraction()
            
            # Phase 4: Export
            self.run_phase4_export()
            
            total_time = time.time() - start_time
            
            print("\n" + "=" * 70)
            print("FULL PIPELINE COMPLETE")
            print("=" * 70)
            print(f"\nTotal execution time: {total_time:.1f}s")
            print(f"\nOutputs:")
            print(f"  • Receivers GeoDataFrame: {len(self.phase2_receivers_gdf)} points")
            print(f"  • Enriched GeoDataFrame: {len(self.phase3_enriched_gdf)} points")
            print(f"  • Profiles CSV: {self.phase4_csv_path}")
            print(f"\nNext: Run P.1812-6 batch processor on {self.phase4_csv_path}")
            
            return {
                'success': True,
                'total_time': total_time,
                'paths': paths,
                'receivers_gdf': self.phase2_receivers_gdf,
                'enriched_gdf': self.phase3_enriched_gdf,
                'profiles_df': self.phase4_profiles_df,
                'csv_path': self.phase4_csv_path,
            }
        
        except Exception as e:
            print_warning(f"\nPipeline execution failed: {e}")
            raise


def run_pipeline(
    config_path: Optional[Path] = None,
    config_dict: Optional[Dict] = None,
    project_root: Optional[Path] = None,
    skip_phase1: bool = False,
) -> Dict[str, Any]:
    """
    Run complete radio propagation pipeline.
    
    Convenience function for executing the full workflow.
    
    Args:
        config_path: Path to config JSON/YAML file
        config_dict: Config dictionary (overrides config_path)
        project_root: Project root directory (auto-detected if None)
        skip_phase1: Skip Phase 1 (land cover download)
        
    Returns:
        Dictionary with all outputs and results
    """
    orchestrator = PipelineOrchestrator(config_path=config_path, config_dict=config_dict)
    
    return orchestrator.run_full_pipeline(
        project_root=project_root,
        skip_phase1=skip_phase1,
    )
