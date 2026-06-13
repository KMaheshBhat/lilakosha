import logging
import os
from datetime import datetime

from datasets import load_dataset
from tqdm import tqdm

# Import your unified CDM models
from cdm import CharacterEntity, Session, SessionMeta, TurnEntity

logger = logging.getLogger(__name__)


def run(config: dict):
    """
    LilaKosha Stage 1: PIPPA Ingestion (Source -> Unified CDM Ledger).
    Aggregates traces into a single timestamped JSONL file in the CDM root.
    """
    # 1. Resolve Volumes from Grounded Config
    processed_vol = config["volumes"]["processed"]
    cdm_root = os.path.join(processed_vol, "cdm")
    os.makedirs(cdm_root, exist_ok=True)
    # 2. Generate Ingestion Artifact Name (YYYYMMDDHHmmSS)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    ledger_file = os.path.join(cdm_root, f"{timestamp}.jsonl")
    # 3. Load Dataset via HF API (Streaming for efficiency)
    logger.info("Connecting to Hugging Face Dataset: PygmalionAI/PIPPA")
    dataset = load_dataset(
        "json",
        data_files="hf://datasets/PygmalionAI/PIPPA/pippa_deduped.jsonl",
        split="train",
        streaming=True,
    )
    sample_limit = config["parameters"].get("limit", None)
    logger.info(f"Ingesting {sample_limit} records into unified ledger: {ledger_file}")
    # 4. Open the Ledger File for a single batch-write session
    with open(ledger_file, "w", encoding="utf-8") as f:
        for i, raw_record in enumerate(tqdm(dataset, total=sample_limit)):
            if sample_limit is not None and i >= sample_limit:
                break
            # 5. Construct CDM Session Envelope using Pydantic Models
            meta_obj = SessionMeta(
                source_identity="PygmalionAI/PIPPA",
                bot_id=raw_record.get("bot_id"),
                bot_name=raw_record.get("bot_name"),
                ingestion_timestamp=timestamp,
            )
            session_trace = Session(kind="session", meta=meta_obj, children=[])
            # 6. Map Primary Character (character:info)
            character_info = CharacterEntity(
                kind="character",
                subkind="info",
                entity_id=raw_record.get("bot_id") or "unknown_bot",
                content=raw_record.get("bot_description", "").strip(),
            )
            session_trace.children.append(character_info)
            # 7. Map Conversational Turns (Linguistic Evidence)
            for turn in raw_record.get("conversation", []):
                actor_id = "user" if turn.get("is_human") else raw_record.get("bot_id")
                turn_obj = TurnEntity(
                    kind="turn",
                    actor_id=actor_id or "unknown_actor",
                    prose=turn.get("message", "").strip(),
                )
                session_trace.children.append(turn_obj)
            # 8. Write record line-by-line (True JSONL format)
            # model_dump_json() outputs a fast, un-indented single-line string
            f.write(session_trace.model_dump_json() + "\n")
    logger.info(f"✅ Successfully aggregated records into {ledger_file}")
