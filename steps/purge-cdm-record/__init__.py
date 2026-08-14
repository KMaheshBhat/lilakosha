import logging
from pathlib import Path

from tqdm import tqdm

from cdm import LedgerIndex

logger = logging.getLogger(__name__)


def _parse_target_uuids(raw_targets: str | list | None) -> set[str]:
    """Helper to normalize target_uuid parameters into a clean set of UUID strings."""
    if not raw_targets:
        return set()
    if isinstance(raw_targets, str):
        return {uuid.strip() for uuid in raw_targets.split(",") if uuid.strip()}
    if isinstance(raw_targets, list):
        return {str(uuid).strip() for uuid in raw_targets if str(uuid).strip()}
    return set()


def run(config: dict) -> None:
    """
    LilaKosha Purge Pass: Targeted CDM Record Purge.
    Surgically removes specific CDM record file(s) from disk and unregisters
    their mapping entries from the master LedgerIndex.

    Parameters supported:
      - target_uuid: A single UUID string, comma-separated string, or list of UUIDs.
      - start_uuid / stop_uuid: Optional range boundaries if targeting a lexical range.
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

    # 2. Extract and Validate Target Scope Parameters
    params = config.get("parameters", {})
    target_uuids = _parse_target_uuids(params.get("target_uuid"))
    start_uuid = params.get("start_uuid")
    stop_uuid = params.get("stop_uuid")

    if not target_uuids and not start_uuid and not stop_uuid:
        logger.error(
            "❌ Aborting purge operation: No target scope parameters provided! "
            "Please specify 'target_uuid', 'start_uuid', or 'stop_uuid'."
        )
        return

    ledger_index = LedgerIndex(mapping_file)

    # 3. Determine Execution Mode
    if target_uuids:
        logger.info(
            f"🎯 Targeted Purge Scope Activated (Explicit UUID List):\n"
            f"    - Target Count: {len(target_uuids)}\n"
            f"    - UUIDs: {', '.join(sorted(target_uuids))}"
        )
    else:
        logger.info(
            f"🎯 Targeted Purge Scope Activated (Lexical Range):\n"
            f"    - Start Boundary: {start_uuid or '[-∞ Unbound]'}\n"
            f"    - Stop Boundary:  {stop_uuid or '[+∞ Unbound]'}"
        )

    # 4. Main Operational Execution
    purged_count = 0
    failed_count = 0

    if target_uuids:
        # Fast direct execution mode for specific target UUIDs
        for target_uuid in tqdm(
            sorted(target_uuids),
            desc="Purging Targeted CDM Records",
        ):
            file_path = records_dir / f"{target_uuid}.json"

            # Step A: Remove physical file if it exists
            if file_path.exists():
                try:
                    file_path.unlink()
                    logger.info(f"Deleted record file: {file_path.name}")
                except Exception as file_err:
                    logger.error(f"Failed to delete file {file_path.name}: {file_err}")
                    failed_count += 1
                    continue
            else:
                logger.warning(
                    f"Record file {file_path.name} not found on disk, proceeding "
                    f"with ledger un-registration."
                )

            # Step B: Remove entry from LedgerIndex
            try:
                deleted = ledger_index.delete_record(target_uuid)
                if deleted:
                    purged_count += 1
                else:
                    logger.warning(
                        f"UUID {target_uuid} was not present in the ledger index."
                    )
            except Exception as ledger_err:
                logger.error(
                    f"Failed to un-register {target_uuid} from "
                    f"ledger index: {ledger_err}"
                )
                failed_count += 1

    else:
        # Range sweep execution mode
        record_files = sorted(records_dir.glob("*.json"))
        skipped_range_count = 0

        for file_path in tqdm(record_files, desc="Scanning & Purging Range Scope"):
            record_uuid = file_path.stem

            if start_uuid and record_uuid < str(start_uuid):
                skipped_range_count += 1
                continue

            if stop_uuid and record_uuid > str(stop_uuid):
                skipped_range_count += 1
                continue

            # Execute purge for range item
            try:
                file_path.unlink(missing_ok=True)
                ledger_index.delete_record(record_uuid)
                purged_count += 1
                logger.info(f"Purged record: {record_uuid}")
            except Exception as err:
                logger.error(f"Failed surgical purge for record {record_uuid}: {err}")
                failed_count += 1

        logger.info(f"  Skipped out-of-range: {skipped_range_count}")

    logger.info("✅ Targeted CDM Purge pass complete.")
    logger.info(f"   Purged records: {purged_count}")
    if failed_count > 0:
        logger.error(f"   Failed operations: {failed_count}")
