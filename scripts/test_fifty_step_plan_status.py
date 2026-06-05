"""Validate the revived 50-step discovery-plan status surface."""

from __future__ import annotations

import json
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import jsonschema

sys.path.insert(0, ".")

from scripts import rift_workflow

failed = 0


def check(desc: str, actual: object, expected: object) -> None:
    global failed
    if actual == expected:
        print(f"  PASS: {desc}")
    else:
        print(f"  FAIL: {desc} expected={expected!r} actual={actual!r}")
        failed += 1


def check_contains(desc: str, text: str, expected: str) -> None:
    global failed
    if expected in text:
        print(f"  PASS: {desc}")
    else:
        print(f"  FAIL: {desc} missing={expected!r}")
        failed += 1


schema = json.loads(Path("docs/schemas/fifty-step-plan-status-v1.schema.json").read_text(encoding="utf-8"))
step48_schema = json.loads(Path("docs/schemas/live-memory-step48-status-v1.schema.json").read_text(encoding="utf-8"))
step48_status = json.loads(Path("docs/live-memory-step48-status.json").read_text(encoding="utf-8"))
step49_schema = json.loads(Path("docs/schemas/live-memory-step49-status-v1.schema.json").read_text(encoding="utf-8"))
step49_status = json.loads(Path("docs/live-memory-step49-status.json").read_text(encoding="utf-8"))

print("=== 50-step plan status JSON ===")
jsonschema.validate(step48_status, step48_schema)
print("  PASS: Step 48 live scan status schema validation")
jsonschema.validate(step49_status, step49_schema)
print("  PASS: Step 49 live scan status schema validation")
check(
    "step 49 generic RiftReader triplet command available", step49_status["RiftReaderGenericTripletScanAvailable"], True
)
check(
    "step 49 generic RiftReader triplet command",
    step49_status["RiftReaderGenericTripletScanCommand"],
    "--scan-float-triplet <x,y,z> --scan-region-base <address> --scan-region-size <bytes>",
)
check("step 49 bounded triplet probe executed", step49_status["BoundedTripletProbeExecuted"], True)
check("step 49 bounded positive control hits", step49_status["BoundedTripletPositiveControlHitCount"], 2)
check("step 49 bounded expected static v0 hits", step49_status["BoundedExpectedStaticV0HitCount"], 0)
check("step 49 bounded expected batch executed", step49_status["BoundedExpectedStaticBatchExecuted"], True)
check("step 49 bounded expected batch regions", step49_status["BoundedExpectedStaticBatchRegionCount"], 4)
check("step 49 bounded expected batch vertices", step49_status["BoundedExpectedStaticBatchVertexCount"], 4)
check("step 49 bounded expected batch scans", step49_status["BoundedExpectedStaticBatchScanCount"], 16)
check("step 49 bounded expected batch hits", step49_status["BoundedExpectedStaticBatchHitCount"], 0)
check("step 49 full-process expected batch executed", step49_status["FullProcessExpectedStaticBatchExecuted"], True)
check("step 49 full-process expected batch vertices", step49_status["FullProcessExpectedStaticBatchVertexCount"], 4)
check("step 49 full-process expected batch scans", step49_status["FullProcessExpectedStaticBatchScanCount"], 4)
check("step 49 full-process expected batch hits", step49_status["FullProcessExpectedStaticBatchHitCount"], 0)
check("step 49 closure mode", step49_status["Step49ClosureMode"], "closed-negative-current-live-state")
check("step 49 complete after negative closure", step49_status["Step49Complete"], True)
output = StringIO()
with patch.object(sys, "argv", ["rift_workflow.py", "fifty-step-plan-status", "--list-json"]), redirect_stdout(output):
    rift_workflow.main()
status = json.loads(output.getvalue())
jsonschema.validate(status, schema)
print("  PASS: 50-step plan status schema validation")
check("schema version", status["SchemaVersion"], "fifty-step-plan-status/v1")
check("total steps", status["TotalSteps"], 50)
check("completed step count", status["CompletedStepCount"], 50)
check("current stage", status["CurrentStageNumber"], 5)
check("current step", status["CurrentStepNumber"], 50)
check("current step status", status["CurrentStepStatus"], "complete")
check("step 46 boundary complete", status["Step46SafetyBoundaryComplete"], True)
check("step 47 scanner implemented", status["Step47ScannerImplemented"], True)
check("step 48 dry-run manifest ready", status["Step48DryRunManifestReady"], True)
check("step 48 live read executed", status["Step48LiveReadExecuted"], True)
check("step 48 pattern found", status["Step48PatternFound"], True)
check("step 48 provider", status["Step48Provider"], "RiftReader.Reader")
check("step 49 initial probe executed", status["Step49InitialProbeExecuted"], True)
check("step 49 cluster confirmed", status["Step49ClusterConfirmed"], False)
check("step 49 closure mode", status["Step49ClosureMode"], "closed-negative-current-live-state")
check("step 49 closed without cluster confirmation", status["Step49ClosedWithoutClusterConfirmation"], True)
check("step 49 full-process expected batch executed", status["Step49FullProcessExpectedStaticBatchExecuted"], True)
check("step 49 full-process expected batch hits", status["Step49FullProcessExpectedStaticBatchHitCount"], 0)
check("step 49 complete", status["Step49Complete"], True)
check("step 49 provider", status["Step49Provider"], "RiftReader.Reader")
check("step 50 final handoff complete", status["Step50FinalHandoffComplete"], True)
check("live process read executed", status["LiveProcessReadExecuted"], True)
check("live process read approved for this run", status["LiveProcessReadApprovedForThisRun"], True)
check("parser/export promotion remains blocked", status["ParserExportPromotionAllowed"], False)
check_contains("next action keeps export promotion blocked", status["NextAction"], "parser/export behavior change")

print("=== 50-step plan status text ===")
text_output = StringIO()
with patch.object(sys, "argv", ["rift_workflow.py", "fifty-step-plan-status"]), redirect_stdout(text_output):
    rift_workflow.main()
text = text_output.getvalue()
check_contains("text status title", text, "FiftyStepPlanStatus")
check_contains("text current step", text, "Step 50")
check_contains("text step 49 probe", text, "Step 49 initial probe executed: true")
check_contains("text step 49 closure", text, "Step 49 closure mode: closed-negative-current-live-state")
check_contains("text step 50 final handoff", text, "Step 50 final handoff complete: true")

print(f"\n{'=' * 50}")
if failed:
    print(f"FAILURES: {failed}")
    sys.exit(1)
else:
    print("All tests passed!")
