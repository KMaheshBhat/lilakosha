import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from tqdm import tqdm

from cdm import LedgerIndex
from cdm.core import (
    Annotation,
    CharacterIdentity,
    CharacterItem,
    ContentVariant,
    Document,
    DocumentMeta,
    PronounSet,
    SequenceItem,
    TurnItem,
)
from cdm.meta import update_meta

logger = logging.getLogger(__name__)


def compute_content_address(raw_record: dict) -> str:
    """
    Computes a deterministic SHA-256 fingerprint by serializing the raw dictionary
    to a standardized, key-sorted, compact JSON string representation.
    """
    standardized_bytes = json.dumps(
        raw_record, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")

    return hashlib.sha256(standardized_bytes).hexdigest()


def count_lines(file_path: Path) -> int:
    """Helper to count total lines in JSONL for accurate tqdm progress display."""
    with open(file_path, "r", encoding="utf-8") as f:
        return sum(1 for _ in f)


def run(config: dict) -> None:
    """
    LilaKosha Stage 1: PIPPA Ingestion (Source -> Individual CDM Document Records).
    Utilizes an append-only mapping ledger alongside an isolated metadata envelope,
    local unique item identifier schemas, and pure SHA-256 content-addressable keys.
    """
    # 1. Resolve Volumes from Grounded Config
    raw_vol = Path(config["volumes"]["raw"])
    pippa_file = raw_vol / "raw" / "PygmalionAI" / "PIPPA" / "pippa_deduped.jsonl"

    if not pippa_file.exists():
        raise FileNotFoundError(
            f"Raw PIPPA dataset not found at {pippa_file}. "
            "Ensure the 'acquire' step has executed successfully."
        )

    processed_vol = Path(config["volumes"]["processed"])
    cdm_root = processed_vol / "cdm"
    records_dir = cdm_root / "records"
    records_dir.mkdir(parents=True, exist_ok=True)

    # 2. Instantiate Cross-Source Master Index
    mapping_file = cdm_root / "mapping.jsonl"
    ledger_index = LedgerIndex(mapping_file)

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    sample_limit = config["parameters"].get("limit", None)
    logger.info(
        f"Processing local raw PIPPA dataset from {pippa_file} "
        f"(limit: {sample_limit}) target: {records_dir}"
    )

    total_lines = count_lines(pippa_file)
    max_count = (
        min(total_lines, sample_limit) if sample_limit is not None else total_lines
    )

    # 3. Stream records individually from local raw JSONL file
    with open(pippa_file, "r", encoding="utf-8") as f:
        for i, line in enumerate(tqdm(f, total=max_count)):
            if sample_limit is not None and i >= sample_limit:
                break

            line_str = line.strip()
            if not line_str:
                continue

            try:
                raw_record = json.loads(line_str)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON at row {i}. Skipping.")
                continue

            bot_id = raw_record.get("bot_id")
            sub_ts = raw_record.get("submission_timestamp")

            # Guard against dirty data rows
            if not bot_id or sub_ts is None:
                logger.warning(
                    f"Encountered malformed raw record at index row {i}. Skipping."
                )
                continue

            # 4. Formulate pure content-addressed SHA-256 native key
            content_hash = compute_content_address(raw_record)

            # 5. Evaluate index state using pure SHA-256 hash
            target_uuid = ledger_index.get_uuid("pippa", content_hash)

            if target_uuid:
                target_file = records_dir / f"{target_uuid}.json"
                # Idempotency check: If record exists on disk, skip processing
                if target_file.exists():
                    continue
            else:
                # Package source-specific markers inside metadata payload
                metadata_payload: Dict[str, Any] = {
                    "bot_id": str(bot_id),
                    "submission_timestamp": str(sub_ts),
                }

                # Register record in mapping index
                target_uuid = ledger_index.register_record(
                    source="pippa",
                    native_id=content_hash,
                    meta=metadata_payload,
                )
                target_file = records_dir / f"{target_uuid}.json"

            # 6. Establish Identity Registry placeholders
            default_pronouns = PronounSet(
                subjective="they", objective="them", possessive="their"
            )

            identities = [
                CharacterIdentity(
                    entity_id="user",
                    name="User",
                    gender="unknown",
                    pronouns=default_pronouns,
                    is_player_controlled=True,
                ),
                CharacterIdentity(
                    entity_id=str(bot_id),
                    name=raw_record.get("bot_name") or "the character",
                    gender="unknown",
                    pronouns=default_pronouns,
                    is_player_controlled=False,
                ),
            ]

            # 7. Construct CDM Document Envelope
            meta_obj = DocumentMeta(
                source={
                    "source_identity": "PygmalionAI/PIPPA",
                    "bot_id": str(bot_id),
                    "bot_name": raw_record.get("bot_name"),
                    "ingestion_timestamp": timestamp,
                    "source_record": raw_record,
                    "identities": identities,
                },
                health={},
                stats={},
                annotations=[],
            )

            document = Document(
                id=target_uuid,
                kind="document",
                meta=meta_obj,
                items=[],
            )

            # Counters for item identifiers
            character_item_counter = 0
            turn_item_counter = 0

            # 8. Map Initial Character Persona
            raw_desc = raw_record.get("bot_description") or ""
            if raw_desc.strip():
                character_item_counter += 1
                character_info = CharacterItem(
                    id=f"character-{character_item_counter:06d}",
                    kind="character",
                    entity_id=str(bot_id),
                    content=[
                        ContentVariant(
                            name="original",
                            text=str(raw_desc.strip()),
                        )
                    ],
                )
                document.items.append(character_info)

            # 9. Map Conversational Turns
            turn_item_ids: List[str] = []
            for turn in raw_record.get("conversation", []) or []:
                actor_id = "user" if turn.get("is_human") else str(bot_id)
                raw_message = turn.get("message") or ""

                turn_item_counter += 1
                turn_id = f"turn-{turn_item_counter:06d}"
                turn_obj = TurnItem(
                    id=turn_id,
                    kind="turn",
                    actor_id=actor_id,
                    content=[
                        ContentVariant(
                            name="original",
                            text=str(raw_message.strip()),
                        )
                    ],
                )
                document.items.append(turn_obj)
                turn_item_ids.append(turn_id)

            # 10. Append SequenceItem for ordered conversation timeline
            if turn_item_ids:
                conversation_sequence = SequenceItem(
                    id="seq-conversation-000001",
                    kind="sequence",
                    item_ids=turn_item_ids,
                    data={
                        "title": (
                            f"Conversation with {raw_record.get('bot_name') or 'bot'}"
                        ),
                        "sequence_for": "session",
                    },
                )
                document.items.append(conversation_sequence)

            # 11. Append lineage annotation
            if document.meta.annotations is None:
                document.meta.annotations = []
            document.meta.annotations.append(
                Annotation(
                    kind="ingestion",
                    content="created from PIPPA raw record",
                )
            )

            # 12. Update meta state (health, stats, resolved properties)
            update_meta(document)

            # 13. Write JSON artifact to target path
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(document.model_dump_json(indent=2, by_alias=True))

    logger.info(
        f"✅ Ingestion cycle tracking updated. "
        f"Canvas objects written out to {records_dir}"
    )
