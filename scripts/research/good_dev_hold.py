"""Good-dev launch, held through migration (solo trader, no copying).

Motivation (evidence, 2026-10-02): launches by a creator with >= 1 earlier migration and a >= 20% migration rate
(same-tape history, point in time) migrated 9.3x base on Oct 1 train, 3.2x on validation and 6.0x on the
Oct 2 03:45-07:40 tape, yet the frozen H7 rule lost on that tape (run_0197f08c47c44a30: 55 trades, -3.13 SOL,
PF 0.55, median hold 28 s). Its quick follow-through exit sold most positions long before a migration could
pay. This evaluator asks whether holding the selected launches through migration is better.

Point-in-time evaluator (same conventions as final_stretch.py):
  select  creator had >= min_prior_migrations completed curves (completed before this launch) and
          migrations / prior launches >= min_migration_rate;
  entry   first curve trade at least `latency_s` after the create, at its price x (1 + entry_cost);
  stop    if, before completion, a trade prints at or below (1 - stop_pct) x entry reference price, sell at that
          print x (1 - curve_exit_cost);
  migrate sell at the last PumpSwap price at or before `exit_after_s` after the pool's first swap x (1 - amm_exit_cost);
  timeout otherwise sell at the last curve price within `max_hold_s` x (1 - curve_exit_cost).
  Fixed `fixed_sol_per_tx` on entry and exit. Completed tokens without a decoded pool are excluded and counted.

    python scripts/research/good_dev_hold.py explore          # train grid (Oct 1 before 16:15 UTC)
    python scripts/research/good_dev_hold.py record           # train / validation / Oct 2, with and without costs

Outcome (2026-10-02): best train setting (no stop, exit 60 s after the pool's first swap) failed validation, so it
was not registered as a hypothesis; the Oct 2 run is descriptive. Holdout (Oct 1 from 19:15) not touched:
validation launches end 18:15 and their outcomes are cut at 19:15.
"""
import itertools
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import duckdb  # noqa: E402

from pipeline import config  # noqa: E402

# entry_cost 0.08: H7's launch fills cost ~11% round trip in slippage + protocol fee (3.03 SOL over 55 x 0.5 SOL)
PARAMS = dict(min_prior_migrations=1, min_migration_rate=0.2, latency_s=1.0, stop_pct=None, exit_after_s=300.0,
              max_hold_s=3600.0, size_sol=0.5, entry_cost=0.08, curve_exit_cost=0.03, amm_exit_cost=0.025,
              fixed_sol_per_tx=0.01)
U = lambda h, m, d=1: datetime(2026, 10, d, h, m, tzinfo=timezone.utc).timestamp()


def selected(con, start: float, end: float, p: dict) -> list[tuple[str, float]]:
    cr = con.execute("SELECT mint, creator, min(recv) t FROM curve_creates WHERE recv < ? GROUP BY 1, 2 ORDER BY t",
                     [end]).fetchall()
    comp = dict(con.execute("SELECT mint, min(recv) FROM curve_completes WHERE recv < ? GROUP BY 1", [end]).fetchall())
    hist, out = {}, []
    for m, c, t in cr:
        h = hist.setdefault(c, [])
        n, k = len(h), sum(1 for x in h if comp.get(x) is not None and comp[x] < t)
        if start <= t < end and k >= p["min_prior_migrations"] and k / max(n, 1) >= p["min_migration_rate"]:
            out.append((m, t))
        h.append(m)
    return out


def evaluate(start: float, end: float, data_end: float, p: dict = PARAMS, con=None) -> dict:
    """Launches in [start, end); outcomes may use data up to data_end only."""
    con = con or duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
    comp = dict(con.execute("SELECT mint, min(recv) FROM curve_completes WHERE recv < ? GROUP BY 1", [data_end]).fetchall())
    pool = dict(con.execute("SELECT mint, pool FROM amm_pools").fetchall())
    trades, excluded = [], 0
    for m, t in selected(con, start, end, p):
        x = con.execute("SELECT recv, vsol / vtok * 1e9 FROM curve_trades WHERE mint = ? AND recv >= ? AND recv <= ? "
                        "AND recv < ? ORDER BY recv, rowid", [m, t + p["latency_s"], t + p["max_hold_s"], data_end]).fetchall()
        if not x:
            continue
        tc = comp.get(m)
        if tc is not None and m not in pool:
            excluded += 1
            continue
        ref = x[0][1]
        cost_in = ref * (1 + p["entry_cost"])
        pre = [(r, q) for r, q in x if tc is None or r < tc]
        hit = None if p["stop_pct"] is None else next(
            (q for r, q in pre if q <= ref * (1 - p["stop_pct"] / 100)), None)
        if hit is not None:
            ret, how = hit * (1 - p["curve_exit_cost"]) / cost_in - 1, "stop"
        elif tc is not None:
            a = con.execute("SELECT recv, sol / tok FROM amm_trades WHERE pool = ? AND recv >= ? AND recv < ? "
                            "ORDER BY recv, rowid", [pool[m], tc, data_end]).fetchall()
            if not a:
                excluded += 1
                continue
            s = [q for r, q in a if r <= a[0][0] + p["exit_after_s"]][-1] * 1e9
            ret, how = s * (1 - p["amm_exit_cost"]) / cost_in - 1, "migrated"
        elif pre:
            ret, how = pre[-1][1] * (1 - p["curve_exit_cost"]) / cost_in - 1, "timeout"
        else:
            continue
        pnl = p["size_sol"] * ret - 2 * p["fixed_sol_per_tx"]
        trades.append({"mint": m, "t": t, "ret": round(ret, 4), "pnl_sol": round(pnl, 4), "exit": how})
    v = sorted(r["pnl_sol"] for r in trades)
    wins, losses = [x for x in v if x > 0], [x for x in v if x <= 0]
    return {"params": p, "window": [start, end], "n_trades": len(v), "excluded_no_pool": excluded,
            "pnl_sol": round(sum(v), 3), "expectancy_sol": round(statistics.mean(v), 4) if v else None,
            "median_sol": round(statistics.median(v), 4) if v else None,
            "win_rate": round(len(wins) / len(v), 3) if v else None,
            "profit_factor": round(sum(wins) / -sum(losses), 3) if losses and sum(losses) < 0 else None,
            "pnl_without_top1": round(sum(v[:-1]), 3) if v else None,
            "exits": {k: sum(1 for r in trades if r["exit"] == k) for k in ("stop", "migrated", "timeout")},
            "trades": trades}


