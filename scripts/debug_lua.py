import json

with open(r"C:\RIFT MODDING\Assets\Exports\semantic-phase4\smoke-lua-012.json", encoding="utf-8-sig") as f:
    data = json.load(f)

entries = data.get("Entries", [])
print(f"Total entries: {len(entries)}")

for i, e in enumerate(entries[:2]):
    dt = e.get("DetectedType")
    tss = e.get("TextSnippetSamples", [])
    print(f"Entry {i}: DetectedType={dt}, TextSnippetSamples type={type(tss)}, len={len(tss)}")
    for j, s in enumerate(tss[:3]):
        print(f"  Snippet {j}: {s[:80]}")
