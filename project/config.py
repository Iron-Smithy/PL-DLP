from pathlib import Path
import re
import json
import sys

ISO_MAP = {
    "english": "eng", 
    "french": "fre", 
    "spanish": "spa", 
    "german": "ger",
    "bengali": "ben", 
    "bosnian": "bos", 
    "bulgarian": "bul", 
    "celtic": "cel",
    "czech": "cze", 
    "chinese": "chi", 
    "danish": "dan", 
    "welsh": "wel",
    "egyption": "egy", 
    "greek": "gre", 
    "finnish": "fin", 
    "georgian": "geo",
    "irish": "gle", 
    "hebrew": "heb", 
    "hindi": "hin", 
    "hungarian": "hun",
    "icelandic": "ice", 
    "korean": "kor", 
    "latin": "lat", 
    "lithuanian": "lit",
    "mongolian": "mon", 
    "dutch": "dut", 
    "norse": "non", 
    "norwegian": "nor",
    "polish": "pol", 
    "portuguese": "por", 
    "russian": "rus", 
    "swedish": "swe",
    "vietnamese": "vie", 
    "japanese": "jpn"
}

YOUTUBE_ISO_MAP = {
    "en": "eng",       # English
    "fr": "fre",       # French
    "es": "spa",       # Spanish
    "de": "ger",       # German
    "bn": "ben",       # Bengali
    "bs": "bos",       # Bosnian
    "bg": "bul",       # Bulgarian
    "cy": "wel",       # Welsh (YouTube uses "cy")
    "cs": "cze",       # Czech
    "zh-Hans": "chi",  # Chinese (Simplified)
    "zh-Hant": "chi",  # Chinese (Traditional)
    "da": "dan",       # Danish
    "egy": "egy",      # Ancient Egyptian (No 2-letter fallback)
    "el": "gre",       # Greek
    "fi": "fin",       # Finnish
    "ka": "geo",       # Georgian
    "ga": "gle",       # Irish
    "he": "heb",       # Hebrew
    "hi": "hin",       # Hindi
    "hu": "hun",       # Hungarian
    "is": "ice",       # Icelandic
    "ko": "kor",       # Korean
    "la": "lat",       # Latin
    "lt": "lit",       # Lithuanian
    "mn": "mon",       # Mongolian
    "nl": "dut",       # Dutch
    "non": "non",      # Old Norse (No 2-letter fallback)
    "no": "nor",       # Norwegian
    "pl": "pol",       # Polish
    "pt": "por",       # Portuguese
    "ru": "rus",       # Russian
    "sv": "swe",       # Swedish
    "vi": "vie",       # Vietnamese
    "ja": "jpn"        # Japanese
}

APP_DIR = Path(__file__).parent.resolve()
CONFIG_FILE = APP_DIR / "config.json"

def _load_user_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Warning] Failed to read config.json: {e}", file=sys.stderr)
    
    # Default fallback values if installer hasn't run yet
    return {
        "music_root": str(Path.home() / "Music" / "pl-dlp"),
        "project_root": str(APP_DIR)
    }

_user_cfg = _load_user_config()

PROGRAM_ROOT = Path(_user_cfg.get("project_root", APP_DIR))
MUSIC_ROOT = Path(_user_cfg.get("music_root", Path.home() / "Music" / "pl-dlp"))

TRASH = MUSIC_ROOT / ".trash"
BACKUP = MUSIC_ROOT / ".backups"
LOG = MUSIC_ROOT / ".log.txt"

AUDIO_EXT = ".m4a"
VIDEO_EXT = ".mp4"
PLAYLIST_HEADER = "pl-"
JSON_FALLBACK_CHAR = "-"
DEFAULT_CONCURRENT_DOWNLOADS = 4

URL_REGEX = re.compile(
    r"https?://(?:(?:music|www)\.)?(?:youtube\.com/(?:watch\?v=|embed/|v/|shorts/)|youtu\.be/)([a-zA-Z0-9_-]{11})"
)