#!/usr/bin/env python3
"""Extract full discovery details including any asset IDs."""
import json

# Check discovery scoreboard JSON
with open("Exports/discovery-workbench-scoreboard.json", encoding="utf-8-sig") as f:
    sb = json.load(f)

print(f"Scoreboard keys: {list(sb.keys())}")
print(f"Candidate count from key 'Candidates': {len(sb.get('Candidates', []))}")
print(f"Candidate count from key 'Scoreboard': {len(sb.get('Scoreboard', []))}")
print(f"Candidate count from key 'scoreboard': {len(sb.get('scoreboard', []))}")

# Find the candidates array
candidates = sb.get("Candidates", sb.get("Scoreboard", sb.get("scoreboard", [])))
print(f"\nCandidates found: {len(candidates)}")
if candidates and isinstance(candidates[0], dict):
    print(f"Sample keys: {list(candidates[0].keys())}")
    for i, c in enumerate(candidates[:8]):
        print(f"\n  [{i}]:")
        for k, v in c.items():
            if isinstance(v, str) and len(v) < 300:
                print(f"    {k}: {v}")
            elif isinstance(v, (int, float)):
                print(f"    {k}: {v}")
            elif isinstance(v, list) and len(v) <= 10:
                print(f"    {k}: {v}")

# Check discovery next probe queue JSON
with open("Exports/discovery-next-probe-queue.json", encoding="utf-8-sig") as f:
    q = json.load(f)

print(f"\nQueue keys: {list(q.keys())}")
queue_items = q.get("Queue", q.get("queue", []))
print(f"Queue items: {len(queue_items)}")
if queue_items and isinstance(queue_items[0], dict):
    print(f"Sample keys: {list(queue_items[0].keys())}")
    for i, item in enumerate(queue_items[:8]):
        print(f"\n  [{i}]:")
        for k, v in item.items():
            if isinstance(v, str) and len(v) < 300:
                print(f"    {k}: {v}")
            elif isinstance(v, (int, float)):
                print(f"    {k}: {v}")
            elif isinstance(v, list) and len(v) <= 10:
                print(f"    {k}: {v}")
