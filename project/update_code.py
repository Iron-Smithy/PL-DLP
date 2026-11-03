import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

REPOSITORY = "Iron-Smithy/PL-DLP"
DEFAULT_BRANCH = "main"
PROJECT_DIR_NAME = "project"
FILES_TO_SKIP = {"config.json"}
DEPENDENCIES = ("yt-dlp", "mutagen", "Pillow", "rich", "PyYAML")

def _download_project(repository: str, branch: str, destination: Path) -> Path:
	archive_url = (
		f"https://github.com/{repository}/archive/refs/heads/{branch}.zip"
	)
	archive_path = destination / "source.zip"
	request = urllib.request.Request(
		archive_url,
		headers={"User-Agent": "pl-dlp-updater"},
	)

	with urllib.request.urlopen(request, timeout=60) as response:
		archive_path.write_bytes(response.read())

	extract_dir = destination / "source"
	with zipfile.ZipFile(archive_path) as archive:
		extract_dir.mkdir()
		for member in archive.infolist():
			member_path = (extract_dir / member.filename).resolve()
			if extract_dir.resolve() not in member_path.parents:
				raise RuntimeError("GitHub archive contains an unsafe path")
		archive.extractall(extract_dir)

	project_dirs = list(extract_dir.glob(f"*/{PROJECT_DIR_NAME}"))
	if len(project_dirs) != 1 or not (project_dirs[0] / "main.py").exists():
		raise RuntimeError(
			f"GitHub archive does not contain a valid root '{PROJECT_DIR_NAME}' folder"
		)
	return project_dirs[0]

def _copy_source(source_dir: Path, installed_dir: Path) -> int:
	updated_files = 0
	for source_path in source_dir.rglob("*"):
		if not source_path.is_file():
			continue

		relative_path = source_path.relative_to(source_dir)
		if relative_path.name in FILES_TO_SKIP or "__pycache__" in relative_path.parts:
			continue

		target_path = installed_dir / relative_path
		target_path.parent.mkdir(parents=True, exist_ok=True)
		shutil.copy2(source_path, target_path)
		updated_files += 1
	return updated_files

def _update_dependencies() -> None:
	command = [sys.executable, "-m", "pip", "install", "--upgrade", *DEPENDENCIES]
	subprocess.run(command, check=True)

def _ensure_manifest_format_config(installed_dir: Path) -> None:
	import config

	config_path = installed_dir / "config.json"
	user_config = config.read_user_config(config_path)
	if config.normalize_manifest_format(user_config.get("manifest_format")):
		return

	print("The preferred manifest format is not set in config.json.")
	manifest_format = config.prompt_manifest_format()
	config.write_user_config({"manifest_format": manifest_format}, config_path)
	print(f"Saved preferred manifest format: {manifest_format}")

def update_application(
	repository: str = REPOSITORY,
	branch: str = DEFAULT_BRANCH,
	installed_dir: Path | None = None,
) -> bool:
	"""Download and install the latest source without replacing local config."""
	target_dir = (installed_dir or Path(__file__).parent).resolve()
	print(f"Checking for updates from https://github.com/{repository}...")

	try:
		with tempfile.TemporaryDirectory(prefix="pl-dlp-update-") as temp_name:
			source_dir = _download_project(repository, branch, Path(temp_name))
			file_count = _copy_source(source_dir, target_dir)
			print(f"Updated {file_count} application files in {target_dir}")
			_update_dependencies()
			_ensure_manifest_format_config(target_dir)
	except (OSError, EOFError, ValueError, urllib.error.URLError, zipfile.BadZipFile, subprocess.CalledProcessError, RuntimeError) as error:
		print(f"[ERROR] Update failed: {error}", file=sys.stderr)
		return False

	print(f"Update completed at {datetime.now().isoformat(timespec='seconds')}")
	return True

if __name__ == "__main__":
	raise SystemExit(0 if update_application() else 1)