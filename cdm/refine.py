from typing import List

from pydantic import BaseModel, Field


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
