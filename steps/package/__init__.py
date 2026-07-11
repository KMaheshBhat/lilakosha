import logging
from pathlib import Path

from cdm.core import Document

logger = logging.getLogger(__name__)


def run(config: dict) -> None:
    """
    LilaKosha Stage: Package (Individual UUIDv7 Canvas Records -> Single JSONL Dataset).

    Reads all individual CDM JSON records from the records directory, converts each to
    a single-line JSON format, and writes them to a dated JSONL file in the dataset
    directory.
    """
    # 1. Resolve volumes and other values from grounded config
    project = config["project"]["name"]
    mark = config["project"]["mark"]
    processed_vol = Path(config["volumes"]["processed"])
    records_dir = processed_vol / "cdm" / "records"
    dataset_dir = processed_vol / "dataset"

    # 2. Ensure dataset directory exists
    dataset_dir.mkdir(parents=True, exist_ok=True)

    # 3. Find all record files
    # UUIDv7 filenames sort lexicographically by creation time.
    record_files = sorted(records_dir.glob("*.json"))
    if not record_files:
        logger.warning(f"No canvas records found to package in {records_dir}")
        return

    logger.info(f"Packaging {len(record_files)} records for dataset export...")

    # 4. Generate output filename with date stamp
    output_file = dataset_dir / f"{project}-dataset-{mark}.jsonl"

    # 5. Stream records and write to JSONL
    success = 0
    with open(output_file, "w", encoding="utf-8") as out_f:
        for record_path in record_files:
            try:
                with open(record_path, "r", encoding="utf-8") as in_f:
                    document = Document.model_validate_json(in_f.read())

                # Write as single-line JSON (compact, no indentation)
                out_f.write(document.model_dump_json() + "\n")
                success += 1
            except Exception:
                RuntimeError("Packaging aborted: 1 record failed validation.")

    logger.info(f"✅ Packaged {success}/{len(record_files)} records to {output_file}")
