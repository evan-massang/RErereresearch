"""H-PREMCONV step 1: point-in-time universe (top 30 USDT perps by prior-month futures quote volume, with a spot pair).

Public data only (data.binance.vision S3 listing + monthly 1d klines). Writes data/raw/web/binance_prem/:
  spot_symbols.json, um_symbols.json, monthly_vol.parquet (symbol, month, fut_qv, fut_days, spot_qv, spot_days),
  universe.json  {month: [ {perp, spot, mult} ... ]}
    python scripts/research/premconv_universe.py
"""
import io
import json
import re
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/raw/web/binance_prem"
S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
DV = "https://data.binance.vision/data"
STABLE = {"USDC", "FDUSD", "TUSD", "BUSD", "USDP", "DAI", "EUR", "AEUR", "USDE", "PYUSD", "USD1", "UST", "USTC"}
RANK_MONTHS = [str(p) for p in pd.period_range("2022-12", "2026-02", freq="M")]  # M-1 for M in 2023-01..2026-03
TOPN = 30


def s3_prefixes(cl, prefix):
    out, marker = [], ""
    while True:
        r = cl.get(S3, params={"prefix": prefix, "delimiter": "/", "marker": marker})
        r.raise_for_status()
        ps = [x for x in re.findall(r"<Prefix>([^<]+)</Prefix>", r.text) if x != prefix]
        out += ps
        if "<IsTruncated>true</IsTruncated>" not in r.text:
            return [x.rstrip("/").split("/")[-1] for x in out]
        marker = re.search(r"<NextMarker>([^<]+)</NextMarker>", r.text).group(1)


def cached_list(cl, name, prefix):
    p = OUT / name
    if not p.exists():
        p.write_text(json.dumps({"fetched_at": time.time(), "prefix": prefix, "data": s3_prefixes(cl, prefix)}))
    return json.loads(p.read_text())["data"]


def map_spot(perp, spot_set):
    if not perp.endswith("USDT") or "_" in perp:
        return None
    base = perp[:-4]
    if base in STABLE:
        return None
    if base + "USDT" in spot_set:
        return (base + "USDT", 1)
    for pre, m in (("1000000", 1_000_000), ("1000", 1000), ("1M", 1_000_000)):
        if base.startswith(pre) and base[len(pre):] + "USDT" in spot_set and base[len(pre):] not in STABLE:
            return (base[len(pre):] + "USDT", m)
    return None


def get_1d(cl, market, sym, month):
    path = "futures/um" if market == "fut" else "spot"
    url = f"{DV}/{path}/monthly/klines/{sym}/1d/{sym}-1d-{month}.zip"
    for a in range(4):
        try:
            r = cl.get(url)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                raw = z.read(z.namelist()[0]).decode()
            rows = [l.split(",") for l in raw.strip().splitlines() if l and l[0].isdigit()]
            return (sum(float(x[7]) for x in rows), len(rows))
        except Exception:
            time.sleep(2 * (a + 1))
    return "ERR"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=60, limits=httpx.Limits(max_connections=24)) as cl:
        spot = set(cached_list(cl, "spot_symbols.json", "data/spot/monthly/klines/"))
        um = cached_list(cl, "um_symbols.json", "data/futures/um/monthly/klines/")
        pairs = {p: m for p in um if (m := map_spot(p, spot))}
        print("perp symbols", len(um), "with spot pair", len(pairs))
        vp = OUT / "monthly_vol.parquet"
        done = pd.read_parquet(vp) if vp.exists() else pd.DataFrame(columns=["symbol", "month", "market", "qv", "days"])
        have = set(zip(done.symbol, done.month, done.market))
        jobs = [(p, mo, "fut") for p in pairs for mo in RANK_MONTHS if (p, mo, "fut") not in have]
        rows = []
        with ThreadPoolExecutor(24) as ex:
            for (p, mo, mk), res in zip(jobs, ex.map(lambda j: get_1d(cl, j[2], j[0], j[1]), jobs)):
                if res == "ERR":
                    print("ERR", p, mo, mk)
                    continue
                rows.append({"symbol": p, "month": mo, "market": mk,
                             "qv": res[0] if res else None, "days": res[1] if res else 0})
        done = pd.concat([done, pd.DataFrame(rows)], ignore_index=True)
        # spot check only for the top 45 perp candidates per month (enough to fill 30 after filters)
        f = done[(done.market == "fut") & (done.days > 0)]
        cand = f.sort_values("qv", ascending=False).groupby("month").head(45)
        have = set(zip(done.symbol, done.month, done.market))
        sj = [(pairs[p][0], mo, "spot") for p, mo in zip(cand.symbol, cand.month) if (pairs[p][0], mo, "spot") not in have]
        sj = list(dict.fromkeys(sj))
        rows = []
        with ThreadPoolExecutor(24) as ex:
            for (s, mo, mk), res in zip(sj, ex.map(lambda j: get_1d(cl, "spot", j[0], j[1]), sj)):
                if res == "ERR":
                    print("ERR", s, mo, mk)
                    continue
                rows.append({"symbol": s, "month": mo, "market": mk,
                             "qv": res[0] if res else None, "days": res[1] if res else 0})
        done = pd.concat([done, pd.DataFrame(rows)], ignore_index=True)
        done.to_parquet(vp, index=False)

    fut = done[done.market == "fut"].set_index(["symbol", "month"])
    sp = done[done.market == "spot"].set_index(["symbol", "month"])
    uni = {}
    for mo in RANK_MONTHS:
        m_next = str(pd.Period(mo, "M") + 1)
        c = fut.xs(mo, level="month")
        c = c[c.days >= 28].sort_values("qv", ascending=False)
        members = []
        for p, r in c.iterrows():
            s, mult = pairs[p]
            if (s, mo) not in sp.index or sp.loc[(s, mo), "days"] < 28:
                continue
            members.append({"perp": p, "spot": s, "mult": mult, "prev_fut_qv": float(r.qv)})
            if len(members) == TOPN:
                break
        uni[m_next] = members
    (OUT / "universe.json").write_text(json.dumps({"rule": "top30 prior-month perp quote volume, spot pair, >=28 days both",
                                                   "data": uni}, indent=0))
    allsyms = {m["perp"] for v in uni.values() for m in v}
    print("months", len(uni), "unique symbols", len(allsyms))
    for mo in ("2023-01", "2024-06", "2025-07", "2026-03"):
        print(mo, [m["perp"] for m in uni[mo]])


if __name__ == "__main__":
    main()
