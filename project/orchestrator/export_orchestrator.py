from pathlib import Path

import subsystem.config as config
import subsystem.downloader as downloader
import subsystem.exporter as exporter
import subsystem.manifest as manifest
import subsystem.metadata as metadata
import subsystem.storage as storage
import subsystem.ui as ui

def export_playlist(
    playlist_name: str,
    output_dir: str | Path,
    target_format: str | None = None,
    no_thumb: bool = False,
    no_video: bool = False,
    legacy_mp3_mode: bool = False,
    max_img_dim: int | None = None,
    zip_output: bool = False,
) -> None:
    """Convert or copy a playlist's media files into an export directory."""
    clean_playlist_name = storage.clean_playlist_name(playlist_name)
    playlist_dir = storage.find_playlist_directory(
        config.MUSIC_ROOT, clean_playlist_name
    )

    if not playlist_dir:
        ui.CONSOLE.print(
            f"[red]Error: Playlist '{playlist_name}' not found.[/]"
        )
        return

    export_dir = Path(output_dir).expanduser().resolve() / clean_playlist_name
    storage.make_directory(export_dir, parents=True)

    manifest_paths = storage.separate_manifest_paths(playlist_dir)
    if not manifest_paths:
        ui.CONSOLE.print(
            f"[red]Error: Manifest for '{clean_playlist_name}' not found.[/]"
        )
        return

    playlist_data = manifest.load_manifest(manifest_paths[0])
    songs = playlist_data.get("songs", playlist_data.get("tracks", []))

    strict_ascii = legacy_mp3_mode
    export_format = "mp3" if legacy_mp3_mode else (target_format or "m4a")
    strip_video = no_video or legacy_mp3_mode
    thumbnail_max_dimension = (
        max_img_dim
        if max_img_dim is not None
        else (500 if legacy_mp3_mode else None)
    )

    ui.CONSOLE.print(
        f"[cyan]Exporting '{clean_playlist_name}' to {export_dir}...[/]"
    )

    for song in songs:
        title = song.get("title", "Unknown")
        safe_name = exporter.sanitize_filename(title, strict_ascii=strict_ascii)
        stored_name = exporter.sanitize_filename(title)
        source_file = _find_source_media(
            playlist_dir, safe_name, stored_name, title
        )
        if source_file is None:
            continue

        target_file = export_dir / f"{safe_name}.{export_format}"
        try:
            if source_file.suffix.lstrip(".") != export_format or strip_video:
                exporter.convert_media(
                    source_file,
                    target_file,
                    target_format=export_format,
                    strip_video=strip_video,
                )
            else:
                storage.copy_file(source_file, target_file)
        except Exception as error:
            ui.CONSOLE.print(f"[red]Failed to export '{title}': {error}[/]")
            continue

        if no_thumb:
            continue

        thumbnail_path = export_dir / f"{safe_name}.jpg"
        local_thumbnail = playlist_dir / "music" / f"{safe_name}_thumb.jpg"
        if not local_thumbnail.exists():
            local_thumbnail = playlist_dir / "music" / f"{safe_name}.jpg"

        if local_thumbnail.exists():
            storage.copy_file(local_thumbnail, thumbnail_path)
        elif song.get("thumbnail_url"):
            try:
                downloader.download_thumbnail(
                    song["thumbnail_url"], thumbnail_path
                )
            except Exception:
                pass

        if not thumbnail_path.exists():
            continue
        if thumbnail_max_dimension:
            exporter.adjust_image_quality(
                thumbnail_path, max_dimension=thumbnail_max_dimension
            )

        if export_format == "mp3":
            exporter.embed_mp3_cover(target_file, thumbnail_path)
        elif export_format == "m4a":
            metadata.write_audio_metadata(
                audio_path=target_file,
                data=song,
                cover_jpg_path=thumbnail_path,
                delete_thumbnail=False,
                album=clean_playlist_name,
            )

    if zip_output:
        archive_base = export_dir.parent / f"{clean_playlist_name}_export"
        zip_file = storage.create_zip_archive(archive_base, export_dir)
        storage.remove_directory_tree(export_dir)
        ui.CONSOLE.print(f"[green]Export successfully zipped to:[/] {zip_file}")
        return

    ui.CONSOLE.print(f"[green]Export complete at:[/] {export_dir}")

def _find_source_media(
    playlist_dir: Path, safe_name: str, stored_name: str, title: str
) -> Path | None:
    for source_name in dict.fromkeys((safe_name, stored_name, title)):
        for extension in (config.AUDIO_EXT, config.VIDEO_EXT, ".mp3", ".webm"):
            candidate = playlist_dir / "music" / f"{source_name}{extension}"
            if candidate.exists():
                return candidate
    return None
