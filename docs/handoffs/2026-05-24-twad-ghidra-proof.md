# TWAD Ghidra proof handoff — 2026-05-24

## Status

Completed the first TWAD proof pass from the retained Ghidra project. This converts the previous `TWAD` static clue from "interesting raw immediate" to a high-confidence archive-header proof. No parser behavior was changed.

## Scope and safety

- Retained generated Ghidra project reused: `Exports/ghidra-projects/RiftAnchorSurvey`
- Generated evidence reports written under ignored `Exports/ghidra-reports/`
- Generated Ghidra scripts stayed under ignored `Exports/ghidra-scripts/`
- No `Source/`, `Extracted/`, or `Exports/` files should be staged or committed.
- Findings below are evidence-backed, but Ghidra auto-names remain non-durable labels.

## Plan document

The execution plan is tracked at:

- `docs/plans/2026-05-24-twad-ghidra-proof-plan.md`

## Static proof from Ghidra

### Owning function

| Item | Evidence |
| --- | --- |
| Function | `FUN_1406e8e90` |
| Entry | `0x1406e8e90` |
| Body range | `0x1406e8e90`..`0x1406e92db` |
| Decompiler role | opens a WAD file path, maps the first `0x10000` bytes, validates header fields, and calls the archive-entry reader on supported files |

Key decompiler evidence:

```c
pvVar5 = CreateFileW(lpFileName, 0x120089, 7, ...);
DVar1 = GetFileSize(pvVar5, ...);
pvVar5 = CreateFileMappingW(..., 0x10000, ...);
piVar6 = MapViewOfFile(pvVar5, 4, 0, 0, 0);
if (*piVar6 == 0x44415754) {
    if (*(ushort *)(mappedBase + 4) < 2) {
        FUN_1406e73c0(context, wadState);
    }
}
```

### Exact compare site

| Address | Instruction | Meaning |
| --- | --- | --- |
| `0x1406e9020` | `CALL [MapViewOfFile]` | maps WAD file view |
| `0x1406e9059` | `MOV [RBX + 0x38], RAX` | stores mapped base pointer |
| `0x1406e905d` | `MOV EAX, dword ptr [RAX]` | reads first 4 bytes of mapped file |
| `0x1406e905f` | `CMP EAX, 0x44415754` | compares file header to `TWAD` little-endian |
| `0x1406e906a` | `MOVZX ECX, word ptr [RAX + 0x4]` | reads version word at header offset `+4` |
| `0x1406e906e` | `CMP CX, 0x1` | accepts version word `<= 1` |
| `0x1406e90bd` | branch target | supported path |
| `0x1406e90c3` | `CALL 0x1406e73c0` | archive-entry reader invoked |

Classification: `TWAD` is an archive file magic/header constant, not an unrelated string or chunk magic.

## Static parser-path proof

The supported-header path calls `FUN_1406e73c0`.

| Item | Evidence |
| --- | --- |
| Function | `FUN_1406e73c0` |
| Entry | `0x1406e73c0` |
| Called from | `FUN_1406e8e90` at `0x1406e90c3` |
| Role hypothesis | walks TWAD archive entry table / linked-entry chain |

Key decompiler evidence from `FUN_1406e73c0`:

```c
uVar2 = *(uint *)(mappedBase + 0x10);
index = uVar2 & 0xffff;
tableBase = *(uint *)(mappedBase + 0x8) + mappedBase;
entry = tableBase - 0x2c + index * 0x2c;
next = *(ushort *)(tableBase + index * 0x2c - 0x18);
```

This aligns with existing repo parser constants:

| Repo/parser concept | Ghidra evidence |
| --- | --- |
| archive magic at `+0` | `CMP EAX, 0x44415754` |
| version at `+4` | `MOVZX ECX, word ptr [mappedBase + 4]` |
| header size/table offset at `+8` | `tableBase = mappedBase + *(uint *)(mappedBase + 8)` |
| first linked entry raw at `+0x10` | `uVar2 = *(uint *)(mappedBase + 0x10)` |
| archive entry size `0x2c` / 44 bytes | `entry = tableBase - 0x2c + index * 0x2c` |
| next raw at entry offset `+0x14` | `next = *(ushort *)(tableBase + index * 0x2c - 0x18)` |

## Caller/input-path proof

`FUN_1406e8e90` is reached from multiple WAD-management paths:

