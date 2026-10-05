"""One-time holdout of the frozen XS_L7_LO rule (reports/candidates/momentum.md).

plan  writes reports/hypotheses/momentum_holdout_plan.json (config, window, sha256 of the code). Refuses to overwrite.
run   checks the code hashes against the plan, refuses if the holdout evidence already exists (run once),
      downloads 2026-04..2026-09 monthly klines + fundingRate into data/raw/web/momentum/holdout/, runs XS_L7_LO,
      the pre-stated variants (funding excluded, settlement episodes excluded) and the equal-weight benchmark,
      and writes research/observations/evidence_momentum_holdout.json.

Window: positions from 2026-04-01; last rebalance is the latest Monday t whose week (to t+7 00:00 UTC) is
fully covered by the archive when the plan is written. On 2026-10-05 daily klines exist through 2026-10-03 and
fundingRate (monthly only) through 2026-09, so the last complete week is t = 2026-09-21 (end 2026-09-28 00:00).
"""
import hashlib, json, sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import momentum_sim as M
import momentum_fetch as F

ROOT = M.ROOT
HO = M.RAW / "holdout"
PLAN = ROOT / "reports/hypotheses/momentum_holdout_plan.json"
EVID = ROOT / "research/observations/evidence_momentum_holdout.json"
CODE = ["scripts/research/momentum_sim.py", "scripts/research/momentum_fetch.py", "scripts/research/momentum_holdout.py"]
START, END = "2026-04-01", "2026-09-28"          # END exclusive (last week t=2026-09-21 closes at END 00:00)
MONTHS = ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]
KEY = "XS_L7_LO"


def sha(p):
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def plan():
    if PLAN.exists():
        raise SystemExit(f"{PLAN} exists; the plan is frozen.")
    rec = {"hypothesis": "H-MOMENTUM XS_L7_LO one-time holdout",
           "written_at_utc": datetime.now(timezone.utc).isoformat(),
           "config": M.CFG[KEY], "frozen_rule": "reports/candidates/momentum.md (section 'Frozen rule'); universe/cost "
           "constants in scripts/research/momentum_sim.py: N_UNIV=40, TAKER=5bp, slippage tiers 2/5/10/20 bp, 2% delisting penalty",
           "window": {"positions_from": START, "positions_until_exclusive": END, "last_rebalance": "2026-09-21",
                      "why_end": "latest Monday whose full week is in the archive: daily klines through 2026-10-03, "
                                 "fundingRate monthly through 2026-09 (no daily funding files exist)"},
           "data": "data.binance.vision futures/um monthly 1d klines and fundingRate 2026-04..2026-09 (plus the train/validation cache for history)",
           "bar": "per episode: n>=50, net>0, PF>1.2, net>0 without the 3 best episodes",
           "reported_variants": ["funding excluded (ret - cost)", "settlement episodes excluded (held past the coin's last nonzero-volume day)",
                                 "equal-weight long benchmark of the same universe, same cost model"],
           "no_tuning": "run once; nothing is changed afterwards; a failure goes to reports/failures/momentum_holdout.md",
           "code_sha256": {p: sha(p) for p in CODE}}
    PLAN.write_text(json.dumps(rec, indent=1))
    print(json.dumps(rec, indent=1))


def fetch():
    old = {f.stem: f for f in (M.RAW / "klines").glob("*.parquet")}
    syms = F.current_symbols()
    cand = []
    for s in syms:
        if s in old:
            last = pd.to_datetime(pd.read_parquet(old[s], columns=["open_time"]).open_time.max(), unit="ms")
            if last < pd.Timestamp("2026-03-01"):
                continue                      # gone before the holdout
        cand.append(s)
    for kind in ("klines", "funding"):
        (HO / kind).mkdir(parents=True, exist_ok=True)

    def one(s):
        for kind in ("klines", "funding"):
            dest = HO / kind / f"{s}.parquet"
            if dest.exists():
                continue
            d = F.fetch_files(s, kind, months=MONTHS)
            if d is not None:
                d.to_parquet(dest)
        return s
    with ThreadPoolExecutor(16) as ex:
        list(ex.map(one, cand))
    return len(syms), len(cand)


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
    nsym, ncand = fetch()
    C, Q, fund = M.load(extra=[HO], last_day=str((pd.Timestamp(END) - pd.Timedelta(days=1)).date()))
    M.SPLITS["holdout"] = (pd.Timestamp(START), pd.Timestamp(END))
    E, W = M.run(M.CFG[KEY], "holdout", C, Q, fund)
    st = M.stats(E, W)
    eq = (1 + W.pnl).cumprod()
    st["compounded_maxdd"] = round(float((eq / eq.cummax() - 1).min()), 4)
    dead = {s: Q[s][Q[s] > 0].last_valid_index() for s in Q.columns}
    settled = E.apply(lambda r: dead[r.sym] is not None and dead[r.sym] < r.end - pd.Timedelta(days=1), axis=1)
    bE, bW = M.run(dict(key="BENCH_EW_LONG", family="bench", L_days=28, skip_days=0, side="long_only"), "holdout", C, Q, fund)
    q = W.groupby(W.t.dt.to_period("M")).pnl.sum().round(4)
    out = {"plan": str(PLAN.relative_to(ROOT)), "config": KEY, "run_at_utc": datetime.now(timezone.utc).isoformat(),
           "symbols_listed": nsym, "symbols_fetched": ncand, "window": rec["window"],
           "bar": bar(E.pnl), "stats": st,
           "variant_funding_excluded": bar(E.ret - E.cost),
           "variant_settlement_excluded": dict(bar(E.pnl[~settled]),
                                               settled_episodes=E[settled][["sym", "start", "pnl"]].astype(str).values.tolist()),
           "benchmark_ew_long": M.stats(bE, bW), "per_month": {str(a): b for a, b in q.items()},
           "top_episodes": E.sort_values("pnl", ascending=False).head(5)[["sym", "start", "end", "ret", "fund", "cost", "pnl"]].astype(str).values.tolist(),
           "worst_episodes": E.sort_values("pnl").head(5)[["sym", "start", "end", "ret", "fund", "cost", "pnl"]].astype(str).values.tolist()}
    E.to_parquet(M.RAW / f"episodes_holdout_{KEY}.parquet")
    W.to_parquet(M.RAW / f"weekly_holdout_{KEY}.parquet")
    EVID.write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: v for k, v in out.items() if k not in ("top_episodes", "worst_episodes")}, indent=1, default=str))


if __name__ == "__main__":
    {"plan": plan, "run": run}[sys.argv[1]]()
