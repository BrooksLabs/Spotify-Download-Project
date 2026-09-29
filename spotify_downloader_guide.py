#!/usr/bin/env python3
"""
Bulletproof Spotify to MP3 Downloader
=====================================

A robust Python script that takes a Spotify track link, scrapes the metadata, 
and uses yt-dlp to download the audio as an MP3. 

It is specifically engineered to bypass YouTube's 403 Forbidden errors, 
avoid official copyright/VEVO channels, and prevent Windows CMD pathing issues.

Usage:
    python spotify_downloader_guide.py
"""

import sys
import os
import subprocess
import urllib.request
import re
from pathlib import Path
from typing import List, Optional


def print_header(text: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {text.upper()}")
    print("=" * 70 + "\n")


def run_command(cmd: List[str], check: bool = True, capture_output: bool = False) -> subprocess.CompletedProcess:
    """Helper to run shell commands safely"""
    print(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, check=check, capture_output=capture_output, text=True)
        if capture_output:
            print(result.stdout.strip())
        return result
    except subprocess.CalledProcessError as e:
        print(f"\nCommand failed with exit code {e.returncode}")
        print(e.stderr or "No error output captured.")
        raise


def setup_environment() -> None:
    print_header("PHASE 1: Setting up tools")
    print("Ensuring yt-dlp is installed and fully updated...\n")
    
    # Use current python executable to avoid CMD PATH issues
    pip_cmd = [sys.executable, "-m", "pip", "install", "--upgrade"]
    
    try:
        # Install/Upgrade yt-dlp
        run_command([*pip_cmd, "yt-dlp"])
        print("\nyt-dlp is up to date!")
    except Exception as e:
        print(f"Setup failed: {e}")
        sys.exit(1)


def download_ffmpeg() -> None:
    print_header("Checking FFmpeg")
    
    if sys.platform == "win32":
        print("Attempting to install FFmpeg via Windows winget...\n")
        try:
            run_command(["winget", "install", "ffmpeg"], check=False)
            print("\nFFmpeg check complete!")
        except Exception:
            print("\nPlease install FFmpeg manually: https://ffmpeg.org/download.html")
    else:
        print("Please ensure FFmpeg is installed via your package manager (brew, apt, etc).")


def create_music_folder() -> Path:
    print_header("PHASE 2: Preparing your music folder")
    default_name = "Music Library"
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


def extract_spotify_metadata(url: str) -> tuple[str, str]:
    """Scrapes public Spotify page to get Artist and Song without API keys"""
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    html = urllib.request.urlopen(req).read().decode('utf-8')
    
    title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
    if not title_match:
        raise ValueError("Could not find track metadata on the page.")
        
    raw_title = title_match.group(1).replace(' | Spotify', '')
    
    if ' - song and lyrics by ' in raw_title:
        song, artist = raw_title.split(' - song and lyrics by ', 1)
    elif ' - song by ' in raw_title:
        song, artist = raw_title.split(' - song by ', 1)
    elif ' - Single by ' in raw_title:
        song, artist = raw_title.split(' - Single by ', 1)
    else:
        parts = raw_title.rsplit(' - ', 1)
        if len(parts) == 2:
            song, artist = parts[0], parts[1]
        else:
            song, artist = raw_title, "Unknown Artist"
            
    return artist.strip(), song.strip()


def guide_download(output_folder: Path) -> None:
    print_header("Download Track")
    
    spotify_url = input("Paste the Spotify track link here: ").strip()

    if not spotify_url or "spotify.com/track/" not in spotify_url:
        print("\nError: Please provide a valid Spotify track link.")
        return

    print("\nFetching metadata from Spotify...")
    try:
        artist, song = extract_spotify_metadata(spotify_url)
        print(f"Found Artist: {artist}")
        print(f"Found Song:   {song}\n")
    except Exception as e:
        print(f"Error extracting metadata: {e}")
        print("Tip: Make sure you copied a 'Track' link, not a Playlist or Album.")
        return

    # Strip illegal characters for Windows file names
    safe_artist = re.sub(r'[\\/*?:"<>|]', "", artist)
    safe_song = re.sub(r'[\\/*?:"<>|]', "", song)
    file_name = f"{safe_artist} - {safe_song}"
    
    output_template = str(output_folder / f"{file_name}.%(ext)s")
    
    # 1. Add "lyrics" to query to avoid official copyright/VEVO channels
    search_query = f"ytsearch1:{artist} {song} lyrics"

    # 2. Call yt_dlp via sys.executable to avoid CMD pathing roadblocks
    # 3. Use android/ios client spoofing to bypass 403 Forbidden roadblocks
    cmd = [
        sys.executable, "-m", "yt_dlp",
        search_query,
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "--extractor-args", "youtube:player_client=android,ios", 
        "--rm-cache-dir", 
        "-o", output_template
    ]

    print("Executing safe download protocol...\n")
    try:
        subprocess.run(cmd, check=True)
        print(f"\nSuccess! Saved as: '{file_name}.mp3'")
    except KeyboardInterrupt:
        print("\nDownload canceled.")
    except Exception as e:
        print(f"\nDownload error: {e}")
        print("Ensure FFmpeg is installed properly.")


def main() -> None:
    print_header("Bulletproof Audio Downloader")
    
    # Automatically install/update yt-dlp on launch
    setup_environment()

    ffmpeg_choice = input("\nCheck/Install FFmpeg now (required for MP3s)? [Y/n]: ").lower().strip()
    if ffmpeg_choice in ("", "y", "yes"):
        download_ffmpeg()

    folder = create_music_folder()
    os.chdir(folder)
    print(f"\nWorking directory: {folder}")

    while True:
        print("\nWhat would you like to do?")
        print("  1. Download a Spotify track")
        print("  2. Quit")

        choice = input("\nEnter number: ").strip()

        if choice == "1":
            guide_download(output_folder=folder)
        elif choice in ("2", "q", "quit", "exit"):
            break
        else:
            print("Invalid choice.")

    print_header("All done!")
    print(f"Your music is saved in: {folder}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExited by user. Come back anytime!")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
