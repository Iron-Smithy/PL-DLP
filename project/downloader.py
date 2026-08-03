import yt_dlp
import json
import config
from datetime import datetime

def extract_data_from_url(url: str) -> dict:
    ydl_info_opts = { 'skip_download': True, 'quiet': True, 'extract_flat': False }
    with yt_dlp.YoutubeDL(ydl_info_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    USELESS_DATA = [
        'formats', 
        'automatic_captions', 
        'subtitles', 
        'thumbnails', 
        'heatmap', 
        '_format_sort_fields'
    ]

    # Remove the data bloat
    for type in USELESS_DATA:
        info.pop(type, None)
    
    return info

def get_iso_code(lang_input: str) -> str:
    # If the input itself is null or empty, return "-" immediately
    if not lang_input:
        return "-"
    # Otherwise, look it up in the dictionary, defaulting to "-" if not found
    return config.YOUTUBE_ISO_MAP.get(lang_input, "-")

def get_publish_date(info: dict) -> str:
    # Check formatted date strings ('YYYYMMDD')
    date_str = info.get("release_date") or info.get("upload_date")
    if date_str and len(date_str) == 8:
        # Convert 'YYYYMMDD' -> 'YYYY-MM-DD'
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

    # Check Unix timestamp if string dates aren't present
    timestamp = info.get("release_timestamp")
    if timestamp:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")

    # Check year-only fallback
    year = info.get("release_year")
    if year:
        return f"{year}-00-00"

    return "-"

def parse_raw_data(info: dict) -> dict:
    return {
        "id": info.get("id"),
        "url": info.get("webpage_url"),
        "thumbnail_url": info.get("thumbnail"),
        "title": info.get("title"),
        "account_name": info.get("uploader"),
        "language": get_iso_code(info.get("language")),
        "publish_date": get_publish_date(info),
        "status": "active"
    }