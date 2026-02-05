#!/usr/bin/env python
"""
Command-line entry point for full radio propagation pipeline.

Executes phases 0-4 with configuration from file or CLI arguments.

Usage:
    python scripts/run_full_pipeline.py --config config.json
    python scripts/run_full_pipeline.py --config config.yaml --project-root /path/to/project
    python scripts/run_full_pipeline.py --skip-phase1
"""

import argparse
import sys
from pathlib import Path

from mst_gis.pipeline.orchestration import run_pipeline


def main():
    """Parse arguments and run pipeline."""
    parser = argparse.ArgumentParser(
        description="Run full radio propagation pipeline (Phases 0-4)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default config
  python scripts/run_full_pipeline.py
  
  # Run with custom config
  python scripts/run_full_pipeline.py --config my_config.json
  
  # Run with custom project root
  python scripts/run_full_pipeline.py --project-root /path/to/project
  
  # Skip Phase 1 (land cover download)
  python scripts/run_full_pipeline.py --skip-phase1
        """,
    )
    
    parser.add_argument(
        '--config',
        type=Path,
        default=None,
        help='Path to config JSON or YAML file (default: use DEFAULT_CONFIG)',
    )
    
    parser.add_argument(
        '--project-root',
        type=Path,
        default=None,
        help='Project root directory (default: current directory)',
    )
    
    parser.add_argument(
        '--skip-phase1',
        action='store_true',
        help='Skip Phase 1 (land cover download)',
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        default=True,
        help='Print progress updates (default: True)',
    )
    
    args = parser.parse_args()
    
    # Validate config path
    if args.config and not args.config.exists():
        print(f"Error: Config file not found: {args.config}")
        sys.exit(1)
    
    # Validate project root
    if args.project_root and not args.project_root.is_dir():
        print(f"Error: Project root is not a directory: {args.project_root}")
        sys.exit(1)
    
    try:
        result = run_pipeline(
            config_path=args.config,
            project_root=args.project_root,
            skip_phase1=args.skip_phase1,
        )
        
        if result['success']:
            print("\n✓ Pipeline completed successfully")
            print(f"\nOutput CSV: {result['csv_path']}")
            sys.exit(0)
        else:
            print("\n✗ Pipeline failed")
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n✗ Pipeline interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n✗ Pipeline error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
