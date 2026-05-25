"""Smoke tests for Python/PowerShell workflow command wiring."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, ".")

from scripts.rift_workflow import COMMAND_MAP, PS_MODE_TO_COMMAND

failed = 0


def check(desc: str, actual: object, expected: object) -> None:
    global failed
    if actual == expected:
        print(f"  PASS: {desc}")
    else:
        print(f"  FAIL: {desc} expected={expected!r} actual={actual!r}")
        failed += 1


EXPECTED_GHIDRA_ALIASES = {
    "GhidraPairingNonExportGuard": "ghidra-pairing-non-export-guard",
    "GhidraPairingReviewReport": "ghidra-pairing-review-report",
    "GhidraAttributeCandidateReport": "ghidra-attribute-candidate-report",
    "GhidraAttributeCandidateGuard": "ghidra-attribute-candidate-guard",
    "GhidraFunctionSiteTargetGuard": "ghidra-function-site-target-guard",
    "GhidraFunctionSiteStatus": "ghidra-function-site-status",
    "GhidraFunctionSiteSurvey": "ghidra-function-site-survey",
    "GhidraReviewRankProbes": "ghidra-review-rank-probes",
    "GhidraReviewRankProbesSummary": "ghidra-review-rank-probes-summary",
    "GhidraWorkflowGuardSuite": "ghidra-workflow-guard-suite",
    "NiDataStreamEvidenceStatus": "nidatastream-evidence-status",
    "NiDataStreamPromotionStatus": "nidatastream-promotion-status",
    "NiDataStreamPromotionDashboard": "nidatastream-promotion-dashboard",
    "NiDataStreamPromotionPreflight": "nidatastream-promotion-preflight",
    "NiDataStreamParserFieldProofGuard": "nidatastream-parser-field-proof-guard",
    "NiDataStreamParserExportNonConsumptionGuard": "nidatastream-parser-export-non-consumption-guard",
    "NiDataStreamDescriptorProofStatus": "nidatastream-descriptor-proof-status",
    "NiDataStreamDescriptorSampleCompare": "nidatastream-descriptor-sample-compare",
    "NiDataStreamDescriptorTableSample": "nidatastream-descriptor-table-sample",
    "NiDataStreamDescriptorTableSampleStatus": "nidatastream-descriptor-table-sample-status",
    "NiDataStreamDescriptorNeighborhoodScan": "nidatastream-descriptor-neighborhood-scan",
    "NiDataStreamDescriptorReferenceClassify": "nidatastream-descriptor-reference-classify",
    "NiDataStreamDescriptorBaseModelReview": "nidatastream-descriptor-base-model-review",
}


print("=== Ghidra command wiring ===")
wrapper_text = Path("scripts/Invoke-RiftWorkflow.ps1").read_text(encoding="utf-8-sig")

for legacy_name, kebab_name in EXPECTED_GHIDRA_ALIASES.items():
    check(f"python PS_MODE_TO_COMMAND {legacy_name}", PS_MODE_TO_COMMAND.get(legacy_name), kebab_name)
    check(f"python COMMAND_MAP has {kebab_name}", kebab_name in COMMAND_MAP, True)
    check(
        f"PowerShell wrapper alias {legacy_name}",
        f"'{legacy_name}' = '{kebab_name}'" in wrapper_text,
        True,
    )

print(f"\n{'=' * 50}")
if failed:
    print(f"FAILURES: {failed}")
    sys.exit(1)
else:
    print("All tests passed!")
