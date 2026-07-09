# Semantic Vocabulary Consumer Contract

**Version:** 1.0
**Generated:** 2026-07-09
**Purpose:** Defines the import contract for consumers of the RIFT semantic vocabulary artifacts.

---

## 1. Artifact Overview

The semantic vocabulary system consists of 5 domain-specific vocabulary artifacts plus a unified index. Each artifact is a self-contained JSON file with a corresponding JSON Schema for validation.

| Vocabulary | Schema ID | Artifact Path | Schema Path | Phase |
|---|---|---|---|---|
| Zone | `zone-vocabulary-v1` | `Exports/semantic-phase1/zone-vocabulary.json` | `docs/schemas/zone-vocabulary-v1.schema.json` | 1 |
| POI | `poi-vocabulary-v1` | `Exports/semantic-phase2/poi-vocabulary.json` | `docs/schemas/poi-vocabulary-v1.schema.json` | 2 |
| Actor | `actor-vocabulary-v1` | `Exports/semantic-phase3/actor-vocabulary.json` | `docs/schemas/actor-vocabulary-v1.schema.json` | 3 |
| UI | `ui-vocabulary-v1` | `Exports/semantic-phase4/ui-vocabulary.json` | `docs/schemas/ui-vocabulary-v1.schema.json` | 4 |
| Audio | `audio-vocabulary-v1` | `Exports/semantic-phase5/audio-vocabulary.json` | `docs/schemas/audio-vocabulary-v1.schema.json` | 5 |
| **Index** | `vocabulary-index-v1` | `Exports/semantic-phase6/vocabulary-index.json` | `docs/schemas/vocabulary-index-v1.schema.json` | 6 |

---

## 2. Schema Validation

All vocabulary artifacts MUST be validated against their corresponding JSON Schema before consumption. Use the `schema` field in each artifact to identify which schema to validate against.

```python
import json
import jsonschema

# Load artifact
with open("Exports/semantic-phase1/zone-vocabulary.json") as f:
    artifact = json.load(f)

# Load corresponding schema
schema_id = artifact["schema"]  # "zone-vocabulary-v1"
with open(f"docs/schemas/{schema_id}.schema.json") as f:
    schema = json.load(f)

# Validate
jsonschema.validate(artifact, schema)
```

---

## 3. Field Meanings

### 3.1 Common Fields (All Vocabularies)

| Field | Type | Description |
|---|---|---|
| `schema` | `string` | Schema identifier. Use this to select the correct validator. |
| `generated_at` | `string` | ISO 8601 timestamp of when the artifact was generated. |

### 3.2 Semantic Category Tags

Entries across POI, Actor, and Audio vocabularies use a tag-based semantic categorization system. Tags use a `prefix:value` format with the following meanings:

| Prefix | Meaning | Confidence | Parser Required |
|---|---|---|---|
| `hint:*` | Heuristic classification based on string pattern matching | Medium | No |
| `ref:*` | Parser-backed reference (texture, model, audio, etc.) | High | Yes (format parser) |
| `type:*` | Binary format type | High | No (header inspection) |
| `asset:*` | Asset classification | High | Yes (signature library) |

**Examples:**

- `hint:actor-object` — String patterns suggest this is an actor/object asset
- `hint:waypoint-poi` — String patterns suggest this is a waypoint/POI asset
- `ref:texture` — Parser confirmed this contains a texture reference
- `ref:model` — Parser confirmed this contains a 3D model reference
- `ref:audio` — Parser confirmed this contains an audio reference
- `type:bin` — Binary format confirmed
- `asset:unknown-binary` — Binary signature not yet classified

### 3.3 Domain-Specific Fields

#### Zone Vocabulary (`zone-vocabulary-v1`)

| Field | Type | Description |
|---|---|---|
| `groups` | `array` | Grouped entries keyed by common strings |
| `groups[].group_key` | `string` | Primary grouping string |
| `groups[].zone_names` | `string[]` | Zone names associated with this group |
| `groups[].map_keys` | `string[]` | Map key identifiers |
| `groups[].file_paths` | `string[]` | File paths within game assets |
| `groups[].shader_references` | `string[]` | Shader variable/parameter names |
| `groups[].entries` | `array` | Raw asset entries (asset_id, archive, entry_index, type) |
| `classification_counts` | `object` | Counts of strings per classification category |
| `total_zone_entries` | `integer` | Total entries across all groups |
| `total_inspected_payloads` | `integer` | Total payloads inspected during generation |

#### POI Vocabulary (`poi-vocabulary-v1`)

| Field | Type | Description |
|---|---|---|
| `names` | `string[]` | Deduplicated list of all unique POI names |
| `entries` | `array` | Individual POI entries |
| `entries[].name_candidates` | `string[]` | Possible name identifiers |
| `entries[].text_snippets` | `string[]` | Extracted text content |
| `entries[].semantic_categories` | `string[]` | Classification tags |
| `total_poi_entries` | `integer` | Total POI entries |
| `total_unique_names` | `integer` | Unique name count |

#### Actor Vocabulary (`actor-vocabulary-v1`)

| Field | Type | Description |
|---|---|---|
| `names` | `string[]` | Deduplicated list of all unique actor names |
| `entries` | `array` | Individual actor entries |
| `entries[].name_candidates` | `string[]` | Possible name identifiers |
| `entries[].text_snippets` | `string[]` | Extracted text content |
| `entries[].semantic_categories` | `string[]` | Classification tags |
| `total_actor_entries` | `integer` | Total actor entries |
| `total_unique_names` | `integer` | Unique name count |

#### UI Vocabulary (`ui-vocabulary-v1`)

