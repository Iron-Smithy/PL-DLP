from pathlib import Path
import shutil

PROGRAM_ROOT = Path("C:/Users/ivank/OneDrive/Desktop/My Code/Projects/Pl-dlp - 2/project")
MUSIC_ROOT = Path("C:/Users/ivank/OneDrive/Desktop/My Code/Projects/Pl-dlp - 2/musicDir")

PLAYLIST_ROOT = MUSIC_ROOT

TRASH = MUSIC_ROOT / ".trash"
BACKUP = MUSIC_ROOT / ".backups"
LOG = MUSIC_ROOT / ".log.txt"

PLAYLIST_HEADER = "pl-"
JSON_FALLBACK_CHAR = "-"