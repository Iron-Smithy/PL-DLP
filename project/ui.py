from rich.console import Console
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn

console = Console()

def list_all(names: list[str], track_count: list[int], tracks_downloaded: list[int], total_sizes: list[int]):
    table = Table(title="All Playlists", header_style="bold cyan")
    table.add_column("Name")
    table.add_column("Tracks", justify="right")
    table.add_column("Tracks Downloaded", justify="right")
    table.add_column("Total Size", justify="right")

    if not (len(names) == len(track_count) == len(tracks_downloaded) == len(total_sizes)):
        raise ValueError("Lists are not all the same length.")

    for i, name in enumerate(names):
        # Converted integers to strings using f-strings
        table.add_row(
            name, 
            f"{track_count[i]}", 
            f"{tracks_downloaded[i]}", 
            f"{total_sizes[i]:.1f} MB"
        )

    console.print(table)

def list_one(pl_name: str, title_list: list[str], downloaded_list: list[bool], length_list: list[int], size_list: list[int]):
    table = Table(title=f"Tracks in {pl_name}", header_style="bold green")
    table.add_column("Title")
    table.add_column("Downloaded?")
    table.add_column("Length", justify="right")
    table.add_column("Size", justify="right")

    if not (len(title_list) == len(downloaded_list) == len(length_list) == len(size_list)):
        raise ValueError("Lists are not all the same length.")

    for i, title in enumerate(title_list):
        # Converted integers to strings using f-strings
        table.add_row(
            title, 
            f"{downloaded_list[i]}", 
            f"{length_list[i]}", 
            f"{size_list[i]:.1f} MB"
        )

    console.print(table)