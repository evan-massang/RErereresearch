"""Cross-sectional OOS test of the frozen H-HLLAG rule on new coins.

Pre-registration: reports/hypotheses/hllag_newcoins_preregistration.json. Imports the frozen
hlanchor_lib (sha256 checked, never modified). Disk is tight, so each coin-day is downloaded,
extracted to parquet in a temp dir, simulated, and the parquet deleted; only per-trade results are kept.

    python scripts/research/hllag_newcoins.py fetchrun   # downloads + sims, prints no results
    python scripts/research/hllag_newcoins.py report     # pooled stats + robustness
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import hlanchor_lib as L  # noqa: E402
from hlanchor_fetch import TRAIN, VALID, HOLDOUT_START  # noqa: E402

LIB_SHA = "98166e5f6997f4e74228beb441c769bfef925c24853d46791b0ba75670ccc3ad"
assert hashlib.sha256((Path(__file__).parent / "hlanchor_lib.py").read_bytes()).hexdigest() == LIB_SHA

PRE = json.load(open(ROOT / "reports/hypotheses/hllag_newcoins_preregistration.json"))
PARAMS = PRE["frozen_rule"]["params"]
RANKED = PRE["coin_selection_rule"]["passing_liquidity_rule_in_rank_order"]
SYM = PRE["coin_selection_rule"]["binance_symbol_map"]
EXCLUDED_PRE = {"DOGE": "size gate: 2025-10-01 DOGEUSDT book_ticker 103.8 MB > 60 MB"}
REF_DAY = "2025-10-01"
SIZE_GATE = 60e6
CAP = 1.45e9
PROBE_SPENT = 124e6  # sizing probes before pre-registration (TRUMP trades, DOGE quotes+book_ticker, TRUMP book_ticker)
MIN_FREE = 2.5e9

RAW = ROOT / "data/raw/web/tardis/newcoins_tmp"
OUT = ROOT / "data/raw/web/tardis/results/newcoins"
LOG = OUT / "fetch_log.json"


def free() -> int:
    return shutil.disk_usage("/").free


def url(exchange, dtype, day, sym):
    y, m, d = day.split("-")
    return f"https://datasets.tardis.dev/v1/{exchange}/{dtype}/{y}/{m}/{d}/{sym}.csv.gz"


def fetch(exchange, dtype, day, sym):
    assert day < HOLDOUT_START
    out = RAW / f"{exchange}_{dtype}_{day}_{sym}.csv.gz"
    r = subprocess.run(["curl", "-sS", "--max-time", "900", "-o", str(out), "-w", "%{http_code}",
                        url(exchange, dtype, day, sym)], capture_output=True, text=True)
    if r.stdout.strip() != "200":
        out.unlink(missing_ok=True)
        return None, 0, r.stdout.strip()
    return out, out.stat().st_size, "200"


def extract(raw: Path, dtype: str, dst: Path):  # identical column handling to hlanchor_fetch.process
    df = pd.read_csv(raw)
    if dtype == "book_ticker":
        df = df[["local_timestamp", "bid_price", "ask_price", "bid_amount", "ask_amount"]]
        chg = (df.bid_price.diff() != 0) | (df.ask_price.diff() != 0)
        df = df[chg]
    elif dtype == "quotes":
        df = df[["timestamp", "local_timestamp", "bid_price", "ask_price", "bid_amount", "ask_amount"]]
    elif dtype == "trades":
        df = df[["timestamp", "local_timestamp", "side", "price", "amount"]]
    df.to_parquet(dst, index=False)
    raw.unlink()


def coin_day(coin, day, log):
    """Download 3 files, simulate L=300 and L=800, keep trades. Returns bytes downloaded."""
    res_f = OUT / f"trades_{coin}_{day}.parquet"
    if res_f.exists() or f"{coin}:{day}" in log["missing"]:
        return 0
    got = 0
    files = [("hyperliquid", "quotes", coin), ("hyperliquid", "trades", coin),
             ("binance-futures", "book_ticker", SYM[coin])]
    for ex, dt, sym in files:
        dst = RAW / f"{dt}_{day}_{coin}.parquet"
        if dst.exists():
            continue
        raw, n, code = fetch(ex, dt, day, sym)
        got += n
        if raw is None:
            log["missing"][f"{coin}:{day}"] = f"{ex} {dt} {sym}: HTTP {code}"
            for p in RAW.glob(f"*_{day}_{coin}.parquet"):
                p.unlink()
            return got
        extract(raw, dt, dst)
    L.PQ = RAW  # point the frozen loader at the temp dir (module global, file unchanged)
    d = L.load_day(coin, day)
    rows = []
    for lat in (300, 800):
        kw = dict(PARAMS, L_ms=lat)
        for t in L.sim_lag(d, **kw):
            t["L_ms"] = lat
            rows.append(t)
    cols = ["coin", "day", "side", "entry_px", "exit_px", "entry_t", "exit_t", "why", "binret_bp",
            "hlret_bp", "pnl", "mk1", "mk5", "mk30", "L_ms"]
    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=cols)
    df.to_parquet(res_f, index=False)
    log["done"].append(f"{coin}:{day}")
    for p in RAW.glob(f"*_{day}_{coin}.parquet"):
        p.unlink()
    return got


def fetchrun():
    RAW.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    log = json.load(open(LOG)) if LOG.exists() else dict(
        bytes=PROBE_SPENT, done=[], missing={}, excluded=dict(EXCLUDED_PRE), ref_size={}, tested=[], cut=[])
    days = TRAIN + VALID
    for coin in RANKED:
        if coin in log["excluded"] or coin in log["tested"]:
            continue
        if free() < MIN_FREE:
            log["cut"].append(f"{coin}: free disk {free()/1e9:.2f} GB < 2.5"); break
        # size gate on the reference day's Binance book_ticker
        if coin not in log["ref_size"]:
            raw, n, code = fetch("binance-futures", "book_ticker", REF_DAY, SYM[coin])
            log["bytes"] += n
            log["ref_size"][coin] = n if raw else f"HTTP {code}"
            if raw is None:
                log["excluded"][coin] = f"reference-day book_ticker HTTP {code}"
                continue
            if n > SIZE_GATE:
                raw.unlink()
                log["excluded"][coin] = f"size gate: {REF_DAY} book_ticker {n/1e6:.1f} MB > 60 MB"
                continue
            extract(raw, "book_ticker", RAW / f"book_ticker_{REF_DAY}_{coin}.parquet")
        ref = log["ref_size"][coin]
        expected = len(days) * (ref + 6e6)
        if log["bytes"] + expected > CAP:
            log["cut"].append(f"{coin}: expected {expected/1e6:.0f} MB would exceed cap "
                              f"(spent {log['bytes']/1e6:.0f} MB)")
            for p in RAW.glob(f"*_{coin}.parquet"):
                p.unlink()
            json.dump(log, open(LOG, "w"), indent=1)
            continue
        for day in days:
            if free() < MIN_FREE:
                log["cut"].append(f"{coin}:{day}: free disk < 2.5 GB")
                json.dump(log, open(LOG, "w"), indent=1)
                return
            log["bytes"] += coin_day(coin, day, log)
            json.dump(log, open(LOG, "w"), indent=1)
            print(f"{coin} {day} spent={log['bytes']/1e6:.0f}MB free={free()/1e9:.2f}GB", flush=True)
        log["tested"].append(coin)
        json.dump(log, open(LOG, "w"), indent=1)
    print("done", json.dumps({k: log[k] for k in ("excluded", "tested", "cut")}))


def stats(df, extra_cost_usd=0.0):
    p = (df.pnl - extra_cost_usd).tolist() if len(df) else []
    return L.bar_stats(p)


def report():
    log = json.load(open(LOG))
    tested = log["tested"]
    fr = [pd.read_parquet(f) for f in sorted(OUT.glob("trades_*.parquet"))]
    tr = pd.concat([f for f in fr if len(f)], ignore_index=True)
    tr = tr[tr.coin.isin(tested)]
    out = dict(tested=tested, excluded=log["excluded"], cut=log["cut"], missing=log["missing"],
               bytes_downloaded=int(log["bytes"]), splits={})
    for split, days in (("train", TRAIN), ("validation", VALID)):
        s = tr[tr.day.isin(days)]
        base = s[s.L_ms == 300]
        cov = sorted(c for c in log["done"] if c.split(":")[1] in days and c.split(":")[0] in tested)
        r = dict(coverage=cov, pooled=stats(base),
                 pooled_plus05bp=stats(base, 0.05),
                 pooled_L800=stats(s[s.L_ms == 800]),
                 per_coin={c: stats(g) for c, g in base.groupby("coin")},
                 per_coin_L800={c: stats(g) for c, g in s[s.L_ms == 800].groupby("coin")},
                 per_day_net={d: round(float(g.pnl.sum()), 2) for d, g in base.groupby("day")})
        if len(base):
            r["markout_bp_mean"] = {h: round(float(base[h].mean()), 3) for h in ("mk1", "mk5", "mk30")}
            cd = base.groupby(["coin", "day"]).pnl.sum().sort_values()
            r["top_coin_day"] = dict(key=" ".join(cd.index[-1]), net=round(float(cd.iloc[-1]), 2))
            top = cd.index[-1]
            r["pooled_ex_top_coin_day"] = stats(base[~((base.coin == top[0]) & (base.day == top[1]))])
        out["splits"][split] = r
    out["verdict_pass"] = bool(out["splits"]["train"]["pooled"]["passes"]
                               and out["splits"]["validation"]["pooled"]["passes"])
    print(json.dumps(out, indent=1, default=str))
    json.dump(out, open(OUT / "report.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    {"fetchrun": fetchrun, "report": report}[sys.argv[1]]()
