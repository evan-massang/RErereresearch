"""Narrative-cluster heat (agent narrative_cluster, 2026-10-05).

Idea: when several NEW launches by different creators share a distinctive keyword within a short window, a
narrative is heating up. Buy the cluster's EARLY LEADER at the moment the cluster forms, before any member has
pumped (unlike the failed sympathy test, which bought old cheap copies after a leader had already pumped).

Rule (fixed before any outcome was computed):
  keywords   lowercase alnum words of >= 4 chars from name + symbol (curve_creates), not all digits, not in the
             sympathy_plays.GENERIC stoplist (same normalisation as sympathy_plays.keys, word keys only).
  launches   curve_creates outside the off-limits ranges, first create per mint, Mayhem tokens excluded
             (mayhem_flags.is_mayhem == True).
  cluster    keyword w FORMS at the create time t of a launch carrying w when the launches carrying w with create
             time in [t - 600 s, t] come from >= K distinct creators (K in {3, 4}). One trigger per keyword per
             1800 s (a keyword that formed a cluster cannot re-fire for 1800 s).
  leader     among the cluster's launches (create in [t-600, t]): not completed at t, last curve state at or
             before t trusted (|vsol - rsol - 30| < 0.01), market cap (vsol/vtok*1e9) at t <= 80 SOL.
             sel 'first'  = earliest created;
             sel 'buyers' = most distinct non-creator buyer wallets in trades at or before t;
             sel 'inflow' = largest non-creator net SOL inflow (buys - sells) at or before t.
             Ties -> earliest created.
  fills      event_studies.outcomes(): exact constant-product, 0.5 SOL, 1.25 % fee/side, 1 s latency, TP/SL on
             later prints, max hold, completion handling. Tips 0.001 / 0.01 SOL per tx (2 tx per trade).
  exits      tp30/sl15 300 s, tp50/sl20 300 s, tp100/sl30 1800 s, tp200/sl50 1800 s.
  re-entry   same token not re-entered within 1800 s for the same (K, sel).
Grid: 2 K x 3 sel x 4 exits = 24 configs.

Data hygiene: trades only outside [1790882100, 1790899200) and before 1791072000. Gap-free segments (no global
trade gap > 60 s; the holdout boundary also splits). [t - 600, t + 1 + 1800 + 1] must lie in one segment (the
cluster window and the outcome window are fully recorded). Curve states are only trusted while
|vsol - rsol - 30| < 0.01; once a token's state turns untrusted it stays so (checked), so a trade whose leader
turns untrusted before its outcome window ends is flagged (`untrusted_in_window`) and excluded from the primary
results (reported separately).
Splits: train = recv < 1790882100 or [1790899200, 1790985600); validation = [1790985600, 1791072000).

    python scripts/research/narrative_cluster_build.py                # build + train table
    python scripts/research/narrative_cluster_build.py --validate CFG  # validation for train-passing configs
"""
import json
import re
import sys
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "research"))
import duckdb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import event_studies as es  # noqa: E402
from sympathy_plays import GENERIC, segments, seg_of, summary, passes, ALLOWED  # noqa: E402
from pipeline import config  # noqa: E402

HOLD0, OCT2, OCT3, OCT4 = 1790882100.0, 1790899200.0, 1790985600.0, 1791072000.0
WIN, COOLDOWN, REENTRY, MAXH, CAP = 600.0, 1800.0, 1800.0, 1800, 80.0
KS = (3, 4)
SELECTIONS = ("first", "buyers", "inflow")
EXIT_COLS = ("g_tp30_sl15_300", "g_tp50_sl20_300", "g_tp100_sl30_1800", "g_tp200_sl50_1800")
SCRATCH = Path("/tmp/claude-0/-home-user-RErereresearch/f8ba0823-6528-5b3d-92e7-a2d8665674ee/scratchpad")
OUT = SCRATCH / "narrative_cluster_trades.parquet"
EVID = ROOT / "research/observations"


def words(name, sym):
    k = set()
    for w in re.split(r"[^a-z0-9]+", f"{name or ''} {sym or ''}".lower()):
        if len(w) >= 4 and w not in GENERIC and not w.isdigit():
            k.add(w)
    return k


