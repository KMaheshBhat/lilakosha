import logging
from pathlib import Path

from tqdm import tqdm

from cdm.core import Document
from cdm.meta import add_annotation, remove_annotation, update_meta

logger = logging.getLogger(__name__)


def run(config: dict) -> None:
    """
    LilaKosha Scalpel Pass: Clear Language Categorizations (CDM).
    Iterates through standalone Common Document Model (CDM) records, purging
    computed language categorization items alongside related refinement
    history annotations.
    Supports optional runtime range filtering via 'start_uuid' and
    'stop_uuid' parameters.
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
            f"🎯 Targeted Scalpel Scope Activated (CDM Language):\n"
            f"    - Start Boundary: {start_uuid or '[-∞ Unbound]'}\n"
            f"    - Stop Boundary:  {stop_uuid or '[+∞ Unbound]'}"
        )
    else:
        logger.info(
            "🔬 Scalpel Scope: Global Sweep (No lexical range parameters provided)"
        )

    logger.info(
        f"Inspecting {len(record_files)} records for language metadata..."
    )

    # 3. Main Operational Execution Loop
    purged_count = 0
    skipped_range_count = 0

    for file_path in tqdm(record_files, desc="Purging Language Metadata"):
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

            # Detect if timeline items contain target categorizations
            has_language_items = any(
                item.kind == "categorization" and item.category == "language"
                for item in document.items
            )

            if has_language_items:
                # Filter out discrete timeline language items
                document.items = [
                    item
                    for item in document.items
                    if not (
                        item.kind == "categorization"
                        and item.category == "language"
                    )
                ]

                # Filter out historical refinement annotations
                remove_annotation(document, "refine-cdm-language")

                # Append a surgical tracking trace token
                add_annotation(
                    document,
                    kind="scalpel-cdm-language",
                    content=(
                        "cleared language categorization items and refinement "
                        "annotations from metadata caches and timeline items "
                        "via scalpel range"
                    ),
                )

                # Re-materialize layout metric statistics post-mutation
                update_meta(document)

                # Save updates cleanly back to the filesystem
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(
                        document.model_dump_json(indent=2, by_alias=True)
                    )

                purged_count += 1

        except Exception as e:
            logger.error(
                f"Failed surgical metadata purge for document {file_path.name}: {e}"
            )

    logger.info("✅ Scalpel language clearance pass complete.")
    logger.info(f"   Purged: {purged_count} records.")
    logger.info(f"   Skipped out-of-range: {skipped_range_count} records.")
