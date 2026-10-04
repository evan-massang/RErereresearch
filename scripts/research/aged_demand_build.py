"""Agent aged_demand (2026-10-04): point-in-time "aged-wallet demand" features on the bonding-curve tape.

Hypothesis: buys from wallets that were already active in our tape hours earlier (aged, likely real traders) and
that are not round-tripping (wash) predict continuation better than raw buyer counts.

Wallet age: first_seen[u] = min recv of any curve trade by u in the ALLOWED data (train + validation; the
holdout 1790882100-1790899200 and anything >= 1791072000 are never queried). A buyer is "aged" at time t when
first_seen <= t - AGE_H hours (AGE_H = 3; a 6 h column is kept as a diagnostic). Because first_seen <= t - 3 h
is itself a fact about the past, using the global min is point in time. Limitation: the tape starts Oct 1
~12:17 UTC, so on Oct 1 "aged" can only mean seen >= 3 h earlier in the same session (triggers start ~15:17).
Wallets first seen in the holdout are not in the data at all, so they are never aged by holdout activity.

prior_mints: distinct mints the wallet touched before it first touched this mint (point in time) -- used to
separate hyperactive bots (hundreds of mints) from human-paced aged wallets.

Round-trip (wash) flag, per token: the wallet has a buy and a sell in this token within RT_S = 10 s of each other,
both received <= t.

Features are evaluated at every aged buy print (the only prints at which an aged-buyer count can rise) for tokens
aged 10-600 s, still on the curve, not Mayhem Mode (flag False in PumpPortal creates; unknown flag -> excluded),
whose trade history from creation to t + 1 + 1800 s sits in one gap-free recording segment inside its split.

    python scripts/research/aged_demand_build.py   # writes scratchpad/aged_demand_features.parquet
"""
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import duckdb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HOLD0, OCT2, OCT3, OCT4 = 1790882100.0, 1790899200.0, 1790985600.0, 1791072000.0
GAP, MAXH, LAT = 60.0, 1800.0, 1.0
AGE_H, AGE_H2, RT_S, HYPER = 3 * 3600.0, 6 * 3600.0, 10.0, 100
WINS = (30.0, 60.0)
SCR = Path("/tmp/claude-0/-home-user-RErereresearch/f8ba0823-6528-5b3d-92e7-a2d8665674ee/scratchpad")
OUT = SCR / "aged_demand_features.parquet"
ALLOWED = f"recv < {OCT4} AND NOT (recv >= {HOLD0} AND recv < {OCT2})"


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


def load(con):
    con.execute(f"""CREATE TEMP TABLE tr AS SELECT row_number() OVER (ORDER BY recv, rowid) rid, recv, slot, mint, usr,
                    buy, sol, vsol, vtok, rsol FROM curve_trades WHERE {ALLOWED}""")
    con.execute("CREATE TEMP TABLE w AS SELECT usr, row_number() OVER () - 1 uid, min(recv) fs FROM tr GROUP BY usr")
    con.execute("""CREATE TEMP TABLE um AS SELECT usr, mint, row_number() OVER (PARTITION BY usr ORDER BY min(recv)) - 1
                   prior_mints FROM tr GROUP BY usr, mint""")
    fl = pd.read_parquet(ROOT / "data/processed/mayhem_flags.parquet", columns=["mint", "is_mayhem"])
    con.register("fl", fl)
    con.execute(f"""CREATE TEMP TABLE cr AS SELECT c.mint, any_value(c.creator) creator, min(c.recv) ct
                    FROM curve_creates c JOIN fl ON fl.mint = c.mint AND fl.is_mayhem = false
                    WHERE {ALLOWED.replace('recv', 'c.recv')} GROUP BY 1""")
    comp = dict(con.execute(f"SELECT mint, min(recv) FROM curve_completes WHERE {ALLOWED} GROUP BY 1").fetchall())
    cr = con.execute("SELECT * FROM cr").df().set_index("mint")
    # trades of candidate tokens within their first 600 s (features only need these)
    d = con.execute("""SELECT tr.mint, tr.recv, w.uid, tr.usr = cr.creator isdev, tr.buy, tr.sol, w.fs, um.prior_mints,
                       abs(tr.vsol - tr.rsol - 30) < 0.01 clean
                       FROM tr JOIN cr USING (mint) JOIN w USING (usr) JOIN um USING (usr, mint)
                       WHERE tr.recv <= cr.ct + 600 ORDER BY tr.mint, tr.rid""").df()
    return cr, comp, d


