import os
import json
from pathlib import Path
import shutil
import tempfile
from datetime import datetime

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

def separate_json_manifest(playlist_directories: list[Path]) -> list[Path]:
    """
    Filters out json manifest paths
    """
    manifests = []

    for playlist_dir in playlist_directories:
        json_path = playlist_dir / (playlist_dir.name.removeprefix("pl-") + ".json")

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