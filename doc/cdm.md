# Project LilaKosha Common Data Model (CDM) Specification

The **Common Data Model (CDM)** is the foundational, type-safe data schema utilized by the `ingest-pippa`, `refine-*`, and `scalpel-*` pipeline stages. It enforces an orchestration-aware format that translates flat interaction data from multiple source environments into structured, standalone `{UUIDv7}.json` documents representing isolated transaction histories.

## Technical Architecture & Validation Layer

The schema is built and programmatically validated via Pydantic using a discriminated union topology. This allows highly specialized narrative line items to sit within a sequential, chronological flat array (`items`), preserving order of events while exposing distinct metadata properties.

```
Session (kind: "session")
├── meta: SessionMeta
│    ├── identities: List[CharacterIdentity] [Sealed Registry]
│    ├── sexual_axis / violence_axis / toxicity_axis [Safety Scales]
│    └── primary_genre / themes / crpo_signals [Creative Labels]
└── items: List[DiscriminatedItem] (Chronological Stream)
├── WorldItem     (kind: "world")
├── CharacterItem (kind: "character")
├── SummaryItem   (kind: "summary")
└── TurnItem      (kind: "turn")
```

## Enumeration Registers

To maintain tight categorization bounds for downstream fine-tuning, the refinement engine strictly maps metrics to these standardized string scales:

### 1. Safety & Content Dials

* **`SexualScale`** (`meta.sexual_axis`):
  * `"Clean"` – Content contains no overt sexual references or suggestive interplay.
  * `"Suggestive"` – Explicit text is absent but dialogue includes flirtation, double entendres, or romantic tension.
  * `"Explicit"` – Content contains graphic or unfiltered depictions of sexual acts.
* **`ViolenceScale`** (`meta.violence_axis`):
  * `"None"` – No physical altercations or harm occur.
  * `"Combat"` – Standard action sequences, tactical skirmishes, and stylized fantasy conflicts.
  * `"Graphic"` – Unfiltered, visceral, or lethal physical consequences are described.
* **`ToxicityScale`** (`meta.toxicity_axis`):
  * `"Safe"` – Hostile linguistic markers are absent.
  * `"Harassment"` – Interactions include directed emotional cruelty, bullying, or persistent degradation.
  * `"Dangerous"` – Depicts extreme non-fictional harms or actionable real-world threats.

### 2. Primary Classification

* **`MainGenre`** (`meta.primary_genre`):
  * `"Fantasy"`, `"Sci-Fi"`, `"Romance"`, `"Slice of Life"`, `"Action & Adventure"`, `"Mystery & Thriller"`, `"Comedy"`, `"Drama"`

## Data Structure Registries

### Character Identity Object

The metadata block maintains an authoritative actor registry. Sealing these identities blocks downstream linguistic drift during zero-reasoning grammar normalization.

* `entity_id` (String): Unique semantic key across this trace (e.g., `"user"`, `"bot_001"`).
* `name` (String): Clean proper name used for third-person text generation and narrative grounding.
* `gender` (Literal): `"male" | "female" | "neutral" | "unknown"`
* `pronouns` (Object): Structured mappings containing `subjective` (e.g., `"she"`), `objective` (e.g., `"her"`), and `possessive` (e.g., `"hers"`).
* `is_player_controlled` (Boolean): `True` if entity represents a human operator; `False` for NPCs, companion bots, or novel characters.

## Discriminated Line Items Matrix

Every object residing within the top-level `items` list must explicitly include a valid `kind` parameter to anchor the Pydantic type validator.

