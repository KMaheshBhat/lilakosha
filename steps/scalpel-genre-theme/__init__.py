import logging
from pathlib import Path

from tqdm import tqdm

from cdm.core import Annotation, Document, DocumentStats

logger = logging.getLogger(__name__)


def run(config: dict) -> None:
    """
    LilaKosha Scalpel Pass: Clear Genre & Themes.
    Iterates through standalone Common Document Model (CDM) records, purging
    computed narrative genres and thematic tags alongside related history annotations
    and timeline categorization items.
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
            f"🎯 Targeted Scalpel Scope Activated (Genre/Theme):\n"
            f"    - Start Boundary: {start_uuid or '[-∞ Unbound]'}\n"
            f"    - Stop Boundary:  {stop_uuid or '[+∞ Unbound]'}"
        )
    else:
        logger.info(
            "🔬 Scalpel Scope: Global Sweep (No lexical range parameters provided)"
        )

    logger.info(
        f"Inspecting {len(record_files)} records for genre and theme metadata..."
    )

    # 3. Main Operational Execution Loop
    purged_count = 0
    skipped_range_count = 0

    for file_path in tqdm(record_files, desc="Purging Genre & Themes"):
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
            has_timeline_items = any(
                item.kind == "categorization"
                and item.category in ("primary_genre", "themes")
                for item in document.items
            )

            # Check if active metadata elements or timeline records are present to clear
            has_metadata = (
                document.meta.primary_genre is not None
                or (document.meta.themes is not None and len(document.meta.themes) > 0)
                or has_timeline_items
            )

            if has_metadata:
                # 1. Nullify the genre and theme dimensions on document metadata
                document.meta.primary_genre = None
                document.meta.themes = None

                # 2. Clear out discrete timeline serialization elements
                document.items = [
                    item
                    for item in document.items
                    if not (
                        item.kind == "categorization"
                        and item.category in ("primary_genre", "themes")
                    )
                ]

                # 3. Filter out historical refinement annotations to maintain
                # track integrity
                if document.meta.annotations:
                    document.meta.annotations = [
                        anno
                        for anno in document.meta.annotations
                        if anno.kind != "refine-genre-theme"
                    ]
                else:
                    document.meta.annotations = []

                # 4. Append a surgical tracking trace token
                scalpel_annotation = Annotation(
                    kind="scalpel-genre-theme",
                    content=(
                        "cleared narrative genre classifications and thematic tags "
                        "from metadata caches and timeline items via scalpel range"
                    ),
                    reasoning=None,
                )
                document.meta.annotations.append(scalpel_annotation)

                # 5. Re-materialize layout metric statistics post-mutation
                #    (preserve word_count)
                turn_count = sum(
                    1 for doc_item in document.items if doc_item.kind == "turn"
                )
                current_word_count = (
                    document.meta.stats.word_count if document.meta.stats else None
                )

                document.meta.stats = DocumentStats(
                    turn_count=turn_count,
                    item_count=len(document.items),
                    character_count=len(document.meta.identities),
                    word_count=current_word_count,
                )

                # 6. Save updates cleanly back to the filesystem
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(document.model_dump_json(indent=2))

                purged_count += 1

        except Exception as e:
            logger.error(
                f"Failed surgical metadata purge for document {file_path.name}: {e}"
            )

    logger.info("✅ Scalpel genre & theme clearance pass complete.")
    logger.info(f"  Purged: {purged_count} records.")
    logger.info(f"  Skipped out-of-range: {skipped_range_count} records.")