def token_rows(m, g, ct, tc, segs):
    T = g.recv.to_numpy(); uid = g.uid.to_numpy(); isdev = g.isdev.to_numpy(); buy = g.buy.to_numpy()
    sol = g.sol.to_numpy(); fs = g.fs.to_numpy(); pm = g.prior_mints.to_numpy(); clean = g.clean.to_numpy()
    s0 = seg_of(segs, ct)
    last_b, last_s, rtflag = {}, {}, set()
    win = deque()  # (T, uid, sol, fs, pm) of non-dev buys within the last max(WINS) s
    aged_since, buyers_since = set(), set()
    rows = []
    for i in range(len(T)):
        t, u = T[i], uid[i]
        if buy[i]:
            if u in last_s and t - last_s[u] <= RT_S:
                rtflag.add(u)
            last_b[u] = t
        else:
            if u in last_b and t - last_b[u] <= RT_S:
                rtflag.add(u)
            last_s[u] = t
        if not buy[i] or isdev[i]:
            continue
        win.append((t, u, sol[i], fs[i], pm[i]))
        buyers_since.add(u)
        if fs[i] <= t - AGE_H:
            aged_since.add(u)
        while win and win[0][0] <= t - WINS[-1]:
            win.popleft()
        age = t - ct
        if fs[i] > t - AGE_H or age < 10 or age > 600 or not clean[i] or (tc is not None and t >= tc - LAT):
            continue
        ceil, split = split_ceiling(t)
        if split is None or t + LAT + MAXH + 1 >= ceil or s0 < 0 or seg_of(segs, t + LAT + MAXH + 1) != s0:
            continue
        rec = {"mint": m, "t": t, "age": age, "split": split, "migrated": tc is not None,
               "nA_since": len(aged_since - rtflag), "nB_since": len(buyers_since)}
        for W in WINS:
            ws = [x for x in win if x[0] > t - W]
            allu = {x[1] for x in ws}
            aged = {x[1] for x in ws if x[3] <= t - AGE_H and x[1] not in rtflag}
            aged6 = {x[1] for x in ws if x[3] <= t - AGE_H2 and x[1] not in rtflag}
            agedh = {x[1] for x in ws if x[3] <= t - AGE_H and x[1] not in rtflag and x[4] <= HYPER}
            w = int(W)
            rec[f"nA{w}"] = len(aged)
            rec[f"nA6_{w}"] = len(aged6)
            rec[f"nAh{w}"] = len(agedh)
            rec[f"solA{w}"] = float(sum(x[2] for x in ws if x[3] <= t - AGE_H and x[1] not in rtflag))
            rec[f"nB{w}"] = len(allu)
            rec[f"solB{w}"] = float(sum(x[2] for x in ws))
            rec[f"share{w}"] = len(aged) / len(allu) if allu else 0.0
            rec[f"wash{w}"] = sum(1 for x in ws if x[1] in rtflag) / len(ws) if ws else 0.0
        rows.append(rec)
    return rows


def run():
    SCR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(ROOT / "data" / "market.duckdb"), read_only=True)
    con.execute(f"SET memory_limit='3GB'; SET threads=2; SET temp_directory='{SCR}/duck_tmp'")
    segs = segments(con)
    cr, comp, d = load(con)
    print("segments", len(segs), "tokens", len(cr), "early trades", len(d), flush=True)
    rows = []
    for n, (m, g) in enumerate(d.groupby("mint", sort=False)):
        ci = cr.loc[m]
        rows.extend(token_rows(m, g, ci.ct, comp.get(m), segs))
        if n % 10000 == 0:
            print(n, len(rows), flush=True)
    f = pd.DataFrame(rows)
    f.to_parquet(OUT)
    # wallet-age diagnostics (no outcomes)
    diag = con.execute("""SELECT count(*) n_buys, avg((fs <= recv - 10800)::INT) aged_frac FROM tr JOIN w USING (usr)
                          WHERE buy""").fetchall()
    print("all buys / aged fraction", diag, flush=True)
    return f


if __name__ == "__main__":
    f = run()
    print(f.groupby("split").size())
    print(f.describe().T.to_string())
