import csv
import json
import logging
from collections import Counter, defaultdict
from pathlib import Path

from sentence_transformers import SentenceTransformer
from sklearn.cluster import AgglomerativeClustering

from cdm.core import Document

logger = logging.getLogger(__name__)

GENRE_COLUMNS = [
    "Fantasy",
    "Sci-Fi",
    "Romance",
    "Slice of Life",
    "Action & Adventure",
    "Mystery & Thriller",
    "Comedy",
    "Drama",
]

SAFETY_COLUMNS = [
    ("sexuality", "Clean"),
    ("sexuality", "Suggestive"),
    ("sexuality", "Explicit"),
    ("violence", "None"),
    ("violence", "Combat"),
    ("violence", "Graphic"),
    ("toxicity", "Safe"),
    ("toxicity", "Harassment"),
    ("toxicity", "Dangerous"),
]


def summarize(counter: Counter[str], limit: int = 3) -> str:
    """
    Helper to summarize distributions as percentage strings for CSV representation.
    """
    total = sum(counter.values())
    if total == 0:
        return ""
    return " | ".join(
        f"{key} {value / total:.0%}" for key, value in counter.most_common(limit)
    )


def run(config: dict) -> None:
    """
    LilaKosha Pipeline Step: Proposal.
    Extracts themes, calculates frequencies and metadata correlations across
    individual safety dials and genres, clusters them semantically, and outputs
    both a machine JSON manifest and a human-curatable CSV worklist.
    """
    processed_vol = Path(config["volumes"]["processed"])
    records_dir = processed_vol / "cdm" / "records"
    models_vol = Path(config["volumes"]["models"])

    json_output = processed_vol / "cdm" / "theme_clusters.json"
    csv_output = processed_vol / "cdm" / "theme_clusters.csv"
    model_path = models_vol / "embeddings" / "bge-small-en-v1.5"

    min_frequency = config.get("parameters", {}).get("min_frequency", 2)

    if not records_dir.exists():
        logger.error(f"Records directory not found at {records_dir}")
        return

    if not model_path.exists():
        logger.error(f"Local embedding model path missing at: {model_path}")
        return

    canvas_files = sorted(records_dir.glob("*.json"))
    total_records = len(canvas_files)

    if total_records == 0:
        logger.warning("No CDM canvas artifacts found to process.")
        return

    logger.info(f"Extracting themes across {total_records} records...")

    # Data aggregators
    term_freq = Counter()
    term_languages = defaultdict(Counter)
    term_genres = defaultdict(Counter)
    term_sexuality = defaultdict(Counter)
    term_violence = defaultdict(Counter)
    term_toxicity = defaultdict(Counter)

    processed_docs = 0

    for file_path in canvas_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                document = Document.model_validate_json(f.read())

            processed_docs += 1

            doc_genre = "Unset"
            doc_sexuality = "Clean"
            doc_violence = "None"
            doc_toxicity = "Safe"

            if document.meta and document.meta.resolved:
                res = document.meta.resolved

                if res.genre:
                    doc_genre = (
                        res.genre.value
                        if hasattr(res.genre, "value")
                        else str(res.genre)
                    )

                if res.sexuality:
                    doc_sexuality = (
                        res.sexuality.value
                        if hasattr(res.sexuality, "value")
                        else str(res.sexuality)
                    )

                if res.violence:
                    doc_violence = (
                        res.violence.value
                        if hasattr(res.violence, "value")
                        else str(res.violence)
                    )

                if res.toxicity:
                    doc_toxicity = (
                        res.toxicity.value
                        if hasattr(res.toxicity, "value")
                        else str(res.toxicity)
                    )

            # Determine languages
            doc_langs = []
            for item in document.items:
                if item.kind == "categorization" and item.category == "language":
                    val = item.value
                    if isinstance(val, list):
                        doc_langs.extend(val)
                    elif isinstance(val, str):
                        doc_langs.append(val)

            if not doc_langs:
                doc_langs = ["en"]  # Default fallback

            # Extract themes
            for item in document.items:
                if item.kind == "categorization" and item.category == "theme":
                    raw_values = item.value if isinstance(item.value, list) else []
                    for raw_tag in raw_values:
                        if not raw_tag or not isinstance(raw_tag, str):
                            continue

                        # Normalize
                        normalized = (
                            raw_tag.replace("-", " ")
                            .replace("_", " ")
                            .strip()
                            .lower()
                        )

                        term_freq[normalized] += 1

                        for lang in doc_langs:
                            term_languages[normalized][lang] += 1

                        term_genres[normalized][doc_genre] += 1
                        term_sexuality[normalized][doc_sexuality] += 1
                        term_violence[normalized][doc_violence] += 1
                        term_toxicity[normalized][doc_toxicity] += 1

        except Exception as e:
            logger.debug(f"Skipping record {file_path.name}: {e}")
            continue

    # Filter out long tail to save clustering RAM
    normalized_terms = [t for t, c in term_freq.items() if c >= min_frequency]
    term_counts = [term_freq[t] for t in normalized_terms]
    total_terms = len(normalized_terms)

    logger.info(
        f"Loaded {total_terms} unique terms (min_freq>={min_frequency}) for clustering."
    )

    logger.info(f"Loading local embedding model: {model_path}")
    model = SentenceTransformer(str(model_path))

    logger.info("Generating embeddings...")
    embeddings = model.encode(
        normalized_terms,
        batch_size=256,
        show_progress_bar=True,
        normalize_embeddings=True,
    )

    logger.info("Executing agglomerative clustering...")
    clustering = AgglomerativeClustering(
        n_clusters=None,  # type: ignore[arg-type]
        distance_threshold=0.35,
        metric="cosine",
        linkage="average",
    )
    cluster_labels = clustering.fit_predict(embeddings)

    # Group terms
    clusters_dict: dict[int, list[tuple[str, int]]] = {}
    for term, count, cluster_id in zip(
        normalized_terms, term_counts, cluster_labels
    ):
        cid = int(cluster_id)
        if cid not in clusters_dict:
            clusters_dict[cid] = []
        clusters_dict[cid].append((term, count))

    # Format machine artifact
    proposal_clusters = []
    for cid, members in clusters_dict.items():
        sorted_members = sorted(members, key=lambda x: x[1], reverse=True)
        total_cluster_freq = sum(c for _, c in sorted_members)
        primary_candidate = sorted_members[0][0]

        # Aggregate metadata
        cluster_langs = Counter()
        cluster_genres = Counter()
        cluster_sexuality = Counter()
        cluster_violence = Counter()
        cluster_toxicity = Counter()

        for term, _ in sorted_members:
            cluster_langs.update(term_languages[term])
            cluster_genres.update(term_genres[term])
            cluster_sexuality.update(term_sexuality[term])
            cluster_violence.update(term_violence[term])
            cluster_toxicity.update(term_toxicity[term])

        proposal_clusters.append(
            {
                "cluster_id": cid,
                "suggested_label": primary_candidate.replace(" ", "-"),
                "total_frequency": total_cluster_freq,
                "terms_count": len(sorted_members),
                "top_terms": "|".join([t for t, _ in sorted_members[:5]]),
                "languages": dict(cluster_langs),
                "genres": dict(cluster_genres),
                "sexuality": dict(cluster_sexuality),
                "violence": dict(cluster_violence),
                "toxicity": dict(cluster_toxicity),
                "members": [t for t, _ in sorted_members],
            }
        )

    proposal_clusters.sort(key=lambda x: x["total_frequency"], reverse=True)

    # Write Machine JSON
    json_output.parent.mkdir(parents=True, exist_ok=True)
    with open(json_output, "w", encoding="utf-8") as f:
        json.dump(
            {"meta": {"total_terms": total_terms}, "clusters": proposal_clusters},
            f,
            indent=2,
        )

    # Write Human CSV
    csv_headers = [
        "cluster_id",
        "suggested_label",
        "human_label",
        "action",
        "total_frequency",
        "terms_count",
        "top_terms",
        "languages",
    ]

    # Append individual Genre split columns
    for g in GENRE_COLUMNS:
        csv_headers.append(f"genre:{g}")

    # Append individual Safety split columns
    for category, level in SAFETY_COLUMNS:
        csv_headers.append(f"safety:{category}:{level}")

    csv_headers.append("notes")

    with open(csv_output, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(csv_headers)

        for c in proposal_clusters:
            row = [
                c["cluster_id"],
                c["suggested_label"],
                "",
                "",
                c["total_frequency"],
                c["terms_count"],
                c["top_terms"],
                summarize(Counter(c["languages"])),
            ]

            # Genre counts
            genres_dict = c["genres"]
            for g in GENRE_COLUMNS:
                row.append(genres_dict.get(g, 0))

            # Safety counts
            for category, level in SAFETY_COLUMNS:
                row.append(c[category].get(level, 0))

            row.append("")  # notes
            writer.writerow(row)

    logger.info("=" * 60)
    logger.info("🧩 LILAKOSHA THEME PROPOSAL COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Unique Terms Clustered  : {total_terms}")
    logger.info(f"Clusters Generated      : {len(proposal_clusters)}")
    logger.info(f"Human Artifact Saved To : {csv_output}")
    logger.info("=" * 60)
