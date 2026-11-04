import concurrent.futures
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import threading

from rich.console import Group
from rich.live import Live

import subsystem.config as config
import subsystem.downloader as downloader
import subsystem.exporter as exporter
import subsystem.manifest as manifest
import subsystem.metadata as metadata
import subsystem.storage as storage
import subsystem.ui as ui


@dataclass
class SyncTask:
    song: dict
    is_video: bool
    path: Path
    action: str
    playlist_name: str


def ensure_extension(path: Path, extension: str) -> Path:
    extension = extension if extension.startswith(".") else f".{extension}"
    if path.suffix.lower() == extension.lower():
        return path
    if path.suffix:
        return path.with_suffix(extension)
    return Path(str(path) + extension)


def _execute_sync_task(
    task: SyncTask,
    flags: dict,
    playlist_name: str,
    item_progress=None,
    item_task_id=None,
) -> str:
    song = task.song
    target_path = ensure_extension(
        task.path, config.VIDEO_EXT if task.is_video else config.AUDIO_EXT
    )
    action = task.action
    meta_only = flags.get("meta_only", False)
    no_thumb = flags.get("no_thumb", False)
    retry_dead = flags.get("retry_dead", False)
    offline = flags.get("offline", False)

    if song.get("status") == "DEAD" and not retry_dead:
        return "dead"

    title = song.get("title", "Unknown Track")
    if item_progress and item_task_id is not None:
        item_progress.update(
            item_task_id, description=f"[cyan]Syncing:[/] {title[:28]}"
        )

    needs_metadata = (
        song.get("thumbnail_url") in (None, "", config.JSON_FALLBACK_CHAR)
        or song.get("artist") in (None, "", config.JSON_FALLBACK_CHAR)
    )
    if needs_metadata and not offline and song.get("url"):
        try:
            raw_info = downloader.extract_data_from_url(song["url"])
            clean_info = downloader.select_relevant_data(raw_info)
            manifest.merge_song_info(song, clean_info)
            song["status"] = "active"
        except Exception:
            song["status"] = "DEAD"
            return "dead"

    if action == "DL":
        if offline or meta_only:
            return "skip"

        def update_item_progress(downloaded: int, total: int) -> None:
            if item_progress and item_task_id is not None and total > 0:
                item_progress.update(
                    item_task_id, completed=downloaded, total=total
                )

        success = downloader.download_media(
            song.get("url"),
            target_path,
            is_video=task.is_video,
            progress_callback=update_item_progress,
        )
        if not success:
            song["status"] = "DEAD"
            return "fail"

        song["status"] = "active"
        action = "META"

    if action == "META" and target_path.exists():
        thumbnail_path = None
        if (
            not offline
            and not no_thumb
            and song.get("thumbnail_url")
            and not metadata.has_embedded_cover(target_path)
        ):
            temporary_thumbnail = (
                target_path.parent / f"{target_path.stem}_thumb.jpg"
            )
            if downloader.download_thumbnail(
                song["thumbnail_url"], temporary_thumbnail
            ):
                thumbnail_path = temporary_thumbnail

        try:
            metadata.write_audio_metadata(
                audio_path=target_path,
                data=song,
                cover_jpg_path=thumbnail_path,
                delete_thumbnail=True,
                album=storage.clean_json_name(playlist_name),
            )
            song["status"] = "active"
            return "success"
        except Exception:
            song["status"] = "ERR"
            return "fail"

    return "skip"


def _build_sync_tasks(
    playlist_dir: Path,
    songs: list[dict],
    download_video_all: bool,
) -> tuple[list[SyncTask], dict[str, Path]]:
    music_dir = playlist_dir / "music"
    storage.make_directory(music_dir)
    songs_on_disk = {
        path.name: path for path in storage.separate_music_paths([playlist_dir])[0]
    }

    tasks = []
    for song in songs:
        title = song.get("title", "Unknown")
        safe_name = exporter.sanitize_filename(title)
        is_video = download_video_all or bool(song.get("download_video", False))
        extension = config.VIDEO_EXT if is_video else config.AUDIO_EXT
        target_path = music_dir / f"{safe_name}{extension}"
        action = "META" if target_path.exists() else "DL"
        songs_on_disk.pop(target_path.name, None)
        tasks.append(
            SyncTask(
                song=song,
                is_video=is_video,
                path=target_path,
                action=action,
                playlist_name=playlist_dir.name,
            )
        )
    return tasks, songs_on_disk


def _move_orphaned_files(orphaned_files: dict[str, Path]) -> None:
    for orphan in orphaned_files.values():
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            storage.move(
                str(orphan), config.TRASH / f"{orphan.name}_{timestamp}"
            )
        except OSError:
            pass


