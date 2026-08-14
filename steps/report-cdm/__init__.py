import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tqdm import tqdm

from cdm.core import ContentVariant, Document

logger = logging.getLogger(__name__)

# ==========================================
# Constants
# ==========================================

G1_HEALTH_DENOMINATORS = {
    "refine-cdm-language": None,
    "refine-cdm-html-to-markdown": "lemonilia/roleplaying-forums-raw",
    "refine-pippa-characters": "PygmalionAI/PIPPA",
    "refine-pippa-safety-dials": "PygmalionAI/PIPPA",
    "refine-pippa-genre-theme": "PygmalionAI/PIPPA",
    "refine-pippa-grammar": "PygmalionAI/PIPPA",
}

VARIANT_ITEM_KINDS = {
    "world",
    "character",
    "summary",
    "narrative",
    "turn",
}

STRUCTURED_ITEM_KINDS = {
    "categorization",
    "sequence",
}

TURN_BUCKETS = [
    (1, 10, "1–10"),
    (11, 25, "11–25"),
    (26, 50, "26–50"),
    (51, 100, "51–100"),
    (101, 250, "101–250"),
    (251, 500, "251–500"),
    (501, float("inf"), "501+"),
]


# ==========================================
# Shared Infrastructure
# ==========================================


def _resolve_records_dir(config: dict) -> Path:
    processed_vol = Path(config["volumes"]["processed"])
    return processed_vol / "cdm" / "records"


def _iter_record_files(
    records_dir: Path,
    start_uuid: Optional[str],
    stop_uuid: Optional[str],
):
    files = sorted(records_dir.glob("*.json"))
    for file_path in files:
        uuid = file_path.stem
        if start_uuid and uuid < start_uuid:
            continue
        if stop_uuid and uuid > stop_uuid:
            continue
        yield file_path


def _load_document(
    file_path: Path,
) -> Tuple[Optional[Document], Optional[str]]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return Document.model_validate_json(f.read()), None
    except Exception as exc:
        return None, str(exc)


def _extract_source_identity(document: Document) -> str:
    source_info = document.meta.source or {}
    return source_info.get("source_identity") or source_info.get("source") or "unknown"


# ==========================================
# Reporter Classes
# ==========================================


