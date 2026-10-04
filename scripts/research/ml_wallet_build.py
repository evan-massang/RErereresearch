"""Agent ml_wallet (2026-10-04): snapshot model + early-detector precision + aged-wallet demand features (build).

Rebuilds the ml_snapshots.py point-in-time snapshots (ages 5-300 s, the same 24 tape features and the same
take-profit / stop-loss labels g_* stored WITHOUT tips) on the allowed data only, and adds wallet features.

Data rules
  - data/market.duckdb read-only. Only recv < 1790882100 (fold A, Oct 1 before the holdout), 1790899200-1790985600
    (fold B, Oct 2; A + B = train) and 1790985600-1791072000 (V, validation) are ever queried.
  - Only clean curve states are used: trades with |vsol - rsol - 30| >= 0.01 are dropped before anything else.
  - Mayhem Mode tokens are skipped; tokens with an unknown flag (no PumpPortal create) are skipped too.
  - A snapshot (mint, t) is kept only if t + LATENCY + 300 s stays inside its own split AND inside the same gap-free
    recording segment (no gap > 60 s in the allowed tape) as the token's create, so no label touches off-limits
    data or a recording gap.

Wallet features (point in time; dev buys excluded from all of them)
  Early detectors (as early_detectors_build/eval): qualifying first buys = a wallet's first buy in a token created
  in the fold with initial mcap 25-40 SOL, slot > create slot + 1, buyer not a creator, mcap after buy <= 50 SOL,
  age <= 900 s; run = 2x the post-buy mcap or migration within 30 min; buys whose label window crosses a recording
  gap are dropped. Precision = run share over >= 8 label-complete buys. Cross-fitted: fold-A snapshots use the
  list built on fold B, fold-B snapshots the list built on fold A; validation uses the list built on A + B.
  Detector = precision >= 0.5.
    det_n_since, det_sol_since, det_n_30, det_sol_30   buys (count, SOL) by detectors since launch / last 30 s
    prec_max, prec_mean, prec_known_n                  over the token's distinct buyers with a known precision
  Aged demand (as aged_demand_build): first_seen = earliest allowed curve trade of the wallet; a buy is aged when
  first_seen <= buy time - 3 h. Wash: the wallet bought and sold the token within 10 s of each other (both <= t).
    aged_n_30, aged_share_30, aged_n_since, aged_share_since  distinct aged non-wash buyers, share of distinct buyers
    wash_share_30, wash_share_since                          share of buys made by wash-flagged wallets

    python scripts/research/ml_wallet_build.py   # -> scratchpad/ml_wallet_snapshots.parquet
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import duckdb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HOLD0, OCT2, OCT3, OCT4 = 1790882100.0, 1790899200.0, 1790985600.0, 1791072000.0
FOLDS = {"A": (0.0, HOLD0), "B": (OCT2, OCT3), "V": (OCT3, OCT4)}
ALLOWED = f"recv < {OCT4} AND NOT (recv >= {HOLD0} AND recv < {OCT2})"
AGES = (5, 10, 20, 30, 60, 120, 300)
EXITS = ((0.2, 0.1), (0.3, 0.15), (0.5, 0.2), (1.0, 0.3))
SIZE, FEE, LATENCY, MAXH = 0.5, 0.0125, 1.0, 300
GAP = 60.0
AGE_H, RT_S = 3 * 3600.0, 10.0
MCAP_LOW, AGE_MAX, RUN_WIN, MIN_N, P_DET = 50.0, 900.0, 1800.0, 8, 0.5
SCR = Path("/tmp/claude-0/-home-user-RErereresearch/f8ba0823-6528-5b3d-92e7-a2d8665674ee/scratchpad")
OUT = SCR / "ml_wallet_snapshots.parquet"


def rt(vs0, vt0, vs1, vt1) -> float:
    """Net SOL of buying SIZE at (vs0, vt0) and selling all at (vs1, vt1), protocol fee both sides, no tip."""
    tok = vt0 - vs0 * vt0 / (vs0 + SIZE * (1 - FEE))
    return (vs1 - vs1 * vt1 / (vt1 + tok)) * (1 - FEE) - SIZE


def rec_segments(con):
    r = con.execute(f"""WITH t AS (SELECT recv, lag(recv) OVER (ORDER BY recv) p FROM curve_trades WHERE {ALLOWED})
                        SELECT p, recv FROM t WHERE recv - p > {GAP} ORDER BY p""").fetchall()
    lo, hi = con.execute(f"SELECT min(recv), max(recv) FROM curve_trades WHERE {ALLOWED}").fetchone()
    return np.array(list(zip([lo] + [b for _, b in r], [a for a, _ in r] + [hi])))


def seg_of(segs, t):
    i = np.searchsorted(segs[:, 0], t, side="right") - 1
    return i if i >= 0 and t <= segs[i, 1] else -1


def load(con):
    con.execute(f"""CREATE TEMP TABLE tr AS SELECT row_number() OVER (ORDER BY recv, rowid) rid, recv, slot, mint, usr,
                    buy, sol, vsol, vtok, abs(vsol - rsol - 30) < 0.01 clean FROM curve_trades WHERE {ALLOWED}""")
    con.execute("CREATE TEMP TABLE w AS SELECT usr, (row_number() OVER ()) - 1 uid, min(recv) fs FROM tr GROUP BY usr")
    fl = pd.read_parquet(ROOT / "data/processed/mayhem_flags.parquet", columns=["mint", "is_mayhem"])
    con.register("fl", fl)
    con.execute(f"""CREATE TEMP TABLE cr AS SELECT c.mint, any_value(c.creator) creator, min(c.recv) ct, min(c.slot) cslot,
                    any_value(fl.is_mayhem) is_mayhem FROM curve_creates c LEFT JOIN fl ON fl.mint = c.mint
                    WHERE {ALLOWED.replace('recv', 'c.recv')} GROUP BY 1""")
    cr = con.execute("""SELECT cr.*, w.uid cuid FROM cr LEFT JOIN w ON w.usr = cr.creator ORDER BY ct""").df()
    comp = dict(con.execute(f"SELECT mint, min(recv) FROM curve_completes WHERE {ALLOWED} GROUP BY 1").fetchall())
    # creator record, point in time, over allowed creates only
    hist, prior, prior_mig = {}, [], []
    for m, c, t in zip(cr.mint, cr.creator, cr.ct):
        h = hist.setdefault(c, [])
        prior.append(len(h))
        prior_mig.append(sum(1 for x in h if comp.get(x) is not None and comp[x] < t))
        h.append(m)
    cr["creator_prior"], cr["creator_prior_mig"] = prior, prior_mig
    cr["cuid"] = cr.cuid.fillna(-1).astype("int64")
    creator_uids = set(con.execute("SELECT DISTINCT w.uid FROM cr JOIN w ON w.usr = cr.creator").df().uid)
    fs = con.execute("SELECT uid, fs FROM w ORDER BY uid").df().fs.to_numpy()
    return cr.set_index("mint"), comp, creator_uids, fs


def fold_trades(con, f):
    a, b = FOLDS[f]
    return con.execute("""SELECT tr.mint, tr.recv, tr.slot, w.uid, tr.buy, tr.sol, tr.vsol vs, tr.vtok vt FROM tr
                          JOIN w USING (usr) JOIN cr USING (mint)
                          WHERE tr.clean AND tr.recv >= ? AND tr.recv < ? AND cr.ct >= ? AND cr.ct < ?
                          ORDER BY tr.mint, tr.rid""", [a, b, a, b]).df()


def qualifying_buys(tr, cr, comp, creator_uids, segs, f):
    """Early-detector qualifying first buys with the run label (ranking only)."""
    rows = []
    for m, g in tr.groupby("mint", sort=False):
        ci = cr.loc[m]
        T, vs, vt = g.recv.to_numpy(), g.vs.to_numpy(), g.vt.to_numpy()
        mc = vs / vt * 1e9
        if not (25 <= mc[0] <= 40):
            continue
        slot, usr, buy = g.slot.to_numpy(), g.uid.to_numpy(), g.buy.to_numpy()
        tc = comp.get(m)
        seen = set()
        for i in np.nonzero(buy)[0]:
            u = usr[i]
            if u in seen:
                continue
            seen.add(u)
            if u == ci.cuid or u in creator_uids or slot[i] <= ci.cslot + 1:
                continue
            if T[i] - ci.ct > AGE_MAX or mc[i] > MCAP_LOW or (tc is not None and T[i] >= tc):
                continue
            hi = np.searchsorted(T, T[i] + RUN_WIN, side="right")
            peak = mc[i + 1:hi].max() if hi > i + 1 else mc[i]
            ran = bool(peak >= 2 * mc[i] or (tc is not None and tc <= T[i] + RUN_WIN))
            s = seg_of(segs, T[i])
            label_ok = ran or (s >= 0 and T[i] + RUN_WIN <= segs[s, 1] and T[i] + RUN_WIN < FOLDS[f][1])
            rows.append((u, ran, label_ok))
    d = pd.DataFrame(rows, columns=["uid", "ran", "label_ok"])
    print(f, "qualifying buys", len(d), "wallets", d.uid.nunique(), flush=True)
    return d


def precision(d):
    g = d[d.label_ok].groupby("uid").ran.agg(["size", "mean"])
    return g[g["size"] >= MIN_N]["mean"].to_dict()


def snapshots(tr, cr, comp, fs, prec, segs, f):
    ceil = FOLDS[f][1]
    rows = []
    for m, g in tr.groupby("mint", sort=False):
        ci = cr.loc[m]
        if pd.isna(ci.is_mayhem) or bool(ci.is_mayhem):
            continue
        ct, cuid = ci.ct, ci.cuid
        s0 = seg_of(segs, ct)
        if s0 < 0:
            continue
        T, buy, sol = g.recv.to_numpy(), g.buy.to_numpy(), g.sol.to_numpy()
        vs, vt, usr, slot = g.vs.to_numpy(), g.vt.to_numpy(), g.uid.to_numpy(), g.slot.to_numpy()
        tc = comp.get(m)
        dev = usr == cuid
        nb = buy & ~dev
        aged = fs[usr] <= T - AGE_H
        pr = np.array([prec.get(u, np.nan) for u in usr])
        det = nb & (pr >= P_DET)
        # wash: time at which each wallet's buy/sell-within-10 s pair is first completed
        lb, ls, wt = {}, {}, {}
        for i in range(len(T)):
            u = usr[i]
            if buy[i]:
                if u in ls and T[i] - ls[u] <= RT_S and u not in wt:
                    wt[u] = T[i]
                lb[u] = T[i]
            else:
                if u in lb and T[i] - lb[u] <= RT_S and u not in wt:
                    wt[u] = T[i]
                ls[u] = T[i]
        wash_t = np.array([wt.get(u, np.inf) for u in usr])
        for age in AGES:
            t = ct + age
            if t + LATENCY + MAXH >= ceil or seg_of(segs, t + LATENCY + MAXH) != s0:
                break
            if tc is not None and tc <= t:
                break
            i = np.searchsorted(T, t, side="right")
            if i == 0:
                continue
            mc = vs[i - 1] / vt[i - 1] * 1e9
            x = {"mint": m, "fold": f, "age": age, "t": t, "creator_prior": ci.creator_prior,
                 "creator_prior_mig": ci.creator_prior_mig, "mcap": mc, "vsol": vs[i - 1], "n_trades": i,
                 "s_since_last": t - T[i - 1]}
            for w in (5, 15, 60):
                j = np.searchsorted(T, t - w, side="right")
                x[f"ret_{w}"] = mc / (vs[j - 1] / vt[j - 1] * 1e9) - 1 if j > 0 else np.nan
            for w in (10, 30):
                j = np.searchsorted(T, t - w, side="right")
                sb, ss = buy[j:i], ~buy[j:i]
                x[f"buys_{w}"] = int(sb.sum())
                x[f"sells_{w}"] = int(ss.sum())
                x[f"net_flow_{w}"] = float(sol[j:i][sb].sum() - sol[j:i][ss].sum())
                x[f"uniq_buyers_{w}"] = len(set(usr[j:i][sb]))
            bm = buy[:i]
            x["uniq_buyers"] = len(set(usr[:i][bm]))
            x["largest_buy"] = float(sol[:i][bm].max()) if bm.any() else 0.0
            x["dev_in"] = float(sol[:i][dev[:i] & bm].sum())
            x["dev_out"] = float(sol[:i][dev[:i] & ~bm].sum())
            x["launch_block_buyers"] = int(((slot[:i] <= ci.cslot + 1) & bm & ~dev[:i]).sum())
            x["sell_share"] = float((~bm).mean())
            # ---- wallet features ----
            j30 = np.searchsorted(T, t - 30, side="right")
            for name, lo in (("since", 0), ("30", j30)):
                sl = slice(lo, i)
                nbm = nb[sl]
                x[f"det_n_{name}"] = int(det[sl].sum())
                x[f"det_sol_{name}"] = float(sol[sl][det[sl]].sum())
                buyers = set(usr[sl][nbm])
                nw = wash_t[sl] <= t
                agedset = set(usr[sl][nbm & aged[sl] & ~nw])
                x[f"aged_n_{name}"] = len(agedset)
                x[f"aged_share_{name}"] = len(agedset) / len(buyers) if buyers else 0.0
                x[f"wash_share_{name}"] = float(nw[nbm].mean()) if nbm.any() else 0.0
            ub, first = np.unique(usr[:i][nb[:i]], return_index=True)
            pk = pr[:i][nb[:i]][first]
            pk = pk[~np.isnan(pk)]
            x["prec_known_n"] = len(pk)
            x["prec_max"] = float(pk.max()) if len(pk) else np.nan
            x["prec_mean"] = float(pk.mean()) if len(pk) else np.nan
            # ---- labels: entry LATENCY after t, TP/SL on prints, fill LATENCY after the trigger print ----
            k = np.searchsorted(T, t + LATENCY, side="right")
            vs0, vt0 = vs[max(k, 1) - 1], vt[max(k, 1) - 1]
            p0 = vs0 / vt0
            for maxhold in (120, 300):
                te = t + LATENCY + maxhold
                cut = tc is not None and tc <= te
                lim = max(np.searchsorted(T, tc if cut else te, side="left" if cut else "right"), k)
                px = vs[k:lim] / vt[k:lim]
                for tp, sl_ in EXITS:
                    hit = np.nonzero((px >= p0 * (1 + tp)) | (px <= p0 * (1 - sl_)))[0]
                    if len(hit):
                        e = np.searchsorted(T, T[k + hit[0]] + LATENCY, side="right")
                        if tc is not None:
                            e = min(e, np.searchsorted(T, tc, side="left"))
                    else:
                        e = lim
                    e = max(e, k, 1)
                    x[f"g_tp{int(tp * 100)}_sl{int(sl_ * 100)}_{maxhold}"] = rt(vs0, vt0, vs[e - 1], vt[e - 1])
            x["migrated"] = tc is not None
            rows.append(x)
    print(f, "snapshots", len(rows), flush=True)
    return rows


def main():
    SCR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(ROOT / "data" / "market.duckdb"), read_only=True)
    con.execute(f"SET memory_limit='3GB'; SET threads=2; SET temp_directory='{SCR}/duck_tmp_mlw'")
    segs = rec_segments(con)
    cr, comp, creator_uids, fs = load(con)
    print("recording segments", len(segs), "creates", len(cr), flush=True)
    trs = {f: fold_trades(con, f) for f in FOLDS}
    qb = {f: qualifying_buys(trs[f], cr, comp, creator_uids, segs, f) for f in ("A", "B")}
    precs = {"A": precision(qb["B"]), "B": precision(qb["A"]), "V": precision(pd.concat([qb["A"], qb["B"]]))}
    for f, p in precs.items():
        v = np.array(list(p.values()))
        print(f, "known-precision wallets", len(v), "detectors", int((v >= P_DET).sum()), flush=True)
    rows = []
    for f in FOLDS:
        rows += snapshots(trs[f], cr, comp, fs, precs[f], segs, f)
        del trs[f]
    d = pd.DataFrame(rows)
    d.to_parquet(OUT)
    return d


if __name__ == "__main__":
    d = main()
    print(d.groupby("fold").size())
    print(d.describe().T.to_string())
