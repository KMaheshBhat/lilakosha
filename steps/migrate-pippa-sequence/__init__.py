import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from tqdm import tqdm

logger = logging.getLogger(__name__)


def migrate_pippa_document(doc_data: Dict[str, Any]) -> bool:
    """
    Ensures a PIPPA document contains a SequenceItem referencing all TurnItems in order.

    Rules:
    - Filters only for PIPPA source records (`source_identity == 'PygmalionAI/PIPPA'`).
    - Collects all item IDs where `kind == 'turn'`.
    - If a session sequence exists, updates its `item_ids` and `data`.
    - If no session sequence exists, creates `seq-conversation-000001`
      with `sequence_for: 'session'`.
    """
    meta = doc_data.get("meta", {})
    source = meta.get("source", {})

    # Rule 1: Restrict strictly to PIPPA ingested records
    if source.get("source_identity") != "PygmalionAI/PIPPA":
        return False

    items: List[Dict[str, Any]] = doc_data.get("items", [])

    # Rule 2: Collect TurnItem IDs in the exact order they appear
    turn_ids = [
        item["id"]
        for item in items
        if isinstance(item, dict) and item.get("kind") == "turn" and "id" in item
    ]

    if not turn_ids:
        return False

    bot_name = source.get("bot_name") or "bot"
    expected_title = f"Conversation with {bot_name}"

    # Search for an existing sequence item representing this session/conversation
    existing_seq_idx = -1
    for idx, item in enumerate(items):
        if isinstance(item, dict) and item.get("kind") == "sequence":
            data = item.get("data", {})
            if (
                data.get("sequence_for") in ("session", "conversation")
                or item.get("id") == "seq-conversation-000001"
            ):
                existing_seq_idx = idx
                break

    doc_modified = False

    if existing_seq_idx >= 0:
        seq_item = items[existing_seq_idx]
        seq_data = seq_item.get("data", {})

        # Check if updates are required for idempotency
        if (
            seq_item.get("item_ids") != turn_ids
            or seq_data.get("sequence_for") != "session"
            or seq_data.get("title") != expected_title
        ):
            seq_item["item_ids"] = turn_ids
            seq_item["data"] = {
                "title": expected_title,
                "sequence_for": "session",
            }
            doc_modified = True
    else:
        # Construct new SequenceItem adhering to the specification
        new_sequence = {
            "id": "seq-conversation-000001",
            "kind": "sequence",
            "item_ids": turn_ids,
            "data": {
                "title": expected_title,
                "sequence_for": "session",
            },
        }
        items.append(new_sequence)
        doc_modified = True

    return doc_modified


def run(config: dict) -> None:
    """
    CDM Migration Pass: PIPPA SequenceItem Generation.
    Iterates over JSON records and adds/updates sequence entries for PIPPA documents.
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
        f"Inspecting {len(record_files)} JSON records for PIPPA sequence migration..."
    )

    migrated_records_count = 0

    for file_path in tqdm(record_files, desc="Migrating PIPPA Sequences"):
        record_uuid = file_path.stem

        if start_uuid and record_uuid < str(start_uuid):
            continue
        if stop_uuid and record_uuid > str(stop_uuid):
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                doc_data = json.load(f)

            if migrate_pippa_document(doc_data):
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(doc_data, f, indent=2, ensure_ascii=False)
                migrated_records_count += 1

        except Exception as e:
            logger.error(f"Failed migrating JSON document {file_path.name}: {e}")

    logger.info(
        f"✅ PIPPA SequenceItem migration complete. "
        f"Updated {migrated_records_count} records."
    )
