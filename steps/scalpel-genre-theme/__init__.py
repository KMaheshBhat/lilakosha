import logging
from pathlib import Path

from tqdm import tqdm

from cdm.core import Annotation, Session

logger = logging.getLogger(__name__)


def run(config: dict) -> None:
    """
    LilaKosha Scalpel Pass: Clear Genre & Themes.
    Iterates through standalone Common Data Model (CDM) records, purging
    computed narrative genres and thematic tags alongside related history annotations.
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
            f"   - Start Boundary: {start_uuid or '[-∞ Unbound]'}\n"
            f"   - Stop Boundary:  {stop_uuid or '[+∞ Unbound]'}"
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
                session = Session.model_validate_json(f.read())

            # Check if active metadata elements are present to clear
            has_metadata = session.meta.primary_genre is not None or (
                session.meta.themes is not None and len(session.meta.themes) > 0
            )

            if has_metadata:
                # 1. Nullify the genre and theme dimensions on session metadata
                session.meta.primary_genre = None
                session.meta.themes = None

                # 2. Filter out historical refinement annotations to maintain
                #    track integrity
                if session.meta.annotations:
                    session.meta.annotations = [
                        anno
                        for anno in session.meta.annotations
                        if anno.kind != "refine-genre-theme"
                    ]
                else:
                    session.meta.annotations = []

                # 3. Append a surgical tracking trace token
                scalpel_annotation = Annotation(
                    kind="scalpel-genre-theme",
                    content=(
                        "cleared narrative genre classifications and thematic tags "
                        "via scalpel range"
                    ),
                    reasoning=None,
                )
                session.meta.annotations.append(scalpel_annotation)

                # 4. Save updates cleanly back to the filesystem
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(session.model_dump_json(indent=2))

                purged_count += 1

        except Exception as e:
            logger.error(
                f"Failed surgical metadata purge for document {file_path.name}: {e}"
            )

    logger.info("✅ Scalpel genre & theme clearance pass complete.")
    logger.info(f"  Purged: {purged_count} records.")
    logger.info(f"  Skipped out-of-range: {skipped_range_count} records.")
