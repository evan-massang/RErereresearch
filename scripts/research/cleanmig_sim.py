"""H-CLEANMIG simulation (agent cleanmig, 2026-10-05). READ-ONLY DB. Pre-registration:
reports/hypotheses/cleanmig_preregistration.json.

Usage:
  python cleanmig_sim.py train                       # all 12 configs on train + reference groups, kill test, selection
  python cleanmig_sim.py valid <filter> <D_s> <exit> # ONE config on validation (run once) + reference groups
"""
from __future__ import annotations

import json, sys, datetime as dt
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/RErereresearch/scripts/research")
import cleanmig_lib as C  # noqa: E402

OUT = "/home/user/RErereresearch/research/observations"
SIZE = 0.5
BASEFEE = 0.000005
EXITS = {"H4": (4 * 3600, False), "H24": (24 * 3600, False), "H4SL40": (4 * 3600, True)}
DELAYS = [1800, 7200]
FILTERS = ["base", "strict"]


def universe(c, segs):
    P = C.migrations(c)
    P = P[(P.quote_in - 84.99).abs() < 0.05].copy()
    P["seg_c"] = [C.seg_of(x, segs) if pd.notna(x) else -1 for x in P.c_recv]
    P["seg_m"] = [C.seg_of(x, segs) for x in P.t_mig]
    P["split"] = [C.split_of(x) for x in P.t_mig]
    P["mayhem"] = P.is_mayhem.fillna(False).astype(bool)
    P["f_base"] = C.filt(P, False)
    P["f_strict"] = C.filt(P, True)
    P["insider"] = P.n_curve < 20
    return P


def skip_reason(r, D, H, stop, segs):
    if r.mayhem:
        return "mayhem"
    if pd.isna(r.c_recv):
        return "no_create_event"
    if r.seg_c != r.seg_m or r.seg_m < 0:
        return "curve_history_crosses_gap"
    te, tx = r.t_mig + D + 1, r.t_mig + D + H + 1
    se, sx = C.seg_of(te, segs), C.seg_of(tx, segs)
    if se != r.seg_m:
        return "entry_in_gap_or_other_segment"
    if r.c_recv < C.HOLD_B and tx >= C.HOLD_A:
        return "lifecycle_crosses_holdout"
    if tx > segs[-1][1]:
        return "exit_past_data_end"
    if sx < 0:
        return "exit_in_gap"
    if stop and sx != se:
        return "stop_window_not_continuous"
    return None


def simulate(r, a, D, H, stop, segs):
    te, tx = r.t_mig + D + 1, r.t_mig + D + H + 1
    sege, segx = segs[C.seg_of(te, segs)], segs[C.seg_of(tx, segs)]
    st = C.state_last(a, te, sege)
    if st is None:
        return {"status": "no_pool_state_at_entry"}
    rs, rt, f, fl_e = st
    mid0 = rs / rt
    q = C.buy_tokens(rs, rt, f, SIZE)
    t_out, reason = tx, "time"
    if stop:
        rcv = a["recv"]; mid = a["rs_post"] / a["rt_post"]
        idx = np.where((rcv > te) & (rcv <= tx - 1) & (mid <= 0.6 * mid0))[0]
        if len(idx):
            t_out, reason = rcv[idx[0]] + 1, "stop"
    segx = segs[C.seg_of(t_out, segs)]
    sx = C.state_last(a, t_out, segx)
    rs2, rt2, f2, fl_x = sx
    out = C.sell_sol(rs2, rt2, f2, q)
    # conservative sensitivity
    ce = C.state_cons(a, te, "buy", sege); cx = C.state_cons(a, t_out, "sell", segx)
    qc = C.buy_tokens(ce[0], ce[1], ce[2], SIZE)
    outc = C.sell_sol(cx[0], cx[1], cx[2], qc)
    return {"status": "ok", "t_entry": te, "t_exit": t_out, "exit_reason": reason, "flag_entry": fl_e, "flag_exit": fl_x,
            "rs_entry": rs, "fee_entry_bps": f * 1e4, "fee_exit_bps": f2 * 1e4,
            "gross_mid": (rs2 / rt2) / mid0 - 1, "pnl": out - SIZE, "pnl_cons": outc - SIZE}


