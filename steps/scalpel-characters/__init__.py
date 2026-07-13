import logging
from pathlib import Path

from tqdm import tqdm

from cdm.core import Document, ResolvedMeta
from cdm.meta import add_annotation, remove_annotation, update_meta

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

            resolved = document.meta.resolved or ResolvedMeta()
            identities = resolved.identities or []

            if pc_names is not None:
                player = next(
                    (
                        identity
                        for identity in identities
                        if identity.is_player_controlled
                    ),
                    None,
                )
                if player is None:
                    continue
                if (player.name or "").strip().lower() not in pc_names:
                    skipped_name_count += 1
                    continue

            # Detect whether character items, refinement annotations,
            # or resolved identities exist
            has_timeline_items = any(
                item.kind == "character" for item in document.items
            )

            has_refine_annotations = any(
                anno.kind == "refine-characters"
                for anno in (document.meta.annotations or [])
            )

            has_resolved_identities = bool(identities)

            if has_timeline_items or has_refine_annotations or has_resolved_identities:
                # A. Purge inline character lore blocks from the transactional timeline
                document.items = [
                    item for item in document.items if item.kind != "character"
                ]

                # B. Clear synthesized identity registry
                if document.meta.resolved:
                    document.meta.resolved.identities = []

                # C. Remove refinement annotation
                remove_annotation(document, "refine-characters")

                # D. Append audit trace
                add_annotation(
                    document,
                    kind="scalpel-characters",
                    content=(
                        "cleared synthesized character timeline profiles and reset "
                        "identity registries via scalpel range"
                    ),
                )

                # E. Re-materialize metadata
                update_meta(document)

                # F. Commit updates
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
