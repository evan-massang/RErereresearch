"""H-FLUSH simulation: buy after forced-liquidation flushes on meme perps.

Lead: sources/leads/documented_edges_round4.md, idea 3 (H-FLUSH; ranked #1 in that file).

Signal (point in time, per coin):
  Binance `metrics` row stamped t is the OI snapshot at t+5min (verified: oi_value/oi matches the
  close of the 1m bar opening at t+4, median abs err 2 bp; see evidence_flush_alignment).
  At snapshot time s:  dOI = log(OI_s / OI_{s-5m});  r = log(P_s / P_{s-5m}), P = 1m close.
  z = x / sd(x over the trailing 30 days, strictly before s; min 20 days of history).
  FLUSH:   zOI <= -q and zP <= -q.
  CONTROL: zP <= -q and zOI >= 0 (equally large price drop, no OI fall).
Decision/entry time T0 = s + 1 min (one extra minute of latency). P0 = open of the 1m bar at T0.
Entry:
  mkt  : buy at P0*(1+slip), taker fee.
  j    : resting limit bid at P0*(1-j) for 5 one-minute bars; fills only if a bar's low is STRICTLY
         below the limit; fill at the limit; maker fee.
Exit: taker at the close of the H-th 1m bar after the fill bar, *(1-slip); stop -3% from entry:
  checked from the fill bar itself (conservative: if the fill bar's low reaches the stop, stopped),
  exit at min(stop, bar open)*(1-slip).
Costs (Hyperliquid tier 0, https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees):
  maker 1.5 bp, taker 4.5 bp, taker slippage 3 bp (stress 5 bp), plus 5 bp per round trip
  venue-mismatch haircut (Binance tape used as HL fill proxy, per the lead), plus funding:
  HL hourly funding (cached data/raw/web/hyperliquid/funding_<coin>.json, read only) charged at
  each hour boundary while held; DOGE / 1000PEPE (no HL cache) use Binance settlements in the hold.
One position per coin; signals while a position or order is live are skipped.
Splits: train <= 2025-06-30, validation 2025-07-01..2026-03-31; holdout (2026-04-01+) never loaded.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BF = ROOT / "data/raw/web/binance_fut"
HL = ROOT / "data/raw/web/hyperliquid"
TRD = BF / "flush_trades"
TRD.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(Path(__file__).parent))
from flush_fetch import UNIVERSE  # noqa: E402

TRAIN_END = pd.Timestamp("2025-07-01")
VAL_END = pd.Timestamp("2026-04-01")
MAKER, TAKER, HAIRCUT, STOP, WIN = 1.5e-4, 4.5e-4, 5e-4, 0.03, 5

# Pre-declared grid: 18 flush configs + 3 controls = 21 configs.
CONFIGS = []
for q in (2.5, 3.0):
    for entry in ("mkt", 0.003, 0.006):
        for H in (15, 60, 120):
            CONFIGS.append(dict(kind="flush", q=q, entry=entry, H=H))
for entry in ("mkt", 0.003, 0.006):
    CONFIGS.append(dict(kind="control", q=2.5, entry=entry, H=60))


def cname(c):
    e = "mkt" if c["entry"] == "mkt" else f"lim{c['entry']*100:.1f}%"
    return f"{c['kind']}_q{c['q']}_{e}_H{c['H']}"


def load_funding(hl: str, sym: str) -> pd.Series:
    p = HL / f"funding_{hl}.json"
    if p.exists():
        rows = json.load(open(p))["rows"]
        f = pd.Series([float(r["fundingRate"]) for r in rows],
                      index=pd.to_datetime([r["time"] for r in rows], unit="ms").floor("h"))
        return f[~f.index.duplicated()].sort_index()
    p = BF / "funding" / f"{sym}.parquet"
    f = pd.read_parquet(p)
    return pd.Series(f.rate.values, index=f.t.dt.floor("min")).sort_index()


# PUMPUSDT before the 2025-07-10 relisting gap was a different asset (price ~0.05-0.16, flat in June);
# pump.fun's PUMP starts after the gap.
START = {"PUMPUSDT": pd.Timestamp("2025-07-10 08:00")}


def signals(sym: str):
    k = pd.read_parquet(BF / "klines1m" / f"{sym}.parquet").set_index("t")
    if sym in START:
        k = k[k.index >= START[sym]]
    grid = pd.date_range(k.index.min(), k.index.max(), freq="min")
    k = k.reindex(grid)
    m = pd.read_parquet(BF / "metrics" / f"{sym}.parquet")
    if sym in START:
        m = m[m.ts >= START[sym]]
    s = (m.ts + pd.Timedelta(minutes=5)).values
    oi = pd.Series(m.oi.values, index=s)
    oi = oi[oi > 0]
    prev = oi.reindex(oi.index - pd.Timedelta(minutes=5)).values
    doi = np.log(oi.values / prev)
    pc = k.close  # close of bar opening at s-1 = price at s
    p_now = pc.reindex(oi.index - pd.Timedelta(minutes=1)).values
    p_prev = pc.reindex(oi.index - pd.Timedelta(minutes=6)).values
    r = np.log(p_now / p_prev)
    df = pd.DataFrame({"doi": doi, "r": r}, index=oi.index).dropna()
    df = df[np.isfinite(df.doi) & np.isfinite(df.r)]
    sd = df.rolling("30D", closed="left").std()
    cnt = df.doi.rolling("30D", closed="left").count()
    df["zoi"] = df.doi / sd.doi
    df["zp"] = df.r / sd.r
    df = df[cnt >= 20 * 288]
    return k, df


def simulate(sym, hl, k, sig, c, slip, fund):
    q = c["q"]
    if c["kind"] == "flush":
        ev = sig[(sig.zoi <= -q) & (sig.zp <= -q)]
    else:
        ev = sig[(sig.zp <= -q) & (sig.zoi >= 0)]
    o, h, l, cl = (k[x].values for x in ("open", "high", "low", "close"))
    t0 = k.index[0]
    n = len(k)
    busy_until = pd.Timestamp(0)
    out = []
    for s, row in ev.iterrows():
        T0 = s + pd.Timedelta(minutes=1)
        if T0 < busy_until:
            continue
        i0 = int((T0 - t0) / pd.Timedelta(minutes=1))
        if i0 + WIN + c["H"] + 2 >= n:
            continue
        P0 = o[i0]
        if not np.isfinite(P0):
            continue
        # entry
        if c["entry"] == "mkt":
            fi, px, fee_in = i0, P0 * (1 + slip), TAKER
        else:
            L = P0 * (1 - c["entry"])
            fi = None
            for i in range(i0, i0 + WIN):
                if np.isfinite(l[i]) and l[i] < L:
                    fi = i
                    break
            if fi is None:
                busy_until = k.index[i0 + WIN]
                out.append(dict(sym=sym, s=s, filled=False))
                continue
            px, fee_in = L, MAKER
        ie = fi + c["H"]
        seg_l = l[fi:ie + 1]
        if np.isnan(seg_l).any() or not np.isfinite(cl[ie]):
            busy_until = k.index[ie + 1]
            out.append(dict(sym=sym, s=s, filled=True, gap=True))
            continue
        stop = px * (1 - STOP)
        hit = np.where(seg_l <= stop)[0]
        if len(hit):
            j = fi + hit[0]
            ref = stop if j == fi else min(stop, o[j])
            exit_px, ie, why = ref * (1 - slip), j, "stop"
        else:
            exit_px, why = cl[ie] * (1 - slip), "time"
        t_in, t_out = k.index[fi], k.index[ie] + pd.Timedelta(minutes=1)
        f = fund[(fund.index > t_in) & (fund.index <= t_out)].sum()
        gross = exit_px / px - 1
        net = gross - fee_in - TAKER - HAIRCUT - f
        busy_until = t_out
        out.append(dict(sym=sym, s=s, filled=True, gap=False, t_in=t_in, t_out=t_out, entry=px,
                        exit=exit_px, why=why, zoi=row.zoi, zp=row.zp, gross=gross, funding=f, net=net))
    return out


def stats(tr: pd.DataFrame) -> dict:
    if len(tr) == 0:
        return dict(n=0)
    x = tr.net.values
    srt = np.sort(x)[::-1]
    pos, neg = x[x > 0].sum(), -x[x < 0].sum()
    daily = tr.groupby(tr.t_in.dt.date).net.sum()
    return dict(n=int(len(x)), days=int(daily.size), net_sum_pct=round(100 * x.sum(), 2),
                mean_bp=round(1e4 * x.mean(), 1), median_bp=round(1e4 * np.median(x), 1),
                win=round(float((x > 0).mean()), 3), pf=round(pos / neg, 3) if neg > 0 else None,
                net_ex_top3_pct=round(100 * srt[3:].sum(), 2),
                day_t=round(daily.mean() / (daily.std(ddof=1) / np.sqrt(daily.size)), 2) if daily.size > 2 else None,
                stops=int((tr.why == "stop").sum()))


def passes(st: dict) -> bool:
    return (st.get("n", 0) >= 50 and st["net_sum_pct"] > 0 and (st["pf"] or 0) > 1.2
            and st["net_ex_top3_pct"] > 0)


if __name__ == "__main__":
    split = sys.argv[1] if len(sys.argv) > 1 else "train"
    only = sys.argv[2].split(",") if len(sys.argv) > 2 else None
    slip = float(sys.argv[3]) if len(sys.argv) > 3 else 3e-4
    hl_of = {v: kk for kk, v in UNIVERSE.items()}
    syms = sorted(p.stem for p in (BF / "klines1m").glob("*.parquet")
                  if p.stem in hl_of and (BF / "metrics" / p.name).exists())
    configs = [c for c in CONFIGS if only is None or cname(c) in only]
    allt = {cname(c): [] for c in configs}
    cover, evcount = {}, {}
    for sym in syms:
        k, sig = signals(sym)
        lo, hi = (pd.Timestamp(0), TRAIN_END) if split == "train" else (TRAIN_END, VAL_END)
        sig = sig[(sig.index >= lo) & (sig.index < hi)]
        if len(sig) == 0:
            continue
        cover[sym] = [str(sig.index.min()), str(sig.index.max()), int(len(sig))]
        evcount[sym] = {f"flush_q{q}": int(((sig.zoi <= -q) & (sig.zp <= -q)).sum()) for q in (2.5, 3.0)}
        evcount[sym]["control_q2.5"] = int(((sig.zp <= -2.5) & (sig.zoi >= 0)).sum())
        fund = load_funding(hl_of[sym], sym)
        for c in configs:
            allt[cname(c)] += simulate(sym, hl_of[sym], k, sig, c, slip, fund)
    res = {}
    for name, rows in allt.items():
        df = pd.DataFrame(rows)
        tr = df[(df.filled) & (~df.get("gap", False).fillna(False).astype(bool))].copy() if len(df) else df
        st = stats(tr) if len(tr) else dict(n=0)
        st["signals_acted"] = int(len(df))
        st["fill_rate"] = round(float(df.filled.mean()), 3) if len(df) else None
        st["pass"] = bool(passes(st)) if st.get("n") else False
        if len(tr):
            st["per_coin"] = {s: dict(n=int(len(g)), net_pct=round(100 * g.net.sum(), 2))
                              for s, g in tr.groupby("sym")}
            st["per_quarter"] = {str(p): dict(n=int(len(g)), net_pct=round(100 * g.net.sum(), 2))
                                 for p, g in tr.groupby(tr.t_in.dt.to_period("Q"))}
            st["top3_bp"] = [round(1e4 * v, 1) for v in np.sort(tr.net.values)[::-1][:3]]
            st["bottom3_bp"] = [round(1e4 * v, 1) for v in np.sort(tr.net.values)[:3]]
            tr.to_csv(TRD / f"{split}_{name}_slip{round(slip*1e4)}.csv",
                      index=False)
        res[name] = st
    out = dict(split=split, slip_bp=slip * 1e4, n_configs=len(configs), coverage=cover,
               event_counts=evcount, results=res)
    tag = "" if round(slip * 1e4) == 3 else f"_slip{round(slip * 1e4)}"
    p = ROOT / f"research/observations/evidence_flush_{split}{tag}.json"
    if only:
        p = p.with_name(p.stem + "_subset.json")
    json.dump(out, open(p, "w"), indent=1, default=str)
    for name, st in res.items():
        print(name, {kk: st.get(kk) for kk in ("n", "days", "fill_rate", "net_sum_pct", "mean_bp", "pf",
                                                "net_ex_top3_pct", "win", "day_t", "stops", "pass")})
