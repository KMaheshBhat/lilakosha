import logging
from datetime import datetime
from pathlib import Path

from datasets import load_dataset
from tqdm import tqdm

from cdm import LedgerIndex
from cdm.core import (
    Annotation,
    CharacterIdentity,
    CharacterItem,
    PronounSet,
    Session,
    SessionMeta,
    TurnItem,
)

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

    # 4. Stream records individually
    for i, raw_record in enumerate(tqdm(dataset, total=sample_limit)):
        if sample_limit is not None and i >= sample_limit:
            break

        bot_id = raw_record.get("bot_id")
        sub_ts = raw_record.get("submission_timestamp")

        # Guard against dirty data rows
        if not bot_id or not sub_ts:
            logger.warning(
                f"Encountered malformed raw record at index row {i}. Skipping."
            )
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
            # tracking file path
            target_uuid = ledger_index.register_record("pippa", native_id)
            target_file = records_dir / f"{target_uuid}.json"

        # 7. Pre-seed Identity Registry placeholders to establish data topology
        #    Full validation/refinement of these fields happens down-stream in
        #    step/refine-characters
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
                entity_id=bot_id,
                name=raw_record.get("bot_name") or "the character",
                gender="unknown",
                pronouns=default_pronouns,
                is_player_controlled=False,
            ),
        ]

        # 8. Construct CDM Session Envelope using your structural Models
        meta_obj = SessionMeta(
            source_identity="PygmalionAI/PIPPA",
            bot_id=bot_id,
            bot_name=raw_record.get("bot_name"),
            ingestion_timestamp=timestamp,
            identities=identities_pool,
            source_record=raw_record,
            annotations=[],
        )

        session_trace = Session(kind="session", meta=meta_obj, items=[])

        # 9. Map Primary Character Initial Persona (character:info Line Item)
        raw_desc = raw_record.get("bot_description") or ""
        if raw_desc.strip():
            character_info = CharacterItem(
                kind="character",
                subkind="info",
                entity_id=bot_id,
                content=raw_desc.strip(),
            )
            session_trace.items.append(character_info)

        # 10. Map Conversational Turns (Linguistic Evidence Line Items)
        for turn in raw_record.get("conversation", []) or []:
            actor_id = "user" if turn.get("is_human") else bot_id
            raw_message = turn.get("message") or ""

            turn_obj = TurnItem(
                kind="turn",
                actor_id=actor_id,
                prose=raw_message.strip(),
            )
            session_trace.items.append(turn_obj)

        # 11. Append the basic lineage trace token
        if session_trace.meta.annotations is None:
            session_trace.meta.annotations = []
        session_trace.meta.annotations.append(
            Annotation(
                kind="ingestion",
                content="created from PIPPA raw record",
            )
        )

        # 12. Write the singular living canvas artifact directly to its slot
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(session_trace.model_dump_json(indent=2))

    logger.info(
        f"✅ Ingestion cycle tracking updated. "
        f"Canvas objects written out to {records_dir}"
    )
