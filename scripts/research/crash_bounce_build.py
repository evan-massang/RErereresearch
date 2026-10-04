"""Crash-bounce (capitulation rebound) on the pump.fun bonding curve: event build + train/validation evaluation.

Hypothesis: mechanical dumps overshoot and remaining organic demand produces a bounce. The bot enters INTO
the crash (1 s after the decision print), before any recovery.

Trigger (first qualifying print per token and variant, all point in time: only trades received at or before it):
  crash  = a sell print whose price is <= (1 - D) x the max print price over the preceding W seconds (inclusive)
  gating = >= 15 distinct non-creator buyers so far, token age >= 30 s, not completed
Variants (5, fixed before any outcome was computed):
  d40_w30     D = 0.40, W = 30 s
  d60_w30     D = 0.60, W = 30 s
  d40_w10     D = 0.40, W = 10 s (fast crash: one big sell or a tight cascade)
  d40_w30_mech  as d40_w30, and the largest seller (SOL) between the window max and the crash print is the creator
                or a launch-block sniper (bought in slot <= create slot + 1): forced / mechanical selling
  d40_w30_dem   as d40_w30, then >= 2 distinct non-creator buyers in the next 5 s; decision at crash + 5 s
Exits (8): TP/SL 20/30, 30/15, 50/30, 100/50 % x max hold 60 s, 300 s. 5 x 8 = 40 configs.
Fills: event_studies.outcomes() (exact constant product, 0.5 SOL, 1.25 % fee per side, 1 s latency, completion).
Tips 0.001 and 0.01 SOL per tx (two tx per trade).
Gaps: token creation, decision and the full 300 s window (+ latency) must lie in one gap-free (<= 60 s) segment.
Splits: train = tokens created Oct 1 before 19:15 UTC (trades capped at 19:15) + created Oct 2 (trades capped at
Oct 3 00:00); validation = tokens created Oct 3 (trades capped at Oct 4 00:00). Holdout never read.

    python scripts/research/crash_bounce_build.py build     # events -> scratch parquet
    python scripts/research/crash_bounce_build.py train     # train table, writes evidence json
    python scripts/research/crash_bounce_build.py validate CONFIG [CONFIG...]   # only configs that passed train
"""
import json
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "research"))
import duckdb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import event_studies as es  # noqa: E402
from pipeline import config  # noqa: E402

es.EXITS = ((0.2, 0.3), (0.3, 0.15), (0.5, 0.3), (1.0, 0.5))
es.MAXHOLDS = (60, 300)
MAXH = max(es.MAXHOLDS)
TIPS = (0.001, 0.01)
MIN_BUYERS, MIN_AGE, DEM_WIN, DEM_N = 15, 30.0, 5.0, 2
VARIANTS = ("d40_w30", "d60_w30", "d40_w10", "d40_w30_mech", "d40_w30_dem")
HOLD0, HOLD1, OCT2, OCT3, OCT4 = 1790882100.0, 1790899200.0, 1790899200.0, 1790985600.0, 1791072000.0
GAP = 60.0
ALLOWED = f"recv < {OCT4} AND NOT (recv >= {HOLD0} AND recv < {HOLD1})"
CHUNKS = [(1790812800.0, HOLD0, HOLD0), (OCT2, OCT2 + 43200, OCT3), (OCT2 + 43200, OCT3, OCT3),
          (OCT3, OCT3 + 43200, OCT4), (OCT3 + 43200, OCT4, OCT4)]
SCRATCH = Path("/tmp/claude-0/-home-user-RErereresearch/f8ba0823-6528-5b3d-92e7-a2d8665674ee/scratchpad")
EVENTS = SCRATCH / "crash_bounce_events.parquet"
EVID = ROOT / "research" / "observations"


def segments(con) -> np.ndarray:
    r = con.execute(f"""WITH t AS (SELECT recv, lag(recv) OVER (ORDER BY recv) p FROM curve_trades WHERE {ALLOWED})
                        SELECT p, recv FROM t WHERE recv - p > {GAP} ORDER BY p""").fetchall()
    lo, hi = con.execute(f"SELECT min(recv), max(recv) FROM curve_trades WHERE {ALLOWED}").fetchone()
    return np.array(list(zip([lo] + [b for _, b in r], [a for a, _ in r] + [hi])))


