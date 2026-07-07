# Binary Signature Consumer Contract — RiftReader Integration Guide

**Version**: v1 (2026-07-07)
**Repo**: `RiftAssetDumper` (Assets repo — no cross-repo edits)
**Status**: Candidate-only. All signatures are Scanning Rule Objects, not parser-proven truth.

---

## Purpose

This document defines the consumer contract for `rift-x64-signature-catalog.json` (schema: `binary-signatures/v1`). It tells RiftReader — or any downstream live-memory reader — how to import the catalog, pattern-scan for each anchor, resolve the resulting match to a usable memory address, and recover when signatures break after a game patch.

This document describes **what the consumer should do**, not how this repo produces the catalog. For the extraction pipeline, see the [Binary Signature Discovery Roadmap](roadmap/binary-signature-roadmap.md).

---

## 1. Catalog Artifact

### 1.1 Location

| Artifact | Path | Schema |
|----------|------|--------|
| Signature catalog | `Exports/binary-phase2/rift-x64-signature-catalog.json` | `docs/schemas/binary-signatures-v1.schema.json` |

The catalog is committed to the Assets repo under `Exports/` (gitignored). RiftReader should vendor a copy (e.g., `data/rift-x64-signature-catalog.json`) and update it manually when the Assets repo ships a new extraction.

### 1.2 Top-Level Fields

| Field | Type | Meaning |
|-------|------|---------|
| `SchemaVersion` | `"binary-signatures/v1"` | Discriminator for schema-aware consumers |
| `BinaryTarget` | string | Always `"rift_x64.exe"` — the PE binary this catalog was extracted from |
| `BinaryVersion` | object | PE timestamp, file size, and UTC date — use for patch detection |
| `ImageBase` | `"0x140000000"` | Base address for RVA-to-VA translation |
| `WildcardPolicy` | string | Human-readable description of which bytes are wildcarded and why |
| `CandidateOnly` | `true` | **Hard safety gate**: all signatures are scanning rules, not guaranteed truth |
| `Anchors` | array | The signature list (see §2) |
| `Summary` | object | Counts: total anchors, unique, per-tier |

### 1.3 Patch Detection

Before trusting any signature, the consumer MUST verify the binary fingerprint:

```
IF BinaryVersion.PETimestamp != runtime_module_timestamp:
    WARN: "Catalog was extracted from a different binary version.
           Signatures may fail to match. Re-run the extraction pipeline."
    CONTINUE (best-effort scan)
```

The PE timestamp (`BinaryVersion.PETimestamp`) is the primary version signal. The file size (`FileSizeBytes`) is a secondary check — both must match for full confidence.

---

## 2. Anchor Structure

Each entry in `Anchors[]` represents one scannable byte pattern plus the metadata needed to resolve it to a usable pointer.

### 2.1 Required Fields (Every Anchor)

| Field | Type | Meaning |
|-------|------|---------|
| `Name` | string | Human-readable label (e.g., `vtable-dispatch`, `cluster-02`) |
| `StabilityTier` | 1, 2, or 3 | Expected survival class (see §5) |
| `SignatureHex` | string | Wildcarded byte pattern: space-separated hex, `??` = any byte |
| `SignatureLength` | integer | Total byte count (including wildcards) |
| `WildcardCount` | integer | Number of `??` positions |
| `UniquenessVerified` | boolean | `true` = exactly 1 match in `.text` at extraction time |
| `DiscoveryMethod` | enum | How the signature was found (`modrm-cluster-heuristic`, etc.) |

### 2.2 Pointer Resolution Fields (When Available)

| Field | Type | Meaning |
|-------|------|---------|
| `PointerResolution.Method` | enum | `rip_relative`, `vtable_dispatch`, `direct_register_offset`, `call_relative`, `none` |
| `PointerResolution.InstructionOffsetToPointer` | integer | Byte offset from match address to the pointer bytes |
| `PointerResolution.Notes` | string | Human-readable resolution instructions |

### 2.3 Struct Layout Fields (When Available)

| Field | Type | Meaning |
|-------|------|---------|
| `StructLayout.Fields[]` | array | Per-field: `Offset`, `OffsetHex`, `Name`, `Type`, `Confidence` |

---

## 3. Scanning Algorithm

### 3.1 Pattern Matching

The `SignatureHex` field uses a simple convention:

- `??` matches **any single byte** (wildcard)
- All other tokens are literal hex bytes (e.g., `48`, `8B`, `0F`)
- Tokens are space-separated
- Example: `"48 85 D2 74 0A 48 83 C1 10 48 8B 01 FF 50 08"` has `WildcardCount: 0`
- Example: `"48 8B 89 ?? ?? ?? ??"` has `WildcardCount: 4` (wildcards the disp32)

