"""H-DELIST step 4: simulate the 12 pre-registered configs (reports/hypotheses/delist_preregistration.json).

Usage: python scripts/research/delist_sim.py train            -> all 12 configs on train, writes evidence + picks config
       python scripts/research/delist_sim.py validation <key> -> the chosen config on validation (run once)
Never reads prices >= 2026-04-01 (the 1h cache holds months <= 2026-03 only, and validation events whose
planned exit is after 2026-03-31 23:00 are dropped).
"""
import json, sys, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data/raw/web/delist"
PRE = json.loads((ROOT / "reports/hypotheses/delist_preregistration.json").read_text())
FUND = ROOT / "data/raw/web/momentum/funding"
H = 3600000
TRAIN_END = pd.Timestamp("2025-07-01", tz="UTC").value // 10**6
VAL_END = pd.Timestamp("2026-04-01", tz="UTC").value // 10**6
LAST_BAR_OK = pd.Timestamp("2026-03-31 23:00", tz="UTC").value // 10**6
_k, _f = {}, {}


def kl(s):
    if s not in _k:
        p = D / "klines1h" / f"{s}.parquet"
        _k[s] = pd.read_parquet(p).set_index("open_time") if p.exists() else None
    return _k[s]


def fund(s):
    if s not in _f:
        p = FUND / f"{s}.parquet"
        _f[s] = pd.read_parquet(p) if p.exists() else None
    return _f[s]


def tier(adv):
    return 3 if adv >= 200e6 else 8 if adv >= 50e6 else 15 if adv >= 10e6 else 30


def fsum(s, t0, t1, scale=None):
    f = fund(s)
    if f is None:
        return 0.0, True
    w = f[(f.calc_time > t0) & (f.calc_time <= t1)]
    return float(w.last_funding_rate.sum()), False


