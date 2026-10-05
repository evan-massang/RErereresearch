"""Fetch Binance USDT-M 5m klines (data.binance.vision monthly zips) for H-PAIRS universe symbols,
only months overlapping [t-30d, t+7d) of weeks the symbol is in the universe, months <= 2026-03.
Stores data/raw/web/pairs/k5m/<SYM>.parquet (open_time ms, open, close); zips never written to disk.
Budget: stop if cumulative download > 1 GB or free disk < 2.5 GB."""
import io, json, shutil, sys, time, zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pandas as pd, requests
sys.path.insert(0, str(Path(__file__).resolve().parent))
from momentum_fetch import s3_list

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/raw/web/pairs"; (OUT / "k5m").mkdir(parents=True, exist_ok=True)
DL = "https://data.binance.vision/"
BUDGET = 1.0e9; MIN_FREE = 2.5e9
U = json.load(open(OUT / "universe.json"))

need = {}
for t, syms in U["universe"].items():
    t = pd.Timestamp(t)
    months = pd.period_range(t - pd.Timedelta(days=30), t + pd.Timedelta(days=6), freq="M")
    for s in syms:
        need.setdefault(s, set()).update(str(m) for m in months if str(m) <= "2026-03")

def plan():
    tot, rows = 0, {}
    def lst(s):
        keys, _ = s3_list(f"data/futures/um/monthly/klines/{s}/5m/")
        return s, keys
    with ThreadPoolExecutor(8) as ex:
        for s, keys in ex.map(lst, sorted(need)):
            rows[s] = sorted(k for k in keys if k.endswith(".zip") and k[-11:-4] in need[s])
    return rows

def main():
    rows = plan()
    nkeys = sum(len(v) for v in rows.values())
    print("symbols", len(rows), "zips", nkeys, flush=True)
    used = [0]
    def get(k):
        for i in range(5):
            try:
                r = requests.get(DL + k, timeout=60)
                if r.status_code == 404: return k, None, 0
                r.raise_for_status()
                z = zipfile.ZipFile(io.BytesIO(r.content))
                df = pd.read_csv(z.open(z.namelist()[0]), header=None, usecols=[0, 1, 4])
                if not str(df.iloc[0, 0]).lstrip("-").isdigit(): df = df.iloc[1:]
                df.columns = ["open_time", "open", "close"]
                return k, df.astype({"open_time": "int64", "open": "float64", "close": "float64"}), len(r.content)
            except Exception as e:
                time.sleep(2 * (i + 1))
        return k, None, 0
    missing = []
    for s in sorted(rows):
        dest = OUT / "k5m" / f"{s}.parquet"
        if dest.exists(): continue
        if used[0] > BUDGET or shutil.disk_usage(ROOT).free < MIN_FREE:
            print("BUDGET/DISK STOP before", s, used[0], shutil.disk_usage(ROOT).free); missing.append(s); continue
        with ThreadPoolExecutor(6) as ex:
            res = list(ex.map(get, rows[s]))
        frames = [d for k, d, n in res if d is not None]
        used[0] += sum(n for k, d, n in res)
        if len(frames) < len(rows[s]) or len(rows[s]) < len(need[s]):
            print("partial", s, len(frames), len(rows[s]), len(need[s]))
        if frames:
            pd.concat(frames).drop_duplicates("open_time").sort_values("open_time").to_parquet(dest, index=False)
        print(s, len(frames), f"{used[0]/1e6:.0f}MB", flush=True)
    json.dump({"downloaded_bytes": used[0], "missing": missing, "months_needed": {k: sorted(v) for k, v in need.items()},
               "zips_found": {k: len(v) for k, v in rows.items()}}, open(OUT / "fetch_log.json", "w"), indent=0)

if __name__ == "__main__":
    main()