The consumer's pattern scanner must:

1. Parse `SignatureHex` into a byte array + wildcard mask
2. Scan the target region (typically `.text` section) for the first match
3. If `UniquenessVerified` is `true` and the scan finds >1 match, the binary has changed — flag as a partial match and log a warning

Pseudocode:

```
def pattern_scan(module_base, text_section, anchor):
    pattern, mask = parse_signature(anchor.SignatureHex)
    for offset in range(0, len(text_section) - anchor.SignatureLength):
        if matches(text_section[offset:], pattern, mask):
            yield module_base + text_rva + offset
```

### 3.2 Pointer Resolution by Method

After finding a match address, resolve it to a usable pointer based on `PointerResolution.Method`:

#### `vtable_dispatch`

The match IS the dispatch gate. No pointer to resolve at the match site. Instead:

1. Find the **caller** of this dispatch gate (walk up the call stack or scan for `CALL` instructions targeting this address)
2. The caller passes a game-object pointer in `RCX` (x64 fastcall convention)
3. Trace `RCX` backwards from the call site to find where the game object was loaded

This is the most stable anchor type — zero wildcards, pure opcode sequence. Survives all patches that don't rewrite the C++ dispatch mechanism.

**Example** (anchor `vtable-dispatch`):

```
Match at: 0x14129C834
15 bytes: 48 85 D2 74 0A 48 83 C1 10 48 8B 01 FF 50 08
         TEST RDX,RDX; JZ +0x0C; ADD RCX,0x10; MOV RAX,[RCX]; CALL [RAX+0x8]
```

#### `rip_relative`

The pointer is at `match_address + instruction_length + displacement`:

1. Read the 4-byte signed displacement at `match_address + InstructionOffsetToPointer`
2. Compute: `target = match_address + instruction_length + displacement`
3. Dereference `target` to get the base pointer
4. Apply struct field offsets from `StructLayout.Fields[]`

Standard x64 RIP-relative addressing: `instruction ends at match + 7, displacement is +3 bytes in`.

#### `direct_register_offset`

The match site contains `[base_register + player_offset]` memory accesses. The consumer must:

1. Identify the base register from the ModRM byte (RBX, RCX, R12, etc.)
2. Trace the register's value backwards to its source (parameter, global, or heap object)
3. Once the base address is known, read at `base + player_offset` for each target offset

This method requires **runtime context** — the register value depends on the calling function's state. Use this for live-memory reading where you can set a breakpoint or sample the register; it is not suitable for static resolution.

#### `none`

Pointer resolution not yet determined. The signature can locate a code region but further analysis (Ghidra FunctionSiteSurvey) is needed to map the containing function's parameter/return conventions. These anchors are **location markers only** — they tell you "interesting code is here" but not what to read.

---

## 4. Struct Field Access

When an anchor has `StructLayout`, the `Fields[]` array tells the consumer what's at each offset from the resolved base pointer:

| Field | Meaning |
|-------|---------|
| `Offset` | Decimal byte offset from the struct base |
| `OffsetHex` | Hex representation (e.g., `0x320`) |
| `Name` | Semantic field name (e.g., `pos_x`, `turn_rate`) |
| `Type` | `float32`, `int32`, `uint32`, or `pointer64` |
| `Confidence` | `confirmed` (multi-source validated), `inferred` (single reference), `tentative` (register-only) |

**Current known layout** (LocalPlayer coordinate struct, from RiftReader validated offsets):

```
Base + 0x304 (772)  →  turn_rate   float32  [confirmed]
Base + 0x30C (780)  →  facing_x    float32  [confirmed]
Base + 0x310 (784)  →  facing_y    float32  [confirmed]
Base + 0x314 (788)  →  facing_z    float32  [inferred]
Base + 0x320 (800)  →  pos_x       float32  [confirmed]
Base + 0x324 (804)  →  pos_y       float32  [confirmed]
Base + 0x328 (808)  →  pos_z       float32  [confirmed]
```

**Important note on `pos_y`**: The ModRM scan found only 25 hits for offset `0x324` (vs. 517 for `0x328` pos_z and 410 for `0x320` pos_x). This strongly suggests Y (elevation) may be derived from a terrain height-map lookup rather than stored alongside X and Z. RiftReader's current code reads `[base + 0x324]` as float32 — the consumer should **validate pos_y values against terrain geometry** before trusting them as the authoritative elevation source.

---

## 5. Stability Tiers

Each anchor is assigned a stability tier that predicts how likely it is to survive a game patch:

