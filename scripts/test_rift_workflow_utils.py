"""Smoke test for rift_workflow_utils.py ported functions."""
import sys
sys.path.insert(0, ".")

from scripts.rift_workflow_utils import (
    json_value_or_dash,
    json_value_or_none,
    json_double_or_none,
    measure_sum_or_zero,
    json_array_count_or_dash,
    required_json_value,
    required_json_boolean,
    required_json_number,
    required_json_integer,
    usage_access_guard_integer,
    assert_proof_guard,
    assert_usage_access_guard,
    is_generated_output_path,
    format_markdown_cell,
    top_text,
    format_nif_usage_access,
    format_vector_sample,
    format_proof_review_summary,
    semantic_hint_primary_model,
    semantic_hint_bucket,
    load_json_report,
)

failed = 0

def check(desc: str, actual, expected):
    global failed
    if actual == expected:
        print(f"  PASS: {desc}")
    else:
        print(f"  FAIL: {desc}  expected={expected!r}  actual={actual!r}")
        failed += 1

def check_raises(desc: str, fn, exc_type=ValueError):
    global failed
    try:
        fn()
        print(f"  FAIL: {desc} (no exception raised)")
        failed += 1
    except exc_type:
        print(f"  PASS: {desc}")


print("=== JSON accessors ===")
check("json_value_or_dash(None)", json_value_or_dash(None, "x"), "-")
check("json_value_or_dash(dict missing)", json_value_or_dash({}, "x"), "-")
check("json_value_or_dash(dict present)", json_value_or_dash({"x": 42}, "x"), 42)
check("json_value_or_dash(non-dict)", json_value_or_dash([1, 2, 3], "x"), "-")
check("json_value_or_none(None)", json_value_or_none(None, "x"), None)
check("json_value_or_none(missing)", json_value_or_none({}, "x"), None)
check("json_value_or_none(present)", json_value_or_none({"x": 99}, "x"), 99)
check("json_double_or_none(string)", json_double_or_none({"a": "3.14"}, "a"), 3.14)
check("json_double_or_none(None)", json_double_or_none(None, "a"), None)
check("json_double_or_none(bad)", json_double_or_none({"a": "abc"}, "a"), None)
check("measure_sum_or_zero", measure_sum_or_zero([{"v": "10"}, {"v": "5"}], "v"), 15.0)
check("json_array_count(dict)", json_array_count_or_dash({"a": [1, 2, 3]}, "a"), "3")
check("json_array_count(empty)", json_array_count_or_dash({}, "a"), "-")

print("=== Required accessors ===")
check("required_json_value", required_json_value({"x": 42}, "x", "test"), 42)
check_raises("required_json_value missing", lambda: required_json_value({}, "x", "test"))
check_raises("required_json_value None", lambda: required_json_value(None, "x", "test"))
check("required_json_number", required_json_number({"x": "3.14"}, "x", "test"), 3.14)
check_raises("required_json_number bad", lambda: required_json_number({"x": "abc"}, "x", "test"))
check("required_json_integer", required_json_integer({"x": "42"}, "x", "test"), 42)
check("required_json_integer(int)", required_json_integer({"x": 99}, "x", "test"), 99)
check_raises("required_json_number rejects bool True", lambda: required_json_number({"x": True}, "x", "test"))
check_raises("required_json_number rejects bool False", lambda: required_json_number({"x": False}, "x", "test"))
check_raises("required_json_integer inherits bool rejection", lambda: required_json_integer({"x": True}, "x", "test"))
print("=== Boolean accessor ===")
check("required_json_boolean(True)", required_json_boolean({"x": True}, "x", "test"), True)
check("required_json_boolean(False)", required_json_boolean({"x": False}, "x", "test"), False)
check_raises("required_json_boolean rejects int 1", lambda: required_json_boolean({"x": 1}, "x", "test"))
check_raises("required_json_boolean rejects string", lambda: required_json_boolean({"x": "true"}, "x", "test"))
check_raises("required_json_boolean rejects None", lambda: required_json_boolean({"x": None}, "x", "test"))
check("usage_access_guard_integer", usage_access_guard_integer({"x": 10}, "x", "test"), 10)
check_raises("usage_access_guard integer missing", lambda: usage_access_guard_integer({}, "x", "test"))

