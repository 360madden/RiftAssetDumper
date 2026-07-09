#!/usr/bin/env python3
"""
Anti-cheat and Anti-RE Protection Scanner for RIFT x64 binary.
Uses only stdlib (struct, os, re, math). No external dependencies.
"""

import io
import math
import os
import struct
import sys

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BINARY_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Exports", "rift_x64.exe")

PE_MZ = b"MZ"
PE_SIG = b"PE\x00\x00"

ANTI_CHEAT_SIGNATURES = {
    "Xigncode": [b"Xigncode", b"xigncode", b"XIGNCODE", b"xign"],
    "nProtect": [b"nProtect", b"GameGuard", b"GameMon", b"npgg"],
    "EasyAntiCheat": [b"EasyAntiCheat", b"EasyAntiCheatEOS", b"EAC"],
    "BattlEye": [b"BattlEye", b"BE Service", b"beservice", b"BEService"],
    "Vanguard": [b"Vanguard", b"vgc.sys", b"vgk.sys"],
    "XTrap": [b"XTrap", b"xtrap"],
    "HackShield": [b"HackShield", b"hackshield"],
    "PunkBuster": [b"punkBuster", b"PunkBuster", b"pbcl", b"pbsv", b"pbsv.dat"],
    "nProtect_GG": [b"GameMon.des", b"GameMon.ker", b"GameMon.lnk", b"NPFF"],
    "CustomGuard": [
        b"GameGuard",
        b"anti-tamper",
        b"integrity check",
        b"code integrity",
        b"virtual protect",
        b"self-check",
        b"checksum validation",
        b"memory scan",
        b"detection engine",
    ],
}

ANTI_DEBUG_APIS = [
    b"IsDebuggerPresent",
    b"CheckRemoteDebuggerPresent",
    b"CheckRemoteDebugger",
    b"NtQueryInformationProcess",
    b"OutputDebugString",
    b"GetTickCount",
    b"GetTickCount64",
    b"QueryPerformanceCounter",
    b"NtSetInformationThread",
    b"ProcessDebugPort",
    b"ProcessDebugFlags",
    b"ProcessDebugObjectHandle",
    b"WaitForDebugEvent",
    b"ContinueDebugEvent",
    b"DebugActiveProcess",
    b"DebugActiveProcessStop",
    b"ReadProcessMemory",
    b"WriteProcessMemory",
    b"NtReadVirtualMemory",
    b"NtWriteVirtualMemory",
    b"NtProtectVirtualMemory",
    b"NtAllocateVirtualMemory",
    b"NtFreeVirtualMemory",
    b"VirtualProtectEx",
    b"ZwQueryInformationProcess",
    b"ZwSetInformationThread",
    b"KiUserExceptionDispatcher",
    b"RtlPcToFileHeader",
    b"NtClose",
    b"NtResumeThread",
    b"NtSuspendThread",
]

SUSPICIOUS_DLLS = [
    b"EasyAntiCheat",
    b"BattlEye",
    b"nProtect",
    b"GameGuard",
    b"Xigncode",
    b"XTrap",
    b"HackShield",
    b"PunkBuster",
    b"Vanguard",
    b"vgc",
    b"vgk",
    b"EasyAntiCheatEOS",
    b"winmm",
    b"ntdll",
    b"kernel32",
    b"psapi",
    b"dbghelp",
    b"winhttp",
    b"ws2_32",
    b"crypt32",
    b"bcrypt",
]

THREAT_STRINGS = [
    b"detected",
    b"cheat",
    b"hack",
    b"modified",
    b"tamper",
    b"tampered",
    b"unauthorized",
    b"illegal",
    b"invalid",
    b"corrupt",
    b"corrupted",
    b"abnormal",
    b"suspicious",
    b"virtual",
    b"protect",
    b"shield",
    b"guard",
    b"debug",
    b"breakpoint",
    b"int3",
    b"trap",
    b"integrity",
    b"authentic",
    b"verify",
    b"verification",
    b"runtime",
    b"monitor",
    b"heuristic",
    b"anomaly",
    b"violation",
    b"bypass",
    b"exploit",
    b"crack",
    b"cracker",
    b"keylog",
    b"inject",
    b"hook",
    b"detour",
    b"trampoline",
]

