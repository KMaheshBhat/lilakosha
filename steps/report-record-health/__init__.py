import json
import logging
from collections import defaultdict
from pathlib import Path

from cdm.core import Session

logger = logging.getLogger(__name__)


def run(config: dict) -> None:
    """
    LilaKosha Telemetry Step: Assess structural and content health metrics
    across all canvas JSON records on disk using native Pydantic models.

    Supports:
      --reset_health true         : Clears 'healthy' tracking flags to force retries.
      --audit_only true           : Run full health report in-memory without disk writes
                                    (Perfect for clean dashboarding via watch -n).
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
    reset_health = params.get("reset_health", False)
    audit_only = params.get("audit_only", False)
    report_breakdown = params.get("report_breakdown", False)

    # Normalize values from the CLI wrapper strings
    if isinstance(hide_anomaly_details, str):
        hide_anomaly_details = hide_anomaly_details.lower() in ("true", "1", "yes")
    if isinstance(reset_health, str):
        reset_health = reset_health.lower() in ("true", "1", "yes")
    if isinstance(audit_only, str):
        audit_only = audit_only.lower() in ("true", "1", "yes")
    if isinstance(report_breakdown, str):
        report_breakdown = report_breakdown.lower() in ("true", "1", "yes")

    # --- Mode 1: Full Health State Reset ---
    if reset_health:
        logger.info(
            f"🔄 RESET MODE ACTIVATED: Clearing health states across "
            f"{total_records} records to force pipeline retries..."
        )
        for file_path in canvas_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                if "meta" in raw_data and isinstance(raw_data["meta"], dict):
                    # Pop the healthy key entirely so it drops
                    # back to Schema default (None)
                    raw_data["meta"].pop("healthy", None)
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(raw_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error(
                    f"Failed to clear health tag on file {file_path.stem}: {str(e)}"
                )
        logger.info(
            "✅ All health tracking flags have been cleared. Exiting reset phase."
        )
        return

    healthy_count = 0
    failure_registry = defaultdict(list)
    stage_stats = {
        "refine-characters": defaultdict(int),
        "refine-safety-dials": defaultdict(int),
        "refine-genre-theme": defaultdict(int),
        "refine-grammar": defaultdict(int),
    }

    if audit_only:
        logger.info(
            f"📊 Running read-only telemetry audit across {total_records} records..."
        )
    else:
        logger.info(
            f"Auditing and mutating data health parameters across "
            f"{total_records} records..."
        )

    # --- Mode 2 & 3: Standard Mutation / Audit Evaluation Pass ---
    for file_path in canvas_files:
        uuid_str = file_path.stem
        issues = []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Authoritative validation against cdm.core.Session
            session = Session.model_validate(data)
            meta = session.meta
            items = session.items or []
            annotations = meta.annotations or []

            # Extract kinds from Pydantic Annotation objects safely
            annotation_kinds = {
                anno.kind for anno in annotations if hasattr(anno, "kind")
            }

            # --- Rule Group 1: refine-characters ---
            if "refine-characters" not in annotation_kinds:
                issues.append("Missing 'refine-characters' annotation")
                stage_stats["refine-characters"]["issue:annotation"] += 1
            has_bot_detail = any(
                item.kind == "character"
                and getattr(item, "subkind", None) == "detail"
                and getattr(item, "entity_id", None) != "user"
                for item in items
            )
            if not has_bot_detail:
                issues.append(
                    "Missing bot character details (subkind=detail, entity_id!=user)"
                )
                stage_stats["refine-characters"]["issue:bot_detail"] += 1
            has_user_info = any(
                item.kind == "character"
                and getattr(item, "subkind", None) == "info"
                and getattr(item, "entity_id", None) == "user"
                for item in items
            )
            if not has_user_info:
                issues.append(
                    "Missing user profiling info (subkind=info, entity_id=user)"
                )
                stage_stats["refine-characters"]["issue:user_info"] += 1
            if (
                "refine-characters" in annotation_kinds
                and has_bot_detail
                and has_user_info
            ):
                stage_stats["refine-characters"]["passed"] += 1

            # --- Rule Group 2: refine-safety-dials ---
            if "refine-safety-dials" not in annotation_kinds:
                issues.append("Missing 'refine-safety-dials' annotation")
                stage_stats["refine-safety-dials"]["issue:annotation"] += 1
            if meta.sexual_axis is None:
                issues.append("Unset 'meta.sexual_axis'")
                stage_stats["refine-safety-dials"]["issue:sexual_axis"] += 1
            if meta.violence_axis is None:
                issues.append("Unset 'meta.violence_axis'")
                stage_stats["refine-safety-dials"]["issue:violence_axis"] += 1
            if meta.toxicity_axis is None:
                issues.append("Unset 'meta.toxicity_axis'")
                stage_stats["refine-safety-dials"]["issue:toxicity_axis"] += 1
            if (
                "refine-safety-dials" in annotation_kinds
                and meta.sexual_axis is not None
                and meta.violence_axis is not None
                and meta.toxicity_axis is not None
            ):
                stage_stats["refine-safety-dials"]["passed"] += 1

            # --- Rule Group 3: refine-genre-theme ---
            if "refine-genre-theme" not in annotation_kinds:
                issues.append("Missing 'refine-genre-theme' annotation")
                stage_stats["refine-genre-theme"]["issue:annotation"] += 1
            if meta.primary_genre is None:
                issues.append("Unset 'meta.primary_genre'")
                stage_stats["refine-genre-theme"]["issue:primary_genre"] += 1
            if not meta.themes:  # Checks for None or empty list
                issues.append("Unset or empty 'meta.themes'")
                stage_stats["refine-genre-theme"]["issue:themes"] += 1
            if (
                "refine-genre-theme" in annotation_kinds
                and meta.primary_genre is not None
                and meta.themes
            ):
                stage_stats["refine-genre-theme"]["passed"] += 1

            # --- Rule Group 4: refine-grammar ---
            if "refine-grammar" not in annotation_kinds:
                issues.append("Missing 'refine-grammar' annotation")
                stage_stats["refine-grammar"]["issue:annotation"] += 1
            # Verify that every turn item correctly retains its original_prose baseline
            missing_lineage_turns = sum(
                1
                for item in items
                if item.kind == "turn" and getattr(item, "original_prose", None) is None
            )
            if missing_lineage_turns > 0:
                issues.append(
                    f"Grammar tracking defect: {missing_lineage_turns} turn items are"
                    " missing 'original_prose'"
                )
                stage_stats["refine-grammar"]["issue:prose"] += 1
            if "refine-grammar" in annotation_kinds and missing_lineage_turns == 0:
                stage_stats["refine-grammar"]["passed"] += 1

            # --- Consolidation State Sync ---
            if not issues:
                healthy_count += 1
                session.meta.healthy = True
            else:
                failure_registry[uuid_str] = issues
                session.meta.healthy = False

            # Persist mutations back to disk ONLY if audit-only mode is deactivated
            if not audit_only:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(
                        session.model_dump(mode="json"), f, indent=2, ensure_ascii=False
                    )

        except Exception as e:
            failure_registry[uuid_str].append(
                f"Pydantic validation/structural crash: {str(e)}"
            )

            # If the session model instantiation crashed entirely,
            # fall back to dirty JSON patch
            if not audit_only:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        raw_data = json.load(f)
                    if "meta" in raw_data and isinstance(raw_data["meta"], dict):
                        raw_data["meta"]["healthy"] = False
                        with open(file_path, "w", encoding="utf-8") as f:
                            json.dump(raw_data, f, indent=2, ensure_ascii=False)
                except Exception as backup_err:
                    logger.error(
                        f"Critical write-back block on file "
                        f"{uuid_str}: {str(backup_err)}"
                    )

    # --- Render Report Output ---
    health_percentage = (healthy_count / total_records) * 100

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
        for stage, stats in stage_stats.items():
            logger.info(f"{stage}")
            passed = stats.get("passed", 0)
            logger.info(
                f"   ✅ PASSED              : {passed}/{total_records} "
                f"({passed / total_records * 100:.2f}%)"
            )
            for check, failures in sorted(stats.items()):
                if check == "passed":
                    continue
                check_name = check.replace("issue:", "").replace("_", " ")
                successes = total_records - failures
                logger.info(
                    f"   {check_name:<20}: "
                    f"{successes}/{total_records} "
                    f"({successes / total_records * 100:.2f}%)"
                )
            logger.info("-" * 60)

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
