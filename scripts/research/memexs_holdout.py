"""One-time holdout of the frozen H-MEMEXS rule VOLG_high_long_LS (reports/candidates/memexs.md).

plan  writes reports/hypotheses/memexs_holdout_plan.json (frozen rule, universe, window, sha256 of the code).
      Refuses to overwrite.
run   checks the code hashes against the plan, refuses if the holdout evidence exists (run once), downloads
      2026-04..2026-09 monthly 1d klines + fundingRate for the frozen meme symbols into
      data/raw/web/memexs/holdout/, merges them with the read-only train/validation cache
      (data/raw/web/momentum/{klines,funding}, <= 2026-03) for signal history, runs memexs_sim.run with the
      frozen config and the pre-declared identity-doubtful exclusion diagnostic, and writes
      research/observations/evidence_memexs_holdout.json.

Window: positions from 2026-04-01 (first rebalance Monday 2026-04-06); last rebalance 2026-09-21, whose week ends
2026-09-28 00:00 UTC. That is the latest week fully covered by the archive on 2026-10-05: fundingRate exists only
as monthly files (through 2026-09); the week from 2026-09-28 would need October funding.
"""
import hashlib, json, sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import memexs_sim as M
import momentum_fetch as F

ROOT = M.ROOT
HO = M.OUT / "holdout"
PLAN = ROOT / "reports/hypotheses/memexs_holdout_plan.json"
EVID = ROOT / "research/observations/evidence_memexs_holdout.json"
CODE = ["scripts/research/memexs_sim.py", "scripts/research/listshort_classify.py",
        "scripts/research/momentum_fetch.py", "scripts/research/memexs_holdout.py"]
START, END = "2026-04-01", "2026-09-28"     # END exclusive
MONTHS = ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]
KEY = "VOLG_high_long_LS"


def sha(p):
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def plan():
    if PLAN.exists():
        raise SystemExit(f"{PLAN} exists; the plan is frozen.")
    pre = M.PRE
    rec = {"hypothesis": "H-MEMEXS VOLG_high_long_LS one-time holdout",
           "written_at_utc": datetime.now(timezone.utc).isoformat(),
           "preregistration": "reports/hypotheses/memexs_preregistration.json",
           "config": M.CFG[KEY],
           "frozen_rule": {
               "signal": pre["signals"]["VOLG"] + " (high = long)",
               "portfolio": pre["portfolio"]["k"] + "; " + pre["portfolio"]["LS"],
               "eligibility": pre["eligibility"],
               "execution": pre["execution"],
               "costs": {k: v for k, v in pre["costs"].items() if k != "lighter_variant"},
               "constants_in_memexs_sim": dict(TAKER=M.TAKER, MIN_ADV=M.MIN_ADV, MIN_N=M.MIN_N, MIN_BARS=M.MIN_BARS)},
           "universe": {"rule": pre["universe_classification"]["source"],
                        "meme_symbols": M.MEMES,
                        "note": "Frozen list from the pre-registration (applied to the 900-symbol archive listing of "
                                "2026-10-05). The archive now also lists CTUSDT (not in that listing); it is not added "
                                "(classification would need a new CoinGecko call, and a perp new on 2026-10-05 has no bars "
                                "in the window).",
                        "look_ahead": pre["universe_classification"]["look_ahead_risk"]},
           "window": {"positions_from": START, "positions_until_exclusive": END,
                      "first_rebalance": "2026-04-06", "last_rebalance": "2026-09-21",
                      "why_end": "latest Monday whose full week is in the archive: fundingRate is monthly-only and "
                                 "published through 2026-09; week t=2026-09-28 would need October funding"},
           "data": "data.binance.vision futures/um monthly 1d klines + fundingRate 2026-04..2026-09 for the frozen meme "
                   "symbols -> data/raw/web/memexs/holdout/; history from data/raw/web/momentum/{klines,funding} read-only",
           "bar": "per coin-week leg: n>=50, net>0, PF>1.2, net>0 without the 3 best legs",
           "reported": ["independent (traded) weeks", "weekly Sharpe x sqrt52", "per month", "concentration by coin",
                        "long/short legs, funding, costs",
                        "pre-declared diagnostic: excluding identity-doubtful coins " + ", ".join(sorted(M.DOUBT))],
           "no_tuning": "run once; nothing changed afterwards; a failure goes to reports/failures/memexs_holdout.md; "
                        "a forward paper test (scripts/research/memexs_forward.py) follows regardless of the result",
           "code_sha256": {p: sha(p) for p in CODE}}
    PLAN.write_text(json.dumps(rec, indent=1, ensure_ascii=False))
    print(json.dumps(rec, indent=1, ensure_ascii=False))


def fetch():
    for kind in ("klines", "funding"):
        (HO / kind).mkdir(parents=True, exist_ok=True)

    def one(s):
        got = {}
        for kind in ("klines", "funding"):
            dest = HO / kind / f"{s}.parquet"
            if dest.exists():
                got[kind] = True; continue
            d = F.fetch_files(s, kind, months=MONTHS)
            got[kind] = d is not None
            if d is not None:
                d.to_parquet(dest)
        return s, got
    with ThreadPoolExecutor(12) as ex:
        return dict(ex.map(one, M.MEMES))


