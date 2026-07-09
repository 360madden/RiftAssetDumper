import argparse
import json
import os
import re
import sys
from collections import defaultdict

FRAMEWORK_APIS = {
    "loadstring",
    "CreateFrame",
    "xpcall",
    "hooksecurefunc",
    "strsplit",
    "strconcat",
    "tonumber",
    "tostring",
    "type",
    "select",
    "pairs",
    "ipairs",
    "pcall",
    "error",
    "assert",
    "setmetatable",
    "getmetatable",
    "rawget",
    "rawset",
    "table",
    "string",
    "math",
    "GetSpellInfo",
    "UnitAura",
    "UnitName",
    "UnitClass",
    "UnitPower",
    "UnitPowerMax",
    "UnitIsDead",
    "UnitIsConnected",
    "UnitHealth",
    "UnitHealthMax",
    "GetItemInfo",
    "GetItemInfoInstant",
    "GetItemCount",
    "GetCoinTextureString",
    "GetInventorySlotInfo",
    "GetInventoryItemID",
    "C_ClassTalents",
    "C_Timer",
    "C_Spell",
    "C_Item",
    "C_Auras",
    "UnitBuff",
    "UnitDebuff",
    "UnitIsUnit",
    "UnitIsFriend",
    "UnitIsEnemy",
    "UnitExists",
    "InCombatLockdown",
    "IsInGroup",
    "IsInRaid",
    "GetInstanceInfo",
    "GetRaidTargetIndex",
    "SetRaidTarget",
    "DoReadyCheck",
    "SendChatMessage",
    "PlaySound",
    "PlaySoundFile",
    "SetPortraitToTexture",
    "GameTooltip",
    "CreateFont",
    "UIParent",
    "WorldFrame",
    "C_GossipInfo",
    "C_QuestLog",
    "C_Map",
    "C_Bags",
}

ADDON_INTERFACE = {
    "setFrameFunctions",
    "createFrame_core",
    "initFrames",
    "getFrameData",
    "getFrameName",
    "setFrameScale",
    "setFrameStrata",
    "setFrameLevel",
    "updateFrame",
    "registerFrame",
    "unregisterFrame",
    "getFrameConfig",
    "setFrameConfig",
    "refreshFrame",
    "hideFrame",
    "showFrame",
    "lockFrame",
    "unlockFrame",
    "resetFrame",
    "moveFrame",
    "resizeFrame",
    "applyFrameTemplate",
    "getFrameTemplate",
    "saveFrameLayout",
    "loadFrameLayout",
    "exportFrameConfig",
    "importFrameConfig",
    "debugFrame",
    "getFrameBounds",
    "setFrameAnchor",
    "getFrameAnchor",
    "resetFrameAnchor",
}

FUNC_DECL_RE = re.compile(r"^\s*(?:local\s+)?function\s+(\w[\w.:]*)\s*\(")
FUNC_RE = re.compile(r"^\s*function\s+(\w[\w.:]*)\s*\(")
COMMENT_RE = re.compile(r"^\s*--\s*(.+)")
LOCAL_VAR_RE = re.compile(r"^\s*local\s+(\w+)\s*=")
TABLE_KEY_RE = re.compile(r"(\w+)\s*=")
IDENTIFIER_RE = re.compile(r"\b([A-Za-z_]\w*)\b")


def parse_snippets(entry):
    snippets = entry.get("TextSnippetSamples", [])
    if not snippets:
        return []
    if isinstance(snippets, str):
        return snippets.split("\n")
    return list(snippets)


def classify_string(text, tokens):
    stripped = text.strip()
    if not stripped:
        return "unknown", None

    m = FUNC_DECL_RE.match(stripped)
    if m:
        return "function-declaration", m.group(1)

    m = LOCAL_VAR_RE.match(stripped)
    if m:
        return "function-declaration", m.group(1)

    if COMMENT_RE.match(stripped):
        return "comment", stripped

    for tok in tokens:
        if tok in FRAMEWORK_APIS:
            return "framework-api", tok
    for tok in tokens:
        if tok in ADDON_INTERFACE:
            return "addon-interface", tok

    return "unknown", None


def extract_identifiers(line):
    return IDENTIFIER_RE.findall(line)