def seg_of(segs, t):
    i = np.searchsorted(segs[:, 0], t, side="right") - 1
    return (segs[i, 0], segs[i, 1]) if i >= 0 and t <= segs[i, 1] else (None, None)


def detect(g, creator, cslot, ct, tc):
    """Return {variant: (decision_time, info)} for the first trigger of each variant."""
    T, slot, usr, buy, sol = g["recv"], g["slot"], g["usr"], g["buy"], g["sol"]
    px = g["vsol"] / g["vtok"]
    n = len(T)
    found = {}
    snipers, buyers = set(), set()
    dq = {10: deque(), 30: deque()}  # monotonic (index) deques for the rolling max
    for i in range(n):
        if tc is not None and T[i] >= tc:
            break
        u = usr[i]
        if buy[i]:
            if u != creator:
                if slot[i] <= cslot + 1:
                    snipers.add(u)
                buyers.add(u)
        for w, d in dq.items():
            while d and px[d[-1]] <= px[i]:
                d.pop()
            d.append(i)
            while T[d[0]] < T[i] - w:
                d.popleft()
        if buy[i] or len(buyers) < MIN_BUYERS or T[i] - ct < MIN_AGE:
            continue
        for w, D, name in ((30, 0.4, "d40_w30"), (30, 0.6, "d60_w30"), (10, 0.4, "d40_w10")):
            jm = dq[w][0]
            if name not in found and px[i] <= (1 - D) * px[jm]:
                found[name] = (T[i], {"dd": 1 - px[i] / px[jm], "dt_crash": T[i] - T[jm]})
        jm = dq[30][0]
        if px[i] <= 0.6 * px[jm]:
            info = {"dd": 1 - px[i] / px[jm], "dt_crash": T[i] - T[jm]}
            if "d40_w30_mech" not in found:
                sells = {}
                for k in range(jm + 1, i + 1):
                    if not buy[k]:
                        sells[usr[k]] = sells.get(usr[k], 0.0) + sol[k]
                top = max(sells, key=sells.get)
                if top == creator or top in snipers:
                    found["d40_w30_mech"] = (T[i], {**info, "top_seller": "creator" if top == creator else "sniper"})
            if "d40_w30_dem" not in found:
                k = i + 1
                nb = set()
                while k < n and T[k] <= T[i] + DEM_WIN and (tc is None or T[k] < tc):
                    if buy[k] and usr[k] != creator:
                        nb.add(usr[k])
                    k += 1
                if len(nb) >= DEM_N:
                    found["d40_w30_dem"] = (T[i] + DEM_WIN, {**info, "dem_buyers": len(nb)})
        if len(found) == len(VARIANTS):
            break
    return found


def build():
    con = duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
    segs = segments(con)
    print("segments", len(segs), [(round(a), round(b)) for a, b in segs], flush=True)
    comp = dict(con.execute(f"SELECT mint, min(recv) FROM curve_completes WHERE {ALLOWED} GROUP BY 1").fetchall())
    rows, dropped = [], 0
    for a, b, ceil in CHUNKS:
        cr = con.execute("""SELECT mint, any_value(creator) creator, min(recv) ct, min(slot) cslot FROM curve_creates
                            WHERE recv >= ? AND recv < ? GROUP BY 1""", [a, b]).df().set_index("mint")
        tr = con.execute(f"""SELECT mint, recv, slot, usr, buy, sol, vsol, vtok FROM curve_trades
                             WHERE mint IN (SELECT mint FROM curve_creates WHERE recv >= ? AND recv < ?)
                             AND recv < ? AND {ALLOWED} ORDER BY mint, recv, rowid""", [a, b, ceil]).df()
        mints = tr.mint.to_numpy()
        cut = np.flatnonzero(mints[1:] != mints[:-1]) + 1
        bounds = np.concatenate([[0], cut, [len(mints)]])
        cols = {c: tr[c].to_numpy() for c in ("recv", "slot", "usr", "buy", "sol", "vsol", "vtok")}
        del tr
        ne = 0
        for s0, s1 in zip(bounds[:-1], bounds[1:]):
            if s1 - s0 < MIN_BUYERS + 1:
                continue
            m = mints[s0]
            if m not in cr.index:
                continue
            ci = cr.loc[m]
            sa, sb = seg_of(segs, ci.ct)
            if sa is None:
                continue
            g = {c: v[s0:s1] for c, v in cols.items()}
            tc = comp.get(m)
            for name, (t, info) in detect(g, ci.creator, ci.cslot, ci.ct, tc).items():
                if t + es.LATENCY + MAXH + 1 > min(sb, ceil):
                    dropped += 1
                    continue
                o = es.outcomes(g["recv"], g["vsol"], g["vtok"], t, tc)
                if not o:
                    continue
                k = np.searchsorted(g["recv"], t, side="right") - 1
                rows.append({"variant": name, "mint": m, "t": t, "age": t - ci.ct,
                             "mcap": g["vsol"][k] / g["vtok"][k] * 1e9, **info, **o})
                ne += 1
        print(f"chunk {a:.0f}-{b:.0f}: tokens {len(cr)} events {ne} (dropped for gaps so far {dropped})", flush=True)
        del cols, mints
    d = pd.DataFrame(rows)
    d.to_parquet(EVENTS)
    return d


