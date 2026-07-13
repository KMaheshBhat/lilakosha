from enum import Enum
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


# ==========================================
# Global Enumerations & Core Scales
# ==========================================
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


# ==========================================
# Core Actor & Identity Schemas
# ==========================================
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
            "The clean proper name used for 3rd-person text "
            "generation and narrative grounding."
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
# Base Item Layer (Addressability)
# ==========================================
class BaseDocumentItem(BaseModel):
    """
    Root class establishing deterministic local addressability across all items.
    IDs must be unique within a document context (e.g., 'turn-000001').
    """

    id: str = Field(
        description="Locally unique identifier within the document boundary."
    )


# ==========================================
# Concrete Item Implementations
# ==========================================
class WorldItem(BaseDocumentItem):
    """Static spatial, environmental, or narrative setup descriptors."""

    kind: Literal["world"] = "world"
    content: str


class CharacterItem(BaseDocumentItem):
    """Chronological, local deep lore extraction or behavioral
    snapshot without restrictive subkind enums."""

    kind: Literal["character"] = "character"
    entity_id: str = Field(description="Maps back to CharacterIdentity.entity_id")
    content: str
    reasoning: Optional[str] = None


class SummaryItem(BaseDocumentItem):
    """Chronological or event-horizon summaries (replaces
    previous multi-pre/post fields)."""

    kind: Literal["summary"] = "summary"
    content: str


class CategorizationItem(BaseDocumentItem):
    """
    Unified evaluation schema replacing feature proliferation
    for tags, scales, genres, and themes.
    """

    kind: Literal["categorization"] = "categorization"
    category: str = Field(
        description=(
            "The dimension being classified (e.g., 'genre', 'theme', 'sexuality')."
        )
    )
    value: Union[str, List[str]] = Field(
        description="The computed metric, status scale label, or string tags list."
    )
    reasoning: Optional[str] = Field(
        default=None, description="The internal model reasoning trace backing the tag."
    )


class NarrativeItem(BaseDocumentItem):
    """
    Structural base for long-form prose and raw script content.
    Allows clean representation of Gutenberg prose assets without
    breaking turn conventions.
    """

    kind: Literal["narrative"] = "narrative"
    prose: str
    prose_revision_comments: Optional[str] = None
    original_prose: Optional[str] = None


class TurnItem(NarrativeItem):
    """
    Specialization of NarrativeItem mapping explicitly back to dialogue
    actors (e.g., PIPPA traces).
    """

    kind: Literal["turn"] = "turn"
    actor_id: str = Field(
        description="Maps directly back to CharacterIdentity.entity_id"
    )
    thought: Optional[str] = Field(
        default="", description="Internal thoughts/reasoning tags or system channels."
    )


class SequenceItem(BaseDocumentItem):
    """
    Flexible execution/training topology representation without
    speculative hierarchy trees or graphs.
    """

    kind: Literal["sequence"] = "sequence"
    item_ids: List[str] = Field(
        description=(
            "Ordered list of item IDs forming a structured timeline "
            "or slice (e.g. ['turn-000001', 'turn-000002'])."
        )
    )


# ==========================================
# Variant Union Mapping
# ==========================================
DocumentItemUnion = Union[
    WorldItem,
    CharacterItem,
    SummaryItem,
    CategorizationItem,
    TurnItem,
    NarrativeItem,
    SequenceItem,
]

DiscriminatedDocumentItem = Annotated[DocumentItemUnion, Field(discriminator="kind")]


class ResolvedMeta(BaseModel):
    identities: List[CharacterIdentity] = Field(
        default_factory=list,
        description="The of all characters present within this trace.",
    )
    sexuality: Optional[SexualScale] = None
    violence: Optional[ViolenceScale] = None
    toxicity: Optional[ToxicityScale] = None
    genre: Optional[MainGenre] = None
    themes: Optional[List[str]] = Field(default_factory=list)


class Annotation(BaseModel):
    kind: str
    content: str
    reasoning: Optional[str] = None


# ==========================================
# Document Level Aggregation Root
# ==========================================
class DocumentMeta(BaseModel):
    model_config = ConfigDict(extra="allow")
    source: Optional[Dict[str, Any]] = None
    resolved: Optional[ResolvedMeta] = None
    health: Optional[Dict[str, Any]] = None
    stats: Optional[Dict[str, Any]] = None
    annotations: Optional[List[Annotation]] = None


class Document(BaseModel):
    """
    The LilaKosha Common Document Model root interface.
    """

    id: str
    kind: Literal["document"] = "document"
    meta: DocumentMeta
    items: List[DiscriminatedDocumentItem]
