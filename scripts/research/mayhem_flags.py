"""Mayhem Mode flag per mint from PumpPortal create messages (data/raw/streams/pumpportal/*.jsonl.gz).

Writes data/processed/mayhem_flags.parquet: mint, recv, is_mayhem (None when the field is absent).
Truncated gzip files (recorder still writing / cut) are read up to the last complete line.
    python scripts/research/mayhem_flags.py
"""
import glob
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import pandas as pd  # noqa: E402

rows, stats = [], {}
for f in sorted(glob.glob(str(ROOT / "data/raw/streams/pumpportal/*.jsonl.gz"))):
    n = flagged = 0
    try:
        with gzip.open(f, "rt") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = d.get("msg") or {}
                if msg.get("txType") != "create" or not msg.get("mint"):
                    continue
                n += 1
                v = msg.get("is_mayhem_mode")
                flagged += v is not None
                rows.append((msg["mint"], d.get("recv"), None if v is None else bool(v), msg.get("traderPublicKey")))
    except (EOFError, OSError):
        pass
    stats[Path(f).name] = (n, flagged)
df = pd.DataFrame(rows, columns=["mint", "recv", "is_mayhem", "pp_creator"]).drop_duplicates("mint")
df.to_parquet(ROOT / "data/processed/mayhem_flags.parquet")
for k, v in stats.items():
    print(k, v)
print(len(df), df.is_mayhem.value_counts(dropna=False).to_dict())
