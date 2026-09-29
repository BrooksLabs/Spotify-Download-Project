# Local-Music-Download-Project
This project is my attempt to localize my existing +10,000 song music library for offline listening. 

# YouTube & iTunes Audio Downloader Guide

Interactive Python script that walks users through installing and using **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** to download audio from YouTube, while using the free **iTunes API** to perfectly tag the files. This was built as a stable, permanent alternative to Spotify-based downloaders that frequently suffer from API rate limits and 403 firewall blocks.

## Features
- **Step-by-step terminal guidance:** Simple menu interface and folder selection helper.
- **Automated Setup:** Checks and auto-installs `yt-dlp` + `mutagen`, and assists with `FFmpeg` configuration.
- **High-Quality Audio:** Bypasses YouTube DRM and forces FFmpeg to encode at 320kbps MP3.
- **Exhaustive ID3 Metadata:** Automatically fetches and embeds Title, Artist, Album, Album Artist, Genre, Composer, Year, Track Number, Disc Number, and the custom `ITUNESADVISORY` (Explicit/Clean) flag.
- **High-Res Artwork:** Injects gorgeous 1000x1000 pixel album covers directly into the MP3 file.
- **Smart Resume Support:** Checks the destination folder before downloading. If a file already exists, it skips the download and safely updates the metadata.
