#!/usr/bin/env python3
"""Extract XML tag and attribute family catalogs from semantic index output."""

import argparse
import json
import os
import sys
from collections import defaultdict

TYPED_STRUCTURE_TAGS = {"OBJECT", "UINT32", "FLOAT", "STRING", "INT32", "ARRAY", "BYTE", "BOOL"}
UI_FRAME_TAGS = {"character", "FontDetails"}

STRUCTURE_META_ATTRS = {"name", "primitiveCount", "className", "array_count", "array_primitiveCount", "array_type"}
FONT_GLYPH_ATTRS = {"code", "postshift", "page", "preshift", "u", "u2", "v", "v2", "yadjust"}


def classify_tag(tag_name: str) -> str:
    if tag_name in TYPED_STRUCTURE_TAGS:
        return "typed-structure"
    if tag_name in UI_FRAME_TAGS:
        return "ui-frame"
    return "unknown"


def classify_attribute(attr_name: str) -> str:
    if attr_name in STRUCTURE_META_ATTRS:
        return "structure-meta"
    if attr_name in FONT_GLYPH_ATTRS:
        return "font-glyph"
    return "unknown"


def build_catalog(input_path: str) -> dict:
    with open(input_path, encoding="utf-8-sig") as f:
        data = json.load(f)

    entries_raw = data.get("Entries", [])
    total_xml = 0
    tag_counter: dict[str, int] = defaultdict(int)
    attr_counter: dict[str, int] = defaultdict(int)
    catalog_entries = []

    for entry in entries_raw:
        if entry.get("DetectedType") != "xml":
            continue
        total_xml += 1

        asset_id = entry.get("AssetIdPrefix", "")
        archive = entry.get("ArchiveName", "")
        parse_status = entry.get("XmlParseStatus") or ""

        tags_in_entry = []
        for tc in entry.get("XmlTagCounts", []):
            name = tc.get("Value", "")
            count = tc.get("Count", 0)
            if name:
                tag_counter[name] += count
                tags_in_entry.append(name)

        attrs_in_entry = []
        for ac in entry.get("XmlAttributeCounts", []):
            name = ac.get("Value", "")
            count = ac.get("Count", 0)
            if name:
                attr_counter[name] += count
                attrs_in_entry.append(name)

        catalog_entries.append(
            {
                "id": asset_id,
                "archive": archive,
                "tags": tags_in_entry,
                "attributes": attrs_in_entry,
                "parse_status": parse_status,
            }
        )

    tag_families: dict[str, list[str]] = defaultdict(list)
    for tag_name in sorted(tag_counter.keys()):
        family = classify_tag(tag_name)
        tag_families[family].append(tag_name)

    attr_families: dict[str, list[str]] = defaultdict(list)
    for attr_name in sorted(attr_counter.keys()):
        family = classify_attribute(attr_name)
        attr_families[family].append(attr_name)

    tag_counts = [
        {"tag": t, "count": tag_counter[t], "family": classify_tag(t)}
        for t in sorted(tag_counter.keys(), key=lambda x: -tag_counter[x])
    ]
    attr_counts = [
        {"attribute": a, "count": attr_counter[a], "family": classify_attribute(a)}
        for a in sorted(attr_counter.keys(), key=lambda x: -attr_counter[x])
    ]

    return {
        "schema": "xml-tag-catalog-v1",
        "source_file": os.path.basename(input_path),
        "total_xml_entries": total_xml,
        "total_tags": len(tag_counter),
        "total_attributes": len(attr_counter),
        "tag_families": dict(tag_families),
        "attribute_families": dict(attr_families),
        "tag_counts": tag_counts,
        "attribute_counts": attr_counts,
        "entries": catalog_entries,
    }


def print_summary(catalog: dict) -> None:
    print(f"Source file : {catalog['source_file']}")
    print(f"XML entries : {catalog['total_xml_entries']}")
    print(f"Unique tags : {catalog['total_tags']}")
    print(f"Unique attrs: {catalog['total_attributes']}")
    print()
    for family, tags in catalog["tag_families"].items():
        print(f"  tag family [{family}]: {len(tags)} tags")
    for family, attrs in catalog["attribute_families"].items():
        print(f"  attr family [{family}]: {len(attrs)} attributes")
    print()
    print("Top 15 tags by count:")
    for tc in catalog["tag_counts"][:15]:
        print(f"  {tc['tag']:20s} {tc['count']:>8d}  ({tc['family']})")
    print()
    print("Top 15 attributes by count:")
    for ac in catalog["attribute_counts"][:15]:
        print(f"  {ac['attribute']:20s} {ac['count']:>8d}  ({ac['family']})")


def main():
    parser = argparse.ArgumentParser(description="Extract XML tag and attribute family catalogs from a semantic index.")
    parser.add_argument(
        "input",
        nargs="?",
        default=r"Exports\semantic-phase4\smoke-xml.json",
        help="Path to semantic index JSON (default: Exports/semantic-phase4/smoke-xml.json)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=r"Exports\semantic-phase4\xml-tag-catalog.json",
        help="Output JSON path (default: Exports/semantic-phase4/xml-tag-catalog.json)",
    )
    args = parser.parse_args()

    input_path = os.path.abspath(args.input)
    output_path = os.path.abspath(args.output)

    if not os.path.isfile(input_path):
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    catalog = build_catalog(input_path)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    print_summary(catalog)
    print()
    print(f"Wrote catalog to {output_path}")


if __name__ == "__main__":
    main()
