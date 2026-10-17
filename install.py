#!/usr/bin/env python3
"""Instalador para quien clonó el repo:  python install.py  (equivale a `astrax-install`)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from astrax_mcp.installer import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
