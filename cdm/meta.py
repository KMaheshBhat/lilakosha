"""
Meta utility functions for DocumentMeta operations.
Provides centralized stats calculation, health assessment, and annotation management.
"""

import logging
from typing import Any, Optional

from cdm.core import (
    Annotation,
    Document,
    MainGenre,
    ResolvedMeta,
    SexualScale,
    ToxicityScale,
    ViolenceScale,
)

logger = logging.getLogger(__name__)


def calculate_resolved(document: Document) -> ResolvedMeta:
    """
    Extracts safety scales, primary genre, descriptive themes, and detected languages
    from document.items while safely retaining pre-existing properties like character
    identities.
    """
    sexuality = None
    violence = None
    toxicity = None
    primary_genre = None
    themes = []
    languages = []

    # Sweep document items for categorization blocks
    for item in document.items:
        if getattr(item, "kind", None) != "categorization":
            continue

        category = getattr(item, "category", None)
        value = getattr(item, "value", None)

        try:
            if category == "sexuality" and isinstance(value, str):
                sexuality = SexualScale(value)
            elif category == "violence" and isinstance(value, str):
                violence = ViolenceScale(value)
            elif category == "toxicity" and isinstance(value, str):
                toxicity = ToxicityScale(value)
            elif category == "genre" and isinstance(value, str):
                primary_genre = MainGenre(value)
            elif category == "theme":
                if isinstance(value, list):
                    themes.extend(value)
                elif isinstance(value, str):
                    themes.append(value)
            elif category == "language":
                if isinstance(value, list):
                    languages.extend(value)
                elif isinstance(value, str):
                    languages.append(value)
        except ValueError:
            # Shield pass against minor formatting variations or casing mismatch
            continue

    source = document.meta.source or {}
    identities = (
        document.meta.resolved.identities
        if document.meta.resolved
        else source.get("identities", [])
    )

    return ResolvedMeta(
        identities=identities,
        sexuality=sexuality,
        violence=violence,
        toxicity=toxicity,
        genre=primary_genre,
        themes=list(dict.fromkeys(themes)),
        languages=list(dict.fromkeys(languages)),
    )


