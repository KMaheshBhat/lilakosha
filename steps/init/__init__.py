import logging
from pathlib import Path
from typing import Any

# Configure internal step logging for Operator Experience (OX)
logger = logging.getLogger(__name__)


def run(config: dict[str, Any]) -> None:
    """
    LilaKosha MK1 Infrastructure Staging.

    Bootstraps the physical directory structure defined in the config's
    'volumes' section and provides acquisition instructions.
    """
    # 1. Extract Volumes (Resolving LILAKOSHA_VOLUME_* exports)
    volumes = config.get("volumes", {})
    if not volumes:
        logger.error("STAGING FAILED: No 'volumes' defined in the configuration.")
        return

    logger.info(f"\n{'=' * 65}\n🛠️  LILAKOSHA MK1: INFRASTRUCTURE STAGING\n{'=' * 65}")

    # 2. Directory Creation Tree
    # This loop dynamically builds the architecture based on the volume schema
    for label, path in volumes.items():
        volume_path = Path(str(path))
        try:
            if not volume_path.exists():
                volume_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"  [CREATED] {label.upper():<10} : {volume_path}")
            else:
                logger.info(f"  [EXISTS ] {label.upper():<10} : {volume_path}")

            # Create standard sub-paths for unified model placement
            if label == "models":
                (volume_path / "google" / "gemma-4-12b-it").mkdir(
                    parents=True, exist_ok=True
                )
                (
                    volume_path
                    / "OpenYourMind"
                    / "gemma-4-12b-it-abliterated-uncensored"
                ).mkdir(parents=True, exist_ok=True)
                (volume_path / "checkpoints").mkdir(parents=True, exist_ok=True)

            # Create flavor sub-paths for GGUF distribution
            if label == "exports":
                (volume_path / "gguf_builds" / "general").mkdir(
                    parents=True, exist_ok=True
                )
                (volume_path / "gguf_builds" / "unbound").mkdir(
                    parents=True, exist_ok=True
                )

        except Exception as e:
            logger.error(f"Failed to initialize volume '{label}' at {volume_path}: {e}")

    # 3. Operator Instructions for Model Acquisition
    models_root = Path(str(volumes.get("models", "[ERROR: MODELS VOLUME MISSING]")))
    raw_root = Path(str(volumes.get("raw", "[ERROR: RAW VOLUME MISSING]")))

    model_non_abliterated = models_root / "google" / "gemma-4-12b-it"
    model_abliterated = (
        models_root / "OpenYourMind" / "gemma-4-12b-it-abliterated-uncensored"
    )

    instruction_block = (
        f"\n{'-' * 65}\n"
        f"📥 MODEL ACQUISITION & PLACEMENT INSTRUCTIONS\n"
        f"{'-' * 65}\n\n"
        f"1. GENERAL VARIANT (Safe/SFW Foundation):\n"
        f"   > Download: https://huggingface.co/google/gemma-4-12b-it\n"
        f"   > Place in: {model_non_abliterated}\n\n"
        f"2. UNBOUND VARIANT (Abliterated/Uncensored Foundation):\n"
        f"   > Download: https://huggingface.co/OpenYourMind/gemma-4-12b-it-abliterated-uncensored\n"
        f"   > Place in: {model_abliterated}\n\n"
        f"3. DATA STAGING:\n"
        f"   > Place messy PIPPA/MUCE logs in the UNIFIED landing zone: {raw_root}\n"
        f"   > The 'prepare' step will introspect and fork these automatically"
    )
    logger.info(instruction_block)

    logger.info(
        f"\n{'=' * 65}\n✅ Infrastructure is staged for LilaKosha-G1.\n{'=' * 65}\n"
    )
