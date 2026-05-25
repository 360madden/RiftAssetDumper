"""Guard v1 NiDataStream promotion schemas remain fail-closed."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

failed = 0


def check(desc: str, actual: Any, expected: Any) -> None:
    global failed
    if actual == expected:
        print(f"  PASS: {desc}")
    else:
        print(f"  FAIL: {desc} expected={expected!r} actual={actual!r}")
        failed += 1


def schema(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


print("=== NiDataStream promotion schema locks ===")
promotion_schema = schema("docs/schemas/nidatastream-promotion-status-v1.schema.json")
descriptor_schema = schema("docs/schemas/nidatastream-descriptor-proof-status-v1.schema.json")

check(
    "promotion parser/export lock",
    promotion_schema["properties"]["ParserExportPromotionAllowed"],
    {"const": False},
)
check(
    "promotion descriptor summary lock",
    promotion_schema["$defs"]["descriptorReportStatus"]["properties"]["FieldOrderPromoted"],
    {"const": False},
)
check(
    "descriptor proof field-order lock",
    descriptor_schema["properties"]["FieldOrderPromoted"],
    {"const": False},
)
check("promotion candidate-only lock", promotion_schema["properties"]["CandidateOnly"], {"const": True})
check("descriptor candidate-only lock", descriptor_schema["properties"]["CandidateOnly"], {"const": True})

print(f"\n{'=' * 50}")
if failed:
    print(f"FAILURES: {failed}")
    sys.exit(1)
else:
    print("All tests passed!")
