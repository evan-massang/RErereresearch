"""H-QIMAKER coin selection (outcome-free: spreads and print counts only).
Rule frozen in reports/hypotheses/qimaker_preregistration.json."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PQ = ROOT / "data/raw/web/tardis/parquet"
CANDS = ["WIF", "kBONK", "FARTCOIN", "PUMP"]
DAYS = ["2024-11-01", "2024-12-01", "2025-01-01", "2025-02-01", "2025-03-01", "2025-04-01",
        "2025-05-01", "2025-06-01", "2025-07-01", "2025-08-01", "2025-09-01", "2025-10-01",
        "2025-11-01", "2025-12-01", "2026-01-01", "2026-02-01", "2026-03-01"]


def min_tick(q: pd.DataFrame) -> float:
    p = np.unique(np.concatenate([q.bid_price.to_numpy(), q.ask_price.to_numpy()]))
    d = np.diff(p)
    d = d[d > 0]
    return float(np.round(d.min(), 12))


def tick_arr(mid: np.ndarray, mt: float) -> np.ndarray:
    # HL: 5 significant figures, but integer prices are always allowed -> cap the sig-fig tick at 1.0
    # (bug fix 2026-10-05 after the first train/validation run: BTC > $100k was assigned a $10 tick).
    return np.maximum(np.minimum(10.0 ** (np.floor(np.log10(mid)) - 4), 1.0), mt)


def stats(coin: str, day: str) -> dict:
    q = pd.read_parquet(PQ / f"quotes_{day}_{coin}.parquet").sort_values("local_timestamp")
    q = q[(q.bid_price > 0) & (q.ask_price > q.bid_price)]
    t = pd.read_parquet(PQ / f"trades_{day}_{coin}.parquet")
    mt = min_tick(q)
    lt = q.local_timestamp.to_numpy(np.int64)
    grid = np.arange(lt[0] // 1_000_000 + 1, lt[-1] // 1_000_000 + 1) * 1_000_000
    i = np.searchsorted(lt, grid, "right") - 1
    b, a = q.bid_price.to_numpy()[i], q.ask_price.to_numpy()[i]
    tk = tick_arr((a + b) / 2, mt)
    one = np.abs((a - b) / tk - 1) < 1e-6 * ((a + b) / 2) / tk + 1e-6
    return dict(coin=coin, day=day, min_tick=mt, frac_1tick=round(float(one.mean()), 4),
                n_prints=int(len(t)), n_snapshots=int(len(q)),
                median_spread_bp=round(float(np.median((a - b) / ((a + b) / 2)) * 1e4), 3))


def main():
    out = {}
    for c in CANDS:
        first = next((d for d in DAYS if (PQ / f"quotes_{d}_{c}.parquet").exists()), None)
        s = stats(c, first)
        s["qualifies"] = bool(s["frac_1tick"] >= 0.70 and s["n_prints"] >= 5000)
        out[c] = s
        print(s)
    json.dump(out, open(ROOT / "data/raw/web/tardis/results/qimaker_coin_selection.json", "w"), indent=1)


if __name__ == "__main__":
    main()
