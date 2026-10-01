"""Run pre-registered hypotheses on their pre-registered windows and record the runs.

    python scripts/research/run_hypotheses.py H3                 # its pre-registered first-test window
    python scripts/research/run_hypotheses.py H3 --in-sample     # the window it was derived from (labelled as such)
    python scripts/research/run_hypotheses.py H2 --split validation

Strategy parameters, execution and pass criteria come from each hypothesis's measurable
definition (copied below verbatim as code) and are not changed here. Train/validation only;
the holdout is evaluated once by a separate script. Results: sim_runs (primary run) and
reports/simulations/<hyp>_<window>.json/.md (primary + latency sweep + cost/size sensitivity).
"""
import argparse
import dataclasses
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import duckdb  # noqa: E402

from pipeline import config, db, market  # noqa: E402
from pipeline.copytrade import base_execution  # noqa: E402
from pipeline.sim import run  # noqa: E402
from pipeline.sim.engine import sweep_latency  # noqa: E402
from pipeline.sim.metrics import performance  # noqa: E402
from pipeline.sim.splits import get_split, record_run  # noqa: E402
from pipeline.strategies import DevDumpEntry, StructureEntry, build_market_store  # noqa: E402

SPLIT_SET = "overnight-2026-10-01"
U = lambda h, m: datetime(2026, 10, 1, h, m, tzinfo=timezone.utc)
PASS = {"min_trades": 30, "min_expectancy_sol": 0.0, "min_profit_factor": 1.2}

HYPS = {
    "H1": {"prefix": "H1:", "factory": lambda: StructureEntry(),
           "execution": dict(tx_latency_s=1.0, fee_bps=125, priority_fee_sol=0.001),
           "first_test": (U(12, 15), U(17, 15)), "in_sample": (U(12, 15), U(13, 15)),
           "sensitivity": {}},
    "H2": {"prefix": "H2:", "factory": lambda: StructureEntry(
               name="h2", min_age_s=45, max_age_s=120, min_buyers_10s=6, max_buyers_10s=14, min_inflow_30s=1.0,
               max_inflow_30s=4.0, require_dev_sold=True, snipers_max_pct=5, stop_pct=15, hold_s=25, size_sol=0.5),
           "execution": dict(tx_latency_s=1.0, fee_bps=125, priority_fee_sol=0.001),
           "first_test": (U(14, 0), U(17, 15)), "in_sample": (U(12, 15), U(14, 0)),
           "sensitivity": {}},
    "H3": {"prefix": "H3:", "factory": lambda: DevDumpEntry(
               size_sol=1.0, max_age_s=30, min_dev_buy_sol=2.9, max_since_dump_s=20, hold_s=20, stop_pct=20),
           "execution": dict(tx_latency_s=1.0, fee_bps=125, priority_fee_sol=0.01, slippage_bps=2000, fail_prob=0.02),
           "first_test": (U(14, 45), U(17, 15)), "in_sample": (U(13, 38), U(14, 45)),
           "sensitivity": {"decu_costs": {"execution": dict(fee_bps=225, priority_fee_sol=0.015)},
                           "size_3_sol": {"factory": lambda: DevDumpEntry(
                               size_sol=3.0, max_age_s=30, min_dev_buy_sol=2.9, max_since_dump_s=20, hold_s=20,
                               stop_pct=20)}}},
}


def tape(start: float, end: float) -> duckdb.DuckDBPyConnection:
    """In-memory copy holding only data before `end` (plus 15 min of history): later data does not exist here."""
    src = market.connect()
    market.load(src)
    src.close()
    con = duckdb.connect()
    con.execute(f"ATTACH '{config.path('data') / 'market.duckdb'}' AS src (READ_ONLY)")
    con.execute("CREATE TABLE curve_trades AS SELECT * FROM src.curve_trades WHERE recv >= ? AND recv < ?", [start - 900, end])
    con.execute("CREATE TABLE curve_creates AS SELECT * FROM src.curve_creates WHERE recv >= ? AND recv < ?", [start - 900, end])
    con.execute("CREATE TABLE curve_completes AS SELECT * FROM src.curve_completes WHERE recv < ?", [end])
    con.execute("CREATE TABLE kol_wallets AS SELECT * FROM src.kol_wallets")
    con.execute("DETACH src")
    return con


def verdict(m: dict) -> dict:
    pf = m["profit_factor"]
    ok = (m["n_trades"] >= PASS["min_trades"] and (m["expectancy_sol"] or 0) > PASS["min_expectancy_sol"]
          and pf is not None and pf > PASS["min_profit_factor"])
    return {"pass": ok, "criteria": PASS}


