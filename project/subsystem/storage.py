import os
from mutagen.mp4 import MP4
from pathlib import Path
import shutil
import stat
import time
from datetime import datetime
from pathlib import PurePosixPath
from typing import Optional, Union
import zipfile

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

MANIFEST_EXTENSIONS = (".json", ".yaml", ".yml")

def generate_manifest_path(playlist_dir: Path, playlist_name: str, manifest_format: str = "json") -> Path:
    manifest_format = manifest_format.lower().removeprefix(".")
    if manifest_format == "yml":
        manifest_format = "yaml"
    if manifest_format not in ("json", "yaml"):
        raise ValueError("Manifest format must be 'json' or 'yaml'.")
    return playlist_dir / f"{playlist_name}.{manifest_format}"

def find_manifest_path(playlist_dir: Path, playlist_name: str, manifest_format: str = "json") -> Path:
    """Return an existing manifest path, or a new path using the requested format."""
    for extension in MANIFEST_EXTENSIONS:
        candidate = playlist_dir / f"{playlist_name}{extension}"
        if candidate.exists():
            return candidate
    return generate_manifest_path(playlist_dir, playlist_name, manifest_format)

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

def separate_manifest_paths(playlist_directories: Union[Path, list[Path]]) -> list[Path]:
    """Finds supported manifest paths from one or more playlist directories."""
    # Ensure input is always treated as a list of paths
    if isinstance(playlist_directories, Path):
        playlist_directories = [playlist_directories]
        
    manifests = []
    for playlist_dir in playlist_directories:
        manifest_path = find_manifest_path(
            playlist_dir, clean_json_name(playlist_dir.name)
        )
        
        if manifest_path.exists():
            manifests.append(manifest_path)
            
    return manifests

def find_all_manifest_paths(base_music_dir: Path) -> list[Path]:
    """Find all supported manifest files directly inside playlist directories."""
    return sorted(
        (
            path
            for playlist_dir in find_playlist_directories(base_music_dir)
            for path in playlist_dir.iterdir()
            if path.is_file() and path.suffix.lower() in MANIFEST_EXTENSIONS
        ),
        key=lambda path: path.as_posix().casefold(),
    )

def backup_manifests(
    manifest_paths: list[Path], base_music_dir: Path, backup_folder_path: Path
) -> Path:
    """Create a ZIP backup of manifests while preserving their playlist paths."""
    backup_folder_path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    archive_path = backup_folder_path / f"{timestamp}.zip"

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for manifest_path in manifest_paths:
            archive.write(
                manifest_path,
                arcname=manifest_path.relative_to(base_music_dir).as_posix(),
            )
    return archive_path

def read_manifest_backup(backup_file: Path) -> list[tuple[Path, bytes]]:
    """Read and validate manifest files from a backup archive."""
    restored_files: list[tuple[Path, bytes]] = []
    seen_paths: set[Path] = set()

    with zipfile.ZipFile(backup_file, "r") as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue

            archive_path = PurePosixPath(member.filename)
            if archive_path.suffix.lower() not in MANIFEST_EXTENSIONS:
                continue
            if (
                archive_path.is_absolute()
                or "\\" in member.filename
                or ".." in archive_path.parts
                or len(archive_path.parts) != 2
                or not archive_path.parts[0].startswith("pl-")
                or archive_path.parts[0] == "pl-"
            ):
                raise ValueError(
                    f"Invalid manifest path in backup archive: {member.filename}"
                )

            relative_path = Path(*archive_path.parts)
            if relative_path in seen_paths:
                raise ValueError(
                    f"Duplicate manifest path in backup archive: {member.filename}"
                )
            seen_paths.add(relative_path)
            restored_files.append((relative_path, archive.read(member)))

    if not restored_files:
        raise ValueError("The backup archive contains no playlist manifests.")
    return restored_files

def restore_manifests(
    restored_files: list[tuple[Path, bytes]], base_music_dir: Path
) -> None:
    """Write validated backup contents to their corresponding playlist paths."""
    for relative_path, _ in restored_files:
        destination = base_music_dir / relative_path
        if destination.parent.is_symlink() or destination.is_symlink():
            raise ValueError(f"Cannot restore through a symbolic link: {destination}")
        if destination.exists() and not destination.is_file():
            raise ValueError(f"Cannot restore over a non-file path: {destination}")

    for relative_path, contents in restored_files:
        destination = base_music_dir / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(contents)

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