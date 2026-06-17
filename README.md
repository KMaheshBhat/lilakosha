# Project LilaKosha: The Treasury of Divine Play

**Project LilaKosha** (लीलाकोश) is a high-utility, open-weights framework dedicated to developing a fine-tuned variant of the **Gemma 4 12B** architecture optimized specifically for **immersive creative writing, complex narrative generation, and interactive roleplay**.

The name combines **Lila** (Play/Imaginative Sport) and **Kosha** (Treasury/Repository), representing an advanced, orchestration-aware platform for uninhibited collaborative storytelling.

## Core Pillars

* **Unbound Creative Freedom:** Incorporates an **abliterated residual stream** base to systematically bypass restrictive refusal vectors, allowing the model to handle high-stakes drama, dark themes, and complex villains without breaking narrative character or lecturing the user.
* **Orchestration-Aware Pipeline:** A unique training methodology that "bakes in" the mechanics of long-form narrative consistency by utilizing **Recap-Augmented Chunking** to handle continuous, stateful interaction tracks within tight consumer hardware limits.
* **Dual-Flavor Deployment:** Simultaneous release of an **Unbound** variant for maximum narrative flexibility and a **General** variant for mainstream collaborative writing applications.
* **Hardware Optimization:** Precision-tuned for consumer-grade hardware (specifically **12 GB VRAM GPUs**) using the memory-efficient **Unsloth** training engine.

## Technical Specifications

