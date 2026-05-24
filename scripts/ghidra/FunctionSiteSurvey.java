// Reusable Ghidra script. Writes static evidence for a target function site.

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStreamWriter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class FunctionSiteSurvey extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2) {
            printerr("Usage: FunctionSiteSurvey.java <target-address> <output-json>");
            return;
        }

        Address target = currentProgram.getAddressFactory().getAddress(args[0]);
        File outFile = new File(args[1]);
        File parent = outFile.getParentFile();
        if (parent != null) {
            parent.mkdirs();
        }

        Map<String, Object> report = new LinkedHashMap<String, Object>();
        report.put("targetAddress", target.toString());
        report.put("programName", currentProgram.getName());
        report.put("imageBase", currentProgram.getImageBase().toString());

        Function function = getFunctionContaining(target);
        if (function == null) {
            report.put("function", null);
        } else {
            report.put("function", describeFunction(function));
            report.put("instructionsNearTarget", collectInstructionsAround(target, 48, 80));
            report.put("functionInstructions", collectFunctionInstructions(function, 500));
            report.put("callers", collectCallers(function, 100));
            report.put("callsFromFunction", collectCallsFromFunction(function, 200));
            report.put("dataRefsFromFunction", collectDataRefsFromFunction(function, 200));
            report.put("decompile", decompile(function));
        }

        BufferedWriter writer = new BufferedWriter(new OutputStreamWriter(new FileOutputStream(outFile), "UTF-8"));
        try {
            writer.write(toJson(report));
            writer.newLine();
        } finally {
            writer.close();
        }
        println("FunctionSiteSurvey wrote: " + outFile.getAbsolutePath());
    }

    private Map<String, Object> describeFunction(Function function) {
        Map<String, Object> item = new LinkedHashMap<String, Object>();
        item.put("name", function.getName());
        item.put("entry", function.getEntryPoint().toString());
        item.put("signature", function.getSignature().toString());
        item.put("bodyMin", function.getBody().getMinAddress().toString());
        item.put("bodyMax", function.getBody().getMaxAddress().toString());
        item.put("bodyNumAddresses", function.getBody().getNumAddresses());
        item.put("parameterCount", function.getParameterCount());
        item.put("returnType", function.getReturnType().getName());
        return item;
    }

    private List<Map<String, Object>> collectInstructionsAround(Address target, int before, int after) {
        Listing listing = currentProgram.getListing();
        Instruction cursor = listing.getInstructionContaining(target);
        for (int i = 0; i < before && cursor != null; i++) {
            Instruction prev = cursor.getPrevious();
            if (prev == null) {
                break;
            }
            cursor = prev;
        }
        List<Map<String, Object>> rows = new ArrayList<Map<String, Object>>();
        int max = before + after + 1;
        for (int i = 0; i < max && cursor != null; i++) {
            rows.add(describeInstruction(cursor, cursor.getAddress().equals(target)));
            cursor = cursor.getNext();
        }
        return rows;
    }

    private List<Map<String, Object>> collectFunctionInstructions(Function function, int limit) {
        List<Map<String, Object>> rows = new ArrayList<Map<String, Object>>();
        Instruction instr = currentProgram.getListing().getInstructionAt(function.getBody().getMinAddress());
        int count = 0;
        while (instr != null && function.getBody().contains(instr.getAddress()) && count < limit) {
            rows.add(describeInstruction(instr, false));
            instr = instr.getNext();
            count++;
        }
        return rows;
    }

    private Map<String, Object> describeInstruction(Instruction instr, boolean target) {
        Map<String, Object> item = new LinkedHashMap<String, Object>();
        item.put("address", instr.getAddress().toString());
        item.put("target", target);
        item.put("mnemonic", instr.getMnemonicString());
        item.put("opStr", instr.toString());
        try {
            item.put("bytes", bytesToHex(instr.getBytes()));
        } catch (Exception ex) {
            item.put("bytes", "<unavailable:" + ex.getClass().getSimpleName() + ">");
        }
        List<Map<String, Object>> refs = new ArrayList<Map<String, Object>>();
        for (Reference ref : instr.getReferencesFrom()) {
            Map<String, Object> r = new LinkedHashMap<String, Object>();
            r.put("to", ref.getToAddress() == null ? null : ref.getToAddress().toString());
            r.put("type", ref.getReferenceType().toString());
            Function toFn = ref.getToAddress() == null ? null : getFunctionContaining(ref.getToAddress());
            if (toFn != null) {
                r.put("toFunction", toFn.getName());
                r.put("toFunctionEntry", toFn.getEntryPoint().toString());
            }
            refs.add(r);
        }
        item.put("refsFrom", refs);
        return item;
    }

    private List<Map<String, Object>> collectCallers(Function function, int limit) {
        List<Map<String, Object>> rows = new ArrayList<Map<String, Object>>();
        ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(function.getEntryPoint());
        int count = 0;
        while (refs.hasNext() && count < limit) {
            Reference ref = refs.next();
            Map<String, Object> item = new LinkedHashMap<String, Object>();
            item.put("from", ref.getFromAddress().toString());
            item.put("type", ref.getReferenceType().toString());
            Function caller = getFunctionContaining(ref.getFromAddress());
            if (caller != null) {
                item.put("caller", caller.getName());
                item.put("callerEntry", caller.getEntryPoint().toString());
                item.put("callerSignature", caller.getSignature().toString());
            }
            rows.add(item);
            count++;
        }
        return rows;
    }

    private List<Map<String, Object>> collectCallsFromFunction(Function function, int limit) {
        List<Map<String, Object>> rows = new ArrayList<Map<String, Object>>();
        Instruction instr = currentProgram.getListing().getInstructionAt(function.getBody().getMinAddress());
        int count = 0;
        while (instr != null && function.getBody().contains(instr.getAddress()) && count < limit) {
            for (Reference ref : instr.getReferencesFrom()) {
                if (!ref.getReferenceType().isCall()) {
                    continue;
                }
                Map<String, Object> item = new LinkedHashMap<String, Object>();
                item.put("from", instr.getAddress().toString());
                item.put("to", ref.getToAddress() == null ? null : ref.getToAddress().toString());
                item.put("type", ref.getReferenceType().toString());
                Function callee = ref.getToAddress() == null ? null : getFunctionContaining(ref.getToAddress());
                if (callee != null) {
                    item.put("callee", callee.getName());
                    item.put("calleeEntry", callee.getEntryPoint().toString());
                    item.put("calleeSignature", callee.getSignature().toString());
                }
                rows.add(item);
                count++;
                if (count >= limit) {
                    break;
                }
            }
            instr = instr.getNext();
        }
        return rows;
    }

    private List<Map<String, Object>> collectDataRefsFromFunction(Function function, int limit) {
        List<Map<String, Object>> rows = new ArrayList<Map<String, Object>>();
        Instruction instr = currentProgram.getListing().getInstructionAt(function.getBody().getMinAddress());
        int count = 0;
        while (instr != null && function.getBody().contains(instr.getAddress()) && count < limit) {
            for (Reference ref : instr.getReferencesFrom()) {
                if (ref.getReferenceType().isCall()) {
                    continue;
                }
                Map<String, Object> item = new LinkedHashMap<String, Object>();
                item.put("from", instr.getAddress().toString());
                item.put("to", ref.getToAddress() == null ? null : ref.getToAddress().toString());
                item.put("type", ref.getReferenceType().toString());
                rows.add(item);
                count++;
                if (count >= limit) {
                    break;
                }
            }
            instr = instr.getNext();
        }
        return rows;
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
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < bytes.length; i++) {
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
