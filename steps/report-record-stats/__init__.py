import json
import logging
from collections import Counter
from pathlib import Path

from cdm.core import Document

logger = logging.getLogger(__name__)


def run(config: dict) -> None:
    """LilaKosha Telemetry Step: Aggregate and report corpus statistics,

    including breakdowns by safety dials, primary genres, and thematic
    distributions.
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
    turn_counts = []  # Track turn counts per record for distribution stats

    logger.info(
        f"Computing aggregate profile statistics across {total_records} records..."
    )

    for file_path in canvas_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            document = Document.model_validate(data)

            stats = document.meta.stats or {}

            # Update aggregators using the returned dictionary values
            sexual_counts[stats["sexual_axis"]] += 1
            violence_counts[stats["violence_axis"]] += 1
            toxicity_counts[stats["toxicity_axis"]] += 1
            genre_counts[stats["primary_genre"]] += 1

            for theme in stats["themes"]:
                theme_counts[theme] += 1

            turn_counts.append(stats["turn_count"])

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

    # 4. Conversation Turn Distribution
    if turn_counts:
        sorted_turns = sorted(turn_counts)
        total_turns = sum(turn_counts)
        min_turns = sorted_turns[0]
        max_turns = sorted_turns[-1]
        avg_turns = sum(turn_counts) / len(turn_counts)
        median_turns = sorted_turns[len(sorted_turns) // 2]

        logger.info("-" * 60)
        logger.info("💬 CONVERSATION TURN DISTRIBUTION")
        logger.info(f"  Records Analyzed      : {total_records}")
        logger.info(f"  Total Turns           : {total_turns}")
        logger.info(f"  Minimum Turns         : {min_turns}")
        logger.info(f"  Maximum Turns         : {max_turns}")
        logger.info(f"  Average Turns         : {avg_turns:.1f}")
        logger.info(f"  Median Turns          : {median_turns}")

        # Define turn count buckets
        buckets = [
            (1, 10, "1–10"),
            (11, 25, "11–25"),
            (26, 50, "26–50"),
            (51, 100, "51–100"),
            (101, 250, "101–250"),
            (251, 500, "251–500"),
            (501, float("inf"), "501+"),
        ]

        logger.info("  Turn Count Buckets")
        for low, high, label in buckets:
            bucket_count = sum(1 for t in turn_counts if low <= t <= high)
            pct = (bucket_count / total_records) * 100
            logger.info(f"    {label:<18} : {bucket_count:>4} ({pct:.1f}%)")

        logger.info("=" * 60)
