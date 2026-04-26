#!/usr/bin/env python3
"""
youtube-reference.py — pull a YouTube video's frames + auto-captions
into a folder so the AI can read them as visual reference for animation
work (Remotion, etc.).

Why this exists
---------------
The model can't watch video. To use a YouTube clip as a reference for
"make our pitch video look like THIS", we need stills + transcript.
This script:

  1. Fetches video metadata (title, duration, channel)
  2. Downloads the auto-generated captions (.vtt → flat text)
  3. Extracts a still PNG every N seconds (default 2s)
  4. Writes a manifest.txt the AI can Read first to orient

Output layout:
  tmp/youtube-ref/<video-id>/
    metadata.txt      title / channel / duration / url
    transcript.txt    flat plaintext, one cue per line with [mm:ss]
    manifest.txt      one row per frame: filename + timestamp
    frames/0001.png   1920×1080 keyframe @ t=0s
    frames/0002.png   @ t=2s
    ...

Usage:
  python youtube-reference.py <youtube-url> [--interval=2] [--out=DIR]

Requires:
  - yt-dlp (installed in the django_backend venv)
  - ffmpeg (Playwright bundles one — auto-detected)

Re-runnable. If the video-id folder exists it gets overwritten so you
can re-run with a different --interval without leftovers.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUT = REPO_ROOT / "tmp" / "youtube-ref"

# yt-dlp + ffmpeg discovery. Both are non-PATH on this machine; we
# probe the common install locations.
def _find_executable(name: str, candidates: list[Path]) -> Path:
    for p in candidates:
        if p.exists():
            return p
    raise SystemExit(
        f"Could not find {name}. Tried: {[str(c) for c in candidates]}"
    )


def find_yt_dlp() -> Path:
    return _find_executable("yt-dlp", [
        REPO_ROOT / "django_backend" / "venv" / "Scripts" / "yt-dlp.exe",
        REPO_ROOT / "django_backend" / "venv" / "bin" / "yt-dlp",
        Path(shutil.which("yt-dlp") or "/dev/null"),
    ])


def find_ffmpeg() -> Path:
    """Locate a usable ffmpeg. Playwright bundles a stripped-down build
    that can't decode YouTube's modern MP4s, so prefer imageio-ffmpeg's
    full binary first."""
    # imageio-ffmpeg is the most reliable fallback: pip install
    # imageio-ffmpeg ships a full v7+ binary that handles every codec
    # YouTube might serve.
    try:
        import imageio_ffmpeg  # type: ignore
        candidate = Path(imageio_ffmpeg.get_ffmpeg_exe())
        if candidate.exists():
            return candidate
    except ImportError:
        pass
    home = Path.home()
    return _find_executable("ffmpeg", [
        Path(shutil.which("ffmpeg") or "/dev/null"),
        home / "AppData/Local/ms-playwright/ffmpeg-1011/ffmpeg-win64.exe",
    ])


def parse_video_id(url: str) -> str:
    """Extract the YouTube video ID from any reasonable URL form."""
    parsed = urlparse(url)
    if parsed.netloc.endswith("youtu.be"):
        return parsed.path.lstrip("/").split("/")[0]
    qs = parse_qs(parsed.query)
    if "v" in qs:
        return qs["v"][0]
    # /shorts/<id> or /embed/<id>
    parts = [p for p in parsed.path.split("/") if p]
    if parts:
        return parts[-1]
    raise SystemExit(f"Could not parse video id from {url!r}")


def fetch_metadata(yt_dlp: Path, url: str) -> dict:
    """Get title / channel / duration in one yt-dlp call."""
    proc = subprocess.run(
        [str(yt_dlp), "--dump-single-json", "--skip-download", url],
        capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode != 0:
        raise SystemExit(f"yt-dlp metadata failed: {proc.stderr[:500]}")
    return json.loads(proc.stdout)


def download_video(yt_dlp: Path, url: str, out_path: Path) -> Path:
    """Download a 720p MP4 (faster than 1080p, plenty for stills)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            str(yt_dlp),
            "-f", "best[height<=720][ext=mp4]/best[height<=720]/best",
            "-o", str(out_path),
            "--no-warnings",
            url,
        ],
        capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode != 0:
        raise SystemExit(f"yt-dlp download failed: {proc.stderr[:500]}")
    return out_path


