"""Iteration 10: add market-wide regime features to the snapshot models (ml_snapshots + ml_exits).

At each snapshot time t (point in time): launches in the last 10 / 60 min, curve completions in the last 60 min,
completions per launch over the last 60 min, curve trades in the last 1 min. H8's result swung with the day's
completion rate (33% vs 19%), so the regime may change which entries pay.

    python scripts/research/ml_regime.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts/research"))
import duckdb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import ml_exits  # noqa: E402
import ml_model  # noqa: E402
from pipeline import config  # noqa: E402

REGIME = ["launches_10m", "launches_60m", "completes_60m", "complete_rate_60m", "trades_1m"]


def add_regime(d: pd.DataFrame) -> pd.DataFrame:
    con = duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
    cr = np.sort(np.array([r[0] for r in con.execute("SELECT min(recv) FROM curve_creates GROUP BY mint").fetchall()]))
    co = np.sort(np.array([r[0] for r in con.execute("SELECT min(recv) FROM curve_completes GROUP BY mint").fetchall()]))
    tr = np.sort(con.execute("SELECT recv FROM curve_trades").fetchnumpy()["recv"])
    t = d.t.to_numpy()
    cnt = lambda arr, w: np.searchsorted(arr, t, side="right") - np.searchsorted(arr, t - w, side="right")
    d = d.copy()
    d["launches_10m"], d["launches_60m"] = cnt(cr, 600), cnt(cr, 3600)
    d["completes_60m"] = cnt(co, 3600)
    d["complete_rate_60m"] = d.completes_60m / d.launches_60m.clip(lower=1)
    d["trades_1m"] = cnt(tr, 60)
    # the recorder was not always running: windows that reach back before the first recorded event are unknown
    first = min(cr[0], tr[0])
    for c in REGIME:
        d.loc[t - 3600 < first, c] = np.nan
    return d


if __name__ == "__main__":
    d = add_regime(pd.read_parquet(config.path("data") / "processed" / "ml_snapshots.parquet"))
    ml_exits.FEATURES = ml_model.FEATURES + REGIME
    import ml_exits as me
    me.FEATURES = ml_model.FEATURES + REGIME
    res = []
    for lab in [c for c in d.columns if c.startswith("g_tp")]:
        r = me.run(d, lab)
        res.append(r)
        for q, k in r["by_quantile"].items():
            t_, v = k["train_oof"]["tip_0.001"], k["validation"]["tip_0.001"]
            print(f"{lab} q{q} train n={t_['n']} exp={t_['expectancy_sol']} pf={t_['profit_factor']} | "
                  f"val n={v['n']} exp={v['expectancy_sol']} pf={v['profit_factor']} wo3={v['pnl_without_top3']}")
    (ROOT / "research/observations/evidence_ml_regime_20261003.json").write_text(json.dumps(res, indent=1))