class _ItemReporter:
    def __init__(self) -> None:
        self.kind_counts: Counter[str] = Counter()
        self.variant_counts: Dict[str, Counter[str]] = defaultdict(Counter)
        self.structured_counts: Dict[str, Counter[str]] = defaultdict(Counter)
        self.content_shape_counts: Dict[str, Counter[str]] = defaultdict(Counter)
        self.total_items_inspected = 0
        self.malformed_items = 0

    def update(self, document: Document) -> None:
        for item in document.items:
            kind = getattr(item, "kind", None) or "<missing_kind>"
            self.kind_counts[kind] += 1
            self.total_items_inspected += 1

            if kind in STRUCTURED_ITEM_KINDS:
                self.content_shape_counts[kind]["structured"] += 1

                if kind == "categorization":
                    category = getattr(item, "category", None)
                    if isinstance(category, str) and category.strip():
                        self.structured_counts[kind][category] += 1
                    else:
                        self.malformed_items += 1
                        self.content_shape_counts[kind]["malformed"] += 1

                elif kind == "sequence":
                    seq_data = getattr(item, "data", None)
                    if isinstance(seq_data, dict):
                        sequence_for = seq_data.get("sequence_for")
                        if isinstance(sequence_for, str) and sequence_for.strip():
                            self.structured_counts[kind][sequence_for] += 1
                        else:
                            self.malformed_items += 1
                            self.content_shape_counts[kind]["malformed"] += 1
                    else:
                        self.malformed_items += 1
                        self.content_shape_counts[kind]["malformed"] += 1

                continue

            if kind in VARIANT_ITEM_KINDS:
                content = getattr(item, "content", None)

                if isinstance(content, list):
                    self.content_shape_counts[kind]["variants"] += 1

                    for variant in content:
                        if not isinstance(variant, ContentVariant):
                            self.malformed_items += 1
                            self.content_shape_counts[kind]["malformed"] += 1
                            continue

                        name = getattr(variant, "name", None)
                        if isinstance(name, str) and name.strip():
                            self.variant_counts[kind][name] += 1
                        else:
                            self.malformed_items += 1
                            self.content_shape_counts[kind]["malformed"] += 1

                elif isinstance(content, str):
                    self.content_shape_counts[kind]["legacy_scalar"] += 1

                elif content is None:
                    self.malformed_items += 1
                    self.content_shape_counts[kind]["missing"] += 1

                else:
                    self.malformed_items += 1
                    self.content_shape_counts[kind]["unexpected"] += 1

                continue

            self.content_shape_counts[kind]["unclassified"] += 1

    def render(self, total_records: int, source_counts: Dict[str, int]) -> None:
        logger.info("=" * 72)
        logger.info(" 📊 CDM DOCUMENT ITEMS SUMMARY")
        logger.info("=" * 72)
        logger.info(f"Total Records Inspected   : {total_records}")
        logger.info(f"Total Items Counted       : {self.total_items_inspected}")
        logger.info(f"Malformed Items Detected  : {self.malformed_items}")
        logger.info("-" * 72)
        logger.info(f"{'ITEM KIND':<25} | {'COUNT':<8} | {'CONTENT SHAPE':<30}")
        logger.info("-" * 72)

        for kind, count in self.kind_counts.most_common():
            shapes = self.content_shape_counts.get(kind, Counter())
            shape_parts = []

            if shapes.get("variants"):
                shape_parts.append(f"variants={shapes['variants']}")
            if shapes.get("legacy_scalar"):
                shape_parts.append(f"legacy_scalar={shapes['legacy_scalar']}")
            if shapes.get("missing"):
                shape_parts.append(f"missing={shapes['missing']}")
            if shapes.get("unexpected"):
                shape_parts.append(f"unexpected={shapes['unexpected']}")
            if shapes.get("malformed"):
                shape_parts.append(f"malformed={shapes['malformed']}")
            if shapes.get("structured"):
                shape_parts.append("structured")
            if shapes.get("unclassified"):
                shape_parts.append("unclassified")

            shape_str = ", ".join(shape_parts) if shape_parts else "-"

            logger.info(f"{kind:<25} | {count:<8} | {shape_str:<30}")

            variants = self.variant_counts.get(kind)
            if variants:
                for variant_name, variant_count in variants.most_common():
                    logger.info(
                        f"{'':<25} | {'':<8} |   └─ {variant_name}: {variant_count}"
                    )

            structured = self.structured_counts.get(kind)
            if structured:
                for structured_key, structured_count in structured.most_common():
                    logger.info(
                        f"{'':<25} | "
                        f"{'':<8} | "
                        f"  └─ {structured_key}: {structured_count}"
                    )

        logger.info("=" * 72)
        logger.info(
            "✅ Document item review complete. "
            f"Inspected {total_records} records, "
            f"{self.total_items_inspected} items, "
            f"{self.malformed_items} malformed variant-bearing items."
        )
        logger.info("")


class _CharNameReporter:
    def __init__(self) -> None:
        self.records: List[Tuple[str, str, str, str, str]] = []

    def update(self, document: Document) -> None:
        resolved = (
            document.meta.resolved or type("obj", (object,), {"identities": []})()
        )
        identities = getattr(resolved, "identities", [])

        player_identity = next(
            (i for i in identities if getattr(i, "is_player_controlled", False)),
            None,
        )
        bot_identity = next(
            (i for i in identities if not getattr(i, "is_player_controlled", False)),
            None,
        )

        player_name = (
            getattr(player_identity, "name", "N/A") if player_identity else "N/A"
        )
        player_gender = (
            getattr(player_identity, "gender", "N/A") if player_identity else "N/A"
        )
        bot_name = getattr(bot_identity, "name", "N/A") if bot_identity else "N/A"
        bot_gender = getattr(bot_identity, "gender", "N/A") if bot_identity else "N/A"

        self.records.append(
            (document.id, player_name, player_gender, bot_name, bot_gender)
        )

    def render(self, *args, **kwargs) -> None:
        logger.info("=" * 60)
        logger.info(" 📊 CHARACTER NAMES & GENDERS REPORT")
        logger.info("=" * 60)
        logger.info("UUID\tPLAYER_NAME\tPLAYER_GENDER\tBOT_NAME\tBOT_GENDER")
        for record in self.records:
            logger.info(
                f"{record[0]}\t{record[1]}\t{record[2]}\t{record[3]}\t{record[4]}"
            )
        logger.info("=" * 60 + "\n")