def simulate(p, cfg):
    tok = p["perp"]; k = kl(tok)
    if k is None:
        return None, "no_1h_data"
    entry_t = ((p["ann_ms"] + cfg["entry_delay_hours"] * H + H - 1) // H) * H
    real = k[k.volume > 0]
    if entry_t not in real.index:
        return None, "no_bar_at_entry"
    last_real = int(real.index.max())
    planned = entry_t + cfg["hold_days"] * 24 * H
    if p["ann_ms"] >= TRAIN_END and planned > LAST_BAR_OK:
        return None, "dropped_holdout_boundary"
    # the 1h cache covers through announcement + 16 d (>= any planned exit), so a last real (volume>0) bar
    # before the planned exit means the perp stopped trading (delisting/settlement) inside the window.
    pre_settle = last_real - 24 * H if last_real < planned else None
    exit_t, reason = planned, "time"
    if pre_settle is not None and pre_settle < planned:
        if pre_settle <= entry_t:
            return None, "perp_settles_before_entry+24h"
        exit_t, reason = pre_settle, "pre_settlement"
    pe = float(k.at[entry_t, "open"])
    stop_px = pe * (1 + cfg["stop_adverse_pct"] / 100)
    win = k.loc[entry_t:exit_t - H]
    stop_bar, px_exit_tok = None, None
    hit = win[win.high >= stop_px]
    if len(hit):
        stop_bar = int(hit.index[0]); o = float(hit.iloc[0].open)
        px_exit_tok = max(o, stop_px); reason = "stop"
    if stop_bar is None:
        if exit_t not in k.index:
            return None, "no_bar_at_exit"
        px_exit_tok = float(k.at[exit_t, "open"])
    # basket
    members = []
    for s in p["basket_top60"]:
        b = kl(s)
        if b is not None and entry_t in b.index and b.at[entry_t, "volume"] > 0:
            members.append(s)
        if len(members) == 50:
            break
    if len(members) < 40:
        return None, "basket_too_small"
    brets, bfund, bslip, missing_exit = [], [], [], 0
    t_close = stop_bar if stop_bar is not None else exit_t
    for s in members:
        b = kl(s); e0 = float(b.at[entry_t, "open"])
        if stop_bar is not None:
            x = float(b.at[stop_bar, "close"]) if stop_bar in b.index else None
        else:
            x = float(b.at[exit_t, "open"]) if exit_t in b.index else None
        if x is None:
            w = b.loc[:t_close]; x = float(w.close.iloc[-1]); missing_exit += 1
        brets.append(x / e0 - 1)
        fs, _ = fsum(s, entry_t, t_close + (H if stop_bar is not None else 0)); bfund.append(fs)
        bslip.append(tier(p["basket_adv"][s]))
    tok_ret = px_exit_tok / pe - 1
    tfund, tmiss = fsum(tok, entry_t, t_close + (H if stop_bar is not None else 0))
    tslip = tier(p["token_adv30"])
    taker = PRE["costs"]["taker_bp_per_side_per_leg"]
    cost_tok = 2 * (taker + tslip) / 1e4 + (0.01 if reason == "stop" else 0)
    cost_bsk = 2 * (taker + float(np.mean(bslip))) / 1e4
    bret, bf = float(np.mean(brets)), float(np.mean(bfund))
    gross_pair = -tok_ret + bret
    fund_pair = tfund - bf
    net = gross_pair + fund_pair - cost_tok - cost_bsk
    net_unhedged = -tok_ret + tfund - cost_tok
    return {"token": p["token"], "perp": tok, "type": p["type"], "ann_utc": p["ann_utc"], "ann_ms": p["ann_ms"],
            "entry_utc": pd.Timestamp(entry_t, unit="ms", tz="UTC").isoformat(),
            "exit_utc": pd.Timestamp(t_close + (H if stop_bar is not None else 0), unit="ms", tz="UTC").isoformat(),
            "exit_reason": reason, "tok_ret": tok_ret, "basket_ret": bret, "gross": gross_pair, "funding": fund_pair,
            "cost": cost_tok + cost_bsk, "net": net, "net_unhedged": net_unhedged, "tok_funding": tfund,
            "token_adv30_musd": p["token_adv30"] / 1e6, "n_basket": len(members), "basket_missing_exit": missing_exit,
            "funding_missing": tmiss, "exit_ms": t_close + (H if stop_bar is not None else 0)}, None


def run(split, cfg, plan):
    trades, skipped, last_exit = [], {}, {}
    for p in sorted(plan, key=lambda x: x["ann_ms"]):
        insplit = p["ann_ms"] < TRAIN_END if split == "train" else TRAIN_END <= p["ann_ms"] < VAL_END
        if not insplit:
            continue
        if p["token"] in last_exit and p["ann_ms"] + cfg["entry_delay_hours"] * H < last_exit[p["token"]]:
            skipped["overlap"] = skipped.get("overlap", 0) + 1; continue
        t, why = simulate(p, cfg)
        if t is None:
            skipped[why] = skipped.get(why, 0) + 1; continue
        trades.append(t); last_exit[p["token"]] = t["exit_ms"]
    return trades, skipped


def stats(tr, col="net"):
    if not tr:
        return {"n": 0}
    x = np.array([t[col] for t in tr])
    pos, neg = x[x > 0].sum(), -x[x < 0].sum()
    srt = np.sort(x)[::-1]
    return {"n": len(x), "n_announcements": len({t["ann_ms"] for t in tr}), "mean_bp": round(x.mean() * 1e4, 1),
            "median_bp": round(float(np.median(x)) * 1e4, 1), "pf": round(pos / neg, 3) if neg > 0 else None,
            "sum": round(x.sum(), 4), "sum_ex_top3": round(srt[3:].sum(), 4), "win": round((x > 0).mean(), 3),
            "t": round(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))), 2) if len(x) > 2 else None,
            "worst_bp": round(x.min() * 1e4, 1), "best_bp": round(x.max() * 1e4, 1)}


