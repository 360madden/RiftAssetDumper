"""Tests for scripts/build_fly_asset_zone_map.py."""

import json

import pytest

from scripts.build_fly_asset_zone_map import REPO_ROOT, derive_confidence


class TestDeriveConfidenceThresholds:
    """Lock the (5, 30) confidence thresholds against silent drift.

    Empirically calibrated against docs/handoffs/2026-06-28-archive-neighbor-verification.md:
      high:   direct OR tight co-bundled sibling (|delta| <= 5)
      medium: plausible sibling (6 <= |delta| <= 30)
      low:    coincidental adjacency (|delta| > 30)
    """

    @pytest.mark.parametrize(
        "method,delta,expected",
        [
            # direct match: always high regardless of delta
            ("direct", 0, "high"),
            ("direct", 5, "high"),
            ("direct", 100, "high"),
            # neighbor high bucket: |delta| <= 5  (15/65 = 23% per handoff)
            ("neighbor", 0, "high"),
            ("neighbor", 1, "high"),
            ("neighbor", 5, "high"),
            # neighbor medium bucket: 6 <= |delta| <= 30  (27/65 = 42% per handoff)
            ("neighbor", 6, "medium"),
            ("neighbor", 15, "medium"),
            ("neighbor", 30, "medium"),
            # neighbor low bucket: |delta| > 30  (23/65 = 35% per handoff)
            ("neighbor", 31, "low"),
            ("neighbor", 100, "low"),
            ("neighbor", 1000, "low"),
            # unmatched: any delta -> None
            ("unmatched", 0, None),
            ("unmatched", 5, None),
            ("unmatched", 30, None),
            # None delta fallback for non-unmatched -> None (conservative)
            ("direct", None, None),
            ("neighbor", None, None),
        ],
    )
    def test_threshold_boundary(self, method, delta, expected):
        assert derive_confidence(method, delta) == expected

    def test_unmatched_method_always_none(self):
        """Even with delta=0 (impossible in practice), unmatched -> None."""
        assert derive_confidence("unmatched", 0) is None
        assert derive_confidence("unmatched", None) is None

    def test_negative_delta_uses_absolute_value(self):
        """The neighbor store uses abs(ei - target_ei); verify both signs route the same."""
        assert derive_confidence("neighbor", -5) == "high"
        assert derive_confidence("neighbor", -30) == "medium"
        assert derive_confidence("neighbor", -31) == "low"


EXPECTED_FIRST4 = "47616d65"


def _load_zone_map_v2() -> dict:
    """Load fly_asset_zone_map_v2.json if it exists (skip otherwise).

    Uses REPO_ROOT from scripts/build_fly_asset_zone_map for a single source of truth
    on the project root (matches the convention used in scripts/).
    """
    v2_path = REPO_ROOT / "Exports" / "semantic-phase1" / "fly_asset_zone_map_v2.json"
    if not v2_path.exists():
        pytest.skip(f"zone-map v2 not built yet ({v2_path.relative_to(REPO_ROOT)} missing)")
    return json.loads(v2_path.read_text(encoding="utf-8-sig"))


class TestFirst4FilterStatus:
    """Lock the First4 discrimination invariant against silent off-magic regressions.

    Empirically verified in docs/handoffs/2026-06-28-archive-neighbor-verification.md:
    all 8 cross-checked archive neighbors share First4 `47616d65` (standard Gamebryo NIF
    magic). Resolution therefore cannot use First4 as a filter -- the discriminating
    signal is Entry-Index Delta. This lockdown catches any silent First4 drift (e.g.
    a future patch that accidentally blends in a non-NIF asset's magic) so the
    policy stays explicit in the test suite.
    """

    FIRST4_ALLOWED = {"", EXPECTED_FIRST4}

    def test_first4_discriminates_is_false_in_v2_json(self):
        """v2.json top-level explicitly records `first4_discriminates: False`."""
        v2 = _load_zone_map_v2()
        assert v2.get("first4_discriminates") is False, (
            "v2.json top-level `first4_discriminates` flipped to True;"
            " First4 unexpectedly started discriminating. Update the"
            " archive-neighbor verification handoff and downgrade the canonical"
            " expectation here only after a fresh empirical finding."
        )
        assert v2.get("expected_first4") == EXPECTED_FIRST4, (
            f"v2.json expected_first4 changed to {v2.get('expected_first4')!r};"
            f" expected {EXPECTED_FIRST4!r} (Gamebryo NIF magic)"
        )

    def test_all_229_cohort_entries_first4_in_allowed_set(self):
        """For every cohort asset, entry.first4 must be empty OR exactly `47616d65`.

        This is the headline First4-discrimination lockdown: any silent off-magic
        regression in zone_map v2 will surface here with an actionable offender list.
        """
        v2 = _load_zone_map_v2()
        entries = v2.get("fly_asset_zone_map", {})
        assert entries, "v2.json has no fly_asset_zone_map entries (cohort not seeded?)"
        offenders = []
        for aid, e in entries.items():
            f4 = e.get("first4") or ""
            if f4 not in self.FIRST4_ALLOWED:
                offenders.append((aid, e.get("method", "?"), f4))
        assert not offenders, (
            f"{len(offenders)} entries have First4 outside {{'', {EXPECTED_FIRST4!r}}};"
            f" first 5 offenders: {offenders[:5]}"
        )

    def test_first4_required_per_method(self):
        """Method-aware first4 invariants:

        - `unmatched` entries must carry an EMPTY first4 string.
        - `direct` + `neighbor` entries must carry `EXPECTED_FIRST4` (non-empty).

        Bundled as one test so a regression surfaces ONE actionable offender list
        with semantic context (the `(aid, method, first4)` triple) rather than
        appearing as a bare "outside-allowed-set" membership error from test 2.
        """
        v2 = _load_zone_map_v2()
        entries = v2.get("fly_asset_zone_map", {})
        bad_empty = [
            (aid, e.get("method"), e.get("first4"))
            for aid, e in entries.items()
            if e.get("method") == "unmatched" and e.get("first4")
        ]
        bad_noncanonical = [
            (aid, e.get("method"), e.get("first4"))
            for aid, e in entries.items()
            if e.get("method") in ("direct", "neighbor") and e.get("first4") != EXPECTED_FIRST4
        ]
        assert not bad_empty, (
            f"{len(bad_empty)} unmatched entries carried a non-empty first4; first 3 offenders: {bad_empty[:3]}"
        )
        assert not bad_noncanonical, (
            f"{len(bad_noncanonical)} tagged entries had wrong first4"
            f" (expected {EXPECTED_FIRST4!r});"
            f" first 3 offenders (aid, method, first4): {bad_noncanonical[:3]}"
        )

    def test_method_direct_or_neighbor_must_have_gamebryo_first4(self):
        """For 'direct' + 'neighbor' entries, first4 must be `47616d65` (not empty)."""
        v2 = _load_zone_map_v2()
        entries = v2.get("fly_asset_zone_map", {})
        bad = [
            (aid, e.get("method"), e.get("first4"))
            for aid, e in entries.items()
            if e.get("method") in ("direct", "neighbor") and e.get("first4") != EXPECTED_FIRST4
        ]
        assert not bad, (
            f"{len(bad)} tagged entries have wrong first4 (expected {EXPECTED_FIRST4!r}); first 5: {bad[:5]}"
        )
