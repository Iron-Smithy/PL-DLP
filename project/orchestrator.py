import concurrent.futures
from datetime import datetime
from pathlib import Path
import threading
import json

from rich.console import Group
from rich.live import Live
from rich.prompt import Confirm, IntPrompt

import config
import downloader
import exporter
import manifest
import metadata
import storage
import ui

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
    playlist_name = storage.clean_playlist_name(playlist_name)
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
        file_name = f"{title}{config.AUDIO_EXT}"
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
        playlist_name = storage.clean_playlist_name(potential_file.stem)
        new_dir = config.MUSIC_ROOT / playlist_name

        if new_dir.exists():
            ui.CONSOLE.print(f"[red]Error: Folder {playlist_name} already exists.[/]")
            return

        storage.make_directory(new_dir, parents=True)
        storage.make_directory(new_dir / "music")

        clean_json_name = storage.clean_json_name(playlist_name)
        target_json = storage.generate_json_path(new_dir, clean_json_name)
        storage.move(str(potential_file), str(target_json))

        ui.CONSOLE.print(f"[green]Manifest moved![/] Folder {playlist_name} is ready.")
        return

    name = storage.clean_playlist_name(Path(playlist_name).expanduser().name)
    path = config.MUSIC_ROOT / name
    if path.exists():
        ui.CONSOLE.print(f"[red]Error: {name} already exists.[/]")
        return

    clean_json_name = storage.clean_json_name(name)
    storage.make_directory(path)
    storage.make_directory(path / "music")
    json_path = storage.generate_json_path(path, clean_json_name)
    storage.make_file(json_path)
    manifest.write_empty_playlist_object(json_path, clean_json_name)

    ui.CONSOLE.print(f"[green]Created empty playlist: {name}[/]")

def cmd_add_songs(playlist_name: str, sources: list[str]):
    """Adds single/multiple URLs or links from a file to an existing playlist manifest."""
    clean_pl_name = storage.clean_playlist_name(playlist_name)
    p_dir = storage.find_playlist_directory(config.MUSIC_ROOT, clean_pl_name)

    if not p_dir:
        ui.CONSOLE.print(f"[red]Error: Playlist '{playlist_name}' not found.[/]")
        return

    clean_json_name = storage.clean_json_name(clean_pl_name)
    json_path = storage.generate_json_path(p_dir, clean_json_name)
    if not json_path.exists():
        ui.CONSOLE.print(f"[red]Error: Manifest '{json_path.name}' missing.[/]")
        return

    # Expand sources into individual URLs
    urls_to_add = []
    for src in sources:
        src_path = Path(src)
        if src_path.is_file():
            content = src_path.read_text(encoding="utf-8").strip()
            if content.startswith("["):
                urls_to_add.extend(json.loads(content))
            else:
                urls_to_add.extend([line.strip() for line in content.splitlines() if line.strip()])
        else:
            urls_to_add.append(src)

    # Process and append tracks
    for url in urls_to_add:
        ui.CONSOLE.print(f"[blue]Fetching track metadata:[/] {url}")
        try:
            raw_info = downloader.extract_data_from_url(url)
            song_data = manifest.create_track_entry_from_raw(raw_info, url)
            manifest.add_track_to_metadata(json_path, song_data)
            ui.CONSOLE.print(f"[green]Added:[/] {song_data.get('title', 'Unknown')}")
        except Exception as e:
            ui.CONSOLE.print(f"[red]Failed to add {url}: {e}[/]")

def extract_urls_from_file(src_path: Path) -> list[str]:
    content = src_path.read_text(encoding="utf-8").strip()

    # Pure JSON format
    if content.startswith("["):
        try:
            parsed = json.loads(content)
            return extract_urls_from_json(parsed)
        except json.JSONDecodeError:
            pass  # Fall back to regex extraction if JSON parsing fails

    return extract_youtube_urls(content)

