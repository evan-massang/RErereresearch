"""Round USD market-cap levels on the pump.fun bonding curve (agent round_levels, 2026-10-05).

Hypothesis: pump.fun's UI and bots show market cap in USD and traders set take-profits / limits at round
levels, so (i) sell pressure and reversals cluster 0-5% below round levels (resistance) and (ii) clean breaks
above a round level with continued buying run (breakout).

Market cap: mcap_sol = vsol / vtok * 1e9 (trusted states only, |vsol - rsol - 30| < 0.01); mcap_usd =
mcap_sol x SOL/USDT close of the last *completed* 1-minute bar (point in time; Binance klines cached by
round_levels_solusd.py). On this curve mcap runs ~$3.3k (launch) to ~$49k (completion), so levels >= $50k
are not reachable and are not used.

Levels (fixed before any outcome was computed):
  R10 (round)       $10k $20k $30k $40k
  R5  (half-round)  $15k $25k $35k $45k
  other (placebo)   every other whole $1k from $6k to $46k (incl. $13k $17k $23k $27k $33k $37k $43k)

Part 1, DESCRIBE (train only): per level L,
  pass   - tokens whose first print >= 0.95L is still < L: share that print >= L within 600 s
  sellsh - share of trades that are sells among trades whose pre-trade mcap is in [0.95L, L)
  ath    - token all-time-high mcap (non-completed tokens) in [0.95L, L) vs [L, 1.05L)
  each compared with the mean of the neighbouring whole-$1k levels (L +- 1k, L +- 2k).

Part 2, RULES (20 configs, fixed here):
  A breakout  first print with mcap in [L(1+X), 1.05 L(1+X)) and >= N distinct buyers in the trailing 10 s,
              L in R10; X in {1%, 3%}; N in {3, 6}; exits TP/SL 30/15 300 s, 50/20 300 s, 100/30 1800 s  (12)
  B retest    as A with X = 1%, but only after the token printed in [0.95L, L) and then fell to <= 0.85L
              without ever printing >= L (a rejection); N in {3, 6}; same 3 exits                        (6)
  C front-run first print in [0.85L, 0.88L) with >= 3 buyers in 10 s, L in R10; take profit at 0.97L
              (just below the level the resistance sellers defend), SL 10% or 20%, max hold 600 s         (2)
  Controls (not eligible for selection): rule A on placebo levels {13,17,23,27,33,37,43}k.
One position per token at a time (a trigger while a previous trade on the token is open is skipped).
Fills: exact constant-product as event_studies.rt()/outcomes() (0.5 SOL, 1.25% fee per side, 1 s latency,
completion handling); a trigger is kept only if creation, trigger and trigger + 1 s + max hold all lie in one
gap-free recording segment (no global gap > 60 s) of allowed data. Mayhem tokens and unflagged tokens excluded.
Allowed data: recv < 1790882100 or 1790899200 <= recv < 1791072000. Train: before 1790985600; validation: after.

    python scripts/research/round_levels_build.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "research"))
import duckdb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import event_studies as es  # noqa: E402
from pipeline import config  # noqa: E402

HOLD0, HOLD1, OCT3, OCT4 = 1790882100.0, 1790899200.0, 1790985600.0, 1791072000.0
ALLOWED = f"recv < {OCT4} AND NOT (recv >= {HOLD0} AND recv < {HOLD1})"
GAP = 60.0
SCRATCH = Path("/tmp/claude-0/-home-user-RErereresearch/f8ba0823-6528-5b3d-92e7-a2d8665674ee/scratchpad")
R10 = [10e3, 20e3, 30e3, 40e3]
R5 = [15e3, 25e3, 35e3, 45e3]
GRID = [k * 1e3 for k in range(6, 47)]
PLACEBO = [13e3, 17e3, 23e3, 27e3, 33e3, 37e3, 43e3]
EXITS = [(0.3, 0.15, 300), (0.5, 0.2, 300), (1.0, 0.3, 1800)]
LAT, SIZE, FEE = es.LATENCY, es.SIZE, es.FEE


def configs():
    c = []
    for X in (0.01, 0.03):
        for N in (3, 6):
            for a, b, mh in EXITS:
                c.append(dict(rule="A", X=X, N=N, tp=a, sl=b, mh=mh, levels="R10"))
    for N in (3, 6):
        for a, b, mh in EXITS:
            c.append(dict(rule="B", X=0.01, N=N, tp=a, sl=b, mh=mh, levels="R10"))
    for sl in (0.1, 0.2):
        c.append(dict(rule="C", X=None, N=3, tp=None, sl=sl, mh=600, levels="R10"))
    ctrl = []
    for X in (0.01, 0.03):
        for N in (3, 6):
            for a, b, mh in EXITS:
                ctrl.append(dict(rule="A", X=X, N=N, tp=a, sl=b, mh=mh, levels="PLACEBO"))
    for d in c + ctrl:
        d["name"] = (f"{d['rule']}_{d['levels']}_X{d['X']}_N{d['N']}_tp{d['tp']}_sl{d['sl']}_{d['mh']}")
    return c, ctrl


def segments(con) -> np.ndarray:
    r = con.execute(f"""WITH t AS (SELECT recv, lag(recv) OVER (ORDER BY recv) p FROM curve_trades WHERE {ALLOWED})
                        SELECT p, recv FROM t WHERE recv - p > {GAP} ORDER BY p""").fetchall()
    lo, hi = con.execute(f"SELECT min(recv), max(recv) FROM curve_trades WHERE {ALLOWED}").fetchone()
    s = np.array(list(zip([lo] + [b for _, b in r], [p for p, _ in r] + [hi])))
    # split at the period boundaries so no window crosses holdout / train-validation / end
    out = []
    for a, b in s:
        for cut in (HOLD0, OCT3, OCT4):
            if a < cut <= b:
                out.append((a, np.nextafter(cut, 0)))
                a = cut
        if a < b:
            out.append((a, b))
    return np.array(out)


def seg_of(segs, t):
    i = np.searchsorted(segs[:, 0], t, side="right") - 1
    return i if i >= 0 and t <= segs[i, 1] else -1


def exit_path(T, vs, vt, t, tc, a, b, mh, tp_px=None):
    """Same mechanics as event_studies.outcomes (one exit). Returns (gross_pnl, exit_time, entry_idx)."""
    k = np.searchsorted(T, t + LAT, side="right")
    vs0, vt0 = vs[k - 1], vt[k - 1]
    p0 = vs0 / vt0
    end = t + LAT + mh
    lim = np.searchsorted(T, min(end, tc), side="left") if tc is not None and tc <= end else np.searchsorted(T, end, side="right")
    lim = max(lim, k)
    px = vs[k:lim] / vt[k:lim]
    up = p0 * (1 + a) if tp_px is None else tp_px
    hit = np.nonzero((px >= up) | (px <= p0 * (1 - b)))[0]
    e = np.searchsorted(T, T[k + hit[0]] + LAT, side="right") if len(hit) else lim
    if tc is not None:
        e = min(e, np.searchsorted(T, tc, side="left"))
    e = max(e, k)
    return es.rt(vs0, vt0, vs[e - 1], vt[e - 1]), (T[e - 1] if e > k else T[k - 1]), k


def main():
    con = duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
    con.execute("SET threads TO 2")
    segs = segments(con)
    print("segments", len(segs), [(round(a), round(b)) for a, b in segs if b - a > 3600], flush=True)
    sol = pd.read_parquet(ROOT / "data/raw/web/solusd/solusdt_1m_20261001_20261003.parquet")
    st, sc = sol.t.to_numpy(float), sol.close.to_numpy()
    fl = pd.read_parquet(ROOT / "data/processed/mayhem_flags.parquet", columns=["mint", "is_mayhem"])
    ok_mints = set(fl.mint[fl.is_mayhem == False])  # noqa: E712
    cr = con.execute(f"SELECT mint, min(recv) ct FROM curve_creates WHERE {ALLOWED} GROUP BY 1").df()
    cr = cr[cr.mint.isin(ok_mints)]
    cr["seg"] = [seg_of(segs, t) for t in cr.ct]
    cr = cr[cr.seg >= 0]
    comp = dict(con.execute(f"SELECT mint, min(recv) FROM curve_completes WHERE {ALLOWED} GROUP BY 1").fetchall())
    con.execute("CREATE TEMP TABLE m AS SELECT * FROM cr")
    print("tokens (non-Mayhem, created in allowed segment):", len(cr), flush=True)
    tr = con.execute(f"""SELECT t.mint, t.recv, t.buy, hash(t.usr) u, t.vsol, t.vtok FROM curve_trades t JOIN m USING (mint)
                         WHERE {ALLOWED.replace('recv', 't.recv')} AND abs(t.vsol - t.rsol - 30) < 0.01
                         ORDER BY t.mint, t.recv, t.rowid""").df()
    print("trusted trades", len(tr), flush=True)
    seginfo = dict(zip(cr.mint, cr.seg))
    ctime = dict(zip(cr.mint, cr.ct))
    cfgs, ctrl = configs()
    allc = cfgs + ctrl
    lev_desc = sorted(set(GRID))
    desc_pass = {L: [0, 0] for L in lev_desc}       # [entered band from below, reached L within 600 s]
    desc_sell = {L: [0, 0, 0, 0] for L in lev_desc}  # [n in [.95L,L), sells there, n in [L,1.05L), sells there]
    ath_rows = []
    trades = []
    bounds = np.flatnonzero(np.r_[True, tr.mint.to_numpy()[1:] != tr.mint.to_numpy()[:-1], True])
    M = tr.mint.to_numpy()
    Tall, Ball, Uall, VSall, VTall = (tr.recv.to_numpy(), tr.buy.to_numpy(), tr.u.to_numpy(),
                                      tr.vsol.to_numpy(), tr.vtok.to_numpy())
    del tr
    for bi in range(len(bounds) - 1):
        i0, i1 = bounds[bi], bounds[bi + 1]
        m = M[i0]
        sg = seginfo[m]
        s0, s1 = segs[sg]
        T = Tall[i0:i1]
        keep = (T >= s0) & (T <= s1)
        T, B, U, vs, vt = T[keep], Ball[i0:i1][keep], Uall[i0:i1][keep], VSall[i0:i1][keep], VTall[i0:i1][keep]
        if len(T) < 2:
            continue
        tc = comp.get(m)
        if tc is not None and not (s0 <= tc <= s1):
            tc = None if tc > s1 else tc
        mc = vs / vt * 1e9 * sc[np.clip(np.searchsorted(st, T, side="right") - 2, 0, len(sc) - 1)]
        train = T[0] < OCT3
        pre_ok = np.ones(len(T), bool)
        if tc is not None:
            pre_ok = T < tc
        # ---------------- describe (train tokens only)
        if train:
            pmc = np.r_[np.nan, mc[:-1]]
            for L in lev_desc:
                j = np.flatnonzero(pre_ok & (mc >= 0.95 * L))
                if len(j) and mc[j[0]] < L and T[j[0]] + 600 <= s1 and (j[0] == 0 or mc[j[0] - 1] < 0.95 * L):
                    desc_pass[L][0] += 1
                    w = (T > T[j[0]]) & (T <= T[j[0]] + 600) & pre_ok
                    desc_pass[L][1] += int(np.any(mc[w] >= L))
                inb = pre_ok & (pmc >= 0.95 * L) & (pmc < L)
                ina = pre_ok & (pmc >= L) & (pmc < 1.05 * L)
                d = desc_sell[L]
                d[0] += int(inb.sum()); d[1] += int((~B[inb]).sum())
                d[2] += int(ina.sum()); d[3] += int((~B[ina]).sum())
            if tc is None and T[-1] + 600 <= s1:
                ath_rows.append(mc.max())
        # ---------------- triggers
        # buyers in trailing 10 s
        lo = np.searchsorted(T, T - 10.0, side="right")
        nb = np.empty(len(T), int)
        for i in range(len(T)):
            nb[i] = len(set(U[lo[i]:i + 1][B[lo[i]:i + 1]]))
        for ci, c in enumerate(allc):
            levels = R10 if c["levels"] == "R10" else PLACEBO
            busy_until = -1.0
            cand = []
            for L in levels:
                if c["rule"] in ("A", "B"):
                    lo_, hi_ = L * (1 + c["X"]), L * (1 + c["X"]) * 1.05
                    above = np.flatnonzero(pre_ok & (mc >= L))
                    first_above = above[0] if len(above) else len(T)
                    if c["rule"] == "B":
                        band = np.flatnonzero(pre_ok[:first_above] & (mc[:first_above] >= 0.95 * L))
                        if not len(band):
                            continue
                        rej = np.flatnonzero(mc[band[0]:first_above] <= 0.85 * L)
                        if not len(rej):
                            continue
                        start = band[0] + rej[0]
                    else:
                        start = 0
                    ok = np.flatnonzero(pre_ok & (mc >= lo_) & (mc < hi_) & (nb >= c["N"]))
                    ok = ok[ok >= start]
                    # must be the token's first approach above L(1+X) (no earlier print >= hi_)
                    if len(ok):
                        hi_first = np.flatnonzero(pre_ok & (mc >= hi_))
                        if len(hi_first) and hi_first[0] < ok[0]:
                            continue
                        cand.append((ok[0], L))
                else:
                    ok = np.flatnonzero(pre_ok & (mc >= 0.85 * L) & (mc < 0.88 * L) & (nb >= c["N"]))
                    if len(ok):
                        hi_first = np.flatnonzero(pre_ok & (mc >= 0.88 * L))
                        if len(hi_first) and hi_first[0] < ok[0]:
                            continue
                        cand.append((ok[0], L))
            for i, L in sorted(cand):
                t = T[i]
                if t <= busy_until or t + LAT + c["mh"] > s1:
                    continue
                if c["rule"] == "C":
                    k = np.searchsorted(T, t + LAT, side="right")
                    solpx = sc[np.clip(np.searchsorted(st, t, side="right") - 2, 0, len(sc) - 1)]
                    tp_px = 0.97 * L / solpx / 1e9  # price (SOL/token) at mcap 0.97L, SOL/USD known at decision
                    g, tx, k = exit_path(T, vs, vt, t, tc, 0, c["sl"], c["mh"], tp_px=tp_px)
                else:
                    g, tx, k = exit_path(T, vs, vt, t, tc, c["tp"], c["sl"], c["mh"])
                busy_until = tx + LAT
                trades.append((c["name"], m, float(t), L, float(mc[i]), int(nb[i]), float(t - ctime[m]), float(g)))
        if bi % 20000 == 0:
            print(bi, len(trades), flush=True)
    td = pd.DataFrame(trades, columns=["config", "mint", "t", "level", "mcap_usd", "buyers10", "age", "gross"])
    td.to_parquet(SCRATCH / "round_levels_trades.parquet")
    pd.DataFrame({"ath": ath_rows}).to_parquet(SCRATCH / "round_levels_ath_train.parquet")
    json.dump({"pass": {str(int(k)): v for k, v in desc_pass.items()},
               "sell": {str(int(k)): v for k, v in desc_sell.items()},
               "segments": segs.tolist(), "configs": [c["name"] for c in cfgs],
               "controls": [c["name"] for c in ctrl]},
              open(SCRATCH / "round_levels_desc_raw.json", "w"))
    print("done", len(td))


if __name__ == "__main__":
    main()