def explore() -> list[dict]:
    """Train-only grid: Oct 1 launches 12:17-16:15 UTC, outcomes up to 17:15."""
    con = duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
    out = []
    for stop, ex, hold in itertools.product([None, 50, 70], [60, 300, 900], [1800, 3600]):
        p = PARAMS | {"stop_pct": stop, "exit_after_s": ex, "max_hold_s": hold}
        o = evaluate(U(12, 17), U(16, 15), U(17, 15), p, con)
        out.append({k: o[k] for k in ("n_trades", "pnl_sol", "expectancy_sol", "profit_factor", "pnl_without_top1",
                                      "exits")} | {"stop_pct": stop, "exit_after_s": ex, "max_hold_s": hold})
    return out


WINDOWS = {"train_oct1": (U(12, 17), U(16, 15), U(17, 15)), "validation_oct1": (U(16, 15), U(18, 15), U(19, 15)),
           "oct2_descriptive": (U(1, 44, 2), U(6, 40, 2), U(7, 41, 2))}
ZERO = dict(entry_cost=0.0, curve_exit_cost=0.0, amm_exit_cost=0.0, fixed_sol_per_tx=0.0)


def record() -> None:
    from pipeline import db, findings, observations
    from pipeline.ingest_web import ingest_document
    con = duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
    p = PARAMS | {"exit_after_s": 60.0}
    keep = ("n_trades", "pnl_sol", "expectancy_sol", "median_sol", "win_rate", "profit_factor", "pnl_without_top1", "exits")
    o = {"params": p, "train_grid": explore(), "windows": {}}
    for k, (a, b, c) in WINDOWS.items():
        o["windows"][k] = {"costs": {x: v for x, v in evaluate(a, b, c, p, con).items() if x in keep},
                           "zero_costs": {x: v for x, v in evaluate(a, b, c, p | ZERO, con).items() if x in keep}}
    ex = "claude:good-dev-hold-2026-10-02"
    path = ROOT / "research/observations/evidence_good_dev_hold_2026-10-02.json"
    path.write_text(json.dumps(o, indent=1))
    rcon = db.connect()
    kept = findings.clear_previous(rcon, ex, ex)
    sid, snap = ingest_document(rcon, str(path), title="Good-dev launches held through migration",
                                canonical_url="stream://pump_curve/2026-10-02/good-dev-hold")
    obs = observations.add_observation(rcon, source_id=sid, snapshot_id=snap, modality="onchain", kind="signal_study",
                                       extractor=ex, status="reviewed", value=o["windows"],
                                       content="Good-dev launch selection, held through migration, three windows.")
    w = o["windows"]
    f = lambda k, c="costs": f"{w[k][c]['pnl_sol']:+.1f} SOL over {w[k][c]['n_trades']} trades"
    new = findings.add_finding(
        rcon, trader_id=None, funnel_stage="exit", evidence_type="observed",
        statement=f"Buying every launch by a creator with an earlier migration (>=20% rate) 1 s after create and "
                  f"holding through migration (0.5 SOL, 8%/3%/2.5% costs + 0.01 SOL/tx): Oct 1 train "
                  f"{f('train_oct1')} (without its best trade {w['train_oct1']['costs']['pnl_without_top1']:+.1f}); "
                  f"validation {f('validation_oct1')}; Oct 2 {f('oct2_descriptive')} although "
                  f"{w['oct2_descriptive']['costs']['exits']['migrated']} of them migrated. With zero costs Oct 2 is "
                  f"still {f('oct2_descriptive', 'zero_costs')}. The selection raises migration odds but a launch-time "
                  f"entry does not pay on average.",
        evidence=[("observation", obs, "supports")], n_supporting=w["oct2_descriptive"]["costs"]["n_trades"],
        n_observable=sum(v["costs"]["n_trades"] for v in w.values()), confidence=0.6,
        notes=f"{ex}; failed validation, not registered; holdout untouched")
    for k in kept:
        findings.set_finding_status(rcon, k, "superseded", "Rebuilt.", superseded_by=new)
    print(json.dumps(o["windows"], indent=1))


if __name__ == "__main__":
    if sys.argv[1:2] == ["explore"]:
        for r in explore():
            print(r)
    elif sys.argv[1:2] == ["record"]:
        record()
