import yt_dlp
import config
import urllib.request
from pathlib import Path
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

def download_thumbnail(thumbnail_url: str, save_path: Path) -> bool:
    """Downloads thumbnail image directly from its web URL."""
    if not thumbnail_url:
        return False
        
    try:
        # Download image file
        urllib.request.urlretrieve(thumbnail_url, save_path)
        return save_path.exists()
    except Exception as e:
        print(f"Failed to download thumbnail: {e}")
        return False

def get_ytdlp_options(target_path: Path, is_video: bool = False, hook=None) -> dict:
    """Builds clean yt-dlp configuration options."""
    
    # Base template (strip file extension from outtmpl because yt-dlp appends it)
    out_template = str(target_path.with_suffix(''))

    if is_video:
        return {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
            'outtmpl': f"{out_template}.%(ext)s",
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'progress_hooks': [hook] if hook else [],
        }
    else:
        return {
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'outtmpl': f"{out_template}.%(ext)s",
            'noplaylist': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
            'progress_hooks': [hook] if hook else [],
        }


def download_media(url: str, target_path: Path, is_video: bool = False, hook=None) -> bool:
    """Downloads either audio (.m4a) or video (.mp4) for a given URL."""
    opts = get_ytdlp_options(target_path, is_video=is_video, hook=hook)
    
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
            return True
    except Exception as e:
        print(f"Download failed for {url}: {e}")
        return False

def get_iso_code(lang_input: str) -> str:
    # If the input itself is null or empty, return "-" immediately
    if not lang_input:
        return config.JSON_FALLBACK_CHAR
    # Otherwise, look it up in the dictionary, defaulting to "-" if not found
    return config.YOUTUBE_ISO_MAP.get(lang_input, config.JSON_FALLBACK_CHAR)

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

    return config.JSON_FALLBACK_CHAR

def parse_raw_data(info: dict) -> dict:
    return {
        "id": info.get("id"),
        "url": info.get("webpage_url"),
        "thumbnail_url": info.get("thumbnail"),
        "title": info.get("title"),
        "length": info.get("duration"),
        "account_name": info.get("uploader"),
        "language": get_iso_code(info.get("language")),
        "publish_date": get_publish_date(info),
        "status": "active"
    }