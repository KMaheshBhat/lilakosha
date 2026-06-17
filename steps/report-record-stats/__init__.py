import json
import logging
from collections import Counter
from pathlib import Path

from cdm.core import Session

logger = logging.getLogger(__name__)


def run(config: dict) -> None:
    """
    LilaKosha Telemetry Step: Aggregate and report corpus statistics,
    including breakdowns by safety dials, primary genres, and thematic distributions.
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

    # Initialize aggregators
    sexual_counts = Counter()
    violence_counts = Counter()
    toxicity_counts = Counter()
    genre_counts = Counter()
    theme_counts = Counter()

    logger.info(
        f"Computing aggregate profile statistics across {total_records} records..."
    )

    for file_path in canvas_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            session = Session.model_validate(data)
            meta = session.meta

            # Extract and count safety classifications (handle Enums safely via .value)
            sexual_counts[meta.sexual_axis.value if meta.sexual_axis else "Unset"] += 1
            violence_counts[
                meta.violence_axis.value if meta.violence_axis else "Unset"
            ] += 1
            toxicity_counts[
                meta.toxicity_axis.value if meta.toxicity_axis else "Unset"
            ] += 1

            # Extract and count primary genres
            genre_counts[
                meta.primary_genre.value if meta.primary_genre else "Unset"
            ] += 1

            # Extract and count themes
            if meta.themes:
                for theme in meta.themes:
                    theme_counts[theme] += 1
            else:
                theme_counts["[No Themes Assigned]"] += 1

        except Exception:
            # Skip unparseable files during stats aggregation to avoid
            # crashing the telemetry loop
            continue

    # --- Render Statistical Breakdown Report ---
    logger.info("=" * 60)
    logger.info("📊 LILAKOSHA DATASET DISTRIBUTION REPORT")
    logger.info("=" * 60)
    logger.info(f"Total Portfolio Volume: {total_records} records")
    logger.info("=" * 60)

    # 1. Safety Axis Sub-Reports
    logger.info("🔒 SAFETY DIAL DISTRIBUTIONS")
    logger.info("  [Sexual Axis]")
    for val, count in sexual_counts.most_common():
        pct = (count / total_records) * 100
        logger.info(f"    - {val:<15} : {count:>4} ({pct:.1f}%)")

    logger.info("  [Violence Axis]")
    for val, count in violence_counts.most_common():
        pct = (count / total_records) * 100
        logger.info(f"    - {val:<15} : {count:>4} ({pct:.1f}%)")

    logger.info("  [Toxicity Axis]")
    for val, count in toxicity_counts.most_common():
        pct = (count / total_records) * 100
        logger.info(f"    - {val:<15} : {count:>4} ({pct:.1f}%)")
    logger.info("-" * 60)

    # 2. Genre Distribution
    logger.info("🎭 PRIMARY GENRE MIX")
    for genre, count in genre_counts.most_common():
        pct = (count / total_records) * 100
        logger.info(f"  - {genre:<22} : {count:>4} ({pct:.1f}%)")
    logger.info("-" * 60)

    # 3. Top Theme Distribution
    logger.info("🏷️  TOP THEMATIC TAGS (FREQUENCY)")
    # Show top 25 themes for clean output readability
    for theme, count in theme_counts.most_common(25):
        pct = (count / total_records) * 100
        logger.info(f"  - {theme:<26} : {count:>4} ({pct:.1f}%)")

    if len(theme_counts) > 25:
        logger.info(f"  ... and {len(theme_counts) - 25} other unique themes.")
    logger.info("=" * 60)
