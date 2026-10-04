"""Sympathy plays on the pump.fun bonding curve (agent sympathy, 2026-10-04).

Idea: when a "leader" token rips, buy an OTHER, already-existing, still-on-curve, cheaper token that shares its
narrative, before slower traders rotate into it.

Leader triggers (each fires once per leader, the first time, on the leader's own tape):
  mc150   leader's market cap (vsol/vtok*1e9) first reaches 150 SOL
  mc250   ... first reaches 250 SOL
  x3_5m   leader's price is >= 3x its minimum over the trailing 300 s
  migr    leader completes its curve (curve_completes recv)
Narrative match (point in time, name/symbol from curve_creates): same normalised name, same normalised symbol,
or a shared keyword (lowercase alnum word of >= 4 chars from name+symbol, not in a fixed GENERIC stoplist).
Sympathy candidate at trigger time t must:
  - have been created (curve_creates recv) before t, and not be the leader;
  - have a standard curve (first recorded vsol >= 20);
  - have at least one curve trade in the current gap-free segment at or before t (so its state is known and it
    is still on the curve), and not have completed at or before t;
  - have a last market cap (at or before t) below the leader's market cap at t.
Selection: 'largest' = highest market cap at t; 'recent' = most recent trade at or before t.
A candidate token is not re-entered (same trigger/selection) within 1800 s of a previous entry.

Fills: event_studies.outcomes() (exact constant-product, 0.5 SOL, 1.25% fee/side, 1 s latency, TP/SL on later
prints, max hold, completion handling). Tips 0.001 and 0.01 SOL per tx (2 tx per trade).
Exits: tp30/sl15 300 s, tp50/sl20 300 s, tp100/sl30 1800 s, tp200/sl50 1800 s.
Grid: 4 triggers x 2 selections x 4 exits = 32 configs.

Data hygiene: only curve_trades outside the holdout [1790882100, 1790899200) and before 1791072000. Gap-free
segments: no global gap between consecutive trades > 60 s (the holdout boundary also splits). The leader's
creation, trigger and trigger+1+1800 s must lie in one segment (so 'first time' is real and the outcome window
is fully recorded).
Splits: train = before holdout + Oct 2; validation = Oct 3.

    python scripts/research/sympathy_plays.py                       # train only
    python scripts/research/sympathy_plays.py --validate CFG [...]  # validation, for configs passing on train
"""
import json
import re
import sys
from collections import defaultdict
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
MAXH, GAP, REENTRY = 1800, 60.0, 1800
EXIT_COLS = ("g_tp30_sl15_300", "g_tp50_sl20_300", "g_tp100_sl30_1800", "g_tp200_sl50_1800")
TRIGGERS = ("mc150", "mc250", "x3_5m", "migr")
SELECTIONS = ("largest", "recent")
ALLOWED = f"recv < {OCT4} AND NOT (recv >= {HOLD0} AND recv < {HOLD1})"
SCRATCH = Path("/tmp/claude-0/-home-user-RErereresearch/f8ba0823-6528-5b3d-92e7-a2d8665674ee/scratchpad")
OUT = SCRATCH / "sympathy_trades.parquet"
GENERIC = set("""coin coins meme memes pump pumps this that with just best test good first solana token tokens like
live from will your real life world super ultra moon money cash trade trader project company currency official
have what when more only make love free time next last back over dont about here they them their then than some
been were sell fees pair paired bonded https http went left right hope rich data index tech king black green
viral community rocket giga chad based degen gonna wanna dollar dollars million billion still into make made
very much than year years today daily season return returns launch launched mode mayhem chain onchain crypto
bitcoin btc6 shit fuck fucking baby little the and for you our""".split())


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def keys(name, sym):
    k = set()
    n, s = norm(name), norm(sym)
    if n:
        k.add("n:" + n)
    if s:
        k.add("s:" + s)
    for w in re.split(r"[^a-z0-9]+", f"{name or ''} {sym or ''}".lower()):
        if len(w) >= 4 and w not in GENERIC and not w.isdigit():
            k.add("w:" + w)
    return k


def segments(con):
    r = con.execute(f"""WITH t AS (SELECT recv, lag(recv) OVER (ORDER BY recv) p FROM curve_trades WHERE {ALLOWED})
                        SELECT p, recv FROM t WHERE recv - p > {GAP} ORDER BY p""").fetchall()
    lo, hi = con.execute(f"SELECT min(recv), max(recv) FROM curve_trades WHERE {ALLOWED}").fetchone()
    starts, ends = [lo] + [b for _, b in r], [a for a, _ in r] + [hi]
    return np.array(list(zip(starts, ends)))


