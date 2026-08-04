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

        names.append(json_data.get("playlist_name", "-"))
        track_count.append(json_data.get("total_tracks", "-"))
        tracks_downloaded.append(len(songs))
        total_sizes.append(size)

    ui.list_all(names, track_count, tracks_downloaded, total_sizes)

def cmd_list_playlist():
    pass