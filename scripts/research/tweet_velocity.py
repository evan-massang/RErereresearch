"""Live X-post engagement at launch (recorder `tweet_snaps` feed) vs the launch's outcome.

Snapshot 0 is taken as soon as the launch's metadata is readable (~1 s after the create); snapshot 1 ~60 s
after the create. Features use only those snapshots, so they are what a trader could see at that time.

Outcomes from the tape: migrated (curve completed), peak multiple within 30 min over the price at snapshot time
(+ latency), and the simulated result of buying at snapshot time.

    python scripts/research/tweet_velocity.py build              # data/processed/tweet_velocity.parquet
    python scripts/research/tweet_velocity.py describe A B       # lift tables for launches in [A, B) (unix)
"""
import bisect
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import duckdb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from pipeline import config  # noqa: E402

SNAPS = ROOT / "data/raw/streams/tweet_snaps"


def snaps() -> pd.DataFrame:
    rows = []
    for f in sorted(SNAPS.glob("*.jsonl.gz")):
        try:
            with gzip.open(f, "rt") as fh:
                for line in fh:
                    try:
                        rows.append(json.loads(line))
                    except ValueError:
                        break
        except (OSError, EOFError):
            continue
    d = pd.DataFrame(rows)
    d = d[d.get("error").isna()] if "error" in d else d
    return d.sort_values("recv").drop_duplicates(["mint", "snap"], keep="first")


def build() -> pd.DataFrame:
    s = snaps()
    s0 = s[s.snap == 0].set_index("mint")
    s1 = s[s.snap == 1].set_index("mint")
    d = s0[["launch_recv", "recv", "status", "handle", "http", "created_timestamp", "views", "likes", "retweets",
            "replies", "quotes", "bookmarks", "followers", "text"]].copy()
    d.columns = ["launch_recv", "snap0_t", "status", "handle", "http", "post_ts", "views0", "likes0", "rts0", "replies0",
                 "quotes0", "bm0", "followers", "text"]
    for c in ("recv", "views", "likes", "retweets"):
        d[f"{c}1"] = s1[c].reindex(d.index)
    d = d.rename(columns={"recv1": "snap1_t", "retweets1": "rts1"})
    d["post_age_min"] = (d.snap0_t - d.post_ts) / 60
    d["views_per_min0"] = d.views0 / d.post_age_min.clip(lower=0.25)
    d["views_gain_60s"] = (d.views1 - d.views0) / ((d.snap1_t - d.snap0_t) / 60).clip(lower=0.25)
    d["likes_gain_60s"] = d.likes1 - d.likes0
    d = d.sort_values("launch_recv")
    d["rank_for_post"] = d.groupby("status").cumcount() + 1
    con = duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
    data_end = con.execute("SELECT max(recv) FROM curve_trades").fetchone()[0]
    comp = dict(con.execute("SELECT mint, min(recv) FROM curve_completes GROUP BY 1").fetchall())
    out = []
    for m, r in d.iterrows():
        x = con.execute("SELECT recv, vsol / vtok * 1e9 FROM curve_trades WHERE mint = ? AND recv <= ? ORDER BY recv, rowid",
                        [m, r.launch_recv + 1800]).fetchall()
        ts = [a for a, _ in x]
        o = {"mint": m, "migrated": m in comp and comp[m] < r.launch_recv + 3600,
             "complete_by_data_end": r.launch_recv + 3600 <= data_end}
        for tag, t in (("s0", r.snap0_t), ("s1", r.snap1_t)):
            if pd.isna(t):
                continue
            i = bisect.bisect_left(ts, t + 1.0)
            if i < len(x):
                p = x[i][1]
                o[f"mcap_at_{tag}"] = p
                o[f"peak30_{tag}"] = max(q for _, q in x[i:]) / p
                o[f"last30_{tag}"] = x[-1][1] / p
        o["n_trades_before_s1"] = bisect.bisect_left(ts, r.snap1_t) if pd.notna(r.snap1_t) else None
        out.append(o)
    return d.reset_index().rename(columns={"index": "mint"}).merge(pd.DataFrame(out), on="mint")


def describe(d: pd.DataFrame, a: float, b: float) -> dict:
    g = d[(d.launch_recv >= a) & (d.launch_recv < b) & (d.http == 200) & d.complete_by_data_end]
    base = float(g.migrated.mean())
    res = {"n": len(g), "base_migration": round(base, 4), "share_peak2x_s1": round(float((g.peak30_s1 >= 2).mean()), 4)}
    qs = {}
    for col in ("views0", "views_per_min0", "views_gain_60s", "likes_gain_60s", "followers", "post_age_min",
                "n_trades_before_s1"):
        x = g.dropna(subset=[col])
        if len(x) < 50:
            continue
        try:
            q = pd.qcut(x[col].rank(method="first"), 5, labels=False)
        except ValueError:
            continue
        qs[col] = [{"q": int(k), "n": int(len(v)), "lo": float(v[col].min()), "hi": float(v[col].max()),
                    "migr": round(float(v.migrated.mean()), 4), "peak2x_s1": round(float((v.peak30_s1 >= 2).mean()), 3),
                    "median_last30_s1": round(float(v.last30_s1.median()), 3)}
                   for k, v in x.groupby(q)]
    res["quintiles"] = qs
    return res


if __name__ == "__main__":
    p = config.path("data") / "processed" / "tweet_velocity.parquet"
    if sys.argv[1] == "build":
        d = build()
        d.to_parquet(p)
        print(len(d), "launches with a snapshot")
    else:
        d = pd.read_parquet(p)
        r = describe(d, float(sys.argv[2]), float(sys.argv[3]))
        print(f"n={r['n']} base migration {r['base_migration']} share peak>=2x {r['share_peak2x_s1']}")
        for col, rows in r["quintiles"].items():
            print(col)
            for q in rows:
                print(f"  q{q['q']} n={q['n']:4} [{q['lo']:.4g}, {q['hi']:.4g}] migr={q['migr']:.3f} peak2x={q['peak2x_s1']:.3f} "
                      f"med_last30={q['median_last30_s1']}")
