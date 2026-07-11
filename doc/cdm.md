# Project LilaKosha Common Document Model (CDM) Specification

The **Common Document Model (CDM)** is the foundational storage, interchange, and enrichment schema used throughout Project LilaKosha.

The CDM serves as the canonical representation for all processed artifacts flowing through ingestion, refinement, reporting, and future training pipelines. Every record stored within the `cdm/records/` repository is represented as a standalone `Document` object serialized to JSON.

The model is intentionally document-oriented rather than conversation-oriented. While conversational datasets such as PIPPA remain a primary ingestion source, the CDM is designed to support a broader range of narrative, literary, analytical, and synthetic content forms.

## Design Goals

The CDM was designed around several core principles:

* **Document-Oriented Storage** – Every artifact is represented as a standalone document with stable identity.
* **Flat Addressable Structure** – All content elements are independently addressable through deterministic item identifiers.
* **Identity Preservation** – Character and actor identities remain stable throughout enrichment and transformation passes.
* **Extensible Semantic Layers** – New classifications, annotations, and evaluations can be added without schema proliferation.
* **Pipeline Compatibility** – Refinement, reporting, and training pipelines operate against a common structural representation.
* **Human Operability** – Records remain readable and inspectable without specialized tooling.

## Architectural Overview

The CDM uses a discriminated-union architecture implemented through Pydantic.

Each document consists of two major sections:

```text
Document (kind: "document")
├── id
├── meta: DocumentMeta
│   ├── identities
│   ├── annotations
│   ├── safety classifications
│   ├── genre classifications
│   ├── operational metadata
│   └── materialized statistics
└── items: List[DocumentItem]
    ├── WorldItem
    ├── CharacterItem
    ├── SummaryItem
    ├── NarrativeItem
    ├── TurnItem
    ├── CategorizationItem
    └── SequenceItem
```

The `items` collection is intentionally maintained as a flat chronological structure rather than a nested hierarchy. This simplifies traversal, enrichment, serialization, and future distributed processing.

## Identity Registry

Each document contains an authoritative identity registry.

```text
Document
└── meta
    └── identities
```

This registry defines every actor referenced throughout the document and serves as the canonical source of truth for names, pronouns, and identity metadata.

Downstream grammar normalization, narrative rewriting, summarization, and future training workloads rely on this registry to prevent semantic drift.

### CharacterIdentity

| Field                  | Description                                                   |
| ---------------------- | ------------------------------------------------------------- |
| `entity_id`            | Stable semantic identifier within the document                |
| `name`                 | Canonical display name                                        |
| `gender`               | `male`, `female`, `neutral`, or `unknown`                     |
| `pronouns`             | Structured pronoun mapping                                    |
| `is_player_controlled` | Indicates whether the identity represents a human participant |

Example:

```json
{
  "entity_id": "user",
  "name": "Traveler",
  "gender": "neutral",
  "pronouns": {
    "subjective": "they",
    "objective": "them",
    "possessive": "their"
  },
  "is_player_controlled": true
}
```

## Metadata Layer

The `meta` section contains document-level attributes that apply to the record as a whole.

### Core Metadata

| Field                 | Description                                |
| --------------------- | ------------------------------------------ |
| `source_identity`     | Origin system or ingestion source          |
| `source_record`       | Optional source-specific metadata          |
| `bot_id`              | Source platform character identifier       |
| `bot_name`            | Source platform character name             |
| `ingestion_timestamp` | Original ingestion timestamp               |
| `healthy`             | Pipeline health state indicator            |
| `crpo_signals`        | Training and ranking signals               |
| `annotations`         | Pipeline-generated operational annotations |

### Classification Metadata

The current model materializes several commonly-used classifications directly within metadata:

| Field           |
| --------------- |
| `sexual_axis`   |
| `violence_axis` |
| `toxicity_axis` |
| `primary_genre` |
| `themes`        |

These fields are additionally mirrored into structural `CategorizationItem` records to support future migration toward fully itemized semantic classification.

### Materialized Statistics

The `stats` field stores precomputed metrics to avoid repeated aggregate scans across large datasets.

Typical metrics include:

* Turn counts
* Item counts
* Character counts
* Word counts
* Future operational metrics

## Document Item Types

Every entry in the `items` collection must declare a valid `kind` discriminator.

### WorldItem

Represents environmental, spatial, setting, or lore information.

```json
{
  "id": "world-000001",
  "kind": "world",
  "content": "The city is protected by a magical barrier."
}
```

### CharacterItem

Represents extracted character knowledge, behavioral observations, or evolving state information.

```json
{
  "id": "character-000001",
  "kind": "character",
  "entity_id": "bot_001",
  "content": "The character distrusts authority figures."
}
```

### SummaryItem

Represents synthesized recap material or compressed context.

