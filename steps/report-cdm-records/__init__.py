import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def run(config: dict) -> None:
    """
    LilaKosha Telemetry Step: Report CDM record UUIDs with lexical sorting.
    Reports total count, start UUID, UUIDs at every 1000th position, and stop UUID.
    """
    processed_vol = Path(config["volumes"]["processed"])
    records_dir = processed_vol / "cdm" / "records"
    if not records_dir.exists():
        logger.error(f"Records directory not found at {records_dir}")
        return
    record_files = list(records_dir.glob("*.json"))
    total_records = len(record_files)
    if total_records == 0:
        logger.warning("No CDM records found to analyze.")
        return
    # Extract UUIDs and sort lexicographically
    uuids = sorted(file_path.stem for file_path in record_files)
    logger.info("=" * 60)
    logger.info("📊 CDM RECORDS REPORT")
    logger.info("=" * 60)
    logger.info(f"Total number of records: {total_records}")
    logger.info(f"Start UUID: {uuids[0]}")
    logger.info("-" * 60)
    # Report UUIDs at every 1000th position
    for i in range(1000, total_records, 1000):
        uuid_1000 = uuids[i - 1]
        uuid_1001 = uuids[i]
        logger.info(f"UUID at position {i}: {uuid_1000}")
        logger.info(f"UUID at position {i + 1}: {uuid_1001}")
    logger.info("-" * 60)
    logger.info(f"Stop UUID: {uuids[-1]}")
    logger.info("=" * 60)
