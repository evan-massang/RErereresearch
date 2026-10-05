"""Forward paper test of the frozen H-MEMEXS rule VOLG_high_long_LS (reports/candidates/memexs.md;
holdout FAILED: reports/failures/memexs_holdout.md). Modeled on scripts/research/momentum_forward.py.

freeze  Writes reports/paper/memexs_volg.json: frozen params, universe, sha256 of memexs_sim.py (the simulator)
        and momentum_fetch.py (the archive fetcher), frozen_at, and the holdout result. Refuses to overwrite.
score   Fetches data.binance.vision files for the frozen meme symbols published after the holdout cache
        (daily 1d klines for days without a monthly file; monthly klines/fundingRate for completed months) into
        data/raw/web/memexs/forward/, runs memexs_sim.run with the frozen config on rebalances whose decision
        time t (Monday 00:00 UTC) is AFTER frozen_at and whose week is complete in the klines, and writes
        reports/paper/memexs_volg_ledger.json with the per-coin-week-leg bar. Refuses if memexs_sim.py changed.

Data notes
- fapi.binance.com returns HTTP 451 here and api.binance.com is blocked: only the data.binance.vision archive is
  used. Daily 1d klines lag about 1 day.
- fundingRate exists only as MONTHLY archive files, so funding for the current month is unknown until its file is
  published. Legs whose week runs past the last published funding month are funding_final=false (their funding is
  counted as 0 in the provisional bar). The official bar uses only funding_final legs.
- History before the forward window comes from data/raw/web/momentum/{klines,funding} (<= 2026-03, read-only) and
  data/raw/web/memexs/holdout (2026-04..2026-09).
- Universe: the frozen 74-symbol meme list. Meme perps listed later are NOT added (the classification would
  need a new CoinGecko call; adding names would change the frozen rule).
- Rate: ~32 eligible memes -> k = 6, about 12 legs a week. 50 legs need 5 complete weeks of rebalances
  (first rebalance 2026-10-12 -> week 5 ends 2026-11-16), and the official bar then waits for the November
  fundingRate file (early December 2026).

    python scripts/research/memexs_forward.py freeze
    python scripts/research/memexs_forward.py score
"""
import hashlib, json, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import memexs_sim as M
import momentum_fetch as F

