#!/usr/bin/env python3
"""
YouTube to MP3 Downloader (Full Metadata Edition)
=================================================

Features:
- Completely bypasses Spotify and its 403 firewall blocks.
- Uses the free iTunes API to fetch accurate, exhaustive ID3 data.
- Automatically grabs high-resolution (1000x1000) album artwork.
- Fills Title, Artist, Album, Year, Track, Genre, Comment, Album Artist, 
  Composer, Discnumber, and the ITUNESADVISORY (Explicit) tag.
- Downloads audio securely from YouTube using yt-dlp.
- Forces 320kbps MP3 encoding via FFmpeg.

Usage:
    python youtube_audio_downloader.py
"""

import sys
import os
import subprocess
import urllib.request
import urllib.parse
import json
import re
from pathlib import Path
from typing import List

def print_header(text: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {text.upper()}")
    print("=" * 70 + "\n")

def run_command(cmd: List[str], check: bool = True, capture_output: bool = False) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(cmd, check=check, capture_output=capture_output, text=True)
        return result
    except subprocess.CalledProcessError as e:
        print(f"\nCommand failed with exit code {e.returncode}")
        print(e.stderr or "No error output captured.")
        raise

def setup_environment() -> None:
    print_header("PHASE 1: Setting up tools")
    print("Ensuring yt-dlp and mutagen are installed...\n")
    pip_cmd = [sys.executable, "-m", "pip", "install", "--upgrade"]
    try:
        run_command([*pip_cmd, "yt-dlp", "mutagen"])
        print("Tools are ready!")
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

def fetch_itunes_metadata(query: str) -> dict:
    """Queries the iTunes API for exhaustive track data and high-res artwork"""
    print("\nFetching metadata from iTunes...")
    
    safe_query = urllib.parse.quote(query)
    url = f"https://itunes.apple.com/search?term={safe_query}&media=music&entity=song&limit=1"
    
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    response = urllib.request.urlopen(req)
    data = json.loads(response.read().decode('utf-8'))
    
    if data['resultCount'] == 0:
        raise ValueError("No matching track found on iTunes.")
        
    track = data['results'][0]
    
    # High-res 1000x1000 cover art
    cover_url = track.get('artworkUrl100', '').replace('100x100bb.jpg', '1000x1000bb.jpg')
    
    # Parse release year
    release_date = track.get('releaseDate', '')
    year = release_date[:4] if release_date else ''

    # Determine ITUNESADVISORY Explicit Rating (1 = Explicit, 2 = Cleaned, 0 = Clean)
    explicitness = track.get('trackExplicitness', '')
    if explicitness == 'explicit':
        advisory = '1'
    elif explicitness == 'cleaned':
        advisory = '2'
    else:
        advisory = '0'
    
    return {
        "artist": track.get('artistName', 'Unknown Artist'),
        "title": track.get('trackName', 'Unknown Title'),
        "album": track.get('collectionName', 'Unknown Album'),
        "album_artist": track.get('collectionArtistName', track.get('artistName', 'Unknown Artist')),
        "genre": track.get('primaryGenreName', 'Unknown Genre'),
        "composer": track.get('artistName', ''), # iTunes rarely returns composer; maps to Artist as fallback
        "year": year,
        "track_num": str(track.get('trackNumber', '1')),
        "track_count": str(track.get('trackCount', '1')),
        "disc_num": str(track.get('discNumber', '1')),
        "disc_count": str(track.get('discCount', '1')),
        "advisory": advisory,
        "cover_url": cover_url
    }

def embed_metadata(mp3_path: Path, track_info: dict) -> None:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, TDRC, TRCK, TCON, TPE2, TCOM, TPOS, COMM, TXXX, error

    try:
        audio = MP3(str(mp3_path), ID3=ID3)
    except Exception:
        return 

    try:
        audio.add_tags()
    except error:
        pass 

    # Core Tags
    audio.tags.add(TIT2(encoding=3, text=track_info["title"]))
    audio.tags.add(TPE1(encoding=3, text=track_info["artist"]))
    audio.tags.add(TALB(encoding=3, text=track_info["album"]))
    audio.tags.add(TPE2(encoding=3, text=track_info["album_artist"]))
    audio.tags.add(TCOM(encoding=3, text=track_info["composer"]))
    audio.tags.add(TCON(encoding=3, text=track_info["genre"]))
    
    # Year
    if track_info["year"]:
        audio.tags.add(TDRC(encoding=3, text=track_info["year"]))

    # Numbering Arrays (e.g., 1/12)
    audio.tags.add(TRCK(encoding=3, text=f"{track_info['track_num']}/{track_info['track_count']}"))
    audio.tags.add(TPOS(encoding=3, text=f"{track_info['disc_num']}/{track_info['disc_count']}"))
    
    # Comment
    audio.tags.add(COMM(encoding=3, lang='eng', desc='', text='Downloaded via yt-dlp & iTunes API'))

    # iTunes Advisory (Explicit Flag)
    audio.tags.add(TXXX(encoding=3, desc='ITUNESADVISORY', text=track_info["advisory"]))

    # Artwork
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
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def process_download(output_folder: Path) -> None:
    print_header("Download Track")
    search_query = input("Enter the 'Artist - Song Title': ").strip()

    if not search_query:
        print("Search query cannot be empty.")
        return

    try:
        track_info = fetch_itunes_metadata(search_query)
        artist = track_info['artist']
        title = track_info['title']
        print(f"Found: {artist} - {title}")
        print(f"Album: {track_info['album']}\n")
    except Exception as e:
        print(f"Failed to fetch metadata: {e}")
        print("Tip: Check your spelling or try including the artist name.")
        return

    safe_artist = sanitize_filename(artist)
    safe_title = sanitize_filename(title)
    file_name = f"{safe_artist} - {safe_title}"
    mp3_path = output_folder / f"{file_name}.mp3"
    output_template = str(output_folder / f"{file_name}.%(ext)s")

    if mp3_path.exists():
        print("-> File already exists. Skipping download and updating metadata...")
        embed_metadata(mp3_path, track_info)
        return

    print("Downloading audio from YouTube at 320kbps...")
    
    yt_query = f"ytsearch1:{artist} {title} audio"
    cmd = [
        sys.executable, "-m", "yt_dlp",
        yt_query,
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "320K",
        "--extractor-args", "youtube:player_client=android,ios", 
        "--rm-cache-dir",
        "--quiet", "--no-warnings", 
        "-o", output_template
    ]

    try:
        run_command(cmd)
        if mp3_path.exists():
            embed_metadata(mp3_path, track_info)
            print("-> Successfully saved, tagged, and embedded artwork!")
        else:
            print("-> Download failed or file missing.")
    except KeyboardInterrupt:
        print("\nDownload canceled.")
    except Exception as e:
        print(f"-> Error downloading track: {e}")

def main() -> None:
    print_header("YouTube 320kbps MP3 Downloader")
    
    setup_environment()

    ffmpeg_choice = input("\nCheck/Install FFmpeg now (required for MP3s)? [Y/n]: ").lower().strip()
    if ffmpeg_choice in ("", "y", "yes"):
        download_ffmpeg()

    folder = create_music_folder()
    os.chdir(folder)
    print(f"\nWorking directory: {folder}")

    while True:
        print("\nWhat would you like to do?")
        print("  1. Search and Download a Track")
        print("  2. Quit")

        choice = input("\nEnter number: ").strip()

        if choice == "1":
            process_download(output_folder=folder)
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