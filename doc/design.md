# LilaKosha-Flow-MK1: High-Level Design

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        main.py (Orchestrator)                   │
│  - Discovers steps and configs                                  │
│  - Loads YAML configuration with env var interpolation          │
│  - Executes steps dynamically via importlib                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         steps/*.py                              │
│  - Each step is a self-contained module with run(config)        │
│  - Steps can be chained: prepare → train → bake                 │
│  - stage is config-less, runs first for infrastructure setup    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      config/*.yaml                              │
│  - lilakosha-g1-12b-g.yaml (General variant)                    │
│  - lilakosha-g1-12b-u.yaml (Unbound variant)                    │
│  - Environment variables: LILAKOSHA_BASE_*                      │
└─────────────────────────────────────────────────────────────────┘
```

## Configuration Schema

### Project Metadata
```yaml
project:
    name: "LilaKosha"
    mark: "MK1"
    generation: "G1"
    model_variant: "general" | "unbound"
    purpose: "Variant-specific description"
```

### Infrastructure Paths
```yaml
infrastructure:
    base_data_dir: "${LILAKOSHA_BASE_DATA}"
    base_process_dir: "${LILAKOSHA_BASE_PROCESS_DIR}"
    base_model_base_dir: "${LILAKOSHA_BASE_MODEL_BASE_DIR}"
    base_export_dir: "${LILAKOSHA_BASE_EXPORT_DIR}"
    inference_service: "http://localhost:8033"
```

### Storage Schema
```yaml
storage_schema:
    raw_data:
        path: "${LILAKOSHA_BASE_DATA}/raw/{variant}"
        purpose: "Storage for datasets"
    processed_data:
        path: "${LILAKOSHA_BASE_PROCESS_DIR}/{variant}_chunks"
        purpose: "Output for recap-augmented chunks"
        structure: "JSONL with [Summary] blocks"
    model_assets:
        path: "${LILAKOSHA_BASE_MODEL_BASE_DIR}"
        sub_paths:
            base: "google/gemma-4-12b-it" | "OpenYourMind/..."
            exports: "gguf_builds/{variant}"
        lora_rank: 128
        lora_alpha: 256
```

### Training Parameters
```yaml
training_params:
    context_window: 4096
    quantization: "4-bit"
    crpo_lambdas:
        novelty: 0.5 | 1.0
        diversity: 0.5 | 1.0
        surprise: 0.5 | 1.0
        quality: 1.0
```

## Directory Structure (Created by `stage`)

```
{LILAKOSHA_BASE_DATA}/
├── raw/
│   ├── general/          # SFW datasets
│   └── unbound/          # PIPPA, MUCE, unrestricted RP logs
{LILAKOSHA_BASE_PROCESS_DIR}/
├── general_chunks/       # Processed SFW data
└── unbound_chunks/       # Processed unrestricted data
{LILAKOSHA_BASE_MODEL_BASE_DIR}/
├── google/gemma-4-12b-it/
├── OpenYourMind/gemma-4-12b-it-abliterated-uncensored/
└── checkpoints/
{LILAKOSHA_BASE_EXPORT_DIR}/
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

1. **`stage`** – Config-less bootstrap; creates directories; prints acquisition instructions
2. **`prepare`** – Reads raw data; connects to inference service; generates recaps
3. **`train`** – Loads model; applies QLoRA; saves adapters to checkpoints
4. **`bake`** – Merges adapters; exports to GGUF format

## Variant Isolation

The General and Unbound variants are isolated at the filesystem level:
- Separate raw data directories
- Separate processed chunk directories
- Separate GGUF export directories
- Different CRPO lambda weights (General: 0.5, Unbound: 1.0)
- Different base model paths (vanilla vs abliterated)
