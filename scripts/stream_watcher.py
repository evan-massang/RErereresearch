"""Record traders' live streams when they go live (for alignment with on-chain trades).

    python scripts/stream_watcher.py --hours 9

Polls each channel every few minutes; when one is live, records it with yt-dlp
into data/raw/video/live/<platform>_<channel>/<UTC start>.mp4 plus a JSON sidecar
holding the wall-clock time recording started (anchor for video time -> chain time).
Twitch past broadcasts of these channels were not available, so live capture is
the only way to get their footage.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANNELS = {
    # seed traders (verified or probable accounts)
    "twitch:decu": "https://www.twitch.tv/decu",
    "twitch:cupseyy": "https://www.twitch.tv/cupseyy",
    "twitch:setuhh": "https://www.twitch.tv/setuhh",
    # streamers named in the lead files as trading live (leads, not verified)
    "kick:orangie": "https://kick.com/orangie",
    "kick:alxcooks": "https://kick.com/alxcooks",
    "kick:solanaswaggy": "https://kick.com/solanaswaggy",
    "kick:tradememecoins": "https://kick.com/tradememecoins",
    # "twitch:d4rkuch1ha": dropped 2026-10-01 18:40 UTC to save disk for the seed traders (unidentified lead;
    # 16:37-18:19 footage kept)
    # "twitch:dvces": dropped 2026-10-01 16:40 UTC to save disk: not identified (480p unreadable, trades
    # migrated tokens the tape does not decode); the 12:45-16:40 footage is kept.
}
OUT = ROOT / "data" / "raw" / "video" / "live"
STATUS = ROOT / "data" / "stream_watcher_status.json"


MIN_FREE_GB = 6.0
# seed traders at 720p so Axiom panels are legible; everyone else at 480p to save disk
QUALITY = {k: "best[height<=720]/best" for k in ("twitch:decu", "twitch:cupseyy", "twitch:setuhh")}


def adopt_running() -> dict[int, str]:
    """yt-dlp recordings left running by a previous watcher (pid -> channel key)."""
    out = {}
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            cmd = (proc / "cmdline").read_bytes().replace(b"\0", b" ").decode()
        except OSError:
            continue
        # the yt-dlp process itself, not a shell whose command line merely mentions it
        if "/yt-dlp " in cmd and "data/raw/video/live" in cmd and not cmd.startswith(("/bin/bash", "bash", "sh ")):
            for key, url in CHANNELS.items():
                if url in cmd:
                    out[int(proc.name)] = key
        # an ffmpeg left writing after its yt-dlp parent was stopped: identify it by the file it holds open
        elif cmd.startswith("ffmpeg"):
            try:
                targets = [os.readlink(fd) for fd in (proc / "fd").iterdir()]
            except OSError:
                continue
            for t in targets:
                if str(OUT) in t:
                    key = Path(t).parent.name.replace("_", ":", 1)
                    if key in CHANNELS:
                        out[int(proc.name)] = key
    return out


def is_live(url: str) -> dict | None:
    p = subprocess.run(["yt-dlp", "--no-warnings", "-J", "--skip-download", url],
                       capture_output=True, text=True, timeout=90)
    if p.returncode != 0:
        return None
    try:
        info = json.loads(p.stdout)
    except ValueError:
        return None
    return info if info.get("is_live") else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=9)
    ap.add_argument("--poll-s", type=float, default=180)
    ap.add_argument("--max-concurrent", type=int, default=3)
    a = ap.parse_args()
    stop = time.time() + a.hours * 3600
    rec: dict[str, subprocess.Popen] = {}
    log: list[dict] = []
    adopted = adopt_running()
    def free_gb() -> float:
        return shutil.disk_usage(ROOT).free / 1e9
    while time.time() < stop:
        if free_gb() < MIN_FREE_GB:
            for key, p in list(rec.items()):
                p.terminate()
                log.append({"event": "stopped_low_disk", "channel": key, "at": datetime.now(timezone.utc).isoformat()})
            for pid in adopted:
                subprocess.run(["kill", str(pid)])
            adopted = {}
        for key in list(rec):
            if rec[key].poll() is not None:
                log.append({"event": "ended", "channel": key, "at": datetime.now(timezone.utc).isoformat(),
                            "rc": rec[key].returncode})
                del rec[key]
        for key, url in CHANNELS.items():
            if key in rec or key in adopted.values() or len(rec) + len(adopted) >= a.max_concurrent \
                    or free_gb() < MIN_FREE_GB + 4:
                continue
            try:
                info = is_live(url)
            except subprocess.TimeoutExpired:
                info = None
            if not info:
                continue
            start = datetime.now(timezone.utc)
            d = OUT / key.replace(":", "_")
            d.mkdir(parents=True, exist_ok=True)
            stem = start.strftime("%Y%m%dT%H%M%SZ")
            (d / f"{stem}.info.json").write_text(json.dumps({
                "channel": key, "url": url, "recording_started_at": start.isoformat(),
                "title": info.get("title"), "id": info.get("id"),
                "note": "video time t corresponds to roughly recording_started_at + t + platform latency (~2-10 s)",
                "yt_dlp_info": {k: info.get(k) for k in ("uploader", "uploader_id", "release_timestamp", "timestamp",
                                                         "concurrent_view_count", "description")}}, indent=1))
            rec[key] = subprocess.Popen(
                ["yt-dlp", "--no-warnings", "-q", "-f", QUALITY.get(key, "best[height<=480]/worst"), "--hls-use-mpegts",
                 "--no-part", "-o", str(d / f"{stem}.%(ext)s"), url],
                stdout=subprocess.DEVNULL, stderr=open(d / f"{stem}.log", "w"), start_new_session=True)
            log.append({"event": "recording", "channel": key, "at": start.isoformat(), "title": info.get("title")})
        adopted = {pid: k for pid, k in adopted.items() if Path(f"/proc/{pid}").exists()}
        STATUS.write_text(json.dumps({"at": datetime.now(timezone.utc).isoformat(), "free_gb": round(free_gb(), 1),
                                      "recording": list(rec) + list(adopted.values()),
                                      "log": log[-50:]}, indent=1))
        time.sleep(a.poll_s)
    # recordings are left running (own session); the next watcher adopts them, so a restart leaves no gap


if __name__ == "__main__":
    sys.exit(main())
