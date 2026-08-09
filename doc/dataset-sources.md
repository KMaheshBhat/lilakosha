# LilaKosha Corpus Source Portfolio

LilaKosha is built around a single source. The corpus is a collection of sources which enter through a common foundry lifecycle:

`discover → acquire / ingest → refine → resolve / prepare → package / train → publish`

The CDM remains flat across these sources. A published generation is a cut of that corpus, not a new branch of the CDM.

## Current source state

| Source                       | Discover | Acquire / Ingest | Refine  | Resolve / Prepare | Program role                 |
| ---------------------------- | -------- | ---------------- | ------- | ----------------- | ---------------------------- |
| PIPPA                        | DONE     | DONE             | DONE    | —                 | H2AI baseline                |
| Gutenberg-62                 | DONE     | DONE             | DONE    | PLANNED           | Literary structural baseline |
| lemonilia-RPGNet             | DONE     | DONE             | WIP     | PLANNED           | H2H forum baseline           |
| lemonilia-* (SFW)            | DONE     | DONE             | PLANNED | PLANNED           | H2H breadth                  |
| XenForo RP / quests          | SCOUTED  | PLANNED          | PLANNED | PLANNED           | Long-form H2H                |
| Discord / proxy ecosystems   | SCOUTED  | INVESTIGATE      | PLANNED | PLANNED           | Author / character identity  |
| RP Repository                | SCOUTED  | INVESTIGATE      | PLANNED | PLANNED           | Human semantic labels        |
| Gutenberg-*                  | DONE     | PLANNED          | PLANNED | PLANNED           | Literary breadth             |
| Other legitimate H2H sources | OPEN     | INVESTIGATE      | PLANNED | PLANNED           | Future vectors               |

The state above is deliberately source-specific. A source does not have to move through the corpus at the same time as another source, and a later generation may revisit an earlier source with a different refinement or resolution strategy.

## Candidate source priority

The following is the order in which the currently known source families are most useful to pursue.

### 1. lemonilia / RPGNet

**Current state:** acquired; refinement in progress.

This is the immediate H2H structural experiment. Unlike PIPPA, RPGNet represents human-to-human roleplay in a forum/thread/post structure. It therefore exercises a different part of the CDM without requiring another entirely different ecosystem.

The important question is not simply whether the text can be extracted. It is whether the CDM can represent contemporary collaborative writing without becoming a PIPPA-shaped model with another parser attached to it.

**Value:** H2H forum baseline and CDM challenge.

### 2. lemonilia / other SFW forums

**Current state:** discovered and available in the same source catalogue; individual acquisition and ingestion remain to be done.

The value here is breadth within the same general source family. Each forum may require its own ingestion treatment, even when the resulting CDM representation is common.

This should tell us whether the RPGNet ingestion approach is a reusable pattern or merely an RPGNet-specific treatment.

**Value:** H2H breadth and ingestion generalization.

### 3. XenForo RP / quest communities

Potential sources include SpaceBattles, Sufficient Velocity, and Questionable Questing.

These are interesting because they move further toward long-form collaborative writing. The material may contain longer narrative passages, community interaction, OOC coordination, thread structure, and other signals that are different from both PIPPA and RPGNet.

This is a useful next structural family once the current forum work has settled.

**Value:** long-form H2H collaborative writing.

### 4. Discord / Tupperbox / PluralKit ecosystems

These are currently a discovery/investigation item rather than an acquisition commitment.

The interesting possibility is that proxy systems may provide source-native distinctions between the human author and the character being represented. If accessible in a legitimate and usable form, this could provide information which would otherwise have to be inferred from the text.

This is potentially a significant challenge to the CDM's representation of authorship, character identity, turns, and OOC coordination.

**Value:** author / character identity and collaborative interaction structure.

### 5. RP Repository and similar character-profile ecosystems

These are worth investigating for a different reason. Character profiles may contain human-authored semantic information alongside writing samples: personality, traits, genre, tone, character descriptions, and other explicitly supplied metadata.

That could eventually provide useful material for comparing what the refinement pipeline infers against what the human creator actually supplied.

**Value:** human-authored semantic labels and character grounding.

### 6. Gutenberg-* beyond #62

Gutenberg-62 already served its most important purpose: it challenged the CDM with a literary document which was structurally unlike a PIPPA conversation.

The remaining Gutenberg works are still useful, particularly for corpus breadth and for exercising the generalized ingestion path, but the structural return is now lower than adding another H2H source family.

**Value:** literary breadth and continued CDM generalization.

### 7. Other legitimate H2H sources

This remains deliberately open.

Potential future sources include legitimately obtainable Discord/RP exports, community datasets, or other contemporary H2H corpora which introduce a structure or interaction pattern not already represented in the corpus.

The criterion is not simply “more roleplay text”. A new source is most interesting when it adds a new vector to the corpus.

**Value:** future H2H vectors.

## Why these sources matter

The source families currently exercise different assumptions about what a creative interaction is:

`PIPPA`
→ human ↔ AI conversation

`Gutenberg`
→ authored literary document

`RPGNet`
→ human ↔ human forum roleplay

`XenForo quests`
→ long-form collaborative writing

`Discord proxy ecosystems`
→ human author ↔ represented character ↔ human collaboration

`RP Repository`
→ human-authored character semantics + writing

The objective is therefore not simply to accumulate a large volume of text. Each additional source should either broaden the corpus or challenge an assumption in the foundry.

RPGNet is the current step because it does both.

## Source pedigree

Generation 1 currently consists of:

```text
LilaKosha-G1
├── PygmalionAI/PIPPA
├── Project Gutenberg #62
└── lemonilia/roleplaying-forums-raw
```

Additional sources may enter the G1 corpus if they are acquired and processed before the G1 cut is made.

A subsequent generation is not a fork of the G1 codebase or a special-case pipeline. It starts from the published G1 dataset cut and may add new sources:

```text
LilaKosha-G2
├── LilaKosha-G1
└── <new sources, if any>
```

The CDM remains a flat corpus. The pedigree records where material came from; it does not require the records themselves to form a tree.

A published dated dataset cut may also be used independently by someone else as a starting point. The generation label identifies the intended corpus baseline; it does not prevent another worker from choosing an earlier or differently dated cut.
