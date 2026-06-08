#!/usr/bin/env python3
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

INPUT_FILE = Path("input.txt")
OUTPUT_DIR = Path("output")
TEMP_DIR = Path(".tmp_audio")

# Hardcoded window around each timestamp.
SECONDS_BEFORE = 30
SECONDS_AFTER = 10
FADE_DURATION = 1


def fail(message: str) -> None:
    print(f"Fehler: {message}", file=sys.stderr)
    sys.exit(1)


def require_binary(name: str) -> None:
    if shutil.which(name) is None:
        fail(f"`{name}` nicht gefunden.")


def parse_time(value: str) -> int:
    parts = value.strip().split(":")
    if not 1 <= len(parts) <= 3:
        raise ValueError(f"Ungueltige Zeit: {value}")

    total = 0
    for part in parts:
        total = total * 60 + int(part)
    return total


def sanitize_filename(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[\\/]+", "_", name)
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^A-Za-z0-9_.-]", "", name)
    name = re.sub(r"_+", "_", name)
    return name.strip("._") or "track"


def extract_video_id(url: str) -> str:
    parsed = urlparse(url)

    if parsed.netloc in {"youtu.be", "www.youtu.be"}:
        video_id = parsed.path.strip("/")
        if video_id:
            return video_id

    query_video_id = parse_qs(parsed.query).get("v", [])
    if query_video_id:
        return query_video_id[0]

    if parsed.path.startswith("/shorts/"):
        video_id = parsed.path.split("/shorts/", 1)[1].strip("/")
        if video_id:
            return video_id

    raise ValueError("Konnte keine Video-ID aus dem Link lesen.")


def is_youtube_url(value: str) -> bool:
    try:
        extract_video_id(value)
        return True
    except ValueError:
        return False


def parse_timestamp_line(line: str):
    match = re.match(r"^(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)$", line)
    if not match:
        return None

    timestamp = parse_time(match.group(1))
    names_raw = match.group(2).replace(",", " ")
    names = [name for name in names_raw.split() if name]
    if not names:
        fail(f"Keine Namen gefunden in: {line}")

    return {
        "timestamp": timestamp,
        "filename": sanitize_filename("_".join(names)) + ".mp3",
    }


def parse_input_file(path: Path):
    if not path.exists():
        fail(f"{path} fehlt.")

    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    jobs = []
    current_url = None

    for line in lines:
        if not line:
            continue

        if is_youtube_url(line):
            if current_url is not None:
                fail(f"Fuer Link fehlt die Timestamp-Zeile: {current_url}")
            current_url = line
            continue

        if current_url is None:
            fail(f"Erwartet wurde ein YouTube-Link, gefunden: {line}")

        timestamp_data = parse_timestamp_line(line)
        if timestamp_data is None:
            fail(f"Timestamp-Zeile konnte nicht gelesen werden: {line}")

        jobs.append(
            {
                "url": current_url,
                "timestamp": timestamp_data["timestamp"],
                "filename": timestamp_data["filename"],
            }
        )
        current_url = None

    if current_url is not None:
        fail(f"Fuer Link fehlt die Timestamp-Zeile: {current_url}")
    if not jobs:
        fail("input.txt enthaelt keine gueltigen Link/Timestamp-Paare.")

    return jobs


def download_audio(youtube_url: str, temp_audio_file: Path) -> None:
    if temp_audio_file.exists():
        temp_audio_file.unlink()
    downloaded_mp3 = temp_audio_file.with_name("source.mp3")
    if downloaded_mp3.exists():
        downloaded_mp3.unlink()

    command = [
        "yt-dlp",
        "--no-progress",
        "--no-warnings",
        "-x",
        "--audio-format",
        "mp3",
        "-o",
        str(temp_audio_file),
        youtube_url,
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        error_output = result.stderr.strip() or result.stdout.strip() or "Download fehlgeschlagen."
        fail(error_output)


def cut_clip(source_file: Path, target_file: Path, start: int, duration: int) -> None:
    fade_out_start = max(0, duration - FADE_DURATION)
    audio_filter = f"afade=t=in:st=0:d={FADE_DURATION},afade=t=out:st={fade_out_start}:d={FADE_DURATION}"

    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        str(start),
        "-i",
        str(source_file),
        "-t",
        str(duration),
        "-vn",
        "-af",
        audio_filter,
        "-acodec",
        "libmp3lame",
        "-q:a",
        "2",
        str(target_file),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        error_output = result.stderr.strip() or result.stdout.strip() or "ffmpeg-Schnitt fehlgeschlagen."
        fail(error_output)


def print_progress(done: int, total: int, label: str) -> None:
    percent = int(done * 100 / total)
    print(f"[{percent:3d}%] {label}")


def main() -> None:
    require_binary("yt-dlp")
    require_binary("ffmpeg")

    jobs = parse_input_file(INPUT_FILE)

    OUTPUT_DIR.mkdir(exist_ok=True)
    TEMP_DIR.mkdir(exist_ok=True)
    temp_audio_file = TEMP_DIR / "source.%(ext)s"
    downloaded_audio_file = TEMP_DIR / "source.mp3"

    total_steps = len(jobs) * 2
    print_progress(0, total_steps, "start")

    for index, job in enumerate(jobs, start=1):
        download_audio(job["url"], temp_audio_file)
        print_progress(index * 2 - 1, total_steps, "download")

        start = max(0, job["timestamp"] - SECONDS_BEFORE)
        duration = SECONDS_BEFORE + SECONDS_AFTER
        target_file = OUTPUT_DIR / job["filename"]
        cut_clip(downloaded_audio_file, target_file, start, duration)
        print_progress(index * 2, total_steps, job["filename"])


if __name__ == "__main__":
    main()
