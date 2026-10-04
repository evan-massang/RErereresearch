"""Point-in-time snapshots of every bonding-curve token at fixed ages, with net-of-cost forward returns.

For each token and each age a in AGES (seconds after its create), features use only trades received at or before
create + a. The label is the result of a 0.5 SOL round trip: buy at the curve state at t = create + a + latency,
sell everything at t + H (or at the last curve state before the curve completes, if it completes first),
computed exactly on the constant-product curve, with the protocol fee on both sides and a fixed priority fee +
tip per transaction. No information after t is in the features.

    python scripts/research/ml_snapshots.py      # data/processed/ml_snapshots.parquet
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import os  # noqa: E402

import duckdb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from pipeline import config  # noqa: E402

AGES = tuple(int(a) for a in os.environ.get("RR_AGES", "5,10,20,30,60,120,300").split(","))
HORIZONS = (30, 120, 600)
EXITS = ((0.2, 0.1), (0.3, 0.15), (0.5, 0.2), (1.0, 0.3))
import os
SIZE, FEE, FIXED = 0.5, 0.0125, 0.01
LATENCY = float(os.environ.get("RR_LATENCY", "1.0"))


def round_trip(vs0, vt0, vs1, vt1) -> float:
    """Net SOL of buying SIZE at curve state (vs0, vt0) and selling all at (vs1, vt1). Reserves in SOL / tokens."""
    k0 = vs0 * vt0
    tok = vt0 - k0 / (vs0 + SIZE * (1 - FEE))
    k1 = vs1 * vt1
    sol_out = (vs1 - k1 / (vt1 + tok)) * (1 - FEE)
    return sol_out - SIZE - 2 * FIXED


def main() -> pd.DataFrame:
    con = duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
    data_end = con.execute("SELECT max(recv) FROM curve_trades").fetchone()[0]
    cr = con.execute("""SELECT mint, any_value(creator) creator, min(recv) ct, min(slot) cslot,
                               any_value(uri) uri FROM curve_creates GROUP BY 1 ORDER BY ct""").df()
    comp = dict(con.execute("SELECT mint, min(recv) FROM curve_completes GROUP BY 1").fetchall())
    # creator record, point in time
    hist, prior, prior_mig = {}, [], []
    for m, c, t in zip(cr.mint, cr.creator, cr.ct):
        h = hist.setdefault(c, [])
        prior.append(len(h))
        prior_mig.append(sum(1 for x in h if comp.get(x) is not None and comp[x] < t))
        h.append(m)
    cr["creator_prior"], cr["creator_prior_mig"] = prior, prior_mig
    cinfo = cr.set_index("mint")
    rows = []
    for day in sorted({int(t // 86400) for t in cr.ct}):
        a, b = day * 86400.0, (day + 1) * 86400.0
        tr = con.execute("""SELECT mint, recv, slot, usr, buy, sol, tok, vsol vs, vtok vt FROM curve_trades
                            WHERE mint IN (SELECT mint FROM curve_creates WHERE recv >= ? AND recv < ?)
                            ORDER BY mint, recv""", [a, b]).df()
        for m, g in tr.groupby("mint", sort=False):
            if m not in cinfo.index:
                continue
            ci = cinfo.loc[m]
            ct, creator = ci.ct, ci.creator
            T = g.recv.to_numpy()
            buy = g.buy.to_numpy()
            sol = g.sol.to_numpy()
            vs, vt = g.vs.to_numpy(), g.vt.to_numpy()
            usr = g.usr.to_numpy()
            slot = g.slot.to_numpy()
            tc = comp.get(m)
            for age in AGES:
                t = ct + age
                if t + LATENCY + max(HORIZONS) > data_end:
                    continue
                if tc is not None and tc <= t:
                    break                                       # already migrated: off the curve
                i = np.searchsorted(T, t, side="right")         # trades known at t
                if i == 0:
                    continue
                mc = vs[i - 1] / vt[i - 1] * 1e9                # SOL per token x 1e9 supply = market cap in SOL
                f = {"mint": m, "age": age, "t": t, "creator_prior": ci.creator_prior,
                     "creator_prior_mig": ci.creator_prior_mig, "mcap": mc, "vsol": vs[i - 1],
                     "n_trades": i, "s_since_last": t - T[i - 1]}
                for w in (5, 15, 60):
                    j = np.searchsorted(T, t - w, side="right")
                    f[f"ret_{w}"] = mc / (vs[j - 1] / vt[j - 1] * 1e9) - 1 if j > 0 else np.nan
                for w in (10, 30):
                    j = np.searchsorted(T, t - w, side="right")
                    sb, ss = buy[j:i], ~buy[j:i]
                    f[f"buys_{w}"] = int(sb.sum())
                    f[f"sells_{w}"] = int(ss.sum())
                    f[f"net_flow_{w}"] = float(sol[j:i][sb].sum() - sol[j:i][ss].sum())
                    f[f"uniq_buyers_{w}"] = len(set(usr[j:i][sb]))
                bm = buy[:i]
                f["uniq_buyers"] = len(set(usr[:i][bm]))
                f["largest_buy"] = float(sol[:i][bm].max()) if bm.any() else 0.0
                dev = usr[:i] == creator
                f["dev_in"] = float(sol[:i][dev & bm].sum())
                f["dev_out"] = float(sol[:i][dev & ~bm].sum())
                f["launch_block_buyers"] = int(((slot[:i] <= ci.cslot + 1) & bm & ~dev).sum())
                f["sell_share"] = float((~bm).mean())
                # entry and exits on the curve
                k = np.searchsorted(T, t + LATENCY, side="right")
                vs0, vt0 = vs[max(k, 1) - 1], vt[max(k, 1) - 1]
                for H in HORIZONS:
                    te = t + LATENCY + H
                    if tc is not None and tc <= te:
                        e = np.searchsorted(T, tc, side="left")     # last curve state before completion
                    else:
                        e = np.searchsorted(T, te, side="right")
                    e = max(e, k, 1)
                    f[f"pnl_{H}"] = round_trip(vs0, vt0, vs[e - 1], vt[e - 1])
                # take-profit / stop-loss exits within MAXHOLD (decision on a print, fill at the curve state
                # LATENCY later); stored WITHOUT the fixed per-tx fee so it can be priced separately: pnl = g - 2*tip
                p0 = vs0 / vt0
                for maxhold in (120, 300):
                    te = t + LATENCY + maxhold
                    lim = np.searchsorted(T, min(te, tc) if tc is not None else te, side="left" if tc is not None and tc <= te else "right")
                    lim = max(lim, k)
                    px = vs[k:lim] / vt[k:lim]
                    for tp, sl in EXITS:
                        hit = np.nonzero((px >= p0 * (1 + tp)) | (px <= p0 * (1 - sl)))[0]
                        if len(hit):
                            e = np.searchsorted(T, T[k + hit[0]] + LATENCY, side="right")
                            if tc is not None:
                                e = min(e, np.searchsorted(T, tc, side="left"))
                        else:
                            e = lim
                        e = max(e, k, 1)
                        f[f"g_tp{int(tp * 100)}_sl{int(sl * 100)}_{maxhold}"] = round_trip(vs0, vt0, vs[e - 1], vt[e - 1]) + 2 * FIXED
                f["migrated"] = tc is not None
                rows.append(f)
        print("day", day, "rows", len(rows), flush=True)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    d = main()
    suffix = ("" if LATENCY == 1.0 else f"_lat{LATENCY:g}") + ("" if "RR_AGES" not in os.environ else "_late")
    d.to_parquet(config.path("data") / "processed" / f"ml_snapshots{suffix}.parquet")
    print(d.shape)
    print(d.groupby("age")[[f"pnl_{h}" for h in HORIZONS]].mean().round(4))
