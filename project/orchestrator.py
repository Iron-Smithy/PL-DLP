import config
import downloader
import exporter
import manifest
import metadata
import storage
import ui

from pathlib import Path
from datetime import datetime

from rich.prompt import Confirm

def cmd_list_all():
    playlist_directories = storage.find_playlist_directories(config.MUSIC_ROOT)
    json_directories = storage.separate_json_manifest_paths(playlist_directories)
    playlist_songs_list: list[list[Path]] = storage.separate_music_paths(playlist_directories)

    names = []
    track_count = []
    tracks_downloaded = []
    total_sizes = []

    for i, json_path in enumerate(json_directories):
        json_data = manifest.load_json_manifest(json_path)

        song_paths = playlist_songs_list[i]

        size = storage.get_directory_size(song_paths)

        names.append(playlist_directories[i].name or json_data.get("playlist_name", config.JSON_FALLBACK_CHAR))
        track_count.append(json_data.get("total_tracks", config.JSON_FALLBACK_CHAR))
        tracks_downloaded.append(len(song_paths))
        total_sizes.append(size)

    ui.list_all(names, track_count, tracks_downloaded, total_sizes)

def cmd_list_playlist(playlist_name: str):
    playlist_name = storage.clean_name(playlist_name)

    playlist_path = storage.find_playlist_directory(
        config.MUSIC_ROOT,
        playlist_name
    )

    if not playlist_path:
        print(f"The playlist {playlist_name} cannot be found")
        exit(1)

    json_path = storage.separate_json_manifest_paths(playlist_path)[0]
    json_data = manifest.load_json_manifest(json_path)

    songs = json_data.get("songs", [])

    music_paths = storage.separate_music_paths(playlist_path)[0]
    downloaded_files = {file.name for file in music_paths}

    titles = []
    downloaded = []
    lengths = []
    sizes = []

    for song in songs:
        title = song["title"]

        file_name = f"{title}.m4a"
        file_exists = file_name in downloaded_files

        if file_exists:
            file_path = playlist_path / "music" / file_name

            length = storage.get_media_duration(file_path)
            size = storage.get_file_size(file_path)
        else:
            length = song.get("length", config.JSON_FALLBACK_CHAR)
            size = 0

        titles.append(title)
        downloaded.append(file_exists)
        lengths.append(length)
        sizes.append(size)

    ui.list_one(
        playlist_name,
        titles,
        downloaded,
        lengths,
        sizes
    )

def cmd_new_playlist(playlist_name: str):
    playlist_name = (playlist_name or "new-playlist").strip()

    potential_file = Path(playlist_name).expanduser().resolve(strict=False)

    if potential_file.is_file() and potential_file.suffix.lower() == ".json":
        playlist_name = storage.clean_name(potential_file.stem)
        new_dir = config.MUSIC_ROOT / playlist_name
        
        if new_dir.exists():
            ui.CONSOLE.print(f"[red]Error: Folder {playlist_name} already exists.[/]")
            
        storage.make_directory(new_dir, parents=True)
        storage.make_directory(new_dir / "Music")
        
        target_json = new_dir / f"{playlist_name.removeprefix("pl-")}.json" # !!! make another storage function. like clean name but removes the pl-
        storage.move(str(potential_file), str(target_json))
        
        ui.CONSOLE.print(f"[green]Manifest moved![/] Folder {pl_name} is ready.")
        return

    # use final path segment so ./pl-x and pl-x are the same token
    name = storage.clean_name(Path(playlist_name).expanduser().name)
    path = config.MUSIC_ROOT / name
    if path.exists():
        ui.CONSOLE.print(f"[red]Error: {name} already exists.[/]")
        return
        
    storage.make_directory(path)
    storage.make_directory(path / "Music")
    storage.make_file(path / f"{name.removeprefix("pl-")}.json") # !!! make another storage function. like clean name but removes the pl-
    
    ui.CONSOLE.print(f"[green]Created empty playlist: {name}[/]")

def cmd_remove_playlist(playlist_name: str):
    playlist_name = (playlist_name).strip()

    playlist_directory = storage.find_playlist_directory(config.MUSIC_ROOT, playlist_name)

    if not playlist_directory:
        ui.CONSOLE.print(f"[red]Error: {playlist_name} not found.[/]")
        return

    if Confirm.ask(f"Are you sure you want to move [bold red]{playlist_name}[/] to trash?"):
        # Create a unique name for the trash
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_path = config.TRASH / f"{playlist_name}_{timestamp}"
        try:
            storage.move(str(playlist_directory), target_path)
        except OSError as e:
            ui.CONSOLE.print(f"[red]Could not move to trash:[/] {e}")
            return
        ui.CONSOLE.print(f"[yellow]{playlist_name} moved to {config.TRASH}[/]")

def cmd_rename_playlist(old_name, new_name):
    old_name = storage.clean_name(old_name)
    new_name = storage.clean_name(new_name)
    old_path = config.MUSIC_ROOT / old_name
    new_path = config.MUSIC_ROOT / new_name

    if not old_path.exists():
        ui.CONSOLE.print(f"[red]Error: Source {old_name} not found.[/]")
        return
    if new_path.exists():
        ui.CONSOLE.print(f"[red]Error: Destination {new_name} already exists.[/]")
        return

    try:
        storage.move(old_path, new_path)
    except OSError as e:
        ui.CONSOLE.print(f"[red]Rename failed:[/] {e}")
        return
    old_txt = new_path / f"{old_name}.txt"
    new_txt = new_path / f"{new_name}.txt"
    if old_txt.exists():
        try:
            old_txt.rename(new_txt)
        except OSError as e:
            ui.CONSOLE.print(f"[red]Folder moved but manifest rename failed:[/] {e}")
            return

    ui.CONSOLE.print(f"[green]Successfully renamed {old_name} to {new_name}[/]")