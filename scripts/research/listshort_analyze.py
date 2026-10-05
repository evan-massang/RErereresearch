"""H-LISTSHORT step 4: build listing events, simulate the pre-declared short grid, score train.

    python scripts/research/listshort_analyze.py train        # train only (selection)
    python scripts/research/listshort_analyze.py validation   # once, only configs passing train
Holdout (listings >= 2026-04-01) is never loaded.

Pre-declared design (fixed before running on train):
  Event unit: one per base coin = its EARLIEST perp listing across Hyperliquid (HL) and Binance
    USDT-M (BN), executed on that venue. Coins whose earliest listing is before 2023-01-01 are dropped.
    Coins named in the round-3 OWN-PRECHECK (Solana meme perps listed on HL 2025+) are CONTAMINATED:
    excluded from all selection statistics, reported separately.
  Listing time: BN = first 1h kline; HL = earliest of first funding record / first 4h / first 1d bar.
  Entry: short at the close of the first available bar whose close >= listing + N.
  Exit: close of the first bar whose close >= entry + H (or last available bar if the market stops).
  Stop: optional, fills at max(stop price, bar open) * (1 + slip) when bar high >= stop price.
  Liquidation: at leverage L, if high >= entry*(1 + 1/L - 0.10) the trade loses 100% of margin.
  Costs: taker HL 0.045% (Hyperliquid docs, tier 0) / BN 0.05% (Binance USDT-M regular VIP0),
    + 0.10% slippage per side on the meme leg; hedge leg taker + 0.02% slippage per side.
  Funding: short receives rate * notional * price_t/entry for every funding stamp in (entry, exit].
  Hedge: long beta * notional of BTCUSDT perp (Binance 1h) over the same window; beta estimated on
    TRAIN events only (pooled OLS of daily coin log-returns on BTC daily log-returns, days after
    entry within the hold window). Also a 50/50 SOL+ETH hedge.
  Returns are per unit of equity at leverage L (default 1x); equal equity per trade.
  Bar (on BTC-hedged, 1x): n >= 50, net > 0, PF > 1.2, net > 0 after removing best 3 trades.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from listshort_classify import candidates  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
HL = ROOT / "data/raw/web/hyperliquid"
BN = ROOT / "data/raw/web/binance_fut"
OBS = ROOT / "research/observations"
H = 3600_000
DAY = 24 * H
ERA_MS = 1672531200000      # 2023-01-01
TRAIN_END = 1751328000000   # 2025-07-01 (exclusive)
VAL_END = 1775001600000     # 2026-04-01 (exclusive) == holdout start
CONTAMINATED = {"AI16Z", "ZEREBRO", "GRIFFAIN", "TRUMP", "MELANIA", "VINE", "JELLY", "JELLYJELLY",
                "LAUNCHCOIN", "PUMP", "USELESS", "YZY"}  # filled from the round-3 set, see report
FEE = {"HL": 0.00045, "BN": 0.0005}
SLIP = 0.0010
HEDGE_COST = 0.0005 + 0.0002
GRID = [(n, h, s) for n in (4, 24, 72) for h in (7, 14, 30) for s in (None, 0.40)]


def load(p):
    return json.loads(Path(p).read_text())


# ---------------------------------------------------------------- data
def bars_hl(d):
    for key, w in (("c1h", H), ("c4h", 4 * H), ("c1d", DAY)):
        rows = d.get(key) or []
        if rows and rows[0]["t"] <= d["first_1d_t"] + DAY:  # this resolution reaches the listing
            return [(r["t"], r["t"] + w, float(r["o"]), float(r["h"]), float(r["l"]), float(r["c"]))
                    for r in rows], key
    return None, None


def event_hl(sym):
    p = HL / f"listshort_{sym}.json"
    if not p.exists():
        return None
    d = load(p)
    if d.get("status") != "ok":
        return {"status": d.get("status")}
    bars, res = bars_hl(d)
    fund = [(int(x["time"]), float(x["fundingRate"])) for x in d["funding"]]
    cands = [d["first_1d_t"] + DAY - 1]  # listing no later than end of first daily bar
    if fund:
        cands.append(fund[0][0] - H)
    if d.get("c4h"):
        cands.append(d["c4h"][0]["t"])
    if d.get("c1h"):
        cands.append(d["c1h"][0]["t"])
    t0 = max(d["first_1d_t"], min(cands))
    return {"status": "ok", "t0": t0, "bars": bars, "res": res, "funding": fund}


def event_bn(sym):
    p = BN / f"listshort_{sym}.json"
    if not p.exists():
        return None
    d = load(p)
    if d.get("status") != "ok":
        return {"status": d.get("status")}
    bars = [(r[0], r[0] + H, r[1], r[2], r[3], r[4]) for r in d["klines_1h"]]
    return {"status": "ok", "t0": bars[0][0], "bars": bars, "res": "1h",
            "funding": [(int(a), float(b)) for a, b in d["funding"]]}


def hedge_series(sym):
    d = load(BN / f"listshort_{sym}.json")
    return np.array([r[0] for r in d["klines_1h"]]), np.array([r[4] for r in d["klines_1h"]])


HEDGE = {s: hedge_series(s) for s in ("BTCUSDT", "ETHUSDT", "SOLUSDT")}


def px_at(sym, t):
    ts, cl = HEDGE[sym]
    i = np.searchsorted(ts + H, t, side="right") - 1  # last bar closed at or before t
    return float(cl[max(i, 0)])


def build_events():
    rows = [r for r in candidates() if r["meme"]]
    by_base = {}
    status = []
    for r in rows:
        ev = event_hl(r["symbol"]) if r["venue"] == "HL" else event_bn(r["symbol"])
        if ev is None:
            status.append((r["venue"], r["symbol"], "not_fetched"))
            continue
        if ev["status"] != "ok":
            status.append((r["venue"], r["symbol"], ev["status"]))
            continue
        ev.update(venue=r["venue"], symbol=r["symbol"], base=r["base"].upper())
        by_base.setdefault(ev["base"], []).append(ev)
    events = []
    for base, evs in by_base.items():
        evs.sort(key=lambda e: e["t0"])
        first = evs[0]
        first["other_listings"] = [(e["venue"], e["symbol"], e["t0"]) for e in evs[1:]]
        if first["t0"] < ERA_MS:
            first["split"] = "pre2023"
        elif first["t0"] < TRAIN_END:
            first["split"] = "train"
        elif first["t0"] < VAL_END:
            first["split"] = "validation"
        else:
            first["split"] = "holdout"  # never simulated
        first["contaminated"] = base in CONTAMINATED
        events.append(first)
    return events, status


# ---------------------------------------------------------------- simulation
def simulate(ev, n_h, hold_d, stop, lev=1.0):
    bars = ev["bars"]
    t_entry_min = ev["t0"] + n_h * H
    ie = next((i for i, b in enumerate(bars) if b[1] >= t_entry_min), None)
    if ie is None:
        return None
    te, pe = bars[ie][1], bars[ie][5]
    t_exit_min = te + hold_d * DAY
    liq_px = pe * (1 + 1 / lev - 0.10)
    stop_px = pe * (1 + stop) if stop else None
    max_high, exit_reason, px, tx = pe, "time", None, None
    for b in bars[ie + 1:]:
        max_high = max(max_high, b[3])
        hit_stop = stop_px is not None and b[3] >= stop_px
        hit_liq = b[3] >= liq_px
        if hit_stop and (not hit_liq or stop_px <= liq_px):
            px, tx, exit_reason = max(stop_px, b[2]) * (1 + SLIP), b[1], "stop"
            if px >= liq_px:
                exit_reason = "liquidated"
            break
        if hit_liq:
            exit_reason, tx, px = "liquidated", b[1], liq_px
            break
        if b[1] >= t_exit_min:
            px, tx = b[5], b[1]
            break
    if px is None:  # data ended (delisted or end of fetched window)
        last = bars[-1]
        if last[1] <= te:
            return None
        px, tx, exit_reason = last[5], last[1], "data_end" if last[1] < t_exit_min - DAY else "time"
    fee = FEE[ev["venue"]] + SLIP
    if exit_reason != "stop":
        px_fill = px * (1 + SLIP) if exit_reason != "liquidated" else px
    else:
        px_fill = px
    price_ret = -(px_fill / (pe * (1 - SLIP)) - 1)
    # funding: short receives rate * notional * (price at stamp / entry)
    fund = 0.0
    j = 0
    for t, rate in ev["funding"]:
        if te < t <= tx:
            while j + 1 < len(bars) and bars[j][1] < t:
                j += 1
            fund += rate * bars[j][5] / pe
    mae = max_high / pe - 1
    short_ret = price_ret + fund - 2 * FEE[ev["venue"]]
    if exit_reason == "liquidated":
        eq_ret = -1.0
    else:
        eq_ret = max(lev * short_ret, -1.0)
    b0, b1 = px_at("BTCUSDT", te), px_at("BTCUSDT", tx)
    e0, e1 = px_at("ETHUSDT", te), px_at("ETHUSDT", tx)
    s0, s1 = px_at("SOLUSDT", te), px_at("SOLUSDT", tx)
    return {"base": ev["base"], "venue": ev["venue"], "symbol": ev["symbol"], "split": ev["split"],
            "contaminated": ev["contaminated"], "res": ev["res"], "t_list": ev["t0"], "t_entry": te,
            "t_exit": tx, "entry": pe, "exit": px, "exit_reason": exit_reason,
            "price_ret": price_ret, "funding": fund, "fees": 2 * FEE[ev["venue"]] + 2 * SLIP,
            "short_ret": short_ret, "eq_ret": eq_ret, "mae": mae, "lev": lev,
            "btc_ret": b1 / b0 - 1, "solEth_ret": 0.5 * (e1 / e0 - 1) + 0.5 * (s1 / s0 - 1)}


def hedged(tr, beta, key="btc_ret"):
    if tr["exit_reason"] == "liquidated":
        return -1.0 + tr["lev"] * beta * tr[key]  # hedge leg still held in cross margin
    return tr["eq_ret"] + tr["lev"] * (beta * tr[key] - (2 * HEDGE_COST * beta))


def estimate_beta(events, hold_d=30, sym="BTCUSDT", n_h=24):
    """Pooled OLS of daily coin log returns on hedge daily log returns, train events only."""
    xs, ys = [], []
    for ev in events:
        if ev["split"] != "train" or ev["contaminated"]:
            continue
        bars = ev["bars"]
        t = ev["t0"] + n_h * H
        end = t + hold_d * DAY
        closes = {}
        for b in bars:
            if t <= b[1] <= end:
                closes[(b[1] - t) // DAY] = b[5]  # last close in each day bucket
        ks = sorted(closes)
        for a, b2 in zip(ks, ks[1:]):
            if b2 != a + 1:
                continue
            ta, tb = t + (a + 1) * DAY, t + (b2 + 1) * DAY
            if sym == "MIX":
                hx = 0.5 * math.log(px_at("ETHUSDT", tb) / px_at("ETHUSDT", ta)) + \
                     0.5 * math.log(px_at("SOLUSDT", tb) / px_at("SOLUSDT", ta))
            else:
                hx = math.log(px_at(sym, tb) / px_at(sym, ta))
            ys.append(math.log(closes[b2] / closes[a]))
            xs.append(hx)
    x, y = np.array(xs), np.array(ys)
    beta = float(np.cov(x, y)[0, 1] / np.var(x, ddof=1))
    return beta, len(x)


def stats(rets):
    r = np.array(sorted(rets))
    if len(r) == 0:
        return {"n": 0}
    gains, losses = r[r > 0].sum(), -r[r < 0].sum()
    top3 = r[:-3].sum() if len(r) > 3 else float("nan")
    return {"n": int(len(r)), "net": float(r.sum()), "mean": float(r.mean()), "median": float(np.median(r)),
            "pf": float(gains / losses) if losses > 0 else float("inf"), "net_ex_top3": float(top3),
            "win": float((r > 0).mean())}


def passes(s):
    return s["n"] >= 50 and s["net"] > 0 and s["pf"] > 1.2 and s["net_ex_top3"] > 0


def run(split):
    events, status = build_events()
    beta_btc, nb = estimate_beta(events)
    beta_mix, nm = estimate_beta(events, sym="MIX")
    counts = {}
    for e in events:
        k = e["split"] + ("_contaminated" if e["contaminated"] else "")
        counts[k] = counts.get(k, 0) + 1
    out = {"split": split, "beta_btc": beta_btc, "beta_btc_nobs": nb, "beta_solEth": beta_mix,
           "beta_solEth_nobs": nm, "event_counts": counts, "fetch_status": status, "configs": []}
    for (n_h, hold_d, stop) in GRID:
        trs = [simulate(e, n_h, hold_d, stop) for e in events if e["split"] == split]
        trs = [t for t in trs if t]
        clean = [t for t in trs if not t["contaminated"]]
        cont = [t for t in trs if t["contaminated"]]
        raw = stats([t["eq_ret"] for t in clean])
        hb = stats([hedged(t, beta_btc) for t in clean])
        hm = stats([hedged(t, beta_mix, "solEth_ret") for t in clean])
        out["configs"].append({
            "N_h": n_h, "hold_d": hold_d, "stop": stop, "raw": raw, "hedged_btc": hb, "hedged_solEth": hm,
            "passes_bar_hedged_btc": passes(hb), "passes_bar_raw": passes(raw),
            "contaminated_raw": stats([t["eq_ret"] for t in cont]),
            "contaminated_hedged_btc": stats([hedged(t, beta_btc) for t in cont]),
            "mae_median": float(np.median([t["mae"] for t in clean])) if clean else None,
            "mae_p90": float(np.percentile([t["mae"] for t in clean], 90)) if clean else None,
            "mae_max": float(max(t["mae"] for t in clean)) if clean else None,
            "n_liquidated_1x": sum(t["exit_reason"] == "liquidated" for t in clean),
            "n_mae_ge_40pct": sum(t["mae"] >= 0.40 for t in clean),
            "n_stopped": sum(t["exit_reason"] == "stop" for t in clean),
            "funding_mean": float(np.mean([t["funding"] for t in clean])) if clean else None,
            "trades": trs,
        })
    return out


if __name__ == "__main__":
    split = sys.argv[1]
    assert split in ("train", "validation"), "holdout is not examined"
    res = run(split)
    OBS.mkdir(parents=True, exist_ok=True)
    (OBS / f"evidence_listshort_{split}.json").write_text(json.dumps(res, indent=1, default=str))
    print("beta_btc", round(res["beta_btc"], 3), res["beta_btc_nobs"], "beta_solEth", round(res["beta_solEth"], 3))
    print("events", res["event_counts"])
    for c in res["configs"]:
        r, h = c["raw"], c["hedged_btc"]
        if not r.get("n"):
            continue
        print(f"N={c['N_h']:>2}h H={c['hold_d']:>2}d stop={c['stop']}: n={r['n']} raw net={r['net']:+.2f} "
              f"PF={r['pf']:.2f} ex3={r['net_ex_top3']:+.2f} med={r['median']:+.3f} | hedgedBTC net={h['net']:+.2f} "
              f"PF={h['pf']:.2f} ex3={h['net_ex_top3']:+.2f} | mix net={c['hedged_solEth']['net']:+.2f} "
              f"| MAE med={c['mae_median']:.2f} p90={c['mae_p90']:.2f} max={c['mae_max']:.2f} "
              f"liq={c['n_liquidated_1x']} stop={c['n_stopped']} fund={c['funding_mean']:+.3f} "
              f"PASS={c['passes_bar_hedged_btc']}")
