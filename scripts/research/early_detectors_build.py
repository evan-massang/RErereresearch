"""Early-detector wallets on the pump.fun bonding curve: build per-buy tables (step 1 of 2).

For every segment (train fold A = Oct 1 before the holdout, train fold B = Oct 2, validation = Oct 3) it writes
one parquet of *qualifying first buys* with the point-in-time trigger features and the run label used only to
rank wallets, plus exact curve-fill outcomes (event_studies.rt / outcomes conventions) for every such buy.

Qualifying first buy (wallet w, token m):
  - w's first buy in m; w is not m's creator and not a creator of any token seen up to the segment end;
  - slot > create slot + 1 (launch-block snipers excluded);
  - token created inside the segment (full tape visible) with a standard initial market cap (25-40 SOL);
  - market cap after the buy (vsol / vtok * 1e9) <= MCAP_LOW and token age <= AGE_MAX.
Run label (ranking only, never a strategy input): within RUN_WIN s after the buy the token prints >= 2x the
post-buy market cap, or completes (migrates). Buys whose label window runs past the end of a continuous data
chunk (no prints for > GAP s anywhere) are dropped from the label; outcomes whose max hold crosses a chunk end
are set to NaN.
Quiet-tape features at the buy (strictly earlier prints): other wallets' buy SOL and distinct buyers in the
previous 30 s, distinct buyers since creation.

No data from the holdout (1790882100-1790899200) or at/after 1791072000 is loaded.

    python scripts/research/early_detectors_build.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "research"))
import duckdb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from pipeline import config  # noqa: E402
import event_studies as es  # noqa: E402  (rt, outcomes, EXITS, MAXHOLDS, LATENCY)

MCAP_LOW, AGE_MAX, RUN_WIN, GAP, QUIET_WIN = 50.0, 900.0, 1800.0, 120.0, 30.0
SEGMENTS = {"A": (0.0, 1790882100.0), "B": (1790899200.0, 1790985600.0), "V": (1790985600.0, 1791072000.0)}
OUT = Path(__import__('os').environ.get('ED_OUT', '/tmp/early_detectors'))


def chunks(T: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    t = np.sort(T)
    br = np.nonzero(np.diff(t) > GAP)[0]
    starts = np.r_[t[0], t[br + 1]]
    ends = np.r_[t[br], t[-1]]
    return starts, ends


def build(seg: str) -> pd.DataFrame:
    a, b = SEGMENTS[seg]
    con = duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
    cr = con.execute("""SELECT mint, any_value(creator) creator, min(recv) ct, min(slot) cslot FROM curve_creates
                        WHERE recv >= ? AND recv < ? GROUP BY 1""", [a, b]).df().set_index("mint")
    creators_all = set(con.execute("SELECT DISTINCT creator FROM curve_creates WHERE recv < ? AND (recv < 1790882100 OR recv >= 1790899200)",
                                   [b]).df().creator)
    comp = dict(con.execute("SELECT mint, min(recv) FROM curve_completes WHERE recv >= ? AND recv < ? GROUP BY 1", [a, b]).fetchall())
    tr = con.execute("""SELECT mint, recv, slot, usr, buy, sol, vsol, vtok FROM curve_trades
                        WHERE recv >= ? AND recv < ? AND mint IN (SELECT mint FROM curve_creates WHERE recv >= ? AND recv < ?)
                        ORDER BY recv, rowid""", [a, b, a, b]).df()
    con.close()
    cs, ce = chunks(tr.recv.to_numpy())
    print(seg, "trades", len(tr), "tokens", tr.mint.nunique(), "chunks", len(cs), flush=True)
    chunk_end = lambda t: ce[np.searchsorted(cs, t, side="right") - 1]
    rows = []
    for m, g in tr.groupby("mint", sort=False):
        ci = cr.loc[m]
        T, vs, vt = g.recv.to_numpy(), g.vsol.to_numpy(), g.vtok.to_numpy()
        mc = vs / vt * 1e9
        if not (25 <= mc[0] <= 40):
            continue
        slot, usr, buy, sol = g.slot.to_numpy(), g.usr.to_numpy(), g.buy.to_numpy(), g.sol.to_numpy()
        tc = comp.get(m)
        seen, buyers_since = set(), set()
        for i in range(len(T)):
            u = usr[i]
            if not buy[i]:
                continue
            first = u not in seen
            seen.add(u)
            n_since = len(buyers_since)
            buyers_since.add(u)
            if not first or u == ci.creator or u in creators_all or slot[i] <= ci.cslot + 1:
                continue
            age = T[i] - ci.ct
            if age > AGE_MAX or mc[i] > MCAP_LOW or (tc is not None and T[i] >= tc):
                continue
            ce_i = chunk_end(T[i])
            # run label
            hi = np.searchsorted(T, T[i] + RUN_WIN, side="right")
            peak = mc[i + 1:hi].max() if hi > i + 1 else mc[i]
            ran = bool(peak >= 2 * mc[i] or (tc is not None and tc <= T[i] + RUN_WIN))
            label_ok = ran or (T[i] + RUN_WIN <= ce_i)
            # quiet-tape features (strictly earlier prints)
            lo = np.searchsorted(T, T[i] - QUIET_WIN, side="left")
            pb = (buy[lo:i]) & (usr[lo:i] != u)
            q_sol = float(sol[lo:i][pb].sum())
            q_n = len(set(usr[lo:i][pb]))
            # follower-flow descriptives: mid-price ratio at +1/+5/+30 s after the buy vs the buy's post price
            fwd = {}
            for h in (1, 5, 30):
                k = np.searchsorted(T, T[i] + h, side="right") - 1
                fwd[f"r{h}"] = (vs[k] / vt[k]) / (vs[i] / vt[i]) - 1
            o = es.outcomes(T, vs, vt, T[i], tc)
            for key in list(o):
                mh = int(key.rsplit("_", 1)[1])
                if T[i] + es.LATENCY + mh > ce_i and not (tc is not None and tc <= T[i] + es.LATENCY + mh):
                    o[key] = np.nan
            rows.append({"seg": seg, "mint": m, "usr": u, "t": T[i], "slot": int(slot[i]), "age": age, "mcap": mc[i],
                         "sol": sol[i], "ran": ran, "label_ok": label_ok, "q_sol30": q_sol, "q_n30": q_n,
                         "n_buyers_before": n_since, **fwd, **o})
    d = pd.DataFrame(rows)
    print(seg, "qualifying first buys", len(d), "wallets", d.usr.nunique(), flush=True)
    return d


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for seg in sys.argv[1:] or list(SEGMENTS):
        build(seg).to_parquet(OUT / f"buys_{seg}.parquet")
