"""Shared fixtures. Everything created here is SYNTHETIC test data."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def pytest_configure(config):
    config.addinivalue_line("markers", "network: needs outbound network (opt in with RR_NETWORK_TESTS=1)")


@pytest.fixture
def archive(tmp_path, monkeypatch):
    """A fresh, isolated archive root + open DB connection."""
    monkeypatch.setenv("RR_ARCHIVE", str(tmp_path / "archive"))
    from pipeline import db

    con = db.connect()
    yield con
    con.close()


@pytest.fixture(scope="session")
def synthetic_video(tmp_path_factory) -> Path:
    """6 s SYNTHETIC test clip: 3 s red then 3 s blue (one hard cut), 440 Hz tone.

    Also writes SYNTHETIC caption sidecars next to it, as the local adapter expects.
    """
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")
    d = tmp_path_factory.mktemp("media")
    out = d / "synthetic_clip.mp4"
    subprocess.run([
        "ffmpeg", "-nostdin", "-y", "-v", "error",
        "-f", "lavfi", "-i", "color=c=red:s=160x120:d=3:r=10",
        "-f", "lavfi", "-i", "color=c=blue:s=160x120:d=3:r=10",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
        "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
        "-map", "[v]", "-map", "2:a", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-metadata", "title=SYNTHETIC test clip", "-shortest", str(out),
    ], check=True)
    shutil.copy(FIXTURES / "synthetic_captions.vtt", d / "synthetic_clip.en.vtt")
    shutil.copy(FIXTURES / "synthetic_captions.srt", d / "synthetic_clip.de.srt")
    return out


@pytest.fixture(scope="session")
def synthetic_audio(synthetic_video, tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("audio") / "synthetic_tone.m4a"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", str(synthetic_video),
                    "-vn", "-c:a", "aac", str(out)], check=True)
    return out