def calculate_health(document: Document) -> dict[str, Any]:
    """
    Evaluates refinement metrics across universal rules (e.g., language refinement)
    and source-specific rule groups (PIPPA grammar, Forums HTML conversion),
    returning explicit tracking flags for telemetry breakdown reporting.
    """
    meta = document.meta
    resolved = meta.resolved or ResolvedMeta()
    items = document.items or []
    annotations = meta.annotations or []
    source = meta.source or {}

    annotation_kinds = {anno.kind for anno in annotations if hasattr(anno, "kind")}
    issues = []
    breakdown = {}

    # --- Universal Rule: Language Refinement Pass ---
    has_lang_anno = "refine-cdm-language" in annotation_kinds
    has_lang_item = any(
        getattr(item, "kind", None) == "categorization"
        and getattr(item, "category", None) == "language"
        and bool(getattr(item, "value", None))
        for item in items
    )

    if not has_lang_anno:
        issues.append("Missing 'refine-cdm-language' annotation")
    if not has_lang_item:
        issues.append("Unset or empty language categorization")

    breakdown["refine-cdm-language"] = {
        "passed": has_lang_anno and has_lang_item,
        "annotation": has_lang_anno,
        "categorization_item": has_lang_item,
    }

    # Extract source identity for specific checks
    source_identity = (
        source.get("source_identity") or source.get("source") or "unknown"
    )

    # --- Source-Specific Rules: lemonilia/roleplaying-forums-raw ---
    is_forums_source = source_identity == "lemonilia/roleplaying-forums-raw"

    if is_forums_source:
        # --- Rule Group: refine-cdm-html-to-markdown ---
        has_html_anno = "refine-cdm-html-to-markdown" in annotation_kinds

        # This check mirrors refine-pippa-grammar: 100% conversion
        # of a specific item type.
        narrative_items = [
            item for item in items if getattr(item, "kind", None) == "narrative"
        ]
        total_narratives = len(narrative_items)

        def is_narrative_html_converted(item: Any) -> bool:
            """
            Verifies narrative item content contains both original and
            refine-cdm-html-to-markdown variants.
            """
            content = getattr(item, "content", [])
            if not isinstance(content, list):
                return False

            variant_names = {
                v.name: getattr(v, "mimetype", None)
                for v in content
                if hasattr(v, "name")
            }

            return (
                "original" in variant_names
                and "refine-cdm-html-to-markdown" in variant_names
            )

        converted_narratives = sum(
            1 for item in narrative_items if is_narrative_html_converted(item)
        )
        has_full_lineage = (total_narratives > 0) and (
            total_narratives == converted_narratives
        )

        if not has_html_anno:
            issues.append("Missing 'refine-cdm-html-to-markdown' annotation")
        if total_narratives > converted_narratives:
            issues.append(
                "HTML conversion lineage defect: "
                f"{total_narratives - converted_narratives} "
                "narrative items are missing correct HTML->Markdown variant lineage."
            )

        breakdown["refine-cdm-html-to-markdown"] = {
            "passed": has_html_anno and has_full_lineage,
            "annotation": has_html_anno,
            "narrative": has_full_lineage,
        }

    # --- Source-Specific Rules: PIPPA ---
    is_pippa_source = source_identity == "PygmalionAI/PIPPA"

    if is_pippa_source:
        # --- Rule Group 1: refine-pippa-characters ---
        has_char_anno = "refine-pippa-characters" in annotation_kinds
        has_bot_detail = any(
            getattr(item, "kind", None) == "character"
            and getattr(item, "entity_id", None) != "user"
            for item in items
        )
        has_user_info = any(
            getattr(item, "kind", None) == "character"
            and getattr(item, "entity_id", None) == "user"
            for item in items
        )

        if not has_char_anno:
            issues.append("Missing 'refine-pippa-characters' annotation")
        if not has_bot_detail:
            issues.append(
                "Missing bot character profile (character item, entity_id!=user)"
            )
        if not has_user_info:
            issues.append(
                "Missing user character profile (character item, entity_id=user)"
            )

        breakdown["refine-pippa-characters"] = {
            "passed": has_char_anno and has_bot_detail and has_user_info,
            "annotation": has_char_anno,
            "bot detail": has_bot_detail,
            "user info": has_user_info,
        }

        # --- Rule Group 2: refine-pippa-safety-dials ---
        has_safety_anno = "refine-pippa-safety-dials" in annotation_kinds
        has_sexual = resolved.sexuality is not None
        has_violence = resolved.violence is not None
        has_toxicity = resolved.toxicity is not None

        if not has_safety_anno:
            issues.append("Missing 'refine-pippa-safety-dials' annotation")
        if not has_sexual:
            issues.append("Unset sexuality categorization")
        if not has_violence:
            issues.append("Unset violence categorization")
        if not has_toxicity:
            issues.append("Unset toxicity categorization")

        breakdown["refine-pippa-safety-dials"] = {
            "passed": (
                has_safety_anno and has_sexual and has_violence and has_toxicity
            ),
            "annotation": has_safety_anno,
            "sexual axis": has_sexual,
            "violence axis": has_violence,
            "toxicity axis": has_toxicity,
        }

        # --- Rule Group 3: refine-pippa-genre-theme ---
        has_genre_anno = "refine-pippa-genre-theme" in annotation_kinds
        has_primary_genre = resolved.genre is not None
        has_themes = bool(resolved.themes)

        if not has_genre_anno:
            issues.append("Missing 'refine-pippa-genre-theme' annotation")
        if not has_primary_genre:
            issues.append("Unset genre categorization")
        if not has_themes:
            issues.append("Unset thematic categorization")

        breakdown["refine-pippa-genre-theme"] = {
            "passed": has_genre_anno and has_primary_genre and has_themes,
            "annotation": has_genre_anno,
            "primary genre": has_primary_genre,
            "themes": has_themes,
        }

        # --- Rule Group 4: refine-pippa-grammar ---
        has_grammar_anno = "refine-pippa-grammar" in annotation_kinds

        turn_items = [
            item for item in items if getattr(item, "kind", None) == "turn"
        ]
        total_turns = len(turn_items)

        def is_turn_grammar_refined(item: Any) -> bool:
            """
            Verifies turn item contains both original and refine-pippa-grammar variants.
            """
            content = getattr(item, "content", [])
            if not isinstance(content, list):
                return False
            variant_names = {v.name for v in content if hasattr(v, "name")}
            return (
                "original" in variant_names
                and "refine-pippa-grammar" in variant_names
            )

        converted_turns = sum(
            1 for item in turn_items if is_turn_grammar_refined(item)
        )
        has_prose_lineage = (total_turns > 0) and (total_turns == converted_turns)

        if not has_grammar_anno:
            issues.append("Missing 'refine-pippa-grammar' annotation")
        if total_turns > converted_turns:
            issues.append(
                f"Grammar tracking defect: {total_turns - converted_turns} turn items "
                "are missing 'refine-pippa-grammar' variant"
            )

        breakdown["refine-pippa-grammar"] = {
            "passed": has_grammar_anno and has_prose_lineage,
            "annotation": has_grammar_anno,
            "prose": has_prose_lineage,
        }

    turn_items = [
        item for item in items if getattr(item, "kind", None) == "turn"
    ]
    total_turns_pippa = len(turn_items)
    converted_turns_pippa = sum(
        1
        for item in turn_items
        if "refine-pippa-grammar"
        in {v.name for v in getattr(item, "content", []) if hasattr(v, "name")}
    )

    return {
        "is_healthy": len(issues) == 0,
        "issues": issues,
        # PIPPA specific turn metrics (kept for compatibility
        # in calculate_health response)
        "turns_metrics": {
            "total_turns": total_turns_pippa,
            "converted_turns": converted_turns_pippa,
        },
        "breakdown": breakdown,
    }


