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

        song_paths = playlist_songs_list[i]

        size = storage.get_directory_size(song_paths)

        names.append(playlist_directories[i].name or json_data.get("playlist_name", config.JSON_FALLBACK_CHAR))
        track_count.append(json_data.get("total_tracks", config.JSON_FALLBACK_CHAR))
        tracks_downloaded.append(len(song_paths))
        total_sizes.append(size)

    ui.list_all(names, track_count, tracks_downloaded, total_sizes)

def cmd_list_playlist(playlist_name: str):
    playlist_name = storage.clean_name(playlist_name)

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
            size = storage.get_file_size(file_path)
        else:
            length = song.get("length", config.JSON_FALLBACK_CHAR)
            size = 0

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

def cmd_new_playlist(playlist_name: str):
    playlist_name = (playlist_name or "new-playlist").strip()

    potential_file = Path(playlist_name).expanduser().resolve(strict=False)

    if potential_file.is_file() and potential_file.suffix.lower() == ".json":
        playlist_name = storage.clean_name(potential_file.stem)
        new_dir = config.MUSIC_ROOT / playlist_name
        
        if new_dir.exists():
            raise ValueError(f"Error: Folder {playlist_name} already exists")
            
        storage.make_directory(new_dir, parents=True)
        storage.make_directory(new_dir / "Music")
        
        target_json = new_dir / f"{playlist_name.removeprefix("pl-")}.json" # !!! make another storage function. like clean name but removes the pl-
        storage.move(str(potential_file), str(target_json))
        
        print(f"NEW (Adopted): Created {playlist_name} from {potential_file.name}")
        return

    # use final path segment so ./pl-x and pl-x are the same token
    name = storage.clean_name(Path(playlist_name).expanduser().name)
    path = config.MUSIC_ROOT / name
    if path.exists():
        raise ValueError(f"Error: {name} already exists.")
        return
        
    storage.make_directory(path)
    storage.make_directory(path / "Music")
    storage.make_file(path / f"{name.removeprefix("pl-")}.json") # !!! make another storage function. like clean name but removes the pl-
    
    print(f"NEW: Created empty playlist '{name}'")