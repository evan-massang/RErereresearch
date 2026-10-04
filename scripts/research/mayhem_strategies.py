"""Mayhem Mode strategy tests (agent family). Train-only by default; validation only for named configs.

Agent wallet: BwWK17cbHxwWBKZkUYvzxLcNQ1YVyaFezduWbtm2de6s (see mayhem_agent.py / evidence_mayhem_agent.json).
Mayhem flag per mint: data/processed/mayhem_flags.parquet (mayhem_flags.py, PumpPortal create messages).

Strategies (each fires once per token, first qualifying moment, point-in-time features only):
  fade_sell_V   agent SELL whose own price jump is <= -25% (log), token age 5-300 s, vsol after it >= V SOL.
  ride_buy_V    agent BUY whose own price jump is >= +20% (log), token age 5-300 s, vsol after it >= V SOL.
  post_agent_R  the agent has traded >= 10 times and then been silent 120 s (trigger = last agent trade + 120 s),
                age <= 1800 s, real SOL in the curve (rsol) >= R and vsol >= 5 at the trigger.
  rsol_cross_R  real SOL in the curve first reaches R within 600 s of creation (Mayhem tokens; non-Mayhem run as
                the matched comparison, same rule).
V in (5, 15); R in (2, 8) for post_agent and (10, 30) for rsol_cross. Exits: TP30/SL15 300 s, TP50/SL20 300 s,
TP100/SL30 1800 s, TP200/SL50 1800 s. 4 strategies x 2 params x 4 exits = 32 Mayhem configs, + 8 non-Mayhem
comparison configs = 40 configs evaluated on train.

Fills: event_studies.outcomes() exit rule and rt() (exact constant product on the recorded curve state, 0.5 SOL, 1.25% fee per side,
1 s latency, TP/SL decided on prints, completion handled). Non-agent trades on Mayhem curves were verified to obey
constant product against the previous recorded state (k ratio 1.0000 from the 1st to the 99.9th percentile), so the
recorded state is a valid fill price between agent ticks; agent ticks rescale virtual SOL and are taken as recorded.
Mayhem curves are NOT backed by vsol: agent ticks move virtual SOL while real SOL (rsol) is drained by agent sells
(rsol ~ 0 when the agent stops), so every exit payout is capped by the real SOL in the curve.
std: exit into the recorded state, cap = recorded rsol (conservative). own_impact: exit into the recorded state plus
our own buy (vs1 + x, vt1 - tok), cap = rsol + our deposit (optimistic). no_reserve_cap: plain rt() for reference.
A config must pass under std AND own_impact.
Tips 0.001 and 0.01 SOL per transaction (2 per trade).
Gap rule: token creation, trigger and the full 1801 s window lie inside one gap-free segment (no global gap > 60 s)
and inside one split window.

    python scripts/research/mayhem_strategies.py                 # train
    python scripts/research/mayhem_strategies.py --validate CFG  # validation for named configs only
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts/research"))
import duckdb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import event_studies as es  # noqa: E402

AGENT = "BwWK17cbHxwWBKZkUYvzxLcNQ1YVyaFezduWbtm2de6s"
HOLD0, HOLD1, OCT3, OCT4 = 1790882100.0, 1790899200.0, 1790985600.0, 1791072000.0
WINDOWS = {"train": [(0.0, HOLD0), (HOLD1, OCT3)], "validation": [(OCT3, OCT4)]}
ALLOWED = f"recv < {OCT4} AND NOT (recv >= {HOLD0} AND recv < {HOLD1})"
GAP, MAXH = 60.0, 1800.0
EXITS = ["g_tp30_sl15_300", "g_tp50_sl20_300", "g_tp100_sl30_1800", "g_tp200_sl50_1800"]
TIPS = (0.001, 0.01)
OUT = ROOT / "research/observations"


def segments(con):
    r = con.execute(f"""WITH t AS (SELECT recv, lag(recv) OVER (ORDER BY recv) p FROM curve_trades WHERE {ALLOWED})
                        SELECT p, recv FROM t WHERE recv - p > {GAP} ORDER BY p""").fetchall()
    lo, hi = con.execute(f"SELECT min(recv), max(recv) FROM curve_trades WHERE {ALLOWED}").fetchone()
    return np.array(list(zip([lo] + [b for _, b in r], [a for a, _ in r] + [hi])))


def bounds(segs, wins, t):
    """(start, end) of the segment-and-window containing t, or None."""
    i = np.searchsorted(segs[:, 0], t, side="right") - 1
    if i < 0 or t > segs[i, 1]:
        return None
    for a, b in wins:
        if a <= t < b:
            return max(a, segs[i, 0]), min(b, segs[i, 1])
    return None


def detect(T, ag, buy, vs, vt, rs, ct, may):
    """Yield (config_base, trigger_index, trigger_time) using only rows <= trigger."""
    lp = np.log(vs / vt)
    jump = np.r_[np.nan, np.diff(lp)]
    age = T - ct
    found = {}
    if may:
        for i in np.nonzero(ag)[0]:
            if not (5 <= age[i] <= 300):
                continue
            for V in (5, 15):
                if vs[i] < V:
                    continue
                if not buy[i] and jump[i] <= -0.25 and f"fade_sell_{V}" not in found:
                    found[f"fade_sell_{V}"] = (i, T[i])
                if buy[i] and jump[i] >= 0.20 and f"ride_buy_{V}" not in found:
                    found[f"ride_buy_{V}"] = (i, T[i])
        ai = np.nonzero(ag)[0]
        for n, j in enumerate(ai):
            if n + 1 < 10:
                continue
            nxt = T[ai[n + 1]] if n + 1 < len(ai) else np.inf
            ts = T[j] + 120.0
            if nxt <= ts:
                continue
            if ts - ct > 1800:
                break
            k = np.searchsorted(T, ts, side="right") - 1  # state at trigger (no agent trade after j up to ts)
            for R in (2, 8):
                if rs[k] >= R and vs[k] >= 5 and f"post_agent_{R}" not in found:
                    found[f"post_agent_{R}"] = (k, ts)
            break  # first silence only
    for R in (10, 30):
        idx = np.nonzero((rs >= R) & (age <= 600))[0]
        if len(idx):
            found[f"rsol_cross_{R}" + ("" if may else "_nonmayhem")] = (idx[0], T[idx[0]])
    return found


def rt_cap(vs0, vt0, vs1, vt1, rs1, own):
    """Round trip of SIZE. Exit sells into the recorded state (std) or the recorded state plus our own buy (own),
    and the payout is capped by the real SOL in the curve: rs1 (std) or rs1 + our deposit (own)."""
    x = es.SIZE * (1 - es.FEE)
    tok = vt0 - vs0 * vt0 / (vs0 + x)
    a, b, cap = (vs1 + x, vt1 - tok, rs1 + x) if own else (vs1, vt1, rs1)
    if b <= 0:
        return np.nan
    return min(a - a * b / (b + tok), max(cap, 0.0)) * (1 - es.FEE) - es.SIZE


def outcomes(T, vs, vt, rs, t, tc):
    """event_studies.outcomes exit rule (TP/SL on prints, LATENCY after the decision print, max hold, completion),
    with the real-reserve cap and both exit-state models."""
    o = {}
    k = np.searchsorted(T, t + es.LATENCY, side="right")
    if k == 0:
        return o
    vs0, vt0 = vs[k - 1], vt[k - 1]
    p0 = vs0 / vt0
    for col in EXITS:
        a, b, mh = col.split("_")[1:]
        a, b, mh = int(a[2:]) / 100, int(b[2:]) / 100, int(mh)
        end = t + es.LATENCY + mh
        lim = np.searchsorted(T, min(end, tc), side="left") if tc is not None and tc <= end else np.searchsorted(T, end, side="right")
        lim = max(lim, k)
        px = vs[k:lim] / vt[k:lim]
        hit = np.nonzero((px >= p0 * (1 + a)) | (px <= p0 * (1 - b)))[0]
        e = np.searchsorted(T, T[k + hit[0]] + es.LATENCY, side="right") if len(hit) else lim
        if tc is not None:
            e = min(e, np.searchsorted(T, tc, side="left"))
        e = max(e, k)
        o[col] = rt_cap(vs0, vt0, vs[e - 1], vt[e - 1], rs[e - 1], False)
        o["own_" + col] = rt_cap(vs0, vt0, vs[e - 1], vt[e - 1], rs[e - 1], True)
        o["nocap_" + col] = es.rt(vs0, vt0, vs[e - 1], vt[e - 1])
    return o


def run(split):
    con = duckdb.connect(str(ROOT / "data/market.duckdb"), read_only=True)
    con.execute("SET memory_limit='3GB'; SET threads=2")
    flags = pd.read_parquet(ROOT / "data/processed/mayhem_flags.parquet")
    may = dict(zip(flags.mint, flags.is_mayhem))
    segs = segments(con)
    wins = WINDOWS[split]
    cr = con.execute("SELECT mint, min(recv) ct FROM curve_creates GROUP BY 1").df()
    comp = dict(con.execute("SELECT mint, min(recv) FROM curve_completes GROUP BY 1").fetchall())
    rows = []
    for a, b in wins:
        lo = max(a, segs[0, 0])
        # chunk creations by 6 h to bound memory
        for c0 in np.arange(lo, b, 21600.0):
            c1 = min(c0 + 21600.0, b)
            mints = cr[(cr.ct >= c0) & (cr.ct < c1)]
            mints = mints[mints.mint.map(lambda m: may.get(m) is not None)]
            if mints.empty:
                continue
            con.register("mm", mints)
            tr = con.execute(f"""SELECT t.mint, t.recv, t.slot, t.usr = '{AGENT}' ag, t.buy, t.vsol, t.vtok, t.rsol
                                 FROM curve_trades t JOIN mm USING (mint)
                                 WHERE {ALLOWED} AND t.recv < {b} ORDER BY t.mint, t.slot, t.recv""").df()
            con.unregister("mm")
            ctd = dict(zip(mints.mint, mints.ct))
            for m, g in tr.groupby("mint", sort=False):
                ct = ctd[m]
                bd = bounds(segs, wins, ct)
                if bd is None:
                    continue
                T = np.maximum.accumulate(g.recv.to_numpy())
                vs, vt = g.vsol.to_numpy(), g.vtok.to_numpy()
                tc = comp.get(m)
                for name, (i, t) in detect(T, g.ag.to_numpy(), g.buy.to_numpy(), vs, vt, g.rsol.to_numpy(), ct,
                                           bool(may[m])).items():
                    if t + es.LATENCY + MAXH + 1 > bd[1] or (tc is not None and t >= tc):
                        continue
                    rs = g.rsol.to_numpy()
                    o = outcomes(T, vs, vt, rs, t, tc)
                    if not o:
                        continue
                    rows.append({"cfg": name, "mint": m, "t": t, "age": t - ct, "vsol": vs[i], "rsol": rs[i],
                                 "mayhem": bool(may[m]), **o})
            print(split, round(c0), len(tr), "events", len(rows), flush=True)
            del tr
    return pd.DataFrame(rows)


def summary(v):
    v = np.sort(v[~np.isnan(v)])
    w, l = v[v > 0], v[v <= 0]
    return {"n": int(len(v)), "total": round(float(v.sum()), 3), "exp": round(float(v.mean()), 4) if len(v) else None,
            "pf": round(float(w.sum() / -l.sum()), 3) if len(l) and l.sum() < 0 else None,
            "wo3": round(float(v[:-3].sum()), 3) if len(v) > 3 else None,
            "win": round(float((v > 0).mean()), 3) if len(v) else None}


def passes(s):
    return s["n"] >= 50 and s["total"] > 0 and (s["pf"] or 0) > 1.2 and (s["wo3"] or -1) > 0


def table(d):
    out = {}
    for base in sorted(d.cfg.unique()):
        x = d[d.cfg == base]
        for col in EXITS:
            for tip in TIPS:
                out[f"{base}|{col}|{tip}"] = {"std": summary(x[col].to_numpy() - 2 * tip),
                                              "own_impact": summary(x["own_" + col].to_numpy() - 2 * tip),
                                              "no_reserve_cap": summary(x["nocap_" + col].to_numpy() - 2 * tip)}
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate", nargs="*")
    args = ap.parse_args()
    if args.validate is None:
        d = run("train")
        d.to_parquet(ROOT / "data/processed/mayhem_events_train.parquet")
        out = table(d)
        out["_meta"] = {"configs": 40, "mayhem_configs": 32, "split": "train",
                        "passing": [k for k, v in out.items() if k != "_meta" and passes(v["std"]) and passes(v["own_impact"])]}
        (OUT / "evidence_mayhem_strategies_train.json").write_text(json.dumps(out, indent=1))
        for k, v in out.items():
            if k.endswith("|0.001"):
                print(f"{k:44} {v['std']}  own {v['own_impact']['exp']}")
        print("passing (both fill models, train):", out["_meta"]["passing"])
    else:
        d = run("validation")
        d = d[d.cfg.isin({c.split("|")[0] for c in args.validate})]
        out = {k: v for k, v in table(d).items() if k.rsplit("|", 1)[0] in {c.rsplit("|", 1)[0] if c.count("|") == 2 else c for c in args.validate}}
        (OUT / "evidence_mayhem_strategies_validation.json").write_text(json.dumps(out, indent=1))
        print(json.dumps(out, indent=1))
