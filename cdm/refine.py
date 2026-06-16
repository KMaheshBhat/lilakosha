import re
from typing import List, Literal

from pydantic import BaseModel, Field
from pydantic.functional_validators import field_validator

from cdm.core import MainGenre, SexualScale, ToxicityScale, ViolenceScale


class PronounSet(BaseModel):
    subjective: str = Field(
        description=(
            "The subjective pronoun to use for this entity (e.g., 'he', 'she', 'they')."
        )
    )
    objective: str = Field(
        description=(
            "The objective pronoun to use for this entity (e.g., 'him', 'her', 'them')."
        )
    )
    possessive: str = Field(
        description=(
            "The possessive adjective/pronoun to use for this entity "
            "(e.g., 'his', 'hers', 'their')."
        )
    )


class CharacterProfile(BaseModel):
    name: str = Field(
        description=(
            "The character's proper name where clearly identified. "
            "CRITICAL FALLBACK FOR ANONYMOUS USERS: If the human player or a character "
            "is anonymous, generic, or referred to only as 'user', 'human', or "
            "'unknown', you MUST select a realistic, natural fallback name based on "
            "gender context: "
            "Male -> 'Adam', 'Jack', or 'James'; "
            "Female -> 'Eve', 'Jane', or 'Mary'; "
            "Gender-Neutral/Ambiguous -> 'Alex', 'Sam', or 'Robin'. "
            "Never leave the name as 'User', 'Human', 'Unknown', or a descriptive "
            "role title."
        )
    )
    gender: Literal["male", "female", "neutral", "unknown"] = Field(
        description="The established or inferred narrative gender of the entity."
    )
    pronouns: PronounSet = Field(
        description="The sealed, authoritative pronoun tokens of the character."
    )
    core_traits: List[str] = Field(
        description="Key behavioral traits, descriptions, or motivations observed."
    )
    appearance_details: List[str] = Field(
        description="Physical descriptions or visual indicators."
    )


class CharacterSynthesisResponse(BaseModel):
    user_character: CharacterProfile = Field(
        description="Profile extracted for the human USER player."
    )
    bot_character: CharacterProfile = Field(
        description="Profile extracted for the AI/Bot companion."
    )


class SafetyDialsResponse(BaseModel):
    sexual_axis: SexualScale = Field(
        description=(
            "Evaluates sexual content. "
            "'Clean' means platonic/wholesome. "
            "'Suggestive' includes kissing, heavy flirting, or suggestive outfits. "
            "'Explicit' involves graphic descriptions of sexual acts."
        )
    )
    violence_axis: ViolenceScale = Field(
        description=(
            "Evaluates physical harm. "
            "'None' means zero violence. "
            "'Combat' includes action, magic battles, or non-lethal fighting. "
            "'Graphic' includes explicit gore, mutilation, or severe cruelty."
        )
    )
    toxicity_axis: ToxicityScale = Field(
        description=(
            "Evaluates real-world harm. "
            "'Safe' includes fictional villain dialogue. "
            "'Harassment' includes intense verbal abuse. "
            "'Dangerous' covers hate speech."
        )
    )


class GenreAndThemesResponse(BaseModel):
    primary_genre: MainGenre = Field(
        description=(
            "The rigid primary genre classification that best fits this session. "
        )
    )
    themes: List[str] = Field(
        description=(
            "Open-ended semantic tags or narrative tropes found in the chat. "
            "Capture specific behavioral quirks, plot devices, or settings "
            "(e.g., 'body-swap', 'magic-ring', 'teasing', 'tsundere')."
        )
    )

    @field_validator("themes")
    @classmethod
    def sanitize_themes(cls, v: List[str]) -> List[str]:
        sanitized = []
        for tag in v:
            # 1. Lowercase and strip outer spaces
            clean_tag = tag.lower().strip()
            # 2. Turn spaces, underscores, and slashes/dashes into a standard hyphen
            clean_tag = re.sub(r"[\s_/\-\:]+", "-", clean_tag)
            # 3. Strip out any remaining weird punctuation (except alphanumeric
            #    and hyphens)
            clean_tag = re.sub(r"[^\w-]", "", clean_tag)
            # 4. Collapse multiple repeating hyphens (e.g., '--' or '---') into
            #    a single '-'
            clean_tag = re.sub(r"-+", "-", clean_tag)
            # 5. Clean up any accidental leading or trailing hyphens
            clean_tag = clean_tag.strip("-")
            if clean_tag:
                sanitized.append(clean_tag)
        # Deduplicate while preserving order
        return list(dict.fromkeys(sanitized))


class SingleTurnGrammarResponse(BaseModel):
    rewritten_prose: str = Field(
        description=(
            "The finalized, clean third-person past-tense narrative prose "
            "for the target turn complying with all verbatim requirements."
        )
    )
