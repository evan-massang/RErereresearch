"""Upper bound for imitating Decu: a bot that knew which tokens Decu would buy, entering latency_s after their
first buy, exiting mechanically (take-profit / stop-loss / max hold on the curve, as in ml_snapshots), 0.5 SOL,
1.25% protocol fee per side, exact constant-product fills, tip per transaction.

If even this oracle loses, an imitation model (which can only be worse at choosing) cannot pass the bar.

    python scripts/research/decu_oracle.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import duckdb  # noqa: E402
import numpy as np  # noqa: E402

from pipeline import config, market  # noqa: E402

WALLET = "4vw54BmAogeRV3vPKWyFet5yf8DTLcREzdSzx4rw9Ud9"
SIZE, FEE = 0.5, 0.0125
EXITS = ((0.2, 0.1), (0.3, 0.15), (0.5, 0.2), (1.0, 0.3), (2.0, 0.4))
TIPS = (0.001, 0.01)


def rt(vs0, vt0, vs1, vt1):
    tok = vt0 - vs0 * vt0 / (vs0 + SIZE * (1 - FEE))
    return (vs1 - vs1 * vt1 / (vt1 + tok)) * (1 - FEE) - SIZE


def main(latency_s: float = 1.0, maxhold: float = 600.0) -> dict:
    con = duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
    comp = dict(con.execute("SELECT mint, min(recv) FROM curve_completes GROUP BY 1").fetchall())
    trips = [t for t in market.round_trips(con, [WALLET]) if t.sol_in >= 0.5]
    res = {f"tp{int(a * 100)}_sl{int(b * 100)}": [] for a, b in EXITS}
    res["mirror_exit"] = []
    for t in trips:
        x = con.execute("SELECT recv, vsol, vtok FROM curve_trades WHERE mint = ? AND recv <= ? ORDER BY recv, rowid",
                        [t.mint, t.first_ts + latency_s + maxhold]).fetchall()
        T = np.array([r[0] for r in x])
        vs = np.array([r[1] for r in x])
        vt = np.array([r[2] for r in x])
        k = np.searchsorted(T, t.first_ts + latency_s, side="right")
        if k == 0 or k >= len(T):
            continue
        vs0, vt0 = vs[k - 1], vt[k - 1]
        tc = comp.get(t.mint)
        lim = len(T) if tc is None else np.searchsorted(T, tc, side="left")
        lim = max(lim, k)
        px = vs[k:lim] / vt[k:lim]
        p0 = vs0 / vt0
        for a, b in EXITS:
            hit = np.nonzero((px >= p0 * (1 + a)) | (px <= p0 * (1 - b)))[0]
            e = np.searchsorted(T, T[k + hit[0]] + latency_s, side="right") if len(hit) else lim
            e = min(max(e, k), lim) if lim > k else k
            res[f"tp{int(a * 100)}_sl{int(b * 100)}"].append(rt(vs0, vt0, vs[max(e, 1) - 1], vt[max(e, 1) - 1]))
        # exit latency_s after Decu's own last sell on the curve (closed trips only)
        if t.closed:
            e = min(np.searchsorted(T, t.last_ts + latency_s, side="right"), lim) if lim > k else k
            res["mirror_exit"].append(rt(vs0, vt0, vs[max(e, 1) - 1], vt[max(e, 1) - 1]))
    out = {"latency_s": latency_s, "n_trips": len(trips)}
    for k_, v in res.items():
        for tip in TIPS:
            a = np.sort(np.array(v) - 2 * tip)
            w, l = a[a > 0], a[a <= 0]
            out[f"{k_}@{tip}"] = {"n": int(len(a)), "pnl": round(float(a.sum()), 3), "exp": round(float(a.mean()), 4) if len(a) else None,
                                  "pf": round(float(w.sum() / -l.sum()), 3) if len(l) and l.sum() < 0 else None,
                                  "wo3": round(float(a[:-3].sum()), 3) if len(a) > 3 else None}
    return out


if __name__ == "__main__":
    for lat in (1.0, 3.0):
        o = main(lat)
        print("latency", lat, "trips", o["n_trips"])
        for k, v in o.items():
            if isinstance(v, dict):
                print(f"  {k:22} {v}")
        (ROOT / f"research/observations/evidence_decu_oracle_lat{lat:g}.json").write_text(json.dumps(o, indent=1))
