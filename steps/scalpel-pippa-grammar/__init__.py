import logging
from pathlib import Path
from typing import Any

from tqdm import tqdm

from cdm.core import Document, TurnItem
from cdm.meta import add_annotation, remove_annotation, update_meta

logger = logging.getLogger(__name__)


def _check_user_info_health(health: Any) -> bool:
    """Helper to safely extract 'user info' health flag across dict/model variants."""
    if not health:
        return False

    breakdown = (
        health.get("breakdown", {})
        if isinstance(health, dict)
        else getattr(health, "breakdown", {})
    )
    if not breakdown:
        return False

    refine_char = (
        breakdown.get("refine-pippa-characters", {})
        if isinstance(breakdown, dict)
        else getattr(breakdown, "refine_pippa_characters", {})
    )
    if not refine_char:
        return False

    if isinstance(refine_char, dict):
        return bool(refine_char.get("user info", False))

    return bool(getattr(refine_char, "user_info", False))


def run(config: dict) -> None:
    """
    LilaKosha Scalpel Pass: Restore Original Prose (PIPPA).
    Iterates through standalone Common Document Model (CDM) records, reverting
    third-person narrative mutations back to their original first-person chat strings
    by trimming refined ContentVariants from TurnItem instances.
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
    character_reset_sentinel = params.get("character_reset_sentinel", False)

    if start_uuid or stop_uuid:
        logger.info(
            f"🎯 Targeted Scalpel Scope Activated (PIPPA Grammar/Prose):\n"
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

            if character_reset_sentinel:
                if not _check_user_info_health(document.meta.health):
                    continue

            modified_file = False

            # Traverse TurnItems and revert content variants back to 'original'
            for item in document.items:
                if not isinstance(item, TurnItem):
                    continue

                # Check if non-original variants exist (e.g., 'grammar-refined')
                has_refined_variants = any(
                    variant.name != "original" for variant in item.content
                )

                if has_refined_variants:
                    # Keep only the 'original' variant
                    original_variants = [
                        variant
                        for variant in item.content
                        if variant.name == "original"
                    ]

                    if original_variants:
                        item.content = original_variants
                        modified_file = True

            if modified_file:
                # Filter out legacy grammar annotations
                remove_annotation(document, "refine-pippa-grammar")

                # Append surgical track annotation
                add_annotation(
                    document,
                    kind="scalpel-pippa-grammar",
                    content=(
                        "roll-back of grammar mutations to original prose state "
                        "via scalpel range"
                    ),
                )

                # Re-materialize layout metric statistics post-mutation
                update_meta(document)

                # Commit updates back to disk with alias alignment
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(
                        document.model_dump_json(indent=2, by_alias=True)
                    )

                restored_count += 1

        except Exception as e:
            logger.error(
                f"Failed surgical prose rollback for document {file_path.name}: {e}"
            )

    logger.info("✅ Scalpel original prose restoration complete.")
    logger.info(f"  Restored: {restored_count} records.")
    logger.info(f"  Skipped out-of-range: {skipped_range_count} records.")
