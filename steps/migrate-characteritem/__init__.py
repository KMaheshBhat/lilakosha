import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from tqdm import tqdm

logger = logging.getLogger(__name__)


def extract_bot_description(doc_data: Dict[str, Any]) -> Optional[str]:
    """Extracts bot_description from meta.source.source_record if present."""
    meta = doc_data.get("meta")
    if not isinstance(meta, dict):
        return None

    source = meta.get("source")
    if not isinstance(source, dict):
        return None

    source_record = source.get("source_record")
    if not isinstance(source_record, dict):
        return None

    bot_desc = source_record.get("bot_description")
    if isinstance(bot_desc, str) and bot_desc.strip():
        return bot_desc
    return None


def migrate_character_dict(
    item: Dict[str, Any], bot_description: Optional[str]
) -> Dict[str, Any]:
    """
    Transforms a raw CharacterItem dictionary into the new CDM schema with content variants.

    Variant rules:
    - If `content` matches `bot_description` exactly, variant name = "original".
    - Otherwise, variant name = "character-refined".
    - `reasoning` is stored as an `annotation` on the variant if present.
    """
    if item.get("kind") != "character":
        return item

    # Idempotency check: Skip if already migrated
    if "content" in item and isinstance(item["content"], list):
        return item

    raw_content = item.get("content", "")
    reasoning = item.get("reasoning")

    # Determine variant name
    if bot_description is not None and raw_content == bot_description:
        variant_name = "original"
    else:
        variant_name = "character-refined"

    variant: Dict[str, Any] = {
        "name": variant_name,
        "text": raw_content,
    }

    # Attach reasoning as an annotation if present and non-empty
    if isinstance(reasoning, str) and reasoning.strip():
        variant["annotation"] = reasoning.strip()

    migrated_item: Dict[str, Any] = {
        "id": item["id"],
        "kind": "character",
        "entity_id": item.get("entity_id", "unknown"),
        "content": [variant],
    }

    return migrated_item


def run(config: dict) -> None:
    """
    CDM Migration Pass: Raw JSON CharacterItem Content Variant Migration.
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
        f"Inspecting {len(record_files)} JSON records for CharacterItem schema migration..."
    )

    migrated_records_count = 0
    migrated_items_count = 0

    for file_path in tqdm(record_files, desc="Migrating JSON CharacterItems"):
        record_uuid = file_path.stem

        if start_uuid and record_uuid < str(start_uuid):
            continue
        if stop_uuid and record_uuid > str(stop_uuid):
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                doc_data = json.load(f)

            bot_description = extract_bot_description(doc_data)
            items = doc_data.get("items", [])
            doc_modified = False
            updated_items = []

            for item in items:
                if isinstance(item, dict) and item.get("kind") == "character":
                    new_item = migrate_character_dict(item, bot_description)
                    if new_item != item:
                        doc_modified = True
                        migrated_items_count += 1
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
        f"✅ CharacterItem migration complete. Modified {migrated_items_count} items "
        f"across {migrated_records_count} records."
    )
