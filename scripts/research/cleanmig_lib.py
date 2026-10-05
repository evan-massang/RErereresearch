"""H-CLEANMIG: structural filter at migration + one delayed PumpSwap buy (agent cleanmig, 2026-10-05).

Research only. Reads data/market.duckdb READ-ONLY. Holdout rows (1790882100 <= recv < 1790899200) are never
loaded: every SQL query below carries the HOLDOUT-exclusion predicate, and asserts check it.

Pre-registration: reports/hypotheses/cleanmig_preregistration.json (written before any P&L was computed).

Facts reused (verified by earlier agents, re-checked here in `check_offset`):
- PumpSwap true SOL reserve = amm_trades.pool_sol_logged + 17.585 (exact sell identity; agent_amm_flow.md,
  agent_lpsell_clock.md). fee_bps already sums LP + protocol + creator fee, so cost per side = fee_bps / 1e4.

Covered tape: the recorder has multi-hour gaps. `segments()` returns maximal intervals with no market-wide
gap > 60 s in BOTH amm_trades and curve_trades (holdout treated as a gap). A trade is eligible only if
token create, migration and entry (+1 s) lie in ONE covered segment, and the exit (+1 s) lies in a covered
segment; the whole lifecycle [token create, exit + 1 s] must not intersect the holdout or pass the data end.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import duckdb

DB = "/home/user/RErereresearch/data/market.duckdb"
MAYHEM = "/home/user/RErereresearch/data/processed/mayhem_flags.parquet"
OFFSET = 17.585
HOLD_A, HOLD_B = 1790882100, 1790899200
VAL_A, VAL_B = 1790985600, 1791072000
NOHOLD = f"(recv < {HOLD_A} OR recv >= {HOLD_B})"
SUPPLY = 1e9
GAP_S = 60.0


def con():
    return duckdb.connect(DB, read_only=True)


def segments(c=None) -> list[tuple[float, float]]:
    """Covered intervals: no market-wide gap > 60 s in amm_trades or curve_trades; holdout is a gap."""
    c = c or con()
    gaps = []
    for t in ("amm_trades", "curve_trades"):
        g = c.execute(f"""SELECT prev, recv FROM (SELECT recv, lag(recv) OVER (ORDER BY recv) prev FROM {t}
                          WHERE {NOHOLD}) WHERE recv - prev > {GAP_S}""").fetchall()
        gaps += g
    lo = max(c.execute(f"SELECT min(recv) FROM {t} WHERE {NOHOLD}").fetchone()[0] for t in ("amm_trades", "curve_trades"))
    hi = min(c.execute(f"SELECT max(recv) FROM {t} WHERE {NOHOLD}").fetchone()[0] for t in ("amm_trades", "curve_trades"))
    gaps.append((HOLD_A - 1e-6, HOLD_B))
    gaps.sort()
    merged = []
    for a, b in gaps:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    segs, cur = [], lo
    for a, b in merged:
        if a > cur:
            segs.append((cur, a))
        cur = max(cur, b)
    if hi > cur:
        segs.append((cur, hi))
    return segs


def seg_of(t: float, segs) -> int:
    for i, (a, b) in enumerate(segs):
        if a <= t <= b:
            return i
    return -1


def split_of(t: float) -> str:
    if HOLD_A <= t < HOLD_B:
        return "holdout"
    if t < VAL_A:
        return "train"
    if t < VAL_B:
        return "valid"
    return "forward"


def migrations(c=None) -> pd.DataFrame:
    """Standard migrations (amm_pools.quote_in ~ 84.99) with token create info and point-in-time curve
    features computed ONLY from curve_trades with recv <= curve completion (<= pool creation)."""
    c = c or con()
    P = c.execute(f"""SELECT p.pool, p.mint, p.recv AS t_mig, p.quote_in, p.base_in,
                             cc.c_recv, cc.c_slot, cc.creator, comp.t_comp
                      FROM amm_pools p
                      LEFT JOIN (SELECT mint, min(recv) c_recv, min(slot) c_slot, any_value(creator) creator
                                 FROM curve_creates WHERE {NOHOLD} GROUP BY mint) cc USING (mint)
                      LEFT JOIN (SELECT mint, min(recv) t_comp FROM curve_completes WHERE {NOHOLD} GROUP BY mint) comp
                                USING (mint)
                      WHERE {NOHOLD.replace('recv', 'p.recv')}""").df()
    c.register("pm", P[["mint", "t_mig", "c_slot", "creator"]])
    # per-wallet net balance up to migration (curve trades with recv <= t_mig), holdout rows excluded by SQL
    W = c.execute(f"""SELECT t.mint, t.usr,
                             sum(CASE WHEN t.buy THEN t.tok ELSE -t.tok END) AS net,
                             min(CASE WHEN t.buy THEN t.slot END) AS first_buy_slot,
                             count(*) AS ntr
                      FROM curve_trades t JOIN pm USING (mint)
                      WHERE t.recv <= pm.t_mig AND {NOHOLD.replace('recv', 't.recv')}
                      GROUP BY t.mint, t.usr""").df()
    W = W.merge(P[["mint", "c_slot", "creator"]], on="mint", how="left")
    rows = []
    for mint, g in W.groupby("mint", sort=False):
        net = g.net.clip(lower=0).to_numpy()
        top10 = np.sort(net)[::-1][:10].sum() / SUPPLY
        cre = g[g.usr == g.creator.iloc[0]].net.sum() / SUPPLY if isinstance(g.creator.iloc[0], str) else np.nan
        cs = g.c_slot.iloc[0]
        snipe = g[(g.first_buy_slot.notna()) & (g.first_buy_slot <= cs + 1)].net.clip(lower=0).sum() / SUPPLY \
            if pd.notna(cs) else np.nan
        rows.append({"mint": mint, "n_curve": int(g.ntr.sum()), "holders": int((g.net > 100).sum()),
                     "top10": top10, "creator_share": cre, "snipe_hold": snipe})
    F = pd.DataFrame(rows)
    P = P.merge(F, on="mint", how="left")
    P["n_curve"] = P.n_curve.fillna(0).astype(int)
    mf = pd.read_parquet(MAYHEM)[["mint", "is_mayhem"]].drop_duplicates("mint")
    P = P.merge(mf, on="mint", how="left")
    return P


def filt(P: pd.DataFrame, strict: bool) -> pd.Series:
    m = ((P.n_curve >= 20) & (P.creator_share < 0.001) & (P.top10 < 0.30) & (P.snipe_hold < 0.03))
    if strict:
        m &= P.holders >= 150
    return m.fillna(False)


# ------------------------------------------------------------------ fills
def load_pool_trades(c, pools: list[str], t_max: float) -> pd.DataFrame:
    c.register("pl", pd.DataFrame({"pool": pools}))
    df = c.execute(f"""SELECT a.recv, a.pool, a.buy, a.tok, a.sol, a.pool_tok_logged rt, a.pool_sol_logged rs_log,
                              a.fee_bps FROM amm_trades a JOIN pl USING (pool)
                       WHERE {NOHOLD.replace('recv', 'a.recv')} AND a.recv <= {t_max} AND a.tok > 0 AND a.sol > 0""").df()
    assert not ((df.recv >= HOLD_A) & (df.recv < HOLD_B)).any()
    return df.sort_values(["pool", "recv"], kind="stable").reset_index(drop=True)


def arrays(g: pd.DataFrame) -> dict:
    recv = g.recv.to_numpy(); buy = g.buy.to_numpy(); tok = g.tok.to_numpy(); sol = g.sol.to_numpy()
    rs_pre = np.maximum(g.rs_log.to_numpy() + OFFSET, 1e-3); rt_pre = g.rt.to_numpy()
    rt_post = np.maximum(np.where(buy, rt_pre - tok, rt_pre + tok), 1.0)
    rs_post = np.maximum(np.where(buy, rs_pre * rt_pre / rt_post, rs_pre - sol), 1e-6)
    return {"recv": recv, "fee": g.fee_bps.to_numpy() / 1e4, "rs_pre": rs_pre, "rt_pre": rt_pre,
            "rs_post": rs_post, "rt_post": rt_post}


def state_last(a: dict, T: float, seg: tuple[float, float]):
    """Last pool state at time T (post-state of last trade with recv <= T). Fee = that trade's fee tier.
    If that trade lies before the covered segment containing T (state crossed a recorder gap), fall back to the
    pre-state of the first trade after T inside the segment (same state if nothing unobserved happened);
    flag 'stale' if neither exists (state last seen before a gap)."""
    r = a["recv"]
    i = np.searchsorted(r, T, side="right") - 1
    if i >= 0 and r[i] >= seg[0]:
        return a["rs_post"][i], a["rt_post"][i], a["fee"][i], "ok"
    j = i + 1
    if j < len(r) and r[j] <= seg[1]:
        return a["rs_pre"][j], a["rt_pre"][j], a["fee"][j], "next_pre"
    if i >= 0:
        return a["rs_post"][i], a["rt_post"][i], a["fee"][i], "stale"
    return None


def state_cons(a: dict, T: float, side: str, seg, max_wait=5.0):
    """Conservative sensitivity (agent_amm_flow rule): candidates = last state and the post-state of the first
    trade within 5 s; buy takes the higher price, sell the lower; sell also marked down to the next trade's
    pre-state if >2% lower."""
    base = state_last(a, T, seg)
    if base is None:
        return None
    rs, rt, f, flag = base
    r = a["recv"]
    j = np.searchsorted(r, T, side="left")
    if j < len(r) and r[j] - T <= max_wait:
        rs2, rt2 = a["rs_post"][j], a["rt_post"][j]
        if (side == "buy" and rs2 / rt2 > rs / rt) or (side == "sell" and rs2 / rt2 < rs / rt):
            rs, rt, f = rs2, rt2, a["fee"][j]
    if side == "sell" and j < len(r) and r[j] <= seg[1]:
        if a["rs_pre"][j] / a["rt_pre"][j] < 0.98 * rs / rt:
            rs, rt = a["rs_pre"][j], a["rt_pre"][j]
    return rs, rt, f, flag


def buy_tokens(rs, rt, f, size):
    x = size / (1 + f)          # fee charged on the quote input (PumpSwap buy); user spends `size` in total
    return rt * x / (rs + x)


def sell_sol(rs, rt, f, q):
    return rs * q / (rt + q) * (1 - f)
