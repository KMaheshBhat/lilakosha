import logging
from pathlib import Path

from tqdm import tqdm

from cdm.core import Annotation, Session, TurnItem

logger = logging.getLogger(__name__)


def run(config: dict) -> None:
    """
    LilaKosha Scalpel Pass: Restore Original Prose.
    Iterates through standalone Common Data Model (CDM) records, reverting
    third-person narrative mutations back to their original first-person chat strings.
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
            f"🎯 Targeted Scalpel Scope Activated (Grammar/Prose):\n"
            f"   - Start Boundary: {start_uuid or '[-∞ Unbound]'}\n"
            f"   - Stop Boundary:  {stop_uuid or '[+∞ Unbound]'}"
        )
    else:
        logger.info(
            "🔬 Scalpel Scope: Global Sweep (No lexical range parameters provided)"
        )

    logger.info(
        f"Inspecting {len(record_files)} records for original prose restoration..."
    )

    # 3. Main Operational Execution Loop
    restored_count = 0
    skipped_range_count = 0

    for file_path in tqdm(record_files, desc="Restoring Original Prose"):
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
                session = Session.model_validate_json(f.read())

            modified_file = False

            # Traverse the transactional ledger items instead of legacy children array
            for item in session.items:
                if not isinstance(item, TurnItem):
                    continue

                # Inverted Idempotency check: Only target turns that have been modified
                if item.original_prose is not None:
                    # Restore the raw snapshot back to the main prose track
                    item.prose = item.original_prose
                    item.original_prose = None
                    item.prose_revision_comments = None
                    modified_file = True

            if modified_file:
                # Filter out legacy grammar annotations to prevent pipeline confusion
                if session.meta.annotations:
                    session.meta.annotations = [
                        anno
                        for anno in session.meta.annotations
                        if anno.kind != "refine-grammar"
                    ]
                else:
                    session.meta.annotations = []

                # Append a surgical track annotation for trace lineage
                scalpel_annotation = Annotation(
                    kind="scalpel-grammar",
                    content=(
                        "roll-back of grammar mutations to original prose state "
                        "via scalpel range"
                    ),
                    reasoning=None,
                )
                session.meta.annotations.append(scalpel_annotation)

                # Commit updates smoothly back to disk
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(session.model_dump_json(indent=2))

                restored_count += 1

        except Exception as e:
            logger.error(
                f"Failed surgical prose rollback for document {file_path.name}: {e}"
            )

    logger.info(
        f"✅ Scalpel original prose restoration complete. "
        f"Restored: {restored_count} records. "
        f"Skipped out-of-range: {skipped_range_count} records."
    )
