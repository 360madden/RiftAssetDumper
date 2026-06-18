"""Tests for `scripts/build_riftflythrough_delivery.py` (delivery-authoritative textures, v0.2).

Covers the v0.2 contract:
  * No absolute Windows paths leak into the emitted JSON (privacy + browser-portable).
  * `linked_texture_urls` are well-formed, consumer-consumable URLs keyed by 16-hex hash.
  * Producer version / schema stamp is correct (no doubled `v`).
  * Legacy dead-path fields (`obj_path`/`world_json`) are absent from entries.

Follows the `test_build_cycle_2_cohort.py` pattern: subprocess smoke + skipif
guards on generated (gitignored) data not being present locally.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "build_riftflythrough_delivery.py"
# Output lives under the canonical nested Assets/Assets/ data tree (gitignored).
DELIVERY_JSON = (
    REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage8" / "riftflythrough-delivery.json"
)
STAGE6_DIR = REPO_ROOT / "Assets" / "Exports" / "discovery-plan" / "cycle-2" / "stage6"

DRIVE_PATH_RE = re.compile(r"[A-Za-z]:\\")
HEX16_RE = re.compile(r"^[0-9a-f]{16}$")


def test_help_exits_zero() -> None:
    """--help must exit 0 and mention the script purpose."""
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0, f"--help returned {r.returncode}: {r.stderr}"
    assert "delivery" in r.stdout.lower()


@pytest.mark.skipif(not STAGE6_DIR.is_dir(), reason="stage6 manifests not generated locally")
def test_build_smoke() -> None:
    """A full build must exit 0 when stage6 data is present."""
    r = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=180,
    )
    assert r.returncode == 0, f"build returned {r.returncode}: {r.stderr}"
    assert "consumer-ready assets" in r.stdout


@pytest.mark.skipif(not DELIVERY_JSON.exists(), reason="delivery JSON not generated locally")
def test_emitted_json_has_no_absolute_paths() -> None:
    """No field in the emitted JSON may contain a Windows drive-letter path.

    Guards the AGENTS.md privacy rule and browser-portability: the consumer
    runs from its own root and can never resolve `C:\\…` paths.
    """
    blob = DELIVERY_JSON.read_text(encoding="utf-8")
    hits = DRIVE_PATH_RE.findall(blob)
    assert not hits, f"absolute Windows path(s) leaked into delivery JSON: {hits[:3]}"


@pytest.mark.skipif(not DELIVERY_JSON.exists(), reason="delivery JSON not generated locally")
def test_emitted_json_contract() -> None:
    """The delivery JSON must satisfy the v0.2 wire contract."""
    d = json.loads(DELIVERY_JSON.read_text(encoding="utf-8"))

    assert d["SchemaVersion"] == "riftflythrough-delivery/v1"
    # Producer version must not carry a doubled `v` (the old `vv0.1` typo).
    version = d["producer"]["version"]
    assert version.startswith("v"), f"producer version missing leading v: {version!r}"
    assert not version.startswith("vv"), f"producer version has doubled v: {version!r}"
    assert d["producer"]["tool"] == "scripts/build_riftflythrough_delivery.py"

    entries = d["entries"]
    assert len(entries) >= 100, f"expected >=100 consumer-ready entries, got {len(entries)}"

    for e in entries:
        # Legacy dead-path fields must be gone.
        assert "obj_path" not in e, f"entry {e['asset_id']} still carries legacy obj_path"
        assert "world_json" not in e, f"entry {e['asset_id']} still carries legacy world_json"
        assert HEX16_RE.match(e["asset_id"]), f"asset_id not 16-hex: {e['asset_id']!r}"

        urls = e["linked_texture_urls"]
        assert e["linked_texture_url_count"] == len(urls)
        for u in urls:
            assert u["url"].startswith("textures/converted/"), f"bad url: {u['url']!r}"
            assert HEX16_RE.match(u["pattern"]), f"bad pattern: {u['pattern']!r}"
            assert u["pattern"] == e["asset_id"], "pattern must equal asset_id"

    # Stats must reconcile with the entry counts.
    stats = d["summary"]
    assert stats["total_assets"] == len(entries)
    assert stats["total_linked_texture_urls"] == sum(e["linked_texture_url_count"] for e in entries)


@pytest.mark.skipif(not DELIVERY_JSON.exists(), reason="delivery JSON not generated locally")
def test_texture_url_resolution_is_nonempty() -> None:
    """At least some linked textures must resolve to converted PNGs.

    A zero-resolution result would mean the RiftFlythrough converted-PNG
    inventory was missing at build time — the whole fidelity point of the
    `linked_texture_urls` field. We assert a sensible floor rather than an exact
    count so the test stays green as the cohort/inventory grows.
    """
    d = json.loads(DELIVERY_JSON.read_text(encoding="utf-8"))
    total_urls = sum(e["linked_texture_url_count"] for e in d["entries"])
    assert total_urls >= 100, f"expected >=100 resolved texture URLs, got {total_urls}"
