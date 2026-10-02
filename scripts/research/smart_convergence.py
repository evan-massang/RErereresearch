"""Smart-money convergence: buy a bonding-curve token once k different proven wallets have bought it.

Motivation: Decu watches a tracker of labelled wallets; copying single winners trade-by-trade (H4) lost out of
sample, but the winners themselves stayed profitable (85 wallets profitable in both halves of Oct 1, vs 55 by
chance). Agreement of several independent winners is a far more selective signal than any one of them.

Smart set (defined ONLY from trades before `set_end`): wallets with >= min_trips closed curve round trips,
total PnL >= min_pnl_sol and win rate >= min_win, that are never the token creator and whose median entry is
>= 2 s after the create (launch-block snipers / bundles are excluded: a solo trader cannot follow them).

Signal: for tokens created in [start, end), the time the k-th distinct smart wallet makes its first buy, if the
token is at most max_age_s old then. Entry/exit (point in time, same conventions as final_stretch.py):
  entry   first curve trade >= signal + latency_s, at its price x (1 + entry_cost);
  stop    a print at or below (1 - stop_pct) x reference before completion -> sold at that print x (1 - exit_cost);
  tp      a print at or above tp_x x reference before completion -> sold at that print x (1 - exit_cost);
  migrate sell at the last PumpSwap price <= exit_after_s after the pool's first swap x (1 - amm_exit_cost);
  timeout last curve price within max_hold_s x (1 - exit_cost).
  Fixed fixed_sol_per_tx on entry and exit.

    python scripts/research/smart_convergence.py explore
"""
import itertools
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import duckdb  # noqa: E402
import pandas as pd  # noqa: E402

from pipeline import config  # noqa: E402

U = lambda h, m, d=1: pd.Timestamp(2026, 10, d, h, m, tz="UTC").timestamp()
SET = dict(min_trips=5, min_pnl_sol=0.5, min_win=0.5)
PARAMS = dict(k=3, max_age_s=600.0, latency_s=1.0, stop_pct=30.0, tp_x=None, exit_after_s=60.0, max_hold_s=1800.0,
              size_sol=0.5, entry_cost=0.03, exit_cost=0.03, amm_exit_cost=0.025, fixed_sol_per_tx=0.01)


def con_():
    return duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)


def trips_sql(con, a: float, b: float) -> pd.DataFrame:
    """Per (wallet, mint) buy/sell totals for tokens traded in [a, b); closed if >= 99% of bought tokens sold."""
    return con.execute("""
        WITH t AS (SELECT usr, mint, recv, buy, sol, tok FROM curve_trades WHERE recv >= ? AND recv < ?),
             c AS (SELECT mint, any_value(creator) creator, min(recv) ct FROM curve_creates GROUP BY 1)
        SELECT t.usr, t.mint, min(CASE WHEN buy THEN recv END) first_buy,
               sum(CASE WHEN buy THEN sol ELSE 0 END) sol_in, sum(CASE WHEN NOT buy THEN sol ELSE 0 END) sol_out,
               sum(CASE WHEN buy THEN tok ELSE 0 END) tok_in, sum(CASE WHEN NOT buy THEN tok ELSE 0 END) tok_out,
               any_value(c.creator) creator, any_value(c.ct) ct
        FROM t LEFT JOIN c USING (mint) GROUP BY 1, 2 HAVING sol_in > 0""", [a, b]).df()


def smart_set(con, a: float, b: float, s: dict = SET) -> set[str]:
    d = trips_sql(con, a, b)
    creators = set(d.creator.dropna())
    d = d[(d.tok_out >= 0.99 * d.tok_in) & d.ct.notna() & (d.first_buy >= d.ct)]
    d["pnl"] = d.sol_out - d.sol_in
    d["age"] = d.first_buy - d.ct
    g = d.groupby("usr").agg(n=("pnl", "size"), pnl=("pnl", "sum"), win=("pnl", lambda x: (x > 0).mean()),
                             age=("age", "median"))
    g = g[(g.n >= s["min_trips"]) & (g.pnl >= s["min_pnl_sol"]) & (g.win >= s["min_win"]) & (g.age >= 2)]
    return set(g.index) - creators