| Tier | Label | Description | Expected Patch Survival |
|:----:|-------|-------------|-------------------------|
| **1** | Engine core | Core engine dispatch, main loop, coordinate transforms. Code that is fundamental to the engine architecture. | **High** — likely survives minor patches; may survive major expansions |
| **2** | Game logic | Zone lookups, entity traversal, property access chains. Code that depends on game-specific data layouts. | **Medium** — survives most patches; may shift on content updates |
| **3** | UI/Rendering | HUD reads, rendering hooks. Code closest to the presentation layer. | **Low** — likely changes on any UI or graphics update |

**Consumer strategy**: Prefer Tier-1 anchors for critical reads (player position). Use Tier-2 for secondary data (zone IDs, entity lists). Treat Tier-3 as convenience only — have a fallback plan.

---

## 6. Patch Recovery Workflow

When the game patches and signatures break:

### 6.1 Detection

The consumer detects a broken catalog when:

- **Zero matches** for a previously-unique signature
- **Multiple matches** for a `UniquenessVerified: true` signature
- `BinaryVersion.PETimestamp` mismatch against the running module

### 6.2 Recovery Steps

```
1. Confirm the binary has changed:
   - Check rift_x64.exe PE timestamp vs catalog BinaryVersion.PETimestamp

2. In the Assets repo, re-run the extraction pipeline:
   cd "C:/RIFT MODDING/Assets"
   python scripts/modrm_scanner.py
   python scripts/signature_match.py
   python scripts/synthesize_signature_catalog.py --validate

3. Review the diff:
   - Which signatures survived? (same hex, different VA)
   - Which signatures broke? (0 matches or went non-unique)
   - Which clusters are new? (new code paths referencing player offsets)

4. Update RiftReader's vendored copy:
   cp Exports/binary-phase2/rift-x64-signature-catalog.json \
      <riftreader>/data/rift-x64-signature-catalog.json

5. Update RiftReader's hardcoded offsets if the struct layout shifted:
   - Check StructLayout.Fields[] for offset changes
   - If pos_x moved from 0x320 to a new offset, update RiftReader's field constants
```

### 6.3 Fallback: When All Tier-1 Signatures Break

If every Tier-1 signature fails (e.g., major engine rewrite), the consumer falls back to:

1. **ModRM re-scan at runtime**: Run the ModRM scanner logic against live `.text` to find current `[RBX+0x320]` patterns
2. **Snapshot-diff discovery**: RiftReader's two-pass value scan (`scan-live-diff` workflow) to rediscover the player coordinate float32 addresses by position change
3. **Manual re-analysis**: Cheat Engine pointer scan + restart survival test (the pre-roadmap workflow)

---

## 7. Safety Boundary

### 7.1 What the Catalog Is

The signature catalog is a **Scanning Rule Object** — it contains:

- Abstract byte patterns with wildcarded addresses
- Relative local offsets (instruction_offset_to_pointer)
- Struct field maps (offset + type + confidence)
- Binary fingerprint metadata

### 7.2 What the Catalog Is NOT

The catalog does **NOT** contain:

- Decompiled C++ code or Ghidra pseudocode
- Absolute virtual addresses as ground truth
- Hardcoded pointer chains (no `[rift_x64.exe + 0x32EBC80]`)
- Promoted parser evidence (all fields are candidate-only)

### 7.3 Ghidra Firewall

The Assets repo enforces a strict safety boundary:

- **Within this repo**: Ghidra evidence is `CandidateOnly` — it must not influence production NIF decode/export paths. Three proof guards (`ghidra_function_site_target_guard`, `ghidra_pairing_non_export_guard`, `ghidra_attribute_candidate_guard`) enforce this.
- **Across the boundary**: The signature catalog crosses the boundary as a Scanning Rule Object — abstract patterns for external consumption. The consumer (RiftReader) is responsible for validating matches at scan time.

### 7.4 Consumer Responsibilities

The consumer MUST:

1. Verify `CandidateOnly` is `true` before trusting any signature
2. Validate `UniquenessVerified` per-anchor at scan time (re-scan the full `.text`)
3. Check `BinaryVersion.PETimestamp` against the running module
4. Treat `Confidence: inferred` and `Confidence: tentative` struct fields as unvalidated until independently confirmed
5. Fall back gracefully when a signature produces 0 or >1 matches

---

## 8. Integration Pseudocode

A complete RiftReader integration:

