import json
import logging
from collections import Counter
from pathlib import Path

from cdm.core import Document

logger = logging.getLogger(__name__)


def run(config: dict) -> None:
    """LilaKosha Pipeline Step: Extract all unique theme tags across CDM records,
    normalize them (removing hyphens/underscores for clean semantic representation),
    and persist the occurrence manifest to processed_vol/cdm/extracted_themes.json.
    """
    processed_vol = Path(config["volumes"]["processed"])
    records_dir = processed_vol / "cdm" / "records"
    output_path = processed_vol / "cdm" / "extracted_themes.json"

    if not records_dir.exists():
        logger.error(f"Records directory not found at {records_dir}")
        return

    canvas_files = sorted(records_dir.glob("*.json"))
    total_records = len(canvas_files)

    if total_records == 0:
        logger.warning("No CDM canvas artifacts found to process.")
        return

    logger.info(
        f"Extracting and normalizing theme tags across {total_records} CDM records..."
    )

    normalized_counts = Counter()
    raw_to_normalized = {}
    normalized_to_raw_variants = {}
    processed_docs = 0

    for file_path in canvas_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                document = Document.model_validate_json(f.read())

            processed_docs += 1

            for item in document.items:
                if item.kind == "categorization" and item.category == "theme":
                    raw_values = item.value if isinstance(item.value, list) else []
                    for raw_tag in raw_values:
                        if not raw_tag or not isinstance(raw_tag, str):
                            continue

                        # Convert hyphens and underscores to natural spaces for
                        # semantic embeddings
                        normalized = (
                            raw_tag.replace("-", " ")
                            .replace("_", " ")
                            .strip()
                            .lower()
                        )

                        normalized_counts[normalized] += 1
                        raw_to_normalized[raw_tag] = normalized

                        if normalized not in normalized_to_raw_variants:
                            normalized_to_raw_variants[normalized] = set()
                        normalized_to_raw_variants[normalized].add(raw_tag)

        except Exception as e:
            logger.debug(
                f"Skipping record {file_path.name} during theme extraction: {e}"
            )
            continue

    # Convert sets to lists for JSON serialization
    variants_map = {
        norm: sorted(list(variants))
        for norm, variants in normalized_to_raw_variants.items()
    }

    manifest = {
        "meta": {
            "total_records_scanned": total_records,
            "successful_records": processed_docs,
            "total_raw_tags_mapped": len(raw_to_normalized),
            "unique_normalized_terms": len(normalized_counts),
        },
        "counts": dict(normalized_counts.most_common()),
        "raw_map": raw_to_normalized,
        "variants_map": variants_map,
    }

    # Ensure parent output directory exists and write artifact
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    logger.info("=" * 60)
    logger.info("🏷️  LILAKOSHA THEME EXTRACTION COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Records Processed        : {processed_docs} / {total_records}")
    logger.info(f"Total Raw Theme Mappings : {len(raw_to_normalized)}")
    logger.info(f"Unique Normalized Terms  : {len(normalized_counts)}")
    logger.info(f"Output Manifest Saved To : {output_path}")
    logger.info("=" * 60)
