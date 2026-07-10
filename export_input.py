#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

OUTPUT_DIR = Path("output")
TEMP_DIR = Path(".tmp_audio")
REPORT_FILE = OUTPUT_DIR / "_report.txt"

# Main timing controls.
CLIP_DURATION_SECONDS = 60
PRE_ROLL_SECONDS = 30
FADE_DURATION_SECONDS = 0.08

# Optional: set this to "firefox", "chrome", "chromium", etc. if YouTube blocks requests.
COOKIES_FROM_BROWSER: str | None = None


@dataclass(frozen=True)
class Entry:
    order_name: str
    source: str | None
    timestamp: str | None
    exact_start: bool = False


ENTRIES = [
    Entry("Berkay", "https://youtu.be/YFNBjam2leY?is=Plc5tKstFtO_qRLz", "0:00", exact_start=True),
    Entry("Serafina", "https://www.youtube.com/watch?v=LlVI7ZNiFlI", "0:53"),
    Entry("Dominik, Niklas, Michael", "https://www.youtube.com/watch?v=04854XqcfCY", "0:36", exact_start=True),
    Entry("Noah Stadelhofer, Felix Kopp", "https://youtu.be/k9EYjn5f_nE", "0:00", exact_start=True),
    Entry("Lisa", "https://youtu.be/GTyEsIMefzc?is=YqsjJX1dWVOgDPLh", "2:10", exact_start=True),
    Entry("Marijan, Manuel Löbel", "https://youtu.be/5EpyN_6dqyk?is=kz_6yUDMU8jcVR0G", "1:39", exact_start=True),
    Entry("Alexandra", "https://www.youtube.com/watch?v=PlOcQyZ6h8s", "2:28"),
    Entry("Silas, Morice, Rico", "https://youtu.be/62c1jdaldBQ?si=nEllzf4ypPWEMgl2", "0:57"),
    Entry("Joscha, Alexandru", "https://youtu.be/l0U7SxXHkPY?is=09Id4mHEI0-VHpyZ", "1:36", exact_start=True),
    Entry("Kristin", "https://youtu.be/W5guhMw_EH0?is=maLSn6i5frLne0Tu", "0:55", exact_start=True),
    Entry("Dave, Max, Erik Schwarz, Leon", "https://youtu.be/zg3CknoEDC8?is=9RLyDF9ktX7RPCyH", "0:50", exact_start=True),
    Entry("Raphael", "https://m.youtube.com/watch?v=gPUENbTGDbs&ra=m", "0:10", exact_start=True),
    Entry("Sophie, Vanessa, Evelyn, Tabea", "https://youtu.be/gGdGFtwCNBE?si=tJnmQRjV81vnSd_J", "0:03", exact_start=True),
    Entry("Benjamin, Laurin Witt", "https://www.youtube.com/watch?v=dxytyRy-O1k&list=RDdxytyRy-O1k&start_radio=1", "1:09", exact_start=True),
    Entry("Nicolas, Chiara, Kayla, Henry", "https://youtu.be/DeumyOzKqgI?is=aIY8uXagwUC3HnMJ", "1:22"),
    Entry("Luzie, Sara, Melis", "https://youtu.be/oTNqEcIVBfk?is=F-gw7XUNq-Eng7-n", "0:00", exact_start=True),
    Entry("Felix Hafner, David, Joel", "https://youtu.be/HAfFfqiYLp0?is=rqgql9BzPs2DDj5e", "1:08", exact_start=True),
    Entry("Riana, Addison, Mathilde", "https://youtu.be/IPKAwJKGSDc?is=_fTUgS3aCDKaLu6h", "0:30", exact_start=True),
    Entry("Denis, Adnan", "https://www.youtube.com/watch?v=lFCXF2UHfz0", "2:10", exact_start=True),
    Entry("Jule, Nele", "https://youtu.be/X5kmM98iklo?is=Q9D5ztX5BINqGj2_", "0:10", exact_start=True),
    Entry("Amelie, Lotta", "https://youtu.be/vGrfFzagzHs?is=iMPGXfVGylrsJbPw", "0:07", exact_start=True),
    Entry("Selin, Sofia", "https://youtu.be/syFZfO_wfMQ?si=NxpKqElMT0YdezaM", "1:50", exact_start=True),
    Entry("Gresa, Emily, Loreen, Eda, Sardiana", "https://youtu.be/y88GdSmOOWw?t=42&is=gs2tWww578g80jVj", "0:43", exact_start=True),
    Entry("Manuel J., Eric Harsch", "https://youtu.be/O20mHKAogs8?is=cCwbGn6PxOI8jpTm", "0:45", exact_start=True),
    Entry("batoul", "https://youtu.be/B3Z4XGAxJB0?is=n4LM_PDsAmZpoaiK", "1:25", exact_start=True),
    Entry("laurin scheu", "https://youtu.be/QV5ZBuNJMx0?is=j-6mrbD1P-b64RvJ", "3:15"),
]

