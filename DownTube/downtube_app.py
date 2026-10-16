#!/usr/bin/env python3
"""
downtube_app.py - download a YouTube video/playlist and turn its subtitles into AI-ready text.

Replaces the old two-step routine:
    1) yt-dlp --write-sub --write-auto-sub --sub-lang en -f "bv[height<=480][ext=mp4]+ba[ext=m4a]" ...
    2) python downtube.py

Run it, paste a YouTube video or playlist link, answer two yes/no questions
(subtitle file? text file?) and it does the rest.

Output (next to this script):
    downloads/<video>.mp4, <video>.en.vtt           single videos
    downloads/<playlist name>/01 - <video>.mp4 ...  playlists
    <either of the above>/text/<title>_en.txt       the AI-ready text (+ _en_raw.txt)

Needs: Python 3.8+, yt-dlp (on PATH, or `pip install yt-dlp`) and ffmpeg (merges video + audio).
Option: --no-video  only fetch subtitles / text (what the old downtube.py did).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple
from urllib.parse import parse_qs, urlparse

# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #
LANGUAGE = "en"                  # subtitle language
MAX_HEIGHT = 480                 # maximum video height
OUTPUT_ROOT = Path(__file__).resolve().parent / "downloads"
SAVE_RAW_TEXT = True             # also write <title>_en_raw.txt (one subtitle line per row), as downtube.py did

# Your exact selector comes first; the two fallbacks are only used when it finds nothing
# (without them yt-dlp fails on videos that have no mp4/m4a stream at this size).
VIDEO_FORMAT = (
    f"bv[height<={MAX_HEIGHT}][ext=mp4]+ba[ext=m4a]"
    f"/b[height<={MAX_HEIGHT}][ext=mp4]"
    f"/b[height<={MAX_HEIGHT}]"
)
VIDEO_EXTENSIONS = ("mp4", "mkv", "webm", "mov", "m4a")


# --------------------------------------------------------------------------- #
# Console helpers
# --------------------------------------------------------------------------- #
def configure_console() -> None:
    """Never crash on titles the console cannot display (emoji, Arabic, ...)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass


def say(message: str = "") -> None:
    print(message, flush=True)


def ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def ask_yes_no(question: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    while True:
        answer = ask(f"{question} [{hint}]: ").lower()
        if not answer:
            return default
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        say("  Please answer y or n.")


class Step:
    """Prints 'message... done' (plain text, CMD friendly)."""

    def __init__(self, message: str) -> None:
        self.message = message

    def __enter__(self) -> "Step":
        print(f"{self.message}... ", end="", flush=True)
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        print("failed" if exc_type else "done", flush=True)
        return False


def _quote(arg: str) -> str:
    return f'"{arg}"' if re.search(r'[\s<>&|^%()"]', arg) else arg


# --------------------------------------------------------------------------- #
# URL handling
# --------------------------------------------------------------------------- #
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_LIST_RE = re.compile(r"^[A-Za-z0-9_-]{10,}$")
_HOSTS = ("youtube.com", "youtu.be", "youtube-nocookie.com")


@dataclass
class Target:
    kind: str   # "video" or "playlist"
    url: str    # clean URL handed to yt-dlp


def parse_youtube_input(text: str) -> Optional[Tuple[Optional[str], Optional[str]]]:
    """Return (video_id, playlist_id) for a YouTube link or bare video ID, else None."""
    text = text.strip().strip("\"'")
    if _ID_RE.match(text):
        return text, None
    if "://" not in text:
        text = "https://" + text
    parsed = urlparse(text)
    host = (parsed.hostname or "").lower()
    if not any(host == h or host.endswith("." + h) for h in _HOSTS):
        return None

    query = parse_qs(parsed.query)
    video_id = (query.get("v") or [None])[0]
    playlist_id = (query.get("list") or [None])[0]
    parts = [p for p in parsed.path.split("/") if p]
    if not video_id:
        if host.endswith("youtu.be") and parts:
            video_id = parts[0]
        elif len(parts) >= 2 and parts[0] in ("shorts", "live", "embed", "v", "e"):
            video_id = parts[1]
    if video_id and not _ID_RE.match(video_id):
        video_id = None
    if playlist_id and not _LIST_RE.match(playlist_id):
        playlist_id = None
    if not (video_id or playlist_id):
        return None
    return video_id, playlist_id


def resolve_target(text: str) -> Optional[Target]:
    parsed = parse_youtube_input(text)
    if parsed is None:
        return None
    video_id, playlist_id = parsed
    if video_id and playlist_id:
        # e.g. a link copied while watching a playlist: ask once instead of guessing
        say("\nThis link is a video that belongs to a playlist.")
        if ask_yes_no("Download the WHOLE playlist instead of just this video?", default=False):
            video_id = None
        else:
            playlist_id = None
    if video_id:
        return Target("video", f"https://www.youtube.com/watch?v={video_id}")
    return Target("playlist", f"https://www.youtube.com/playlist?list={playlist_id}")


# --------------------------------------------------------------------------- #
# yt-dlp wrapper
# --------------------------------------------------------------------------- #
class YtDlpError(Exception):
    """yt-dlp could not read the link."""


@dataclass
class Entry:
    index: int        # position in the playlist (1 for a single video)
    video_id: str
    title: str


@dataclass
class Probe:
    title: str        # video title, or playlist title
    entries: List[Entry]
    total: int        # number of items in the playlist listing


def find_ytdlp() -> Optional[List[str]]:
    exe = shutil.which("yt-dlp")
    if exe:
        return [exe]
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        return None
    return [sys.executable, "-m", "yt_dlp"]


def ytdlp_version(ytdlp: List[str]) -> Optional[str]:
    try:
        result = subprocess.run([*ytdlp, "--version"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _last_error(stderr: str) -> str:
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    errors = [line for line in lines if line.startswith("ERROR")]
    return (errors or lines or [""])[-1]


def _title(value: object, fallback: str) -> str:
    text = str(value or "").strip()
    return fallback if text in ("", "NA") else text


def probe(ytdlp: List[str], target: Target) -> Probe:
    """Ask yt-dlp what the link contains (video title, or the list of playlist videos)."""
    cmd = [*ytdlp, "-J", "--flat-playlist", "--encoding", "utf-8"]
    if target.kind == "video":
        cmd.append("--no-playlist")
    cmd.append(target.url)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except OSError as exc:
        raise YtDlpError(f"could not run yt-dlp ({exc})")
    if proc.returncode != 0 or not proc.stdout.strip():
        raise YtDlpError(_last_error(proc.stderr) or "could not read this link (private, deleted or unavailable?)")
    try:
        data = json.loads(proc.stdout)
    except ValueError:
        raise YtDlpError("yt-dlp returned data that could not be read")

    if "entries" in data:
        raw = data.get("entries") or []
        entries = []
        for index, item in enumerate(raw, 1):
            video_id = str((item or {}).get("id") or "")
            if _ID_RE.match(video_id):
                entries.append(Entry(index, video_id, _title(item.get("title"), video_id)))
        if not entries:
            raise YtDlpError("no videos found - this looks like a channel page. Paste a playlist link instead")
        return Probe(_title(data.get("title"), "playlist"), entries, len(raw))

    video_id = str(data.get("id") or "")
    title = _title(data.get("title"), video_id)
    return Probe(title, [Entry(1, video_id, title)], 1)


def run_download(ytdlp: List[str], target: Target, run_dir: Path, want_subs: bool,
                 subs_dir: Optional[Path], skip_video: bool) -> int:
    """Run yt-dlp the same way the old commands did; its normal progress output is shown live."""
    cmd = list(ytdlp)
    if want_subs:
        cmd += ["--write-subs", "--write-auto-subs", "--sub-langs", LANGUAGE, "--sub-format", "vtt"]
    if skip_video:
        cmd.append("--skip-download")
    else:
        cmd += ["-f", VIDEO_FORMAT, "--merge-output-format", "mp4"]
    # -i: a failed subtitle download (e.g. HTTP 429) must not abort the video download.
    # Your playlist command already had it; the single-video one did not.
    cmd.append("-i")
    if target.kind == "video":
        cmd.append("--no-playlist")
    cmd += ["-P", str(run_dir)]
    if want_subs and subs_dir is not None:
        cmd += ["-P", f"subtitle:{subs_dir}"]      # subtitles only needed for the text -> temp folder
    template = ("%(title)s [%(id)s].%(ext)s" if target.kind == "video"
                else "%(playlist_index)s - %(title)s [%(id)s].%(ext)s")
    cmd += ["-o", template, target.url]
    say("Running: " + " ".join(_quote(part) for part in cmd))
    say()
    return subprocess.run(cmd).returncode


def find_file(directory: Optional[Path], video_id: str, extensions: Sequence[str]) -> Optional[Path]:
    """Find '<anything> [<video id>].<ext>' (yt-dlp's default naming) in a folder."""
    if directory is None:
        return None
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return None
    for ext in extensions:
        suffix = f"[{video_id}].{ext}"
        for name in names:
            if name.endswith(suffix):
                return directory / name
    return None


# --------------------------------------------------------------------------- #
# Subtitle -> text pipeline (the logic of downtube.py)
# --------------------------------------------------------------------------- #
# YouTube auto-captions carry per-word timing tags such as <00:00:01.040>.
_WORD_TIMING_TAG = re.compile(r"<(?:\d{1,2}:)?\d{2}:\d{2}[.,]\d{3}>")


def parse_vtt_to_transcript(vtt_file):
    """Parse a VTT file into transcript format.

    Same logic as downtube.py: for YouTube auto-captions only the first text line after
    each timestamp is read (those captions repeat every line in the following cue).
    One fix: manually written subtitles carry no per-word timing tags and may use two
    lines per cue; the old code silently dropped the second line, so for those files
    every line of each cue is kept. Auto-caption output is unchanged.
    """
    transcript = []
    try:
        with open(vtt_file, 'r', encoding='utf-8', errors='replace') as file:
            content = file.read()

        lines = content.split('\n')
        auto_captions = bool(_WORD_TIMING_TAG.search(content))

        for i, line in enumerate(lines):
            if '-->' in line:
                # This is a timestamp line
                timestamps = line.split('-->')
                start_time = parse_timestamp(timestamps[0].strip())

                if auto_captions:
                    cue_lines = lines[i + 1:i + 2]
                else:
                    cue_lines = []
                    for text_line in lines[i + 1:]:
                        if not text_line.strip() or '-->' in text_line:
                            break
                        cue_lines.append(text_line)

                for cue_line in cue_lines:
                    text = cue_line.strip()
                    if text and not text.startswith('WEBVTT'):
                        transcript.append({
                            'text': text,
                            'start': start_time,
                            'duration': 2.0  # Default duration
                        })

        return transcript
    except Exception as e:
        print(f"Error parsing VTT file: {str(e)}")
        return []


def parse_timestamp(timestamp):
    """Convert VTT timestamp to seconds"""
    try:
        parts = timestamp.replace(',', '.').split(':')
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return float(hours) * 3600 + float(minutes) * 60 + float(seconds)
        elif len(parts) == 2:
            minutes, seconds = parts
            return float(minutes) * 60 + float(seconds)
    except ValueError:
        pass
    return 0.0


def process_transcript_for_ai(transcript):
    """Process transcript to optimize for AI input by removing duplicates and optimizing text
    (unchanged from downtube.py)"""
    if not transcript:
        return ""

    # Extract just the text from transcript entries
    text_entries = [entry['text'] for entry in transcript]

    # Process the text to remove duplicates and optimize
    processed_text = []
    prev_text = ""

    for text in text_entries:
        # Skip if this line is identical or nearly identical to the previous one
        # (Some subtitle systems repeat lines with minimal differences)
        if text == prev_text:
            continue

        # Check for significant overlap with previous line
        # This helps catch cases where only a word or two is added
        if prev_text and (prev_text in text or text in prev_text):
            # If current text is longer, replace previous text
            if len(text) > len(prev_text):
                if processed_text:  # Make sure we have something to replace
                    processed_text[-1] = text
                    prev_text = text
                continue
            # If current text is shorter, skip it
            else:
                continue

        # Add text to processed list
        processed_text.append(text)
        prev_text = text

    # Build optimized text:
    # 1. Join sentences that belong together (often split across subtitle entries)
    # 2. Maintain paragraph structure for major topic changes

    optimized_text = ""
    current_sentence = ""

    for text in processed_text:
        # Check if this text ends with sentence-ending punctuation
        ends_sentence = bool(re.search(r'[.!?]"?\s*$', text))

        # If text starts with lowercase and previous doesn't end with sentence punctuation,
        # it's likely a continuation
        starts_lowercase = bool(re.match(r'^[a-z]', text))

        # Join with the current sentence if it's a continuation
        if starts_lowercase and current_sentence:
            current_sentence += " " + text
        else:
            # If we have a complete sentence, add it to the optimized text
            if current_sentence:
                optimized_text += current_sentence + " "
            current_sentence = text

        # If this part ends a sentence, reset current_sentence
        if ends_sentence:
            if current_sentence:
                optimized_text += current_sentence + " "
                current_sentence = ""

    # Add any remaining text
    if current_sentence:
        optimized_text += current_sentence

    # Final cleanup:
    # 1. Normalize spacing
    # 2. Remove any special subtitle formatting
    optimized_text = re.sub(r'\s+', ' ', optimized_text)  # Normalize spaces
    optimized_text = re.sub(r'<[^>]+>', '', optimized_text)  # Remove HTML-like tags
    optimized_text = re.sub(r'\[[^\]]+\]', '', optimized_text)  # Remove bracketed content
    optimized_text = re.sub(r'\([^)]*\)', '', optimized_text)  # Remove parenthesized content that's likely not part of the script

    return optimized_text.strip()


def clean_filename(title):
    """Clean a string to make it a valid filename"""
    # Step 1: Replace invalid characters (and control characters) with underscores
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
    clean_title = re.sub(invalid_chars, '_', title)

    # Step 2: Check for reserved names in Windows
    reserved_names = [
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    ]

    # If the cleaned name (without extension) matches a reserved name, add an underscore
    if clean_title.upper() in reserved_names:
        clean_title = clean_title + "_"

    # Step 3: Remove leading/trailing periods and spaces
    clean_title = clean_title.strip('. ')

    # Step 4: Replace multiple spaces with a single space
    clean_title = re.sub(r'\s+', ' ', clean_title)

    # Step 5: Trim to a reasonable length (max 100 chars)
    if len(clean_title) > 100:
        clean_title = clean_title[:97] + "..."

    # Step 6: If the title is empty after cleaning, use a default name
    if not clean_title:
        clean_title = "youtube_video"

    return clean_title


@dataclass
class TextResult:
    text_file: Path
    raw_file: Optional[Path]
    entries: int
    raw_bytes: int
    text_bytes: int
    chars: int

    @property
    def reduction(self) -> float:
        return ((self.raw_bytes - self.text_bytes) / self.raw_bytes) * 100 if self.raw_bytes > 0 else 0

    @property
    def tokens(self) -> int:
        return self.chars // 4   # rough estimate: ~4 characters per token


def write_text_files(vtt_file: Path, text_dir: Path, base_name: str) -> TextResult:
    """Create <base>_en.txt (AI-optimized) and, if enabled, <base>_en_raw.txt."""
    transcript = parse_vtt_to_transcript(vtt_file)
    if not transcript:
        raise ValueError("the subtitle file is empty or malformed")

    text_dir.mkdir(parents=True, exist_ok=True)
    raw_text = "".join(f"{entry['text']}\n" for entry in transcript)   # one subtitle per line
    raw_file = None
    if SAVE_RAW_TEXT:
        raw_file = text_dir / f"{base_name}_{LANGUAGE}_raw.txt"
        with open(raw_file, "w", encoding="utf-8") as file:
            file.write(raw_text)

    optimized_text = process_transcript_for_ai(transcript)
    text_file = text_dir / f"{base_name}_{LANGUAGE}.txt"
    with open(text_file, "w", encoding="utf-8") as file:
        file.write(optimized_text)

    return TextResult(
        text_file=text_file,
        raw_file=raw_file,
        entries=len(transcript),
        raw_bytes=len(raw_text.replace("\n", os.linesep).encode("utf-8")),  # size as written on this OS
        text_bytes=len(optimized_text.encode("utf-8")),
        chars=len(optimized_text),
    )


# --------------------------------------------------------------------------- #
# One download from start to finish
# --------------------------------------------------------------------------- #
@dataclass
class ItemResult:
    entry: Entry
    video: Optional[Path] = None
    vtt: Optional[Path] = None
    text: Optional[TextResult] = None
    problems: Optional[List[str]] = None


def process_entry(entry: Entry, *, run_dir: Path, vtt_dir: Optional[Path], text_dir: Path,
                  want_vtt: bool, want_text: bool, skip_video: bool,
                  numbered: bool, width: int) -> ItemResult:
    item = ItemResult(entry, problems=[])
    if not skip_video:
        item.video = find_file(run_dir, entry.video_id, VIDEO_EXTENSIONS)
        if item.video is None:
            item.problems.append("video was not downloaded")
    if want_vtt or want_text:
        item.vtt = find_file(vtt_dir, entry.video_id, (f"{LANGUAGE}.vtt",))
        if item.vtt is None:
            item.problems.append(f"no {LANGUAGE.upper()} subtitles available")
        elif want_text:
            base = clean_filename(entry.title)
            if numbered:
                base = f"{entry.index:0{width}d} - {base}"
            try:
                item.text = write_text_files(item.vtt, text_dir, base)
            except Exception as exc:
                item.problems.append(f"could not create the text file ({exc})")
    return item


def _short(path: Optional[Path], base: Path) -> str:
    if path is None:
        return "-"
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def print_playlist_line(item: ItemResult, total: int, want_vtt: bool, want_text: bool, skip_video: bool) -> None:
    say(f"[{item.entry.index}/{total}] {item.entry.title}")
    parts = []
    if not skip_video:
        parts.append("video " + ("OK" if item.video else "MISSING"))
    if want_vtt:
        parts.append("subtitles " + ("OK" if item.vtt else "MISSING"))
    if want_text:
        parts.append("text " + (f"OK ({item.text.chars:,} chars, ~{item.text.tokens:,} tokens)" if item.text else "MISSING"))
    say("    " + " | ".join(parts))
    for problem in item.problems or []:
        say(f"    ! {problem}")


def print_single_result(item: ItemResult, run_dir: Path, want_vtt: bool, want_text: bool, skip_video: bool) -> None:
    say("=" * 60)
    say(item.entry.title)
    say("=" * 60)
    say(f"Folder: {run_dir}")
    if not skip_video:
        say(f"  Video      : {_short(item.video, run_dir)}")
    if want_vtt:
        say(f"  Subtitles  : {_short(item.vtt, run_dir)}")
    if want_text:
        say(f"  Text       : {_short(item.text.text_file if item.text else None, run_dir)}")
        if item.text and item.text.raw_file:
            say(f"  Raw text   : {_short(item.text.raw_file, run_dir)}")
    for problem in item.problems or []:
        say(f"  ! {problem}")
    if item.text:
        t = item.text
        say()
        say("Statistics:")
        say(f"   - {t.entries:,} subtitle entries processed")
        say(f"   - {t.raw_bytes:,} bytes in raw format")
        say(f"   - {t.text_bytes:,} bytes in optimized format")
        say(f"   - {t.reduction:.1f}% size reduction")
        say(f"   - {t.chars:,} characters for AI model")
        say(f"   - ~{t.tokens:,} estimated tokens for AI model")


def handle_url(ytdlp: List[str], user_input: str, skip_video: bool) -> None:
    target = resolve_target(user_input)
    if target is None:
        say("\nThat doesn't look like a YouTube video or playlist link. Examples:")
        say("  https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        say("  https://youtu.be/dQw4w9WgXcQ")
        say("  https://www.youtube.com/playlist?list=PLxxxxxxxxxxxxxxxx")
        return

    say()
    want_vtt = ask_yes_no("Do you want the subtitle file (.vtt)?")
    want_text = ask_yes_no("Do you want the text file (.txt) for your AI model?")
    if skip_video and not (want_vtt or want_text):
        say("\nNothing to do: no video, no subtitle file and no text file.")
        return

    say()
    try:
        with Step("Checking the link"):
            info = probe(ytdlp, target)
    except YtDlpError as exc:
        say(f"Error: {exc}")
        return
    if target.kind == "video":
        say(f"Video found: {info.title}")
    else:
        say(f"Playlist found: {info.title} ({len(info.entries)} videos)")

    run_dir = OUTPUT_ROOT if target.kind == "video" else OUTPUT_ROOT / clean_filename(info.title)
    text_dir = run_dir / "text"
    run_dir.mkdir(parents=True, exist_ok=True)
    say(f"Saving to: {run_dir}")
    say()

    need_subs = want_vtt or want_text
    # Subtitles you did not ask for are fetched into a throw-away folder (only needed for the text).
    temp_dir = Path(tempfile.mkdtemp(prefix="downtube_")) if (need_subs and not want_vtt) else None
    vtt_dir = run_dir if want_vtt else temp_dir
    numbered = target.kind == "playlist"
    width = len(str(info.total))
    results: List[ItemResult] = []
    try:
        code = run_download(ytdlp, target, run_dir, need_subs, temp_dir, skip_video)
        say()
        if code != 0:
            say(f"yt-dlp finished with errors (exit code {code}). Checking what was saved...")
            say()
        for entry in info.entries:
            item = process_entry(entry, run_dir=run_dir, vtt_dir=vtt_dir, text_dir=text_dir,
                                 want_vtt=want_vtt, want_text=want_text, skip_video=skip_video,
                                 numbered=numbered, width=width)
            results.append(item)
            if numbered:
                print_playlist_line(item, len(info.entries), want_vtt, want_text, skip_video)
    finally:
        if temp_dir is not None:
            shutil.rmtree(temp_dir, ignore_errors=True)

    if numbered:
        say()
        say("=" * 60)
        say(f"Finished: {len(results)} videos | "
            f"{sum(1 for r in results if r.video)} downloaded | "
            f"{sum(1 for r in results if r.vtt and want_vtt)} subtitle files | "
            f"{sum(1 for r in results if r.text)} text files")
        say(f"Folder: {run_dir}")
        if want_text:
            say(f"Text files: {text_dir}")
    else:
        print_single_result(results[0], run_dir, want_vtt, want_text, skip_video)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Download a YouTube video or playlist and turn its subtitles into AI-ready text.")
    parser.add_argument("--no-video", action="store_true",
                        help="skip the video download; only fetch the subtitle / text files")
    args = parser.parse_args(argv)

    configure_console()
    say("=" * 60)
    say("YouTube Downloader + Subtitle Text".center(60))
    say("=" * 60)

    ytdlp = find_ytdlp()
    version = ytdlp_version(ytdlp) if ytdlp else None
    if version is None:
        say("\nError: yt-dlp is not installed or not accessible in PATH.")
        say("Install it with: pip install -U yt-dlp   (or put yt-dlp.exe in a folder on PATH)")
        return 1
    say(f"Using yt-dlp version: {version}")
    say(f"Files are saved in: {OUTPUT_ROOT}")

    while True:
        say("\nPaste a YouTube video or playlist link (press Enter to quit).")
        try:
            text = ask("> ")
        except KeyboardInterrupt:
            break
        if not text:
            break
        try:
            handle_url(ytdlp, text, args.no_video)
        except KeyboardInterrupt:
            say("\n\nCancelled.")
        except Exception as exc:  # keep the app alive, show what happened
            say(f"\nUnexpected error: {exc!r}")

    say("\nBye.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
