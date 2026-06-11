# LilaKosha-Flow-MK1: High-Level Design

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        main.py (Orchestrator)                     │
│  - Discovers configs (*.yml) in config/ directory               │
│  - Loads YAML configuration with env var interpolation            │
│  - Executes steps dynamically via importlib                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         steps/*.py                              │
│  - Each step is a self-contained module with run(config)          │
│  - Steps can be chained: init → prepare → train → bake            │
│  - init runs first for infrastructure setup                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      config/*.yml                               │
│  - 10-init.yml (Infrastructure staging)                         │
│  - 30-prepare.yml (Recap-augmented data processing)           │
│  - 60-train-and-bake-lilakosha-1g-12b-g.yml (General variant)  │
│  - 61-train-and-bake-lilakosha-1g-12b-u.yml (Unbound variant)  │
│  - Environment variables: LILAKOSHA_VOLUME_*                    │
│  - Services: LILAKOSHA_SERVICE_*                                │
└─────────────────────────────────────────────────────────────────┘
```

## Configuration Schema

### Project Metadata
```yaml
project:
    name: "LilaKosha"
    mark: "MK1"
    generation: "G1"
    model_variant: "general" | "unbound" | "infrastructure" | "teacher-pass"
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
    teacher: "${LILAKOSHA_SERVICE_TEACHER}"     # Generates Recaps/Highlights
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
2. **`prepare`** – Reads raw data; connects to teacher service; generates recaps/highlights
3. **`train`** – Loads model; applies QLoRA; saves adapters to checkpoints
4. **`bake`** – Merges adapters; exports to GGUF format

## Variant Isolation

The General and Unbound variants are isolated at the filesystem level:
- Separate GGUF export directories (`gguf_builds/general` vs `gguf_builds/unbound`)
- Different CRPO lambda weights (General: 0.5, Unbound: 1.0)
- Different base model paths (vanilla vs abliterated)
- Raw data is unified in a single landing zone; prepare step introspects and forks automatically
- Processed chunks are variant-agnostic output
