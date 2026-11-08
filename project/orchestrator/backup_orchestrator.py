from pathlib import Path
import zipfile
import zlib

from rich.prompt import Confirm

import subsystem.config as config
import subsystem.storage as storage
import subsystem.ui as ui

def cmd_backup() -> None:
    try:
        manifest_paths = storage.find_all_manifest_paths(config.MUSIC_ROOT)
    except OSError as error:
        ui.CONSOLE.print(f"[red]Could not find playlist manifests: {error}[/]")
        return

    if not manifest_paths:
        ui.CONSOLE.print("[yellow]No playlist manifests found to back up.[/]")
        return

    try:
        archive_path = storage.backup_manifests(
            manifest_paths, config.MUSIC_ROOT, config.BACKUP
        )
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        ui.CONSOLE.print(f"[red]Could not create manifest backup: {error}[/]")
        return

    ui.CONSOLE.print(f"[green]Manifest backup created: {archive_path}[/]")

def cmd_restore(backup_file: str) -> None:
    archive_path = Path(backup_file)
    try:
        restored_files = storage.read_manifest_backup(archive_path)
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
        storage.restore_manifests(restored_files, config.MUSIC_ROOT)
    except (OSError, ValueError) as error:
        ui.CONSOLE.print(f"[red]Could not restore manifest backup: {error}[/]")
        return

    ui.CONSOLE.print(
        f"[green]Restored {len(restored_files)} manifest file(s) "
        f"from {archive_path}.[/]"
    )