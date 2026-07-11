import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from datasets import load_dataset
from tqdm import tqdm

from cdm import LedgerIndex
from cdm.core import (
    Annotation,
    CharacterIdentity,
    CharacterItem,
    Document,
    DocumentMeta,
    DocumentStats,
    PronounSet,
    TurnItem,
)

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


def run(config: dict) -> None:
    """
    LilaKosha Stage 1: PIPPA Ingestion (Source -> Individual CDM Document Records).
    Utilizes an append-only mapping ledger alongside an isolated metadata envelope,
    local unique item identifier schemas, and pure SHA-256 content-addressable keys.
    """
    # 1. Resolve Volumes from Grounded Config
    processed_vol = Path(config["volumes"]["processed"])
    cdm_root = processed_vol / "cdm"
    records_dir = cdm_root / "records"
    records_dir.mkdir(parents=True, exist_ok=True)

    # 2. Instantiate our Cross-Source Master Index
    mapping_file = cdm_root / "mapping.jsonl"
    ledger_index = LedgerIndex(mapping_file)

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    # 3. Load Dataset via HF API (Streaming Mode)
    logger.info("Connecting to Hugging Face Dataset: PygmalionAI/PIPPA")
    dataset = load_dataset(
        "json",
        data_files="hf://datasets/PygmalionAI/PIPPA/pippa_deduped.jsonl",
        split="train",
        streaming=True,
    )

    sample_limit = config["parameters"].get("limit", None)
    logger.info(
        f"Processing up to {sample_limit} "
        f"records against data layer target: {records_dir}"
    )

    # 4. Stream records individually
    for i, raw_record in enumerate(tqdm(dataset, total=sample_limit)):
        if sample_limit is not None and i >= sample_limit:
            break

        bot_id = raw_record.get("bot_id")
        sub_ts = raw_record.get("submission_timestamp")

        # Guard against dirty data rows
        if not bot_id or sub_ts is None:
            logger.warning(
                f"Encountered malformed raw record at index row {i}. Skipping."
            )
            continue

        # 5. Formulate the pure content-addressed SHA-256 native key
        content_hash = compute_content_address(raw_record)

        # 6. Evaluate index state using the pure SHA-256 hash
        target_uuid = ledger_index.get_uuid("pippa", content_hash)

        if target_uuid:
            target_file = records_dir / f"{target_uuid}.json"
            # Idempotency Skip condition check: If it exists on disk, we are done
            if target_file.exists():
                continue
        else:
            # Package source-specific markers inside an isolated dict tracking envelope
            metadata_payload: Dict[str, Any] = {
                "bot_id": str(bot_id),
                "submission_timestamp": str(sub_ts),
            }

            # Register it cleanly into the ledger
            target_uuid = ledger_index.register_record(
                source="pippa",
                native_id=content_hash,
                meta=metadata_payload,
            )
            target_file = records_dir / f"{target_uuid}.json"

        # 7. Pre-seed Identity Registry placeholders to establish data topology
        # Typo correction: Pydantic base model core uses possessive
        default_pronouns = PronounSet(
            subjective="they", objective="them", possessive="their"
        )

        identities_pool = [
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

        # 8. Construct CDM Document Envelope using structural Models
        meta_obj = DocumentMeta(
            source_identity="PygmalionAI/PIPPA",
            bot_id=str(bot_id),
            bot_name=raw_record.get("bot_name"),
            ingestion_timestamp=timestamp,
            identities=identities_pool,
            source_record=raw_record,
            annotations=[],
            stats=DocumentStats(),
        )

        document_trace = Document(
            id=target_uuid, kind="document", meta=meta_obj, items=[]
        )

        # Track internal counters for local deterministic unique identifiers
        character_item_counter = 0
        turn_item_counter = 0

        # 9. Map Primary Character Initial Persona (character Line Item)
        # Note: subkind parameter has been removed entirely per CDM specifications
        raw_desc = raw_record.get("bot_description") or ""
        if raw_desc.strip():
            character_item_counter += 1
            character_info = CharacterItem(
                id=f"character-{character_item_counter:06d}",
                kind="character",
                entity_id=str(bot_id),
                content=str(raw_desc.strip()),
            )
            document_trace.items.append(character_info)

        # 10. Map Conversational Turns (Linguistic Evidence Line Items)
        for turn in raw_record.get("conversation", []) or []:
            actor_id = "user" if turn.get("is_human") else str(bot_id)
            raw_message = turn.get("message") or ""

            turn_item_counter += 1
            turn_obj = TurnItem(
                id=f"turn-{turn_item_counter:06d}",
                kind="turn",
                actor_id=actor_id,
                prose=str(raw_message.strip()),
            )
            document_trace.items.append(turn_obj)

        # 11. Append the basic lineage trace token to meta annotations
        if document_trace.meta.annotations is None:
            document_trace.meta.annotations = []
        document_trace.meta.annotations.append(
            Annotation(
                kind="ingestion",
                content="created from PIPPA raw record",
            )
        )

        # 12. Materialize basic document runtime statistics metrics block
        document_trace.meta.stats = DocumentStats(
            turn_count=turn_item_counter,
            item_count=len(document_trace.items),
            character_count=len(identities_pool),
        )

        # 13. Write the singular living canvas artifact directly to its slot
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(document_trace.model_dump_json(indent=2))

    logger.info(
        f"✅ Ingestion cycle tracking updated. "
        f"Canvas objects written out to {records_dir}"
    )