def stats(p, tip):
    p = np.asarray(p, float) - 2 * (tip + BASEFEE)
    n = len(p)
    if n == 0:
        return {"n": 0}
    gw, gl = p[p > 0].sum(), -p[p < 0].sum()
    s = np.sort(p)
    return {"n": n, "net": round(float(p.sum()), 4), "mean": round(float(p.mean()), 5),
            "mean_ret_pct": round(float(p.mean() / SIZE * 100), 2), "median_ret_pct": round(float(np.median(p) / SIZE * 100), 2),
            "win": round(float((p > 0).mean()), 3), "pf": round(float(gw / gl), 3) if gl > 0 else None,
            "net_ex3": round(float(s[:-3].sum()), 4) if n > 3 else None,
            "best3": [round(float(x), 4) for x in s[-3:]], "worst3": [round(float(x), 4) for x in s[:3]]}


def passes(s):
    return s.get("n", 0) >= 50 and s["net"] > 0 and (s["pf"] or 0) > 1.2 and (s["net_ex3"] or -1) > 0


def run_group(P, mask, D, ekey, segs, arrays):
    H, stop = EXITS[ekey]
    rows, skips = [], {}
    for r in P[mask].itertuples():
        why = skip_reason(r, D, H, stop, segs)
        if why:
            skips[why] = skips.get(why, 0) + 1
            continue
        a = arrays.get(r.pool)
        if a is None:
            skips["no_pool_trades"] = skips.get("no_pool_trades", 0) + 1
            continue
        res = simulate(r, a, D, H, stop, segs)
        if res["status"] != "ok":
            skips[res["status"]] = skips.get(res["status"], 0) + 1
            continue
        res.update({"pool": r.pool, "mint": r.mint, "t_mig": r.t_mig, "split": r.split})
        rows.append(res)
    return pd.DataFrame(rows), skips


def summarize(T, skips):
    if len(T) == 0:
        return {"n": 0, "skips": skips}
    s = {"main_tip0.001": stats(T.pnl, 0.001), "main_tip0.01": stats(T.pnl, 0.01),
         "cons_tip0.001": stats(T.pnl_cons, 0.001),
         "stale0_tip0.001": stats(np.where(T.flag_exit == "stale", -SIZE, T.pnl), 0.001),
         "gross_mid_mean_pct": round(float(T.gross_mid.mean() * 100), 2),
         "gross_mid_median_pct": round(float(T.gross_mid.median() * 100), 2),
         "n_stale_exit": int((T.flag_exit == "stale").sum()), "n_nextpre_exit": int((T.flag_exit == "next_pre").sum()),
         "n_stop": int((T.exit_reason == "stop").sum()),
         "rugs_le_-90pct": int((T.pnl <= -0.9 * SIZE).sum()), "losses": int((T.pnl - 2 * (0.001 + BASEFEE) < 0).sum()),
         "ret_pct_quantiles": {str(q): round(float(np.quantile(T.pnl / SIZE * 100, q)), 1) for q in (0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95)},
         "fee_entry_bps_counts": {str(int(k)): int(v) for k, v in T.fee_entry_bps.round().value_counts().items()},
         "skips": skips}
    s["passes_bar"] = passes(s["main_tip0.001"])
    return s


def by_hour(T):
    if len(T) == 0:
        return {}
    h = pd.to_datetime(T.t_entry, unit="s").dt.hour
    g = T.assign(h=h, net=T.pnl - 2 * (0.001 + BASEFEE)).groupby("h").net
    return {int(k): {"n": int(v.size), "net": round(float(v.sum()), 4), "mean_ret_pct": round(float(v.mean() / SIZE * 100), 1)}
            for k, v in g}


