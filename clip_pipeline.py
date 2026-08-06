"""
clip_pipeline.py

End-to-end pipeline: feed it a YouTube URL, it will:
  1. Download the video (yt-dlp)
  2. Transcribe it with word-level timestamps (faster-whisper, runs locally)
  3. Ask Claude to split the transcript into natural "Part 1 / Part 2 / ..."
     break points (topic changes, cliffhangers, case transitions)
  4. Extract each part as its own video file (ffmpeg)
  5. Optionally produce a 9:16 vertical crop of each part for Shorts

Requirements:
    pip install yt-dlp faster-whisper anthropic --break-system-packages
    ffmpeg must be installed and on PATH (not a pip package)

Environment:
    ANTHROPIC_API_KEY must be set in your environment

Usage:
    python clip_pipeline.py "https://www.youtube.com/watch?v=XXXXXXXX"
    python clip_pipeline.py "<url>" --vertical           # also produce 9:16 crops
    python clip_pipeline.py "<url>" --part-length 10      # target ~10 min parts
    python clip_pipeline.py "<url>" --whisper-model small # faster, less accurate

NOTE ON LEGALITY:
    Downloading video via yt-dlp is against YouTube's Terms of Service,
    independent of any copyright question about the content itself. This
    script does not change or bypass that -- it's a plain wrapper around
    yt-dlp/whisper/ffmpeg. Decide source-by-source whether that's a risk
    you're comfortable with; using a channel's official RSS/podcast feed
    (where one exists) avoids this specific issue.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yt_dlp
from faster_whisper import WhisperModel
from anthropic import Anthropic


# ----------------------------------------------------------------------
# 1. Download
# ----------------------------------------------------------------------

def download_video(url: str, out_dir: Path) -> Path:
    """Download best available <=1080p video+audio, merged to mp4."""
    out_template = str(out_dir / "source.%(ext)s")
    ydl_opts = {
        "format": "bestvideo[height<=1080]+bestaudio/best",
        "outtmpl": out_template,
        "merge_output_format": "mp4",
        "quiet": False,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    # yt-dlp names the final merged file source.mp4 given merge_output_format
    source_path = out_dir / "source.mp4"
    if not source_path.exists():
        # fallback: find whatever got created
        candidates = list(out_dir.glob("source.*"))
        if not candidates:
            raise FileNotFoundError("Download finished but no output file found.")
        source_path = candidates[0]
    return source_path


# ----------------------------------------------------------------------
# 2. Transcribe
# ----------------------------------------------------------------------

def transcribe(video_path: Path, model_size: str = "medium.en"):
    """
    Returns list of (start_seconds, end_seconds, text) tuples.
    Uses CPU by default; change device="cuda" if you have a GPU set up.
    """
    model = WhisperModel(model_size, device="auto", compute_type="auto")
    segments, _info = model.transcribe(
        str(video_path), word_timestamps=True, vad_filter=True
    )
    transcript = [(seg.start, seg.end, seg.text.strip()) for seg in segments]
    return transcript


def transcript_to_text_block(transcript, max_chars: int = 60000) -> str:
    """
    Flatten transcript into '[123s] text' lines for the LLM prompt.
    Truncates if it would blow past a sane prompt size (long-form videos
    can run multiple hours -- 60k chars is a generous safety cap).
    """
    lines = []
    total = 0
    for start, _end, text in transcript:
        line = f"[{int(start)}s] {text}"
        total += len(line)
        if total > max_chars:
            lines.append("...[transcript truncated for length]...")
            break
        lines.append(line)
    return "\n".join(lines)


# ----------------------------------------------------------------------
# 3. Detect natural part breaks via Claude
# ----------------------------------------------------------------------

def detect_parts(transcript, target_minutes: int = 10, video_duration_s: float = None):
    """
    Asks Claude to split the transcript into sequential parts at natural
    narrative breaks rather than fixed intervals. Returns a list of dicts:
        [{"start": 0, "end": 612, "title": "..."}, ...]
    """
    client = Anthropic()  # reads ANTHROPIC_API_KEY from env
    transcript_block = transcript_to_text_block(transcript)

    duration_note = (
        f"The video is approximately {int(video_duration_s // 60)} minutes long. "
        if video_duration_s
        else ""
    )

    prompt = f"""Here is a timestamped transcript of a long-form YouTube video.
{duration_note}Split it into sequential parts of roughly {target_minutes} minutes
each, but adjust each boundary to land on a natural narrative break (topic
change, cliffhanger, case/section transition) rather than an arbitrary time
cutoff. Every part must be sequential and non-overlapping, and together they
should cover the full video from 0 to the end.

