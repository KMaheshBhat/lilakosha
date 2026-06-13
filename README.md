# Project LilaKosha: The Treasury of Divine Play

**Project LilaKosha** (लीलाकोश) is a high-utility, open-weights framework dedicated to developing a fine-tuned version of the **Gemma 4 12B** architecture specifically for **immersive creative writing, complex narrative generation, and interactive roleplay**. 

The name combines **Lila** (Play/Imaginative Sport) and **Kosha** (Treasury/Repository), representing a deep architectural repository for uninhibited collaborative storytelling.

## Core Pillars

*   **Unbound Creative Freedom:** Utilizing an **abliterated base** to bypass restrictive refusal vectors, allowing the model to handle high-stakes drama and complex villains without breaking character.
*   **Orchestration-Aware Pipeline:** A unique training methodology that "bakes in" the dynamics of long-form narrative by using **Recap-Augmented Chunking** to handle the "Continue" use case within hardware limits.
*   **Dual-Flavor Deployment:** Simultaneous release of an **Unbound** variant for maximum flexibility and a **General** variant for mainstream collaborative writing.
*   **Hardware Optimization:** Precision-tuned for consumer-grade hardware (specifically **12 GB VRAM GPUs**) using the **Unsloth** memory-efficient training engine.

## Technical Specifications

