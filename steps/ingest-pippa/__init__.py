import json
import logging
import os
from datetime import datetime

from datasets import load_dataset
from tqdm import tqdm

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
    sample_limit = 10
    logger.info(f"Ingesting {sample_limit} records into unified ledger: {ledger_file}")
    # 4. Open the Ledger File for a single batch-write session
    with open(ledger_file, "w", encoding="utf-8") as f:
        for i, raw_record in enumerate(tqdm(dataset, total=sample_limit)):
            if i >= sample_limit:
                break
            # 5. Construct CDM Session Envelope
            session_trace = {
                "kind": "session",
                "meta": {
                    "source_identity": "PygmalionAI/PIPPA",
                    "bot_id": raw_record.get("bot_id"),
                    "bot_name": raw_record.get("bot_name"),
                    "ingestion_timestamp": timestamp,
                },
                "children": [],
            }
            # 6. Map Primary Character (character:info)
            session_trace["children"].append(
                {
                    "kind": "character",
                    "subkind": "info",
                    "entity_id": raw_record.get("bot_id"),
                    "content": raw_record.get("bot_description", "").strip(),
                }
            )
            # 7. Map Conversational Turns (Linguistic Evidence)
            for turn in raw_record.get("conversation", []):
                session_trace["children"].append(
                    {
                        "kind": "turn",
                        "actor_id": "user"
                        if turn["is_human"]
                        else raw_record.get("bot_id"),
                        "prose": turn["message"].strip(),
                    }
                )
            # 8. Write record line-by-line (True JSONL format)
            f.write(json.dumps(session_trace) + "\n")
    logger.info(f"✅ Successfully aggregated {sample_limit} records into {ledger_file}")
