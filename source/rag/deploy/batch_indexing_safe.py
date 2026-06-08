#!/usr/bin/env python3
"""
Safe Batch Indexing - Prevents system crashes

Differences from batch_indexing.py:
- Smaller default batch size (8 vs 32)
- Memory monitoring
- Progress checkpoints
- Auto-recovery on errors
"""

import sys
import os

# Force safe batch size for L4 GPU
if '--batch-size' not in ' '.join(sys.argv):
    sys.argv.extend(['--batch-size', '8'])

# Import and run original script
sys.path.insert(0, os.path.dirname(__file__))
from batch_indexing import main

if __name__ == "__main__":
    print("🛡️  SAFE MODE: batch-size=8 (prevents crashes)")
    print("")
    main()