ROOT = M.ROOT
HO = M.OUT / "holdout"
FWD = M.OUT / "forward"
MANIFEST = FWD / "manifest.json"
FREEZE = ROOT / "reports/paper/memexs_volg.json"
LEDGER = ROOT / "reports/paper/memexs_volg_ledger.json"
SIM = ROOT / "scripts/research/memexs_sim.py"
FETCH = ROOT / "scripts/research/momentum_fetch.py"
KEY = "VOLG_high_long_LS"
FIRST_FWD_MONTH = "2026-10"
BAR = dict(min_legs=50, net_gt=0.0, pf_gt=1.2, net_ex_top3_gt=0.0)


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def freeze():
    if FREEZE.exists():
        raise SystemExit(f"{FREEZE} exists; frozen strategies are never changed.")
    hp = ROOT / "research/observations/evidence_memexs_holdout.json"
    ho = json.loads(hp.read_text()) if hp.exists() else None
    FREEZE.parent.mkdir(parents=True, exist_ok=True)
    rec = {"name": "memexs_volg", "module": "scripts/research/memexs_sim.py", "function": "run",
           "config": M.CFG[KEY],
           "params": {"TAKER": M.TAKER, "MIN_ADV": M.MIN_ADV, "MIN_N": M.MIN_N, "MIN_BARS": M.MIN_BARS,
                      "slippage_per_side": "2/5/10/20 bp for 30d avg daily quote volume >=1e9 / 2e8-1e9 / 5e7-2e8 / <5e7",
                      "delisting_penalty": 0.02, "k": "max(2, floor(n_eligible/5))",
                      "weights": "+0.5/k top-k by VOLG, -0.5/k bottom-k",
                      "signal": "VOLG = qv(t-7..t-1) / (qv(t-35..t-8)/4)",
                      "rebalance": "Monday 00:00 UTC, fill at close(t-1), hold 7 days"},
           "universe": M.MEMES,
           "module_sha256": _sha(SIM), "fetch_sha256": _sha(FETCH), "frozen_at": time.time(),
           "frozen_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "bar": BAR,
           "unit": "per coin-week leg P&L as a fraction of strategy capital (gross 1x, dollar-neutral)",
           "holdout_passed": (bool(ho["bar"]["passes"]) if ho else None),
           "order_of_events": ("holdout run FIRST (" + ho["run_at_utc"] + ", verdict " + ("PASS" if ho["bar"]["passes"] else "FAIL")
                               + ": n=%d net=%.3f PF=%.3f net_ex_top3=%.3f), then this freeze" % (
                                   ho["bar"]["n"], ho["bar"]["net"], ho["bar"]["pf"], ho["bar"]["net_minus_top3"]))
           if ho else "freeze written before any holdout result",
           "source": "reports/candidates/memexs.md (train n=736 PF 1.28 ex-top3 +0.10; validation n=686 PF 1.25 ex-top3 +0.18; fragile)",
           "expected_rate": "about 12 legs/week; 50 legs after 5 complete weeks (~2026-11-16), official bar after the "
                            "November fundingRate file (~early December 2026)",
           "caveats": ["holdout failed (reports/failures/memexs_holdout.md)",
                       "validation was 75% one coin (PIPPIN); train depended on identity-doubtful coins",
                       "universe is today's CoinGecko meme-token list (look-ahead); later meme listings not added",
                       "fundingRate only in monthly archive files: funding finalises up to ~1 month late",
                       "fapi.binance.com returns HTTP 451 here; archive only"]}
    FREEZE.write_text(json.dumps(rec, indent=1, ensure_ascii=False))
    print(json.dumps(rec, indent=1, ensure_ascii=False))


def _published(key: str) -> bool:
    return F.get_zip_csv(key) is not None


def update_data():
    for k in ("klines", "funding"):
        (FWD / k).mkdir(parents=True, exist_ok=True)
    man = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {"kline_months": [], "kline_days": [], "fund_months": []}
    today = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
    last_full = str(today.to_period("M") - 1)
    months = [str(p) for p in pd.period_range(FIRST_FWD_MONTH, last_full, freq="M")] if last_full >= FIRST_FWD_MONTH else []
    new_k = [m for m in months if m not in man["kline_months"]
             and _published(f"data/futures/um/monthly/klines/BTCUSDT/1d/BTCUSDT-1d-{m}.zip")]
    new_f = [m for m in months if m not in man["fund_months"]
             and _published(f"data/futures/um/monthly/fundingRate/BTCUSDT/BTCUSDT-fundingRate-{m}.zip")]
    covered = set(man["kline_months"]) | set(new_k)
    days = [str(d.date()) for d in pd.date_range(f"{FIRST_FWD_MONTH}-01", today - pd.Timedelta(days=1))
            if str(d.to_period("M")) not in covered and str(d.date()) not in man["kline_days"]]
    days = [d for d in days if _published(f"data/futures/um/daily/klines/BTCUSDT/1d/BTCUSDT-1d-{d}.zip")]
    if not (new_k or new_f or days):
        return man

    def one(s):
        for kind, ms, ds in (("klines", new_k, days), ("funding", new_f, [])):
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
    with ThreadPoolExecutor(12) as ex:
        list(ex.map(one, M.MEMES))
    man["kline_months"] += new_k; man["fund_months"] += new_f; man["kline_days"] += days
    MANIFEST.write_text(json.dumps(man, indent=1))
    return man


