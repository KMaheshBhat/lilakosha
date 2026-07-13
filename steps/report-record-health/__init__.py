import json
import logging
from collections import defaultdict
from pathlib import Path

from cdm.core import Document

logger = logging.getLogger(__name__)


def run(config: dict) -> None:
    """
    LilaKosha Telemetry Step: Assess structural and content health metrics
    across all canvas JSON records on disk using native Pydantic models.

    Supports:
      --hide_anomaly_details true : Mutes granular issue printing.
      --report_breakdown true     : Provides specific check/stage wise breakdown
    """
    processed_vol = Path(config["volumes"]["processed"])
    records_dir = processed_vol / "cdm" / "records"

    if not records_dir.exists():
        logger.error(f"Records directory not found at {records_dir}")
        return

    canvas_files = list(records_dir.glob("*.json"))
    total_records = len(canvas_files)

    if total_records == 0:
        logger.warning("No canvas artifacts found to evaluate.")
        return

    # Extract dynamic configuration parameters passed via pipeline config or CLI flags
    params = config.get("parameters", {})
    hide_anomaly_details = params.get("hide_anomaly_details", False)
    report_breakdown = params.get("report_breakdown", False)

    # Normalize values from the CLI wrapper strings
    if isinstance(hide_anomaly_details, str):
        hide_anomaly_details = hide_anomaly_details.lower() in ("true", "1", "yes")
    if isinstance(report_breakdown, str):
        report_breakdown = report_breakdown.lower() in ("true", "1", "yes")

    healthy_count = 0
    failure_registry = defaultdict(list)

    # Telemetry aggregation frameworks mapped by stage and checks
    stage_breakdown = {
        "refine-characters": {
            "passed": 0,
            "annotation": 0,
            "bot detail": 0,
            "user info": 0,
        },
        "refine-safety-dials": {
            "passed": 0,
            "annotation": 0,
            "sexual axis": 0,
            "violence axis": 0,
            "toxicity axis": 0,
        },
        "refine-genre-theme": {
            "passed": 0,
            "annotation": 0,
            "primary genre": 0,
            "themes": 0,
        },
        "refine-grammar": {"passed": 0, "annotation": 0, "prose": 0},
    }

    total_turns = 0
    converted_turns = 0

    logger.info(
        f"📊 Running read-only telemetry audit across {total_records} records..."
    )

    # --- Standard Evaluation Pass ---
    for file_path in canvas_files:
        uuid_str = file_path.stem

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Authoritative validation against cdm.core.Document
            document = Document.model_validate(data)

            health = document.meta.health or {}

            # Track turn conversion metrics
            turns_metrics = health.get("turns_metrics", {})
            total_turns += turns_metrics.get("total_turns", 0)
            converted_turns += turns_metrics.get("converted_turns", 0)

            # Aggregate breakdown counts
            breakdown_data = health.get("breakdown", {})
            for stage, checks in breakdown_data.items():
                if stage in stage_breakdown:
                    for check_key, passed_check in checks.items():
                        if check_key in stage_breakdown[stage] and passed_check:
                            stage_breakdown[stage][check_key] += 1

            if health.get("is_healthy", False):
                healthy_count += 1
            else:
                failure_registry[uuid_str] = health.get(
                    "issues", ["Unspecified validation issue"]
                )

        except Exception as e:
            failure_registry[uuid_str].append(
                f"Pydantic validation/structural crash: {str(e)}"
            )

    # --- Render Report Output ---
    health_percentage = (
        (healthy_count / total_records) * 100 if total_records > 0 else 0
    )

    logger.info("=" * 60)
    logger.info("📊 LILAKOSHA PIPELINE DATA HEALTH REPORT")
    logger.info("=" * 60)
    logger.info(f"Total Records Evaluated: {total_records}")
    logger.info(f"Healthy Records:         {healthy_count} ({health_percentage:.2f}%)")
    logger.info(f"Defective Records:       {len(failure_registry)}")
    logger.info("=" * 60)

    if report_breakdown:
        logger.info("📈 PIPELINE STAGE BREAKDOWN")
        logger.info("=" * 60)

        # Iteration mirrors the layout requested in the telemetry definition
        for stage, checks in stage_breakdown.items():
            logger.info(f"{stage}")

            passed_count = checks["passed"]
            passed_pct = (
                (passed_count / total_records * 100) if total_records > 0 else 0
            )
            logger.info(
                f" ✅ PASSED              : "
                f"{passed_count}/{total_records} ({passed_pct:.2f}%)"
            )

            for check_name, count in checks.items():
                if check_name == "passed":
                    continue
                check_pct = (count / total_records * 100) if total_records > 0 else 0
                logger.info(
                    f"    {check_name:<20}: {count}/{total_records} ({check_pct:.2f}%)"
                )

            logger.info("-" * 60)

        conversion_percentage = (
            (converted_turns / total_turns * 100) if total_turns > 0 else 0
        )
        remaining_turns = total_turns - converted_turns

        # Conservative local compute estimate: ~5 seconds per turn.
        estimated_seconds = remaining_turns * 5
        estimated_hours = estimated_seconds / 3600

        logger.info(" 📝 Grammar Conversion Summary")
        logger.info(f"    Total Turns             : {total_turns}")
        logger.info(
            f"    Turns Converted         : "
            f"{converted_turns} ({conversion_percentage:.2f}%)"
        )
        logger.info(f"    Turns Remaining         : {remaining_turns}")
        logger.info(
            f"    Estimated Local Compute : {estimated_hours:.1f} hours (@5s/turn)"
        )
        logger.info("=" * 60)

    if failure_registry:
        if hide_anomaly_details:
            logger.info("ℹ️  Anomaly details hidden by configuration parameter flag.")
            logger.info("=" * 60)
        else:
            logger.info("❌ DETECTED ANOMALY REGISTRY BY RECORD ID:")
            for uuid, faults in failure_registry.items():
                logger.info(f"   ↳ UUID: {uuid}")
                for fault in faults:
                    logger.info(f"       - {fault}")
            logger.info("=" * 60)
