__author__ = "Iron Smithy"
__version__ = "0.1.0"

import orchestrator

import argparse

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="pl-dlp", description="Playlist Manager"
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. 'ls' command (playlist is optional: if omitted, list all playlists)
    ls_parser = subparsers.add_parser(
        "ls", help="List playlists or tracks in a playlist"
    )
    ls_parser.add_argument(
        "playlist",
        nargs="?",
        default=None,
        help="Optional name of a playlist",
    )

    # 2. 'new' command
    new_parser = subparsers.add_parser(
        "new", help="Create a new empty playlist folder"
    )
    new_parser.add_argument("playlist_name", help="Name of the new playlist")

    # 3. 'rm' command
    rm_parser = subparsers.add_parser(
        "rm", help="Move a playlist to the trash bin"
    )
    rm_parser.add_argument("playlist", help="Name of the playlist to remove")

    # 4. 'mv' command
    mv_parser = subparsers.add_parser(
        "mv", help="Move or rename a playlist folder"
    )
    mv_parser.add_argument("old_path", help="Current playlist name/path")
    mv_parser.add_argument("new_path", help="New playlist name/path")

    # 5. 'update' command (Download/Sync)
    update_parser = subparsers.add_parser("update", help="Update/Sync playlist")
    update_parser.add_argument("playlist", help="Name of playlist to update")
    update_parser.add_argument(
        "--meta-only", action="store_true", help="Only update metadata JSON"
    )

    # Parse arguments provided by the user
    args = parser.parse_args()

    # Route commands to their respective actions
    if args.command == "ls":
        if args.playlist:
            orchestrator.cmd_list_playlist(args.playlist)
        else:
            orchestrator.cmd_list_all()

    elif args.command == "new":
        orchestrator.cmd_new_playlist(args.playlist_name)

    elif args.command == "rm":
        print(f"[ACTION] Moving playlist to trash: {args.playlist}")

    elif args.command == "mv":
        print(f"[ACTION] Renaming '{args.old_path}' to '{args.new_path}'")

    elif args.command == "update":
        print(
            f"[ACTION] Updating {args.playlist} (Meta-only: {args.meta_only})"
        )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130) from None