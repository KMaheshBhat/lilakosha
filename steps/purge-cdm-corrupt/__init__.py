import logging
from pathlib import Path

from tqdm import tqdm

from cdm import LedgerIndex
from cdm.core import Document

logger = logging.getLogger(__name__)


def run(config: dict) -> None:
    """
    LilaKosha Purge Pass: Purge Corrupt CDM Records.
    Scans the CDM record directory, identifies invalid or corrupted JSON records
    (e.g., caused by interrupted writes or power outages), deletes the corrupted
    record files from disk, and removes their corresponding mapping entries from
    the master LedgerIndex so they can be safely re-ingested.
    """
    # 1. Resolve Data Infrastructure & Ledger Index
    processed_vol = Path(config["volumes"]["processed"])
    cdm_root = processed_vol / "cdm"
    records_dir = cdm_root / "records"
    mapping_file = cdm_root / "mapping.jsonl"

    if not records_dir.exists():
        logger.error(
            f"Records directory not found: {records_dir}. Run ingestion first."
        )
        return

    record_files = sorted(records_dir.glob("*.json"))
    if not record_files:
        logger.warning(f"No CDM records found inside {records_dir}")
        return

    ledger_index = LedgerIndex(mapping_file)

    # 2. Extract Target Range Parameters
    params = config.get("parameters", {})
    start_uuid = params.get("start_uuid")
    stop_uuid = params.get("stop_uuid")

    if start_uuid or stop_uuid:
        logger.info(
            f"🎯 Targeted Purge Scope Activated:\n"
            f"    - Start Boundary: {start_uuid or '[-∞ Unbound]'}\n"
            f"    - Stop Boundary:  {stop_uuid or '[+∞ Unbound]'}"
        )
    else:
        logger.info("🔬 Perge Scope: Global Sweep for Corrupt CDM Records")

    logger.info(f"Inspecting {len(record_files)} record files for corruption...")

    # 3. Main Operational Execution Loop
    corrupt_count = 0
    skipped_range_count = 0

    for file_path in tqdm(record_files, desc="Scanning for Corrupt CDM Records"):
        record_uuid = file_path.stem  # Extract target UUIDv7 token string

        # Check floor constraint boundary
        if start_uuid and record_uuid < str(start_uuid):
            skipped_range_count += 1
            continue

        # Check ceiling constraint boundary
        if stop_uuid and record_uuid > str(stop_uuid):
            skipped_range_count += 1
            continue

        is_corrupt = False
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Empty file check
            if not content.strip():
                is_corrupt = True
            else:
                # Validate CDM structural integrity via Pydantic model
                Document.model_validate_json(content)

        except Exception as err:
            logger.warning(
                f"Detected corrupt CDM document record '{file_path.name}': {err}"
            )
            is_corrupt = True

        # 4. Perform Purge on Corrupted Artifacts
        if is_corrupt:
            # Step A: Delete file from local record storage
            try:
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"Deleted corrupt file: {file_path.name}")
            except Exception as file_err:
                logger.error(f"Failed to delete file {file_path.name}: {file_err}")

            # Step B: Purge record entry from LedgerIndex (in-memory + mapping.jsonl)
            try:
                ledger_index.delete_record(record_uuid)
            except Exception as ledger_err:
                logger.error(
                    f"Failed to un-register {record_uuid} from ledger index: "
                    f"{ledger_err}"
                )

            corrupt_count += 1

    logger.info("✅ Corrupt CDM Purge pass completed.")
    logger.info(f"   Purged corrupt records: {corrupt_count}")
    logger.info(f"   Skipped out-of-range: {skipped_range_count}")
