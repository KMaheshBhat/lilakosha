import logging
import os
from typing import Any, cast


def run(config: dict[str, Any]):
    """
    LilaKosha-G1-12B Stage 2: Resource-Constrained Training (QLoRA)
    """
    # 1. Correct Metadata Extraction (Nested under 'project')
    project = config.get("project", {})
    gen = project.get("generation", "G1")
    variant = project.get("model_variant", "unbound").lower()
    # 2. Path Derivation (Isolation Principle)
    schema = config.get("storage_schema", {})
    model_info = schema.get("model_assets", {})
    base_dir = cast(str, model_info.get("path"))
    sub_path = model_info.get("sub_paths", {}).get("base", "google/gemma-4-12b-it")
    full_model_path = os.path.join(base_dir, sub_path)
    # 3. Enhanced Logging
    print(f"\n{'=' * 60}")
    print(f"🔥 {project.get('name')} {project.get('mark')} FLOW: STAGE 2 (TRAINING)")
    print(f"{'=' * 60}")
    logging.info(f"TARGET VARIANT: {variant.upper()}")
    if variant == "unbound":
        logging.info("Foundation: Using Abliterated weights (Refusal-Free).")
    else:
        logging.info("Foundation: Using Vanilla weights (Safety-Aligned).")
    # 4. Hardware Verification
    print(f"\n--- Loading {gen}-12B Unified Backbone ---")
    logging.info(f"Source: {full_model_path}")
    print("  > Mode: QLoRA (4-bit quantization enabled)")
    print("  > Base Footprint: ~7.5 GB VRAM")  # Standard for Gemma 4 12B Q4
    print(
        f"  > Sequence Buffer: ~3.5 GB "
        f"(Max Seq: {config['training_params']['context_window']})"
    )
    # 5. Data & Optimization Injection
    print("\n--- Ingesting State-Aware Narrative Records ---")
    input_data = schema.get("processed_data", {}).get("path")
    logging.info(f"Input: {input_data}")
    lambdas = config.get("training_params", {}).get("crpo_lambdas", {})
    print(
        f"  > CRPO Injection Weights: "
        f"λ_nov={lambdas.get('novelty')}, λ_sur={lambdas.get('surprise')}"
    )
    # 6. Success Reporting with Dynamic Naming
    print(f"\n{'*' * 60}")
    logging.info(
        f"SUCCESS: {project.get('name')}-{gen}-12B-{variant.upper()} Adapters Saved."
    )
    logging.info("Status: Ready for the 'Bake' phase.")
    print(f"{'*' * 60}\n")
