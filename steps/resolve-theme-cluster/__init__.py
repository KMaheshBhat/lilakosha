import json
import logging
from pathlib import Path

from sentence_transformers import SentenceTransformer
from sklearn.cluster import AgglomerativeClustering

logger = logging.getLogger(__name__)


def run(config: dict) -> None:
    """LilaKosha Pipeline Step: Compute semantic embeddings for unique
    normalized theme terms, cluster them into semantically related groups, and output a
    proposal manifest for human curation.
    """
    processed_vol = Path(config["volumes"]["processed"])
    models_vol = Path(config["volumes"]["models"])

    manifest_path = processed_vol / "cdm" / "extracted_themes.json"
    model_path = models_vol / "embeddings" / "bge-small-en-v1.5"
    output_path = processed_vol / "cdm" / "theme_clusters_proposal.json"

    if not manifest_path.exists():
        logger.error(f"Extracted themes manifest missing at: {manifest_path}")
        return

    if not model_path.exists():
        logger.error(f"Local embedding model path missing at: {model_path}")
        return

    # 1. Load extracted theme manifest
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    counts: dict[str, int] = manifest.get("counts", {})
    if not counts:
        logger.warning("No normalized theme terms found in manifest.")
        return

    normalized_terms = list(counts.keys())
    term_counts = list(counts.values())
    total_terms = len(normalized_terms)

    logger.info(
        f"Loaded {total_terms} unique normalized theme terms for semantic clustering."
    )

    # 2. Load Local Embedding Model
    logger.info(f"Loading local sentence embedding model from: {model_path}")
    model = SentenceTransformer(str(model_path))

    # 3. Generate Embeddings
    logger.info("Generating dense vector embeddings...")
    embeddings = model.encode(
        normalized_terms,
        batch_size=256,
        show_progress_bar=True,
        normalize_embeddings=True,
    )

    # 4. Perform Agglomerative Clustering based on Cosine Distance
    # distance_threshold=0.35 yields fine-grained semantic buckets (similarity >= 0.65)
    logger.info("Executing agglomerative semantic clustering pass...")
    clustering = AgglomerativeClustering(
        n_clusters=None, # type: ignore[arg-type]
        distance_threshold=0.35,
        metric="cosine",
        linkage="average",
    )
    cluster_labels = clustering.fit_predict(embeddings)

    # 5. Group terms into semantic clusters
    clusters_dict: dict[int, list[tuple[str, int]]] = {}
    for term, count, cluster_id in zip(
        normalized_terms, term_counts, cluster_labels
    ):
        cid = int(cluster_id)
        if cid not in clusters_dict:
            clusters_dict[cid] = []
        clusters_dict[cid].append((term, count))

    # 6. Format Clusters into Proposal Structure sorted by aggregate volume
    proposal_clusters = []
    for cid, members in clusters_dict.items():
        # Sort terms within cluster by individual term frequency
        sorted_members = sorted(members, key=lambda x: x[1], reverse=True)
        total_cluster_freq = sum(c for _, c in sorted_members)
        primary_candidate = sorted_members[0][0]

        proposal_clusters.append(
            {
                "cluster_id": cid,
                "total_frequency": total_cluster_freq,
                "suggested_label": primary_candidate,
                "human_assigned_label": None,  # Slot for human curation pass
                "terms_count": len(sorted_members),
                "top_terms": [
                    {"term": t, "count": c} for t, c in sorted_members[:20]
                ],
                "all_terms": [
                    {"term": t, "count": c} for t, c in sorted_members
                ],
            }
        )

    # Sort overall clusters by aggregate usage frequency
    proposal_clusters.sort(key=lambda x: x["total_frequency"], reverse=True)

    proposal_manifest = {
        "meta": {
            "total_terms_clustered": total_terms,
            "total_clusters_generated": len(proposal_clusters),
            "distance_threshold": 0.35,
            "metric": "cosine",
        },
        "clusters": proposal_clusters,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(proposal_manifest, f, indent=2, ensure_ascii=False)

    logger.info("=" * 60)
    logger.info("🧩 LILAKOSHA THEME CLUSTERING COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Unique Terms Clustered  : {total_terms}")
    logger.info(f"Clusters Generated      : {len(proposal_clusters)}")
    logger.info(f"Proposal Output Saved To: {output_path}")
    logger.info("=" * 60)
