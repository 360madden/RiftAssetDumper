// Reusable Ghidra script. Scans a bounded neighborhood around candidate descriptor-table references.

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.Memory;

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStreamWriter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class DescriptorTableNeighborhoodScanner extends GhidraScript {
    private static final int MAX_WINDOW_BYTES = 8192;
    private static final int MAX_BYTE_COUNT = 32;
    private static final int MAX_HITS = 512;

    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 7) {
            printerr("Usage: DescriptorTableNeighborhoodScanner.java <output-json> <before-bytes> <after-bytes> <step-bytes> <byte-count> <max-hits> <field:base>...");
            return;
        }

        File outFile = new File(args[0]);
        File parent = outFile.getParentFile();
        if (parent != null) {
            parent.mkdirs();
        }
        int beforeBytes = parseNumber(args[1]);
        int afterBytes = parseNumber(args[2]);
        int stepBytes = parseNumber(args[3]);
        int byteCount = parseNumber(args[4]);
        int maxHits = parseNumber(args[5]);
        if (beforeBytes < 0 || afterBytes < 0 || beforeBytes > MAX_WINDOW_BYTES || afterBytes > MAX_WINDOW_BYTES) {
            printerr("DescriptorTableNeighborhoodScanner window must be between 0 and " + MAX_WINDOW_BYTES + " bytes on each side.");
            return;
        }
        if (stepBytes <= 0 || stepBytes > 256) {
            printerr("DescriptorTableNeighborhoodScanner step must be between 1 and 256 bytes.");
            return;
        }
        if (byteCount <= 0 || byteCount > MAX_BYTE_COUNT) {
            printerr("DescriptorTableNeighborhoodScanner byte-count must be between 1 and " + MAX_BYTE_COUNT + ".");
            return;
        }
        if (maxHits <= 0 || maxHits > MAX_HITS) {
            printerr("DescriptorTableNeighborhoodScanner max-hits must be between 1 and " + MAX_HITS + ".");
            return;
        }

        List<FieldSpec> fields = parseFields(args);
        Map<String, Object> report = new LinkedHashMap<String, Object>();
        report.put("SchemaVersion", "ghidra-descriptor-table-neighborhood-scan/v1");
        report.put("CandidateOnly", true);
        report.put("FieldOrderPromoted", false);
        report.put("ParserExportPromotionAllowed", false);
        report.put("programName", currentProgram.getName());
        report.put("imageBase", currentProgram.getImageBase().toString());
        report.put("beforeBytes", beforeBytes);
        report.put("afterBytes", afterBytes);
        report.put("stepBytes", stepBytes);
        report.put("byteCountRequested", byteCount);
        report.put("maxHits", maxHits);
        report.put("fieldCount", fields.size());

        List<Map<String, Object>> hits = new ArrayList<Map<String, Object>>();
        int scannedRows = 0;
        int memoryBackedRows = 0;
        int skippedRows = 0;
        boolean truncated = false;
        Memory memory = currentProgram.getMemory();
        for (FieldSpec field : fields) {
            Address baseAddress = currentProgram.getAddressFactory().getAddress(field.baseAddress);
            if (baseAddress == null) {
                skippedRows++;
                continue;
            }
            for (int relativeOffset = -beforeBytes; relativeOffset <= afterBytes; relativeOffset += stepBytes) {
                scannedRows++;
                Address address;
                try {
                    address = baseAddress.add(relativeOffset);
                } catch (Exception ex) {
                    skippedRows++;
                    continue;
                }
                if (memory.getBlock(address) == null) {
                    skippedRows++;
                    continue;
                }
                memoryBackedRows++;
                byte[] bytes = new byte[byteCount];
                int bytesRead;
                try {
                    bytesRead = memory.getBytes(address, bytes);
                } catch (Exception ex) {
                    skippedRows++;
                    continue;
                }
                if (!hasNonZero(bytes, bytesRead)) {
                    continue;
                }
                Map<String, Object> hit = new LinkedHashMap<String, Object>();
                hit.put("field", field.fieldName);
                hit.put("baseAddress", field.baseAddress);
                hit.put("relativeOffsetBytes", relativeOffset);
                hit.put("address", address.toString());
                hit.put("byteCountRead", bytesRead);
                hit.put("bytes", bytesToHex(bytes, bytesRead));
                hits.add(hit);
                if (hits.size() >= maxHits) {
                    truncated = true;
                    break;
                }
            }
            if (truncated) {
                break;
            }
        }
        report.put("scannedRowCount", scannedRows);
        report.put("memoryBackedRowCount", memoryBackedRows);
        report.put("skippedRowCount", skippedRows);
        report.put("hitCount", hits.size());
        report.put("truncated", truncated);
        report.put("hits", hits);
        report.put(
            "interpretation",
            "Candidate-only bounded nonzero-byte neighborhood scan around descriptor-table data references. Hits are triage leads only and must not change parser/export behavior."
        );

        BufferedWriter writer = new BufferedWriter(new OutputStreamWriter(new FileOutputStream(outFile), "UTF-8"));
        try {
            writer.write(toJson(report));
            writer.newLine();
        } finally {
            writer.close();
        }
        println("DescriptorTableNeighborhoodScanner wrote: " + outFile.getAbsolutePath());
    }

    private int parseNumber(String value) {
        String trimmed = value.trim().toLowerCase();
        if (trimmed.startsWith("0x")) {
            return Integer.parseInt(trimmed.substring(2), 16);
        }
        return Integer.parseInt(trimmed);
    }

    private List<FieldSpec> parseFields(String[] args) {
        List<FieldSpec> fields = new ArrayList<FieldSpec>();
        for (int i = 6; i < args.length; i++) {
            String[] parts = args[i].split(":", 2);
            if (parts.length == 2) {
                fields.add(new FieldSpec(parts[0], normalizeAddress(parts[1])));
            }
        }
        return fields;
    }

    private String normalizeAddress(String value) {
        return value.trim().toLowerCase().replaceFirst("^0x", "");
    }

    private boolean hasNonZero(byte[] bytes, int length) {
        int boundedLength = Math.max(0, Math.min(length, bytes.length));
        for (int i = 0; i < boundedLength; i++) {
            if ((bytes[i] & 0xff) != 0) {
                return true;
            }
        }
        return false;
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

    private static class FieldSpec {
        String fieldName;
        String baseAddress;

        FieldSpec(String fieldName, String baseAddress) {
            this.fieldName = fieldName;
            this.baseAddress = baseAddress;
        }
    }
}
