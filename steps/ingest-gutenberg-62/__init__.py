import logging
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cdm import LedgerIndex
from cdm.core import (
    Annotation,
    ContentVariant,
    Document,
    DocumentMeta,
    NarrativeItem,
    SequenceItem,
)
from cdm.meta import update_meta

logger = logging.getLogger(__name__)

GUTENBERG_62_URL = "https://www.gutenberg.org/cache/epub/62/pg62.txt"
SOURCE_NATIVE_ID = "gutenberg:62"


def fetch_source_text(url: str) -> str:
    """Downloads raw Gutenberg text file."""
    logger.info(f"Fetching raw Gutenberg text from {url}")
    req = urllib.request.Request(
        url, headers={"User-Agent": "LilaKosha-Ingestion/1.0"}
    )
    with urllib.request.urlopen(req) as response:
        return response.read().decode("utf-8")


def normalize_paragraph_text(raw_block: str) -> str:
    """
    Normalizes multi-line wrapped prose into a single-line paragraph.
    1. Handles soft hyphenation at line breaks (e.g. 'horri-\nble' -> 'horrible').
    2. Collapses newlines and excess whitespace into single spaces.
    """
    text = re.sub(r"(\b\w+)-\n\s*(\w+\b)", r"\1\2", raw_block)
    text = re.sub(r"\s+", " ", text.strip())
    return text


def parse_chapter_blocks(book_text: str) -> List[Tuple[str, List[str]]]:
    """
    Parses the main book payload into structured sections (Foreword + Chapters).
    Ignores pre-foreword front matter (TOC, dedication, illustration list).
    Returns a list of tuples: (Section Title, List of Paragraph Raw Strings).
    """
    start_marker = "*** START OF THE PROJECT GUTENBERG EBOOK A PRINCESS OF MARS ***"
    end_marker = "*** END OF THE PROJECT GUTENBERG EBOOK A PRINCESS OF MARS ***"

    start_pos = book_text.find(start_marker)
    end_pos = book_text.find(end_marker)

    if start_pos == -1 or end_pos == -1:
        raise ValueError("Failed to locate standard Gutenberg boundary markers.")

    content = book_text[start_pos + len(start_marker) : end_pos]

    # Regex matching FOREWORD or CHAPTER headers
    chapter_pattern = re.compile(
        r"^(FOREWORD|CHAPTER\s+[IVXLCDM]+\s*\n\s*[^\n]+)",
        re.MULTILINE,
    )

    matches = list(chapter_pattern.finditer(content))
    if not matches:
        raise ValueError("No chapter or foreword headers found in content.")

    # Find where the actual content sections begin (skip TOC/illustrations front matter)
    # The true FOREWORD is the last match starting with FOREWORD before CHAPTER I
    first_chapter_idx = next(
        (i for i, m in enumerate(matches) if "CHAPTER I" in m.group(0)), None
    )

    if first_chapter_idx is not None and first_chapter_idx > 0:
        # Keep only matches starting from the true FOREWORD right before CHAPTER I
        valid_matches = matches[first_chapter_idx - 1 :]
    else:
        valid_matches = matches

    sections: List[Tuple[str, List[str]]] = []

    for idx, match in enumerate(valid_matches):
        header_raw = match.group(0).strip()
        title_lines = [line.strip() for line in header_raw.splitlines() if line.strip()]
        if len(title_lines) > 1:
            title = f"{title_lines[0]}: {' '.join(title_lines[1:])}"
        else:
            title = title_lines[0]

        start = match.end()
        end = (
            valid_matches[idx + 1].start()
            if idx + 1 < len(valid_matches)
            else len(content)
        )
        section_body = content[start:end]

        raw_paragraphs = [
            p.strip() for p in re.split(r"\n\s*\n", section_body) if p.strip()
        ]

        sections.append((title, raw_paragraphs))

    return sections

def extract_footnote_if_present(raw_p: str) -> Tuple[str, Optional[str]]:
    """
    Extracts standalone footnote blocks starting with '[1]', '[2]', etc.
    Returns (cleaned_text, footnote_content).
    """
    footnote_match = re.match(r"^(\[\d+\])\s+(.*)", raw_p, re.DOTALL)
    if footnote_match:
        fn_tag = footnote_match.group(1)
        fn_body = normalize_paragraph_text(footnote_match.group(2))
        return "", f"{fn_tag} {fn_body}"
    return raw_p, None


