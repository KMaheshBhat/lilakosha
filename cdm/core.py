from enum import Enum
from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class SexualScale(str, Enum):
    CLEAN = "Clean"
    SUGGESTIVE = "Suggestive"
    EXPLICIT = "Explicit"


class ViolenceScale(str, Enum):
    NONE = "None"
    COMBAT = "Combat"
    GRAPHIC = "Graphic"


class ToxicityScale(str, Enum):
    SAFE = "Safe"
    HARASSMENT = "Harassment"
    DANGEROUS = "Dangerous"


class MainGenre(str, Enum):
    FANTASY = "Fantasy"
    SCI_FI = "Sci-Fi"
    ROMANCE = "Romance"
    SLICE_OF_LIFE = "Slice of Life"
    ACTION_ADVENTURE = "Action & Adventure"
    MYSTERY_THRILLER = "Mystery & Thriller"
    COMEDY = "Comedy"
    DRAMA = "Drama"


class PronounSet(BaseModel):
    subjective: str = Field(description="e.g., 'he', 'she', 'they'")
    objective: str = Field(description="e.g., 'him', 'her', 'them'")
    possessive: str = Field(description="e.g., 'his', 'hers', 'their'")


class CharacterIdentity(BaseModel):
    """
    Authoritative actor registry. Sealing these fields blocks downstream
    linguistic drift during zero-reasoning grammar normalization.
    """

    entity_id: str = Field(
        description=(
            "The unique semantic identifier for the actor "
            "(e.g., 'user', 'bot_123', 'char_001')."
        )
    )
    name: str = Field(
        description=(
            "The clean proper name used for 3rd-person text generation "
            "and narrative grounding."
        )
    )
    gender: Literal["male", "female", "neutral", "unknown"] = "unknown"
    pronouns: PronounSet
    is_player_controlled: bool = Field(
        default=False,
        description=(
            "True if this entity represents a human user/PC. "
            "False for NPCs, companion bots, or novel characters."
        ),
    )


# ==========================================
# Session Line Items
# ==========================================
class WorldItem(BaseModel):
    kind: Literal["world"] = "world"
    subkind: Literal["info", "detail"]
    content: str


class CharacterItem(BaseModel):
    """Chronological, local deep lore extraction or behavioral snapshot."""

    kind: Literal["character"] = "character"
    subkind: Literal["info", "detail"]
    entity_id: str
    content: str
    reasoning: Optional[str] = None


class SummaryItem(BaseModel):
    kind: Literal["summary"] = "summary"
    subkind: Literal["pre", "scenario", "post"]
    content: str


class TurnItem(BaseModel):
    kind: Literal["turn"] = "turn"
    actor_id: str  # Maps directly back to CharacterIdentity.entity_id
    thought: Optional[str] = ""
    prose: str
    prose_revision_comments: Optional[str] = None
    original_prose: Optional[str] = None


ItemUnion = Union[WorldItem, CharacterItem, SummaryItem, TurnItem]
DiscriminatedItem = Annotated[ItemUnion, Field(discriminator="kind")]


class Annotation(BaseModel):
    kind: str
    content: str
    reasoning: Optional[str] = None


# ==========================================
# Session Meta
# ==========================================
class SessionMeta(BaseModel):
    model_config = ConfigDict(extra="allow")
    source_record: Optional[dict] = None
    source_identity: str
    bot_id: Optional[str] = None
    bot_name: Optional[str] = "the character"
    ingestion_timestamp: Optional[str] = None
    identities: List[CharacterIdentity] = Field(
        default_factory=list,
        description="The sealed directory of all characters present within this trace.",
    )
    sexual_axis: Optional[SexualScale] = None
    violence_axis: Optional[ViolenceScale] = None
    toxicity_axis: Optional[ToxicityScale] = None
    primary_genre: Optional[MainGenre] = None
    themes: Optional[List[str]] = Field(default_factory=list)
    crpo_signals: Optional[dict] = Field(default_factory=dict)
    annotations: Optional[List[Annotation]] = None
    healthy: Optional[bool] = None


class Session(BaseModel):
    kind: Literal["session"] = "session"
    meta: SessionMeta
    items: List[DiscriminatedItem]
