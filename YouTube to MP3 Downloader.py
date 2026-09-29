#!/usr/bin/env python3
"""
YouTube to MP3 Downloader (Confirmation & Fallback Edition)
===========================================================

Features:
- Completely bypasses Spotify and its 403 firewall blocks.
- Uses the free iTunes API to fetch accurate, exhaustive ID3 data.
- Built-in Fallback Engine: Detects if iTunes returns the wrong song and 
  generates custom metadata to correctly download leaks, mixtapes, and singles.
- Interactive Confirmation: Pauses and displays the found metadata for user 
  approval before downloading to prevent wrong songs or accidental typos.
- Batch downloads full albums with accurate track ordering and dedicated subfolders.
- Automatically appends "[ALBUM]" to album names for context.
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
import difflib
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

def parse_itunes_track(track: dict) -> dict:
    cover_url = track.get('artworkUrl100', '').replace('100x100bb.jpg', '1000x1000bb.jpg')
    release_date = track.get('releaseDate', '')
    year = release_date[:4] if release_date else ''

    explicitness = track.get('trackExplicitness', '')
    if explicitness == 'explicit':
        advisory = '1'
    elif explicitness == 'cleaned':
        advisory = '2'
    else:
        advisory = '0'
        
    raw_album = track.get('collectionName', 'Unknown Album')
    album_with_tag = f"{raw_album} [ALBUM]"
    
    return {
        "artist": track.get('artistName', 'Unknown Artist'),
        "title": track.get('trackName', 'Unknown Title'),
        "album": album_with_tag,
        "album_artist": track.get('collectionArtistName', track.get('artistName', 'Unknown Artist')),
        "genre": track.get('primaryGenreName', 'Unknown Genre'),
        "composer": track.get('artistName', ''), 
        "year": year,
        "track_num": str(track.get('trackNumber', '1')),
        "track_count": str(track.get('trackCount', '1')),
        "disc_num": str(track.get('discNumber', '1')),
        "disc_count": str(track.get('discCount', '1')),
        "advisory": advisory,
        "cover_url": cover_url
    }

def fetch_itunes_metadata(query: str) -> dict:
    print("\nFetching metadata from iTunes...")
    safe_query = urllib.parse.quote(query)
    url = f"https://itunes.apple.com/search?term={safe_query}&media=music&entity=song&limit=1"
    
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    response = urllib.request.urlopen(req)
    data = json.loads(response.read().decode('utf-8'))
    
    if data['resultCount'] == 0:
        raise ValueError("No matching track found on iTunes.")
        
    return parse_itunes_track(data['results'][0])

def fetch_itunes_album_tracks(query: str) -> List[dict]:
    print("\nSearching iTunes for album...")
    safe_query = urllib.parse.quote(query)
    
    search_url = f"https://itunes.apple.com/search?term={safe_query}&media=music&entity=album&limit=1"
    req = urllib.request.Request(search_url, headers={"User-Agent": "Mozilla/5.0"})
    response = urllib.request.urlopen(req)
    data = json.loads(response.read().decode('utf-8'))
    
    if data['resultCount'] == 0:
        raise ValueError("No matching album found on iTunes.")
        
    album_data = data['results'][0]
    collection_id = album_data['collectionId']
    
    lookup_url = f"https://itunes.apple.com/lookup?id={collection_id}&entity=song"
    req2 = urllib.request.Request(lookup_url, headers={"User-Agent": "Mozilla/5.0"})
    response2 = urllib.request.urlopen(req2)
    data2 = json.loads(response2.read().decode('utf-8'))
    
    tracks = []
    for item in data2['results']:
        if item.get('wrapperType') == 'track':
            tracks.append(parse_itunes_track(item))
            
    return tracks

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

    audio.tags.add(TIT2(encoding=3, text=track_info["title"]))
    audio.tags.add(TPE1(encoding=3, text=track_info["artist"]))
    audio.tags.add(TALB(encoding=3, text=track_info["album"]))
    audio.tags.add(TPE2(encoding=3, text=track_info["album_artist"]))
    audio.tags.add(TCOM(encoding=3, text=track_info["composer"]))
    audio.tags.add(TCON(encoding=3, text=track_info["genre"]))
    
    if track_info["year"]:
        audio.tags.add(TDRC(encoding=3, text=track_info["year"]))

    audio.tags.add(TRCK(encoding=3, text=f"{track_info['track_num']}/{track_info['track_count']}"))
    audio.tags.add(TPOS(encoding=3, text=f"{track_info['disc_num']}/{track_info['disc_count']}"))
    audio.tags.add(COMM(encoding=3, lang='eng', desc='', text='Downloaded via yt-dlp & iTunes API'))
    audio.tags.add(TXXX(encoding=3, desc='ITUNESADVISORY', text=track_info["advisory"]))

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

def download_yt_audio(query: str, output_template: str) -> bool:
    cmd = [
        sys.executable, "-m", "yt_dlp",
        query,
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
        return True
    except KeyboardInterrupt:
        raise
    except Exception as e:
        print(f"-> Error downloading track: {e}")
        return False

def process_single_download(output_folder: Path) -> None:
    print_header("Download Single Track")
    search_query = input("Enter the 'Artist - Song Title': ").strip()

    if not search_query:
        return

    if "-" in search_query:
        parts = search_query.split("-", 1)
        target_artist = parts[0].strip()
        target_title = parts[1].strip()
    else:
        target_artist = ""
        target_title = search_query.strip()

    track_info = None
    try:
        temp_info = fetch_itunes_metadata(search_query)
        actual_title = temp_info['title'].lower()
        expected_title = target_title.lower()
        ratio = difflib.SequenceMatcher(None, expected_title, actual_title).ratio()
        
        if expected_title in actual_title or actual_title in expected_title or ratio > 0.5:
            track_info = temp_info
        else:
            print(f"\n[!] iTunes returned a mismatch ('{temp_info['title']}'). Bypassing iTunes...")
    except Exception as e:
        print(f"\n[!] iTunes search failed. Bypassing iTunes...")

    if not track_info:
        artist = target_artist if target_artist else "Unknown Artist"
        title = target_title
        print(f"-> Generating custom metadata for Mixtape/Leak...\n")
        track_info = {
            "artist": artist,
            "title": title,
            "album": "Unknown Album [ALBUM]",
            "album_artist": artist,
            "genre": "Mixtape/Leak",
            "composer": artist,
            "year": "",
            "track_num": "1",
            "track_count": "1",
            "disc_num": "1",
            "disc_count": "1",
            "advisory": "1",
            "cover_url": None
        }

    print("\n--- CONFIRM TRACK DETAILS ---")
    print(f"Artist: {track_info['artist']}")
    print(f"Title:  {track_info['title']}")
    print(f"Album:  {track_info['album']}")
    print("-----------------------------\n")

    confirm = input("Is this correct? Proceed with download? [Y/n]: ").strip().lower()
    if confirm not in ('', 'y', 'yes'):
        print("-> Download canceled by user.\n")
        return

    safe_artist = sanitize_filename(track_info['artist'])
    safe_title = sanitize_filename(track_info['title'])
    file_name = f"{safe_artist} - {safe_title}"
    mp3_path = output_folder / f"{file_name}.mp3"
    output_template = str(output_folder / f"{file_name}.%(ext)s")

    if mp3_path.exists():
        print("-> File already exists. Skipping download and updating metadata...")
        embed_metadata(mp3_path, track_info)
        return

    print("Downloading audio from YouTube at 320kbps...")
    yt_search_artist = track_info['artist'] if track_info['artist'] != "Unknown Artist" else ""
    yt_query = f"ytsearch1:{yt_search_artist} {track_info['title']} audio".strip()
    
    if download_yt_audio(yt_query, output_template):
        if mp3_path.exists():
            embed_metadata(mp3_path, track_info)
            print("-> Successfully saved, tagged, and embedded artwork!")
        else:
            print("-> Download failed or file missing.")

def process_album_download(output_folder: Path) -> None:
    print_header("Download Full Album")
    search_query = input("Enter the 'Artist - Album Title': ").strip()

    if not search_query:
        return

    try:
        tracks = fetch_itunes_album_tracks(search_query)
    except Exception as e:
        print(f"Failed to fetch album metadata: {e}")
        return

    first_track = tracks[0]
    
    print("\n--- CONFIRM ALBUM DETAILS ---")
    print(f"Artist: {first_track['album_artist']}")
    print(f"Album:  {first_track['album']}")
    print(f"Tracks: {len(tracks)}")
    print("-----------------------------\n")

    confirm = input("Is this correct? Proceed with downloading the full album? [Y/n]: ").strip().lower()
    if confirm not in ('', 'y', 'yes'):
        print("-> Album download canceled by user.\n")
        return

    safe_album_artist = sanitize_filename(first_track["album_artist"])
    clean_album_name = first_track["album"].replace(" [ALBUM]", "")
    safe_album = sanitize_filename(clean_album_name)
    
    album_folder = output_folder / f"{safe_album_artist} - {safe_album}"
    album_folder.mkdir(parents=True, exist_ok=True)
    print(f"Saving to directory: {album_folder.name}\n")

    for index, track_info in enumerate(tracks, 1):
        artist = track_info['artist']
        title = track_info['title']
        safe_artist = sanitize_filename(artist)
        safe_title = sanitize_filename(title)
        
        track_num = track_info['track_num'].zfill(2)
        file_name = f"{track_num} - {safe_artist} - {safe_title}"
        
        mp3_path = album_folder / f"{file_name}.mp3"
        output_template = str(album_folder / f"{file_name}.%(ext)s")

        print(f"[{index}/{len(tracks)}] Downloading: {title}")
        
        if mp3_path.exists():
            print("  -> File already exists. Updating metadata...")
            embed_metadata(mp3_path, track_info)
            continue

        yt_query = f"ytsearch1:{artist} {title} audio"
        
        try:
            if download_yt_audio(yt_query, output_template):
                if mp3_path.exists():
                    embed_metadata(mp3_path, track_info)
                    print("  -> Embedded ID3 tags and cover art.")
                else:
                    print("  -> Download failed or file missing.")
        except KeyboardInterrupt:
            print("\nAlbum download canceled.")
            break

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
        print("  1. Search and Download a Single Track")
        print("  2. Search and Download a Full Album")
        print("  3. Quit")

        choice = input("\nEnter number: ").strip()

        if choice == "1":
            process_single_download(output_folder=folder)
        elif choice == "2":
            process_album_download(output_folder=folder)
        elif choice in ("3", "q", "quit", "exit"):
            break
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")

    print_header("All done!")
    print(f"Your music is saved in: {folder}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExited by user. Come back anytime!")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
