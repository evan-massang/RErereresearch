"""H-LOTTOSHORT: weekly funding-gated, beta-hedged short of the Binance USDT-M meme-perp basket vs BTC (or BTC/SOL),
per reports/hypotheses/lottoshort_preregistration.json (frozen before any return was computed).

usage: python scripts/research/lottoshort_sim.py train           # 12 configs on train + selection
       python scripts/research/lottoshort_sim.py validation KEY  # selected config, run once
       python scripts/research/lottoshort_sim.py diag SPLIT KEY  # diagnostics (not used for selection)
Reads data/raw/web/momentum/{klines,funding} read-only, days <= 2026-03-31 only. Never reads any holdout cache.
"""
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/web/momentum"
OUT = ROOT / "data/raw/web/lottoshort"
OBS = ROOT / "research/observations"
PRE = json.load(open(ROOT / "reports/hypotheses/lottoshort_preregistration.json"))
CFG = {c["key"]: c for c in PRE["configs"]}
MEMES = PRE["universe"]["meme_symbols"]
DOUBT = set(PRE["universe"]["identity_doubtful_diagnostic"])
TAKER, MIN_ADV, MIN_N, MIN_BARS, DELIST_PEN = 0.0005, 5e6, 3, 35, 0.02
LAST_DAY = pd.Timestamp("2026-03-31")
SPLITS = {"train": (pd.Timestamp("2022-01-03"), pd.Timestamp("2025-06-23")),
          "validation": (pd.Timestamp("2025-07-07"), pd.Timestamp("2026-03-23"))}  # first / last rebalance Monday
HEDGES = ["BTCUSDT", "SOLUSDT"]
ALT_EXCLUDE = {"BTCUSDT", "ETHUSDT", "SOLUSDT", "BTCDOMUSDT", "DEFIUSDT", "USDCUSDT", "BUSDUSDT", "TUSDUSDT",
               "FDUSDUSDT", "USDPUSDT", "USDEUSDT", "USD1USDT", "EURUSDT", "XUSDUSDT", "RLUSDUSDT"}


def load(symbols):
    cl, qv, fund = {}, {}, {}
    for s in symbols:
        p = RAW / "klines" / f"{s}.parquet"
        if not p.exists():
            continue
        d = pd.read_parquet(p)
        d.index = pd.to_datetime(d.open_time, unit="ms").dt.normalize()
        d = d[~d.index.duplicated()]
        d = d[d.index <= LAST_DAY]
        if not len(d):
            continue
        cl[s], qv[s] = d.close, d.quote_volume
        pf = RAW / "funding" / f"{s}.parquet"
        if pf.exists():
            f = pd.read_parquet(pf).drop_duplicates("calc_time")
            t = pd.to_datetime(f.calc_time, unit="ms").dt.round("h")
            fs = pd.Series(f.last_funding_rate.values, index=t).groupby(level=0).last().sort_index()
            fund[s] = fs[fs.index < LAST_DAY + pd.Timedelta(days=1)]
    C = pd.DataFrame(cl).sort_index()
    full = pd.date_range(C.index.min(), LAST_DAY, freq="D")
    return C.reindex(full), pd.DataFrame(qv).reindex(full), fund


def slip(advq):
    advq = np.asarray(advq, dtype=float)
    return np.where(advq >= 1e9, 2e-4, np.where(advq >= 2e8, 5e-4, np.where(advq >= 5e7, 10e-4, 20e-4)))


def fsum(fund, s, a, b, left_closed):
    if s not in fund:
        return np.nan
    fs = fund[s]
    m = (fs.index >= a) & (fs.index < b) if left_closed else (fs.index > a) & (fs.index <= b)
    return float(fs[m].sum()) if m.any() else np.nan


