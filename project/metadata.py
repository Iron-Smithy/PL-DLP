from mutagen.mp4 import MP4, MP4Cover
from pathlib import Path

def write_audio_metadata(audio_path: Path, data: dict, cover_jpg_path: Path = None, delete_thumbnail: bool = True):
    """Embeds MP4 metadata atoms directly into an M4A file."""
    # Ensure file exists before opening
    if not audio_path.exists():
        raise ValueError(f"Audio file not found at {audio_path}")

    audio = MP4(audio_path)
    
    # Mutagen keys use the '/xa9' unicode character instead of the raw symbol sometimes
    audio['/xa9nam'] = data.get('title', '-')
    audio['/xa9ART'] = data.get('artist', '-')
    audio['/xa9wrt'] = data.get('composer', '-')
    audio['/xa9day'] = data.get('release_date', '-')
    audio['/xa9lan'] = data.get('language', '-')
    audio['/xa9per'] = data.get('vocalist_vsynth', '-')


    video_id = data.get('id', '')
    if video_id:
        # Store in standard comment field (Visible in Windows)
        audio['/xa9cmt'] = f"YouTube ID: {video_id}"
        
        # Store in a hidden custom iTunes atom (Clean database style)
        id_bytes = video_id.encode('utf-8')
        audio['***REMOVED***-:com.apple.iTunes:YT_ID'] = [id_bytes]

    # Attach cover artwork
    if cover_jpg_path and cover_jpg_path.exists():
        with open(cover_jpg_path, 'rb') as img:
            audio['covr'] = [MP4Cover(img.read(), imageformat=MP4Cover.FORMAT_JPEG)]

    # Save metadata back into the .m4a binary
    audio.save()

    if delete_thumbnail and cover_jpg_path and cover_jpg_path.exists():
        cover_jpg_path.unlink()


def write_audio_thumbnail(audio_path: Path, cover_jpg_path: Path, delete_thumbnail: bool = True):
    if not audio_path.exists():
        raise ValueError(f"Audio file not found at {audio_path}")

    audio = MP4(audio_path)

    if cover_jpg_path and cover_jpg_path.exists():
        with open(cover_jpg_path, 'rb') as img:
            audio['covr'] = [MP4Cover(img.read(), imageformat=MP4Cover.FORMAT_JPEG)]

    audio.save()

    if delete_thumbnail and cover_jpg_path and cover_jpg_path.exists():
        cover_jpg_path.unlink()

audio = Path("C:/Users/ivank/OneDrive/Desktop/My Code/Projects/Pl-dlp - 2/musicDir/pl-myplaylist/music/song.m4a")
data = {
    "id": "dQw4w9WgXcQ",
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "title": "Never Gonna Give You Up",
    "artist": "Rick Astley",
    "composer": "Stock Aitken Waterman",
    "vocalist_vsynth": "-",
    "language": "English",
    "release_date": "1987-07-27",
    "download_video": False,
    "status": "active"
}
write_audio_metadata(audio, data)