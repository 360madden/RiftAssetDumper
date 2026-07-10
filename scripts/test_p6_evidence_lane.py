"""Tests for P6 evidence lane: candidate scorer, proof packets, restart gate."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.rift_candidate_scorer import (
    _score_categories,
    _score_name_candidates,
    _score_pattern_label,
    score_candidates,
)
from scripts.rift_proof_packets import (
    _packet_id,
    build_packets_from_scan,
    merge_packets,
)
from scripts.rift_restart_gate import (
    _build_candidate_history,
    _candidate_key,
    evaluate_gate,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SEMANTIC_INDEX = {
    "SchemaVersion": "asset-semantic-index/v1",
    "Entries": [
        {
            "AssetIdPrefix": "aabbccdd11223344",
            "ArchiveName": "test.dat",
            "EntryIndex": 0,
            "CompressedSize": 100,
            "UnpackedSize": 200,
            "Compression": 0,
            "DetectedType": "xml",
            "First4": "3C3F786D",
            "First8": "3C3F786D6C207665",
            "First16": "3C3F786D6C2076657273696F6E3D2231",
            "MagicLabel": "xml-question-mark",
            "SemanticCategories": ["hint:map-zone", "type:xml"],
            "NameCandidates": ["zone_map", "continent_data"],
            "ReferenceSamples": [],
            "XmlTagCounts": [],
            "XmlAttributeCounts": [],
            "TextSnippetSamples": [],
        },
        {
            "AssetIdPrefix": "1122334455667788",
            "ArchiveName": "test.dat",
            "EntryIndex": 1,
            "CompressedSize": 50,
            "UnpackedSize": 100,
            "Compression": 0,
            "DetectedType": "nif",
            "First4": "02000000",
            "First8": "0200000014000000",
            "First16": "02000000140000000600000001000000",
            "MagicLabel": "nif-gamebryo-20",
            "SemanticCategories": ["hint:actor-model", "type:nif"],
            "NameCandidates": ["npc_humanoid", "creature_wolf"],
            "ReferenceSamples": [],
            "XmlTagCounts": [],
            "XmlAttributeCounts": [],
            "TextSnippetSamples": [],
        },
        {
            "AssetIdPrefix": "aabb001122334455",
            "ArchiveName": "ui.dat",
            "EntryIndex": 0,
            "CompressedSize": 80,
            "UnpackedSize": 160,
            "Compression": 0,
            "DetectedType": "lua",
            "First4": "2D2D2041",
            "First8": "2D2D204164646F6E",
            "First16": "2D2D204164646F6E206672616D65776F",
            "MagicLabel": "lua-double-dash",
            "SemanticCategories": ["hint:ui-lua-xml", "type:lua"],
            "NameCandidates": ["addon_frame", "ui_button"],
            "ReferenceSamples": [],
            "XmlTagCounts": [],
            "XmlAttributeCounts": [],
            "TextSnippetSamples": [],
        },
    ],
}


SCAN_RESULT = {
    "ScanResult": {
        "PatternResults": [
            {
                "Label": "zone-pattern",
                "MatchCount": 2,
                "Matches": [
                    {
                        "Address": "0x7FFE00001000",
                        "RegionBase": "0x7FFE00000000",
                        "OffsetInRegion": 0x1000,
                        "SnippetHex": "48656C6C6F",
                    },
                    {
                        "Address": "0x7FFE00002000",
                        "RegionBase": "0x7FFE00000000",
                        "OffsetInRegion": 0x2000,
                        "SnippetHex": "576F726C64",
                    },
                ],
            },
            {
                "Label": "unknown-pattern",
                "MatchCount": 1,
                "Matches": [
                    {
                        "Address": "0x7FFE00003000",
                        "RegionBase": "0x7FFE00000000",
                        "OffsetInRegion": 0x3000,
                        "SnippetHex": "DEADBEEF",
                    },
                ],
            },
        ]
    }
}


# ---------------------------------------------------------------------------
# Candidate scorer tests
# ---------------------------------------------------------------------------


class TestCandidateScorer:
    def test_score_categories_map_zone(self):
        assert _score_categories(["hint:map-zone"]) == 100

    def test_score_categories_multiple(self):
        score = _score_categories(["hint:map-zone", "type:xml"])
        assert score == 125  # 100 + 25

    def test_score_categories_empty(self):
        assert _score_categories([]) == 0

    def test_score_pattern_label_zone(self):
        assert _score_pattern_label("zone-pattern") == 40

    def test_score_pattern_label_unknown(self):
        assert _score_pattern_label("unknown-pattern") == 0

    def test_score_name_candidates_actor(self):
        assert _score_name_candidates(["npc_humanoid"]) == 20

    def test_score_name_candidates_empty(self):
        assert _score_name_candidates([]) == 0

    def test_score_candidates_basic(self):
        scored = score_candidates(SCAN_RESULT, SEMANTIC_INDEX)
        assert scored["TotalCandidates"] == 3
        assert scored["SchemaVersion"] == "scored-candidates/v1"
        # zone-pattern matches should have higher scores
        zone_scores = [c["TotalScore"] for c in scored["Candidates"] if c["PatternLabel"] == "zone-pattern"]
        unknown_scores = [c["TotalScore"] for c in scored["Candidates"] if c["PatternLabel"] == "unknown-pattern"]
        assert max(zone_scores) > max(unknown_scores)

    def test_score_candidates_sorted_by_score(self):
        scored = score_candidates(SCAN_RESULT, SEMANTIC_INDEX)
        scores = [c["TotalScore"] for c in scored["Candidates"]]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# Proof packets tests
# ---------------------------------------------------------------------------


class TestProofPackets:
    def test_packet_id_deterministic(self):
        id1 = _packet_id("0x1000", "session1", 1234)
        id2 = _packet_id("0x1000", "session1", 1234)
        assert id1 == id2

    def test_packet_id_varies_by_address(self):
        id1 = _packet_id("0x1000", "session1", 1234)
        id2 = _packet_id("0x2000", "session1", 1234)
        assert id1 != id2

    def test_build_packets_from_scan(self):
        packets = build_packets_from_scan(SCAN_RESULT, pid=9999, session_label="test-run")
        assert packets["PacketCount"] == 3
        assert packets["Pid"] == 9999
        assert packets["SessionLabel"] == "test-run"
        for p in packets["Packets"]:
            assert p["Pid"] == 9999
            assert p["SessionLabel"] == "test-run"
            assert p["Status"] == "candidate"
            assert p["RestartCount"] == 0

    def test_merge_packets_new(self):
        packets1 = build_packets_from_scan(SCAN_RESULT, pid=1000, session_label="run1")
        packets2 = build_packets_from_scan(SCAN_RESULT, pid=2000, session_label="run2")
        merged = merge_packets(packets1, packets2)
        # Different PIDs → different packet IDs → all 6 kept
        assert merged["PacketCount"] == 6
        assert merged.get("MergedFromPrevious", 0) == 0

    def test_merge_packets_none_existing(self):
        packets = build_packets_from_scan(SCAN_RESULT, pid=1000, session_label="run1")
        merged = merge_packets(None, packets)
        assert merged["PacketCount"] == 3


# ---------------------------------------------------------------------------
# Restart gate tests
# ---------------------------------------------------------------------------


class TestRestartGate:
    def test_candidate_key(self):
        p = {"PatternLabel": "zone", "SnippetHex": "AABB"}
        assert _candidate_key(p) == "zone:AABB"

    def test_build_candidate_history(self):
        packets = build_packets_from_scan(SCAN_RESULT, pid=1000, session_label="run1")
        history = _build_candidate_history(packets)
        assert len(history) == 3

    def test_evaluate_gate_all_candidates(self):
        packets = build_packets_from_scan(SCAN_RESULT, pid=1000, session_label="run1")
        history = _build_candidate_history(packets)
        report = evaluate_gate(history)
        assert report["DurableCount"] == 0
        assert report["CandidateCount"] == 3
        assert report["TotalCandidates"] == 3

    def test_evaluate_gate_durable_after_two_sessions(self):
        packets1 = build_packets_from_scan(SCAN_RESULT, pid=1000, session_label="run1")
        packets2 = build_packets_from_scan(SCAN_RESULT, pid=2000, session_label="run2")
        merged = merge_packets(packets1, packets2)
        # Simulate restart counts and asset-backed scores
        for p in merged["Packets"]:
            p["RestartCount"] = 2
            p["Score"] = 100
            p["AssetCategories"] = ["hint:map-zone"]
        history = _build_candidate_history(merged)
        report = evaluate_gate(history)
        # All 3 candidates should be durable (asset-backed + 2 restarts)
        assert report["DurableCount"] == 3
        assert report["CandidateCount"] == 0