print("=== Guards ===")
check_raises("assert_proof_guard false", lambda: assert_proof_guard(False, "fail"))
assert_proof_guard(True, "pass")  # should not raise
print("  PASS: assert_proof_guard true")
check_raises("assert_usage_access_guard false", lambda: assert_usage_access_guard(False, "fail"))
assert_usage_access_guard(True, "pass")
print("  PASS: assert_usage_access_guard true")

print("=== Generated output path ===")
check("Source/", is_generated_output_path("Source/foo"), True)
check("Extracted/", is_generated_output_path("Extracted/bar"), True)
check("Exports/", is_generated_output_path("Exports/baz"), True)
check("bin/", is_generated_output_path("bin/Debug/foo.dll"), True)
check("obj/", is_generated_output_path("obj/project.csproj.nuget.g.props"), True)
check("__pycache__/", is_generated_output_path("scripts/__pycache__/foo.pyc"), True)
check(".pyc", is_generated_output_path("module.cpython-39.pyc"), True)
check("src/", is_generated_output_path("src/RiftAssetDumper/Program.cs"), False)
check("scripts/", is_generated_output_path("scripts/Invoke-RiftAssetWorkflow.ps1"), False)
check("empty", is_generated_output_path(""), False)

print("=== Formatting ===")
check("markdown cell pipe", format_markdown_cell("hello|world"), "hello\\|world")
check("markdown cell None", format_markdown_cell(None), "-")
check("markdown cell empty", format_markdown_cell("  "), "-")
check("top_text normal", top_text(["a", "b", "c"], lambda x: x.upper()), "A | B | C")
check("top_text empty", top_text([], lambda x: x), "none")
check("format_nif_usage", format_nif_usage_access({"DataStreamUsage": 5, "DataStreamAccess": 19}), "usage=5 access=19")

print("=== Vector sample ===")
v_pos = {"Index": 0, "Components": 3, "X": 1.0, "Y": 2.0, "Z": 3.0, "Attribute": "position", "PreviousDistance": 0.5, "NextDistance": 1.0}
check("vector pos", format_vector_sample(v_pos), "v0=(1.0,2.0,3.0) prev=0.5 next=1.0")

v_norm = {"Index": 1, "Components": 3, "X": 0.0, "Y": 1.0, "Z": 0.0, "Attribute": "normal", "VectorLength": 1.0}
check("vector normal", format_vector_sample(v_norm), "v1=(0.0,1.0,0.0) len=1.0")

print("=== Proof review ===")
check("proof empty", format_proof_review_summary({}), "proofFlags=- planes=- sign=- parityBreaks=-")
review = {
    "FirstSegmentProofReview": {
        "ReviewFlags": ["A", "B"],
        "DominantPlaneCounts": [{"Value": "XY", "Count": 10}],
        "PositiveDominantSignedAreaCount": 5,
        "NegativeDominantSignedAreaCount": 2,
        "ZeroDominantSignedAreaCount": 0,
        "NonAlternatingParityTransitionCount": 0,
    }
}
check("proof valid", format_proof_review_summary(review), "proofFlags=A,B planes=XY:10 sign=+5/-2/0 parityBreaks=0")

print("=== Semantic hints ===")
entry = {"NameCandidates": ["art/project/models/char/head.ma", "other/file.dds"]}
check("primary model", semantic_hint_primary_model(entry), "art/project/models/char/head.ma")
check("hint bucket", semantic_hint_bucket("art/project/models/characters/player/head.ma"), "models/characters/player/head.ma")

print(f"\n{'='*50}")
if failed:
    print(f"FAILURES: {failed}")
    sys.exit(1)
else:
    print("All tests passed!")
