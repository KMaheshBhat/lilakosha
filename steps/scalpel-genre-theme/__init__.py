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
    """
    processed_vol = Path(config["volumes"]["processed"])
    records_dir = processed_vol / "cdm" / "records"

    if not records_dir.exists():
        logger.error(
            f"Records directory not found: {records_dir}. Run ingestion first."
        )
        return

    record_files = sorted(records_dir.glob("*.json"))
    if not record_files:
        logger.warning(f"No canvas records found to evaluate inside {records_dir}")
        return

    logger.info(
        f"Inspecting {len(record_files)} records for genre and theme metadata..."
    )

    for file_path in tqdm(record_files, desc="Purging Genre & Themes"):
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

                # 2. Filter out historical refinement annotations to
                #    maintain track integrity
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
                    content="cleared narrative genre classifications and thematic tags",
                    reasoning=None,
                )
                session.meta.annotations.append(scalpel_annotation)

                # 4. Save updates cleanly back to the filesystem
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(session.model_dump_json(indent=2))

        except Exception as e:
            logger.error(
                f"Failed surgical metadata purge for document {file_path.name}: {e}"
            )

    logger.info("✅ Scalpel genre & theme clearance pass complete.")