```python
import json
import struct

def load_catalog(path):
    catalog = json.load(open(path))
    assert catalog["SchemaVersion"] == "binary-signatures/v1"
    assert catalog["CandidateOnly"] is True
    return catalog

def verify_binary(catalog, runtime_module):
    rt_timestamp = get_pe_timestamp(runtime_module)
    ct_timestamp = catalog["BinaryVersion"]["PETimestamp"]
    if rt_timestamp != ct_timestamp:
        log.warning(f"Binary version mismatch: "
                     f"catalog={ct_timestamp} runtime={rt_timestamp}")
    return rt_timestamp == ct_timestamp

def find_anchor(catalog, name):
    for anchor in catalog["Anchors"]:
        if anchor["Name"] == name:
            return anchor
    return None

def resolve_pointer(match_va, anchor):
    method = anchor.get("PointerResolution", {}).get("Method", "none")
    offset = anchor.get("PointerResolution", {}).get("InstructionOffsetToPointer", 0)

    if method == "vtable_dispatch":
        # Match IS the gate; consumer must trace the caller's RCX
        return None  # Caller must provide game-object pointer

    elif method == "rip_relative":
        # Standard x64: displacement at match + offset, instruction length = offset + 4
        disp = read_i32(match_va + offset)
        target = match_va + offset + 4 + disp
        return read_ptr(target)

    elif method == "direct_register_offset":
        # Requires runtime register context — not statically resolvable
        return None

    elif method == "none":
        return None

    return None

def read_player_position(module_base, text_section, catalog):
    anchor = find_anchor(catalog, "vtable-dispatch")  # Tier-1, zero wildcards
    if not anchor:
        return None

    matches = list(pattern_scan(module_base, text_section, anchor))
    match_count = len(matches)

    if anchor["UniquenessVerified"] and match_count > 1:
        log.warning(f"Anchor {anchor['Name']} matched {match_count} times "
                     "(expected 1). Binary may have changed.")

    if match_count == 0:
        return None  # Signature broken — see §6 patch recovery

    match_va = matches[0]
    # vtable-dispatch: trace caller's RCX to get game object
    # Then apply StructLayout offsets
    struct_layout = anchor.get("StructLayout", {}).get("Fields", [])
    pos_x = pos_z = None
    for field in struct_layout:
        if field["Name"] == "pos_x":
            pos_x = read_f32(base_ptr + field["Offset"])
        elif field["Name"] == "pos_z":
            pos_z = read_f32(base_ptr + field["Offset"])
    return (pos_x, pos_z)
```

---

## 9. Current Catalog Summary

Extracted: **2026-07-07** from `rift_x64.exe` (PE timestamp 1781782683, 2026-06-18 build).

| Anchor | Tier | Length | Wildcards | Unique | Method |
|--------|:----:|:------:|:---------:|:------:|--------|
| `vtable-dispatch` | 1 | 15 | 0 | ✅ | vtable_dispatch |
| `#1 (28h)` | 2 | 28 | 4 | ✅ | direct_register_offset |
| `#2 (17h)` | 2 | 40 | 0 | ✅ | none |
| `#3 (17h)` | 2 | 40 | 4 | ✅ | direct_register_offset |
| `#4 (15h)` | 2 | 16 | 0 | ✅ | none |
| `#5 (14h)` | 2 | 16 | 0 | ✅ | none |
| `#6 (13h)` | 2 | 32 | 0 | ✅ | none |
| `#7 (11h)` | 2 | 16 | 1 | ✅ | none |
| `#8 (9h)` | 2 | 16 | 4 | ✅ | direct_register_offset |

**Total**: 9 anchors (1 Tier-1, 8 Tier-2, 0 Tier-3). All 9 verified unique against the full `.text` section.

**Known limitation**: 5 of 8 Tier-2 anchors have `PointerResolution.Method: "none"` — they locate code regions containing player-coordinate ModRM instructions but pointer resolution has not been mapped yet (see §3.2 `none` for guidance). These require Ghidra FunctionSiteSurvey to determine the containing function's calling convention. Until then, they are location markers only.

---

## 10. Schema Reference

The authoritative schema is `docs/schemas/binary-signatures-v1.schema.json` (JSON Schema 2020-12). Key constraints:

- `SchemaVersion`: `const "binary-signatures/v1"`
- `CandidateOnly`: `const true`
- `Anchors[]`: `minItems: 1`
- `SignatureHex`: pattern `^([0-9A-Fa-f]{2}|\?\?)( ([0-9A-Fa-f]{2}|\?\?))*$` (at least one token)
- `StabilityTier`: `minimum: 1, maximum: 3`
- `StructLayout.Fields[].Confidence`: `enum ["confirmed", "inferred", "tentative"]`
- `additionalProperties: false` throughout

---

*This document is part of the Binary Signature Discovery roadmap (Phase 5 M5.3). It describes the consumer-facing contract for `rift-x64-signature-catalog.json`. All signatures are candidate-only Scanning Rule Objects — the consumer is responsible for runtime validation.*