def extract_youtube_urls(text_content: str) -> list[str]:
    """Finds all YouTube and YouTube Music links and normalizes them."""
    matches = config.URL_REGEX.findall(text_content)
    # Deduplicate while preserving order
    seen = set()
    clean_urls = []
    
    for video_id in matches:
        if video_id not in seen:
            seen.add(video_id)
            clean_urls.append(f"https://www.youtube.com/watch?v={video_id}")
            
    return clean_urls

import json

def extract_urls_from_json(json_data) -> list[str]:
    """Recursively extracts YouTube URLs/IDs from any JSON structure."""
    found_urls = []
    
    if isinstance(json_data, dict):
        for key, value in json_data.items():
            # If the JSON already has a dedicated video ID or URL key
            if key in ("id", "videoId") and isinstance(value, str) and len(value) == 11:
                found_urls.append(f"https://www.youtube.com/watch?v={value}")
            else:
                found_urls.extend(extract_urls_from_json(value))
                
    elif isinstance(json_data, list):
        for item in json_data:
            found_urls.extend(extract_urls_from_json(item))
            
    elif isinstance(json_data, str):
        found_urls.extend(extract_youtube_urls(json_data))
        
    return list(dict.fromkeys(found_urls))  # Remove duplicates preserving order

def cmd_import_playlist(source: str, playlist_name: str = None):
    """Imports a YouTube/YTM playlist URL or a local JSON/TXT list of links into a new JSON playlist."""
    src_path = Path(source)

    # Determine base target name & directory
    default_name = src_path.stem if src_path.is_file() else "imported_playlist"
    raw_name = playlist_name if playlist_name else default_name
    clean_pl_name = storage.clean_playlist_name(raw_name)

    urls_to_process = []

    # Local File (List of URLs in TXT or JSON)
    if src_path.is_file():
        urls_to_process = extract_urls_from_file(src_path)

    # YouTube Playlist URL
    else:
        ui.CONSOLE.print(
            f"[bold blue]Scraping playlist entries from YouTube:[/] {source}"
        )
        urls_to_process = downloader.import_playlist(source, urls_to_process)

    # Abort early if 0 valid track links were found (Prevents creating empty folders)
    if not urls_to_process:
        ui.CONSOLE.print(
            f"[red]No valid YouTube track links found in '{source}'. Aborting import.[/]"
        )
        return

    p_dir = config.MUSIC_ROOT / clean_pl_name
    p_dir.mkdir(parents=True, exist_ok=True)
    (p_dir / "music").mkdir(parents=True, exist_ok=True)

    json_name = storage.clean_json_name(clean_pl_name)
    json_path = storage.generate_json_path(p_dir, json_name)

    # Initialize manifest dictionary if missing
    if not json_path.exists():
        manifest.write_empty_playlist_object(json_path, clean_pl_name)

    ui.CONSOLE.print(
        f"[green]Found {len(urls_to_process)} track links to import.[/]"
    )

    imported_count = 0

    # Extract metadata and write JSON entries
    for url in urls_to_process:
        try:
            ui.CONSOLE.print(f"[blue]Extracting metadata:[/] {url}")
            raw_info = downloader.extract_data_from_url(url)
            song_data = manifest.create_track_entry_from_raw(raw_info, url)

            manifest.add_track_to_metadata(json_path, song_data)
            imported_count += 1
            ui.CONSOLE.print(
                f"[green]Added:[/] {song_data.get('title', 'Unknown')}"
            )

        except Exception as e:
            ui.CONSOLE.print(f"[red]Failed to import track ({url}): {e}[/]")

    # Cleanup directory if all track metadata extractions failed
    if imported_count == 0:
        ui.CONSOLE.print(
            f"[red]Failed to import any tracks. Cleaning up empty playlist folder...[/]"
        )
        storage.remove_directory_tree(p_dir)
    else:
        ui.CONSOLE.print(
            f"\n[bold green]Import complete for '{clean_pl_name}'![/] Run 'update' to download audio files."
        )

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
    old_name = storage.clean_playlist_name(old_name)
    new_name = storage.clean_playlist_name(new_name)
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

