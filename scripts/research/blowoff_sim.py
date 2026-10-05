"""H-BLOWOFF event backtest per reports/hypotheses/blowoff_preregistration.json (frozen before any return was
computed). Events come from scripts/research/blowoff_features.py (feature-only).

usage: python scripts/research/blowoff_sim.py train            # every pre-registered config on train
       python scripts/research/blowoff_sim.py validation KEY   # the ONE selected config, run once (lock file)
Never reads anything dated >= 2026-04-01 (all caches are capped at 2026-03-31).

Execution (as pre-registered):
  entry  = open of the 1h bar starting D 01:00 UTC (features are known at D 00:00; 1h latency).
  exit   = open of the 1h bar starting entry + H*24h, or the stop: 2.5 x sig30 (coin's 30-day daily log-return
           std up to D-1) against the position, checked on 1h high/low; fill at the stop price, or the bar open if
           the open is already through the stop; the stop exit time is the end of that bar.
           A coin with no bar left (delisting) exits at its last close with a 2% penalty (memexs convention).
  hedge  = (basket configs) opposite position of beta x notional in the equal-weight basket of the other eligible
           memes on D with a 1h open at entry; beta = OLS slope of the coin's daily returns on the basket's over the
           60 days to D-1 (>= 40 obs, clipped to [0, 3], else 1). Same entry/exit hours as the coin leg.
  costs  = per side 5 bp taker + memexs liquidity-tier slippage (30-day ADV >= $1B 2 bp, >= $200M 5, >= $50M 10,
           else 20), on both coin and hedge legs; funding prints with entry < calc_time <= exit, paid or received on
           entry notional (hedge: basket members' mean funding times beta).
  Lighter (informational only): 0 taker fee, half the tier slippage, Binance funding as proxy.
"""
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blowoff_features as bf  # noqa: E402

ROOT = bf.ROOT
PRE_F = ROOT / "reports/hypotheses/blowoff_preregistration.json"
K1H = [ROOT / "data/raw/web/lsratio/k1h", ROOT / "data/raw/web/qhoi/klines1h", ROOT / "data/raw/web/blowoff/k1h"]
OUT = ROOT / "data/raw/web/blowoff"
EVD = ROOT / "research/observations"
TAKER = 5e-4
HOUR = pd.Timedelta(hours=1)


def slip(adv):
    return 2e-4 if adv >= 1e9 else 5e-4 if adv >= 2e8 else 10e-4 if adv >= 5e7 else 20e-4


def load_1h(syms):
    H = {}
    for s in syms:
        fr = [pd.read_parquet(d / f"{s}.parquet") for d in K1H if (d / f"{s}.parquet").exists()]
        if not fr:
            continue
        d = pd.concat(fr)
        d = d.drop_duplicates("open_time").sort_values("open_time")
        d.index = pd.to_datetime(d.open_time, unit="ms")
        d = d[d.index < bf.CUT]
        if s in bf.REUSED:
            d = d[d.index >= bf.REUSED[s]]
        H[s] = d[["open", "high", "low", "close"]].astype(float)
    return H


class Data:
    def __init__(self):
        self.X = pd.read_parquet(OUT / "features.parquet")
        self.syms = sorted(self.X.sym.unique())
        self.h = load_1h(self.syms)
        self.fund = {s: bf.load_funding(s) for s in self.syms}
        self.cum = {s: (f.cumsum() if f is not None and len(f) else None) for s, f in self.fund.items()}
        cl = {}
        for s in self.syms:
            cl[s] = bf.load_daily(s).close
        self.C = pd.DataFrame(cl)
        self.ret = self.C.pct_change(fill_method=None)
        E = self.X[self.X.elig.astype(bool)]
        self.elig = E.groupby("day").sym.apply(set).to_dict()
        self.adv = self.X.set_index(["sym", "day"]).adv
        # basket daily return: equal-weight mean over eligible memes each day
        el = self.X.pivot(index="day", columns="sym", values="elig").reindex(self.ret.index).fillna(False).astype(bool)
        self.el = el

    def fsum(self, s, t0, t1):
        """sum of funding prints with t0 < calc_time <= t1"""
        c = self.cum.get(s)
        if c is None:
            return 0.0
        a = c[c.index <= t0]
        b = c[c.index <= t1]
        return float((b.iloc[-1] if len(b) else 0.0) - (a.iloc[-1] if len(a) else 0.0))

    def beta(self, s, D):
        w = self.ret.loc[D - pd.Timedelta(days=60):D - pd.Timedelta(days=1)]
        m = self.el.loc[w.index].copy()
        if s in m.columns:
            m[s] = False
        b = w.where(m).mean(axis=1)
        y = w[s] if s in w.columns else None
        if y is None:
            return 1.0
        ok = y.notna() & b.notna()
        if ok.sum() < 40 or b[ok].var() == 0:
            return 1.0
        return float(np.clip(np.cov(y[ok], b[ok])[0, 1] / b[ok].var(), 0, 3))


