import logging
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from lingua import LanguageDetectorBuilder
from tqdm import tqdm

from cdm.core import CategorizationItem, Document
from cdm.meta import add_annotation, update_meta

logger = logging.getLogger(__name__)

# Initialize the detector once at module load
detector = LanguageDetectorBuilder.from_all_languages().build()

# Explicit list of CDM item kinds that possess a .content list of ContentVariants
SUPPORTED_CONTENT_KINDS: Set[str] = {
    "narrative",
    "turn",
    "world",
    "character",
    "summary",
}


def detect_document_languages(
    doc: Document,
    target_kinds: Set[str] | None = None,
    preferred_variants_by_kind: Dict[str, List[str]] | None = None,
    window_size: int = 5,
    min_confidence: float = 0.05,
    max_languages: int = 5,
) -> Tuple[List[str], str]:
    """Iterates through all document items matching `target_kinds` in
    sliding/chunked windows, evaluates language confidence per window via lingua-py,
    aggregates maximum confidence scores per language across all windows, and returns
    (detected_languages, reasoning_string).

    Text is extracted from content variants according to
    `preferred_variants_by_kind`: for each item the preferred variant list is
    consulted in order and the first available variant's text is used.
    """
    if target_kinds is None:
        target_kinds = {"turn", "narrative"}

    if preferred_variants_by_kind is None:
        preferred_variants_by_kind = {kind: ["original"] for kind in target_kinds}

    # 1. Gather all matching items across the document by item.kind
    target_items = [
        item for item in doc.items
        if getattr(item, "kind", None) in target_kinds
    ]

    if not target_items:
        return [], ""

    # Map to store max confidence score observed per language across all windows
    max_scores_by_lang: dict[str, float] = {}
    total_windows = 0

    # 2. Process in non-overlapping windows of size `window_size`
    for i in range(0, len(target_items), window_size):
        window_items = target_items[i : i + window_size]
        sample_texts = []

        for item in window_items:
            kind = getattr(item, "kind", None)
            content_list = getattr(item, "content", [])

            # Resolve the preferred variant order for this kind;
            # fall back to ["original"] then first available if nothing is configured.
            kind_str = kind if kind is not None else ""
            variant_prefs = preferred_variants_by_kind.get(
                kind_str, ["original"]
            )
            selected_text = _select_variant_text(
                content_list, variant_prefs
            )

            if selected_text:
                sample_texts.append(selected_text)

        if not sample_texts:
            continue

        total_windows += 1
        combined_text = "\n".join(sample_texts)

        # Compute confidence values for this window
        confidence_values = detector.compute_language_confidence_values(combined_text)

        for entry in confidence_values:
            if entry.language and entry.language.iso_code_639_1:
                iso_code = entry.language.iso_code_639_1.name.lower()
                # Store the highest confidence score seen across windows
                if (
                    iso_code not in max_scores_by_lang
                    or entry.value > max_scores_by_lang[iso_code]
                ):
                    max_scores_by_lang[iso_code] = entry.value

    if not max_scores_by_lang:
        return [], ""

    # 3. Filter by min_confidence threshold
    valid_scores = [
        (iso, score) for iso, score in max_scores_by_lang.items()
        if score >= min_confidence
    ]

    if not valid_scores:
        return [], ""

    # 4. Sort by highest aggregated score
    valid_scores.sort(key=lambda x: x[1], reverse=True)

    # 5. Cap to `max_languages`
    final_scores = valid_scores[:max_languages]
    detected_langs = [iso for iso, _ in final_scores]

    # Build signal trace
    signal_str = " ".join([f"{iso}:{score:.2f}" for iso, score in final_scores])
    reasoning = (
        f"Detected using lingua-py windowing (size={window_size}, "
        f"windows={total_windows}, kinds={sorted(list(target_kinds))}). {signal_str}"
    )

    return detected_langs, reasoning


def _select_variant_text(
    content_list: Any,
    preferred_variants: List[str],
) -> str | None:
    """Return the text of the first content variant whose name matches
    `preferred_variants` in order.  Falls back to the first variant that has
    text when none of the preferred names are present.
    """
    if isinstance(content_list, str):
        return content_list.strip() or None

    if not isinstance(content_list, list):
        return None

    # Try preferred variants in order
    for pref_name in preferred_variants:
        for variant in content_list:
            text_val = getattr(variant, "text", None)
            if (
                getattr(variant, "name", None) == pref_name
                and text_val
                and text_val.strip()
            ):
                return text_val.strip()

    # Fallback: first variant that has any text
    for variant in content_list:
        text_val = getattr(variant, "text", None)
        if text_val and text_val.strip():
            return text_val.strip()

    return None


