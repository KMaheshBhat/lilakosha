import logging
import urllib.request
from pathlib import Path

from huggingface_hub import snapshot_download

logger = logging.getLogger(__name__)

GUTENBERG_62_URL = "https://www.gutenberg.org/cache/epub/62/pg62.txt"
EMBEDDING_REPO = "BAAI/bge-small-en-v1.5"

def acquire_gutenberg_62(raw_vol: Path) -> None:
    target_dir = raw_vol / "raw" / "gutenberg" / "62"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / "pg62.txt"

    if target_file.exists() and target_file.stat().st_size > 0:
        logger.info(f"Gutenberg #62 raw text already acquired at: {target_file}")
        return

    logger.info(
        f"Downloading Gutenberg #62 from {GUTENBERG_62_URL} to {target_file}..."
    )

    try:
        req = urllib.request.Request(
            GUTENBERG_62_URL, headers={"User-Agent": "LilaKosha-Acquisition/1.0"}
        )
        with urllib.request.urlopen(req) as response:
            content = response.read().decode("utf-8")

        with open(target_file, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"✅ Successfully acquired Gutenberg #62 raw text at {target_file}")
    except Exception as e:
        logger.error(f"Failed to download Gutenberg #62 from {GUTENBERG_62_URL}: {e}")


def acquire_embeddings(models_vol: Path) -> None:
    target_dir = models_vol / "embeddings" / "bge-small-en-v1.5"
    target_dir.mkdir(parents=True, exist_ok=True)

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


def run(config: dict) -> None:
    """LilaKosha Pipeline Step: Acquire open model weights and raw source datasets."""
    raw_vol = Path(config["volumes"]["raw"])
    models_vol = Path(config["volumes"]["models"])

    acquire_gutenberg_62(raw_vol)
    acquire_embeddings(models_vol)
