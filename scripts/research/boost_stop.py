"""Follow-up (pre-stated by coordinator): THIN pools (reserve <= 150 SOL at entry), single exit +300 s, plus a
protective stop. Stop triggers at the first trade after entry whose post-trade mid is >= X% below the entry fill
price (size / tokens received); exit fills at trigger time + latency on the actual state (conservative sell state
from amm_flow_lib). X in {20, 30}, latency in {0.25, 1.0}: 4 configs, tips 0.001 / 0.01 per tx (2 tx).
Usage: python boost_stop.py train   |   python boost_stop.py valid <config> ...   Agent boost, 2026-10-04."""
import json, sys
import numpy as np, pandas as pd
sys.path.insert(0, "/home/user/RErereresearch/scripts/research")
import boost_lib as B, amm_flow_lib as L

OUT = "/home/user/RErereresearch/research/observations/evidence_boost_stop_{}20261004.json"
DAY2 = 1790899200  # train Oct 2 segment starts here; earlier train = Oct 1


def trip(a, c, lat, X, size=L.SIZE):
    te = c + lat
    rs, rt, f, ok = L.state_for(a, np.array([te]), "buy")
    if not ok[0] or rs[0] > 150:
        return None
    x = size / (1 + f[0])
    q = rt[0] * x / (rs[0] + x)
    fill = size / q
    t_exit, stopped = c + 300.0, False
    idx = np.where((a["recv"] > te) & (a["recv"] <= c + 300.0) & (a["mid"] <= (1 - X) * fill))[0]
    if len(idx):
        t_exit, stopped = a["recv"][idx[0]] + lat, True
    rs2, rt2, f2, ok2 = L.state_for(a, np.array([t_exit]), "sell")
    if not ok2[0]:
        return None
    return rs2[0] * q / (rt2[0] + q) * (1 - f2[0]) - size, stopped


def main(split, keep=None):
    df, created = B.load(split)
    rows = []
    for pool, g in df.groupby("pool", sort=False):
        a = L.pool_arrays(g)
        c = created[pool]
        for lat in (0.25, 1.0):
            for X in (0.2, 0.3):
                r = trip(a, c, lat, X)
                if r is not None:
                    rows.append({"cfg": f"L{lat}_X300_THIN_STOP{int(X*100)}", "created": c, "pnl": r[0], "stopped": r[1]})
    T = pd.DataFrame(rows)
    res = {}
    for cfg, s in T.groupby("cfg"):
        if keep and cfg not in keep:
            continue
        res[cfg] = {"stopped_frac": round(float(s.stopped.mean()), 3)}
        for tip in (0.001, 0.01):
            st = L.stats(s.pnl.to_numpy(), tip); st["pass"] = L.passes(st)
            if split == "train":
                st["oct1"] = L.stats(s[s.created < DAY2].pnl.to_numpy(), tip)
                st["oct2"] = L.stats(s[s.created >= DAY2].pnl.to_numpy(), tip)
            res[cfg][str(tip)] = st
    json.dump({"agent": "boost", "split": split, "modality": "onchain", "is_synthetic": False, "n_configs": 4,
               "doc": __doc__, "results": res}, open(OUT.format("" if split == "train" else "valid_"), "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:] or None)
