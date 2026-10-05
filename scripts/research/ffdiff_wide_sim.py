"""H-FFDIFF-WIDE simulator. Rules, configs and slippage model are frozen in
reports/hypotheses/ffdiff_wide_preregistration.json (written before any data/P&L of this family).

The signal (ffdiff_sim.features) and the walk-forward/exit/liquidation logic are ffdiff_sim.simulate's iteration-2
logic, copied with exactly two changes: (1) leverage is a float (0.5), (2) slippage is per leg and per venue
(slip_HL, slip_BN from the pre-registered liquidity tiers) instead of one scalar.

    python scripts/research/ffdiff_wide_sim.py universe     # identity check + liquidity tiers (no P&L)
    python scripts/research/ffdiff_wide_sim.py train        # configs A-D on train
    python scripts/research/ffdiff_wide_sim.py validation KEY [KEY..]   # once, only for train passers
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/research"))
import ffdiff_sim as fs  # noqa: E402  (features, H, CUTOFF, fees, MM_BN reused unchanged)

HL = ROOT / "data/raw/web/hyperliquid"
BNF = ROOT / "data/raw/web/binance_fut/ffdiff"
BNC = ROOT / "data/raw/web/binance_carry/funding"
W = ROOT / "data/raw/web/ffdiff_wide"
OBS = ROOT / "research/observations"
H, CUTOFF = fs.H, fs.CUTOFF
FEE_HL, FEE_BN, MM_BN = fs.FEE_HL, fs.FEE_BN, fs.MM_BN
TRAIN_END = pd.Timestamp("2025-07-01")
SPLITS = {"train": (pd.Timestamp("2024-06-01"), TRAIN_END), "validation": (TRAIN_END, CUTOFF)}
# Pre-registered configs (key, universe, L, X, Z, lev, exit, stop, slip_mult)
CONFIGS = {
    "A_all_L72_X40": ("all", 72, 0.40, 14, 0.5, "flip", 0.40, 1.0),
    "B_nonmeme_L72_X40": ("nonmeme", 72, 0.40, 14, 0.5, "flip", 0.40, 1.0),
    "C_all_L72_X80": ("all", 72, 0.80, 14, 0.5, "flip", 0.40, 1.0),
    "D_all_L72_X40_slip2x": ("all", 72, 0.40, 14, 0.5, "flip", 0.40, 2.0),
}
PROMOTABLE = ("A_all_L72_X40", "B_nonmeme_L72_X40", "C_all_L72_X80")
TIERS = [(20e6, 2), (5e6, 3), (1e6, 5), (250e3, 8), (50e3, 12), (0, 15)]  # USD/h -> bp per fill (frozen)


def slip_bp(v):
    if v is None or not np.isfinite(v):
        return 15
    for lo, bp in TIERS:
        if v >= lo:
            return bp
    return 15


def _hl_json(kind, coin):
    for p in (HL / f"{kind}_{coin}.json", HL / "ffdiff" / f"{kind}_{coin}.json"):
        if p.exists():
            return json.loads(p.read_text())["rows"]
    return None


def load_pair(p):
    rows = _hl_json("funding", p["hl"])
    if rows is not None:
        f = pd.DataFrame(rows)
        f = pd.DataFrame({"t": pd.to_datetime(f.time, unit="ms"), "r": f.fundingRate.astype(float)}) if len(f) else None
    else:
        q = W / "hl_funding" / f"{p['hl']}.parquet"
        f = pd.read_parquet(q) if q.exists() else None
        f = pd.DataFrame({"t": pd.to_datetime(f.t_ms, unit="ms"), "r": f.rate.astype(float)}) if f is not None and len(f) else None
    rows = _hl_json("candles_4h", p["hl"])
    if rows is not None:
        k = pd.DataFrame(rows)
        k = pd.DataFrame({"t": pd.to_datetime(k.t, unit="ms"), "h": k.h.astype(float), "l": k.l.astype(float),
                          "c": k.c.astype(float), "v": k.v.astype(float)}) if len(k) else None
    else:
        q = W / "hl_k4h" / f"{p['hl']}.parquet"
        k = pd.read_parquet(q) if q.exists() else None
        k = pd.DataFrame({"t": pd.to_datetime(k.t, unit="ms"), "h": k.h, "l": k.l, "c": k.c, "v": k.v}) if k is not None and len(k) else None
    if f is None or k is None:
        return None
    f["t"] = f.t.dt.floor("h")
    f = f[f.t < CUTOFF].drop_duplicates("t").set_index("t").r.sort_index()
    k = k[k.t + 4 * H <= CUTOFF].drop_duplicates("t").set_index("t").sort_index()
    for q in (BNC / f"{p['bn']}.parquet", BNF / f"{p['bn']}_funding.parquet", W / "bn_funding" / f"{p['bn']}.parquet"):
        if q.exists():
            bf = pd.read_parquet(q)
            break
    else:
        return None
    tcol = "t_ms" if "t_ms" in bf else "t"
    bf = pd.DataFrame({"t": pd.to_datetime(bf[tcol], unit="ms"), "r": bf.rate.astype(float)}).drop_duplicates("t")
    bf = bf[bf.t < CUTOFF].set_index("t").r.sort_index()
    for q in (BNF / f"{p['bn']}_k4h.parquet", W / "bn_k4h" / f"{p['bn']}.parquet"):
        if q.exists():
            bk = pd.read_parquet(q)
            break
    else:
        return None
    bk = pd.DataFrame({"t": pd.to_datetime(bk.t, unit="ms"), "h": bk.h, "l": bk.l, "c": bk.c, "qv": bk.qv})
    bk = bk[(bk.t + 4 * H <= CUTOFF) & (bk.qv > 0)].drop_duplicates("t").set_index("t").sort_index()
    if f.empty or k.empty or bf.empty or bk.empty:
        return None
    return {"hf": f, "hk": k, "bf": bf, "bk": bk}


def liquidity(d):
    """Pre-registered proxy: median 4h quote volume / 4 over train bars (>= 2024-06-01, < 2025-07-01);
    fallback: first 180 available bars if < 42 train bars."""
    out = {}
    for venue, k, qv in (("HL", d["hk"], d["hk"].v * d["hk"].c), ("BN", d["bk"], d["bk"].qv)):
        m = (k.index >= pd.Timestamp("2024-06-01")) & (k.index < TRAIN_END)
        x = qv[m] if m.sum() >= 42 else qv.iloc[:180]
        out[venue] = float(x.median() / 4) if len(x) else float("nan")
    return out


def build_universe():
    u = json.loads((W / "universe_raw.json").read_text())["pairs"]
    keep, rej = [], []
    for p in u:
        d = load_pair(p)
        if d is None:
            rej.append({"hl": p["hl"], "bn": p["bn"], "why": "no data on a venue before 2026-04-01"})
            continue
        hc, bc = d["hk"].c, d["bk"].c
        com = hc.index.intersection(bc.index)
        if len(com) < 42:
            rej.append({"hl": p["hl"], "bn": p["bn"], "why": f"{len(com)} common 4h bars"})
            continue
        ratio = float(np.median(hc[com].values / (bc[com].values * p["ratio"])))
        if not 0.995 <= ratio <= 1.005:
            rej.append({"hl": p["hl"], "bn": p["bn"], "why": f"identity: median ratio {ratio:.4f}"})
            continue
        liq = liquidity(d)
        q = dict(p, median_ratio=ratio, common_bars=len(com), first_common=str(com.min()),
                 train_bars=int((com < TRAIN_END).sum()), V_HL=liq["HL"], V_BN=liq["BN"],
                 slip_HL_bp=slip_bp(liq["HL"]), slip_BN_bp=slip_bp(liq["BN"]))
        keep.append(q)
    (W / "universe.json").write_text(json.dumps({"rule": "reports/hypotheses/ffdiff_wide_preregistration.json",
                                                "pairs": keep, "rejected": rej}, indent=1))
    print(len(u), "name-matched;", len(keep), "kept;", len(rej), "rejected")
    for r in rej:
        print("  rej", r)
    df = pd.DataFrame(keep)
    print("meme", int(df.meme.sum()), "non-meme", int((~df.meme).sum()), "with train bars", int((df.train_bars > 0).sum()))
    print("slip HL tiers", df.slip_HL_bp.value_counts().sort_index().to_dict())
    print("slip BN tiers", df.slip_BN_bp.value_counts().sort_index().to_dict())


def simulate(p, d, F, cfg, split):
    """ffdiff_sim.simulate (iteration 2) with float leverage and per-venue slippage."""
    _, L, X, Z, lev, exit_mode, stop, smult = cfg
    sh, sb = p["slip_HL_bp"] * 1e-4 * smult, p["slip_BN_bp"] * 1e-4 * smult
    s0, s1 = SPLITS[split]
    hk, bk, hf, bf = d["hk"], d["bk"], d["hf"], d["bf"]
    hc = pd.Series(hk.c.values, index=hk.index + 4 * H)
    bc = pd.Series(bk.c.values, index=bk.index + 4 * H)
    common = hc.index.intersection(bc.index)
    mm_hl = 1 / (2 * p["hl_maxlev_now"])
    cost_side = FEE_HL + FEE_BN + sh + sb
    eps, Ts = [], F.index
    Fv = F
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
        T, reason, liq_leg = T0, None, None
        k = Ts.get_loc(T0)
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
            if s == 1:
                if hh >= ph0 * (1 + 1 / lev) / (1 + mm_hl):
                    reason, liq_leg = "liq", "HL"; break
                if bl <= pb0 * (1 - 1 / lev) / (1 - MM_BN):
                    reason, liq_leg = "liq", "BN"; break
            else:
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
            if exit_mode == "flip" and s * Fv.loc[T, f"D{L}"] < 0:
                reason = "exit_signal"; break
            if T - T0 >= pd.Timedelta(days=Z):
                reason = "time"; break
            if T == s1:
                reason = "split_end"; break
        T1 = T
        ph1, pb1 = hc[T1], bc[T1]
        hp = hf[(hf.index > T0) & (hf.index <= T1)]
        bp = bf[(bf.index > T0) & (bf.index <= T1)]
        mh = hc.reindex(hp.index.floor("4h") + 4 * H).values / ph0
        mb = bc.reindex(bp.index.floor("4h") + 4 * H).values / pb0
        funding = s * (float(np.nansum(hp.values * mh)) - float(np.nansum(bp.values * mb)))
        hret, bret = ph1 / ph0 - 1, pb1 / pb0 - 1
        if reason == "liq":
            if liq_leg == "HL":
                basis = -1 / lev + s * bret
                cost = cost_side + FEE_BN + sb
            else:
                basis = -1 / lev - s * hret
                cost = cost_side + FEE_HL + sh
        else:
            basis = s * (-hret + bret)
            cost = 2 * cost_side
        eps.append({"coin": p["hl"], "meme": p["meme"], "dir": "shortHL" if s == 1 else "shortBN", "t0": str(T0),
                    "t1": str(T1), "days": (T1 - T0).total_seconds() / 86400, "D_entry": float(r[f"D{L}"]),
                    "slip_bp_legs": [p["slip_HL_bp"] * smult, p["slip_BN_bp"] * smult],
                    "funding": funding, "basis": basis, "cost": cost, "net": funding + basis - cost,
                    "exit": reason, "liq_leg": liq_leg})
        while j < len(Tlist) and Tlist[j] <= T1:
            j += 1
    return eps


def stats(eps):
    st = fs.stats(eps)
    if not eps:
        return st
    df = pd.DataFrame(eps)
    bc = df.groupby("coin").net.sum().sort_values(ascending=False)
    gp = bc[bc > 0].sum()
    st["n_coins"] = int(df.coin.nunique())
    st["top3_coins"] = bc.head(3).round(4).to_dict()
    st["top3_coin_share_of_positive_coin_net"] = float(bc.head(3).clip(lower=0).sum() / gp) if gp > 0 else None
    st["net_ex_top3_coins"] = float(bc.iloc[3:].sum())
    st["by_meme"] = {("meme" if k else "nonmeme"): {"n": int(len(g)), "net": round(float(g.net.sum()), 4),
                     "funding": round(float(g.funding.sum()), 4), "pf": round(float(g.net[g.net > 0].sum() / -g.net[g.net < 0].sum()), 3) if (g.net < 0).any() else None}
                     for k, g in df.groupby("meme")}
    df["q"] = pd.to_datetime(df.t0).dt.to_period("Q").astype(str)
    st["by_quarter_detail"] = {q: {"n": int(len(g)), "net": round(float(g.net.sum()), 4),
                                   "mean_net_bp": round(float(g.net.mean() * 1e4), 1),
                                   "mean_funding_bp": round(float(g.funding.mean() * 1e4), 1),
                                   "mean_cost_bp": round(float(g.cost.mean() * 1e4), 1)}
                               for q, g in df.groupby("q")}
    st["median_days"] = float(df.days.median())
    st["mean_funding_bp"] = float(df.funding.mean() * 1e4)
    st["mean_basis_bp"] = float(df.basis.mean() * 1e4)
    st["mean_cost_bp"] = float(df.cost.mean() * 1e4)
    return st


def load_all():
    u = json.loads((W / "universe.json").read_text())["pairs"]
    out = []
    for p in u:
        d = load_pair(p)
        out.append((p, d, fs.features(d, Ls=(72,))))
    return out


def run(split, keys):
    if split == "validation":
        tr = json.loads((OBS / "evidence_ffdiff_wide_train.json").read_text())["configs"]
        bad = [k for k in keys if k not in PROMOTABLE or not tr[k]["pass"]]
        if bad:
            raise SystemExit(f"validation refused for {bad}: not a promotable config that passed train")
    data = load_all()
    res = {}
    for key in keys:
        cfg = CONFIGS[key]
        eps = []
        for p, d, F in data:
            if cfg[0] == "nonmeme" and p["meme"]:
                continue
            eps += simulate(p, d, F, cfg, split)
        st = stats(eps)
        ok = fs.passes(st)
        res[key] = {"cfg": cfg, "stats": st, "pass": ok, "episodes": eps}
        print(f"{key:22s} n={st['n']:4d} net={st.get('net', 0):+.3f} pf={st.get('pf', 0):.2f} "
              f"ex3={st.get('net_ex_top3', 0):+.3f} mean={st.get('mean_bp', 0):+.1f}bp "
              f"fund={st.get('mean_funding_bp', 0):+.1f}bp basis={st.get('mean_basis_bp', 0):+.1f}bp "
              f"cost={st.get('mean_cost_bp', 0):.1f}bp liq={st.get('liq', 0)} worst={st.get('worst', 0):+.3f} "
              f"PASS={ok}", flush=True)
    out = OBS / f"evidence_ffdiff_wide_{split}.json"
    out.write_text(json.dumps({"family": "H-FFDIFF-WIDE", "split": split,
                               "preregistration": "reports/hypotheses/ffdiff_wide_preregistration.json",
                               "is_synthetic": False, "configs": res}, indent=1, default=str))
    print("wrote", out)


def main():
    mode = sys.argv[1]
    if mode == "universe":
        build_universe()
    elif mode == "train":
        run("train", list(CONFIGS))
    elif mode == "validation":
        run("validation", sys.argv[2:])


if __name__ == "__main__":
    main()
