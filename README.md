# pl-dlp

> ⚠️ **Work in Progress**
> This project is currently in active development. Installer scripts have **not** been heavily tested on **Linux or Windows**. Expect edge cases or potential environment bugs. Manual setup instructions are provided below as a fallback.

`pl-dlp` is a CLI music and playlist manager built on top of `yt-dlp` and `mutagen`. It allows you to organize tracks in JSON or YAML playlist manifests, sync media files based on those manifests, write metadata directly into M4A files, and export playlists as MP3 intended for older hardware. The application configuration remains JSON.

## Key Components

* **JSON and YAML playlist manifests:** songs and download metadata can be stored in JSON (`.json`) or YAML (`.yaml`/`.yml`) files. Existing manifests retain their original format when updated.

* **Multi-Threaded Downloader:** Parallel downloading and processing engine displayed with `rich` progress bars.

* **Embedded Metadata:** Native M4A/MP4 tagging using `mutagen`, including embedded thumbnail cover art.

* **Exporter:** Export playlists into standard formats (`mp3`, `m4a`, `flac`, `wav`), have the option to strip video channels, re-size artwork, or package them directly into ZIP archives.

* **MP3 Player Support:** Exporting using `--legacy-mp3` mode to strip unsafe ASCII characters, removing video streams, and embedding ID3v2.3 cover art.

### Example manifests

The [`musicDir` examples](./musicDir) include both supported manifest formats:

* [`myplaylist.json`](./musicDir/pl-myplaylist/myplaylist.json) shows per-track video download selection and `dont_override` for protecting hand-edited title, artist, and composer fields.
* [`otherplaylist.yaml`](./musicDir/pl-otherplaylist/otherplaylist.yaml) shows the same manifest structure in YAML, including one video track and a track whose title and artist are protected from metadata updates.

`download_video_all: true` forces video downloads for every track in that playlist. Otherwise, set `download_video: true` only on tracks that should download as video. `status` is managed by the sync process; use `active` for tracks ready to sync.

## Installation

> **Note on Compatibility:** The automated installer scripts are functional, but they lack testing across different environments. If you encounter issues, follow the manual installation steps below.

### Automated Installation

`pl-dlp` includes interactive installation scripts designed to automatically check Python dependencies, install system requirements, create standard configuration directories, and place the executable on your system `PATH`.

#### **On Linux (Ubuntu / Debian / Arch):**
Run `install.sh` with standard permissions. It will attempt to detect your system package manager (`apt` or `pacman`), install missing dependencies, copy application files, and place a launcher script in `~/.local/bin`

```bash
chmod +x install.sh
./install.sh
```
#### **On Windows:**

Run `installer.ps1` via PowerShell. It verifies Python 3.10+ installation (offering to install Python 3.12 via `winget` if missing), copies project files, and appends `pl-dlp` to your User `PATH` environment variable.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1
```

### Manual Installation

If you prefer to set up `pl-dlp` manually or if the installer scripts fail:

#### 1. System Dependencies

Ensure **Python 3.10+** and **FFmpeg** are installed and added to your system `PATH`.

* **Linux (Ubuntu/Debian):** `sudo apt update && sudo apt install python3 python3-pip ffmpeg`

* **Linux (Arch):** `sudo pacman -S python python-pip ffmpeg`

* **Windows:** Install Python via [python.org](https://www.python.org/) (ensure "Add Python to PATH" is checked) and download `ffmpeg` manually or via `winget install Gyan.FFmpeg`.

#### 2. Clone the Repository

```bash
git clone https://github.com/Iron-Smithy/PL-DLP
cd PL-DLP
```

#### 3. Install Python Package Dependencies

Install the required Python modules:

```bash
pip install yt-dlp mutagen Pillow rich PyYAML
```

(Note: If using Linux with an externally managed environment, you may need to add `--break-system-packages` or use a Python virtual environment).

#### 4. Setup Configuration (`config.json`)

Create a file named `config.json` inside your project directory to define where your media files and source code live:

```json
{
    "music_root": "/path/to/your/Music/pl-dlp",
    "project_root": "/path/to/your/pl-dlp",
    "manifest_format": "json"
}

```

#### 5. Make `pl-dlp` Globally Accessible (Optional)

* **Linux:** Create a wrapper script in `/usr/local/bin/pl-dlp`:

```bash
sudo bash -c 'cat <<EOF> /usr/local/bin/pl-dlp
#!/bin/sh
exec python3 "/path/to/your/pl-dlp/main.py" "\$@"
EOF'
sudo chmod +x /usr/local/bin/pl-dlp

```

* **Windows:** Create a file named `pl-dlp.cmd` in your project folder:

```cmd
@echo off
python "C:\path\to\your\pl-dlp\main.py" %*

```

Then manually add the project folder to your User Environment `PATH`.

## CLI Command Overview & Examples

### 1. `ls` — List Playlists or Tracks

View summary statistics across all managed playlists, or inspect track states inside a specific playlist.

```bash
# List all playlists, total track count, and disk space
pl-dlp ls

