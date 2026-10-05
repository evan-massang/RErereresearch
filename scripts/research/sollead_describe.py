"""H-SOLLEAD step 1 (describe, TRAIN ONLY): does SOL/USD lead memecoin prices on the curve and PumpSwap?

- Cross-correlation of the SOL 1-minute return (bucket t) with the equal-weight index return of active curve
  tokens / migrated pools (bucket t+k), k = -3..10, in SOL terms and USD terms (USD = SOL-terms + SOL return).
- Joint distributed-lag OLS of index return on SOL returns at lags 0..10 (Newey-West t-stats, 10 lags).
- Event study: SOL h-minute return (h = 1, 3, 5, ending at the close of bucket t) at or beyond the train
  1st/99th percentile and fixed thresholds; cumulative index return over buckets t+1..t+k, k = 1..10,
  minus the unconditional mean drift over k minutes. Events de-overlapped with a 10-minute cooldown.

Writes research/observations/evidence_sollead_describe.json.
    python scripts/research/sollead_describe.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sollead_lib as L  # noqa: E402

OUT = L.ROOT / "research" / "observations" / "evidence_sollead_describe.json"
LAGS = range(-3, 11)


def nw_ols(y, X, lags=10):
    X = np.column_stack([np.ones(len(y)), X])
    XtX_inv = np.linalg.inv(X.T @ X)
    b = XtX_inv @ X.T @ y
    e = y - X @ b
    u = X * e[:, None]
    S = u.T @ u
    for l in range(1, lags + 1):
        w = 1 - l / (lags + 1)
        G = u[l:].T @ u[:-l]
        S += w * (G + G.T)
    V = XtX_inv @ S @ XtX_inv
    return b, np.sqrt(np.diag(V))


def describe(idx: pd.DataFrame, sol: pd.DataFrame, name: str) -> dict:
    mins = np.arange(sol.index.min(), L.VAL_B, 60)
    df = pd.DataFrame(index=mins)
    df["s"] = sol.r1.reindex(mins)
    df["x"] = idx.r.reindex(mins)
    df["k"] = idx.k.reindex(mins)
    df["split"] = L.split_of(df.index.to_numpy())
    tr = df.copy()
    tr.loc[tr.split != "train", ["s", "x"]] = np.nan  # keep the time grid; non-train minutes blanked
    out = {"train_minutes_with_index": int(tr.x.notna().sum()),
           "median_tokens_per_minute": float(tr.k[tr.x.notna()].median())}
    xc = {}
    for k in LAGS:
        a, b = tr.s, tr.x.shift(-k)
        m = a.notna() & b.notna()
        c_sol = float(np.corrcoef(a[m], b[m])[0, 1])
        c_usd = float(np.corrcoef(a[m], (b + tr.s.shift(-k))[m])[0, 1])
        xc[str(k)] = {"corr_sol_terms": round(c_sol, 4), "corr_usd_terms": round(c_usd, 4), "n": int(m.sum())}
    out["xcorr_sol_t_vs_index_t_plus_k"] = xc
    out["approx_corr_se"] = round(1 / np.sqrt(out["train_minutes_with_index"]), 4)
    # distributed lag
    X = np.column_stack([tr.s.shift(l) for l in range(0, 11)])
    y = tr.x.to_numpy()
    m = ~np.isnan(X).any(1) & ~np.isnan(y)
    b, se = nw_ols(y[m], X[m])
    out["distributed_lag_beta"] = {f"lag{l}": {"beta": round(float(b[l + 1]), 4), "t_nw": round(float(b[l + 1] / se[l + 1]), 2)}
                                   for l in range(11)}
    out["distributed_lag_sum_lags1_10"] = round(float(b[2:].sum()), 4)
    out["distributed_lag_n"] = int(m.sum())
    # event study
    drift = float(tr.x.mean())
    ev = {}
    for h in (1, 3, 5):
        sh = tr.s.rolling(h, min_periods=h).sum()  # return over buckets t-h+1..t
        q01, q99 = float(sh.quantile(0.01)), float(sh.quantile(0.99))
        for lab, thr in (("p99", q99), ("p01", q01), ("+0.5%", 0.005), ("-0.5%", -0.005), ("+1%", 0.01), ("-1%", -0.01)):
            hit = (sh >= thr) if thr > 0 else (sh <= thr)
            ts, last = [], -1e18
            for t in sh.index[hit.fillna(False).to_numpy()]:
                if t - last >= 600:
                    ts.append(t)
                    last = t
            resp = {}
            for k in (1, 2, 3, 5, 10):
                vals = []
                for t in ts:
                    fut = tr.x.reindex(np.arange(t + 60, t + 60 * (k + 1), 60))
                    if fut.notna().sum() == k:
                        vals.append(fut.sum() - k * drift)
                v = np.array(vals)
                resp[str(k)] = {"mean_abn": round(float(v.mean()), 5) if len(v) else None,
                                "t": round(float(v.mean() / (v.std(ddof=1) / np.sqrt(len(v)))), 2) if len(v) > 2 else None,
                                "n": int(len(v))}
            ev[f"h{h}|{lab}"] = {"threshold": round(thr, 5), "n_events": len(ts),
                                 "sol_move_mean": round(float(sh.reindex(ts).mean()), 5) if ts else None,
                                 "abn_cum_index_logret": resp}
    out["event_study"] = ev
    out["drift_per_min"] = round(drift, 6)
    return out


def main():
    sol = L.sol_minutes()
    con = L.connect()
    res = {"what": "H-SOLLEAD train-only description; index = equal-weight mean of clipped 1-min log returns",
           "sol_train_1m_ret_sd": None}
    s_tr = sol.r1[L.split_of(sol.index.to_numpy()) == "train"]
    res["sol_train_1m_ret_sd"] = round(float(s_tr.std()), 5)
    res["sol_train_abs_1m_ret_p99"] = round(float(s_tr.abs().quantile(0.99)), 5)
    for name, fn in (("curve", L.curve_minute_panel), ("amm", L.amm_minute_panel)):
        panel = fn(con)
        print(name, "panel rows", len(panel), flush=True)
        for mt in (1, 5):
            idx = L.index_returns(panel, min_trades=mt)
            r = describe(idx, sol, name)
            res[f"{name}|min_trades{mt}"] = r
            xc = r["xcorr_sol_t_vs_index_t_plus_k"]
            print(name, mt, {k: v["corr_sol_terms"] for k, v in xc.items()})
            print("  DL", {k: (v["beta"], v["t_nw"]) for k, v in r["distributed_lag_beta"].items()})
    OUT.write_text(json.dumps(res, indent=1))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
