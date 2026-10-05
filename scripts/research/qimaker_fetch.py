"""H-QIMAKER amendment-1 fetch (reports/hypotheses/qimaker_preregistration.json).
Stage 'probe': first available train day per candidate -> coin rule (spreads/prints only).
Stage 'all': all train+validation days for qualifiers in rank order under a 0.9 GB raw budget.
Raw csv.gz deleted after parquet extraction. Holdout never fetched."""
from __future__ import annotations
import json, shutil, subprocess, sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from hlanchor_fetch import TRAIN, VALID, HOLDOUT_START, url  # noqa: E402
import qimaker_coins as QC  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/web/tardis/qimaker_tmp"
PQ = ROOT / "data/raw/web/tardis/parquet_qimaker"
LOG = ROOT / "data/raw/web/tardis/results/qimaker_fetch_log.json"
RAW.mkdir(parents=True, exist_ok=True); PQ.mkdir(parents=True, exist_ok=True)
CANDS = ["BTC", "ETH", "HYPE", "ZEC", "NEAR", "SOL", "XRP", "SAND", "SUI", "ENA", "WLD", "DOGE", "LIT", "PONS"]
CAP = 0.9e9
log = json.load(open(LOG)) if LOG.exists() else {"bytes": 0, "files": {}, "probe": {}, "dropped": []}


def free_gb():
    return shutil.disk_usage("/").free / 1e9


def get(dtype, day, coin):
    dst = PQ / f"{dtype}_{day}_{coin}.parquet"
    if dst.exists():
        return True
    assert day < HOLDOUT_START
    if free_gb() < 2.5:
        raise SystemExit("free disk < 2.5 GB, stopping")
    raw = RAW / f"{dtype}_{day}_{coin}.csv.gz"
    r = subprocess.run(["curl", "-sS", "--max-time", "600", "-o", str(raw), "-w", "%{http_code} %{size_download}",
                        url("hyperliquid", dtype, day, coin)], capture_output=True, text=True)
    code, size = r.stdout.split()
    log["bytes"] += int(size)
    log["files"][dst.name] = [code, int(size)]
    if code != "200":
        raw.unlink(missing_ok=True)
        return False
    df = pd.read_csv(raw)
    cols = {"quotes": ["timestamp", "local_timestamp", "bid_price", "ask_price", "bid_amount", "ask_amount"],
            "trades": ["timestamp", "local_timestamp", "side", "price", "amount"]}[dtype]
    df[cols].to_parquet(dst, index=False)
    raw.unlink()
    return True


def probe():
    for c in CANDS:
        for d in TRAIN:
            if get("quotes", d, c) and get("trades", d, c):
                QC.PQ = PQ
                s = QC.stats(c, d)
                s["qualifies"] = bool(s["frac_1tick"] >= 0.70 and s["n_prints"] >= 5000)
                log["probe"][c] = s
                print(s, flush=True)
                break
        else:
            log["probe"][c] = {"coin": c, "qualifies": False, "note": "no train day available"}
        json.dump(log, open(LOG, "w"), indent=1)
    print("bytes so far", log["bytes"])


def fetch_all():
    quals = [c for c in CANDS if log["probe"].get(c, {}).get("qualifies")]
    for c in quals:
        start = log["bytes"]
        days = TRAIN + VALID
        # estimate from probe day file sizes
        est = sum(v[1] for k, v in log["files"].items() if k.endswith(f"_{c}.parquet")) * len(days)
        if start + est > CAP:
            log["dropped"].append({"coin": c, "reason": f"estimated {est/1e6:.0f} MB would breach cap"})
            print("drop", c, flush=True)
            continue
        for d in days:
            get("quotes", d, c) and get("trades", d, c)
        print(c, "MB", (log["bytes"] - start) / 1e6, "total", log["bytes"] / 1e6, "free", free_gb(), flush=True)
        json.dump(log, open(LOG, "w"), indent=1)


if __name__ == "__main__":
    probe() if sys.argv[1] == "probe" else fetch_all()
    json.dump(log, open(LOG, "w"), indent=1)
