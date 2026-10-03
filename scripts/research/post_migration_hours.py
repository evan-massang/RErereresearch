"""Hour-scale behaviour of migrated tokens (15-min GeckoTerminal OHLCV, survivorship-free universe).

At decision time D = migration + h, only bars that ENDED by D are used (bar start + 15 min <= D). Entry at the
open of the first bar starting at or after D; exit at the close of the last bar ending by D + hold (no bar =
no trade then; the last known close is used, so dead tokens count at their last price). Costs: COST per side.

    python scripts/research/post_migration_hours.py describe <from_unix> <to_unix>   # migrations in window
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

DIR = ROOT / "data/raw/web/ohlcv15"
BAR = 900
COST = 0.02
HS = (1, 2, 4, 8, 12, 24)
HOLDS = (4, 24)


def load() -> list[dict]:
    out = []
    for f in DIR.glob("*.json"):
        d = json.loads(f.read_text())
        if d["ohlcv"]:
            d["bars"] = np.array(d["ohlcv"], dtype=float)
            out.append(d)
    return out


def snapshot(d: dict, h: float, hold: float) -> dict | None:
    b, t0 = d["bars"], d["migrated_recv"]
    D = t0 + h * 3600
    known = b[b[:, 0] + BAR <= D]
    if not len(known):
        return None
    after = b[b[:, 0] >= D]
    if not len(after) or after[0, 0] > D + 3600:      # nothing trades within an hour of D: cannot enter
        return None
    entry = after[0, 1]
    fin = b[b[:, 0] + BAR <= D + hold * 3600]
    if fin[-1, 0] + BAR > d["fetched_at"]:
        pass
    if D + hold * 3600 > d["fetched_at"]:
        return None                                    # outcome not observable yet
    exit_ = fin[-1, 4]
    c = known[:, 4]
    last1h = known[known[:, 0] + BAR > D - 3600]
    last4h = known[known[:, 0] + BAR > D - 4 * 3600]
    return {"pool": d["pool"], "mint": d["mint"], "h": h, "hold": hold, "D": D,
            "price": c[-1], "ath": known[:, 2].max(), "from_ath": c[-1] / known[:, 2].max() - 1,
            "ret_1h": c[-1] / last1h[0, 1] - 1 if len(last1h) else np.nan,
            "ret_4h": c[-1] / last4h[0, 1] - 1 if len(last4h) else np.nan,
            "vol_1h": float(last1h[:, 5].sum()), "vol_4h": float(last4h[:, 5].sum()),
            "bars_1h": int(len(last1h)), "mcap_usd": c[-1] * 1e9,
            "fwd": exit_ / entry - 1, "net": (exit_ * (1 - COST)) / (entry * (1 + COST)) - 1}


def table(ds: list[dict], a: float, b: float) -> pd.DataFrame:
    rows = [s for d in ds if a <= d["migrated_recv"] < b for h in HS for hold in HOLDS
            if (s := snapshot(d, h, hold)) is not None]
    return pd.DataFrame(rows)


if __name__ == "__main__":
    ds = load()
    t = table(ds, float(sys.argv[2]), float(sys.argv[3]))
    print(len(ds), "pools loaded;", t.mint.nunique(), "tokens in window")
    g = t.groupby(["h", "hold"]).agg(n=("net", "size"), med_net=("net", "median"), mean_net=("net", "mean"),
                                     share_up=("net", lambda x: (x > 0).mean()), share_2x=("fwd", lambda x: (x >= 1).mean()))
    print(g.round(3))
