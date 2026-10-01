"""FFmpeg/ffprobe wrappers (no database access; pure file in -> file out)."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .provenance import SourceUnavailable


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=True)
    except FileNotFoundError as e:
        raise SourceUnavailable(f"{cmd[0]} is not installed (run scripts/setup.sh)", status="error") from e
    except subprocess.CalledProcessError as e:
        tail = (e.stderr or "").strip().splitlines()[-5:]
        raise SourceUnavailable(f"{cmd[0]} failed: {' | '.join(tail)}", status="error") from e


def ffprobe(path: Path | str) -> dict:
    out = _run(["ffprobe", "-v", "error", "-print_format", "json",
                "-show_format", "-show_streams", str(path)]).stdout
    return json.loads(out)


def duration_s(path: Path | str) -> float | None:
    d = ffprobe(path).get("format", {}).get("duration")
    return float(d) if d is not None else None


def has_video_stream(path: Path | str) -> bool:
    return any(s.get("codec_type") == "video" for s in ffprobe(path).get("streams", []))


def image_size(path: Path | str) -> tuple[int | None, int | None]:
    for s in ffprobe(path).get("streams", []):
        if s.get("codec_type") == "video":
            return s.get("width"), s.get("height")
    return None, None


def extract_audio(src: Path | str, out: Path | str, sample_rate: int = 16000) -> Path:
    """Mono 16-bit PCM WAV — the input format ASR models expect."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    _run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", str(src), "-vn",
          "-ac", "1", "-ar", str(sample_rate), "-c:a", "pcm_s16le", str(out)])
    return out


def extract_clip(src: Path | str, out: Path | str, start_s: float, end_s: float, reencode: bool = True) -> Path:
    if end_s <= start_s:
        raise ValueError("end_s must be greater than start_s")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    codec = ["-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac"] if reencode else ["-c", "copy"]
    _run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-ss", f"{start_s:.3f}", "-i", str(src),
          "-t", f"{end_s - start_s:.3f}", *codec, str(out)])
    return out


def extract_frame(src: Path | str, out: Path | str, timestamp_s: float, width: int | None = None) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    vf = ["-vf", f"scale={width}:-2"] if width else []
    _run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-ss", f"{timestamp_s:.3f}", "-i", str(src),
          "-frames:v", "1", *vf, "-q:v", "2", str(out)])
    if not out.exists():
        raise SourceUnavailable(f"no frame at {timestamp_s:.3f}s (past end of stream?)", status="error")
    return out


_PTS_RE = re.compile(r"pts_time:([0-9.]+)")


def extract_scene_frames(src: Path | str, out_dir: Path | str, threshold: float = 0.3,
                         width: int | None = None) -> list[tuple[float, Path]]:
    """Frames where the picture changes by more than `threshold` (0–1)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp_pattern = out_dir / "_scene_%06d.jpg"
    scale = f",scale={width}:-2" if width else ""
    proc = _run(["ffmpeg", "-nostdin", "-y", "-v", "info", "-i", str(src),
                 "-vf", f"select='gt(scene,{threshold})',showinfo{scale}",
                 "-fps_mode", "vfr", "-q:v", "2", str(tmp_pattern)])
    times = [float(m) for m in _PTS_RE.findall(proc.stderr)]
    files = sorted(out_dir.glob("_scene_*.jpg"))
    return list(zip(times, files))


_SCORE_RE = re.compile(r"lavfi\.scene_score=([0-9.]+)")


def scene_scores(src: Path | str, start_s: float, end_s: float, fps: float = 4.0) -> list[tuple[float, float]]:
    """Visual change score (0-1) between consecutive sampled frames in [start_s, end_s).

    Trading UIs change constantly in small ways (ticking numbers), so useful
    thresholds are much lower than for film cuts; calibrate on real footage.
    """
    if end_s <= start_s:
        return []
    base = max(0.0, start_s)
    proc = _run(["ffmpeg", "-nostdin", "-v", "info", "-ss", f"{base:.3f}", "-t", f"{end_s - base:.3f}",
                 "-i", str(src), "-vf", f"fps={fps},select='gte(scene,0)',metadata=print",
                 "-an", "-f", "null", "-"])
    times = [float(m) for m in _PTS_RE.findall(proc.stderr)]
    scores = [float(m) for m in _SCORE_RE.findall(proc.stderr)]
    if len(times) != len(scores):
        raise SourceUnavailable("could not align ffmpeg scene scores with timestamps", status="error")
    return [(round(base + t, 3), sc) for t, sc in zip(times, scores) if base + t < end_s]