def calculate_stats(document: Document) -> dict[str, Any]:
    """Calculate runtime statistics for a document.

    Args:
        document: The CDM Document to calculate stats for.

    Returns:
        A dictionary with metrics and feature lists/labels for downstream
        aggregation and reporting.
    """
    meta = document.meta
    resolved = meta.resolved or ResolvedMeta()

    # 1. Structural Numerical Counts
    turn_count = sum(
        1 for item in document.items if getattr(item, "kind", None) == "turn"
    )
    narrative_count = sum(
        1 for item in document.items if getattr(item, "kind", None) == "narrative"
    )
    item_count = len(document.items)
    character_count = len(resolved.identities) if resolved.identities else 0

    # 2. Word Count across variants
    total_word_count = 0
    for item in document.items:
        content = getattr(item, "content", None)
        if isinstance(content, list):
            for variant in content:
                text = getattr(variant, "text", "")
                if text:
                    total_word_count += len(text.split())

    # 3. Safety Axes & Classifications
    sexual_axis = resolved.sexuality.value if resolved.sexuality else "Unset"
    violence_axis = resolved.violence.value if resolved.violence else "Unset"
    toxicity_axis = resolved.toxicity.value if resolved.toxicity else "Unset"
    primary_genre = resolved.genre.value if resolved.genre else "Unset"
    themes = list(resolved.themes) if resolved.themes else ["[No Themes Assigned]"]
    languages = (
            getattr(resolved, "languages", None)
            or [
                getattr(item, "value", None)
                for item in document.items
                if getattr(item, "kind", None) == "categorization"
                and getattr(item, "category", None) == "language"
                and getattr(item, "value", None) is not None
            ]
            or ["[No Languages Assigned]"]
        )

    # Normalize list if nested
    flat_languages = []
    for lang in languages:
        if isinstance(lang, list):
            flat_languages.extend(lang)
        else:
            flat_languages.append(lang)

    return {
        "narrative_count": narrative_count,
        "turn_count": turn_count,
        "item_count": item_count,
        "character_count": character_count,
        "word_count": total_word_count,
        "sexual_axis": sexual_axis,
        "violence_axis": violence_axis,
        "toxicity_axis": toxicity_axis,
        "primary_genre": primary_genre,
        "themes": themes,
        "languages": list(dict.fromkeys(flat_languages)),
    }


def update_meta(document: Document) -> None:
    """
    Update document.meta.resolved, health, and stats with calculated values.

    Args:
        document: The CDM Document to update.
    """
    document.meta.resolved = calculate_resolved(document)
    document.meta.health = calculate_health(document)
    document.meta.stats = calculate_stats(document)


def add_annotation(
    document: Document,
    kind: str,
    content: str,
    reasoning: Optional[str] = None,
) -> None:
    """
    Add an annotation to the document's meta.annotations list.

    Args:
        document: The CDM Document to add annotation to.
        kind: The annotation kind identifier.
        content: The annotation content.
        reasoning: Optional reasoning trace.
    """
    if document.meta.annotations is None:
        document.meta.annotations = []

    document.meta.annotations.append(
        Annotation(kind=kind, content=content, reasoning=reasoning)
    )


def remove_annotation(document: Document, kind: str) -> None:
    """
    Remove all annotations matching the given kind from the document.

    Args:
        document: The CDM Document to remove annotations from.
        kind: The annotation kind to remove.
    """
    if document.meta.annotations:
        document.meta.annotations = [
            anno for anno in document.meta.annotations if anno.kind != kind
        ]
    else:
        document.meta.annotations = []


def has_annotation(document: Document, kind: str) -> bool:
    """
    Check if the document has an annotation with the given kind.

    Args:
        document: The CDM Document to check.
        kind: The annotation kind to look for.

    Returns:
        True if an annotation with the given kind exists, False otherwise.
    """
    return any(anno.kind == kind for anno in (document.meta.annotations or []))
