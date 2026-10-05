"""H-UPBITLEAD coin selection (pre-train data only: 2025-03 daily volumes).

Rule frozen in reports/hypotheses/upbitlead_preregistration.json (universe.selection_rule_pre_train_only).
Writes data/raw/web/upbitlead/selection_202503.json and prints the list.
"""
from __future__ import annotations

import io, json, time, zipfile
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/raw/web/upbitlead"
OUT.mkdir(parents=True, exist_ok=True)
S = requests.Session()
EXCL = {"USDT", "USDC", "USD1", "USDE", "USDS", "USDG", "RLUSD", "PYUSD", "EURC", "JPYC", "XAUT"}
PREFIX = [("", 1), ("1000", 1000), ("1000000", 1_000_000), ("1M", 1_000_000)]


def upbit(path, **params):
    for a in range(6):
        r = S.get("https://api.upbit.com/v1/" + path, params=params, timeout=30)
        if r.status_code == 429:
            time.sleep(1 + a); continue
        if r.status_code == 404:
            return None
        r.raise_for_status(); time.sleep(0.15)
        return r.json()
    raise RuntimeError("upbit 429s")


def bn_daily(sym):
    url = f"https://data.binance.vision/data/futures/um/monthly/klines/{sym}/1d/{sym}-1d-2025-03.zip"
    r = S.get(url, timeout=60)
    if r.status_code != 200:
        return None
    z = zipfile.ZipFile(io.BytesIO(r.content))
    df = pd.read_csv(z.open(z.namelist()[0]), header=None)
    if not str(df.iloc[0, 0]).isdigit():
        df = df.iloc[1:]
    return df[7].astype(float)  # quote volume


def main():
    mk = [m["market"] for m in upbit("market/all", isDetails="false") if m["market"].startswith("KRW-")]
    coins = sorted(m[4:] for m in mk if m[4:] not in EXCL)
    usdt = upbit("candles/days", market="KRW-USDT", count=31, to="2025-04-01T00:00:00Z")
    krw_usd = {c["candle_date_time_utc"][:10]: c["trade_price"] for c in usdt}
    rows = []
    for c in coins:
        sym = mult = qv = None
        for p, m in PREFIX:
            q = bn_daily(f"{p}{c}USDT")
            if q is not None:
                sym, mult, qv = f"{p}{c}USDT", m, q; break
        if sym is None:
            rows.append({"coin": c, "binance": None}); continue
        d = upbit("candles/days", market=f"KRW-{c}", count=31, to="2025-04-01T00:00:00Z") or []
        d = [x for x in d if x["candle_date_time_utc"][:7] == "2025-03"]
        up_usd = sum(x["candle_acc_trade_price"] / krw_usd.get(x["candle_date_time_utc"][:10], 1450.0) for x in d)
        rows.append({"coin": c, "binance": sym, "mult": mult, "upbit_days": len(d), "upbit_usd_mar": up_usd,
                     "bn_qv_mar": float(qv.sum()), "bn_mean_daily": float(qv.mean()),
                     "upbit_mean_daily": up_usd / 31, "ratio": up_usd / float(qv.sum()) if qv.sum() else None})
        print(rows[-1], flush=True)
    df = pd.DataFrame(rows)
    ok = df[df.binance.notna()].copy()
    ok["drop_major"] = ok.bn_mean_daily > 300e6
    ok["eligible"] = (~ok.drop_major) & (ok.bn_mean_daily >= 2e6) & (ok.upbit_mean_daily >= 0.5e6) & (ok.upbit_days == 31)
    sel = ok[ok.eligible].sort_values("ratio", ascending=False).head(40)
    hl = requests.post("https://api.hyperliquid.xyz/info", json={"type": "meta"}, timeout=30).json()
    hlnames = {u["name"] for u in hl["universe"] if not u.get("isDelisted")}
    out = {"rule": "see reports/hypotheses/upbitlead_preregistration.json universe.selection_rule_pre_train_only",
           "krw_markets": len(mk), "candidates_non_stable": len(coins), "with_binance_perp_2025_03": int(len(ok)),
           "eligible": int(ok.eligible.sum()),
           "coin_list": [{"coin": r.coin, "binance": r.binance, "mult": int(r.mult), "ratio_mar25": round(r.ratio, 4),
                          "bn_mean_daily_musd": round(r.bn_mean_daily / 1e6, 2),
                          "upbit_mean_daily_musd": round(r.upbit_mean_daily / 1e6, 2),
                          "hl_listed_20261005": (r.coin in hlnames) or (f"k{r.coin}" in hlnames)} for r in sel.itertuples()],
           "all_rows": json.loads(ok.to_json(orient="records")),
           "no_binance_perp_2025_03": df[df.binance.isna()].coin.tolist()}
    (OUT / "selection_202503.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out["coin_list"], indent=0))


if __name__ == "__main__":
    main()
