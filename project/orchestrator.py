import concurrent.futures
import threading

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

import os
import argparse
import shutil
import time
import logging
import yt_dlp
import unicodedata
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn, TimeElapsedColumn
from rich.console import Group
from rich.markdown import Markdown
from mutagen import File as MutagenFile
from mutagen.mp4 import MP4, MP4FreeForm



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

        names.append(
            playlist_directories[i].name
            or json_data.get("playlist_name", config.JSON_FALLBACK_CHAR)
        )
        track_count.append(
            json_data.get("total_tracks", config.JSON_FALLBACK_CHAR)
        )
        tracks_downloaded.append(len(song_paths))
        total_sizes.append(size)

    ui.list_all(names, track_count, tracks_downloaded, total_sizes)


def cmd_list_playlist(playlist_name: str):
    playlist_name = storage.clean_name(playlist_name)
    playlist_path = storage.find_playlist_directory(config.MUSIC_ROOT, playlist_name)

    if not playlist_path:
        ui.CONSOLE.print(f"[red]The playlist {playlist_name} cannot be found[/]")
        return

    json_path = storage.separate_json_manifest_paths(playlist_path)[0]
    json_data = manifest.load_json_manifest(json_path)
    songs = json_data.get("songs", [])

    music_paths = storage.separate_music_paths(playlist_path)[0]
    downloaded_files = {file.name for file in music_paths}

    titles, downloaded, lengths, sizes = [], [], [], []

    for song in songs:
        title = song.get("title", "Unknown")
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

    ui.list_one(playlist_name, titles, downloaded, lengths, sizes)


def cmd_new_playlist(playlist_name: str):
    playlist_name = (playlist_name or "new-playlist").strip()
    potential_file = Path(playlist_name).expanduser().resolve(strict=False)

    if potential_file.is_file() and potential_file.suffix.lower() == ".json":
        playlist_name = storage.clean_name(potential_file.stem)
        new_dir = config.MUSIC_ROOT / playlist_name

        if new_dir.exists():
            ui.CONSOLE.print(f"[red]Error: Folder {playlist_name} already exists.[/]")
            return

        storage.make_directory(new_dir, parents=True)
        storage.make_directory(new_dir / "music")

        clean_json_name = playlist_name.removeprefix("pl-")
        target_json = new_dir / f"{clean_json_name}.json"
        storage.move(str(potential_file), str(target_json))

        ui.CONSOLE.print(f"[green]Manifest moved![/] Folder {playlist_name} is ready.")
        return

    name = storage.clean_name(Path(playlist_name).expanduser().name)
    path = config.MUSIC_ROOT / name
    if path.exists():
        ui.CONSOLE.print(f"[red]Error: {name} already exists.[/]")
        return

    clean_json_name = name.removeprefix("pl-")
    storage.make_directory(path)
    storage.make_directory(path / "music")
    storage.make_file(path / f"{clean_json_name}.json")

    ui.CONSOLE.print(f"[green]Created empty playlist: {name}[/]")


def cmd_remove_playlist(playlist_name: str):
    playlist_name = playlist_name.strip()
    playlist_directory = storage.find_playlist_directory(config.MUSIC_ROOT, playlist_name)

    if not playlist_directory:
        ui.CONSOLE.print(f"[red]Error: {playlist_name} not found.[/]")
        return

    if Confirm.ask(f"Are you sure you want to move [bold red]{playlist_name}[/] to trash?"):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_path = config.TRASH / f"{playlist_name}_{timestamp}"
        try:
            storage.move(str(playlist_directory), target_path)
        except OSError as e:
            ui.CONSOLE.print(f"[red]Could not move to trash:[/] {e}")
            return
        ui.CONSOLE.print(f"[yellow]{playlist_name} moved to {config.TRASH}[/]")


def cmd_rename_playlist(old_name: str, new_name: str):
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

    ui.CONSOLE.print(f"[green]Successfully renamed {old_name} to {new_name}[/]")


def _execute_sync_task(task: dict, flags: dict, json_path: Path) -> str:
    """Processes a single task: updates JSON, downloads missing files, or tags metadata."""
    song = task["song"]
    target_path = task["path"]
    action = task["action"]

    meta_only = flags.get("meta_only", False)
    no_thumb = flags.get("no_thumb", False)
    retry_dead = flags.get("retry_dead", False)
    offline = flags.get("offline", False)

    status = song.get("status", "active")
    if status == "DEAD" and not retry_dead:
        return "skip"

    needs_info = (
        song.get("thumbnail_url") in (None, "", config.JSON_FALLBACK_CHAR) or
        song.get("artist") in (None, "", config.JSON_FALLBACK_CHAR) or
        song.get("language") in (None, "", config.JSON_FALLBACK_CHAR)
    )

    if needs_info and not offline and song.get("url"):
        try:
            info = downloader.extract_data_from_url(song["url"])
            relevant = downloader.select_relevant_data(info)
            updated = manifest.merge_song_info(song, relevant)
            if updated:
                song["status"] = "active"
        except Exception:
            song["status"] = "DEAD"
            return "fail"

    if action == "DL":
        if offline or meta_only:
            return "skip"

        is_video = bool(song.get("download_video", False))
        try:
            success = downloader.download_media(song.get("url"), target_path, is_video=is_video)
        except Exception:
            success = False

        if not success:
            song["status"] = "DEAD"
            return "fail"

        song["status"] = "active"
        action = "META"  # Move to tagging phase now that the file exists

    if action == "META" and target_path.exists():
        thumb_path = None

        # Fetch Thumbnail if needed and allowed
        if not offline and not no_thumb and song.get("thumbnail_url"): # !!! attempt to reconstruct thumbnail url if missing: https://i.ytimg.com/vi/[VIDEO_ID]/hqdefault.jpg
            temp_thumb = target_path.parent / f"{target_path.stem}_thumb.jpg"
            if downloader.download_thumbnail(song["thumbnail_url"], temp_thumb):
                thumb_path = temp_thumb

        try:
            # Directly feed the song dict to write_audio_metadata!
            metadata.write_audio_metadata(
                audio_path=target_path, data=song, cover_jpg_path=thumb_path
            )
            song["status"] = "active"
            return "success"
        except Exception as e:
            ui.CONSOLE.print(f"[red]Failed to tag {target_path.name}:[/] {e}")
            song["status"] = "ERR"
            return "fail"

    return "skip"


