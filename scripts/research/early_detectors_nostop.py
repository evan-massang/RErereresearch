"""Early-detector follow-up (coordinator request, 2026-10-04): no-stop exits, TRAIN first, validation only for passes.

Same cross-fitted detector lists and triggers as early_detectors_eval.py (P in {0.3, 0.5} x quiet off/on).
Exits (1800 s max hold, fills as event_studies.outcomes: decision print + 1 s latency, exact curve round trip):
  tp100   take-profit +100%, no stop;
  tp200   take-profit +200%, no stop;
  hold    no take-profit, no stop: last curve state at 1800 s or the last state before completion.
A trade whose 1800 s window crosses the end of a continuous data chunk (and the token has not completed by then)
is dropped (NaN), as in the build step. 12 configs; tips 0.001 / 0.01 SOL per tx, two tx per trade.

    ED_OUT=<dir> python scripts/research/early_detectors_nostop.py
"""
import itertools
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "research"))
import duckdb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from pipeline import config  # noqa: E402
import event_studies as es  # noqa: E402
import early_detectors_build as bld  # noqa: E402
import early_detectors_eval as ev  # noqa: E402

D = Path(os.environ.get("ED_OUT", "/tmp/early_detectors"))
MH = 1800.0
EXITS = {"tp100": 1.0, "tp200": 2.0, "hold": np.inf}


def exit_pnl(T, vs, vt, t, tc, a):
    L = es.LATENCY
    k = np.searchsorted(T, t + L, side="right")
    if k == 0:
        return np.nan
    vs0, vt0 = vs[k - 1], vt[k - 1]
    p0 = vs0 / vt0
    end = t + L + MH
    lim = np.searchsorted(T, min(end, tc), side="left") if tc is not None and tc <= end else np.searchsorted(T, end, side="right")
    lim = max(lim, k)
    hit = np.nonzero(vs[k:lim] / vt[k:lim] >= p0 * (1 + a))[0]
    e = np.searchsorted(T, T[k + hit[0]] + L, side="right") if len(hit) else lim
    if tc is not None:
        e = min(e, np.searchsorted(T, tc, side="left"))
    e = max(e, k)
    return es.rt(vs0, vt0, vs[e - 1], vt[e - 1])


def score(con, x: pd.DataFrame, seg: str) -> pd.DataFrame:
    a, b = bld.SEGMENTS[seg]
    cs, ce = bld.chunks(con.execute("SELECT recv FROM curve_trades WHERE recv >= ? AND recv < ?", [a, b]).df().recv.to_numpy())
    comp = dict(con.execute("SELECT mint, min(recv) FROM curve_completes WHERE recv >= ? AND recv < ? GROUP BY 1", [a, b]).fetchall())
    rows = []
    for r in x.itertuples():
        q = con.execute("SELECT recv, vsol, vtok FROM curve_trades WHERE mint = ? AND recv >= ? AND recv < ? ORDER BY recv, rowid",
                        [r.mint, a, b]).fetchall()
        T, vs, vt = (np.array([z[i] for z in q]) for i in range(3))
        tc = comp.get(r.mint)
        cend = ce[np.searchsorted(cs, r.t, side="right") - 1]
        ok = r.t + es.LATENCY + MH <= cend or (tc is not None and tc <= r.t + es.LATENCY + MH)
        rows.append({"mint": r.mint, "t": r.t, **{k: exit_pnl(T, vs, vt, r.t, tc, v) if ok else np.nan for k, v in EXITS.items()}})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    A, B = pd.read_parquet(D / "buys_A.parquet"), pd.read_parquet(D / "buys_B.parquet")
    con = duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
    out = {"grid_size": 0, "train": {}, "train_passing": [], "validation": {}}
    for p, quiet in itertools.product(ev.PS, (False, True)):
        s = pd.concat([score(con, ev.triggers(B, ev.detectors(A, p), quiet), "B"),
                       score(con, ev.triggers(A, ev.detectors(B, p), quiet), "A")])
        for ex in EXITS:
            out["grid_size"] += 1
            key = f"P{p}|quiet{int(quiet)}|{ex}_nostop_1800"
            out["train"][key] = {str(tip): ev.stats(s[ex].to_numpy() - 2 * tip) for tip in ev.TIPS}
            print(key, out["train"][key], flush=True)
    out["train_passing"] = [k for k, v in out["train"].items() if v["0.001"]["pass"]]
    if out["train_passing"]:  # validation read only for train passes, once
        V = pd.read_parquet(D / "buys_V.parquet")
        AB = pd.concat([A, B])
        for k in out["train_passing"]:
            p, q, col = k.split("|")
            s = score(con, ev.triggers(V, ev.detectors(AB, float(p[1:])), q == "quiet1"), "V")
            out["validation"][k] = {str(tip): ev.stats(s[col.split("_")[0]].to_numpy() - 2 * tip) for tip in ev.TIPS}
            print("VAL", k, out["validation"][k])
    (ROOT / "research/observations/evidence_early_detectors_nostop_20261004.json").write_text(json.dumps(out, indent=1))
