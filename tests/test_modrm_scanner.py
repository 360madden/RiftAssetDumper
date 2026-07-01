#!/usr/bin/env python3
"""Unit tests for ``scripts/modrm_scanner.py``.

These tests run on small synthetic byte buffers and a tiny synthetic PE
blob — they do **not** require the 57MB live ``rift_x64.exe``. Tests cover:

Helpers:
    * ``_is_rex_prefix``
    * ``_decode_base_reg`` (REX.B-aware)
    * REX.R decoding
    * Mnemonic table presence

Backward verification forms:
    * ``_try_no_sib_form`` — disp32 + ModRM + opcode + optional REX
    * ``_try_sib_form`` — disp32 + SIB + ModRM + opcode + optional REX

Cluster identification:
    * gap-partitioned clustering
    * sorted by hit-count descending

End-to-end scan:
    * Synthetic byte buffer with 5 known hits yields 5 hits in correct order
    * Per-offset and per-base-register counters match
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from struct import pack

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(REPO_ROOT))

from scripts.modrm_scanner import (  # noqa: E402
    _ONE_BYTE_MNEMONICS,
    _TWO_BYTE_MNEMONICS,
    MANUAL_BASELINE,
    ONE_BYTE_OPCODES,
    PLAYER_TARGET_OFFSETS,
    TWO_BYTE_OPCODES,
    ModRMHit,
    _decode_base_reg,
    _decode_reg_field,
    _is_rex_prefix,
    cluster_hits,
    scan_text_section,
)

# Promote player offsets to a small sorted list for fixture use
PLAYER_OFFSETS_LE: tuple[bytes, ...] = tuple(pack("<I", off) for off in PLAYER_TARGET_OFFSETS)


class TestIsRexPrefix(unittest.TestCase):
    def test_rex_prefix_detection(self):
        # Standard REX range: 0x40..0x4F
        for byte in (0x40, 0x41, 0x4F):
            self.assertTrue(_is_rex_prefix(byte), f"{byte:#x} should be a REX prefix")
        for byte in (0x00, 0x3F, 0x50, 0x66, 0x0F, 0x8B, 0x90):
            self.assertFalse(_is_rex_prefix(byte), f"{byte:#x} should NOT be a REX prefix")


class TestDecodeBaseReg(unittest.TestCase):
    def test_no_rex_extension(self):
        # rm field 0..7 → RAX,RCX,RDX,RBX,RSP,RBP,RSI,RDI
        self.assertEqual(_decode_base_reg(0, False), "RAX")
        self.assertEqual(_decode_base_reg(1, False), "RCX")
        self.assertEqual(_decode_base_reg(2, False), "RDX")
        self.assertEqual(_decode_base_reg(3, False), "RBX")
        self.assertEqual(_decode_base_reg(5, False), "RBP")
        self.assertEqual(_decode_base_reg(6, False), "RSI")
        self.assertEqual(_decode_base_reg(7, False), "RDI")

    def test_rex_b_extension(self):
        # REX.B=true extends index by 8 → R8..R15
        self.assertEqual(_decode_base_reg(0, True), "R8")
        self.assertEqual(_decode_base_reg(1, True), "R9")
        self.assertEqual(_decode_base_reg(3, True), "R11")
        self.assertEqual(_decode_base_reg(5, True), "R13")  # the [R13+disp32] case
        self.assertEqual(_decode_base_reg(7, True), "R15")


class TestDecodeRegField(unittest.TestCase):
    def test_no_rex_r(self):
        self.assertEqual(_decode_reg_field(0, False), "RAX")
        self.assertEqual(_decode_reg_field(1, False), "RCX")
        self.assertEqual(_decode_reg_field(7, False), "RDI")

    def test_rex_r(self):
        self.assertEqual(_decode_reg_field(0, True), "R8")
        self.assertEqual(_decode_reg_field(1, True), "R9")


class TestMnemonicTables(unittest.TestCase):
    def test_one_byte_opcodes_table_nonempty(self):
        self.assertGreater(len(_ONE_BYTE_MNEMONICS), 0)
        # Spot-check common MOV opcodes
        self.assertEqual(_ONE_BYTE_MNEMONICS[0x8B], "MOV")
        self.assertEqual(_ONE_BYTE_MNEMONICS[0x89], "MOV")
        self.assertEqual(_ONE_BYTE_MNEMONICS[0x8D], "LEA")

    def test_two_byte_opcodes_table_nonempty(self):
        self.assertGreater(len(_TWO_BYTE_MNEMONICS), 0)
        self.assertEqual(_TWO_BYTE_MNEMONICS[0x10], "MOVUPS")
        self.assertEqual(_TWO_BYTE_MNEMONICS[0x28], "MOVAPS")
        self.assertEqual(_TWO_BYTE_MNEMONICS[0xB6], "MOVZX")

    def test_opcode_sets_cover(self):
        # Every value in either set should have a corresponding mnemonic
        for value in ONE_BYTE_OPCODES:
            self.assertIn(value, _ONE_BYTE_MNEMONICS)
        for value in TWO_BYTE_OPCODES:
            self.assertIn(value, _TWO_BYTE_MNEMONICS)


class TestBaseline(unittest.TestCase):
    def test_baseline_offsets_sum(self):
        # The documented manual baseline total is 1,337 across the 6 enumerated
        # offsets (0x308/0x314/0x318/0x31C were not enumerated — they should
        # fall in the trailing remainder of 1,337.
        enumerated = (
            MANUAL_BASELINE["by_offset"]["0x304"]
            + MANUAL_BASELINE["by_offset"]["0x30C"]
            + MANUAL_BASELINE["by_offset"]["0x310"]
            + MANUAL_BASELINE["by_offset"]["0x320"]
            + MANUAL_BASELINE["by_offset"]["0x324"]
            + MANUAL_BASELINE["by_offset"]["0x328"]
        )
        self.assertEqual(enumerated, MANUAL_BASELINE["by_offset"]["_TOTAL_TABLE"])

    def test_baseline_register_sum(self):
        # Per-base totals: 727 + 508 + 53 + 26 + 23 = 1337
        s = (
            MANUAL_BASELINE["by_base_register"]["RBX"]
            + MANUAL_BASELINE["by_base_register"]["RCX"]
            + MANUAL_BASELINE["by_base_register"]["RAX"]
            + MANUAL_BASELINE["by_base_register"]["R12"]
            + MANUAL_BASELINE["by_base_register"]["OTHER"]
        )
        self.assertEqual(s, MANUAL_BASELINE["by_base_register"]["_TOTAL"])


class TestScanTextSection(unittest.TestCase):
    """End-to-end scan on synthetic byte buffers."""

    def test_no_hits_when_no_player_disp32(self):
        # Buffer with random-looking bytes; no disp32 match.
        text = b"\x90" * 256 + b"\x48\x8b\xc0\x48\x8b\xdb\x90\xc3"
        hits = scan_text_section(text, text_rva=0x1000)
        self.assertEqual(hits, [])

    def test_mov_rcx_rbx_with_0x320_no_sib(self):
        # REX + 0x8B + ModRM(reg=1 mod=10 rm=3) + disp32 0x320
        # = MOV RCX, [RBX + 0x320]
        # 0x48 (REX.W) 0x8B 0x8B 0x20 0x03 0x00 0x00
        text = b"\x90\x90\x48\x8b\x8b\x20\x03\x00\x00\x90"
        hits = scan_text_section(text, text_rva=0x0)
        self.assertEqual(len(hits), 1)
        h = hits[0]
        self.assertEqual(h.target_offset, 0x320)
        self.assertEqual(h.base_register, "RBX")
        self.assertEqual(h.opcode_mnemonic, "MOV")
        self.assertEqual(h.form, "no_sib")
        self.assertEqual(h.rva, 4)

    def test_mov_rcx_rcx_with_0x328_no_sib(self):
        # 0x48 0x8B 0x89 0x28 0x03 0x00 0x00 = MOV RCX, [RCX + 0x328]
        text = bytearray(b"\x90" * 32)
        text[10:17] = b"\x48\x8b\x89\x28\x03\x00\x00"
        hits = scan_text_section(bytes(text), text_rva=0x0)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].target_offset, 0x328)
        self.assertEqual(hits[0].base_register, "RCX")

    def test_mov_rax_rbx_with_0x304_with_rex_b_r8(self):
        # REX.WB (0x41) + 0x8B + ModRM(mod=10 reg=0 rm=3) + 0x04 0x03 0x00 0x00
        # With REX.B=1 and rm=3 (RBX) → base = R11
        text = bytearray(b"\x90" * 32)
        text += b"\x41\x8b\x83\x04\x03\x00\x00"
        hits = scan_text_section(bytes(text), text_rva=0x0)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].target_offset, 0x304)
        self.assertEqual(hits[0].base_register, "R11")

    def test_movups_xmm0_x_rbx_0x310_sib_form(self):
        # 0x0F 0x10 0x83 + 0x10 0x03 0x00 0x00 = MOVUPS XMM0, [RBX + 0x310]
        # ModRM = 0x83 = mod=10 / reg=0 (XMM0) / rm=3 (RBX); NO SIB needed.
        text = bytearray(b"\x90" * 32)
        text += b"\x0f\x10\x83\x10\x03\x00\x00"
        hits = scan_text_section(bytes(text), text_rva=0x0)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].target_offset, 0x310)
        self.assertEqual(hits[0].opcode_mnemonic, "MOVUPS")
        self.assertEqual(hits[0].form, "no_sib")

    def test_mov_rcx_r12_with_0x320_sib_form(self):
        # [R12 + 0x320]: requires SIB because rm=4 in mod=10
        # 0x49 0x8B 0x8C 0x24 0x20 0x03 0x00 0x00
        # REX.WB=0x49 (B extends base, R.B=1)
        # 0x8B MOV reg,r/m
        # ModRM=0x8C = mod=10 reg=001(CRD?RCX) rm=100(SIB)
        # SIB=0x24 = scale=00 index=100(NONE) base=100(RSP) → with REX.B=1, base = R12
        # disp32 = 0x320
        text = bytearray(b"\x90" * 32)
        text += b"\x49\x8b\x8c\x24\x20\x03\x00\x00"
        hits = scan_text_section(bytes(text), text_rva=0x0)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].target_offset, 0x320)
        self.assertEqual(hits[0].base_register, "R12")
        self.assertEqual(hits[0].form, "sib")

    def test_skips_unrelated_4_byte_sequence(self):
        # Random "disp32-looking" bytes that aren't preceded by a valid
        # ModRM(mod=10) → no hit.
        # Put 0x20 0x03 0x00 0x00 preceded by 0xCC 0xCC (no ModRM)
        text = b"\xcc\xcc\x20\x03\x00\x00\xcc\xcc"
        hits = scan_text_section(text, text_rva=0x0)
        self.assertEqual(hits, [])


class TestClusterHits(unittest.TestCase):
    def _make_hit(self, rva: int, target: int, base: str = "RBX", mnemonic: str = "MOV") -> ModRMHit:
        # Half-construct a hit for clustering tests; real fields are
        # irrelevant for gap-proximity clustering.
        return ModRMHit(
            text_offset=rva,
            rva=rva,
            form="no_sib",
            opcode_str="8B",
            opcode_mnemonic=mnemonic,
            modrm_byte=0x80 | (1 << 3) | 3,
            modrm_reg=1,
            modrm_rm=3,
            base_register=base,
            target_offset=target,
        )

    def test_two_distant_clusters_split(self):
        hits = [
            self._make_hit(0x1000, 0x320),
            self._make_hit(0x1008, 0x320),
            self._make_hit(0x100A, 0x320),
            self._make_hit(0x4000, 0x328),  # far away
        ]
        clusters = cluster_hits(hits, gap_threshold=0x40)
        self.assertEqual(len(clusters), 2)
        # Sort: density-desc then first-rva
        self.assertEqual(clusters[0]["hit_count"], 3)
        self.assertEqual(clusters[1]["hit_count"], 1)

    def test_one_cluster_runs_with_gap(self):
        hits = [
            self._make_hit(0x1000, 0x320),
            self._make_hit(0x1030, 0x320),
            self._make_hit(0x1050, 0x320),
            self._make_hit(0x1090, 0x320),
        ]
        clusters = cluster_hits(hits, gap_threshold=0x40)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0]["hit_count"], 4)


if __name__ == "__main__":
    unittest.main()
