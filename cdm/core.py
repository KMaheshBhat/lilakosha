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


class WorldEntity(BaseModel):
    kind: Literal["world"] = "world"
    subkind: Literal["info", "detail"]
    content: str


class CharacterEntity(BaseModel):
    kind: Literal["character"] = "character"
    subkind: Literal["info", "detail"]
    entity_id: str
    content: str
    reasoning: Optional[str] = None


class SummaryEntity(BaseModel):
    kind: Literal["summary"] = "summary"
    subkind: Literal["pre", "scenario", "post"]
    content: str


class TurnEntity(BaseModel):
    kind: Literal["turn"] = "turn"
    actor_id: str
    thought: Optional[str] = ""
    prose: str


ChildUnion = Union[WorldEntity, CharacterEntity, SummaryEntity, TurnEntity]

DiscriminatedChild = Annotated[ChildUnion, Field(discriminator="kind")]


class Annotation(BaseModel):
    kind: str
    content: str
    reasoning: Optional[str] = None


class SessionMeta(BaseModel):
    model_config = ConfigDict(extra="allow")
    source_identity: str
    bot_id: Optional[str] = None
    bot_name: Optional[str] = "the character"
    ingestion_timestamp: Optional[str] = None
    flavor_tag: Optional[str] = "unbound"
    tense_format: Optional[str] = "3rd_person"
    crpo_signals: Optional[dict] = Field(default_factory=dict)
    user_pc_name: Optional[str] = None
    annotations: Optional[List[Annotation]] = None
    sexual_axis: Optional[SexualScale] = None
    violence_axis: Optional[ViolenceScale] = None
    toxicity_axis: Optional[ToxicityScale] = None
    primary_genre: Optional[MainGenre] = None
    themes: Optional[List[str]] = Field(default_factory=list)


class Session(BaseModel):
    kind: Literal["session"] = "session"
    meta: SessionMeta

    # 3. Pass the annotated discriminated union into the List
    children: List[DiscriminatedChild]
