import config
import downloader
import exporter
import manifest
import metadata
import storage
import ui
from pathlib import Path

def cmd_list_all():
    playlist_directories = storage.find_playlist_directories(config.MUSIC_ROOT)
    json_directories = storage.separate_json_manifest_paths(playlist_directories)
    playlist_songs_list: list[list[Path]] = storage.separate_music_paths(playlist_directories)

    names = []
    track_count = []
    tracks_downloaded = []
    total_sizes = []

    for i, json_path in enumerate(json_directories):
        json_data = manifest.load_json_manifest(json_path)

        songs = playlist_songs_list[i]

        size = sum(file.stat().st_size for file in songs) / (1024*1024)

        names.append(json_data.get("playlist_name", "-")) # !!! change to use the folder name not the json name
        track_count.append(json_data.get("total_tracks", "-"))
        tracks_downloaded.append(len(songs))
        total_sizes.append(size)

    ui.list_all(names, track_count, tracks_downloaded, total_sizes)

def cmd_list_playlist(playlist_name):
    playlist_name = storage.reason_playlist_true_name(playlist_name)

    playlist_path = storage.find_playlist_directory(
        config.MUSIC_ROOT,
        playlist_name
    )

    if not playlist_path:
        print(f"The playlist {playlist_name} cannot be found")
        exit(1)

    json_path = storage.separate_json_manifest_paths(playlist_path)[0]
    json_data = manifest.load_json_manifest(json_path)

    songs = json_data.get("songs", [])

    music_paths = storage.separate_music_paths(playlist_path)[0]
    downloaded_files = {file.name for file in music_paths}

    titles = []
    downloaded = []
    lengths = []
    sizes = []

    for song in songs:
        title = song["title"]

        file_name = f"{title}.m4a"
        file_exists = file_name in downloaded_files

        if file_exists:
            file_path = playlist_path / "music" / file_name

            length = storage.get_media_duration(file_path)
            size = file_path.stat().st_size / (1024 * 1024)
        else:
            length = song.get("length", "-")
            size = song.get("size", 0)

        titles.append(title)
        downloaded.append(file_exists)
        lengths.append(length)
        sizes.append(size)

    ui.list_one(
        playlist_name,
        titles,
        downloaded,
        lengths,
        sizes
    )