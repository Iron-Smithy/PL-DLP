import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import config

MIN_PYTHON = (3, 10)

def verify_python_version(python_exe: str) -> bool:
    """Checks if a given Python executable meets minimum version requirements."""
    try:
        res = subprocess.run(
            [python_exe, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
            capture_output=True,
            text=True,
            check=True
        )
        major, minor = map(int, res.stdout.strip().split("."))
        return (major, minor) >= MIN_PYTHON
    except Exception:
        return False

def prompt_directory(prompt_msg: str, default_path: Path) -> Path:
    user_val = input(f"{prompt_msg} [Default: {default_path}]: ").strip()
    target = Path(user_val) if user_val else default_path
    target.mkdir(parents=True, exist_ok=True)
    return target.resolve()

def main():
    print("=" * 50)
    print("           pl-dlp System Installer")
    print("=" * 50)

    python_exe = sys.executable

    # Validate Active Python Executable
    if not verify_python_version(python_exe):
        print(f"\n[Error] Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required.")
        print(f"Current executable ({python_exe}) is incompatible.")
        custom_path = input("Enter full path to a valid python.exe/binary (or press Enter to exit): ").strip()
        if custom_path and verify_python_version(custom_path):
            python_exe = custom_path
        else:
            sys.exit("Installation aborted: Suitable Python interpreter not found.")

    # Collect Paths from User with Sensible Defaults
    if os.name == "nt":
        default_prog = Path.home() / "AppData" / "Local"
        default_music = Path.home() / "Music" / "pl-dlp"
    else:
        default_prog = Path.home() / ".local" / "share"
        default_music = Path.home() / "Music" / "pl-dlp"

    print("\nDirectory Configuration")
    music_root = prompt_directory("Where should music and playlists be stored?", default_music)
    prog_base = prompt_directory("Where should pl-dlp program files live?", default_prog)
    manifest_format = config.prompt_manifest_format()
    
    project_root = prog_base / "pl-dlp_src"
    project_root.mkdir(parents=True, exist_ok=True)

    # Copy Application Source Code to PROJECT_ROOT
    current_source_dir = Path(__file__).parent.resolve()
    print(f"\nCopying project files to {project_root}...")
    for item in current_source_dir.glob("*"):
        if item.name in [".git", "__pycache__", ".venv", "exports"]:
            continue
        dest = project_root / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)

    # Generate Machine-Readable config.json
    config_payload = {
        "music_root": str(music_root),
        "project_root": str(project_root),
        "manifest_format": manifest_format
    }
    config_file = project_root / "config.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config_payload, f, indent=4)
    print(f"[Success] Generated config at {config_file}")

    # Verify or Install Python Dependencies
    print("\nChecking Python dependencies...")
    
    # Map import names to pip package names
    module_to_pip = {
        "yt_dlp": "yt-dlp",
        "mutagen": "mutagen",
        "PIL": "Pillow",
        "rich": "rich",
        "yaml": "PyYAML"
    }

    missing_modules = []

    for mod in module_to_pip.keys():
        try:
            __import__(mod)
        except ImportError:
            missing_modules.append(mod)

    if not missing_modules:
        print("[Success] All required dependencies are already installed!")
    else:
        # Determine exact missing pip package names
        missing_pip_packages = [module_to_pip[m] for m in missing_modules]
        print(f"[Info] Missing modules: {', '.join(missing_modules)}")
        print(f"[Info] Attempting standard pip install for: {', '.join(missing_pip_packages)}...")
        
        try:
            # Try standard pip install first
            subprocess.run([python_exe, "-m", "pip", "install"] + missing_pip_packages, check=True)
            print("[Success] Dependencies installed via pip.")
        except subprocess.CalledProcessError:
            print("\n[Warning] Standard pip install failed (your OS uses an externally managed environment).")
            print("To install directly via pip, Python requires the '--break-system-packages' flag.")
            
            user_choice = input("Would you like to install using '--break-system-packages'? (y/N): ").strip().lower()
            
            if user_choice in ["y", "yes"]:
                try:
                    subprocess.run(
                        [python_exe, "-m", "pip", "install"] + missing_pip_packages + ["--break-system-packages"],
                        check=True
                    )
                    print("[Success] Dependencies installed via pip.")
                except subprocess.CalledProcessError as e:
                    print(f"[Error] Failed to install packages via pip: {e}")
            else:
                print("\n[Notice] Skipping pip installation.")
                print("Please install the missing dependencies manually using your system package manager:")
                print(f"  Missing Packages: {', '.join(missing_pip_packages)}")

    # Global Command Setup
    print("\n***REMOVED*** Creating Global Executable Launcher ***REMOVED***")
    main_script = project_root / "main.py"

    if os.name == "nt":  # Windows Wrapper
        cmd_wrapper = project_root / "pl-dlp.cmd"
        cmd_content = f'@echo off\n"{python_exe}" "{main_script}" %*\n'
        cmd_wrapper.write_text(cmd_content, encoding="utf-8")
        print(f"[Created] {cmd_wrapper}")

        # Update Windows User PATH Variable
        try:
            reg_query = subprocess.run(
                ["reg", "query", "HKCU\\Environment", "/v", "Path"],
                capture_output=True, text=True
            )
            current_path = ""
            if reg_query.returncode == 0:
                for line in reg_query.stdout.splitlines():
                    if "Path" in line:
                        current_path = line.split("REG_SZ")[-1].strip()

            if str(project_root) not in current_path:
                new_path = f"{current_path};{project_root}" if current_path else str(project_root)
                subprocess.run(
                    ["setx", "Path", new_path],
                    check=True, stdout=subprocess.DEVNULL
                )
                print(f"[Success] Added '{project_root}' to User PATH environment variable.")
            else:
                print(f"[Info] '{project_root}' is already present in PATH.")
        except Exception as e:
            print(f"[Notice] Could not modify PATH automatically: {e}")
            print(f"Manually add '{project_root}' to your System PATH variable.")

    else:  # Linux (Ubuntu / Arch Wrapper)
        linux_bin = Path("/usr/local/bin/pl-dlp")
        sh_script = f'#!/bin/sh\nexec "{python_exe}" "{main_script}" "$@"\n'
        
        try:
            linux_bin.write_text(sh_script, encoding="utf-8")
            linux_bin.chmod(0o755)
            print(f"[Success] Created executable symlink at {linux_bin}")
        except PermissionError:
            user_bin = Path.home() / ".local" / "bin"
            user_bin.mkdir(parents=True, exist_ok=True)
            local_launcher = user_bin / "pl-dlp"
            local_launcher.write_text(sh_script, encoding="utf-8")
            local_launcher.chmod(0o755)
            print(f"[Success] Created launcher at {local_launcher}")
            print(f"Ensure '{user_bin}' is in your $PATH.")

    print("\n" + "=" * 50)
    print("Installation Complete!")
    print("Restart your terminal session to run 'pl-dlp' from anywhere.")
    print("=" * 50)

if __name__ == "__main__":
    main()