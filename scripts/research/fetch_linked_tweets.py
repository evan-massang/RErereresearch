"""Fetch every X post linked from recorded launches' metadata, through the fxtwitter mirror (JSON).

Point-in-time note: the post's text, author, author follower count (approximately) and the post's creation
time existed at launch; like/view counts did not (they accumulate) and must not be used as launch-time features.
Cached in data/raw/web/tweets/<status_id>.json; failures in _failed.json (retried next run).

    python scripts/research/fetch_linked_tweets.py [--concurrency 6]
"""
import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import duckdb  # noqa: E402
import httpx  # noqa: E402

from pipeline import config  # noqa: E402

META = ROOT / "data/raw/web/token_metadata"
OUT = ROOT / "data/raw/web/tweets"
RX = re.compile(r"(?:x|twitter)\.com/([A-Za-z0-9_]+)/status/(\d+)")


def linked_posts() -> dict[str, str]:
    con = duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
    posts = {}
    for (uri,) in con.execute("SELECT DISTINCT uri FROM curve_creates WHERE uri LIKE 'http%'").fetchall():
        f = META / (uri.rstrip("/").split("/")[-1].replace(".json", "")[:80] + ".json")
        if not f.exists():
            continue
        try:
            tw = json.loads(f.read_text()).get("twitter") or ""
        except ValueError:
            continue
        m = RX.search(tw)
        if m:
            posts[m.group(2)] = m.group(1)
    return posts


async def one(client, sem, sid, handle, failed):
    f = OUT / f"{sid}.json"
    if f.exists():
        return
    async with sem:
        for attempt in range(3):
            try:
                r = await client.get(f"https://api.fxtwitter.com/{handle}/status/{sid}", timeout=15)
                if r.status_code == 200:
                    d = r.json()
                    t = d.get("tweet") or {}
                    a = t.get("author") or {}
                    f.write_text(json.dumps({
                        "id": sid, "handle": handle, "text": t.get("text"), "created_at": t.get("created_at"),
                        "created_timestamp": t.get("created_timestamp"), "lang": t.get("lang"),
                        "author": {"screen_name": a.get("screen_name"), "name": a.get("name"), "followers": a.get("followers"),
                                   "following": a.get("following"), "tweets": a.get("tweets"), "joined": a.get("joined"),
                                   "description": a.get("description"), "verified": a.get("verified") or a.get("is_blue_verified")},
                        "has_media": bool(t.get("media")), "is_reply": bool(t.get("replying_to")),
                        "quote_of": (t.get("quote") or {}).get("id"),
                        "not_point_in_time": {"likes": t.get("likes"), "replies": t.get("replies"), "retweets": t.get("retweets"),
                                              "views": t.get("views")}}))
                    return
                if r.status_code == 404:
                    f.write_text(json.dumps({"id": sid, "handle": handle, "missing": True}))
                    return
                await asyncio.sleep(2 * (attempt + 1))
            except (httpx.HTTPError, ValueError):
                await asyncio.sleep(1)
    failed.append(sid)


async def main(conc: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    posts = linked_posts()
    todo = [(s, h) for s, h in posts.items() if not (OUT / f"{s}.json").exists()]
    print(f"{len(posts)} linked posts, {len(todo)} to fetch", flush=True)
    failed: list[str] = []
    sem = asyncio.Semaphore(conc)
    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0 research"}) as client:
        for i in range(0, len(todo), 200):
            await asyncio.gather(*(one(client, sem, s, h, failed) for s, h in todo[i:i + 200]))
            print(f"{min(i + 200, len(todo))}/{len(todo)}, {len(failed)} failed", flush=True)
    (OUT / "_failed.json").write_text(json.dumps(failed))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--concurrency", type=int, default=6)
    asyncio.run(main(ap.parse_args().concurrency))
