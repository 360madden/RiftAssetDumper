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


class TestNoLegacyZoneKeysInDelivery:
    """Lock the v0.6 unifier invariant (producer version 0.6, shipped 2026-06-28).

    Post-v0.6 the delivery JSON API surface is `first4` / `confidence` (matching
    scene-manifest-v1 schema's nested zone.first4 / zone.confidence in flattened
    form). Any future regression -- whether at the top level or under any nested
    restructure -- must be caught here so a silent reintroduction would break
    the sibling RiftFlythrough consumer's transform_loader.js.
    """

    def test_no_legacy_zone_first4_or_zone_confidence_keys(self) -> None:
        """Recursive key-set walk: LEGACY prefixed keys must be absent at any depth.

        Reviewer item: replaced shallow top-level iteration with a recursive walk
        so a future restructure that nests zone fields (e.g. entry.zone.first4
        or summary.zone.zone_confidence) is also caught.
        """
        repo_root = REPO_ROOT
        delivery_path = DELIVERY_JSON
        if not delivery_path.exists():
            pytest.skip(
                f"riftflythrough-delivery.json not built yet "
                f"({delivery_path.relative_to(repo_root)} missing); "
                "run scripts/build_riftflythrough_delivery.py first."
            )
        d = json.loads(delivery_path.read_text(encoding="utf-8-sig"))
        legacy_keys = {"zone_first4", "zone_confidence"}
        offenders: list[list[str]] = []

        def walk(node: object, path: list[str]) -> None:
            if isinstance(node, dict):
                for k, v in node.items():
                    if k in legacy_keys:
                        offenders.append(path + [k])
                    walk(v, path + [k])
            elif isinstance(node, list):
                for i, item in enumerate(node):
                    walk(item, path + [str(i)])

        walk(d, [])
        assert not offenders, (
            f"v0.6 unifier regression: legacy prefixed keys still appear in "
            f"riftflythrough-delivery.json at {offenders[:3]}. The rename to "
            f"`first4` / `confidence` was a hard break; remove them from the producer."
        )

    def test_v0_6_unifier_first4_and_confidence_keys_present(self) -> None:
        """Value-range lockdown: new keys present AND values in expected set.

        Reviewer item: catch future regressions that emit the keys but with
        wrong values (typos, corrupted magic, off-magic). Reuses the cycle 5.2
        TestFirst4FilterStatus invariant shape — first4 in (empty, 47616d65),
        confidence in (high, medium, low).
        """
        repo_root = REPO_ROOT
        delivery_path = DELIVERY_JSON
        if not delivery_path.exists():
            pytest.skip(f"riftflythrough-delivery.json not built yet ({delivery_path.relative_to(repo_root)} missing).")
        d = json.loads(delivery_path.read_text(encoding="utf-8-sig"))
        entries = d.get("entries") or []
        tagged = [e for e in entries if (e.get("zone_method") or "unmatched") != "unmatched"]
        assert tagged, "no tagged entries in delivery -- cannot validate first4/confidence keys"
        missing_first4 = [e["asset_id"] for e in tagged if "first4" not in e]
        missing_confidence = [e["asset_id"] for e in tagged if "confidence" not in e]
        assert not missing_first4, (
            f"v0.6 unifier regression: {len(missing_first4)} tagged entries lack "
            f"first4 key; first 3: {missing_first4[:3]}"
        )
        assert not missing_confidence, (
            f"v0.6 unifier regression: {len(missing_confidence)} tagged entries lack "
            f"confidence key; first 3: {missing_confidence[:3]}"
        )
        # Allowed values — f-string-friendly naming (no escaped curly braces).
        allowed_first4_values = {"", "47616d65"}
        allowed_confidence_values = ("high", "medium", "low")
        bad_first4 = [e["asset_id"] for e in tagged if e.get("first4") not in allowed_first4_values]
        bad_confidence = [e["asset_id"] for e in tagged if e.get("confidence") not in allowed_confidence_values]
        assert not bad_first4, (
            f"v0.6 unifier regression: {len(bad_first4)} tagged entries carry "
            f"first4 outside the allowed set [empty, 47616d65]; first 3: {bad_first4[:3]}"
        )
        assert not bad_confidence, (
            f"v0.6 unifier regression: {len(bad_confidence)} tagged entries carry "
            f"confidence outside the allowed set (high, medium, low); "
            f"first 3: {bad_confidence[:3]}"
        )
