import logging
from pathlib import Path

from tqdm import tqdm

from cdm.core import Annotation, Document

logger = logging.getLogger(__name__)


def run(config: dict) -> None:
    """
    LilaKosha Scalpel Pass: Restore Original Prose.
    Iterates through standalone Common Document Model (CDM) records, reverting
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
    # When enabled, only restore prose for documents whose player identity
    # has been reset by the character scalpel.
    character_reset_sentinel = params.get("character_reset_sentinel", False)

    # Format localized diagnostic headers for clear Operator Experience (OX)
    if start_uuid or stop_uuid:
        logger.info(
            f"🎯 Targeted Scalpel Scope Activated (Grammar/Prose):\n"
            f"    - Start Boundary: {start_uuid or '[-∞ Unbound]'}\n"
            f"    - Stop Boundary:  {stop_uuid or '[+∞ Unbound]'}"
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
                document = Document.model_validate_json(f.read())

            # Optional safety guard: only restore prose if the player identity
            # has been reset to the default tracking placeholder.
            if character_reset_sentinel:
                player_identity = next(
                    (
                        identity
                        for identity in document.meta.identities
                        if identity.is_player_controlled
                    ),
                    None,
                )
                if (
                    player_identity is None
                    or player_identity.name != "User"
                    or player_identity.gender != "unknown"
                ):
                    continue

            modified_file = False

            # Traverse the transactional ledger items matching discriminated kind tokens
            for item in document.items:
                if item.kind != "turn":
                    continue

                # Inverted Idempotency check: Only target turns that have been modified
                if getattr(item, "original_prose", None) is not None:
                    # Restore the raw snapshot back to the main prose track
                    item.prose = item.original_prose or ""
                    item.original_prose = None
                    item.prose_revision_comments = None
                    modified_file = True

            if modified_file:
                # Filter out legacy grammar annotations to prevent pipeline confusion
                if document.meta.annotations:
                    document.meta.annotations = [
                        anno
                        for anno in document.meta.annotations
                        if anno.kind != "refine-grammar"
                    ]
                else:
                    document.meta.annotations = []

                # Append a surgical track annotation for trace lineage
                scalpel_annotation = Annotation(
                    kind="scalpel-grammar",
                    content=(
                        "roll-back of grammar mutations to original prose state "
                        "via scalpel range"
                    ),
                    reasoning=None,
                )
                document.meta.annotations.append(scalpel_annotation)

                # Re-materialize layout metric statistics post-mutation
                # (preserve word_count)
                turn_count = sum(
                    1 for doc_item in document.items if doc_item.kind == "turn"
                )
                current_word_count = (
                    document.meta.stats.get("word_count")
                    if document.meta.stats
                    else None
                )

                document.meta.stats = {
                    "turn_count": turn_count,
                    "item_count": len(document.items),
                    "character_count": len(document.meta.identities),
                    "word_count": current_word_count,
                }

                # Commit updates smoothly back to disk
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(document.model_dump_json(indent=2))

                restored_count += 1

        except Exception as e:
            logger.error(
                f"Failed surgical prose rollback for document {file_path.name}: {e}"
            )

    logger.info("✅ Scalpel original prose restoration complete.")
    logger.info(f"  Restored: {restored_count} records.")
    logger.info(f"  Skipped out-of-range: {skipped_range_count} records.")
