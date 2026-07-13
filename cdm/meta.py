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
    Extracts safety scales, primary genre, and descriptive themes from
    document.items while safely retaining pre-existing properties
    like character identities.
    """
    # 1. Start with values from the existing metadata to retain identities
    #    and protect any pre-existing cached attributes.
    sexuality = None
    violence = None
    toxicity = None
    primary_genre = None
    themes = []

    # 2. Sweep the document items timeline matrix for new categorization blocks
    for item in document.items:
        if item.kind != "categorization":
            continue

        category = item.category
        value = item.value

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
        except ValueError:
            # Shield pass from minor formatting variations or loose casings
            continue

    # 3. Construct the updated payload while retaining the historical context
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
    )


def calculate_health(document: Document) -> dict[str, Any]:
    """
    Evaluates specific metrics across all 4 rule groups and returns explicit tracking
    flags for granular telemetry breakdown reporting.
    """
    meta = document.meta
    resolved = meta.resolved or ResolvedMeta()
    items = document.items or []
    annotations = meta.annotations or []

    # Safe extraction of processed annotation kinds
    annotation_kinds = {anno.kind for anno in annotations if hasattr(anno, "kind")}

    # Tracking list for descriptive text logs
    issues = []

    # --- Rule Group 1: refine-characters ---
    has_char_anno = "refine-characters" in annotation_kinds
    has_bot_detail = any(
        item.kind == "character" and getattr(item, "entity_id", None) != "user"
        for item in items
    )
    has_user_info = any(
        item.kind == "character" and getattr(item, "entity_id", None) == "user"
        for item in items
    )

    if not has_char_anno:
        issues.append("Missing 'refine-characters' annotation")
    if not has_bot_detail:
        issues.append("Missing bot character profile (character item, entity_id!=user)")
    if not has_user_info:
        issues.append("Missing user character profile (character item, entity_id=user)")

    # --- Rule Group 2: refine-safety-dials ---
    has_safety_anno = "refine-safety-dials" in annotation_kinds
    has_sexual = resolved.sexuality is not None
    has_violence = resolved.violence is not None
    has_toxicity = resolved.toxicity is not None

    if not has_safety_anno:
        issues.append("Missing 'refine-safety-dials' annotation")
    if not has_sexual:
        issues.append("Unset sexuality categorization")
    if not has_violence:
        issues.append("Unset violence categorization")
    if not has_toxicity:
        issues.append("Unset toxicity categorization")

    # --- Rule Group 3: refine-genre-theme ---
    has_genre_anno = "refine-genre-theme" in annotation_kinds
    has_primary_genre = resolved.genre is not None
    has_themes = bool(resolved.themes)

    if not has_genre_anno:
        issues.append("Missing 'refine-genre-theme' annotation")
    if not has_primary_genre:
        issues.append("Unset genre categorization")
    if not has_themes:
        issues.append("Unset thematic categorization")

    # --- Rule Group 4: refine-grammar ---
    has_grammar_anno = "refine-grammar" in annotation_kinds

    turn_items = [item for item in items if item.kind == "turn"]
    total_turns = len(turn_items)
    converted_turns = sum(
        1 for item in turn_items if getattr(item, "original_prose", None) is not None
    )

    has_prose_lineage = total_turns == converted_turns

    if not has_grammar_anno:
        issues.append("Missing 'refine-grammar' annotation")
    if total_turns > converted_turns:
        issues.append(
            f"Grammar tracking defect: {total_turns - converted_turns} turn items "
            "are missing 'original_prose'"
        )

    return {
        "is_healthy": len(issues) == 0,
        "issues": issues,
        "turns_metrics": {
            "total_turns": total_turns,
            "converted_turns": converted_turns,
        },
        # Granular tracking matrix to reconstruct your breakdown
        "breakdown": {
            "refine-characters": {
                "passed": has_char_anno and has_bot_detail and has_user_info,
                "annotation": has_char_anno,
                "bot detail": has_bot_detail,
                "user info": has_user_info,
            },
            "refine-safety-dials": {
                "passed": has_safety_anno
                and has_sexual
                and has_violence
                and has_toxicity,
                "annotation": has_safety_anno,
                "sexual axis": has_sexual,
                "violence axis": has_violence,
                "toxicity axis": has_toxicity,
            },
            "refine-genre-theme": {
                "passed": has_genre_anno and has_primary_genre and has_themes,
                "annotation": has_genre_anno,
                "primary genre": has_primary_genre,
                "themes": has_themes,
            },
            "refine-grammar": {
                "passed": has_grammar_anno and has_prose_lineage,
                "annotation": has_grammar_anno,
                "prose": has_prose_lineage,
            },
        },
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
    turn_count = sum(1 for item in document.items if item.kind == "turn")
    item_count = len(document.items)

    # Safely guard identities calculation in case it's missing or None
    character_count = len(resolved.identities) if resolved.identities else 0

    # 2. Extract Safety Axes (handle Enums safely via .value)
    sexual_axis = resolved.sexuality.value if resolved.sexuality else "Unset"
    violence_axis = resolved.violence.value if resolved.violence else "Unset"
    toxicity_axis = resolved.toxicity.value if resolved.toxicity else "Unset"

    # 3. Extract Primary Genre Mix
    primary_genre = resolved.genre.value if resolved.genre else "Unset"

    # 4. Extract Thematic Tags List
    # Returns a list of themes or a fallback list to match your original counter logic
    themes = list(resolved.themes) if resolved.themes else ["[No Themes Assigned]"]

    return {
        "turn_count": turn_count,
        "item_count": item_count,
        "character_count": character_count,
        "sexual_axis": sexual_axis,
        "violence_axis": violence_axis,
        "toxicity_axis": toxicity_axis,
        "primary_genre": primary_genre,
        "themes": themes,
    }


def update_meta(document: Document) -> None:
    """
    Update document.meta.stats with calculated values.

    Args:
        document: The CDM Document to update stats for.
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

    Initializes the annotations list if it is None.

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
