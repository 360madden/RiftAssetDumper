// VtableResolver — Read 64-bit pointers at target addresses, resolve to function names
//@category RiftBinaryDiscovery
import ghidra.app.script.GhidraScript;
import ghidra.program.model.memory.Memory;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolTable;
import ghidra.util.Msg;
import java.io.FileWriter;
import java.io.File;

public class VtableResolver extends GhidraScript {

    private static final int MAX_SLOTS = 32;

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2) {
            println("Usage: VtableResolver.java <out.json> <addr1> [addr2...]");
            return;
        }

        String outPath = args[0];
        StringBuilder json = new StringBuilder();
        json.append("{\n");
        json.append("  \"programName\": \"" + currentProgram.getName() + "\",\n");
        json.append("  \"results\": [\n");

        FunctionManager funcMan = currentProgram.getFunctionManager();
        SymbolTable symTable = currentProgram.getSymbolTable();
        Memory memory = currentProgram.getMemory();

        boolean firstResult = true;
        for (int a = 1; a < args.length; a++) {
            if (monitor.isCancelled()) break;

            String addrStr = args[a];
            Address addr = parseAddress(addrStr);

            if (!firstResult) json.append(",\n");
            firstResult = false;

            json.append("    {\n");
            json.append("      \"targetAddress\": \"" + addrStr + "\",\n");
            json.append("      \"slots\": [\n");

            boolean firstSlot = true;
            for (int slot = 0; slot < MAX_SLOTS; slot++) {
                if (monitor.isCancelled()) break;

                long offset = (long)slot * 8;
                Address ptrAddr = addr.add(offset);

                try {
                    byte[] ptrBytes = new byte[8];
                    if (memory.getBytes(ptrAddr, ptrBytes) != 8) break;

                    // Read as little-endian 64-bit
                    long ptrValue = 0;
                    for (int i = 0; i < 8; i++) {
                        ptrValue |= (ptrBytes[i] & 0xFFL) << (i * 8);
                    }

                    if (ptrValue == 0) continue; // Skip null slots

                    // Try to resolve to a function
                    Address targetAddr = addr.getNewAddress(ptrValue);
                    Function func = funcMan.getFunctionAt(targetAddr);
                    Symbol sym = symTable.getPrimarySymbol(targetAddr);

                    String funcName = null;
                    if (func != null) {
                        funcName = func.getName();
                    } else if (sym != null) {
                        funcName = sym.getName();
                    } else {
                        funcName = "0x" + Long.toHexString(ptrValue);
                    }

                    if (!firstSlot) json.append(",\n");
                    firstSlot = false;

                    json.append("        {\n");
                    json.append("          \"slot\": " + slot + ",\n");
                    json.append("          \"offset\": \"+0x" + Integer.toHexString(slot * 8) + "\",\n");
                    json.append("          \"pointer\": \"0x" + Long.toHexString(ptrValue) + "\",\n");
                    json.append("          \"resolvedName\": \"" + escapeJson(funcName) + "\"\n");
                    json.append("        }");

                } catch (Exception e) {
                    break; // Ran off the end of memory
                }
            }

            json.append("\n      ]\n");
            json.append("    }");
        }

        json.append("\n  ]\n");
        json.append("}\n");

        FileWriter fw = new FileWriter(new File(outPath));
        fw.write(json.toString());
        fw.close();

        println("Wrote vtable resolution to: " + outPath);
    }

    private Address parseAddress(String s) throws Exception {
        if (s.startsWith("0x") || s.startsWith("0X")) {
            s = s.substring(2);
        }
        long val = Long.parseUnsignedLong(s, 16);
        return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(val);
    }

    private static String escapeJson(String s) {
        if (s == null) return "null";
        return s.replace("\\", "\\\\").replace("\"", "\\\"");
    }
}
