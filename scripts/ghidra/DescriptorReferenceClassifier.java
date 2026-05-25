// Reusable Ghidra script. Classifies references to candidate descriptor data addresses.

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.RefType;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.program.model.symbol.ReferenceManager;
import ghidra.program.model.symbol.Symbol;

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStreamWriter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class DescriptorReferenceClassifier extends GhidraScript {
    private static final int MAX_BYTE_COUNT = 64;
    private static final int MAX_REFS_PER_FIELD = 512;

    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 4) {
            printerr("Usage: DescriptorReferenceClassifier.java <output-json> <byte-count> <max-refs-per-field> <field:address>...");
            return;
        }

        File outFile = new File(args[0]);
        File parent = outFile.getParentFile();
        if (parent != null) {
            parent.mkdirs();
        }
        int byteCount = parseNumber(args[1]);
        int maxRefsPerField = parseNumber(args[2]);
        if (byteCount <= 0 || byteCount > MAX_BYTE_COUNT) {
            printerr("DescriptorReferenceClassifier byte-count must be between 1 and " + MAX_BYTE_COUNT + ".");
            return;
        }
        if (maxRefsPerField <= 0 || maxRefsPerField > MAX_REFS_PER_FIELD) {
            printerr("DescriptorReferenceClassifier max-refs-per-field must be between 1 and " + MAX_REFS_PER_FIELD + ".");
            return;
        }

        List<FieldSpec> fields = parseFields(args);
        Map<String, Object> report = new LinkedHashMap<String, Object>();
        report.put("SchemaVersion", "ghidra-descriptor-reference-classification/v1");
        report.put("CandidateOnly", true);
        report.put("FieldOrderPromoted", false);
        report.put("ParserExportPromotionAllowed", false);
        report.put("programName", currentProgram.getName());
        report.put("imageBase", currentProgram.getImageBase().toString());
        report.put("byteCountRequested", byteCount);
        report.put("maxRefsPerField", maxRefsPerField);
        report.put("fieldCount", fields.size());

        List<Map<String, Object>> fieldRows = new ArrayList<Map<String, Object>>();
        int totalReferenceCount = 0;
        int totalCapturedReferenceCount = 0;
        int fieldWithReferencesCount = 0;
        int readReferenceCount = 0;
        int writeReferenceCount = 0;
        int dataReferenceCount = 0;
        int addressLikeReferenceCount = 0;
        int uniqueReferencingFunctionCount = 0;
        Map<String, Object> globalFunctions = new LinkedHashMap<String, Object>();
        for (FieldSpec field : fields) {
            Map<String, Object> fieldRow = classifyField(field, byteCount, maxRefsPerField);
            fieldRows.add(fieldRow);
            int fieldReferenceCount = intValue(fieldRow.get("referenceCountTo"));
            int fieldCapturedCount = intValue(fieldRow.get("capturedReferenceCount"));
            totalReferenceCount += fieldReferenceCount;
            totalCapturedReferenceCount += fieldCapturedCount;
            if (fieldReferenceCount > 0) {
                fieldWithReferencesCount++;
            }
            readReferenceCount += intValue(fieldRow.get("readReferenceCount"));
            writeReferenceCount += intValue(fieldRow.get("writeReferenceCount"));
            dataReferenceCount += intValue(fieldRow.get("dataReferenceCount"));
            addressLikeReferenceCount += intValue(fieldRow.get("addressLikeReferenceCount"));
            Object referencesValue = fieldRow.get("references");
            if (referencesValue instanceof Iterable) {
                for (Object referenceValue : (Iterable<?>) referencesValue) {
                    if (!(referenceValue instanceof Map)) {
                        continue;
                    }
                    Object functionEntry = ((Map<?, ?>) referenceValue).get("fromFunctionEntry");
                    Object functionName = ((Map<?, ?>) referenceValue).get("fromFunction");
                    if (functionEntry instanceof String && !((String) functionEntry).isEmpty()) {
                        globalFunctions.put((String) functionEntry, functionName == null ? "" : functionName);
                    }
                }
            }
        }
        uniqueReferencingFunctionCount = globalFunctions.size();
        report.put("fields", fieldRows);
        report.put("totalReferenceCount", totalReferenceCount);
        report.put("totalCapturedReferenceCount", totalCapturedReferenceCount);
        report.put("fieldWithReferencesCount", fieldWithReferencesCount);
        report.put("readReferenceCount", readReferenceCount);
        report.put("writeReferenceCount", writeReferenceCount);
        report.put("dataReferenceCount", dataReferenceCount);
        report.put("addressLikeReferenceCount", addressLikeReferenceCount);
        report.put("uniqueReferencingFunctionCount", uniqueReferencingFunctionCount);
        report.put(
            "interpretation",
            "Candidate-only reference classification for descriptor data addresses. Reference kinds are triage leads only and must not change parser/export behavior."
        );

        BufferedWriter writer = new BufferedWriter(new OutputStreamWriter(new FileOutputStream(outFile), "UTF-8"));
        try {
            writer.write(toJson(report));
            writer.newLine();
        } finally {
            writer.close();
        }
        println("DescriptorReferenceClassifier wrote: " + outFile.getAbsolutePath());
    }

    private Map<String, Object> classifyField(FieldSpec field, int byteCount, int maxRefsPerField) {
        Map<String, Object> item = new LinkedHashMap<String, Object>();
        item.put("field", field.fieldName);
        item.put("address", field.address);
        Address address = currentProgram.getAddressFactory().getAddress(field.address);
        item.put("addressValid", address != null);
        List<Map<String, Object>> references = new ArrayList<Map<String, Object>>();
        item.put("references", references);
        if (address == null) {
            item.put("memoryBacked", false);
            item.put("byteCountRead", 0);
            item.put("bytes", "");
            item.put("symbolCount", 0);
            item.put("symbols", new ArrayList<Map<String, Object>>());
            item.put("referenceCountTo", 0);
            item.put("capturedReferenceCount", 0);
            item.put("referencesTruncated", false);
            putReferenceCounts(item, 0, 0, 0, 0, 0, 0);
            item.put("referencingFunctionCount", 0);
            return item;
        }

        Memory memory = currentProgram.getMemory();
        boolean memoryBacked = memory.getBlock(address) != null;
        item.put("memoryBacked", memoryBacked);
        if (memoryBacked) {
            try {
                byte[] bytes = new byte[byteCount];
                int bytesRead = memory.getBytes(address, bytes);
                item.put("byteCountRead", bytesRead);
                item.put("bytes", bytesToHex(bytes, bytesRead));
            } catch (Exception ex) {
                item.put("byteCountRead", 0);
                item.put("bytes", "");
                item.put("byteReadError", ex.getClass().getSimpleName() + ": " + ex.getMessage());
            }
        } else {
            item.put("byteCountRead", 0);
            item.put("bytes", "");
        }
        List<Map<String, Object>> symbols = collectSymbols(address);
        item.put("symbolCount", symbols.size());
        item.put("symbols", symbols);

        ReferenceManager referenceManager = currentProgram.getReferenceManager();
        ReferenceIterator refs = referenceManager.getReferencesTo(address);
        int referenceCount = 0;
        int capturedReferenceCount = 0;
        int readReferenceCount = 0;
        int writeReferenceCount = 0;
        int dataReferenceCount = 0;
        int addressLikeReferenceCount = 0;
        int flowReferenceCount = 0;
        Map<String, Object> functions = new LinkedHashMap<String, Object>();
        while (refs.hasNext()) {
            Reference ref = refs.next();
            referenceCount++;
            RefType type = ref.getReferenceType();
            if (type.isRead()) {
                readReferenceCount++;
            }
            if (type.isWrite()) {
                writeReferenceCount++;
            }
            if (type.isData()) {
                dataReferenceCount++;
            }
            if (type.isFlow()) {
                flowReferenceCount++;
            }
            if (isAddressLike(type)) {
                addressLikeReferenceCount++;
            }
            Map<String, Object> referenceRow = describeReference(ref);
            Object functionEntry = referenceRow.get("fromFunctionEntry");
            Object functionName = referenceRow.get("fromFunction");
            if (functionEntry instanceof String && !((String) functionEntry).isEmpty()) {
                functions.put((String) functionEntry, functionName == null ? "" : functionName);
            }
            if (capturedReferenceCount < maxRefsPerField) {
                references.add(referenceRow);
                capturedReferenceCount++;
            }
        }
        item.put("referenceCountTo", referenceCount);
        item.put("capturedReferenceCount", capturedReferenceCount);
        item.put("referencesTruncated", referenceCount > capturedReferenceCount);
        putReferenceCounts(
            item,
            readReferenceCount,
            writeReferenceCount,
            dataReferenceCount,
            addressLikeReferenceCount,
            flowReferenceCount,
            functions.size()
        );
        return item;
    }

    private void putReferenceCounts(
            Map<String, Object> item,
            int readReferenceCount,
            int writeReferenceCount,
            int dataReferenceCount,
            int addressLikeReferenceCount,
            int flowReferenceCount,
            int referencingFunctionCount) {
        item.put("readReferenceCount", readReferenceCount);
        item.put("writeReferenceCount", writeReferenceCount);
        item.put("dataReferenceCount", dataReferenceCount);
        item.put("addressLikeReferenceCount", addressLikeReferenceCount);
        item.put("flowReferenceCount", flowReferenceCount);
        item.put("referencingFunctionCount", referencingFunctionCount);
    }

    private List<Map<String, Object>> collectSymbols(Address address) {
        List<Map<String, Object>> rows = new ArrayList<Map<String, Object>>();
        Symbol[] symbols = currentProgram.getSymbolTable().getSymbols(address);
        for (Symbol symbol : symbols) {
            Map<String, Object> row = new LinkedHashMap<String, Object>();
            row.put("name", symbol.getName());
            row.put("type", symbol.getSymbolType().toString());
            row.put("source", symbol.getSource().toString());
            row.put("primary", symbol.isPrimary());
            row.put("dynamic", symbol.isDynamic());
            rows.add(row);
        }
        return rows;
    }

    private Map<String, Object> describeReference(Reference ref) {
        Map<String, Object> item = new LinkedHashMap<String, Object>();
        RefType type = ref.getReferenceType();
        Address fromAddress = ref.getFromAddress();
        item.put("fromAddress", fromAddress == null ? "" : fromAddress.toString());
        item.put("toAddress", ref.getToAddress() == null ? "" : ref.getToAddress().toString());
        item.put("operandIndex", ref.getOperandIndex());
        item.put("referenceType", type.toString());
        item.put("referenceKind", referenceKind(type));
        item.put("source", ref.getSource().toString());
        item.put("primary", ref.isPrimary());
        item.put("data", type.isData());
        item.put("read", type.isRead());
        item.put("write", type.isWrite());
        item.put("flow", type.isFlow());
        item.put("call", type.isCall());
        item.put("jump", type.isJump());
        item.put("computed", type.isComputed());
        item.put("indirect", type.isIndirect());
        item.put("memoryReference", ref.isMemoryReference());
        item.put("offsetReference", ref.isOffsetReference());
        item.put("shiftedReference", ref.isShiftedReference());
        item.put("externalReference", ref.isExternalReference());
        item.put("operandReference", ref.isOperandReference());
        item.put("mnemonicReference", ref.isMnemonicReference());

        if (fromAddress != null) {
            Function function = getFunctionContaining(fromAddress);
            if (function != null) {
                item.put("fromFunction", function.getName());
                item.put("fromFunctionEntry", function.getEntryPoint().toString());
                item.put("fromFunctionSignature", function.getSignature().toString());
            } else {
                item.put("fromFunction", "");
                item.put("fromFunctionEntry", "");
                item.put("fromFunctionSignature", "");
            }
            Instruction instr = currentProgram.getListing().getInstructionContaining(fromAddress);
            if (instr != null) {
                item.put("instructionAddress", instr.getAddress().toString());
                item.put("instructionMnemonic", instr.getMnemonicString());
                item.put("instructionText", instr.toString());
                try {
                    item.put("instructionBytes", bytesToHex(instr.getBytes()));
                } catch (Exception ex) {
                    item.put("instructionBytes", "");
                    item.put("instructionByteError", ex.getClass().getSimpleName() + ": " + ex.getMessage());
                }
            }
        }
        return item;
    }

    private boolean isAddressLike(RefType type) {
        return type.isData() && !type.isRead() && !type.isWrite();
    }

    private String referenceKind(RefType type) {
        if (type.isRead() && type.isWrite()) {
            return "read-write";
        }
        if (type.isRead()) {
            return "read";
        }
        if (type.isWrite()) {
            return "write";
        }
        if (isAddressLike(type)) {
            return "address-like-data";
        }
        if (type.isCall()) {
            return "call";
        }
        if (type.isFlow()) {
            return "flow";
        }
        return "other";
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
        for (int i = 3; i < args.length; i++) {
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

    private int intValue(Object value) {
        if (value instanceof Number) {
            return ((Number) value).intValue();
        }
        return 0;
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

    private static class FieldSpec {
        String fieldName;
        String address;

        FieldSpec(String fieldName, String address) {
            this.fieldName = fieldName;
            this.address = address;
        }
    }
}
