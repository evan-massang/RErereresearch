"""BOOST-window strategies: pre-declared grid, train selection, validation only for train passers. Agent boost.

Grid (30 configs) = entry latency {0.25, 1.0 s after the pool-creation event} x exit {5} x liquidity filter {3}.
Exits: X120 single sell at +120 s; X300 single at +300 s; X340 single at +340 s (end of BOOST window, median last
BOOST slice +341 s on train); S5 five equal slices at +60/120/180/240/300 s; S4 four slices at +90/180/270/330 s.
Liquidity filter on the pool SOL reserve at the entry instant (point in time; ~85 SOL unless a creation bundle hit):
ALL; THIN rs <= 150 SOL; BUNDLED rs > 150 SOL (150 chosen from the bimodal shape, not tuned).
Size 0.5 SOL, exact constant-product fills from amm_flow_lib (conservative state choice), fee_bps/1e4 per side,
tips 0.001 and 0.01 SOL per transaction (1 + number of exit slices).
Usage: python boost_sim.py train   |   python boost_sim.py valid <config> [<config> ...]
"""
import json, sys
import numpy as np, pandas as pd
sys.path.insert(0, "/home/user/RErereresearch/scripts/research")
import boost_lib as B, amm_flow_lib as L

EXITS = {"X120": [120.0], "X300": [300.0], "X340": [340.0], "S5": [60.0, 120, 180, 240, 300],
         "S4": [90.0, 180, 270, 330]}
LATS = [0.25, 1.0]
LIQ = ["ALL", "THIN", "BUNDLED"]
TIPS = [0.001, 0.01]
OUT = "/home/user/RErereresearch/research/observations/evidence_boost_{}_20261004.json"


def run(split):
    df, created = B.load(split)
    if split == "valid":
        assert df.recv.min() >= L.VAL_A
    rows = []
    for pool, g in df.groupby("pool", sort=False):
        a = L.pool_arrays(g)
        c = created[pool]
        for lat in LATS:
            rs, rt, f, ok = L.state_for(a, np.array([c + lat]), "buy")
            for ex, ts in EXITS.items():
                pnl, ntx = B.sliced_trip(a, c + lat, [c + t for t in ts])
                rows.append({"pool": pool, "created": c, "lat": lat, "exit": ex, "rs_in": rs[0], "pnl": pnl, "ntx": ntx})
    return pd.DataFrame(rows)


def evaluate(T):
    res = {}
    for lat in LATS:
        for ex in EXITS:
            for liq in LIQ:
                s = T[(T.lat == lat) & (T.exit == ex)]
                if liq == "THIN":
                    s = s[s.rs_in <= 150]
                elif liq == "BUNDLED":
                    s = s[s.rs_in > 150]
                name = f"L{lat}_{ex}_{liq}"
                res[name] = {}
                for tip in TIPS:
                    p = s.pnl.to_numpy() - (s.ntx.to_numpy() - 2) * tip  # stats() charges 2 tips itself
                    st = L.stats(p, tip)
                    st["pass"] = L.passes(st)
                    res[name][str(tip)] = st
    return res


if __name__ == "__main__":
    split = sys.argv[1]
    T = run(split)
    res = evaluate(T)
    if split == "valid":
        res = {k: v for k, v in res.items() if k in sys.argv[2:]}
    ev = {"agent": "boost", "date": "2026-10-04", "split": split, "modality": "onchain", "is_synthetic": False,
          "n_configs": 30, "pools": int(T.pool.nunique()), "grid_doc": __doc__, "results": res}
    json.dump(ev, open(OUT.format(split), "w"), indent=1)
    for k, v in sorted(res.items(), key=lambda kv: -(kv[1]["0.001"].get("net") or -99)):
        a, b = v["0.001"], v["0.01"]
        print(f"{k:22s} n={a['n']:4d} net={a['net']:8.3f} pf={a['pf']} ex3={a['net_ex3']} win={a['win']} | tip.01 net={b['net']:8.3f} pf={b['pf']} pass={a['pass']},{b['pass']}")
