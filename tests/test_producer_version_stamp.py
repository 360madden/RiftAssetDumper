#!/usr/bin/env python3
"""Behavior tests for the RiftAssetDumper producer-version stamp.

Regression for the v1.0.0 consumer-pin durability layer: validates that the
producer-version stamp (`Producer: RiftAssetDumper <version>`) actually lands
in the generated output headers, not just that the source mentions the helper.

3 test functions, 4 effective cases (test 3 is parametrized over 2 inputs),
no source-grep, no tautological meta-tests:

1. `test_producer_version_returns_valid_string` — `producer_version()` returns
   a non-empty string in valid format (tag-based `v...` or SHA-like hex).

2. `test_build_world_placed_merge_obj_header_contains_producer_version` —
   `_build_obj_header(N)` returns a header with both `Producer: RiftAssetDumper`
   and the expected asset count. Catches a future refactor that removes the
   producer line from the header.

3. `test_build_texture_map_emits_producer_version_in_js_header[empty|populated]`
   — parametrized over the empty-index and populated-index code branches of
   `generate_texture_map_js`. Catches a future refactor that drops the
   producer line from one path but not the other. Adding a new path (e.g.,
   bulk_export_for_flythrough.py header stamp) costs 1 new parametrize case.

A future refactor that drops the producer-version stamp from either output
file will fail test 2 or 3.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def test_producer_version_returns_valid_string() -> None:
    """rift_workflow_utils.producer_version() returns a non-empty, well-formed string."""
    from rift_workflow_utils import producer_version

    v = producer_version()
    assert v, "producer_version() returned empty"
    is_tag_based = v.startswith("v") and any(c.isdigit() for c in v)
    is_sha_like = all(c in "0123456789abcdef" for c in v)
    assert is_tag_based or is_sha_like, (
        f"producer_version() returned unexpected format: {v!r} (expected tag-based 'v...' or SHA-like hex)"
    )


def test_build_world_placed_merge_obj_header_contains_producer_version() -> None:
    """_build_obj_header(N) emits the producer-version line in the OBJ header."""
    from build_world_placed_merge import _build_obj_header

    header = _build_obj_header(217)
    text = "".join(header)
    assert "Producer: RiftAssetDumper" in text, f"missing 'Producer: RiftAssetDumper' in OBJ header:\n{text}"
    assert "217 assets indexed" in text, f"missing '217 assets indexed' in OBJ header:\n{text}"
    assert all(line.startswith("#") for line in header if line.strip()), (
        f"OBJ header lines should all be comments (start with '#'):\n{header}"
    )


@pytest.mark.parametrize(
    "index",
    [
        pytest.param({"assets": {}}, id="empty"),
        pytest.param({"assets": {"abc123def4567890": {"linked_textures": ["x.png"]}}}, id="populated"),
    ],
)
def test_build_texture_map_emits_producer_version_in_js_header(index: dict[str, object]) -> None:
    """generate_texture_map_js(index) emits the producer-version line in the JS header.

    Parametrized over the empty-index and populated-index code branches.
    Catches a future refactor that drops the producer line from one path but
    not the other.
    """
    from build_texture_map import generate_texture_map_js

    js = generate_texture_map_js(index)
    first_5_lines = js.splitlines()[:5]
    assert any("Producer: RiftAssetDumper" in line for line in first_5_lines), (
        "missing 'Producer: RiftAssetDumper' in first 5 JS lines:\n" + "\n".join(first_5_lines)
    )


if __name__ == "__main__":
    test_producer_version_returns_valid_string()
    test_build_world_placed_merge_obj_header_contains_producer_version()
    test_build_texture_map_emits_producer_version_in_js_header({"assets": {}})
    test_build_texture_map_emits_producer_version_in_js_header(
        {"assets": {"abc123def4567890": {"linked_textures": ["x.png"]}}}
    )
    print("All 3 test functions passed (test 3 runs as 2 parametrized cases)!")
