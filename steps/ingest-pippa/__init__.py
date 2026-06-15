import logging
from datetime import datetime
from pathlib import Path

from datasets import load_dataset
from tqdm import tqdm

from cdm import CharacterEntity, LedgerIndex, Session, SessionMeta, TurnEntity
from cdm.core import Annotation

logger = logging.getLogger(__name__)


def run(config: dict):
    """
    LilaKosha Stage 1: PIPPA Ingestion (Source -> Individual UUIDv7 Canvas Records).
    Utilizes an append-only mapping ledger to implement skip-friendly,
    idempotent ingestion.
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

    # 3. Load Dataset via HF API (Streaming for efficiency)
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

    # 4. Stream records individually without wrapping
    #    them inside a broad macro open block
    for i, raw_record in enumerate(tqdm(dataset, total=sample_limit)):
        if sample_limit is not None and i >= sample_limit:
            break

        bot_id = raw_record.get("bot_id")
        sub_ts = raw_record.get("submission_timestamp")

        # Guard against dirty data rows
        if not bot_id or not sub_ts:
            continue

        # 5. Formulate the explicit key namespace for this source
        native_id = f"{bot_id}_{sub_ts}"

        # 6. Evaluate index state
        target_uuid = ledger_index.get_uuid("pippa", native_id)

        if target_uuid:
            target_file = records_dir / f"{target_uuid}.json"
            # Idempotency Skip condition check: If it exists on disk, we are done
            if target_file.exists():
                continue
        else:
            # If it hasn't been mapped yet, register it and mint a fresh
            # target tracking file path
            target_uuid = ledger_index.register_record("pippa", native_id)
            target_file = records_dir / f"{target_uuid}.json"

        # 7. Construct CDM Session Envelope using your structural Models
        meta_obj = SessionMeta(
            source_identity="PygmalionAI/PIPPA",
            bot_id=bot_id,
            bot_name=raw_record.get("bot_name"),
            ingestion_timestamp=timestamp,
        )

        session_trace = Session(kind="session", meta=meta_obj, children=[])

        # 8. Store the original data cleanly in a dedicated, unedited property
        # Storing raw_record directly on the object scope matching your art perspective
        session_trace.meta.source_record = raw_record

        # 9. Map Primary Character (character:info)
        character_info = CharacterEntity(
            kind="character",
            subkind="info",
            entity_id=bot_id,
            content=raw_record.get("bot_description", "").strip(),
        )
        session_trace.children.append(character_info)

        # 10. Map Conversational Turns (Linguistic Evidence)
        for turn in raw_record.get("conversation", []):
            actor_id = "user" if turn.get("is_human") else bot_id
            turn_obj = TurnEntity(
                kind="turn",
                actor_id=actor_id or "unknown_actor",
                prose=turn.get("message", "").strip(),
            )
            session_trace.children.append(turn_obj)

        # 11. Append the basic lineage trace token
        if not session_trace.meta.annotations:
            session_trace.meta.annotations = []
        session_trace.meta.annotations.append(
            Annotation(
                kind="ingestion",
                content="created from PIPPA raw record",
            )
        )

        # 12. Write the singular living canvas artifact directly to its slot
        # Using model_dump_json with an indent pass ensures high document readability
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(session_trace.model_dump_json(indent=2))

    logger.info(
        f"✅ Ingestion cycle tracking updated. "
        f"Canvas objects written out to {records_dir}"
    )
