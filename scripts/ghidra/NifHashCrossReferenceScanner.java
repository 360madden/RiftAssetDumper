// Searches the entire binary for a NIF hash IdPrefix (16-char hex, e.g. cf54e712ff57eaac)
// as both an ASCII string literal and a raw 8-byte LE value.
// Reports every occurrence with containing function, cross-references, and decompiled context.
//
// Usage: NifHashCrossReferenceScanner.java <nif-hash> <output-json>
//   nif-hash: 16-character hex NIF IdPrefix (e.g. cf54e712ff57eaac)
//   output-json: path to write the JSON report

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryAccessException;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.program.model.symbol.SourceType;
import ghidra.program.model.data.AbstractStringDataType;
import ghidra.program.model.data.StringDataInstance;
import ghidra.program.model.listing.Data;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Symbol;

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStreamWriter;
import java.math.BigInteger;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

public class NifHashCrossReferenceScanner extends GhidraScript {

    // The exact ASCII bytes of the hash string (16 bytes, no null)
    private byte[] hashBytes;

    // The raw 64-bit value of the hash as little-endian bytes (8 bytes)
    private byte[] rawLeBytes;

    // The hash string for display
    private String hashString;

    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2) {
            printerr("Usage: NifHashCrossReferenceScanner.java <nif-hash> <output-json>");
            printerr("  nif-hash: 16-character hex NIF IdPrefix (e.g. cf54e712ff57eaac)");
            return;
        }

        hashString = args[0].trim().toLowerCase();
        if (hashString.length() != 16 || !hashString.matches("[0-9a-f]{16}")) {
            printerr("Invalid NIF hash: must be exactly 16 hexadecimal characters (e.g. cf54e712ff57eaac)");
            return;
        }

        File outFile = new File(args[1]);
        File parent = outFile.getParentFile();
        if (parent != null) {
            parent.mkdirs();
        }

        // Prepare search patterns
        hashBytes = hashString.getBytes("ASCII");          // 16 ASCII bytes
        BigInteger bigVal = new BigInteger(hashString, 16);
        // Raw 64-bit value as little-endian bytes (8 bytes, least significant first)
        byte[] raw = new byte[8];
        for (int i = 0; i < 8; i++) {
            raw[i] = (byte) ((bigVal.shiftRight(i * 8)).longValue() & 0xff);
        }
        rawLeBytes = raw;

        Map<String, Object> report = new LinkedHashMap<String, Object>();
        report.put("SchemaVersion", "ghidra-nif-hash-cross-reference-scan/v1");
        report.put("CandidateOnly", true);
        report.put("FieldOrderPromoted", false);
        report.put("ParserExportPromotionAllowed", false);
        report.put("hash", hashString);
        report.put("programName", currentProgram.getName());
        report.put("imageBase", currentProgram.getImageBase().toString());

        List<Map<String, Object>> stringMatches = new ArrayList<Map<String, Object>>();
        List<Map<String, Object>> rawMatches = new ArrayList<Map<String, Object>>();

        println("Scanning " + currentProgram.getName() + " for NIF hash: " + hashString);
        println("  ASCII string bytes: " + bytesToHex(hashBytes));
        println("  Raw LE uint64 bytes: " + bytesToHex(rawLeBytes));

        // ── Scan 1: Search memory for the ASCII string ──
        Memory memory = currentProgram.getMemory();
        int totalMemoryScanned = 0;
        Set<String> visitedFunctions = new HashSet<String>();

        try {
            List<Address> asciiHits = findBytes(memory, hashBytes);
            println("  ASCII string match count: " + asciiHits.size());

            for (Address addr : asciiHits) {
                Map<String, Object> match = describeMatch(addr, "ascii-string");
                stringMatches.add(match);
                totalMemoryScanned++;
            }
        } catch (Exception ex) {
            printerr("  ASCII scan error: " + ex.getClass().getSimpleName() + ": " + ex.getMessage());
        }

        // ── Scan 2: Search memory for the raw 8-byte LE value ──
        try {
            List<Address> rawHits = findBytes(memory, rawLeBytes);
            println("  Raw LE uint64 match count: " + rawHits.size());

            for (Address addr : rawHits) {
                Map<String, Object> match = describeMatch(addr, "raw-uint64-le");
                rawMatches.add(match);
                totalMemoryScanned++;
            }
        } catch (Exception ex) {
            printerr("  Raw value scan error: " + ex.getClass().getSimpleName() + ": " + ex.getMessage());
        }

        // ── Scan 3: Search for cross-references to any match address ──
        List<Map<String, Object>> allRefs = new ArrayList<Map<String, Object>>();
        List<Map<String, Object>> decompileResults = new ArrayList<Map<String, Object>>();
        Set<String> seenCallers = new HashSet<String>();

        for (Map<String, Object> match : stringMatches) {
            collectCrossReferences(match, allRefs, seenCallers, decompileResults);
        }
        for (Map<String, Object> match : rawMatches) {
            collectCrossReferences(match, allRefs, seenCallers, decompileResults);
        }

        report.put("stringMatchCount", stringMatches.size());
        report.put("rawMatchCount", rawMatches.size());
        report.put("totalMatchCount", stringMatches.size() + rawMatches.size());
        report.put("crossReferenceCount", allRefs.size());
        report.put("uniqueReferencingFunctions", seenCallers.size());
        report.put("stringMatches", stringMatches);
        report.put("rawMatches", rawMatches);
        report.put("crossReferences", allRefs);
        report.put("decompiledFunctions", decompileResults);

        // ── Also scan nearby labeled strings for names ──
        List<Map<String, Object>> nearbyStrings = scanNearbyStrings(stringMatches, rawMatches);
        report.put("nearbyLabeledStrings", nearbyStrings);

        // ── Write output ──
        BufferedWriter writer = new BufferedWriter(new OutputStreamWriter(new FileOutputStream(outFile), "UTF-8"));
        try {
            writer.write(toJson(report));
            writer.newLine();
        } finally {
            writer.close();
        }
        println("NifHashCrossReferenceScanner wrote: " + outFile.getAbsolutePath());
        println("  Summary: " + (stringMatches.size() + rawMatches.size()) + " matches, "
            + allRefs.size() + " cross-refs, "
            + seenCallers.size() + " referencing functions");
    }

    private List<Address> findBytes(Memory memory, byte[] pattern) throws Exception {
        List<Address> hits = new ArrayList<Address>();
        if (pattern == null || pattern.length == 0) {
            return hits;
        }

        int maxHits = 256; // safety limit per scan

        // Iterate over each memory block and search within its bounds
        MemoryBlock[] blocks = memory.getBlocks();
        for (MemoryBlock block : blocks) {
            if (hits.size() >= maxHits) break;

            Address blockStart = block.getStart();
            Address current = blockStart;

            while (hits.size() < maxHits) {
                Address found = memory.findBytes(current, pattern, null, true, monitor);
                if (found == null || !block.contains(found)) {
                    break;
                }
                hits.add(found);
                current = found.add(1);
                // Avoid spinning on the same position if pattern is self-overlapping
                if (current.equals(found)) {
                    current = found.add(pattern.length);
                }
                if (monitor.isCancelled()) {
                    break;
                }
            }
            if (monitor.isCancelled()) {
                break;
            }
        }

        return hits;
    }

    private Map<String, Object> describeMatch(Address address, String matchType) {
        Map<String, Object> item = new LinkedHashMap<String, Object>();
        item.put("address", address.toString());
        item.put("matchType", matchType);
        item.put("imageBaseOffset", computeOffset(address));

        // Check if inside a defined function
        Function function = getFunctionContaining(address);
        if (function != null) {
            item.put("inFunction", true);
            item.put("functionName", function.getName());
            item.put("functionEntry", function.getEntryPoint().toString());
            item.put("functionSignature", function.getSignature().toString());
        } else {
            item.put("inFunction", false);
        }

        // Show bytes around the match
        Memory memory = currentProgram.getMemory();
        try {
            byte[] context = new byte[64];
            // Read 32 bytes before and 32 after (or as much as possible)
            Address start = address.subtract(16);
            int bytesRead = memory.getBytes(start, context);
            item.put("contextBytes", bytesToHex(context, bytesRead));
            item.put("contextStartAddress", start.toString());
        } catch (Exception ex) {
            item.put("contextBytes", "<error: " + ex.getMessage() + ">");
        }

        // Check if the address is inside a defined data type (e.g., string label)
        Data dataAt = currentProgram.getListing().getDefinedDataAt(address);
        if (dataAt != null) {
            item.put("definedDataType", dataAt.getDataType().getName());
            item.put("definedDataValue", String.valueOf(dataAt.getValue()));
        }

        return item;
    }

    private void collectCrossReferences(
            Map<String, Object> match,
            List<Map<String, Object>> allRefs,
            Set<String> seenCallers,
            List<Map<String, Object>> decompileResults)
            throws Exception {

        String addrStr = (String) match.get("address");
        if (addrStr == null) return;

        Address address = currentProgram.getAddressFactory().getAddress(addrStr);
        if (address == null) return;

        ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(address);
        int refCount = 0;
        while (refs.hasNext() && refCount < 50) {
            Reference ref = refs.next();
            refCount++;

            Map<String, Object> refItem = new LinkedHashMap<String, Object>();
            refItem.put("from", ref.getFromAddress().toString());
            refItem.put("type", ref.getReferenceType().toString());
            refItem.put("matchAddress", addrStr);
            refItem.put("matchType", match.get("matchType"));

            Function caller = getFunctionContaining(ref.getFromAddress());
            if (caller != null) {
                refItem.put("callerFunction", caller.getName());
                refItem.put("callerEntry", caller.getEntryPoint().toString());

                String callerKey = caller.getEntryPoint().toString();
                if (seenCallers.add(callerKey)) {
                    // Decompile this function if we haven't already
                    Map<String, Object> decompItem = new LinkedHashMap<String, Object>();
                    decompItem.put("functionName", caller.getName());
                    decompItem.put("functionEntry", caller.getEntryPoint().toString());
                    decompItem.put("functionSignature", caller.getSignature().toString());
                    decompItem.put("referencedHash", hashString);
                    decompItem.put("decompile", decompile(caller));
                    decompileResults.add(decompItem);
                }

                // Also collect the calling instruction for context
                Instruction instr = currentProgram.getListing().getInstructionAt(ref.getFromAddress());
                if (instr != null) {
                    refItem.put("instructionMnemonic", instr.getMnemonicString());
                    refItem.put("instructionOpStr", instr.toString());
                    try {
                        refItem.put("instructionBytes", bytesToHex(instr.getBytes()));
                    } catch (Exception ex) {
                        refItem.put("instructionBytes", "<unavailable>");
                    }
                }
            } else {
                refItem.put("callerFunction", null);
            }

            allRefs.add(refItem);
        }
    }

    private String computeOffset(Address address) {
        try {
            long imageBase = currentProgram.getImageBase().getOffset();
            long addr = address.getOffset();
            long offset = addr - imageBase;
            return String.format("0x%x", offset);
        } catch (Exception ex) {
            return address.toString();
        }
    }

    private List<Map<String, Object>> scanNearbyStrings(
            List<Map<String, Object>> stringMatches,
            List<Map<String, Object>> rawMatches) {

        List<Map<String, Object>> results = new ArrayList<Map<String, Object>>();
        Set<String> seen = new HashSet<String>();

        // Walk all match addresses and their full matching function bodies
        // searching for human-readable string data nearby.
        for (Map<String, Object> match : stringMatches) {
            String addrStr = (String) match.get("address");
            if (addrStr == null) continue;
            Address addr;
            try {
                addr = currentProgram.getAddressFactory().getAddress(addrStr);
            } catch (Exception ex) {
                continue;
            }
            Function fn = getFunctionContaining(addr);
            if (fn == null) continue;

            String fnKey = fn.getEntryPoint().toString();
            if (!seen.add(fnKey)) continue;

            List<Map<String, Object>> nearbyStrings = new ArrayList<Map<String, Object>>();

            // Walk the function body looking for defined string data
            Listing listing = currentProgram.getListing();
            Data data = listing.getDefinedDataAfter(fn.getBody().getMinAddress());
            while (data != null && fn.getBody().contains(data.getAddress())) {
                if (data.getDataType() instanceof AbstractStringDataType) {
                    String strVal = StringDataInstance.getStringDataInstance(data).getStringValue();
                    if (strVal != null && strVal.length() > 2) {
                        Map<String, Object> s = new LinkedHashMap<String, Object>();
                        s.put("address", data.getAddress().toString());
                        s.put("value", strVal.length() > 100 ? strVal.substring(0, 100) + "..." : strVal);
                        s.put("label", getLabelAt(data.getAddress()));
                        nearbyStrings.add(s);
                    }
                }
                data = listing.getDefinedDataAfter(data.getAddress());
            }

            if (!nearbyStrings.isEmpty()) {
                Map<String, Object> fnStrings = new LinkedHashMap<String, Object>();
                fnStrings.put("functionName", fn.getName());
                fnStrings.put("functionEntry", fn.getEntryPoint().toString());
                fnStrings.put("strings", nearbyStrings);
                results.add(fnStrings);
            }
        }

        return results;
    }

    private String getLabelAt(Address address) {
        Symbol symbol = currentProgram.getSymbolTable().getPrimarySymbol(address);
        if (symbol != null) {
            return symbol.getName();
        }
        return null;
    }

    private Map<String, Object> decompile(Function function) {
        Map<String, Object> item = new LinkedHashMap<String, Object>();
        DecompInterface decompiler = new DecompInterface();
        try {
            decompiler.openProgram(currentProgram);
            DecompileResults results = decompiler.decompileFunction(function, 120, monitor);
            item.put("completed", results.decompileCompleted());
            item.put("errorMessage", results.getErrorMessage());
            if (results.decompileCompleted() && results.getDecompiledFunction() != null) {
                item.put("c", results.getDecompiledFunction().getC());
            }
        } finally {
            decompiler.dispose();
        }
        return item;
    }

    private String bytesToHex(byte[] bytes) {
        return bytesToHex(bytes, bytes.length);
    }

    private String bytesToHex(byte[] bytes, int length) {
        StringBuilder sb = new StringBuilder();
        int boundedLength = Math.max(0, Math.min(length, bytes.length));
        for (int i = 0; i < boundedLength; i++) {
            if (i > 0) {
                sb.append(' ');
            }
            sb.append(String.format("%02x", bytes[i] & 0xff));
        }
        return sb.toString();
    }

    private String toJson(Object value) {
        if (value == null) {
            return "null";
        }
        if (value instanceof String) {
            return quote((String) value);
        }
        if (value instanceof Number || value instanceof Boolean) {
            return value.toString();
        }
        if (value instanceof Map) {
            StringBuilder sb = new StringBuilder();
            sb.append("{");
            boolean first = true;
            for (Object entryObj : ((Map<?, ?>) value).entrySet()) {
                Map.Entry<?, ?> entry = (Map.Entry<?, ?>) entryObj;
                if (!first) {
                    sb.append(",");
                }
                first = false;
                sb.append(quote(String.valueOf(entry.getKey())));
                sb.append(":");
                sb.append(toJson(entry.getValue()));
            }
            sb.append("}");
            return sb.toString();
        }
        if (value instanceof Iterable) {
            StringBuilder sb = new StringBuilder();
            sb.append("[");
            boolean first = true;
            for (Object item : (Iterable<?>) value) {
                if (!first) {
                    sb.append(",");
                }
                first = false;
                sb.append(toJson(item));
            }
            sb.append("]");
            return sb.toString();
        }
        return quote(String.valueOf(value));
    }

    private String quote(String value) {
        StringBuilder sb = new StringBuilder();
        sb.append('"');
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            switch (c) {
                case '"': sb.append("\\\""); break;
                case '\\': sb.append("\\\\"); break;
                case '\b': sb.append("\\b"); break;
                case '\f': sb.append("\\f"); break;
                case '\n': sb.append("\\n"); break;
                case '\r': sb.append("\\r"); break;
                case '\t': sb.append("\\t"); break;
                default:
                    if (c < 0x20) {
                        sb.append(String.format("\\u%04x", (int)c));
                    } else {
                        sb.append(c);
                    }
            }
        }
        sb.append('"');
        return sb.toString();
    }
}