REIHENFOLGE = [
    "Berkay",
    "Noah Stadelhofer, Felix Kopp",
    "Lisa",
    "Marijan, Manuel Löbel",
    "Serafina",
    "Kristin",
    "Silas, Morice, Rico",
    "Joscha, Alexandru",
    "Alexandra",
    "Dave, Max, Erik Schwarz, Leon",
    "Raphael",
    "Sophie, Vanessa, Evelyn, Tabea",
    "Benjamin, Laurin Witt",
    "Nicolas, Chiara, Kayla, Henry",
    "Luzie, Sara, Melis",
    "Felix Hafner, David, Joel",
    "Riana, Addison, Mathilde",
    "Denis, Adnan",
    "Dominik, Niklas, Michael",
    "Jule, Nele",
    "Amelie, Lotta",
    "Selin, Sofia",
    "Gresa, Emily, Loreen, Eda, Sardiana",
    "Manuel J., Eric Harsch",
    "batoul",
    "laurin scheu",
]


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


def sanitize_filename_part(value: str) -> str:
    value = value.strip().lower()
    value = (
        value.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )
    value = re.sub(r"[\\/]+", "_", value)
    value = re.sub(r"[&,+.]+", " ", value)
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"[^a-z0-9_-]", "", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("_") or "track"


def build_output_filename(index: int, order_name: str) -> str:
    name_parts = [sanitize_filename_part(part) for part in order_name.split(",")]
    name_parts = [part for part in name_parts if part]
    return f"{index:02d}_{'_'.join(name_parts)}.mp3"


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

    raise ValueError(f"Konnte keine Video-ID aus dem Link lesen: {url}")


def build_jobs() -> tuple[list[dict[str, object]], list[str]]:
    entries_by_name = {entry.order_name: entry for entry in ENTRIES}
    unknown_entries = sorted(set(entries_by_name) - set(REIHENFOLGE))
    duplicate_order_names = [name for name in REIHENFOLGE if REIHENFOLGE.count(name) > 1]

    if unknown_entries:
        fail(f"Eintraege ohne Reihenfolge: {', '.join(unknown_entries)}")
    if duplicate_order_names:
        fail(f"Doppelte Namen in REIHENFOLGE: {', '.join(sorted(set(duplicate_order_names)))}")

    jobs: list[dict[str, object]] = []
    missing: list[str] = []

    for index, order_name in enumerate(REIHENFOLGE, start=1):
        entry = entries_by_name.get(order_name)
        if entry is None:
            missing.append(f"{index:02d} {order_name}: fehlt komplett in ENTRIES")
            continue

        if not entry.source or not entry.timestamp:
            missing.append(f"{index:02d} {order_name}: Quelle oder Timestamp fehlt")
            continue

        timestamp_seconds = parse_time(entry.timestamp)
        start_seconds = timestamp_seconds if entry.exact_start else max(0, timestamp_seconds - PRE_ROLL_SECONDS)
        jobs.append(
            {
                "index": index,
                "order_name": order_name,
                "url": entry.source,
                "timestamp": entry.timestamp,
                "exact_start": entry.exact_start,
                "start_seconds": start_seconds,
                "filename": build_output_filename(index, order_name),
                "video_id": extract_video_id(entry.source),
            }
        )

    return jobs, missing


def yt_dlp_attempts(youtube_url: str, target_template: Path) -> list[list[str]]:
    base_command = [
        "yt-dlp",
        "--no-progress",
        "--no-warnings",
        "--force-overwrites",
        "--extractor-retries",
        "3",
        "--fragment-retries",
        "3",
        "--retry-sleep",
        "1",
        "--force-ipv4",
        "-x",
        "--audio-format",
        "mp3",
        "-o",
        str(target_template),
    ]

    attempts = [
        base_command + ["--extractor-args", "youtube:player_client=android", youtube_url],
        base_command + ["--extractor-args", "youtube:player_client=ios", youtube_url],
        base_command + ["--extractor-args", "youtube:player_client=web", youtube_url],
    ]

    if COOKIES_FROM_BROWSER:
        attempts.append(
            base_command
            + [
                "--cookies-from-browser",
                COOKIES_FROM_BROWSER,
                "--extractor-args",
                "youtube:player_client=android",
                youtube_url,
            ]
        )

    return attempts


