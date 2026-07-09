#!/usr/bin/env python3
"""
RIFT Live Memory Scanner
========================
Reads live game memory to validate signatures and discover runtime structures.

Usage:
    python scripts/rift_memory_scanner.py --scan-strings
    python scripts/rift_memory_scanner.py --validate-sigs
    python scripts/rift_memory_scanner.py --find-unit-registry
    python scripts/rift_memory_scanner.py --all

Requirements:
    - Game must be running (rift_x64.exe)
    - Run as Administrator for memory access
"""

import argparse
import ctypes
import ctypes.wintypes
import struct
import sys
from pathlib import Path

# Windows API constants
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_ALL_ACCESS = 0x1F0FFF
MEM_COMMIT = 0x1000
PAGE_READABLE = [0x02, 0x04, 0x06, 0x20, 0x40, 0x60, 0x80]

# Windows API functions
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

OpenProcess = kernel32.OpenProcess
OpenProcess.restype = ctypes.wintypes.HANDLE
OpenProcess.argtypes = [ctypes.wintypes.DWORD, ctypes.wintypes.BOOL, ctypes.wintypes.DWORD]

ReadProcessMemory = kernel32.ReadProcessMemory
ReadProcessMemory.restype = ctypes.wintypes.BOOL
ReadProcessMemory.argtypes = [
    ctypes.wintypes.HANDLE,
    ctypes.wintypes.LPVOID,
    ctypes.wintypes.LPVOID,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]

CloseHandle = kernel32.CloseHandle


class MemoryBasicInformation(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", ctypes.wintypes.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", ctypes.wintypes.DWORD),
        ("Protect", ctypes.wintypes.DWORD),
        ("Type", ctypes.wintypes.DWORD),
    ]


VirtualQueryEx = kernel32.VirtualQueryEx
VirtualQueryEx.restype = ctypes.c_size_t
VirtualQueryEx.argtypes = [
    ctypes.wintypes.HANDLE,
    ctypes.wintypes.LPVOID,
    ctypes.POINTER(MemoryBasicInformation),
    ctypes.c_size_t,
]


