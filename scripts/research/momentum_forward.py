"""Forward paper test of the frozen XS_L7_LO momentum rule (reports/candidates/momentum.md).

freeze  Writes reports/paper/momentum_xs_l7_lo.json: frozen params, sha256 of momentum_sim.py (the simulator)
        and momentum_fetch.py, frozen_at. Refuses to overwrite.
score   Fetches data.binance.vision files published after the holdout cache (daily 1d klines for days without a
        monthly file yet; monthly klines/fundingRate for completed months), runs momentum_sim.run with the frozen
        config on rebalances whose decision time t (Monday 00:00 UTC) is AFTER frozen_at and whose week is
        complete in the klines, and writes reports/paper/momentum_xs_l7_lo_ledger.json with the per-episode bar.
        Refuses if momentum_sim.py changed.

Data notes
- fapi.binance.com public klines/fundingRate return HTTP 451 (restricted location) from this container
  (checked 2026-10-05); api.binance.com is blocked. Only the data.binance.vision archive is used.
- The archive has daily 1d klines (about 1 day lag) but fundingRate only as MONTHLY files. Funding for the
  current month is therefore unknown until the month's file is published: episodes whose holding period goes
  past the last published funding month are marked funding_final=false (their funding is missing, counted as
  0 in the provisional bar). The official bar uses only closed episodes with funding_final=true.
- An episode still held at the last scored rebalance is 'open' (marked to market incl. an exit cost) and is
  not counted in the bar.
- About 8 coins per week and median episode length 1 week: >= 50 closed episodes takes ~4-7 weeks of
  rebalances, plus up to a month for the funding file.

    python scripts/research/momentum_forward.py freeze
    python scripts/research/momentum_forward.py score
"""
import hashlib, json, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import momentum_sim as M
import momentum_fetch as F

ROOT = M.ROOT
HO = M.RAW / "holdout"            # 2026-04..2026-09 monthly cache written by momentum_holdout.py
FWD = M.RAW / "forward"
MANIFEST = FWD / "manifest.json"
FREEZE = ROOT / "reports/paper/momentum_xs_l7_lo.json"
LEDGER = ROOT / "reports/paper/momentum_xs_l7_lo_ledger.json"
SIM = ROOT / "scripts/research/momentum_sim.py"
FETCH = ROOT / "scripts/research/momentum_fetch.py"
KEY = "XS_L7_LO"
FIRST_FWD_MONTH = "2026-10"       # first month not in the holdout cache
BAR = dict(min_trades=50, net_gt=0.0, pf_gt=1.2, net_ex_top3_gt=0.0)


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def freeze():
    if FREEZE.exists():
        raise SystemExit(f"{FREEZE} exists; frozen strategies are never changed.")
    holdout = ROOT / "research/observations/evidence_momentum_holdout.json"
    ho = json.loads(holdout.read_text()) if holdout.exists() else None
    FREEZE.parent.mkdir(parents=True, exist_ok=True)
    rec = {"name": "momentum_xs_l7_lo", "module": "scripts/research/momentum_sim.py", "function": "run",
           "config": M.CFG[KEY],
           "params": {"N_UNIV": M.N_UNIV, "TAKER": M.TAKER, "slippage_per_side": "2/5/10/20 bp for 30d avg daily quote "
                      "volume >=1e9 / 2e8-1e9 / 5e7-2e8 / <5e7", "delisting_penalty": 0.02, "excluded": sorted(M.EXCL),
                      "stable_bases": list(M.STABLE_BASES), "rebalance": "Monday 00:00 UTC, fill at close(t-1), hold 7 days"},
           "module_sha256": _sha(SIM), "fetch_sha256": _sha(FETCH), "frozen_at": time.time(),
           "frozen_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "bar": BAR,
           "unit": "per-episode P&L as a fraction of strategy capital (gross 1x long, 1/8 per coin)",
           "order_of_events": ("holdout run FIRST (" + ho["run_at_utc"] + ", verdict " + ("PASS" if ho["bar"]["passes"] else "FAIL")
                               + ": n=%d net=%.3f PF=%.3f net_ex_top3=%.3f), then this freeze" % (
                                   ho["bar"]["n"], ho["bar"]["net"], ho["bar"]["pf"], ho["bar"]["net_minus_top3"]))
           if ho else "freeze written before any holdout result",
           "source": "reports/candidates/momentum.md (train n=1189 PF 1.29; validation n=560 PF 1.38 net_ex_top3 +0.33; fragile)",
           "caveats": ["validation pass depended on squeeze/settlement episodes and negative-funding receipts",
                       "holdout failed (reports/failures/momentum_holdout.md)",
                       "fundingRate only in monthly archive files: funding finalises up to ~1 month late",
                       "fapi.binance.com returns HTTP 451 here; archive only"]}
    FREEZE.write_text(json.dumps(rec, indent=1))
    print(json.dumps(rec, indent=1))


def _months_between(a: str, b: str):
    return [str(p) for p in pd.period_range(a, b, freq="M")]


def _published(key: str) -> bool:
    return F.get_zip_csv(key) is not None


