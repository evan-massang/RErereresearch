"""Shared loader for the pump.fun livestream poll recorder (data/raw/streams/pump_live/*.jsonl.gz).

EXPLORATORY. All of this data is after 2026-10-04 00:00 UTC (the forward-test period). Nothing here is a
frozen strategy; any rule found must be frozen and then tested on data recorded AFTER the freeze.

Reads gzip files tolerantly (the newest file is still being written): stops at a truncated line / EOFError.
Several recorder processes can overlap in time (file suffix = pid); polls are de-duplicated on recv.
"""
import gzip
import json
import zlib
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
LIVE_DIR = ROOT / "data" / "raw" / "streams" / "pump_live"

COLS = ("mint", "symbol", "num_participants", "market_cap", "usd_market_cap", "complete", "created_timestamp",
        "last_trade_timestamp", "reply_count", "ath_market_cap", "is_currently_live", "livestream_title",
        "virtual_sol_reserves", "virtual_token_reserves", "creator")


def _lines(path: Path):
    try:
        with gzip.open(path, "rt") as f:
            for line in f:
                yield line
    except (EOFError, OSError, zlib.error):
        return


def load_polls():
    """Returns (polls, rows, stats). polls: one row per successful poll (recv, n, src). rows: one row per coin per poll."""
    polls, rows = [], []
    stats = {"files": 0, "lines": 0, "error_lines": 0, "bad_lines": 0, "dup_polls": 0}
    seen = set()
    for p in sorted(LIVE_DIR.glob("*.jsonl.gz")):
        stats["files"] += 1
        for line in _lines(p):
            stats["lines"] += 1
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                stats["bad_lines"] += 1
                break  # truncated tail of a file being written
            if "error" in d:
                stats["error_lines"] += 1
                continue
            key = round(d["recv"], 3)
            if key in seen:
                stats["dup_polls"] += 1
                continue
            seen.add(key)
            polls.append({"recv": d["recv"], "n": d.get("n"), "ncoins": len(d.get("coins") or []), "src": p.name})
            for c in d.get("coins") or []:
                r = {k: c.get(k) for k in COLS}
                r["recv"] = d["recv"]
                rows.append(r)
    polls = pd.DataFrame(polls).sort_values("recv").reset_index(drop=True)
    rows = pd.DataFrame(rows).sort_values(["recv", "mint"]).reset_index(drop=True)
    rows["viewers"] = rows.num_participants.astype(float)
    rows["complete"] = rows.complete.astype(bool)
    return polls, rows, stats
