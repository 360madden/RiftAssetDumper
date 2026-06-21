#!/usr/bin/env python3
"""Semantic category loader for scene manifests and RiftFlythrough delivery.

Cycle 5 surface: read bounded asset-semantic-index/v1 matrix reports from
``Exports/discovery-matrix/nif-semantic-hints/`` and join asset_ids to
semantic hint categories (``hint:map-zone``, ``hint:actor-object``,
``hint:waypoint-poi``). The matrix is produced via
``python scripts/rift_asset_discovery_matrix.py`` (see
``scripts/discovery-matrices/nif-semantic-hints.json`` for the job specs).

Each matrix file is schema-validated against
``docs/schemas/asset-semantic-index-v1.schema.json`` and contains an
``Entries[]`` array; each entry has a 16-char hex ``AssetIdPrefix`` (join
key) and a ``SemanticCategories[]`` list (multi-tag).

One matrix report = one targeted hint filter, but entries may carry more
than one hint tag in their ``SemanticCategories`` list. The loader returns
the union of per-matrix hints for each asset_id, never more than the
configured set of three (one hint per matrix file). The matrix files are
promoted, not parsed: a hint category is only ever set for an asset if
that asset appears in the corresponding matrix report.

This module is purely read-only: it never writes output, never spawns
dotnet, and never crashes on missing files. Empty / missing matrices
degrade to ``categories=[]``, ``sources={}``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

# Fixed hint-set shipped by Cycle 5.  Adding a new hint here is a wire-format
# extension; consumers (RiftFlythrough renderer) need to know about the new
# tag.  Keep this list in sync with the matrix jobs in
# ``scripts/discovery-matrices/nif-semantic-hints.json``.
HINTS: tuple[str, ...] = ("hint:actor-object", "hint:map-zone", "hint:waypoint-poi")

# Sentinel value emitted in ``sources`` map entries when a matrix report is
# missing.  Exported so consumers / tests don't hardcode the literal.
ABSENT_MARKER: str = "<absent>"

# Path conventions (all under gitignored ``Exports/``).  None of the inputs
# are tracked and the loader never writes to them.
DEFAULT_MATRIX_DIR = REPO_ROOT / "Exports" / "discovery-matrix" / "nif-semantic-hints"
MATRIX_FILE_NAMES: dict[str, str] = {
    "hint:actor-object": "semantic-nif-actor-object.json",
    "hint:map-zone": "semantic-nif-map-zone.json",
    "hint:waypoint-poi": "semantic-nif-waypoint-poi.json",
}

# Source path style emitted in scene-manifest ``semantic.sources``.  Emitting
# just the basename keeps the manifest free of absolute paths and avoids
# leaking repo-layout, while still letting a consumer trace the matrix file
# to its type (``semantic-nif-<category>.json`` is unambiguous).
SOURCE_BASENAME_ONLY: bool = True


def _matrix_path(hint: str, matrix_dir: Path = DEFAULT_MATRIX_DIR) -> Path:
    """Return the matrix JSON path for one hint category."""
    name = MATRIX_FILE_NAMES.get(hint)
    if name is None:
        raise ValueError(
            f"SemanticSurface: unsupported hint {hint!r}; valid hints: {sorted(MATRIX_FILE_NAMES)}"
        )
    return matrix_dir / name


def load_matrix(hint: str, matrix_dir: Path = DEFAULT_MATRIX_DIR) -> list[dict[str, Any]]:
    """Load the Entries[] list for one hint's matrix file.

    Returns an empty list when the matrix file is missing or unreadable.
    The matrix schema (``asset-semantic-index/v1``) requires ``Entries``
    to be a list, so the loader never raises on malformed input -- it
    degrades to ``[]`` so callers can build empty Categories output
    without try/except.
    """
    path = _matrix_path(hint, matrix_dir)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return []
    entries = data.get("Entries")
    if not isinstance(entries, list):
        return []
    return entries


def load_all_matrices(matrix_dir: Path = DEFAULT_MATRIX_DIR) -> dict[str, list[dict[str, Any]]]:
    """Load all hint matrix reports from ``matrix_dir``.

    Returns a ``{hint: entries[] }`` mapping for every supported hint.
    Missing / empty matrices degrade to ``[]`` entries (not a failure).
    """
    return {hint: load_matrix(hint, matrix_dir) for hint in HINTS}


def categorize_asset(
    asset_id: str, matrices: dict[str, list[dict[str, Any]]] | None = None
) -> list[str]:
    """Return the union of hint categories an asset appears under.

    Each ``hint:*`` matrix report is filtered to ``asset_id`` prefix
    matches (``AssetIdPrefix`` is a 16-char hex).  An asset that appears in
    multiple hint reports gets all its hints in the result (deduplicated,
    order = ``HINTS`` tuple order).  An asset missing from all matrices
    returns ``[]``.

    The loader treats ``AssetIdPrefix`` as a join key; entries with
    mismatched / missing prefixes are ignored.  Casing is preserved.
    """
    if not asset_id:
        # Early-return before any disk work; an empty id can never match.
        return []
    if matrices is None:
        matrices = load_all_matrices()
    found: list[str] = []
    for hint in HINTS:
        entries = matrices.get(hint) or []
        if any(str(e.get("AssetIdPrefix", "")).lower() == asset_id.lower() for e in entries):
            found.append(hint)
    return found


def build_semantic_block(asset_id: str, matrix_dir: Path = DEFAULT_MATRIX_DIR) -> dict[str, Any]:
    """Build the ``semantic`` sub-record for one asset_id.

    Returns a dict with:
      - ``categories``: ordered list of hint strings (subset of ``HINTS``)
      - ``sources``: ordered ``{hint: matrix-source-path}`` mapping for
        every hint whose matrix file exists (even one with 0 entries), or
        :data:`ABSENT_MARKER` when the report is missing on disk.  Source
        paths use the matrix basename only (``SOURCE_BASENAME_ONLY``) so
        manifests stay free of absolute paths and don't leak repo layout.

    Always returns the contract: ``{"categories": [], "sources": {...}}``,
    even when ``matrix_dir`` does not exist.
    """
    categories: list[str] = []
    sources: dict[str, str] = {}
    inputs = load_all_matrices(matrix_dir)
    for hint in HINTS:
        rel_path = _matrix_path(hint, matrix_dir)
        if not rel_path.exists():
            # Matrix file is missing entirely on disk (fresh clone, partial
            # scan, or test fixture).  Signal the absence to consumers via
            # the well-known sentinel so they can distinguish "scanned but
            # absent" from "not scanned".
            sources[hint] = ABSENT_MARKER
            continue
        # Always emit the basename (unambiguous: one file per hint).  Avoids
        # leaking absolute paths and keeps the manifest portable across
        # clones that relocate the ``Exports/`` tree.
        sources[hint] = rel_path.name if SOURCE_BASENAME_ONLY else str(rel_path)
        entries = inputs.get(hint) or []
        if any(str(e.get("AssetIdPrefix", "")).lower() == asset_id.lower() for e in entries):
            categories.append(hint)
    return {"categories": categories, "sources": sources}


__all__ = [
    "HINTS",
    "ABSENT_MARKER",
    "MATRIX_FILE_NAMES",
    "DEFAULT_MATRIX_DIR",
    "SOURCE_BASENAME_ONLY",
    "load_matrix",
    "load_all_matrices",
    "categorize_asset",
    "build_semantic_block",
]