class RIFTMemoryScanner:
    """Memory scanner for RIFT game process."""

    def __init__(self):
        self.process_handle = None
        self.process_id = None
        self.module_base = None
        self.module_size = None

    def find_process(self, name: str = "rift_x64.exe") -> bool:
        """Find the RIFT process by name."""
        import subprocess

        # Use tasklist to find process
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {name}", "/FO", "CSV", "/NH"], capture_output=True, text=True
        )

        lines = result.stdout.strip().split("\n")
        for line in lines:
            if name.lower() in line.lower():
                # Extract PID from CSV
                parts = line.split(",")
                if len(parts) >= 2:
                    pid_str = parts[1].strip('"')
                    try:
                        self.process_id = int(pid_str)
                        print(f"Found {name} with PID {self.process_id}")
                        return True
                    except ValueError:
                        continue

        print(f"Process {name} not found. Is the game running?")
        return False

    def open_process(self) -> bool:
        """Open the process with read access."""
        if not self.process_id:
            print("Process not found. Call find_process() first.")
            return False

        self.process_handle = OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, self.process_id)

        if not self.process_handle:
            error = ctypes.get_last_error()
            print(f"Failed to open process. Error: {error}")
            print("Try running as Administrator.")
            return False

        print(f"Opened process {self.process_id}")
        return True

    def find_module(self, name: str = "rift_x64.exe") -> bool:
        """Find the base address and size of the main module."""
        import subprocess

        # Use wmic to get module info
        subprocess.run(
            ["wmic", "process", "where", f"ProcessId={self.process_id}", "get", "CommandLine", "/VALUE"],
            capture_output=True,
            text=True,
        )

        # Known RVA of 'Inspect.Unit.Detail' string from static analysis
        # File offset 0x26762D8 -> RVA 0x26772D8
        KNOWN_STRING_RVA = 0x26772D8
        SEARCH_STRING = b"Inspect.Unit.Detail\x00"

        print("Finding module base via string reference...")

        # Scan memory for the string
        regions = self.enumerate_regions()
        for region in regions:
            base = region["base"]
            size = region["size"]

            if size > 0x10000000:  # Skip regions > 256MB
                continue

            data = self.read_memory(base, min(size, 0x100000))  # Read up to 1MB
            if not data:
                continue

            idx = data.find(SEARCH_STRING)
            if idx != -1:
                string_addr = base + idx
                # Calculate module base
                self.module_base = string_addr - KNOWN_STRING_RVA
                self.module_size = 0x4000000  # 64MB estimated

                print(f"Found string at: 0x{string_addr:X}")
                print(f"Calculated module base: 0x{self.module_base:X}")
                print(f"Module size: 0x{self.module_size:X}")
                return True

        # Fallback
        print("Could not find module base via string reference")
        self.module_base = 0x140000000
        self.module_size = 0x4000000
        return True

    def read_memory(self, address: int, size: int) -> bytes | None:
        """Read memory from the process."""
        buffer = ctypes.create_string_buffer(size)
        bytes_read = ctypes.c_size_t(0)

        success = ReadProcessMemory(
            self.process_handle, ctypes.c_void_p(address), buffer, size, ctypes.byref(bytes_read)
        )

        if success:
            return buffer.raw[: bytes_read.value]
        else:
            return None

    def read_pointer(self, address: int) -> int | None:
        """Read a 64-bit pointer from memory."""
        data = self.read_memory(address, 8)
        if data and len(data) == 8:
            return struct.unpack("<Q", data)[0]
        return None

    def read_float(self, address: int) -> float | None:
        """Read a 32-bit float from memory."""
        data = self.read_memory(address, 4)
        if data and len(data) == 4:
            return struct.unpack("<f", data)[0]
        return None

    def scan_pattern(self, pattern: bytes, start: int = None, size: int = None) -> list:
        """Scan memory for a byte pattern."""
        if start is None:
            start = self.module_base
        if size is None:
            size = self.module_size

        results = []
        chunk_size = 0x10000  # 64KB chunks

        for offset in range(0, size, chunk_size):
            addr = start + offset
            data = self.read_memory(addr, chunk_size)

            if data:
                # Find pattern in chunk
                idx = 0
                while True:
                    idx = data.find(pattern, idx)
                    if idx == -1:
                        break
                    results.append(addr + idx)
                    idx += 1

        return results

    def scan_string(self, target: str, start: int = None, size: int = None) -> list:
        """Scan memory for a null-terminated string."""
        pattern = target.encode("ascii") + b"\x00"
        return self.scan_pattern(pattern, start, size)

    def scan_float(self, value: float, start: int = None, size: int = None) -> list:
        """Scan memory for a specific float value."""
        pattern = struct.pack("<f", value)
        return self.scan_pattern(pattern, start, size)

    def enumerate_regions(self) -> list:
        """Enumerate all committed memory regions."""
        regions = []
        address = 0

        while address < 0x7FFFFFFFFFFFF:  # User-mode address space limit
            mbi = MemoryBasicInformation()
            result = VirtualQueryEx(
                self.process_handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)
            )

            if result == 0:
                break

            if mbi.State == MEM_COMMIT and mbi.Protect in PAGE_READABLE:
                regions.append({"base": mbi.BaseAddress or 0, "size": mbi.RegionSize, "protect": mbi.Protect})

            next_address = (mbi.BaseAddress or 0) + mbi.RegionSize
            if next_address <= address:
                break
            address = next_address

        return regions

    def validate_signature(self, signature: bytes, name: str = "") -> list:
        """Validate a byte signature against the running process."""
        print(f"\nValidating signature: {name}")
        print(f"Pattern: {signature.hex()}")

        matches = self.scan_pattern(signature)

        if matches:
            print(f"Found {len(matches)} matches:")
            for addr in matches:
                print(f"  0x{addr:X}")
        else:
            print("No matches found")

        return matches

    def scan_strings_area(self):
        """Scan for known strings in the game memory."""
        print("\n" + "=" * 60)
        print("SCANNING FOR KNOWN STRINGS")
        print("=" * 60)

        strings_to_find = [
            "Inspect.Unit.Detail",
            "detail@unit",
            "Inspect.Unit.List",
            "Inspect.Zone.Detail",
            "player",
            "health",
            "mana",
            "calling",
            "level",
            "name",
            "LocalPlayerBase",
            "unit",
            "zone",
        ]

        # Scan all memory regions
        regions = self.enumerate_regions()
        print(f"Found {len(regions)} readable memory regions")

        for s in strings_to_find:
            refs = []
            for region in regions:
                base = region["base"]
                size = region["size"]

                # Skip very large regions (likely empty)
                if size > 0x10000000:  # > 256MB
                    continue

                found = self.scan_string(s, base, size)
                refs.extend(found)

            if refs:
                print(f"\n'{s}' found at:")
                for addr in refs[:5]:  # Limit to first 5
                    print(f"  0x{addr:X}")
            else:
                print(f"'{s}' not found")

    def validate_signatures(self):
        """Validate all known signatures against the running process."""
        print("\n" + "=" * 60)
        print("VALIDATING BYTE SIGNATURES")
        print("=" * 60)

        # Load signatures from catalog if available
        sig_catalog = Path("Exports/binary-phase2/signature-catalog.json")
        if sig_catalog.exists():
            import json

            with open(sig_catalog) as f:
                catalog = json.load(f)

            for sig in catalog.get("signatures", []):
                sig_hex = sig["signature_hex"].replace("??", "00")
                sig_bytes = bytes.fromhex(sig_hex)
                name = sig.get("name", "unknown")
                self.validate_signature(sig_bytes, name)
        else:
            print("Signature catalog not found. Using hardcoded signatures.")

            # Hardcoded signatures for testing
            signatures = [
                ("Getter Thunk", bytes.fromhex("4533C0BA10000000E9")),
                ("LocalPlayer Offset", bytes.fromhex("488B8380EB3200")),
            ]

            for name, sig in signatures:
                self.validate_signature(sig, name)

    def find_code_references(self, target_rva: int, name: str = ""):
        """Find code that references a specific RVA (LEA instructions)."""
        print(f"\nFinding code references to RVA 0x{target_rva:X} ({name})...")

        # Search for LEA instructions with RIP-relative addressing
        # LEA reg, [rip+disp32] = 48 8D [modrm] [disp32]
        # where mod=00, r/m=101 (RIP-relative)

        results = []

        # Scan the code section
        code_start = self.module_base + 0x1000  # .text section starts at RVA 0x1000
        code_size = 0x1700000  # ~23MB

        chunk_size = 0x100000  # 1MB chunks
        for offset in range(0, code_size, chunk_size):
            addr = code_start + offset
            data = self.read_memory(addr, chunk_size)

            if not data:
                continue

            # Search for LEA instructions
            for i in range(len(data) - 7):
                # Check for REX.W prefix (0x48)
                if data[i] != 0x48:
                    continue

                # Check for LEA opcode (0x8D)
                if data[i + 1] != 0x8D:
                    continue

                # Check ModR/M byte for RIP-relative addressing (mod=00, r/m=101)
                modrm = data[i + 2]
                mod = (modrm >> 6) & 3
                r_m = modrm & 7

                if mod != 0 or r_m != 5:
                    continue

                # Get displacement (32-bit signed)
                disp = struct.unpack_from("<i", data, i + 3)[0]

                # Calculate instruction RVA
                inst_file_offset = addr + i - self.module_base
                inst_rva = inst_file_offset

                # Calculate target RVA
                calc_target = inst_rva + 7 + disp

                if calc_target == target_rva:
                    reg = (modrm >> 3) & 7
                    results.append({"address": addr + i, "rva": inst_rva, "register": reg, "displacement": disp})

        if results:
            print(f"Found {len(results)} references:")
            for ref in results:
                print(
                    f"  0x{ref['address']:X} (RVA 0x{ref['rva']:X}): LEA R{ref['register']}, [rip+0x{ref['displacement'] & 0xFFFFFFFF:X}]"
                )
        else:
            print("No references found")

        return results

    def find_player_object(self):
        """Try to find the player object in memory."""
        print("\n" + "=" * 60)
        print("SEARCHING FOR PLAYER OBJECT")
        print("=" * 60)

        # Known offset from our analysis
        LOCAL_PLAYER_OFFSET = 0x32EBC80

        # Try to read from expected location
        addr = self.module_base + LOCAL_PLAYER_OFFSET
        print(f"\nTrying base + 0x{LOCAL_PLAYER_OFFSET:X} = 0x{addr:X}")

        ptr = self.read_pointer(addr)
        if ptr:
            print(f"  Found pointer: 0x{ptr:X}")

            # Try to read player coordinates from this pointer
            # Offsets from our analysis
            offsets = {
                "pos_x": 0x320,
                "pos_y": 0x324,
                "pos_z": 0x328,
                "facing": 0x30C,
                "turn_rate": 0x304,
            }

            print("\n  Reading player data:")
            for name, offset in offsets.items():
                value = self.read_float(ptr + offset)
                if value is not None:
                    print(f"    {name}: {value:.4f}")
                else:
                    print(f"    {name}: <read failed>")
        else:
            print("  No pointer found at expected location")
            print("  The offset may have changed in this game version")

            # Scan all memory regions for potential player objects
            print("\n  Scanning all memory for float patterns...")
            regions = self.enumerate_regions()

            # Look for typical player coordinates (positive Z, reasonable XY)
            # This is a heuristic scan
            for region in regions[:10]:  # Limit to first 10 regions
                base = region["base"]
                size = region["size"]

                if size > 0x1000000:  # Skip regions > 16MB
                    continue

                data = self.read_memory(base, size)
                if not data:
                    continue

                # Look for sequences of 3 floats that could be coordinates
                for i in range(0, len(data) - 12, 4):
                    try:
                        x = struct.unpack_from("<f", data, i)[0]
                        y = struct.unpack_from("<f", data, i + 4)[0]
                        z = struct.unpack_from("<f", data, i + 8)[0]

                        # Check if these look like valid coordinates
                        if -1000 < x < 1000 and -1000 < y < 1000 and 0 < z < 500:
                            # Check if surrounding memory looks like a game object
                            # (has pointers, reasonable values)
                            print(f"    Potential coords at 0x{base + i:X}: ({x:.2f}, {y:.2f}, {z:.2f})")
                    except struct.error, ValueError, OverflowError:
                        continue

    def scan_for_unit_registry(self):
        """Scan memory for potential unit registry structures."""
        print("\n" + "=" * 60)
        print("SCANNING FOR UNIT REGISTRY")
        print("=" * 60)

        # The unit registry is likely a hash table or array
        # Look for patterns that suggest a collection of unit objects

        # Scan for strings that might be part of unit objects
        unit_strings = ["player", "target", "focus"]

        for s in unit_strings:
            refs = self.scan_string(s)
            if refs:
                print(f"\n'{s}' references found at:")
                for addr in refs[:10]:
                    # Check if this looks like a unit object
                    # Try to read surrounding memory
                    data = self.read_memory(addr - 0x10, 0x40)
                    if data:
                        print(f"  0x{addr:X}")
                        # Look for pointer-like values
                        for i in range(0, len(data) - 8, 8):
                            val = struct.unpack_from("<Q", data, i)[0]
                            if 0x10000 < val < 0x7FFFFFFFFFFFF:
                                print(f"    Potential pointer at offset {i - 0x10}: 0x{val:X}")

    def trace_lua_method(self, method_name: str):
        """Trace the implementation of a Lua method."""
        print("\n" + "=" * 60)
        print(f"TRACING LUA METHOD: {method_name}")
        print("=" * 60)

        # Find the string
        refs = self.scan_string(method_name)
        if not refs:
            print(f"String '{method_name}' not found")
            return

        string_addr = refs[0]
        string_rva = string_addr - self.module_base
        print(f"String found at: 0x{string_addr:X} (RVA 0x{string_rva:X})")

        # Find code references to this string
        code_refs = self.find_code_references(string_rva, method_name)

        if code_refs:
            # Analyze the function containing the first reference
            first_ref = code_refs[0]
            func_addr = first_ref["address"]

            print(f"\nAnalyzing function at 0x{func_addr:X}...")

            # Read the function prologue
            func_data = self.read_memory(func_addr - 0x20, 0x100)
            if func_data:
                print("Function bytes:")
                for i in range(0, min(64, len(func_data)), 16):
                    offset = func_addr - 0x20 + i
                    hex_bytes = " ".join(f"{func_data[i + j]:02x}" for j in range(16))
                    print(f"  0x{offset:X}: {hex_bytes}")

    def close(self):
        """Close the process handle."""
        if self.process_handle:
            CloseHandle(self.process_handle)
            self.process_handle = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def main():
    parser = argparse.ArgumentParser(description="RIFT Live Memory Scanner")
    parser.add_argument("--scan-strings", action="store_true", help="Scan for known strings")
    parser.add_argument("--validate-sigs", action="store_true", help="Validate byte signatures")
    parser.add_argument("--find-player", action="store_true", help="Find player object")
    parser.add_argument("--find-unit-registry", action="store_true", help="Scan for unit registry")
    parser.add_argument("--trace-method", type=str, help="Trace a Lua method implementation")
    parser.add_argument("--find-refs", type=str, help="Find code references to a string")
    parser.add_argument("--all", action="store_true", help="Run all scans")
    parser.add_argument("--process", default="rift_x64.exe", help="Process name")

    args = parser.parse_args()

    # Default to all if no specific scan selected
    if not any(
        [
            args.scan_strings,
            args.validate_sigs,
            args.find_player,
            args.find_unit_registry,
            args.trace_method,
            args.find_refs,
            args.all,
        ]
    ):
        args.all = True

    print("=" * 60)
    print("RIFT Live Memory Scanner")
    print("=" * 60)
    print(f"Target: {args.process}")
    print()

    with RIFTMemoryScanner() as scanner:
        # Find and open process
        if not scanner.find_process(args.process):
            sys.exit(1)

        if not scanner.open_process():
            sys.exit(1)

        if not scanner.find_module():
            sys.exit(1)

        # Run requested scans
        if args.all or args.scan_strings:
            scanner.scan_strings_area()

        if args.all or args.validate_sigs:
            scanner.validate_signatures()

        if args.all or args.find_player:
            scanner.find_player_object()

        if args.all or args.find_unit_registry:
            scanner.scan_for_unit_registry()

        if args.trace_method:
            scanner.trace_lua_method(args.trace_method)

        if args.find_refs:
            # Find RVA of the string
            refs = scanner.scan_string(args.find_refs)
            if refs:
                string_rva = refs[0] - scanner.module_base
                scanner.find_code_references(string_rva, args.find_refs)

    print("\n" + "=" * 60)
    print("SCAN COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
