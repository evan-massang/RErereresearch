"""H-LPSELL: passive PumpSwap LP position, exact constant-product share-of-k accounting.

Research only (agent "lpsell_clock", 2026-10-05). Reads data/market.duckdb READ-ONLY. Writes only
research/observations/evidence_lpsell_<split>.json.

Accounting (exact, robust to third-party deposits/withdrawals):
- True quote reserve R_s = pool_sol_logged + off_pool. off_pool is measured per pool from the exact sell identity
  sol = R_s*tok/(R_t+tok) (median over the pool's sells; ~17.5845 for migrated pools, 0 for a few odd pools).
  It is real SOL: migrated pools are created with quote_in 84.99 SOL while the first logged reserve is 67.41.
- LP fee stays in the reserves, protocol + creator fees leave. Per unit of LP, sqrt(k) grows only through swaps;
  deposits/withdrawals scale k and LP supply together. So per-unit growth G = prod over swaps during the hold of
  sqrt(k_pre(i+1)/k_pre(i)) for consecutive swaps whose token reserve chains exactly (rt_pre(i+1) == rt_post(i)).
  If the chain breaks (liquidity event or missed swap) that step's growth is set to 1 (conservative: fees of
  missed swaps are not credited). Growth per step is clipped to [1, 1.01].
- Position with liquidity L (=sqrt(sol*tok) deposited) is worth sol = L*G*sqrt(P), tok = L*G/sqrt(P) at price P.
- Entry: 0.5 SOL total; swap s SOL into tokens through the pool (exact fill, fee on top, conservative higher-priced
  state), deposit the rest balanced at the post-swap price. Exit: withdraw at the conservative lower-priced state,
  then sell the withdrawn tokens through the pool (reserves reduced by our withdrawal), fee charged.
- Costs: 4 transactions (swap, deposit, withdraw, sell) x (tip + 5000 lamports base fee).
- Benchmarks: cash (0) and holding 0.5 SOL of the token over the same window (amm_flow_lib.round_trip).
- Stop: if a swap's post-trade mid <= 0.6 x entry mid during the hold, exit at that time + 1 s.

Splits: train = recv < 1790882100 or 1790899200 <= recv < 1790985600; valid = 1790985600..1791072000.
Holdout and forward rows are never loaded. Pools created inside the holdout are dropped. Entry and exit must lie
in the same segment.
"""
from __future__ import annotations

import json
import sys
import numpy as np
import pandas as pd
import duckdb

sys.path.insert(0, "/home/user/RErereresearch/scripts/research")
from amm_flow_lib import state_for, stats, passes  # noqa: E402

DB = "/home/user/RErereresearch/data/market.duckdb"
HOLD_A, HOLD_B = 1790882100, 1790899200
VAL_A, VAL_B = 1790985600, 1791072000
SEG = {"train": [(0, HOLD_A), (HOLD_B, VAL_A)], "valid": [(VAL_A, VAL_B)]}
SIZE = 0.5
BASE_FEE = 5e-6
NTX = 4
AGES = [600, 3600, 14400]
HOLDS = [3600, 14400]
VTHR = [0.0, 2.0, 5.0]
MIN_RES = 50.0
STOP = 0.6


def load(split):
    con = duckdb.connect(DB, read_only=True)
    where = f"(recv < {HOLD_A} OR (recv >= {HOLD_B} AND recv < {VAL_A}))"
    if split == "valid":
        where = f"(recv < {HOLD_A} OR (recv >= {HOLD_B} AND recv < {VAL_B}))"
    pools = con.execute("SELECT pool, min(recv) AS created FROM amm_pools GROUP BY pool").df()
    pools = pools[~((pools.created >= HOLD_A) & (pools.created < HOLD_B)) & (pools.created < VAL_B)]
    df = con.execute(f"""SELECT recv, slot, pool, buy, tok, sol, pool_tok_logged AS rt, pool_sol_logged AS rs_log,
                         fee_bps FROM amm_trades WHERE {where} AND tok > 0 AND sol > 0""").df()
    con.close()
    df = df[df.pool.isin(set(pools.pool))]
    df = df.sort_values(["pool", "slot", "recv"], kind="stable").reset_index(drop=True)
    return df, dict(zip(pools.pool, pools.created))


