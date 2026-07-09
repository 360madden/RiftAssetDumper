"""
Ghidra script to find the function implementing Inspect.Unit.Detail.
Uses string cross-reference analysis to trace the Lua method registration.
"""

from ghidra.program.model.symbol import RefType
from ghidra.program.model.address import AddressSet

def find_xrefs_to_string(program, search_str):
    """Find all cross-references to a string in the binary."""
    results = []
    listing = program.getListing()
    memory = program.getMemory()
    
    # Find the string first
    addr = memory.getMinAddress()
    while addr is not None:
        found_addr = memory.findBytes(addr, search_str, None, True, None)
        if found_addr is None:
            break
        
        print("Found string '%s' at %s" % (search_str, found_addr))
        
        # Find all references to this address
        ref_mgr = program.getReferenceManager()
        refs_to = ref_mgr.getReferencesTo(found_addr)
        
        for ref in refs_to:
            from_addr = ref.getFromAddress()
            ref_type = ref.getReferenceType()
            results.append((from_addr, ref_type))
            print("  Reference from %s (type: %s)" % (from_addr, ref_type))
        
        addr = found_addr.add(1)
    
    return results

def get_function_containing(program, addr):
    """Get the function containing the given address."""
    fm = program.getFunctionManager()
    func = fm.getFunctionContaining(addr)
    return func

def analyze_function_calls(program, func_addr, depth=0):
    """Recursively analyze function calls from a given function."""
    if depth > 3:
        return
    
    fm = program.getFunctionManager()
    func = fm.getFunctionAt(func_addr)
    if func is None:
        func = fm.getFunctionContaining(func_addr)
    if func is None:
        return
    
    indent = "  " * depth
    print("%sFunction: %s at %s" % (indent, func.getName(), func.getEntryPoint()))
    
    # Get all calls from this function
    ref_mgr = program.getReferenceManager()
    body = func.getBody()
    refs = ref_mgr.getReferencesInSet(body, RefType.UNCONDITIONAL_CALL)
    
    for ref in refs:
        to_addr = ref.getToAddress()
        if to_addr.isExternalAddress():
            print("%s  CALL external: %s" % (indent, to_addr))
        else:
            target_func = fm.getFunctionAt(to_addr)
            if target_func:
                print("%s  CALL: %s" % (indent, target_func.getName()))
            else:
                print("%s  CALL: %s" % (indent, to_addr))
            
            if depth < 2:
                analyze_function_calls(program, to_addr, depth + 1)

def main():
    program = getCurrentProgram()
    print("=" * 60)
    print("Analyzing: %s" % program.getName())
    print("=" * 60)
    
    # Step 1: Find the string "Inspect.Unit.Detail"
    print("\n[Step 1] Finding 'Inspect.Unit.Detail' string...")
    refs = find_xrefs_to_string(program, "Inspect.Unit.Detail")
    
    # Step 2: Find the string "detail@unit"
    print("\n[Step 2] Finding 'detail@unit' string...")
    refs2 = find_xrefs_to_string(program, "detail@unit")
    
    # Step 3: Find all Inspect.* method names
    print("\n[Step 3] Finding all Inspect.* method names...")
    inspect_methods = []
    listing = program.getListing()
    memory = program.getMemory()
    
    addr = memory.getMinAddress()
    while addr is not None:
        found_addr = memory.findBytes(addr, "Inspect.", None, True, None)
        if found_addr is None:
            break
        
        # Read the string
        sb = []
        for i in range(64):
            b = memory.getByte(found_addr.add(i))
            if b == 0:
                break
            sb.append(chr(b & 0xFF))
        
        method_name = "".join(sb)
        if method_name.startswith("Inspect.") and "." in method_name[8:]:
            inspect_methods.append((found_addr, method_name))
        
        addr = found_addr.add(1)
    
    print("Found %d Inspect.* methods:" % len(inspect_methods))
    for addr, name in inspect_methods:
        print("  %s at %s" % (name, addr))
    
    # Step 4: Analyze the function that registers these methods
    print("\n[Step 4] Analyzing method registration function...")
    if refs:
        for ref_addr, ref_type in refs[:1]:  # Focus on first reference
            func = get_function_containing(program, ref_addr)
            if func:
                print("Function containing reference: %s at %s" % (func.getName(), func.getEntryPoint()))
                analyze_function_calls(program, func.getEntryPoint(), 0)

if __name__ == "__main__":
    main()