def run(cfg, split, D, basket_syms, gate=None, slipx=1.0, use_funding=True, exclude=(), hedge_on=True):
    """D = (C, Q, fund) containing basket_syms and BTC/SOL. Returns legs E, weeks W."""
    C, Q, fund = D
    gate = gate or cfg["gate"]
    bsyms = [s for s in basket_syms if s in C.columns and s not in exclude]
    R = C / C.shift(1) - 1
    Cf = C.ffill(limit=5)
    lastbar = {s: C[s].last_valid_index() for s in C.columns}
    P = C.notna()
    nb = P.cumsum(); p30 = P.rolling(30, min_periods=1).sum()
    adv = Q.fillna(0).rolling(30, min_periods=1).sum() / 30
    hsyms = ["BTCUSDT"] if cfg["hedge"] == "BTC" else ["BTCUSDT", "SOLUSDT"]
    hret = R[hsyms].mean(axis=1) if len(hsyms) == 2 else R["BTCUSDT"]
    first, last = SPLITS[split]
    mondays = pd.date_range(first, last, freq="7D")
    legs, weeks = [], []
    w_old = pd.Series(dtype=float)
    last_rec = {}              # symbol -> index of leg that last held it (meme legs)
    prev_meme_idx, prev_week = [], None

    def charge_prev(c_by_sym, week_idx, meme_idx):
        """closing costs with no current position: meme symbols -> their last leg; hedge -> pro-rata on meme_idx."""
        tot = 0.0
        hs = sum(v for s, v in c_by_sym.items() if s in HEDGES)
        for s, v in c_by_sym.items():
            if s not in HEDGES:
                legs[last_rec[s]]["cost"] += v
        if hs and meme_idx:
            den = sum(abs(legs[i]["w"]) for i in meme_idx)
            for i in meme_idx:
                legs[i]["hcost"] += hs * abs(legs[i]["w"]) / den
        tot = sum(c_by_sym.values())
        if week_idx is not None:
            weeks[week_idx]["pnl"] -= tot; weeks[week_idx]["cost"] += tot
        return tot

    for t in mondays:
        dp = t - pd.Timedelta(days=1)
        dexit = t + pd.Timedelta(days=6)
        bs = [s for s in bsyms]
        elig = (nb.loc[dp, bs] >= MIN_BARS) & P.loc[dp, bs] & (p30.loc[dp, bs] >= 25) & (adv.loc[dp, bs] >= MIN_ADV)
        u = list(elig[elig].index)
        rec = dict(t=t, n_elig=len(u), gate_F=np.nan, beta=np.nan, traded=False, pnl=0.0, cost=0.0, fund=0.0,
                   meme_px=0.0, hedge_px=0.0, n_legs=0)
        w = pd.Series(dtype=float)
        if len(u) >= MIN_N:
            # basket weights
            if cfg["weighting"] == "IV":
                vol = R.loc[dp - pd.Timedelta(days=29):dp, u].std()
                cnt = R.loc[dp - pd.Timedelta(days=29):dp, u].notna().sum()
                vol[cnt < 20] = np.nan
                vol = vol.fillna(vol.median())
                b = (1 / vol); b = b / b.sum()
            else:
                b = pd.Series(1.0 / len(u), index=u)
            # beta
            W = cfg["beta_window_days"]
            win = R.loc[dp - pd.Timedelta(days=W - 1):dp, u]
            wm = win.notna().mul(b, axis=1)
            bret = (win.fillna(0).mul(b, axis=1).sum(axis=1) / wm.sum(axis=1).replace(0, np.nan))
            h = hret.loc[bret.index]
            ok = bret.notna() & h.notna()
            beta = float(np.cov(bret[ok], h[ok])[0, 1] / np.var(h[ok], ddof=1)) if ok.sum() >= 10 else np.nan
            beta = float(np.clip(beta, 0.25, 3.0)) if np.isfinite(beta) else 1.0
            # funding gate (per-8h equivalent)
            F = pd.Series({s: fsum(fund, s, t - pd.Timedelta(days=7), t, True) / 21 for s in u}).dropna()
            Fm = float(F.mean()) if len(F) else np.nan
            rec.update(gate_F=Fm, beta=beta)
            on = gate == "G0" or (np.isfinite(Fm) and ((gate == "G1" and Fm > 0) or (gate == "G2" and Fm > 1e-4)))
            if on:
                if hedge_on:
                    S, H = 1 / (1 + beta), beta / (1 + beta)
                else:
                    S, H = 1.0, 0.0
                w = -S * b
                if H > 0:
                    for hs in hsyms:
                        w[hs] = H / len(hsyms)
        allsym = w.index.union(w_old.index)
        cps = pd.Series(TAKER + slip(adv.loc[dp, allsym].fillna(0).values) * slipx, index=allsym)
        cdelta = {s: abs(w.get(s, 0.0) - w_old.get(s, 0.0)) * cps[s] for s in allsym}
        if not len(w):
            # flat week: closing costs belong to the previous traded week
            if any(v > 0 for v in cdelta.values()):
                charge_prev(cdelta, prev_week, prev_meme_idx)
            weeks.append(rec); w_old = pd.Series(dtype=float); prev_meme_idx = []
            continue
        # closing costs of symbols that dropped out (memes -> their last leg; hedge cannot drop while traded)
        drop_c = {s: v for s, v in cdelta.items() if s not in w.index}
        if drop_c:
            charge_prev(drop_c, None, prev_meme_idx)
        rec["cost"] += sum(drop_c.values())
        # per-symbol P&L
        px, fr, cs, dl = {}, {}, {}, set()
        for s, ws in w.items():
            # archive gaps (e.g. SOLUSDT 2022-02-26..28, 2022-04-01..02) are forward-filled; a leg is a delisting exit
            # only if the symbol has no bar at all on or after dexit (amendment before any output was seen)
            lv = min(dexit, lastbar[s])
            px[s] = ws * (Cf.loc[lv, s] / Cf.loc[dp, s] - 1)
            if lastbar[s] < dexit:
                px[s] -= abs(ws) * DELIST_PEN; dl.add(s)
            f = fsum(fund, s, t, min(t + pd.Timedelta(days=7), lv + pd.Timedelta(days=1)), False) if use_funding else 0.0
            fr[s] = (f if np.isfinite(f) else 0.0) * ws      # paid by the position
            cs[s] = cdelta[s]
        hpx = sum(px[s] for s in w.index if s in HEDGES); hfr = sum(fr[s] for s in w.index if s in HEDGES)
        hcs = sum(cs[s] for s in w.index if s in HEDGES)
        memes_now = [s for s in w.index if s not in HEDGES]
        den = sum(abs(w[s]) for s in memes_now)
        idx = []
        for s in memes_now:
            sh = abs(w[s]) / den
            legs.append(dict(sym=s, t=t, w=w[s], ret=px[s], fund=fr[s], cost=cs[s], delist=s in dl,
                             hret=hpx * sh, hfund=hfr * sh, hcost=hcs * sh))
            last_rec[s] = len(legs) - 1; idx.append(len(legs) - 1)
        rec.update(traded=True, n_legs=len(memes_now),
                   meme_px=sum(px[s] for s in memes_now), hedge_px=hpx, fund=sum(fr.values()),
                   cost=rec["cost"] + sum(cs.values()),
                   hedge_ret_week=float(np.mean([Cf.loc[dexit, h] / Cf.loc[dp, h] - 1 for h in hsyms])),
                   btc_ret_week=float(Cf.loc[dexit, "BTCUSDT"] / Cf.loc[dp, "BTCUSDT"] - 1),
                   short_notional=float(-w[memes_now].sum()))
        rec["pnl"] = rec["meme_px"] + hpx - rec["fund"] - rec["cost"]
        weeks.append(rec)
        prev_week, prev_meme_idx = len(weeks) - 1, idx
        w_old = w.drop(list(dl))
    if len(w_old):  # force-close at split end
        dl_ = SPLITS[split][1] + pd.Timedelta(days=6)
        c = {s: abs(ws) * (TAKER + float(slip([adv.loc[dl_, s] if pd.notna(adv.loc[dl_, s]) else 0])[0]) * slipx)
             for s, ws in w_old.items()}
        charge_prev(c, prev_week, prev_meme_idx)
    E = pd.DataFrame(legs)
    E["pnl"] = E.ret - E.fund - E.cost + E.hret - E.hfund - E.hcost
    Wk = pd.DataFrame(weeks)
    T = Wk[Wk.traded]
    assert abs(E.pnl.sum() - T.pnl.sum()) < 1e-9, (E.pnl.sum(), T.pnl.sum())
    return E, Wk


