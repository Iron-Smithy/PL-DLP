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
        
        ui.CONSOLE.print(f"[green]Manifest moved![/] Folder {playlist_name} is ready.")
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

def _execute_sync_task(task: dict, meta_only: bool = False, no_thumb: bool = False, offline: bool = False) -> str:
    """Processes a single task: downloads missing files or updates metadata."""
    song = task["song"]
    target_path = task["path"]
    action = task["action"]

    # 1. Skip downloading if offline or if user requested meta-only on a missing file
    if action == "DL":
        if offline or meta_only:
            return "skip"
        
        # Call downloader module to fetch the track
        success = downloader.download_media(song["url"], target_path)
        if not success:
            return "fail"
            
        action = "META"  # Proceed to tag the newly downloaded file

    # 2. Embed / update metadata tags
    if action == "META" and target_path.exists():
        thumb_path = None
        if not offline:
            if not no_thumb and song.get("thumbnail_url"):
                temp_thumb = target_path.parent / f"{target_path.stem}_thumb.jpg"
                if downloader.download_thumbnail(song["thumbnail_url"], temp_thumb):
                    thumb_path = temp_thumb

            if song.get("url"):
                raw_metadata = downloader.select_relevant_data(downloader.extract_data_from_url(song["url"]))
        print(song)
        exit()

        # Apply tags using metadata module
        metadata.write_audio_metadata(
            audio_path=target_path,
            title=song.get("title", "-"),
            artist=song.get("account_name", "-"),
            cover_jpg_path=thumb_path
        )
        
        # Cleanup temporary thumbnail if it was downloaded
        if thumb_path and thumb_path.exists():
            thumb_path.unlink(missing_ok=True)
            
        return "success"

    return "fail"

def _process_playlist_sync(playlist_dir: Path, flags: dict) -> dict:
    """Scans a single playlist, cleans orphans, and runs updates."""
    json_paths = storage.separate_json_manifest_paths([playlist_dir])
    if not json_paths:
        ui.CONSOLE.print(f"[red]Error: Missing manifest in {playlist_dir.name}[/]")
        return {"dl": 0, "meta": 0, "fail": 0, "skip": 0}

    json_data = manifest.load_json_manifest(json_paths[0])
    desired_songs = json_data.get("songs", [])
    
    music_dir = playlist_dir / "music"
    storage.make_directory(music_dir,)

    # Get local files on disk
    music_paths = storage.separate_music_paths([playlist_dir])[0]
    songs_on_disk = {file.name: file for file in music_paths}

    tasks = []
    for song in desired_songs:
        title = song.get("title", "Unknown")
        target_path = music_dir / f"{title}.m4a"

        action = "META" if target_path.exists() else "DL"
        
        # Remove from disk list so remaining items become identified as orphans
        songs_on_disk.pop(target_path.name, None)
        
        tasks.append({
            "song": song, 
            "path": target_path, 
            "action": action, 
            "pl_path": playlist_dir
        })

    # Clean orphans by moving them safely to trash
    for orphan in songs_on_disk.values():
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            storage.move(str(orphan), config.TRASH / f"{orphan.name}_{timestamp}")
            ui.CONSOLE.print(f"[yellow]Orphan moved to trash:[/] {orphan.name}")
        except OSError as error:
            ui.CONSOLE.print(f"[red]Could not move {orphan.name} to trash:[/] {error}")

    # Process task execution
    stats = {"dl": 0, "meta": 0, "fail": 0, "skip": 0}
    for task in tasks:
        res = _execute_sync_task(
            task, 
            meta_only=flags.get("meta_only", False),
            no_thumb=flags.get("no_thumb", False),
            offline=flags.get("offline", False)
        )
        
        if res == "success":
            if task["action"] == "DL":
                stats["dl"] += 1
            else:
                stats["meta"] += 1
        elif res == "skip":
            stats["skip"] += 1
        else:
            stats["fail"] += 1

    return stats

def cmd_update_playlist(playlist_name: str | None, meta_only: bool, no_thumb: bool, retry_dead: bool, check_json: bool, offline: bool):
    """Entry point for updating one or all playlists."""
    flags = {
        "meta_only": meta_only,
        "no_thumb": no_thumb,
        "retry_dead": retry_dead,
        "check_json": check_json,
        "offline": offline
    }

    if playlist_name:
        clean_pname = storage.clean_name(playlist_name)
        target_dir = storage.find_playlist_directory(config.MUSIC_ROOT, clean_pname)
        if not target_dir:
            ui.CONSOLE.print(f"[red]Error: Playlist '{clean_pname}' not found.[/]")
            return
        targets = [target_dir]
    else:
        targets = storage.find_playlist_directories(config.MUSIC_ROOT)

    if not targets:
        ui.CONSOLE.print("[bold green]No playlists found to update.[/]")
        return

    total_stats = {"dl": 0, "meta": 0, "fail": 0, "skip": 0}

    for p_dir in targets:
        ui.CONSOLE.print(f"[bold blue]Updating playlist:[/] {p_dir.name}")
        stats = _process_playlist_sync(p_dir, flags)
        
        for k in total_stats:
            total_stats[k] += stats[k]

    # Print clean summary using UI
    ui.CONSOLE.print("\n[bold]Sync Finished![/]")
    ui.CONSOLE.print(f"Downloaded: [green]{total_stats['dl']}[/] | Updated Meta: [yellow]{total_stats['meta']}[/] | Skipped: [blue]{total_stats['skip']}[/] | Failures: [red]{total_stats['fail']}[/]")

def cmd_update_all(meta_only: bool, no_thumb: bool, retry_dead: bool, check_json: bool, offline: bool):
    """Wrapper function to update all playlists by calling cmd_update_playlist with None."""
    cmd_update_playlist(
        playlist_name=None,
        meta_only=meta_only,
        no_thumb=no_thumb,
        retry_dead=retry_dead,
        check_json=check_json,
        offline=offline
    )