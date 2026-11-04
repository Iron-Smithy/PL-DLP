import io
import urllib.request
from datetime import datetime
from pathlib import Path
import yt_dlp
from PIL import Image

import subsystem.config as config

class YDLQuietLogger:
    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        pass

def import_playlist(source: str, urls_to_process: list) -> list:
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(source, download=False)
        entries = info.get("entries") or []

        for entry in entries:
            if not entry:
                continue

            # Ensure we build a valid full YouTube URL from flat entries
            url_or_id = entry.get("url") or entry.get("id")
            if url_or_id:
                if not url_or_id.startswith("http"):
                    full_url = f"https://www.youtube.com/watch?v={url_or_id}"
                else:
                    full_url = url_or_id
                urls_to_process.append(full_url)
    return urls_to_process

def extract_data_from_url(url: str) -> dict:
    ydl_info_opts = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "logger": YDLQuietLogger(),
        "extract_flat": False,
    }
    with yt_dlp.YoutubeDL(ydl_info_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    USELESS_DATA = [
        "formats",
        "automatic_captions",
        "subtitles",
        "thumbnails",
        "heatmap",
        "_format_sort_fields",
    ]

    for data_type in USELESS_DATA:
        info.pop(data_type, None)

    return info

def download_thumbnail(thumbnail_url: str, save_path: Path) -> bool:
    """Downloads thumbnail image directly from its web URL."""
    if not thumbnail_url:
        return False

    try:
        request = urllib.request.Request(
            thumbnail_url,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            image_data = response.read()

        save_path.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(io.BytesIO(image_data)) as image:
            if image.mode in ("RGBA", "LA"):
                background = Image.new("RGB", image.size, "white")
                background.paste(image, mask=image.getchannel("A"))
                image = background
            else:
                image = image.convert("RGB")
            image.save(save_path, format="JPEG", quality=95)

        return save_path.exists()
    except Exception:
        return False

def get_ytdlp_options(
    target_path: Path, is_video: bool = False, hook=None
) -> dict:
    audio_ext = config.AUDIO_EXT.lstrip(".")
    video_ext = config.VIDEO_EXT.lstrip(".")

    if is_video:
        opts = {
            "format": "bestvideo+bestaudio/best",
            "outtmpl": str(target_path.with_suffix("")) + ".%(ext)s",
            "merge_output_format": video_ext,
        }
    else:
        opts = {
            "format": "bestaudio/best",
            "outtmpl": str(target_path.with_suffix("")) + ".%(ext)s",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": audio_ext,
                    "preferredquality": "0",
                }
            ],
        }

    opts.update(
        {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "logger": YDLQuietLogger(),
            "writethumbnail": False,
        }
    )

    if hook:
        opts["progress_hooks"] = [hook]

    return opts

def download_media(
    url: str, target_path: Path, is_video: bool = False, progress_callback=None
) -> bool:
    def _ydl_hook(d):
        if progress_callback and d.get("status") == "downloading":
            total = (
                d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            )
            downloaded = d.get("downloaded_bytes", 0)
            if total > 0:
                progress_callback(downloaded, total)

    opts = get_ytdlp_options(
        target_path, is_video=is_video, hook=_ydl_hook if progress_callback else None
    )

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

        if not target_path.exists():
            raise RuntimeError(
                f"yt-dlp reported success, but expected file was not created: "
                f"{target_path}"
            )

        return True
    
    except Exception as e:
        print("\n[ERROR] Download failed")
        print(f"Type: {type(e).__name__}")
        print(f"Message: {e}")
        raise

def get_iso_code(lang_input: str) -> str:
    if not lang_input:
        return config.JSON_FALLBACK_CHAR
    return config.YOUTUBE_ISO_MAP.get(lang_input, config.JSON_FALLBACK_CHAR)

def get_publish_date(info: dict) -> str:
    date_str = info.get("release_date") or info.get("upload_date")
    if date_str and len(date_str) == 8:
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

    timestamp = info.get("release_timestamp")
    if timestamp:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")

    year = info.get("release_year")
    if year:
        return f"{year}-00-00"

    return config.JSON_FALLBACK_CHAR

def select_relevant_data(info: dict) -> dict:
    return {
        "id": info.get("id"),
        "title": info.get("title"),
        "account_name": info.get("uploader") or info.get("artist"),
        "publish_date": get_publish_date(info),
        "language": get_iso_code(info.get("language")),
        "thumbnail_url": info.get("thumbnail"),
    }