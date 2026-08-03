import json
from pathlib import Path

def load_json_manifest(json_path: Path) -> dict:
    """Takes a specific json path and returns its contents."""
    if not json_path.exists():
        return False
    return json.loads(json_path.read_text(encoding="utf-8"))

def write_to_json(write_path: Path, data):
    with open(write_path, "w") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

def add_track_to_metadata(json_path: Path, new_track_data: dict):
    # Read existing metadata
    data = load_json_manifest(json_path)
    if data == False:
        raise ValueError("JSON does not exist")

    # Modify or append new data
    data["tracks"].append(new_track_data)
    data["total_tracks"] = len(data["tracks"])

    # Write updated dictionary back to disk
    write_to_json(json_path, data)