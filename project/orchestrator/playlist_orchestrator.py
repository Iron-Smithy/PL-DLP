from datetime import datetime
import json
import os
from pathlib import Path
import platform
import subprocess

from rich.prompt import Confirm, IntPrompt

import subsystem.config as config
import subsystem.exporter as exporter
import subsystem.manifest as manifest
import subsystem.storage as storage
import subsystem.ui as ui

def cmd_config_manifest_format(manifest_format: str | None = None) -> None:
    try:
        user_config = config.read_user_config(config.CONFIG_FILE)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        ui.CONSOLE.print(f"[red]Could not read config.json: {error}[/]")
        return

    current_format = config.normalize_manifest_format(
        user_config.get("manifest_format")
    )
    if manifest_format is None and current_format is not None:
        ui.CONSOLE.print(f"Preferred manifest format: {current_format}")
        return

    chosen_format = manifest_format or config.prompt_manifest_format()
    try:
        config.write_user_config(
            {"manifest_format": chosen_format}, config.CONFIG_FILE
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        ui.CONSOLE.print(f"[red]Could not update config.json: {error}[/]")
        return

    config.MANIFEST_FORMAT = chosen_format
    ui.CONSOLE.print(f"[green]Preferred manifest format set to {chosen_format}.[/]")

def cmd_open(target: str) -> None:
    if target.casefold() == "self":
        folder = config.PROGRAM_ROOT
    else:
        folder = storage.find_playlist_directory(config.MUSIC_ROOT, target)
        if folder is None:
            ui.CONSOLE.print(f"[red]Playlist '{target}' was not found.[/]")
            return

    if not folder.is_dir():
        ui.CONSOLE.print(f"[red]Folder does not exist: {folder}[/]")
        return

    system_name = platform.system()
    try:
        if system_name == "Windows":
            os.startfile(str(folder))
        elif system_name == "Darwin":
            _open_folder_with_command(["open", str(folder)])
        elif system_name == "Linux":
            _open_folder_with_command(["xdg-open", str(folder)])
        else:
            ui.CONSOLE.print(
                f"[red]Opening folders is not supported on {system_name}.[/]"
            )
            return
    except (OSError, subprocess.TimeoutExpired) as error:
        ui.CONSOLE.print(f"[red]Could not open folder '{folder}': {error}[/]")
        return

    ui.CONSOLE.print(f"[green]Opened folder: {folder}[/]")

def _open_folder_with_command(command: list[str]) -> None:
    result = subprocess.run(
        command, capture_output=True, text=True, timeout=15
    )
    if result.returncode:
        raise OSError(
            result.stderr.strip() or "The system folder opener failed."
        )

def cmd_list_all() -> None:
    playlist_dirs = storage.find_playlist_directories(config.MUSIC_ROOT)
    names = []
    track_counts = []
    downloaded_track_counts = []
    total_sizes = []

    for playlist_dir in playlist_dirs:
        manifest_paths = storage.separate_manifest_paths(playlist_dir)
        if not manifest_paths:
            continue
        playlist_data = manifest.load_manifest(manifest_paths[0])
        music_paths = storage.separate_music_paths(playlist_dir)[0]

        names.append(
            playlist_dir.name
            or playlist_data.get("playlist_name", config.JSON_FALLBACK_CHAR)
        )
        track_counts.append(
            playlist_data.get("total_tracks", config.JSON_FALLBACK_CHAR)
        )
        downloaded_track_counts.append(len(music_paths))
        total_sizes.append(storage.get_directory_size(music_paths))

    ui.list_all(names, track_counts, downloaded_track_counts, total_sizes)

def cmd_list_playlist(playlist_name: str) -> None:
    clean_playlist_name = storage.clean_playlist_name(playlist_name)
    playlist_dir = storage.find_playlist_directory(
        config.MUSIC_ROOT, clean_playlist_name
    )
    if not playlist_dir:
        ui.CONSOLE.print(
            f"[red]The playlist {clean_playlist_name} cannot be found[/]"
        )
        return

    manifest_path = storage.separate_manifest_paths(playlist_dir)[0]
    playlist_data = manifest.load_manifest(manifest_path)
    songs = playlist_data.get("songs", [])
    music_paths = storage.separate_music_paths(playlist_dir)[0]
    downloaded_files = {path.name: path for path in music_paths}

    titles = []
    downloaded = []
    lengths = []
    sizes = []
    for song in songs:
        title = song.get("title", "Unknown")
        safe_title = exporter.sanitize_filename(title)
        file_path = next(
            (
                downloaded_files[f"{name}{extension}"]
                for name in dict.fromkeys((safe_title, title))
                for extension in (config.AUDIO_EXT, config.VIDEO_EXT)
                if f"{name}{extension}" in downloaded_files
            ),
            None,
        )

        if file_path is None:
            length = song.get("length", config.JSON_FALLBACK_CHAR)
            size = 0
        else:
            length = storage.get_media_duration(file_path)
            size = storage.get_file_size(file_path)

        titles.append(title)
        downloaded.append(file_path is not None)
        lengths.append(length)
        sizes.append(size)

    ui.list_one(clean_playlist_name, titles, downloaded, lengths, sizes)

def cmd_new_playlist(
    playlist_name: str, manifest_format: str | None = None
) -> None:
    requested_name = (playlist_name or "new-playlist").strip()
    potential_manifest = Path(requested_name).expanduser().resolve(strict=False)

    if (
        potential_manifest.is_file()
        and potential_manifest.suffix.lower() in storage.MANIFEST_EXTENSIONS
    ):
        clean_playlist_name = storage.clean_playlist_name(
            potential_manifest.stem
        )
        playlist_dir = config.MUSIC_ROOT / clean_playlist_name
        if playlist_dir.exists():
            ui.CONSOLE.print(
                f"[red]Error: Folder {clean_playlist_name} already exists.[/]"
            )
            return

        storage.make_directory(playlist_dir, parents=True)
        storage.make_directory(playlist_dir / "music")
        manifest_name = storage.clean_json_name(clean_playlist_name)
        target_manifest = (
            playlist_dir / f"{manifest_name}{potential_manifest.suffix.lower()}"
        )
        storage.move(str(potential_manifest), str(target_manifest))
        ui.CONSOLE.print(
            f"[green]Manifest moved![/] Folder {clean_playlist_name} is ready."
        )
        return

    clean_playlist_name = storage.clean_playlist_name(
        Path(requested_name).expanduser().name
    )
    playlist_dir = config.MUSIC_ROOT / clean_playlist_name
    if playlist_dir.exists():
        ui.CONSOLE.print(
            f"[red]Error: {clean_playlist_name} already exists.[/]"
        )
        return

    manifest_name = storage.clean_json_name(clean_playlist_name)
    storage.make_directory(playlist_dir)
    storage.make_directory(playlist_dir / "music")
    manifest_path = storage.generate_manifest_path(
        playlist_dir,
        manifest_name,
        manifest_format or config.MANIFEST_FORMAT,
    )
    manifest.write_empty_playlist_object(manifest_path, manifest_name)
    ui.CONSOLE.print(
        f"[green]Created empty playlist: {clean_playlist_name}[/]"
    )

def cmd_remove_playlist(playlist_name: str) -> None:
    playlist_name = playlist_name.strip()
    playlist_dir = storage.find_playlist_directory(
        config.MUSIC_ROOT, playlist_name
    )
    if not playlist_dir:
        ui.CONSOLE.print(f"[red]Error: {playlist_name} not found.[/]")
        return

    if Confirm.ask(
        f"Are you sure you want to move [bold red]{playlist_name}[/] to trash?"
    ):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_path = config.TRASH / f"{playlist_name}_{timestamp}"
        try:
            storage.move(str(playlist_dir), target_path)
        except OSError as error:
            ui.CONSOLE.print(f"[red]Could not move to trash:[/] {error}")
            return
        ui.CONSOLE.print(f"[yellow]{playlist_name} moved to {config.TRASH}[/]")

def cmd_rename_playlist(old_name: str, new_name: str) -> None:
    clean_old_name = storage.clean_playlist_name(old_name)
    clean_new_name = storage.clean_playlist_name(new_name)
    old_path = config.MUSIC_ROOT / clean_old_name
    new_path = config.MUSIC_ROOT / clean_new_name

    if not old_path.exists():
        ui.CONSOLE.print(f"[red]Error: Source {clean_old_name} not found.[/]")
        return
    if new_path.exists():
        ui.CONSOLE.print(
            f"[red]Error: Destination {clean_new_name} already exists.[/]"
        )
        return

    try:
        storage.move(old_path, new_path)
    except OSError as error:
        ui.CONSOLE.print(f"[red]Rename failed:[/] {error}")
        return

    ui.CONSOLE.print(
        f"[green]Successfully renamed {clean_old_name} to {clean_new_name}[/]"
    )

def cmd_clear_fail(
    playlist_name: str,
    song_name: str | None = None,
    all_songs: bool = False,
) -> None:
    clean_playlist_name = storage.clean_playlist_name(playlist_name)
    playlist_dir = storage.find_playlist_directory(
        config.MUSIC_ROOT, clean_playlist_name
    )
    if not playlist_dir:
        ui.CONSOLE.print(
            f"[red]Error: Playlist '{clean_playlist_name}' not found.[/]"
        )
        return

    manifest_paths = storage.separate_manifest_paths(playlist_dir)
    if not manifest_paths:
        ui.CONSOLE.print(
            f"[red]Error: No playlist manifest found in '{playlist_dir}'.[/]"
        )
        return

    manifest_path = manifest_paths[0]
    playlist_data = manifest.load_manifest(manifest_path)
    songs = playlist_data.get("songs", [])
    if not songs:
        ui.CONSOLE.print(
            f"[yellow]No songs found in playlist '{clean_playlist_name}'.[/]"
        )
        return

    if all_songs:
        songs_to_clear = songs
    elif song_name:
        matches = [
            song
            for song in songs
            if song.get("title", "").lower() == song_name.lower()
        ]
        if not matches:
            ui.CONSOLE.print(
                f"[yellow]No song matching '{song_name}' found in playlist.[/]"
            )
            return
        if len(matches) == 1:
            songs_to_clear = matches
        else:
            songs_to_clear = [_select_song_match(song_name, matches)]
    else:
        ui.CONSOLE.print(
            "[red]Error: Must specify a song_name or set all_songs=True.[/]"
        )
        return

    for song in songs_to_clear:
        song["status"] = "active"
    manifest.write_manifest(manifest_path, playlist_data)
    ui.CONSOLE.print(
        "[green]Successfully reset failure status for "
        f"{len(songs_to_clear)} track(s).[/]"
    )

def _select_song_match(song_name: str, matches: list[dict]) -> dict:
    ui.CONSOLE.print(f"[yellow]Multiple songs named '{song_name}' found:[/]")
    for index, song in enumerate(matches, 1):
        title = song.get("title", "Unknown")
        song_id = song.get("id", "N/A")
        ui.CONSOLE.print(
            f"  [cyan]{index}[/]. {title} [dim]({song_id})[/dim]"
        )

    selected_index = IntPrompt.ask(
        "Which song do you want to clear?",
        choices=[str(index) for index in range(1, len(matches) + 1)],
    )
    return matches[selected_index - 1]
