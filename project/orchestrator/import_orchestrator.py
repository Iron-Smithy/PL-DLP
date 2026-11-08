from pathlib import Path

import subsystem.config as config
import subsystem.downloader as downloader
import subsystem.manifest as manifest
import command_utility as command_utility
import subsystem.storage as storage
import subsystem.ui as ui

def add_songs(playlist_name: str, sources: list[str]) -> None:
    """Fetch metadata for source URLs and append tracks to an existing playlist."""
    clean_playlist_name = storage.clean_playlist_name(playlist_name)
    playlist_dir = storage.find_playlist_directory(
        config.MUSIC_ROOT, clean_playlist_name
    )

    if not playlist_dir:
        ui.CONSOLE.print(f"[red]Error: Playlist '{playlist_name}' not found.[/]")
        return

    manifest_name = storage.clean_json_name(clean_playlist_name)
    manifest_path = storage.find_manifest_path(
        playlist_dir, manifest_name, config.MANIFEST_FORMAT
    )
    if not manifest_path.exists():
        ui.CONSOLE.print(f"[red]Error: Manifest '{manifest_path.name}' missing.[/]")
        return

    for url in command_utility.read_url_sources(sources):
        ui.CONSOLE.print(f"[blue]Fetching track metadata:[/] {url}")
        try:
            raw_info = downloader.extract_data_from_url(url)
            song_data = manifest.create_track_entry_from_raw(raw_info, url)
            manifest.add_track_to_metadata(manifest_path, song_data)
            ui.CONSOLE.print(f"[green]Added:[/] {song_data.get('title', 'Unknown')}")
        except Exception as error:
            ui.CONSOLE.print(f"[red]Failed to add {url}: {error}[/]")

def import_playlist(
    source: str,
    playlist_name: str | None = None,
    manifest_format: str | None = None,
) -> None:
    """Import a YouTube playlist or local link file into a playlist manifest."""
    source_path = Path(source)
    default_name = (
        source_path.stem if source_path.is_file() else "imported_playlist"
    )
    requested_name = playlist_name or default_name
    clean_playlist_name = storage.clean_playlist_name(requested_name)

    if source_path.is_file():
        urls_to_import = command_utility.extract_urls_from_file(source_path)
    else:
        ui.CONSOLE.print(
            f"[bold blue]Scraping playlist entries from YouTube:[/] {source}"
        )
        urls_to_import = downloader.import_playlist(source, [])

    if not urls_to_import:
        ui.CONSOLE.print(
            f"[red]No valid YouTube track links found in '{source}'. "
            "Aborting import.[/]"
        )
        return

    playlist_dir = config.MUSIC_ROOT / clean_playlist_name
    playlist_dir.mkdir(parents=True, exist_ok=True)
    (playlist_dir / "music").mkdir(parents=True, exist_ok=True)

    manifest_name = storage.clean_json_name(clean_playlist_name)
    manifest_path = storage.find_manifest_path(
        playlist_dir, manifest_name, manifest_format or config.MANIFEST_FORMAT
    )
    if not manifest_path.exists():
        manifest.write_empty_playlist_object(manifest_path, clean_playlist_name)

    ui.CONSOLE.print(
        f"[green]Found {len(urls_to_import)} track links to import.[/]"
    )

    imported_count = 0
    for url in urls_to_import:
        try:
            ui.CONSOLE.print(f"[blue]Extracting metadata:[/] {url}")
            raw_info = downloader.extract_data_from_url(url)
            song_data = manifest.create_track_entry_from_raw(raw_info, url)
            manifest.add_track_to_metadata(manifest_path, song_data)
            imported_count += 1
            ui.CONSOLE.print(
                f"[green]Added:[/] {song_data.get('title', 'Unknown')}"
            )
        except Exception as error:
            ui.CONSOLE.print(f"[red]Failed to import track ({url}): {error}[/]")

    if imported_count == 0:
        ui.CONSOLE.print(
            "[red]Failed to import any tracks. "
            "Cleaning up empty playlist folder...[/]"
        )
        storage.remove_directory_tree(playlist_dir)
        return

    ui.CONSOLE.print(
        f"\n[bold green]Import complete for '{clean_playlist_name}'![/] "
        "Run 'update' to download audio files."
    )
