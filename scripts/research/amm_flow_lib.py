"""Shared loader, point-in-time features and exact constant-product fills for the PumpSwap order-flow study.

Research only (agent "amm_flow", 2026-10-04). Reads data/market.duckdb READ-ONLY.

Data facts checked on train (see evidence json):
- amm_trades.pool_sol_logged is the PRE-trade quote reserve as logged; on sells, the exact constant-product
  identity sol = R_s * tok / (R_t + tok) holds with R_s = pool_sol_logged + 17.585 (p90 and p99 identical).
  So the reserve the swap math uses is logged + ~17.585 SOL. The task brief said "logged - 17.6"; that would
  understate liquidity by ~35 SOL and overstate impact. Main runs use the exact (+17.585) reserve; a
  sensitivity run uses the brief's (-17.6) figure.
- fee_bps = lp + protocol + creator bps (pipeline/market.py sums all three); on sells user_sol/sol = 1 - fee_bps/1e4.
  So total cost per side is fee_bps/1e4. Main runs charge fee_bps/1e4; a sensitivity run adds another 0.25%
  on top (the brief's reading) to be safe.

Splits (recv, UTC epoch seconds):
- train  : recv < 1790882100  OR  1790899200 <= recv < 1790985600
- holdout: 1790882100 <= recv < 1790899200   (never loaded)
- valid  : 1790985600 <= recv < 1791072000
- forward: recv >= 1791072000                 (never loaded)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import duckdb

DB = "/home/user/RErereresearch/data/market.duckdb"
OFFSET = 17.585            # exact reserve offset (see docstring)
HOLD_A, HOLD_B = 1790882100, 1790899200
VAL_A, VAL_B = 1790985600, 1791072000
SIZE = 0.5

SEGMENTS = {"train": [(0, HOLD_A), (HOLD_B, VAL_A)], "valid": [(VAL_A, VAL_B)]}


def load(split: str) -> tuple[pd.DataFrame, dict]:
    """Return trades usable for `split` (decision windows + allowed past), sorted by pool, recv.

    For train only train rows are loaded. For valid, train rows + valid rows are loaded (train rows serve as
    point-in-time history only; decisions are made inside the valid window). Holdout and forward rows never load.
    Pools created inside the holdout are dropped (their age would come from the holdout window).
    """
    con = duckdb.connect(DB, read_only=True)
    where = f"(recv < {HOLD_A} OR (recv >= {HOLD_B} AND recv < {VAL_A}))"
    if split == "valid":
        where = f"(recv < {HOLD_A} OR (recv >= {HOLD_B} AND recv < {VAL_B}))"
    pools = con.execute(f"SELECT pool, min(recv) AS created FROM amm_pools GROUP BY pool").df()
    pools = pools[~((pools.created >= HOLD_A) & (pools.created < HOLD_B)) & (pools.created < VAL_B)]
    df = con.execute(f"""SELECT recv, pool, hash(usr) AS u, buy, tok, sol, pool_tok_logged AS rt,
                                pool_sol_logged AS rs_log, fee_bps
                         FROM amm_trades WHERE {where} AND tok > 0 AND sol > 0""").df()
    con.close()
    df = df[df.pool.isin(set(pools.pool))]
    df = df.sort_values(["pool", "recv"], kind="stable").reset_index(drop=True)
    return df, dict(zip(pools.pool, pools.created))


def pool_arrays(g: pd.DataFrame, offset: float = OFFSET) -> dict:
    """Per-pool arrays: pre/post reserves, post-trade mid price."""
    recv = g.recv.to_numpy()
    buy = g.buy.to_numpy()
    tok = g.tok.to_numpy()
    sol = g.sol.to_numpy()
    rs_pre = np.maximum(g.rs_log.to_numpy() + offset, 1e-3)
    rt_pre = g.rt.to_numpy()
    # post state computed from the trade itself (exact for sells: sol = R_s*tok/(R_t+tok); buys: constant product
    # on the token side). Not taken from the next trade's pre-state, because liquidity can be withdrawn/added
    # between trades and that would leak a later event back to this trade's time.
    rt_post = np.where(buy, rt_pre - tok, rt_pre + tok)
    rt_post = np.maximum(rt_post, 1.0)
    rs_post = np.where(buy, rs_pre * rt_pre / rt_post, rs_pre - sol)
    rs_post = np.maximum(rs_post, 1e-6)
    return {"recv": recv, "buy": buy, "tok": tok, "sol": sol, "u": g.u.to_numpy(), "fee": g.fee_bps.to_numpy() / 1e4,
            "rs_pre": rs_pre, "rt_pre": rt_pre, "rs_post": rs_post, "rt_post": rt_post,
            "mid": rs_post / rt_post}


def state_for(a: dict, T: np.ndarray, side: str, max_wait: float = 5.0):
    """Reserve state for a fill at time T (vector). Conservative: candidates are the pool state at T (post-state
    of the last trade received <= T) and the post-state of the first trade received >= T (if within max_wait s).
    Entry ('buy') takes the higher-priced candidate, exit ('sell') the lower-priced one.
    Returns (rs, rt, fee, ok)."""
    recv = a["recv"]
    i_last = np.searchsorted(recv, T, side="right") - 1
    i_next = np.searchsorted(recv, T, side="left")
    ok = i_last >= 0
    il = np.clip(i_last, 0, len(recv) - 1)
    rs, rt, fee = a["rs_post"][il].copy(), a["rt_post"][il].copy(), a["fee"][il].copy()
    has_next = (i_next < len(recv))
    inx = np.clip(i_next, 0, len(recv) - 1)
    has_next &= (recv[inx] - T) <= max_wait
    rs2, rt2 = a["rs_post"][inx], a["rt_post"][inx]
    p1, p2 = rs / rt, rs2 / rt2
    use2 = has_next & ((p2 > p1) if side == "buy" else (p2 < p1))
    rs[use2], rt[use2], fee[use2] = rs2[use2], rt2[use2], a["fee"][inx][use2]
    return rs, rt, fee, ok


def round_trip(a: dict, t_entry: np.ndarray, t_exit: np.ndarray, extra_fee: float = 0.0,
               size: float = SIZE) -> np.ndarray:
    """Net SOL of buying `size` SOL at t_entry and selling all tokens at t_exit, exact constant product,
    fees per side, BEFORE tips. Our own buy is applied to the pool before the exit only through its effect on our
    fill (we assume other flow is unchanged; our sell is priced on the exit state plus our own earlier buy is
    not re-added, i.e. we do not assume our buy's impact persists to help our exit)."""
    rs, rt, f, ok = state_for(a, t_entry, "buy")
    x = size / (1 + f + extra_fee)
    q = rt * x / (rs + x)
    rs2, rt2, f2, ok2 = state_for(a, t_exit, "sell")
    out = rs2 * q / (rt2 + q) * (1 - f2 - extra_fee)
    r = out - size
    r[~(ok & ok2)] = np.nan
    return r


def stats(pnl: np.ndarray, tip: float) -> dict:
    p = np.asarray(pnl, float) - 2 * tip
    p = p[~np.isnan(p)]
    n = len(p)
    if n == 0:
        return {"n": 0}
    gw, gl = p[p > 0].sum(), -p[p < 0].sum()
    srt = np.sort(p)
    return {"n": int(n), "net": round(float(p.sum()), 4), "mean": round(float(p.mean()), 5),
            "win": round(float((p > 0).mean()), 3), "pf": round(float(gw / gl), 3) if gl > 0 else None,
            "net_ex3": round(float(srt[:-3].sum()), 4) if n > 3 else None,
            "median": round(float(np.median(p)), 5)}


def passes(s: dict) -> bool:
    return (s.get("n", 0) >= 50 and s["net"] > 0 and (s["pf"] or 0) > 1.2 and (s["net_ex3"] or -1) > 0)
