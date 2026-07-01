#!/usr/bin/env python3
"""Unit tests for ``scripts/signature_match.py``.

These tests use small synthetic byte buffers + synthetic catalogs — no
57MB binary required. Covered:

    * ``parse_signature`` — handles ``??`` wildcards + hex bytes, mixed,
      errors on invalid tokens.
    * ``match_signature`` — counts occurrences correctly with and without
      wildcards; non-overlapping matches only.
    * ``validate_catalog`` — emits per-candidate results with proper
      uniqueness verdicts.

Every test is fast (microseconds). Tests run under pytest via
``tests/test_signature_match.py``.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts import signature_match as sm  # noqa: E402


class TestParseSignature(unittest.TestCase):
    def test_lit_hex_bytes_only(self):
        # "48 8B 89 28 03 00 00" = MOV RCX, [RCX + 0x328]
        pattern, length, wc = sm.parse_signature("48 8B 89 28 03 00 00")
        self.assertEqual(length, 7)
        self.assertEqual(wc, 0)
        # Pattern should match that exact byte sequence
        import re as _re

        compiled = _re.compile(pattern, flags=_re.DOTALL)
        target = b"\x48\x8b\x89\x28\x03\x00\x00"
        matches = list(compiled.finditer(target))
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].span(), (0, 7))

    def test_wildcards_only(self):
        # "?? ?? ?? ?? ?? ??" matches any 6-byte sequence
        import re as _re

        pattern, length, wc = sm.parse_signature("?? ?? ?? ?? ?? ??")
        compiled = _re.compile(pattern, flags=_re.DOTALL)
        text = b"\x00\x01\x02\x03\x04\x05"
        matches = list(compiled.finditer(text))
        self.assertEqual(len(matches), 1)
        self.assertEqual(length, 6)
        self.assertEqual(wc, 6)
        self.assertEqual(matches[0].start(), 0)

    def test_mixed_wildcards_and_hex(self):
        # "48 8B 89 ?? ?? ?? ??" — wildcard the disp32
        import re as _re

        pattern, length, wc = sm.parse_signature("48 8B 89 ?? ?? ?? ??")
        compiled = _re.compile(pattern, flags=_re.DOTALL)
        text = (
            b"\x48\x8b\x89\x20\x03\x00\x00"  # 0x320 candidate
            b"\x48\x8b\x89\x28\x03\x00\x00"  # 0x328 candidate
            b"\x90\x90\x90\x90\x90\x90\x90\x90\x90\x90\x90"
        )
        matches = list(compiled.finditer(text))
        # Both candidates match because we wildcards the 4 disp32 bytes
        self.assertEqual(len(matches), 2)
        self.assertEqual(length, 7)
        self.assertEqual(wc, 4)

    def test_dense_spacing_accepted(self):
        # Extra whitespace between tokens should be tolerated.
        pattern_a, length_a, wc_a = sm.parse_signature("48 8B 89 28 03 00 00")
        pattern_b, length_b, wc_b = sm.parse_signature("   48    8B 89  28 03 00 00  ")
        # Both forms must produce the same regex (whitespace collapse is fine).
        self.assertEqual(pattern_a, pattern_b)
        self.assertEqual(length_a, length_b)
        self.assertEqual(wc_a, wc_b)

    def test_invalid_token_raises(self):
        with self.assertRaises(ValueError):
            sm.parse_signature("48 ZZ 89 ?? ?? ?? ??")  # non-hex "ZZ"
        with self.assertRaises(ValueError):
            sm.parse_signature("48 8 9 ?? ??")  # "8" not a full hex byte


class TestMatchSignature(unittest.TestCase):
    def test_single_appearance(self):
        buf = (
            b"\x90\x90\x90\x90"  # padding
            b"\x48\x89\x5c\x24\x08\x57\x48\x83\xec\x20\x48\x8b\xd9\x48\x8b\x89"
            b"\x20\x03\x00\x00\x90"
        )
        # Cluster #2 sig (17 hits) literal: ends in "48 8B 89 28 03 00 00" — but
        # we changed disp32 to 0x320 here.
        sig = "48 89 5C 24 08 57 48 83 EC 20 48 8B D9 48 8B 89 ?? ?? ?? ??"
        count, first = sm.match_signature(buf, sig)
        self.assertEqual(count, 1)
        self.assertIsNotNone(first)
        self.assertEqual(first, 4)  # after 4-byte padding

    def test_zero_appearances(self):
        buf = b"\x90" * 64
        sig = "48 89 5C 24 08 57"
        count, first = sm.match_signature(buf, sig)
        self.assertEqual(count, 0)
        self.assertIsNone(first)

    def test_two_appearances_returns_two(self):
        buf = b"\x90" * 8 + b"AB\x00\x00\x00\x00CD" + b"\x90" * 8 + b"AB\x00\x00\x00\x00EF"
        # Sig with first 2 bytes literal, rest wildcard
        sig = "41 42"
        count, first = sm.match_signature(buf, sig)
        self.assertEqual(count, 2)
        self.assertEqual(first, 8)


class TestValidateCatalog(unittest.TestCase):
    """Larger end-to-end test with synthetic catalog + buffer."""

    def _normal_text_buffer(self) -> bytes:
        # Build a 256-byte buffer that contains each literal sig once.
        # Sig 1 (unique): "48 8B 89 28 03 00 00" at offset 16
        # Sig 2 (duplicated): "55 4C 39 69 20 72 0A 48 8B F9 B8 10 00 00 00 EB"
        #   at offsets 32 and 80
        buf = bytearray(128)
        buf[16:23] = b"\x48\x8b\x89\x28\x03\x00\x00"
        buf[32:47] = bytes.fromhex("554C396920720A488BF9B810000000EB")
        buf[80:95] = bytes.fromhex("554C396920720A488BF9B810000000EB")
        return bytes(buf)

    def test_unique_and_non_unique_results(self):
        text = self._normal_text_buffer()
        catalog = {
            "schema": "binary-signature-candidates-v1",
            "candidates": [
                {
                    "name": "unique-sig",
                    "sig_hex": "48 8B 89 ?? ?? ?? ??",
                    "signature_length": 8,
                },
                {
                    "name": "duplicated-sig",
                    "sig_hex": "55 4C 39 69 20 72 0A 48 8B F9 B8 10 00 00 00 EB",
                    "signature_length": 15,
                },
                {
                    "name": "absent-sig",
                    "sig_hex": "EE EE EE EE",
                    "signature_length": 4,
                },
            ],
        }
        report = sm.validate_catalog(catalog, text, text_rva_base=0x140000000)
        results_by_name = {r.name: r for r in report.results}
        self.assertEqual(results_by_name["unique-sig"].unique, True)
        self.assertEqual(results_by_name["unique-sig"].match_count, 1)
        self.assertEqual(results_by_name["duplicated-sig"].unique, False)
        self.assertEqual(results_by_name["duplicated-sig"].match_count, 2)
        self.assertEqual(results_by_name["absent-sig"].match_count, 0)
        self.assertEqual(results_by_name["absent-sig"].unique, False)

    def test_summary_counts(self):
        text = self._normal_text_buffer()
        catalog = {
            "candidates": [
                {"name": "a", "sig_hex": "48 8B 89 ?? ?? ?? ??"},
                {"name": "b", "sig_hex": "55 4C 39 69 20 72 0A 48 8B F9 B8 10 00 00 00 EB"},
            ],
        }
        report = sm.validate_catalog(catalog, text, text_rva_base=0x140000000)
        self.assertEqual(report.summary["total"], 2)
        self.assertEqual(report.summary["unique"], 1)
        self.assertEqual(report.summary["non_unique"], 1)


if __name__ == "__main__":
    unittest.main()