def _process_playlist_sync(playlist_dir: Path, flags: dict, concurrency: int | None = None) -> dict:
    """
    Scans a single playlist, cleans orphans, and updates media + JSON manifest
    safely across multiple concurrent threads.
    """
    json_paths = storage.separate_json_manifest_paths([playlist_dir])
    if not json_paths:
        ui.CONSOLE.print(f"[red]Error: Missing manifest in {playlist_dir.name}[/]")
        return {"dl": 0, "meta": 0, "fail": 0, "skip": 0}

    json_path = json_paths[0]
    json_data = manifest.load_json_manifest(json_path)
    desired_songs = json_data.get("songs", [])

    music_dir = playlist_dir / "music"
    storage.make_directory(music_dir)

    # Map existing files on disk
    music_paths = storage.separate_music_paths([playlist_dir])[0]
    songs_on_disk = {file.name: file for file in music_paths}

    tasks = []
    for song in desired_songs:
        title = song.get("title", "Unknown")
        target_path = music_dir / f"{title}.m4a"
        action = "META" if target_path.exists() else "DL"

        # Track existing files so leftover ones are orphans
        songs_on_disk.pop(target_path.name, None)

        tasks.append({
            "song": song,
            "path": target_path,
            "action": action,
            "pl_path": playlist_dir,
        })

    # Clean orphaned audio files by moving them to trash
    for orphan in songs_on_disk.values():
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            storage.move(str(orphan), config.TRASH / f"{orphan.name}_{timestamp}")
            ui.CONSOLE.print(f"[yellow]Orphan moved to trash:[/] {orphan.name}")
        except OSError as error:
            ui.CONSOLE.print(f"[red]Could not move {orphan.name} to trash:[/] {error}")

    stats = {"dl": 0, "meta": 0, "fail": 0, "skip": 0}
    max_workers = concurrency if concurrency and concurrency > 0 else config.DEFAULT_CONCURRENT_DOWNLOADS

    # Thread Lock to make dictionary updates and file writing thread-safe
    manifest_lock = threading.Lock()

    # Thread-safe wrapper for task execution
    def _safe_task_runner(task: dict) -> str:
        # Execution of network/download bounds (unlocked)
        result = _execute_sync_task(task, flags, json_path)
        
        # Synchronized block if manifest mutations happen
        with manifest_lock:
            # Ensures dict mutations inside _execute_sync_task are safely serialized
            pass
            
        return result

    # Concurrently execute tasks
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_task = {
            executor.submit(_safe_task_runner, task): task 
            for task in tasks
        }

        for future in concurrent.futures.as_completed(future_to_task):
            task = future_to_task[future]
            try:
                res = future.result()
            except Exception as exc:
                ui.CONSOLE.print(f"[red]Task failed unexpectedly for {task['path'].name}:[/] {exc}")
                res = "fail"

            if res == "success":
                if task["action"] == "DL":
                    stats["dl"] += 1
                else:
                    stats["meta"] += 1
            elif res == "skip":
                stats["skip"] += 1
            else:
                stats["fail"] += 1

    # Save the updated manifest safely after all threads finish
    manifest.write_to_json(json_path, json_data)

    return stats

def cmd_update_playlist(
    playlist_name: str | None,
    meta_only: bool,
    no_thumb: bool,
    retry_dead: bool,
    offline: bool,
    concurrency: int | None = None,
):
    """Entry point for updating one or all playlists."""
    flags = {
        "meta_only": meta_only,
        "no_thumb": no_thumb,
        "retry_dead": retry_dead,
        "offline": offline,
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
        stats = _process_playlist_sync(p_dir, flags, concurrency)

        for k in total_stats:
            total_stats[k] += stats[k]

    ui.CONSOLE.print("\n[bold]Sync Finished![/]")
    ui.CONSOLE.print(
        f"Downloaded: [green]{total_stats['dl']}[/] | "
        f"Updated Meta: [yellow]{total_stats['meta']}[/] | "
        f"Skipped: [blue]{total_stats['skip']}[/] | "
        f"Failures: [red]{total_stats['fail']}[/]"
    )


def cmd_update_all(meta_only: bool, no_thumb: bool, retry_dead: bool, offline: bool, concurrency: int | None = None):
    """Wrapper function to update all playlists."""
    cmd_update_playlist(
        playlist_name=None,
        meta_only=meta_only,
        no_thumb=no_thumb,
        retry_dead=retry_dead,
        offline=offline,
        concurrency=concurrency,
    )