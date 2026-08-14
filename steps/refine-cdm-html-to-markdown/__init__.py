import logging
from pathlib import Path
from typing import Any, Dict, List, Set

from markdownify import markdownify
from tqdm import tqdm

from cdm.core import Document
from cdm.meta import add_annotation, remove_annotation, update_meta

logger = logging.getLogger(__name__)

# Explicit list of CDM item kinds that possess a .content list of ContentVariants
SUPPORTED_CONTENT_KINDS: Set[str] = {
    "narrative",
    "turn",
    "world",
    "character",
    "summary",
}


def run(config: Dict[str, Any]) -> None:
    """
    LilaKosha Refinement Pass: HTML to Markdown CDM Refinement (v2).

    Deterministically converts HTML prose variants into clean Markdown
    using markdownify.

    Configuration Parameters:
      - cdm_html_to_markdown_target: List of target definitions (kind
        and variant preference order).
      - start_uuid / stop_uuid: Optional range boundaries for target records.
    """
    # 1. Resolve Data Infrastructure
    processed_vol = Path(config["volumes"]["processed"])
    records_dir = processed_vol / "cdm" / "records"

    if not records_dir.exists():
        logger.warning(f"CDM records directory not found at {records_dir}")
        return

    # 2. Extract & Validate Parameters (Early Check)
    params = config.get("parameters", config)
    targets = params.get("cdm_html_to_markdown_target")

    if not targets:
        # Fallback default target if none provided
        targets = [{"kind": "narrative", "variants": ["original"]}]

    target_map: Dict[str, List[str]] = {}
    for target_spec in targets:
        kind = target_spec.get("kind")
        variants = target_spec.get("variants", [])

        # Fail initially if specified target kind does not support ContentVariants
        if kind not in SUPPORTED_CONTENT_KINDS:
            raise ValueError(
                f"Invalid target kind '{kind}' specified in "
                "cdm_html_to_markdown_target. target validation failed. "
                f"Allowed content kinds are: {sorted(SUPPORTED_CONTENT_KINDS)}"
            )

        target_map[kind] = variants

    start_uuid = params.get("start_uuid")
    stop_uuid = params.get("stop_uuid")

    record_files = sorted(records_dir.glob("*.json"))

    # v2: Pre-filter record_files by file.stem before opening/parsing
    if start_uuid or stop_uuid:
        record_files = [
            f
            for f in record_files
            if (not start_uuid or f.stem >= str(start_uuid))
            and (not stop_uuid or f.stem <= str(stop_uuid))
        ]
        logger.info(
            f"🎯 Targeted Refinement Scope Activated (HTML to Markdown v2):\n"
            f"    - Start Boundary: {start_uuid or '[-∞ Unbound]'}\n"
            f"    - Stop Boundary:  {stop_uuid or '[+∞ Unbound]'}\n"
            f"    - Pre-filtered to {len(record_files)} candidate files"
        )
    else:
        logger.info(
            "🔬 Refinement Scope: Global Sweep (No lexical range parameters provided)"
        )

    logger.info(
        f"--- Executing Step: REFINE-CDM-HTML-TO-MARKDOWN across "
        f"{len(record_files)} records ---"
    )

    processed_count = 0
    skipped_error_count = 0

    # 3. Process CDM Records
    for record_path in tqdm(record_files, desc="Converting HTML to Markdown (v2)"):
        try:
            with open(record_path, "r", encoding="utf-8") as f:
                document = Document.model_validate_json(f.read())

            doc_modified = False

            # Iterate through all items
            for item in document.items:
                if item.kind not in target_map:
                    continue

                content = getattr(item, "content", None)
                if not content:
                    continue

                # Find candidate variant by preference order
                candidate_variant = None
                preferred_variants = target_map[item.kind]
                for pref_var in preferred_variants:
                    for var in content:
                        if var.name == pref_var:
                            candidate_variant = var
                            break
                    if candidate_variant:
                        break

                if candidate_variant and candidate_variant.text:
                    # Deterministic conversion via markdownify
                    markdown_text = markdownify(candidate_variant.text)

                    # Create new variant
                    new_variant = candidate_variant.model_copy(deep=True)
                    new_variant.name = "refine-cdm-html-to-markdown"
                    new_variant.text = markdown_text

                    # Update or Append logic
                    existing_variant_idx = -1
                    for idx, var in enumerate(content):
                        if var.name == "refine-cdm-html-to-markdown":
                            existing_variant_idx = idx
                            break

                    if existing_variant_idx >= 0:
                        # Overwrite existing refined variant
                        content[existing_variant_idx] = new_variant
                    else:
                        # Append new refined variant
                        content.append(new_variant)

                    doc_modified = True

            if doc_modified:
                # Retain remove_annotation for run cleanup
                remove_annotation(document, "refine-cdm-html-to-markdown")

                add_annotation(
                    document,
                    kind="refine-cdm-html-to-markdown",
                    content=(
                        "Converted targeted HTML content variants to Markdown format."
                    ),
                )
                update_meta(document)

                with open(record_path, "w", encoding="utf-8") as f:
                    f.write(document.model_dump_json(indent=2, by_alias=True))

                processed_count += 1

        except Exception as e:
            logger.error(
                f"⚠️ Error converting HTML to Markdown for record "
                f"{record_path.name}: {e}. Skipping record and continuing."
            )
            skipped_error_count += 1
            continue

    logger.info(
        f"✅ REFINE-CDM-HTML-TO-MARKDOWN complete. "
        f"Updated {processed_count} records. "
        f"Skipped {skipped_error_count} records due to errors."
    )
