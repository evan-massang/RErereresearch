"""H-PAIRS simulation (pre-registered in reports/hypotheses/pairs_preregistration.json).

Step 1 (form): weekly pair formation from trailing 30 days of 5m log closes -> data/raw/web/pairs/formation.json
Step 2 (sim):  12-config grid on train; chosen config run once on validation.

Point-in-time: formation uses bars with open_time in [t-30d, t); z at bar k uses spread over bars <= k (closes);
fills at the OPEN of bar k+1 (or k+2 in the delay sensitivity). Holdout (>= 2026-04-01) is never loaded.

Usage: python scripts/research/pairs_sim.py form
       python scripts/research/pairs_sim.py train
       python scripts/research/pairs_sim.py valid --config KEY
"""
import json, sys, math
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data/raw/web/pairs"
BAR = 300_000
T0 = pd.Timestamp("2024-06-01", tz="UTC"); T_END = pd.Timestamp("2026-04-01", tz="UTC")
TRAIN = (pd.Timestamp("2024-07-01", tz="UTC"), pd.Timestamp("2025-07-01", tz="UTC"))
VALID = (pd.Timestamp("2025-07-01", tz="UTC"), pd.Timestamp("2026-04-01", tz="UTC"))
FORM_BARS = 8640
TCRIT = -3.33613 - 6.1101 / FORM_BARS - 6.823 / FORM_BARS ** 2
GROSS = 2000.0
COSTS = {"HL": 4.5 + 1.0, "BINANCE": 5.0 + 1.0, "HL_slip2": 4.5 + 2.0}   # bp per leg per side
CONFIGS = {f"z{zi}_o{zo}_h{h}": dict(z_in=zi, z_out=zo, hold_mult=h)
           for zi in (2.0, 2.5, 3.0) for zo in (0.0, 0.5) for h in (2, 4)}