def summary(tr, sk):
    st = stats(tr)
    if tr:
        st.update({"gross_mean_bp": round(np.mean([t["gross"] for t in tr]) * 1e4, 1),
                   "funding_mean_bp": round(np.mean([t["funding"] for t in tr]) * 1e4, 1),
                   "cost_mean_bp": round(np.mean([t["cost"] for t in tr]) * 1e4, 1),
                   "tok_ret_mean_bp": round(np.mean([t["tok_ret"] for t in tr]) * 1e4, 1),
                   "basket_ret_mean_bp": round(np.mean([t["basket_ret"] for t in tr]) * 1e4, 1)})
    b = PRE["bar_per_split"]
    st["passes_bar"] = bool(st["n"] >= b["n_min"] and st["mean_bp"] > 0 and (st["pf"] or 0) > b["profit_factor_gt"] and st["sum_ex_top3"] > 0) if tr else False
    st["unhedged_informational"] = stats(tr, "net_unhedged")
    st["by_type"] = {ty: stats([t for t in tr if t["type"] == ty]) for ty in ("delist", "monitor")}
    st["by_year"] = {y: stats([t for t in tr if t["ann_utc"][:4] == y]) for y in sorted({t["ann_utc"][:4] for t in tr})}
    st["exit_reasons"] = pd.Series([t["exit_reason"] for t in tr]).value_counts().to_dict() if tr else {}
    st["skipped"] = sk
    return st


def main():
    plan = json.loads((D / "plan.json").read_text())
    split = sys.argv[1]
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d")
    cfgs = {c["key"]: c for c in PRE["configs"]}
    if split == "train":
        res = {}
        for key, c in cfgs.items():
            tr, sk = run("train", c, plan)
            res[key] = (summary(tr, sk), tr)
        passing = [k for k, (s, _) in res.items() if s["passes_bar"]]
        if passing:
            chosen = max(passing, key=lambda k: res[k][0]["sum_ex_top3"]); rule = "highest net_sum_without_top3 among passing"
        else:
            chosen = max(res, key=lambda k: res[k][0]["pf"] or 0); rule = "no config passed; highest PF chosen (verdict FAIL at train)"
        out = {"hypothesis": "H-DELIST", "split": "train", "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
               "preregistration": "reports/hypotheses/delist_preregistration.json", "modality": "document",
               "finding_type": "observed (backtest on train, 12 pre-registered configs)",
               "configs": {k: s for k, (s, _) in res.items()}, "chosen": chosen, "chosen_rule": rule,
               "chosen_trades": res[chosen][1]}
        json.dump(out, open(ROOT / f"research/observations/evidence_delist_train_{stamp}.json", "w"), indent=1, default=str)
        for k, (s, _) in res.items():
            print(k, {x: s.get(x) for x in ("n", "n_announcements", "mean_bp", "median_bp", "pf", "sum_ex_top3", "gross_mean_bp", "funding_mean_bp", "cost_mean_bp", "passes_bar")},
                  "unhedged", {x: s["unhedged_informational"].get(x) for x in ("mean_bp", "pf")}, s["exit_reasons"], s["skipped"])
        print("CHOSEN", chosen, rule)
    else:
        key = sys.argv[2]
        marker = D / "VALIDATION_RUN_ONCE"
        if marker.exists():
            sys.exit("validation already run: " + marker.read_text())
        marker.write_text(f"{key} {dt.datetime.now(dt.timezone.utc).isoformat()}")
        tr, sk = run("validation", cfgs[key], plan)
        s = summary(tr, sk)
        out = {"hypothesis": "H-DELIST", "split": "validation", "config": key, "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
               "preregistration": "reports/hypotheses/delist_preregistration.json", "modality": "document",
               "finding_type": "observed (backtest on validation, run once)", "result": s, "trades": tr}
        json.dump(out, open(ROOT / f"research/observations/evidence_delist_validation_{stamp}.json", "w"), indent=1, default=str)
        print(json.dumps({k: v for k, v in s.items() if k not in ("by_year",)}, indent=1, default=str))


if __name__ == "__main__":
    main()
