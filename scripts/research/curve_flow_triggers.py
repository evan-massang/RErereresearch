"""Discrete order-flow event triggers on the pump.fun bonding curve (agent curve_flow, 2026-10-04).

Pre-registered before any outcome was looked at. Four ideas x 2 trigger variants x 4 exits = 32 configs.

  whale      a buy of >= X SOL (X in {3, 5}) by a wallet that is neither the token's creator nor a launch
             sniper (bought in slot <= create slot + 1), and that was already present in the recorded
             curve tape on an earlier UTC day (Oct 2 triggers: seen Oct 1 before the holdout; Oct 3: Oct 1-2).
  absorb     a non-creator sell of >= 2 SOL; the trigger is the first later trade, within N s
             (N in {10, 30}), whose post-trade price is above the price just before the sell. Age >= 30 s.
  accum      a non-creator, non-sniper wallet makes its k-th separate buy (k in {3, 5}) of this token:
             each buy >= 0.2 SOL, consecutive buys >= 2 s apart, no sells by that wallet so far. Age >= 10 s.
  burst      token older than 300 s; >= B distinct first-time buyers of the token (B in {4, 7}) inside a
             30 s window whose first trade follows >= 120 s with no trades on the token.

One trigger per token per variant (the first). Features use only trades received at or before the trigger.
Fills: event_studies.outcomes() (exact constant-product, 0.5 SOL, 1.25% fee per side, 1 s latency,
completion handling). Exits (4): TP/SL 30/15 and 50/20 with 300 s max hold, 100/30 and 200/50 with 1800 s.
Tips 0.001 and 0.01 SOL per tx (2 tx per trade).

Data hygiene: only curve_trades outside the holdout [1790882100, 1790899200) and before 1791072000.
The tape has recording gaps; a trigger is kept only if the token's creation, the trigger and the full
1800 s max-hold window lie inside one gap-free recording segment (no global gap > 60 s).
Splits: train = before holdout + Oct 2; validation = Oct 3.

    python scripts/research/curve_flow_triggers.py           # build events + outcomes, print train only
    python scripts/research/curve_flow_triggers.py --validate CONFIG [CONFIG ...]
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

HOLD0, HOLD1, OCT2, OCT3, OCT4 = 1790882100.0, 1790899200.0, 1790899200.0, 1790985600.0, 1791072000.0
MAXH = 1800
EXIT_COLS = ("g_tp30_sl15_300", "g_tp50_sl20_300", "g_tp100_sl30_1800", "g_tp200_sl50_1800")
VARIANTS = {"whale": (3.0, 5.0), "absorb": (10, 30), "accum": (3, 5), "burst": (4, 7)}
GAP = 60.0
OUT = Path("/tmp/claude-0/-home-user-RErereresearch/f8ba0823-6528-5b3d-92e7-a2d8665674ee/scratchpad/curve_flow_events.parquet")
ALLOWED = f"recv < {OCT4} AND NOT (recv >= {HOLD0} AND recv < {HOLD1})"
# create-time chunks (UTC day halves) and the trade-recv ceiling for each
CHUNKS = [(1790812800.0, HOLD0, HOLD0), (OCT2, OCT2 + 43200, OCT3), (OCT2 + 43200, OCT3, OCT3),
          (OCT3, OCT3 + 21600, OCT4), (OCT3 + 21600, OCT3 + 43200, OCT4),
          (OCT3 + 43200, OCT3 + 64800, OCT4), (OCT3 + 64800, OCT4, OCT4)]


def segments(con) -> np.ndarray:
    r = con.execute(f"""WITH t AS (SELECT recv, lag(recv) OVER (ORDER BY recv) p FROM curve_trades WHERE {ALLOWED})
                        SELECT p, recv FROM t WHERE recv - p > {GAP} ORDER BY p""").fetchall()
    lo, hi = con.execute(f"SELECT min(recv), max(recv) FROM curve_trades WHERE {ALLOWED}").fetchone()
    starts = [lo] + [b for _, b in r]
    ends = [a for a, _ in r] + [hi]
    return np.array(list(zip(starts, ends)))


def seg_end(segs, t):
    i = np.searchsorted(segs[:, 0], t, side="right") - 1
    return (segs[i, 0], segs[i, 1]) if i >= 0 and t <= segs[i, 1] else (None, None)


def detect(g, creator, cslot, ct, tc, day_known):
    """Yield (variant, trigger_index) for the first trigger of each variant on one token's tape."""
    T, slot, usr, buy, sol = g["recv"], g["slot"], g["usr"], g["buy"], g["sol"]
    px = g["vsol"] / g["vtok"]
    n = len(T)
    found = {}
    snipers = set()
    acc = {}  # wallet -> [nbuys, last_t, sold]
    seen_buyers = set()
    first_buy_idx = []  # indices of first-time-buyer trades
    pending = []  # absorption: (sell_index, pre_price)
    for i in range(n):
        if tc is not None and T[i] >= tc:
            break
        u, b, s, age = usr[i], buy[i], sol[i], T[i] - ct
        if u != creator and b and slot[i] <= cslot + 1:
            snipers.add(u)
        # --- absorb: resolve pending large sells
        if pending:
            keep = []
            for (j, pre) in pending:
                for N in VARIANTS["absorb"]:
                    key = ("absorb", N)
                    if key in found or T[i] - T[j] > N:
                        continue
                    if px[i] > pre and age >= 30:
                        found[key] = i
                if T[i] - T[j] <= max(VARIANTS["absorb"]):
                    keep.append((j, pre))
            pending = keep
        if not b and u != creator and s >= 2.0 and i > 0:
            pending.append((i, px[i - 1]))
        # --- whale
        if b and u != creator and u not in snipers and u in day_known:
            for X in VARIANTS["whale"]:
                if ("whale", X) not in found and s >= X:
                    found[("whale", X)] = i
        # --- accum
        if u != creator and u not in snipers:
            a = acc.get(u)
            if not b:
                if a is not None:
                    a[2] = True
            elif s >= 0.2:
                if a is None:
                    acc[u] = [1, T[i], False]
                elif not a[2] and T[i] - a[1] >= 2.0:
                    a[0] += 1
                    a[1] = T[i]
                    if age >= 10:
                        for k in VARIANTS["accum"]:
                            if ("accum", k) not in found and a[0] >= k:
                                found[("accum", k)] = i
        # --- burst
        if b and u not in seen_buyers:
            seen_buyers.add(u)
            first_buy_idx.append(i)
            if age > 300:
                j = np.searchsorted(T, T[i] - 30.0, side="left")
                if j > 0 and T[j] - T[j - 1] >= 120.0:
                    nb = sum(1 for q in first_buy_idx[-50:] if q >= j)
                    for B in VARIANTS["burst"]:
                        if ("burst", B) not in found and nb >= B:
                            found[("burst", B)] = i
        elif b:
            seen_buyers.add(u)
        if len(found) == 8:
            break
    return found


