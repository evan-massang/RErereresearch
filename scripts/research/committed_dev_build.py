"""Agent committed_dev (2026-10-04): buy pump.fun launches whose creator bought >= D SOL at launch and has NOT
sold anything by token age T, while >= B organic buyers (not creator, not launch-block snipers) have arrived.

Rules fixed before any outcome was computed (point in time, decision at exactly ct + T using only trades with
recv <= ct + T; entry at the first curve state >= 1 s later via event_studies.outcomes / same fill model):

  variant  dev launch buy  organic buyers  extra filters
  A        >= 1 SOL        >= 10           -
  B        >= 1 SOL        >= 20           -
  C        >= 1 SOL        >= 10           creator has 0 prior launches in allowed recorded data; not Mayhem Mode
  D        >= 2 SOL        >= 10           as C, plus <= 3 distinct non-creator launch-block (slot <= cslot+1) buyers
  T in (60, 120, 300) s
  exits: tp50_sl20 max 300 s; tp100_sl30 max 1800 s; devx = tp200_sl50 max 1800 s OR creator's first sell
         (exit fill 1 s after that sell is received)
  -> 4 variants x 3 ages x 3 exits = 36 configs.

Fills: exact constant product, 0.5 SOL, 1.25% fee per side, 1 s latency, completion cut (event_studies).
Price path uses only clean curve states (|vsol - rsol - 30| < 0.01); the entry state must be clean.
Outcome window (trigger + 1 s + 1800 s) must sit in one gap-free recording segment (no global gap > 60 s) and
inside its split: train window ends before 1790882100 (Oct 1 part) or before 1790985600 (Oct 2 part);
validation window ends before 1791072000. Off-limits data (holdout, >= Oct 4) is never queried.
Mayhem Mode: is_mayhem_mode from PumpPortal create messages; mints without a PumpPortal create are 'unknown'
and are kept (flag recorded so the effect of coverage can be checked).

    python scripts/research/committed_dev_build.py   # writes scratchpad parquet of per-trigger outcomes
"""
import glob
import gzip
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

HOLD0, OCT2, OCT3, OCT4 = 1790882100.0, 1790899200.0, 1790985600.0, 1791072000.0
GAP, MAXH = 60.0, 1800.0
AGES = (60, 120, 300)
OUT = Path("/tmp/claude-0/-home-user-RErereresearch/f8ba0823-6528-5b3d-92e7-a2d8665674ee/scratchpad/committed_dev_events.parquet")
ALLOWED = f"recv < {OCT4} AND NOT (recv >= {HOLD0} AND recv < {OCT2})"
EXITS = (("tp50_sl20_300", 0.5, 0.2, 300.0, False), ("tp100_sl30_1800", 1.0, 0.3, 1800.0, False),
         ("devx_tp200_sl50_1800", 2.0, 0.5, 1800.0, True))


def split_ceiling(t):
    if t < HOLD0:
        return HOLD0, "train"
    if OCT2 <= t < OCT3:
        return OCT3, "train"
    if OCT3 <= t < OCT4:
        return OCT4, "validation"
    return None, None


def segments(con):
    r = con.execute(f"""WITH t AS (SELECT recv, lag(recv) OVER (ORDER BY recv) p FROM curve_trades WHERE {ALLOWED})
                        SELECT p, recv FROM t WHERE recv - p > {GAP} ORDER BY p""").fetchall()
    lo, hi = con.execute(f"SELECT min(recv), max(recv) FROM curve_trades WHERE {ALLOWED}").fetchone()
    return np.array(list(zip([lo] + [b for _, b in r], [a for a, _ in r] + [hi])))


def seg_of(segs, t):
    i = np.searchsorted(segs[:, 0], t, side="right") - 1
    return i if i >= 0 and t <= segs[i, 1] else -1


def mayhem_flags():
    flags = {}
    for f in sorted(glob.glob(str(ROOT / "data/raw/streams/pumpportal/*.jsonl.gz"))):
        name = Path(f).name
        if name >= "20261004":  # off-limits day; not needed
            continue
        try:
            with gzip.open(f, "rt") as fh:
                for line in fh:
                    if '"create"' not in line:
                        continue
                    try:
                        j = json.loads(line)
                    except Exception:
                        continue
                    r, m = j.get("recv", 0), j.get("msg", {})
                    if r >= OCT4 or HOLD0 <= r < OCT2:
                        continue
                    if m.get("txType") == "create" and "is_mayhem_mode" in m:
                        flags[m["mint"]] = bool(m["is_mayhem_mode"])
        except EOFError:  # file truncated at a recorder restart; keep what was read
            pass
    return flags


def sim(T, vs, vt, t, tc, a, b, mh, dev_sell_t):
    """Same fill model as event_studies.outcomes, one exit; optional exit on creator's first sell."""
    k = np.searchsorted(T, t + es.LATENCY, side="right")
    if k == 0:
        return None
    vs0, vt0 = vs[k - 1], vt[k - 1]
    p0 = vs0 / vt0
    end = t + es.LATENCY + mh
    if dev_sell_t is not None and dev_sell_t < end:
        end_dev = dev_sell_t  # decision at the dev's sell print; fill LATENCY later
    else:
        end_dev = None
    lim_t = end if end_dev is None else end_dev
    lim = np.searchsorted(T, min(lim_t, tc), side="left") if tc is not None and tc <= lim_t else np.searchsorted(T, lim_t, side="right")
    lim = max(lim, k)
    px = vs[k:lim] / vt[k:lim]
    hit = np.nonzero((px >= p0 * (1 + a)) | (px <= p0 * (1 - b)))[0]
    if len(hit):
        e = np.searchsorted(T, T[k + hit[0]] + es.LATENCY, side="right")
    elif end_dev is not None:
        e = np.searchsorted(T, end_dev + es.LATENCY, side="right")
    else:
        e = lim
    if tc is not None:
        e = min(e, np.searchsorted(T, tc, side="left"))
    e = max(e, k)
    return es.rt(vs0, vt0, vs[e - 1], vt[e - 1])


