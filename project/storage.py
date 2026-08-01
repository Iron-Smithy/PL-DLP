from pathlib import Path

def find_playlist_directories(base_music_dir: Path) -> list[Path]:
    """
    Scans base_music_dir for folders starting with 'pl-'.
    Returns a list of Path objects for each found playlist folder.
    """
    if not base_music_dir.exists():
        return []

    # glob("pl-*") matches any file/folder starting with "pl-"
    # [p for p in ... if p.is_dir()] ensures we only get directories
    playlist_dirs = [path for path in base_music_dir.glob("pl-*") if path.is_dir()]
    
    return playlist_dirs