def build():
    con = duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
    segs = segments(con)
    print("segments", [(round(a), round(b)) for a, b in segs], flush=True)
    comp = dict(con.execute(f"SELECT mint, min(recv) FROM curve_completes WHERE {ALLOWED} GROUP BY 1").fetchall())
    known1 = {r[0] for r in con.execute(f"SELECT DISTINCT usr FROM curve_trades WHERE recv < {HOLD0}").fetchall()}
    known2 = known1 | {r[0] for r in con.execute(
        f"SELECT DISTINCT usr FROM curve_trades WHERE recv >= {OCT2} AND recv < {OCT3}").fetchall()}
    rows = []
    for a, b, ceil in CHUNKS:
        cr = con.execute("""SELECT mint, any_value(creator) creator, min(recv) ct, min(slot) cslot FROM curve_creates
                            WHERE recv >= ? AND recv < ? GROUP BY 1""", [a, b]).df().set_index("mint")
        tr = con.execute(f"""SELECT mint, recv, slot, usr, buy, sol, vsol, vtok FROM curve_trades
                             WHERE mint IN (SELECT mint FROM curve_creates WHERE recv >= ? AND recv < ?)
                             AND recv < ? AND {ALLOWED} ORDER BY mint, recv, rowid""", [a, b, ceil]).df()
        day_known = set() if a < OCT2 else (known1 if a < OCT3 else known2)
        mints = tr.mint.to_numpy()
        cut = np.flatnonzero(mints[1:] != mints[:-1]) + 1
        bounds = np.concatenate([[0], cut, [len(mints)]])
        cols = {c: tr[c].to_numpy() for c in ("recv", "slot", "usr", "buy", "sol", "vsol", "vtok")}
        del tr
        ne = 0
        for s0, s1 in zip(bounds[:-1], bounds[1:]):
            m = mints[s0]
            if m not in cr.index:
                continue
            ci = cr.loc[m]
            sa, sb = seg_end(segs, ci.ct)
            if sa is None:
                continue
            g = {c: v[s0:s1] for c, v in cols.items()}
            tc = comp.get(m)
            found = detect(g, ci.creator, ci.cslot, ci.ct, tc, day_known)
            for (kind, p), i in found.items():
                t = g["recv"][i]
                if t + es.LATENCY + MAXH + 1 > sb:  # window must stay inside the gap-free segment
                    continue
                o = es.outcomes(g["recv"], g["vsol"], g["vtok"], t, tc)
                if not o:
                    continue
                rows.append({"kind": kind, "param": p, "mint": m, "t": t, "age": t - ci.ct,
                             "mcap": g["vsol"][i] / g["vtok"][i] * 1e9, **{c: o[c] for c in EXIT_COLS}})
                ne += 1
        print(f"chunk {a:.0f}-{b:.0f}: tokens {len(cr)} events {ne}", flush=True)
    d = pd.DataFrame(rows)
    d.to_parquet(OUT)
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


