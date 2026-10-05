"""H-DELIST step 1: fetch Binance CMS article lists (catalog 161 Delisting, catalog 49 Latest News titles)
and article bodies for delisting / monitoring-tag / futures-delist articles.

Public keyless endpoints (www.binance.com/bapi/composite/v1/public/cms/...). Cache: data/raw/web/delist/cms/.
releaseDate (ms) is the point-in-time announcement timestamp.
"""
import json, re, sys, time
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/raw/web/delist/cms"
OUT.mkdir(parents=True, exist_ok=True)
LIST = "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query"
DETAIL = "https://www.binance.com/bapi/composite/v1/public/cms/article/detail/query"
sess = requests.Session()
sess.headers["User-Agent"] = "Mozilla/5.0 research"


def get(url, params):
    for i in range(6):
        try:
            r = sess.get(url, params=params, timeout=30)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            print("retry", e, file=sys.stderr)
        time.sleep(2 + 3 * i)
    raise RuntimeError(f"failed {url} {params}")


def list_catalog(cid):
    dest = OUT / f"catalog_{cid}.json"
    if dest.exists():
        return json.loads(dest.read_text())
    arts, page = [], 1
    while True:
        d = get(LIST, {"type": 1, "catalogId": cid, "pageNo": page, "pageSize": 50})["data"]["catalogs"][0]
        arts += d["articles"]
        print(cid, page, len(arts), d["total"], file=sys.stderr)
        if not d["articles"] or len(arts) >= d["total"]:
            break
        page += 1
        time.sleep(0.4)
    dest.write_text(json.dumps(arts))
    return arts


REL = re.compile(r"monitoring tag|will delist|delist", re.I)
EXCL = re.compile(r"margin|trading pairs|trading pair |alpha|loans|fiat|options|earn|convert|deposits and withdrawals", re.I)

if __name__ == "__main__":
    a161 = list_catalog(161)
    a49 = list_catalog(49)
    want = {}
    for a in a161 + a49:
        t = a["title"]
        if re.search(r"monitoring tag", t, re.I) or (re.search(r"delist", t, re.I) and not EXCL.search(t)) \
                or re.search(r"Futures Will Delist", t, re.I):
            want[a["code"]] = a
    print("articles to fetch bodies:", len(want), file=sys.stderr)
    bd = OUT / "bodies"; bd.mkdir(exist_ok=True)
    for code, a in want.items():
        f = bd / f"{code}.json"
        if f.exists():
            continue
        try:
            d = get(DETAIL, {"articleCode": code})["data"]
        except RuntimeError as e:
            print("SKIP", code, a["title"], file=sys.stderr); time.sleep(20); continue
        f.write_text(json.dumps({"code": code, "title": d.get("title"), "releaseDate": a["releaseDate"],
                                 "publishDate": d.get("publishDate"), "body": d.get("body")}))
        time.sleep(1.5)
    print("done", file=sys.stderr)