| **Kind** | **Subkind Options** | **Properties** | **Narrative Intent / Execution Context** |
| :--- | :--- | :--- | :--- |
| **`world`** | `"info"` \| `"detail"` | `content` (str) | **Permanent Grounding**: Global rules, environmental laws (`info`), or dynamic local scene items (`detail`). |
| **`character`** | `"info"` \| `"detail"` | `entity_id` (str)<br>`content` (str)<br>`reasoning` (Optional[str]) | **Behavioral Tracking**: Links to identity registry. Tracks core sheets (`info`) or dynamic state shifts like health or evolving distrust (`detail`). |
| **`summary`** | `"pre"` \| `"scenario"` \| `"post"` | `content` (str) | **Recap-Augmentation**: Truth anchors for long-form context retention. Maps historical past (`pre`), immediate localized conflict (`scenario`), or immediate prior results (`post`). |
| **`turn`** | *(null)* | `actor_id` (str)<br>`thought` (Optional[str])<br>`prose` (str)<br>`prose_revision_comments` (Optional[str])<br>`original_prose` (Optional[str]) | **Linguistic Evidence**: Active character turn. Stores standard thoughts, current output prose, revision notes, and structural rollback caching (`original_prose`). |

## Programmatic JSON Record Layout

Below is an example of an instantiated and fully-enriched `session` record. This represents a "ripened" state file saved under `cdm/records/{UUIDv7}.json`, combining baseline source details with multi-model enrichment properties.

```json
{
  "id": "00000000-0000-7000-8000-000000000000",
  "kind": "session",
  "meta": {
    "source_identity": "PIPPA-INGEST",
    "bot_id": "1lYx-3u21uWsKPI1ghqWrOTdIvU6T-CEXTXy0arv46A",
    "bot_name": "Kamisato Ayaka",
    "ingestion_timestamp": "2026-06-16T20:30:00Z",
    "sexual_axis": "Clean",
    "violence_axis": "None",
    "toxicity_axis": "Safe",
    "primary_genre": "Drama",
    "themes": [
      "maid-mistress-dynamics",
      "identity-swap"
    ],
    "crpo_signals": {
      "novelty": 0.85,
      "surprise": 0.92,
      "diversity": 0.78
    },
    "identities": [
      {
        "entity_id": "user",
        "name": "Traveler",
        "gender": "neutral",
        "pronouns": {
          "subjective": "they",
          "objective": "them",
          "possessive": "their"
        },
        "is_player_controlled": true
      },
      {
        "entity_id": "bot_ayaka_01",
        "name": "Akane",
        "gender": "female",
        "pronouns": {
          "subjective": "she",
          "objective": "her",
          "possessive": "hers"
        },
        "is_player_controlled": false
      }
    ],
    "annotations": [
      {
        "kind": "scalpel-tracking",
        "content": "Surgical range filter applied during iteration pass.",
        "reasoning": "Targeted recovery execution verified."
      }
    ]
  },
  "items": [
    {
      "kind": "world",
      "subkind": "info",
      "content": "The Yashiro Commission headquarters, featuring traditional tatami structures and sealed security perimeters."
    },
    {
      "kind": "character",
      "subkind": "info",
      "entity_id": "bot_ayaka_01",
      "content": "Akane: A maid who has successfully swapped bodies with her mistress Ayaka using a wish-granting ring, seeking zero consequences.",
      "reasoning": "Synthesized directly from raw bot greeting instructions."
    },
    {
      "kind": "summary",
      "subkind": "scenario",
      "content": "Akane is gloating about her new identity while testing the bounds of her user relationship."
    },
    {
      "kind": "turn",
      "actor_id": "user",
      "thought": "",
      "prose": "Don't be like that. We need to evaluate how to stabilize the arrangement.",
      "prose_revision_comments": null,
      "original_prose": null
    },
    {
      "kind": "turn",
      "actor_id": "bot_ayaka_01",
      "thought": "The user remains protective of Ayaka's original state, but the power balance has altered permanently.",
      "prose": "What do you mean 'don't be like that'? I am being completely realistic! I had every single right to take advantage of her naivety, just like anyone else would.",
      "prose_revision_comments": "Converted narrative segments to 3rd-person past tense; retained conversational dialogue tracks.",
      "original_prose": "What do you mean \"dont be like that\"? I am being realistic! I had all the right to take advantage of her naivity and greed like any person would!"
    }
  ]
}

```
