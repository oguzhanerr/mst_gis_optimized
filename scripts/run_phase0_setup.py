#!/usr/bin/env python
"""
Command-line entry point for Phase 0 setup.

Creates directory structure and validates configuration.

Usage:
    python scripts/run_phase0_setup.py
    python scripts/run_phase0_setup.py --config config.json
    python scripts/run_phase0_setup.py --project-root /path/to/project
"""

import argparse
import sys
from pathlib import Path

from mst_gis.pipeline.orchestration import PipelineOrchestrator


def main():
    """Parse arguments and run Phase 0."""
    parser = argparse.ArgumentParser(
        description="Run Phase 0: Setup and configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default config
  python scripts/run_phase0_setup.py
  
  # Run with custom config
  python scripts/run_phase0_setup.py --config my_config.json
  
  # Run with custom project root
  python scripts/run_phase0_setup.py --project-root /path/to/project
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
        orchestrator = PipelineOrchestrator(config_path=args.config)
        paths = orchestrator.run_phase0_setup(project_root=args.project_root)
        
        print("\n✓ Phase 0 complete")
        print("\nCreated directories:")
        for key, path in paths.items():
            if key != 'project_root':
                print(f"  {key}: {path}")
        
        print("\nNext steps:")
        print("  1. Run Phase 1: python scripts/run_phase1_dataprep.py")
        print("  2. Or run full pipeline: python scripts/run_full_pipeline.py")
        
        sys.exit(0)
    
    except KeyboardInterrupt:
        print("\n✗ Setup interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n✗ Setup error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
