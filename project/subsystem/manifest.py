import json
import subsystem.config as config
import subsystem.downloader as downloader
from pathlib import Path
import yaml

def load_manifest(manifest_path: Path) -> dict:
    """Load a JSON or YAML playlist manifest."""
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest does not exist at {manifest_path}")

    text = manifest_path.read_text(encoding="utf-8", errors="replace")
    if manifest_path.suffix.lower() in (".yaml", ".yml"):
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)

    if not isinstance(data, dict):
        raise ValueError(f"Manifest at {manifest_path} must contain a JSON/YAML object.")
    return data

def write_manifest(manifest_path: Path, data: dict):
    with open(manifest_path, "w", encoding="utf-8") as file:
        if manifest_path.suffix.lower() in (".yaml", ".yml"):
            yaml.safe_dump(data, file, allow_unicode=True, sort_keys=False)
        else:
            json.dump(data, file, indent=4, ensure_ascii=False)

def add_track_to_metadata(manifest_path: Path, new_track_data: dict):
    # Read existing metadata
    data = load_manifest(manifest_path)

    # Determine whether the manifest key is 'songs' or 'tracks'
    key = "songs" if "songs" in data else "tracks"
    if key not in data:
        data[key] = []

    # Append new track data
    data[key].append(new_track_data)
    data["total_tracks"] = len(data[key])

    # Write updated dictionary back to disk
    write_manifest(manifest_path, data)

def get_first_available(data, keys: list[str], default=config.JSON_FALLBACK_CHAR):
    """Retrieves the first existing key from a dictionary, returning default if none exist."""
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return default

def write_empty_playlist_object(manifest_path: Path, pl_name: str):
    write_manifest(
        manifest_path,
        {
            "playlist_name": pl_name,
            "download_video_all": False,
            "total_tracks": 0,
            "songs": []
        }
    )

def create_track_entry_from_raw(raw_data: dict, url: str) -> dict:
    """Extracts YouTube metadata for a URL and returns a complete track dictionary ready for the manifest."""

    # Extract values using downloader helper functions where applicable
    pub_date = downloader.get_publish_date(raw_data) if 'downloader' in globals() else config.JSON_FALLBACK_CHAR
    iso_lang = downloader.get_iso_code(raw_data.get("language")) if 'downloader' in globals() else config.JSON_FALLBACK_CHAR

    # Build full base dictionary with extracted metadata
    song_data = {
        "id": raw_data.get("id", config.JSON_FALLBACK_CHAR),
        "url": url,
        "title": get_first_available(raw_data, ["track", "title"]),
        "artist": get_first_available(raw_data, ["artist", "creator", "uploader", "channel", "account_name"]),
        "composer": raw_data.get("composer", config.JSON_FALLBACK_CHAR),
        "vocalist_vsynth": raw_data.get("vocalist_vsynth", config.JSON_FALLBACK_CHAR),
        "language": iso_lang if iso_lang else config.JSON_FALLBACK_CHAR,
        "release_date": pub_date if pub_date else config.JSON_FALLBACK_CHAR,
        "length": format_length(raw_data.get("duration")),
        "download_video": False,
        "status": "active",
        "thumbnail_url": raw_data.get("thumbnail", config.JSON_FALLBACK_CHAR),
        "dont_override": []
    }

    # 3. Pass through merge_song_info to catch any additional overrides/formatting
    merge_song_info(raw_data, song_data)

    return song_data

def merge_song_info(song: dict, info: dict) -> bool:
    """
    Updates missing or updated fields in an existing song dictionary using raw or extracted info.
    Respects 'dont_override' entries in the song dictionary.
    Returns True if any field was modified, False otherwise.
    """
    updated = False

    if not info:
        return False

    dont_override = song.get("dont_override", [])
    if not ("id" in dont_override) and info.get("id") and song.get("id") != info["id"]:
        song["id"] = info["id"]
        updated = True

    # Title Update
    title = info.get("title") or get_first_available(info, ["track", "title"], default=None)
    if not ("title" in dont_override) and title and song.get("title") != title:
        song["title"] = title
        updated = True

    # Artist / Account Name Update
    # Checks specific 'artist' or 'account_name' / 'uploader' fields
    artist = (
        info.get("artist")
        or info.get("account_name")
        or get_first_available(info, ["creator", "uploader", "channel"], default=None)
    )
    if not ("artist" in dont_override) and artist:
        # Override if song artist is placeholder or if a new explicit artist was found
        if song.get("artist") in (None, "", "-", config.JSON_FALLBACK_CHAR) or song.get("artist") != artist:
            song["artist"] = artist
            updated = True

    # Composer Update
    composer = info.get("composer")
    if not ("composer" in dont_override) and composer and song.get("composer") != composer:
        song["composer"] = composer
        updated = True

    # Vocalist / Vsynth Update
    vocalist = info.get("vocalist_vsynth")
    if not ("vocalist_vsynth" in dont_override) and vocalist and song.get("vocalist_vsynth") != vocalist:
        song["vocalist_vsynth"] = vocalist
        updated = True

    # Release / Publish Date Update
    # Accepts raw publish_date or formats YYYYMMDD via downloader.get_publish_date
    pub_date = info.get("publish_date") or info.get("release_date")
    if not pub_date and "downloader" in globals():
        pub_date = downloader.get_publish_date(info)

    if not ("release_date" in dont_override) and pub_date and song.get("release_date") != pub_date:
        song["release_date"] = pub_date
        updated = True

    # Language Update
    # Converts language code to ISO code if raw language string is provided
    lang = info.get("language")
    if lang and len(lang) != 3 and "downloader" in globals():
        lang = downloader.get_iso_code(lang)

    if not ("language" in dont_override) and lang and song.get("language") != lang:
        song["language"] = lang
        updated = True

    # Length / Duration Update
    raw_length = info.get("length") if info.get("length") is not None else info.get("duration")
    if not ("length" in dont_override) and raw_length is not None:
        normalized_length = format_length(raw_length) if not isinstance(raw_length, str) or ":" not in raw_length else raw_length
        if song.get("length") != normalized_length:
            song["length"] = normalized_length
            updated = True

    # Thumbnail URL Update
    thumb = info.get("thumbnail_url") or info.get("thumbnail")
    if not ("thumbnail_url" in dont_override) and thumb and song.get("thumbnail_url") != thumb:
        song["thumbnail_url"] = thumb
        updated = True

    # Default / System Fields
    if song.get("download_video") not in (True, False):
        song["download_video"] = False
        updated = True

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