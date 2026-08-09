import logging
import urllib.request
from pathlib import Path

from huggingface_hub import hf_hub_download

logger = logging.getLogger(__name__)


def acquire_gutenberg_62(config: dict) -> None:
    """
    Download Gutenberg eBook #62 raw text file if not already present.
    """
    raw_vol = Path(config["volumes"]["raw"])
    target_dir = raw_vol / "raw" / "gutenberg" / "62"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / "pg62.txt"

    if target_file.exists():
        logger.info(f"Gutenberg 62 raw file already exists: {target_file}")
        return

    url = "https://www.gutenberg.org/cache/epub/62/pg62.txt"
    logger.info(f"Downloading Gutenberg 62 from {url}...")
    urllib.request.urlretrieve(url, target_file)
    logger.info(f"Successfully downloaded Gutenberg 62 to {target_file}")


def acquire_pippa(config: dict) -> None:
    """
    Download PIPPA deduped dataset from Hugging Face Hub (PygmalionAI/PIPPA).
    """
    raw_vol = Path(config["volumes"]["raw"])
    target_dir = raw_vol / "raw" / "PygmalionAI" / "PIPPA"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / "pippa_deduped.jsonl"

    if target_file.exists():
        logger.info(f"PIPPA raw dataset already exists: {target_file}")
        return

    logger.info("Downloading pippa_deduped.jsonl from Hugging Face...")
    downloaded_path = hf_hub_download(
        repo_id="PygmalionAI/PIPPA",
        filename="pippa_deduped.jsonl",
        repo_type="dataset",
        local_dir=target_dir,
    )
    logger.info(f"Successfully downloaded PIPPA dataset to {downloaded_path}")


def acquire_rpgnet(config: dict) -> None:
    """
    Download RPGnet source Parquet files from
    Hugging Face Hub (lemonilia/roleplaying-forums-raw).
    """
    raw_vol = Path(config["volumes"]["raw"])
    target_dir = raw_vol / "raw" / "lemonilia" / "roleplaying-forums-raw"
    target_dir.mkdir(parents=True, exist_ok=True)

    repo_id = "lemonilia/roleplaying-forums-raw"
    parquet_files = [
        "RPGnet--roleplay-by-post-play-forum--part1.parquet",
        "RPGnet--roleplay-by-post-play-forum--part2.parquet",
    ]

    for filename in parquet_files:
        target_file = target_dir / filename
        if target_file.exists():
            logger.info(f"RPGnet source file already exists: {target_file}")
            continue

        logger.info(f"Downloading {filename} from Hugging Face repo '{repo_id}'...")
        downloaded_path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            repo_type="dataset",
            local_dir=target_dir,
        )
        logger.info(f"Successfully downloaded {filename} to {downloaded_path}")


def run(config: dict) -> None:
    """
    LilaKosha Data Acquisition Step.
    Executes raw data download subroutines.
    """
    logger.info("Starting LilaKosha raw data acquisition pipeline...")
    acquire_gutenberg_62(config)
    acquire_pippa(config)
    acquire_rpgnet(config)
    logger.info("LilaKosha raw data acquisition completed successfully.")