KNOWN_SECTION_NAMES = {
    b".text",
    b".rdata",
    b".data",
    b".pdata",
    b".rsrc",
    b".reloc",
    b".bss",
    b".idata",
    b".edata",
    b".tls",
    b".CRT",
    b".debug",
}
UNUSUAL_MARKERS = [
    b"UPX",
    b"ASPack",
    b"PECompact",
    b"Themida",
    b"VMProtect",
    b"Obsidium",
    b"Enigma",
    b"Armadillo",
    b".packed",
    b".vmp",
    b".vmp0",
    b".vmp1",
    b".themida",
    b".enigma",
    b".adata",
]


def read_at(f, offset, size):
    f.seek(offset)
    return f.read(size)


def parse_dos_header(data):
    if data[:2] != PE_MZ:
        return None
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    if e_lfanew + 4 > len(data) or data[e_lfanew : e_lfanew + 4] != PE_SIG:
        return None
    return e_lfanew


def parse_pe(pedata, offset):
    machine, num_sections = struct.unpack_from("<HH", pedata, offset + 4)
    time_stamp = struct.unpack_from("<I", pedata, offset + 8)[0]
    size_opt = struct.unpack_from("<H", pedata, offset + 20)[0]
    coff_size = 24
    opt_off = offset + coff_size
    magic = struct.unpack_from("<H", pedata, opt_off)[0]
    is_64 = magic == 0x20B
    if is_64:
        img_base = struct.unpack_from("<Q", pedata, opt_off + 24)[0]
        section_align = struct.unpack_from("<I", pedata, opt_off + 32)[0]
        file_align = struct.unpack_from("<I", pedata, opt_off + 36)[0]
        size_image = struct.unpack_from("<I", pedata, opt_off + 56)[0]
        num_data_dir = struct.unpack_from("<I", pedata, opt_off + 108)[0]
    else:
        img_base = struct.unpack_from("<I", pedata, opt_off + 28)[0]
        section_align = struct.unpack_from("<I", pedata, opt_off + 32)[0]
        file_align = struct.unpack_from("<I", pedata, opt_off + 36)[0]
        size_image = struct.unpack_from("<I", pedata, opt_off + 56)[0]
        num_data_dir = struct.unpack_from("<I", pedata, opt_off + 92)[0]

    sections_off = opt_off + size_opt
    sections = []
    for i in range(num_sections):
        s_off = sections_off + i * 40
        name = pedata[s_off : s_off + 8].rstrip(b"\x00")
        vsize, vaddr, raw_size, raw_ptr = struct.unpack_from("<IIII", pedata, s_off + 8)
        sections.append(
            {
                "name": name,
                "vsize": vsize,
                "vaddr": vaddr,
                "raw_size": raw_size,
                "raw_ptr": raw_ptr,
            }
        )

    dir_off = opt_off + (24 if is_64 else 16) + (96 if num_data_dir >= 1 else 0)
    if dir_off + 8 <= len(pedata):
        imp_rva, imp_size = struct.unpack_from("<II", pedata, dir_off)
    else:
        imp_rva, imp_size = 0, 0

    last_sec_end = max((s["raw_ptr"] + s["raw_size"] for s in sections if s["raw_ptr"] > 0), default=0)

    return {
        "machine": machine,
        "num_sections": num_sections,
        "time_stamp": time_stamp,
        "is_64": is_64,
        "img_base": img_base,
        "section_align": section_align,
        "file_align": file_align,
        "size_image": size_image,
        "sections": sections,
        "imp_rva": imp_rva,
        "imp_size": imp_size,
        "last_sec_end": last_sec_end,
    }


def entropy(data):
    if not data:
        return 0.0
    freq = [0] * 256
    for b in data:
        freq[b] += 1
    length = len(data)
    ent = 0.0
    for c in freq:
        if c > 0:
            p = c / length
            ent -= p * math.log2(p)
    return ent


