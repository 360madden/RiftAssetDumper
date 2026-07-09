#!/usr/bin/env python3
"""Merge XML tag catalogs and Lua string catalogs into a unified UI vocabulary artifact."""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import UTC, datetime

TYPED_STRUCTURE_TAGS = {"OBJECT", "UINT32", "FLOAT", "STRING", "INT32", "ARRAY", "BYTE", "BOOL"}
UI_FRAME_TAGS = {"character", "FontDetails"}

STRUCTURE_META_ATTRS = {"name", "primitiveCount", "className", "array_count", "array_primitiveCount", "array_type"}
FONT_GLYPH_ATTRS = {"code", "postshift", "page", "preshift", "u", "u2", "v", "v2", "yadjust"}

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


def classify_tag(tag_name):
    if tag_name in TYPED_STRUCTURE_TAGS:
        return "typed-structure"
    if tag_name in UI_FRAME_TAGS:
        return "ui-frame"
    return "font-glyph"


def classify_attribute(attr_name):
    if attr_name in STRUCTURE_META_ATTRS:
        return "structure-meta"
    if attr_name in FONT_GLYPH_ATTRS:
        return "font-glyph"
    return "unknown"


def classify_lua_function(name):
    if name in FRAMEWORK_APIS:
        return "framework-api"
    if name in ADDON_INTERFACE:
        return "addon-interface"
    return "function-declaration"


