"""H-SOLLEAD shared helpers: SOL/USD 1-minute returns and per-minute memecoin price panels (agent sollead).

Research only. Reads data/market.duckdb READ-ONLY and the cached Binance SOLUSDT 1m klines
(data/raw/web/solusd/solusdt_1m_20261001_20261003.parquet, fetched by scripts/research/round_levels_solusd.py).

Minute convention: a kline with open time t covers [t, t+60). A memecoin "minute close" for bucket t is the
last trusted price print with recv in [t, t+60). Lag k: SOL return in bucket t vs memecoin return in bucket t+k.

Curve price = vsol/vtok on trusted states only (|vsol - rsol - 30| < 0.01), Mayhem tokens excluded, prints at
or after the token's completion excluded. AMM price = post-trade mid with true quote reserve = logged + 17.585.

Splits (recv, UTC s): train = recv < 1790882100 OR 1790899200 <= recv < 1790985600;
validation = 1790985600 <= recv < 1791072000; holdout and >= 1791072000 never loaded.
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DB = str(ROOT / "data" / "market.duckdb")
SOL_PARQUET = ROOT / "data" / "raw" / "web" / "solusd" / "solusdt_1m_20261001_20261003.parquet"
MAYHEM = ROOT / "data" / "processed" / "mayhem_flags.parquet"
HOLD_A, HOLD_B = 1790882100, 1790899200
VAL_A, VAL_B = 1790985600, 1791072000
OFFSET = 17.585
ALLOWED = f"(recv < {HOLD_A} OR (recv >= {HOLD_B} AND recv < {VAL_B}))"


def split_of(t):
    t = np.asarray(t, float)
    out = np.full(t.shape, "", dtype=object)
    out[(t < HOLD_A) | ((t >= HOLD_B) & (t < VAL_A))] = "train"
    out[(t >= VAL_A) & (t < VAL_B)] = "valid"
    return out


def connect():
    con = duckdb.connect(DB, read_only=True)
    con.execute("SET threads=2; SET memory_limit='3GB'")
    return con


def mayhem_mints() -> set:
    d = pd.read_parquet(MAYHEM)
    return set(d.loc[d.is_mayhem.astype(bool), "mint"])


def sol_minutes() -> pd.DataFrame:
    s = pd.read_parquet(SOL_PARQUET)
    s = s[s.t < VAL_B].sort_values("t").set_index("t")
    s["r1"] = np.log(s.close / s.open)  # within-minute return (open -> close)
    return s


def curve_minute_panel(con) -> pd.DataFrame:
    """Per (mint, minute) last trusted price, trade count and SOL volume."""
    may = mayhem_mints()
    con.register("may", pd.DataFrame({"mint": sorted(may)}))
    q = f"""
    WITH comp AS (SELECT mint, min(recv) tc FROM curve_completes GROUP BY 1),
    t AS (SELECT c.mint, c.recv, c.vsol, c.vtok, c.sol FROM curve_trades c LEFT JOIN comp ON c.mint = comp.mint
          WHERE {ALLOWED.replace('recv', 'c.recv')} AND abs(c.vsol - c.rsol - 30) < 0.01 AND c.vtok > 0
            AND (comp.tc IS NULL OR c.recv < comp.tc)
            AND c.mint NOT IN (SELECT mint FROM may))
    SELECT mint, CAST(floor(recv / 60) * 60 AS BIGINT) m, arg_max(vsol / vtok, recv) p, count(*) n, sum(sol) vol,
           max(vsol) vsol_last
    FROM t GROUP BY 1, 2"""
    return con.execute(q).df()


def amm_minute_panel(con) -> pd.DataFrame:
    may = mayhem_mints()
    con.register("may", pd.DataFrame({"mint": sorted(may)}))
    q = f"""
    WITH t AS (SELECT pool, recv, buy, tok, sol, pool_tok_logged rt, pool_sol_logged + {OFFSET} rs FROM amm_trades
               WHERE {ALLOWED} AND tok > 0 AND sol > 0 AND pool_tok_logged > tok
                 AND mint NOT IN (SELECT mint FROM may)),
    u AS (SELECT pool, recv, sol,
                 CASE WHEN buy THEN rs * rt / (rt - tok) ELSE rs - sol END rs2,
                 CASE WHEN buy THEN rt - tok ELSE rt + tok END rt2 FROM t)
    SELECT pool AS mint, CAST(floor(recv / 60) * 60 AS BIGINT) m, arg_max(rs2 / rt2, recv) p, count(*) n,
           sum(sol) vol, arg_max(rs2, recv) rs_last
    FROM u WHERE rs2 > 0 AND rt2 > 0 GROUP BY 1, 2"""
    return con.execute(q).df()


def index_returns(panel: pd.DataFrame, min_trades: int = 1, clip: float = 0.5) -> pd.DataFrame:
    """Equal-weight index: per minute m, mean log return of tokens with a price in both m-1 and m.
    Returns are clipped at +-clip (log) to stop single-token blow-ups dominating."""
    p = panel[panel.n >= min_trades].sort_values(["mint", "m"])
    prev_m = p.groupby("mint").m.shift(1)
    prev_p = p.groupby("mint").p.shift(1)
    ok = (p.m - prev_m) == 60
    r = np.log(p.p / prev_p).where(ok).clip(-clip, clip)
    d = pd.DataFrame({"m": p.m, "r": r}).dropna()
    g = d.groupby("m").r
    return pd.DataFrame({"r": g.mean(), "med": g.median(), "k": g.size()})