def pool_arrays(g):
    recv = g.recv.to_numpy()
    buy = g.buy.to_numpy()
    tok = g.tok.to_numpy()
    sol = g.sol.to_numpy()
    rt_pre = g.rt.to_numpy()
    rsl = g.rs_log.to_numpy()
    s = ~buy
    if s.sum() > 0:
        off = float(np.median(sol[s] * (rt_pre[s] + tok[s]) / tok[s] - rsl[s]))
    else:
        off = 17.5845
    rs_pre = np.maximum(rsl + off, 1e-3)
    rt_post = np.maximum(np.where(buy, rt_pre - tok, rt_pre + tok), 1.0)
    # post state: next pre-state when the token side chains exactly, else constant product without fee
    chain = np.zeros(len(recv), bool)
    chain[:-1] = np.isclose(rt_pre[1:], rt_post[:-1], rtol=1e-9, atol=1e-3)
    rs_post_cp = np.where(buy, rs_pre * rt_pre / rt_post, rs_pre - sol)
    rs_post = rs_post_cp.copy()
    rs_post[:-1] = np.where(chain[:-1], rs_pre[1:], rs_post_cp[:-1])
    rs_post = np.maximum(rs_post, 1e-6)
    k_pre = rs_pre * rt_pre
    grow = np.ones(len(recv))
    grow[:-1] = np.where(chain[:-1], np.sqrt(np.clip(k_pre[1:] / k_pre[:-1], 1.0, 1.01 ** 2)), 1.0)
    return {"recv": recv, "buy": buy, "tok": tok, "sol": sol, "fee": g.fee_bps.to_numpy() / 1e4,
            "rs_pre": rs_pre, "rt_pre": rt_pre, "rs_post": rs_post, "rt_post": rt_post,
            "mid": rs_post / rt_post, "lg": np.cumsum(np.log(grow)), "off": off, "chain_frac": float(chain[:-1].mean()) if len(recv) > 1 else 1.0}


def lp_trade(a, t0, t1, tip):
    """Return dict with LP pnl, hold pnl, fee growth, exit reason; or None if no state."""
    rs, rt, f, ok = state_for(a, np.array([t0]), "buy")
    if not ok[0]:
        return None
    rs, rt, f = float(rs[0]), float(rt[0]), float(f[0])
    p_entry = rs / rt
    # solve swap size s so that remaining SOL matches the post-swap price * tokens
    lo, hi = 0.0, SIZE
    for _ in range(60):  # bisection on s + q(s)*p1(s) = SIZE (left side increasing in s)
        s = 0.5 * (lo + hi)
        x = s / (1 + f)
        q = rt * x / (rs + x)
        p1 = (rs + x) / (rt - q)
        if s + q * p1 > SIZE:
            hi = s
        else:
            lo = s
    s = lo
    x = s / (1 + f)
    q = rt * x / (rs + x)
    p1 = (rs + x) / (rt - q)
    dep_sol = SIZE - s
    dep_tok = min(q, dep_sol / p1)
    L = np.sqrt(dep_sol * dep_tok)
    leftover = dep_sol - dep_tok * p1  # ~0
    # stop check on post-trade mids in (t0, t1]
    recv = a["recv"]
    i0 = np.searchsorted(recv, t0, side="right")
    i1 = np.searchsorted(recv, t1, side="right")
    texit, reason = t1, "time"
    if i1 > i0:
        hit = np.nonzero(a["mid"][i0:i1] <= STOP * p_entry)[0]
        if len(hit):
            texit, reason = float(recv[i0 + hit[0]]) + 1.0, "stop"
    j1 = np.searchsorted(recv, texit, side="right")
    lg0 = a["lg"][i0 - 1] if i0 > 0 else 0.0
    lg1 = a["lg"][j1 - 2] if j1 - 2 >= 0 else 0.0  # growth of swaps i0..j1-2 needs pre-state of j1-1 (known by texit)
    G = float(np.exp(max(lg1 - lg0, 0.0))) if j1 - 1 > i0 else 1.0
    rs2, rt2, f2, ok2 = state_for(a, np.array([texit]), "sell")
    if not ok2[0]:
        return None
    rs2, rt2, f2 = float(rs2[0]), float(rt2[0]), float(f2[0])
    P = rs2 / rt2
    w_sol = L * G * np.sqrt(P)
    w_tok = L * G / np.sqrt(P)
    w_sol = min(w_sol, rs2 * 0.5)
    w_tok = min(w_tok, rt2 * 0.5)
    rsr, rtr = rs2 - w_sol, rt2 - w_tok
    out = rsr * w_tok / (rtr + w_tok) * (1 - f2)
    costs = NTX * (tip + BASE_FEE)
    lp = w_sol + out + leftover - SIZE - costs
    # hold-token benchmark: buy SIZE at entry state, sell at exit state, 2 tx
    xq = SIZE / (1 + f)
    qq = rt * xq / (rs + xq)
    hold = rs2 * qq / (rt2 + qq) * (1 - f2) - SIZE - 2 * (tip + BASE_FEE)
    # mark-to-mid decomposition (no exit costs)
    il = 2 * np.sqrt(P / p1) / (1 + P / p1) - 1  # value vs hold at same mid, no fee
    return {"lp": lp, "hold": hold, "G": G, "pr": P / p_entry, "reason": reason, "il": il,
            "entry_cost": SIZE - (dep_sol + dep_tok * p_entry + leftover)}