def download_captions(yt_dlp: Path, url: str, out_dir: Path) -> Path | None:
    """Download auto-generated English captions as VTT.
    Returns path to the .vtt or None if no captions available."""
    out_dir.mkdir(parents=True, exist_ok=True)
    template = str(out_dir / "captions.%(ext)s")
    proc = subprocess.run(
        [
            str(yt_dlp),
            "--skip-download",
            "--write-auto-subs",
            "--sub-lang", "en,en-orig,en-US",
            "--sub-format", "vtt",
            "-o", template,
            url,
        ],
        capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode != 0:
        # Captions are best-effort — don't fail the whole run.
        print(f"  [warn] captions failed: {proc.stderr[:200].strip()}")
        return None
    # yt-dlp writes captions.<lang>.vtt — find it.
    for f in sorted(out_dir.glob("captions*.vtt")):
        return f
    return None


_TIMECODE = re.compile(
    r"^(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2})\.\d+ --> "
)


def vtt_to_flat_text(vtt: Path) -> str:
    """Strip the WebVTT cue formatting and return one cue per line as
    `[mm:ss] text`. Drops duplicate consecutive lines (auto-captions
    often repeat the same phrase across cues as the speaker continues)."""
    lines: list[tuple[int, str]] = []
    last_text = ""
    current_ts: int | None = None
    with vtt.open("r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            m = _TIMECODE.match(line)
            if m:
                h, mm, ss = int(m["h"]), int(m["m"]), int(m["s"])
                current_ts = h * 3600 + mm * 60 + ss
                continue
            if not line.strip() or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
                continue
            # Strip karaoke-style <c>tags</c> and timecode pills.
            text = re.sub(r"<[^>]+>", "", line).strip()
            if not text or text == last_text:
                continue
            last_text = text
            if current_ts is not None:
                lines.append((current_ts, text))
    if not lines:
        return ""
    out = []
    for ts, text in lines:
        m, s = divmod(ts, 60)
        out.append(f"[{m:02d}:{s:02d}] {text}")
    return "\n".join(out) + "\n"


def extract_frames(
    ffmpeg: Path, video_path: Path, frames_dir: Path, interval: float
) -> int:
    """Extract one frame every `interval` seconds. Returns the count."""
    frames_dir.mkdir(parents=True, exist_ok=True)
    out_pattern = str(frames_dir / "%04d.png")
    # -vf "fps=1/2" → one frame every 2 seconds. "select" with a
    # mod-on-pts expression would also work but fps= is simpler.
    fps_expr = f"fps=1/{interval}"
    proc = subprocess.run(
        [
            str(ffmpeg),
            "-y", "-loglevel", "error",
            "-i", str(video_path),
            "-vf", fps_expr,
            "-vsync", "0",
            out_pattern,
        ],
        capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode != 0:
        raise SystemExit(f"ffmpeg failed: {proc.stderr[:500]}")
    count = len(list(frames_dir.glob("*.png")))
    return count


def write_manifest(
    out_dir: Path,
    metadata: dict,
    frame_count: int,
    interval: float,
    transcript_present: bool,
) -> None:
    title = metadata.get("title", "(unknown)")
    channel = metadata.get("uploader") or metadata.get("channel") or "(unknown)"
    duration_s = metadata.get("duration") or 0
    mins, secs = divmod(int(duration_s), 60)

    metadata_md = (
        f"title:    {title}\n"
        f"channel:  {channel}\n"
        f"duration: {mins:02d}:{secs:02d}  ({duration_s} seconds)\n"
        f"url:      {metadata.get('webpage_url', '(unknown)')}\n"
        f"video_id: {metadata.get('id', '(unknown)')}\n"
    )
    (out_dir / "metadata.txt").write_text(metadata_md, encoding="utf-8")

    manifest_lines = [
        "# Frame manifest — one PNG per row, with the source timestamp.",
        f"# Interval: {interval}s  ·  Total frames: {frame_count}  ·  Video: {duration_s}s",
        "",
    ]
    for i in range(1, frame_count + 1):
        ts = (i - 1) * interval
        m, s = divmod(int(ts), 60)
        manifest_lines.append(f"frames/{i:04d}.png  [{m:02d}:{s:02d}]")
    (out_dir / "manifest.txt").write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

    print("")
    print(f"  -> metadata.txt   ({title[:60]})")
    if transcript_present:
        print(f"  -> transcript.txt (auto-captions)")
    print(f"  -> manifest.txt   ({frame_count} frames @ every {interval}s)")
    print(f"  -> frames/        {frame_count} x .png")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("url", help="YouTube URL")
    ap.add_argument(
        "--interval", type=float, default=2.0,
        help="Seconds between frames (default 2). Lower = more frames "
             "= more reference but more storage.",
    )
    ap.add_argument(
        "--out", default=str(DEFAULT_OUT),
        help=f"Output base directory (default {DEFAULT_OUT}). The video-id "
             "subfolder is created/overwritten under this.",
    )
    args = ap.parse_args()

    yt_dlp = find_yt_dlp()
    ffmpeg = find_ffmpeg()
    video_id = parse_video_id(args.url)
    out_dir = Path(args.out) / video_id
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    print(f"YouTube reference extraction")
    print(f"  url:       {args.url}")
    print(f"  video_id:  {video_id}")
    print(f"  out:       {out_dir}")
    print(f"  interval:  {args.interval}s")
    print("")

    print("[1/4] Fetching metadata...")
    metadata = fetch_metadata(yt_dlp, args.url)

    print("[2/4] Downloading captions (best effort)...")
    vtt = download_captions(yt_dlp, args.url, out_dir)
    transcript_present = False
    if vtt:
        flat = vtt_to_flat_text(vtt)
        if flat.strip():
            (out_dir / "transcript.txt").write_text(flat, encoding="utf-8")
            transcript_present = True
        # Keep the raw .vtt too in case the user wants timestamps with sub-second precision.

    print("[3/4] Downloading video (<=720p, mp4)...")
    video_path = out_dir / "video.mp4"
    download_video(yt_dlp, args.url, video_path)

    print(f"[4/4] Extracting frames every {args.interval}s...")
    frame_count = extract_frames(ffmpeg, video_path, out_dir / "frames", args.interval)

    write_manifest(out_dir, metadata, frame_count, args.interval, transcript_present)

    # Optional cleanup: keep the .mp4 around so re-runs with a different
    # interval can re-extract without re-downloading. Disk cost ~50MB
    # per typical product video — fine for a dev machine.
    print("")
    print(f"Done. Tell the AI: read {out_dir.relative_to(REPO_ROOT)}/manifest.txt first.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        sys.exit(130)