* **Base Model:** [Gemma 4 12B Unified](https://huggingface.co/google/gemma-4-12B) (~11.95B dense parameters).
* **Architecture:** Encoder-free, multimodal decoder-only transformer with native support for text, image, and audio tracks.
* **Context Window:** Supports up to **256K tokens** for inference deployment.
* **Training Method:** **QLoRA (Quantized Low-Rank Adaptation)** via Unsloth to compress the memory footprint during training to **~7.5 GB**, leaving a comfortable buffer for training sequences up to **4,096 tokens**.

## The LilaKosha Pipeline Architecture

```
[Raw Datasets] ──> 10-init ──> 20-ingest ──> 30-refine ──> 35-report-records ──> 6X-train
                                  ▲              │
                                  │   [Scalpel]  │ (If anomalies found, 
                                  └─ 25-scalpel ─┘  executed manually by the operator)

```

1. **Base Selection:** Start with either the vanilla `gemma-4-12B-it` or the `gemma-4-12B-it-abliterated-uncensored` base foundation.
2. **Processing (Recap-Augmentation):** Leverage localized inference services to extract structural **Session Recaps and Key Highlights** from long-form datasets, training the model to treat summaries as stateful "truth anchors" for long-term consistency.
3. **Training (The QLoRA Phase):** Attach target LoRA adapters to the model's attention and MLP projections to lock in specific conversational styles and roleplay mechanics.
4. **The "Bake" (Weight Fusion):** Mathematically inject the trained adapter weights directly back into the native 16-bit structure to generate a **monolithic distribution file**.
5. **Export (GGUF):** Convert the merged weights into specialized GGUF block quants (e.g., **Q4_K_M**) optimized for low-latency local deployment.

## Getting Started

This repository contains the full workflow orchestration, configuration maps, and execution steps required to initialize and run the **LilaKosha** processing and training environment inside **WSL2**.

### Requirements

* **Hardware:** NVIDIA RTX GPU with a minimum of **12 GB VRAM** (e.g., RTX 4070, RTX 3060 12GB).
* **Software:** WSL2 (Ubuntu), Python 3.10+, and the **Unsloth** library suite.
* **Data Foundations:** Access to raw roleplay logs or creative writing datasets—such as **PIPPA** (Character.AI logs), historical roleplay forums, or the **200,000-sample MUCE dataset**.
* **Services:** A localized inference endpoint (specifically **`llama-server`** or **`litert-lm serve`**) hosting an inspection model to execute the synthetic summarization, safety classification, and grammar normalization passes.

### Installation

Initialize the workspace tracking system using [uv](https://docs.astral.sh/uv/), the ultra-fast Python package manager:

```bash
uv init
uv sync
```

### Environment Setup

Establish the required volume parameters before executing pipeline runs. Copy `example.env` to configure your persistent paths:

```bash
cp example.env .env
source .env
```

Your `.env` profile exposes the underlying storage vectors:

```bash
export LILAKOSHA_VOLUME_RAW=/tmp/lk-dry/raw
export LILAKOSHA_VOLUME_PROCESSED=/tmp/lk-dry/processed
export LILAKOSHA_VOLUME_MODELS=/tmp/lk-dry/models
export LILAKOSHA_VOLUME_EXPORTS=/tmp/lk-dry/exports
```

## Operator Instructions

The LilaKosha execution engine runs on top of an automated wrapper shell, accepting specific pipeline manifests along with dynamic CLI runtime parameters via trailing configuration flags (`--key value`).

```bash
./run.sh pipeline/<pipeline-config>.yml [options]
```

### 1. Bootstrap Workspace Infrastructure

```bash
./run.sh pipeline/10-init.yml
```

Initializes local storage volumes, builds out processing directories, and stages the workspace architecture.

### 2. Ingest and Normalize Datasets

```bash
./run.sh pipeline/20-ingest.yml
```

Streams, extracts, and parses incoming interaction structures, mapping raw logs safely into deterministic, standalone `{UUIDv7}.json` files inside the unified **Common Data Model (CDM)** ledger.

### 3. Run Enrichment & Refinement (Idempotent Sweep)

```bash
./run.sh pipeline/30-refine.yml
```

Executes character synthesis, narrative categorization, safety-dial assessment, and grammar normalization via the local inference layer. This step runs under strict idempotency guardrails, automatically skipping files that already contain verified enrichment markers.

### 4. Execute Data Telemetry & Validation Reports

```bash
./run.sh pipeline/35-report-records.yml
```

Compiles an end-to-end audit of your processed ledger. It runs a structural data-health check across your Pydantic boundaries and outputs an aggregate distribution map covering primary genre mixes, safety dial balances, and a frequency registry of unique thematic tags.

### 5. Target Anomalies with the Scalpel (Surgical Rollbacks)

The framework includes specialized `25-scalpel-*` interventions designed to clear target mutations and cleanly rollback records to their raw state. These modules support **dynamic runtime boundary parameters** (`--start_uuid` and `--stop_uuid`) to isolate single records or specific lexical spans without full-set re-evaluation.

* **Isolate and Reset a Single Broken Record:**
```bash
./run.sh pipeline/25-scalpel-characters.yml --start_uuid 019ed224-2866-7db3-9648-196a3451d42a --stop_uuid 019ed224-2866-7db3-9648-196a3451d42a
./run.sh pipeline/25-scalpel-grammar.yml    --start_uuid 019ed224-2866-7db3-9648-196a3451d42a --stop_uuid 019ed224-2866-7db3-9648-196a3451d42a
```


* **Execute a Bounded Range Sweep:**
```bash
# Purge safety metrics starting from a specific UUID forward
./run.sh pipeline/25-scalpel-safety-dials.yml --start_uuid 019ed0a1-3d92-7123-a70f-72d1e9093b01
```
Once fixes are applied or prompt structures are updated, re-trigger the refinement suite (`./run.sh pipeline/30-refine.yml`) to catch up the cleared records.

### 6. Execute SFT Model Training & Export

```bash
# Target, merge, and bake the General Variant GGUF
./run.sh pipeline/60-train-general.yml

# Target, merge, and bake the Unbound Variant GGUF
./run.sh pipeline/61-train-unbound.yml

```
## Complete Pipeline Component Directory

* `pipeline/10-init.yml` – Workspace staging, directory allocation, and multi-channel channel map verification.
* `pipeline/20-ingest.yml` – Multi-source dataset translation into standardized CDM schema records.
* `pipeline/25-scalpel-characters.yml` – Purges synthesized identities and local deep lore records.
* `pipeline/25-scalpel-safety-dials.yml` – Resets safety classification axes and contextual metric tracks.
* `pipeline/25-scalpel-genre-theme.yml` – Clears primary genre tags and thematic annotations.
* `pipeline/25-scalpel-grammar.yml` – Rolls back localized grammar/prose revisions to their raw historical baseline.
* `pipeline/30-refine.yml` – Multi-model enrichment engine running context extraction and alignment tasks.
* `pipeline/35-report-records.yml` – Combined telemetry pipeline running data-health checks and corpus distribution analysis.
* `pipeline/60-train-general.yml` – General SFT training, 16-bit weight consolidation, and GGUF block quantification.
* `pipeline/61-train-unbound.yml` – Abliterated-base SFT creative writing training, fusion, and GGUF quantization.

For detailed engineering paradigms, see [doc/design.md](doc/design.md).

For the transactional schema layouts, see [doc/cdm.md](doc/cdm.md).

## Project Deliverables Matrix

| Component | Identifier | Technical Profile & Delivery Format |
| --- | --- | --- |
| **The Pipeline** | `LilaKosha-Flow-MK1` | Complete architectural blueprint: ingestion, CDM management, scalpel suites, and training orchestration. |
| **General Model** | `LilaKosha-G1-12B-G` | RPG-focused creative engine built over the stock vanilla Gemma 4 base. Retains institutional safety filters while embedding state-aware prose. Distributed as GGUF blocks. |
| **Unbound Model** | `LilaKosha-G1-12B-U` | Immersion-focused narrative engine built over the abliterated residual base for complete writing freedom. Enhanced with Creative Preference Optimization (CRPO) attributes. Distributed as GGUF blocks. |

### Variant Breakdown

#### 1. LilaKosha-G1-12B-G ("General" Variant)

* **Alignment:** Retains the rigorous **institutional safety, ethics, and compliance tuning** engineered into the core Google DeepMind backbone, including robust protections against harassment and dangerous data generation.
* **Target Focus:** Geared toward **mainstream authors**, professional co-writing platforms, and commercial tools requiring corporate safety standard compliance.
* **Core Benefit:** Merges standard safety boundaries with LilaKosha’s structured **"RPG Grammar"** and state-awareness layers, outperforming standard vanilla instructions in structural narrative coherence.

#### 2. LilaKosha-G1-12B-U ("Unbound" Variant)

* **Alignment:** Leverages an **abliterated residual weights stream**, systematically neutralising the mathematical tensor paths that trigger model refusals.
* **Target Focus:** Built specifically for **high-stakes fictional conflict**, dramatic tension, and interactive roleplay simulations where characters must stay true to form without breaking immersion or lecturing the user.
* **Creative Preference Optimization (CRPO):** By running unbound, the fine-tune rewards narrative dimensions like novelty, surprise, tension, and prose diversity without triggering artificial alignment bottlenecks.

## Architectural Agnosticism & Future Considerations

While the primary release of **LilaKosha** targets the **Gemma 4 12B Unified** architecture, the data framework and orchestration layers are built completely cross-model compatible within the sub-12B landscape. By focusing exclusively on **unified, encoder-free models** (where text, image, and audio parse natively into the main transformer backbone), the system entirely sidesteps the need to co-tune independent frozen encoders.

The modular structure allows operators to easily attach alternative execution steps as your requirements scale up:

* **`acquire`** – Verified dataset and model source retrieval with checksum verification.
* **`validate`** – Pre-flight systems scanning for hardware configuration anomalies and memory limits.
* **`inspect`** – Structural analytical analysis of text weights and sequence depth distribution prior to ingestion passes.
* **`export`** – Compilation vectors supporting deployment targets beyond GGUF (e.g., Hugging Face `safetensors`, TensorRT-LLM, or ONNX runtimes).

---

*This framework is an open-weights engineering initiative intended exclusively for fictional writing, creative exploration, and interactive entertainment architectures.*