def price_at(h, t):
    """open of the 1h bar starting at t, else None"""
    return float(h.open.loc[t]) if t in h.index else None


def trade(d, ev, side, H, hedge, lighter=False):
    s, D = ev.sym, ev.day
    h = d.h.get(s)
    te = D + HOUR
    if h is None or te not in h.index:
        return None
    p0 = float(h.open.loc[te])
    tend = te + pd.Timedelta(days=H)
    dist = 2.5 * ev.sig30 if pd.notna(ev.sig30) else np.inf
    stop = p0 * np.exp(dist) if side < 0 else p0 * np.exp(-dist)
    seg = h.loc[te:tend - HOUR]
    exit_p, tx, why, pen = None, None, "time", 0.0
    for t, r in seg.iterrows():
        if side < 0 and r.high >= stop:
            exit_p, tx, why = max(r.open, stop), t + HOUR, "stop"
            break
        if side > 0 and r.low <= stop:
            exit_p, tx, why = min(r.open, stop), t + HOUR, "stop"
            break
    if exit_p is None:
        if tend in h.index:
            exit_p, tx = float(h.open.loc[tend]), tend
        else:
            last = h.index[h.index < tend]
            last = last[last >= te]
            if len(last) == 0:
                return None
            if last[-1] >= bf.CUT - HOUR * 2:  # data end of the split cache, not a delisting
                exit_p, tx, why = float(h.close.loc[last[-1]]), last[-1] + HOUR, "data_end"
            else:
                exit_p, tx, why, pen = float(h.close.loc[last[-1]]), last[-1] + HOUR, "delist", 0.02
    gross = side * (exit_p / p0 - 1) - pen
    fund = -side * d.fsum(s, te, tx)
    adv = float(ev.adv)
    cps = (0.0 if lighter else TAKER) + slip(adv) * (0.5 if lighter else 1.0)
    cost = 2 * cps
    hg = hf = hc = 0.0
    beta, nb = np.nan, 0
    if hedge:
        mem = [m for m in d.elig.get(D, set()) if m != s and m in d.h and te in d.h[m].index]
        if mem:
            beta = d.beta(s, D)
            rs, fs, cs = [], [], []
            for m in mem:
                hm = d.h[m]
                pm0 = float(hm.open.loc[te])
                if tx in hm.index:
                    pm1 = float(hm.open.loc[tx])
                else:
                    lm = hm.index[(hm.index < tx) & (hm.index >= te)]
                    pm1 = float(hm.close.loc[lm[-1]]) if len(lm) else pm0
                rs.append(pm1 / pm0 - 1)
                fs.append(d.fsum(m, te, tx))
                am = d.adv.get((m, D), 0.0)
                cs.append((0.0 if lighter else TAKER) + slip(am if pd.notna(am) else 0.0) * (0.5 if lighter else 1.0))
            nb = len(mem)
            hg = -side * beta * float(np.mean(rs))
            hf = side * beta * float(np.mean(fs))
            hc = 2 * beta * float(np.mean(cs))
    net = gross + fund - cost + hg + hf - hc
    return dict(sym=s, day=D, side=side, H=H, p0=p0, exit=exit_p, exit_t=tx, why=why, gross_coin=gross,
                fund_coin=fund, cost_coin=cost, beta=beta, n_basket=nb, gross_hedge=hg, fund_hedge=hf,
                cost_hedge=hc, gross=gross + hg, funding=fund + hf, cost=cost + hc, net=net)


def stats(T):
    if T is None or len(T) == 0:
        return dict(n=0)
    n = T.net.values
    pos, neg = n[n > 0].sum(), -n[n < 0].sum()
    srt = np.sort(n)[::-1]
    return dict(n=int(len(n)), net_sum=float(n.sum()), mean_net_bp=float(n.mean() * 1e4),
                mean_gross_bp=float(T.gross.mean() * 1e4), mean_funding_bp=float(T.funding.mean() * 1e4),
                mean_cost_bp=float(T.cost.mean() * 1e4), pf=float(pos / neg) if neg > 0 else float("inf"),
                net_ex_top3=float(srt[3:].sum()), win_rate=float((n > 0).mean()),
                stops=int((T.why == "stop").sum()), delists=int((T.why == "delist").sum()),
                median_net_bp=float(np.median(n) * 1e4), n_symbols=int(T.sym.nunique()))


def passes(st):
    return bool(st.get("n", 0) >= 50 and st["net_sum"] > 0 and st["pf"] > 1.2 and st["net_ex_top3"] > 0)


def run_cfg(d, cfg, split, lighter=False):
    E = bf.events(d.X, cfg["arm"], cfg["q"])
    E = E[E.split == split]
    A = bf.accept(E, cfg["H"])
    side = -1 if cfg["arm"] == "short" else 1
    rows, skipped = [], 0
    for _, ev in A.iterrows():
        r = trade(d, ev, side, cfg["H"], cfg["hedge"] == "basket", lighter)
        if r is None:
            skipped += 1
        else:
            rows.append(r)
    return pd.DataFrame(rows), skipped, len(A)


