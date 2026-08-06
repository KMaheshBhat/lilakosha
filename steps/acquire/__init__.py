import logging
from pathlib import Path

from huggingface_hub import snapshot_download

logger = logging.getLogger(__name__)

EMBEDDING_REPO = "BAAI/bge-small-en-v1.5"


def run(config: dict) -> None:
    """LilaKosha Pipeline Step: Acquire open model weights (such as sentence embeddings)
    and verify local staging paths.
    """
    models_vol = Path(config["volumes"]["models"])
    target_dir = models_vol / "embeddings" / "bge-small-en-v1.5"

    target_dir.mkdir(parents=True, exist_ok=True)

    # Check if essential model files already exist locally
    config_file = target_dir / "config.json"
    model_file = target_dir / "model.safetensors"

    if config_file.exists() and model_file.exists():
        logger.info(f"Embedding model already acquired at: {target_dir}")
        return

    logger.info(
        f"Acquiring open embedding model '{EMBEDDING_REPO}' into {target_dir}..."
    )

    try:
        snapshot_download(
            repo_id=EMBEDDING_REPO,
            local_dir=str(target_dir),
        )
        logger.info(f"✅ Successfully acquired {EMBEDDING_REPO}")
    except Exception as e:
        logger.error(
            f"Failed to download embedding model {EMBEDDING_REPO}: {e}"
        )
