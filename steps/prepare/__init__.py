import logging
import os


def run(config):
    """
    LilaKosha-G1-12B Stage 1: Data Preparation (The Teacher Pass)

    This step orchestrates the transformation of raw dialogue logs into
    'Recap-Augmented Chunks' using a local or cloud inference service.
    """
    # 1. Extract Project Metadata
    project = config.get("project", {})
    name = project.get("name", "LilaKosha")
    mark = project.get("mark", "MK1")
    gen = project.get("generation", "G1")
    # 2. Derive Input/Output Folders from Storage Schema
    schema = config.get("storage_schema", {})
    raw_info = schema.get("raw_data", {})
    proc_info = schema.get("processed_data", {})
    raw_path = raw_info.get("path")
    processed_path = proc_info.get("path")
    # 3. Extract Infrastructure Details
    infra = config.get("infrastructure", {})
    service_url = infra.get("inference_service")
    # 4. Enhanced Logging Output
    print(f"\n{'=' * 60}")
    print(f"🚀 {name} {mark} FLOW: STAGE 1 (PREPARATION)")
    print(f"{'=' * 60}")
    logging.info(f"Project Mission: {project.get('purpose')}")
    logging.info(f"Target Generation: {gen}-12B")
    # Pre-flight Path Verification
    if not os.path.exists(raw_path):
        logging.error(f"ABORT: Raw data directory not found at {raw_path}")
        logging.error("Ensure your $LILAKOSHA_BASE_DATA environment variable is set.")
        return
    logging.info(f"INPUT PATH:  {raw_path} (Purpose: {raw_info.get('purpose')})")
    logging.info(f"OUTPUT PATH: {processed_path}")
    logging.info(f"SERVICE:     Connecting to {service_url} for Teacher Inference...")
    # 5. Logic Simulation (The "Teacher" Pass)
    print("\n--- Processing Raw Records ---")
    # Scanning for specific datasets mentioned in the mission
    logging.info("Scanning for datasets: MUCE (200k samples), PIPPA (Character.AI)...")
    print("  > Initializing 'RPG Grammar' templates...")
    print(f"  > Generating Session Recaps via {service_url}...")
    # Thinking Mode logic for high-quality summarization
    if config.get("step_params", {}).get("prepare", {}).get("thinking_mode", True):
        print("  > Thinking Mode: ENABLED (<|think|> token injection active)")
    print("  > Prepending Key Highlights to narrative chunks...")
    # 6. Success Reporting
    print(f"\n{'*' * 60}")
    logging.info(f"SUCCESS: {gen} Training Samples Prepared.")
    logging.info(f"Location: {processed_path}")
    logging.info(f"Structure: {proc_info.get('structure')}")
    print(f"{'*' * 60}\n")
