#!/usr/bin/env python
"""
Command-line entry point for Phase 1 data preparation.

Downloads and caches land cover GeoTIFF from Sentinel Hub.

Usage:
    python scripts/run_phase1_dataprep.py --config config.json
    python scripts/run_phase1_dataprep.py --config config.json --cache-dir /path/to/cache
    python scripts/run_phase1_dataprep.py --config config.json --force-download
"""

import argparse
import sys
from pathlib import Path

from mst_gis.pipeline.orchestration import PipelineOrchestrator


def main():
    """Parse arguments and run Phase 1."""
    parser = argparse.ArgumentParser(
        description="Run Phase 1: Land cover data preparation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default config and cache
  python scripts/run_phase1_dataprep.py --config config.json
  
  # Run with custom cache directory
  python scripts/run_phase1_dataprep.py --config config.json --cache-dir /path/to/cache
  
  # Force re-download even if cached
  python scripts/run_phase1_dataprep.py --config config.json --force-download
        """,
    )
    
    parser.add_argument(
        '--config',
        type=Path,
        required=True,
        help='Path to config JSON or YAML file',
    )
    
    parser.add_argument(
        '--cache-dir',
        type=Path,
        default=None,
        help='Cache directory for GeoTIFF files (default: data/intermediate/api_data)',
    )
    
    parser.add_argument(
        '--force-download',
        action='store_true',
        help='Force re-download even if cached',
    )
    
    args = parser.parse_args()
    
    # Validate config path
    if not args.config.exists():
        print(f"Error: Config file not found: {args.config}")
        sys.exit(1)
    
    # Validate cache dir
    if args.cache_dir and not args.cache_dir.is_dir():
        print(f"Error: Cache directory is not a directory: {args.cache_dir}")
        sys.exit(1)
    
    try:
        orchestrator = PipelineOrchestrator(config_path=args.config)
        
        # Run Phase 0 first (setup)
        orchestrator.run_phase0_setup()
        
        # Run Phase 1 (data prep)
        lc_path = orchestrator.run_phase1_dataprep(landcover_cache_dir=args.cache_dir)
        
        print("\n✓ Phase 1 complete")
        print(f"\nLand cover GeoTIFF: {lc_path}")
        print(f"File size: {lc_path.stat().st_size / (1024*1024):.1f} MB")
        
        print("\nNext steps:")
        print("  1. Run Phase 2: python scripts/run_full_pipeline.py")
        print("  2. Or continue manually through Phase 4")
        
        sys.exit(0)
    
    except KeyboardInterrupt:
        print("\n✗ Data preparation interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n✗ Data preparation error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
