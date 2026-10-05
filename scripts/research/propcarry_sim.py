"""H-PROPCARRY episode simulator. Rules frozen in reports/hypotheses/propcarry_preregistration.json.

Usage:
  python scripts/research/propcarry_sim.py train            # 12-config HL grid on train, x1/x2/x4 spot cost
  python scripts/research/propcarry_sim.py validation KEY   # ONE run of the selected config (HL + Binance replicate)
  python scripts/research/propcarry_sim.py binance_train KEY
  python scripts/research/propcarry_sim.py lighter          # descriptive funding comparison (no P&L)

All inputs are cut at 2026-04-01 00:00 UTC on load (holdout never read).
"""
import json, sys, datetime as dt, statistics as st
from collections import defaultdict

H = 3600_000
HOLD = int(dt.datetime(2026, 4, 1, tzinfo=dt.timezone.utc).timestamp() * 1000)
TRAIN_END = int(dt.datetime(2025, 7, 1, tzinfo=dt.timezone.utc).timestamp() * 1000) - H   # 2025-06-30 23:00
VAL_START = int(dt.datetime(2025, 7, 1, tzinfo=dt.timezone.utc).timestamp() * 1000)
VAL_END = HOLD - H                                                                          # 2026-03-31 23:00
COINS = ["PENGU", "PUMP", "TRUMP", "BONK", "FARTCOIN", "USELESS"]
HL_SYM = {"PENGU": "PENGU", "PUMP": "PUMP", "TRUMP": "TRUMP", "BONK": "kBONK", "FARTCOIN": "FARTCOIN"}
SPOT_FILE = {"PENGU": "data/raw/web/spot_ohlcv/PENGU_1h.json", "TRUMP": "data/raw/web/spot_ohlcv/TRUMP_1h.json",
             "BONK": "data/raw/web/spot_ohlcv/kBONK_1h.json", "FARTCOIN": "data/raw/web/spot_ohlcv/FARTCOIN_1h.json",
             "PUMP": "data/raw/web/spot_ohlcv/PUMP_1h.json", "USELESS": "data/raw/web/propcarry/USELESS_spot_1h.json"}
BIN_MULT = {"BONK": 1000}  # 1000BONKUSDT vs BONK spot
COLLAT_STOP, BASIS_STOP = 1.6, 0.03
TIPS_BP, HOP_BP = 1.0, 2.0
PERP_RT_BP = {"hl": 2 * (4.5 + 1.7), "binance": 2 * (5.0 + 1.0)}


def jup_cost():
    q = json.load(open("data/raw/web/propcarry/jupiter_quotes_20261005.json"))
    return {r["coin"]: r["rt_bp"] for r in q["rows"] if r["size_sol"] == 5 and r["coin"] in COINS}


def load_spot(c):
    d = json.load(open(SPOT_FILE[c]))
    # key = bar CLOSE hour (t_open + 1h); value (o, h, l, c)
    return {r[0] + H: (r[1], r[2], r[3], r[4]) for r in d["rows"] if r[0] + H < HOLD}


def load_hl(c):
    d = json.load(open(f"data/raw/web/hyperliquid/funding_{HL_SYM[c]}.json"))
    out = {}
    for r in d["rows"]:
        t = r["time"] // H * H
        if t < HOLD:
            out[t] = (float(r["fundingRate"]), float(r["premium"]))
    return out


