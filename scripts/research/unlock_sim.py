"""H-UNLOCK step 3: simulate the pre-registered short-around-unlock trades.

Reads reports/hypotheses/unlock_preregistration.json. Never reads prices >= 2026-04-01.
Usage: python scripts/research/unlock_sim.py train            -> all 12 configs on train
       python scripts/research/unlock_sim.py validation <key>  -> one config, run once
"""
import json, sys, pathlib, datetime
import pandas as pd, numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
U = ROOT / "data/raw/web/unlock"
PRE = json.load(open(ROOT / "reports/hypotheses/unlock_preregistration.json"))
DAYMS = 86400000
D = lambda s: pd.Timestamp(s).value // (86400 * 10**9)
TRAIN_END, VAL_START, VAL_END = D("2025-06-30"), D("2025-07-01"), D("2026-03-31")
HOLD = D("2026-04-01")
TAKER = 5e-4

_k, _f = {}, {}
def kl(s):
    if s not in _k:
        k = pd.read_parquet(U / "klines" / f"{s}.parquet")
        k["day"] = k.open_time // DAYMS
        k = k[k.day < HOLD].set_index("day")
        _k[s] = k
    return _k[s]
def fund(s):
    if s not in _f:
        p = U / "funding" / f"{s}.parquet"
        _f[s] = pd.read_parquet(p) if p.exists() else None
    return _f[s]

def slip(qv):
    if qv >= 200e6: return 3e-4
    if qv >= 50e6: return 8e-4
    if qv >= 10e6: return 15e-4
    return 30e-4

def hl_set():
    meta = json.load(open(U / "hl_meta.json"))
    names = {u["name"] for u in meta["universe"]}
    return names

def window_ret(s, e_day, x_day):
    k = kl(s)
    if e_day in k.index and x_day in k.index:
        return k.loc[x_day, "open"] / k.loc[e_day, "open"] - 1
    return np.nan

def trade(ev, k_days, m_days, stop=0.35):
    s = ev.symbol; T = int(ev.day)
    e_day, x_day = T - k_days, T + m_days
    k = kl(s)
    if e_day not in k.index:
        return None, "no_entry_bar"
    if x_day >= HOLD:
        return None, "exit_beyond_data"
    pe = k.loc[e_day, "open"]
    hist = k[(k.index >= e_day - 30) & (k.index < e_day)]
    qv = hist.quote_volume.mean() if len(hist) else 0
    sl = slip(qv)
    path = k[(k.index >= e_day) & (k.index < x_day)]
    exit_px, reason, extra, xd = None, "time", 0.0, x_day
    lim = pe * (1 + stop)
    for d, r in path.iterrows():
        if d > e_day and r.open >= lim:
            exit_px, reason, extra, xd = r.open, "stop_gap", 0.01, d; break
        if r.high >= lim:
            exit_px, reason, extra, xd = lim, "stop", 0.01, d; break
    if exit_px is None:
        if x_day in k.index:
            exit_px = k.loc[x_day, "open"]
        else:
            last = k[k.index < x_day]
            exit_px, reason, extra, xd = last.close.iloc[-1], "delisted", 0.02, int(last.index[-1]) + 1
    gross = -(exit_px / pe - 1)
    f = fund(s); fsum, fflag = 0.0, f is None
    if f is not None:
        t0, t1 = e_day * DAYMS, xd * DAYMS
        fsum = f[(f.calc_time > t0) & (f.calc_time <= t1)].last_funding_rate.sum()
        if len(f) == 0 or f.calc_time.min() > t0 + DAYMS: fflag = True
    cost = 2 * (TAKER + sl) + extra
    btc = window_ret("BTCUSDT", e_day, x_day)
    return dict(symbol=s, protocol=ev.protocol, unlock_date=ev.date, size_pct=ev.size_pct,
                team_share=ev.tok_team / ev.tok_vest, entry_date=str(pd.Timestamp(e_day * DAYMS, unit="ms").date()),
                exit_day=xd, exit_reason=reason, gross=gross, funding=fsum, funding_missing=fflag,
                cost=cost, net=gross + fsum - cost, btc_short=-btc, mkt_adj_gross=gross + btc,
                qv30=qv), "ok"

def run(events, k_days, m_days):
    out, skipped = [], {"overlap": 0}
    last_exit = {}
    for ev in events.sort_values(["day", "symbol"]).itertuples():
        e_day = int(ev.day) - k_days
        if ev.symbol in last_exit and e_day < last_exit[ev.symbol]:
            skipped["overlap"] += 1; continue
        t, why = trade(ev, k_days, m_days)
        if t is None:
            skipped[why] = skipped.get(why, 0) + 1; continue
        last_exit[ev.symbol] = t["exit_day"]
        out.append(t)
    return pd.DataFrame(out), skipped

