# LilaKosha-Flow-MK1: High-Level Design

## Architecture Overview

```text
┌─────────────────────────────────────────────────────────────────────┐
│                    main.py (Pipeline Orchestrator)                  │
│  - Discovers pipeline/*.yml configurations                          │
│  - Loads YAML with environment interpolation                        │
│  - Validates LILAKOSHA_VOLUME_* configuration                       │
│  - Applies runtime parameter overrides                              │
│  - Dynamically executes steps via importlib                         │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         pipeline/*.yml                              │
│                                                                     │
│ 10-init.yml              Workspace initialization                   │
│ 15-restore.yml           Restore published CDM dataset              │
│ 20-ingest-*.yml          Raw dataset ingestion                      │
│ 25-scalpel-*.yml         Operator correction workflows              │
│ 30-refine.yml            Automated enrichment pipeline              │
│ 35-report-*.yml          Dataset telemetry & validation             │
│ 40-package.yml           Package CDM as JSONL                       │
│ 45-publish.yml           Publish packaged dataset                   │
│ 5x-prepare-*.yml         Training dataset projections               │
│ 6x-train-*.yml           Model training workflows                   │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           steps/*.py                                │
│                                                                     │
│  - Each pipeline stage is an independent run(config) module         │
│  - All processing revolves around the Canonical Data Model (CDM)    │
│  - Ingest and Restore populate the same CDM workspace               │
│  - Scalpel performs targeted operator corrections                   │
│  - Refine stages are designed to be idempotent                      │
│  - Reports provide read-only telemetry and structural validation    │
│  - Package and Publish create distributable datasets                │
│  - Prepare generates task-specific training projections             │
│  - Train consumes projections without modifying the CDM             │
└─────────────────────────────────────────────────────────────────────┘
```

## Configuration Schema

### Project Metadata

```yaml
project:
    name: "LilaKosha"
    mark: "MK1"
    generation: "G1"
    model_variant: "general" | "unbound"
```

### Pipeline Infrastructure Configuration

Every pipeline is entirely configuration-driven. A pipeline declares four independent concerns:

* **Volumes** — Physical storage locations for datasets, CDM records, models, and exports.
* **Services** — Available inference backends (local or remote) that may be used during execution.
* **Bindings** — Maps individual pipeline stages to a specific inference service and execution policy.
* **Parameters** — Runtime values that customize a particular execution without changing pipeline code.

```yaml
project:
    name: "LilaKosha"
    mark: "MK1"
    generation: "G1"

volumes:
    raw: "${LILAKOSHA_VOLUME_RAW}"
    processed: "${LILAKOSHA_VOLUME_PROCESSED}"
    models: "${LILAKOSHA_VOLUME_MODELS}"
    exports: "${LILAKOSHA_VOLUME_EXPORTS}"

services:
    local:
        provider: openai-compatible
        base_url: "${LILAKOSHA_SERVICE_LOCAL}"
        api_key: dummy
        model: local

    openrouter:
        provider: openai-compatible
        base_url: https://openrouter.ai/api/v1
        api_key: "${OPENROUTER_API_KEY}"
        model: "nvidia/nemotron-3-ultra-550b-a55b"

    kilo:
        provider: openai-compatible
        base_url: https://api.kilo.ai/api/gateway
        api_key: "${KILO_API_KEY}"
        model: "nvidia/nemotron-3-ultra-550b-a55b"

bindings:
    refine-characters:
        service: kilo
        temperature: 0.1
        max_tokens: 4096
        execution:
            requests_per_minute: 20

    refine-grammar:
        service: local
        temperature: 0.0
        max_tokens: 2048
        execution:
            requests_per_minute: 20

parameters:
    start_uuid: null
    stop_uuid: null
```

This separation allows a single pipeline definition to run unchanged across different environments. Operators can switch between local inference, cloud providers, or self-hosted gateways simply by changing service bindings rather than modifying pipeline logic. Likewise, execution policies such as rate limiting, model selection, and generation parameters remain configuration rather than code, making pipelines portable, reproducible, and easy to adapt to new infrastructure.

### Storage Schema

```
{LILAKOSHA_VOLUME_RAW}/
└──
    └── (raw source datasets placed here)

{LILAKOSHA_VOLUME_PROCESSED}/
├── cdm/
│   ├── mapping.jsonl              (Global Content-Addressed Identity Ledger)
│   └── records/
│       └── [UUIDv7].json          (Canonical CDM Session Records)
└── dataset/
    └── LilaKosha-dataset-*.jsonl  (Packaged portable CDM datasets)

{LILAKOSHA_VOLUME_MODELS}/
├── google/
│   └── gemma-4-12b-it/
├── OpenYourMind/
│   └── gemma-4-12b-it-abliterated-uncensored/
└── checkpoints/
    ├── general/
    └── unbound/

{LILAKOSHA_VOLUME_EXPORTS}/
└── gguf_builds/
    ├── general/
    └── unbound/
```

### Training Parameters

