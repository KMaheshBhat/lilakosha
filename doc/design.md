# LilaKosha-Flow-MK1: High-Level Design

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        main.py (Orchestrator)                   │
│  - Discovers configs (*.yml) in pipeline/ directory             │
│  - Loads YAML configuration with env var interpolation          │
│  - Validates LILAKOSHA_VOLUME_* and LILAKOSHA_SERVICE_* vars    │
│  - Executes steps dynamically via importlib                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      pipeline/*.yml                             │
│  - 10-init.yml (Infrastructure staging)                         │
│  - 20-ingest.yml (PIPPA dataset ingestion)                      │
│  - 25-scalpel-*.yml (Removes refinements)                       │
│  - 30-refine.yml (Combined refinement pipeline)                 │
│  - 60-train-general.yml (General variant)                       │
│  - 61-train-unbound.yml (Unbound variant)                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         steps/*.py                              │
│  - Each step is a self-contained module with run(config)        │
│  - Steps can be chained: init → ingest-[source]                 │
│    → scalpel-[aspect] → refine-[aspect] → train → bake          │
│  - scalpel-* clears state; refine-* is idempotent (skips done)  │
│  - init runs first for infrastructure setup                     │
└─────────────────────────────────────────────────────────────────┘
```

## Configuration Schema

### Project Metadata
```yaml
project:
    name: "LilaKosha"
    mark: "MK1"
    generation: "G1"
    model_variant: "general" | "unbound" | "infrastructure"
```

### Infrastructure Paths
```yaml
volumes:
    raw: "${LILAKOSHA_VOLUME_RAW}"      # Unified landing zone for raw datasets
    processed: "${LILAKOSHA_VOLUME_PROCESSED}" # Recap-augmented output chunks
    models: "${LILAKOSHA_VOLUME_MODELS}"     # Model storage (base + checkpoints)
    exports: "${LILAKOSHA_VOLUME_EXPORTS}"    # GGUF builds output

services:
    inspector: "${LILAKOSHA_SERVICE_INSPECTOR}" # Tags samples (SFW vs Mature)
    grammar: "${LILAKOSHA_SERVICE_GRAMMAR}"       # Converts person and tense
    summarizer: "${LILAKOSHA_SERVICE_SUMMARIZER}" # Generates recaps/highlights
```

### Storage Schema
```
# Directory structure created by init step:
# {LILAKOSHA_VOLUME_RAW}/
#   └── (raw datasets placed here - unified landing zone)
# {LILAKOSHA_VOLUME_PROCESSED}/
#   └── (recap-augmented chunks output)
# {LILAKOSHA_VOLUME_MODELS}/
#   ├── google/gemma-4-12b-it/
#   ├── OpenYourMind/gemma-4-12b-it-abliterated-uncensored/
#   └── checkpoints/
# {LILAKOSHA_VOLUME_EXPORTS}/
#   └── gguf_builds/
#       ├── general/
#       └── unbound/
```

### Training Parameters
```yaml
training_params:
    base_model_path: "google/gemma-4-12b-it" | "OpenYourMind/..."
    context_window: 4096
    quantization: "4-bit"
    crpo_lambdas:
        novelty: 0.5 | 1.0
        surprise: 0.5 | 1.0
        quality: 1.0
```

## Directory Structure (Created by `init`)

```
{LILAKOSHA_VOLUME_RAW}/
└── (unified landing zone for raw datasets)

{LILAKOSHA_VOLUME_PROCESSED}/
└── (recap-augmented chunks output)

{LILAKOSHA_VOLUME_MODELS}/
├── google/gemma-4-12b-it/
├── OpenYourMind/gemma-4-12b-it-abliterated-uncensored/
└── checkpoints/

{LILAKOSHA_VOLUME_EXPORTS}/
└── gguf_builds/
    ├── general/
    └── unbound/
```

## Step Interface

All pipeline steps follow a consistent interface:

```python
def run(config: dict[str, Any] | None = None) -> None:
    """
    Step implementation receives the full config dictionary.
    Returns None; raises exceptions on failure.
    """
```

### Step Execution Flow

1. **`init`** – Infrastructure staging; creates directories; prints acquisition instructions
2. **`ingest-pippa`** – PIPPA dataset ingestion and transformation
3. **`scalpel-*`** – Removes refinements (idempotent: clears state for reprocessing)
4. **`refine-*`** – Character and content refinement (idempotent: skips already-processed data)
5. **`train`** – Loads model; applies QLoRA; saves adapters to checkpoints
6. **`bake`** – Merges adapters; exports to GGUF format

### Data Model

The `ingest-pippa` and `refine-*` steps transform raw datasets into the **LilaKosha Common Data Model (CDM)**, a unified schema for recap-augmented chunks. See [cdm.md](cdm.md) for the complete entity specification and JSON record format.

## Variant Isolation

The General and Unbound variants are isolated at the filesystem level:
- Separate GGUF export directories (`gguf_builds/general` vs `gguf_builds/unbound`)
- Different CRPO lambda weights (General: 0.5, Unbound: 1.0)
- Different base model paths (vanilla vs abliterated)
- Raw data is unified in a single landing zone; ingest-pippa step processes and forks automatically
- Processed chunks are variant-agnostic output
