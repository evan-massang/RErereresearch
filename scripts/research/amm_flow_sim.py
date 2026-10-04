"""Non-overlapping trade simulation of a small, pre-declared grid of PumpSwap order-flow rules (agent amm_flow).

Decisions at the 15 s snapshot grid built by amm_flow_features.py (point-in-time features). One open position
per pool; the next decision after an exit is the first grid time >= exit time. Entry: 0.5 SOL at t+1 s,
conservative exact constant-product fill (amm_flow_lib.state_for). Exits:
- "H600": sell at entry+600 s;
- "TPSL": watch the pool's post-trade mid after entry; first trade with mid >= entry_mid*(1+tp) or
  <= entry_mid*(1-sl) triggers a sell at that trade's recv + 1 s (conservative fill); else sell at entry+600 s.
Tips: 0.001 and 0.01 SOL per transaction (2 per round trip). Fees: fee_bps/1e4 per side (main), with
sensitivities: +0.25%/side extra fee, and reserve = logged - 17.6 (brief's estimate) instead of logged + 17.585.

Usage: python scripts/research/amm_flow_sim.py train SNAP.parquet OUT.json [config names to run, default all]
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/RErereresearch/scripts/research")
import amm_flow_lib as L  # noqa: E402

MAXH = 600.0


def _grid() -> dict:
    g = {}
    ex = {"H600": None, "TPSL5": (0.05, 0.05)}
    for exn, e in ex.items():
        # 1. order-flow momentum (5 min imbalance + many distinct buyers)
        for th in (0.5, 0.7):
            for rs in (100, 600):
                g[f"ofi_mom_th{th}_rs{rs}_{exn}"] = (
                    lambda d, th=th, rs=rs: (d.ofi300 >= th) & (d.nbw60 >= 10) & (d.rs >= rs), e)
        # 2. contrarian: heavy selling over the last minute, price down >= 5%
        for rs in (100, 600):
            g[f"ofi_rev_rs{rs}_{exn}"] = (
                lambda d, rs=rs: (d.ofi60 <= -0.5) & (d.ret60 <= -0.05) & (d.rs >= rs), e)
        # 3. absorption of a large sell: >= x% of SOL reserve sold in one trade in the last 60 s, price has
        #    recovered >= 70% of that trade's drop, and net buying over the minute
        for bs in (0.01, 0.03):
            g[f"absorb_bs{bs}_{exn}"] = (
                lambda d, bs=bs: (d.bigsell60 >= bs) & (d.recov60 >= 0.7) & (d.ofi60 > 0) & (d.rs >= 100), e)
        # 4. streak of buys from distinct wallets
        for k in (8, 15):
            for rs in (100, 600):
                g[f"streak{k}_rs{rs}_{exn}"] = (lambda d, k=k, rs=rs: (d.streak >= k) & (d.rs >= rs), e)
        # 5. deep dip from the post-migration high with buying returning (age >= 30 min)
        for dd in (-0.5, -0.3):
            g[f"dip{dd}_{exn}"] = (
                lambda d, dd=dd: (d.dd <= dd) & (d.ofi60 >= 0.5) & (d.age >= 1800) & (d.rs >= 100), e)
        # 6. young pool (< 30 min since migration) near its high with net buying
        g[f"young_{exn}"] = (lambda d: (d.age < 1800) & (d.dd >= -0.1) & (d.ofi300 >= 0.5) & (d.rs >= 100), e)
    return g


GRID = _grid()


def simulate(snap: pd.DataFrame, arrays: dict, rule, exit_, extra_fee=0.0, alt=False) -> list[dict]:
    sig = snap[rule(snap).fillna(False).to_numpy()]
    trades = []
    for pool, g in sig.groupby("pool", sort=False):
        a = arrays[pool]["alt" if alt else "main"]
        busy_until = -1.0
        for t in g.t.to_numpy():
            if t < busy_until:
                continue
            te = t + 1.0
            tx = te + MAXH
            if exit_ is not None:
                tp, sl = exit_
                rs, rt, _, ok = L.state_for(a, np.array([te]), "buy")
                m0 = rs[0] / rt[0]
                i0 = np.searchsorted(a["recv"], te, side="right")
                i1 = np.searchsorted(a["recv"], te + MAXH, side="right")
                m = a["mid"][i0:i1]
                hit = np.nonzero((m >= m0 * (1 + tp)) | (m <= m0 * (1 - sl)))[0]
                if len(hit):
                    tx = a["recv"][i0 + hit[0]] + 1.0
            p = L.round_trip(a, np.array([te]), np.array([tx]), extra_fee=extra_fee)[0]
            trades.append({"pool": pool, "t": float(t), "pnl": float(p), "hold": tx - te})
            busy_until = tx + 1.0
    return trades


def main(split: str, snap_path: str, out: str, names: list[str]) -> None:
    snap = pd.read_parquet(snap_path)
    df, _ = L.load(split)
    df = df[df.pool.isin(set(snap.pool))]
    arrays = {p: {"main": L.pool_arrays(g), "alt": L.pool_arrays(g, offset=-17.6)}
              for p, g in df.groupby("pool", sort=False)}
    del df
    res = {}
    for name in names or list(GRID):
        rule, ex = GRID[name]
        tr = simulate(snap, arrays, rule, ex)
        p = np.array([x["pnl"] for x in tr]) if tr else np.array([])
        r = {"tip0.001": L.stats(p, 0.001), "tip0.01": L.stats(p, 0.01), "pools": len({x["pool"] for x in tr})}
        r["pass_tip0.001"] = L.passes(r["tip0.001"])
        r["pass_tip0.01"] = L.passes(r["tip0.01"])
        if r["pass_tip0.001"] or split == "valid":
            px = np.array([x["pnl"] for x in simulate(snap, arrays, rule, ex, extra_fee=0.0025)])
            pa = np.array([x["pnl"] for x in simulate(snap, arrays, rule, ex, alt=True)])
            r["sens_extra_fee_tip0.001"] = L.stats(px, 0.001)
            r["sens_reserve_minus17.6_tip0.001"] = L.stats(pa, 0.001)
            if tr:
                pp = pd.DataFrame(tr).groupby("pool").pnl.sum().sort_values()
                r["top_pools_pnl"] = pp.tail(5).round(4).to_dict()
        res[name] = r
        s = r["tip0.001"]
        print(f"{name:32s} n={s.get('n',0):5d} net={s.get('net')} pf={s.get('pf')} ex3={s.get('net_ex3')} "
              f"win={s.get('win')} | tip.01 net={r['tip0.01'].get('net')} pools={r['pools']}", flush=True)
    json.dump({"split": split, "n_configs": len(res), "results": res}, open(out, "w"), indent=1, default=str)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:])
