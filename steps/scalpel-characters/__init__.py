import logging
from pathlib import Path

from tqdm import tqdm

from cdm.core import Annotation, Document, DocumentStats, PronounSet

logger = logging.getLogger(__name__)


def run(config: dict) -> None:
    """
    LilaKosha Scalpel Pass: Clear Character Synthesis.
    Iterates through standalone Common Document Model (CDM) records, purging synthesized
    character profiles from the timeline, resetting core identities inside the
    authoritative registry back to base tracking defaults, and cleaning historical
    tracking annotations. Supports optional runtime lexical range filtering
    via 'start_uuid' and 'stop_uuid'.
    """
    # 1. Resolve Data Infrastructure Paths
    processed_vol = Path(config["volumes"]["processed"])
    records_dir = processed_vol / "cdm" / "records"

    if not records_dir.exists():
        logger.error(
            f"Records directory not found: {records_dir}. Run ingestion first."
        )
        return

    record_files = sorted(records_dir.glob("*.json"))
    if not record_files:
        logger.warning(f"No canvas records found inside {records_dir}")
        return

    # 2. Extract and Validate Targeted Scope Markers
    params = config.get("parameters", {})
    start_uuid = params.get("start_uuid")
    stop_uuid = params.get("stop_uuid")
    pc_names = params.get("pc_names")
    if isinstance(pc_names, str):
        pc_names = {
            name.strip().lower() for name in pc_names.split(",") if name.strip()
        }
    elif pc_names:
        pc_names = {name.lower() for name in pc_names}
    else:
        pc_names = None

    if start_uuid or stop_uuid:
        logger.info(
            f"🎯 Targeted Scalpel Scope Activated (Character Synthesis):\n"
            f"    - Start Boundary: {start_uuid or '[-∞ Unbound]'}\n"
            f"    - Stop Boundary:  {stop_uuid or '[+∞ Unbound]'}"
        )
    else:
        logger.info(
            "🔬 Scalpel Scope: Global Sweep (No lexical range parameters provided)"
        )

    logger.info(
        f"Inspecting {len(record_files)} records for synthesized character entities..."
    )

    # 3. Main Operational Execution Loop
    purged_count = 0
    skipped_range_count = 0
    skipped_name_count = 0

    for file_path in tqdm(record_files, desc="Purging Character Profiles"):
        record_uuid = file_path.stem  # Extract the tracking UUIDv7 token string

        # Enforce floor constraint boundary
        if start_uuid and record_uuid < str(start_uuid):
            skipped_range_count += 1
            continue

        # Enforce ceiling constraint boundary
        if stop_uuid and record_uuid > str(stop_uuid):
            skipped_range_count += 1
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                document = Document.model_validate_json(f.read())

            if pc_names is not None:
                player = next(
                    (
                        identity
                        for identity in document.meta.identities
                        if identity.is_player_controlled
                    ),
                    None,
                )
                if player is None:
                    continue
                if (player.name or "").strip().lower() not in pc_names:
                    skipped_name_count += 1
                    continue

            # Detect whether character items or refinement annotations exist
            has_timeline_items = any(
                item.kind == "character" for item in document.items
            )
            has_refine_annotations = any(
                anno.kind == "refine-characters"
                for anno in (document.meta.annotations or [])
            )

            if has_timeline_items or has_refine_annotations:
                # A. Purge inline character lore blocks from the transactional timeline
                document.items = [
                    item for item in document.items if item.kind != "character"
                ]

                # B. Reset Authoritative Identity Registry fields
                #    to default fallback states
                bot_id = document.meta.bot_id or "unknown_bot"

                default_pronouns = PronounSet(
                    subjective="they", objective="them", possessive="their"
                )
                for identity in document.meta.identities:
                    if identity.entity_id == "user":
                        identity.name = "User"
                        identity.gender = "unknown"
                        identity.pronouns = default_pronouns
                    elif identity.entity_id == bot_id:
                        identity.name = document.meta.bot_name or "Bot"
                        identity.gender = "unknown"
                        identity.pronouns = default_pronouns

                # C. Filter out historical processing annotations to
                #    prevent tracking pollution
                if document.meta.annotations:
                    document.meta.annotations = [
                        anno
                        for anno in document.meta.annotations
                        if anno.kind != "refine-characters"
                    ]
                else:
                    document.meta.annotations = []

                # D. Append standard surgical tracking trace token to
                #    satisfy audit trails
                scalpel_annotation = Annotation(
                    kind="scalpel-character",
                    content=(
                        "cleared synthesized character timeline profiles and reset "
                        "identity registries via scalpel range"
                    ),
                    reasoning=None,
                )
                document.meta.annotations.append(scalpel_annotation)

                # E. Re-materialize layout metric statistics post-mutation
                turn_count = sum(
                    1 for doc_item in document.items if doc_item.kind == "turn"
                )
                document.meta.stats = DocumentStats(
                    turn_count=turn_count,
                    item_count=len(document.items),
                    character_count=len(document.meta.identities),
                )

                # F. Commit updates cleanly back to disk
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(document.model_dump_json(indent=2))

                purged_count += 1

        except Exception as e:
            logger.error(
                f"Failed surgical profile purge for document {file_path.name}: {e}"
            )

    logger.info("✅ Scalpel character clearance pass complete.")
    logger.info(f"  Purged: {purged_count} records.")
    logger.info(f"  Skipped by UUID range: {skipped_range_count} records.")
    logger.info(f"  Skipped by player-name filter: {skipped_name_count} records.")
