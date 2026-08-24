import re
import subprocess
from pathlib import Path
from PIL import Image
from mutagen.id3 import APIC, ID3, ID3NoHeaderError

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
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    if not output_path.exists():
        raise RuntimeError(f"ffmpeg completed but did not create {output_path}")

def embed_mp3_cover(mp3_path: Path, cover_jpg_path: Path):
    """Embeds a JPG image directly into the MP3 ID3 metadata tag using ID3v2.3 for increased compatibility."""
    if not mp3_path.exists() or not cover_jpg_path.exists():
        return

    try:
        try:
            tags = ID3(mp3_path)
        except ID3NoHeaderError:
            tags = ID3()

        with open(cover_jpg_path, "rb") as img:
            tags.add(
                APIC(
                    encoding=0,  # ISO-8859-1 / Latin-1 required for ID3v2.3 compatibility
                    mime="image/jpeg",
                    type=3,  # Front Cover
                    desc="Cover",
                    data=img.read(),
                )
            )

        tags.save(mp3_path, v2_version=3)
    except Exception as e:
        print(f"Failed to embed cover art: {e}")