def load_binance():
    f = json.load(open("data/raw/web/propcarry/binance_funding.json"))["data"]
    k = json.load(open("data/raw/web/propcarry/binance_perp_1h.json"))["data"]
    fund = {c: {(r[0] // H) * H: (r[2], r[1]) for r in f[c] if r[0] < HOLD} for c in f}
    perp = {c: {r[0] + H: (r[1], r[2], r[3], r[4]) for r in k[c] if r[0] + H < HOLD} for c in k}
    return fund, perp


class Venue:
    """Point-in-time accessors for one coin on one venue."""
    def __init__(self, kind, coin, spot, fund, perp=None):
        self.kind, self.coin, self.spot, self.fund, self.perp = kind, coin, spot, fund, perp
        self.first = min(fund) if fund else None
        self.mult = BIN_MULT.get(coin, 1) if kind == "binance" else 1

    def signal(self, T, L):
        """annualised mean hourly funding over (T-L h, T]; None if < 90% coverage."""
        if self.kind == "hl":
            xs = [self.fund[t][0] for t in range(T - (L - 1) * H, T + H, H) if t in self.fund]
            if len(xs) < 0.9 * L:
                return None
            return st.mean(xs) * 8760
        prints = [(t, v) for t, v in self.fund.items() if T - L * H < t <= T]
        cover = sum(v[1] for _, v in prints)
        if cover < 0.9 * L:
            return None
        return sum(v[0] for _, v in prints) / L * 8760

    def px(self, t):
        """(spot ohlc, perp ohlc) at bar closing t, or None."""
        s = self.spot.get(t)
        if s is None:
            return None
        if self.kind == "hl":
            f = self.fund.get(t)
            if f is None:
                return None
            k = 1 + f[1]
            return s, (s[0] * k, s[1] * k, s[2] * k, s[3] * k)
        p = self.perp.get(t)
        if p is None:
            return None
        m = self.mult
        return s, tuple(x / m for x in p)  # perp in spot units

    def rate_at(self, t):
        f = self.fund.get(t)
        return None if f is None else f[0]


def mondays(t0, t1):
    d = dt.datetime.fromtimestamp(t0 / 1000, dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    d += dt.timedelta(days=(7 - d.weekday()) % 7)
    while d.timestamp() * 1000 <= t1:
        yield int(d.timestamp() * 1000)
        d += dt.timedelta(days=7)


def run(v, L, F, Z, split, cost_bp):
    lo, hi, last = (0, TRAIN_END - 23 * H, TRAIN_END) if split == "train" else (VAL_START, VAL_END - 23 * H, VAL_END)
    eps, busy_until = [], -1
    if v.first is None:
        return eps
    for T in mondays(max(lo, v.first + 30 * 24 * H), hi):
        if T < busy_until:
            continue
        s = v.signal(T, L)
        if s is None or s < F:
            continue
        p0 = v.px(T)
        if p0 is None:
            continue
        S0, P0 = p0[0][3], p0[1][3]
        b0 = P0 / S0 - 1
        E = min(T + Z * 24 * H, last)
        fund, reason, last_ok, t = 0.0, "time", (T, S0, P0), T
        SE = PE = None
        while t < E:
            t += H
            px = v.px(t)
            r = v.rate_at(t)
            if px is None:
                if (t - last_ok[0]) > 6 * H:
                    reason = "gap"; t, SE, PE = last_ok; break
                if r is not None and v.kind == "binance":
                    fund += r * last_ok[2] / P0
                continue
            (so, sh, sl, sc), (po, ph, pl, pc) = px
            if r is not None:
                fund += r * pc / P0
            if ph >= COLLAT_STOP * P0:
                reason = "collat_stop"; PE = max(COLLAT_STOP * P0, po); SE = min(sc, COLLAT_STOP * S0); break
            if pc / sc - 1 >= b0 + BASIS_STOP:
                reason = "basis_stop"; SE, PE = sc, pc; break
            last_ok = (t, sc, pc)
        if SE is None:
            if t >= E and last_ok[0] == E:
                SE, PE = last_ok[1], last_ok[2]
            else:
                t, SE, PE = last_ok
                reason = reason if reason != "time" else "gap"
            if E == last and reason == "time" and E < T + Z * 24 * H:
                reason = "split_end"
        spot_r, perp_r = SE / S0 - 1, PE / P0 - 1
        cost = cost_bp / 1e4
        unit = spot_r - perp_r + fund - cost
        eps.append({"coin": v.coin, "venue": v.kind, "entry": iso(T), "exit": iso(t), "signal_ann": round(s, 4),
                    "reason": reason, "spot_ret": spot_r, "perp_ret": perp_r, "basis_pnl": spot_r - perp_r,
                    "funding": fund, "cost": cost, "pnl_unit": unit, "roc": unit / 2,
                    "entry_basis": b0})
        busy_until = t  # flat at exit time; may re-enter at a decision at or after exit
    return eps


def iso(ms):
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def stats(eps):
    r = sorted(e["roc"] for e in eps)
    gp, gl = sum(x for x in r if x > 0), -sum(x for x in r if x < 0)
    n = len(r)
    out = {"n": n, "net": sum(r), "pf": (gp / gl) if gl > 0 else (float("inf") if gp > 0 else 0.0),
           "net_ex_top3": sum(r[:-3]) if n > 3 else sum(r) - sum(r[-3:]),
           "mean_bp": (sum(r) / n * 1e4) if n else 0, "win": (sum(x > 0 for x in r) / n) if n else 0,
           "funding_unit": sum(e["funding"] for e in eps), "basis_unit": sum(e["basis_pnl"] for e in eps),
           "cost_unit": sum(e["cost"] for e in eps), "worst": min(r) if r else None,
           "mean_funding_bp_per_ep": (sum(e["funding"] for e in eps) / n * 1e4) if n else 0,
           "mean_cost_bp_per_ep": (sum(e["cost"] for e in eps) / n * 1e4) if n else 0}
    out["passes"] = bool(n >= 50 and out["net"] > 0 and out["pf"] > 1.2 and out["net_ex_top3"] > 0)
    for k in ("net", "pf", "net_ex_top3", "mean_bp", "win", "funding_unit", "basis_unit", "cost_unit", "worst",
              "mean_funding_bp_per_ep", "mean_cost_bp_per_ep"):
        if isinstance(out[k], float) and out[k] != float("inf"):
            out[k] = round(out[k], 5)
    return out


def breakdown(eps, key):
    g = defaultdict(list)
    for e in eps:
        g[key(e)].append(e)
    return {k: {"n": len(v), "net": round(sum(x["roc"] for x in v), 5),
                "funding_unit": round(sum(x["funding"] for x in v), 5),
                "basis_unit": round(sum(x["basis_pnl"] for x in v), 5)} for k, v in sorted(g.items())}


def venues(kind):
    out = {}
    if kind == "hl":
        for c in HL_SYM:
            out[c] = Venue("hl", c, load_spot(c), load_hl(c))
    else:
        fund, perp = load_binance()
        for c in COINS:
            if fund.get(c):
                out[c] = Venue("binance", c, load_spot(c), fund[c], perp[c])
    return out


def cfg_list():
    return [(L, F, Z) for L in (24, 168) for F in (0.12, 0.20, 0.35) for Z in (7, 14)]


def key(L, F, Z):
    return f"L{L}_F{int(F*100)}_Z{Z}"


def simulate(vs, L, F, Z, split, stress, kind):
    jc = jup_cost()
    eps = []
    for c, v in vs.items():
        cbp = jc[c] * stress + HOP_BP + TIPS_BP + PERP_RT_BP[kind]
        eps += run(v, L, F, Z, split, cbp)
    return eps


def full_report(eps):
    return {"stats": stats(eps),
            "by_year": breakdown(eps, lambda e: e["entry"][:4]),
            "by_quarter": breakdown(eps, lambda e: e["entry"][:4] + "Q" + str((int(e["entry"][5:7]) - 1) // 3 + 1)),
            "by_coin": breakdown(eps, lambda e: e["coin"]),
            "by_exit": breakdown(eps, lambda e: e["reason"]),
            "worst5": sorted(({k: (round(x, 5) if isinstance(x, float) else x) for k, x in e.items()} for e in eps),
                             key=lambda e: e["roc"])[:5],
            "best5": sorted(({k: (round(x, 5) if isinstance(x, float) else x) for k, x in e.items()} for e in eps),
                            key=lambda e: -e["roc"])[:5]}


def main():
    mode = sys.argv[1]
    meta = {"preregistration": "reports/hypotheses/propcarry_preregistration.json",
            "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "jupiter_5sol_rt_bp": jup_cost(),
            "perp_rt_bp": PERP_RT_BP, "hop_bp": HOP_BP, "tips_bp": TIPS_BP,
            "unit": "net/pf/net_ex_top3/worst are sums of per-episode return on capital (capital = 2 x notional); *_unit fields are per unit notional"}
    if mode == "train":
        vs = venues("hl")
        res = {"meta": meta, "venue": "hl", "split": "train", "configs": {}}
        for (L, F, Z) in cfg_list():
            k = key(L, F, Z)
            res["configs"][k] = {}
            for stress in (1, 2, 4):
                eps = simulate(vs, L, F, Z, "train", stress, "hl")
                res["configs"][k][f"x{stress}"] = full_report(eps) if stress == 2 else {"stats": stats(eps)}
        passing = {k: v["x2"]["stats"] for k, v in res["configs"].items() if v["x2"]["stats"]["passes"]}
        sel = max(passing, key=lambda k: (passing[k]["net_ex_top3"], passing[k]["n"])) if passing else None
        res["selected"] = sel
        if sel:
            s = res["configs"][sel]["x2"]["stats"]
            margin = s["mean_funding_bp_per_ep"] - s["mean_cost_bp_per_ep"]
            res["kill_test"] = {"mean_funding_bp_per_ep": s["mean_funding_bp_per_ep"],
                                "mean_cost_bp_per_ep": s["mean_cost_bp_per_ep"], "margin_bp": round(margin, 2),
                                "killed": margin <= 5}
        json.dump(res, open("research/observations/evidence_propcarry_train.json", "w"), indent=1, default=str)
        for k, v in res["configs"].items():
            a = v["x2"]["stats"]
            print(k, "x2:", {x: a[x] for x in ("n", "net", "pf", "net_ex_top3", "mean_bp", "mean_funding_bp_per_ep", "passes")},
                  "| x1 net", v["x1"]["stats"]["net"], "pf", v["x1"]["stats"]["pf"], "| x4 net", v["x4"]["stats"]["net"])
        print("selected", sel, res.get("kill_test"))
    elif mode in ("validation", "binance_train"):
        L, F, Z = parse(sys.argv[2])
        res = {"meta": meta, "config": sys.argv[2]}
        if mode == "validation":
            for kind in ("hl", "binance"):
                vs = venues(kind)
                res[kind] = {f"x{s}": (full_report if s == 2 else (lambda e: {"stats": stats(e)}))(
                    simulate(vs, L, F, Z, "validation", s, kind)) for s in (1, 2, 4)}
            out = "research/observations/evidence_propcarry_validation.json"
        else:
            vs = venues("binance")
            res["binance_train"] = {f"x{s}": (full_report if s == 2 else (lambda e: {"stats": stats(e)}))(
                simulate(vs, L, F, Z, "train", s, "binance")) for s in (1, 2, 4)}
            out = "research/observations/evidence_propcarry_binance_train.json"
        json.dump(res, open(out, "w"), indent=1, default=str)
        print(json.dumps({k: {s: v[s]["stats"] for s in v} for k, v in res.items() if k not in ("meta", "config")}, indent=1))
    elif mode == "lighter":
        lighter_desc()


def parse(k):
    a, b, c = k.split("_")
    return int(a[1:]), int(b[1:]) / 100, int(c[1:])


def lighter_desc():
    lt = json.load(open("data/raw/web/propcarry/lighter_funding.json"))["data"]
    hl = {c: load_hl(c) for c in HL_SYM}
    fb, _ = load_binance()
    res = {"units": "Lighter rate = percent per hour (docs.lighter.xyz/trading/funding: floor InterestRate 0.01%/8h); direction 'long' = longs pay (+), 'short' = shorts pay (-) [inferred from doc sign convention]",
           "window": "overlap of all three venues, < 2026-04-01", "coins": {}}
    for c in COINS:
        L = {(r[0] * 1000) // H * H: (float(r[1]) / 100) * (1 if r[2] == "long" else -1) for r in lt.get(c, [])}
        if not L:
            continue
        row = {"lighter_first": iso(min(L))}
        for split, a, b in (("train", 0, TRAIN_END), ("validation", VAL_START, VAL_END)):
            ls = [v for t, v in L.items() if a <= t <= b]
            d = {"lighter_n_h": len(ls), "lighter_mean_ann": round(st.mean(ls) * 8760, 4) if ls else None,
                 "lighter_share_at_floor": round(sum(abs(x - 0.0000125) < 6e-7 for x in ls) / len(ls), 3) if ls else None}
            if c in hl:
                hs = [v[0] for t, v in hl[c].items() if a <= t <= b and t in L]
                ls2 = [L[t] for t, v in hl[c].items() if a <= t <= b and t in L]
                if hs:
                    d.update({"overlap_h": len(hs), "hl_mean_ann_overlap": round(st.mean(hs) * 8760, 4),
                              "lighter_mean_ann_overlap": round(st.mean(ls2) * 8760, 4)})
            bs = [v for t, v in fb.get(c, {}).items() if a <= t <= b]
            if bs:
                d["binance_mean_ann"] = round(sum(x[0] for x in bs) / sum(x[1] for x in bs) * 8760, 4)
            row[split] = d
        res["coins"][c] = row
    json.dump(res, open("research/observations/evidence_propcarry_lighter_funding.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
