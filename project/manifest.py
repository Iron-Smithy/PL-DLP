import config

import json
from pathlib import Path

#temp, should come from main
import storage
playlist_dirs = storage.find_playlist_directories(config.PLAYLIST_ROOT)