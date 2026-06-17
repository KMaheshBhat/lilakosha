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
