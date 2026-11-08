__author__ = "Iron Smithy"
__version__ = "0.2.4"

import sys  # Built-in module
import update_code

if __name__ == "__main__" and sys.argv[1:2] == ["update-self"]:
    raise SystemExit(0 if update_code.update_application() else 1)

module_to_pip = {
    "yt_dlp": "yt-dlp",
    "mutagen": "mutagen",
    "PIL": "Pillow",
    "rich": "rich",
    "yaml": "PyYAML"
}

missing_modules = []

# Run the dynamic check
for mod in module_to_pip.keys():
    try:
        __import__(mod)
    except ImportError:
        missing_modules.append(mod)

# Handle the results
if missing_modules:
    missing_pip_packages = [module_to_pip[m] for m in missing_modules]
    print(f"[Info] Missing modules: {', '.join(missing_modules)}")
    sys.exit(1)

import argparse
import subsystem.config as config
import orchestrator.playlist_orchestrator as playlist_orchestrator
import orchestrator.export_orchestrator as export_orchestrator
import orchestrator.import_orchestrator as import_orchestrator
import orchestrator.update_orchestrator as update_orchestrator
import orchestrator.backup_orchestrator as backup_orchestrator

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
    new_parser.add_argument(
        "--manifest-format",
        choices=["json", "yaml"],
        default=None,
        help="Format for the new manifest (default: config setting)",
    )

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
    import_parser.add_argument(
        "--manifest-format",
        choices=["json", "yaml"],
        default=None,
        help="Format for a new manifest (default: config setting)",
    )

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

    export_parser = subparsers.add_parser("export", help="Export a playlist with compatibility & formatting options")
    export_parser.add_argument("playlist", help="Name of the playlist to export")
    export_parser.add_argument(
        "-o",
        "--output",
        default="./exports",
        help="Destination directory for exported files (default: ./exports)",
    )
    export_parser.add_argument(
        "-f",
        "--format",
        choices=["mp3", "m4a", "flac", "wav"],
        default=None,
        help="Target audio container format",
    )
    export_parser.add_argument("--no-thumb", action="store_true", help="Skip thumbnail image processing")
    export_parser.add_argument("--no-video", action="store_true", help="Strip video streams from exported tracks")
    export_parser.add_argument(
        "--legacy-mp3",
        action="store_true",
        help="Enable strict legacy MP3 player mode (ASCII filenames, MP3 format, video stripped)",
    )
    export_parser.add_argument(
        "--max-img-dim",
        type=int,
        default=None,
        help="Maximum pixel dimension for cover art",
    )
    export_parser.add_argument(
        "--zip",
        action="store_true",
        help="Compress the exported directory into a ZIP archive",
    )

    # 'update' command
    update_parser = subparsers.add_parser(
        "update", aliases=["sync", "up"], help="Update/Sync playlist"
    )
    update_parser.add_argument(
        "playlist", nargs="?", default=None, help="Optional name of playlist to update"
    )
    # Media Controls
    update_parser.add_argument("--meta-only", action="store_true", help="Only process manifest metadata; do not download audio/video files")
    update_parser.add_argument("--no-thumb", action="store_true", help="Skip embedding thumbnails/artwork into downloaded files")
    update_parser.add_argument("--retry-dead", action="store_true", help="Ignore 'dead link' flags in manifests and retry fetching them anyway")

    # Network & Engine Behavior
    update_parser.add_argument("--offline", action="store_true", help="Do not download or fetch anything online")
    update_parser.add_argument(
        "--concurrency", "-j", type=int, default=config.DEFAULT_CONCURRENT_DOWNLOADS, help="Parallel downloads"
    )

    clear_fail = subparsers.add_parser("clear-fail", help="Set songs in a playlist to 'active'")
    clear_fail.add_argument("playlist_name", help="Name of the playlist")
    clear_fail.add_argument(
        "song_name",
        nargs="?",
        help="Name of the song to set active",
    )
    clear_fail.add_argument(
        "--all",
        action="store_true",
        help="Set all songs in the playlist to active",
    )

    parser_update_self = subparsers.add_parser(
        "update-self", 
        help="Pull the latest code from GitHub and update Python dependencies"
    )

    config_parser = subparsers.add_parser(
        "config",
        help="View or set the preferred playlist manifest format",
    )
    config_parser.add_argument(
        "manifest_format",
        nargs="?",
        choices=["json", "yaml"],
        help="Preferred format for new manifests",
    )

    open_parser = subparsers.add_parser(
        "open", help="Open the program or a playlist folder in the file manager"
    )
    open_parser.add_argument(
        "target",
        help="'self' for the program folder, or a playlist name",
    )

    subparsers.add_parser(
        "backup", help="Back up all playlist manifests to a ZIP archive"
    )

    restore_parser = subparsers.add_parser(
        "restore", help="Restore playlist manifests from a backup ZIP archive"
    )
    restore_parser.add_argument("backup_file", help="Path to a manifest backup ZIP file")

    return parser

def main() -> int:
    parser = create_parser()
    args = parser.parse_args()

    # Route commands using lists to catch all aliases
    if args.command in ["ls", "list", "dir"]:
        if args.playlist:
            playlist_orchestrator.cmd_list_playlist(args.playlist)
        else:
            playlist_orchestrator.cmd_list_all()

    elif args.command in ["new", "create", "make"]:
        playlist_orchestrator.cmd_new_playlist(args.playlist_name, args.manifest_format)

    elif args.command in ["add", "append"]:
        import_orchestrator.add_songs(args.playlist, args.urls)

    elif args.command in ["import", "ingest", "fetch"]:
        import_orchestrator.import_playlist(
            args.source, args.playlist_name, args.manifest_format
        )

    elif args.command in ["rm", "remove", "del", "delete"]:
        playlist_orchestrator.cmd_remove_playlist(args.playlist_name)

    elif args.command in ["mv", "rename", "move"]:
        playlist_orchestrator.cmd_rename_playlist(args.old_name, args.new_name)

    elif args.command == "export":
        export_orchestrator.export_playlist(
            playlist_name=args.playlist,
            output_dir=args.output,
            target_format=args.format,
            no_thumb=args.no_thumb,
            no_video=args.no_video,
            legacy_mp3_mode=args.legacy_mp3,
            max_img_dim=args.max_img_dim,
            zip_output=args.zip,
        )

    elif args.command == "clear-fail":
        if args.song_name and args.all:
            parser.error("clear-fail requires either SONG_NAME or --all, not both")

        if not args.song_name and not args.all:
            parser.error("clear-fail requires either SONG_NAME or --all")

        if args.all:
            playlist_orchestrator.cmd_clear_fail(args.playlist_name, all_songs=True)
        else:
            playlist_orchestrator.cmd_clear_fail(
                args.playlist_name,
                song_name=args.song_name,
            )
        
    elif args.command == "update-self":
        return 0 if update_code.update_application() else 1

    elif args.command == "config":
        playlist_orchestrator.cmd_config_manifest_format(args.manifest_format)

    elif args.command == "open":
        playlist_orchestrator.cmd_open(args.target)

    elif args.command == "backup":
        backup_orchestrator.cmd_backup()

    elif args.command == "restore":
        backup_orchestrator.cmd_restore(args.backup_file)

    elif args.command in ["update", "sync", "up"]:
        update_opts = vars(args).copy()
        playlist = update_opts.pop("playlist")
        update_opts.pop("command")
        
        if playlist:
            update_orchestrator.cmd_update_playlist(playlist, **update_opts)
        else:
            update_orchestrator.cmd_update_all(**update_opts)

    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130) from None