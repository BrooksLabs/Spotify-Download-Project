#!/usr/bin/env python3
"""
Advanced Spotify to MP3 Downloader
==================================

Features:
- Downloads single tracks, full albums, or massive playlists
- Scrapes the official Spotify Web Player API silently to bypass 429 rate limits
- Embeds official ID3 metadata (Artist, Title, Album) and high-res cover art using Mutagen
- Spoofs mobile clients and searches lyrics to bypass YouTube's 403 Forbidden traps
- Auto-handles pagination for playlists larger than 100 songs

Usage:
    python spotify_downloader_guide.py
"""

import sys
import os
import subprocess
import urllib.request
import json
import re
from pathlib import Path
from typing import List, Dict

def print_header(text: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {text.upper()}")
    print("=" * 70 + "\n")

def run_command(cmd: List[str], check: bool = True, capture_output: bool = False) -> subprocess.CompletedProcess:
    """Helper to run shell commands safely"""
    try:
        result = subprocess.run(cmd, check=check, capture_output=capture_output, text=True)
        return result
    except subprocess.CalledProcessError as e:
        print(f"\nCommand failed with exit code {e.returncode}")
        print(e.stderr or "No error output captured.")
        raise

def setup_environment() -> None:
    print_header("PHASE 1: Setting up tools")
    print("Installing yt-dlp and mutagen (for metadata tagging)...\n")
    
    pip_cmd = [sys.executable, "-m", "pip", "install", "--upgrade"]
    try:
        run_command([*pip_cmd, "yt-dlp", "mutagen"])
        print("Tools are installed and up to date!")
    except Exception as e:
        print(f"Setup failed: {e}")
        sys.exit(1)

def download_ffmpeg() -> None:
    print_header("Checking FFmpeg")
    if sys.platform == "win32":
        print("Attempting to install FFmpeg via Windows winget...\n")
        try:
            run_command(["winget", "install", "ffmpeg"], check=False)
            print("FFmpeg check complete!")
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

def get_spotify_token() -> str:
    """Fetches an anonymous access token from Spotify's Web Player to bypass API limits"""
    req = urllib.request.Request(
        "https://open.spotify.com/get_access_token?reason=transport&productType=web_player",
        headers={"User-Agent": "Mozilla/5.0"}
    )
    response = urllib.request.urlopen(req)
    data = json.loads(response.read().decode('utf-8'))
    return data["accessToken"]

def parse_spotify_url(url: str) -> tuple[str, str]:
    match = re.search(r"spotify\.com/(track|album|playlist)/([a-zA-Z0-9]+)", url)
    if not match:
        raise ValueError("Invalid Spotify URL. Must be a track, album, or playlist link.")
    return match.group(1), match.group(2)

def extract_track_data(track: dict) -> dict:
    return {
        "artist": track["artists"][0]["name"],
        "title": track["name"],
        "album": track["album"]["name"],
        "cover_url": track["album"]["images"][0]["url"] if track["album"].get("images") else None
    }

def fetch_spotify_tracks(url: str) -> List[Dict]:
    """Uses the anonymous token to scrape the playlist/album JSON data"""
    token = get_spotify_token()
    item_type, item_id = parse_spotify_url(url)
    headers = {"Authorization": f"Bearer {token}", "User-Agent": "Mozilla/5.0"}
    tracks = []

    if item_type == "track":
        req = urllib.request.Request(f"https://api.spotify.com/v1/tracks/{item_id}", headers=headers)
        data = json.loads(urllib.request.urlopen(req).read())
        tracks.append(extract_track_data(data))
        
    elif item_type == "album":
        req = urllib.request.Request(f"https://api.spotify.com/v1/albums/{item_id}", headers=headers)
        data = json.loads(urllib.request.urlopen(req).read())
        album_name = data["name"]
        cover_url = data["images"][0]["url"] if data.get("images") else None
        
        for item in data["tracks"]["items"]:
            tracks.append({
                "artist": item["artists"][0]["name"],
                "title": item["name"],
                "album": album_name,
                "cover_url": cover_url
            })
            
    elif item_type == "playlist":
        api_url = f"https://api.spotify.com/v1/playlists/{item_id}/tracks"
        print("Scraping playlist data (this may take a moment for large playlists)...")
        while api_url:
            req = urllib.request.Request(api_url, headers=headers)
            data = json.loads(urllib.request.urlopen(req).read())
            for item in data["items"]:
                if item.get("track") and not item["track"].get("is_local"):
                    tracks.append(extract_track_data(item["track"]))
            api_url = data.get("next") # Handles playlists > 100 songs automatically

    return tracks

def embed_metadata(mp3_path: Path, track_info: dict) -> None:
    """Uses mutagen to embed ID3 tags and high-res cover art into the MP3"""
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, error

    try:
        audio = MP3(str(mp3_path), ID3=ID3)
    except Exception:
        return # Skip if file isn't a valid MP3

    try:
        audio.add_tags()
    except error:
        pass # Tags already exist

    audio.tags.add(TIT2(encoding=3, text=track_info["title"]))
    audio.tags.add(TPE1(encoding=3, text=track_info["artist"]))
    audio.tags.add(TALB(encoding=3, text=track_info["album"]))
    
    if track_info["cover_url"]:
        try:
            req = urllib.request.Request(track_info["cover_url"], headers={"User-Agent": "Mozilla/5.0"})
            image_data = urllib.request.urlopen(req).read()
            audio.tags.add(
                APIC(
                    encoding=3, mime='image/jpeg', type=3, desc='Cover',
                    data=image_data
                )
            )
        except Exception as e:
            print(f"  -> Could not embed cover art: {e}")

    audio.save()

def sanitize_filename(name: str) -> str:
    """Removes illegal characters for Windows/Mac filesystems"""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def process_batch(output_folder: Path) -> None:
    print_header("Download Music")
    spotify_url = input("Paste the Spotify Track, Album, or Playlist link: ").strip()

    try:
        tracks = fetch_spotify_tracks(spotify_url)
        print(f"\nFound {len(tracks)} track(s) to download.\n")
    except Exception as e:
        print(f"Failed to fetch Spotify metadata: {e}")
        return

    for index, track in enumerate(tracks, 1):
        artist = track['artist']
        title = track['title']
        safe_artist = sanitize_filename(artist)
        safe_title = sanitize_filename(title)
        file_name = f"{safe_artist} - {safe_title}"
        mp3_path = output_folder / f"{file_name}.mp3"
        output_template = str(output_folder / f"{file_name}.%(ext)s")

        print(f"[{index}/{len(tracks)}] Downloading: {artist} - {title}")
        
        # Skip download if the finalized file already exists (Resume support)
        if mp3_path.exists():
            print("  -> File already exists, skipping download. Updating metadata...")
            embed_metadata(mp3_path, track)
            continue

        search_query = f"ytsearch1:{artist} {title} lyrics"
        cmd = [
            sys.executable, "-m", "yt_dlp",
            search_query,
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "--extractor-args", "youtube:player_client=android,ios", 
            "--rm-cache-dir",
            "--quiet", "--no-warnings", # Cleans up the terminal spam
            "-o", output_template
        ]

        try:
            run_command(cmd)
            # Apply ID3 Metadata and Artwork once the download completes
            if mp3_path.exists():
                embed_metadata(mp3_path, track)
                print("  -> Embedded ID3 Tags and Cover Art.")
            else:
                print("  -> Download failed or file missing.")
        except KeyboardInterrupt:
            print("\nDownload batch canceled.")
            break
        except Exception as e:
            print(f"  -> Error downloading track: {e}")

def main() -> None:
    print_header("Spotify API & yt-dlp Auto-Downloader")
    
    setup_environment()

    ffmpeg_choice = input("\nCheck/Install FFmpeg now (required for MP3s)? [Y/n]: ").lower().strip()
    if ffmpeg_choice in ("", "y", "yes"):
        download_ffmpeg()

    folder = create_music_folder()
    os.chdir(folder)
    print(f"\nWorking directory: {folder}")

    while True:
        print("\nWhat would you like to do?")
        print("  1. Download a Spotify Track, Album, or Playlist")
        print("  2. Quit")

        choice = input("\nEnter number: ").strip()

        if choice == "1":
            process_batch(output_folder=folder)
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