class _HealthReporter:
    def __init__(self, hide_anomaly_details: bool, report_breakdown: bool) -> None:
        self.hide_anomaly_details = hide_anomaly_details
        self.report_breakdown = report_breakdown
        self.healthy_count = 0
        self.failure_registry: Dict[str, List[str]] = defaultdict(list)
        self.source_counts: Dict[str, int] = defaultdict(int)
        self.total_turns = 0
        self.converted_turns = 0
        self.stage_breakdown: Dict[str, Dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )

    def update(self, document: Document) -> None:
        source_identity = _extract_source_identity(document)
        self.source_counts[source_identity] += 1

        try:
            health = document.meta.health or {}

            turns_metrics = health.get("turns_metrics") or {}
            self.total_turns += turns_metrics.get("total_turns", 0)
            self.converted_turns += turns_metrics.get("converted_turns", 0)

            breakdown_data = health.get("breakdown") or {}
            for stage, checks in breakdown_data.items():
                if isinstance(checks, dict):
                    for check_key, passed_check in checks.items():
                        if passed_check:
                            self.stage_breakdown[stage][check_key] += 1

            if health.get("is_healthy", False):
                self.healthy_count += 1
            else:
                self.failure_registry[document.id] = health.get(
                    "issues", ["Unspecified validation issue"]
                )

        except Exception as exc:
            self.failure_registry[document.id].append(
                f"Pydantic validation/structural crash: {exc}"
            )

    def _render_breakdown(self, total_records: int) -> None:
        logger.info("=" * 60)
        logger.info(" 📈 PIPELINE STAGE BREAKDOWN")
        logger.info("=" * 60)

        for stage, checks in self.stage_breakdown.items():
            target_source = G1_HEALTH_DENOMINATORS.get(stage)
            if target_source:
                stage_denom = self.source_counts.get(target_source, 0)
            else:
                stage_denom = total_records

            logger.info(f"{stage} (Target Source: {target_source or 'ALL'})")

            passed_count = checks.get("passed", 0)
            passed_pct = (passed_count / stage_denom * 100) if stage_denom > 0 else 0
            logger.info(
                f" ✅ PASSED              : "
                f"{passed_count}/{stage_denom} ({passed_pct:.2f}%)"
            )

            for check_name, count in checks.items():
                if check_name == "passed":
                    continue
                check_pct = (count / stage_denom * 100) if stage_denom > 0 else 0
                logger.info(
                    f"    {check_name:<20}: {count}/{stage_denom} ({check_pct:.2f}%)"
                )

            logger.info("-" * 60)

        conversion_pct = (
            (self.converted_turns / self.total_turns * 100)
            if self.total_turns > 0
            else 0
        )
        remaining_turns = self.total_turns - self.converted_turns
        estimated_seconds = remaining_turns * 5
        estimated_hours = estimated_seconds / 3600

        logger.info(" 📝 Grammar Conversion Summary")
        logger.info(f"    Total Turns             : {self.total_turns}")
        logger.info(
            f"    Turns Converted         : "
            f"{self.converted_turns} ({conversion_pct:.2f}%)"
        )
        logger.info(f"    Turns Remaining         : {remaining_turns}")
        logger.info(
            f"    Estimated Local Compute : {estimated_hours:.1f} hours (@5s/turn)"
        )
        logger.info("=" * 60)

    def render(self, total_records: int, source_counts: Dict[str, int]) -> None:
        health_pct = (
            (self.healthy_count / total_records) * 100 if total_records > 0 else 0
        )

        logger.info("=" * 60)
        logger.info("📊 LILAKOSHA PIPELINE DATA HEALTH REPORT")
        logger.info("=" * 60)
        logger.info(f"Total Records Evaluated: {total_records}")
        logger.info(
            f"Healthy Records:         {self.healthy_count} ({health_pct:.2f}%)"
        )
        logger.info(f"Defective Records:       {len(self.failure_registry)}")
        logger.info("=" * 60)

        logger.info("📦 SOURCE RECORD BREAKDOWN")
        logger.info("=" * 60)
        for src_id, count in sorted(
            self.source_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            src_pct = (count / total_records * 100) if total_records > 0 else 0
            logger.info(f"    {src_id:<32}: {count} ({src_pct:.2f}%)")
        logger.info("=" * 60)

        if self.report_breakdown:
            self._render_breakdown(total_records)

        if self.failure_registry:
            if self.hide_anomaly_details:
                logger.info(
                    "ℹ️  Anomaly details hidden by configuration parameter flag."
                )
                logger.info("=" * 60)
            else:
                logger.info("❌ DETECTED ANOMALY REGISTRY BY RECORD ID:")
                for uuid, faults in self.failure_registry.items():
                    logger.info(f"   ↳ UUID: {uuid}")
                    for fault in faults:
                        logger.info(f"        - {fault}")
                logger.info("=" * 60)


class _StatsReporter:
    def __init__(self) -> None:
        self.sexual_counts: Counter = Counter()
        self.violence_counts: Counter = Counter()
        self.toxicity_counts: Counter = Counter()
        self.genre_counts: Counter = Counter()
        self.theme_counts: Counter = Counter()
        self.language_counts: Counter = Counter()
        self.turn_counts: List[int] = []
        self.narrative_counts: List[int] = []

    def update(self, document: Document) -> None:
        stats = document.meta.stats or {}

        # Update aggregators using safe dictionary lookups
        self.sexual_counts[stats.get("sexual_axis", "Unset")] += 1
        self.violence_counts[stats.get("violence_axis", "Unset")] += 1
        self.toxicity_counts[stats.get("toxicity_axis", "Unset")] += 1
        self.genre_counts[stats.get("primary_genre", "Unset")] += 1

        for theme in stats.get("themes", []):
            self.theme_counts[theme] += 1

        for lang in stats.get("languages", []):
            self.language_counts[lang] += 1

        if "turn_count" in stats:
            self.turn_counts.append(stats["turn_count"])

        if "narrative_count" in stats:
            self.narrative_counts.append(stats["narrative_count"])

    def render(self, total_records: int, source_counts: Dict[str, int]) -> None:
        logger.info("=" * 60)
        logger.info("📊 LILAKOSHA DATASET DISTRIBUTION REPORT")
        logger.info("=" * 60)
        logger.info(f"Total Portfolio Volume: {total_records} records")
        logger.info("=" * 60)

        # 1. Safety Axis Sub-Reports
        logger.info("🔒 SAFETY DIAL DISTRIBUTIONS")
        logger.info("  [Sexual Axis]")
        for val, count in self.sexual_counts.most_common():
            pct = (count / total_records) * 100
            logger.info(f"    - {val:<15} : {count:>4} ({pct:.1f}%)")

        logger.info("  [Violence Axis]")
        for val, count in self.violence_counts.most_common():
            pct = (count / total_records) * 100
            logger.info(f"    - {val:<15} : {count:>4} ({pct:.1f}%)")

        logger.info("  [Toxicity Axis]")
        for val, count in self.toxicity_counts.most_common():
            pct = (count / total_records) * 100
            logger.info(f"    - {val:<15} : {count:>4} ({pct:.1f}%)")
        logger.info("-" * 60)

        # 2. Genre Distribution
        logger.info("🎭 PRIMARY GENRE MIX")
        for genre, count in self.genre_counts.most_common():
            pct = (count / total_records) * 100
            logger.info(f"  - {genre:<22} : {count:>4} ({pct:.1f}%)")
        logger.info("-" * 60)

        # 3. Top Theme Distribution
        logger.info("🏷️  TOP THEMATIC TAGS (FREQUENCY)")
        for theme, count in self.theme_counts.most_common(25):
            pct = (count / total_records) * 100
            logger.info(f"  - {theme:<26} : {count:>4} ({pct:.1f}%)")

        if len(self.theme_counts) > 25:
            logger.info(f"  ... and {len(self.theme_counts) - 25} other unique themes.")
        logger.info("-" * 60)

        # 4. Language Distribution
        logger.info("🌐 LANGUAGE DISTRIBUTION")
        for lang, count in self.language_counts.most_common():
            pct = (count / total_records) * 100
            logger.info(f"  - {lang:<22} : {count:>4} ({pct:.1f}%)")
        logger.info("-" * 60)

        # 4a. Narrative Item Distribution
        if self.narrative_counts:
            sorted_narratives = sorted(self.narrative_counts)
            total_narratives = sum(sorted_narratives)
            min_count = sorted_narratives[0]
            max_count = sorted_narratives[-1]
            avg_count = total_narratives / len(sorted_narratives)
            median_count = sorted_narratives[len(sorted_narratives) // 2]

            logger.info("📖 NARRATIVE ITEM DISTRIBUTION")
            logger.info(f"  Records Analyzed       : {len(sorted_narratives)}")
            logger.info(f"  Total Narrative Items  : {total_narratives}")
            logger.info(f"  Minimum Narrative Count: {min_count}")
            logger.info(f"  Maximum Narrative Count: {max_count}")
            logger.info(f"  Average Narrative Count: {avg_count:.1f}")
            logger.info(f"  Median Narrative Count : {median_count}")

            logger.info("  Narrative Count Buckets")
            for low, high, label in TURN_BUCKETS:
                bucket_count = sum(1 for t in sorted_narratives if low <= t <= high)
                pct = (bucket_count / total_records) * 100
                logger.info(f"    {label:<18} : {bucket_count:>4} ({pct:.1f}%)")
            logger.info("-" * 60)

        # 5. Conversation Turn Distribution
        if self.turn_counts:
            sorted_turns = sorted(self.turn_counts)
            total_turns = sum(sorted_turns)
            min_turns = sorted_turns[0]
            max_turns = sorted_turns[-1]
            avg_turns = total_turns / len(sorted_turns)
            median_turns = sorted_turns[len(sorted_turns) // 2]

            logger.info("💬 CONVERSATION TURN DISTRIBUTION")
            logger.info(f"  Records Analyzed      : {len(sorted_turns)}")
            logger.info(f"  Total Turns           : {total_turns}")
            logger.info(f"  Minimum Turns         : {min_turns}")
            logger.info(f"  Maximum Turns         : {max_turns}")
            logger.info(f"  Average Turns         : {avg_turns:.1f}")
            logger.info(f"  Median Turns          : {median_turns}")

            logger.info("  Turn Count Buckets")
            for low, high, label in TURN_BUCKETS:
                bucket_count = sum(1 for t in sorted_turns if low <= t <= high)
                pct = (bucket_count / total_records) * 100
                logger.info(f"    {label:<18} : {bucket_count:>4} ({pct:.1f}%)")

        logger.info("=" * 60 + "\n")


class _TurnDistributionReporter:
    def __init__(self) -> None:
        self.turn_counts: List[int] = []

    def update(self, document: Document) -> None:
        stats = document.meta.stats or {}
        if "turn_count" in stats:
            self.turn_counts.append(stats["turn_count"])

    def render(self, total_records: int, source_counts: Dict[str, int]) -> None:
        if not self.turn_counts:
            logger.info("No turn_count data available for distribution analysis.")
            return

        sorted_turns = sorted(self.turn_counts)
        total_turns = sum(sorted_turns)
        min_turns = sorted_turns[0]
        max_turns = sorted_turns[-1]
        avg_turns = total_turns / len(sorted_turns)
        median_turns = sorted_turns[len(sorted_turns) // 2]

        logger.info("=" * 60)
        logger.info("📊 CONVERSATION TURN DISTRIBUTION")
        logger.info("=" * 60)
        logger.info(f"Total Records Analyzed : {len(sorted_turns)}")
        logger.info(f"Total Turns            : {total_turns}")
        logger.info(f"Minimum Turns          : {min_turns}")
        logger.info(f"Maximum Turns          : {max_turns}")
        logger.info(f"Average Turns          : {avg_turns:.1f}")
        logger.info(f"Median Turns           : {median_turns}")

        logger.info("  Turn Count Buckets")
        for low, high, label in TURN_BUCKETS:
            bucket_count = sum(1 for t in sorted_turns if low <= t <= high)
            pct = (bucket_count / total_records) * 100
            logger.info(f"    {label:<18} : {bucket_count:>4} ({pct:.1f}%)")

        logger.info("=" * 60)


# ==========================================
# Reporter Factory
# ==========================================


SECTION_REPORTER_MAP = {
    "health": lambda params: _HealthReporter(
        _str_to_bool(params.get("report_hide_anomaly_details", False)),
        _str_to_bool(params.get("report_breakdown", False)),
    ),
    "stats": lambda params: _StatsReporter(),
    "items": lambda params: _ItemReporter(),
    "char_names": lambda params: _CharNameReporter(),
    "turn_distribution": lambda params: _TurnDistributionReporter(),
}


def _str_to_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes")
    return bool(value)


def _build_reporters(params: dict):
    sections = params.get("report_sections")
    if sections is not None:
        normalized = [str(s).strip().lower() for s in sections if str(s).strip()]
        reporters = []
        for section in normalized:
            factory = SECTION_REPORTER_MAP.get(section)
            if factory is None:
                logger.warning("Unknown report section ignored: %s", section)
                continue
            reporters.append(factory(params))
        return reporters

    # Fallback to legacy boolean flags
    reporters = []

    if params.get("report_items"):
        reporters.append(_ItemReporter())

    if params.get("report_char_names"):
        reporters.append(_CharNameReporter())

    if params.get("report_health"):
        reporters.append(
            _HealthReporter(
                _str_to_bool(params.get("report_hide_anomaly_details", False)),
                _str_to_bool(params.get("report_breakdown", False)),
            )
        )

    if params.get("report_stats"):
        reporters.append(_StatsReporter())

    if params.get("report_turn_distribution"):
        reporters.append(_TurnDistributionReporter())

    return reporters


# ==========================================
# Main Entry Point
# ==========================================


def run(config: dict) -> None:
    params = config.get("parameters", {})

    records_dir = _resolve_records_dir(config)
    if not records_dir.exists():
        logger.error("Records directory not found: %s", records_dir)
        return

    start_uuid = params.get("start_uuid")
    stop_uuid = params.get("stop_uuid")
    file_iter = _iter_record_files(records_dir, start_uuid, stop_uuid)

    reporters = _build_reporters(params)
    if not reporters:
        logger.warning("No report-* flags enabled; nothing to do.")
        return

    active_sections = params.get("report_sections")
    if active_sections is not None:
        logger.info(
            "Active report sections: %s", ", ".join(str(s) for s in active_sections)
        )
    else:
        legacy_flags = [k for k in params if k.startswith("report_") and params[k]]
        if legacy_flags:
            logger.info("Active legacy report flags: %s", ", ".join(legacy_flags))

    logger.info("Running unified CDM report across records...")

    total_records = 0
    skipped_records = 0
    source_counts: Dict[str, int] = {}

    for file_path in tqdm(file_iter, desc="Scanning CDM Records"):
        document, parse_error = _load_document(file_path)
        if document is None:
            skipped_records += 1
            logger.debug("Skipping %s: %s", file_path.name, parse_error)
            continue

        total_records += 1
        source_identity = _extract_source_identity(document)
        source_counts[source_identity] = source_counts.get(source_identity, 0) + 1

        for reporter in reporters:
            reporter.update(document)

    for reporter in reporters:
        reporter.render(total_records, source_counts)

    if skipped_records:
        logger.warning(
            "Skipped %d records due to parse/validation failures.",
            skipped_records,
        )
