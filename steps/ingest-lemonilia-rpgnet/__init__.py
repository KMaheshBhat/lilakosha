import hashlib
import json
import logging
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import unquote

import duckdb
from bs4 import BeautifulSoup
from bs4.element import Tag
from tqdm import tqdm

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


def compute_content_address(raw_record: dict) -> str:
    """
    Computes a deterministic SHA-256 fingerprint of a raw source record.

    This is retained as a diagnostic/content-address helper. It is not used
    as the primary thread identity.
    """
    standardized_bytes = json.dumps(
        raw_record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    return hashlib.sha256(standardized_bytes).hexdigest()


def extract_thread_identity(
    thread_url: str | None,
) -> tuple[str, str]:
    """
    Extract thread ID and slug from a XenForo thread URL.

    Examples:

        /index.php?threads/some-thread.12345/
        /index.php?threads/some-thread.12345/post-67890

    Returns:
        (thread_id, thread_slug)
    """
    if not thread_url:
        return "", ""

    match = re.search(
        r"/index\.php\?threads/(.+)\.(\d+)(?:/|$)",
        thread_url,
    )

    if not match:
        return "", ""

    return (
        match.group(2),
        unquote(match.group(1)),
    )


def get_safe_attribute(
    element: Tag | None,
    attr: str,
) -> str:
    """
    BeautifulSoup helper to safely retrieve an attribute value as a string.
    """
    if element is None:
        return ""

    value = element.get(attr)

    if value is None:
        return ""

    if isinstance(value, list):
        return " ".join(str(item) for item in value)

    return str(value)


def extract_post_id(post: Tag) -> str:
    """
    Extract the stable numeric XenForo post ID.

    Prefer:
        data-content="post-123"

    then:
        id="js-post-123"

    Final fallback:
        an explicit /posts/123 URL.
    """

    data_content = get_safe_attribute(
        post,
        "data-content",
    )

    match = re.fullmatch(
        r"post-(\d+)",
        data_content,
    )

    if match:
        return match.group(1)

    element_id = get_safe_attribute(
        post,
        "id",
    )

    match = re.fullmatch(
        r"js-post-(\d+)",
        element_id,
    )

    if match:
        return match.group(1)

    for link in post.select("a[href]"):
        href = get_safe_attribute(
            link,
            "href",
        )

        match = re.search(
            r"/posts/(\d+)/?",
            href,
        )

        if match:
            return match.group(1)

    return ""


def extract_post_url(post: Tag) -> str:
    """
    Extract the XenForo post URL attached to the post.

    Example:

        /index.php?threads/some-thread.12345/post-67890
    """

    for link in post.select("a[href]"):
        href = get_safe_attribute(
            link,
            "href",
        )

        if re.search(
            r"/index\.php\?threads/.+\.\d+/post-\d+",
            href,
        ):
            return href

    return ""


def extract_thread_url(post: Tag) -> str:
    """
    Recover the containing XenForo thread URL from the post.

    The returned value is the canonical thread URL without the
    post-specific suffix.
    """

    parent_item = post.find(
        "meta",
        attrs={"itemprop": "parentItem"},
    )

    if isinstance(parent_item, Tag):
        thread_url = get_safe_attribute(
            parent_item,
            "itemid",
        )

        if thread_url:
            return re.sub(
                r"/post-\d+/?$",
                "/",
                thread_url,
            )

    post_url = extract_post_url(post)

    if post_url:
        return re.sub(
            r"/post-\d+/?$",
            "/",
            post_url,
        )

    return ""


def extract_author(post: Tag) -> tuple[str, str]:
    """
    Extract stable author identity and display name.

    Returns:
        (author_id, author_name)
    """

    author_name = get_safe_attribute(
        post,
        "data-author",
    ).strip()

    author_id = ""

    author_link = post.select_one(
        "a[data-user-id]"
    )

    if isinstance(author_link, Tag):
        author_id = get_safe_attribute(
            author_link,
            "data-user-id",
        ).strip()

    if not author_name:
        name_node = post.select_one(
            '[itemprop="author"] [itemprop="name"]'
        )

        if isinstance(name_node, Tag):
            author_name = name_node.get_text(
                " ",
                strip=True,
            )

    return author_id, author_name


def extract_timestamp(post: Tag) -> str:
    """
    Extract the ISO-8601 publication timestamp.
    """

    time_node = post.select_one(
        "time[datetime]"
    )

    if not isinstance(time_node, Tag):
        return ""

    return get_safe_attribute(
        time_node,
        "datetime",
    ).strip()


def extract_post_content(post: Tag) -> str:
    """
    Extract the original RPGnet post HTML.

    The original ContentVariant retains this HTML as its text payload.
    HTML -> Markdown is performed later by refine-cdm-html-to-markdown.
    """

    user_content = post.select_one(
        "div.message-userContent"
    )

    if not isinstance(user_content, Tag):
        return ""

    message_body = user_content.select_one(
        "article.message-body"
    )

    if isinstance(message_body, Tag):
        content_node = message_body
    else:
        content_node = user_content

    wrapper = content_node.select_one(
        "div.bbWrapper"
    )

    if isinstance(wrapper, Tag):
        content_node = wrapper

    return content_node.decode_contents()


def extract_thread_title(
    soup: BeautifulSoup,
) -> str:
    """
    Extract the visible thread title when available.
    """

    title_node = soup.select_one("h1")

    if not isinstance(title_node, Tag):
        return ""

    return title_node.get_text(
        " ",
        strip=True,
    )


def extract_posts_from_html(
    html_content: str,
) -> List[Dict[str, Any]]:
    """
    Extract post-level records from one scraped RPGnet/XenForo page.

    A source page may contain a complete thread or a partial thread snapshot.
    Thread identity is therefore recovered independently from each post.
    """

    soup = BeautifulSoup(
        html_content,
        "html.parser",
    )

    thread_title = extract_thread_title(
        soup
    )

    posts: List[Dict[str, Any]] = []

    post_articles = soup.select(
        "article.message.message--post"
    )

    for post_index, article in enumerate(
        post_articles,
        start=1,
    ):
        post_id = extract_post_id(
            article
        )

        if not post_id:
            logger.warning(
                "Skipping RPGnet post without post ID "
                "(post index %s)",
                post_index,
            )
            continue

        thread_url = extract_thread_url(
            article
        )

        thread_id, thread_slug = (
            extract_thread_identity(
                thread_url
            )
        )

        if not thread_id:
            logger.warning(
                "Skipping RPGnet post %s: "
                "unable to determine thread identity",
                post_id,
            )
            continue

        author_id, author_name = extract_author(
            article
        )

        timestamp = extract_timestamp(
            article
        )

        post_html = extract_post_content(
            article
        )

        if not post_html:
            logger.warning(
                "Skipping RPGnet post %s: empty post content",
                post_id,
            )
            continue

        posts.append(
            {
                "post_index": post_index,
                "post_id": post_id,
                "post_url": extract_post_url(article),
                "thread_id": thread_id,
                "thread_slug": thread_slug,
                "thread_url": thread_url,
                "thread_title": thread_title,
                "author_id": author_id,
                "author": author_name,
                "timestamp": timestamp,
                "text": post_html,
            }
        )

    return posts


def get_next_narrative_counter(
    narrative_item_ids: List[str],
) -> int:
    """
    Return the next unused narrative item counter.
    """

    max_counter = 0

    for item_id in narrative_item_ids:
        match = re.fullmatch(
            r"narrative-(\d+)",
            item_id,
        )

        if match:
            max_counter = max(
                max_counter,
                int(match.group(1)),
            )

    return max_counter + 1


def rebuild_thread_sequence(
    document: Document,
    thread_id: str,
    thread_slug: str,
) -> None:
    """
    Rebuild the canonical ordered sequence for the thread.

    Ordering is based on source timestamp, with numeric post ID as the
    deterministic secondary key.
    """

    narrative_items = [
        item
        for item in document.items
        if isinstance(item, NarrativeItem)
    ]

    def sort_key(
        item: NarrativeItem,
    ) -> tuple[str, int]:
        timestamp = ""
        post_id = ""

        for variant in item.content:
            if variant.name != "original":
                continue

            extra_fields = variant.model_extra or {}

            timestamp = str(
                extra_fields.get(
                    "timestamp",
                    "",
                )
            )

            post_id = str(
                extra_fields.get(
                    "post_id",
                    "",
                )
            )

            break

        try:
            numeric_post_id = int(post_id)
        except (TypeError, ValueError):
            numeric_post_id = 0

        return (
            timestamp,
            numeric_post_id,
        )

    narrative_items.sort(
        key=sort_key
    )

    narrative_item_ids = [
        item.id
        for item in narrative_items
    ]

    document.items = [
        item
        for item in document.items
        if not (
            isinstance(item, SequenceItem)
            and item.id == "seq-thread-000001"
        )
    ]

    document.items.append(
        SequenceItem(
            id="seq-thread-000001",
            kind="sequence",
            item_ids=narrative_item_ids,
            data={
                "title": thread_slug,
                "sequence_for": "thread",
                "thread_id": thread_id,
            },
        )
    )


def reconcile_thread(
    *,
    thread_id: str,
    thread_posts: List[Dict[str, Any]],
    section_url: str,
    records_dir: Path,
    ledger_index: LedgerIndex,
    timestamp: str,
) -> tuple[bool, int]:
    """
    Reconcile one RPGnet thread into its CDM Document.

    Returns:
        (document_changed, newly_added_post_count)
    """

    native_thread_key = (
        f"rpgnet:thread:{thread_id}"
    )

    target_uuid = ledger_index.get_uuid(
        "lemonilia-rpgnet",
        native_thread_key,
    )

    target_file = (
        records_dir
        / f"{target_uuid}.json"
        if target_uuid
        else None
    )

    document: Document
    is_new_document = False

    # ------------------------------------------------------------------
    # Load existing document
    # ------------------------------------------------------------------

    if (
        target_file is not None
        and target_file.exists()
    ):
        with open(
            target_file,
            "r",
            encoding="utf-8",
        ) as handle:
            document = Document(
                **json.load(handle)
            )

        if document.meta.annotations is None:
            document.meta.annotations = []

    # ------------------------------------------------------------------
    # Create new document
    # ------------------------------------------------------------------

    else:
        is_new_document = True

        first_post = thread_posts[0]

        thread_slug = first_post[
            "thread_slug"
        ]

        canonical_thread_url = (
            f"/index.php?threads/"
            f"{thread_slug}.{thread_id}/"
        )

        metadata_payload: Dict[str, Any] = {
            "section_url": section_url,
            "thread_id": thread_id,
            "thread_slug": thread_slug,
            "thread_url": canonical_thread_url,
        }

        target_uuid = ledger_index.register_record(
            source="lemonilia-rpgnet",
            native_id=native_thread_key,
            meta=metadata_payload,
        )

        target_file = (
            records_dir
            / f"{target_uuid}.json"
        )

        meta_obj = DocumentMeta()

        meta_obj.source = {
            "source_identity": "lemonilia/roleplaying-forums-raw",
            "forum_name": "RPGnet",
            "section_url": section_url,
            "thread_id": thread_id,
            "thread_slug": thread_slug,
            "thread_url": canonical_thread_url,
            "ingestion_timestamp": timestamp,
        }

        meta_obj.health = {}
        meta_obj.stats = {}
        meta_obj.annotations = []

        document = Document(
            id=target_uuid,
            kind="document",
            meta=meta_obj,
            items=[],
        )

    # ------------------------------------------------------------------
    # Build existing post identity index
    # ------------------------------------------------------------------

    post_id_to_item: Dict[
        str,
        NarrativeItem,
    ] = {}

    narrative_item_ids: List[str] = []

    for item in document.items:

        if not isinstance(
            item,
            NarrativeItem,
        ):
            continue

        narrative_item_ids.append(
            item.id
        )

        for variant in item.content:

            if variant.name != "original":
                continue

            extra_fields = (
                variant.model_extra
                or {}
            )

            post_id = extra_fields.get(
                "post_id"
            )

            if post_id:
                post_id_to_item[
                    str(post_id)
                ] = item

    next_counter = get_next_narrative_counter(
        narrative_item_ids
    )

    new_posts_added = False
    posts_updated = False
    newly_added_posts = 0

    # ------------------------------------------------------------------
    # Reconcile posts into this thread document
    # ------------------------------------------------------------------

    for post in thread_posts:

        post_id = str(
            post["post_id"]
        )

        existing_item = (
            post_id_to_item.get(
                post_id
            )
        )

        # --------------------------------------------------------------
        # Existing post: reconcile
        # --------------------------------------------------------------

        if existing_item is not None:

            for index, variant in enumerate(
                existing_item.content
            ):

                if variant.name != "original":
                    continue

                extra_fields = (
                    variant.model_extra
                    or {}
                )

                old_text = variant.text

                old_author_id = str(
                    extra_fields.get(
                        "author_id",
                        "",
                    )
                )

                old_author_name = str(
                    extra_fields.get(
                        "author_name",
                        "",
                    )
                )

                old_timestamp = str(
                    extra_fields.get(
                        "timestamp",
                        "",
                    )
                )

                old_post_url = str(
                    extra_fields.get(
                        "post_url",
                        "",
                    )
                )

                old_thread_url = str(
                    extra_fields.get(
                        "thread_url",
                        "",
                    )
                )

                new_author_id = str(
                    post["author_id"]
                    or ""
                )

                new_author_name = str(
                    post["author"]
                    or ""
                )

                new_timestamp = str(
                    post["timestamp"]
                    or ""
                )

                new_post_url = str(
                    post["post_url"]
                    or ""
                )

                new_thread_url = str(
                    post["thread_url"]
                    or ""
                )

                changed = (
                    old_text
                    != post["text"]
                    or old_author_id
                    != new_author_id
                    or old_author_name
                    != new_author_name
                    or old_timestamp
                    != new_timestamp
                    or old_post_url
                    != new_post_url
                    or old_thread_url
                    != new_thread_url
                )

                if changed:
                    updated_variant = ContentVariant(
                        name="original",
                        text=post["text"],
                        **{
                            "actor_id": new_author_id,
                            "author_id": new_author_id,
                            "author_name": new_author_name,
                            "post_id": post_id,
                            "timestamp": new_timestamp,
                            "post_url": new_post_url,
                            "thread_id": thread_id,
                            "thread_url": new_thread_url,
                        },
                    )

                    existing_item.content[
                        index
                    ] = updated_variant

                    posts_updated = True

                break

        # --------------------------------------------------------------
        # New post: create NarrativeItem
        # --------------------------------------------------------------

        else:

            item_id = (
                f"narrative-{next_counter:06d}"
            )

            next_counter += 1

            narrative_item = NarrativeItem(
                id=item_id,
                kind="narrative",
                content=[
                    ContentVariant(
                        name="original",
                        text=post["text"],
                        **{
                            "actor_id": post["author_id"],
                            "author_id": post["author_id"],
                            "author_name": post["author"],
                            "post_id": post_id,
                            "timestamp": post["timestamp"],
                            "post_url": post["post_url"],
                            "thread_id": thread_id,
                            "thread_url": post["thread_url"],
                        },
                    )
                ],
            )

            document.items.append(
                narrative_item
            )

            narrative_item_ids.append(
                item_id
            )

            post_id_to_item[
                post_id
            ] = narrative_item

            new_posts_added = True
            newly_added_posts += 1

    # ------------------------------------------------------------------
    # Rebuild ordered thread sequence
    # ------------------------------------------------------------------

    if (
        is_new_document
        or new_posts_added
        or posts_updated
    ):
        rebuild_thread_sequence(
            document,
            thread_id,
            thread_posts[0]["thread_slug"],
        )

    # ------------------------------------------------------------------
    # Append ingestion lineage annotation
    # ------------------------------------------------------------------

    if (
        is_new_document
        or new_posts_added
        or posts_updated
    ):
        status = (
            "created"
            if is_new_document
            else "reconciled"
        )

        if document.meta.annotations is None:
            document.meta.annotations = []

        document.meta.annotations.append(
            Annotation(
                kind="ingestion",
                content=(
                    f"document {status} from RPGnet raw "
                    f"Parquet source page ({section_url}) "
                    f"for thread {thread_id}"
                ),
            )
        )

    # ------------------------------------------------------------------
    # Update CDM materialized metadata
    # ------------------------------------------------------------------

    update_meta(
        document
    )

    # ------------------------------------------------------------------
    # Write CDM document
    # ------------------------------------------------------------------

    with open(
        target_file,
        "w",
        encoding="utf-8",
    ) as handle:
        handle.write(
            document.model_dump_json(
                indent=2,
                by_alias=True,
            )
        )

    return (
        is_new_document
        or new_posts_added
        or posts_updated,
        newly_added_posts,
    )


def process_batch(
    rows: List[tuple],
    column_names: List[str],
    records_dir: Path,
    ledger_index: LedgerIndex,
    timestamp: str,
) -> tuple[int, int, int]:
    """
    Process one bounded batch of DuckDB source rows.

    Returns:
        (
            processed_document_count,
            newly_added_post_count,
            skipped_row_count,
        )
    """

    processed_documents = 0
    processed_posts = 0
    skipped_rows = 0

    for row in rows:

        raw_record = dict(
            zip(
                column_names,
                row,
            )
        )

        section_url = str(
            raw_record.get(
                "section_url",
                "",
            )
        )

        raw_html = (
            raw_record.get(
                "contents"
            )
            or ""
        )

        if not raw_html:
            skipped_rows += 1
            continue

        # --------------------------------------------------------------
        # Extract all posts from this source page
        # --------------------------------------------------------------

        incoming_posts = extract_posts_from_html(
            raw_html
        )

        if not incoming_posts:
            skipped_rows += 1
            continue

        # --------------------------------------------------------------
        # Group posts by native RPGnet thread ID
        # --------------------------------------------------------------

        posts_by_thread: Dict[
            str,
            List[Dict[str, Any]],
        ] = defaultdict(list)

        for post in incoming_posts:
            posts_by_thread[
                post["thread_id"]
            ].append(post)

        # --------------------------------------------------------------
        # Reconcile each represented thread
        # --------------------------------------------------------------

        for thread_id, thread_posts in posts_by_thread.items():

            if not thread_id:
                continue

            changed, newly_added_posts = reconcile_thread(
                thread_id=thread_id,
                thread_posts=thread_posts,
                section_url=section_url,
                records_dir=records_dir,
                ledger_index=ledger_index,
                timestamp=timestamp,
            )

            if changed:
                processed_documents += 1

            processed_posts += newly_added_posts

    return (
        processed_documents,
        processed_posts,
        skipped_rows,
    )


def run(config: dict) -> None:
    """
    LilaKosha Stage 1: RPGnet Ingestion.

    Reads the acquired RPGnet XenForo HTML Parquet corpus, extracts posts,
    groups them by native RPGnet thread ID, and reconciles those posts
    into CDM Document records through LedgerIndex.

    The ingestion is restart-safe and idempotent at thread/post identity level.

    Source-row processing is deliberately bounded by batch_size so that
    the complete Parquet result set is never materialized in memory.

    `limit` and `batch_size` are independent:

        limit      = maximum number of source rows to process
        batch_size = number of source rows fetched into memory at once
    """

    # ------------------------------------------------------------------
    # 1. Resolve source and destination volumes
    # ------------------------------------------------------------------

    raw_vol = Path(
        config["volumes"]["raw"]
    )

    rpgnet_dir = (
        raw_vol
        / "raw"
        / "lemonilia"
        / "roleplaying-forums-raw"
    )

    parquet_pattern = (
        rpgnet_dir
        / "RPGnet--roleplay-by-post-play-forum--part*.parquet"
    )

    parquet_files = list(
        rpgnet_dir.glob(
            "RPGnet--roleplay-by-post-play-forum--part*.parquet"
        )
    )

    if not parquet_files:
        raise FileNotFoundError(
            f"Raw RPGnet dataset not found at {rpgnet_dir}. "
            "Ensure the 'acquire' step has executed successfully."
        )

    processed_vol = Path(
        config["volumes"]["processed"]
    )

    cdm_root = (
        processed_vol
        / "cdm"
    )

    records_dir = (
        cdm_root
        / "records"
    )

    records_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ------------------------------------------------------------------
    # 2. Instantiate cross-source LedgerIndex
    # ------------------------------------------------------------------

    mapping_file = (
        cdm_root
        / "mapping.jsonl"
    )

    ledger_index = LedgerIndex(
        mapping_file
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d%H%M%S"
    )

    parameters = config.get(
        "parameters",
        {},
    )

    sample_limit = parameters.get(
        "limit"
    )

    batch_size = int(
        parameters.get(
            "batch_size",
            25,
        )
    )

    if batch_size <= 0:
        raise ValueError(
            f"batch_size must be greater than zero, got {batch_size}"
        )

    logger.info(
        "Processing local raw RPGnet dataset from %s "
        "(limit: %s, batch_size: %s) target: %s",
        rpgnet_dir,
        sample_limit,
        batch_size,
        records_dir,
    )

    # ------------------------------------------------------------------
    # 3. Build source query
    #
    # `limit` remains a source-selection constraint.
    # Batching is performed by fetchmany() below.
    # ------------------------------------------------------------------

    limit_clause = ""

    if sample_limit is not None:
        limit_clause = (
            f" LIMIT {int(sample_limit)}"
        )

    query = f"""
        SELECT
            section_url,
            contents
        FROM read_parquet('{parquet_pattern.as_posix()}')
        {limit_clause}
    """

    # ------------------------------------------------------------------
    # 4. Open DuckDB and stream bounded batches
    # ------------------------------------------------------------------

    con = duckdb.connect(
        database=":memory:"
    )

    processed_documents = 0
    processed_posts = 0
    skipped_rows = 0
    processed_source_rows = 0

    try:
        cursor = con.execute(
            query
        )

        column_names = [
            description[0]
            for description in con.description
        ]

        # Do not fetchall().
        #
        # DuckDB keeps the query cursor alive while we consume it in
        # bounded batches. At most batch_size source rows are materialized
        # here at a time.
        progress_total = (
            int(sample_limit)
            if sample_limit is not None
            else None
        )

        with tqdm(
            total=progress_total,
            desc="Ingesting & Reconciling RPGnet",
            unit="row",
        ) as progress:

            while True:

                rows = cursor.fetchmany(
                    batch_size
                )

                if not rows:
                    break

                batch_documents, batch_posts, batch_skipped = (
                    process_batch(
                        rows=rows,
                        column_names=column_names,
                        records_dir=records_dir,
                        ledger_index=ledger_index,
                        timestamp=timestamp,
                    )
                )

                processed_source_rows += len(
                    rows
                )

                processed_documents += (
                    batch_documents
                )

                processed_posts += (
                    batch_posts
                )

                skipped_rows += (
                    batch_skipped
                )

                progress.update(
                    len(rows)
                )

                logger.info(
                    "RPGnet batch complete: "
                    "%s source row(s) processed, "
                    "%s thread document(s) changed, "
                    "%s post(s) newly added, "
                    "%s source row(s) skipped",
                    processed_source_rows,
                    batch_documents,
                    batch_posts,
                    batch_skipped,
                )

    finally:
        con.close()

    logger.info(
        "RPGnet ingestion & reconciliation complete: "
        "%s source row(s) processed, "
        "%s thread document(s) changed, "
        "%s post(s) newly added, "
        "%s source row(s) skipped. "
        "CDM records written to %s",
        processed_source_rows,
        processed_documents,
        processed_posts,
        skipped_rows,
        records_dir,
    )