def seg_of(segs, t):
    i = np.searchsorted(segs[:, 0], t, side="right") - 1
    return (segs[i, 0], segs[i, 1]) if i >= 0 and t <= segs[i, 1] else (None, None)


def build():
    con = duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
    con.execute("SET threads TO 2; SET memory_limit = '3GB'")
    segs = segments(con)
    print("segments:", [(round(a), round(b), round((b - a) / 3600, 2)) for a, b in segs], flush=True)
    cr = con.execute(f"""SELECT mint, min(recv) ct, any_value(name) AS name, any_value(symbol) AS sym FROM curve_creates
                         WHERE {ALLOWED} GROUP BY 1 ORDER BY ct""").df()
    cr["mid"] = np.arange(len(cr), dtype=np.int32)
    mid_of = dict(zip(cr.mint, cr.mid))
    comp = {mid_of[m]: t for m, t in con.execute(f"SELECT mint, min(recv) FROM curve_completes WHERE {ALLOWED} GROUP BY 1").fetchall()
            if m in mid_of}
    con.register("crm", cr[["mint", "mid"]])
    tr = con.execute(f"""SELECT c.mid, t.recv, t.vsol, t.vtok FROM curve_trades t JOIN crm c USING (mint)
                         WHERE {ALLOWED.replace('recv', 't.recv')} AND t.vtok > 0 ORDER BY c.mid, t.recv, t.rowid""").df()
    mids = tr.mid.to_numpy()
    T, VS, VT = tr.recv.to_numpy(), tr.vsol.to_numpy(), tr.vtok.to_numpy()
    del tr
    bounds = np.searchsorted(mids, np.arange(len(cr) + 1))
    print("trades", len(T), flush=True)

    def tape(m):
        a, b = bounds[m], bounds[m + 1]
        return T[a:b], VS[a:b], VT[a:b]

    std = np.array([bounds[m + 1] > bounds[m] and VS[bounds[m]] >= 20 for m in range(len(cr))])
    ct = cr.ct.to_numpy()
    # --- leader triggers
    trig = []  # (kind, leader mid, t, leader mcap)
    for m in range(len(cr)):
        if not std[m]:
            continue
        t_, vs, vt = tape(m)
        s0, s1 = seg_of(segs, ct[m])
        if s0 is None:
            continue
        tc = comp.get(m)
        ok = (t_ <= s1) & ((t_ < tc) if tc is not None else True)
        px = vs / vt
        mc = px * 1e9
        for kind, X in (("mc150", 150), ("mc250", 250)):
            h = np.nonzero(ok & (mc >= X))[0]
            if len(h):
                trig.append((kind, m, t_[h[0]], mc[h[0]]))
        # trailing 300 s min (inclusive) via searchsorted + per-row min over a short window
        lo = np.searchsorted(t_, t_ - 300, side="left")
        cm = np.minimum.accumulate(px)  # cheap pre-filter: 3x over all-time min
        cand = np.nonzero(ok & (px >= 3 * cm))[0]
        for i in cand:
            if px[i] >= 3 * px[lo[i]:i + 1].min():
                trig.append(("x3_5m", m, t_[i], mc[i]))
                break
        if tc is not None and s0 <= tc <= s1:
            k = np.searchsorted(t_, tc, side="left")
            if k:
                trig.append(("migr", m, tc, mc[k - 1]))
    print("triggers", pd.Series([x[0] for x in trig]).value_counts().to_dict(), flush=True)
    # --- narrative index
    kidx = defaultdict(list)
    lkeys = []
    for m, (n, s) in enumerate(zip(cr.name, cr.sym)):
        k = keys(n, s)
        lkeys.append(k)
        if std[m]:
            for x in k:
                kidx[x].append(m)
    rows, last_entry = [], {}
    stats = defaultdict(int)
    for kind, L, t, lmc in sorted(trig, key=lambda x: x[2]):
        s0, s1 = seg_of(segs, t)
        if s0 is None or t + es.LATENCY + MAXH + 1 > s1:
            stats[kind + "_window_out"] += 1
            continue
        stats[kind + "_kept"] += 1
        cands = set()
        for x in lkeys[L]:
            cands.update(kidx.get(x, ()))
        cands.discard(L)
        info = []
        for c in cands:
            if ct[c] >= t:
                continue
            tc = comp.get(c)
            if tc is not None and tc <= t:
                continue
            t_, vs, vt = tape(c)
            k = np.searchsorted(t_, t, side="right")
            if k == 0 or t_[k - 1] < s0:
                continue
            cmc = vs[k - 1] / vt[k - 1] * 1e9
            if cmc >= lmc:
                continue
            match = "name" if ("n:" + norm(cr.name[L])) in lkeys[c] else "sym" if ("s:" + norm(cr.sym[L])) in lkeys[c] else "kw"
            info.append((c, cmc, t_[k - 1], match))
        if not info:
            continue
        stats[kind + "_with_cands"] += 1
        for sel in SELECTIONS:
            c, cmc, lt, match = max(info, key=(lambda x: x[1]) if sel == "largest" else (lambda x: x[2]))
            if t - last_entry.get((kind, sel, c), -1e18) < REENTRY:
                continue
            t_, vs, vt = tape(c)
            o = es.outcomes(t_, vs, vt, t, comp.get(c))
            if not o:
                continue
            last_entry[(kind, sel, c)] = t
            rows.append({"trigger": kind, "sel": sel, "leader": cr.mint[L], "leader_name": cr.name[L], "t": t,
                         "leader_mc": lmc, "sym": cr.mint[c], "sym_name": cr.name[c], "sym_mc": cmc,
                         "sym_age": t - ct[c], "sym_idle": t - lt, "match": match, "n_cands": len(info),
                         **{col: o[col] for col in EXIT_COLS}})
    print(dict(stats), flush=True)
    d = pd.DataFrame(rows)
    d.to_parquet(OUT)
    return d