def cmd_export_playlist(
    playlist_name: str,
    output_dir: str | Path,
    target_format: str | None = None,
    no_thumb: bool = False,
    no_video: bool = False,
    legacy_mp3_mode: bool = False,
    max_img_dim: int | None = None,
    zip_output: bool = False,
):
    """Exports and processes playlist files"""
    clean_pname = storage.clean_playlist_name(playlist_name)
    p_dir = storage.find_playlist_directory(config.MUSIC_ROOT, clean_pname)

    if not p_dir:
        ui.CONSOLE.print(
            f"[red]Error: Playlist '{playlist_name}' not found.[/]"
        )
        return

    out_path = Path(output_dir).expanduser().resolve() / clean_pname
    storage.make_directory(out_path, parents=True)

    json_paths = storage.separate_json_manifest_paths(p_dir)
    if not json_paths:
        ui.CONSOLE.print(
            f"[red]Error: Manifest for '{clean_pname}' not found.[/]"
        )
        return

    data = manifest.load_json_manifest(json_paths[0])
    songs = data.get("songs", data.get("tracks", []))

    strict_ascii = legacy_mp3_mode
    export_fmt = "mp3" if legacy_mp3_mode else (target_format or "m4a")
    strip_video = no_video or legacy_mp3_mode

    # Auto-cap thumbnails to 500x500 in legacy mode if no explicit max dimension was passed
    effective_max_dim = (
        max_img_dim
        if max_img_dim is not None
        else (500 if legacy_mp3_mode else None)
    )

    ui.CONSOLE.print(
        f"[cyan]Exporting '{clean_pname}' to {out_path}...[/]"
    )

    for song in songs:
        title = song.get("title", "Unknown")
        safe_name = exporter.sanitize_filename(
            title, strict_ascii=strict_ascii
        )

        # Locate original track audio or video file
        src_file = None
        for ext in (
            config.AUDIO_EXT,
            config.VIDEO_EXT,
            ".mp3",
            ".m4a",
            ".webm",
        ):
            candidate = p_dir / "music" / f"{title}{ext}"
            if candidate.exists():
                src_file = candidate
                break

        if not src_file:
            continue

        target_file = out_path / f"{safe_name}.{export_fmt}"

        # Convert or copy audio file
        if src_file.suffix.lstrip(".") != export_fmt or strip_video:
            exporter.convert_media(
                src_file,
                target_file,
                target_format=export_fmt,
                strip_video=strip_video,
            )
        else:
            storage.copy_file(src_file, target_file)

        # Process and embed thumbnail unless --no-thumb is explicitly passed
        if not no_thumb:
            thumb_dest = out_path / f"{safe_name}.jpg"
            
            # Check if the image exists locally
            thumb_src = p_dir / "music" / f"{title}_thumb.jpg"
            if not thumb_src.exists():
                thumb_src = p_dir / "music" / f"{title}.jpg"

            # Copy local file or re-download from JSON manifest URL
            if thumb_src.exists():
                storage.copy_file(thumb_src, thumb_dest)
            elif song.get("thumbnail_url"):
                try:
                    downloader.download_thumbnail(song["thumbnail_url"], thumb_dest)
                except Exception:
                    pass

            # Resize and embed if successfully acquired
            if thumb_dest.exists():
                if effective_max_dim:
                    exporter.adjust_image_quality(
                        thumb_dest, max_dimension=effective_max_dim
                    )

                if export_fmt == "mp3":
                    exporter.embed_mp3_cover(target_file, thumb_dest)

    if zip_output:
        archive_base = out_path.parent / f"{clean_pname}_export"
        zip_file = storage.create_zip_archive(archive_base, out_path)
        storage.remove_directory_tree(out_path)
        ui.CONSOLE.print(f"[green]Export successfully zipped to:[/] {zip_file}")
    else:
        ui.CONSOLE.print(f"[green]Export complete at:[/] {out_path}")

