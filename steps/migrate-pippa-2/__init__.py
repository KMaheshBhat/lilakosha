import json
import logging
from pathlib import Path
from typing import Any, Dict, Tuple

from tqdm import tqdm

logger = logging.getLogger(__name__)


def fix_character_refinement_naming(doc: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """
    Fixes the singular 'refine-pippa-character' typo across breakdown keys,
    annotations, and item variant names to 'refine-pippa-characters'.
    """
    modified = False

    # 1. Fix meta.annotations[].kind
    meta = doc.get("meta", {})
    annotations = meta.get("annotations", [])
    if isinstance(annotations, list):
        for ann in annotations:
            if isinstance(ann, dict) and ann.get("kind") == "refine-pippa-character":
                ann["kind"] = "refine-pippa-characters"
                modified = True

    # 2. Fix meta.health.breakdown keys
    health = meta.get("health", {})
    breakdown = health.get("breakdown")
    if isinstance(breakdown, dict) and "refine-pippa-character" in breakdown:
        breakdown["refine-pippa-characters"] = breakdown.pop("refine-pippa-character")
        modified = True

    # 3. Fix items[].content[].name
    items = doc.get("items", [])
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for variant in content:
                if (
                    isinstance(variant, dict)
                    and variant.get("name") == "refine-pippa-character"
                ):
                    variant["name"] = "refine-pippa-characters"
                    modified = True

    return doc, modified


def run(config: dict) -> None:
    """
    CDM Migration Pass 2: Rename 'refine-pippa-character' to 'refine-pippa-characters'
    across all JSON records.
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
        f"Inspecting {len(record_files)} JSON records "
        "for character refinement naming fix..."
    )

    migrated_records_count = 0

    for file_path in tqdm(record_files, desc="Migrating CDM JSON Records (Pass 2)"):
        record_uuid = file_path.stem

        if start_uuid and record_uuid < str(start_uuid):
            continue
        if stop_uuid and record_uuid > str(stop_uuid):
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                doc_data = json.load(f)

            updated_doc, doc_modified = fix_character_refinement_naming(doc_data)

            if doc_modified:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(updated_doc, f, indent=2, ensure_ascii=False)
                migrated_records_count += 1

        except Exception as e:
            logger.error(f"Failed migrating JSON document {file_path.name}: {e}")

    logger.info(
        f"✅ CDM migration pass 2 complete. Modified {migrated_records_count} records."
    )
