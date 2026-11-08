from datetime import datetime
from pathlib import Path, PurePosixPath
import zipfile
import zlib

from rich.prompt import Confirm

import subsystem.config as config
import subsystem.storage as storage
import subsystem.ui as ui

def _find_manifest_files() -> list[Path]:
    return sorted(
        (
            path
            for playlist_dir in storage.find_playlist_directories(config.MUSIC_ROOT)
            for path in playlist_dir.iterdir()
            if path.is_file()
            and path.suffix.lower() in storage.MANIFEST_EXTENSIONS
        ),
        key=lambda path: path.as_posix().casefold(),
    )

def cmd_backup() -> None:
    try:
        manifest_paths = _find_manifest_files()
    except OSError as error:
        ui.CONSOLE.print(f"[red]Could not find playlist manifests: {error}[/]")
        return

    if not manifest_paths:
        ui.CONSOLE.print("[yellow]No playlist manifests found to back up.[/]")
        return

    try:
        config.BACKUP.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        archive_path = config.BACKUP / f"{timestamp}.zip"
        with zipfile.ZipFile(
            archive_path, "w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for manifest_path in manifest_paths:
                archive.write(
                    manifest_path,
                    arcname=manifest_path.relative_to(config.MUSIC_ROOT).as_posix(),
                )
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        ui.CONSOLE.print(f"[red]Could not create manifest backup: {error}[/]")
        return

    ui.CONSOLE.print(f"[green]Manifest backup created: {archive_path}[/]")

def _read_backup(backup_file: Path) -> list[tuple[Path, bytes]]:
    restored_files: list[tuple[Path, bytes]] = []
    seen_paths: set[Path] = set()

    with zipfile.ZipFile(backup_file, "r") as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue

            archive_path = PurePosixPath(member.filename)
            if archive_path.suffix.lower() not in storage.MANIFEST_EXTENSIONS:
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

def cmd_restore(backup_file: str) -> None:
    archive_path = Path(backup_file)
    try:
        restored_files = _read_backup(archive_path)
    except (
        OSError,
        ValueError,
        EOFError,
        RuntimeError,
        NotImplementedError,
        zipfile.BadZipFile,
        zlib.error,
    ) as error:
        ui.CONSOLE.print(f"[red]Could not read manifest backup: {error}[/]")
        return

    existing_files = [
        relative_path
        for relative_path, _ in restored_files
        if (config.MUSIC_ROOT / relative_path).exists()
    ]
    for relative_path, _ in restored_files:
        destination = config.MUSIC_ROOT / relative_path
        if destination.parent.is_symlink() or destination.is_symlink():
            ui.CONSOLE.print(
                f"[red]Cannot restore through a symbolic link: {destination}[/]"
            )
            return
        if destination.exists() and not destination.is_file():
            ui.CONSOLE.print(
                f"[red]Cannot restore over a non-file path: {destination}[/]"
            )
            return

    if existing_files and not Confirm.ask(
        "Do you wish to restore this backup? "
        f"It will override {len(existing_files)} manifest file(s).",
        default=False,
    ):
        ui.CONSOLE.print("[yellow]Manifest restore cancelled.[/]")
        return

    try:
        for relative_path, contents in restored_files:
            destination = config.MUSIC_ROOT / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(contents)
    except OSError as error:
        ui.CONSOLE.print(f"[red]Could not restore manifest backup: {error}[/]")
        return

    ui.CONSOLE.print(
        f"[green]Restored {len(restored_files)} manifest file(s) "
        f"from {archive_path}.[/]"
    )