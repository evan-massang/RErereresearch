"""H-LPHEDGE historical simulation (pre-registration: reports/hypotheses/lphedge_preregistration.json).

Delta-hedged full-range PumpSwap LP: P1 = PUMP/USDC (hedge Lighter PUMP), P2 = PENGU/SOL (hedge Lighter PENGU + SOL).
Inputs (data/raw/web/lphedge/, from scripts/research/lphedge_fetch.py): GeckoTerminal 15m pool OHLCV, PumpSwap
Deposit/WithdrawEvents (liquidity history), Lighter 15m candles + 1h funding, Lighter order-book spreads.

    python scripts/research/lphedge_sim.py train          # 12-config grid on train, applies the selection rule
    python scripts/research/lphedge_sim.py validation     # runs ONLY the config chosen on train, once
"""
import json
import math
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data/raw/web/lphedge"
EVID = ROOT / "research/observations"


def ts(s):
    return int(datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


SPLITS = {"train": (ts("2026-04-08"), ts("2026-07-25")), "validation": (ts("2026-07-25"), ts("2026-10-05"))}
BAR = 900
LP_BPS = 25
SIZE = 5000.0
GAS_SOL_PER_TX, TX_PER_DAY = 0.0005, 2
POOL_FEE_TOTAL_BPS = 30            # lp 25 + protocol 5 + creator 0 (measured)
SOL_ACQ_BPS = 5                    # P2 setup only: acquiring/selling the SOL half (assumption, stated)
POOLS = {"P1": {"name": "PUMP_USDC", "base_dec": 6, "quote_dec": 6, "tok": "PUMP", "sol_leg": False},
         "P2": {"name": "PENGU_SOL", "base_dec": 6, "quote_dec": 9, "tok": "PENGU", "sol_leg": True}}
GRID = [(u, b, iv) for u in ("P1", "P1+P2") for b in (0.02, 0.05, 0.10) for iv in (900, 3600)]


def load_json(n):
    return json.loads((D / n).read_text())


def half_spreads():
    rows = [json.loads(l) for l in open(D / "lighter_spreads.jsonl")]
    rows += [json.loads(l) for l in open(ROOT / "data/raw/web/memelead/lighter_spreads_20261005T1021Z.jsonl")]
    out = {}
    for c in ("PUMP", "PENGU", "SOL"):
        x = [r["rt1000_bp"] for r in rows if r["coin"] == c and r.get("rt1000_bp") is not None]
        out[c] = {"n": len(x), "median_rt_bp": statistics.median(x), "half_bp": statistics.median(x) / 2}
    return out


def liquidity_fn(pool):
    """Pool liquidity sqrt(base*quote) in HUMAN units at time t, from Deposit/WithdrawEvents (pre-event values)."""
    p = POOLS[pool]
    ev = sorted(load_json(f"lp_events_{p['name']}.json")["events"], key=lambda e: (e["slot"], e["ts"]))
    pts = []   # (time, supply_after, r = sqrtk_per_lp at that time)
    for e in ev:
        r = math.sqrt(e["pool_base"] * e["pool_quote"]) / e["lp_supply"]
        sup_after = e["lp_supply"] + (e["lp_amount"] if e["kind"] == "DepositEvent" else -e["lp_amount"])
        pts.append((e["ts"], e["lp_supply"], sup_after, r))
    scale = 10 ** ((p["base_dec"] + p["quote_dec"]) / 2)
    times = np.array([q[0] for q in pts], float)
    rs = np.array([q[3] for q in pts])

    def L(t):
        i = int(np.searchsorted(times, t, side="right"))     # events at or before t: 0..i-1
        sup = pts[0][1] if i == 0 else pts[i - 1][2]
        r = float(np.interp(t, times, rs))
        return sup * r / scale
    return L, len(pts), pts


def series(pool, t0, t1):
    """15m grid points k = t0 + k*BAR (k = 0..N). Price at a point = close of the bar ending there."""
    p = POOLS[pool]
    gtok = {r[0]: r for r in load_json(f"gt_{p['name']}_token.json")["ohlcv"]}
    gusd = {r[0]: r for r in load_json(f"gt_{p['name']}_usd.json")["ohlcv"]}
    lc = {m: {c["t"] // 1000: c["c"] for c in load_json(f"lighter_candles_{m}.json")["candles"]}
          for m in ([p["tok"], "SOL"])}
    N = (t1 - t0) // BAR
    grid = [t0 + k * BAR for k in range(N + 1)]
    P, vol, have_pool = [], [], []
    perp = {m: [] for m in lc}
    have_perp = {m: [] for m in lc}
    last = {"P": None, **{m: None for m in lc}}
    for t in grid:
        b = t - BAR                         # bar that ends at t
        if b in gtok:
            last["P"] = gtok[b][4]
        P.append(last["P"])
        vol.append(gusd[b][5] if b in gusd else 0.0)
        have_pool.append(b in gtok)
        for m in lc:
            if b in lc[m]:
                last[m] = lc[m][b]
            perp[m].append(last[m])
            have_perp[m].append(b in lc[m])
    fund = {}
    for m in lc:
        fund[m] = {f["timestamp"]: (float(f["rate"]) / 100.0) * (1 if f["direction"] == "long" else -1)
                   for f in load_json(f"lighter_funding_{m}.json")["fundings"]}
    return grid, np.array(P, float), np.array(vol), have_pool, {m: np.array(v, float) for m, v in perp.items()}, have_perp, fund


def run_pool(pool, b, iv, t0, t1, hs):
    p = POOLS[pool]
    grid, P, vol, have_pool, perp, have_perp, fund = series(pool, t0, t1)
    Lfn, n_ev, _ = liquidity_fn(pool)
    tok, sol = p["tok"], "SOL"
    solpx = perp[sol]
    usd = (lambda k: solpx[k]) if p["sol_leg"] else (lambda k: 1.0)
    V0 = SIZE
    Lo = V0 / usd(0) / (2 * math.sqrt(P[0]))              # our liquidity, human units
    x = lambda k: Lo / math.sqrt(P[k])                     # LP token units
    y = lambda k: Lo * math.sqrt(P[k])                     # LP quote units
    h_tok = x(0)
    h_sol = y(0) if p["sol_leg"] else 0.0
    c_tok, c_sol = hs[tok]["half_bp"] / 1e4, hs[sol]["half_bp"] / 1e4
    # setup (once per split): buy token half through the pool (+impact) and sell it back at the end; open/close shorts
    Lp0 = Lfn(grid[0])
    quote_res_usd = Lp0 * math.sqrt(P[0]) * usd(0)
    half = V0 / 2
    impact = half / quote_res_usd
    setup = 2 * half * (POOL_FEE_TOTAL_BPS / 1e4 + impact)
    setup += 2 * h_tok * perp[tok][0] * c_tok
    if p["sol_leg"]:
        setup += 2 * half * SOL_ACQ_BPS / 1e4 + 2 * h_sol * solpx[0] * c_sol
    days = {}
    step = iv // BAR
    n_trades = 0
    for k in range(len(grid) - 1):
        t = grid[k]
        day = (t - t0) // 86400
        d = days.setdefault(day, {"day": datetime.fromtimestamp(t0 + day * 86400, timezone.utc).strftime("%Y-%m-%d"),
                                  "pool": pool, "lp": 0.0, "fee": 0.0, "hedge": 0.0, "funding": 0.0, "hcost": 0.0,
                                  "gas": 0.0, "n_trades": 0, "bars_pool": 0, "bars_perp_min": 0, "v_start": None,
                                  "vol_usd": 0.0, "tvl_start": None, "rets": []})
        if d["v_start"] is None:
            d["v_start"] = 2 * Lo * math.sqrt(P[k]) * usd(k)
            d["tvl_start"] = 2 * Lfn(t) * math.sqrt(P[k]) * usd(k)
            d["gas"] = TX_PER_DAY * GAS_SOL_PER_TX * solpx[k]
            d["_pp"] = 0
            d["_pq"] = {m: 0 for m in perp}
        # check at point k
        if k % step == 0:
            if abs(x(k) - h_tok) > b * x(k):
                dq = abs(x(k) - h_tok)
                d["hcost"] += dq * perp[tok][k] * c_tok
                h_tok = x(k); d["n_trades"] += 1
            if p["sol_leg"] and abs(y(k) - h_sol) > b * y(k):
                d["hcost"] += abs(y(k) - h_sol) * solpx[k] * c_sol
                h_sol = y(k); d["n_trades"] += 1
        # interval k -> k+1
        d["lp"] += 2 * Lo * (math.sqrt(P[k + 1]) * usd(k + 1) - math.sqrt(P[k]) * usd(k))
        Lp = Lfn(grid[k + 1] - BAR / 2)
        share = Lo / (Lp + Lo)
        d["fee"] += vol[k + 1] * LP_BPS / 1e4 * share
        d["vol_usd"] += vol[k + 1]
        d["hedge"] += -h_tok * (perp[tok][k + 1] - perp[tok][k])
        if p["sol_leg"]:
            d["hedge"] += -h_sol * (solpx[k + 1] - solpx[k])
        tn = grid[k + 1]
        if tn % 3600 == 0:
            for m, hq in ((tok, h_tok), (sol, h_sol)):
                if hq and tn in fund[m]:
                    d["funding"] += fund[m][tn] * hq * perp[m][k + 1]
        d["bars_pool"] += have_pool[k + 1]
        for m in perp:
            d["_pq"][m] += have_perp[m][k + 1]
        if P[k + 1] > 0 and P[k] > 0:
            d["rets"].append(math.log(P[k + 1] / P[k]))
    out = []
    for d in days.values():
        need = [tok] + ([sol] if p["sol_leg"] else [])
        d["bars_perp_min"] = min(d["_pq"][m] for m in need)
        d.pop("_pq"); d.pop("_pp")
        d["pnl"] = d["lp"] + d["fee"] + d["hedge"] + d["funding"] - d["hcost"] - d["gas"]
        r = d.pop("rets")
        d["sigma_day"] = float(np.std(r) * math.sqrt(len(r))) if len(r) > 10 else None
        d["scored"] = d["bars_pool"] >= 90 and d["bars_perp_min"] >= 90
        d["pnl_bp"] = d["pnl"] / d["v_start"] * 1e4
        n_trades += d["n_trades"]
        out.append(d)
    return {"pool": pool, "days": out, "setup": setup, "n_lp_events": n_ev, "impact_frac": impact, "n_trades": n_trades}


def stats(pool_runs):
    days = [d for r in pool_runs for d in r["days"] if d["scored"]]
    pn = [d["pnl"] for d in days]
    setup = sum(r["setup"] for r in pool_runs)
    gp = sum(v for v in pn if v > 0); gl = -sum(v for v in pn if v < 0)
    net = sum(pn) - setup
    top3 = sum(sorted(pn, reverse=True)[:3])
    comp = {k: round(sum(d[k] for d in days), 2) for k in ("lp", "hedge", "fee", "funding", "hcost", "gas", "vol_usd")}
    comp["lp_plus_hedge(LVR+basis)"] = round(comp["lp"] + comp["hedge"], 2)
    s = {"n_pool_days": len(days), "n_unscored_days": sum(1 for r in pool_runs for d in r["days"] if not d["scored"]),
         "unscored_days": [f"{d['pool']}:{d['day']}" for r in pool_runs for d in r["days"] if not d["scored"]],
         "net_usd": round(net, 2), "sum_day_pnl_usd": round(sum(pn), 2), "setup_usd": round(setup, 2),
         "pf": round(gp / gl, 3) if gl > 0 else None, "net_ex_top3_usd": round(net - top3, 2),
         "mean_bp_per_day": round(float(np.mean([d["pnl_bp"] for d in days])), 3) if days else None,
         "win_days": sum(1 for v in pn if v > 0), "n_hedge_trades": sum(d["n_trades"] for d in days),
         "components_usd": comp}
    s["passes_bar"] = bool(s["n_pool_days"] >= 50 and net > 0 and (s["pf"] or 0) > 1.2 and s["net_ex_top3_usd"] > 0)
    per = {}
    for r in pool_runs:
        dd = [d for d in r["days"] if d["scored"]]
        if not dd:
            continue
        sig = [d["sigma_day"] for d in dd if d["sigma_day"]]
        per[r["pool"]] = {"n": len(dd), "net_usd": round(sum(d["pnl"] for d in dd) - r["setup"], 2),
                          "mean_fee_bp": round(float(np.mean([d["fee"] / d["v_start"] * 1e4 for d in dd])), 3),
                          "mean_funding_bp": round(float(np.mean([d["funding"] / d["v_start"] * 1e4 for d in dd])), 3),
                          "mean_lp_plus_hedge_bp": round(float(np.mean([(d["lp"] + d["hedge"]) / d["v_start"] * 1e4 for d in dd])), 3),
                          "mean_hcost_bp": round(float(np.mean([d["hcost"] / d["v_start"] * 1e4 for d in dd])), 3),
                          "mean_gas_bp": round(float(np.mean([d["gas"] / d["v_start"] * 1e4 for d in dd])), 3),
                          "diag_mean_sigma_day": round(float(np.mean(sig)), 4) if sig else None,
                          "diag_sigma2_over_8_bp": round(float(np.mean([s_ ** 2 / 8 for s_ in sig])) * 1e4, 3) if sig else None,
                          "mean_vol_over_tvl": round(float(np.mean([d["vol_usd"] / d["tvl_start"] for d in dd])), 4),
                          "median_tvl_usd": round(float(np.median([d["tvl_start"] for d in dd]))),
                          "setup_usd": round(r["setup"], 2), "price_impact_frac_setup": r["impact_frac"]}
    s["per_pool"] = per
    return s


def run_config(u, b, iv, split, hs):
    t0, t1 = SPLITS[split]
    pools = ["P1"] if u == "P1" else ["P1", "P2"]
    runs = [run_pool(p, b, iv, t0, t1, hs) for p in pools]
    return runs, stats(runs)


def main(split):
    hs = half_spreads()
    cfg_name = lambda c: f"{c[0]}_b{int(c[1]*100)}_{c[2]//60}m"
    if split == "train":
        res = {}
        for c in GRID:
            runs, s = run_config(*c, "train", hs)
            res[cfg_name(c)] = s
            print(cfg_name(c), {k: s[k] for k in ("n_pool_days", "net_usd", "pf", "net_ex_top3_usd", "mean_bp_per_day", "passes_bar")}, flush=True)
        passing = [k for k, v in res.items() if v["passes_bar"]]
        chosen = None
        if passing:
            chosen = max(passing, key=lambda k: (res[k]["net_usd"] / res[k]["n_pool_days"], -res[k]["n_hedge_trades"]))
        # stress (reported, not used for selection): 2x spreads on every config
        hs2 = {k: {**v, "half_bp": v["half_bp"] * 2} for k, v in hs.items()}
        stress = {cfg_name(c): {k: run_config(*c, "train", hs2)[1][k] for k in ("net_usd", "pf", "passes_bar")} for c in GRID}
        out = {"hypothesis": "H-LPHEDGE", "split": "train", "window": [SPLITS["train"][0], SPLITS["train"][1]],
               "is_synthetic": False, "computed_at": time.time(), "half_spreads": hs, "configs": res,
               "passing_configs": passing, "chosen_config": chosen, "stress_2x_spread": stress,
               "validation_examined": False}
        p1 = run_config("P1", 0.05, 900, "train", hs)[0]
        out["daily_P1_b5_15m"] = [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in d.items()} for d in p1[0]["days"]]
        EVID.mkdir(parents=True, exist_ok=True)
        (EVID / "evidence_lphedge_train.json").write_text(json.dumps(out, indent=1))
        print("passing", passing, "chosen", chosen)
    else:
        tr = json.loads((EVID / "evidence_lphedge_train.json").read_text())
        chosen = tr["chosen_config"]
        if not chosen:
            sys.exit("no config passed train: validation must not be examined")
        c = next(c for c in GRID if cfg_name(c) == chosen)
        runs, s = run_config(*c, "validation", hs)
        out = {"hypothesis": "H-LPHEDGE", "split": "validation", "config": chosen, "is_synthetic": False,
               "computed_at": time.time(), "result": s,
               "daily": [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in d.items()} for r in runs for d in r["days"]]}
        (EVID / "evidence_lphedge_validation.json").write_text(json.dumps(out, indent=1))
        print(chosen, s)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "train")