def download_audio(youtube_url: str, target_template: Path) -> None:
    errors: list[str] = []

    for attempt_number, command in enumerate(yt_dlp_attempts(youtube_url, target_template), start=1):
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0:
            return

        error_output = result.stderr.strip() or result.stdout.strip() or "Download fehlgeschlagen."
        errors.append(f"Versuch {attempt_number}: {error_output}")

    hint = ""
    if any("403" in error for error in errors):
        if COOKIES_FROM_BROWSER:
            hint = f" YouTube blockiert den Abruf weiterhin trotz `--cookies-from-browser {COOKIES_FROM_BROWSER}`."
        else:
            hint = " Setze `COOKIES_FROM_BROWSER` oben im Skript z. B. auf `firefox` oder `chrome`, falls dein Browser dort eingeloggt ist."

    fail("Download fehlgeschlagen.\n" + "\n".join(errors) + hint)


def cut_clip(source_file: Path, target_file: Path, start_seconds: int) -> None:
    fade_out_start = max(0.0, CLIP_DURATION_SECONDS - FADE_DURATION_SECONDS)
    audio_filter = (
        f"afade=t=in:st=0:d={FADE_DURATION_SECONDS},"
        f"afade=t=out:st={fade_out_start}:d={FADE_DURATION_SECONDS}"
    )

    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        str(start_seconds),
        "-i",
        str(source_file),
        "-t",
        str(CLIP_DURATION_SECONDS),
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


def write_report(jobs: list[dict[str, object]], missing: list[str]) -> None:
    lines = [
        f"Clip length: {CLIP_DURATION_SECONDS}s",
        f"Pre-roll for non-'los' entries: {PRE_ROLL_SECONDS}s",
        f"Fade in/out: {FADE_DURATION_SECONDS}s",
        "",
        "Exports:",
    ]

    for job in jobs:
        mode = "los" if job["exact_start"] else f"-{PRE_ROLL_SECONDS}s"
        lines.append(
            f"{job['index']:02d} {job['filename']} | {job['timestamp']} | start={job['start_seconds']}s | {mode}"
        )

    lines.extend(["", "Missing / skipped:"])
    lines.extend(missing or ["none"])
    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_progress(done: int, total: int, label: str) -> None:
    percent = int(done * 100 / total) if total else 100
    print(f"[{percent:3d}%] {label}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--redo",
        action="store_true",
        help="Re-export files even if the target mp3 already exists.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    require_binary("yt-dlp")
    require_binary("ffmpeg")

    jobs, missing = build_jobs()
    if not jobs:
        fail("Keine vollstaendigen Eintraege gefunden.")

    OUTPUT_DIR.mkdir(exist_ok=True)
    TEMP_DIR.mkdir(exist_ok=True)
    write_report(jobs, missing)

    active_jobs = []
    skipped_outputs = []
    for job in jobs:
        target_file = OUTPUT_DIR / str(job["filename"])
        if target_file.exists() and not args.redo:
            skipped_outputs.append(str(job["filename"]))
            continue
        active_jobs.append(job)

    total_steps = len(active_jobs) * 2
    print_progress(0, total_steps, "start")

    cached_video_id = None
    cached_audio_file = None

    for filename in skipped_outputs:
        print(f"[skip] {filename}")

    for job_index, job in enumerate(active_jobs, start=1):
        video_id = job["video_id"]
        if cached_video_id != video_id:
            target_template = TEMP_DIR / f"{video_id}.%(ext)s"
            cached_audio_file = TEMP_DIR / f"{video_id}.mp3"
            if cached_audio_file.exists() and args.redo:
                cached_audio_file.unlink()
            if not cached_audio_file.exists():
                download_audio(str(job["url"]), target_template)
            cached_video_id = video_id
        print_progress(job_index * 2 - 1, total_steps, f"download {job['index']:02d}")

        if cached_audio_file is None:
            fail("Interner Fehler: Audiodatei fehlt nach dem Download.")

        target_file = OUTPUT_DIR / str(job["filename"])
        cut_clip(cached_audio_file, target_file, int(job["start_seconds"]))
        print_progress(job_index * 2, total_steps, str(job["filename"]))

    if skipped_outputs and not args.redo:
        print(f"Uebersprungen: {len(skipped_outputs)} bestehende Dateien. Fuer Neu-Export `--redo` verwenden.")

    print(f"Fertig. Bericht: {REPORT_FILE}")


if __name__ == "__main__":
    main()
