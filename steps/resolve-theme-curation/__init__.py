import csv
import json
import logging
from pathlib import Path

from tqdm import tqdm

from cdm.core import CategorizationItem, Document
from cdm.meta import add_annotation, update_meta

logger = logging.getLogger(__name__)


def run(config: dict) -> None:
    """LilaKosha Pipeline Step: Theme Curation Resolution.
    Reads curated mappings from theme_clusters.csv and theme_clusters.json,
    translates raw themes to canonical forms, and writes/upserts them into
    a new CategorizationItem under category 'lilakosha:g1:theme'.
    """
    processed_vol = Path(config["volumes"]["processed"])
    records_dir = processed_vol / "cdm" / "records"
    json_path = processed_vol / "cdm" / "theme_clusters.json"
    csv_path = processed_vol / "cdm" / "theme_clusters.csv"

    if not csv_path.exists() or not json_path.exists():
        logger.error("Missing theme_clusters.csv or theme_clusters.json.")
        return

    # 1. Load Cluster Memberships
    with open(json_path, "r", encoding="utf-8") as f:
        machine_data = json.load(f)

    cluster_members = {}
    for c in machine_data.get("clusters", []):
        cluster_members[str(c["cluster_id"])] = c["members"]

    # 2. Build Translation Map from Curated CSV
    normalized_to_canonical = {}

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = str(row.get("cluster_id", "")).strip()
            if not cid or cid not in cluster_members:
                continue

            action = row.get("action", "").strip().lower()
            human_label = row.get("human_label", "").strip()
            suggested_label = row.get("suggested_label", "").strip()

            # Determine the resolved canonical label
            if action == "drop":
                resolved_label = None  # Explicit drop
            else:
                resolved_label = human_label if human_label else suggested_label
                resolved_label = resolved_label.replace(" ", "-").lower()

            for member_term in cluster_members[cid]:
                normalized_to_canonical[member_term] = resolved_label

    logger.info(
        f"Loaded curated taxonomy mapping for {len(normalized_to_canonical)} terms."
    )

    # 3. Walk Documents & Append/Update `lilakosha:g1:theme`
    canvas_files = sorted(records_dir.glob("*.json"))
    modified_count = 0

    logger.info(f"Applying canonical theme mapping to {len(canvas_files)} records...")

    for file_path in tqdm(canvas_files, desc="Applying Curated Themes"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                document = Document.model_validate_json(f.read())

            # Read raw themes from existing category=="theme" items
            raw_themes = []
            for item in document.items:
                if item.kind == "categorization" and item.category == "theme":
                    val = item.value
                    if isinstance(val, list):
                        raw_themes.extend(val)
                    elif isinstance(val, str):
                        raw_themes.append(val)

            # Map and deduplicate themes
            new_themes = set()
            for raw_tag in raw_themes:
                if not isinstance(raw_tag, str) or not raw_tag.strip():
                    continue

                normalized = (
                    raw_tag.replace("-", " ").replace("_", " ").strip().lower()
                )

                if normalized in normalized_to_canonical:
                    canonical = normalized_to_canonical[normalized]
                    if canonical:  # Exclude dropped clusters
                        new_themes.add(canonical)
                else:
                    # Pass-through unmapped/unclustered low-frequency tail terms
                    new_themes.add(raw_tag.strip().replace(" ", "-").lower())

            sorted_canonical_themes = sorted(list(new_themes))

            # Find existing target item if already present
            existing_target_item = None
            for item in document.items:
                if (
                    item.kind == "categorization"
                    and item.category == "lilakosha:g1:theme"
                ):
                    existing_target_item = item
                    break

            changed = False

            if existing_target_item:
                if existing_target_item.value != sorted_canonical_themes:
                    existing_target_item.value = sorted_canonical_themes
                    changed = True
            else:
                if sorted_canonical_themes:
                    # Calculate new categorization item ID
                    existing_cat_count = sum(
                        1
                        for item in document.items
                        if item.kind == "categorization"
                    ) + 1

                    target_item = CategorizationItem(
                        id=f"categorization-{existing_cat_count:06d}",
                        kind="categorization",
                        category="lilakosha:g1:theme",
                        value=sorted_canonical_themes,
                    )
                    document.items.append(target_item)
                    changed = True

            # Save and register metadata annotation if modified
            if changed:
                add_annotation(
                    document,
                    kind="resolve-theme-curation",
                    content=(
                        "resolved raw themes into canonical "
                        "'lilakosha:g1:theme' categorization"
                    ),
                )
                update_meta(document)

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(document.model_dump_json(indent=2, by_alias=True))
                modified_count += 1

        except Exception as e:
            logger.error(f"Failed processing {file_path.name}: {e}")

    logger.info("=" * 60)
    logger.info("✅ LILAKOSHA THEME CURATION APPLIED")
    logger.info("=" * 60)
    logger.info(f"Records Inspected : {len(canvas_files)}")
    logger.info(f"Records Modified  : {modified_count}")
    logger.info("=" * 60)