def load_json(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def build_xml_vocabulary(xml_catalog):
    tag_counts = defaultdict(int)
    attr_counts = defaultdict(int)
    xml_entries = xml_catalog.get("entries", [])

    for entry in xml_entries:
        for tag in entry.get("tags", []):
            tag_counts[tag] += 1
        for attr in entry.get("attributes", []):
            attr_counts[attr] += 1

    tag_families = defaultdict(list)
    for tag_name, total in tag_counts.items():
        family = classify_tag(tag_name)
        tag_families[family].append({"tag": tag_name, "count": total})
    for family in tag_families:
        tag_families[family].sort(key=lambda x: -x["count"])

    attr_families = defaultdict(list)
    for attr_name, total in attr_counts.items():
        family = classify_attribute(attr_name)
        attr_families[family].append({"attribute": attr_name, "count": total})
    for family in attr_families:
        attr_families[family].sort(key=lambda x: -x["count"])

    return {
        "xml_tags": dict(tag_families),
        "xml_attributes": dict(attr_families),
        "total_unique_tags": len(tag_counts),
        "total_unique_attributes": len(attr_counts),
        "xml_entries": xml_entries,
    }


def build_lua_vocabulary(lua_catalog):
    func_families = defaultdict(list)
    func_entries = defaultdict(list)
    all_comments = []
    lua_entries = lua_catalog.get("entries", [])

    seen_comments = set()

    for entry in lua_entries:
        for fn in entry.get("functions", []):
            name = fn["name"]
            family = classify_lua_function(name)
            func_families[family].append(name)
            func_entries[name].append(
                {
                    "entry_index": entry.get("entry_index", 0),
                    "archive": entry.get("archive", ""),
                }
            )

        for comment in entry.get("comments", []):
            text = comment.get("text", "")
            if text not in seen_comments:
                seen_comments.add(text)
                all_comments.append(
                    {
                        "text": text,
                        "entries": [
                            {
                                "entry_index": entry.get("entry_index", 0),
                                "archive": entry.get("archive", ""),
                            }
                        ],
                    }
                )

    for family in func_families:
        func_families[family] = sorted(set(func_families[family]))

    lua_function_output = {}
    for family, names in func_families.items():
        lua_function_output[family] = [{"name": name, "entries": func_entries.get(name, [])} for name in names]

    all_func_names = set()
    for names in func_families.values():
        all_func_names.update(names)

    return {
        "lua_functions": lua_function_output,
        "lua_comments": all_comments,
        "total_unique_functions": len(all_func_names),
        "total_unique_comments": len(all_comments),
        "lua_entries": lua_entries,
    }


def build_cross_references(xml_entries, lua_entries):
    archive_to_lua_funcs = defaultdict(set)
    for entry in lua_entries:
        archive = entry.get("archive", "")
        if not archive:
            continue
        for fn in entry.get("functions", []):
            archive_to_lua_funcs[archive].add(fn["name"])

    xml_tag_to_lua = defaultdict(lambda: defaultdict(int))
    for entry in xml_entries:
        archive = entry.get("archive", "")
        if not archive or archive not in archive_to_lua_funcs:
            continue
        lua_funcs = archive_to_lua_funcs[archive]
        for tag in entry.get("tags", []):
            for func in lua_funcs:
                xml_tag_to_lua[tag][func] += 1

    cross_refs = []
    for tag, func_counts in sorted(xml_tag_to_lua.items()):
        top_funcs = sorted(func_counts.items(), key=lambda x: -x[1])
        cross_refs.append(
            {
                "xml_tag": tag,
                "lua_functions": [f for f, _ in top_funcs],
                "co_occurrence_count": sum(func_counts.values()),
            }
        )
    cross_refs.sort(key=lambda x: -x["co_occurrence_count"])

    return cross_refs


def main():
    parser = argparse.ArgumentParser(
        description="Merge XML tag catalogs and Lua string catalogs into a unified UI vocabulary."
    )
    parser.add_argument(
        "--xml-catalog",
        default=r"Exports\semantic-phase4\xml-tag-catalog.json",
        help="Path to XML tag catalog JSON (default: Exports/semantic-phase4/xml-tag-catalog.json)",
    )
    parser.add_argument(
        "--lua-catalog",
        default=r"Exports\semantic-phase4\lua-string-catalog.json",
        help="Path to Lua string catalog JSON (default: Exports/semantic-phase4/lua-string-catalog.json)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=r"Exports\semantic-phase4\ui-vocabulary.json",
        help="Output JSON path (default: Exports/semantic-phase4/ui-vocabulary.json)",
    )
    args = parser.parse_args()

    xml_path = os.path.abspath(args.xml_catalog)
    lua_path = os.path.abspath(args.lua_catalog)
    output_path = os.path.abspath(args.output)

    if not os.path.isfile(xml_path):
        print(f"Error: XML catalog not found: {xml_path}", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(lua_path):
        print(f"Error: Lua catalog not found: {lua_path}", file=sys.stderr)
        sys.exit(1)

    xml_catalog = load_json(xml_path)
    lua_catalog = load_json(lua_path)

    xml_vocab = build_xml_vocabulary(xml_catalog)
    lua_vocab = build_lua_vocabulary(lua_catalog)

    cross_refs = build_cross_references(xml_vocab["xml_entries"], lua_vocab["lua_entries"])

    result = {
        "schema": "ui-vocabulary-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_files": {
            "xml_catalog": os.path.basename(xml_path),
            "lua_catalog": os.path.basename(lua_path),
        },
        "summary": {
            "total_xml_entries": xml_catalog.get("total_xml_entries", 0),
            "total_lua_entries": lua_catalog.get("total_lua_entries", 0),
            "total_unique_tags": xml_vocab["total_unique_tags"],
            "total_unique_attributes": xml_vocab["total_unique_attributes"],
            "total_unique_functions": lua_vocab["total_unique_functions"],
            "total_unique_comments": lua_vocab["total_unique_comments"],
        },
        "xml_tags": xml_vocab["xml_tags"],
        "xml_attributes": xml_vocab["xml_attributes"],
        "lua_functions": lua_vocab["lua_functions"],
        "lua_comments": lua_vocab["lua_comments"],
        "cross_references": cross_refs,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"UI vocabulary written to: {output_path}")
    print()
    print("Summary:")
    print(f"  XML entries:        {result['summary']['total_xml_entries']}")
    print(f"  Lua entries:        {result['summary']['total_lua_entries']}")
    print(f"  Unique XML tags:    {result['summary']['total_unique_tags']}")
    print(f"  Unique XML attrs:   {result['summary']['total_unique_attributes']}")
    print(f"  Unique Lua funcs:   {result['summary']['total_unique_functions']}")
    print(f"  Unique Lua comments:{result['summary']['total_unique_comments']}")
    print()
    print("XML tag families:")
    for family, tags in result["xml_tags"].items():
        print(f"  [{family}]: {len(tags)} tags")
    print()
    print("XML attribute families:")
    for family, attrs in result["xml_attributes"].items():
        print(f"  [{family}]: {len(attrs)} attributes")
    print()
    print("Lua function families:")
    for family, funcs in result["lua_functions"].items():
        print(f"  [{family}]: {len(funcs)} functions")
    print()
    print(f"Cross-references: {len(cross_refs)} xml-tag -> lua-function links")
    if cross_refs:
        print("  Top 5 co-occurrences:")
        for cr in cross_refs[:5]:
            funcs_str = ", ".join(cr["lua_functions"][:3])
            if len(cr["lua_functions"]) > 3:
                funcs_str += f" (+{len(cr['lua_functions']) - 3} more)"
            print(f"    {cr['xml_tag']:12s} <-> {funcs_str:40s}  (n={cr['co_occurrence_count']})")


if __name__ == "__main__":
    main()