def load_prices():
    U = json.load(open(D / "universe.json"))
    syms = sorted({s for v in U["universe"].values() for s in v})
    n = int((T_END - T0).value // 10**6 // BAR)
    t0ms = T0.value // 10**6
    O = np.full((n, len(syms)), np.nan); C = np.full((n, len(syms)), np.nan)
    have = []
    for j, s in enumerate(syms):
        p = D / "k5m" / f"{s}.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        idx = ((df.open_time.values - t0ms) // BAR).astype(np.int64)
        ok = (idx >= 0) & (idx < n) & ((df.open_time.values - t0ms) % BAR == 0)
        O[idx[ok], j] = df.open.values[ok]; C[idx[ok], j] = df.close.values[ok]
        have.append(s)
    return U, syms, O, C, have


def bar_of(ts):
    return int((ts - T0).value // 10**6 // BAR)


def ffill(a):
    a = a.copy()
    for j in range(a.shape[1]):
        s = pd.Series(a[:, j]).ffill().values
        a[:, j] = s
    return a


def eg(y, x):
    """OLS y = a + b x; ADF(1 lag, const) t-stat on residual; AR half-life (bars)."""
    X = np.column_stack([np.ones_like(x), x])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ coef
    de = np.diff(e); lag = e[:-1]
    # ADF: de_t = c + g e_{t-1} + d de_{t-1}
    Y = de[1:]; Z = np.column_stack([np.ones(len(Y)), lag[1:], de[:-1]])
    g, res, *_ = np.linalg.lstsq(Z, Y, rcond=None)
    r = Y - Z @ g
    s2 = r @ r / (len(Y) - 3)
    cov = s2 * np.linalg.inv(Z.T @ Z)
    t = g[1] / math.sqrt(cov[1, 1])
    # half-life: de_t = c + lam e_{t-1}
    Z2 = np.column_stack([np.ones(len(de)), lag])
    lam = np.linalg.lstsq(Z2, de, rcond=None)[0][1]
    hl = -math.log(2) / lam if lam < 0 else np.inf
    return coef[0], coef[1], t, hl


def form():
    U, syms, O, C, have = load_prices()
    col = {s: j for j, s in enumerate(syms)}
    out = {}
    for t, uni in U["universe"].items():
        tt = pd.Timestamp(t, tz="UTC"); k = bar_of(tt)
        W = C[k - FORM_BARS:k]
        ok = [s for s in uni if s in have and np.isfinite(W[:, col[s]]).mean() >= 0.95]
        L = {s: np.log(pd.Series(W[:, col[s]]).ffill().bfill().values) for s in ok}
        cands = []
        for a in range(len(ok)):
            for b in range(a + 1, len(ok)):
                best = None
                for yv, xv in ((ok[a], ok[b]), (ok[b], ok[a])):
                    c0, c1, ts, hl = eg(L[yv], L[xv])
                    if best is None or ts < best[4]:
                        best = (yv, xv, c0, c1, ts, hl)
                yv, xv, c0, c1, ts, hl = best
                if ts < TCRIT and c1 > 0 and 10 <= hl <= 288:
                    cands.append(best)
        cands.sort(key=lambda r: r[4])
        cnt, sel = {}, []
        for r in cands:
            if cnt.get(r[0], 0) >= 3 or cnt.get(r[1], 0) >= 3:
                continue
            sel.append(dict(y=r[0], x=r[1], a=r[2], b=r[3], tstat=r[4], hl=r[5]))
            cnt[r[0]] = cnt.get(r[0], 0) + 1; cnt[r[1]] = cnt.get(r[1], 0) + 1
            if len(sel) >= 30:
                break
        out[t] = {"n_universe_ok": len(ok), "n_candidates": len(cands), "pairs": sel,
                  "dropped_missing": [s for s in uni if s not in ok]}
        print(t, len(ok), len(cands), len(sel), flush=True)
    json.dump(out, open(D / "formation.json", "w"), indent=0)


def simulate(cfg, split, delay=1):
    U, syms, O, C, have = load_prices()
    col = {s: j for j, s in enumerate(syms)}
    Cf = ffill(C)
    Of = np.where(np.isfinite(O), O, np.vstack([np.full((1, O.shape[1]), np.nan), Cf[:-1]]))
    F = json.load(open(D / "formation.json"))
    lo, hi = bar_of(split[0]), bar_of(split[1])
    trades = []
    for t, f in F.items():
        k0 = bar_of(pd.Timestamp(t, tz="UTC")); k1 = k0 + 2016
        if k1 <= lo or k0 >= hi:
            continue
        for p in f["pairs"]:
            jy, jx, b, hlb = col[p["y"]], col[p["x"]], p["b"], p["hl"]
            W = int(min(max(round(2 * hlb), 20), 576))
            seg = slice(k0 - W, k1)
            s = np.log(Cf[seg, jy]) - b * np.log(Cf[seg, jx])
            ss = pd.Series(s)
            z = ((ss - ss.rolling(W).mean()) / ss.rolling(W).std()).values[W:]   # z[i] -> bar k0+i
            zprev = ((ss - ss.rolling(W).mean()) / ss.rolling(W).std()).values[W - 1:-1]
            maxh = max(1, int(round(cfg["hold_mult"] * hlb)))
            wy, wx = 1 / (1 + b), b / (1 + b)
            i, nb = 0, len(z)
            while i < nb:
                kd = k0 + i
                # entry window: decision bar inside split and inside week, fill bar before week end and split end
                lastfill = min(k1, hi) - 1
                if kd < lo or kd + delay >= lastfill:
                    if kd + delay >= lastfill:
                        break
                    i += 1; continue
                zi, zp = z[i], zprev[i]
                if not (np.isfinite(zi) and np.isfinite(zp) and abs(zi) >= cfg["z_in"] and abs(zp) < cfg["z_in"]):
                    i += 1; continue
                side = -1 if zi > 0 else 1        # +1 = long spread (long y, short x)
                ke = kd + delay
                # exit decision
                stop = cfg["z_in"] + 2.0
                j = i + 1; reason = None; kx = None
                while j < nb:
                    zj = z[j]
                    if np.isfinite(zj):
                        if abs(zj) <= cfg["z_out"] or (side == 1 and zj >= -cfg["z_out"]) or (side == -1 and zj <= cfg["z_out"]):
                            reason = "revert"
                        elif abs(zj) >= stop:
                            reason = "stop"
                        elif j - i >= maxh:
                            reason = "time"
                    if reason:
                        kx = k0 + j + delay
                        break
                    j += 1
                if reason is None or kx > lastfill:
                    if k1 < hi:
                        kx, reason = k1, "week_end"          # re-formation closes everything
                    else:
                        kx, reason = hi - 1, "split_end"     # split boundary
                py = Of[kx, jy] / Of[ke, jy] - 1; px = Of[kx, jx] / Of[ke, jx] - 1
                gret = side * (wy * py - wx * px)
                trades.append(dict(week=t, y=p["y"], x=p["x"], b=b, hl=hlb, side=side,
                                   entry_bar=ke, exit_bar=kx,
                                   entry_time=str(T0 + pd.Timedelta(minutes=5 * ke)),
                                   exit_time=str(T0 + pd.Timedelta(minutes=5 * kx)),
                                   z_entry=float(zi), reason=reason, hold_bars=kx - ke,
                                   gross_usd=GROSS * gret))
                if reason == "stop":
                    break                                   # pair disabled for the week
                i = j + 1
    return pd.DataFrame(trades)


def metrics(df, cost_bp):
    if df.empty:
        return dict(n=0)
    net = df.gross_usd - GROSS * 2 * cost_bp / 1e4
    w, l = net[net > 0].sum(), -net[net < 0].sum()
    top3 = net.sort_values(ascending=False).head(3).sum()
    return dict(n=int(len(df)), gross_usd=round(float(df.gross_usd.sum()), 2), net_usd=round(float(net.sum()), 2),
                gross_bp_per_trade=round(float(df.gross_usd.mean() / GROSS * 1e4), 2),
                net_bp_per_trade=round(float(net.mean() / GROSS * 1e4), 2),
                pf=round(float(w / l), 3) if l > 0 else None, win_rate=round(float((net > 0).mean()), 3),
                net_ex_top3=round(float(net.sum() - top3), 2),
                passes=bool(len(df) >= 50 and net.sum() > 0 and l > 0 and w / l > 1.2 and net.sum() - top3 > 0))


def report(df):
    r = {c: metrics(df, bp) for c, bp in COSTS.items()}
    if not df.empty:
        yr = pd.to_datetime(df.entry_time).dt.year
        r["by_year_HL"] = {int(y): metrics(df[yr == y], COSTS["HL"]) for y in sorted(yr.unique())}
        r["exit_reasons"] = df.reason.value_counts().to_dict()
        r["median_hold_bars"] = float(df.hold_bars.median())
        r["trades_per_day"] = round(len(df) / max(1, (pd.to_datetime(df.entry_time).max() - pd.to_datetime(df.entry_time).min()).days), 2)
    return r


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "form":
        form()
    elif cmd == "train":
        res = {}
        for key, cfg in CONFIGS.items():
            df = simulate(cfg, TRAIN)
            df.to_csv(D / f"trades_train_{key}.csv", index=False)
            res[key] = report(df)
            print(key, res[key]["HL"], flush=True)
        json.dump(res, open(D / "results_train.json", "w"), indent=1)
    elif cmd == "train_delay":
        key = sys.argv[3]
        df = simulate(CONFIGS[key], TRAIN, delay=2)
        r = report(df); print(json.dumps(r["HL"]))
        json.dump(r, open(D / f"results_train_delay2_{key}.json", "w"), indent=1)
    elif cmd == "valid":
        key = sys.argv[3]
        df = simulate(CONFIGS[key], VALID); df.to_csv(D / f"trades_valid_{key}.csv", index=False)
        r = report(df)
        df2 = simulate(CONFIGS[key], VALID, delay=2)
        r["delay2_informational"] = {c: metrics(df2, bp) for c, bp in COSTS.items()}
        json.dump({"config": key, **r}, open(D / f"results_valid_{key}.json", "w"), indent=1)
        print(json.dumps(r, indent=1))