def scan_strings(data, patterns, label, max_hits=20):
    hits = []
    for pat in patterns:
        start = 0
        while True:
            idx = data.find(pat, start)
            if idx == -1:
                break
            ctx_lo = max(0, idx - 20)
            ctx_hi = min(len(data), idx + len(pat) + 60)
            ctx = data[ctx_lo:ctx_hi]
            ctx_clean = ctx.replace(b"\x00", b"").replace(b"\xff", b"")
            hits.append((idx, pat, ctx_clean))
            start = idx + len(pat)
            if len(hits) >= max_hits:
                break
    return hits


def extract_strings_ascii(data, min_len=6, max_strings=200):
    result = []
    buf = []
    start = 0
    for i, b in enumerate(data):
        if 32 <= b < 127:
            if not buf:
                start = i
            buf.append(chr(b))
        else:
            if len(buf) >= min_len:
                result.append((start, "".join(buf)))
            buf = []
            if len(result) >= max_strings:
                break
    return result


def rva_to_offset(rva, sections):
    for s in sections:
        if s["vaddr"] <= rva < s["vaddr"] + s["vsize"]:
            return s["raw_ptr"] + (rva - s["vaddr"])
    return None


def parse_import_table(full_data, pe, rva, size):
    if rva == 0 or size == 0:
        return []
    off = rva_to_offset(rva, pe["sections"])
    if off is None or off >= len(full_data):
        return []
    imports = []
    desc_size = 20
    while off + desc_size <= len(full_data):
        ilt_rva, ts, fwd, name_rva, iat_rva = struct.unpack_from("<IIIII", full_data, off)
        if name_rva == 0:
            break
        name_off = rva_to_offset(name_rva, pe["sections"])
        if name_off is None or name_off >= len(full_data):
            off += desc_size
            continue
        dll_name_raw = full_data[name_off : name_off + 256].split(b"\x00")[0]
        dll_name = dll_name_raw.decode("ascii", errors="replace")
        funcs = []
        thunk_off = rva_to_offset(ilt_rva, pe["sections"]) if ilt_rva else rva_to_offset(iat_rva, pe["sections"])
        if thunk_off and thunk_off < len(full_data):
            t = thunk_off
            while t + 8 <= len(full_data):
                if pe["is_64"]:
                    val = struct.unpack_from("<Q", full_data, t)[0]
                    if val == 0:
                        break
                    if val & (1 << 63):
                        funcs.append(f"ord:{val & 0xFFFF}")
                    else:
                        hint_off = rva_to_offset(val & 0x7FFFFFFF, pe["sections"])
                        if hint_off and hint_off + 2 < len(full_data):
                            fn = full_data[hint_off + 2 : hint_off + 64].split(b"\x00")[0]
                            funcs.append(fn.decode("ascii", errors="replace"))
                    t += 8
                else:
                    val = struct.unpack_from("<I", full_data, t)[0]
                    if val == 0:
                        break
                    if val & (1 << 31):
                        funcs.append(f"ord:{val & 0xFFFF}")
                    else:
                        hint_off = rva_to_offset(val & 0x7FFFFFFF, pe["sections"])
                        if hint_off and hint_off + 2 < len(full_data):
                            fn = full_data[hint_off + 2 : hint_off + 64].split(b"\x00")[0]
                            funcs.append(fn.decode("ascii", errors="replace"))
                    t += 4
        imports.append((dll_name, funcs))
        off += desc_size
    return imports


SEP = "-" * 72


