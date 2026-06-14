import re
from typing import List

from pydantic import BaseModel, Field
from pydantic.functional_validators import field_validator

from cdm.core import MainGenre, SexualScale, ToxicityScale, ViolenceScale


class CharacterProfile(BaseModel):
    name: str = Field(
        description=(
            "The character's proper name where identified. "
            "Otherwise, the formal or assumed name in this trace."
        )
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
            clean_tag = tag.lower().strip()
            clean_tag = re.sub(r"[\s_]+", "-", clean_tag)
            clean_tag = re.sub(r"[^\w-]", "", clean_tag)
            if clean_tag:
                sanitized.append(clean_tag)
        return list(dict.fromkeys(sanitized))
