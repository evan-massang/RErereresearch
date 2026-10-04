"""Train-only exploration: mid-price path of BOOST pools relative to entry at creation + L. Agent boost."""
import numpy as np, pandas as pd, sys
sys.path.insert(0, "/home/user/RErereresearch/scripts/research")
import boost_lib as B, amm_flow_lib as L

df, created = B.load("train")
print("pools", df.pool.nunique(), "rows", len(df))
rows = []
for pool, g in df.groupby("pool", sort=False):
    a = L.pool_arrays(g)
    c = created[pool]
    r = {"pool": pool}
    for lat in (0.25, 1.0):
        rs, rt, f, ok = L.state_for(a, np.array([c + lat]), "buy")
        r[f"p_in{lat}"] = rs[0] / rt[0]; r[f"rs_in{lat}"] = rs[0]
    for t in (5, 30, 60, 120, 180, 240, 300, 340, 360, 420, 600, 840):
        rs, rt, f, ok = L.state_for(a, np.array([c + t]), "sell")
        r[f"p{t}"] = rs[0] / rt[0]
    r["p0"] = (L.OFFSET + 84.99 - L.OFFSET) / 206900000.0
    rows.append(r)
R = pd.DataFrame(rows)
for lat in (0.25, 1.0):
    print(f"--- entry lat {lat}: entry price / initial price", (R[f"p_in{lat}"] / R.p0).describe(percentiles=[.1, .5, .9]).round(3).to_dict())
    for t in (5, 30, 60, 120, 180, 240, 300, 340, 360, 420, 600, 840):
        x = R[f"p{t}"] / R[f"p_in{lat}"] - 1
        print(t, "mean %.4f median %.4f win %.3f p10 %.3f p90 %.3f" % (x.mean(), x.median(), (x > 0).mean(), x.quantile(.1), x.quantile(.9)))
R.to_parquet("/tmp/claude-0/-home-user-RErereresearch/f8ba0823-6528-5b3d-92e7-a2d8665674ee/scratchpad/explore_train.parquet")
