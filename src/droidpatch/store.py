"""JSON-backed record storage for DroidPatch."""

import json
from pathlib import Path
from typing import Any


def load_records(data_file: str | Path) -> list[dict[str, Any]]:
    """Load document records from JSON; fail with a clear error if the file is invalid."""
    path = Path(data_file)
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON array in {path}, got {type(payload).__name__}")

    return payload
