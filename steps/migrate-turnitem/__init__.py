import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from tqdm import tqdm

logger = logging.getLogger(__name__)


def migrate_turn_dict(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transforms a raw TurnItem dictionary into the new CDM schema with content variants.

    Mapping rules:
    - original: legacy `original_prose` if present, else legacy `prose`
    - grammar-refined: legacy `prose` (only if `original_prose` was present)
    - annotation on original: legacy `thought` if non-empty
    - annotation on grammar-refined: legacy `prose_revision_comments` if non-empty
    """
    if item.get("kind") != "turn":
        return item

    # Idempotency check: Skip if already migrated to new content structure
    if "content" in item and isinstance(item["content"], list):
        return item

    variants: List[Dict[str, Any]] = []

    prose = item.get("prose", "")
    original_prose = item.get("original_prose")
    revision_comments = item.get("prose_revision_comments")
    thought = item.get("thought")

    # Clean annotation values (ignore empty strings or None)
    thought_annotation = thought.strip() if isinstance(thought, str) and thought.strip() else None
    comment_annotation = (
        revision_comments.strip()
        if isinstance(revision_comments, str) and revision_comments.strip()
        else None
    )

    if original_prose is not None:
        # Refined turn: 'original_prose' was the input, 'prose' was the rewritten output
        orig_variant: Dict[str, Any] = {
            "name": "original",
            "text": original_prose,
        }
        if thought_annotation:
            orig_variant["annotation"] = thought_annotation
        variants.append(orig_variant)

        refined_variant: Dict[str, Any] = {
            "name": "grammar-refined",
            "text": prose,
        }
        if comment_annotation:
            refined_variant["annotation"] = comment_annotation
        variants.append(refined_variant)
    else:
        # Unrefined turn: 'prose' holds the raw text
        orig_variant = {
            "name": "original",
            "text": prose,
        }
        if thought_annotation:
            orig_variant["annotation"] = thought_annotation
        variants.append(orig_variant)

    # Build updated turn dictionary adhering to the new CDM TurnItem spec
    migrated_item: Dict[str, Any] = {
        "id": item["id"],
        "kind": "turn",
        "actor_id": item.get("actor_id", "unknown"),
        "content": variants,
    }

    return migrated_item


def run(config: dict) -> None:
    """
    CDM Migration Pass: Raw JSON TurnItem Content Variant Migration.
    Reads flat JSON files directly without loading Pydantic core models.
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
        f"Inspecting {len(record_files)} JSON records for TurnItem schema migration..."
    )

    migrated_records_count = 0
    migrated_turns_count = 0

    for file_path in tqdm(record_files, desc="Migrating JSON TurnItems"):
        record_uuid = file_path.stem

        if start_uuid and record_uuid < str(start_uuid):
            continue
        if stop_uuid and record_uuid > str(stop_uuid):
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                doc_data = json.load(f)

            items = doc_data.get("items", [])
            doc_modified = False
            updated_items = []

            for item in items:
                if isinstance(item, dict) and item.get("kind") == "turn":
                    new_item = migrate_turn_dict(item)
                    if new_item != item:
                        doc_modified = True
                        migrated_turns_count += 1
                    updated_items.append(new_item)
                else:
                    updated_items.append(item)

            if doc_modified:
                doc_data["items"] = updated_items
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(doc_data, f, indent=2, ensure_ascii=False)
                migrated_records_count += 1

        except Exception as e:
            logger.error(f"Failed migrating JSON document {file_path.name}: {e}")

    logger.info(
        f"✅ TurnItem migration complete. Modified {migrated_turns_count} turns "
        f"across {migrated_records_count} records."
    )
