import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.address.Address;
import java.io.FileWriter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class TargetedDisasm extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        String outPath = args[0];
        String addrStr = args[1];
        int before = args.length > 2 ? Integer.parseInt(args[2]) : 30;
        int after = args.length > 3 ? Integer.parseInt(args[3]) : 60;

        Address target = currentProgram.getAddressFactory().getAddress(addrStr);
        Instruction instr = getInstructionAt(target);
        if (instr == null) {
            instr = getInstructionAfter(target);
        }
        if (instr == null) {
            println("No instruction at " + addrStr);
            return;
        }

        Instruction cursor = instr;
        for (int i = 0; i < before && cursor != null; i++) {
            Instruction prev = cursor.getPrevious();
            if (prev == null) break;
            cursor = prev;
        }

        List<Map<String, String>> rows = new ArrayList<>();
        int count = 0;
        while (cursor != null && count < before + after + 1) {
            Map<String, String> row = new LinkedHashMap<>();
            row.put("addr", cursor.getAddress().toString());
            row.put("mnem", cursor.getMnemonicString());
            row.put("text", cursor.toString());
            row.put("isTarget", cursor.getAddress().equals(target) ? "true" : "false");
            rows.add(row);
            count++;
            cursor = cursor.getNext();
        }

        StringBuilder sb = new StringBuilder();
        sb.append("{\n");
        sb.append("  \"target\": \"").append(addrStr).append("\",\n");
        sb.append("  \"instructionCount\": ").append(rows.size()).append(",\n");
        sb.append("  \"instructions\": [\n");
        for (int i = 0; i < rows.size(); i++) {
            if (i > 0) sb.append(",\n");
            Map<String, String> r = rows.get(i);
            sb.append("    {\"addr\": \"").append(r.get("addr")).append("\", ");
            sb.append("\"mnem\": \"").append(r.get("mnem")).append("\", ");
            sb.append("\"text\": \"").append(escapeJson(r.get("text"))).append("\"");
            if ("true".equals(r.get("isTarget"))) {
                sb.append(", \"isTarget\": true");
            }
            sb.append("}");
        }
        sb.append("\n  ]\n}\n");

        FileWriter fw = new FileWriter(outPath);
        fw.write(sb.toString());
        fw.close();
        println("Wrote " + outPath);
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
