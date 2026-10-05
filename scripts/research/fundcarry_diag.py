"""H-FUNDCARRY proxy check (train period only, no strategy outcomes).

The simulator prices the perp leg as spot * (1 + premium_t) because Hyperliquid does not serve 1h perp candles
for the train period. Here we compare that proxy with the observed basis perp_4h_close / spot_close - 1 at the
same timestamps (HL 4h candles reach back ~5000 x 4h), for timestamps < 2026-01-01.
Also summarises funding coverage per coin.

    python scripts/research/fundcarry_diag.py
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
HL = ROOT / "data/raw/web/hyperliquid"
SPOT = ROOT / "data/raw/web/spot_ohlcv"
H = 3600_000
TRAIN_END = 1767225600000


def main():
    umap = json.loads((HL / "universe_map.json").read_text())
    rows, allerr = {}, []
    for coin, v in umap.items():
        try:
            fr = json.loads((HL / f"funding_{coin}.json").read_text())["rows"]
            sp = json.loads((SPOT / f"{coin}_1h.json").read_text())
            c4 = json.loads((HL / f"candles_4h_{coin}.json").read_text())["rows"]
        except FileNotFoundError:
            rows[coin] = "missing"
            continue
        prem = {x["time"] // H * H: float(x["premium"]) for x in fr}
        spot = {r[0] + H: r[4] * v["mult"] for r in sp["rows"]}
        err, obs = [], []
        for c in c4:
            tc = (c["T"] + 1) // H * H
            if tc >= TRAIN_END or tc not in spot or tc not in prem:
                continue
            b = float(c["c"]) / spot[tc] - 1
            obs.append(b)
            err.append(b - prem[tc])
        rate = np.array([float(x["fundingRate"]) for x in fr if x["time"] < TRAIN_END])
        rows[coin] = dict(venue=sp["venue"], funding_hours=len(fr), first=fr[0]["time"] if fr else None,
                          spot_hours=len(sp["rows"]), n4h=len(err),
                          basis_obs_mad=float(np.median(np.abs(obs))) if obs else None,
                          proxy_err_mad=float(np.median(np.abs(err))) if err else None,
                          proxy_err_p95=float(np.percentile(np.abs(err), 95)) if err else None,
                          mean_funding_ann=float(rate.mean() * 8760) if len(rate) else None)
        allerr += err
    out = dict(per_coin=rows, pooled=dict(n=len(allerr), mad=float(np.median(np.abs(allerr))),
                                          p95=float(np.percentile(np.abs(allerr), 95)),
                                          mean=float(np.mean(allerr))))
    for k, r in rows.items():
        print(k, r)
    print("pooled", out["pooled"])
    (ROOT / "research/observations/evidence_fundcarry_proxycheck.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