| Caller | Callsite | Role hypothesis |
| --- | --- | --- |
| `FUN_1406e8c60` | `0x1406e8d4f` | enumerates WAD files via `FindFirstFileW` / `FindNextFileW` and opens each candidate |
| `FUN_1406e7490` | `0x1406e758c` | handles `ReadDirectoryChangesW` refresh and opens changed WAD file path |
| `FUN_1406e9a20` | `0x1406e9ae7` | reopens queued WAD paths, refreshes watched directory, and reprocesses entries |

The caller chain supports the interpretation that this is the client-side WAD/archive manager, not an isolated parser artifact.

## Byte-level cross-check

### Copied local archives

A header survey over local copied archive files found:

| Scope | Files checked | Files with `TWAD` at header | Version group |
| --- | ---: | ---: | --- |
| `Source/Assets/assets.*` | 27 | 27 | `(major=1, minor=0, uint32=1, headerSize=20)` |

Sample header bytes from copied archives:

```text
54 57 41 44 01 00 00 00 14 00 00 00 d1 05 00 00 d1 05 00 00
```

Interpretation:

- `54 57 41 44` = ASCII `TWAD`
- `01 00` at offset `+4` = version word `1`, matching the Ghidra `<= 1` check
- `14 00 00 00` at offset `+8` = header size/table offset `20`, matching the repo `ArchiveHeaderSize`
- `d1 05 00 00` = `1489`, matching observed max-entry / first-linked values in copied archive samples

### Live install archives

A header survey over the live install archive folder found:

| Scope | Files checked | Files with `TWAD` at header | Version group |
| --- | ---: | ---: | --- |
| live install `Assets/assets.*` | 244 | 244 | `(major=1, minor=0, uint32=1, headerSize=20)` |

### Manifest contrast

The manifest files are distinct and use `TWAM`, not `TWAD`:

| Scope | Magic | Major | Minor | Block table offset | Block table size |
| --- | --- | ---: | ---: | ---: | ---: |
| copied `assets64.manifest` | `TWAM` | 3 | 0 | 80 | 256 |
| copied `assets64-live.manifest` | `TWAM` | 3 | 0 | 80 | 256 |
| live install `assets64.manifest` | `TWAM` | 3 | 0 | 80 | 256 |

This supports the existing repo split:

- `TWAM` = manifest layer
- `TWAD` = archive file layer

### Occurrence scan

A local copied-source occurrence scan found all copied archive `assets.*` `TWAD` hits at file offset `0`. The only non-archive hits were in local generated/report-like files under ignored local source data.

## Confidence classification

| Claim | Confidence | Reason |
| --- | --- | --- |
| `TWAD` is archive file magic | High | Ghidra header compare, WAD file error strings, caller enumeration, and local archive headers all agree. |
| Current supported archive version is major word `<= 1` | High | Ghidra checks word at `+4`; all copied/live archive headers use `1.0`. |
| `FUN_1406e73c0` walks archive linked entries | Medium-high | It reads header offsets and 44-byte entries exactly like the repo parser; Ghidra variable names are still auto-generated. |
| `TWAD` is not a chunk-level payload magic | High for current evidence | Copied archive hits are at file offset `0`, and the Ghidra function maps whole WAD files and checks offset `0`. |
| Parser behavior should change now | Low / blocked | Existing parser already recognizes `TWAD`; this proof strengthens documentation and future alignment but does not justify behavior changes alone. |

## Decision

The `TWAD` lead is proven as an archive-header/file-magic path. No parser behavior change is recommended in this milestone.

## Tracked test added

Added `TwadArchiveHeader_MatchesClientGhidraProof` in `src/RiftAssetDumper.Tests/BasicTests.cs`.

The test constructs a minimal archive header matching the proven client/Ghidra layout:

- `TWAD` at offset `+0`
- version `1` at offset `+4`
- header size/table offset `20` at offset `+8`
- max entries at offset `+12`
- first linked entry raw at offset `+16`

It invokes the existing private parser path through reflection and verifies the archive probe fields without changing production parser behavior.

## Recommended next milestone

Use this proof to align durable docs/tests, not parser behavior:

1. Inspect whether the repo parser should warn on unsupported TWAD version the same way the client does.
2. If a behavior gap exists, propose a tiny read-only warning/test first, not extraction logic changes.
3. Then return to the `NiDataStream` / `NiMesh` Ghidra leads for geometry-specific truth.
