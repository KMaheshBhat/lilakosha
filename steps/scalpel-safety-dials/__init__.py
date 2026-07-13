import logging
from pathlib import Path

from tqdm import tqdm

from cdm.core import Document
from cdm.meta import add_annotation, remove_annotation, update_meta

logger = logging.getLogger(__name__)


def run(config: dict) -> None:
    """
    LilaKosha Scalpel Pass: Clear Safety Dials.
    Iterates through standalone Common Document Model (CDM) records, purging
    computed safety metrics from the items timeline and tracking annotations
    to allow clean evaluations. Supports optional runtime range filtering
    via 'start_uuid' and 'stop_uuid' parameters.
    """
    # 1. Resolve Data Infrastructure
    processed_vol = Path(config["volumes"]["processed"])
    records_dir = processed_vol / "cdm" / "records"

    if not records_dir.exists():
        logger.error(
            f"Records directory not found: {records_dir}. Run ingestion first."
        )
        return

    record_files = sorted(records_dir.glob("*.json"))
    if not record_files:
        logger.warning(f"No canvas records found inside {records_dir}")
        return

    # 2. Extract and Validate Target Range Markers
    params = config.get("parameters", {})
    start_uuid = params.get("start_uuid")
    stop_uuid = params.get("stop_uuid")

    # Format localized diagnostic headers for clear Operator Experience (OX)
    if start_uuid or stop_uuid:
        logger.info(
            f"🎯 Targeted Scalpel Scope Activated:\n"
            f"    - Start Boundary: {start_uuid or '[-∞ Unbound]'}\n"
            f"    - Stop Boundary:  {stop_uuid or '[+∞ Unbound]'}"
        )
    else:
        logger.info(
            "🔬 Scalpel Scope: Global Sweep (No lexical range parameters provided)"
        )

    logger.info(f"Inspecting {len(record_files)} files for safety metrics clearance...")

    # 3. Main Operational Execution Loop
    purged_count = 0
    skipped_range_count = 0

    target_categories = {"sexuality", "violence", "toxicity"}

    for file_path in tqdm(record_files, desc="Processing Scalpel Operation"):
        record_uuid = file_path.stem  # Extract the tracking UUIDv7 token string

        # Check floor constraint boundary
        if start_uuid and record_uuid < str(start_uuid):
            skipped_range_count += 1
            continue

        # Check ceiling constraint boundary
        if stop_uuid and record_uuid > str(stop_uuid):
            skipped_range_count += 1
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                document = Document.model_validate_json(f.read())

            # Evaluate state vectors for pending execution conditions within items loop
            has_metrics = any(
                item.kind == "categorization" and item.category in target_categories
                for item in document.items
            )

            if has_metrics:
                # 1. Filter out the specific structural safety layout vectors
                document.items = [
                    item
                    for item in document.items
                    if not (
                        item.kind == "categorization"
                        and item.category in target_categories
                    )
                ]

                # 2. Purge stale lineage tracking details to clean up metrics
                remove_annotation(document, "refine-safety-dials")

                # 3. Inject explicit scalpel audit token
                add_annotation(
                    document,
                    kind="scalpel-safety-dials",
                    content=(
                        "cleared safety dial metrics and annotations via scalpel range"
                    ),
                )

                # 4. Re-materialize layout metric statistics post-mutation
                update_meta(document)

                # 5. Commit modification atomicity directly to local slot
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(document.model_dump_json(indent=2))

                purged_count += 1

        except Exception as e:
            logger.error(
                f"Failed surgical safety metrics purge for document "
                f"{file_path.name}: {e}"
            )

    logger.info("✅ Scalpel pass completed.")
    logger.info(f"  Purged: {purged_count} records.")
    logger.info(f"  Skipped out-of-range: {skipped_range_count} records.")
