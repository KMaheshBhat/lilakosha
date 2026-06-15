import json
import logging
from pathlib import Path

import uuid_utils as uuid

logger = logging.getLogger(__name__)


class LedgerIndex:
    """Manages lookups and thread/process-safe additions to the common index."""

    def __init__(self, mapping_path: Path):
        self.mapping_path = mapping_path
        self._lookup = {}
        # Ensure file exists
        self.mapping_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.mapping_path.exists():
            self.mapping_path.touch()
        self._load_index()

    def _load_index(self):
        with open(self.mapping_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    # Namespace lookup using tuple composite key
                    key = (entry["source"], entry["native_id"])
                    self._lookup[key] = entry["uuid"]
                except (json.JSONDecodeError, KeyError):
                    continue

    def get_uuid(self, source: str, native_id: str) -> str | None:
        return self._lookup.get((source, native_id))

    def register_record(self, source: str, native_id: str) -> str:
        existing_uuid = self.get_uuid(source, native_id)
        if existing_uuid:
            return existing_uuid
        # Generate sortable UUIDv7
        new_uuid = str(uuid.uuid7())
        entry = {"source": source, "native_id": native_id, "uuid": new_uuid}
        # Append instantly to the mapping transaction log
        with open(self.mapping_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        self._lookup[(source, native_id)] = new_uuid
        return new_uuid
