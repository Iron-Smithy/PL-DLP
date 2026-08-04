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