def build():
    con = duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
    con.execute("SET threads TO 2; SET memory_limit = '3GB'")
    segs = segments(con)
    mf = pd.read_parquet(config.path("data") / "processed" / "mayhem_flags.parquet")
    mayhem = set(mf.mint[mf.is_mayhem == True])  # noqa: E712
    cr = con.execute(f"""SELECT mint, min(recv) ct, arg_min(name, recv) AS name, arg_min(symbol, recv) AS sym,
                                arg_min(creator, recv) AS creator
                         FROM curve_creates WHERE {ALLOWED} GROUP BY 1 ORDER BY ct""").df()
    n_all = len(cr)
    cr = cr[~cr.mint.isin(mayhem)].reset_index(drop=True)
    print("creates", n_all, "non-mayhem", len(cr), flush=True)
    cr["mid"] = np.arange(len(cr), dtype=np.int32)
    mid_of = dict(zip(cr.mint, cr.mid))
    comp = {mid_of[m]: t for m, t in con.execute(f"SELECT mint, min(recv) FROM curve_completes WHERE {ALLOWED} GROUP BY 1").fetchall()
            if m in mid_of}
    con.register("crm", cr[["mint", "mid", "creator"]])
    tr = con.execute(f"""SELECT c.mid, t.recv, t.vsol, t.vtok, abs(t.vsol - t.rsol - 30) < 0.01 AS ok, t.buy, t.sol,
                                hash(t.usr) AS u, t.usr = c.creator AS isdev
                         FROM curve_trades t JOIN crm c USING (mint)
                         WHERE {ALLOWED.replace('recv', 't.recv')} AND t.vtok > 0 ORDER BY c.mid, t.recv, t.rowid""").df()
    mids = tr.mid.to_numpy()
    T, VS, VT, OK = tr.recv.to_numpy(), tr.vsol.to_numpy(), tr.vtok.to_numpy(), tr.ok.to_numpy()
    BUY, SOL, U, DEV = tr.buy.to_numpy(), tr.sol.to_numpy(), tr.u.to_numpy(), tr.isdev.to_numpy()
    del tr
    bounds = np.searchsorted(mids, np.arange(len(cr) + 1))
    print("trades", len(T), flush=True)
    ct, creator = cr.ct.to_numpy(), cr.creator.to_numpy()
    kw = [words(n, s) for n, s in zip(cr.name, cr.sym)]

    # --- cluster formation (point in time: only creates at or before t)
    recent = defaultdict(deque)
    last_fire = {K: {} for K in KS}
    trig = []  # (K, keyword, t, members)
    stats = defaultdict(int)
    for m in range(len(cr)):
        t = ct[m]
        for w in kw[m]:
            dq = recent[w]
            dq.append(m)
            while dq and ct[dq[0]] < t - WIN:
                dq.popleft()
            nc = len({creator[x] for x in dq})
            for K in KS:
                if nc >= K and t - last_fire[K].get(w, -1e18) >= COOLDOWN:
                    last_fire[K][w] = t
                    trig.append((K, w, t, list(dq)))
    print("cluster triggers", pd.Series([x[0] for x in trig]).value_counts().to_dict(), flush=True)

    rows, last_entry = [], {}
    for K, w, t, members in trig:
        s0, s1 = seg_of(segs, t)
        if s0 is None or t - WIN < s0 or t + es.LATENCY + MAXH + 1 > s1:
            stats[f"K{K}_window_out"] += 1
            continue
        stats[f"K{K}_kept"] += 1
        info = []
        for c in members:
            tc = comp.get(c)
            if tc is not None and tc <= t:
                continue
            a, b = bounds[c], bounds[c + 1]
            k = a + np.searchsorted(T[a:b], t, side="right")
            if k == a or not OK[k - 1]:
                continue
            mc = VS[k - 1] / VT[k - 1] * 1e9
            if mc > CAP:
                continue
            sl = slice(a, k)
            nd = ~DEV[sl]
            buyers = len(set(U[sl][BUY[sl] & nd].tolist()))
            inflow = float(np.where(BUY[sl], SOL[sl], -SOL[sl])[nd].sum())
            info.append((c, ct[c], buyers, inflow, mc))
        if not info:
            stats[f"K{K}_no_leader"] += 1
            continue
        for sel in SELECTIONS:
            if sel == "first":
                c, cc, buyers, inflow, mc = min(info, key=lambda x: x[1])
            elif sel == "buyers":
                c, cc, buyers, inflow, mc = max(info, key=lambda x: (x[2], -x[1]))
            else:
                c, cc, buyers, inflow, mc = max(info, key=lambda x: (x[3], -x[1]))
            if t - last_entry.get((K, sel, c), -1e18) < REENTRY:
                continue
            a, b = bounds[c], bounds[c + 1]
            Tc, VSc, VTc, OKc = T[a:b], VS[a:b], VT[a:b], OK[a:b]
            end = t + es.LATENCY + MAXH + es.LATENCY
            win = (Tc > t) & (Tc <= end)
            untrusted = bool((~OKc[win]).any())
            good = OKc  # once untrusted, stays untrusted: the trusted rows are a prefix
            o = es.outcomes(Tc[good], VSc[good], VTc[good], t, comp.get(c))
            if not o:
                continue
            last_entry[(K, sel, c)] = t
            rows.append({"K": K, "sel": sel, "kw": w, "t": t, "n_members": len(members), "n_cands": len(info),
                         "mint": cr.mint[c], "name": cr.name[c], "age": t - cc, "buyers": buyers, "inflow": inflow,
                         "mc": mc, "untrusted_in_window": untrusted, **{col: o[col] for col in EXIT_COLS}})
    print(dict(stats), flush=True)
    d = pd.DataFrame(rows)
    d.to_parquet(OUT)
    return d, dict(stats)