```yaml
training_params:
    base_model_path: "google/gemma-4-12b-it" | "OpenYourMind/gemma-4-12b-it-abliterated-uncensored"
    context_window: 4048
    quantization: "4-bit"
    crpo_lambdas:
        novelty: 0.5 | 1.0
        surprise: 0.5 | 1.0
        quality: 1.0
```

## Data Lineage & Mapping Strategy

To ensure strict processing invariance and decouple system lookups from varying third-party platform formats, the pipeline enforces a centralized transaction-log registry layout within `{LILAKOSHA_VOLUME_PROCESSED}/cdm/mapping.jsonl`.

### The Global Ledger Schema

Every record tracked by the ingestion ecosystem must resolve its local footprint into a single, standardized metadata JSON row matching this structural protocol:

```json
{
  "source": "string (e.g., 'pippa', 'gutenberg')",
  "native_id": "string (Strict SHA-256 content-addressable signature)",
  "uuid": "string (Sortable UUIDv7 tracking string acting as filename)",
  "meta": {
    "nested_source_specific_key_1": "value",
    "nested_source_specific_key_2": "value"
  }
}
```

### Architectural Rules for Ingestion Mapping

1. **Pure Content Addressability:** The `native_id` field must look like a pure cryptographic digest. It is calculated by generating a deterministic SHA-256 fingerprint from the sorted, standardized key-value elements of the raw row record.
2. **Metadata Isolation:** Source-specific indices (such as PIPPA's `bot_id` and `submission_timestamp`, or Gutenberg's `gutenberg_id`) cannot sit at the ledger root. They must be nested within an optional dictionary envelope under the top-level `meta` key.
3. **Cache Memory Stability:** The internal `LedgerIndex` runtime maps lookups using an explicit `Tuple[str, str]` key format (`(source, native_id)`) bound exclusively to a `str` value representing the calculated UUIDv7 tracking token. This prevents source-specific metadata dictionaries from leaking into structural runtime caches.

## Step Interface

All pipeline steps implement a consistent, automated execution interface:

```python
from typing import Any

def run(config: dict[str, Any]) -> None:
    """
    Step implementation receives the fully interpolated config dictionary.
    Returns None; raises exceptions explicitly on execution blockers.
    """
```

### Standard Execution Pipeline

1. **`init`** – Infrastructure staging. Creates the workspace layout, verifies configured storage volumes, and validates the execution environment before any pipeline work begins.
2. **`restore`** – Reconstructs the canonical CDM workspace from a previously packaged or published dataset. Recreates the identity ledger and individual UUIDv7 record files, allowing downstream refinement, reporting, and training to resume without access to the original raw source dataset.
3. **`ingest-*`** – Imports supported third-party datasets into the Canonical Data Model (CDM). Each source record is normalized, assigned a deterministic content identity, registered within the global identity ledger, and written as an independent UUIDv7 session record.
4. **`scalpel-*`** – Implements targeted operator correction workflows. Evaluates explicit runtime boundary parameters (for example `start_uuid` and `stop_uuid`) to selectively clear or repair specific refinements without affecting adjacent records or unrelated annotations.
5. **`refine-*`** – Multi-stage enrichment engine performing structural analysis, metadata extraction, narrative annotation, grammar normalization, safety classification, recap generation, and other automated augmentation tasks. Refinement stages are designed to be idempotent, skipping records whose corresponding annotations have already been verified.
6. **`report-*`** – Read-only telemetry and validation passes that inspect dataset health, verify schema integrity, measure refinement coverage, compute statistical distributions, and identify anomalous or incomplete records requiring operator attention.
7. **`package`** – Traverses the canonical CDM workspace, validates every session record against the CDM schema, and exports the corpus as a portable JSONL dataset suitable for archival, publication, interchange, and future restoration.
8. **`publish-*`** – Publishes packaged datasets to external repositories (such as Hugging Face), creating reproducible, versioned dataset releases that can later be restored into a fresh CDM workspace.
9. **`prepare-*`** – Projects the canonical CDM into one or more task-specific training datasets. Different preparation pipelines may generate instruction-tuning examples, recap-augmented conversations, or other specialized training formats without modifying the underlying CDM records.
10. **`train-*`** – Initializes the model training environment, loads the selected foundation model and training projection, configures QLoRA or related fine-tuning strategies, and produces task-specific adapter checkpoints.
11. **`bake`** – Merges trained adapter weights back into the foundation model, performs optional quantization, and exports deployable artifacts such as GGUF distributions optimized for local inference.

## Variant Isolation

The General and Unbound channels are decoupled completely at the filesystem and mathematical optimization boundaries:

* **FS Layout Separation:** Build tracks map to clean isolated distribution targets (`gguf_builds/general` vs `gguf_builds/unbound`).
* **Alignment Tuning:** Variations utilize disparate base paths (standard vanilla parameters vs. abliterated residual stream matrices) to alter base instruction behaviors.
* **CRPO Directives:** Creative Preference Optimization (CRPO) configurations toggle active lambda forces (General variants use conservative settings; Unbound loops extend parameters to max ranges for unrestricted creative flow).
* **Ledger Invariance:** Raw datasets and standardized CDM rows remain invariant. Variant forks occur down the pipeline stream, allowing the identical processed canvas file to drive both alignment variants.
