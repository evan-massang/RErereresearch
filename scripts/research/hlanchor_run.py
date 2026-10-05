"""Run H-HLANCHOR and H-HLLAG configs on a split. Usage: python hlanchor_run.py train|valid [cfg ...]"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import hlanchor_lib as L  # noqa: E402
from hlanchor_fetch import COINS, TRAIN, VALID  # noqa: E402

# pre-registered configs (14 total)
CONFIGS = {}
for k in (10, 15, 20):
    for T in (10, 30):
        CONFIGS[f"anchor_k{k}_T{T}"] = ("anchor", dict(k_bp=k, T_s=T))
for th in (15, 25):
    for Lm in (300, 800):
        for H in (5, 30):
            CONFIGS[f"lag_th{th}_L{Lm}_H{H}"] = ("lag", dict(theta_bp=th, L_ms=Lm, H_s=H))

# post-train additions (configs 15-16), rationale: on train the gap-close exit fired within ~1 s on
# ~95% of trades, while the gross markout from the entry fill kept rising to 30 s (theta 15: +3.3 bp,
# theta 25: +8.2 bp at L=300). Test a pure 30-s time exit, and a larger theta=40.
CONFIGS["lag_th25_L300_H30_timeonly"] = ("lag", dict(theta_bp=25, L_ms=300, H_s=30, close_bp=None))
CONFIGS["lag_th40_L300_H30_timeonly"] = ("lag", dict(theta_bp=40, L_ms=300, H_s=30, close_bp=None))

OUT = Path(__file__).resolve().parents[2] / "data/raw/web/tardis/results"
OUT.mkdir(parents=True, exist_ok=True)


def run_one(args):
    coin, day, names = args
    d = L.load_day(coin, day)
    if d is None:
        return coin, day, None
    res = {}
    for nm in names:
        fam, kw = CONFIGS[nm]
        if fam == "anchor":
            tr, fl = L.sim_anchor(d, **kw)
            res[nm] = (tr, fl)
        else:
            tr = L.sim_lag(d, **kw)
            res[nm] = (tr, [])
    return coin, day, res


def main(split, names):
    days = TRAIN if split == "train" else VALID
    jobs = [(c, dd, names) for dd in days for c in COINS]
    all_tr = {n: [] for n in names}
    all_fl = {n: [] for n in names}
    cover = []
    with ProcessPoolExecutor(4) as ex:
        for coin, day, res in ex.map(run_one, jobs):
            if res is None:
                continue
            cover.append(f"{day}:{coin}")
            for n in names:
                all_tr[n] += res[n][0]
                all_fl[n] += res[n][1]
    summary = {}
    for n in names:
        tr = pd.DataFrame(all_tr[n])
        fl = pd.DataFrame(all_fl[n]) if all_fl[n] else tr
        st = L.bar_stats(tr.pnl.tolist() if len(tr) else [])
        if len(fl) and "mk1" in fl:
            for h in (1, 5, 30):
                st[f"markout{h}s_bp_mean"] = round(float(fl[f"mk{h}"].mean()), 3)
        if len(tr):
            st["exit_mix"] = tr.why.value_counts().to_dict()
            st["by_coin"] = {c: L.bar_stats(g.pnl.tolist())["net"] for c, g in tr.groupby("coin")}
            st["by_coin_n"] = tr.groupby("coin").size().to_dict()
            st["days_positive"] = int((tr.groupby("day").pnl.sum() > 0).sum())
            st["days"] = int(tr.day.nunique())
            tr.to_parquet(OUT / f"{split}_{n}.parquet", index=False)
        summary[n] = st
        print(n, json.dumps({k: v for k, v in st.items() if k not in ("by_coin", "by_coin_n")}), flush=True)
    return cover, summary


if __name__ == "__main__":
    split = sys.argv[1]
    names = sys.argv[2:] or list(CONFIGS)
    cover, summary = main(split, names)
    out = OUT / f"summary_{split}.json"
    json.dump(dict(coverage=cover, summary=summary), open(out, "w"), indent=1, default=str)
    print("coverage", len(cover), cover)