def main():
    mode = sys.argv[1]
    c = C.con()
    segs = C.segments(c)
    P = universe(c, segs)
    if mode == "train":
        P = P[P.split == "train"]
        tmax = C.VAL_B + 2 * 86400  # exits of Oct 2 24 h holds land on Oct 3
    else:
        P = P[P.split == "valid"]
        tmax = segs[-1][1] + 10
    df = C.load_pool_trades(c, list(P.pool), tmax)
    # offset re-check on sells (exact identity sol = R_s*tok/(R_t+tok))
    s = df[~df.buy].head(200000)
    rel = (s.rs_log + C.OFFSET) * s.tok / (s.rt + s.tok) / s.sol - 1
    offset_check = {"n_sells": int(len(s)), "abs_rel_err_p50": float(rel.abs().median()), "p90": float(rel.abs().quantile(0.9))}
    arrays = {p: C.arrays(g) for p, g in df.groupby("pool", sort=False)}
    out = {"generated_utc": dt.datetime.utcnow().isoformat(timespec="seconds"), "mode": mode,
           "prereg": "reports/hypotheses/cleanmig_preregistration.json", "offset_check": offset_check,
           "segments": [[round(a, 1), round(b, 1)] for a, b in segs],
           "universe": {"standard_migrations_in_split": int(len(P)), "mayhem": int(P.mayhem.sum()),
                        "mayhem_unknown": int(P.is_mayhem.isna().sum()), "no_create": int(P.c_recv.isna().sum()),
                        "insider_lt20_trades": int(P.insider.sum()),
                        "pass_base": int((P.f_base & ~P.mayhem).sum()), "pass_strict": int((P.f_strict & ~P.mayhem).sum())},
           "configs": {}, "reference": {}}
    if mode == "train":
        cfgs = [(f, D, e) for f in FILTERS for D in DELAYS for e in EXITS]
    else:
        cfgs = [(sys.argv[2], int(sys.argv[3]), sys.argv[4])]
    alltr = []
    for f, D, e in cfgs:
        T, sk = run_group(P, P[f"f_{f}"], D, e, segs, arrays)
        key = f"{f}_D{D // 60}m_{e}"
        out["configs"][key] = summarize(T, sk)
        out["configs"][key]["by_entry_hour_utc"] = by_hour(T)
        if len(T):
            alltr.append(T.assign(config=key))
    # descriptive references (same D / exit): unfiltered and insider graduations
    refs = [(D, e) for D in DELAYS for e in ("H4", "H24")] if mode == "train" else [(int(sys.argv[3]), sys.argv[4])]
    for D, e in refs:
        for name, m in (("unfiltered", P.n_curve >= 0), ("insider_lt20", P.insider), ("organic_ge20_failfilter", (~P.insider) & ~P.f_base)):
            T, sk = run_group(P, m, D, e, segs, arrays)
            out["reference"][f"{name}_D{D // 60}m_{e}"] = summarize(T, sk)
    if mode == "train":
        elig = {k: v for k, v in out["configs"].items() if v.get("main_tip0.001", {}).get("n", 0) >= 10}
        kill_pass = any(v["main_tip0.001"]["mean_ret_pct"] > -2.0 for v in elig.values())
        out["kill_test"] = {"configs_n_ge_10": list(elig), "means_pct": {k: v["main_tip0.001"]["mean_ret_pct"] for k, v in elig.items()},
                            "pass": kill_pass}
        if kill_pass and elig:
            best = sorted(elig.items(), key=lambda kv: (kv[1]["main_tip0.001"]["net_ex3"], kv[1]["main_tip0.001"]["n"]))[-1][0]
            out["selected"] = best
        else:
            out["selected"] = None
    tag = "train" if mode == "train" else "valid"
    path = f"{OUT}/evidence_cleanmig_{tag}_20261005.json"
    json.dump(out, open(path, "w"), indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))
    if alltr:
        pd.concat(alltr).to_csv(f"{OUT}/evidence_cleanmig_{tag}_trades_20261005.csv", index=False)
    print(path)


if __name__ == "__main__":
    main()