def run(config: dict[str, Any]) -> None:
    """LilaKosha Pipeline Step: Language Refinement Pass

    Inspects targeted CDM record items, detects languages using lingua-py,
    and attaches/updates a CategorizationItem with category='language'.

    Configuration Parameters:
      - cdm_language_target: List of target definitions (kind and content
        variant preference order).  All targeted kinds are introspected for
        language.  Within each kind the first available variant matching the
        preference list is used; falls back to the first variant that has text.
      - start_uuid / stop_uuid: Optional range boundaries for target records.
      - window_size, min_language_confidence, max_languages: lingua-py tuning.
    """
    processed_vol = Path(config["volumes"]["processed"])
    records_dir = processed_vol / "cdm" / "records"

    if not records_dir.exists():
        logger.error(f"Records directory not found: {records_dir}")
        return

    record_files = sorted(records_dir.glob("*.json"))

    # ------------------------------------------------------------------ #
    # 1. Resolve Parameters                                              #
    # ------------------------------------------------------------------ #
    params = config.get("parameters", {})

    # --- Target configuration (kind + variant preference order) ---
    targets = params.get("cdm_language_target")

    if not targets:
        # Fallback default target if none provided
        targets = [{"kind": "turn", "variants": ["original"]}]

    target_kinds: Set[str] = set()
    preferred_variants_by_kind: Dict[str, List[str]] = {}
    for target_spec in targets:
        kind = target_spec.get("kind")
        variants = target_spec.get("variants", [])

        # Fail initially if specified target kind does not support ContentVariants
        if kind not in SUPPORTED_CONTENT_KINDS:
            raise ValueError(
                f"Invalid target kind '{kind}' specified in "
                "cdm_language_target. target validation failed. "
                f"Allowed content kinds are: {sorted(SUPPORTED_CONTENT_KINDS)}"
            )

        target_kinds.add(kind)
        preferred_variants_by_kind[kind] = variants if variants else ["original"]

    start_uuid = params.get("start_uuid")
    stop_uuid = params.get("stop_uuid")
    window_size = params.get("window_size", 5)
    min_language_confidence = params.get("min_language_confidence", 0.05)
    max_languages = params.get("max_languages", 999)

    if start_uuid or stop_uuid:
        logger.info(
            f"🎯 Targeted Refinement Scope Activated (CDM Language):\n"
            f"    - Start Boundary: {start_uuid or '[-∞ Unbound]'}\n"
            f"    - Stop Boundary:  {stop_uuid or '[+∞ Unbound]'}"
        )
        filtered_files: List[Any] = []
        for file in record_files:
            stem = file.stem
            if start_uuid and stem < str(start_uuid):
                continue
            if stop_uuid and stem > str(stop_uuid):
                continue
            filtered_files.append(file)
        record_files = filtered_files
    else:
        logger.info(
            "🔬 Refinement Scope: Global Sweep (No lexical range parameters provided)"
        )

    logger.info(
        f"Processing {len(record_files)} records for language categorization..."
    )

    processed_count = 0

    for file_path in tqdm(record_files, desc="Refining CDM Languages"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                doc = Document.model_validate_json(f.read())

            # Detect language codes and confidence trace on targeted item kinds
            languages, reasoning_str = detect_document_languages(
                doc,
                target_kinds=target_kinds,
                preferred_variants_by_kind=preferred_variants_by_kind,
                window_size=window_size,
                min_confidence=min_language_confidence,
                max_languages=max_languages,
            )

            if not languages:
                continue

            # Check if a 'language' CategorizationItem already exists
            existing_item = None
            for item in doc.items:
                if (
                    isinstance(item, CategorizationItem)
                    or item.kind == "categorization"
                ) and getattr(item, "category", None) == "language":
                    existing_item = item
                    break

            if existing_item:
                existing_item.value = languages
                existing_item.reasoning = reasoning_str
            else:
                # Generate deterministic item ID
                item_id = f"categorization-lang-{len(doc.items):06d}"
                lang_item = CategorizationItem(
                    id=item_id,
                    category="language",
                    value=languages,
                    reasoning=reasoning_str,
                )
                doc.items.append(lang_item)

            # Record step annotation trace
            add_annotation(
                doc,
                kind="refine-cdm-language",
                content=f"Detected primary language codes: {', '.join(languages)}",
            )

            # Re-calculate meta snapshots and save record
            update_meta(doc)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(doc.model_dump_json(indent=2, by_alias=True))

            processed_count += 1

        except Exception as e:
            logger.error(
                f"Failed processing language detection for {file_path.name}: {e}"
            )

    logger.info(
        f"✅ Language refinement pass complete. Processed {processed_count} records."
    )
