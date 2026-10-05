"""H-FFDIFF simulator: HL vs Binance USDS-M funding-differential carry on memecoin perps (perp vs perp).

PRE-REGISTERED RULES (written before any P&L was computed; only funding-feature counts had been looked at)
---------------------------------------------------------------------------------------------------------
Universe: memecoin perps listed on both HL and Binance USDS-M (listshort_classify rule; ffdiff_fetch.universe()),
  36 pairs with data (USELESS has no HL data before the holdout). A pair is tradable on a 4h bar only when both
  venues have a 4h candle for it and both funding series are live (HL prints in the last 24h, a BN print in the
  last 12h). HL 4h candles exist only from ~2024-06-23 (candleSnapshot serves the latest 5000), so P&L starts there.

Clock: 4h bars (UTC 00/04/.../20). Decision at bar boundary T, fill at the 4h close at T on both venues
  (+ slippage). Signal uses only HL prints with floor-hour <= T-1h and BN prints with time < T (point in time).
Funding, annualised: f_HL(window) = sum(HL hourly rates in window)/hours*8760;
  f_BN(window) = sum(BN settlement rates in window)/hours*8760 (handles 1/4/8h intervals).
  D_W(T) = f_HL - f_BN over the trailing W hours.
Entry (one position per pair): s = sign(D_L). Open if s*D_L >= X and s*D_24 >= X ("persistent": both the L-hour
  and the last-24h differential). s=+1: short HL, long BN; s=-1: long HL, short BN. Equal notional N per leg.
Exit at the first 4h boundary where: s*D_24 < Y (Y = 10%/yr); or held >= Z days; or a leg is liquidated;
  or data gap / end of split (force-close at the split boundary; entries must lie inside the split).
Grid (16): L in {24, 72} h x X in {40, 80} %/yr x Z in {7, 14} d x leverage per leg in {1, 2}.
P&L per unit N (sum of the two legs):
  funding  = s * [ sum_HL r_h * P_HL(h)/P_HL0  -  sum_BN r_b * P_BN(b)/P_BN0 ]  over prints in (T0, T1];
             P(.) = close of the 4h bar containing the print.
  basis    = s * [ -(P_HL1/P_HL0 - 1) + (P_BN1/P_BN0 - 1) ]  (both perps' own closes).
  costs    = 2 x (HL taker 4.5 bp + Binance taker 5.0 bp) + 4 x slippage (5 bp base; 2 bp sensitivity).
             HL: https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees (tier 0 taker 0.045%).
             Binance USDS-M regular user taker 0.0500%: https://www.binance.com/en/fee/futureFee
Liquidation, each leg separately (legs are on different venues; no cross-venue margin transfer is modelled):
  isolated margin N/lev; short leg liquidated if a later 4h HIGH >= P0*(1 + 1/lev)/(1 + mm); long leg if a later
  4h LOW <= P0*(1 - 1/lev)/(1 - mm) (equity = maintenance margin on current notional; accrued funding ignored). mm_HL = 1/(2*maxLeverage) (HL docs: maintenance = half the initial margin at max
  leverage; maxLeverage = today's meta value); mm_BN = 5% (assumed, conservative; Binance brackets not reachable).
  On liquidation the leg loses its whole margin (N/lev), the other leg is closed at that bar's close with fee+slip.
Splits: train entries < 2025-07-01; validation 2025-07-01..2026-03-31 (looked at once, only for configs passing
  the bar on train); holdout >= 2026-04-01 never loaded (loaders drop rows >= CUTOFF).
Bar: n >= 50, net > 0, PF > 1.2, net > 0 without the 3 best episodes.

    python scripts/research/ffdiff_sim.py features              # train funding-feature counts only
    python scripts/research/ffdiff_sim.py train [slip_bp]       # full grid on train
    python scripts/research/ffdiff_sim.py validation L,X,Z,lev ...
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
HL = ROOT / "data/raw/web/hyperliquid"
BN = ROOT / "data/raw/web/binance_fut/ffdiff"
OBS = ROOT / "research/observations"
CUTOFF = pd.Timestamp("2026-04-01")
SPLITS = {"train": (pd.Timestamp("2023-11-01"), pd.Timestamp("2025-07-01")),
          "validation": (pd.Timestamp("2025-07-01"), CUTOFF)}
H = pd.Timedelta(hours=1)
FEE_HL, FEE_BN, MM_BN, Y = 4.5e-4, 5.0e-4, 0.05, 0.10
GRID = [(L, X, Z, lev) for L in (24, 72) for X in (0.40, 0.80) for Z in (7, 14) for lev in (1, 2)]
# ITERATION 2 (added after the train grid failed; rationale in reports/failures/agent_ffdiff.md): the D24<10% exit
# closed positions after a median ~2 days, so collected funding (24-50 bp/trade) stayed below the 39 bp round trip,
# and 1x legs were still liquidated in meme pumps (11 in L24_X40). Hold until the trailing-L differential flips
# sign (max 14 d) and close the pair when either leg's adverse close-to-entry move reaches 40% (pre-empts liquidation).
GRID2 = [(72, 0.40, 14, 1, "flip", 0.40), (72, 0.80, 14, 1, "flip", 0.40)]


def _hl(kind, coin):
    p = HL / f"{kind}_{coin}.json"
    if not p.exists():
        p = HL / "ffdiff" / f"{kind}_{coin}.json"
    return json.loads(p.read_text())["rows"]


def load_pair(p):
    f = pd.DataFrame(_hl("funding", p["hl"]))
    k = pd.DataFrame(_hl("candles_4h", p["hl"]))
    if f.empty or k.empty:
        return None
    f = pd.DataFrame({"t": pd.to_datetime(f.time, unit="ms").dt.floor("h"), "r": f.fundingRate.astype(float)})
    f = f[f.t < CUTOFF].drop_duplicates("t").set_index("t").r
    k = pd.DataFrame({"t": pd.to_datetime(k.t, unit="ms"), "h": k.h.astype(float), "l": k.l.astype(float),
                      "c": k.c.astype(float)})
    k = k[k.t + 4 * H <= CUTOFF].drop_duplicates("t").set_index("t")
    bf = pd.read_parquet(BN / f"{p['bn']}_funding.parquet")
    bf = pd.DataFrame({"t": pd.to_datetime(bf.t, unit="ms"), "r": bf.rate}).drop_duplicates("t")
    bf = bf[bf.t < CUTOFF].set_index("t").r
    bk = pd.read_parquet(BN / f"{p['bn']}_k4h.parquet")
    bk = pd.DataFrame({"t": pd.to_datetime(bk.t, unit="ms"), "h": bk.h, "l": bk.l, "c": bk.c, "qv": bk.qv})
    bk = bk[(bk.t + 4 * H <= CUTOFF) & (bk.qv > 0)].drop_duplicates("t").set_index("t")
    return {"hf": f, "hk": k, "bf": bf, "bk": bk}


def features(d, Ls=(24, 72)):
    """Per 4h boundary T (= bar open + 4h): D_W for W in Ls and 24, liveness flags. Point in time."""
    hf, bf = d["hf"], d["bf"]
    t0 = max(hf.index.min(), bf.index.min()).ceil("4h")
    t1 = min(hf.index.max(), bf.index.max()) + 4 * H
    T = pd.date_range(t0, t1, freq="4h")
    # cumulative sums on a fine grid for windowed sums
    hcs = hf.sort_index().cumsum()
    bcs = bf.sort_index().cumsum()

    def wsum(cs, ends, starts):  # sum of prints with starts < t <= ends
        a = cs.reindex(cs.index.union(ends)).ffill().fillna(0).reindex(ends).values
        b = cs.reindex(cs.index.union(starts)).ffill().fillna(0).reindex(starts).values
        return a - b

    def wcount(idx, ends, starts):
        s = pd.Series(1.0, index=idx).cumsum()
        a = s.reindex(s.index.union(ends)).ffill().fillna(0).reindex(ends).values
        b = s.reindex(s.index.union(starts)).ffill().fillna(0).reindex(starts).values
        return a - b

    out = pd.DataFrame(index=T)
    hend = T - H                       # HL prints with floor-hour <= T-1h
    bend = T - pd.Timedelta(seconds=1)  # BN prints strictly before T
    for W in sorted(set(Ls) | {24}):
        w = pd.Timedelta(hours=W)
        fh = wsum(hcs, hend, hend - w) / W * 8760
        fb = wsum(bcs, bend, bend - w) / W * 8760
        out[f"D{W}"] = fh - fb
        out[f"nh{W}"] = wcount(hf.index, hend, hend - w)
        out[f"fh{W}"], out[f"fb{W}"] = fh, fb
    out["live"] = (out["nh24"] >= 20) & (wcount(bf.index, bend, bend - pd.Timedelta(hours=12)) >= 1)
    return out


def simulate(p, d, F, cfg, split, slip):
    L, X, Z, lev = cfg[:4]
    exit_mode, stop = (cfg[4], cfg[5]) if len(cfg) > 4 else ("d24", None)
    s0, s1 = SPLITS[split]
    hk, bk, hf, bf = d["hk"], d["bk"], d["hf"], d["bf"]
    # boundary T -> close of bar ending at T
    hc = pd.Series(hk.c.values, index=hk.index + 4 * H)
    bc = pd.Series(bk.c.values, index=bk.index + 4 * H)
    common = hc.index.intersection(bc.index)
    mm_hl = 1 / (2 * p["hl_maxlev_now"])
    cost_side = FEE_HL + FEE_BN + 2 * slip
    eps, i, Ts = [], 0, F.index
    Fv = F.reindex(Ts)
    tradable = set(common)
    Tlist = [t for t in Ts if s0 <= t < s1]
    j = 0
    while j < len(Tlist):
        T0 = Tlist[j]
        r = Fv.loc[T0]
        j += 1
        if T0 not in tradable or not r["live"] or np.isnan(r[f"D{L}"]):
            continue
        s = 1 if r[f"D{L}"] > 0 else -1
        if not (s * r[f"D{L}"] >= X and s * r["D24"] >= X):
            continue
        ph0, pb0 = hc[T0], bc[T0]
        # walk forward
        T, reason, liq_leg = T0, None, None
        k = j - 1
        prev = T0
        while True:
            k += 1
            if k >= len(Ts):
                reason = "data_end"; T = prev; break
            T = Ts[k]
            if T > s1:
                reason = "split_end"; T = prev; break
            if T not in tradable or not Fv.loc[T, "live"]:
                reason = "gap"; T = prev; break
            bar = T - 4 * H
            hh, hl_, bh, bl = hk.h.get(bar), hk.l.get(bar), bk.h.get(bar), bk.l.get(bar)
            if s == 1:   # short HL, long BN
                if hh >= ph0 * (1 + 1 / lev) / (1 + mm_hl):
                    reason, liq_leg = "liq", "HL"; break
                if bl <= pb0 * (1 - 1 / lev) / (1 - MM_BN):
                    reason, liq_leg = "liq", "BN"; break
            else:        # long HL, short BN
                if bh >= pb0 * (1 + 1 / lev) / (1 + MM_BN):
                    reason, liq_leg = "liq", "BN"; break
                if hl_ <= ph0 * (1 - 1 / lev) / (1 - mm_hl):
                    reason, liq_leg = "liq", "HL"; break
            prev = T
            if stop is not None:
                adv_short = (hc[T] / ph0 - 1) if s == 1 else (bc[T] / pb0 - 1)
                adv_long = -((bc[T] / pb0 - 1) if s == 1 else (hc[T] / ph0 - 1))
                if max(adv_short, adv_long) >= stop:
                    reason = "stop"; break
            if exit_mode == "d24" and s * Fv.loc[T, "D24"] < Y:
                reason = "exit_signal"; break
            if exit_mode == "flip" and s * Fv.loc[T, f"D{L}"] < 0:
                reason = "exit_signal"; break
            if T - T0 >= pd.Timedelta(days=Z):
                reason = "time"; break
            if T == s1:
                reason = "split_end"; break
        T1 = T
        ph1, pb1 = hc[T1], bc[T1]
        # funding over (T0, T1], marked at the close of the bar containing each print
        hp = hf[(hf.index > T0) & (hf.index <= T1)]
        bp = bf[(bf.index > T0) & (bf.index <= T1)]
        mh = hc.reindex(hp.index.floor("4h") + 4 * H).values / ph0
        mb = bc.reindex(bp.index.floor("4h") + 4 * H).values / pb0
        fh = float(np.nansum(hp.values * mh))
        fb = float(np.nansum(bp.values * mb))
        funding = s * (fh - fb)
        hret, bret = ph1 / ph0 - 1, pb1 / pb0 - 1
        if reason == "liq":
            if liq_leg == "HL":
                leg_hl, leg_bn = -1 / lev, s * bret
            else:
                leg_bn, leg_hl = -1 / lev, -s * hret
            basis = leg_hl + leg_bn
            cost = cost_side + (FEE_BN if liq_leg == "HL" else FEE_HL) + slip
        else:
            basis = s * (-hret + bret)
            cost = 2 * cost_side
        net = funding + basis - cost
        eps.append({"coin": p["hl"], "dir": "shortHL" if s == 1 else "shortBN", "t0": str(T0), "t1": str(T1),
                    "days": (T1 - T0).total_seconds() / 86400, "D_entry": float(r[f"D{L}"]),
                    "funding": funding, "basis": basis, "cost": cost, "net": net, "exit": reason, "liq_leg": liq_leg})
        # resume scanning at the exit boundary (re-entry allowed from the next bar)
        while j < len(Tlist) and Tlist[j] <= T1:
            j += 1
    return eps


def stats(eps):
    if not eps:
        return {"n": 0}
    x = np.array([e["net"] for e in eps])
    g, l = x[x > 0].sum(), -x[x < 0].sum()
    srt = np.sort(x)
    df = pd.DataFrame(eps)
    df["q"] = pd.to_datetime(df.t0).dt.to_period("Q").astype(str)
    cum = np.cumsum(x[np.argsort(pd.to_datetime(df.t0).values)])
    return {"n": len(x), "net": float(x.sum()), "pf": float(g / l) if l > 0 else float("inf"),
            "net_ex_top3": float(srt[:-3].sum()) if len(x) > 3 else float("nan"),
            "mean_bp": float(x.mean() * 1e4), "win": float((x > 0).mean()),
            "funding": float(df.funding.sum()), "basis": float(df.basis.sum()), "cost": float(df.cost.sum()),
            "liq": int((df.exit == "liq").sum()), "worst": float(x.min()),
            "maxdd": float(np.max(np.maximum.accumulate(np.r_[0, cum]) - np.r_[0, cum])),
            "exits": df.exit.value_counts().to_dict(),
            "by_quarter": df.groupby("q").net.agg(["count", "sum"]).round(4).reset_index().values.tolist(),
            "by_coin": df.groupby("coin").net.agg(["count", "sum"]).round(4).sort_values("sum").reset_index().values.tolist(),
            "by_dir": df.groupby("dir").net.agg(["count", "sum"]).round(4).reset_index().values.tolist()}


def passes(st):
    return st.get("n", 0) >= 50 and st["net"] > 0 and st["pf"] > 1.2 and st["net_ex_top3"] > 0


def load_all():
    u = json.loads((HL / "ffdiff/universe.json").read_text())["pairs"]
    out = []
    for p in u:
        d = load_pair(p)
        if d is None:
            continue
        out.append((p, d, features(d)))
    return out


def main():
    mode = sys.argv[1]
    data = load_all()
    if mode == "features":
        s0, s1 = SPLITS["train"]
        rows = []
        for p, d, F in data:
            F = F[(F.index >= s0) & (F.index < s1) & F.live]
            hasp = F.index >= pd.Timestamp("2024-06-24")
            for W in (24, 72):
                for X in (0.2, 0.4, 0.8):
                    m = (np.sign(F[f"D{W}"]) * F[f"D{W}"] >= X) & (np.sign(F[f"D{W}"]) * F["D24"] >= X)
                    on = m & ~m.shift(1, fill_value=False)
                    rows.append({"coin": p["hl"], "W": W, "X": X, "bars": int(m.sum()), "onsets": int(on.sum()),
                                 "onsets_with_prices": int((on & hasp).sum())})
        df = pd.DataFrame(rows)
        print(df.groupby(["W", "X"])[["bars", "onsets", "onsets_with_prices"]].sum())
        print(df[(df.W == 24) & (df.X == 0.4)].sort_values("onsets").to_string())
        return
    slip = float(sys.argv[2]) * 1e-4 if mode in ("train", "train2") and len(sys.argv) > 2 else 5e-4
    if mode == "train2":
        mode, cfgs = "train", GRID2
        slip = float(sys.argv[2]) * 1e-4 if len(sys.argv) > 2 else 5e-4
        tagx = "_iter2"
    else:
        tagx = ""
    def parse(a):
        v = a.split(",")
        c = (int(v[0]), float(v[1]), int(v[2]), int(v[3]))
        return c + ((v[4], float(v[5])) if len(v) > 4 else ())
    cfgs = cfgs if tagx else GRID if mode == "train" else [parse(a) for a in sys.argv[2:]]
    res = {}
    for cfg in cfgs:
        eps = []
        for p, d, F in data:
            eps += simulate(p, d, F, cfg, mode, slip)
        st = stats(eps)
        key = f"L{cfg[0]}_X{int(round(cfg[1]*100))}_Z{cfg[2]}_lev{cfg[3]}" + (f"_{cfg[4]}_stop{int(cfg[5]*100)}" if len(cfg) > 4 else "")
        res[key] = {"stats": st, "pass": passes(st), "episodes": eps}
        print(f"{key:22s} n={st['n']:4d} net={st.get('net',0):+.3f} pf={st.get('pf',0):.2f} "
              f"ex3={st.get('net_ex_top3',0):+.3f} mean={st.get('mean_bp',0):+.1f}bp fund={st.get('funding',0):+.3f} "
              f"basis={st.get('basis',0):+.3f} cost={st.get('cost',0):.3f} liq={st.get('liq',0)} "
              f"worst={st.get('worst',0):+.3f} dd={st.get('maxdd',0):.3f} PASS={passes(st)}", flush=True)
    tag = f"{mode}" + (f"_slip{int(slip*1e4)}" if mode == "train" else "") + tagx
    out = OBS / f"evidence_ffdiff_{tag}.json"
    out.write_text(json.dumps({"family": "H-FFDIFF", "mode": mode, "slip_bp": slip * 1e4,
                               "is_synthetic": False, "configs": res}, indent=1, default=str))
    print("wrote", out)


if __name__ == "__main__":
    main()
