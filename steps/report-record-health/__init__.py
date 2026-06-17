import json
import logging
from collections import defaultdict
from pathlib import Path

from cdm.core import Session

logger = logging.getLogger(__name__)


def run(config: dict) -> None:
    """
    LilaKosha Telemetry Step: Assess structural and content health metrics
    across all canvas JSON records on disk using native Pydantic models.
    """
    processed_vol = Path(config["volumes"]["processed"])
    records_dir = processed_vol / "cdm" / "records"

    if not records_dir.exists():
        logger.error(f"Records directory not found at {records_dir}")
        return

    canvas_files = list(records_dir.glob("*.json"))
    total_records = len(canvas_files)

    if total_records == 0:
        logger.warning("No canvas artifacts found to evaluate.")
        return

    healthy_count = 0
    failure_registry = defaultdict(list)

    logger.info(f"Auditing data health parameters across {total_records} records...")

    for file_path in canvas_files:
        uuid_str = file_path.stem

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Authoritative validation against cdm.core.Session
            session = Session.model_validate(data)
            meta = session.meta
            items = session.items or []
            annotations = meta.annotations or []

            # Extract kinds from Pydantic Annotation objects safely
            annotation_kinds = {
                anno.kind for anno in annotations if hasattr(anno, "kind")
            }

            issues = []

            # --- Rule Group 1: refine-characters ---
            if "refine-characters" not in annotation_kinds:
                issues.append("Missing 'refine-characters' annotation")

            has_bot_detail = any(
                item.kind == "character"
                and getattr(item, "subkind", None) == "detail"
                and getattr(item, "entity_id", None) != "user"
                for item in items
            )
            if not has_bot_detail:
                issues.append(
                    "Missing bot character details (subkind=detail, entity_id!=user)"
                )

            has_user_info = any(
                item.kind == "character"
                and getattr(item, "subkind", None) == "info"
                and getattr(item, "entity_id", None) == "user"
                for item in items
            )
            if not has_user_info:
                issues.append(
                    "Missing user profiling info (subkind=info, entity_id=user)"
                )

            # --- Rule Group 2: refine-safety-dials ---
            if "refine-safety-dials" not in annotation_kinds:
                issues.append("Missing 'refine-safety-dials' annotation")

            if meta.sexual_axis is None:
                issues.append("Unset 'meta.sexual_axis'")
            if meta.violence_axis is None:
                issues.append("Unset 'meta.violence_axis'")
            if meta.toxicity_axis is None:
                issues.append("Unset 'meta.toxicity_axis'")

            # --- Rule Group 3: refine-genre-theme ---
            if "refine-genre-theme" not in annotation_kinds:
                issues.append("Missing 'refine-genre-theme' annotation")
            if meta.primary_genre is None:
                issues.append("Unset 'meta.primary_genre'")
            if not meta.themes:  # Checks for None or empty list
                issues.append("Unset or empty 'meta.themes'")

            # --- Rule Group 4: refine-grammar ---
            if "refine-grammar" not in annotation_kinds:
                issues.append("Missing 'refine-grammar' annotation")

            # Verify that every turn item correctly retains its original_prose baseline
            missing_lineage_turns = sum(
                1
                for item in items
                if item.kind == "turn" and getattr(item, "original_prose", None) is None
            )
            if missing_lineage_turns > 0:
                issues.append(
                    f"Grammar tracking defect: {missing_lineage_turns} turn items are"
                    " missing 'original_prose'"
                )

            # --- Consolidation ---
            if not issues:
                healthy_count += 1
            else:
                failure_registry[uuid_str] = issues

        except Exception as e:
            failure_registry[uuid_str].append(
                f"Pydantic validation/structural crash: {str(e)}"
            )

    # --- Render Report Output ---
    health_percentage = (healthy_count / total_records) * 100

    logger.info("=" * 60)
    logger.info("📊 LILAKOSHA PIPELINE DATA HEALTH REPORT")
    logger.info("=" * 60)
    logger.info(f"Total Records Evaluated: {total_records}")
    logger.info(f"Healthy Records:         {healthy_count} ({health_percentage:.2f}%)")
    logger.info(f"Defective Records:       {len(failure_registry)}")
    logger.info("=" * 60)

    if failure_registry:
        logger.info("❌ DETECTED ANOMALY REGISTRY BY RECORD ID:")
        for uuid, faults in failure_registry.items():
            logger.info(f"  ↳ UUID: {uuid}")
            for fault in faults:
                logger.info(f"      - {fault}")
        logger.info("=" * 60)