def load_all():
    dirs = (M.RAW, HO, FWD)
    cl, qv, fund = {}, {}, {}
    for s in M.MEMES:
        parts = [pd.read_parquet(d / "klines" / f"{s}.parquet") for d in dirs if (d / "klines" / f"{s}.parquet").exists()]
        if not parts:
            continue
        d = pd.concat(parts, ignore_index=True).drop_duplicates("open_time", keep="last")
        d.index = pd.to_datetime(d.open_time, unit="ms").dt.normalize()
        d = d[~d.index.duplicated(keep="last")].sort_index()
        cl[s], qv[s] = d.close, d.quote_volume
        fp = [pd.read_parquet(x / "funding" / f"{s}.parquet") for x in dirs if (x / "funding" / f"{s}.parquet").exists()]
        if fp:
            f = pd.concat(fp, ignore_index=True).drop_duplicates("calc_time")
            t = pd.to_datetime(f.calc_time, unit="ms").dt.round("h")
            fund[s] = pd.Series(f.last_funding_rate.values, index=t).groupby(level=0).last().sort_index()
    C = pd.DataFrame(cl).sort_index()
    full = pd.date_range(C.index.min(), C.index.max(), freq="D")
    return C.reindex(full), pd.DataFrame(qv).reindex(full), fund


def _bar(p: pd.Series) -> dict:
    p = p.sort_values(ascending=False)
    w, l = float(p[p > 0].sum()), float(-p[p < 0].sum())
    out = dict(n=int(len(p)), net=round(float(p.sum()), 5), pf=round(w / l, 3) if l > 0 else None,
               net_ex_top3=round(float(p.iloc[3:].sum()), 5))
    out["passes"] = bool(out["n"] >= BAR["min_legs"] and out["net"] > 0 and l > 0 and w / l > BAR["pf_gt"]
                         and out["net_ex_top3"] > 0)
    return out


def score() -> dict:
    rec = json.loads(FREEZE.read_text())
    if _sha(SIM) != rec["module_sha256"]:
        raise SystemExit("memexs_sim.py changed since freezing; scoring refused.")
    man = update_data()
    C, Q, fund = load_all()
    ref = "DOGEUSDT"
    last_kline = C.index[C[ref].notna()].max()
    frozen = pd.Timestamp(rec["frozen_at"], unit="s")
    first_t = frozen.normalize() + pd.Timedelta(days=(7 - frozen.weekday()) % 7 or 7)   # first Monday after frozen_at
    end = last_kline + pd.Timedelta(days=1)
    n_weeks = max(0, (end - first_t).days // 7)
    fund_until = (pd.Period(max(man["fund_months"]), "M").end_time.normalize() + pd.Timedelta(days=1)
                  if man["fund_months"] else pd.Timestamp("2026-10-01"))
    out = {"name": rec["name"], "frozen_at_utc": rec["frozen_at_utc"],
           "scored_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "first_rebalance": str(first_t.date()), "last_kline_day": str(last_kline.date()),
           "funding_final_until": str(fund_until), "rebalances_scored": n_weeks, "bar_rule": rec["bar"],
           "holdout_passed": rec.get("holdout_passed")}
    if n_weeks == 0:
        out.update(status="no complete post-freeze week yet", official_bar=_bar(pd.Series(dtype=float)), legs=[])
    else:
        w_end = first_t + pd.Timedelta(days=7 * n_weeks)
        M.SPLITS["forward"] = (first_t, w_end)
        E, W = M.run(M.CFG[KEY], "forward", C[C.index < w_end], Q[Q.index < w_end], fund)
        E["week_end"] = E.t + pd.Timedelta(days=7)
        E["funding_final"] = E.week_end <= fund_until
        off = E[E.funding_final]
        out.update(status="scored", official_bar=_bar(off.pnl),
                   provisional_bar_all=_bar(E.pnl), provisional_funding_excluded=_bar(E.ret - E.cost),
                   n_funding_pending=int((~E.funding_final).sum()),
                   weekly=W.assign(t=W.t.astype(str)).round(6).to_dict("records"),
                   legs=E.assign(t=E.t.astype(str), week_end=E.week_end.astype(str)).round(6).to_dict("records"))
    LEDGER.write_text(json.dumps(out, indent=1, default=str, ensure_ascii=False))
    print(json.dumps({k: v for k, v in out.items() if k not in ("legs", "weekly")}, indent=1, default=str, ensure_ascii=False))
    return out


if __name__ == "__main__":
    {"freeze": freeze, "score": score}[sys.argv[1]]()