def summary(v):
    v = np.sort(np.asarray(v, dtype=float))
    w, l = v[v > 0], v[v <= 0]
    return {"n": int(len(v)), "total": round(float(v.sum()), 3), "exp": round(float(v.mean()), 4) if len(v) else None,
            "pf": round(float(w.sum() / -l.sum()), 3) if len(l) and l.sum() < 0 else None,
            "wo3": round(float(v[:-3].sum()), 3) if len(v) > 3 else None,
            "win": round(float((v > 0).mean()), 3) if len(v) else None}


def passes(s):
    return s["n"] >= 50 and s["total"] > 0 and (s["pf"] or 0) > 1.2 and (s["wo3"] or -1) > 0


def table(d, split):
    out = {}
    for kind in TRIGGERS:
        for sel in SELECTIONS:
            g = d[(d.trigger == kind) & (d.sel == sel)]
            for col in EXIT_COLS:
                cfg = f"{kind}|{sel}|{col}"
                out[cfg] = {f"tip{tip}": summary(g[col].to_numpy() - 2 * tip) for tip in es.TIPS}
                out[cfg]["pass_0.001"] = passes(out[cfg]["tip0.001"])
                out[cfg]["pass_0.01"] = passes(out[cfg]["tip0.01"])
    return out


if __name__ == "__main__":
    d = pd.read_parquet(OUT) if ("--cached" in sys.argv or "--validate" in sys.argv) and OUT.exists() else build()
    tr = d[(d.t < HOLD0) | ((d.t >= OCT2) & (d.t < OCT3))]
    if "--validate" in sys.argv:
        cfgs = sys.argv[sys.argv.index("--validate") + 1:]
        va = d[(d.t >= OCT3) & (d.t < OCT4)]
        res = {c: v for c, v in table(va, "validation").items() if c in cfgs}
        print(json.dumps(res, indent=1))
        (ROOT / "research/observations/evidence_sympathy_validation_20261004.json").write_text(json.dumps(res, indent=1))
        sys.exit()
    res = table(tr, "train")
    for k, v in sorted(res.items(), key=lambda kv: -(kv[1]["tip0.001"]["exp"] or -9)):
        print(f"{k:42} {v['tip0.001']}  pass={v['pass_0.001']}/{v['pass_0.01']}")
    extra = {"n_configs": len(res), "train_rows": int(len(tr)),
             "by_day": {k: {"n": int(len(g)), "exp_tp50_0.001": round(float(g['g_tp50_sl20_300'].mean() - 0.002), 4)}
                        for k, g in tr.groupby(np.where(tr.t < HOLD0, "oct1", "oct2"))},
             "match_mix": tr.match.value_counts().to_dict()}
    print(extra)
    (ROOT / "research/observations/evidence_sympathy_train_20261004.json").write_text(json.dumps({"meta": extra, "configs": res}, indent=1))
