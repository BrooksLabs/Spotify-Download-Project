#!/usr/bin/env python3
"""
Spotify Downloader Guide with spotDL
====================================

A beginner-friendly Python script that walks users through installing and using
spotDL to download Spotify playlists/albums/tracks as tagged MP3 files.

GitHub project idea: A documented, interactive onboarding script for spotDL users.

Features:
- Step-by-step terminal instructions
- Automatic checks (Python version, pip, spotdl presence)
- Runs safe installation / ffmpeg download commands
- Helps with folder navigation and command generation
- Explains resume behavior for large libraries

Usage:
    python spotify_downloader_guide.py

Requirements: Just Python 3.7+ to run this guide script itself.
spotDL and FFmpeg will be installed during the process if missing.
"""

import sys
import os
import subprocess
import shutil
from pathlib import Path


def print_header(text: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {text.upper()}")
    print("=" * 70 + "\n")


def run_command(cmd: list[str], check: bool = True, capture_output: bool = False) -> subprocess.CompletedProcess:
    """Helper to run shell commands with nice feedback"""
    print(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, check=check, capture_output=capture_output, text=True)
        if capture_output:
            print(result.stdout.strip())
        return result
    except subprocess.CalledProcessError as e:
        print(f"Command failed with exit code {e.returncode}")
        print(e.stderr or "No error output captured.")
        raise


def check_python_version() -> None:
    if sys.version_info < (3, 7):
        print("Error: Python 3.7 or newer is required.")
        print(f"You are running: {sys.version}")
        sys.exit(1)
    print(f"Python version OK: {sys.version.split()[0]}")


def is_spotdl_installed() -> bool:
    return shutil.which("spotdl") is not None


def install_spotdl() -> None:
    print_header("PHASE 1: Installing spotDL")
    print("Installing spotDL via pip...\n")

    pip_cmd = ["pip3"] if sys.platform.startswith("darwin") else ["pip"]
    try:
        run_command([*pip_cmd, "install", "--upgrade", "pip"], check=False)
        run_command([*pip_cmd, "install", "spotdl"])
        print("\nspotDL installed successfully!")
    except Exception as e:
        print(f"Installation failed: {e}")
        print("\nTry running manually:")
        print("  pip install spotdl   # or pip3 install spotdl on Mac")
        sys.exit(1)


def download_ffmpeg() -> None:
    if not is_spotdl_installed():
        print("spotDL not found — install it first.")
        return

    print_header("Installing FFmpeg (required for audio conversion)")
    print("spotDL can download FFmpeg automatically...\n")
    try:
        run_command(["spotdl", "--download-ffmpeg"])
        print("\nFFmpeg setup complete!")
    except Exception as e:
        print(f"Auto-download failed: {e}")
        print("\nManual FFmpeg installation options:")
        print("• Windows: https://ffmpeg.org/download.html → add to PATH")
        print("• Mac:    brew install ffmpeg   (if you have Homebrew)")
        print("• Linux:  sudo apt install ffmpeg   (or equivalent)")


def create_music_folder() -> Path:
    print_header("PHASE 2: Preparing your music folder")
    default_name = "Spotify Library"
    folder_name = input(f"Enter folder name [{default_name}]: ").strip() or default_name

    home = Path.home()
    suggestions = [
        home / "Music" / folder_name,
        home / "Downloads" / folder_name,
        Path.cwd() / folder_name,
    ]

    print("\nSuggested locations:")
    for i, p in enumerate(suggestions, 1):
        print(f"  {i}. {p}")

    choice = input("\nChoose number or enter full path: ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(suggestions):
        target = suggestions[int(choice) - 1]
    else:
        target = Path(choice).expanduser().resolve()

    target.mkdir(parents=True, exist_ok=True)
    print(f"\nMusic folder ready: {target}")
    return target


def guide_download(playlist_url: str | None = None, output_folder: Path | None = None) -> None:
    print_header("Downloading your Spotify content")
    if not playlist_url:
        print("1. Open Spotify → find playlist/album/track")
        print("2. Click ••• → Share → Copy link")
        playlist_url = input("\nPaste the Spotify link here: ").strip()

    if not output_folder:
        output_folder = Path.cwd()

    cmd = ["spotdl", playlist_url, "--output", str(output_folder), "--preload"]
    # --preload tries to speed up by pre-resolving matches

    print("\nWe will run this command (you can copy-paste it too):")
    print("  " + " ".join(cmd))
    print("\nFeatures:")
    print("• Downloads best-matching YouTube audio → MP3")
    print("• Embeds metadata, album art, lyrics (when available)")
    print("• Skips already downloaded files automatically")
    print("• Press Ctrl+C to pause — re-run same command to resume")

    input("\nPress Enter to start download (or Ctrl+C to skip)...")
    try:
        run_command(cmd)
    except KeyboardInterrupt:
        print("\nDownload paused. Re-run the same command to resume.")
    except Exception as e:
        print(f"\nDownload error: {e}")
        print("Tip: Make sure FFmpeg is installed and in PATH.")


def main() -> None:
    print_header("spotDL Interactive Setup Guide")
    print("Follow the steps below to download your Spotify music library.\n")

    check_python_version()

    if not is_spotdl_installed():
        install_choice = input("spotDL not found. Install now? [Y/n]: ").lower().strip()
        if install_choice in ("", "y", "yes"):
            install_spotdl()
        else:
            print("Skipping installation. Run 'pip install spotdl' manually.")
            return

    ffmpeg_choice = input("\nDownload FFmpeg now (recommended)? [Y/n]: ").lower().strip()
    if ffmpeg_choice in ("", "y", "yes"):
        download_ffmpeg()

    folder = create_music_folder()

    os.chdir(folder)  # So relative paths work nicely
    print(f"\nChanged directory to: {folder}")

    while True:
        print("\nWhat would you like to do?")
        print("  1. Download a playlist/album/track")
        print("  2. Show full spotDL help")
        print("  3. Quit")

        choice = input("\nEnter number: ").strip()

        if choice == "1":
            guide_download(output_folder=folder)
        elif choice == "2":
            if is_spotdl_installed():
                run_command(["spotdl", "--help"], capture_output=False)
            else:
                print("spotDL not installed yet.")
        elif choice in ("3", "q", "quit", "exit"):
            break
        else:
            print("Invalid choice.")

    print_header("All done!")
    print("Your music is saved in:", folder)
    print("\nPro tip — for future auto-sync of new songs:")
    print("  spotdl [playlist_url] sync   # experimental sync mode in newer versions")
    print("Or watch the repo: https://github.com/spotDL/spotify-downloader")
    print("Happy listening!\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExited by user. Come back anytime!")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        print("Feel free to open an issue on the GitHub repo.")