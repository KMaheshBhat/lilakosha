import logging
from pathlib import Path

from tqdm import tqdm

from cdm.core import Annotation, Session

logger = logging.getLogger(__name__)


def run(config: dict) -> None:
    """
    LilaKosha Scalpel Pass: Clear Safety Dials.
    Iterates through standalone Common Data Model (CDM) records, purging
    computed safety metrics and tracking annotations to allow clean evaluations.
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
        f"Inspecting {len(record_files)} records for safety metrics clearance..."
    )

    for file_path in tqdm(record_files, desc="Purging Safety Metrics"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                session = Session.model_validate_json(f.read())

            # Check if there are active metrics to clear
            has_metrics = (
                session.meta.sexual_axis is not None
                or session.meta.violence_axis is not None
                or session.meta.toxicity_axis is not None
            )

            if has_metrics:
                # 1. Nullify the safety dimensions on the session metadata
                session.meta.sexual_axis = None
                session.meta.violence_axis = None
                session.meta.toxicity_axis = None

                # 2. Filter out historical safety-dials annotations to
                #    ensure clean lineage
                if session.meta.annotations:
                    session.meta.annotations = [
                        anno
                        for anno in session.meta.annotations
                        if anno.kind != "refine-safety-dials"
                    ]
                else:
                    session.meta.annotations = []

                # 3. Append a surgical tracking trace token
                scalpel_annotation = Annotation(
                    kind="scalpel-safety-dials",
                    content="cleared safety dial metrics and annotations",
                    reasoning=None,
                )
                session.meta.annotations.append(scalpel_annotation)

                # 4. Save updates cleanly back to the filesystem
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(session.model_dump_json(indent=2))

        except Exception as e:
            logger.error(
                f"Failed surgical safety metrics purge for document "
                f"{file_path.name}: {e}"
            )

    logger.info("✅ Scalpel safety dials clearance pass complete.")
