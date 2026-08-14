import logging
from pathlib import Path

from cdm.ledger_index import LedgerIndex

logger = logging.getLogger(__name__)


def run(config: dict) -> None:
    """
    LilaKosha Telemetry Step: Report CDM record UUIDs with lexical sorting,
    sampling intervals, and source range transitions using LedgerIndex.
    """
    processed_vol = Path(config["volumes"]["processed"])

    # 1. Inspect physical filesystem as before
    records_dir = processed_vol / "cdm" / "records"
    if not records_dir.exists():
        logger.error(f"Records directory not found at {records_dir}")
        return

    record_files = list(records_dir.glob("*.json"))
    total_physical = len(record_files)
    if total_physical == 0:
        logger.warning("No CDM records found on disk to analyze.")
        return

    # 2. Query LedgerIndex for metadata mapping
    mapping_path = processed_vol / "cdm" / "mapping.jsonl"
    ledger = LedgerIndex(mapping_path)
    ledger_records = ledger.get_records()

    if not ledger_records:
        logger.warning("Ledger index is empty or mapping file missing.")
        return

    # 3. Sort entries lexicographically by UUID
    sorted_records = sorted(ledger_records, key=lambda r: r["uuid"])
    total_records = len(sorted_records)

    logger.info("=" * 60)
    logger.info("📊 CDM RECORDS REPORT")
    logger.info("=" * 60)
    logger.info(f"Total Physical Files: {total_physical}")
    logger.info(f"Total Indexed Records: {total_records}")
    logger.info(
        f"Start UUID: {sorted_records[0]['uuid']} "
        f"(Source: {sorted_records[0].get('source', 'unknown')})"
    )
    logger.info("-" * 60)

    # 4. Report UUIDs at every 1000th position
    for i in range(1000, total_records, 1000):
        uuid_1000 = sorted_records[i - 1]["uuid"]
        uuid_1001 = sorted_records[i]["uuid"]
        logger.info(f"UUID at position {i}: {uuid_1000}")
        logger.info(f"UUID at position {i + 1}: {uuid_1001}")

    logger.info("-" * 60)
    logger.info(
        f"Stop UUID: {sorted_records[-1]['uuid']} "
        f"(Source: {sorted_records[-1].get('source', 'unknown')})"
    )

    # 5. Detect and report Source Range Boundaries
    logger.info("=" * 60)
    logger.info("📍 SOURCE RANGES & BOUNDARIES")
    logger.info("=" * 60)

    current_source = sorted_records[0].get("source", "unknown")
    range_start_idx = 0

    for idx, rec in enumerate(sorted_records):
        src = rec.get("source", "unknown")
        if src != current_source:
            prev_rec = sorted_records[idx - 1]
            count = idx - range_start_idx
            logger.info(f"Source [{current_source}]: {count} records")
            logger.info(
                f"  └─ Start UUID (pos {range_start_idx + 1}): "
                f"{sorted_records[range_start_idx]['uuid']}"
            )
            logger.info(f"  └─ End UUID   (pos {idx}): {prev_rec['uuid']}")
            logger.info("-" * 40)

            current_source = src
            range_start_idx = idx

    # Final source block print
    final_count = total_records - range_start_idx
    logger.info(f"Source [{current_source}]: {final_count} records")
    logger.info(
        f"  └─ Start UUID (pos {range_start_idx + 1}): "
        f"{sorted_records[range_start_idx]['uuid']}"
    )
    logger.info(f"  └─ End UUID   (pos {total_records}): {sorted_records[-1]['uuid']}")
    logger.info("=" * 60)
