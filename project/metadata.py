from mutagen.mp4 import MP4, MP4Cover
from pathlib import Path

def write_audio_metadata(audio_path: Path, data: dict, cover_jpg_path: Path = None, delete_thumbnail: bool = True, album: str = None):
    """Embeds MP4 metadata atoms and cover art directly into an M4A file."""
    # Ensure audio file exists before opening
    if not audio_path.exists():
        raise ValueError(f"Audio file not found at {audio_path}")

    audio = MP4(audio_path)
    
    audio['\xa9nam'] = [data.get('title', '-')]
    audio['\xa9ART'] = [data.get('artist', '-')]
    audio['\xa9wrt'] = [data.get('composer', '-')]
    audio['\xa9day'] = [data.get('release_date', '-')]
    audio['\xa9lan'] = [data.get('language', '-')]

    if album:
        audio['\xa9alb'] = [album or '-']

    video_id = data.get('id', '')
    vocalist = data.get('vocalist_vsynth', '-')
    
    comment_lines = []
    if video_id:
        comment_lines.append(f"YouTube ID: {video_id}")
    if vocalist and vocalist != '-':
        comment_lines.append(f"Vocalist: {vocalist}")
        
    audio['\xa9cmt'] = ["\n".join(comment_lines)] if comment_lines else ["-"]

    # Handle Cover Art Embedding
    if cover_jpg_path and cover_jpg_path.exists():
        with open(cover_jpg_path, "rb") as img_file:
            audio['covr'] = [MP4Cover(img_file.read(), imageformat=MP4Cover.FORMAT_JPEG)]
        
        # Delete the temporary thumbnail if flag is set
        if delete_thumbnail:
            cover_jpg_path.unlink()

    # Finalize and write to disk
    audio.save()

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