"""H-SPOTCARRY-WIDE universe from the data.binance.vision S3 listing (no prices fetched here).

Lists USD-M fundingRate symbols and spot monthly kline symbols, matches USDT perps to spot pairs
(same name, or 1000X/10000X/1000000X/1MX -> X with multiplier), then lists available monthly files per
symbol for funding, perp 1h klines and spot 1h klines. Months >= 2026-04 (holdout) are dropped.
Output: data/raw/web/binance_carry/universe.json
"""
import json, re, sys, time, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor
OUT = "/home/user/RErereresearch/data/raw/web/binance_carry/universe.json"
S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
LAST = "2026-03"


def ls(prefix, delim=True):
    out, marker = [], ""
    while True:
        q = {"prefix": prefix, "marker": marker}
        if delim:
            q["delimiter"] = "/"
        for a in range(6):
            try:
                x = urllib.request.urlopen(f"{S3}?{urllib.parse.urlencode(q)}", timeout=60).read().decode()
                break
            except Exception:
                time.sleep(2 + 3 * a)
        else:
            raise RuntimeError(prefix)
        items = re.findall(r"<Prefix>([^<]+)</Prefix>", x)[1:] if delim else []
        keys = re.findall(r"<Key>([^<]+)</Key>", x)
        out += items + keys
        if "<IsTruncated>true</IsTruncated>" not in x:
            return out
        nm = re.findall(r"<NextMarker>([^<]+)</NextMarker>", x)
        marker = nm[0] if nm else (items + keys)[-1]


def months(prefix):
    ks = ls(prefix, delim=False)
    return sorted({m for k in ks if k.endswith(".zip") for m in re.findall(r"(\d{4}-\d{2})\.zip$", k) if m <= LAST})


def main():
    fsyms = [p.rstrip("/").split("/")[-1] for p in ls("data/futures/um/monthly/fundingRate/")]
    ssyms = set(p.rstrip("/").split("/")[-1] for p in ls("data/spot/monthly/klines/"))
    print(len(fsyms), "funding symbols;", len(ssyms), "spot symbols", file=sys.stderr)
    pairs = []
    for f in fsyms:
        if not f.endswith("USDT"):
            continue
        if f in ssyms:
            pairs.append((f, f, 1)); continue
        m = re.match(r"^(1000000|10000|1000|1M)(.+USDT)$", f)
        if m and m.group(2) in ssyms:
            k = {"1000000": 1e6, "10000": 1e4, "1000": 1e3, "1M": 1e6}[m.group(1)]
            pairs.append((f, m.group(2), k))
    print(len(pairs), "pairs", file=sys.stderr)

    def info(p):
        f, s, k = p
        return {"perp": f, "spot": s, "mult": k,
                "funding": months(f"data/futures/um/monthly/fundingRate/{f}/"),
                "perp_1h": months(f"data/futures/um/monthly/klines/{f}/1h/"),
                "spot_1h": months(f"data/spot/monthly/klines/{s}/1h/")}
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(info, pairs))
    json.dump({"rule": __doc__, "pairs": res}, open(OUT, "w"), indent=0)
    n = sum(len(r["funding"]) + len(r["perp_1h"]) + len(r["spot_1h"]) for r in res)
    print(len(res), "pairs;", n, "monthly files <=", LAST)


if __name__ == "__main__":
    main()