def unit_stats(p):
    p = pd.Series(p).sort_values(ascending=False)
    wins, losses = p[p > 0].sum(), -p[p < 0].sum()
    return dict(n=int(len(p)), net=round(float(p.sum()), 4), pf=round(float(wins / losses), 3) if losses > 0 else None,
                net_ex_top3=round(float(p.iloc[3:].sum()), 4), top3=[round(float(x), 4) for x in p.iloc[:3]],
                mean_bp=round(float(p.mean()) * 1e4, 1) if len(p) else None)


def passes(u, nmin=50):
    return bool(u["n"] >= nmin and u["net"] > 0 and (u["pf"] or 0) > 1.2 and u["net_ex_top3"] > 0)


def ols(y, x):
    X = np.column_stack([np.ones(len(x)), x]); y = np.asarray(y, float)
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ b; n = len(y)
    s2 = e @ e / (n - 2); V = s2 * np.linalg.inv(X.T @ X)
    r2 = 1 - (e @ e) / ((y - y.mean()) @ (y - y.mean()))
    return dict(alpha_bp=round(b[0] * 1e4, 1), alpha_t=round(b[0] / np.sqrt(V[0, 0]), 2), beta=round(b[1], 3),
                beta_t=round(b[1] / np.sqrt(V[1, 1]), 2), r2=round(r2, 3), n=n)