def ensure_extension(path: Path, extension: str) -> Path:
    extension = extension if extension.startswith(".") else f".{extension}"

    if path.suffix.lower() == extension.lower():
        return path

    if path.suffix:
        return path.with_suffix(extension)

    return Path(str(path) + extension)

def _execute_sync_task(
    task: dict,
    flags: dict,
    json_path: Path,
    item_progress=None,
    item_task_id=None,
) -> str:
    song = task["song"]
    is_video = task["is_video"]
    album = storage.clean_json_name(task["playlist_name"])
    
    # Resolve exact path on disk depending on audio vs video mode
    target_path = ensure_extension(
        task["path"],
        config.VIDEO_EXT if is_video else config.AUDIO_EXT
    )
    action = task["action"]

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

    # 1. Fetch metadata if missing
    needs_info = (
        song.get("thumbnail_url") in (None, "", config.JSON_FALLBACK_CHAR)
        or song.get("artist") in (None, "", config.JSON_FALLBACK_CHAR)
    )

    if needs_info and not offline and song.get("url"):
        try:
            raw_info = downloader.extract_data_from_url(song["url"])
            clean_info = downloader.select_relevant_data(raw_info)
            manifest.merge_song_info(song, clean_info)
            song["status"] = "active"
        except Exception:
            song["status"] = "DEAD"
            return "dead"

    # 2. Download Media
    if action == "DL":
        if offline or meta_only:
            return "skip"

        def _progress_cb(downloaded, total):
            if item_progress and item_task_id is not None and total > 0:
                item_progress.update(
                    item_task_id, completed=downloaded, total=total
                )

        success = downloader.download_media(
            song.get("url"),
            target_path,
            is_video=is_video,
            progress_callback=_progress_cb,
        )

        if not success:
            song["status"] = "DEAD"
            return "fail"

        song["status"] = "active"
        action = "META"

    # 3. Apply media metadata
    if action == "META" and target_path.exists():
        thumb_path = None
        if not offline and not no_thumb and song.get("thumbnail_url"):
            temp_thumb = target_path.parent / f"{target_path.stem}_thumb.jpg"
            if downloader.download_thumbnail(song["thumbnail_url"], temp_thumb):
                thumb_path = temp_thumb

        try:
            metadata.write_audio_metadata(
                audio_path=target_path,
                data=song,
                cover_jpg_path=thumb_path,
                delete_thumbnail=True,
                album=album
            )
            song["status"] = "active"
            return "success"
        except Exception:
            song["status"] = "ERR"
            return "fail"

    return "skip"

def _process_playlist_sync(
    playlist_dir: Path, flags: dict, concurrency: int | None = None
) -> dict:
    json_paths = storage.separate_json_manifest_paths([playlist_dir])
    if not json_paths:
        ui.CONSOLE.print(
            f"[red]Error: Missing manifest in {playlist_dir.name}[/]"
        )
        return {"dl": 0, "meta": 0, "fail": 0, "skip": 0, "dead": 0}

    json_path = json_paths[0]
    json_data = manifest.load_json_manifest(json_path)
    desired_songs = json_data.get("songs", [])
    download_all = bool(json_data.get("download_video_all", False))

    music_dir = playlist_dir / "music"
    storage.make_directory(music_dir)

    music_paths = storage.separate_music_paths([playlist_dir])[0]
    songs_on_disk = {file.name: file for file in music_paths}

    tasks = []
    for song in desired_songs:
        title = song.get("title", "Unknown")
        is_video = download_all or bool(song.get("download_video", False))
        ext = config.VIDEO_EXT if is_video else config.AUDIO_EXT
        target_path = music_dir / f"{title}{ext}"

        action = "META" if target_path.exists() else "DL"
        songs_on_disk.pop(target_path.name, None)

        tasks.append(
            {
                "song": song,
                "is_video": is_video,
                "path": target_path,
                "action": action,
                "pl_path": playlist_dir,
                "playlist_name": playlist_dir.name,
            }
        )

    # Clean orphans
    for orphan in songs_on_disk.values():
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            storage.move(
                str(orphan), config.TRASH / f"{orphan.name}_{timestamp}"
            )
        except OSError:
            pass

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

                def _thread_job(t=task, tid=item_task_id):
                    res = _execute_sync_task(
                        t, flags, json_path, item_progress, tid
                    )
                    item_progress.remove_task(tid)
                    return res

                future = executor.submit(_thread_job)
                future_to_task[future] = task

            for future in concurrent.futures.as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    res = future.result()
                except Exception as e:
                    print(f"Error type: {type(e).__name__}")
                    print(f"Error message: {e}")
                    res = "fail"

                with manifest_lock:
                    if res == "success":
                        if task["action"] == "DL":
                            stats["dl"] += 1
                        else:
                            stats["meta"] += 1
                    elif res == "skip":
                        stats["skip"] += 1
                    elif res == "dead":
                        stats["dead"] += 1
                    else:
                        stats["fail"] += 1

                global_progress.update(main_task_id, advance=1)

    manifest.write_to_json(json_path, json_data)
    ui.render_sync_summary(stats, len(tasks), playlist_dir.name)

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
        clean_pl_name = storage.clean_playlist_name(playlist_name)
        target_dir = storage.find_playlist_directory(config.MUSIC_ROOT, clean_pl_name)
        if not target_dir:
            ui.CONSOLE.print(f"[red]Error: Playlist '{clean_pl_name}' not found.[/]")
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

