# Project Lilakosha: The Treasury of Divine Play

**Project Lilakosha** (लीलाकोश) is a high-utility, open-weights framework dedicated to developing a fine-tuned version of the **Gemma 4 12B** architecture specifically for **immersive creative writing, complex narrative generation, and interactive roleplay**. 

The name combines **Lila** (Play/Imaginative Sport) and **Kosha** (Treasury/Repository), representing a deep architectural repository for uninhibited collaborative storytelling.

## Core Pillars
*   **Unbound Creative Freedom:** Utilizing an **abliterated base** to bypass restrictive refusal vectors, allowing the model to handle high-stakes drama and complex villains without breaking character.
*   **Orchestration-Aware Pipeline:** A unique training methodology that "bakes in" the dynamics of long-form narrative by using **Recap-Augmented Chunking** to handle the "Continue" use case within hardware limits.
*   **Dual-Flavor Deployment:** Simultaneous release of an **Uncensored/Abliterated** variant for maximum flexibility and a **Safe/SFW** variant for mainstream collaborative writing.
*   **Hardware Optimization:** Precision-tuned for consumer-grade hardware (specifically **12 GB VRAM GPUs**) using the **Unsloth** memory-efficient training engine.

## Technical Specifications
*   **Base Model:** [Gemma 4 12B Unified](https://huggingface.co/google/gemma-4-12B) (~11.95B dense parameters).
*   **Architecture:** Encoder-free, multimodal decoder-only transformer with native support for text, image, and audio.
*   **Context Window:** Supports up to **256K tokens** for inference.
*   **Training Method:** **QLoRA (Quantized Low-Rank Adaptation)** via Unsloth to shrink the memory footprint to **~7.5 GB**, leaving a buffer for training sequences up to **4,096 tokens**.

## The Lilakosha Pipeline
1.  **Base Selection:** Start with either the vanilla `gemma-4-12B-it` or the `gemma-4-12B-it-abliterated-uncensored` base.
2.  **Processing (Recap-Augmentation):** Use a teacher model to generate **Session Recaps and Key Highlights** for long-form datasets. This trains the model to treat summaries as "truth anchors" for long-term consistency.
3.  **Training (The QLoRA Phase):** Attach trainable LoRA adapters to the attention and MLP projections to target roleplay and conversational style.
4.  **The "Bake" (Weight Fusion):** Mathematically inject the trained adapter weights back into the native 16-bit structure to create a **monolithic distribution file**.
5.  **Export (GGUF):** Convert the merged model into specialized GGUF block quants (e.g., **Q4_K_M**) for optimized local deployment.

## Getting Started
This repository contains the configuration and scripts required to initialize the **Lilakosha** training environment on **WSL2**. 

### Requirements
*   **Hardware:** NVIDIA RTX GPU with at least **12 GB VRAM** (e.g., RTX 4070).
*   **Software:** WSL2 (Ubuntu), Python 3.10+, and the **Unsloth** library.

### Future-Proofing and Model Agnosticism
While the initial release of **Lilakosha** leverages the **Gemma 4 12B Unified** architecture, the underlying pipeline is engineered for cross-model compatibility within the sub-12B parameter space. By focusing on **unified, encoder-free architectures**—where text, image, and audio flow directly into the LLM backbone—the pipeline avoids the complexity of co-tuning separate frozen encoders. This "Orchestration-Aware" framework, combined with **modular mechanistic interventions** like abliteration and **Creative Preference Optimization (CRPO)**, establishes a scalable standard. As hardware constraints remain a reality for consumer-grade devices, this pipeline ensures that future high-utility models can be rapidly fine-tuned for **long-form state awareness** and **unbound creative prose** without reinventing the training infrastructure.

### Project Deliverables
The project will result in two distinct primary deliverables:

**1. Optimized GGUF Model Distributions**
*   **The Safe/General Variant:** A production-ready, monolithic **GGUF** (e.g., Q4_K_M) distribution based on the vanilla `google/gemma-4-12B-it`. This version is designed for mainstream collaborative writing, maintaining standard corporate guardrails and professional grounding while benefiting from the pipeline's enhanced creative "soul".
*   **The Unbound/Abliterated Variant:** A twin distribution based on the `gemma-4-12B-it-abliterated-uncensored` base. This variant provides the maximum narrative flexibility required for intense dramatic roleplay, completely decoupled from standard refusal vectors.

**2. The Lilakosha Orchestration-Aware Pipeline**
*   **Recap-Augmentation Toolset:** The complete "Processing" codebase used to transform raw roleplay logs into **recap-augmented chunks**, training the model to treat summaries as "truth anchors" for long-term consistency.
*   **Unsloth-Optimized Training Engine:** A unified Python implementation for **QLoRA training** that shrinks the model footprint to **~7.5 GB**, allowing for high-performance tuning on **12 GB consumer GPUs**.
*   **Weight-Fusion (Bake) Automation:** The specific mathematical routines used to merge trained adapters back into a native 16-bit structure and convert the result into local GGUF block quants (e.g., Q4_K_M or Q8_0).

---

*This project is an open-weights initiative intended for fictional writing and entertainment purposes.*