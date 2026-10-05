"""H-XLEAD: minute-level cross-asset lead-lag into Binance meme perps (Guo, Sang, Tu & Wang, JEDC 163, 2024).

Usage:
  python scripts/research/xlead_sim.py train        # fit + select on train only (2024-01 .. 2025-06-30)
  python scripts/research/xlead_sim.py validation   # scores ONLY configs that passed the bar on train (once)
Holdout (2026-04-01 onward) is never loaded (and was never downloaded).

Model (pre-registered): for each meme i, every completed minute t, predict the log return close_t -> close_{t+h}
from lags 0..2 (i.e. minutes t, t-1, t-2, all completed) of the 1m log returns of BTC, SOL and the equal-weight
meme index excluding i (feature set "base", 9 regressors, no intercept). Feature set "own" adds i's own lags 0..2.
Per-coin OLS with a tiny ridge (1e-8 * trace), refit every Monday 00:00 UTC on the trailing 30 days whose targets
were fully realised before the refit time. Features are clipped at +-5% per minute; realised P&L is never clipped.
A coin trades only once it has 30 days of history (the first refit after that).

Execution (Binance klines as the price source, execution assumed on Hyperliquid at the same price):
  taker: enter at close_t (delay 0, optimistic) or close_{t+1} (delay 1), exit at close of the minute h later.
         cost per side = 4.5 bp HL taker (base tier, https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees)
         + slippage s (3 bp base; 2 and 5 bp sensitivity).
  maker: post a limit at close_t; filled only if minute t+1 trades THROUGH it by >= 1 bp (low < 0.9999*close_t
         for a buy, high > 1.0001*close_t for a sell); fee 1.5 bp HL maker, no slippage on entry; exit taker
         at close_{t+h} with 4.5 bp + s. Unfilled orders are dropped.
One position per coin at a time; re-entry allowed at the exit minute. Trade P&L in bp of notional.
Trade when |pred| >= c * round-trip cost (taker RT = 2*(4.5+s); maker RT = 1.5 + 4.5 + s).
"""
import json, os, sys, glob
import numpy as np
import pandas as pd

ROOT = "/home/user/RErereresearch"
RAW = f"{ROOT}/data/raw/web/binance_fut/xlead"
LEADERS = ["BTCUSDT", "SOLUSDT"]
MEMES = ["DOGEUSDT", "1000PEPEUSDT", "1000SHIBUSDT", "1000BONKUSDT", "1000FLOKIUSDT", "WIFUSDT", "BOMEUSDT",
         "MEMEUSDT", "PEOPLEUSDT", "MYROUSDT", "POPCATUSDT", "TURBOUSDT", "BRETTUSDT", "MEWUSDT", "NEIROUSDT",
         "GOATUSDT", "MOODENGUSDT", "PNUTUSDT", "CHILLGUYUSDT", "PENGUUSDT", "FARTCOINUSDT", "DOGSUSDT"]
T0 = pd.Timestamp("2024-01-01", tz="UTC")
TRAIN_END = pd.Timestamp("2025-07-01", tz="UTC")
VAL_END = pd.Timestamp("2026-04-01", tz="UTC")
TAKER, MAKER = 4.5, 1.5
FIT_DAYS = 30

# 15 pre-registered configs: (name, feats, h, c, mode)
CONFIGS = ([(f"T_base_h{h}_c{c}", "base", h, c, "taker") for h in (1, 3, 5) for c in (1.5, 2.0, 3.0)]
           + [(f"M_base_h{h}_c{c}", "base", h, c, "maker") for h in (3, 5) for c in (1.0, 1.5)]
           + [(f"T_own_h5_c{c}", "own", 5, c, "taker") for c in (1.5, 2.0)])