# Show individual tracks and download statuses for a playlist
pl-dlp ls pl-rock

```

### 2. `import` — Ingest Playlists or Links

Create a playlist manifest by scraping a YouTube playlist URL or parsing a local `.txt`/`.json` file containing YouTube URLs. New manifests use the `manifest_format` setting in `config.json` (`json` by default); choose `yaml` for YAML. A per-command `--manifest-format json|yaml` overrides the setting when creating a manifest. Existing playlist manifests keep their current type regardless of the override.

```bash
# Scrape a YouTube playlist URL
pl-dlp import "https://www.youtube.com/playlist?list=..." my-playlist

# Create a YAML manifest for a new playlist
pl-dlp new my-playlist --manifest-format yaml

# Import a playlist and choose the new manifest format
pl-dlp import "https://www.youtube.com/playlist?list=..." my-playlist --manifest-format yaml

# Parse a local text file containing YouTube links
pl-dlp import links.txt custom-playlist

```

### 3. `add` — Append Links to an Existing Playlist

Append single or multiple YouTube track URLs (or a file of URLs) to an existing manifest.

```bash
pl-dlp add pl-rock "https://www.youtube.com/watch?v=XXXXXX"

```

### 4. `update` — Synchronize Local Tracks & Metadata

Runs the sync engine to download missing media files and apply embedded metadata.
Media files not represented by the manifest, and playlists removed with the CLI,
are moved to `.trash_bin` rather than deleted. The trash and backup folders are
created as needed.

```bash
# Sync all existing playlists using 4 concurrent workers
pl-dlp update -j 4

# Sync a specific playlist without downloading cover art
pl-dlp update pl-rock --no-thumb

# Refresh metadata JSON without downloading media files
pl-dlp update pl-rock --meta-only

# Force retry fetching tracks previously marked as "DEAD"
pl-dlp update pl-rock --retry-dead

```

### 5. `config` — View or Set Preferences

View the preferred format for new playlist manifests, or change it. When the setting is missing, running `pl-dlp config` asks you to choose; installations and self-updates also ask before saving a missing preference.

```bash
# Show the current setting (prompts if missing)
pl-dlp config

# Set the default format for new manifests
pl-dlp config yaml
pl-dlp config json
```

### 6. `open` — Open a Folder in the File Manager

Open the installed source folder or a playlist folder using the operating system's standard graphical folder opener.

```bash
# Open the pl-dlp source folder
pl-dlp open self

# Open a playlist folder
pl-dlp open my-playlist
```

On Linux this uses `xdg-open`; a graphical desktop session is required. If the file manager cannot be launched, pl-dlp reports the error.

### 7. `export` — Format and Package Media

Convert and move files out of `pl-dlp` into custom locations or older devices.

```bash
# Export playlist as standard MP3s to a destination folder
pl-dlp export pl-rock -o ~/Desktop/CarSDCard -f mp3

# Legacy mode (ASCII filenames, MP3 format, video stripped, capped thumbnails)
pl-dlp export pl-rock -o ~/Desktop/OldPlayer --legacy-mp3

# Export and compress directly into a ZIP file
pl-dlp export pl-rock -o ./out --zip

```

### 8. `clear-fail` — Reset Error States

Reset track statuses that were marked as failed or broken back to `active`.

```bash
# Reset a single track by title
pl-dlp clear-fail pl-rock "Song Title"

# Reset all failed tracks inside a playlist
pl-dlp clear-fail pl-rock --all

```

### 9. `backup` and `restore` — Back Up or Restore Manifests

Create a ZIP archive containing every JSON/YAML playlist manifest, or restore
those files from an archive. Backups are saved under `.backup_bin` in the configured
music root. Restoring asks for confirmation if any manifest will be overwritten.

```bash
# Create a timestamped backup
pl-dlp backup

# Restore manifests from a backup archive
pl-dlp restore ~/Music/pl-dlp/.backup_bin/20261107_193000_000000.zip
```

## Troubleshooting & Built-in Help

The built-in argparse help menus can be accessed on any command by passing `-h` or `--help`:

```bash
pl-dlp --help
pl-dlp update --help
pl-dlp export --help

```

## Updating pl-dlp

Keep `pl-dlp` up to date with the latest features and `yt-dlp` fixes:

```bash
pl-dlp update-self
```

The self-updater preserves your `config.json` and resolves file/folder name
conflicts left by older layouts, such as a legacy `orchestrator.py` beside the
current `orchestrator` folder. If an older installed version fails before it
can run `update-self`, remove that conflicting legacy file once, then update:

```powershell
Remove-Item "$env:LOCALAPPDATA\pl-dlp_src\orchestrator.py"
python "$env:LOCALAPPDATA\pl-dlp_src\main.py" update-self
```