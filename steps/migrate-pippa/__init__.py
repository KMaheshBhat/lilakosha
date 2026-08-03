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
                if kind in ("scalpel-grammar", "refine-grammar"):
                    ann["kind"] = "refine-pippa-grammar"
                    modified = True
                elif kind in ("refine-character", "refine-characters"):
                    ann["kind"] = "refine-pippa-character"
                    modified = True

    # -------------------------------------------------------------------------
    # 2. Rename keys in meta.health.breakdown (refine-* -> refine-pippa-*)
    # -------------------------------------------------------------------------
    health = meta.get("health", {})
    breakdown = health.get("breakdown")
    if isinstance(breakdown, dict):
        new_breakdown = {}
        for key, value in breakdown.items():
            if key.startswith("refine-") and not key.startswith("refine-pippa-"):
                # Handle specific singular/plural edge cases to keep standard names
                if key in ("refine-grammar", "refine-pippa-grammar"):
                    new_key = "refine-pippa-grammar"
                elif key in ("refine-character", "refine-characters"):
                    new_key = "refine-pippa-character"
                else:
                    new_key = key.replace("refine-", "refine-pippa-", 1)

                new_breakdown[new_key] = value
                if new_key != key:
                    modified = True
            else:
                new_breakdown[key] = value

        health["breakdown"] = new_breakdown

    # -------------------------------------------------------------------------
    # 3. Update items[].content[].name
    # -------------------------------------------------------------------------
    items = doc.get("items", [])
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue

            content = item.get("content")
            if not isinstance(content, list):
                continue

            for variant in content:
                if not isinstance(variant, dict):
                    continue

                variant_name = variant.get("name", "")

                # Standardize turn and character refinement content variant names
                if variant_name in ("grammar-refined", "refine-grammar"):
                    variant["name"] = "refine-pippa-grammar"
                    modified = True
                elif variant_name in (
                    "character-refined",
                    "refine-characters",
                    "refine-character",
                ):
                    variant["name"] = "refine-pippa-character"
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
