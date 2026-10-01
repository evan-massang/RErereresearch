"""Subtitle/transcript ingestion and speech-to-text.

Three ways a transcript enters the archive, all landing in the same tables:
  * platform captions fetched by a video adapter (method platform_manual / platform_auto)
  * an existing caption/transcript file you supply (method imported)
  * speech-to-text on the media (method asr) via a pluggable Transcriber
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

import duckdb

from . import config, db, media
from .ids import stable_id
from .provenance import SourceUnavailable, register_artifact, tracked


@dataclass
class Segment:
    start_s: float | None
    end_s: float | None
    text: str
    avg_logprob: float | None = None


# ---------------------------------------------------------------- parsing

_TS = r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})"
_CUE_RE = re.compile(rf"{_TS}\s*-->\s*{_TS}")
_TAG_RE = re.compile(r"<[^>]+>")


def _secs(h, m, s, ms) -> float:
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000


def _clean(line: str) -> str:
    return html.unescape(_TAG_RE.sub("", line)).strip()


def parse_cues(text: str) -> list[Segment]:
    """Parse WebVTT or SRT. Rolling auto-caption duplicates are collapsed."""
    segments: list[Segment] = []
    recent: list[str] = []          # last emitted lines, to drop roll-up repeats
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n").replace("\r", "\n")):
        lines = [l for l in block.strip().split("\n") if l.strip()]
        idx = next((i for i, l in enumerate(lines) if "-->" in l), None)
        if idx is None:
            continue                 # header, NOTE, STYLE, REGION blocks
        m = _CUE_RE.search(lines[idx])
        if not m:
            continue
        g = m.groups()
        start, end = _secs(*g[:4]), _secs(*g[4:])
        new_lines = []
        for raw in lines[idx + 1:]:
            line = _clean(raw)
            if not line or line in recent:
                continue
            new_lines.append(line)
            recent = (recent + [line])[-3:]
        if new_lines:
            segments.append(Segment(start, end, " ".join(new_lines)))
    return segments


def parse_plain_text(text: str) -> list[Segment]:
    """Untimed transcript: one segment per non-empty paragraph."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return [Segment(None, None, " ".join(p.split())) for p in paras]


def load_transcript_file(path: Path | str) -> list[Segment]:
    path = Path(path)
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    suffix = path.suffix.lower()
    if suffix in {".vtt", ".srt"}:
        return parse_cues(text)
    if suffix == ".json":
        data = json.loads(text)
        items = data.get("segments", data) if isinstance(data, dict) else data
        return [Segment(i.get("start_s", i.get("start")), i.get("end_s", i.get("end")),
                        i["text"].strip(), i.get("avg_logprob")) for i in items]
    return parse_plain_text(text)


# ---------------------------------------------------------------- storage

def _store(con, *, transcript_id: str, source_id: str, method: str, language: str | None,
           model: str | None, artifact_id: str | None, segments: list[Segment],
           details: dict[str, Any] | None = None) -> str:
    con.execute("DELETE FROM transcript_segments WHERE transcript_id = ?", [transcript_id])
    db.upsert(con, "transcripts", {
        "transcript_id": transcript_id, "source_id": source_id, "method": method,
        "language": language, "model": model, "artifact_id": artifact_id,
        "segment_count": len(segments), "created_at": db.now(), "details": details,
    })
    db.insert_many(con, "transcript_segments", [
        {"transcript_id": transcript_id, "seq": i, "start_s": s.start_s, "end_s": s.end_s,
         "text": s.text, "avg_logprob": s.avg_logprob}
        for i, s in enumerate(segments)
    ])
    return transcript_id


def _require_source(con, source_id: str) -> None:
    if not db.exists(con, "sources", "source_id", source_id):
        raise ValueError(f"unknown source_id {source_id!r}; ingest the source first")


def ingest_caption_file(con: duckdb.DuckDBPyConnection, source_id: str, path: Path | str, *,
                        method: str = "imported", language: str | None = None) -> str:
    """Parse a caption/transcript file (VTT, SRT, JSON, TXT) and store it."""
    _require_source(con, source_id)
    path = Path(path)
    archived = path
    root = config.archive_root()
    if root not in path.resolve().parents:
        archived = config.path("raw_subtitles", source_id) / path.name
        archived.write_bytes(path.read_bytes())
    with tracked(con, stage="captions_parse", adapter=method, uri=str(path), source_id=source_id) as ev:
        artifact_id = register_artifact(con, source_id, "subtitle", archived)
        segments = load_transcript_file(archived)
        transcript_id = stable_id("tr", source_id, method, language, artifact_id)
        _store(con, transcript_id=transcript_id, source_id=source_id, method=method,
               language=language, model=None, artifact_id=artifact_id, segments=segments,
               details={"original_path": str(path)})
        ev.details = {"segments": len(segments), "transcript_id": transcript_id}
    return transcript_id


