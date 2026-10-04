"""Diagnostic (train only): gross mid-to-mid return of the grid's trades, with and without the conservative
fill choice, to separate 'no signal' from 'signal eaten by costs'. Agent amm_flow."""
import json, sys
import numpy as np, pandas as pd
sys.path.insert(0, "/home/user/RErereresearch/scripts/research")
import amm_flow_lib as L, amm_flow_sim as S

snap = pd.read_parquet(sys.argv[1])
df, _ = L.load("train")
arr = {p: {"main": L.pool_arrays(g)} for p, g in df.groupby("pool", sort=False)}
del df
out = {}
for name, (rule, ex) in S.GRID.items():
    tr = pd.DataFrame(S.simulate(snap, arr, rule, ex))
    if tr.empty:
        continue
    g_cons, g_plain = [], []
    for r in tr.itertuples():
        a = arr[r.pool]["main"]
        te, tx = np.array([r.t + 1]), np.array([r.t + 1 + r.hold])
        b = L.state_for(a, te, "buy"); s = L.state_for(a, tx, "sell")
        g_cons.append((s[0] / s[1])[0] / (b[0] / b[1])[0] - 1)
        i0 = np.searchsorted(a["recv"], te, "right") - 1; i1 = np.searchsorted(a["recv"], tx, "right") - 1
        g_plain.append(a["mid"][i1][0] / a["mid"][i0][0] - 1)
    g_cons, g_plain = np.array(g_cons), np.array(g_plain)
    out[name] = {"n": len(tr), "gross_mid_ret_conservative_mean": round(float(g_cons.mean()), 4),
                 "gross_mid_ret_plain_mean": round(float(g_plain.mean()), 4),
                 "gross_mid_ret_plain_median": round(float(np.median(g_plain)), 4),
                 "net_sol_per_trade_tip0.001": round(float(tr.pnl.mean() - 0.002), 4)}
    print(name, out[name], flush=True)
json.dump(out, open(sys.argv[2], "w"), indent=1)
