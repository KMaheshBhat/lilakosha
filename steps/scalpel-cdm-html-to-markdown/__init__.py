import logging
from pathlib import Path

from tqdm import tqdm

from cdm.core import Document
from cdm.meta import add_annotation, remove_annotation, update_meta

logger = logging.getLogger(__name__)

# Explicit list of CDM item kinds that possess a .content list of ContentVariants
SUPPORTED_CONTENT_KINDS: set[str] = {
    "narrative",
    "turn",
    "world",
    "character",
    "summary",
}


def run(config: dict) -> None:
    """
    LilaKosha Scalpel Pass: Revert Markdown Variants (HTML to Markdown) (v2).
    Iterates through standalone Common Document Model (CDM) records, reverting
    markdownified HTML prose variants back to their original HTML state
    by removing the 'refine-cdm-html-to-markdown' ContentVariants from items.
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

    # v2: Pre-filter record_files by file.stem before opening/parsing
    if start_uuid or stop_uuid:
        record_files = [
            f
            for f in record_files
            if (not start_uuid or f.stem >= str(start_uuid))
            and (not stop_uuid or f.stem <= str(stop_uuid))
        ]
        logger.info(
            f"🎯 Targeted Scalpel Scope Activated (CDM HTML to Markdown v2):\n"
            f"    - Start Boundary: {start_uuid or '[-∞ Unbound]'}\n"
            f"    - Stop Boundary:  {stop_uuid or '[+∞ Unbound]'}\n"
            f"    - Pre-filtered to {len(record_files)} candidate files"
        )
    else:
        logger.info(
            "🔬 Scalpel Scope: Global Sweep (No lexical range parameters provided)"
        )

    logger.info(
        f"Inspecting {len(record_files)} records for markdown variant removal (v2)..."
    )

    # 3. Main Operational Execution Loop
    removed_count = 0
    skipped_range_count = 0
    error_count = 0

    for file_path in tqdm(record_files, desc="Removing Markdown Variants (v2)"):
        record_uuid = file_path.stem  # Extract the tracking UUIDv7 token string

        # Check floor constraint boundary
        # (should not happen after pre-filter, but keep for safety)
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

            modified_file = False

            # Traverse content-carrying items and remove the specific markdown variant
            for item in document.items:
                if item.kind not in SUPPORTED_CONTENT_KINDS:
                    continue

                content = getattr(item, "content", None)
                if not content:
                    continue

                # Check if the refined markdown variant exists
                has_refined_variant = any(
                    variant.name == "refine-cdm-html-to-markdown" for variant in content
                )

                if has_refined_variant:
                    # Remove only the 'refine-cdm-html-to-markdown' variant
                    # Keep all other variants (e.g., 'original')
                    setattr(
                        item,
                        "content",
                        [
                            variant
                            for variant in content
                            if variant.name != "refine-cdm-html-to-markdown"
                        ],
                    )
                    modified_file = True

            if modified_file:
                # Filter out legacy HTML to Markdown annotations
                remove_annotation(document, "refine-cdm-html-to-markdown")

                # Append surgical track annotation
                add_annotation(
                    document,
                    kind="scalpel-cdm-html-to-markdown",
                    content=(
                        "roll-back of markdown mutations to original HTML state "
                        "via scalpel range"
                    ),
                )

                # Re-materialize layout metric statistics post-mutation
                update_meta(document)

                # Commit updates back to disk with alias alignment
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(document.model_dump_json(indent=2, by_alias=True))

                removed_count += 1

        except Exception as e:
            logger.error(
                f"Failed surgical markdown rollback for document {file_path.name}: {e}"
            )
            error_count += 1

    logger.info("✅ Scalpel markdown variant removal (v2) complete.")
    logger.info(f"  Restored: {removed_count} records.")
    logger.info(f"  Skipped out-of-range: {skipped_range_count} records.")
    logger.info(f"  Errors: {error_count} records.")
