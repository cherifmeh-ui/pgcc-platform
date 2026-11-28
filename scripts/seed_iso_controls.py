#!/usr/bin/env python3
"""Safe wrapper for the canonical ISO control seed.

The backend seed performs validated upserts and preserves assessment fields.
This legacy root entrypoint delegates to it instead of deleting all controls.
"""
from __future__ import annotations

import asyncio
import runpy
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
SEED_SCRIPT = BACKEND / "scripts" / "seed_iso_controls.py"

if __name__ == "__main__":
    sys.path.insert(0, str(BACKEND))
    namespace = runpy.run_path(str(SEED_SCRIPT))
    asyncio.run(namespace["seed"]())
