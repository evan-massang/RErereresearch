"""Prepare blind batches of linked X posts for narrative scoring, and merge scores back.

    python scripts/research/narrative_batches.py make <out_dir> [--before HH:MM] [--limit N]
        writes batch_###.json files: [{"id", "coin_name", "coin_symbol", "post_text", "author", "followers",
        "account_age_days", "post_age_minutes"}] — no outcomes, no mints.
    python scripts/research/narrative_batches.py merge <out_dir>
        reads batch_###.scores.json ([{"id", "score", "category", "reason"}]) into
        data/processed/narrative_scores.parquet.
"""
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import duckdb  # noqa: E402
import pandas as pd  # noqa: E402

from pipeline import config  # noqa: E402


def make(out: Path, before: float | None, limit: int | None, after: float | None = None) -> None:
    df = pd.read_parquet(config.path("data") / "processed" / "tweet_signals.parquet")
    df = df[~df.post_missing]
    if before:
        df = df[df.created < before]
    if after:
        df = df[df.created >= after]
    con = duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
    names = {m: (n, s) for m, n, s in con.execute("SELECT mint, name, symbol FROM curve_creates").fetchall()}
    rows = [{"id": r.mint, "coin_name": names.get(r.mint, ("", ""))[0], "coin_symbol": names.get(r.mint, ("", ""))[1],
             "post_text": r.text, "author": r.author, "followers": int(r.followers) if pd.notna(r.followers) else None,
             "account_age_days": round(r.account_age_d) if pd.notna(r.account_age_d) else None,
             "post_age_minutes": round(r.post_age_min) if pd.notna(r.post_age_min) else None}
            for r in df.itertuples()]
    random.Random(7).shuffle(rows)                       # order carries no outcome information
    if limit:
        rows = rows[:limit]
    out.mkdir(parents=True, exist_ok=True)
    for i in range(0, len(rows), 60):
        (out / f"batch_{i // 60:03d}.json").write_text(json.dumps(rows[i:i + 60], ensure_ascii=False, indent=0))
    print(len(rows), "posts in", (len(rows) + 59) // 60, "batches")


def merge(out: Path) -> None:
    rows = []
    for f in sorted(out.glob("batch_*.scores.json")):
        for r in json.loads(f.read_text()):
            rows.append({"mint": r["id"], "score": r.get("score"), "category": r.get("category"), "reason": r.get("reason")})
    df = pd.DataFrame(rows).drop_duplicates("mint")
    p = config.path("data") / "processed" / "narrative_scores.parquet"
    if p.exists():
        old = pd.read_parquet(p)
        df = pd.concat([old[~old.mint.isin(df.mint)], df])
    df.to_parquet(p)
    print(len(df), "scored")


if __name__ == "__main__":
    hm = lambda s: datetime.strptime(f"2026-10-01 {s}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).timestamp()
    cmd, out = sys.argv[1], Path(sys.argv[2])
    if cmd == "make":
        before = hm(sys.argv[sys.argv.index("--before") + 1]) if "--before" in sys.argv else None
        after = hm(sys.argv[sys.argv.index("--after") + 1]) if "--after" in sys.argv else None
        limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
        make(out, before, limit, after)
    else:
        merge(out)
