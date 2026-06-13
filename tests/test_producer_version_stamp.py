#!/usr/bin/env python3
"""Behavior tests for the RiftAssetDumper producer-version stamp.

Regression for the v1.0.0 consumer-pin durability layer: validates that the
producer-version stamp (`Producer: RiftAssetDumper <version>`) actually lands
in the generated output headers, not just that the source mentions the helper.

4 behavior tests, no source-grep, no tautological meta-tests:

1. `test_producer_version_returns_valid_string` — `producer_version()` returns
   a non-empty string in valid format (tag-based `v...` or SHA-like hex).

2. `test_build_world_placed_merge_obj_header_contains_producer_version` —
   `_build_obj_header(N)` returns a header with both `Producer: RiftAssetDumper`
   and the expected asset count. Catches a future refactor that removes the
   producer line from the header.

3. `test_build_texture_map_emits_producer_version_in_js_header` —
   `generate_texture_map_js({})` returns JS content with
   `Producer: RiftAssetDumper` in its first 5 lines. Catches a future refactor
   that removes the producer line from the JS empty-map path.

4. `test_build_texture_map_populated_path_emits_producer_version_in_js_header` —
   Same as test 3 but exercises the populated-path code branch with a minimal
   1-entry index. Catches a future refactor that drops the producer line from
   one path but not the other.

A future refactor that drops the producer-version stamp from either output
file will fail test 2, 3, or 4.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def test_producer_version_returns_valid_string() -> None:
    """rift_workflow_utils.producer_version() returns a non-empty, well-formed string."""
    from rift_workflow_utils import producer_version

    v = producer_version()
    assert v, "producer_version() returned empty"
    # Valid format: tag-based ("v...") or SHA-like hex string (no tag)
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
    # Sanity: the header should be a comment block (every line starts with '#')
    assert all(line.startswith("#") for line in header if line.strip()), (
        f"OBJ header lines should all be comments (start with '#'):\n{header}"
    )


def test_build_texture_map_emits_producer_version_in_js_header() -> None:
    """generate_texture_map_js({}) emits the producer-version line in the JS header."""
    from build_texture_map import generate_texture_map_js

    js = generate_texture_map_js({"assets": {}})  # empty index → empty-map path
    first_5_lines = js.splitlines()[:5]
    assert any("Producer: RiftAssetDumper" in line for line in first_5_lines), (
        "missing 'Producer: RiftAssetDumper' in first 5 JS lines:\n" + "\n".join(first_5_lines)
    )


def test_build_texture_map_populated_path_emits_producer_version_in_js_header() -> None:
    """generate_texture_map_js(index) with 1 entry also emits the producer-version line.

    Mirrors the empty-path test (test 3) but exercises the populated-path code
    branch in generate_texture_map_js. Catches a future refactor that
    accidentally drops the producer-version stamp from one of the 2 paths.
    """
    from build_texture_map import generate_texture_map_js

    index = {"assets": {"abc123def4567890": {"linked_textures": ["x.png"]}}}
    js = generate_texture_map_js(index)
    first_5_lines = js.splitlines()[:5]
    assert any("Producer: RiftAssetDumper" in line for line in first_5_lines), (
        "missing 'Producer: RiftAssetDumper' in first 5 JS lines (populated path):\n" + "\n".join(first_5_lines)
    )


if __name__ == "__main__":
    test_producer_version_returns_valid_string()
    test_build_world_placed_merge_obj_header_contains_producer_version()
    test_build_texture_map_emits_producer_version_in_js_header()
    test_build_texture_map_populated_path_emits_producer_version_in_js_header()
    print("All 4 behavior tests passed!")
