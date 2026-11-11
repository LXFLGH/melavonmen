#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mcp/install.py — 便捷入口，调用 scripts/install_harness.py"""
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

from install_harness import main

if __name__ == "__main__":
    main()
