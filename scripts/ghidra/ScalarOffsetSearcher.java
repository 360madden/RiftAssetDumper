// ScalarOffsetSearcher.java — Ghidra script that finds instructions accessing
// specific memory offsets. Designed to locate player coordinate access code in
// rift_x64.exe by searching for scalar operands matching known field offsets
// (+0x304, +0x30C, +0x310, +0x314, +0x320, +0x324, +0x328).
//
// Usage:
//   ScalarOffsetSearcher.java <output-json> <offset1> <offset2> ...
//
// Example:
//   ScalarOffsetSearcher.java player-offsets.json 0x304 0x30C 0x310 0x320 0x324 0x328

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.scalar.Scalar;
import ghidra.util.exception.CancelledException;

import java.io.*;
import java.util.*;

public class ScalarOffsetSearcher extends GhidraScript {

    private static final int MAX_RESULTS_PER_OFFSET = 200;
    private static final int CONTEXT_INSTRUCTIONS = 2;

    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2) {
            printerr("Usage: ScalarOffsetSearcher.java <output-json> <offset1> <offset2> ...");
            printerr("Example: ScalarOffsetSearcher.java player-offsets.json 0x304 0x30C 0x310 0x320 0x324 0x328");
            return;
        }

        File outFile = new File(args[0]);
        File parent = outFile.getParentFile();
        if (parent != null) {
            parent.mkdirs();
        }

        // Parse target offsets
        List<Long> targetOffsets = new ArrayList<>();
        for (int i = 1; i < args.length; i++) {
            targetOffsets.add(parseOffset(args[i]));
        }
        println("Searching for offsets: " + targetOffsets);

        // Results grouped by offset
        Map<Long, List<Map<String, Object>>> resultsByOffset = new LinkedHashMap<>();
        for (Long offset : targetOffsets) {
            resultsByOffset.put(offset, new ArrayList<>());
        }

        // Iterate ALL instructions
        long totalInstructions = 0;
        long matchedInstructions = 0;
        InstructionIterator iter = currentProgram.getListing().getInstructions(true);

        while (iter.hasNext() && !monitor.isCancelled()) {
            Instruction instr = iter.next();
            totalInstructions++;

            // Check each operand for matching scalar values
            for (int opIdx = 0; opIdx < instr.getNumOperands(); opIdx++) {
                Scalar scalar = instr.getScalar(opIdx);
                if (scalar == null) continue;

                long value = scalar.getValue();
                if (!targetOffsets.contains(value)) continue;

                List<Map<String, Object>> results = resultsByOffset.get(value);
                if (results != null && results.size() < MAX_RESULTS_PER_OFFSET) {
                    Map<String, Object> hit = new LinkedHashMap<>();
                    hit.put("address", instr.getAddress().toString());
                    hit.put("mnemonic", instr.getMnemonicString());
                    hit.put("operandIndex", opIdx);
                    hit.put("scalarValue", value);
                    hit.put("scalarHex", String.format("0x%x", value));
                    hit.put("instructionText", instr.toString());
                    hit.put("byteLength", instr.getLength());

                    // Get instruction bytes
                    try {
                        byte[] bytes = new byte[instr.getLength()];
                        currentProgram.getMemory().getBytes(instr.getAddress(), bytes);
                        hit.put("instructionBytes", bytesToHex(bytes));
                    } catch (CancelledException ce) {
                        // Same cancellation-propagation rule as the context walks —
                        // a cancel mid-bytes-read must not be silently swallowed.
                        throw ce;
                    } catch (Exception ex) {
                        hit.put("instructionBytes", "");
                    }

                    // Get containing function
                    Function func = getFunctionContaining(instr.getAddress());
                    if (func != null) {
                        hit.put("functionName", func.getName());
                        hit.put("functionEntry", func.getEntryPoint().toString());
                        hit.put("functionSignature", func.getSignature().toString());
                    } else {
                        hit.put("functionName", "");
                        hit.put("functionEntry", "");
                        hit.put("functionSignature", "");
                    }

                    // Get context (nearby instructions)
                    List<Map<String, String>> context = new ArrayList<>();
                    List<String> contextWarnings = null;  // folded per-hit summary
                    Address addr = instr.getAddress();
                    try {
                        // Previous instructions
                        Address prevAddr = addr;
                        for (int c = 0; c < CONTEXT_INSTRUCTIONS; c++) {
                            Address nextPrev = prevAddr.previous();
                            if (nextPrev == null) break;
                            prevAddr = nextPrev;
                            Instruction prevInstr = currentProgram.getListing().getInstructionAt(prevAddr);
                            if (prevInstr != null) {
                                Map<String, String> ctx = new LinkedHashMap<>();
                                ctx.put("address", prevInstr.getAddress().toString());
                                ctx.put("text", prevInstr.toString());
                                ctx.put("isTarget", "false");
                                context.add(0, ctx);
                            }
                        }
                    } catch (CancelledException ce) {
                        // User cancellation must propagate. The plain `catch (Exception)` block
                        // previously swallowed it as just-another-exception, which froze the
                        // script run; monitor.checkCancelled() could not drain cleanup work.
                        throw ce;
                    } catch (Exception ex) {
                        // Non-cancellation failure: accumulate into per-hit summary
                        // so the next-context warning folds into ONE printerr line.
                        if (contextWarnings == null) {
                            contextWarnings = new ArrayList<>();
                        }
                        contextWarnings.add("previous:" + ex.getClass().getName() + ":" + ex.getMessage());
                    }

                    // Target instruction
                    Map<String, String> targetCtx = new LinkedHashMap<>();
                    targetCtx.put("address", instr.getAddress().toString());
                    targetCtx.put("text", instr.toString());
                    targetCtx.put("isTarget", "true");
                    context.add(targetCtx);

                    // Next instructions
                    try {
                        Address nextAddr = addr;
                        for (int c = 0; c < CONTEXT_INSTRUCTIONS; c++) {
                            Address nextNext = nextAddr.next();
                            if (nextNext == null) break;
                            nextAddr = nextNext;
                            Instruction nextInstr = currentProgram.getListing().getInstructionAt(nextAddr);
                            if (nextInstr != null) {
                                Map<String, String> ctx = new LinkedHashMap<>();
                                ctx.put("address", nextInstr.getAddress().toString());
                                ctx.put("text", nextInstr.toString());
                                ctx.put("isTarget", "false");
                                context.add(ctx);
                            }
                        }
                    } catch (CancelledException ce) {
                        // User cancellation must propagate (see prev-walk catch above).
                        throw ce;
                    } catch (Exception ex) {
                        // Non-cancellation failure: accumulate into per-hit summary.
                        if (contextWarnings == null) {
                            contextWarnings = new ArrayList<>();
                        }
                        contextWarnings.add("next:" + ex.getClass().getName() + ":" + ex.getMessage());
                    }

                    // Single summary printerr line per hit (covers both walks).
                    // Bounds per-offset noise regardless of hit count.
                    if (contextWarnings != null) {
                        printerr("WARN: scalar-offset-search partial context at "
                                + addr + " (" + String.join("; ", contextWarnings) + ")");
                    }

                    hit.put("context", context);
                    results.add(hit);
                    matchedInstructions++;
                }
            }
        }

        // Build report
        Map<String, Object> report = new LinkedHashMap<>();
        report.put("SchemaVersion", "ghidra-scalar-offset-search/v1");
        report.put("CandidateOnly", true);
        report.put("programName", currentProgram.getName());
        report.put("imageBase", currentProgram.getImageBase().toString());
        report.put("totalInstructionsScanned", totalInstructions);
        report.put("totalMatches", matchedInstructions);
        report.put("targetOffsets", targetOffsets);

        List<Map<String, Object>> offsetSummaries = new ArrayList<>();
        for (Long offset : targetOffsets) {
            List<Map<String, Object>> hits = resultsByOffset.get(offset);
            Map<String, Object> summary = new LinkedHashMap<>();
            summary.put("offset", offset);
            summary.put("offsetHex", String.format("0x%x", offset));
            summary.put("matchCount", hits != null ? hits.size() : 0);
            summary.put("truncated", hits != null && hits.size() >= MAX_RESULTS_PER_OFFSET);
            summary.put("hits", hits != null ? hits : new ArrayList<>());
            offsetSummaries.add(summary);
        }
        report.put("results", offsetSummaries);

        // Write JSON
        BufferedWriter writer = new BufferedWriter(new OutputStreamWriter(new FileOutputStream(outFile), "UTF-8"));
        try {
            writer.write(toJson(report));
            writer.newLine();
        } finally {
            writer.close();
        }

        println("ScalarOffsetSearcher wrote: " + outFile.getAbsolutePath());
        println("Scanned " + totalInstructions + " instructions, found " + matchedInstructions + " matches.");
    }

    private long parseOffset(String value) {
        String trimmed = value.trim().toLowerCase();
        if (trimmed.startsWith("0x")) {
            return Long.parseLong(trimmed.substring(2), 16);
        }
        return Long.parseLong(trimmed);
    }

    private String bytesToHex(byte[] bytes) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < bytes.length; i++) {
            if (i > 0) sb.append(' ');
            sb.append(String.format("%02x", bytes[i] & 0xff));
        }
        return sb.toString();
    }

    private String toJson(Object value) {
        if (value == null) return "null";
        if (value instanceof String) return quote((String) value);
        if (value instanceof Number || value instanceof Boolean) return value.toString();
        if (value instanceof Map) {
            StringBuilder sb = new StringBuilder();
            sb.append("{");
            boolean first = true;
            for (Object entryObj : ((Map<?, ?>) value).entrySet()) {
                Map.Entry<?, ?> entry = (Map.Entry<?, ?>) entryObj;
                if (!first) sb.append(",");
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
                if (!first) sb.append(",");
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
                        sb.append(String.format("\\u%04x", (int) c));
                    } else {
                        sb.append(c);
                    }
            }
        }
        sb.append('"');
        return sb.toString();
    }
}
