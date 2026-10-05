"""H-LPHEDGE-2: single pre-registered config (PUMP/USDC, band 5%, 1 h check) on the never-examined validation split.

Pre-registration: reports/hypotheses/lphedge2_preregistration.json. Reuses lphedge_sim.py (iteration 1) for data,
liquidity history, fees, funding and costs; adds (a) the corrected coverage rule and (b) a margin model for the 1x
Lighter short:
  * collateral C reset at 00:00 UTC each day to 1x the short notional (h x Lighter close);
  * at every 15m point the short's equity is checked against the Lighter candle HIGH of the coming bar:
    equity = C + hedge P&L since 00:00 (closes) - h x (high - previous close). If equity < maintenance margin
    (6% of h x high, Lighter orderBookDetails maintenance_margin_fraction 600) the short is liquidated:
    the whole remaining collateral is lost (conservative: equity -> 0, which also covers Lighter's 1% liquidation
    fee), h -> 0 until the next check re-opens it (paying half spread).

    python scripts/research/lphedge2_sim.py validation      # runs ONCE
"""
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/research"))
import lphedge_sim as s1  # noqa: E402

PREREG = json.loads((ROOT / "reports/hypotheses/lphedge2_preregistration.json").read_text())
B, IV = 0.05, 3600
MMF = 0.06


