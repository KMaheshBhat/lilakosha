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

```text
                            [Published Dataset]
                                    │
                                15-restore
                                    │
                                    ▼
[Start Workspace] ──> 10-init ──> 20-ingest-* ────────────┐
                                    ▲                     │
[Raw Datasets] ─────────────────────┘                     ▼
                                                     Canonical CDM
                                                       Records
                                                          │
                         ┌────────────────────────────────┼─────────────────────────────────┐
                         │                                │                                 │
                         ▼                                ▼                                 ▼
                    25-scalpel-*                      30-refine                       35-report-*
                  (manual operator)                     ▲ │                           (telemetry)
                         │                              │ │
                         └──────────────────────────────┘ │
                                                          │
                                                          ▼
                                                    40-package
                                                          │
                                                          ▼
                                                    Dataset JSONL
                                                          │
                                                    45-publish
                                                          │
                                                          ▼
                                                  [Published Dataset]
                                                          │
                                                          ▼
                                                   5x-prepare-*
                                               (training projections)
                                                          │
                                                          ▼
                                                     6x-train-*
```

The pipeline is organized around a **Canonical Data Model (CDM)** that serves as the authoritative representation of every conversational session. All ingestion, refinement, inspection, packaging, and training preparation operate on this common representation rather than directly on raw datasets.

1. **Initialize (10-init):** Create the working directory structure, initialize the CDM workspace, and prepare the environment for subsequent processing.
2. **Acquire the Dataset:** Populate the CDM workspace by either ingesting supported raw datasets (`20-ingest-*`) or restoring a previously published dataset (`15-restore`). Both paths produce the identical structured canonical CDM representation. (The content of course depends on what was ingested or restored - restored records could have refinements already run on them).
3. **Curate the Corpus:** Apply automated refinement passes (`30-refine`) to enrich each session with structural metadata such as recaps, narrative signals, and quality annotations. Operator-driven scalpel workflows (`25-scalpel-*`) may be executed selectively to correct or improve specific records, while reporting pipelines (`35-report-*`) provide health and quality telemetry throughout the process.
4. **Package & Publish:** Export the curated CDM corpus into a portable JSONL dataset (`40-package`) suitable for archival, sharing, and reproducible distribution. The packaged dataset can then be published (`45-publish`) and later restored into a fresh CDM workspace without requiring access to the original raw source material.
5. **Prepare Training Projections:** Generate one or more task-specific training datasets (`5x-prepare-*`) from the canonical CDM. These projections transform the rich structured records into instruction-tuning examples, recap-augmented conversations, or other specialized training formats while leaving the underlying CDM unchanged.
6. **Train the Model:** Fine-tune the target foundation model (`6x-train-*`) using the prepared training projections. Multiple training variants can be produced from the same curated CDM corpus, including both the General and Unbound model families.
7. **Bake & Export:** Merge the resulting LoRA adapters into the base model weights and export optimized deployment artifacts (such as GGUF block quantizations) for efficient local inference.

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

* **Alignment:** Leverages an **abliterated residual weights stream**, systematically neutralizing the mathematical tensor paths that trigger model refusals.
* **Target Focus:** Built specifically for **high-stakes fictional conflict**, dramatic tension, and interactive roleplay simulations where characters must stay true to form without breaking immersion or lecturing the user.
* **Creative Preference Optimization (CRPO):** By running unbound, the fine-tune rewards narrative dimensions like novelty, surprise, tension, and prose diversity without triggering artificial alignment bottlenecks.

## Repository Documentation Index

For active machine control and execution instructions, see [doc/operator.md](doc/operator.md).

For detailed structural paradigms and engineering design choices, see [doc/design.md](doc/design.md).

For transactional schema constraints and payload structural layers, see [doc/cdm.md](doc/cdm.md).

---

*This framework is an open-weights engineering initiative intended exclusively for fictional writing, creative exploration, and interactive entertainment architectures.*
