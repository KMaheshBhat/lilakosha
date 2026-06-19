import json
import logging
from pathlib import Path
from typing import Any, Dict, Tuple

import uuid_utils as uuid

logger = logging.getLogger(__name__)


class LedgerIndex:
    """Manages lookups and thread/process-safe additions to the common index."""

    def __init__(self, mapping_path: Path):
        self.mapping_path = mapping_path
        # Explicit type signatures stop the IDE from guessing or falling back
        # to Unknown types
        self._lookup: Dict[Tuple[str, str], str] = {}

        # Ensure directory structures are active
        self.mapping_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.mapping_path.exists():
            self.mapping_path.touch()
        self._load_index()

    def _load_index(self) -> None:
        with open(self.mapping_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry: Dict[str, Any] = json.loads(line)
                    # Force strict string conversion to keep the cache map
                    # cleanly aligned
                    key = (str(entry["source"]), str(entry["native_id"]))
                    self._lookup[key] = str(entry["uuid"])
                except (json.JSONDecodeError, KeyError):
                    continue

    def get_uuid(self, source: str, native_id: str) -> str | None:
        return self._lookup.get((source, native_id))

    def register_record(
        self, source: str, native_id: str, meta: dict | None = None
    ) -> str:
        existing_uuid = self.get_uuid(source, native_id)
        if existing_uuid:
            return existing_uuid

        # Generate sortable UUIDv7 string safely
        new_uuid: str = str(uuid.uuid7())

        # Construct the clean metadata tracking row
        entry: Dict[str, Any] = {
            "source": source,
            "native_id": native_id,
            "uuid": new_uuid,
        }
        if meta is not None:
            entry["meta"] = meta

        # Append transaction log mutation line item instantly
        with open(self.mapping_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

        # Keep lookups tightly bound to primitives without leaking
        # any nested dictionaries into value slots
        self._lookup[(source, native_id)] = new_uuid
        return new_uuid
