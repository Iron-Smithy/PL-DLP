import config

import json
from pathlib import Path

def load_json_manifest(json_path: Path) -> dict:
    """Takes a specific json path and returns its contents."""
    if not json_path.exists():
        return {}
    return json.loads(json_path.read_text(encoding="utf-8"))

def write_to_json(write_path, data):
    with open(write_path, "w") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)