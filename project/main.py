__author__ = "Iron Smithy"
__version__ = "0.1.0"

import argparse
import orchestrator


def main() -> int:
    parser = argparse.ArgumentParser(prog="pl-dlp", description="Playlist Manager")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. 'ls' command
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
    new_parser = subparsers.add_parser("new", help="Create a new empty playlist folder")
    new_parser.add_argument("playlist_name", help="Name of the new playlist")

    # 3. 'rm' command
    rm_parser = subparsers.add_parser("rm", help="Move a playlist to the trash bin")
    rm_parser.add_argument("playlist_name", help="Name of the playlist to remove")

    # 4. 'mv' command
    mv_parser = subparsers.add_parser("mv", help="Rename a playlist folder")
    mv_parser.add_argument("old_name", help="Current playlist name")
    mv_parser.add_argument("new_name", help="New playlist name")

    # 5. 'update' command (Download/Sync)
    update_parser = subparsers.add_parser("update", help="Update/Sync playlist")
    update_parser.add_argument(
        "playlist", nargs="?", default=None, help="Optional name of playlist to update"
    )

    # ***REMOVED*** Media & Download Controls ***REMOVED***
    update_parser.add_argument(
        "--meta-only",
        action="store_true",
        help="Only process metadata JSON; do not download audio/video files",
    )
    update_parser.add_argument(
        "--no-thumb",
        action="store_true",
        help="Skip embedding thumbnails/artwork into downloaded files",
    )
    update_parser.add_argument(
        "--retry-dead",
        action="store_true",
        help="Ignore 'dead link' flags in JSON and retry fetching them anyway",
    )

    # ***REMOVED*** Network & Writing Behavior ***REMOVED***
    update_parser.add_argument(
        "--offline", action="store_true", help="Do not download or fetch anything online"
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
        orchestrator.cmd_remove_playlist(args.playlist_name)

    elif args.command == "mv":
        orchestrator.cmd_rename_playlist(args.old_name, args.new_name)

    elif args.command == "update":
        flags_info = (
            f"Meta-only: {args.meta_only}, "
            f"No-thumb: {args.no_thumb}, "
            f"Retry-dead: {args.retry_dead}, "
            f"Offline: {args.offline}"
        )

        if args.playlist:
            print(
                f"[ACTION] Updating specific playlist: {args.playlist} | Flags: {flags_info}"
            )
            orchestrator.cmd_update_playlist(args.playlist, args.meta_only, args.no_thumb, args.retry_dead, args.offline)
        else:
            print(f"[ACTION] Updating ALL playlists globally | Flags: {flags_info}")
            orchestrator.cmd_update_all(args.meta_only, args.no_thumb, args.retry_dead, args.offline)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130) from None