def signals(con, smart: set[str], a: float, b: float, k: int, max_age_s: float) -> list[tuple[str, float]]:
    con.execute("CREATE OR REPLACE TEMP TABLE smart AS SELECT unnest(?) usr", [sorted(smart)])
    rows = con.execute("""
        WITH c AS (SELECT mint, min(recv) ct FROM curve_creates GROUP BY 1 HAVING ct >= ? AND ct < ?),
             f AS (SELECT t.mint, t.usr, min(t.recv) fb FROM curve_trades t JOIN smart USING (usr) JOIN c USING (mint)
                   WHERE t.buy AND t.recv <= c.ct + ? GROUP BY 1, 2),
             r AS (SELECT mint, fb, row_number() OVER (PARTITION BY mint ORDER BY fb) rn FROM f)
        SELECT mint, fb FROM r WHERE rn = ? ORDER BY fb""", [a, b, max_age_s, k]).fetchall()
    return rows


def evaluate(con, sigs, data_end: float, p: dict = PARAMS) -> dict:
    comp = dict(con.execute("SELECT mint, min(recv) FROM curve_completes WHERE recv < ? GROUP BY 1", [data_end]).fetchall())
    pool = dict(con.execute("SELECT mint, pool FROM amm_pools").fetchall())
    trades, excluded = [], 0
    for m, t in sigs:
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
        hit = next(((r, q) for r, q in pre if (p["stop_pct"] is not None and q <= ref * (1 - p["stop_pct"] / 100))
                    or (p["tp_x"] is not None and q >= ref * p["tp_x"])), None)
        if hit is not None:
            ret, how = hit[1] * (1 - p["exit_cost"]) / cost_in - 1, "stop" if hit[1] < ref else "tp"
        elif tc is not None:
            a = con.execute("SELECT recv, sol / tok FROM amm_trades WHERE pool = ? AND recv >= ? AND recv < ? "
                            "ORDER BY recv, rowid", [pool[m], tc, data_end]).fetchall()
            if not a:
                excluded += 1
                continue
            s = [q for r, q in a if r <= a[0][0] + p["exit_after_s"]][-1] * 1e9
            ret, how = s * (1 - p["amm_exit_cost"]) / cost_in - 1, "migrated"
        elif pre:
            ret, how = pre[-1][1] * (1 - p["exit_cost"]) / cost_in - 1, "timeout"
        else:
            continue
        trades.append({"mint": m, "t": t, "ret": round(ret, 4),
                       "pnl_sol": round(p["size_sol"] * ret - 2 * p["fixed_sol_per_tx"], 4), "exit": how})
    v = sorted(r["pnl_sol"] for r in trades)
    wins, losses = [x for x in v if x > 0], [x for x in v if x <= 0]
    return {"n_trades": len(v), "excluded_no_pool": excluded, "pnl_sol": round(sum(v), 3),
            "expectancy_sol": round(statistics.mean(v), 4) if v else None,
            "median_sol": round(statistics.median(v), 4) if v else None,
            "win_rate": round(len(wins) / len(v), 3) if v else None,
            "profit_factor": round(sum(wins) / -sum(losses), 3) if losses and sum(losses) < 0 else None,
            "pnl_without_top3": round(sum(v[:-3]), 3) if len(v) > 3 else None,
            "exits": {k: sum(1 for r in trades if r["exit"] == k) for k in ("stop", "tp", "migrated", "timeout")},
            "trades": trades}


def explore() -> list[dict]:
    """Train only: smart set from 12:17-14:15, signals on tokens created 14:15-16:15, outcomes to 17:15."""
    con = con_()
    smart = smart_set(con, U(12, 17), U(14, 15))
    print(f"smart wallets: {len(smart)}")
    out = []
    for k, stop, tp, ex in itertools.product([2, 3, 4, 5], [30, 50], [None, 2.0, 3.0], [60, 300]):
        p = PARAMS | {"k": k, "stop_pct": stop, "tp_x": tp, "exit_after_s": ex}
        o = evaluate(con, signals(con, smart, U(14, 15), U(16, 15), k, p["max_age_s"]), U(17, 15), p)
        out.append({kk: o[kk] for kk in ("n_trades", "pnl_sol", "expectancy_sol", "median_sol", "profit_factor",
                                         "pnl_without_top3", "exits")} | {"k": k, "stop": stop, "tp": tp, "exit_after_s": ex})
    return out


if __name__ == "__main__":
    if sys.argv[1:2] == ["explore"]:
        for r in sorted(explore(), key=lambda r: -(r["pnl_sol"] or 0)):
            print(r)
