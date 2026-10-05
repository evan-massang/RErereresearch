"""H-SPOTCARRY-WIDE episode simulator. Rule frozen in reports/hypotheses/spotcarry_wide_preregistration.json
(written before any price data was fetched or any P&L computed).

Long Q spot units + short Q USD-M perp units (1x isolated), Binance only. Capital = Q*spot0 + Q*perp0.
Clock: integer hour boundaries T (hours since epoch). Information at T = funding prints with calc hour <= T and
1h bars that closed by T (open <= T-1). Entry/exit signals at T fill at the close of bar opening at T (time T+1).
Stop: perp bar high >= 1.5*entry -> perp at max(1.5*entry, bar open), spot at the bar close.

    python scripts/research/spotcarry_sim.py train|validation [config_key ...] [--spotfee 0.00075] [--slipx 2]
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data/raw/web/binance_carry"
PRE = json.loads((ROOT / "reports/hypotheses/spotcarry_wide_preregistration.json").read_text())
CONFIGS = {c["key"]: c for c in PRE["configs"]}
H_MS = 3_600_000
def hr(s): return int(pd.Timestamp(s, tz="UTC").timestamp() // 3600)
SPLITS = {"train": (0, hr("2025-07-01")), "validation": (hr("2025-07-01"), hr("2026-04-01"))}
DATA_END = hr("2026-04-01")
SPOT_FEE, PERP_FEE = 0.001, 0.0005
TIER1, TIER2 = 20e6, 2e6
SLIP1, SLIP2 = 0.0005, 0.0015
MMR = 0.025
DELIST_PEN = 0.02
ANN = 365 * 24 / 72


def load_pair(p):
    fs, ps, ss = D / f"funding/{p['perp']}.parquet", D / f"perp/{p['perp']}.parquet", D / f"spot/{p['spot']}.parquet"
    if not (fs.exists() and ps.exists() and ss.exists()):
        return None
    f, pp, sp = pd.read_parquet(fs), pd.read_parquet(ps), pd.read_parquet(ss)
    if len(f) < 10 or len(pp) < 800 or len(sp) < 800:
        return None
    k = float(p["mult"])
    h0 = int(min(pp.h.min(), sp.h.min()))
    h1 = int(max(pp.h.max(), sp.h.max())) + 2
    n = h1 - h0
    def grid(s, col, scale=1.0):
        a = np.full(n, np.nan)
        a[s.h.to_numpy() - h0] = s[col].to_numpy().astype(float) / scale
        return a
    po, phi, pc = grid(pp, "open", k), grid(pp, "high", k), grid(pp, "close", k)
    sc, qv = grid(sp, "close"), grid(sp, "qv")
    th = np.rint(f.t_ms.to_numpy() / H_MS).astype(np.int64) - h0
    keep = (th >= 0) & (th < n)
    th, rate, iv = th[keep], f.rate.to_numpy()[keep], f.interval_h.to_numpy()[keep].astype(float)
    th, ui = np.unique(th, return_index=True)
    rate, iv = rate[ui], iv[ui]
    # interval: column if present, else gap to previous print
    gap = np.diff(np.concatenate([[th[0] - 8], th])).astype(float)
    iv = np.where(iv > 0, iv, np.clip(gap, 1, 8))
    fg = np.zeros(n); fg[th] = rate
    cs = np.cumsum(fg)
    s72 = cs - np.concatenate([np.zeros(72), cs[:-72]])          # prints in (T-72, T]
    last8 = np.full(n, np.nan); last8[th] = rate * 8 / iv
    last8 = pd.Series(last8).ffill().to_numpy()
    q = np.nan_to_num(qv)
    cq = np.cumsum(q)
    vol7 = np.full(n, np.nan)                                     # bars open in [T-168, T-1]
    vol7[168:] = (cq[167:-1] - np.concatenate([[0], cq[:-169]])) / 7
    T = np.arange(n)
    first_p, first_s = int(pp.h.min()) - h0, int(sp.h.min()) - h0
    last_p, last_s = int(pp.h.max()) - h0, int(sp.h.max()) - h0
    have = np.zeros(n, bool); have[1:] = ~np.isnan(pc[:-1]) & ~np.isnan(sc[:-1])   # bar ending at T exists
    elig = (T - 720 >= first_p) & (T - 720 >= first_s) & have & (vol7 >= TIER2)
    return dict(sym=p["perp"], spot=p["spot"], mult=k, h0=h0, n=n, po=po, phi=phi, pc=pc, sc=sc, th=th, rate=rate,
                s72=s72 * ANN, last8=last8, vol7=vol7, elig=elig, last_common=min(last_p, last_s))


def run_pair(P, cfg, split, spot_fee=SPOT_FEE, slipx=1.0):
    h0, n = P["h0"], P["n"]
    a, b = SPLITS[split]
    a, b = max(a - h0, 0), min(b - h0, n - 1)
    F, X, Z, STOP = cfg["F_ann"], cfg["exit_ann"], cfg["Z_days"] * 24, 1 + cfg["stop"]
    s72, po, phi, pc, sc = P["s72"], P["po"], P["phi"], P["pc"], P["sc"]
    sig = P["elig"] & (s72 >= F) & (P["last8"] >= 0.0001)
    delisted = P["last_common"] + h0 < DATA_END - 2
    eps, T = [], a
    cand = np.flatnonzero(sig[a:b]) + a
    ci = 0
    while ci < len(cand):
        T = cand[ci]
        if T + 1 > b or np.isnan(pc[T]) or np.isnan(sc[T]):
            ci += 1; continue
        tf = T + 1                                  # entry fill time (close of bar T)
        P0, S0 = pc[T], sc[T]
        slip = (SLIP1 if P["vol7"][T] >= TIER1 else SLIP2) * slipx
        tier = 1 if P["vol7"][T] >= TIER1 else 2
        liq = P0 * 2 / (1 + MMR)
        reason, te, Pe, Se, pen = None, None, None, None, 0.0
        mae = 0.0
        bb = tf
        last_ok = T
        while True:
            # bar bb: open bb, close bb+1
            if bb > P["last_common"] and delisted and bb < b:
                reason, te, Pe, Se, pen = "delist", last_ok + 1, pc[last_ok], sc[last_ok], DELIST_PEN; break
            if bb + 1 > b:                           # split end: close at last bar of split
                j = last_ok
                reason, te, Pe, Se = "split_end", j + 1, pc[j], sc[j]; break
            okb = not (np.isnan(phi[bb]) or np.isnan(sc[bb]))
            if okb:
                mae = max(mae, phi[bb] / P0 - 1)
                if phi[bb] >= STOP * P0:
                    if po[bb] >= liq:
                        reason, te, Pe, Se = "liquidation", bb, None, sc[bb]
                    else:
                        reason, te, Pe, Se = "stop", bb, max(STOP * P0, po[bb]), sc[bb]
                    break
                last_ok = bb
            Tb = bb + 1                              # decision boundary after bar bb closes
            if okb and (s72[Tb] < X or Tb - tf >= Z):
                j = Tb
                while j < min(b, n) and (np.isnan(pc[j]) or np.isnan(sc[j])):
                    j += 1
                if j >= b or j >= n:
                    j = last_ok
                reason = "signal" if s72[Tb] < X else "time"
                te, Pe, Se = j + 1, pc[j], sc[j]; break
            bb += 1
        Q = 1.0 / S0
        cap = 1.0 + Q * P0
        fm = (P["th"] > tf) & (P["th"] <= te)
        idx = P["th"][fm] - 1
        mark = pc[np.clip(idx, 0, n - 1)]
        mark = np.where(np.isnan(mark), P0, mark)
        funding = float(np.sum(P["rate"][fm] * Q * mark))
        if reason == "liquidation":
            perp_pnl = -Q * P0; Pe_fee = liq
        else:
            perp_pnl = -Q * (Pe - P0); Pe_fee = Pe
        spot_pnl = Q * (Se - S0)
        cost = spot_fee * (1 + Q * Se) + PERP_FEE * Q * (P0 + Pe_fee) + slip * (1 + Q * Se + Q * P0 + Q * Pe_fee)
        pen_abs = pen * cap
        ret = (spot_pnl + perp_pnl + funding - cost - pen_abs) / cap
        eps.append(dict(sym=P["sym"], entry_T=int(T + h0), entry=str(pd.Timestamp((T + h0) * 3600, unit="s")),
                        hours=int(te - tf), reason=reason, tier=tier, s72_entry=float(s72[T]),
                        basis_entry=float(P0 / S0 - 1), ret=float(ret), funding=float(funding / cap),
                        basis_pnl=float((spot_pnl + perp_pnl) / cap), cost=float((cost + pen_abs) / cap),
                        mae_perp=float(mae)))
        # re-entry allowed from the next decision hour >= exit fill time
        nxt = te if reason not in ("stop", "liquidation") else te + 1
        while ci < len(cand) and cand[ci] < nxt:
            ci += 1
    return eps


def stats(df):
    if len(df) == 0:
        return {"n": 0}
    r = df.ret.to_numpy()
    pos, neg = r[r > 0].sum(), -r[r < 0].sum()
    srt = np.sort(r)[::-1]
    byc = df.groupby("sym").ret.sum().sort_values(ascending=False)
    day = df.assign(d=df.entry.str[:10]).groupby("d").ret.sum().sort_values(ascending=False)
    eq = np.cumsum(r[np.argsort(df.entry_T.to_numpy(), kind="stable")])
    return {"n": int(len(r)), "net": float(r.sum()), "pf": float(pos / neg) if neg > 0 else None,
            "net_ex_top3": float(srt[3:].sum()), "mean": float(r.mean()), "median": float(np.median(r)),
            "win": float((r > 0).mean()), "funding": float(df.funding.sum()), "basis": float(df.basis_pnl.sum()),
            "cost": float(df.cost.sum()), "worst": [df.loc[df.ret.idxmin(), "sym"], float(r.min())],
            "best": [df.loc[df.ret.idxmax(), "sym"], float(r.max())],
            "max_dd_sum": float(np.max(np.maximum.accumulate(np.concatenate([[0], eq])) - np.concatenate([[0], eq]))),
            "coins": int(df.sym.nunique()), "top3_coins": {k: float(v) for k, v in byc.head(3).items()},
            "top3_coin_share_of_net": float(byc.head(3).sum() / r.sum()) if r.sum() != 0 else None,
            "net_ex_top3_days": float(day.iloc[3:].sum()), "event_days": int(len(day)),
            "reasons": df.reason.value_counts().to_dict(), "tier": df.tier.value_counts().to_dict(),
            "mae_perp_max": float(df.mae_perp.max()), "hours_median": float(df.hours.median())}


def bar(s):
    return bool(s["n"] >= 50 and s["net"] > 0 and (s["pf"] or 0) > 1.2 and s["net_ex_top3"] > 0)


def main():
    args = sys.argv[1:]
    split = args[0]
    spot_fee = float(args[args.index("--spotfee") + 1]) if "--spotfee" in args else SPOT_FEE
    slipx = float(args[args.index("--slipx") + 1]) if "--slipx" in args else 1.0
    keys = [x for x in args[1:] if x in CONFIGS] or list(CONFIGS)
    U = json.load(open(D / "universe.json"))["pairs"]
    pairs = [P for P in (load_pair(p) for p in U) if P is not None]
    print(len(pairs), "pairs loaded", file=sys.stderr)
    out = {"split": split, "spot_fee": spot_fee, "slip_mult": slipx, "pairs_loaded": len(pairs), "configs": {}}
    for kk in keys:
        cfg = CONFIGS[kk]
        df = pd.DataFrame([e for P in pairs for e in run_pair(P, cfg, split, spot_fee, slipx)])
        s = stats(df)
        s["passes_bar"] = bar(s) if s["n"] else False
        if len(df):
            q = pd.to_datetime(df.entry).dt.to_period("Q").astype(str)
            s["by_quarter"] = {k: {"n": int(len(g)), "net": float(g.ret.sum()), "funding": float(g.funding.sum())}
                               for k, g in df.groupby(q)}
            s["by_year"] = {k: {"n": int(len(g)), "net": float(g.ret.sum()), "mean": float(g.ret.mean())}
                            for k, g in df.groupby(df.entry.str[:4])}
            s["ex_2024Q4"] = stats(df[q != "2024Q4"])
            s["ex_2024Q4"] = {k: s["ex_2024Q4"][k] for k in ("n", "net", "pf", "net_ex_top3")}
            s["by_coin_top10"] = df.groupby("sym").ret.agg(["count", "sum"]).sort_values("sum", ascending=False).head(10).round(4).to_dict("index")
            s["by_coin_bottom5"] = df.groupby("sym").ret.agg(["count", "sum"]).sort_values("sum").head(5).round(4).to_dict("index")
            s["worst5"] = df.nsmallest(5, "ret")[["sym", "entry", "reason", "ret", "funding", "basis_pnl"]].round(4).to_dict("records")
            s["best5"] = df.nlargest(5, "ret")[["sym", "entry", "reason", "ret", "funding", "basis_pnl"]].round(4).to_dict("records")
        out["configs"][kk] = s
        print(kk, {k: s.get(k) for k in ("n", "net", "pf", "net_ex_top3", "funding", "basis", "cost", "passes_bar")}, file=sys.stderr)
        df.to_parquet(ROOT / f"data/raw/web/binance_carry/episodes_{split}_{kk}_sf{spot_fee}_sx{slipx}.parquet")
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
