"""
LilaKosha Step: Refresh metadata for all records.

Updates stats and health status based on current document state.
Intended to be run manually via a separate pipeline invocation.
Supports range filtering via start_uuid and stop_uuid parameters.
"""

import logging
from pathlib import Path

from tqdm import tqdm

from cdm.core import Document
from cdm.meta import update_meta

logger = logging.getLogger(__name__)


def run(config: dict) -> None:
    """
    LilaKosha Step: Refresh metadata for all records.

    Updates meta based on current document state.
    Intended to be run manually via a separate pipeline invocation.
    Supports range filtering via start_uuid and stop_uuid parameters.
    """
    # Resolve paths from configuration volumes
    processed_vol = Path(config["volumes"]["processed"])
    records_dir = processed_vol / "cdm" / "records"

    if not records_dir.exists():
        logger.error(
            f"Records directory not found: {records_dir}. Run ingestion first."
        )
        return

    record_files = sorted(records_dir.glob("*.json"))
    if not record_files:
        logger.warning(f"No canvas records found to refresh inside {records_dir}")
        return

    # Extract range parameters
    params = config.get("parameters", {})
    start_uuid = params.get("start_uuid")
    stop_uuid = params.get("stop_uuid")

    if start_uuid or stop_uuid:
        logger.info(
            f"🎯 Targeted Refresh Scope Activated:\n"
            f"    - Start Boundary: {start_uuid or '[-∞ Unbound]'}\n"
            f"    - Stop Boundary:  {stop_uuid or '[+∞ Unbound]'}"
        )
    else:
        logger.info(
            "🔬 Refresh Scope: Global Sweep (No lexical range parameters provided)"
        )

    logger.info(f"Inspecting {len(record_files)} records for metadata refresh...")

    skipped_range_count = 0
    refreshed_count = 0

    for file_path in tqdm(record_files, desc="Refreshing Metadata"):
        record_uuid = file_path.stem

        # Check floor constraint boundary
        if start_uuid and record_uuid < str(start_uuid):
            skipped_range_count += 1
            continue

        # Check ceiling constraint boundary
        if stop_uuid and record_uuid > str(stop_uuid):
            skipped_range_count += 1
            continue

        try:
            # 1. Load the standalone canvas document
            with open(file_path, "r", encoding="utf-8") as f:
                document = Document.model_validate_json(f.read())

            # 2. Update stats
            update_meta(document)

            # 4. Commit changes back to disk
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(document.model_dump_json(indent=2))

            refreshed_count += 1

        except Exception as e:
            logger.error(f"Failed metadata refresh for document {file_path.name}: {e}")

    logger.info(
        f"✅ Metadata refresh pass complete. "
        f"Refreshed: {refreshed_count} records. "
        f"Skipped out-of-range: {skipped_range_count} records."
    )
