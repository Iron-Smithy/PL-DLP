from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Table

CONSOLE = Console()

def format_bytes(size_in_bytes: int) -> str:
    """Converts a byte integer into a human-readable file size string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_in_bytes < 1024.0:
            return (
                f"{size_in_bytes:.0f} {unit}"
                if unit == "B"
                else f"{size_in_bytes:.2f} {unit}"
            )
        size_in_bytes /= 1024.0

    return f"{size_in_bytes:.2f} PB"

def list_all(
    names: list[str],
    track_count: list[int],
    tracks_downloaded: list[int],
    total_sizes: list[int],
):
    table = Table(title="All Playlists", header_style="bold cyan")
    table.add_column("Name")
    table.add_column("Tracks", justify="right")
    table.add_column("Tracks Downloaded", justify="right")
    table.add_column("Total Size", justify="right")

    if not (
        len(names)
        == len(track_count)
        == len(tracks_downloaded)
        == len(total_sizes)
    ):
        raise ValueError("Lists are not all the same length.")

    for i, name in enumerate(names):
        table.add_row(
            name,
            f"{track_count[i]}",
            f"{tracks_downloaded[i]}",
            f"{format_bytes(total_sizes[i])}",
        )

    CONSOLE.print(table)

def list_one(
    pl_name: str,
    title_list: list[str],
    downloaded_list: list[bool],
    length_list: list[int],
    size_list: list[int],
):
    table = Table(title=f"Tracks in {pl_name}", header_style="bold green")
    table.add_column("Title")
    table.add_column("Downloaded?")
    table.add_column("Length", justify="right")
    table.add_column("Size", justify="right")

    if not (
        len(title_list)
        == len(downloaded_list)
        == len(length_list)
        == len(size_list)
    ):
        raise ValueError("Lists are not all the same length.")

    for i, title in enumerate(title_list):
        table.add_row(
            title,
            "[bold green]Yes[/]" if downloaded_list[i] else "[bold red]No[/]",
            f"{length_list[i]}",
            f"{format_bytes(size_list[i])}",
        )

    CONSOLE.print(table)

def create_sync_progress_group():
    """Restores the v8.7.2 dual progress bars with spinners and stylized text."""
    global_progress = Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=None),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed}/{task.total})"),
        console=CONSOLE,
    )

    item_progress = Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(bar_width=25),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=CONSOLE,
    )

    return global_progress, item_progress

def render_sync_summary(stats: dict, total_tasks: int, playlist_name: str):
    """Restores the old version's fancy colored table & panel summary."""
    table = Table.grid(padding=(0, 2))
    table.add_column(justify="left")
    table.add_column(justify="right")

    table.add_row("[bold cyan]Playlist:[/]", playlist_name)
    table.add_row("[bold white]Total Tracks Evaluated:[/]", str(total_tasks))
    table.add_row("[bold green]Downloaded (New):[/]", str(stats.get("dl", 0)))
    table.add_row("[bold yellow]Metadata Refreshed:[/]", str(stats.get("meta", 0)))
    table.add_row("[bold blue]Skipped / Up-to-date:[/]", str(stats.get("skip", 0)))

    if stats.get("dead", 0) > 0:
        table.add_row("[bold magenta]Dead Links Encountered:[/]", str(stats["dead"]))
    if stats.get("fail", 0) > 0:
        table.add_row("[bold red]Failed Operations:[/]", str(stats["fail"]))

    CONSOLE.print("\n")
    CONSOLE.print(
        Panel(
            table,
            title="[magenta]PL-DLP Sync Engine Summary[/]",
            border_style="blue",
            expand=False,
        )
    )