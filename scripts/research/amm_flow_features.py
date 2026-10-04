"""Build point-in-time decision snapshots for post-migration PumpSwap pools (agent amm_flow).

Decision grid: every 15 s per pool, inside the split's decision windows, where the pool had >= 3 trades in the
60 s up to and including t. Features use only trades with recv <= t. Forward outcomes: exact constant-product
0.5 SOL round trips entering at t+1 s and exiting at t+1+H s (H = 60, 180, 600), conservative fill (see
amm_flow_lib.state_for). Exits never cross a window end, so no holdout/forward data enter outcomes.

Usage: python scripts/research/amm_flow_features.py train|valid OUT.parquet
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/RErereresearch/scripts/research")
import amm_flow_lib as L  # noqa: E402

STEP = 15.0
HS = (60, 180, 600)


def streak_distinct(buy: np.ndarray, u: np.ndarray) -> np.ndarray:
    out = np.zeros(len(buy), np.int32)
    seen: set = set()
    for i in range(len(buy)):
        if buy[i]:
            seen.add(u[i])
            out[i] = len(seen)
        else:
            seen = set()
    return out


def pool_snapshots(a: dict, created: float, windows: list[tuple[float, float]], offset_alt: dict | None) -> pd.DataFrame:
    recv = a["recv"]
    t0, t1 = recv[0], recv[-1]
    grids = []
    for (wa, wb) in windows:
        lo, hi = max(wa, np.ceil(t0 / STEP) * STEP), min(wb - max(HS) - 15, t1)
        if hi > lo:
            grids.append(np.arange(lo, hi, STEP))
    if not grids:
        return pd.DataFrame()
    T = np.concatenate(grids)
    i_now = np.searchsorted(recv, T, side="right") - 1          # last trade <= t
    i60 = np.searchsorted(recv, T - 60, side="right")            # first trade > t-60
    active = (i_now >= 0) & (i_now - i60 + 1 >= 3)
    T, i_now, i60 = T[active], i_now[active], i60[active]
    if len(T) == 0:
        return pd.DataFrame()
    buy, sol = a["buy"], a["sol"]
    bs = np.concatenate([[0], np.cumsum(np.where(buy, sol, 0.0))])
    ss = np.concatenate([[0], np.cumsum(np.where(buy, 0.0, sol))])
    nb = np.concatenate([[0], np.cumsum(buy)])
    d = {"t": T, "age": T - created, "rs": a["rs_post"][i_now], "mid": a["mid"][i_now]}
    for W in (60, 180, 300):
        iw = np.searchsorted(recv, T - W, side="right")
        B = bs[i_now + 1] - bs[iw]
        S = ss[i_now + 1] - ss[iw]
        d[f"vol{W}"] = B + S
        d[f"ofi{W}"] = np.where(B + S > 0, (B - S) / np.maximum(B + S, 1e-12), 0.0)
        d[f"n{W}"] = i_now + 1 - iw
        d[f"nbuy{W}"] = nb[i_now + 1] - nb[iw]
        j = iw - 1                                                 # state at t-W = post of last trade <= t-W
        pm = np.where(j >= 0, a["mid"][np.clip(j, 0, None)], a["rs_pre"][0] / a["rt_pre"][0])
        d[f"ret{W}"] = d["mid"] / pm - 1
    runmax = np.maximum.accumulate(a["mid"])
    d["dd"] = d["mid"] / runmax[i_now] - 1                        # vs post-migration high (loaded rows only)
    d["streak"] = streak_distinct(buy, a["u"])[i_now]
    # distinct buyers / sellers and the largest sell in last 60 s
    u = a["u"]
    nbw, nsw, mxs, rec = [], [], [], []
    mid, rs_pre, rt_pre = a["mid"], a["rs_pre"], a["rt_pre"]
    for k in range(len(T)):
        s0, s1 = i60[k], i_now[k] + 1
        bb = buy[s0:s1]
        uu = u[s0:s1]
        nbw.append(len(set(uu[bb])))
        nsw.append(len(set(uu[~bb])))
        sl = np.where(~bb, sol[s0:s1], 0.0)
        if sl.max() > 0:
            jj = s0 + int(sl.argmax())
            before = rs_pre[jj] / rt_pre[jj]
            after = mid[jj]
            mxs.append(sol[jj] / rs_pre[jj])
            drop = before - after
            rec.append((mid[i_now[k]] - after) / drop if drop > 0 else np.nan)
        else:
            mxs.append(0.0)
            rec.append(np.nan)
    d["nbw60"], d["nsw60"], d["bigsell60"], d["recov60"] = nbw, nsw, mxs, rec
    for H in HS:
        d[f"pnl{H}"] = L.round_trip(a, T + 1, T + 1 + H)
        d[f"pnl{H}_x"] = L.round_trip(a, T + 1, T + 1 + H, extra_fee=0.0025)      # brief's extra 0.25%/side
        if offset_alt is not None:
            d[f"pnl{H}_lo"] = L.round_trip(offset_alt, T + 1, T + 1 + H)          # reserve = logged - 17.6
    return pd.DataFrame(d)


def main(split: str, out: str) -> None:
    df, created = L.load(split)
    windows = L.SEGMENTS[split]
    parts = []
    for pool, g in df.groupby("pool", sort=False):
        if len(g) < 10 or pool not in created:
            continue
        a = L.pool_arrays(g)
        alt = L.pool_arrays(g, offset=-17.6)
        snap = pool_snapshots(a, created[pool], windows, alt)
        if len(snap):
            snap.insert(0, "pool", pool)
            parts.append(snap)
    res = pd.concat(parts, ignore_index=True)
    res.to_parquet(out)
    print(split, len(res), "snapshots,", res.pool.nunique(), "pools")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
