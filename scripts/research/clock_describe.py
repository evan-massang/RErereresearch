"""H-CLOCK step 0 (descriptive, TRAIN ONLY): does curve / PumpSwap buy flow or price change cluster at
second-of-minute 0-5 or at quarter-hour marks?

Research only (agent "lpsell_clock", 2026-10-05). Reads data/market.duckdb READ-ONLY.
Writes research/observations/evidence_clock_describe_train.json.

Clock = on-chain block time `ts` (integer s). Train parts, by recv:
  day1 = recv < 1790882100 ; day2 = 1790899200 <= recv < 1790985600. Nothing else is read.
Curve: trusted states only (|vsol - rsol - 30| < 0.01), Mayhem mints excluded (data/processed/mayhem_flags.parquet).
Metrics per (part, venue): buy count, buy SOL, distinct buyers, sum of |log price impact|, net signed log impact
(curve: per trade log(post/pre) with pre = state before the trade; AMM: log of pre/post true-reserve price).
Normalisation: each (hour, second) cell is divided by that hour's mean per second (60 cells), then averaged across
hours; the hour-to-hour standard error is reported. Same for minute-of-hour with each hour's mean per minute.
Pre-declared decision rule (from the lead): continue only if the 0-5 s mark (or the quarter-hour minute) carries
> 1.3x its neighbours (s 54-59 and 6-11; minutes +-1..3) on BOTH train days, for buy SOL or count.
"""
from __future__ import annotations

import json
import numpy as np
import pandas as pd
import duckdb

DB = "/home/user/RErereresearch/data/market.duckdb"
MAYHEM = "/home/user/RErereresearch/data/processed/mayhem_flags.parquet"
PARTS = {"day1": "recv < 1790882100", "day2": "recv >= 1790899200 AND recv < 1790985600"}


def curve_rows(con, where):
    return con.execute(f"""
        SELECT ts, usr, buy, sol,
               CASE WHEN buy THEN ln((vsol/vtok) / ((vsol-sol)/(vtok+tok)))
                    ELSE ln((vsol/vtok) / ((vsol+sol)/(vtok-tok))) END AS lr
        FROM curve_trades
        WHERE {where} AND abs(vsol - rsol - 30) < 0.01 AND tok > 0 AND sol > 0
          AND mint NOT IN (SELECT mint FROM read_parquet('{MAYHEM}') WHERE is_mayhem)
    """).df()


def amm_rows(con, where):
    return con.execute(f"""
        SELECT ts, usr, buy, sol,
               CASE WHEN buy THEN ln(((pool_sol_logged+17.585+sol)/(pool_tok_logged-tok)) / ((pool_sol_logged+17.585)/pool_tok_logged))
                    ELSE ln(((pool_sol_logged+17.585-sol)/(pool_tok_logged+tok)) / ((pool_sol_logged+17.585)/pool_tok_logged)) END AS lr
        FROM amm_trades WHERE {where} AND tok > 0 AND sol > 0 AND pool_tok_logged > tok
    """).df()


