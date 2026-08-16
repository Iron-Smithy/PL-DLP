import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from PIL import Image

import config

# Strips illegal OS characters: < > : " / \ | ? * and control codes
ILLEGAL_CHAR_REGEX = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

def sanitize_filename(filename: str, strict_ascii: bool = False) -> str:
    """Removes OS-illegal characters and optionally restricts output to ASCII for older MP3 players."""
    cleaned = ILLEGAL_CHAR_REGEX.sub("_", filename).strip(" .")
    if strict_ascii:
        cleaned = cleaned.encode("ascii", "ignore").decode("ascii").strip(" .")
    return cleaned or "unnamed_track"

def adjust_image_quality(image_path: Path, max_dimension: int = 500):
    """Downscales thumbnail resolution if larger than max_dimension."""
    if not image_path.exists():
        return
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            if width > max_dimension or height > max_dimension:
                img.thumbnail(
                    (max_dimension, max_dimension), Image.Resampling.LANCZOS
                )
                img.save(image_path, quality=85, optimize=True)
    except Exception:
        pass

def convert_media(
    input_path: Path, output_path: Path, target_format: str, strip_video: bool = True
):
    """Converts media files and strips video streams when exporting to standard audio formats."""
    cmd = ["ffmpeg", "-y", "-i", str(input_path)]

    if strip_video or target_format in ("mp3", "m4a", "flac", "wav"):
        cmd.append("-vn")

    if target_format == "mp3":
        cmd.extend(["-c:a", "libmp3lame", "-q:a", "2"])
    elif target_format == "m4a":
        cmd.extend(["-c:a", "aac", "-b:a", "192k"])

    cmd.append(str(output_path))
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)