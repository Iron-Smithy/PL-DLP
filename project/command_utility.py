import json
from pathlib import Path
from typing import Any

import subsystem.config as config

def extract_youtube_urls(text_content: str) -> list[str]:
    """Find YouTube video IDs in text and return normalized watch URLs."""
    seen_video_ids = set()
    urls = []
    for video_id in config.URL_REGEX.findall(text_content):
        if video_id not in seen_video_ids:
            seen_video_ids.add(video_id)
            urls.append(f"https://www.youtube.com/watch?v={video_id}")
    return urls

def extract_urls_from_json(json_data: Any) -> list[str]:
    """Recursively extract YouTube URLs and video IDs from JSON data."""
    found_urls = []

    if isinstance(json_data, dict):
        for key, value in json_data.items():
            if key in ("id", "videoId") and isinstance(value, str) and len(value) == 11:
                found_urls.append(f"https://www.youtube.com/watch?v={value}")
            else:
                found_urls.extend(extract_urls_from_json(value))
    elif isinstance(json_data, list):
        for item in json_data:
            found_urls.extend(extract_urls_from_json(item))
    elif isinstance(json_data, str):
        found_urls.extend(extract_youtube_urls(json_data))

    return list(dict.fromkeys(found_urls))

def extract_urls_from_file(source_path: Path) -> list[str]:
    content = source_path.read_text(encoding="utf-8").strip()

    if content.startswith("["):
        try:
            return extract_urls_from_json(json.loads(content))
        except json.JSONDecodeError:
            pass

    return extract_youtube_urls(content)

def read_url_sources(sources: list[str]) -> list[str]:
    """Expand URL arguments and text/JSON files into individual source items."""
    expanded_sources = []
    for source in sources:
        source_path = Path(source)
        if not source_path.is_file():
            expanded_sources.append(source)
            continue

        content = source_path.read_text(encoding="utf-8").strip()
        if content.startswith("["):
            expanded_sources.extend(json.loads(content))
        else:
            expanded_sources.extend(
                line.strip() for line in content.splitlines() if line.strip()
            )
    return expanded_sources
