"""H-CTO: buy migrated pump.fun tokens after a DexScreener community takeover (CTO) becomes public; hour-scale holds.

Data:
  - CTO times: research/observations/evidence_cto_orders_backfill.json (orders/v1, first APPROVED communityTakeover,
    paymentTimestamp). Public visibility = payment + LAG (claimDate is not in the backfill; the measured
    payment->claimDate lag of 10 live CTOs is in evidence_cto_visibility_lag.json).
  - Prices: data/raw/web/ohlcv15_cto/<pool>.json (GeckoTerminal 15-min USD bars, fetched with before_timestamp and
    filtered so no bar ends after 1791072000).

Rule (pre-declared grid, see GRID): T = payment + LAG. Entry at the open of the first bar starting at or after T
(no bar within 1 h -> no trade). Exits on bar closes: TP / SL checked on each close, otherwise the close of the last
bar ending by entry + hold (dead tokens count at their last price). Cost 2% per side.
Liquidity proxy (pump AMM constant product from the migration reserves 85 SOL x 206.9M tokens):
quote reserve y = sqrt(K * price_SOL); liquidity = 2 * y * SOLUSD, from the last completed bar before entry.

Splits by CTO payment time. Train: P < 1790882100 or 1790899200 <= P < 1790985600, and the trade window must not
touch [1790882100, 1790899200). Validation: 1790985600 <= P < 1791072000. Every trade must exit by 1791072000.

    python scripts/research/cto_sim.py train         # grid on train + controls; writes evidence
    python scripts/research/cto_sim.py validate CFG  # once, only configs that passed train
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "data/raw/web/ohlcv15_cto"
OLD = ROOT / "data/raw/web/ohlcv15"
ORD = ROOT / "research/observations/evidence_cto_orders_backfill.json"
SOL = ROOT / "data/raw/web/solusd/solusdt_1m_20261001_20261003.parquet"
BAR, COST, CUT = 900, 0.02, 1791072000
HO_A, HO_B, VAL_A = 1790882100, 1790899200, 1790985600
K = 84.99 * 206.9e6

GRID = {}
for liq in (0, 10_000):
    for hold in (4, 24):
        for tp, sl in ((None, None), (None, 0.40), (0.50, 0.25), (1.00, 0.40)):
            name = f"L15_H{hold}_{'TP%d' % (tp * 100) if tp else 'noTP'}_{'SL%d' % (sl * 100) if sl else 'noSL'}_liq{liq // 1000}k"
            GRID[name] = dict(lag=15, hold=hold, tp=tp, sl=sl, liq=liq)
for hold in (4, 24):
    GRID[f"L60_H{hold}_noTP_noSL_liq0k"] = dict(lag=60, hold=hold, tp=None, sl=None, liq=0)


def load():
    """Refetched pools (ohlcv15_cto, complete up to CUT) override the Oct-3 cache (ohlcv15, complete only up to its
    own fetched_at). Each pool carries `cut`: no trade may end after it."""
    ds = {}
    for src in (OLD, DIR):
        for f in src.glob("*.json"):
            d = json.loads(f.read_text())
            d["cut"] = min(CUT, d.get("data_cut", d["fetched_at"] // BAR * BAR))
            b = np.array(d["ohlcv"], dtype=float).reshape(-1, 6)
            b = b[b[:, 0] + BAR <= d["cut"]]
            d["bars"] = b
            if len(b):
                ds[d["mint"]] = d
    rows = json.loads(ORD.read_text())["rows"]
    cto = {}
    for m, r in rows.items():
        ps = sorted(o["paymentTimestamp"] / 1000 for o in r.get("orders", [])
                    if o["type"] == "communityTakeover" and o.get("status") == "approved")
        if ps:
            cto[m] = ps[0]
    sol = pd.read_parquet(SOL)
    return ds, cto, sol


def solusd(sol, t):
    i = np.searchsorted(sol.t.values, t, side="right") - 1
    return float(sol.close.values[max(i, 0)])


def trade(d, T, c, sol, cost=COST):
    """Enter at first bar open >= T; returns dict or None."""
    b = d["bars"]
    after = b[b[:, 0] >= T]
    if not len(after) or after[0, 0] > T + 3600:
        return None
    E, entry = after[0, 0], after[0, 1]
    end = E + c["hold"] * 3600
    if end > d["cut"]:
        return None
    known = b[b[:, 0] + BAR <= E]
    if not len(known):
        return None
    last = known[-1, 4]
    s = solusd(sol, E)
    liq = 2 * np.sqrt(K * last / s) * s
    if liq < c["liq"]:
        return None
    win = b[(b[:, 0] >= E) & (b[:, 0] + BAR <= end)]
    exit_, why = (win[-1, 4], "time") if len(win) else (entry, "time")
    for row in win:
        r = row[4] / entry - 1
        if c["sl"] is not None and r <= -c["sl"]:
            exit_, why = row[4], "sl"
            break
        if c["tp"] is not None and r >= c["tp"]:
            exit_, why = row[4], "tp"
            break
    return {"mint": d["mint"], "E": E, "end": end, "entry": entry, "exit": exit_, "why": why, "liq": liq,
            "age_h": (E - d["migrated_recv"]) / 3600, "from_ath": last / known[:, 2].max() - 1,
            "net": exit_ * (1 - cost) / (entry * (1 + cost)) - 1}


def stats(x):
    x = np.asarray(sorted(x))
    if not len(x):
        return {"n": 0}
    g, l = x[x > 0].sum(), -x[x < 0].sum()
    pf = g / l if l > 0 else float("inf")
    return {"n": int(len(x)), "net": round(float(x.sum()), 3), "mean": round(float(x.mean()), 4),
            "median": round(float(np.median(x)), 4), "pf": round(float(pf), 3), "share_up": round(float((x > 0).mean()), 3),
            "net_wo_top3": round(float(x[:-3].sum()), 3) if len(x) > 3 else None}


def passes(s):
    return s["n"] >= 50 and s["net"] > 0 and s["pf"] > 1.2 and (s["net_wo_top3"] or -1) > 0


def in_split(P, tr, split):
    if split == "train":
        ok = P < HO_A or HO_B <= P < VAL_A
        return ok and (tr is None or tr["end"] <= HO_A or tr["E"] >= HO_B)
    return VAL_A <= P < CUT


def run(split, cfgs, ds, cto, sol):
    out = {}
    for name in cfgs:
        c = GRID[name]
        tr, ctl, pre = [], [], []
        for m, P in cto.items():
            d = ds.get(m)
            if d is None or P < d["migrated_recv"] or not in_split(P, None, split):
                continue
            t = trade(d, P + c["lag"] * 60, c, sol)
            if t is None or not in_split(P, t, split):
                continue
            tr.append(t)
            # control 1: same token, entry one hold earlier, exit by the CTO trade's entry (no CTO yet)
            p = trade(d, t["E"] - c["hold"] * 3600, c, sol)
            if p is not None and p["E"] >= d["migrated_recv"] and p["end"] <= t["E"]:
                pre.append(p["net"] - t["net"])
            # control 2: tokens with no CTO before the exit, same clock time, similar age and drawdown
            cs = []
            for m2, d2 in ds.items():
                if m2 == m or cto.get(m2, 9e18) <= t["end"]:
                    continue
                q = trade(d2, P + c["lag"] * 60, c, sol)
                if q is None or q["E"] != t["E"]:
                    continue
                if abs(np.log(q["age_h"] / t["age_h"])) <= np.log(1.5) and abs(q["from_ath"] - t["from_ath"]) <= 0.15:
                    cs.append(q["net"])
            if cs:
                ctl.append((t["net"], float(np.mean(cs)), len(cs)))
        s = stats([t["net"] for t in tr])
        s["pass"] = passes(s) if s["n"] else False
        s["exits"] = pd.Series([t["why"] for t in tr]).value_counts().to_dict() if tr else {}
        if ctl:
            a = np.array([(x, y) for x, y, _ in ctl])
            s["matched_ctrl"] = {"n_cto_with_ctrl": len(ctl), "cto_mean": round(float(a[:, 0].mean()), 4),
                                 "ctrl_mean": round(float(a[:, 1].mean()), 4),
                                 "ctrl_median_of_means": round(float(np.median(a[:, 1])), 4),
                                 "ctrl_tokens_per_cto_median": int(np.median([k for *_, k in ctl]))}
        if pre:
            s["same_token_pre_cto_minus_cto"] = {"n": len(pre), "mean_diff": round(float(np.mean(pre)), 4)}
        # cost robustness: per-side cost = max(2%, 1.25% fee + impact of 0.5 SOL on the quote reserve)
        if tr:
            r2 = []
            for t in tr:
                y = t["liq"] / 2 / solusd(sol, t["E"])
                cst = max(COST, 0.0125 + 0.5 / max(y, 1e-9))
                r2.append(t["exit"] * (1 - cst) / (t["entry"] * (1 + cst)) - 1)
            s["net_liq_cost"] = stats(r2)
        out[name] = s
        print(name, {k: s.get(k) for k in ("n", "net", "mean", "median", "pf", "net_wo_top3", "share_up", "pass")},
              s.get("matched_ctrl"), flush=True)
    return out


if __name__ == "__main__":
    ds, cto, sol = load()
    split = sys.argv[1]
    cnt = {"cto_total_in_universe": len(cto),
           "with_ohlcv": sum(m in ds for m in cto),
           "before_migration": sum(1 for m, P in cto.items() if m in ds and P < ds[m]["migrated_recv"]),
           "train": sum(1 for m, P in cto.items() if m in ds and P >= ds[m]["migrated_recv"] and in_split(P, None, "train")),
           "validation": sum(1 for m, P in cto.items() if m in ds and P >= ds[m]["migrated_recv"] and in_split(P, None, "val")),
           "after_cut": sum(1 for P in cto.values() if P >= CUT)}
    print(cnt)
    if split == "train":
        res = run("train", list(GRID), ds, cto, sol)
        Path(ROOT / "research/observations/evidence_cto_train.json").write_text(json.dumps(
            {"counts": cnt, "n_configs": len(GRID), "grid": GRID, "results": res}, indent=1, default=str))
    elif split == "validate":
        cfgs = sys.argv[2:]
        tr = json.loads((ROOT / "research/observations/evidence_cto_train.json").read_text())["results"]
        assert all(tr[c]["pass"] for c in cfgs), "only train-passing configs may be validated"
        res = run("val", cfgs, ds, cto, sol)
        Path(ROOT / "research/observations/evidence_cto_validation.json").write_text(json.dumps(
            {"counts": cnt, "configs": cfgs, "results": res}, indent=1, default=str))
    elif split == "counts":
        pass