def run(split):
    df, created = load(split)
    segs = SEG[split]
    rows = []
    offs = []
    for pool, g in df.groupby("pool", sort=False):
        c = created.get(pool)
        if c is None or len(g) < 5:
            continue
        a = pool_arrays(g)
        offs.append((a["off"], a["chain_frac"]))
        recv = a["recv"]
        csum = np.cumsum(a["sol"])
        for A in AGES:
            t0 = c + A
            for H in HOLDS:
                t1 = t0 + H
                if not any(lo <= t0 and t1 < hi for lo, hi in segs):
                    continue
                if split == "valid" and t0 < VAL_A:
                    continue
                il = np.searchsorted(recv, t0, side="right") - 1
                if il < 0:
                    continue
                if t0 - recv[il] > 3600:  # pool dead for 1 h before entry: skip (no state confidence)
                    continue
                res_true = a["rs_post"][il]
                if res_true < MIN_RES:
                    continue
                j = np.searchsorted(recv, t0 - 3600, side="left")
                vol1h = csum[il] - (csum[j - 1] if j > 0 else 0.0)
                vt = vol1h / (2 * res_true)
                for tip in (0.001, 0.01):
                    r = lp_trade(a, t0, t1, tip)
                    if r is None:
                        continue
                    r.update({"pool": pool, "A": A, "H": H, "vt": vt, "tip": tip, "res": res_true, "t0": t0,
                              "fee_tier": float(a["fee"][il])})
                    rows.append(r)
    return pd.DataFrame(rows), offs


def summarize(R):
    out = {}
    for A in AGES:
        for H in HOLDS:
            for V in VTHR:
                name = f"A{A}_H{H}_V{V:g}"
                d = {}
                for tip in (0.001, 0.01):
                    x = R[(R.A == A) & (R.H == H) & (R.vt >= V) & (R.tip == tip)]
                    s = stats(x.lp.to_numpy(), 0.0)
                    s["pass"] = passes(s) if s.get("n") else False
                    s["hold_benchmark"] = stats(x.hold.to_numpy(), 0.0)
                    if len(x):
                        s["median_fee_growth_pct"] = round(float((x.G.median() - 1) * 100), 3)
                        s["mean_fee_growth_pct"] = round(float((x.G.mean() - 1) * 100), 3)
                        s["median_price_ratio"] = round(float(x.pr.median()), 4)
                        s["mean_il_pct"] = round(float(x.il.mean() * 100), 3)
                        s["stop_frac"] = round(float((x.reason == "stop").mean()), 3)
                        s["mean_entry_cost_sol"] = round(float(x.entry_cost.mean()), 5)
                    d[f"tip{tip}"] = s
                out[name] = d
    return out


if __name__ == "__main__":
    split = sys.argv[1] if len(sys.argv) > 1 else "train"
    only = sys.argv[2].split(",") if len(sys.argv) > 2 else None
    R, offs = run(split)
    summ = summarize(R)
    if only:
        summ = {k: v for k, v in summ.items() if k in only}
    o = np.array(offs)
    meta = {"split": split, "n_pools_seen": len(offs),
            "offset_quantiles": np.quantile(o[:, 0], [0.05, 0.25, 0.5, 0.75, 0.95]).round(4).tolist(),
            "chain_frac_median": float(np.median(o[:, 1])),
            "configs": len(AGES) * len(HOLDS) * len(VTHR), "size_sol": SIZE, "ntx": NTX, "min_res": MIN_RES,
            "stop": STOP}
    print(json.dumps(meta))
    for k, v in summ.items():
        t = v["tip0.001"]
        if t.get("n"):
            print(k, "n", t["n"], "net", t["net"], "pf", t["pf"], "ex3", t["net_ex3"], "med", t["median"],
                  "feeG%", t.get("median_fee_growth_pct"), t.get("mean_fee_growth_pct"), "pr", t.get("median_price_ratio"),
                  "IL%", t.get("mean_il_pct"), "stop", t.get("stop_frac"),
                  "| hold net", t["hold_benchmark"].get("net"), "| tip.01 net", v["tip0.01"].get("net"), "PASS" if t["pass"] else "")
    tag = "train" if split == "train" else "valid"
    with open(f"/home/user/RErereresearch/research/observations/evidence_lpsell_{tag}.json", "w") as fh:
        json.dump({"meta": meta, "configs": summ}, fh, indent=1)
    R.to_parquet(f"/tmp/claude-0/-home-user-RErereresearch/f8ba0823-6528-5b3d-92e7-a2d8665674ee/scratchpad/lpsell_{tag}.parquet")
