"""Does a blind narrative score of the linked X post predict a launch's outcome?

Scores come from data/processed/narrative_scores.parquet (narrative_batches.py merge): an LLM rated each post
1-5 with no outcome information. Outcomes: migration and 30-min peak multiple from the tape.

    python scripts/research/narrative_eval.py [--before HH:MM] [--after HH:MM]
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import pandas as pd  # noqa: E402

from pipeline import config  # noqa: E402


def main(before: float | None, after: float | None) -> pd.DataFrame:
    sc = pd.read_parquet(config.path("data") / "processed" / "narrative_scores.parquet")
    tw = pd.read_parquet(config.path("data") / "processed" / "tweet_signals.parquet")
    d = tw.merge(sc, on="mint")
    if before:
        d = d[d.created < before]
    if after:
        d = d[d.created >= after]
    base = d.migrated.mean()
    print(f"n={len(d)} base migration {base:.4f} peak>=3x {(d.peak_30m_x >= 3).mean():.3f}")
    for s in sorted(d.score.dropna().unique()):
        g = d[d.score == s]
        print(f"score {int(s)}: n={len(g):4} migr={g.migrated.mean():.4f} lift={g.migrated.mean() / base if base else 0:4.2f} "
              f"peak>=3x={(g.peak_30m_x >= 3).mean():.3f} peak>=2x={(g.peak_30m_x >= 2).mean():.3f}")
    print("by category:")
    for c, g in d.groupby("category"):
        if len(g) >= 15:
            print(f"  {c:16} n={len(g):4} migr={g.migrated.mean():.4f} lift={g.migrated.mean() / base if base else 0:4.2f} peak>=3x={(g.peak_30m_x >= 3).mean():.3f}")
    hi = d[(d.score >= 4) & (d.rank_for_post == 1)]
    print(f"score>=4 AND first coin for post: n={len(hi)} migr={hi.migrated.mean():.4f} peak>=3x={(hi.peak_30m_x >= 3).mean():.3f}")
    return d


if __name__ == "__main__":
    hm = lambda s: datetime.strptime(f"2026-10-01 {s}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).timestamp()
    b = hm(sys.argv[sys.argv.index("--before") + 1]) if "--before" in sys.argv else None
    a = hm(sys.argv[sys.argv.index("--after") + 1]) if "--after" in sys.argv else None
    main(b, a)