def stats(E, Wk, split):
    T = Wk[Wk.traded].copy()
    wk, lg = unit_stats(T.pnl), unit_stats(E.pnl)
    eq = T.pnl.cumsum(); dd = float((eq - eq.cummax()).min()) if len(eq) else 0.0
    T["half"] = T.t.dt.year.astype(str) + np.where(T.t.dt.month <= 6, "H1", "H2")
    bycoin = E.groupby("sym").pnl.sum().sort_values(ascending=False)
    out = dict(split=split, weeks=wk, legs=lg, weeks_possible=int(len(Wk)), weeks_traded=int(len(T)),
               weeks_gated_off=int(((Wk.n_elig >= MIN_N) & ~Wk.traded).sum()),
               weeks_too_few_memes=int((Wk.n_elig < MIN_N).sum()),
               mean_basket_size=round(float(T.n_legs.mean()), 1) if len(T) else None,
               mean_beta=round(float(T.beta.mean()), 3) if len(T) else None,
               mean_short_notional=round(float(T.short_notional.mean()), 3) if len(T) else None,
               weekly_sharpe=round(float(T.pnl.mean() / T.pnl.std() * np.sqrt(52)), 3) if len(T) > 2 else None,
               maxdd_additive=round(dd, 4),
               meme_short_px=round(float(T.meme_px.sum()), 4), hedge_long_px=round(float(T.hedge_px.sum()), 4),
               funding_paid=round(float(T.fund.sum()), 4), costs=round(float(T.cost.sum()), 4),
               meme_funding_paid=round(float(E.fund.sum()), 4), hedge_funding_paid=round(float(E.hfund.sum()), 4),
               per_half=T.groupby("half").pnl.sum().round(4).to_dict(),
               per_year=T.groupby(T.t.dt.year).pnl.sum().round(4).to_dict(),
               top3_coins=bycoin.iloc[:3].round(4).to_dict(), worst3_coins=bycoin.iloc[-3:].round(4).to_dict(),
               delist_exits=int(E.delist.sum()) if len(E) else 0,
               first_week=str(T.t.min().date()) if len(T) else None, last_week=str(T.t.max().date()) if len(T) else None)
    if len(T) > 5:
        out["beta_check_btc"] = ols(T.pnl, T.btc_ret_week)
        out["beta_check_hedge"] = ols(T.pnl, T.hedge_ret_week)
    nmin_unit = "weeks" if split == "train" else "legs"
    out["pass_weeks_unit"] = passes(wk) if split == "train" else bool(wk["net"] > 0 and (wk["pf"] or 0) > 1.2 and wk["net_ex_top3"] > 0)
    out["pass_legs_unit"] = passes(lg)
    out["n_unit_for_bar"] = nmin_unit
    out["pass"] = bool(out["pass_weeks_unit"] and out["pass_legs_unit"])
    hy = out["per_half"]
    out["kill_test"] = dict(halves_positive=int(sum(v > 0 for v in hy.values())), halves=len(hy), maxdd_ok=bool(dd > -0.35))
    return out


def short(r):
    return {k: r[k] for k in ["weeks", "legs", "weeks_traded", "maxdd_additive", "pass"]} | {"per_year": r["per_year"]}


