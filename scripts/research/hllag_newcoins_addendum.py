"""Addendum to the H-HLLAG new-coins test: PENGU, kSHIB (stage A), DOGE, kPEPE (stage B).

Pre-registration: reports/hypotheses/hllag_newcoins_addendum.json (parent:
reports/hypotheses/hllag_newcoins_preregistration.json). Same frozen hlanchor_lib.sim_lag
(sha256 asserted by importing hllag_newcoins), same params, days and bar.

Disk: one coin-day at a time; each raw csv.gz is read in chunks, reduced to the same columns and
Binance change-dedup as hllag_newcoins.extract (dedup carries the previous row across chunk
boundaries, so the output is identical to a whole-file read), raw deleted, simulated, parquet deleted.
Free disk must stay > 2.5 GB, checked (with the file's Content-Length) before every download.

    python scripts/research/hllag_newcoins_addendum.py fetchrun A   # PENGU, kSHIB
    python scripts/research/hllag_newcoins_addendum.py fetchrun B   # DOGE, kPEPE
    python scripts/research/hllag_newcoins_addendum.py report
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import hllag_newcoins as N  # noqa: E402  (asserts the frozen lib sha256)

L = N.L
ADD = json.load(open(N.ROOT / "reports/hypotheses/hllag_newcoins_addendum.json"))
STAGES = {k: v["coins"] for k, v in ADD["stages"].items()}
SYM = dict(N.SYM, DOGE="DOGEUSDT")
PARAMS = N.PARAMS
RAW = N.RAW
OUT = N.ROOT / "data/raw/web/tardis/results/newcoins_addendum"
LOG = OUT / "fetch_log.json"
CHUNK = 2_000_000
COLS = {"book_ticker": ["local_timestamp", "bid_price", "ask_price", "bid_amount", "ask_amount"],
        "quotes": ["timestamp", "local_timestamp", "bid_price", "ask_price", "bid_amount", "ask_amount"],
        "trades": ["timestamp", "local_timestamp", "side", "price", "amount"]}


def content_length(u: str) -> int | None:
    r = subprocess.run(["curl", "-sSI", "--max-time", "60", u], capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if line.lower().startswith("content-length:"):
            return int(line.split(":")[1])
    return None


def extract_chunked(raw: Path, dtype: str, dst: Path) -> int:
    parts, prev = [], None
    for ch in pd.read_csv(raw, usecols=COLS[dtype], chunksize=CHUNK):
        ch = ch[COLS[dtype]]
        if dtype == "book_ticker":
            bd, ad = ch.bid_price.diff(), ch.ask_price.diff()
            if prev is not None:
                bd.iloc[0] = ch.bid_price.iloc[0] - prev[0]
                ad.iloc[0] = ch.ask_price.iloc[0] - prev[1]
            prev = (ch.bid_price.iloc[-1], ch.ask_price.iloc[-1])
            ch = ch[(bd != 0) | (ad != 0)]
        parts.append(ch)
    df = pd.concat(parts, ignore_index=True)
    df.to_parquet(dst, index=False)
    raw.unlink()
    return len(df)


def coin_day(coin, day, log) -> str:
    res_f = OUT / f"trades_{coin}_{day}.parquet"
    key = f"{coin}:{day}"
    if res_f.exists() or key in log["missing"]:
        return "skip"
    files = [("hyperliquid", "quotes", coin), ("hyperliquid", "trades", coin),
             ("binance-futures", "book_ticker", SYM[coin])]
    for ex, dt, sym in files:
        dst = RAW / f"{dt}_{day}_{coin}.parquet"
        if dst.exists():
            continue
        u = N.url(ex, dt, day, sym)
        cl = content_length(u)
        if cl is not None and N.free() - 1.3 * cl < N.MIN_FREE:
            return f"disk: free {N.free()/1e9:.2f} GB, next file {cl/1e6:.0f} MB"
        raw, n, code = N.fetch(ex, dt, day, sym)
        log["bytes"] += n
        if raw is None:
            log["missing"][key] = f"{ex} {dt} {sym}: HTTP {code}"
            for p in RAW.glob(f"*_{day}_{coin}.parquet"):
                p.unlink()
            return "missing"
        log["min_free_gb"] = min(log.get("min_free_gb", 99), round(N.free() / 1e9, 2))
        extract_chunked(raw, dt, dst)
    L.PQ = RAW
    d = L.load_day(coin, day)
    rows = []
    for lat in (300, 800):
        for t in L.sim_lag(d, **dict(PARAMS, L_ms=lat)):
            t["L_ms"] = lat
            rows.append(t)
    cols = ["coin", "day", "side", "entry_px", "exit_px", "entry_t", "exit_t", "why", "binret_bp",
            "hlret_bp", "pnl", "mk1", "mk5", "mk30", "L_ms"]
    pd.DataFrame(rows if rows else None, columns=None if rows else cols).to_parquet(res_f, index=False)
    log["done"].append(key)
    for p in RAW.glob(f"*_{day}_{coin}.parquet"):
        p.unlink()
    return "done"


def fetchrun(stage):
    RAW.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    for p in RAW.glob("*"):
        p.unlink()
    log = json.load(open(LOG)) if LOG.exists() else dict(bytes=0, done=[], missing={}, tested=[], cut={})
    for coin in STAGES[stage]:
        if coin in log["tested"]:
            continue
        ok = True
        for day in N.TRAIN + N.VALID:
            st = coin_day(coin, day, log)
            json.dump(log, open(LOG, "w"), indent=1)
            print(f"{coin} {day} {st} dl={log['bytes']/1e6:.0f}MB free={N.free()/1e9:.2f}GB", flush=True)
            if st.startswith("disk"):
                log["cut"][coin] = f"{day}: {st}"
                ok = False
                break
        if ok:
            log["tested"].append(coin)
            log["cut"].pop(coin, None)
        json.dump(log, open(LOG, "w"), indent=1)
        if not ok:
            break
    for p in RAW.glob("*"):
        p.unlink()
    print("done", json.dumps({k: log[k] for k in ("tested", "cut")}))


def block(tr, days):
    s = tr[tr.day.isin(days)]
    base = s[s.L_ms == 300]
    r = dict(base=N.stats(base), plus05bp=N.stats(base, 0.05), L800=N.stats(s[s.L_ms == 800]),
             coin_days_with_trades=int(base.groupby(["coin", "day"]).ngroups))
    if len(base):
        r["markout_bp_mean"] = {h: round(float(base[h].mean()), 2) for h in ("mk1", "mk5", "mk30")}
        cd = base.groupby(["coin", "day"]).pnl.sum().sort_values()
        top = cd.index[-1]
        r["top_coin_day"] = dict(key=" ".join(top), net=round(float(cd.iloc[-1]), 2))
        r["ex_top_coin_day"] = N.stats(base[~((base.coin == top[0]) & (base.day == top[1]))])
        r["per_day_net"] = {f"{c} {d}": round(float(v), 2) for (c, d), v in
                            base.groupby(["coin", "day"]).pnl.sum().items()}
    return r


def load(dirp, coins):
    fr = [pd.read_parquet(f) for f in sorted(dirp.glob("trades_*.parquet"))]
    fr = [f for f in fr if len(f)]
    if not fr:
        return pd.DataFrame(columns=["coin", "day", "pnl", "L_ms"])
    t = pd.concat(fr, ignore_index=True)
    return t[t.coin.isin(coins)]


def report():
    log = json.load(open(LOG))
    tested = log["tested"]
    tr = load(OUT, tested)
    parent_log = json.load(open(N.LOG))
    parent_tested = [c for c in ("TRUMP", "SPX") if c in parent_log["tested"]]
    par = load(N.OUT, parent_tested)
    out = dict(tested=tested, cut=log["cut"], missing=log["missing"], done=log["done"],
               bytes_downloaded=int(log["bytes"]), min_free_gb=log.get("min_free_gb"),
               per_coin={}, groups={})
    splits = (("train", N.TRAIN), ("validation", N.VALID))
    for c in tested:
        g = tr[tr.coin == c]
        out["per_coin"][c] = {sp: block(g, ds) for sp, ds in splits}
        out["per_coin"][c]["passes_both"] = bool(all(out["per_coin"][c][sp]["base"]["passes"]
                                                     for sp, _ in splits))
    groups = {"A_PENGU_kSHIB": [c for c in STAGES["A"] if c in tested],
              "B_DOGE_kPEPE": [c for c in STAGES["B"] if c in tested]}
    for name, cs in groups.items():
        if cs:
            g = tr[tr.coin.isin(cs)]
            out["groups"][name] = dict(coins=cs, **{sp: block(g, ds) for sp, ds in splits})
            out["groups"][name]["passes_both"] = bool(all(out["groups"][name][sp]["base"]["passes"]
                                                          for sp, _ in splits))
    allc = pd.concat([par, tr], ignore_index=True)
    out["groups"]["all_new_coins_informational"] = dict(
        coins=parent_tested + tested, **{sp: block(allc, ds) for sp, ds in splits})
    print(json.dumps(out, indent=1, default=str))
    json.dump(out, open(OUT / "report.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    if sys.argv[1] == "fetchrun":
        fetchrun(sys.argv[2])
    else:
        report()
