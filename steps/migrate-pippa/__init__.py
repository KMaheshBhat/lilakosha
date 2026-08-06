import json
import logging
from pathlib import Path
from typing import Any, Dict, Tuple

from tqdm import tqdm

logger = logging.getLogger(__name__)


def migrate_cdm_document(doc: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """
    Transforms a CDM document to standardize all refinement references
    to 'refine-pippa-*'.  Returns the updated document and a boolean flag
    indicating if changes were made.
    """
    modified = False

    # -------------------------------------------------------------------------
    # 1. Update meta.annotations[].kind
    # -------------------------------------------------------------------------
    meta = doc.get("meta", {})
    annotations = meta.get("annotations", [])
    if isinstance(annotations, list):
        for ann in annotations:
            if isinstance(ann, dict):
                kind = ann.get("kind", "")
                # Map old names like 'scalpel-grammar', 'refine-grammar', etc.
                if kind in ("refine-safety-dials"):
                    ann["kind"] = "refine-pippa-safety-dials"
                    modified = True
                elif kind in ("refine-genre-theme"):
                    ann["kind"] = "refine-pippa-genre-theme"
                    modified = True

    return doc, modified


def run(config: dict) -> None:
    """
    CDM Migration Pass: Update all refinement step names to refine-pippa-* across
    raw JSON records.
    """
    processed_vol = Path(config["volumes"]["processed"])
    records_dir = processed_vol / "cdm" / "records"

    if not records_dir.exists():
        logger.error(f"Records directory not found: {records_dir}")
        return

    record_files = sorted(records_dir.glob("*.json"))
    if not record_files:
        logger.warning(f"No CDM JSON records found inside {records_dir}")
        return

    params = config.get("parameters", {})
    start_uuid = params.get("start_uuid")
    stop_uuid = params.get("stop_uuid")

    logger.info(
        f"Inspecting {len(record_files)} JSON records for CDM schema migration..."
    )

    migrated_records_count = 0

    for file_path in tqdm(record_files, desc="Migrating CDM JSON Records"):
        record_uuid = file_path.stem

        if start_uuid and record_uuid < str(start_uuid):
            continue
        if stop_uuid and record_uuid > str(stop_uuid):
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                doc_data = json.load(f)

            updated_doc, doc_modified = migrate_cdm_document(doc_data)

            if doc_modified:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(updated_doc, f, indent=2, ensure_ascii=False)
                migrated_records_count += 1

        except Exception as e:
            logger.error(f"Failed migrating JSON document {file_path.name}: {e}")

    logger.info(
        f"✅ CDM migration complete. Modified {migrated_records_count} records."
    )