def profile(df, unit):
    """unit 'sec' -> second-of-minute, 'min' -> minute-of-hour. Returns index table (mean, se) per metric."""
    df = df[np.isfinite(df.lr)].copy()
    df["hour"] = df.ts // 3600
    df["pos"] = (df.ts % 60) if unit == "sec" else ((df.ts // 60) % 60)
    b = df[df.buy]
    cell = pd.DataFrame({
        "buy_n": b.groupby(["hour", "pos"]).size(),
        "buy_sol": b.groupby(["hour", "pos"]).sol.sum(),
        "buyers": b.groupby(["hour", "pos"]).usr.nunique(),
        "abs_lr": df.assign(a=df.lr.abs()).groupby(["hour", "pos"]).a.sum(),
        "net_lr": df.groupby(["hour", "pos"]).lr.sum(),
    }).fillna(0.0)
    full = pd.MultiIndex.from_product([cell.index.levels[0], range(60)], names=["hour", "pos"])
    cell = cell.reindex(full, fill_value=0.0)
    # keep hours with full coverage of activity (at least 50 positions with buys) to avoid partial hours
    cov = (cell.buy_n > 0).groupby(level=0).sum()
    keep = cov[cov >= 50].index
    cell = cell.loc[keep]
    out = {}
    for m in ["buy_n", "buy_sol", "buyers", "abs_lr"]:
        x = cell[m].unstack()
        idx = x.div(x.mean(axis=1), axis=0)
        out[m] = {"mean": idx.mean().round(4).tolist(), "se": (idx.std() / np.sqrt(len(idx))).round(4).tolist()}
    # net signed price change per position (raw, average log-return sum per hour cell; x1e4 = bps)
    x = cell["net_lr"].unstack() * 1e4
    out["net_lr_bps"] = {"mean": x.mean().round(3).tolist(), "se": (x.std() / np.sqrt(len(x))).round(3).tolist()}
    out["hours"] = int(len(keep))
    return out


def mark_ratio(prof, unit):
    res = {}
    for m in ["buy_n", "buy_sol", "buyers", "abs_lr"]:
        v = np.array(prof[m]["mean"])
        if unit == "sec":
            mark = v[0:6].mean()
            nb = np.r_[v[54:60], v[6:12]].mean()
            res[m] = {"mark_0_5": round(float(mark), 4), "neigh": round(float(nb), 4), "ratio": round(float(mark / nb), 4),
                      "max_pos": int(v.argmax()), "max_val": round(float(v.max()), 4), "min_val": round(float(v.min()), 4)}
        else:
            q = [0, 15, 30, 45]
            mark = v[q].mean()
            nbi = sorted({(m0 + d) % 60 for m0 in q for d in (-3, -2, -1, 1, 2, 3)})
            nb = v[nbi].mean()
            res[m] = {"quarter": round(float(mark), 4), "neigh": round(float(nb), 4), "ratio": round(float(mark / nb), 4),
                      "max_pos": int(v.argmax()), "max_val": round(float(v.max()), 4)}
    return res


if __name__ == "__main__":
    con = duckdb.connect(DB, read_only=True)
    ev = {"note": "TRAIN ONLY descriptive; index = cell / hour mean per position; ratio>1.3 on both days required"}
    for part, where in PARTS.items():
        for venue, fn in (("curve", curve_rows), ("amm", amm_rows)):
            df = fn(con, where)
            for unit in ("sec", "min"):
                p = profile(df, unit)
                r = mark_ratio(p, unit)
                ev[f"{part}_{venue}_{unit}"] = {"n_trades": int(len(df)), "profile": p, "marks": r}
                print(part, venue, unit, "trades", len(df), "hours", p["hours"],
                      {k: (v["ratio"], v["max_pos"], v["max_val"]) for k, v in r.items()})
            del df
    # creates (curve) by second-of-minute (recv clock; no ts column on creates)
    for part, where in PARTS.items():
        c = con.execute(f"SELECT recv FROM curve_creates WHERE {where}").df()
        c["hour"] = (c.recv // 3600).astype(int)
        c["pos"] = (np.floor(c.recv) % 60).astype(int)
        x = c.groupby(["hour", "pos"]).size().unstack(fill_value=0).reindex(columns=range(60), fill_value=0)
        x = x[x.sum(axis=1) > 600]
        idx = x.div(x.mean(axis=1), axis=0).mean()
        v = idx.to_numpy()
        ratio = v[0:6].mean() / np.r_[v[54:60], v[6:12]].mean()
        ev[f"{part}_creates_sec_recv"] = {"n": int(len(c)), "index": idx.round(4).tolist(), "ratio_0_5": round(float(ratio), 4)}
        print(part, "creates sec ratio", round(float(ratio), 3), "max", int(v.argmax()), round(float(v.max()), 3))
    con.close()
    with open("/home/user/RErereresearch/research/observations/evidence_clock_describe_train.json", "w") as fh:
        json.dump(ev, fh, indent=1)