def configs(d):
    for kind, ps in VARIANTS.items():
        for p in ps:
            for col in EXIT_COLS:
                yield f"{kind}|{p}|{col}", d[(d.kind == kind) & (d.param == p)], col


if __name__ == "__main__":
    if "--validate" in sys.argv:
        want = set(sys.argv[sys.argv.index("--validate") + 1:])
        d = pd.read_parquet(OUT)
        va = d[(d.t >= OCT3) & (d.t < OCT4)]
        res = {}
        for name, sub, col in configs(va):
            if name in want:
                res[name] = {str(tip): summary(sub[col].to_numpy() - 2 * tip) for tip in es.TIPS}
                print(name, res[name])
        p = ROOT / "research/observations/evidence_curve_flow_validation_20261004.json"
        p.write_text(json.dumps({"note": "Validation (Oct 3) looked at once, only for configs passing the bar on train.",
                                 "results": res}, indent=1))
        sys.exit()
    d = build() if "--reuse" not in sys.argv else pd.read_parquet(OUT)
    tr = d[(d.t < HOLD0) | ((d.t >= OCT2) & (d.t < OCT3))]
    res = {}
    for name, sub, col in configs(tr):
        res[name] = {str(tip): summary(sub[col].to_numpy() - 2 * tip) for tip in es.TIPS}
        r = res[name]["0.001"]
        print(f"{name:34} n={r['n']:5} mean={r['mean']} total={r['total']} pf={r['pf']} wo3={r['wo3']} "
              f"win={r['win']} pass={r['pass']} | tip.01 total={res[name]['0.01']['total']}")
    counts = {f"{k}|{p}": {"train": int(((tr.kind == k) & (tr.param == p)).sum()),
                           "validation_events_built_not_scored": int(((d.kind == k) & (d.param == p) & (d.t >= OCT3)).sum())}
              for k, ps in VARIANTS.items() for p in ps}
    (ROOT / "research/observations/evidence_curve_flow_train_20261004.json").write_text(json.dumps(
        {"n_configs": 32, "bar": "n>=50, total>0, PF>1.2, total without best 3 > 0 (tip 0.001 for selection)",
         "event_counts": counts, "train": res}, indent=1))