def load_merged(last_day):
    cl, qv, fund = {}, {}, {}
    for s in M.MEMES:
        parts = [pd.read_parquet(d / "klines" / f"{s}.parquet") for d in (M.RAW, HO) if (d / "klines" / f"{s}.parquet").exists()]
        if not parts:
            continue
        d = pd.concat(parts, ignore_index=True).drop_duplicates("open_time")
        d.index = pd.to_datetime(d.open_time, unit="ms").dt.normalize()
        d = d[~d.index.duplicated()].sort_index()
        cl[s], qv[s] = d.close, d.quote_volume
        fp = [pd.read_parquet(x / "funding" / f"{s}.parquet") for x in (M.RAW, HO) if (x / "funding" / f"{s}.parquet").exists()]
        if fp:
            f = pd.concat(fp, ignore_index=True).drop_duplicates("calc_time")
            t = pd.to_datetime(f.calc_time, unit="ms").dt.round("h")
            fund[s] = pd.Series(f.last_funding_rate.values, index=t).groupby(level=0).last().sort_index()
    C = pd.DataFrame(cl).sort_index()
    C = C[C.index <= pd.Timestamp(last_day)]
    full = pd.date_range(C.index.min(), C.index.max(), freq="D")
    return C.reindex(full), pd.DataFrame(qv).reindex(full), fund


def bar(p):
    p = p.sort_values(ascending=False)
    w, l = p[p > 0].sum(), -p[p < 0].sum()
    return dict(n=int(len(p)), net=round(float(p.sum()), 4), pf=round(float(w / l), 3) if l > 0 else None,
                net_minus_top3=round(float(p.iloc[3:].sum()), 4),
                passes=bool(len(p) >= 50 and p.sum() > 0 and l > 0 and w / l > 1.2 and p.iloc[3:].sum() > 0))


def run():
    rec = json.loads(PLAN.read_text())
    bad = [p for p in CODE if sha(p) != rec["code_sha256"][p]]
    if bad:
        raise SystemExit(f"code changed since the plan: {bad}; holdout refused.")
    if EVID.exists():
        raise SystemExit(f"{EVID} exists; the holdout runs once.")
    got = fetch()
    C, Q, fund = load_merged(str((pd.Timestamp(END) - pd.Timedelta(days=1)).date()))
    M.SPLITS["holdout"] = (pd.Timestamp(START), pd.Timestamp(END))
    E, W = M.run(M.CFG[KEY], "holdout", C, Q, fund)
    st = M.stats(E, W)
    E2, W2 = M.run(M.CFG[KEY], "holdout", C, Q, fund, exclude=M.DOUBT)
    st2 = M.stats(E2, W2)
    bycoin = E.groupby("sym").pnl.agg(["count", "sum"]).sort_values("sum", ascending=False)
    net = float(E.pnl.sum())
    out = {"plan": str(PLAN.relative_to(ROOT)), "config": KEY, "run_at_utc": datetime.now(timezone.utc).isoformat(),
           "symbols_with_holdout_klines": sorted(s for s, g in got.items() if g["klines"]),
           "window": rec["window"], "bar": bar(E.pnl), "stats": st,
           "per_month": {str(a): round(float(b), 4) for a, b in W.groupby(W.t.dt.to_period("M")).pnl.sum().items()},
           "per_month_weeks": {str(a): int(b) for a, b in W.groupby(W.t.dt.to_period("M")).size().items()},
           "concentration": {"by_coin_top10": bycoin.head(10).round(4).to_dict("index"),
                             "by_coin_bottom5": bycoin.tail(5).round(4).to_dict("index"),
                             "top3_coin_share_of_net": round(float(bycoin["sum"].iloc[:3].sum() / net), 3) if net > 0 else None,
                             "n_coins": int(len(bycoin))},
           "diagnostic_ex_identity_doubtful": dict(bar(E2.pnl), weekly_sharpe=st2["weekly_sharpe"],
                                                   per_year=st2["per_year"]),
           "top_legs": E.sort_values("pnl", ascending=False).head(5)[["sym", "t", "w", "ret", "fund", "cost", "pnl"]].astype(str).values.tolist(),
           "worst_legs": E.sort_values("pnl").head(5)[["sym", "t", "w", "ret", "fund", "cost", "pnl"]].astype(str).values.tolist()}
    E.to_parquet(M.OUT / f"legs_holdout_{KEY}.parquet")
    W.to_parquet(M.OUT / f"weekly_holdout_{KEY}.parquet")
    EVID.write_text(json.dumps(out, indent=1, default=str, ensure_ascii=False))
    print(json.dumps({k: v for k, v in out.items() if k != "symbols_with_holdout_klines"}, indent=1, default=str, ensure_ascii=False))


if __name__ == "__main__":
    {"plan": plan, "run": run}[sys.argv[1]]()