# ---------------------------------------------------------------- speech-to-text

class Transcriber(Protocol):
    name: str
    model_name: str

    def transcribe(self, audio_path: Path, language: str | None) -> tuple[list[Segment], dict[str, Any]]:
        ...


class FasterWhisperTranscriber:
    """faster-whisper (CTranslate2). Downloads the model from Hugging Face on first use."""

    name = "faster-whisper"

    def __init__(self, model: str = "small", device: str = "auto", compute_type: str = "int8",
                 download_root: str | None = None, beam_size: int = 5, vad_filter: bool = True):
        self.model_name = model
        self.device, self.compute_type = device, compute_type
        self.download_root, self.beam_size, self.vad_filter = download_root, beam_size, vad_filter
        self._model = None

    def _load(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            try:
                self._model = WhisperModel(self.model_name, device=self.device,
                                           compute_type=self.compute_type, download_root=self.download_root)
            except Exception as e:  # network / HF hub failures surface here
                raise SourceUnavailable(f"could not load whisper model {self.model_name!r}: {e}") from e
        return self._model

    def transcribe(self, audio_path: Path, language: str | None) -> tuple[list[Segment], dict[str, Any]]:
        model = self._load()
        segs, info = model.transcribe(str(audio_path), language=language,
                                      beam_size=self.beam_size, vad_filter=self.vad_filter)
        out = [Segment(s.start, s.end, s.text.strip(), s.avg_logprob) for s in segs]
        return out, {"language": info.language, "language_probability": info.language_probability,
                     "duration": info.duration}


TRANSCRIBERS: dict[str, Callable[..., Transcriber]] = {
    "faster-whisper": FasterWhisperTranscriber,
}


def find_media(con, source_id: str) -> Path:
    row = con.execute(
        "SELECT local_path FROM artifacts WHERE source_id = ? AND role IN ('audio', 'video') "
        "ORDER BY CASE role WHEN 'audio' THEN 0 ELSE 1 END, created_at DESC LIMIT 1", [source_id]
    ).fetchone()
    if not row:
        raise ValueError(f"no media artifact for {source_id}; ingest with --media or pass --media-path")
    return config.resolve(row[0])


def transcribe(con: duckdb.DuckDBPyConnection, source_id: str, *, transcriber: Transcriber,
               media_path: Path | str | None = None, language: str | None = None) -> str:
    """Speech-to-text for a source's media; stores segments + a JSON artifact."""
    _require_source(con, source_id)
    media_path = Path(media_path) if media_path else find_media(con, source_id)
    with tracked(con, stage="transcribe", adapter=transcriber.name, uri=str(media_path),
                 source_id=source_id) as ev:
        wav = media.extract_audio(media_path, config.path("audio", source_id) / f"{media_path.stem}.16k.wav")
        segments, info = transcriber.transcribe(wav, language)
        lang = language or info.get("language")
        transcript_id = stable_id("tr", source_id, "asr", transcriber.name, transcriber.model_name, lang)
        out = config.path("transcripts", source_id) / f"{transcript_id}.json"
        out.write_text(json.dumps({
            "source_id": source_id, "transcriber": transcriber.name, "model": transcriber.model_name,
            "info": info, "segments": [asdict(s) for s in segments],
        }, ensure_ascii=False, indent=1))
        artifact_id = register_artifact(con, source_id, "transcript_json", out)
        _store(con, transcript_id=transcript_id, source_id=source_id, method="asr", language=lang,
               model=f"{transcriber.name}:{transcriber.model_name}", artifact_id=artifact_id,
               segments=segments, details=info)
        ev.details = {"segments": len(segments), "transcript_id": transcript_id}
    return transcript_id


def transcript_text(con, transcript_id: str) -> str:
    rows = con.execute("SELECT text FROM transcript_segments WHERE transcript_id = ? ORDER BY seq",
                       [transcript_id]).fetchall()
    return "\n".join(r[0] for r in rows)
