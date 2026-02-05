#!/usr/bin/env python
"""Entry point for batch processor - Run P1812 propagation analysis on terrain profiles."""

import sys
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mst_gis.propagation import batch_process


if __name__ == "__main__":
    print("Starting MST-GIS Batch Processor")
    print("=" * 50)
    batch_process()
    print("=" * 50)
    print("✅ Batch processing complete")
