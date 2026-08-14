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

    logger.info(f"{'=' * 65}")
    logger.info("🛠️  LILAKOSHA MK1: INFRASTRUCTURE STAGING")
    logger.info(f"{'=' * 65}")

    # 2. Directory Creation Tree
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
                (volume_path / "embeddings" / "bge-small-en-v1.5").mkdir(
                    parents=True, exist_ok=True
                )
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
    raw_root = Path(str(volumes.get("raw", "[ERROR: RAW VOLUME MISSING]")))
    models_root = Path(str(volumes.get("models", "[ERROR: MODELS VOLUME MISSING]")))

    model_embedding = models_root / "embeddings" / "bge-small-en-v1.5"
    model_non_abliterated = models_root / "google" / "gemma-4-12b-it"
    model_abliterated = (
        models_root / "OpenYourMind" / "gemma-4-12b-it-abliterated-uncensored"
    )

    logger.info(f"{'-' * 65}")
    logger.info("📥 MODEL ACQUISITION & PLACEMENT INSTRUCTIONS")
    logger.info(f"{'-' * 65}")
    logger.info("1. DATA STAGING:")
    logger.info(
        f"   > Place messy PIPPA/Gutenberg source into landing zone: {raw_root}"
    )
    logger.info("   > Use 'acquire' step instead if internet access is available")
    logger.info("   > The 'ingest' steps will introspect and fork these automatically")
    logger.info("2. EMBEDDING MODEL (Semantic Theme Resolution):")
    logger.info("   > Download: https://huggingface.co/BAAI/bge-small-en-v1.5")
    logger.info(f"   > Place in: {model_embedding} (or auto-acquire via pipeline)")
    logger.info("   > Use 'acquire' step instead if internet access is available")
    logger.info("3. GENERAL VARIANT (Safe/SFW Foundation):")
    logger.info("   > Download: https://huggingface.co/google/gemma-4-12b-it")
    logger.info(f"   > Place in: {model_non_abliterated}")
    logger.info("4. UNBOUND VARIANT (Abliterated/Uncensored Foundation):")
    logger.info(
        "   > Download: https://huggingface.co/OpenYourMind/gemma-4-12b-it-abliterated-uncensored"
    )
    logger.info(f"   > Place in: {model_abliterated}")
    logger.info(f"{'=' * 65}")
    logger.info("✅ Infrastructure is staged for LilaKosha-G1.")
    logger.info(f"{'=' * 65}")