def alt_universe():
    syms = json.load(open(RAW / "symbols.json"))
    syms = [s if isinstance(s, str) else s.get("symbol") for s in syms]
    return sorted(s for s in syms if s and s.endswith("USDT") and "_" not in s and s not in ALT_EXCLUDE and s not in MEMES)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    a = sys.argv[1:]
    D = load(MEMES + HEDGES)
    if a[0] == "train":
        res = {}
        for k, c in CFG.items():
            E, Wk = run(c, "train", D, MEMES)
            res[k] = stats(E, Wk, "train"); print(k, short(res[k]), flush=True)
            E.to_parquet(OUT / f"legs_train_{k}.parquet"); Wk.to_parquet(OUT / f"weekly_train_{k}.parquet")
        passing = [k for k in res if res[k]["pass"]]
        pool = passing or list(res)
        sel = max(pool, key=lambda k: res[k]["weeks"]["net_ex_top3"])
        print("passing:", passing, "selected:", sel)
        json.dump(dict(split="train", preregistration="reports/hypotheses/lottoshort_preregistration.json",
                       passing=passing, selected=sel, selected_is_diagnostic_only=not passing, results=res),
                  open(OBS / "evidence_lottoshort_train_20261005.json", "w"), indent=1, default=str)
    elif a[0] == "validation":
        k = a[1]
        ev = json.load(open(OBS / "evidence_lottoshort_train_20261005.json"))
        assert ev["selected"] == k, "validation must use the config selected on train"
        f = OBS / "evidence_lottoshort_validation_20261005.json"
        assert not f.exists(), "validation already run once"
        E, Wk = run(CFG[k], "validation", D, MEMES)
        r = stats(E, Wk, "validation"); print(k, short(r))
        E.to_parquet(OUT / f"legs_validation_{k}.parquet"); Wk.to_parquet(OUT / f"weekly_validation_{k}.parquet")
        json.dump(dict(split="validation", config=k, diagnostic_only=ev["selected_is_diagnostic_only"], result=r),
                  open(f, "w"), indent=1, default=str)
    elif a[0] == "diag":
        split, k = a[1], a[2]
        c = CFG[k]
        out = {}
        variants = [("primary", {}), ("G0_always_on", dict(gate="G0")), ("slipx2", dict(slipx=2.0)),
                    ("no_funding", dict(use_funding=False)), ("ex_identity_doubtful", dict(exclude=DOUBT)),
                    ("unhedged_short_same_gate", dict(hedge_on=False)), ("unhedged_short_G0", dict(hedge_on=False, gate="G0"))]
        Wks = {}
        for name, kw in variants:
            E, Wk = run(c, split, D, MEMES, **kw)
            out[name] = stats(E, Wk, split); Wks[name] = Wk; print(name, short(out[name]), flush=True)
        alts = alt_universe()
        DA = load(alts + HEDGES)
        for name, kw in [("ALT_placebo_same_config", {}), ("ALT_placebo_G0", dict(gate="G0"))]:
            E, Wk = run(c, split, DA, alts, **kw)
            out[name] = stats(E, Wk, split); Wks[name] = Wk; print(name, short(out[name]), flush=True)
            Wk.to_parquet(OUT / f"weekly_{split}_{k}_{name}.parquet")
        # meme-specific excess over the alt placebo, week by week (G0 vs G0 so both trade every week)
        m = Wks["G0_always_on"].set_index("t"); p = Wks["ALT_placebo_G0"].set_index("t")
        j = m[m.traded].pnl.to_frame("meme").join(p[p.traded].pnl.rename("alt"), how="inner")
        d = j.meme - j.alt
        out["meme_minus_alt_G0_weekly"] = dict(n=int(len(d)), mean_bp=round(float(d.mean()) * 1e4, 1),
                                              t=round(float(d.mean() / d.std() * np.sqrt(len(d))), 2),
                                              corr_meme_alt=round(float(j.corr().iloc[0, 1]), 3),
                                              meme_sum=round(float(j.meme.sum()), 4), alt_sum=round(float(j.alt.sum()), 4))
        out["alt_universe_size"] = len(alts)
        print("meme-alt", out["meme_minus_alt_G0_weekly"])
        json.dump(dict(split=split, config=k, note="diagnostics, not used for selection", results=out),
                  open(OBS / f"evidence_lottoshort_diag_{split}_20261005.json", "w"), indent=1, default=str)