def run():
    con = duckdb.connect(str(ROOT / "data" / "market.duckdb"), read_only=True)
    con.execute("SET memory_limit='3GB'; SET threads=2")
    segs = segments(con)
    print("segments", len(segs), flush=True)
    mayhem = mayhem_flags()
    print("pumpportal creates", len(mayhem), "mayhem", sum(mayhem.values()), flush=True)
    comp = dict(con.execute(f"SELECT mint, min(recv) FROM curve_completes WHERE {ALLOWED} GROUP BY 1").fetchall())
    cr = con.execute(f"""SELECT mint, any_value(creator) creator, min(recv) ct, min(slot) cslot FROM curve_creates
                         WHERE {ALLOWED} GROUP BY 1 ORDER BY ct""").df()
    # creator's prior launches (point in time, allowed recorded data only)
    cr["prior"] = cr.groupby("creator").cumcount()
    # candidate mints: creator launch buy >= 1 SOL (slot <= cslot + 1)
    con.register("crv", cr[["mint", "creator", "ct", "cslot"]])
    dev = con.execute(f"""SELECT c.mint, sum(t.sol) devin FROM crv c JOIN curve_trades t ON t.mint = c.mint
                          WHERE t.usr = c.creator AND t.buy AND t.slot <= c.cslot + 1 AND t.recv <= c.ct + 5
                          AND {ALLOWED.replace('recv', 't.recv')} GROUP BY 1 HAVING sum(t.sol) >= 1""").df()
    cand = cr.merge(dev, on="mint")
    print("launches", len(cr), "dev>=1 SOL", len(cand), flush=True)
    rows = []
    for lo, hi in ((1790812800.0, HOLD0), (OCT2, OCT2 + 43200), (OCT2 + 43200, OCT3), (OCT3, OCT3 + 43200), (OCT3 + 43200, OCT4)):
        cc = cand[(cand.ct >= lo) & (cand.ct < hi)].set_index("mint")
        ceil = HOLD0 if hi <= HOLD0 else (OCT3 if hi <= OCT3 else OCT4)
        con.register("cc", cc.reset_index()[["mint"]])
        tr = con.execute(f"""SELECT mint, recv, slot, usr, buy, sol, vsol, vtok, rsol FROM curve_trades
                             WHERE mint IN (SELECT mint FROM cc) AND recv < ? AND {ALLOWED}
                             ORDER BY mint, recv, rowid""", [ceil]).df()
        ne = 0
        for m, g in tr.groupby("mint", sort=False):
            ci = cc.loc[m]
            T = g.recv.to_numpy(); slot = g.slot.to_numpy(); usr = g.usr.to_numpy(); buy = g.buy.to_numpy()
            clean = np.abs(g.vsol.to_numpy() - g.rsol.to_numpy() - 30) < 0.01
            Tc, vsc, vtc = T[clean], g.vsol.to_numpy()[clean], g.vtok.to_numpy()[clean]
            isdev = usr == ci.creator
            dsell = np.nonzero(isdev & ~buy)[0]
            first_dev_sell = T[dsell[0]] if len(dsell) else None
            tc = comp.get(m)
            snipe = (~isdev) & buy & (slot <= ci.cslot + 1)
            n_launch_block = len(set(usr[snipe]))
            snipers = set(usr[snipe])
            for age in AGES:
                t = ci.ct + age
                if tc is not None and tc <= t + es.LATENCY:
                    continue
                if first_dev_sell is not None and first_dev_sell <= t:
                    continue
                ceil_s, split = split_ceiling(t)
                s0, s1 = seg_of(segs, ci.ct), seg_of(segs, t + es.LATENCY + MAXH + 1)
                if split is None or s0 < 0 or s0 != s1 or t + es.LATENCY + MAXH + 1 >= ceil_s:
                    continue
                upto = T <= t
                org = {u for u in usr[upto & buy & ~isdev & ~snipe] if u not in snipers}
                n_org = len(org)
                if n_org < 10:
                    continue
                k = np.searchsorted(Tc, t + es.LATENCY, side="right")
                kraw = np.searchsorted(T, t + es.LATENCY, side="right")
                if k == 0 or kraw == 0 or not clean[kraw - 1]:
                    continue  # entry state must be clean
                rec = {"mint": m, "creator": ci.creator, "ct": ci.ct, "age": age, "t": t, "split": split,
                       "devin": ci.devin, "prior": int(ci.prior), "n_org": n_org, "n_lb": n_launch_block,
                       "mayhem": mayhem.get(m), "mcap": vsc[k - 1] / vtc[k - 1] * 1e9,
                       "migrated": tc is not None}
                for name, a, b, mh, dx in EXITS:
                    rec[name] = sim(Tc, vsc, vtc, t, tc, a, b, mh, first_dev_sell if dx else None)
                rows.append(rec)
                ne += 1
        print(f"chunk {lo:.0f}-{hi:.0f}: cand tokens {len(cc)} events {ne}", flush=True)
        del tr
    d = pd.DataFrame(rows)
    d.to_parquet(OUT)
    return d


if __name__ == "__main__":
    d = run()
    print(d.groupby(["split", "age"]).size())