*   **Base Model:** [Gemma 4 12B Unified](https://huggingface.co/google/gemma-4-12B) (~11.95B dense parameters).
*   **Architecture:** Encoder-free, multimodal decoder-only transformer with native support for text, image, and audio.
*   **Context Window:** Supports up to **256K tokens** for inference.
*   **Training Method:** **QLoRA (Quantized Low-Rank Adaptation)** via Unsloth to shrink the memory footprint to **~7.5 GB**, leaving a buffer for training sequences up to **4,096 tokens**.

## The LilaKosha Pipeline

1.  **Base Selection:** Start with either the vanilla `gemma-4-12B-it` or the `gemma-4-12B-it-abliterated-uncensored` base.
2.  **Processing (Recap-Augmentation):** Use a teacher model to generate **Session Recaps and Key Highlights** for long-form datasets. This trains the model to treat summaries as "truth anchors" for long-term consistency.
3.  **Training (The QLoRA Phase):** Attach trainable LoRA adapters to the attention and MLP projections to target roleplay and conversational style.
4.  **The "Bake" (Weight Fusion):** Mathematically inject the trained adapter weights back into the native 16-bit structure to create a **monolithic distribution file**.
5.  **Export (GGUF):** Convert the merged model into specialized GGUF block quants (e.g., **Q4_K_M**) for optimized local deployment.

## Getting Started

This repository contains the configuration and scripts required to initialize the **LilaKosha** training environment on **WSL2**.

### Requirements

*   **Hardware:** NVIDIA RTX GPU with at least **12 GB VRAM** (e.g., RTX 4070).
*   **Software:** WSL2 (Ubuntu), Python 3.10+, and the **Unsloth** library.
*   **Data:** Access to high-quality, long-form "raw" roleplay and creative datasets—such as **PIPPA** (Character.AI logs), **roleplay forums**, or the **200,000-sample MUCE dataset**—to serve as the foundation for the "Recap-Augmented" processing stage.
*   **Services:** A localized inference service (specifically **`llama-server`** or **`litert-lm serve`**) hosting a "Teacher" model (e.g., Gemma 4 12B or 31B) to perform the synthetic summarization and "raw" data inspection required to generate **Session Recaps** and **Key Highlights** before training begins.

### Installation

Initialize the project with [uv](https://docs.astral.sh/uv/), the fast Python package manager:

```bash
uv init
uv sync
```

### Environment Setup

Set the required environment variables before running the pipeline:

```bash
export LILAKOSHA_VOLUME_RAW=/tmp/lk-dry/raw
export LILAKOSHA_VOLUME_PROCESSED=/tmp/lk-dry/processed
export LILAKOSHA_VOLUME_MODELS=/tmp/lk-dry/models
export LILAKOSHA_VOLUME_EXPORTS=/tmp/lk-dry/exports
```

For convenience, copy `example.env` to `.env` and source it:

```bash
cp example.env .env
source .env
```

### Operator Instructions

Run the pipeline orchestrator to see available commands:

```bash
uv run main.py
```

**Bootstrap Infrastructure:**
```bash
uv run main.py config/10-init.yml
```
This creates the directory structure for both General and Unbound variants.

**Execute Pipeline Steps:**
```bash
# Stage 1: Data Preparation (Teacher Pass)
uv run main.py config/30-prepare.yml

# Stage 2: Training & Fusion (General variant)
uv run main.py config/60-train-and-bake-lilakosha-1g-12b-g.yml

# Stage 2: Training & Fusion (Unbound variant)
uv run main.py config/61-train-and-bake-lilakosha-1g-12b-u.yml
```

**Available Pipeline Steps:**
- `init` – Bootstrap infrastructure (creates directories, prints acquisition instructions)
- `prepare` – Recap-augmented data processing (Stage 1, Teacher Pass)
- `train` – QLoRA adapter training (Stage 2)
- `bake` – Weight fusion and GGUF export (Final Phase)

**Available Configurations:**
- `config/10-init.yml` – Infrastructure staging
- `config/30-prepare.yml` – Data preparation with teacher model
- `config/60-train-and-bake-lilakosha-1g-12b-g.yml` – General variant training
- `config/61-train-and-bake-lilakosha-1g-12b-u.yml` – Unbound variant training

For detailed design documentation, see [doc/design.md](doc/design.md).

## Project Deliverables

| Component | Identifier | Description |
| :--- | :--- | :--- |
| **The Pipeline** | **LilaKosha-Flow-MK1** | The complete technical blueprint: data preparation, training logic, and the final "Bake". |
| **General Model** | **LilaKosha-G1-12B-G** | The "General" RPG-tuned model based on the non-abliterated, professionally-grounded Gemma 4 base. |
| **Unbound Model** | **LilaKosha-G1-12B-U** | The "Unbound" creative engine based on the **abliterated** base for maximum narrative freedom. |

### 1A. The LilaKosha-G1-12B-G "General" Variant

This variant serves as the standard, professionally grounded foundation of the project.
*   **Base Model:** Built on the vanilla **google/gemma-4-12B-it**.
*   **Alignment:** It retains the extensive **institutional safety and ethics tuning** performed by Google DeepMind, including rigorous CSAM filtering and protections against dangerous content or harassment.
*   **Target Audience:** Ideal for **mainstream authors**, professional collaborative writing, and educational tools where "General" linguistic competence and corporate-standard guardrails are expected.
*   **Training Focus:** While "General," it still benefits from the pipeline's **"RPG Grammar"** and **State-Awareness**, making it more creative and coherent in long-form narratives than a standard out-of-the-box model.

### 1B. The LilaKosha-G1-12B-U "Unbound" Variant

This variant directly embodies the project's pillar of **"Unbound Creative Freedom"**.
*   **Base Model:** Built on the **gemma-4-12B-it-abliterated-uncensored** base.
*   **Alignment:** It uses an **abliterated residual stream**, where the specific mathematical directions that trigger "refusal" behaviors have been removed.
*   **Target Audience:** Specifically engineered for **immersive roleplay**, intense dramatic conflict, and high-stakes storytelling where the model must handle "complex villains" or "dark themes" without breaking character or "lecturing" the user.
*   **Creative Logic:** By being "Unbound," the model is free to prioritize **novelty, surprise, and diversity**—the core dimensions of **Creative Preference Optimization (CRPO)**—without being constrained by standard refusal vectors.

### 2. The LilaKosha-Flow-MK1 Orchestration-Aware Pipeline

*   **Recap-Augmentation Toolset:** The complete "Processing" codebase used to transform raw roleplay logs into **recap-augmented chunks**, training the model to treat summaries as "truth anchors" for long-term consistency. See [doc/cdm.md](doc/cdm.md) for the Common Data Model schema.
*   **Unsloth-Optimized Training Engine:** A unified Python implementation for **QLoRA training** that shrinks the model footprint to **~7.5 GB**, allowing for high-performance tuning on **12 GB consumer GPUs**.
*   **Weight-Fusion (Bake) Automation:** The specific mathematical routines used to merge trained adapters back into a native 16-bit structure and convert the result into local GGUF block quants (e.g., Q4_K_M or Q8_0).

## Future-Proofing and Model Agnosticism

While the initial release of **LilaKosha** leverages the **Gemma 4 12B Unified** architecture, the underlying pipeline is engineered for cross-model compatibility within the sub-12B parameter space. By focusing on **unified, encoder-free architectures**—where text, image, and audio flow directly into the LLM backbone—the pipeline avoids the complexity of co-tuning separate frozen encoders. This "Orchestration-Aware" framework, combined with **modular mechanistic interventions** like abliteration and **Creative Preference Optimization (CRPO)**, establishes a scalable standard. As hardware constraints remain a reality for consumer-grade devices, this pipeline ensures that future high-utility models can be rapidly fine-tuned for **long-form state awareness** and **unbound creative prose** without reinventing the training infrastructure.

## Future Considerations

The modular step architecture allows easy extension of the pipeline. Potential additions include:

*   **`acquire`** – Automated model and dataset download from HuggingFace with progress tracking and checksum verification.
*   **`validate`** – Pre-flight checks for model integrity, dataset quality, and VRAM availability.
*   **`inspect`** – Raw data statistics and quality analysis before processing.
*   **`export`** – Alternative export formats beyond GGUF (safetensors, ONNX) for different deployment targets.
*   **`full`** – Convenience step group that chains `stage → acquire → prepare → train → bake` for end-to-end execution.

---

*This project is an open-weights initiative intended for fictional writing and entertainment purposes.*