def run(config: dict) -> None:
    """
    LilaKosha Stage 1: Gutenberg #62 Ingestion.
    Transforms raw Gutenberg eBook into hierarchical CDM Sequence and Narrative Items.
    """
    processed_vol = Path(config["volumes"]["processed"])
    cdm_root = processed_vol / "cdm"
    records_dir = cdm_root / "records"
    records_dir.mkdir(parents=True, exist_ok=True)

    ledger_index = LedgerIndex(cdm_root / "mapping.jsonl")
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    target_uuid = ledger_index.get_uuid("gutenberg", SOURCE_NATIVE_ID)

    if target_uuid:
        target_file = records_dir / f"{target_uuid}.json"
        if target_file.exists():
            logger.info(
                f"Record for {SOURCE_NATIVE_ID} already "
                f"exists at {target_file}. Skipping."
            )
            return
    else:
        metadata_payload: Dict[str, Any] = {
            "book_id": "62",
            "title": "A Princess of Mars",
            "author": "Edgar Rice Burroughs",
            "source_url": GUTENBERG_62_URL,
        }
        target_uuid = ledger_index.register_record(
            source="gutenberg",
            native_id=SOURCE_NATIVE_ID,
            meta=metadata_payload,
        )
        target_file = records_dir / f"{target_uuid}.json"

    raw_text = fetch_source_text(GUTENBERG_62_URL)

    meta_obj = DocumentMeta(
        source={
            "source_identity": SOURCE_NATIVE_ID,
            "title": "A Princess of Mars",
            "author": "Edgar Rice Burroughs",
            "ingestion_timestamp": timestamp,
            "source_url": GUTENBERG_62_URL,
        },
        health={},
        stats={},
        annotations=[],
    )

    document = Document(id=target_uuid, kind="document", meta=meta_obj, items=[])

    parsed_sections = parse_chapter_blocks(raw_text)

    narrative_counter = 0
    sequence_counter = 0

    chapter_sequence_ids: List[str] = []

    for section_title, paragraphs in parsed_sections:
        section_item_ids: List[str] = []

        for raw_p in paragraphs:
            if re.match(r"^\[Illustration:.*\]$", raw_p.strip(), re.DOTALL):
                continue

            p_text, footnote_body = extract_footnote_if_present(raw_p)

            if footnote_body:
                if section_item_ids:
                    last_item_id = section_item_ids[-1]
                    for item in reversed(document.items):
                        if item.id == last_item_id and isinstance(item, NarrativeItem):
                            if item.content:
                                item.content[0].annotation = footnote_body
                            break
                else:
                    logger.warning(
                        "Found footnote block without preceding narrative item in "
                        f"section '{section_title}': {footnote_body}"
                    )
                continue

            if not p_text.strip():
                continue

            clean_text = normalize_paragraph_text(p_text)

            narrative_counter += 1
            item_id = f"narrative-{narrative_counter:06d}"

            content_variant = ContentVariant(
                name="original",
                text=clean_text,
                annotation=None,
            )

            narrative_item = NarrativeItem(
                id=item_id,
                kind="narrative",
                content=[content_variant],
            )

            document.items.append(narrative_item)
            section_item_ids.append(item_id)

        # Build SequenceItem for this section/chapter with metadata
        sequence_counter += 1
        chap_seq_id = f"seq-chap-{sequence_counter:06d}"
        chapter_seq = SequenceItem(
            id=chap_seq_id,
            kind="sequence",
            item_ids=section_item_ids,
            data={
                "title": section_title,
                "sequence_for": "chapter",
            },
        )
        document.items.append(chapter_seq)
        chapter_sequence_ids.append(chap_seq_id)

    # Build Root SequenceItem representing the entire book with metadata
    root_seq = SequenceItem(
        id="seq-book-000001",
        kind="sequence",
        item_ids=chapter_sequence_ids,
        data={
            "title": "A Princess of Mars",
            "sequence_for": "book",
        },
    )
    document.items.append(root_seq)

    if document.meta.annotations is None:
        document.meta.annotations = []
    document.meta.annotations.append(
        Annotation(
            kind="ingestion",
            content="created from Project Gutenberg ebook #62",
        )
    )

    update_meta(document)

    with open(target_file, "w", encoding="utf-8") as f:
        f.write(document.model_dump_json(indent=2, by_alias=True))

    logger.info(
        f"✅ Ingestion complete for {SOURCE_NATIVE_ID}. Output written to {target_file}"
    )
