#!/usr/bin/env python3
"""Export a verified render directory to MP3. No upload, sync, or network I/O."""
from __future__ import annotations

import argparse
from datetime import datetime
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import wave

from render_episode import atomic_text, check_wave, episode_hash, file_hash, require, safe_file

VERSION = 1
BITRATE = "96k"


def encoder():
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError) as error:
        raise ValueError("Install FFmpeg on PATH or pip install -r requirements-audio.txt") from error


def run(command):
    subprocess.run(command, check=True, capture_output=True, text=True, timeout=180)


def _export_locked(directory, receipt_path):
    manifest = json.loads(safe_file(directory, "manifest.json").read_text(encoding="utf-8"))
    require(manifest.get("audio_status") == "ready", "Source audio is not ready")
    fingerprint = manifest.get("fingerprint", "")
    require(isinstance(fingerprint, str) and re.fullmatch(r"[0-9a-f]{64}", fingerprint),
            "Invalid render fingerprint")
    checks = manifest.get("file_hashes", {})
    episode_path = safe_file(directory, "episode.json")
    require(file_hash(episode_path) == checks.get("episode.json"), "Episode snapshot checksum mismatch")
    ep = json.loads(episode_path.read_text(encoding="utf-8"))
    require(episode_hash(ep) == manifest.get("episode_sha256"), "Episode does not match the render")
    source = safe_file(directory, manifest["audio_file"])
    digest = file_hash(source)
    require(digest == checks.get(source.name), "Source audio checksum mismatch")
    require(type(manifest.get("duration_seconds")) in {int, float} and manifest["duration_seconds"] > 0,
            "Invalid source duration")
    target = safe_file(directory, f"episode-{fingerprint[:12]}.mp3")
    if receipt_path.exists():
        try:
            old = json.loads(receipt_path.read_text(encoding="utf-8"))
            if (old.get("version") == VERSION and old.get("source_sha256") == digest
                    and old.get("status") == "ready" and old.get("bitrate") == BITRATE
                    and old.get("render_fingerprint") == fingerprint
                    and old.get("episode_sha256") == manifest["episode_sha256"]
                    and old.get("file") == target.name and target.is_file()
                    and file_hash(target) == old.get("sha256")):
                return old
        except (ValueError, TypeError, AttributeError, OSError):
            pass
    # Invalidate any previous MP3 completion before encoding this render.
    atomic_text(receipt_path, json.dumps({"version": VERSION, "status": "processing",
                                          "render_fingerprint": fingerprint}) + "\n")
    executable = encoder()
    with tempfile.TemporaryDirectory(prefix=".mp3-", dir=directory) as tmp:
        tmp = Path(tmp)
        compressed, decoded = tmp / "episode.mp3", tmp / "verified.wav"
        run([executable, "-hide_banner", "-loglevel", "error", "-nostdin", "-i", str(source),
             "-map", "0:a:0", "-vn", "-map_metadata", "-1", "-ac", "1", "-ar", "44100",
             "-c:a", "libmp3lame", "-b:a", BITRATE, "-id3v2_version", "3",
             "-metadata", f"title={ep['title']}", "-metadata", "artist=Brief to Podcast",
             "-metadata", "comment=AI-generated synthetic voice", str(compressed)])
        run([executable, "-hide_banner", "-loglevel", "error", "-nostdin", "-i", str(compressed),
             "-map", "0:a:0", "-ac", "1", "-ar", "22050", "-c:a", "pcm_s16le", str(decoded)])
        duration = check_wave(decoded)
        require(abs(duration - manifest["duration_seconds"]) < 2, "MP3 duration mismatch")
        require(compressed.stat().st_size > 1000, "MP3 is empty")
        os.replace(compressed, target)
    receipt = {"version": VERSION, "status": "ready", "title": ep["title"],
               "file": target.name, "mime_type": "audio/mpeg", "bitrate": BITRATE,
               "duration_seconds": round(duration, 3), "byte_size": target.stat().st_size,
               "sha256": file_hash(target), "source_sha256": digest,
               "episode_sha256": manifest["episode_sha256"], "render_fingerprint": fingerprint,
               "created_at": datetime.now().astimezone().isoformat()}
    atomic_text(receipt_path, json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    return receipt


def export_mp3(directory):
    directory = Path(directory)
    require(directory.is_dir(), "Render directory does not exist")
    with safe_file(directory, ".render.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        receipt_path = safe_file(directory, "mobile_audio.json")
        try:
            return _export_locked(directory, receipt_path)
        except (ValueError, KeyError, TypeError, AttributeError, OSError, EOFError,
                wave.Error, subprocess.SubprocessError) as error:
            atomic_text(receipt_path, json.dumps({"version": VERSION, "status": "failed",
                                                "error": str(error)}, ensure_ascii=False, indent=2) + "\n")
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="Directory containing a ready manifest and episode.json")
    args = parser.parse_args()
    try:
        receipt = export_mp3(args.directory)
    except (ValueError, KeyError, TypeError, AttributeError, OSError, EOFError,
            wave.Error, subprocess.SubprocessError) as error:
        parser.exit(2, f"Cannot export MP3: {error}\n")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
