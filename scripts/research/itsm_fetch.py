"""H-ITSM data: point-in-time monthly universe (top 30 HL-listed Binance USDT-M perps by prior-month quote volume)
and 15m futures klines from data.binance.vision for members (month M and M-1 for the sigma lookback).

Pre-registration: reports/hypotheses/itsm_preregistration.json. Holdout guard: no month >= 2026-04 is requested.
Writes data/raw/web/itsm/: universe.json, k15/<SYM>.parquet (open_time ms, o, c, qv), fetch_log.json.
Zips are streamed in memory and discarded. Stops if free disk < 2.5 GB or downloads exceed 800 MB.
"""
import io, json, shutil, sys, time, zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import httpx
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/raw/web/itsm"
DK = ROOT / "data/raw/web/momentum/klines"  # read-only reuse: daily klines, all archive USDT-M perps
DV = "https://data.binance.vision/data/futures/um/monthly/klines/{s}/15m/{s}-15m-{m}.zip"
STABLE = {"USDC", "FDUSD", "TUSD", "BUSD", "USDP", "DAI", "EUR", "AEUR", "USDE", "PYUSD", "USD1", "UST", "USTC"}
TRADE_MONTHS = [str(p) for p in pd.period_range("2022-01", "2026-03", freq="M")]
LAST_MONTH = "2026-03"
TOPN = 30
MIN_FREE = 2.5e9
MAX_BYTES = 800e6
BYTES = {"n": 0}


def hl_map():
    u = json.loads((OUT / "hl_meta_raw.json").read_text())["universe"]
    m = {}
    for x in u:
        n = x["name"]
        m[n + "USDT"] = n
        if n.startswith("k"):
            m["1000" + n[1:] + "USDT"] = n
    return m


def universe():
    hl = hl_map()
    rows = []
    for p in DK.glob("*.parquet"):
        s = p.stem
        if not s.endswith("USDT") or s[:-4] in STABLE or s not in hl:
            continue
        d = pd.read_parquet(p, columns=["open_time", "quote_volume"])
        d["month"] = pd.to_datetime(d.open_time, unit="ms").dt.to_period("M").astype(str)
        g = d.groupby("month").agg(qv=("quote_volume", "sum"), days=("quote_volume", "size")).reset_index()
        g["symbol"] = s
        rows.append(g)
    v = pd.concat(rows)
    uni = {}
    for m in TRADE_MONTHS:
        prev = str(pd.Period(m, "M") - 1)
        c = v[(v.month == prev) & (v.days >= 28)].sort_values("qv", ascending=False).head(TOPN)
        uni[m] = list(c.symbol)
    (OUT / "universe.json").write_text(json.dumps({"rule": "top30 HL-mapped USDT-M perps by M-1 quote volume, >=28 daily bars, no stables",
                                                   "hl_mapped_symbols": len(set(v.symbol)), "data": uni}, indent=0))
    print("hl-mapped archive symbols", v.symbol.nunique(), "unique members", len({s for x in uni.values() for s in x}))
    for m in ("2022-01", "2024-01", "2025-07", "2026-03"):
        print(m, uni[m])


def get(cl, s, m):
    if m > LAST_MONTH:
        raise RuntimeError("holdout guard")
    for a in range(5):
        try:
            r = cl.get(DV.format(s=s, m=m))
            if r.status_code == 404:
                return None
            r.raise_for_status()
            BYTES["n"] += len(r.content)
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                raw = z.read(z.namelist()[0]).decode()
            a_ = np.array([[float(x[0]), float(x[1]), float(x[4]), float(x[7])]
                           for x in (l.split(",") for l in raw.strip().splitlines()) if x[0][:1].isdigit()])
            if not len(a_):
                return None
            df = pd.DataFrame(a_, columns=["t", "o", "c", "qv"])
            t = df.t.astype("int64")
            df["t"] = np.where(t > 10**14, t // 1000, t)
            return df
        except Exception:
            time.sleep(2 * (a + 1))
    return "ERR"


def data():
    uni = json.loads((OUT / "universe.json").read_text())["data"]
    need = {}
    for m, syms in uni.items():
        for s in syms:
            need.setdefault(s, set()).update({m, str(pd.Period(m, "M") - 1)})
    (OUT / "k15").mkdir(parents=True, exist_ok=True)
    log = {"missing": [], "err": []}
    with httpx.Client(timeout=60, limits=httpx.Limits(max_connections=16)) as cl:
        for i, (s, months) in enumerate(sorted(need.items())):
            p = OUT / "k15" / f"{s}.parquet"
            if p.exists():
                continue
            if shutil.disk_usage("/").free < MIN_FREE or BYTES["n"] > MAX_BYTES:
                print("STOP: disk/budget", shutil.disk_usage("/").free, BYTES["n"]); break
            ms = sorted(months)
            with ThreadPoolExecutor(12) as ex:
                res = list(ex.map(lambda m: get(cl, s, m), ms))
            parts = []
            for m, r in zip(ms, res):
                if r is None: log["missing"].append(f"{s} {m}")
                elif isinstance(r, str): log["err"].append(f"{s} {m}")
                else: parts.append(r)
            if parts:
                df = pd.concat(parts).drop_duplicates("t").sort_values("t")
                df = df.astype({"o": "float64", "c": "float64", "qv": "float32"})
                df.to_parquet(p, index=False)
            print(i, s, len(ms), "MB", round(BYTES["n"] / 1e6, 1), flush=True)
    log["bytes"] = BYTES["n"]
    (OUT / "fetch_log.json").write_text(json.dumps(log, indent=0))
    print("done bytes", BYTES["n"], "missing", len(log["missing"]), "err", len(log["err"]))


if __name__ == "__main__":
    {"universe": universe, "data": data}[sys.argv[1]]()