def candles_high():
    return {c["t"] // 1000: c["h"] for c in s1.load_json("lighter_candles_PUMP.json")["candles"]}


def run(t0, t1, hs):
    pool, p = "P1", s1.POOLS["P1"]
    grid, P, vol, have_pool, perp, have_perp, fund = s1.series(pool, t0, t1)
    hi = candles_high()
    Lfn, n_ev, _ = s1.liquidity_fn(pool)
    tok = "PUMP"
    pp = perp[tok]
    Lo = s1.SIZE / (2 * math.sqrt(P[0]))
    x = lambda k: Lo / math.sqrt(P[k])
    h = x(0)
    c = hs[tok]["half_bp"] / 1e4
    Lp0 = Lfn(grid[0])
    impact = (s1.SIZE / 2) / (Lp0 * math.sqrt(P[0]))
    setup = 2 * (s1.SIZE / 2) * (s1.POOL_FEE_TOTAL_BPS / 1e4 + impact) + 2 * h * pp[0] * c
    step = IV // s1.BAR
    days = {}
    liquidations = []
    for k in range(len(grid) - 1):
        t = grid[k]
        day = (t - t0) // 86400
        d = days.get(day)
        if d is None:
            d = days[day] = {"day": datetime.fromtimestamp(t0 + day * 86400, timezone.utc).strftime("%Y-%m-%d"),
                             "lp": 0.0, "fee": 0.0, "hedge": 0.0, "funding": 0.0, "hcost": 0.0, "liq_loss": 0.0,
                             "gas": s1.TX_PER_DAY * s1.GAS_SOL_PER_TX * perp["SOL"][k], "n_trades": 0,
                             "bars_pool": 0, "bars_perp": 0, "v_start": 2 * Lo * math.sqrt(P[k]),
                             "tvl_start": 2 * Lfn(t) * math.sqrt(P[k]), "vol_usd": 0.0, "basis_bp": [],
                             "lp_ret_hedge_ideal": 0.0}
            d["_C"] = h * pp[k]               # collateral reset to 1x notional
            d["_hp"] = 0.0                     # hedge P&L since 00:00
        if k % step == 0:
            if h == 0.0 or abs(x(k) - h) > B * x(k):
                d["hcost"] += abs(x(k) - h) * pp[k] * c
                if h == 0.0:
                    d["_C"] = x(k) * pp[k]
                h = x(k)
                d["n_trades"] += 1
        # margin check against the coming bar's high
        bar_start = grid[k + 1] - s1.BAR
        if h > 0 and bar_start in hi:
            H = hi[bar_start]
            eq = d["_C"] + d["_hp"] - h * (H - pp[k])
            if eq < MMF * h * H:
                loss = d["_C"] + d["_hp"]              # all remaining equity lost (conservative)
                d["liq_loss"] += loss
                d["hedge"] += 0.0
                liquidations.append({"t": grid[k], "h": h, "price": H})
                d["_hp"] = -d["_C"]
                h = 0.0
        d["lp"] += 2 * Lo * (math.sqrt(P[k + 1]) - math.sqrt(P[k]))
        Lp = Lfn(grid[k + 1] - s1.BAR / 2)
        d["fee"] += vol[k + 1] * s1.LP_BPS / 1e4 * Lo / (Lp + Lo)
        d["vol_usd"] += vol[k + 1]
        hp = -h * (pp[k + 1] - pp[k])
        d["hedge"] += hp
        d["_hp"] += hp
        # decomposition: hedge P&L had the short been marked at POOL prices -> LVR part; remainder = basis
        d["lp_ret_hedge_ideal"] += -h * (P[k + 1] - P[k])
        tn = grid[k + 1]
        if tn % 3600 == 0 and h and tn in fund[tok]:
            d["funding"] += fund[tok][tn] * h * pp[k + 1]
        d["bars_pool"] += have_pool[k + 1]
        d["bars_perp"] += have_perp[tok][k + 1]
        if P[k + 1] and pp[k + 1]:
            d["basis_bp"].append((pp[k + 1] / P[k + 1] - 1) * 1e4)
    out = []
    for d in days.values():
        d.pop("_C"); d.pop("_hp")
        d["lvr"] = d["lp"] + d["lp_ret_hedge_ideal"]           # LP + ideal hedge at pool prices
        d["basis"] = d["hedge"] - d["lp_ret_hedge_ideal"]       # perp-vs-pool price differences
        d["pnl"] = d["lp"] + d["fee"] + d["hedge"] + d["funding"] - d["hcost"] - d["gas"] - d["liq_loss"]
        b = d.pop("basis_bp")
        d["basis_bp_mean"] = float(np.mean(b)) if b else None
        d["scored"] = (d["bars_perp"] >= PREREG["coverage_rule"]["min_perp_bars"] and
                       d["bars_pool"] >= PREREG["coverage_rule"]["min_pool_bars"])
        d["pnl_bp"] = d["pnl"] / d["v_start"] * 1e4
        out.append(d)
    return out, setup, liquidations, impact


def main():
    if sys.argv[1:] != ["validation"]:
        sys.exit("usage: lphedge2_sim.py validation")
    ev = ROOT / "research/observations/evidence_lphedge2_validation.json"
    if ev.exists():
        sys.exit("validation already run once; refusing to re-run")
    hs = s1.half_spreads()
    t0, t1 = s1.SPLITS["validation"]
    days, setup, liqs, impact = run(t0, t1, hs)
    sc = [d for d in days if d["scored"]]
    pn = [d["pnl"] for d in sc]
    gp, gl = sum(v for v in pn if v > 0), -sum(v for v in pn if v < 0)
    net = sum(pn) - setup
    top3 = sum(sorted(pn, reverse=True)[:3])
    comp = {k: round(sum(d[k] for d in sc), 2) for k in ("fee", "funding", "lp", "hedge", "lvr", "basis", "hcost", "gas",
                                                          "liq_loss", "vol_usd")}
    bp = lambda key: round(float(np.mean([d[key] / d["v_start"] * 1e4 for d in sc])), 3)
    res = {"n_pool_days": len(sc), "unscored_days": [d["day"] for d in days if not d["scored"]],
           "net_usd": round(net, 2), "sum_day_pnl_usd": round(sum(pn), 2), "setup_usd": round(setup, 2),
           "pf": round(gp / gl, 3) if gl else None, "net_ex_top3_usd": round(net - top3, 2),
           "mean_bp_per_day": round(float(np.mean([d["pnl_bp"] for d in sc])), 3), "win_days": sum(v > 0 for v in pn),
           "components_usd": comp,
           "components_bp_per_day": {k: bp(k) for k in ("fee", "funding", "lvr", "basis", "hcost", "gas", "liq_loss")},
           "n_hedge_trades": sum(d["n_trades"] for d in sc), "liquidations": liqs,
           "median_tvl_usd": round(float(np.median([d["tvl_start"] for d in sc]))),
           "mean_vol_over_tvl": round(float(np.mean([d["vol_usd"] / d["tvl_start"] for d in sc])), 4),
           "mean_basis_bp": round(float(np.mean([d["basis_bp_mean"] for d in sc if d["basis_bp_mean"] is not None])), 2),
           "setup_price_impact_frac": impact,
           "start_capital_usd": s1.SIZE * 1.5}
    res["passes_bar"] = bool(res["n_pool_days"] >= 50 and net > 0 and (res["pf"] or 0) > 1.2 and res["net_ex_top3_usd"] > 0)
    out = {"hypothesis": "H-LPHEDGE-2", "parent": "H-LPHEDGE (reports/failures/agent_lphedge.md)", "split": "validation",
           "window": [t0, t1], "config": "P1 PUMP/USDC, b=5%, check 1h", "is_synthetic": False,
           "computed_at_utc": time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime()), "half_spreads": hs, "result": res,
           "daily": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items()} for d in days]}
    ev.write_text(json.dumps(out, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
