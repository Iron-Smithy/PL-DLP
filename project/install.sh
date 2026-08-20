#!/usr/bin/env bash

set -e

echo "========================================="
echo "      pl-dlp Linux System Installer     "
echo "========================================="

# Detect Package Manager and Auto-Install Missing Base Dependencies
if command -v pacman &> /dev/null; then
    echo "[Info] Arch Linux detected."
    sudo pacman -S --needed --noconfirm python python-pip ffmpeg
elif command -v apt &> /dev/null; then
    echo "[Info] Ubuntu/Debian detected."
    sudo apt update
    sudo apt install -y python3 python3-pip python3-venv ffmpeg
else
    echo "[Warning] Unknown Linux distribution. Ensure python3, pip, and ffmpeg are installed."
fi

# Verify Python Executable
PYTHON_BIN=""
if command -v python3 &> /dev/null; then
    PYTHON_BIN="python3"
elif command -v python &> /dev/null; then
    PYTHON_BIN="python"
fi

if [ -z "$PYTHON_BIN" ]; then
    echo "[ERROR] Python 3 binary could not be found."
    exit 1
fi

# Execute Core Python Installer
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
"$PYTHON_BIN" "$SCRIPT_DIR/setup.py"