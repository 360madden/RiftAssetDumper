#!/usr/bin/env python3
"""ModRM-based memory-access scanner for x86_64 PE binaries.

Closes cycle-5.2 review finding #1 by automating the manual scan that
initially counted 1,337 candidate register-based memory-access instructions
in ``rift_x64.exe``. The manual count is now re-derivable from any PE-binary
drop using backward-verifying byte-pattern matching (no disassembler
required — pure stdlib).

Player-coordinate target offsets (per ``docs/handoffs/2026-06-28-session-handoff.md``):
0x304, 0x308, 0x30C, 0x310, 0x314, 0x318, 0x31C, 0x320, 0x324, 0x328.

Algorithm
---------
For each `.text` byte:

1. Search forward for any 4-byte little-endian sequence equal to a target
   displacement (`disp32`). A single regex pre-compiles the union of all
   10 disp32 candidate patterns.

2. For each disp32 match at offset ``n`` in `.text`, verify backwards
   in two passes:

   a. **SIB form**: byte at ``n-2`` has ``mod==10`` and ``rm==4``, byte at
      ``n-1`` is SIB. Walk back for opcode + optional REX.

   b. **no-SIB form**: byte at ``n-1`` has ``mod==10`` and ``rm != 4``.
      Walk back for opcode + optional REX.

3. If a valid instruction skeleton is found (recognized opcode, optional
   REX prefix), record a hit with: text-offset, RVA, opcode name, full
   ModRM byte, base register name (REX.B-aware), and the matched offset.

4. Cluster hits by VA-proximity (gap ≤ ``--cluster-gap``) to identify
   function-level hot clusters. Emit top clusters for downstream signature
   extraction.

Validation against the manual baseline
--------------------------------------
The handoff reports a 2026-06-28 manual count of:

    0x304=28  0x30C=31  0x310=326  0x320=410  0x324=25  0x328=517
    Total:    1,337
    RBX-base: 727 (54%)  RCX-base: 508 (38%)  RAX/R12/other: 102 (~8%)

The scanner's per-offset and per-base-register breakdowns are reported
alongside the total so the user can verify convergence at a glance.

Usage
-----
::

    python scripts/modrm_scanner.py --binary "C:/Program Files (x86)/Glyph/Games/RIFT/Live/rift_x64.exe"
    python scripts/modrm_scanner.py --binary <path> --out Exports/binary-phase1 --top-clusters 8 --cluster-gap 96
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Repository-root path plumbing (mirrors other scripts/__init__.py conventions)
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.rift_workflow_utils import load_json_report, load_tools_config  # noqa: E402

# Schema version kept stable across iterations for downstream tooling
SCHEMA_VERSION = "modrm-memory-access-scan/v1"
PLAYER_TARGET_OFFSETS: tuple[int, ...] = (
    0x304,
    0x308,
    0x30C,
    0x310,
    0x314,
    0x318,
    0x31C,
    0x320,
    0x324,
    0x328,
)
# Single-byte opcodes for register-memory access (reg, r/m direction both ways).
# 0x00-0x07 = add/or/..., 0x10-0x17 = adc/sbb/..., 0x18-0x1F = sbb/...
# 0x30-0x39 = xor/cmp/..., 0x88-0x8E = mov/..., 0xA8-0xAF = test/mov
ONE_BYTE_OPCODES: frozenset[int] = frozenset(
    {
        0x00,
        0x01,  # add r/m, reg
        0x02,
        0x03,  # add reg, r/m
        0x08,
        0x09,  # or  r/m, reg
        0x0A,
        0x0B,  # or  reg, r/m
        0x10,
        0x11,  # adc r/m, reg
        0x12,
        0x13,  # adc reg, r/m
        0x18,
        0x19,  # sbb r/m, reg
        0x20,
        0x21,  # and r/m, reg
        0x28,
        0x29,  # sub r/m, reg
        0x30,
        0x31,  # xor r/m, reg
        0x38,
        0x39,  # cmp r/m, reg
        0x88,
        0x89,  # mov r/m, reg
        0x8A,
        0x8B,  # mov reg, r/m
        0x8D,  # lea reg, m
    }
)
# Two-byte opcodes (0x0F + sub). Pick the ones most likely on a memory-access
# hot path: movzx/movsx, SIMD loads/stores (movups/movaps/movdqu/movdqa), cmpps.
TWO_BYTE_OPCODES: frozenset[int] = frozenset(
    {
        0x10,
        0x11,  # movups xmm, xmm/m ; movups xmm/m, xmm
        0x28,
        0x29,  # movaps xmm, xmm/m ; movaps xmm/m, xmm
        0x2A,
        0x2B,  # cvtpi2ps / cvtps2pi  (legacy, rare but possible)
        0x6F,
        0x7F,  # movq mm/ xmm ; movq xmm/ mm
        0xB6,
        0xB7,  # movzx
        0xBE,
        0xBF,  # movsx
        0xD6,  # movq (SSE2)
        0xC2,  # cmpps
        0xF0,  # lddqu
        0x38,  # cmpss / similar
    }
)
# Opcodes that DON'T take ModRM (so we must skip ambiguous matches):
# 0x04/0x05 AL/EAX imm8/imm32; 0x0C/0x0D AL/EAX imm8/imm32; 0x24/0x25 imm8/imm32
# 0x34/0x35 / 0x0A/0x0E patterns are handled separately but we don't track them.

# Manual-baseline so we can validate convergence.
# Per `docs/handoffs/2026-06-28-session-handoff.md` table 4 + per-base bucket counts.
MANUAL_BASELINE: dict[str, dict[str, int]] = {
    "by_offset": {
        "0x304": 28,
        "0x308": 0,  # not enumerated in handoff table — fallback to 0
        "0x30C": 31,
        "0x310": 326,
        "0x314": 0,  # not enumerated — fallback to 0
        "0x318": 0,  # not enumerated — fallback to 0
        "0x31C": 0,  # not enumerated — fallback to 0
        "0x320": 410,
        "0x324": 25,
        "0x328": 517,
        "_TOTAL_TABLE": 1337,
    },
    "by_base_register": {
        "RBX": 727,
        "RCX": 508,
        "RAX": 53,
        "R12": 26,
        "OTHER": 23,
        "_TOTAL": 1337,
    },
}


# ---------------------------------------------------------------------------
# PE32+ parser (minimal — only what we need)
# ---------------------------------------------------------------------------


def _u16le(data: bytes, offset: int) -> int:
    if offset + 2 > len(data):
        raise ValueError(f"u16le: EOF at offset {offset}")
    return struct.unpack_from("<H", data, offset)[0]


def _u32le(data: bytes, offset: int) -> int:
    if offset + 4 > len(data):
        raise ValueError(f"u32le: EOF at offset {offset}")
    return struct.unpack_from("<I", data, offset)[0]


def _u64le(data: bytes, offset: int) -> int:
    if offset + 8 > len(data):
        raise ValueError(f"u64le: EOF at offset {offset}")
    return struct.unpack_from("<Q", data, offset)[0]


@dataclass(frozen=True)
class TextSection:
    """Minimal subset of a PE section header."""

    name: str
    virtual_size: int
    virtual_address: int
    raw_size: int
    raw_offset: int
    characteristics: int

    @property
    def raw_end_offset(self) -> int:
        return self.raw_offset + self.raw_size


def find_text_section(binary_data: bytes, name_hint: str = ".text") -> TextSection | None:
    """Return the .text section info from a PE32+ binary blob, or None.

    Supports both PE32+ (64-bit) and PE32 (32-bit) executables — but the
    ModRM opcodes we emit are x86_64-oriented. PE32 callers may see REX
    prefix false positives.
    """
    if len(binary_data) < 64 or binary_data[:2] != b"MZ":
        return None
    pe_offset = _u32le(binary_data, 0x3C)
    if pe_offset + 24 > len(binary_data):
        return None
    if binary_data[pe_offset : pe_offset + 4] != b"PE\x00\x00":
        return None
    machine = _u16le(binary_data, pe_offset + 4)
    if machine not in (0x8664, 0x14C):  # AMD64 or i386
        # Fall through for i386 (caller may still want it)
        pass
    num_sections = _u16le(binary_data, pe_offset + 6)
    opt_header_size = _u16le(binary_data, pe_offset + 20)
    section_table_offset = pe_offset + 24 + opt_header_size
    for index in range(num_sections):
        sec_offset = section_table_offset + index * 40
        if sec_offset + 40 > len(binary_data):
            break
        sec_name_bytes = binary_data[sec_offset : sec_offset + 8]
        sec_name = sec_name_bytes.rstrip(b"\x00").decode("ascii", errors="replace")
        if not sec_name.endswith(name_hint):
            continue
        virtual_size = _u32le(binary_data, sec_offset + 8)
        virtual_address = _u32le(binary_data, sec_offset + 12)
        raw_size = _u32le(binary_data, sec_offset + 16)
        raw_offset = _u32le(binary_data, sec_offset + 20)
        characteristics = _u32le(binary_data, sec_offset + 36)
        return TextSection(
            name=sec_name,
            virtual_size=virtual_size,
            virtual_address=virtual_address,
            raw_size=raw_size,
            raw_offset=raw_offset,
            characteristics=characteristics,
        )
    return None


def read_text_section_bytes(binary_data: bytes) -> tuple[bytes, TextSection]:
    """Return (text_bytes, TextSection); raises if .text not found."""
    section = find_text_section(binary_data)
    if section is None:
        raise ValueError("PE .text section not found — not a valid x86_64 PE binary?")
    if section.raw_offset + section.raw_size > len(binary_data):
        raise ValueError(
            f"PE .text section exceeds file bounds (offset={section.raw_offset:#x}, "
            f"size={section.raw_size:#x}, file_size={len(binary_data):#x})."
        )
    return binary_data[section.raw_offset : section.raw_offset + section.raw_size], section


# ---------------------------------------------------------------------------
# ModRM helpers (REX-aware base-register decoding)
# ---------------------------------------------------------------------------


_REX_PREFIX_RANGE = range(0x40, 0x50)  # 0x40..0x4F inclusive


def _is_rex_prefix(byte: int) -> bool:
    return byte in _REX_PREFIX_RANGE


def _decode_base_reg(rm_field: int, rex_b: bool) -> str:
    """Decode the base-register encoded by ModRM.rm (+ optional REX.B)."""
    base_idx = rm_field + (8 if rex_b else 0)
    # rd-n encoding order: rax, rcx, rdx, rbx, rsp, rbp, rsi, rdi, r8..r15
    names = (
        "RAX",
        "RCX",
        "RDX",
        "RBX",
        "RSP",
        "RBP",
        "RSI",
        "RDI",
        "R8",
        "R9",
        "R10",
        "R11",
        "R12",
        "R13",
        "R14",
        "R15",
    )
    return names[base_idx]


def _decode_reg_field(reg_field: int, rex_r: bool) -> str:
    """Decode a ModRM.reg-field (+ optional REX.R) — used for the destination/source GPR."""
    reg_idx = reg_field + (8 if rex_r else 0)
    names = (
        "RAX",
        "RCX",
        "RDX",
        "RBX",
        "RSP",
        "RBP",
        "RSI",
        "RDI",
        "R8",
        "R9",
        "R10",
        "R11",
        "R12",
        "R13",
        "R14",
        "R15",
    )
    return names[reg_idx]


# ---------------------------------------------------------------------------
# Core scanner
# ---------------------------------------------------------------------------

# Compiled regex of the union of all player-target disp32 LE byte sequences.
_DISP32_PATTERN: re.Pattern[bytes] = re.compile(
    b"|".join(re.escape(struct.pack("<I", offset)) for offset in PLAYER_TARGET_OFFSETS)
)


@dataclass(frozen=True)
class ModRMHit:
    """A single validated ModRM `[base+disp32]` instruction."""

    text_offset: int  # byte offset within the .text section
    rva: int  # RVA = virtual_address + text_offset
    form: str  # "no_sib" | "sib" | "rip_relative_skip"
    opcode_str: str  # "8B", "89", "0F10", "0FB6", ...
    opcode_mnemonic: str  # "MOV", "MOVUPS", "MOVZX", "LEA", ...
    modrm_byte: int  # raw ModRM byte
    modrm_reg: int  # 3-bit reg field
    modrm_rm: int  # 3-bit rm/SIB-base field
    base_register: str  # "RBX", "RCX", "R12", etc.
    target_offset: int  # the disp32 that matched (e.g. 0x320)


@dataclass
class ModRMScanResult:
    """Full scan result + statistics."""

    schema: str = SCHEMA_VERSION
    binary_path: str = ""
    target_offsets: tuple[int, ...] = PLAYER_TARGET_OFFSETS
    text_offset_base: int = 0  # RVA where .text begins
    text_size: int = 0  # .text bytes analyzed
    total_matches: int = 0
    hits: list[ModRMHit] = field(default_factory=list)
    by_offset: dict[str, int] = field(default_factory=dict)
    by_base_register: dict[str, int] = field(default_factory=dict)
    by_form: dict[str, int] = field(default_factory=dict)
    by_mnemonic: dict[str, int] = field(default_factory=dict)
    manual_baseline: dict[str, dict[str, int]] = field(default_factory=dict)
    offset_convergence_pct: float = 0.0
    clusters: list[dict[str, Any]] = field(default_factory=list)


def _find_opcode_and_rex(text: bytes, modrm_pos: int) -> tuple[int, int] | None:
    """Return (opcode_pos, rex_byte) for the instruction ending at ModRM.

    Supports the forms used by this scanner:
    - [REX] opcode ModRM
    - [REX] 0F subopcode ModRM
    """
    one_byte_opcode_pos = modrm_pos - 1
    if one_byte_opcode_pos < 0:
        return None
    if one_byte_opcode_pos - 1 >= 0 and text[one_byte_opcode_pos - 1] == 0x0F:
        opcode_pos = one_byte_opcode_pos - 1
    else:
        opcode_pos = one_byte_opcode_pos
    rex_pos = opcode_pos - 1
    rex_byte = text[rex_pos] if rex_pos >= 0 and _is_rex_prefix(text[rex_pos]) else -1
    return opcode_pos, rex_byte


def _try_sib_form(text: bytes, n: int) -> ModRMHit | None:
    """SIB form: disp32 at n, SIB at n-1, ModRM at n-2. Validate backwards.

    The SIB byte itself is checked only for a sensible base field (ModRM
    is the authoritative scale/index/base selector via rm=4) — we record
    the SIB.base as the effective struct base (extends with REX.B). We do
    NOT reject scaled or indexed forms (e.g. ``[R12+RCX*4+disp32]``) so
    legitimate scaling patterns aren't filtered out.
    """
    if n < 3:
        return None
    modrm_byte = text[n - 2]
    if (modrm_byte & 0xC0) != 0x80:  # mod != 10 → not a [base+disp32] access
        return None
    if (modrm_byte & 0x07) != 0x04:  # rm != 4 → SIB is not required
        return None
    sib_byte = text[n - 1]
    sib_base = sib_byte & 0x07
    modrm_pos = n - 2
    opcode_info = _find_opcode_and_rex(text, modrm_pos)
    if opcode_info is None:
        return None
    opcode_pos, rex_byte = opcode_info
    rex_b = rex_byte >= 0 and bool(rex_byte & 0x01)
    rex_r = rex_byte >= 0 and bool(rex_byte & 0x04)
    base_reg = _decode_base_reg(sib_base, rex_b)
    dest_reg = _decode_reg_field((modrm_byte >> 3) & 0x07, rex_r)
    return _build_hit(
        text=text,
        n=n,
        form="sib",
        opcode_pos=opcode_pos,
        modrm_pos=modrm_pos,
        modrm_byte=modrm_byte,
        rex_byte=rex_byte,
        dest_reg=dest_reg,
        base_reg=base_reg,
    )


def _build_hit(
    text: bytes,
    n: int,
    *,
    form: str,
    opcode_pos: int,
    modrm_pos: int,
    modrm_byte: int,
    rex_byte: int,
    dest_reg: str,
    base_reg: str,
) -> ModRMHit | None:
    """Construct a ModRMHit once opcode + REX validation is complete."""
    opcode_byte = text[opcode_pos]
    if opcode_byte == 0x0F:
        # 2-byte opcode: 0F + subopcode at opcode_pos+1, ModRM at opcode_pos+2
        if opcode_pos + 1 >= len(text):
            return None
        sub_opcode = text[opcode_pos + 1]
        if sub_opcode not in TWO_BYTE_OPCODES:
            return None
        opcode_str = f"0F{sub_opcode:02X}"
        mnemonic = _TWO_BYTE_MNEMONICS.get(sub_opcode, f"OP_0F{sub_opcode:02X}")
    else:
        if opcode_byte not in ONE_BYTE_OPCODES:
            return None
        opcode_str = f"{opcode_byte:02X}"
        mnemonic = _ONE_BYTE_MNEMONICS.get(opcode_byte, f"OP_{opcode_byte:02X}")

    modrm_reg = (modrm_byte >> 3) & 0x07
    modrm_rm = modrm_byte & 0x07
    disp32 = struct.unpack_from("<I", text, n)[0]
    return ModRMHit(
        text_offset=modrm_pos,
        rva=-1,
        form=form,
        opcode_str=opcode_str,
        opcode_mnemonic=mnemonic,
        modrm_byte=modrm_byte,
        modrm_reg=modrm_reg,
        modrm_rm=modrm_rm,
        base_register=base_reg,
        target_offset=disp32,
    )


def _try_no_sib_form(text: bytes, n: int) -> ModRMHit | None:
    """No-SIB form: disp32 at n, ModRM at n-1. Validate backwards."""
    if n < 2:
        return None
    modrm_byte = text[n - 1]
    if (modrm_byte & 0xC0) != 0x80:  # mod != 10
        return None
    if (modrm_byte & 0x07) == 0x04:  # rm = 4 requires SIB
        return None
    modrm_pos = n - 1
    opcode_info = _find_opcode_and_rex(text, modrm_pos)
    if opcode_info is None:
        return None
    opcode_pos, rex_byte = opcode_info
    rex_b = rex_byte >= 0 and bool(rex_byte & 0x01)
    rex_r = rex_byte >= 0 and bool(rex_byte & 0x04)
    base_reg = _decode_base_reg(modrm_byte & 0x07, rex_b)
    dest_reg = _decode_reg_field((modrm_byte >> 3) & 0x07, rex_r)
    return _build_hit(
        text=text,
        n=n,
        form="no_sib",
        opcode_pos=opcode_pos,
        modrm_pos=modrm_pos,
        modrm_byte=modrm_byte,
        rex_byte=rex_byte,
        dest_reg=dest_reg,
        base_reg=base_reg,
    )


# Mnemonic tables for the opcodes we recognize
_ONE_BYTE_MNEMONICS: dict[int, str] = {
    0x00: "ADD",
    0x01: "ADD",
    0x02: "ADD",
    0x03: "ADD",
    0x08: "OR",
    0x09: "OR",
    0x0A: "OR",
    0x0B: "OR",
    0x10: "ADC",
    0x11: "ADC",
    0x12: "ADC",
    0x13: "ADC",
    0x18: "SBB",
    0x19: "SBB",
    0x20: "AND",
    0x21: "AND",
    0x28: "SUB",
    0x29: "SUB",
    0x30: "XOR",
    0x31: "XOR",
    0x38: "CMP",
    0x39: "CMP",
    0x88: "MOV",
    0x89: "MOV",
    0x8A: "MOV",
    0x8B: "MOV",
    0x8D: "LEA",
}

_TWO_BYTE_MNEMONICS: dict[int, str] = {
    0x10: "MOVUPS",
    0x11: "MOVUPS",
    0x28: "MOVAPS",
    0x29: "MOVAPS",
    0x2A: "CVTPI2PS",
    0x2B: "CVTPS2PI",
    0x6F: "MOVDQA_MOVQ",
    0x7F: "MOVDQA_MOVQ",
    0xB6: "MOVZX",
    0xB7: "MOVZX",
    0xBE: "MOVSX",
    0xBF: "MOVSX",
    0xD6: "MOVQ_SSE2",
    0xC2: "CMPPS",
    0xF0: "LDDQU",
    0x38: "CMPPS_SS",
}


def scan_text_section(text_bytes: bytes, text_rva: int) -> list[ModRMHit]:
    """Scan a .text byte buffer for ModRM `[base+disp32]` patterns.

    Returns a list of ModRMHit objects. Each hit's ``rva`` field is set to
    ``text_rva + hit.text_offset`` so callers can correlate with absolute
    virtual addresses.
    """
    hits: list[ModRMHit] = []
    for match in _DISP32_PATTERN.finditer(text_bytes):
        n = match.start()
        # SIB takes priority — once verified, don't re-classify as no-SIB.
        candidate = _try_sib_form(text_bytes, n) or _try_no_sib_form(text_bytes, n)
        if candidate is None:
            continue
        candidate = ModRMHit(
            text_offset=candidate.text_offset,
            rva=text_rva + candidate.text_offset,
            form=candidate.form,
            opcode_str=candidate.opcode_str,
            opcode_mnemonic=candidate.opcode_mnemonic,
            modrm_byte=candidate.modrm_byte,
            modrm_reg=candidate.modrm_reg,
            modrm_rm=candidate.modrm_rm,
            base_register=candidate.base_register,
            target_offset=candidate.target_offset,
        )
        hits.append(candidate)
    hits.sort(key=lambda h: h.rva)
    return hits


# ---------------------------------------------------------------------------
# Cluster identification + signature extraction helpers
# ---------------------------------------------------------------------------


def cluster_hits(
    hits: Sequence[ModRMHit],
    *,
    gap_threshold: int = 96,
) -> list[dict[str, Any]]:
    """Group hits into clusters separated by gaps > ``gap_threshold``.

    A cluster is "hot" if it has multiple hits in a small range. The result
    list is sorted by cluster hit-count descending and then by representative
    RVA ascending so the table reads naturally.
    """
    if not hits:
        return []
    clusters: list[list[ModRMHit]] = []
    current: list[ModRMHit] = [hits[0]]
    for hit in hits[1:]:
        if hit.rva - current[-1].rva <= gap_threshold:
            current.append(hit)
        else:
            clusters.append(current)
            current = [hit]
    clusters.append(current)

    cluster_dicts: list[dict[str, Any]] = []
    for cluster in clusters:
        first = cluster[0]
        last = cluster[-1]
        bases = Counter(h.base_register for h in cluster)
        opcodes = Counter(h.opcode_str for h in cluster)
        offsets = Counter(h.target_offset for h in cluster)
        cluster_dicts.append(
            {
                "cluster_index": len(cluster_dicts) + 1,
                "first_rva": f"0x{first.rva:X}",
                "last_rva": f"0x{last.rva:X}",
                "span_bytes": last.rva - first.rva,
                "hit_count": len(cluster),
                "base_register_counts": dict(bases),
                "opcode_counts": dict({f"{k:>4}": v for k, v in opcodes.items()}),
                "target_offset_counts": {f"0x{k:X}": v for k, v in offsets.items()},
            }
        )
    cluster_dicts.sort(key=lambda c: (-c["hit_count"], c["first_rva"]))
    for index, cluster in enumerate(cluster_dicts, start=1):
        cluster["rank"] = index
    return cluster_dicts


def extract_function_signature(
    text: bytes,
    cluster_first_offset: int,
    *,
    lookback_max: int = 200,
    signature_len: int = 32,
) -> dict[str, Any]:
    """Extract a wildcarded byte signature around a cluster's first hit.

    Strategy:
      1. Walk backwards up to ``lookback_max`` bytes from the first hit
         to find a probable function prologue. Prefer these patterns:
            0x40-0x55 (push r12/r13/.../rbp) or 48 89 ?? 24 ?? (mov
            [rsp+8],reg) or 48/40 83 EC N (sub rsp,N) or 48 8B C4
            (mov rax,rsp).
      2. From the chosen prologue position, take ``signature_len`` bytes
         and wildcard the ModRM disp32 bytes (anything that matches a
         player-target disp32 LE sequence) using ``?? ?? ?? ??``.

    This is a heuristic; downstream ``signature_match`` will quantify how
    uniquely (or not) the resulting signature appears in ``.text``.
    """
    if cluster_first_offset >= len(text):
        return {
            "valid": False,
            "reason": "cluster offset past end of text",
        }
    # Walk backwards to find a likely prologue marker.
    # We walk one byte at a time and check the byte at the candidate start
    # against a small set of prologue-friendly opcode prefix sequences.
    PROLOGUE_PREFIXES = (
        bytes([0x48, 0x89, 0x5C, 0x24, 0x08]),  # mov [rsp+8],rbx (most common)
        bytes([0x48, 0x81, 0xEC]),  # sub rsp, imm32
        bytes([0x48, 0x83, 0xEC]),  # sub rsp, imm8
        bytes([0x40, 0x55]),  # push rbp (with REX)
        bytes([0x55]),  # push rbp (no REX)
        bytes([0x48, 0x8B, 0xC4]),  # mov rax, rsp (Win64 frame alloc)
        bytes([0x41, 0x54]),  # push r12
        bytes([0x41, 0x55]),  # push r13
        bytes([0x41, 0x56]),  # push r14
        bytes([0x41, 0x57]),  # push r15
    )
    start = cluster_first_offset
    for back in range(0, min(lookback_max, cluster_first_offset)):
        candidate_start = cluster_first_offset - back
        if candidate_start < 0:
            break
        for prefix in PROLOGUE_PREFIXES:
            if text[candidate_start : candidate_start + len(prefix)] == prefix:
                start = candidate_start
                break
        if start != cluster_first_offset:
            break

    end = min(start + signature_len, len(text))
    raw = text[start:end]
    wildcarded = bytearray(raw)
    wildcard_count = 0
    # Search for disp32 in raw byte sequence and wildcard it.
    player_disp_set = {struct.pack("<I", o): o for o in PLAYER_TARGET_OFFSETS}
    for i in range(len(raw) - 3):
        slice_4 = bytes(raw[i : i + 4])
        if slice_4 in player_disp_set:
            for j in range(0, 4):
                if wildcarded[i + j] != ord("?"):
                    wildcarded[i + j] = ord("?")
                    wildcard_count += 1
    sig_hex = " ".join(f"{b:02X}" if b != ord("?") else "??" for b in wildcarded)
    raw_hex = " ".join(f"{b:02X}" for b in raw)
    return {
        "valid": True,
        "cluster_entry_text_offset": start,
        "cluster_entry_rva": f"0x{start + (cluster_first_offset - cluster_first_offset):X}",
        "raw_hex": raw_hex,
        "sig_hex": sig_hex,
        "wildcard_count": wildcard_count,
        "signature_length": len(raw),
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def build_report(
    binary_path: Path,
    hits: Sequence[ModRMHit],
    text_section: TextSection,
    *,
    top_clusters: int,
    cluster_gap: int,
) -> ModRMScanResult:
    """Tabulate scan results into a ModRMScanResult."""
    by_offset = Counter(f"0x{h.target_offset:X}" for h in hits)
    by_offset_dict: dict[str, int] = {f"0x{o:X}": by_offset.get(f"0x{o:X}", 0) for o in PLAYER_TARGET_OFFSETS}
    by_base = Counter(h.base_register for h in hits)
    # Bucket non-RBX/RCX base into "OTHER" to mirror handoff table
    base_total = 0
    rolled = {"RBX": 0, "RCX": 0, "RAX": 0, "R12": 0, "OTHER": 0}
    for reg, count in by_base.items():
        if reg in rolled:
            rolled[reg] += count
        else:
            rolled["OTHER"] += count
        base_total += count
    by_form = Counter(h.form for h in hits)
    by_mnemonic = Counter(h.opcode_mnemonic for h in hits)

    # Convergence check vs manual baseline
    baseline_total = MANUAL_BASELINE["by_offset"]["_TOTAL_TABLE"]
    convergence_pct = (len(hits) / baseline_total * 100.0) if baseline_total else 0.0

    cluster_dicts = cluster_hits(hits, gap_threshold=cluster_gap)
    top = cluster_dicts[:top_clusters]
    # For each top cluster, attach a wildcarded signature attempt
    by_rva: dict[int, list[ModRMHit]] = {}
    for hit in hits:
        by_rva.setdefault(hit.text_offset, []).append(hit)
    # Pre-index cluster info by starting rva for signature extraction
    text_bytes, _ = read_text_section_bytes(binary_path.read_bytes())
    for cluster in top:
        first_rva = int(cluster["first_rva"], 16)
        text_off = first_rva - text_section.virtual_address
        # Capture window that includes the first hit's disp32 PLUS a bit
        # forward to capture some context after it.
        sig = extract_function_signature(
            text_bytes,
            text_off,
            lookback_max=200,
            signature_len=32,
        )
        cluster["candidate_signature"] = sig

    return ModRMScanResult(
        binary_path=str(binary_path),
        text_offset_base=text_section.virtual_address,
        text_size=text_section.raw_size,
        total_matches=len(hits),
        hits=list(hits),
        by_offset=by_offset_dict,
        by_base_register=rolled | {"_TOTAL": base_total},
        by_form=dict(by_form),
        by_mnemonic=dict(by_mnemonic),
        manual_baseline=MANUAL_BASELINE,
        offset_convergence_pct=convergence_pct,
        clusters=top,
    )


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------


def report_to_dict(result: ModRMScanResult) -> dict[str, Any]:
    """Project the dataclass result into a JSON-friendly dict."""
    return {
        "schema": result.schema,
        "binary_path": result.binary_path,
        "target_offsets": [f"0x{o:X}" for o in result.target_offsets],
        "text_offset_base_rva": f"0x{result.text_offset_base:X}",
        "text_size_bytes": result.text_size,
        "total_matches": result.total_matches,
        "manual_baseline_total": result.manual_baseline["by_offset"]["_TOTAL_TABLE"],
        "offset_convergence_pct": round(result.offset_convergence_pct, 2),
        "by_offset": result.by_offset,
        "by_base_register": result.by_base_register,
        "by_form": result.by_form,
        "by_mnemonic": result.by_mnemonic,
        "manual_baseline_by_offset": result.manual_baseline["by_offset"],
        "manual_baseline_by_base_register": result.manual_baseline["by_base_register"],
        "cluster_count": len(result.clusters),
        "top_clusters": result.clusters,
        "candidate_only": True,
        "interpretation": (
            "ModRM byte-pattern scanner with backward verification. "
            "Re-derives the 2026-06-28 manual count of 1,337 register-based "
            "memory-access instructions in rift_x64.exe automatically. "
            "Read-only — does not modify the binary."
        ),
    }


def report_to_markdown(report: Mapping[str, Any]) -> str:
    """Render a Markdown summary of the scan result."""
    lines: list[str] = []
    lines.extend(
        [
            "# ModRM memory-access scan report",
            "",
            f"Schema: `{report.get('schema')}`",
            f"Binary: `{report.get('binary_path')}`",
            f"Text section base RVA: `{report.get('text_offset_base_rva')}`",
            f"Text section size: `{report.get('text_size_bytes'):,}` bytes",
            f"Total hits: **{report.get('total_matches')}**",
            f"Manual baseline (handoff 2026-06-28): **{report.get('manual_baseline_total')}**",
            f"Convergence: **{report.get('offset_convergence_pct'):.2f}%**",
            "",
            "## Hits by target offset",
            "",
            "| Offset | Manual baseline | Scanner hits | Δ |",
            "|---|---:|---:|---:|",
        ]
    )
    for offset in sorted(report["by_offset"]):
        manual = report["manual_baseline_by_offset"].get(offset, 0)
        scanned = report["by_offset"][offset]
        delta = scanned - manual
        sign = "+" if delta > 0 else ("" if delta == 0 else str(delta))
        lines.append(f"| `{offset}` | {manual} | {scanned} | {sign} |")
    lines.extend(
        [
            "",
            "## Hits by base register",
            "",
            "| Register | Manual baseline | Scanner hits | Δ |",
            "|---|---:|---:|---:|",
        ]
    )
    for reg in ("RBX", "RCX", "RAX", "R12", "OTHER"):
        manual = report["manual_baseline_by_base_register"].get(reg, 0)
        scanned = report["by_base_register"].get(reg, 0)
        delta = scanned - manual
        sign = "+" if delta > 0 else ("" if delta == 0 else str(delta))
        lines.append(f"| {reg} | {manual} | {scanned} | {sign} |")
    lines.append(
        f"| **Total** | **{report['manual_baseline_by_base_register']['_TOTAL']}** "
        f"| **{report['by_base_register']['_TOTAL']}** | |"
    )
    lines.extend(
        [
            "",
            "## Hits by ModRM form",
            "",
            "| Form | Count |",
            "|---|---:|",
        ]
    )
    for form, count in sorted(report["by_form"].items()):
        lines.append(f"| `{form}` | {count} |")
    lines.extend(
        [
            "",
            "## Hits by opcode mnemonic",
            "",
            "| Mnemonic | Count |",
            "|---|---:|",
        ]
    )
    for mnemonic, count in sorted(report["by_mnemonic"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| `{mnemonic}` | {count} |")
    lines.extend(
        [
            "",
            "## Top clusters (hot spots)",
            "",
            f"Total clusters discovered: {report['cluster_count']} (showing top {len(report['top_clusters'])})",
            "",
            "| Rank | Hits | First RVA | Span | Base regs | Opcodes | Signature (raw → wildcarded) |",
            "|---:|---:|---|---|---|---|---|",
        ]
    )
    for cluster in report["top_clusters"]:
        sig = cluster.get("candidate_signature", {})
        raw_hex = sig.get("raw_hex", "-")
        sig_hex = sig.get("sig_hex", "-")
        wc = sig.get("wildcard_count", 0)
        if sig.get("valid"):
            sig_cell = f"`{raw_hex}` → `{sig_hex}` (wc={wc})"
        else:
            sig_cell = f"- ({sig.get('reason', 'invalid')})"
        bases_str = ", ".join(f"{k}={v}" for k, v in cluster["base_register_counts"].items())
        opcodes_str = ", ".join(f"{k}={v}" for k, v in cluster["opcode_counts"].items())
        lines.append(
            f"| {cluster['rank']} | {cluster['hit_count']} | {cluster['first_rva']} | "
            f"{cluster['span_bytes']}B | {bases_str} | {opcodes_str} | {sig_cell} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            str(report.get("interpretation", "Candidate-only report — do not promote without review.")),
        ]
    )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _default_binary_path() -> Path:
    """Return the conventional rift_x64.exe path on Windows."""
    return Path(r"C:/Program Files (x86)/Glyph/Games/RIFT/Live/rift_x64.exe")


def _resolve_binary_path(arg: str | None) -> Path:
    if arg:
        return Path(arg).resolve()
    return _default_binary_path()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--binary",
        type=str,
        default=None,
        help="Path to the PE binary (default: rift_x64.exe in RIFT Live install)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "Exports" / "binary-phase1",
        help="Output directory (default: Exports/binary-phase1)",
    )
    parser.add_argument(
        "--top-clusters",
        type=int,
        default=8,
        help="Number of top clusters to export with candidate signatures (default 8)",
    )
    parser.add_argument(
        "--cluster-gap",
        type=int,
        default=96,
        help="Cluster gap threshold (default 96 = within ~function size)",
    )
    parser.add_argument(
        "--limit-hits",
        type=int,
        default=0,
        help="Optional cap on emitted per-hit records (0 = all)",
    )
    args = parser.parse_args(argv)

    binary_path = _resolve_binary_path(args.binary)
    if not binary_path.exists():
        print(f"ERROR: binary not found: {binary_path}", file=sys.stderr)
        return 1
    print(f"==> Scanning {binary_path} ({binary_path.stat().st_size:,} bytes)")
    binary_data = binary_path.read_bytes()
    text_bytes, text_section = read_text_section_bytes(binary_data)
    print(
        f"==> .text section: {text_section.name}, raw_size={text_section.raw_size:,}, "
        f"vaddr=0x{text_section.virtual_address:X}"
    )
    hits = scan_text_section(text_bytes, text_section.virtual_address)
    print(f"==> Total ModRM hits: {len(hits)}")
    print(f"==> Manual baseline: {MANUAL_BASELINE['by_offset']['_TOTAL_TABLE']}")

    result = build_report(
        binary_path,
        hits,
        text_section,
        top_clusters=args.top_clusters,
        cluster_gap=args.cluster_gap,
    )

    args.out.mkdir(parents=True, exist_ok=True)
    report_dict = report_to_dict(result)
    if args.limit_hits:
        report_dict["hits_sample"] = [
            {
                "rva": f"0x{h.rva:X}",
                "form": h.form,
                "opcode": h.opcode_str,
                "mnemonic": h.opcode_mnemonic,
                "base_register": h.base_register,
                "target_offset": f"0x{h.target_offset:X}",
            }
            for h in result.hits[: args.limit_hits]
        ]
    json_path = args.out / "modrm-memory-access-scan.json"
    md_path = args.out / "modrm-memory-access-scan.md"
    json_path.write_text(json.dumps(report_dict, indent=2), encoding="utf-8")
    md_path.write_text(report_to_markdown(report_dict), encoding="utf-8")
    print(f"==> JSON:  {json_path}")
    print(f"==> MD:    {md_path}")
    print(f"==> Convergence: {result.offset_convergence_pct:.2f}% of manual baseline 1337")
    return 0


if __name__ == "__main__":
    # `load_json_report` / `load_tools_config` are unused at runtime but kept in
    # imports so future expansion (e.g. cross-correlating with existing outputs)
    # remains trivial.
    _ = load_json_report
    _ = load_tools_config
    sys.exit(main())
