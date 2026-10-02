"""Final-stretch strategy (solo trader, no copying): buy a bonding-curve token once it is far along its curve,
hold it through migration, sell into the post-migration minutes on PumpSwap.

Point-in-time evaluator (the event simulator cannot exit on the AMM):
  entry   first curve trade at least `latency_s` after the first trade that reached `entry_mcap_sol`
          (market cap = vsol/vtok x 1e9), at that trade's price x (1 + entry_cost);
  stop    if, before the curve completes, a trade prints at or below (1 - stop_pct) x reference price, the
          position is sold at that trade's price x (1 - curve_exit_cost)  (the actual print, not the stop level);
  migrate if the curve completes, sell at the last PumpSwap swap price at or before `exit_after_s` after the
          pool's first swap, x (1 - amm_exit_cost);
  timeout otherwise sell at the last curve price within `max_hold_s`, x (1 - curve_exit_cost).
  Fixed costs: `fixed_sol_per_tx` (priority fee + tip) on entry and exit. Tokens that completed but whose pool was
  not decoded are excluded and counted.

    python scripts/research/final_stretch.py 12:17 16:45          # exploration window (entries)
"""
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import duckdb  # noqa: E402

from pipeline import config  # noqa: E402

PARAMS = dict(entry_mcap_sol=250.0, latency_s=1.0, stop_pct=30.0, exit_after_s=300.0, max_hold_s=3600.0,
              size_sol=1.0, entry_cost=0.03, curve_exit_cost=0.03, amm_exit_cost=0.025, fixed_sol_per_tx=0.01)


def hm(s: str) -> float:
    return datetime.strptime(f"2026-10-01 {s}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).timestamp()


def evaluate(start: float, end: float, data_end: float, p: dict = PARAMS) -> dict:
    """Entries in [start, end); outcomes may use data up to data_end only."""
    con = duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
    comp = dict(con.execute("SELECT mint, min(recv) FROM curve_completes WHERE recv < ? GROUP BY 1", [data_end]).fetchall())
    pool = dict(con.execute("SELECT mint, pool FROM amm_pools").fetchall())
    trades, excluded = [], 0
    for m, t in con.execute("""SELECT mint, min(recv) FROM curve_trades WHERE vsol / vtok * 1e9 >= ? AND recv < ?
                               GROUP BY 1 HAVING min(recv) >= ? AND min(recv) < ?""",
                            [p["entry_mcap_sol"], end, start, end]).fetchall():
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
        hit = next((q for r, q in pre if q <= ref * (1 - p["stop_pct"] / 100)), None)
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
        else:
            ret, how = pre[-1][1] * (1 - p["curve_exit_cost"]) / cost_in - 1, "timeout"
        pnl = p["size_sol"] * ret - 2 * p["fixed_sol_per_tx"]
        trades.append({"mint": m, "t": t, "ret": round(ret, 4), "pnl_sol": round(pnl, 4), "exit": how})
    v = sorted(r["pnl_sol"] for r in trades)
    wins, losses = [x for x in v if x > 0], [x for x in v if x <= 0]
    return {"params": p, "window": [start, end], "n_trades": len(v), "excluded_no_pool": excluded,
            "pnl_sol": round(sum(v), 3), "expectancy_sol": round(statistics.mean(v), 4) if v else None,
            "median_sol": round(statistics.median(v), 4) if v else None,
            "win_rate": round(len(wins) / len(v), 3) if v else None,
            "profit_factor": round(sum(wins) / -sum(losses), 3) if losses and sum(losses) < 0 else None,
            "expectancy_without_top3": round(statistics.mean(v[:-3]), 4) if len(v) > 3 else None,
            "exits": {k: sum(1 for r in trades if r["exit"] == k) for k in ("stop", "migrated", "timeout")},
            "trades": trades}


if __name__ == "__main__":
    a, b = (hm(sys.argv[1]), hm(sys.argv[2])) if len(sys.argv) >= 3 else (hm("12:17"), hm("16:45"))
    data_end = hm(sys.argv[3]) if len(sys.argv) >= 4 else b + 3600
    o = evaluate(a, b, data_end)
    print(json.dumps({k: v for k, v in o.items() if k != "trades"}, indent=1))
