"""Overnight analysis on the recorded tape (re-runnable as data accumulates).

    python scripts/research/overnight_analysis.py train        # development period only
    python scripts/research/overnight_analysis.py validation

Writes reports/simulations/overnight_<split>.json and .md. The holdout is never
touched here; it is evaluated once by scripts/research/evaluate_holdout.py.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pipeline import config, db, market  # noqa: E402
from pipeline.copytrade import copy_test  # noqa: E402
from pipeline.sim.splits import get_split  # noqa: E402

SPLIT_SET = "overnight-2026-10-01"
SEEDS = {"decu": "4vw54BmAogeRV3vPKWyFet5yf8DTLcREzdSzx4rw9Ud9",
         "cupsey": "2fg5QD1eD7rzNNCsvnhmXFm5hqNgwTTG8p7kQ6f3rx6f",
         "leck": "98T65wcMEjoNLDTJszBHGZEX75QRe8QaANXokv4yw3Mp",
         "setuh": "62N1K57D37AUDGp68tnDYKPjGDsaAAtmo357nBtEtuR"}


def main(split: str) -> dict:
    if split not in ("train", "validation"):
        raise SystemExit("only train or validation; the holdout has its own one-shot script")
    rdb = db.connect()
    start_dt, end_dt, _ = get_split(rdb, SPLIT_SET, split)
    start, end = start_dt.timestamp(), min(end_dt.timestamp(), datetime.now(timezone.utc).timestamp())
    src = market.connect()
    loaded = market.load(src)
    src.close()
    # Work on an in-memory copy holding only data available before the period's end (plus 1 h of history
    # before its start): nothing after `end` exists for this analysis, and the shared DB is never modified.
    import duckdb
    con = duckdb.connect()
    con.execute(f"ATTACH '{config.path('data') / 'market.duckdb'}' AS src (READ_ONLY)")
    con.execute("CREATE TABLE curve_trades AS SELECT * FROM src.curve_trades WHERE recv >= ? AND recv < ?",
                [start - 3600, end])
    con.execute("CREATE TABLE curve_creates AS SELECT * FROM src.curve_creates WHERE recv < ?", [end])
    con.execute("CREATE TABLE curve_completes AS SELECT * FROM src.curve_completes WHERE recv < ?", [end])
    con.execute("CREATE TABLE kol_wallets AS SELECT * FROM src.kol_wallets")
    con.execute("DETACH src")
    in_window = con.execute("SELECT count(*), count(DISTINCT mint), count(DISTINCT usr) FROM curve_trades "
                            "WHERE recv >= ?", [start]).fetchone()
    names = dict(con.execute("SELECT wallet, name FROM kol_wallets").fetchall())

    def trips_for(w):
        return [t for t in market.round_trips(con, [w]) if start <= t.first_ts < end]

    out = {"split": split, "window": [start, end], "hours": round((end - start) / 3600, 2),
           "tape": {"trades": in_window[0], "tokens": in_window[1], "wallets": in_window[2]},
           "loaded": loaded, "seeds": {}, "leaders": []}
    for slug, w in SEEDS.items():
        trips = trips_for(w)
        entry = {"wallet": w, "summary": market.summarize(trips)}
        if any(t.closed for t in trips):
            entry["selection_edge"] = market.selection_edge(con, [t for t in trips if t.closed])
            entry["copy"] = copy_test(con, w, start, end)
        out["seeds"][slug] = entry

    # every tracked wallet, ranked by realized bonding-curve PnL in the window
    board = []
    for row in market.leaderboard(con, min_trips=5):
        trips = [t for t in market.round_trips(con, [row["wallet"]]) if start <= t.first_ts < end]
        s = market.summarize(trips)
        if s.get("closed_trips", 0) >= 5:
            board.append({"wallet": row["wallet"], "name": names.get(row["wallet"]), **s})
    board.sort(key=lambda r: -r["pnl_sol"])
    out["leaderboard_top"] = board[:25]
    out["leaderboard_n"] = len(board)
    for row in board[:8]:
        w = row["wallet"]
        trips = [t for t in trips_for(w) if t.closed]
        out["leaders"].append({"wallet": w, "name": row["name"], "summary": row,
                               "selection_edge": market.selection_edge(con, trips),
                               "copy": copy_test(con, w, start, end)})
    rep = config.path("simulation_reports")
    (rep / f"overnight_{split}.json").write_text(json.dumps(out, indent=1, default=str))
    (rep / f"overnight_{split}.md").write_text(render(out))
    return out


def render(o: dict) -> str:
    L = [f"# Overnight tape analysis — {o['split']} period", "",
         f"Window: {datetime.fromtimestamp(o['window'][0], timezone.utc):%Y-%m-%d %H:%M} → "
         f"{datetime.fromtimestamp(o['window'][1], timezone.utc):%H:%M} UTC ({o['hours']} h). "
         f"Tape: {o['tape']['trades']:,} bonding-curve trades, {o['tape']['tokens']:,} tokens, "
         f"{o['tape']['wallets']:,} wallets.", "",
         "All numbers are bonding-curve trades only, from on-chain events. PnL in SOL after the on-chain 1.25% fee, "
         "before priority fees. Copy tests add a 0.001 SOL priority fee per tx, 20% slippage tolerance and 2% random "
         "tx failure (assumptions).", ""]

    def copy_table(c):
        if not c or not c.get("sweep"):
            return ["(no copyable trades)"]
        rows = ["| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |",
                "|---|---|---|---|---|---|---|---|---|"]
        for s in c["sweep"]:
            fee = (s["protocol_fee_drag_sol"] or 0) + (s["network_fee_drag_sol"] or 0)
            rows.append(f"| {s['delay_s']}s | {s['n_trades']} | {s['realized_pnl_sol']:.3f} | "
                        f"{(s['expectancy_sol'] or 0):.4f} | {s['win_rate'] if s['win_rate'] is not None else '–'} | "
                        f"{s['profit_factor'] if s['profit_factor'] is not None else '–'} | {s['failed_tx']} | "
                        f"{fee:.3f} | {'below data resolution' if s['below_data_resolution'] else ''} |")
        return rows

    L += ["## Seed traders", ""]
    for slug, e in o["seeds"].items():
        L += [f"### {slug}", "", f"`{e['wallet']}`", "", f"```\n{json.dumps(e['summary'], indent=1)}\n```"]
        if "selection_edge" in e:
            L += ["Selection vs random same-moment tokens:", f"```\n{json.dumps(e['selection_edge'])}\n```",
                  "Copy test (0.5 SOL per entry):", ""] + copy_table(e.get("copy"))
        L.append("")
    L += ["## Most profitable tracked wallets in this window", "",
          f"{o['leaderboard_n']} wallets had ≥5 closed bonding-curve round trips.", "",
          "| name | trips | PnL SOL | win rate | PF | median hold s | median entry mcap SOL | best-trade share |",
          "|---|---|---|---|---|---|---|---|"]
    for r in o["leaderboard_top"]:
        L.append(f"| {r['name']} | {r['closed_trips']} | {r['pnl_sol']} | {r['win_rate']} | {r['profit_factor']} | "
                 f"{r['median_hold_s']} | {r['median_entry_mcap_sol']} | {r['best_trade_share_of_pnl']} |")
    L += ["", "## Top wallets: is their selection better than random, and can it be copied?", ""]
    for x in o["leaders"]:
        L += [f"### {x['name']} (`{x['wallet'][:8]}…`)", "", f"Selection edge: `{json.dumps(x['selection_edge'])}`",
              ""] + copy_table(x["copy"]) + [""]
    return "\n".join(L)


if __name__ == "__main__":
    res = main(sys.argv[1] if len(sys.argv) > 1 else "train")
    print(json.dumps({"hours": res["hours"], "tape": res["tape"],
                      "seeds": {k: v["summary"] for k, v in res["seeds"].items()},
                      "top": [(r["name"], r["closed_trips"], r["pnl_sol"]) for r in res["leaderboard_top"][:10]]},
                     indent=1, default=str))
