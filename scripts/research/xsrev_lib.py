"""H-XSREV shared helpers: point-in-time daily universe (tiers by trailing 30d quote volume) and HL mapping.

Ranking uses data/raw/web/momentum/klines/<SYM>.parquet (Binance 1d archive klines, read-only reuse).
Rank on day d uses only daily bars d-30..d-1 (all closed before 00:00 of d).
"""
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DAILY = ROOT / "data/raw/web/momentum/klines"
PAIRS = ROOT / "data/raw/web/xsrev/hl_bn_pairs.json"  # private: HL meta x Binance archive symbols
QV_COPY = ROOT / "data/raw/web/xsrev/daily_qv.parquet"  # private copy of the daily quote-volume panel
EXCL = {"BTCDOMUSDT", "DEFIUSDT", "FOOTBALLUSDT", "BLUEBIRDUSDT", "USDCUSDT"}
STABLE_BASES = {"USDC", "TUSD", "BUSD", "FDUSD", "USDP", "USDE", "USD1", "DAI", "PYUSD", "USDT"}
START_DAY = pd.Timestamp("2023-02-01")
END_DAY = pd.Timestamp("2026-03-31")
TIERS = {"A": (11, 50), "B": (51, 150)}


def hl_symbols():
    return {p["bn"] for p in json.load(open(PAIRS))["pairs"]}


def excluded(sym):
    return sym in EXCL or sym[:-4] in STABLE_BASES or "_" in sym


@lru_cache(None)
def daily_panel():
    """Wide frame of daily quote volume (index day, columns symbol), NaN where no bar."""
    if QV_COPY.exists():
        return pd.read_parquet(QV_COPY)
    cols = {}
    for f in sorted(DAILY.glob("*.parquet")):
        s = f.stem
        if excluded(s):
            continue
        d = pd.read_parquet(f, columns=["open_time", "quote_volume"])
        d["day"] = pd.to_datetime(d.open_time, unit="ms").dt.normalize()
        d = d[d.day < pd.Timestamp("2026-04-01")]
        cols[s] = d.drop_duplicates("day").set_index("day").quote_volume
    qv = pd.DataFrame(cols).sort_index()
    full = pd.date_range(qv.index.min(), qv.index.max(), freq="D")
    qv = qv.reindex(full)
    qv.to_parquet(QV_COPY, compression="zstd")
    return qv


@lru_cache(None)
def tiers():
    """Long frame: day, symbol, rank, tier, n_hist (daily bars before day) for HL-listed tier members."""
    qv = daily_panel()
    vol30 = qv.shift(1).rolling(30, min_periods=25).sum()          # days d-30..d-1
    nhist = qv.notna().astype(int).cumsum().shift(1)                # bars before d
    days = qv.index[(qv.index >= START_DAY) & (qv.index <= END_DAY)]
    hl = hl_symbols()
    rows = []
    for d in days:
        v = vol30.loc[d].dropna().sort_values(ascending=False)
        rk = pd.Series(np.arange(1, len(v) + 1), index=v.index)
        for s, r in rk.items():
            if r > 150 or s not in hl:
                continue
            t = "A" if 11 <= r <= 50 else ("B" if r >= 51 else None)
            if t is None or nhist.loc[d, s] < 60:
                continue
            rows.append((d, s, int(r), t))
    return pd.DataFrame(rows, columns=["day", "symbol", "rank", "tier"])


def symbols_needed():
    t = tiers()
    out = {}
    for s, g in t.groupby("symbol"):
        m0 = (g.day.min() - pd.Timedelta(days=32)).strftime("%Y-%m")
        m1 = (g.day.max() + pd.Timedelta(days=1)).strftime("%Y-%m")
        out[s] = [max(m0, "2023-01"), min(m1, "2026-03")]
    return out