def update_data():
    """Incremental fetch into data/raw/web/momentum/forward/{klines,funding}/<SYM>.parquet."""
    for k in ("klines", "funding"):
        (FWD / k).mkdir(parents=True, exist_ok=True)
    man = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {"kline_months": [], "kline_days": [], "fund_months": []}
    today = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
    last_full_month = str((today.to_period("M") - 1))
    months = _months_between(FIRST_FWD_MONTH, last_full_month) if last_full_month >= FIRST_FWD_MONTH else []
    new_kmonths = [m for m in months if m not in man["kline_months"]
                   and _published(f"data/futures/um/monthly/klines/BTCUSDT/1d/BTCUSDT-1d-{m}.zip")]
    new_fmonths = [m for m in months if m not in man["fund_months"]
                   and _published(f"data/futures/um/monthly/fundingRate/BTCUSDT/BTCUSDT-fundingRate-{m}.zip")]
    covered = set(man["kline_months"]) | set(new_kmonths)
    days = [str(d.date()) for d in pd.date_range(f"{FIRST_FWD_MONTH}-01", today - pd.Timedelta(days=1))
            if str(d.to_period("M")) not in covered and str(d.date()) not in man["kline_days"]]
    days = [d for d in days if _published(f"data/futures/um/daily/klines/BTCUSDT/1d/BTCUSDT-1d-{d}.zip")]
    if not (new_kmonths or new_fmonths or days):
        return man
    syms = F.current_symbols()
    active = {f.stem for f in (HO / "klines").glob("*.parquet")}
    old = {f.stem for f in (M.RAW / "klines").glob("*.parquet")}
    syms = [s for s in syms if s in active or s not in old]     # drop symbols already gone before 2026-04

    def one(s):
        for kind, ms, ds in (("klines", new_kmonths, days), ("funding", new_fmonths, [])):
            if not (ms or ds):
                continue
            d = F.fetch_files(s, kind, months=ms, days=ds)
            if d is None:
                continue
            p = FWD / kind / f"{s}.parquet"
            if p.exists():
                d = pd.concat([pd.read_parquet(p), d], ignore_index=True)
            col = "open_time" if kind == "klines" else "calc_time"
            d.drop_duplicates(col, keep="last").sort_values(col).reset_index(drop=True).to_parquet(p)
    with ThreadPoolExecutor(16) as ex:
        list(ex.map(one, syms))
    man["kline_months"] += new_kmonths
    man["fund_months"] += new_fmonths
    man["kline_days"] += days
    MANIFEST.write_text(json.dumps(man, indent=1))
    return man


def _bar(p: pd.Series) -> dict:
    p = p.sort_values(ascending=False)
    w, l = float(p[p > 0].sum()), float(-p[p < 0].sum())
    out = dict(n=int(len(p)), net=round(float(p.sum()), 5), pf=round(w / l, 3) if l > 0 else None,
               net_ex_top3=round(float(p.iloc[3:].sum()), 5))
    out["passes"] = bool(out["n"] >= BAR["min_trades"] and out["net"] > 0 and l > 0 and w / l > BAR["pf_gt"]
                         and out["net_ex_top3"] > 0)
    return out


def score() -> dict:
    rec = json.loads(FREEZE.read_text())
    if _sha(SIM) != rec["module_sha256"]:
        raise SystemExit("momentum_sim.py changed since freezing; scoring refused.")
    man = update_data()
    C, Q, fund = M.load(extra=[HO, FWD], last_day="2100-01-01")
    last_kline = C.index[C["BTCUSDT"].notna()].max()
    frozen = pd.Timestamp(rec["frozen_at"], unit="s")
    first_t = (frozen.normalize() + pd.Timedelta(days=(7 - frozen.weekday()) % 7 or 7))   # first Monday after frozen_at
    # last complete week: t + 7 days <= last kline day + 1
    end = last_kline + pd.Timedelta(days=1)
    n_weeks = max(0, (end - first_t).days // 7)
    fund_until = (pd.Period(max(man["fund_months"]), "M").end_time.normalize() + pd.Timedelta(days=1)
                  if man["fund_months"] else pd.Timestamp("2026-10-01"))
    out = {"name": rec["name"], "frozen_at_utc": rec["frozen_at_utc"],
           "scored_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "first_rebalance": str(first_t.date()), "last_kline_day": str(last_kline.date()),
           "funding_final_until": str(fund_until), "rebalances_scored": n_weeks, "bar_rule": rec["bar"]}
    if n_weeks == 0:
        out.update(status="no complete post-freeze week yet", official_bar=_bar(pd.Series(dtype=float)), episodes=[])
    else:
        w_end = first_t + pd.Timedelta(days=7 * n_weeks)
        M.SPLITS["forward"] = (first_t, w_end)
        E, W = M.run(M.CFG[KEY], "forward", C, Q, fund)
        E["closed"] = E.end < w_end
        E["funding_final"] = E.end <= fund_until
        off = E[E.closed & E.funding_final]
        out.update(status="scored",
                   official_bar=_bar(off.pnl),
                   provisional_bar_all_closed=_bar(E[E.closed].pnl),
                   provisional_funding_excluded=_bar((E.ret - E.cost)[E.closed]),
                   n_open=int((~E.closed).sum()), n_funding_pending=int((E.closed & ~E.funding_final).sum()),
                   weekly=W.assign(t=W.t.astype(str)).round(6).to_dict("records"),
                   episodes=E.assign(start=E.start.astype(str), end=E.end.astype(str)).round(6).to_dict("records"))
    LEDGER.write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: v for k, v in out.items() if k not in ("episodes", "weekly")}, indent=1, default=str))
    return out


if __name__ == "__main__":
    {"freeze": freeze, "score": score}[sys.argv[1]]()
