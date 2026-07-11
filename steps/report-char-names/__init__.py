import json
import logging
from pathlib import Path

from cdm.core import Document

logger = logging.getLogger(__name__)


def run(config: dict) -> None:
    """
    LilaKosha Telemetry Step: Report character names and genders
    from all canvas JSON records.
    """
    processed_vol = Path(config["volumes"]["processed"])
    records_dir = processed_vol / "cdm" / "records"

    if not records_dir.exists():
        logger.error(f"Records directory not found at {records_dir}")
        return

    canvas_files = list(records_dir.glob("*.json"))
    total_records = len(canvas_files)

    if total_records == 0:
        logger.warning("No canvas artifacts found to analyze.")
        return

    logger.info(
        f"Extracting character names and genders across {total_records} records..."
    )

    # Print header
    logger.info("UUID\tPLAYER_NAME\tPLAYER_GENDER\tBOT_NAME\tBOT_GENDER")

    for file_path in canvas_files:
        uuid = file_path.stem

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            document = Document.model_validate(data)
            identities = document.meta.identities

            # Find player-controlled identity (user)
            player_identity = next(
                (identity for identity in identities if identity.is_player_controlled),
                None,
            )

            # Find bot identity (not player-controlled)
            bot_identity = next(
                (
                    identity
                    for identity in identities
                    if not identity.is_player_controlled
                ),
                None,
            )

            player_name = player_identity.name if player_identity else "N/A"
            player_gender = player_identity.gender if player_identity else "N/A"
            bot_name = bot_identity.name if bot_identity else "N/A"
            bot_gender = bot_identity.gender if bot_identity else "N/A"

            logger.info(
                f"{uuid}\t{player_name}\t{player_gender}\t{bot_name}\t{bot_gender}"
            )

        except Exception:
            # Skip unparseable files during stats aggregation to avoid
            # crashing the telemetry loop
            logger.info(f"{uuid}\tERROR\tERROR\tERROR\tERROR")