def main():
    if not os.path.isfile(BINARY_PATH):
        print(f"ERROR: Binary not found at {BINARY_PATH}")
        sys.exit(1)

    size = os.path.getsize(BINARY_PATH)
    print(f"{'=' * 72}")
    print("  Anti-Cheat / Anti-RE Protection Scanner")
    print(f"  Target: {os.path.basename(BINARY_PATH)}  ({size:,} bytes)")
    print(f"{'=' * 72}\n")

    with open(BINARY_PATH, "rb") as f:
        dos = read_at(f, 0, min(size, 4096))
        pe_off = parse_dos_header(dos)
        if pe_off is None:
            print("ERROR: Not a valid PE file")
            sys.exit(1)
        hdr = read_at(f, 0, min(size, 64 * 1024))
        pe = parse_pe(hdr, pe_off)

    with open(BINARY_PATH, "rb") as f:
        full = f.read()

    print(SEP)
    print("  PE HEADER SUMMARY")
    print(SEP)
    print(
        f"  Machine:          0x{pe['machine']:04X} ({'AMD64' if pe['machine'] == 0x8664 else 'x86' if pe['machine'] == 0x14C else 'Unknown'})"
    )
    print(f"  Sections:         {pe['num_sections']}")
    print(f"  Timestamp:        0x{pe['time_stamp']:08X}")
    print(f"  Image base:       0x{pe['img_base']:016X}")
    print(f"  Image size:       0x{pe['size_image']:X}")
    print()

    print(SEP)
    print("  SECTION ANALYSIS")
    print(SEP)
    unusual_names = []
    entropies = {}
    for s in pe["sections"]:
        sdata = full[s["raw_ptr"] : s["raw_ptr"] + s["raw_size"]] if s["raw_ptr"] + s["raw_size"] <= len(full) else b""
        ent = entropy(sdata)
        entropies[s["name"].decode("ascii", errors="replace")] = ent
        flag = ""
        if ent > 7.0:
            flag = "  *** HIGH ENTROPY (likely packed/encrypted)"
        if s["name"] in UNUSUAL_MARKERS:
            flag += "  [UNUSUAL NAME]"
            unusual_names.append(s["name"])
        is_known = s["name"] in KNOWN_SECTION_NAMES
        label = s["name"].decode("ascii", errors="replace")
        print(
            f"  {label:<12}  VA=0x{s['vaddr']:08X}  Raw=0x{s['raw_ptr']:08X}  "
            f"VSize=0x{s['vsize']:08X}  RSize=0x{s['raw_size']:08X}  "
            f"Ent={ent:.2f}  {'KNOWN' if is_known else 'UNKNOWN'}{flag}"
        )

    if pe["last_sec_end"] < size:
        overlay_size = size - pe["last_sec_end"]
        print(f"\n  ** Overlay detected: {overlay_size:,} bytes at offset 0x{pe['last_sec_end']:X}")
    else:
        print("\n  No overlay detected.")

    max_ent = max(entropies.values()) if entropies else 0
    packed = max_ent > 7.0
    print(f"\n  Max section entropy: {max_ent:.2f}  -> {'PACKED/OBFUSCATED' if packed else 'Normal'}")

    print(f"\n{SEP}")
    print("  ANTI-CHEAT SIGNATURES")
    print(SEP)
    ac_found = {}
    for name, pats in ANTI_CHEAT_SIGNATURES.items():
        hits = scan_strings(full, pats, name, max_hits=5)
        if hits:
            ac_found[name] = hits
            print(f"\n  [+] {name}  ({len(hits)} matches)")
            for idx, pat, ctx in hits[:5]:
                print(f"      offset 0x{idx:08X}  pattern={pat[:20]!r}")
                ctx_str = ctx[:80].decode("ascii", errors="replace")
                print(f"        context: ...{ctx_str}...")
        else:
            print(f"  [-] {name}  -- not found")

    print(f"\n{SEP}")
    print("  ANTI-DEBUGGING API SIGNATURES")
    print(SEP)
    dbg_found = {}
    for api in ANTI_DEBUG_APIS:
        hits = scan_strings(full, [api], api.decode(), max_hits=3)
        if hits:
            dbg_found[api.decode()] = hits
            for idx, pat, _ctx in hits[:2]:
                print(f"  [+] {pat.decode('ascii', errors='replace'):<40}  at 0x{idx:08X}")

    if not dbg_found:
        print("  [-] No direct anti-debug API strings found in binary image.")

    print("\n  Searching for encoded / partial anti-debug markers...")
    encoded_markers = [
        b"IsDebugger",
        b"DebugPort",
        b"DebugObject",
        b"DebugFlag",
        b"ThreadHideFromDebugger",
        b"ProcessDebugPort",
        b"ProcessDebugFlags",
        b"ProcessDebugObjectHandle",
        b"NtQueryInfo",
        b"ZwQueryInfo",
        b"CheckRemote",
        b"QueryPerformance",
    ]
    for marker in encoded_markers:
        hits = scan_strings(full, [marker], marker.decode(), max_hits=2)
        for idx, pat, _ctx in hits[:2]:
            print(f"  [+] {pat.decode():<40}  at 0x{idx:08X}")

    print(f"\n{SEP}")
    print("  DLL IMPORT ANALYSIS")
    print(SEP)

    imports = parse_import_table(full, pe, pe["imp_rva"], pe["imp_size"])
    all_dlls = [dll for dll, _ in imports]
    all_funcs = [fn for _, fns in imports for fn in fns]

    print(f"  Total DLLs imported:    {len(all_dlls)}")
    print(f"  Total functions:        {len(all_funcs)}")
    print()

    suspicious = []
    for dll in all_dlls:
        dll_lower = dll.lower()
        is_susp = any(s.decode().lower() in dll_lower for s in SUSPICIOUS_DLLS)
        tag = " *** SUSPICIOUS" if is_susp else ""
        if is_susp:
            suspicious.append(dll)
        print(f"    {dll}{tag}")

    if suspicious:
        print(f"\n  Suspicious DLLs: {suspicious}")

    if len(all_dlls) < 5:
        print(f"\n  ** Very few imported DLLs ({len(all_dlls)}) - possible packing!")

    interesting_dlls = {
        "dbghelp.dll",
        "psapi.dll",
        "winhttp.dll",
        "ws2_32.dll",
        "crypt32.dll",
        "bcrypt.dll",
        "winmm.dll",
    }
    found_interesting = [dll for dll in all_dlls if dll.lower() in interesting_dlls]
    if found_interesting:
        print(f"  Notable DLLs: {found_interesting}")

    anti_debug_dlls = {
        "dbghelp.dll": ["StackWalk64", "MiniDumpWriteDump"],
        "psapi.dll": ["EnumProcessModules", "GetModuleInformation"],
    }
    for dll in all_dlls:
        dl = dll.lower()
        if dl in anti_debug_dlls:
            fn_list = next((fns for d, fns in imports if d == dll), [])
            print(f"  {dll} functions: {fn_list[:10]}")

    print(f"\n{SEP}")
    print("  THREAT / SECURITY KEYWORD STRINGS")
    print(SEP)
    threat_hits = {}
    for kw in THREAT_STRINGS:
        hits = scan_strings(full, [kw], kw.decode(), max_hits=3)
        if hits:
            threat_hits[kw.decode()] = hits

    for kw, hits in sorted(threat_hits.items()):
        print(f"  [{len(hits):2d}] {kw:<20}  first at 0x{hits[0][0]:08X}")

    if not threat_hits:
        print("  [-] No threat-keyword strings found.")

    print(f"\n{SEP}")
    print("  PACKING / OBFUSCATION INDICATORS")
    print(SEP)

    indicators = 0
    if packed:
        print(f"  [!] High entropy sections detected ({max_ent:.2f}) - possible packing")
        indicators += 1

    if unusual_names:
        print(f"  [!] Unusual section names: {[n.decode() for n in unusual_names]}")
        indicators += 1

    if len(all_dlls) < 8:
        print(f"  [!] Low import count ({len(all_dlls)}) - possible packing")
        indicators += 1

    for s in pe["sections"]:
        if s["name"] == b".text":
            ratio = s["raw_size"] / max(pe["size_image"], 1)
            if ratio > 0.9:
                print(f"  [!] .text section occupies {ratio * 100:.0f}% of image - may contain packed data")
                indicators += 1

    if pe["last_sec_end"] < size:
        overlay_pct = (size - pe["last_sec_end"]) / size * 100
        if overlay_pct > 5:
            print(f"  [!] Significant overlay ({overlay_pct:.1f}% of file) - possible appended payload")
            indicators += 1

    ent_vals = list(entropies.values())
    if len(ent_vals) > 1:
        var = max(ent_vals) - min(ent_vals)
        if var > 1.5:
            print(f"  [!] Large entropy variance between sections ({var:.2f}) - selective packing likely")
            indicators += 1

    packer_names = [
        b"UPX",
        b"Themida",
        b"VMProtect",
        b"ASPack",
        b"PECompact",
        b"Obsidium",
        b"Enigma",
        b"Armadillo",
        b".vmp",
    ]
    for pn in packer_names:
        hits = scan_strings(full, [pn], pn.decode(), max_hits=2)
        if hits:
            print(f"  [!] Packer signature found: {pn.decode()} at 0x{hits[0][0]:08X}")
            indicators += 1

    print(f"\n{SEP}")
    print("  RESOURCE SECTION CHECK")
    print(SEP)
    rsrc = [s for s in pe["sections"] if s["name"] == b".rsrc"]
    if rsrc:
        rs = rsrc[0]
        rsdata = (
            full[rs["raw_ptr"] : rs["raw_ptr"] + rs["raw_size"]] if rs["raw_ptr"] + rs["raw_size"] <= len(full) else b""
        )
        rs_ent = entropy(rsdata)
        print(f"  .rsrc section: VA=0x{rs['vaddr']:08X}  Size=0x{rs['raw_size']:X}  Entropy={rs_ent:.2f}")
        if rs_ent > 7.0:
            print("  [!] High entropy resource section - possible encrypted resources")
        else:
            print("  Resource entropy appears normal.")
    else:
        print("  No .rsrc section found.")

    print(f"\n{SEP}")
    print("  DETECTION SUMMARY")
    print(SEP)

    print(f"\n  Anti-Cheat Systems Detected:  {len(ac_found)}")
    for name in ac_found:
        print(f"    - {name}")

    print(f"\n  Anti-Debug APIs Found:        {len(dbg_found)}")
    for name in dbg_found:
        print(f"    - {name}")

    print(f"\n  Packer / Obfuscation:         {'DETECTED' if packed else 'NOT DETECTED'}")
    if packed:
        for s in pe["sections"]:
            ent = entropies.get(s["name"].decode(), 0)
            if ent > 7.0:
                print(f"    - Section '{s['name'].decode()}' entropy = {ent:.2f}")

    print(f"\n  Obfuscation Indicators:       {indicators} flags triggered")

    print(f"\n{SEP}")
    print("  OVERALL RE DIFFICULTY ASSESSMENT")
    print(SEP)

    difficulty = 0
    reasons = []
    if ac_found:
        difficulty += len(ac_found) * 2
        reasons.append(f"{len(ac_found)} anti-cheat system(s) present")
    if dbg_found:
        difficulty += len(dbg_found)
        reasons.append(f"{len(dbg_found)} anti-debug technique(s) found")
    if packed:
        difficulty += 3
        reasons.append("Binary appears packed/obfuscated")
    if indicators > 3:
        difficulty += 2
        reasons.append(f"{indicators} packing indicators triggered")

    if difficulty == 0:
        grade = "LOW"
        desc = "No significant protections detected. Standard PE analysis tools should work."
    elif difficulty <= 3:
        grade = "LOW-MEDIUM"
        desc = "Minor protections. Standard RE tools should handle it with minor caveats."
    elif difficulty <= 6:
        grade = "MEDIUM"
        desc = "Moderate protections. Requires awareness of anti-debug and some RE skill."
    elif difficulty <= 10:
        grade = "MEDIUM-HIGH"
        desc = "Significant protections. May need to bypass anti-debug and handle obfuscation."
    else:
        grade = "HIGH"
        desc = "Heavy protections. Full anti-cheat + obfuscation. Advanced RE required."

    print(f"\n  Difficulty:  {grade}  (score: {difficulty})")
    print(f"  Assessment:  {desc}")
    if reasons:
        print("\n  Factors:")
        for r in reasons:
            print(f"    - {r}")

    print(f"\n{SEP}")
    print("  NOTABLE STRINGS (samples)")
    print(SEP)
    ascii_strings = extract_strings_ascii(full, min_len=8, max_strings=500)
    security_strings = [
        s
        for s in ascii_strings
        if any(
            kw in s[1].lower()
            for kw in [
                "protect",
                "guard",
                "detect",
                "cheat",
                "hack",
                "anti",
                "secure",
                "integrity",
                "debug",
                "monitor",
                "tamper",
                "violation",
                "unauthorized",
                "encrypt",
                "virtual",
                "shield",
                "bypass",
                "hook",
                "inject",
            ]
        )
    ]
    for offset, st in security_strings[:30]:
        print(f"    0x{offset:08X}: {st[:80]}")

    print(f"\n{'=' * 72}")
    print("  Scan complete. Report generated by scan_anti_re.py")
    print(f"{'=' * 72}")


if __name__ == "__main__":
    main()
