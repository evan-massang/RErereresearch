"""After migration: how pump.fun tokens trade on PumpSwap in the first 30 minutes (decoded AMM swaps).

    python scripts/research/post_migration_finding.py

Price = SOL / tokens of each swap (execution price, swaps >= 0.01 SOL). Reference = the pool's first such
swap. Only pools of tokens whose curve completion is in the tape and with >= 30 min of data after it, using
data before 19:15 UTC only (the holdout of overnight-2026-10-01 is not looked at).
"""
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import duckdb  # noqa: E402

from pipeline import config, db, findings, observations  # noqa: E402
from pipeline.ingest_web import ingest_document  # noqa: E402

EX = "claude:post-migration-2026-10-01"
# 19:15 UTC: the holdout of split set overnight-2026-10-01 starts here; nothing after it is used
CUTOFF = 1790882100.0


def main() -> dict:
    m = duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
    rows = m.execute("""
        WITH t AS (SELECT pool, recv, sol / tok AS p FROM amm_trades WHERE tok > 0 AND sol >= 0.01 AND recv < ?),
        f AS (SELECT pool, min(recv) AS t0, arg_min(p, recv) AS p0 FROM t GROUP BY 1)
        SELECT f.pool, f.p0,
          (SELECT arg_max(p, recv) FROM t WHERE t.pool = f.pool AND t.recv <= f.t0 + 60),
          (SELECT arg_max(p, recv) FROM t WHERE t.pool = f.pool AND t.recv <= f.t0 + 300),
          (SELECT arg_max(p, recv) FROM t WHERE t.pool = f.pool AND t.recv <= f.t0 + 1800),
          (SELECT max(p) FROM t WHERE t.pool = f.pool AND t.recv <= f.t0 + 1800),
          (SELECT max(recv) FROM t) - f.t0
        FROM f WHERE f.pool IN (SELECT pool FROM amm_pools WHERE mint IN (SELECT mint FROM curve_completes))""",
        [CUTOFF]).fetchall()
    rows = [r for r in rows if r[6] > 1800]
    out = {"n_pools": len(rows), "reference": "first AMM swap >= 0.01 SOL", "horizons": {}}
    for i, h in ((2, "1m"), (3, "5m"), (4, "30m"), (5, "max_within_30m")):
        v = [r[i] / r[1] - 1 for r in rows]
        out["horizons"][h] = {"median": round(statistics.median(v), 3), "share_up": round(sum(x > 0 for x in v) / len(v), 3),
                              "share_ge_2x": round(sum(x >= 1 for x in v) / len(v), 3)}
    p = ROOT / "research/observations/evidence_post_migration_2026-10-01.json"
    p.write_text(json.dumps(out, indent=1))
    return out


def record(o: dict) -> None:
    con = db.connect()
    con.execute("DELETE FROM finding_evidence WHERE finding_id IN (SELECT finding_id FROM findings WHERE notes LIKE ?)",
                [f"%{EX}%"])
    con.execute("DELETE FROM findings WHERE notes LIKE ?", [f"%{EX}%"])
    con.execute("DELETE FROM observations WHERE extractor = ?", [EX])
    p = ROOT / "research/observations/evidence_post_migration_2026-10-01.json"
    sid, snap = ingest_document(con, str(p), title="Post-migration price paths on PumpSwap",
                                canonical_url="stream://pumpswap/2026-10-01/post-migration")
    obs = observations.add_observation(con, source_id=sid, snapshot_id=snap, modality="onchain", kind="price_paths",
                                       extractor=EX, status="reviewed", value=o,
                                       content="Execution-price paths of migrated pump.fun tokens on PumpSwap, 30 min.")
    h = o["horizons"]
    findings.add_finding(
        con, trader_id=None, funnel_stage="exit", evidence_type="observed",
        statement=f"Across {o['n_pools']} pump.fun tokens that migrated during the recording, the PumpSwap price "
                  f"(vs the first AMM swap) is a median {h['1m']['median']:+.0%} after 1 min and "
                  f"{h['5m']['median']:+.0%} after 5 min ({h['5m']['share_up']:.0%} up), "
                  f"{h['max_within_30m']['share_ge_2x']:.0%} reach 2x within 30 min, but after 30 min the median is "
                  f"{h['30m']['median']:+.0%}. A position held through migration has a short window to sell into.",
        evidence=[("observation", obs, "supports")], n_supporting=round(h["5m"]["share_up"] * o["n_pools"]),
        n_observable=o["n_pools"], confidence=0.7,
        notes=f"{EX}; execution prices incl. fees/impact; 19 of 334 migrations lack a decoded pool")


if __name__ == "__main__":
    o = main()
    record(o)
    print(json.dumps(o, indent=1))
