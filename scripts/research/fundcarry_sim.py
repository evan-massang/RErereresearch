"""H-FUNDCARRY episode simulator: short Hyperliquid perp + long equal units of spot, collect hourly funding.

Pre-registered (written before any train result was computed):
  grid (12 configs): L (trailing funding window, h) in {24, 72}
                     F (entry: trailing mean funding, annualised) in {0.30, 0.50, 1.00}
                     Z (max hold, days) in {7, 14}
  fixed: exit when trailing-L funding < 10%/yr; margin stop when perp unrealised loss >= 50% of initial
         margin (2x isolated -> spot close >= +25% vs entry); liquidation if the intrahour perp high reaches the
         isolated-2x liquidation price (maintenance = half the initial margin at max leverage, per HL docs);
         force close at the split end and at the coin's last funding print (delisting).
  costs (per side): HL perp taker 0.045% (base tier, hyperliquid.gitbook.io/.../trading/fees) + 0.05% perp
         impact; Solana DEX fee+slippage 0.5% (sensitivity 0.3% / 1.0%); $0.10 SOL priority/Jito tip per swap
         and $2 bridge/transfer per round trip on a $10,000 notional.
  splits: train = entries <= 2025-12-31; validation = 2026-01-01..2026-06-30 (looked at once, only configs
         that pass the bar on train); holdout >= 2026-07-01 is not on disk.
  bar: n >= 50, net > 0, PF > 1.2, net > 0 with the 3 best episodes removed.

Timing (no lookahead): funding print at hour t (rate for (t-1h, t]) -> signal at t -> trade at the spot close of
the bar ending at t. An open position earns the prints at t+1h..exit hour. The perp price is approximated as
spot * (1 + premium_t), premium_t from fundingHistory (HL hourly perp-vs-oracle premium); 1h perp candles are
not served for the train period (candleSnapshot keeps 5000 candles). Spot = CEX hourly close (Binance/OKX/MEXC)
as the price proxy for the Solana DEX leg.

    python scripts/research/fundcarry_sim.py train|validation|diag
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
HL = ROOT / "data/raw/web/hyperliquid"
SPOT = ROOT / "data/raw/web/spot_ohlcv"
H = 3600_000
SPLITS = {"train": (0, 1767225600000), "validation": (1767225600000, 1782864000000)}  # [start, end)
LEV = 2.0
PERP_FEE, PERP_IMPACT = 0.00045, 0.0005
NOTIONAL = 10_000.0
TIP, BRIDGE = 0.10, 2.0
EXIT_Y = 0.10
STOP = 0.25
GRID = [(L, F, Z) for L in (24, 72) for F in (0.30, 0.50, 1.00) for Z in (7, 14)]


def load():
    umap = json.loads((HL / "universe_map.json").read_text())
    coins = {}
    for coin, v in umap.items():
        ff, sf = HL / f"funding_{coin}.json", SPOT / f"{coin}_1h.json"
        if not v["verified"] or not ff.exists() or not sf.exists():
            continue
        fr = json.loads(ff.read_text())["rows"]
        sp = json.loads(sf.read_text())
        if not fr or not sp["rows"]:
            continue
        mult = v["mult"]
        t = np.array([x["time"] // H * H for x in fr], dtype=np.int64)
        t, idx = np.unique(t, return_index=True)
        rate = np.array([float(fr[i]["fundingRate"]) for i in idx])
        prem = np.array([float(fr[i]["premium"]) for i in idx])
        s = {r[0] + H: r for r in sp["rows"]}  # key = close time
        close = np.array([s[x][4] * mult if x in s else np.nan for x in t])
        high = np.array([s[x][2] * mult if x in s else np.nan for x in t])
        coins[coin] = dict(t=t, rate=rate, prem=prem, close=close, high=high,
                           maxlev=v["hl_max_leverage_now"] or 3, venue=sp["venue"])
    return coins


def trailing_mean(t, rate, L):
    """Mean of the last L hourly prints ending at index i, NaN if the window has gaps (needs L prints in L hours)."""
    out = np.full(len(t), np.nan)
    cs = np.concatenate([[0], np.cumsum(rate)])
    for i in range(L - 1, len(t)):
        if t[i] - t[i - L + 1] == (L - 1) * H:
            out[i] = (cs[i + 1] - cs[i - L + 1]) / L
    return out * 24 * 365


def episodes(c, L, F, Z, split, dex):
    lo, hi = SPLITS[split]
    t, rate, prem, close, high = c["t"], c["rate"], c["prem"], c["close"], c["high"]
    sig = trailing_mean(t, rate, L)
    mm = 1.0 / (2 * c["maxlev"])
    out, i, n = [], 0, len(t)
    last_in_split = np.where(t < hi)[0]
    if not len(last_in_split):
        return out
    end_i = last_in_split[-1]
    while i <= end_i:
        if not (t[i] >= lo and sig[i] >= F and np.isfinite(close[i])):
            i += 1
            continue
        e = i
        s0, b0 = close[e], prem[e]
        p0 = s0 * (1 + b0)
        pliq = p0 * (1 + 1 / LEV) / (1 + mm)
        fund, reason, j, liq = 0.0, None, e, False
        last_close = s0
        miss = 0
        while True:
            j += 1
            if j > end_i or t[j] - t[j - 1] > 6 * H:   # split end or data gap/delisting: close at last good hour
                j -= 1
                reason = "split_end" if j == end_i else "data_gap"
                break
            sj = close[j] if np.isfinite(close[j]) else last_close
            miss += not np.isfinite(close[j])
            fund += rate[j] * sj / s0
            hj = high[j] if np.isfinite(high[j]) else sj
            if hj * (1 + max(prem[j], 0)) >= pliq:
                liq, reason = True, "liquidated"
                break
            last_close = sj
            if sj >= s0 * (1 + STOP):
                reason = "margin_stop"
                break
            if sig[j] < EXIT_Y:
                reason = "funding_exit"
                break
            if t[j] - t[e] >= Z * 24 * H:
                reason = "max_hold"
                break
        s1 = close[j] if np.isfinite(close[j]) else last_close
        r1 = s1 / s0
        fixed = (2 * TIP + BRIDGE) / NOTIONAL
        if liq:
            # perp margin (N/LEV) lost; spot sold at that hour's close; perp exit fee not paid
            basis = 0.0
            hedge = (r1 - 1) - (1 + b0) / LEV
            cost = (PERP_FEE + PERP_IMPACT) + dex * (1 + r1) + fixed
        else:
            b1 = prem[j]
            basis = b0 - b1 * r1
            hedge = basis
            cost = (PERP_FEE + PERP_IMPACT) * (1 + r1 * (1 + b1)) + dex * (1 + r1) + fixed
        out.append(dict(coin=c.get("name"), entry_ms=int(t[e]), exit_ms=int(t[j]), hours=int((t[j] - t[e]) // H),
                        entry_sig=float(sig[e]), funding=float(fund), basis=float(basis), hedge=float(hedge),
                        spot_move=float(r1 - 1), cost=float(cost), net=float(fund + hedge - cost), reason=reason,
                        spot_missing_h=int(miss)))
        i = j + 1
    return out


def stats(eps):
    if not eps:
        return dict(n=0)
    eps = sorted(eps, key=lambda e: e["exit_ms"])
    r = np.array([e["net"] for e in eps])
    pos, neg = r[r > 0].sum(), -r[r < 0].sum()
    cum = np.cumsum(r)
    dd = float((np.maximum.accumulate(np.concatenate([[0], cum]))[1:] - cum).max())
    top3 = np.sort(r)[::-1][:3].sum()
    w = min(eps, key=lambda e: e["net"])
    return dict(n=len(r), net=float(r.sum()), mean=float(r.mean()), median=float(np.median(r)),
                pf=float(pos / neg) if neg > 0 else float("inf"), win=float((r > 0).mean()),
                net_ex_top3=float(r.sum() - top3), funding_only=float(sum(e["funding"] for e in eps)),
                basis_total=float(sum(e["basis"] for e in eps)), cost_total=float(sum(e["cost"] for e in eps)),
                max_dd=dd, worst=dict(coin=w["coin"], net=w["net"], reason=w["reason"], entry_ms=w["entry_ms"]),
                coins=len({e["coin"] for e in eps}),
                reasons={k: sum(e["reason"] == k for e in eps) for k in {e["reason"] for e in eps}},
                liquidations=sum(e["reason"] == "liquidated" for e in eps),
                spot_missing_h=int(sum(e["spot_missing_h"] for e in eps)),
                held_h=int(sum(e["hours"] for e in eps)))


def passes(s):
    return s.get("n", 0) >= 50 and s["net"] > 0 and s["pf"] > 1.2 and s["net_ex_top3"] > 0


def run(split, configs, dexes=(0.005,)):
    coins = load()
    for k, c in coins.items():
        c["name"] = k
    res = []
    for (L, F, Z) in configs:
        for dex in dexes:
            eps = [e for c in coins.values() for e in episodes(c, L, F, Z, split, dex)]
            s = stats(eps)
            res.append(dict(L=L, F=F, Z=Z, dex=dex, split=split, passes=passes(s), stats=s, episodes=eps))
    return coins, res


if __name__ == "__main__":
    # usage: fundcarry_sim.py <split> <lev> [L,F,Z ...]
    # Iteration 2 (rationale: at 2x, 22 of 141 train episodes of the best grid cell were liquidated and
    # liquidations alone lost more than the whole config) reruns the same 12-cell grid at 1x isolated.
    split, LEV = sys.argv[1], float(sys.argv[2])
    STOP = 0.5 / LEV  # margin use >= 50% of initial margin
    cfg = [tuple(float(v) if k == 1 else int(v) for k, v in enumerate(a.split(","))) for a in sys.argv[3:]] or GRID
    coins, res = run(split, cfg, (0.005, 0.003, 0.01))
    for r in res:
        s = r["stats"]
        if s["n"]:
            print(f"L={r['L']:>2} F={r['F']:.2f} Z={r['Z']:>2} dex={r['dex']:.3f} n={s['n']:>3} net={s['net']:+.3f} "
                  f"PF={s['pf']:.2f} exTop3={s['net_ex_top3']:+.3f} fund={s['funding_only']:+.3f} "
                  f"basis={s['basis_total']:+.3f} cost={s['cost_total']:.3f} win={s['win']:.2f} dd={s['max_dd']:.3f} "
                  f"worst={s['worst']['coin']}:{s['worst']['net']:+.3f}({s['worst']['reason']}) liq={s['liquidations']} "
                  f"pass={r['passes']}")
    out = ROOT / f"research/observations/evidence_fundcarry_{split}_lev{LEV:g}.json"
    out.write_text(json.dumps(dict(split=split, grid=cfg, exit_y=EXIT_Y, stop=STOP, lev=LEV,
                                   perp_fee=PERP_FEE, perp_impact=PERP_IMPACT,
                                   coins={k: dict(venue=c["venue"], maxlev=c["maxlev"], hours=len(c["t"]),
                                                  first_ms=int(c["t"][0]), last_ms=int(c["t"][-1]),
                                                  spot_cov=float(np.isfinite(c["close"]).mean()))
                                          for k, c in coins.items()},
                                   results=res), indent=1))
