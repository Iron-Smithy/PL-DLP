import os
import json
from mutagen.mp4 import MP4, MP4Cover
from pathlib import Path
import shutil
import tempfile
import stat
import time
from datetime import datetime
from typing import Optional, Union


def find_playlist_directories(base_music_dir: Path) -> list[Path]:
    """
    Scans base_music_dir for folders starting with 'pl-'.
    Returns a list of Path objects for each found playlist folder.
    """
    if not base_music_dir.exists():
        return []

    # glob("pl-*") matches any file/folder starting with "pl-"
    # [p for p in ... if p.is_dir()] ensures we only get directories
    playlist_directories = [path for path in base_music_dir.glob("pl-*") if path.is_dir()]
    
    return playlist_directories

def clean_playlist_name(playlist_name: str) -> str:
    if not playlist_name:
        raise ValueError("Not a valid name")
    clean_name = playlist_name.strip().lower()
    if clean_name.startswith("pl-"):
        clean_name = clean_name[3:]
    return f"pl-{clean_name}"

def clean_json_name(playlist_name: str) -> str:
    playlist_name = clean_playlist_name(playlist_name)
    return playlist_name.removeprefix("pl-")

def generate_json_path(playlist_dir: Path, playlist_name: str):
    return playlist_dir / (playlist_name + ".json")

def find_playlist_directory(base_music_dir: Path, playlist_name: str, create_if_missing: bool = False) -> Optional[Path]:
    """
    Finds a specific playlist folder, ensuring it has the 'pl-' prefix.
    Can optionally create the folder if it does not exist.
    """
    if not base_music_dir.exists():
        if create_if_missing:
            base_music_dir.mkdir(parents=True, exist_ok=True)
        else:
            return None

    # Normalizes the name to ensure it starts with 'pl-'
    target_name = clean_playlist_name(playlist_name)

    playlist_path = base_music_dir / target_name

    # Handles the folder if it exists
    if playlist_path.is_dir():
        return playlist_path

    # Handles the folder if it is missing
    if create_if_missing:
        playlist_path.mkdir(exist_ok=True)
        return playlist_path
        
    return None

def separate_music_paths(playlist_directories: Union[Path, list[Path]]) -> list[list[Path]]:
    """Filters out music paths from one or more directory paths."""
    
    if isinstance(playlist_directories, Path):
        playlist_directories = [playlist_directories]
        
    playlists = []
    for playlist_dir in playlist_directories:
        music_dir = playlist_dir / "music"
        
        if not music_dir.exists():
            playlists.append([])
            continue
            
        song_paths = [path for path in music_dir.glob("*") if path.is_file()]
        playlists.append(song_paths)
        
    return playlists

def separate_json_manifest_paths(playlist_directories: Union[Path, list[Path]]) -> list[Path]:
    """Filters out json manifest paths from one or more directory paths."""
    # Ensure input is always treated as a list of paths
    if isinstance(playlist_directories, Path):
        playlist_directories = [playlist_directories]
        
    manifests = []
    for playlist_dir in playlist_directories:
        # Generate the expected JSON file name based on the directory name
        json_path = generate_json_path(playlist_dir, clean_json_name(playlist_dir.name))
        
        if json_path.exists():
            manifests.append(json_path)
            
    return manifests

def backup_manifests(manifest_paths: list[Path], backup_folder_path: Path):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_zip_path = backup_folder_path / timestamp

    # Create a temporary directory that deletes itself when done
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        
        # Gather and copy files into the temporary directory
        for src_path in manifest_paths:
            if src_path.exists():
                # Using src.name ensures the file keeps its original name in the ZIP
                dest = temp_dir_path / src_path.name
                
                # Handle potential name collisions (e.g., two different 'data.json' files)
                if dest.exists():
                    dest = temp_dir_path / f"{src_path.stem}_{src_path.parent.name}{src_path.suffix}"
                    
                shutil.copy2(src_path, dest)
                
        # Zip the temporary directory into final archive
        shutil.make_archive(output_zip_path, 'zip', temp_dir)

def get_media_duration(file_path: str) -> str:
    """
    Helper abstraction tool. Attempts reading media duration tags. 
    Returns strings like '3:45' or returns 'N/A' upon exception.
    """
    try:
        audio = MP4(file_path)
        mins, secs = divmod(int(audio.info.length), 60)
        return f"{mins}:{secs:02d}"
    except Exception:
        return "N/A"

def copy_file(src: Path, dest: Path):
    """Copies a file preserving file metadata."""
    shutil.copy2(src, dest)

def remove_directory_tree(directory_path: Path, retries: int = 5, delay: float = 0.3):
    """Recursively deletes a directory tree"""
    if not directory_path.exists():
        return

    def _handle_remove_readonly(func, path, exc):
        # Clear read-only attribute if set
        os.chmod(path, stat.S_IWRITE)
        try:
            func(path)
        except Exception:
            pass

    for attempt in range(retries):
        try:
            # Works across Python 3.12+ (onexc) and older versions (onerror)
            if hasattr(shutil, "rmtree"):
                shutil.rmtree(directory_path, onexc=_handle_remove_readonly)
            return
        except PermissionError:
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                # Final attempt ignoring non-critical cleanup errors
                shutil.rmtree(directory_path, ignore_errors=True)

def create_zip_archive(output_base_path: Union[str, Path], root_dir: Path) -> Path:
    """Creates a ZIP archive of a directory and returns the path to the created archive."""
    archive_path = shutil.make_archive(
        str(output_base_path), "zip", str(root_dir)
    )
    return Path(archive_path)

def get_file_size(file_path: Path) -> int:
    return file_path.stat().st_size

def get_directory_size(file_paths: list[Path]) -> int:
    return sum(get_file_size(file_path) for file_path in file_paths)

def make_file(file_path: Path):
    file_path.touch()

def make_directory(directory_path: Path, parents: bool = False, exists_ok: bool = True):
    directory_path.mkdir(parents=parents, exist_ok=exists_ok)

def move(to_move: Path, target: Path):
    shutil.move(to_move, target)