def table(d):
    out = {}
    for K in KS:
        for sel in SELECTIONS:
            g = d[(d.K == K) & (d.sel == sel)]
            for col in EXIT_COLS:
                cfg = f"K{K}|{sel}|{col}"
                out[cfg] = {f"tip{tip}": summary(g[col].to_numpy() - 2 * tip) for tip in es.TIPS}
                out[cfg]["pass_0.001"] = passes(out[cfg]["tip0.001"])
                out[cfg]["pass_0.01"] = passes(out[cfg]["tip0.01"])
    return out


def day(t):
    return np.where(t < HOLD0, "oct1", np.where(t < OCT3, "oct2", "oct3"))


if __name__ == "__main__":
    if ("--cached" in sys.argv or "--validate" in sys.argv) and OUT.exists():
        d, stats = pd.read_parquet(OUT), None
    else:
        d, stats = build()
    prim = d[~d.untrusted_in_window]
    if "--validate" in sys.argv:
        cfgs = sys.argv[sys.argv.index("--validate") + 1:]
        va = prim[(prim.t >= OCT3) & (prim.t < OCT4)]
        res = {c: v for c, v in table(va).items() if c in cfgs}
        print(json.dumps(res, indent=1))
        (EVID / "evidence_narrative_cluster_validation_20261005.json").write_text(json.dumps(res, indent=1))
        sys.exit()
    trn = prim[(prim.t < HOLD0) | ((prim.t >= OCT2) & (prim.t < OCT3))]
    res = table(trn)
    for k, v in sorted(res.items(), key=lambda kv: -(kv[1]["tip0.001"]["exp"] or -9)):
        print(f"{k:34} {v['tip0.001']}  pass={v['pass_0.001']}/{v['pass_0.01']}")
    byday = {}
    for cfg in res:
        K, sel, col = cfg.split("|")
        g = trn[(trn.K == int(K[1:])) & (trn.sel == sel)]
        byday[cfg] = {dd: summary(gg[col].to_numpy() - 0.002) for dd, gg in g.groupby(day(g.t.to_numpy()))}
    tr_all = d[(d.t < HOLD0) | ((d.t >= OCT2) & (d.t < OCT3))]
    sens = {}  # untrusted-in-window trades included (prices from the trusted prefix)
    for K in KS:
        for sel in SELECTIONS:
            g = tr_all[(tr_all.K == K) & (tr_all.sel == sel)]
            sens[f"K{K}|{sel}|g_tp50_sl20_300"] = summary(g["g_tp50_sl20_300"].to_numpy() - 0.002)
    meta = {"n_configs": len(res), "build_stats": stats, "train_rows": int(len(trn)),
            "train_rows_untrusted_excluded": int(tr_all.untrusted_in_window.sum()),
            "top_keywords_train": trn[trn.sel == "first"].drop_duplicates(["K", "kw", "t"]).kw.value_counts().head(30).to_dict(),
            "median_leader_mc": trn.groupby("sel").mc.median().round(2).to_dict(),
            "median_leader_age_s": trn.groupby("sel").age.median().round(1).to_dict(),
            "sensitivity_untrusted_included_tp50": sens}
    print(json.dumps({k: v for k, v in meta.items() if k != "sensitivity_untrusted_included_tp50"}, indent=1))
    (EVID / "evidence_narrative_cluster_train_20261005.json").write_text(
        json.dumps({"meta": meta, "configs": res, "by_day_tip0.001": byday}, indent=1))