def process_entry(idx, entry):
    lines = parse_snippets(entry)
    functions = []
    comments = []
    all_funcs = set()
    all_comments = set()

    archive = entry.get("Archive", "")
    snippet_text = " ".join(lines)
    tokens = extract_identifiers(snippet_text)

    for line in lines:
        category, name = classify_string(line, tokens)

        if category == "function-declaration" and name:
            if name not in all_funcs:
                all_funcs.add(name)
                functions.append(
                    {
                        "name": name,
                        "entry_index": idx,
                        "archive": archive,
                    }
                )

        elif category == "comment":
            trimmed = line.strip()
            if trimmed not in all_comments:
                all_comments.add(trimmed)
                comments.append(
                    {
                        "text": trimmed,
                        "entry_index": idx,
                        "archive": archive,
                    }
                )

        elif category in ("framework-api", "addon-interface") and name:
            if name not in all_funcs:
                all_funcs.add(name)
                functions.append(
                    {
                        "name": name,
                        "entry_index": idx,
                        "archive": archive,
                        "category": category,
                    }
                )

    return (
        {
            "id": entry.get("ID", ""),
            "archive": archive,
            "entry_index": idx,
            "size": entry.get("Size", 0),
            "magic": entry.get("Magic", ""),
            "functions": functions,
            "comments": comments,
        },
        list(all_funcs),
        list(all_comments),
    )


def main():
    parser = argparse.ArgumentParser(description="Extract Lua string catalogs from semantic index output")
    parser.add_argument(
        "input_file",
        nargs="?",
        default=None,
        help="Path to semantic index JSON (default: Exports/semantic-phase4/smoke-lua.json)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output JSON path (default: Exports/semantic-phase4/lua-string-catalog.json)",
    )
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    input_file = args.input_file
    if input_file is None:
        input_file = os.path.join(project_root, "Exports", "semantic-phase4", "smoke-lua.json")
    elif not os.path.isabs(input_file):
        input_file = os.path.join(os.getcwd(), input_file)

    output_file = args.output
    if output_file is None:
        output_file = os.path.join(project_root, "Exports", "semantic-phase4", "lua-string-catalog.json")
    elif not os.path.isabs(output_file):
        output_file = os.path.join(os.getcwd(), output_file)

    if not os.path.isfile(input_file):
        print(f"Error: input file not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    with open(input_file, encoding="utf-8-sig") as f:
        data = json.load(f)

    entries_raw = data.get("Entries", data.get("entries", []))

    lua_entries = [e for e in entries_raw if e.get("DetectedType") == "lua"]

    total_lua = len(lua_entries)
    total_snippets = 0

    families = defaultdict(list)
    all_func_decls = []
    all_comments = []
    processed = []

    for idx, entry in enumerate(lua_entries):
        processed_entry, func_names, comment_texts = process_entry(idx, entry)
        processed.append(processed_entry)

        snippets = parse_snippets(entry)
        total_snippets += len(snippets)

        for fname in func_names:
            families["function-declaration"].append(fname)
        for ctext in comment_texts:
            families["comment"].append(ctext)

        for fn in processed_entry["functions"]:
            cat = fn.pop("category", "function-declaration")
            if cat == "function-declaration":
                families["function-declaration"].append(fn["name"])
                all_func_decls.append(fn)
            elif cat == "framework-api":
                families["framework-api"].append(fn["name"])
                all_func_decls.append(fn)
            elif cat == "addon-interface":
                families["addon-interface"].append(fn["name"])
                all_func_decls.append(fn)

        for ct in processed_entry["comments"]:
            families["unknown"].append(ct["text"])
            all_comments.append(ct)

    families["function-declaration"] = sorted(set(families["function-declaration"]))
    families["comment"] = sorted(set(families["comment"]))
    families["framework-api"] = sorted(set(families["framework-api"]))
    families["addon-interface"] = sorted(set(families["addon-interface"]))
    families["unknown"] = sorted(set(families["unknown"]))

    result = {
        "schema": "lua-string-catalog-v1",
        "source_file": os.path.basename(input_file),
        "total_lua_entries": total_lua,
        "total_snippets": total_snippets,
        "string_families": dict(families),
        "function_declarations": all_func_decls,
        "comments": all_comments,
        "entries": processed,
    }

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Lua string catalog written to: {output_file}")
    print(f"  Lua entries processed:  {total_lua}")
    print(f"  Total snippet lines:    {total_snippets}")
    print(f"  Function declarations:  {len(families['function-declaration'])}")
    print(f"  Comments:               {len(families['comment'])}")
    print(f"  Framework API strings:  {len(families['framework-api'])}")
    print(f"  Addon interface strings:{len(families['addon-interface'])}")
    print(f"  Unknown strings:        {len(families['unknown'])}")


if __name__ == "__main__":
    main()
