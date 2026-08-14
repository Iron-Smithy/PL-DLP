__author__ = "Iron Smithy"
__version__ = "0.1.0"

import argparse
import orchestrator
import config


def create_parser() -> argparse.ArgumentParser:
    """Creates and configures the CLI argument parser."""
    parser = argparse.ArgumentParser(prog="pl-dlp", description="Playlist Manager")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 'ls' command
    ls_parser = subparsers.add_parser(
        "ls", aliases=["list", "dir"], help="List playlists or tracks in a playlist"
    )
    ls_parser.add_argument(
        "playlist",
        nargs="?",
        default=None,
        help="Optional name of a playlist",
    )

    # 'new' command (blank playlists)
    new_parser = subparsers.add_parser(
        "new", aliases=["create", "make"], help="Create a new empty playlist folder"
    )
    new_parser.add_argument("playlist_name", help="Name of the new playlist")

    # 'add' command (Append songs/URLs to an existing playlist)
    add_parser = subparsers.add_parser(
        "add", aliases=["append"], help="Add one or more song URLs to a playlist"
    )
    add_parser.add_argument("playlist", help="Target playlist name")
    add_parser.add_argument("urls", nargs="+", help="One or more YouTube URLs or a text/JSON file with URLs")

    # 'import' command (YouTube playlist URL, or raw JSON/TXT list of links)
    import_parser = subparsers.add_parser(
        "import", aliases=["ingest", "fetch"], help="Import a YouTube playlist or list of links"
    )
    import_parser.add_argument("source", help="YouTube Playlist URL or file path (JSON/TXT array of URLs)")
    import_parser.add_argument("playlist_name", nargs="?", default=None, help="Optional custom name for imported playlist")

    # 'rm' command
    rm_parser = subparsers.add_parser(
        "rm", aliases=["remove", "del", "delete"], help="Move a playlist to the trash bin"
    )
    rm_parser.add_argument("playlist_name", help="Name of the playlist to remove")

    # 'mv' command
    mv_parser = subparsers.add_parser(
        "mv", aliases=["rename", "move"], help="Rename a playlist folder"
    )
    mv_parser.add_argument("old_name", help="Current playlist name")
    mv_parser.add_argument("new_name", help="New playlist name")

    # 'update' command
    update_parser = subparsers.add_parser(
        "update", aliases=["sync", "up"], help="Update/Sync playlist"
    )
    update_parser.add_argument(
        "playlist", nargs="?", default=None, help="Optional name of playlist to update"
    )
    # Media Controls
    update_parser.add_argument("--meta-only", action="store_true", help="Only process metadata JSON; do not download audio/video files")
    update_parser.add_argument("--no-thumb", action="store_true", help="Skip embedding thumbnails/artwork into downloaded files")
    update_parser.add_argument("--retry-dead", action="store_true", help="Ignore 'dead link' flags in JSON and retry fetching them anyway")

    # Network & Engine Behavior
    update_parser.add_argument("--offline", action="store_true", help="Do not download or fetch anything online")
    update_parser.add_argument(
        "--concurrency", "-j", type=int, default=config.DEFAULT_CONCURRENT_DOWNLOADS, help="Parallel downloads"
    )

    return parser


def main() -> int:
    parser = create_parser()
    args = parser.parse_args()

    # Route commands using lists to catch all aliases
    if args.command in ["ls", "list", "dir"]:
        if args.playlist:
            orchestrator.cmd_list_playlist(args.playlist)
        else:
            orchestrator.cmd_list_all()

    elif args.command in ["new", "create", "make"]:
        orchestrator.cmd_new_playlist(args.playlist_name)

    elif args.command in ["add", "append"]:
        orchestrator.cmd_add_songs(args.playlist, args.urls)

    elif args.command in ["import", "ingest", "fetch"]:
        orchestrator.cmd_import_playlist(args.source, args.playlist_name)

    elif args.command in ["rm", "remove", "del", "delete"]:
        orchestrator.cmd_remove_playlist(args.playlist_name)

    elif args.command in ["mv", "rename", "move"]:
        orchestrator.cmd_rename_playlist(args.old_name, args.new_name)

    elif args.command in ["update", "sync", "up"]:
        update_opts = vars(args)
        playlist = update_opts.pop("playlist")
        update_opts.pop("command")
        if playlist:
            orchestrator.cmd_update_playlist(playlist, **update_opts)
        else:
            orchestrator.cmd_update_all(**update_opts)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130) from None