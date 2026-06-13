from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, Field

# ----------------------------------------------------------------------
# 1. Define Sub-Models for Children Entities
# ----------------------------------------------------------------------


class WorldEntity(BaseModel):
    kind: Literal["world"] = "world"
    subkind: Literal["info", "detail"]
    content: str


class CharacterEntity(BaseModel):
    kind: Literal["character"] = "character"
    subkind: Literal["info", "detail"]
    entity_id: str
    content: str


class SummaryEntity(BaseModel):
    kind: Literal["summary"] = "summary"
    subkind: Literal["pre", "scenario", "post"]
    content: str


class TurnEntity(BaseModel):
    kind: Literal["turn"] = "turn"
    actor_id: str
    thought: Optional[str] = ""  # PIPPA conversations only have raw message text
    prose: str


# ----------------------------------------------------------------------
# 2. Define the Top-Level Session Container
# ----------------------------------------------------------------------

ChildUnion = Union[WorldEntity, CharacterEntity, SummaryEntity, TurnEntity]

# 2. Wrap that Union in Annotated, attaching the discriminator metadata to it
DiscriminatedChild = Annotated[ChildUnion, Field(discriminator="kind")]


class SessionMeta(BaseModel):
    source_identity: str
    bot_id: Optional[str] = None
    bot_name: Optional[str] = "the character"
    ingestion_timestamp: Optional[str] = None
    flavor_tag: Optional[str] = "unbound"  # Provided defaults for fields PIPPA
    tense_format: Optional[str] = "3rd_person"  # doesn't inherently include.
    crpo_signals: Optional[dict] = Field(default_factory=dict)


class Session(BaseModel):
    kind: Literal["session"] = "session"
    meta: SessionMeta

    # 3. Pass the annotated discriminated union into the List
    children: List[DiscriminatedChild]