def slim(m: dict) -> dict:
    keys = ("n_trades", "realized_pnl_sol", "expectancy_sol", "median_trade_sol", "win_rate", "profit_factor",
            "max_drawdown_sol", "protocol_fee_drag_sol", "network_fee_drag_sol", "slippage_drag_sol", "failed_tx",
            "rug_like_trades", "median_hold_s", "pnl_without_best_trade_sol", "open_positions_at_end")
    return {k: (round(m[k], 4) if isinstance(m.get(k), float) else m.get(k)) for k in keys}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("hyp", choices=sorted(HYPS))
    ap.add_argument("--split", choices=("train", "validation"), default="train")
    ap.add_argument("--in-sample", action="store_true", help="the window the hypothesis was derived from")
    a = ap.parse_args()
    h = HYPS[a.hyp]
    rdb = db.connect()
    hyp_id = rdb.execute("SELECT hypothesis_id FROM hypotheses WHERE statement LIKE ?", [h["prefix"] + "%"]).fetchone()[0]
    if a.split == "validation":
        s, e, _ = get_split(rdb, SPLIT_SET, "validation")
        role = "validation"
    else:
        s, e = h["in_sample"] if a.in_sample else h["first_test"]
        role = "in_sample" if a.in_sample else "first_test"
        ts, te, _ = get_split(rdb, SPLIT_SET, "train")
        assert ts <= s and e <= te, "train-split runs must stay inside the train period"
    start, end = s.timestamp(), e.timestamp()
    now = datetime.now(timezone.utc).timestamp()
    if end > now:
        raise SystemExit(f"window ends {e:%H:%M} UTC, data not complete yet")
    con = tape(start, end)
    store = build_market_store(con, start, end)
    base = base_execution(**h["execution"])
    res = run(h["factory"](), store, start=start, end=end, execution=base)
    prim = performance(res)
    label = f"{a.hyp} {role} {s:%H:%M}-{e:%H:%M} UTC"
    run_id = record_run(rdb, res, strategy=h["factory"](), split_set=SPLIT_SET, split_name=a.split,
                        hypothesis_id=hyp_id, notes=f"{label}; pre-registered parameters and execution")
    out = {"hypothesis": a.hyp, "hypothesis_id": hyp_id, "role": role, "window": [s.isoformat(), e.isoformat()],
           "run_id": run_id, "execution": base.to_dict(), "strategy": h["factory"]().spec(),
           "primary": slim(prim), "verdict": verdict(prim) if role != "in_sample" else "in-sample, not a test",
           "latency_sweep": [{"delay_s": r["delay_s"], **slim(r["metrics"])} for r in
                             sweep_latency(h["factory"], store, start=start, end=end, base=base,
                                           delays_s=(0.1, 0.5, 1, 2, 5, 10))],
           "sensitivity": {}}
    for name, v in h["sensitivity"].items():
        ex = dataclasses.replace(base, **v.get("execution", {}))
        r = run(v.get("factory", h["factory"])(), store, start=start, end=end, execution=ex)
        out["sensitivity"][name] = slim(performance(r))
    rep = config.path("simulation_reports")
    stem = f"{a.hyp.lower()}_{role}"
    (rep / f"{stem}.json").write_text(json.dumps(out, indent=1, default=str))
    (rep / f"{stem}.md").write_text(render(out))
    print(json.dumps({"label": label, "primary": out["primary"], "verdict": out["verdict"]}, indent=1, default=str))


def render(o: dict) -> str:
    p = o["primary"]
    L = [f"# {o['hypothesis']} — {o['role'].replace('_', ' ')} run", "",
         f"Window {o['window'][0]} → {o['window'][1]}; run `{o['run_id']}`; hypothesis `{o['hypothesis_id']}`.", "",
         f"Strategy: `{json.dumps(o['strategy'])}`", "",
         f"Execution: fee {o['execution']['fee_bps']} bps, priority+tip {o['execution']['priority_fee_sol']} SOL/tx, "
         f"latency {o['execution']['tx_latency_s']} s, slippage tolerance {o['execution']['slippage_bps']} bps, "
         f"tx failure {o['execution']['fail_prob']:.0%}.", "",
         f"**Verdict:** {o['verdict'] if isinstance(o['verdict'], str) else ('PASS' if o['verdict']['pass'] else 'FAIL')} "
         f"(pass needs ≥{PASS['min_trades']} trades, expectancy > 0, PF > {PASS['min_profit_factor']}).", "",
         "| run | trades | PnL SOL | expectancy | median | win rate | PF | max DD | fees+network | slippage | failed tx |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]

    def row(name, m):
        f = lambda x, d=3: "–" if x is None else (f"{x:.{d}f}" if isinstance(x, float) else str(x))
        return (f"| {name} | {m['n_trades']} | {f(m['realized_pnl_sol'])} | {f(m['expectancy_sol'], 4)} | "
                f"{f(m['median_trade_sol'], 4)} | {f(m['win_rate'], 2)} | {f(m['profit_factor'], 2)} | "
                f"{f(m['max_drawdown_sol'])} | {f((m['protocol_fee_drag_sol'] or 0) + (m['network_fee_drag_sol'] or 0))} | "
                f"{f(m['slippage_drag_sol'])} | {m['failed_tx']} |")
    L.append(row("primary", p))
    for r in o["latency_sweep"]:
        L.append(row(f"latency {r['delay_s']} s", r))
    for k, m in o["sensitivity"].items():
        L.append(row(k, m))
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