def halves(T):
    if len(T) < 2:
        return {}
    T = T.sort_values("day")
    k = len(T) // 2
    out = {}
    for nm, x in (("first", T.iloc[:k]), ("second", T.iloc[k:])):
        out[nm] = dict(n=len(x), mean_gross_bp=float(x.gross.mean() * 1e4),
                       mean_cost_bp=float(x.cost.mean() * 1e4), mean_net_bp=float(x.net.mean() * 1e4),
                       gross_gt_2x_cost=bool(x.gross.mean() > 2 * x.cost.mean()))
    return out


def placebo(d, cfg, split, n_draw=400, seed=7):
    """same coins, random eligible non-event days in the same split, same direction & hold"""
    E = bf.events(d.X, cfg["arm"], cfg["q"])
    E = E[E.split == split]
    ev_keys = set(zip(E.sym, E.day))
    pool = d.X[(d.X.split == split) & d.X.elig.astype(bool) & d.X.sym.isin(set(E.sym))]
    pool = pool[[(a, b) not in ev_keys for a, b in zip(pool.sym, pool.day)]]
    if len(pool) == 0:
        return {}
    smp = pool.sample(min(n_draw, len(pool)), random_state=seed)
    side = -1 if cfg["arm"] == "short" else 1
    rows = [trade(d, ev, side, cfg["H"], cfg["hedge"] == "basket") for _, ev in smp.iterrows()]
    P = pd.DataFrame([r for r in rows if r])
    if len(P) == 0:
        return {}
    se = P.gross.std() / np.sqrt(len(P))
    return dict(n=len(P), mean_gross_bp=float(P.gross.mean() * 1e4), se_bp=float(se * 1e4),
                t=float(P.gross.mean() / se) if se > 0 else None, mean_net_bp=float(P.net.mean() * 1e4))


def main():
    pre = json.load(open(PRE_F))
    cfgs = {c["key"]: c for c in pre["configs"]}
    d = Data()
    mode = sys.argv[1]
    if mode == "train":
        res = {}
        for k, c in cfgs.items():
            T, sk, na = run_cfg(d, c, "train")
            st = stats(T)
            res[k] = dict(stats=st, accepted_events=na, skipped_no_1h_bar=sk, pass_bar=passes(st),
                          halves=halves(T) if len(T) else {},
                          lighter_info=stats(run_cfg(d, c, "train", lighter=True)[0]))
            res[k]["kill_test_pass"] = bool(res[k]["halves"] and all(v["gross_gt_2x_cost"] for v in res[k]["halves"].values()))
            res[k]["placebo"] = placebo(d, c, "train")
            if len(T):
                T.to_parquet(OUT / f"trades_train_{k}.parquet")
            print(k, json.dumps(st), "pass", res[k]["pass_bar"], "kill", res[k]["kill_test_pass"], flush=True)
        elig = {k: v for k, v in res.items() if v["pass_bar"] and v["kill_test_pass"]}
        sel = max(elig, key=lambda k: (res[k]["stats"]["pf"], res[k]["stats"]["net_ex_top3"])) if elig else None
        out = dict(hypothesis="H-BLOWOFF", split="train", created="2026-10-05", is_synthetic=False,
                   selection_rule=pre["selection_rule"], selected=sel, results=res)
        json.dump(out, open(EVD / "evidence_blowoff_train.json", "w"), indent=1, default=str)
        print("SELECTED", sel)
    elif mode == "validation":
        k = sys.argv[2]
        lock = OUT / "VALIDATION_RUN.lock"
        if lock.exists():
            sys.exit("validation already run once: " + lock.read_text())
        lock.write_text(f"{k} run 2026-10-05\n")
        c = cfgs[k]
        T, sk, na = run_cfg(d, c, "validation")
        st = stats(T)
        TL = run_cfg(d, c, "validation", lighter=True)[0]
        out = dict(hypothesis="H-BLOWOFF", split="validation", created="2026-10-05", is_synthetic=False, config=c,
                   stats=st, pass_bar=passes(st), accepted_events=na, skipped_no_1h_bar=sk,
                   lighter_info=stats(TL), placebo=placebo(d, c, "validation"),
                   contamination_note=pre["long_arm_contamination"] if c["arm"] == "long" else None)
        if len(T):
            T.to_parquet(OUT / f"trades_validation_{k}.parquet")
            out["top5_trades"] = T.nlargest(5, "net")[["sym", "day", "net", "why"]].to_dict("records")
            out["by_symbol_net"] = T.groupby("sym").net.sum().sort_values().to_dict()
        json.dump(out, open(EVD / "evidence_blowoff_validation.json", "w"), indent=1, default=str)
        print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