def cmd_clear_fail(playlist_name: str, song_name: str = None, all_songs: bool = False):
    clean_pl_name = storage.clean_playlist_name(playlist_name)
    target_dir = storage.find_playlist_directory(config.MUSIC_ROOT, clean_pl_name)
    
    if not target_dir:
        ui.CONSOLE.print(f"[red]Error: Playlist '{clean_pl_name}' not found.[/]")
        return

    json_paths = storage.separate_json_manifest_paths(target_dir)

    # Check if the list returned any valid JSON manifest paths
    if not json_paths:
        ui.CONSOLE.print(f"[red]Error: No JSON manifest found in '{target_dir}'.[/]")
        return

    # Extract the single Path object from the list
    json_path = json_paths[0]
    
    json_data = manifest.load_json_manifest(json_path)
    songs = json_data.get("songs", [])

    if not songs:
        ui.CONSOLE.print(f"[yellow]No songs found in playlist '{clean_pl_name}'.[/]")
        return

    targets_to_clear = []

    # Clear all failed statuses
    if all_songs:
        targets_to_clear = songs

    # Target specific song by name
    elif song_name:
        matches = [
            s for s in songs 
            if s.get("title", "").lower() == song_name.lower()
        ]

        if not matches:
            ui.CONSOLE.print(f"[yellow]No song matching '{song_name}' found in playlist.[/]")
            return
            
        elif len(matches) == 1:
            targets_to_clear = matches
            
        else:
            # Disambiguation prompt for duplicate titles
            ui.CONSOLE.print(f"[yellow]Multiple songs named '{song_name}' found:[/]")
            for index, song in enumerate(matches, 1):
                title = song.get("title", "Unknown")
                song_id = song.get("id", "N/A")
                ui.CONSOLE.print(f"  [cyan]{index}[/]. {title} [dim]({song_id})[/dim]")

            # Safe integer prompt with validation
            selected_idx = IntPrompt.ask(
                "Which song do you want to clear?",
                choices=[str(i) for i in range(1, len(matches) + 1)]
            )
            targets_to_clear = [matches[selected_idx - 1]]
    else:
        ui.CONSOLE.print("[red]Error: Must specify a song_name or set all_songs=True.[/]")
        return

    # Reset failure/status indicators
    cleared_count = 0
    for song in targets_to_clear:
        song["status"] = "active"
        cleared_count += 1

    # Save manifest back to disk
    manifest.write_to_json(json_path, json_data)
    ui.CONSOLE.print(f"[green]Successfully reset failure status for {cleared_count} track(s).[/]")