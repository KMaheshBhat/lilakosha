import json
import logging
from collections import Counter, defaultdict
from pathlib import Path

from tqdm import tqdm

logger = logging.getLogger(__name__)


# Unstructured CDM items that use List[ContentVariant].
VARIANT_ITEM_KINDS = {
    "world",
    "character",
    "summary",
    "narrative",
    "turn",
}

# Structured CDM items that intentionally do not use ContentVariant.
STRUCTURED_ITEM_KINDS = {
    "categorization",
    "sequence",
}


def run(config: dict) -> None:
    """
    CDM Inspection Pass: Review Document Items across JSON records.

    Collects:
    - item kind frequencies
    - ContentVariant name frequencies for unstructured items
    - legacy scalar-content counts
    - missing/unexpected/malformed content for variant-bearing items
    - structured item counts

    This pass performs raw JSON inspection only; it does not load CDM
    models and does not modify records.
    """
    processed_vol = Path(config["volumes"]["processed"])
    records_dir = processed_vol / "cdm" / "records"

    if not records_dir.exists():
        logger.error(f"Records directory not found: {records_dir}")
        return

    record_files = sorted(records_dir.glob("*.json"))
    if not record_files:
        logger.warning(f"No CDM JSON records found inside {records_dir}")
        return

    params = config.get("parameters", {})
    start_uuid = params.get("start_uuid")
    stop_uuid = params.get("stop_uuid")

    logger.info(
        f"Inspecting {len(record_files)} JSON records for item kinds "
        f"and ContentVariant distributions..."
    )

    kind_counts: Counter[str] = Counter()
    variant_counts: dict[str, Counter[str]] = defaultdict(Counter)
    structured_counts: dict[str, Counter[str]] = defaultdict(Counter)
    content_shape_counts: dict[str, Counter[str]] = defaultdict(Counter)

    documents_inspected = 0
    total_items_inspected = 0
    malformed_items = 0

    for file_path in tqdm(record_files, desc="Reviewing CDM Items"):
        record_uuid = file_path.stem

        if start_uuid and record_uuid < str(start_uuid):
            continue

        if stop_uuid and record_uuid > str(stop_uuid):
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                doc_data = json.load(f)

            documents_inspected += 1

            items = doc_data.get("items", [])

            if not isinstance(items, list):
                logger.warning(
                    f"{file_path.name}: 'items' is not a list"
                )
                continue

            for item in items:
                if not isinstance(item, dict):
                    malformed_items += 1
                    continue

                total_items_inspected += 1

                kind = item.get("kind", "<missing_kind>")
                kind_counts[kind] += 1

                # ---------------------------------------------------------
                # Structured items
                #
                # These intentionally do NOT use ContentVariant.
                # ---------------------------------------------------------
                if kind in STRUCTURED_ITEM_KINDS:
                    content_shape_counts[kind]["structured"] += 1

                    if kind == "categorization":
                        category = item.get("category")
                        if isinstance(category, str) and category.strip():
                            structured_counts[kind][category] += 1
                        else:
                            malformed_items += 1

                    elif kind == "sequence":
                        data = item.get("data")
                        if isinstance(data, dict):
                            sequence_for = data.get("sequence_for")
                            if isinstance(sequence_for, str) and sequence_for.strip():
                                structured_counts[kind][sequence_for] += 1
                            else:
                                malformed_items += 1
                        else:
                            malformed_items += 1

                    continue

                # ---------------------------------------------------------
                # Variant-bearing unstructured items
                # ---------------------------------------------------------
                if kind in VARIANT_ITEM_KINDS:
                    content = item.get("content")

                    if isinstance(content, list):
                        content_shape_counts[kind]["variants"] += 1

                        for variant in content:
                            if not isinstance(variant, dict):
                                malformed_items += 1
                                content_shape_counts[kind]["malformed"] += 1
                                continue

                            name = variant.get("name")

                            if isinstance(name, str) and name.strip():
                                variant_counts[kind][name] += 1
                            else:
                                malformed_items += 1
                                content_shape_counts[kind]["malformed"] += 1

                    elif isinstance(content, str):
                        content_shape_counts[kind]["legacy_scalar"] += 1

                    elif content is None:
                        malformed_items += 1
                        content_shape_counts[kind]["missing"] += 1

                    else:
                        malformed_items += 1
                        content_shape_counts[kind]["unexpected"] += 1

                    continue

                # ---------------------------------------------------------
                # Unknown item kind
                #
                # Don't assume that an unknown future item kind is malformed.
                # Record it separately so the inspection remains forward
                # compatible with future CDM extensions.
                # ---------------------------------------------------------
                content_shape_counts[kind]["unclassified"] += 1

        except Exception as e:
            logger.error(
                f"Failed inspecting JSON document {file_path.name}: {e}"
            )

    # ---------------------------------------------------------------------
    # Output Summary Report
    # ---------------------------------------------------------------------
    logger.info("=" * 72)
    logger.info(" 📊 CDM DOCUMENT ITEMS SUMMARY")
    logger.info("=" * 72)
    logger.info(f"Total Documents Inspected : {documents_inspected}")
    logger.info(f"Total Items Counted       : {total_items_inspected}")
    logger.info(f"Malformed Items Detected  : {malformed_items}")
    logger.info("-" * 72)
    logger.info(
        f"{'ITEM KIND':<25} | "
        f"{'COUNT':<8} | "
        f"{'CONTENT SHAPE':<30}"
    )
    logger.info("-" * 72)

    for kind, count in kind_counts.most_common():
        shapes = content_shape_counts.get(kind, Counter())

        shape_parts = []

        if shapes.get("variants"):
            shape_parts.append(f"variants={shapes['variants']}")

        if shapes.get("legacy_scalar"):
            shape_parts.append(
                f"legacy_scalar={shapes['legacy_scalar']}"
            )

        if shapes.get("missing"):
            shape_parts.append(f"missing={shapes['missing']}")

        if shapes.get("unexpected"):
            shape_parts.append(
                f"unexpected={shapes['unexpected']}"
            )

        if shapes.get("malformed"):
            shape_parts.append(
                f"malformed={shapes['malformed']}"
            )

        if shapes.get("structured"):
            shape_parts.append("structured")

        if shapes.get("unclassified"):
            shape_parts.append("unclassified")

        shape_str = ", ".join(shape_parts) if shape_parts else "-"

        logger.info(
            f"{kind:<25} | "
            f"{count:<8} | "
            f"{shape_str:<30}"
        )

        variants = variant_counts.get(kind)

        if variants:
            for variant_name, variant_count in variants.most_common():
                logger.info(
                    f"{'':<25} | "
                    f"{'':<8} | "
                    f"  └─ {variant_name}: {variant_count}"
                )

        structured = structured_counts.get(kind)

        if structured:
            for structured_key, structured_count in structured.most_common():
                logger.info(
                    f"{'':<25} | "
                    f"{'':<8} | "
                    f"  └─ {structured_key}: {structured_count}"
                )

    logger.info("=" * 72 + "\n")

    logger.info(
        "✅ Document item review complete. "
        f"Inspected {documents_inspected} documents, "
        f"{total_items_inspected} items, "
        f"{malformed_items} malformed variant-bearing items."
    )
