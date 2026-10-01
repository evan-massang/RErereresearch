"""Fetch the metadata JSON (name, description, X/website links) of every recorded pump.fun launch.

The URI is in each CreateEvent, so this is information a trader has at launch. ipfs.io refuses most
requests from here, so IPFS content is fetched from the pinata gateway (same content hash). Results are
cached in data/raw/web/token_metadata/<key>.json; failures are listed in .../_failed.json and retried next run.

    python scripts/research/fetch_token_metadata.py [--concurrency 24]
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import duckdb  # noqa: E402
import httpx  # noqa: E402

from pipeline import config  # noqa: E402

CACHE = ROOT / "data/raw/web/token_metadata"


def key(uri: str) -> str:
    return uri.rstrip("/").split("/")[-1].replace(".json", "")[:80]


def urls(uri: str) -> list[str]:
    if "/ipfs/" in uri:
        cid = uri.split("/ipfs/")[1]
        return [f"https://pump.mypinata.cloud/ipfs/{cid}", f"https://gateway.pinata.cloud/ipfs/{cid}", uri]
    return [uri]


async def one(client, sem, uri, failed):
    f = CACHE / f"{key(uri)}.json"
    if f.exists():
        return
    async with sem:
        for u in urls(uri):
            try:
                r = await client.get(u, timeout=12, follow_redirects=True)
                if r.status_code == 200:
                    f.write_text(json.dumps(r.json()))
                    return
                if r.status_code == 429:
                    await asyncio.sleep(2)
            except (httpx.HTTPError, ValueError):
                continue
    failed.append(uri)


async def main(conc: int) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
    uris = [r[0] for r in con.execute("SELECT DISTINCT uri FROM curve_creates WHERE uri LIKE 'http%'").fetchall()]
    todo = [u for u in uris if not (CACHE / f"{key(u)}.json").exists()]
    print(f"{len(uris)} uris, {len(todo)} to fetch", flush=True)
    failed: list[str] = []
    sem = asyncio.Semaphore(conc)
    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0 research"}) as client:
        for i in range(0, len(todo), 500):
            await asyncio.gather(*(one(client, sem, u, failed) for u in todo[i:i + 500]))
            print(f"{min(i + 500, len(todo))}/{len(todo)} done, {len(failed)} failed", flush=True)
    (CACHE / "_failed.json").write_text(json.dumps(failed))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--concurrency", type=int, default=24)
    asyncio.run(main(ap.parse_args().concurrency))
