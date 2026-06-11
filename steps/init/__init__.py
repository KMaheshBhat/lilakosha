import logging
import os
from typing import Any

# Configure internal step logging for Operator Experience (OX)
logger = logging.getLogger(__name__)


def run(config: dict[str, Any]) -> None:
    """
    LilaKosha MK1 Infrastructure Staging.

    Bootstraps the physical directory structure defined in the config's
    'volumes' section and provides acquisition instructions.
    """
    # 1. Extract Volumes (Resolving $LILAKOSHA_VOLUME_* exports)
    volumes = config.get("volumes", {})
    if not volumes:
        logger.error("STAGING FAILED: No 'volumes' defined in the configuration.")
        return
    print(f"\n{'=' * 65}")
    print("🛠️  LILAKOSHA MK1: INFRASTRUCTURE STAGING")
    print(f"{'=' * 65}")
    # 2. Directory Creation Tree
    # This loop dynamically builds the architecture based on the volume schema
    for label, path in volumes.items():
        # Ensure path is treated as a string to satisfy StrPath requirements
        path_str = str(path)
        try:
            if not os.path.exists(path_str):
                os.makedirs(path_str, exist_ok=True)
                print(f"  [CREATED] {label.upper():<10} : {path_str}")
            else:
                print(f"  [EXISTS ] {label.upper():<10} : {path_str}")
            # Create standard sub-paths for unified model placement
            if label == "models":
                os.makedirs(
                    os.path.join(path_str, "google/gemma-4-12b-it"), exist_ok=True
                )
                os.makedirs(
                    os.path.join(
                        path_str, "OpenYourMind/gemma-4-12b-it-abliterated-uncensored"
                    ),
                    exist_ok=True,
                )
                os.makedirs(os.path.join(path_str, "checkpoints"), exist_ok=True)
            # Create flavor sub-paths for GGUF distribution
            if label == "exports":
                os.makedirs(
                    os.path.join(path_str, "gguf_builds/general"), exist_ok=True
                )
                os.makedirs(
                    os.path.join(path_str, "gguf_builds/unbound"), exist_ok=True
                )
        except Exception as e:
            logger.error(f"Failed to initialize volume '{label}' at {path_str}: {e}")
    # 3. Operator Instructions for Model Acquisition
    # Based on the user's specific requirement for placement instructions
    models_root = volumes.get("models", "[ERROR: MODELS VOLUME MISSING]")
    raw_root = volumes.get("raw", "[ERROR: RAW VOLUME MISSING]")
    print(f"\n{'-' * 65}")
    print("📥 MODEL ACQUISITION & PLACEMENT INSTRUCTIONS")
    print(f"{'-' * 65}")
    print("\n1. GENERAL VARIANT (Safe/SFW Foundation):")
    print("   > Download: https://huggingface.co/google/gemma-4-12b-it")
    print(f"   > Place in: {os.path.join(models_root, 'google/gemma-4-12b-it')}")
    print("\n2. UNBOUND VARIANT (Abliterated/Uncensored Foundation):")
    print(
        "   > Download: https://huggingface.co/OpenYourMind/gemma-4-12b-it-abliterated-uncensored"
    )
    ubm = os.path.join(
        models_root, "OpenYourMind/gemma-4-12b-it-abliterated-uncensored"
    )
    print(f"   > Place in: {ubm}")
    print("\n3. DATA STAGING:")
    print(f"   > Place messy PIPPA/MUCE logs in the UNIFIED landing zone: {raw_root}")
    print("   > The 'prepare' step will introspect and fork these automatically")

    print(f"\n{'=' * 65}")
    print("✅ Infrastructure is staged for LilaKosha-G1.")
    print(f"{'=' * 65}\n")