def load(end):
    n = int((end - T0).total_seconds() // 60)
    idx0 = T0.value // 10**6
    out = {}
    for sym in LEADERS + MEMES:
        files = sorted(glob.glob(f"{RAW}/{sym}/*.parquet"))
        df = pd.concat([pd.read_parquet(f) for f in files])
        ot = df.open_time.values
        if ot.max() > 10**14:  # microseconds in newer archive files
            ot = np.where(ot > 10**14, ot // 1000, ot)
        pos = (ot - idx0) // 60000
        ok = (pos >= 0) & (pos < n)
        arr = {k: np.full(n, np.nan) for k in ("close", "high", "low")}
        for k in arr:
            arr[k][pos[ok]] = df[k].values[ok]
        out[sym] = arr
    return n, out


def build(n, data):
    lr = {s: np.diff(np.log(data[s]["close"]), prepend=np.nan) for s in data}
    M = np.vstack([lr[s] for s in MEMES])  # memes x n
    Mc = np.clip(M, -0.05, 0.05)
    cnt = np.sum(~np.isnan(Mc), 0)
    tot = np.nansum(Mc, 0)
    return lr, Mc, cnt, tot


def lags(x, k=3):
    x = np.clip(np.nan_to_num(x, nan=0.0), -0.05, 0.05)
    cols = [x]
    for j in range(1, k):
        cols.append(np.concatenate([np.zeros(j), x[:-j]]))
    return np.column_stack(cols)


def predict_coin(i, sym, n, data, lr, Mc, cnt, tot, h, feats):
    """Walk-forward predictions of log(close_{t+h}/close_t) for coin sym; NaN where no model."""
    own = Mc[i]
    o = np.nan_to_num(own, nan=0.0)
    c2 = cnt - (~np.isnan(own)).astype(int)
    idx = np.where(c2 > 0, (tot - o) / np.maximum(c2, 1), np.nan)
    X = [lags(lr["BTCUSDT"]), lags(lr["SOLUSDT"]), lags(idx)]
    if feats == "own":
        X.append(lags(own))
    X = np.hstack(X)
    close = data[sym]["close"]
    y = np.full(n, np.nan)
    y[:-h] = np.log(close[h:] / close[:-h])
    valid = ~np.isnan(y) & ~np.isnan(lr["BTCUSDT"]) & ~np.isnan(lr["SOLUSDT"]) & ~np.isnan(own) & ~np.isnan(idx)
    first = np.argmax(~np.isnan(close))
    pred = np.full(n, np.nan)
    week = 7 * 1440
    # Mondays: 2024-01-01 is a Monday
    starts = np.arange(0, n, week)
    for s in starts:
        if s - first < FIT_DAYS * 1440:
            continue
        lo, hi = s - FIT_DAYS * 1440, s - h  # targets realised before s
        m = valid[lo:hi]
        if m.sum() < 5000:
            continue
        Xa, ya = X[lo:hi][m], y[lo:hi][m]
        A = Xa.T @ Xa
        A += np.eye(A.shape[0]) * 1e-8 * np.trace(A)
        b = np.linalg.solve(A, Xa.T @ ya)
        e = min(s + week, n)
        pred[s:e] = X[s:e] @ b
    pred[np.isnan(close)] = np.nan
    return pred, y


def simulate(pred, data, sym, h, thr, mode, slip, delay, lo, hi):
    close, high, low = data[sym]["close"], data[sym]["high"], data[sym]["low"]
    n = len(close)
    sig = np.where(np.abs(np.nan_to_num(pred[lo:hi])) >= thr)[0] + lo
    trades = []
    free_at = -1
    for t in sig:
        if t < free_at:
            continue
        d = 1.0 if pred[t] > 0 else -1.0
        if mode == "taker":
            te, tx = t + delay, t + delay + h
            if tx >= n or tx >= hi + h + delay:
                continue
            pe, px = close[te], close[tx]
            if np.isnan(pe) or np.isnan(px):
                continue
            g = d * (px / pe - 1) * 1e4
            cost = 2 * (TAKER + slip)
        else:
            tx = t + h
            if tx >= n:
                continue
            pe, px = close[t], close[tx]
            if np.isnan(pe) or np.isnan(px) or np.isnan(low[t + 1]):
                continue
            filled = low[t + 1] < pe * 0.9999 if d > 0 else high[t + 1] > pe * 1.0001
            if not filled:
                continue
            g = d * (px / pe - 1) * 1e4
            cost = MAKER + TAKER + slip
        trades.append((t, d, g, g - cost))
        free_at = tx
    return trades


def stats(net):
    net = np.asarray(net)
    if len(net) == 0:
        return {"n": 0}
    w, l = net[net > 0].sum(), -net[net < 0].sum()
    s = np.sort(net)[::-1]
    return {"n": int(len(net)), "net_bp": round(float(net.sum()), 1), "mean_bp": round(float(net.mean()), 3),
            "pf": round(float(w / l), 3) if l > 0 else None, "win": round(float((net > 0).mean()), 3),
            "net_ex3_bp": round(float(net.sum() - s[:3].sum()), 1)}


def passes(st):
    return st["n"] >= 50 and st["net_bp"] > 0 and (st["pf"] or 0) > 1.2 and st["net_ex3_bp"] > 0


def run(split):
    end = TRAIN_END if split == "train" else VAL_END
    lo_ts = T0 if split == "train" else TRAIN_END
    n, data = load(end)
    lo = int((lo_ts - T0).total_seconds() // 60)
    hi = n
    lr, Mc, cnt, tot = build(n, data)
    times = pd.to_datetime(T0.value + np.arange(n, dtype=np.int64) * 60 * 10**9, utc=True)
    quarter = times.to_period("Q").astype(str).values
    passing = None
    if split == "validation":
        tr = json.load(open(f"{ROOT}/research/observations/evidence_xlead_train.json"))
        passing = tr["passing_train"]
        if not passing:
            print("no config passed train; validation not scored")
            return
    res = {"split": split, "range": [str(lo_ts), str(end)], "configs": {}, "diagnostics": {}}
    cache = {}
    for name, feats, h, c, mode in CONFIGS:
        if passing is not None and name not in passing:
            continue
        key = (feats, h)
        if key not in cache:
            cache[key] = {}
            diag = {"bins": {}, "oos_r2": {}}
            allp, ally = [], []
            for i, sym in enumerate(MEMES):
                p, y = predict_coin(i, sym, n, data, lr, Mc, cnt, tot, h, feats)
                cache[key][sym] = p
                m = ~np.isnan(p[lo:hi]) & ~np.isnan(y[lo:hi])
                pp, yy = p[lo:hi][m], y[lo:hi][m]
                if len(pp):
                    diag["oos_r2"][sym] = round(float(1 - np.sum((yy - pp) ** 2) / np.sum(yy ** 2)), 5)
                allp.append(pp); ally.append(yy)
            P, Y = np.concatenate(allp), np.concatenate(ally)
            ab = np.abs(P) * 1e4
            edges = [0, 2, 5, 7.5, 10, 15, 22.5, 30, 45, 1e9]
            for a, b in zip(edges[:-1], edges[1:]):
                m = (ab >= a) & (ab < b)
                if m.sum():
                    diag["bins"][f"{a}-{b}bp"] = {"n": int(m.sum()),
                                                  "mean_pred_bp": round(float(ab[m].mean()), 2),
                                                  "mean_signed_realised_bp": round(float((np.sign(P[m]) * Y[m]).mean() * 1e4), 3)}
            diag["pooled_oos_r2"] = round(float(1 - np.sum((Y - P) ** 2) / np.sum(Y ** 2)), 5)
            diag["corr"] = round(float(np.corrcoef(P, Y)[0, 1]), 4)
            res["diagnostics"][f"{feats}_h{h}"] = diag
            print(f"diag {feats} h{h}", json.dumps({k: v for k, v in diag.items() if k != 'oos_r2'}))
        preds = cache[key]
        out = {}
        for slip in (2.0, 3.0, 5.0):
            rt = 2 * (TAKER + slip) if mode == "taker" else MAKER + TAKER + slip
            thr = c * rt / 1e4
            for delay in ((0, 1) if mode == "taker" else (0,)):
                allt = []
                for sym in MEMES:
                    for t, d, g, nt in simulate(preds[sym], data, sym, h, thr, mode, slip, delay, lo, hi):
                        allt.append((sym, t, g, nt))
                tag = f"slip{slip:g}_d{delay}"
                if not allt:
                    out[tag] = {"n": 0}
                    continue
                df = pd.DataFrame(allt, columns=["sym", "t", "gross", "net"])
                st = stats(df.net.values)
                st["gross_mean_bp"] = round(float(df.gross.mean()), 3)
                st["cost_rt_bp"] = rt
                days = (hi - lo) / 1440
                st["trades_per_day"] = round(len(df) / days, 2)
                st["notional_turnover_per_day_x_coin_capital"] = round(2 * len(df) / days / len(MEMES), 2)
                if slip == 3.0 and delay == 0:
                    st["per_coin"] = {s: stats(g.net.values) | {"gross_mean_bp": round(float(g.gross.mean()), 2)}
                                      for s, g in df.groupby("sym")}
                    df["q"] = quarter[df.t.values]
                    st["per_quarter"] = {q: stats(g.net.values) | {"gross_mean_bp": round(float(g.gross.mean()), 2)}
                                         for q, g in df.groupby("q")}
                out[tag] = st
        base = out["slip3_d0"]
        out["passes_bar_slip3_d0"] = bool(base.get("n", 0) and passes(base))
        res["configs"][name] = out
        print(name, {k: out[k] if not isinstance(out[k], dict) else
                     {kk: vv for kk, vv in out[k].items() if kk not in ("per_coin", "per_quarter")}
                     for k in ("slip3_d0", "passes_bar_slip3_d0")})
    res["n_configs"] = len(CONFIGS)
    if split == "train":
        res["passing_train"] = [k for k, v in res["configs"].items() if v["passes_bar_slip3_d0"]]
    else:
        res["validated"] = [k for k, v in res["configs"].items() if v["passes_bar_slip3_d0"]]
    res["is_synthetic"] = False
    res["data"] = {"source": "data.binance.vision USD-M futures monthly 1m klines", "cache": RAW,
                   "coins": MEMES, "leaders": LEADERS}
    json.dump(res, open(f"{ROOT}/research/observations/evidence_xlead_{split}.json", "w"), indent=1)


if __name__ == "__main__":
    run(sys.argv[1])
