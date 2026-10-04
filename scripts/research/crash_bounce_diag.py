"""Train-only diagnostics for crash_bounce_build.py events: price path after the trigger, and losses by bucket.

Checks the failure is real (not a fill bug): median price relative to the trigger print at +1 s (entry), +5, +30,
+60, +300 s; the round trip of an immediate exit (cost floor); and net PnL by market cap at trigger / top seller.

    python scripts/research/crash_bounce_diag.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "research"))
import duckdb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import crash_bounce_build as cb  # noqa: E402
import event_studies as es  # noqa: E402
from pipeline import config  # noqa: E402

d = pd.read_parquet(cb.EVENTS)
tr = cb.split(d, "train")
x = tr[tr.variant == "d40_w30"].copy()
con = duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
comp = dict(con.execute(f"SELECT mint, min(recv) FROM curve_completes WHERE {cb.ALLOWED} GROUP BY 1").fetchall())
rng = np.random.default_rng(0)
samp = x.sample(min(600, len(x)), random_state=0)
paths, floor, peak = [], [], []
for r in samp.itertuples():
    q = con.execute(f"SELECT recv, vsol, vtok FROM curve_trades WHERE mint = ? AND {cb.ALLOWED} ORDER BY recv, rowid",
                    [r.mint]).fetchall()
    T = np.array([a[0] for a in q]); vs = np.array([a[1] for a in q]); vt = np.array([a[2] for a in q])
    px = vs / vt
    k0 = np.searchsorted(T, r.t, side="right") - 1
    row = {}
    for h in (1, 5, 30, 60, 300):
        k = np.searchsorted(T, r.t + h, side="right") - 1
        row[f"+{h}s"] = px[k] / px[k0]
    paths.append(row)
    k1 = np.searchsorted(T, r.t + 1, side="right") - 1
    floor.append(es.rt(vs[k1], vt[k1], vs[k1], vt[k1]))  # immediate round trip at the entry state
    lim = np.searchsorted(T, r.t + 301, side="right")
    peak.append(px[k1:lim].max() / px[k1] - 1)
P = pd.DataFrame(paths)
out = {
    "variant": "d40_w30", "n_sampled": len(samp),
    "median_px_rel_trigger": P.median().round(4).to_dict(),
    "mean_px_rel_trigger": P.mean().round(4).to_dict(),
    "share_up_vs_trigger": (P > 1).mean().round(3).to_dict(),
    "immediate_roundtrip_sol_median": round(float(np.median(floor)), 4),
    "max_gain_within_300s_from_entry_quantiles": {q: round(float(np.quantile(peak, q)), 3) for q in (.25, .5, .75, .9)},
}
col = "g_tp30_sl15_60"
x["mc_bucket"] = pd.cut(x.mcap, [0, 30, 40, 60, 100, 1e9])
out["net_0.001_by_mcap_" + col] = {str(k): {"n": int(len(g)), "mean": round(float(g[col].mean() - 0.002), 4)}
                                   for k, g in x.groupby("mc_bucket", observed=True)}
m = tr[tr.variant == "d40_w30_mech"]
out["mech_by_top_seller_" + col] = {k: {"n": int(len(g)), "mean": round(float(g[col].mean() - 0.002), 4)}
                                    for k, g in m.groupby("top_seller")}
x["age_bucket"] = pd.cut(x.age, [0, 60, 300, 1800, 1e9])
out["net_0.001_by_age_" + col] = {str(k): {"n": int(len(g)), "mean": round(float(g[col].mean() - 0.002), 4)}
                                  for k, g in x.groupby("age_bucket", observed=True)}
(cb.EVID / "evidence_crash_bounce_train_diag_20261004.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
