# LilaKosha-Flow-MK1: High-Level Design

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                        main.py (Orchestrator)                    │
│  - Discovers configs (*.yml) in pipeline/ directory              │
│  - Loads YAML configuration with env var interpolation           │
│  - Validates LILAKOSHA_VOLUME_* environment configurations       │
│  - Executes steps dynamically via importlib                      │
└──────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                        pipeline/*.yml                            │
│  - 10-init.yml (Infrastructure staging)                          │
│  - 20-ingest.yml (Dataset ingestion & normalization)             │
│  - 25-scalpel-*.yml (Targeted atomic rollbacks)                  │
│  - 30-refine.yml (Multi-model enrichment pipeline)               │
│  - 35-report-records.yml (Data validation & stats reporting)     │
│  - 60-train-general.yml (General variant SFT & baking)           │
│  - 61-train-unbound.yml (Unbound variant SFT & baking)           │
└──────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                         steps/*.py                               │
│  - Each step is a self-contained module with run(config)         │
│  - Execution pipeline: init → ingest → scalpel → refine          │
│                        → report-records → train → bake           │
│  - scalpel-* clears state; refine-* is strictly idempotent       │
│  - report-records runs structural validation and taxonomy audits │
└──────────────────────────────────────────────────────────────────┘

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

### Infrastructure Paths

```yaml
volumes:
    raw: "${LILAKOSHA_VOLUME_RAW}"             # Unified landing zone for raw datasets
    processed: "${LILAKOSHA_VOLUME_PROCESSED}" # CDM records and canvas outputs
    models: "${LILAKOSHA_VOLUME_MODELS}"       # Model storage (base + checkpoints)
    exports: "${LILAKOSHA_VOLUME_EXPORTS}"     # GGUF builds output

services:
    inspector: "${LILAKOSHA_SERVICE_INSPECTOR}" # Evaluates safety dials and classifications
    grammar: "${LILAKOSHA_SERVICE_GRAMMAR}"     # Standardizes person, tense, and prose
    summarizer: "${LILAKOSHA_SERVICE_SUMMARIZER}" # Generates entity details and recaps
```

### Storage Schema

```
# Directory structure instantiated by init step:
# {LILAKOSHA_VOLUME_RAW}/
#    └── (raw datasets placed here - unified landing zone)
# {LILAKOSHA_VOLUME_PROCESSED}/
#    └── cdm/
#        └── records/
#            └── [UUIDv7].json (Standardized Canvas CDM Files)
# {LILAKOSHA_VOLUME_MODELS}/
#    ├── google/gemma-4-12b-it/
#    ├── OpenYourMind/gemma-4-12b-it-abliterated-uncensored/
#    └── checkpoints/
# {LILAKOSHA_VOLUME_EXPORTS}/
#    └── gguf_builds/
#        ├── general/
#        └── unbound/
```

### Training Parameters

```yaml
training_params:
    base_model_path: "google/gemma-4-12b-it" | "OpenYourMind/gemma-4-12b-it-abliterated-uncensored"
    context_window: 4096
    quantization: "4-bit"
    crpo_lambdas:
        novelty: 0.5 | 1.0
        surprise: 0.5 | 1.0
        quality: 1.0
```

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

1. **`init`** – Infrastructure staging: handles directories allocation, mounts target spaces, and verifies configuration channels.
2. **`ingest-pippa`** – Streams and normalizes third-party log objects (e.g., PIPPA JSONL schemas) cleanly into standalone CDM rows.
3. **`scalpel-*`** – Implements targeted atomic resets. Evaluates explicit runtime boundary parameters (`--start_uuid` / `--stop_uuid`) to isolate and rollback specific data mutations without invalidating adjacent ledger blocks.
4. **`refine-*`** – Multi-model enrichment engine running context extraction and alignment tasks. Executes under strict idempotency guardrails, bypassing files that already contain verified annotation tags.
5. **`report-record-health`** – Telemetry pass verifying canvas consistency, checking schemas against Pydantic models, and printing a surgical failure registry of corrupted files.
6. **`report-record-stats`** – Statistical analysis step building distribution profiles across your primary genres, safety classifications, and narrative thematic tags.
7. **`train`** – Shuts down localized inference servers, initializes the memory-efficient **Unsloth** environment, loads QLoRA parameters, and targets model weights.
8. **`bake`** – Merges low-rank adapters back into raw FP16 weights, extracts quantized blocks, and compiles local GGUF distribution packages.

## Variant Isolation

The General and Unbound channels are decoupled completely at the filesystem and mathematical optimization boundaries:

* **FS Layout Separation:** Build tracks map to clean isolated distribution targets (`gguf_builds/general` vs `gguf_builds/unbound`).
* **Alignment Tuning:** Variations utilize disparate base paths (standard vanilla parameters vs. abliterated residual stream matrices) to alter base instruction behaviors.
* **CRPO Directives:** Creative Preference Optimization (CRPO) configurations toggle active lambda forces (General variants use conservative settings; Unbound loops extend parameters to max ranges for unrestricted creative flow).
* **Ledger Invariance:** Raw datasets and standardized CDM rows remain invariant. Variant forks occur down the pipeline stream, allowing the identical processed canvas file to drive both alignment variants.
