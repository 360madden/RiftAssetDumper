/* Reusable Ghidra script — disassemble ±40 instructions around target addresses.
 * Usage: DisasmContext.java <out.json> <addr1> [addr2 ... addrN]
 *
 * For each address, reports the instruction at that address plus surrounding
 * context instructions. Designed for fast execution (no decompilation).
 */
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.address.Address;
import java.io.File;
import java.io.FileWriter;
import java.util.LinkedHashMap;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public class DisasmContext extends GhidraScript {

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2) {
            printerr("Usage: DisasmContext.java <out.json> <addr1> [addr2 ... addrN]");
            return;
        }

        String outPath = args[0];
        List<Map<String, Object>> results = new ArrayList<>();

        for (int i = 1; i < args.length; i++) {
            if (monitor.isCancelled()) break;

            Address target = currentProgram.getAddressFactory().getAddress(args[i]);
            if (target == null) {
                println("WARNING: Cannot parse address: " + args[i]);
                continue;
            }

            Map<String, Object> entry = new LinkedHashMap<>();
            entry.put("target", target.toString());

            List<Map<String, String>> instrs = new ArrayList<>();

            // Walk backwards to find start of context window
            Instruction instr = getInstructionAt(target);
            if (instr == null) {
                instr = getInstructionAfter(target);
            }
            if (instr == null) {
                instr = getInstructionBefore(target);
            }

            if (instr != null) {
                // Walk backwards ~20 instructions
                Instruction cursor = instr;
                for (int back = 0; back < 20 && cursor != null; back++) {
                    cursor = cursor.getPrevious();
                }
                // Start from the found position (or beginning)
                Instruction start = (cursor != null) ? cursor : instr;
                if (start == null && instr != null) start = instr;
                if (start == null) start = getFirstInstruction();

                // Walk forward ~40 instructions
                int count = 0;
                cursor = start;
                while (cursor != null && count < 40 && !monitor.isCancelled()) {
                    Map<String, String> row = new LinkedHashMap<>();
                    row.put("addr", cursor.getAddress().toString());
                    row.put("mnem", cursor.getMnemonicString());
                    row.put("text", cursor.toString());
                    instrs.add(row);
                    count++;
                    cursor = cursor.getNext();
                }
            }

            entry.put("instructions", instrs);
            entry.put("instructionCount", instrs.size());
            results.add(entry);
        }

        // Write JSON manually to avoid dependency issues
        FileWriter fw = new FileWriter(new File(outPath));
        fw.write("{\n");
        fw.write("  \"programName\": \"" + currentProgram.getName() + "\",\n");
        fw.write("  \"results\": [\n");
        for (int i = 0; i < results.size(); i++) {
            if (i > 0) fw.write(",\n");
            Map<String, Object> entry = results.get(i);
            fw.write("    {\n");
            fw.write("      \"target\": \"" + entry.get("target") + "\",\n");

            @SuppressWarnings("unchecked")
            List<Map<String, String>> instrs = (List<Map<String, String>>) entry.get("instructions");
            fw.write("      \"instructionCount\": " + instrs.size() + ",\n");
            fw.write("      \"instructions\": [\n");
            for (int j = 0; j < instrs.size(); j++) {
                if (j > 0) fw.write(",\n");
                Map<String, String> row = instrs.get(j);
                fw.write("        {\"addr\": \"" + row.get("addr") + "\", ");
                fw.write("\"mnem\": \"" + row.get("mnem") + "\", ");
                fw.write("\"text\": \"" + escapeJson(row.get("text")) + "\"}");
            }
            fw.write("\n      ]\n");
            fw.write("    }");
        }
        fw.write("\n  ]\n");
        fw.write("}\n");
        fw.close();
        println("Wrote " + outPath + " (" + results.size() + " entries)");
    }

    private String escapeJson(String s) {
        if (s == null) return "";
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"': sb.append("\\\""); break;
                case '\\': sb.append("\\\\"); break;
                case '\n': sb.append("\\n"); break;
                case '\r': sb.append("\\r"); break;
                case '\t': sb.append("\\t"); break;
                default: sb.append(c);
            }
        }
        return sb.toString();
    }
}