```json
{
  "id": "summary-000001",
  "kind": "summary",
  "content": "The protagonists escaped the fortress."
}
```

### NarrativeItem

Represents generic long-form prose content.

This type enables storage of literary, narrative, or non-conversational datasets without forcing dialogue semantics.

```json
{
  "id": "narrative-000001",
  "kind": "narrative",
  "prose": "The storm arrived shortly after sunset."
}
```

### TurnItem

A specialization of `NarrativeItem` representing actor-attributed conversational content.

```json
{
  "id": "turn-000001",
  "kind": "turn",
  "actor_id": "user",
  "thought": "",
  "prose": "We should leave before nightfall."
}
```

Additional fields support grammar refinement lineage tracking:

| Field                     | Purpose                                    |
| ------------------------- | ------------------------------------------ |
| `original_prose`          | Original source text                       |
| `prose_revision_comments` | Revision rationale                         |
| `thought`                 | Internal reasoning or side-channel content |

### CategorizationItem

Represents a structured semantic classification attached to the document.

This mechanism replaces continual schema expansion whenever new evaluation dimensions are introduced.

Examples include:

* Safety classifications
* Genre assignments
* Theme extraction
* Quality scores
* Evaluation labels
* Future ranking metrics

```json
{
  "id": "categorization-000001",
  "kind": "categorization",
  "category": "genre",
  "value": "Fantasy"
}
```

### SequenceItem

Represents ordered relationships between existing items.

This provides lightweight structural grouping without introducing complex graph hierarchies.

```json
{
  "id": "sequence-000001",
  "kind": "sequence",
  "item_ids": [
    "turn-000001",
    "turn-000002",
    "turn-000003"
  ]
}
```

## Classification Enumerations

### SexualScale

| Value        | Meaning                         |
| ------------ | ------------------------------- |
| `Clean`      | No overt sexual content         |
| `Suggestive` | Romantic or suggestive material |
| `Explicit`   | Graphic sexual content          |

### ViolenceScale

| Value     | Meaning                   |
| --------- | ------------------------- |
| `None`    | No meaningful violence    |
| `Combat`  | Standard action or combat |
| `Graphic` | Graphic injury or harm    |

### ToxicityScale

| Value        | Meaning                           |
| ------------ | --------------------------------- |
| `Safe`       | No significant hostile language   |
| `Harassment` | Degrading or abusive interactions |
| `Dangerous`  | Extreme harmful content           |

### MainGenre

* Fantasy
* Sci-Fi
* Romance
* Slice of Life
* Action & Adventure
* Mystery & Thriller
* Comedy
* Drama

## Example Document

```json
{
  "id": "019f0000-0000-7000-8000-000000000000",
  "kind": "document",
  "meta": {
    "source_identity": "PIPPA-INGEST",
    "bot_name": "Akane",
    "sexual_axis": "Suggestive",
    "primary_genre": "Fantasy",
    "themes": [
      "identity",
      "power-dynamics"
    ]
  },
  "items": [
    {
      "id": "world-000001",
      "kind": "world",
      "content": "The Yashiro Commission controls regional governance."
    },
    {
      "id": "character-000001",
      "kind": "character",
      "entity_id": "bot_akane",
      "content": "Akane seeks to preserve her stolen identity."
    },
    {
      "id": "summary-000001",
      "kind": "summary",
      "content": "Akane has successfully displaced her former mistress."
    },
    {
      "id": "categorization-000001",
      "kind": "categorization",
      "category": "genre",
      "value": "Fantasy"
    },
    {
      "id": "categorization-000002",
      "kind": "categorization",
      "category": "theme",
      "value": [
        "identity",
        "power-dynamics"
      ]
    },
    {
      "id": "turn-000001",
      "kind": "turn",
      "actor_id": "user",
      "thought": "",
      "prose": "What happens if the truth comes out?"
    },
    {
      "id": "turn-000002",
      "kind": "turn",
      "actor_id": "bot_akane",
      "thought": "The user still believes restitution is possible.",
      "prose": "Then everyone loses."
    },
    {
      "id": "sequence-000001",
      "kind": "sequence",
      "item_ids": [
        "turn-000001",
        "turn-000002"
      ]
    }
  ]
}
```

## Evolution Notes

The CDM evolved from an earlier conversation-centric Session model into a generalized document-oriented architecture.

Major milestones include:

* Session → Document transition
* Removal of item subkind hierarchies
* Introduction of stable item identifiers
* Introduction of `NarrativeItem`
* Introduction of `CategorizationItem`
* Introduction of `SequenceItem`
* Materialized document statistics
* Identity-registry-based actor modeling

The current architecture intentionally favors extensibility and operational simplicity over deeply nested object hierarchies, enabling efficient enrichment pipelines, large-scale dataset maintenance, and future training workflows.