| Field | Type | Description |
|---|---|---|
| `xml_tags` | `object` | XML tags grouped by category (ui-frame, typed-structure) |
| `xml_attributes` | `object` | XML attributes grouped by category |
| `lua_functions` | `object` | Lua functions grouped by category (function-declaration, framework-api, addon-interface) |
| `lua_comments` | `array` | Extracted Lua comments with entry references |
| `cross_references` | `array` | XML-to-Lua cross-references |
| `summary` | `object` | Aggregate counts |

#### Audio Vocabulary (`audio-vocabulary-v1`)

| Field | Type | Description |
|---|---|---|
| `categories` | `object` | Audio entries grouped by category (ambient, sfx, footstep, voice) |
| `categories[].entries[].name` | `string` | Audio asset name or locator identifier |
| `categories[].entries[].zone_associations` | `string[]` | Zones where this audio is used |
| `riff_audio_assets` | `object` | RIFF audio asset metadata (archive, count, size distribution) |
| `zone_cross_references` | `object` | Zone-to-audio mapping |
| `all_unique_audio_strings` | `string[]` | All unique audio-related strings |

---

## 4. `hint:*` vs Parser-Backed Distinctions

The semantic categorization system distinguishes between two confidence levels:

### 4.1 `hint:*` Tags (Heuristic)

- **Source**: Pattern matching on extracted strings
- **Confidence**: Medium — may produce false positives
- **Parser Required**: No
- **Use Cases**: Initial asset triage, broad classification, search indexing
- **Examples**: `hint:actor-object`, `hint:waypoint-poi`, `hint:quest-objective`, `hint:map-zone`

### 4.2 `ref:*` Tags (Parser-Backed)

- **Source**: Format-specific parsers (texture headers, model structures, audio RIFF headers)
- **Confidence**: High — verified against binary format specifications
- **Parser Required**: Yes — format parser must be available
- **Use Cases**: Asset import pipeline, format validation, resource binding
- **Examples**: `ref:texture`, `ref:model`, `ref:audio`

### 4.3 Consumer Guidance

- For **discovery and search**, prefer `hint:*` tags for breadth
- For **import and rendering**, require `ref:*` tags for reliability
- Always validate against the JSON Schema before trusting any field

---

## 5. Stability Guarantees

### 5.1 Schema Versioning

- All schemas use `v1` suffix, indicating initial stable release
- Schema changes that break backward compatibility will increment the version number
- The `schema` field in each artifact MUST match the schema file name

### 5.2 Field Stability

| Field | Stability | Notes |
|---|---|---|
| `schema` | Stable | Will only change with major version bump |
| `generated_at` | Stable | Always present, ISO 8601 format |
| `names` | Stable | May grow as new assets are analyzed |
| `entries` | Stable | May grow as new assets are analyzed |
| `semantic_categories` | Stable | New tags may be added, existing tags will not be removed |
| `classification_counts` | Stable | Counts may change as analysis improves |

### 5.3 Artifact Immutability

- Published artifacts are immutable once generated
- Re-analysis produces a new artifact with an updated `generated_at` timestamp
- Consumers SHOULD cache artifacts by `generated_at` to detect updates

### 5.4 Cross-Reference Stability

Cross-references between vocabularies (e.g., audio-to-zone) are derived data and may be updated. The reference types are stable but the specific references may change as analysis improves.

---

## 6. Import Workflow

### 6.1 Recommended Import Order

1. Load `vocabulary-index-v1` to discover available vocabularies
2. Validate the index against `vocabulary-index-v1.schema.json`
3. Load each vocabulary artifact referenced in the index
4. Validate each artifact against its corresponding schema
5. Build in-memory indexes by domain (zone, POI, actor, UI, audio)

### 6.2 Minimal Import Example

```python
import json
from pathlib import Path

INDEX_PATH = Path("Exports/semantic-phase6/vocabulary-index.json")
SCHEMA_DIR = Path("docs/schemas")

def load_vocabulary_system():
    # Load and validate index
    with open(INDEX_PATH) as f:
        index = json.load(f)

    vocabularies = {}
    for entry in index["vocabularies"]:
        schema_path = SCHEMA_DIR / f"{entry['schema']}.schema.json"
        artifact_path = Path(entry["path"])

        with open(artifact_path) as f:
            vocab = json.load(f)

        vocabularies[entry["id"]] = {
            "schema": entry["schema"],
            "phase": entry["phase"],
            "status": entry["status"],
            "data": vocab,
        }

    return index, vocabularies
```

---

## 7. File Layout

```
Exports/
  semantic-phase1/
    zone-vocabulary.json          # Phase 1 artifact
  semantic-phase2/
    poi-vocabulary.json           # Phase 2 artifact
  semantic-phase3/
    actor-vocabulary.json         # Phase 3 artifact
  semantic-phase4/
    ui-vocabulary.json            # Phase 4 artifact
  semantic-phase5/
    audio-vocabulary.json         # Phase 5 artifact
  semantic-phase6/
    vocabulary-index.json         # Unified index

docs/
  schemas/
    zone-vocabulary-v1.schema.json
    poi-vocabulary-v1.schema.json
    actor-vocabulary-v1.schema.json
    ui-vocabulary-v1.schema.json
    audio-vocabulary-v1.schema.json
    vocabulary-index-v1.schema.json
```

---

## 8. Consumer Responsibilities

- Validate artifacts before use (JSON Schema validation)
- Handle missing fields gracefully (some vocabularies have optional fields)
- Respect the `hint:*` vs `ref:*` distinction for confidence scoring
- Cache artifacts by `generated_at` to avoid redundant loads
- Do not modify artifacts; treat them as read-only published data
