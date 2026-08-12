from pathlib import Path
import shutil

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

AUDIO_EXT = ".m4a"
VIDEO_EXT = ".mp4"

PROGRAM_ROOT = Path("C:/Users/ivank/OneDrive/Desktop/My Code/Projects/Pl-dlp - 2/project")
MUSIC_ROOT = Path("C:/Users/ivank/OneDrive/Desktop/My Code/Projects/Pl-dlp - 2/musicDir")

PLAYLIST_ROOT = MUSIC_ROOT

TRASH = MUSIC_ROOT / ".trash"
BACKUP = MUSIC_ROOT / ".backups"
LOG = MUSIC_ROOT / ".log.txt"

PLAYLIST_HEADER = "pl-"
JSON_FALLBACK_CHAR = "-"
DEFAULT_CONCURRENT_DOWNLOADS = 4