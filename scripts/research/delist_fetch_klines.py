"""H-DELIST step 3: choose eligible events + hedge-basket members (from daily VOLUME only), then
download Binance USDT-M 1h monthly klines (data.binance.vision, months <= 2026-03) for the event tokens
and basket members in the months each event window touches. Output data/raw/web/delist/{plan.json,klines1h/<SYM>.parquet}.
"""
import io, json, shutil, sys, time, zipfile, datetime as dt
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pandas as pd, requests

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data/raw/web/delist"; KL = ROOT / "data/raw/web/momentum/klines"
OUT = D / "klines1h"; OUT.mkdir(parents=True, exist_ok=True)
DL = "https://data.binance.vision/data/futures/um/monthly/klines/{s}/1h/{s}-1h-{m}.zip"
LAST = "2026-03"
EXCL_BASE = set("BTC ETH USDC FDUSD TUSD BUSD USDP DAI USDE AEUR EUR PAX BTCDOM DEFI FOOTBALL BLUEBIRD XAU XAG XPT XPD PAXG XAUT COPPER "
                "TSLA NVDA MSTR COIN HOOD AAPL AMZN GOOGL META MSFT QQQ SPY CRCL AMD INTC PLTR".split())
KCOLS = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "count", "tbv", "tbqv", "ignore"]
sess = requests.Session()


def base(sym):
    b = sym[:-4]
    for p in ("1000000", "1000", "1M"):
        if b.startswith(p) and len(b) > len(p):
            return b[len(p):]
    return b


def months(t0, t1):
    out, m = [], pd.Timestamp(t0).to_period("M")
    while m <= pd.Timestamp(t1).to_period("M"):
        if str(m) <= LAST:
            out.append(str(m))
        m += 1
    return out


def main():
    ev = json.loads((D / "events.json").read_text())["events"]
    daily = {}
    for p in KL.glob("*.parquet"):
        daily[p.stem] = pd.read_parquet(p, columns=["open_time", "quote_volume"])
    plan = []
    for e in ev:
        if not e["perp"] or e["perp_age_days_at_ann"] < 30:
            continue
        ann = pd.Timestamp(e["ann_ms"], unit="ms", tz="UTC")
        day = (e["ann_ms"] // 86400000) * 86400000
        lo, hi = day - 30 * 86400000, day
        recent = {x["token"] for x in ev if 0 <= e["ann_ms"] - x["ann_ms"] <= 365 * 86400000 or x["ann_ms"] == e["ann_ms"]}
        vols = []
        for s, k in daily.items():
            b = base(s)
            if b in EXCL_BASE or b in recent:
                continue
            w = k[(k.open_time >= lo) & (k.open_time < hi)]
            if len(w) >= 25:
                vols.append((w.quote_volume.sum() / 30, s))
        vols.sort(reverse=True)
        tokw = daily[e["perp"]]; tokw = tokw[(tokw.open_time >= lo) & (tokw.open_time < hi)]
        plan.append({**e, "basket_top60": [s for _, s in vols[:60]],
                     "basket_adv": {s: v for v, s in vols[:60]},
                     "token_adv30": float(tokw.quote_volume.sum() / 30),
                     "months": months(ann - pd.Timedelta(days=1), ann + pd.Timedelta(days=16))})
    (D / "plan.json").write_text(json.dumps(plan, indent=1))
    need = {}
    for p in plan:
        for s in [p["perp"]] + p["basket_top60"]:
            need.setdefault(s, set()).update(p["months"])
    print(len(plan), "events;", len(need), "symbols;", sum(len(v) for v in need.values()), "symbol-months", file=sys.stderr)
    total = [0]

    def fetch(item):
        s, ms = item
        dest = OUT / f"{s}.parquet"
        if dest.exists():
            return s, "cached"
        if shutil.disk_usage("/").free < 2.5e9:
            return s, "DISK"
        frames = []
        for m in sorted(ms):
            for i in range(4):
                try:
                    r = sess.get(DL.format(s=s, m=m), timeout=60)
                    break
                except Exception:
                    time.sleep(3 * (i + 1)); r = None
            if r is None or r.status_code != 200:
                continue
            total[0] += len(r.content)
            z = zipfile.ZipFile(io.BytesIO(r.content)); txt = z.read(z.namelist()[0]).decode()
            lines = [l for l in txt.strip().splitlines() if l and (l[0].isdigit())]
            if lines:
                frames.append(pd.read_csv(io.StringIO("\n".join(lines)), header=None, names=KCOLS))
        if not frames:
            return s, "none"
        df = pd.concat(frames).drop_duplicates("open_time").sort_values("open_time")
        df[["open_time", "open", "high", "low", "close", "volume", "quote_volume"]].to_parquet(dest)
        return s, len(df)

    with ThreadPoolExecutor(12) as ex:
        for i, (s, st) in enumerate(ex.map(fetch, sorted(need.items()))):
            if st in ("DISK",):
                print("STOP: disk < 2.5GB", file=sys.stderr); break
            if i % 25 == 0:
                print(i, s, st, f"{total[0]/1e6:.1f}MB", file=sys.stderr, flush=True)
    print("downloaded MB", total[0] / 1e6, file=sys.stderr)


if __name__ == "__main__":
    main()
