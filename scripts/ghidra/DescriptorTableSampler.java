// Reusable Ghidra script. Samples computed descriptor-table entries for candidate-only review.

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

public class DescriptorTableSampler extends GhidraScript {
    private static final int MAX_BYTE_COUNT = 64;

    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 5) {
            printerr("Usage: DescriptorTableSampler.java <output-json> <stride-bytes> <byte-count> <index>... <field:base:offset>...");
            return;
        }

        File outFile = new File(args[0]);
        File parent = outFile.getParentFile();
        if (parent != null) {
            parent.mkdirs();
        }
        int strideBytes = parseNumber(args[1]);
        int byteCount = parseNumber(args[2]);
        if (strideBytes <= 0) {
            printerr("DescriptorTableSampler requires a positive stride.");
            return;
        }
        if (byteCount <= 0 || byteCount > MAX_BYTE_COUNT) {
            printerr("DescriptorTableSampler byte-count must be between 1 and " + MAX_BYTE_COUNT + ".");
            return;
        }
        SampleRequest request = parseSampleRequest(args);
        List<Integer> indices = request.indices;
        List<FieldSpec> fields = request.fields;

        Map<String, Object> report = new LinkedHashMap<String, Object>();
        report.put("SchemaVersion", "ghidra-descriptor-table-sample/v1");
        report.put("CandidateOnly", true);
        report.put("FieldOrderPromoted", false);
        report.put("ParserExportPromotionAllowed", false);
        report.put("programName", currentProgram.getName());
        report.put("imageBase", currentProgram.getImageBase().toString());
        report.put("strideBytes", strideBytes);
        report.put("byteCountRequested", byteCount);
        report.put("indexCount", indices.size());
        report.put("fieldCount", fields.size());

        List<Map<String, Object>> rows = new ArrayList<Map<String, Object>>();
        Memory memory = currentProgram.getMemory();
        for (FieldSpec field : fields) {
            Address baseAddress = currentProgram.getAddressFactory().getAddress(field.baseAddress);
            for (Integer index : indices) {
                Map<String, Object> row = new LinkedHashMap<String, Object>();
                row.put("field", field.fieldName);
                row.put("baseAddress", field.baseAddress);
                row.put("staticTableOffsetBytes", field.staticTableOffsetBytes);
                row.put("index", index);
                row.put("indexHex", String.format("%02x", index));
                row.put("strideBytes", strideBytes);
                row.put("byteCountRequested", byteCount);
                if (baseAddress == null) {
                    row.put("computedAddress", "");
                    row.put("byteCountRead", 0);
                    row.put("bytes", "");
                    row.put("error", "invalid-base-address");
                    rows.add(row);
                    continue;
                }
                try {
                    Address computedAddress = baseAddress.add((long) index * (long) strideBytes);
                    row.put("computedAddress", computedAddress.toString());
                    if (memory.getBlock(computedAddress) == null) {
                        row.put("byteCountRead", 0);
                        row.put("bytes", "");
                        row.put("error", "computed-address-not-memory-backed");
                    } else {
                        byte[] bytes = new byte[byteCount];
                        int bytesRead = memory.getBytes(computedAddress, bytes);
                        row.put("byteCountRead", bytesRead);
                        row.put("bytes", bytesToHex(bytes, bytesRead));
                    }
                } catch (Exception ex) {
                    row.put("computedAddress", "");
                    row.put("byteCountRead", 0);
                    row.put("bytes", "");
                    row.put("error", ex.getClass().getSimpleName() + ": " + ex.getMessage());
                }
                rows.add(row);
            }
        }
        report.put("rowCount", rows.size());
        report.put("rows", rows);
        report.put(
            "interpretation",
            "Candidate-only indexed descriptor-table bytes. Use these rows to compare static table entries against copied-sample descriptor records; do not promote parser/export behavior from this report alone."
        );

        BufferedWriter writer = new BufferedWriter(new OutputStreamWriter(new FileOutputStream(outFile), "UTF-8"));
        try {
            writer.write(toJson(report));
            writer.newLine();
        } finally {
            writer.close();
        }
        println("DescriptorTableSampler wrote: " + outFile.getAbsolutePath());
    }

    private int parseNumber(String value) {
        String trimmed = value.trim().toLowerCase();
        if (trimmed.startsWith("0x")) {
            return Integer.parseInt(trimmed.substring(2), 16);
        }
        if (trimmed.matches(".*[a-f].*")) {
            return Integer.parseInt(trimmed, 16);
        }
        return Integer.parseInt(trimmed);
    }

    private SampleRequest parseSampleRequest(String[] args) {
        SampleRequest request = new SampleRequest();
        for (int i = 3; i < args.length; i++) {
            String[] parts = args[i].split(":", 3);
            if (parts.length == 3) {
                request.fields.add(new FieldSpec(parts[0], normalizeAddress(parts[1]), parseNumber(parts[2])));
                continue;
            }
            for (String indexPart : args[i].split(",")) {
                String trimmed = indexPart.trim();
                if (!trimmed.isEmpty()) {
                    request.indices.add(parseDescriptorIndex(trimmed));
                }
            }
        }
        return request;
    }

    private int parseDescriptorIndex(String value) {
        String trimmed = value.trim().toLowerCase();
        if (trimmed.startsWith("0x")) {
            int parsed = Integer.parseInt(trimmed.substring(2), 16);
            return boundedDescriptorIndex(value, parsed);
        }
        int parsed = Integer.parseInt(trimmed, 16);
        return boundedDescriptorIndex(value, parsed);
    }

    private int boundedDescriptorIndex(String value, int parsed) {
        if (parsed < 0 || parsed > 0xff) {
            throw new IllegalArgumentException("descriptor index out of byte range: " + value);
        }
        return parsed;
    }

    private String normalizeAddress(String value) {
        return value.trim().toLowerCase().replaceFirst("^0x", "");
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
        int staticTableOffsetBytes;

        FieldSpec(String fieldName, String baseAddress, int staticTableOffsetBytes) {
            this.fieldName = fieldName;
            this.baseAddress = baseAddress;
            this.staticTableOffsetBytes = staticTableOffsetBytes;
        }
    }

    private static class SampleRequest {
        List<Integer> indices = new ArrayList<Integer>();
        List<FieldSpec> fields = new ArrayList<FieldSpec>();
    }
}
