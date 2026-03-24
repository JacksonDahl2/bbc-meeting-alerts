#!/usr/bin/env python3
"""
One-time setup: downloads the BBC News countdown theme via yt-dlp.

Prerequisites:
    brew install ffmpeg        # yt-dlp needs ffmpeg for mp3 transcoding
    uv add yt-dlp              # or pip install yt-dlp

Usage:
    uv run python src/download_audio.py

The file is saved to assets/bbc_news.mp3. If it already exists, this
script exits immediately without re-downloading.

Note: If this URL stops working, search YouTube for "BBC News countdown theme"
and update the constant below.
"""

import os
import subprocess
import sys

# BBC News countdown / theme — update this URL if the video is removed
BBC_YOUTUBE_URL = "https://www.youtube.com/watch?v=4TSJhIZmL0A"

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
OUTPUT_PATH = os.path.join(ASSETS_DIR, "bbc_news.mp3")


def main() -> None:
    if os.path.exists(OUTPUT_PATH):
        print(f"Audio already exists at {OUTPUT_PATH} — skipping download.")
        return

    os.makedirs(ASSETS_DIR, exist_ok=True)

    # Check that ffmpeg is available (required for mp3 transcoding)
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            check=True,
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        print(
            "ERROR: ffmpeg not found. Install it first:\n"
            "    brew install ffmpeg",
            file=sys.stderr,
        )
        sys.exit(1)

    # Check that yt-dlp is available
    try:
        subprocess.run(
            ["yt-dlp", "--version"],
            check=True,
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        print(
            "ERROR: yt-dlp not found. Install it first:\n"
            "    uv add yt-dlp  (or pip install yt-dlp)",
            file=sys.stderr,
        )
        sys.exit(1)

    output_template = os.path.join(ASSETS_DIR, "bbc_news.%(ext)s")

    cmd = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "0",          # best quality
        "--output", output_template,
        "--no-playlist",
        "--js-runtimes", "node",         # use node for YouTube JS extraction
        BBC_YOUTUBE_URL,
    ]

    print(f"Downloading BBC News theme from:\n  {BBC_YOUTUBE_URL}\n")
    result = subprocess.run(cmd)

    if result.returncode != 0:
        print("ERROR: yt-dlp failed. Check the URL above and try again.", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(OUTPUT_PATH):
        print(
            f"ERROR: Expected output file not found at {OUTPUT_PATH}\n"
            "yt-dlp may have saved it under a different name.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"\nDone. Audio saved to:\n  {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
