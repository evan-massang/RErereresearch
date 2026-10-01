"""Frame and clip extraction for an ingested video source."""

from __future__ import annotations

from pathlib import Path

import duckdb

from . import config, db, media
from .ids import stable_id
from .ingest_transcript import find_media
from .provenance import register_artifact, sha256_file, tracked


def _store_frame(con, source_id: str, ts: float, method: str, path: Path, *,
                 anchor_s: float | None = None, scene_score: float | None = None) -> str:
    frame_id = stable_id("frm", source_id, round(ts * 1000), method)
    final = path.with_name(f"t{round(ts * 1000):010d}_{method}.jpg")
    if final != path:
        path.replace(final)
    w, h = media.image_size(final)
    db.upsert(con, "frames", {
        "frame_id": frame_id, "source_id": source_id, "timestamp_s": ts, "method": method,
        "local_path": config.rel(final), "sha256": sha256_file(final),
        "width": w, "height": h, "anchor_s": anchor_s, "scene_score": scene_score, "created_at": db.now(),
    })
    return frame_id


def window_timestamps(anchor_s: float, *, before: float, after: float, step: float,
                      dense_radius: float, dense_step: float, duration: float | None = None) -> list[float]:
    """Regular grid over [anchor-before, anchor+after] plus a denser grid close to the anchor."""
    if step <= 0 or dense_step <= 0:
        raise ValueError("steps must be positive")
    pts = set()
    t = anchor_s - before
    while t <= anchor_s + after + 1e-9:
        pts.add(round(t, 3))
        t += step
    t = anchor_s - dense_radius
    while t <= anchor_s + dense_radius + 1e-9:
        pts.add(round(t, 3))
        t += dense_step
    pts.add(round(anchor_s, 3))
    hi = (duration - 0.05) if duration else float("inf")
    return sorted(p for p in pts if 0 <= p <= hi)


def extract_decision_window(
    con: duckdb.DuckDBPyConnection,
    source_id: str,
    anchor_s: float,
    *,
    before: float = 12.0,
    after: float = 18.0,
    step: float = 2.0,
    dense_radius: float = 4.0,
    dense_step: float = 0.5,
    adaptive: bool = True,
    change_threshold: float = 0.03,
    sample_fps: float = 4.0,
    max_frames: int = 150,
    width: int | None = None,
    media_path: Path | str | None = None,
) -> list[str]:
    """Frames before, at and after a decision, densified wherever the screen changes quickly.

    Inspect the frames *before* the decision to see what the trader saw, and
    after it to see what they did next. With ``adaptive``, any sampled moment
    whose visual change score exceeds ``change_threshold`` is added too.
    """
    src = Path(media_path) if media_path else find_media(con, source_id)
    if not media.has_video_stream(src):
        raise ValueError(f"{src} has no video stream (audio-only media?)")
    duration = media.duration_s(src)
    planned: dict[float, float | None] = {t: None for t in window_timestamps(
        anchor_s, before=before, after=after, step=step, dense_radius=dense_radius,
        dense_step=dense_step, duration=duration)}
    if adaptive:
        for t, score in media.scene_scores(src, anchor_s - before, anchor_s + after, fps=sample_fps):
            if score >= change_threshold and (duration is None or t < duration):
                planned[round(t, 3)] = max(score, planned.get(round(t, 3)) or 0.0)
    times = sorted(planned)
    if len(times) > max_frames:   # keep the anchor neighbourhood and the change points, thin the rest
        keep = {t for t in times if abs(t - anchor_s) <= dense_radius or planned[t] is not None}
        rest = [t for t in times if t not in keep]
        stride = max(1, len(rest) // max(1, max_frames - len(keep)))
        times = sorted(keep | set(rest[::stride]))[:max_frames]
    out_dir = config.path("frames", source_id)
    ids = []
    with tracked(con, stage="frames", adapter="ffmpeg", uri=str(src), source_id=source_id) as ev:
        for ts in times:
            tmp = out_dir / f"_tmp_{round(ts * 1000)}.jpg"
            media.extract_frame(src, tmp, ts, width)
            ids.append(_store_frame(con, source_id, ts, "window", tmp, anchor_s=anchor_s, scene_score=planned[ts]))
        ev.details = {"method": "window", "anchor_s": anchor_s, "count": len(ids),
                      "adaptive_added": sum(1 for t in times if planned[t] is not None)}
    return ids


def extract_frames(
    con: duckdb.DuckDBPyConnection,
    source_id: str,
    *,
    timestamps: list[float] | None = None,
    every_s: float | None = None,
    scene_threshold: float | None = None,
    start_s: float = 0.0,
    end_s: float | None = None,
    max_frames: int | None = None,
    width: int | None = None,
    media_path: Path | str | None = None,
) -> list[str]:
    """Extract stills by explicit timestamps, a fixed interval, or scene changes."""
    if sum(x is not None for x in (timestamps, every_s, scene_threshold)) != 1:
        raise ValueError("pass exactly one of timestamps, every_s, scene_threshold")
    src = Path(media_path) if media_path else find_media(con, source_id)
    if not media.has_video_stream(src):
        raise ValueError(f"{src} has no video stream (audio-only media?)")
    out_dir = config.path("frames", source_id)
    frame_ids: list[str] = []
    with tracked(con, stage="frames", adapter="ffmpeg", uri=str(src), source_id=source_id) as ev:
        if scene_threshold is not None:
            method = "scene"
            for ts, path in media.extract_scene_frames(src, out_dir, scene_threshold, width)[:max_frames]:
                frame_ids.append(_store_frame(con, source_id, ts, method, path))
            for leftover in out_dir.glob("_scene_*.jpg"):   # beyond max_frames
                leftover.unlink()
        else:
            if every_s is not None:
                method = "interval"
                stop = end_s if end_s is not None else (media.duration_s(src) or 0.0)
                n = int(max(0.0, stop - start_s) // every_s) + 1
                timestamps = [start_s + i * every_s for i in range(n)]
                timestamps = [t for t in timestamps if t < stop] or [start_s]
            else:
                method = "timestamp"
            for ts in timestamps[:max_frames] if max_frames else timestamps:
                tmp = out_dir / f"_tmp_{round(ts * 1000)}.jpg"
                media.extract_frame(src, tmp, ts, width)
                frame_ids.append(_store_frame(con, source_id, ts, method, tmp))
        ev.details = {"method": method, "count": len(frame_ids)}
    return frame_ids


def extract_clip(con: duckdb.DuckDBPyConnection, source_id: str, start_s: float, end_s: float,
                 media_path: Path | str | None = None) -> str:
    src = Path(media_path) if media_path else find_media(con, source_id)
    out = config.path("clips", source_id) / f"{round(start_s * 1000):010d}-{round(end_s * 1000):010d}.mp4"
    with tracked(con, stage="clip", adapter="ffmpeg", uri=str(src), source_id=source_id):
        media.extract_clip(src, out, start_s, end_s)
        return register_artifact(con, source_id, "clip", out,
                                 details={"start_s": start_s, "end_s": end_s})