def summary(v):
    v = np.sort(np.asarray(v, float))
    w, l = v[v > 0], v[v <= 0]
    tot = float(v.sum())
    pf = float(w.sum() / -l.sum()) if len(l) and l.sum() < 0 else None
    wo3 = float(v[:-3].sum()) if len(v) > 3 else None
    ok = len(v) >= 50 and tot > 0 and pf is not None and pf > 1.2 and wo3 is not None and wo3 > 0
    return {"n": int(len(v)), "mean": round(float(v.mean()), 4) if len(v) else None, "total": round(tot, 3),
            "pf": round(pf, 3) if pf is not None else None, "wo3": round(wo3, 3) if wo3 is not None else None,
            "win": round(float((v > 0).mean()), 3) if len(v) else None, "pass": bool(ok)}


def split(d, which):
    if which == "train":
        return d[(d.t < HOLD0) | ((d.t >= OCT2) & (d.t < OCT3))]
    return d[(d.t >= OCT3) & (d.t < OCT4)]


def table(d, which):
    s = split(d, which)
    gcols = [c for c in d.columns if c.startswith("g_")]
    out = {}
    for var in VARIANTS:
        x = s[s.variant == var]
        for c in gcols:
            out[f"{var}|{c}"] = {str(tip): summary(x[c].to_numpy() - 2 * tip) for tip in TIPS}
            if which == "train":
                out[f"{var}|{c}"]["by_day_0.001"] = {
                    "oct1": summary(x[x.t < HOLD0][c].to_numpy() - 0.002),
                    "oct2": summary(x[x.t >= OCT2][c].to_numpy() - 0.002)}
    return out


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "build":
        build()
    elif cmd == "train":
        d = pd.read_parquet(EVENTS)
        out = table(d, "train")
        gross = {v: {c: round(float(split(d, "train")[lambda z: z.variant == v][c].mean()), 4)
                     for c in d.columns if c.startswith("g_")} for v in VARIANTS}
        res = {"n_configs": len(out), "note": "train only; validation not looked at unless a config passes",
               "configs": out, "gross_mean_before_tips": gross,
               "event_meta": split(d, "train").groupby("variant")[["dd", "dt_crash", "age", "mcap"]].median().round(3)
               .to_dict(orient="index"),
               "mech_top_seller": split(d, "train")[lambda z: z.variant == "d40_w30_mech"].top_seller.value_counts()
               .to_dict()}
        (EVID / "evidence_crash_bounce_train_20261004.json").write_text(json.dumps(res, indent=1))
        for k, v in sorted(out.items(), key=lambda kv: -kv[1]["0.001"]["mean"]):
            print(f"{k:34} {v['0.001']}  tip.01 mean {v['0.01']['mean']}  oct1 {v['by_day_0.001']['oct1']['mean']}"
                  f" oct2 {v['by_day_0.001']['oct2']['mean']}")
        print("passing:", [k for k, v in out.items() if v["0.001"]["pass"]])
    elif cmd == "validate":
        d = pd.read_parquet(EVENTS)
        out = table(d, "validation")
        sel = {k: out[k] for k in sys.argv[2:]}
        (EVID / "evidence_crash_bounce_validation_20261004.json").write_text(json.dumps(sel, indent=1))
        print(json.dumps(sel, indent=1))
