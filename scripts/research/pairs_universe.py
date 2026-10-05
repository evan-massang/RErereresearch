"""H-PAIRS universe: weekly (Monday 00:00 UTC) top-N Binance USDT-M perps by prior 30-day quote volume,
restricted to coins present in Hyperliquid perp meta (snapshot data/raw/web/pairs/hl_meta_20261005.json).
Uses only daily klines closed before each Monday (data/raw/web/momentum/klines, months <= 2026-03).
Output: data/raw/web/pairs/universe.json  {monday_iso: [symbols]}"""
import json, re
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
KL = ROOT / "data/raw/web/momentum/klines"
OUT = ROOT / "data/raw/web/pairs"
N = 30
START, END = "2024-07-01", "2026-03-30"   # Mondays; holdout (>= 2026-04-01) never used
STABLE = {"USDC", "TUSD", "BUSD", "FDUSD", "USDP", "USDE", "PAXG", "XAUT", "BTCDOM", "DEFI", "FOOTBALL", "BLUEBIRD"}


def hl_names():
    m = json.load(open(OUT / "hl_meta_20261005.json"))
    return {u["name"] for u in m["universe"]}


def to_hl(sym, hl):
    base = sym[:-4]
    if base in hl:
        return base
    mm = re.match(r"^1000+(.*)$", base)
    if mm and "k" + mm.group(1) in hl:
        return "k" + mm.group(1)
    if "k" + base in hl:            # e.g. NEIROUSDT -> kNEIRO, DOGSUSDT -> kDOGS
        return "k" + base
    return None


def main():
    hl = hl_names()
    vols = {}
    for p in KL.glob("*USDT.parquet"):
        sym = p.stem
        if not re.match(r"^[0-9A-Z]+USDT$", sym) or sym[:-4] in STABLE:
            continue
        h = to_hl(sym, hl)
        if h is None:
            continue
        d = pd.read_parquet(p, columns=["open_time", "quote_volume"])
        d["day"] = pd.to_datetime(d.open_time, unit="ms", utc=True).dt.normalize()
        vols[sym] = d.set_index("day").quote_volume
    V = pd.DataFrame(vols).sort_index()
    uni, hlmap = {}, {}
    for t in pd.date_range(START, END, freq="W-MON", tz="UTC"):
        w = V.loc[(V.index >= t - pd.Timedelta(days=30)) & (V.index < t)]
        ok = w.notna().sum() >= 30          # full 30-day history before t
        s = w.sum()[ok].sort_values(ascending=False).head(N)
        uni[t.strftime("%Y-%m-%d")] = list(s.index)
    syms = sorted({s for v in uni.values() for s in v})
    hlmap = {s: to_hl(s, hl) for s in syms}
    json.dump({"N": N, "universe": uni, "hl_name": hlmap}, open(OUT / "universe.json", "w"), indent=0)
    print(len(uni), "weeks;", len(syms), "distinct symbols")


if __name__ == "__main__":
    main()
