import json
import config
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

def get_first_available(data, keys: list[str], default=config.JSON_FALLBACK_CHAR):
    """Retrieves the first existing key from a dictionary, returning default if none exist."""
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return default

def parse_and_update_data(raw_data: dict, ):
    pass

def merge_song_info(song: dict, info: dict) -> bool:
    updated = False

    if not info:
        return False

    # Required or visible metadata from the source should override empty placeholders.
    if info.get("id") and song.get("id") != info["id"]:
        song["id"] = info["id"]
        updated = True

    if info.get("url") and song.get("url") != info["url"]:
        song["url"] = info["url"]
        updated = True

    if info.get("title") and song.get("title") != info["title"]:
        song["title"] = info["title"]
        updated = True

    if info.get("length") is not None:
        normalized_length = format_length(info["length"])
        if song.get("length") != normalized_length:
            song["length"] = normalized_length
            updated = True

    if info.get("publish_date") and song.get("release_date") != info["publish_date"]:
        song["release_date"] = info["publish_date"]
        updated = True

    if info.get("language") and song.get("language") in (None, "", "-", config.JSON_FALLBACK_CHAR):
        song["language"] = info["language"]
        updated = True

    if info.get("account_name") and song.get("artist") in (None, "", "-", config.JSON_FALLBACK_CHAR):
        song["artist"] = info["account_name"]
        updated = True

    if info.get("thumbnail_url") and song.get("thumbnail_url") != info["thumbnail_url"]:
        song["thumbnail_url"] = info["thumbnail_url"]
        updated = True

    if song.get("download_video") not in (True, False):
        song["download_video"] = False
        updated = True

    # If status exists as part of info, keep it aligned with the extracted source.
    if song.get("status") not in ("active", "DEAD", "ERR"):
        song["status"] = "active"
        updated = True

    return updated

def format_length(length):
    if length is None:
        return config.JSON_FALLBACK_CHAR
    if isinstance(length, int):
        minutes, seconds = divmod(length, 60)
        return f"{minutes}:{seconds:02d}"
    if isinstance(length, str) and length.isdigit():
        minutes, seconds = divmod(int(length), 60)
        return f"{minutes}:{seconds:02d}"
    return str(length)