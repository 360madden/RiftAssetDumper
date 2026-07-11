"""Pytest conftest — ensures scripts/ is on sys.path for bare module imports.

Some scripts (e.g., build_world_placed_merge.py) use bare imports like
``from rift_workflow_utils import producer_version`` which require the
``scripts/`` directory to be on ``sys.path``. When tests import these
modules via ``from scripts.foo import ...``, the bare import chain fails
because only the project root (``.``) is on the path (per pyproject.toml
``pythonpath = ["."]``).

This conftest adds ``scripts/`` to ``sys.path`` so those bare imports
resolve correctly during test collection.
"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
if _scripts_dir not in sys.path:
    sys.path.append(_scripts_dir)