Respond with ONLY valid JSON, no other text, no markdown fences, in this
exact shape:
[
  {{"start": 0, "end": 615, "title": "Short descriptive title for this part"}},
  {{"start": 615, "end": 1204, "title": "..."}}
]

Transcript:
{transcript_block}"""

    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()

    # Defensive parsing: strip accidental code fences if the model adds them
    raw_text = re.sub(r"^```(json)?|```$", "", raw_text.strip(), flags=re.MULTILINE).strip()

    try:
        parts = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Could not parse part-split response as JSON: {e}\nRaw response:\n{raw_text}"
        )

    return parts


# ----------------------------------------------------------------------
# 4. Extract each part with ffmpeg
# ----------------------------------------------------------------------

def extract_part(source: Path, start: float, end: float, out_path: Path):
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(source),
            "-ss", str(start),
            "-to", str(end),
            "-c:v", "libx264",
            "-c:a", "aac",
            str(out_path),
        ],
        check=True,
    )


def reframe_vertical(source: Path, out_path: Path):
    """
    Naive center-crop to 9:16. Fine for single-speaker/static layouts.
    For multi-person or graphics-heavy sources you'd want a face-tracking
    crop instead -- ask if you need that added.
    """
    vf = "crop=ih*9/16:ih:(iw-ih*9/16)/2:0"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(source),
            "-vf", vf,
            "-c:a", "copy",
            str(out_path),
        ],
        check=True,
    )


# ----------------------------------------------------------------------
# 5. Orchestration
# ----------------------------------------------------------------------

def sanitize_filename(name: str) -> str:
    return re.sub(r"[^\w\-]+", "_", name).strip("_")[:60]


def run_pipeline(url: str, target_minutes: int, whisper_model: str, make_vertical: bool, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)

    print("[1/4] Downloading video...")
    source_path = download_video(url, out_dir)

    print("[2/4] Transcribing (this can take a while on CPU)...")
    transcript = transcribe(source_path, model_size=whisper_model)
    video_duration = transcript[-1][1] if transcript else None

    print("[3/4] Asking Claude for natural part breaks...")
    parts = detect_parts(transcript, target_minutes=target_minutes, video_duration_s=video_duration)

    print(f"[4/4] Extracting {len(parts)} part(s)...")
    parts_dir = out_dir / "parts"
    parts_dir.mkdir(exist_ok=True)
    manifest = []

    for i, part in enumerate(parts, start=1):
        title_slug = sanitize_filename(part.get("title", f"part_{i}"))
        filename = f"part_{i:02d}_{title_slug}.mp4"
        out_path = parts_dir / filename

        print(f"  - Part {i}: {part['start']}s - {part['end']}s :: {part.get('title')}")
        extract_part(source_path, part["start"], part["end"], out_path)

        entry = {
            "part": i,
            "title": part.get("title"),
            "start": part["start"],
            "end": part["end"],
            "file": str(out_path),
        }

        if make_vertical:
            vertical_path = parts_dir / f"part_{i:02d}_{title_slug}_vertical.mp4"
            reframe_vertical(out_path, vertical_path)
            entry["vertical_file"] = str(vertical_path)

        manifest.append(entry)

    manifest_path = out_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nDone. {len(parts)} part(s) written to {parts_dir}")
    print(f"Manifest: {manifest_path}")
    return manifest


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Download, transcribe, and part-split a YouTube video.")
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("--part-length", type=int, default=10, help="Target minutes per part (default: 10)")
    parser.add_argument("--whisper-model", default="medium.en", help="faster-whisper model size (default: medium.en)")
    parser.add_argument("--vertical", action="store_true", help="Also produce 9:16 vertical crops of each part")
    parser.add_argument("--out-dir", default="./output", help="Output directory (default: ./output)")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    run_pipeline(
        url=args.url,
        target_minutes=args.part_length,
        whisper_model=args.whisper_model,
        make_vertical=args.vertical,
        out_dir=Path(args.out_dir),
    )


if __name__ == "__main__":
    main()