def stats(df, col="net"):
    if len(df) == 0: return dict(n=0)
    x = df[col].values
    pos, neg = x[x > 0].sum(), -x[x < 0].sum()
    srt = np.sort(x)[::-1]
    return dict(n=int(len(x)), mean_bp=round(1e4 * x.mean(), 1), median_bp=round(1e4 * np.median(x), 1),
                pf=round(pos / neg, 3) if neg > 0 else None, sum=round(x.sum(), 4),
                sum_ex_top3=round(srt[3:].sum(), 4), win=round((x > 0).mean(), 3),
                gross_mean_bp=round(1e4 * df.gross.mean(), 1), funding_mean_bp=round(1e4 * df.funding.mean(), 1),
                cost_mean_bp=round(1e4 * df.cost.mean(), 1), btc_short_mean_bp=round(1e4 * df.btc_short.mean(), 1),
                mkt_adj_gross_mean_bp=round(1e4 * df.mkt_adj_gross.mean(), 1),
                t_net=round(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))), 2) if len(x) > 2 else None)

def passes(st):
    return st.get("n", 0) >= 50 and st["mean_bp"] > 0 and (st["pf"] or 0) > 1.2 and st["sum_ex_top3"] > 0

def load_events():
    ev = pd.read_parquet(U / "events.parquet")
    first = {s: int(kl(s).index.min()) for s in ev.symbol.unique()}
    ev = ev[ev.symbol.map(first) <= ev.day - 60]
    return ev

def by_year(df):
    if len(df) == 0: return {}
    y = df.unlock_date.str[:4]
    return {k: stats(g) for k, g in df.groupby(y)}

if __name__ == "__main__":
    mode = sys.argv[1]
    ev_all = load_events()
    thr = PRE["size_threshold_pct"]
    hl = hl_set()
    def hlname(s):
        b = s[:-4]
        for p in ("1000000", "1000", "1M"):
            if b.startswith(p): b = b[len(p):]
        return b in hl or ("k" + b) in hl
    stamp = datetime.date.today().strftime("%Y%m%d")
    if mode == "train":
        ev = ev_all[(ev_all.day <= TRAIN_END) & (ev_all.size_pct >= thr)]
        res = {}
        for c in PRE["configs"]:
            df, sk = run(ev, c["entry_days_before_unlock"], c["exit_days_after_unlock"])
            st = stats(df); st["passes_bar"] = passes(st); st["skipped"] = sk
            st["by_year"] = by_year(df)
            st["exit_reasons"] = df.exit_reason.value_counts().to_dict() if len(df) else {}
            st["hl_subset"] = stats(df[df.symbol.map(hlname)]) if len(df) else {}
            st["size_ge5"] = stats(df[df.size_pct >= 5]) if len(df) else {}
            st["team_majority"] = stats(df[df.team_share > 0.5]) if len(df) else {}
            st["funding_missing_trades"] = int(df.funding_missing.sum()) if len(df) else 0
            res[c["key"]] = st
            df.to_parquet(U / f"trades_train_{c['key']}.parquet")
            print(c["key"], {k: st.get(k) for k in ("n", "mean_bp", "median_bp", "pf", "sum_ex_top3", "gross_mean_bp", "btc_short_mean_bp", "passes_bar")})
        passing = [k for k, v in res.items() if v["passes_bar"]]
        pool = passing or list(res)
        sel = max(pool, key=lambda k: res[k]["mean_bp"])
        out = dict(hypothesis="H-UNLOCK", split="train", generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   preregistration="reports/hypotheses/unlock_preregistration.json", n_events_eligible=int(len(ev)),
                   configs=res, passing_configs=passing, selected_config=sel,
                   selection_rule=PRE["selection"], finding_type="observed (backtest on train)")
        json.dump(out, open(ROOT / f"research/observations/evidence_unlock_train_{stamp}.json", "w"), indent=1, default=str)
        print("selected", sel, "passing", passing)
    elif mode == "validation":
        key = sys.argv[2]
        flag = U / "validation_done.flag"
        if flag.exists():
            sys.exit("validation already run once: " + flag.read_text())
        c = [c for c in PRE["configs"] if c["key"] == key][0]
        ev = ev_all[(ev_all.day >= VAL_START) & (ev_all.day <= VAL_END) & (ev_all.size_pct >= thr)]
        df, sk = run(ev, c["entry_days_before_unlock"], c["exit_days_after_unlock"])
        st = stats(df); st["passes_bar"] = passes(st); st["skipped"] = sk
        st["by_year"] = by_year(df); st["exit_reasons"] = df.exit_reason.value_counts().to_dict() if len(df) else {}
        st["hl_subset"] = stats(df[df.symbol.map(hlname)]) if len(df) else {}
        st["size_ge5"] = stats(df[df.size_pct >= 5]) if len(df) else {}
        st["team_majority"] = stats(df[df.team_share > 0.5]) if len(df) else {}
        df.to_parquet(U / f"trades_validation_{key}.parquet")
        out = dict(hypothesis="H-UNLOCK", split="validation", config=key, generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   n_events_eligible=int(len(ev)), result=st, finding_type="observed (backtest on validation, run once)")
        json.dump(out, open(ROOT / f"research/observations/evidence_unlock_validation_{stamp}.json", "w"), indent=1, default=str)
        flag.write_text(f"{key} {out['generated_utc']}")
        print(json.dumps({k: st.get(k) for k in ("n", "mean_bp", "median_bp", "pf", "sum_ex_top3", "gross_mean_bp", "btc_short_mean_bp", "passes_bar", "skipped")}))
