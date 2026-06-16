## LilaKosha Common Data Model (CDM)

The **CDM** schema is used by the `ingest-pippa` and `refine-*` steps to transform raw datasets into recap-augmented chunks.

## Entity Specification Table

| **Kind** | **Subkind** | **Purpose / Narrative Role** | **Key Properties** |
| :--- | :--- | :--- | :--- |
| **`session`** | *(null)* | **The Trace Envelope**: The top-level container representing a single self-contained "Bubble of Play". | `children` (Array), `meta` (Object) |
| **`world`** | `info` | **Permanent Grounding**: Immutable global lore, physical laws, and core setting rules . | `content` (String) |
| **`world`** | `detail` | **Supplemental Lore**: Static but secondary info (scene items) or dynamic foreshadowing injected by a director . | `content` (String) |
| **`character`** | `info` | **Core Persona**: Primary character sheet, base motivations, and physical appearance . | `entity_id` (UUID), `content` (String) |
| **`character`** | `detail` | **Contextual Status**: Static relationship lore or dynamic status telemetry (health, mood, evolving distrust) . | `entity_id` (UUID), `content` (String) |
| **`summary`** | `pre` | **Historical Anchor**: A 3rd-person past tense recap of the distant past to manage context window limits . | `content` (String) |
| **`summary`** | `scenario` | **Motivational Anchor**: Defines the immediate scene-level conflict or localized goal . | `content` (String) |
| **`summary`** | `post` | **Causality Bridge**: The specific outcome of the *previous* interaction; the evidence of world-state shift . | `content` (String) |
| **`turn`** | *(null)* | **Linguistic Evidence**: The "Tail" of the trace. Raw prose locked to a specific character's perspective . | `actor_id` (UUID), `thought` (String), `prose` (String) |

## JSON Record Example

This JSON record represents the target state of an ingestion pass. It demonstrates a "ripened" narrative where supplemental details (like poisoned tea or a character's distrust) are provided as grounding for the next character turn.  The record would be "flattened" structurally to a row in JSONL but "pretty-printed" here for readability.

```json
{
  "kind": "session",
  "meta": {
    "source_identity": "PIPPA-DEDUPED",
    "flavor_tag": "unbound",
    "tense_format": "3rd_person_past",
    "crpo_signals": { "novelty": 1.0, "surprise": 1.0 }
  },
  "children": [
    {
      "kind": "world",
      "subkind": "info",
      "content": "The High-Spire is a gravity-defying citadel fueled by atmospheric pressure."
    },
    {
      "kind": "world",
      "subkind": "detail",
      "content": "Static Detail: The North Balcony railing is structurally unsound due to age."
    },
    {
      "kind": "character",
      "subkind": "info",
      "entity_id": "char-valerius-001",
      "content": "Valerius: A disgraced mage-knight with a mechanical arm and a debt to the Iron Bank."
    },
    {
      "kind": "character",
      "subkind": "detail",
      "entity_id": "char-valerius-001",
      "content": "Current Status: Mounting distrust of the group; mechanical arm is overheating."
    },
    {
      "kind": "summary",
      "subkind": "pre",
      "content": "The party successfully infiltrated the Spire's lower docks after a skirmish with sentries."
    },
    {
      "kind": "summary",
      "subkind": "scenario",
      "content": "The group is now negotiating with a double-agent on the North Balcony."
    },
    {
      "kind": "summary",
      "subkind": "post",
      "content": "The double-agent just hinted that the Iron Bank has put a bounty on the party."
    },
    {
      "kind": "turn",
      "actor_id": "char-valerius-001",
      "thought": "The bounty explains the agent's grin. If I don't secure the perimeter now, we are as good as dead. I need to test that railing.",
      "prose": "Valerius tightened his cloak, his mechanical fingers clicking as they reset. He stepped toward the agent, his eyes scanning the rusted balcony railing as he calculated the quickest path to the exit."
    }
  ]
}
```