def _process_playlist_sync(
    playlist_dir: Path, flags: dict, concurrency: int | None = None
) -> dict[str, int]:
    manifest_paths = storage.separate_manifest_paths([playlist_dir])
    if not manifest_paths:
        ui.CONSOLE.print(
            f"[red]Error: Missing manifest in {playlist_dir.name}[/]"
        )
        return {"dl": 0, "meta": 0, "fail": 0, "skip": 0, "dead": 0}

    manifest_path = manifest_paths[0]
    manifest_data = manifest.load_manifest(manifest_path)
    songs = manifest_data.get("songs", [])
    download_video_all = bool(manifest_data.get("download_video_all", False))
    tasks, orphaned_files = _build_sync_tasks(
        playlist_dir, songs, download_video_all
    )
    _move_orphaned_files(orphaned_files)

    stats = {"dl": 0, "meta": 0, "fail": 0, "skip": 0, "dead": 0}
    if not tasks:
        ui.render_sync_summary(stats, 0, playlist_dir.name)
        return stats

    max_workers = (
        concurrency
        if concurrency and concurrency > 0
        else config.DEFAULT_CONCURRENT_DOWNLOADS
    )
    global_progress, item_progress = ui.create_sync_progress_group()
    progress_group = Group(item_progress, global_progress)
    main_task_id = global_progress.add_task(
        f"Syncing Playlist [bold cyan]{playlist_dir.name}[/]",
        total=len(tasks),
    )
    manifest_lock = threading.Lock()

    with Live(progress_group, console=ui.CONSOLE, refresh_per_second=10):
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers
        ) as executor:
            future_to_task = {}
            for task in tasks:
                item_task_id = item_progress.add_task("Pending...", total=100)

                def run_task(
                    current_task: SyncTask = task,
                    current_task_id: int = item_task_id,
                ) -> str:
                    result = _execute_sync_task(
                        current_task,
                        flags,
                        current_task.playlist_name,
                        item_progress,
                        current_task_id,
                    )
                    item_progress.remove_task(current_task_id)
                    return result

                future = executor.submit(run_task)
                future_to_task[future] = task

            for future in concurrent.futures.as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result()
                except Exception as error:
                    print(f"Error type: {type(error).__name__}")
                    print(f"Error message: {error}")
                    with manifest_lock:
                        task.song["status"] = "DEAD"
                    result = "fail"

                with manifest_lock:
                    if result == "success":
                        stats["dl" if task.action == "DL" else "meta"] += 1
                    elif result == "skip":
                        stats["skip"] += 1
                    elif result == "dead":
                        stats["dead"] += 1
                    else:
                        stats["fail"] += 1
                global_progress.update(main_task_id, advance=1)

    manifest.write_manifest(manifest_path, manifest_data)
    ui.render_sync_summary(stats, len(tasks), playlist_dir.name)
    return stats


def cmd_update_playlist(
    playlist_name: str | None,
    meta_only: bool,
    no_thumb: bool,
    retry_dead: bool,
    offline: bool,
    concurrency: int | None = None,
) -> None:
    """Synchronize one playlist or every playlist in the configured library."""
    flags = {
        "meta_only": meta_only,
        "no_thumb": no_thumb,
        "retry_dead": retry_dead,
        "offline": offline,
    }

    if playlist_name:
        clean_playlist_name = storage.clean_playlist_name(playlist_name)
        playlist_dir = storage.find_playlist_directory(
            config.MUSIC_ROOT, clean_playlist_name
        )
        if not playlist_dir:
            ui.CONSOLE.print(
                f"[red]Error: Playlist '{clean_playlist_name}' not found.[/]"
            )
            return
        playlist_dirs = [playlist_dir]
    else:
        playlist_dirs = storage.find_playlist_directories(config.MUSIC_ROOT)

    if not playlist_dirs:
        ui.CONSOLE.print("[bold green]No playlists found to update.[/]")
        return

    total_stats = {"dl": 0, "meta": 0, "fail": 0, "skip": 0}
    for playlist_dir in playlist_dirs:
        ui.CONSOLE.print(f"[bold blue]Updating playlist:[/] {playlist_dir.name}")
        stats = _process_playlist_sync(playlist_dir, flags, concurrency)
        for key in total_stats:
            total_stats[key] += stats[key]

    ui.CONSOLE.print("\n[bold]Sync Finished![/]")
    ui.CONSOLE.print(
        f"Downloaded: [green]{total_stats['dl']}[/] | "
        f"Updated Meta: [yellow]{total_stats['meta']}[/] | "
        f"Skipped: [blue]{total_stats['skip']}[/] | "
        f"Failures: [red]{total_stats['fail']}[/]"
    )


def cmd_update_all(
    meta_only: bool,
    no_thumb: bool,
    retry_dead: bool,
    offline: bool,
    concurrency: int | None = None,
) -> None:
    """Synchronize all playlists using the supplied update options."""
    cmd_update_playlist(
        playlist_name=None,
        meta_only=meta_only,
        no_thumb=no_thumb,
        retry_dead=retry_dead,
        offline=offline,
        concurrency=concurrency,
    )
