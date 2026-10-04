"""Identify the pump.fun Mayhem Mode agent wallet(s) from curve_trades (train window only).

Wallets ranked by distinct Mayhem mints traded vs distinct non-Mayhem mints traded, with fee_bps.
    python scripts/research/mayhem_agent.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import duckdb  # noqa: E402

HOLD0, OCT2, OCT3, OCT4 = 1790882100.0, 1790899200.0, 1790985600.0, 1791072000.0
TRAIN = f"(recv < {HOLD0} OR (recv >= {OCT2} AND recv < {OCT3}))"


def connect():
    con = duckdb.connect(str(ROOT / "data/market.duckdb"), read_only=True)
    con.execute("SET memory_limit='3GB'; SET threads=2")
    con.execute(f"CREATE TEMP VIEW flags AS SELECT mint, is_mayhem FROM read_parquet('{ROOT}/data/processed/mayhem_flags.parquet')")
    return con


if __name__ == "__main__":
    con = connect()
    q = f"""SELECT t.usr, count(DISTINCT CASE WHEN f.is_mayhem THEN t.mint END) mm,
                   count(DISTINCT CASE WHEN NOT f.is_mayhem THEN t.mint END) nm,
                   count(*) n, sum(t.buy::INT) nb, avg(t.sol) avg_sol, min(t.fee_bps) fmin, max(t.fee_bps) fmax
            FROM curve_trades t JOIN flags f USING (mint) WHERE {TRAIN} GROUP BY 1 ORDER BY mm DESC LIMIT 25"""
    print(con.execute(q).df().to_string())
    print(con.execute(f"""SELECT f.is_mayhem, count(DISTINCT t.mint) FROM curve_trades t JOIN flags f USING (mint)
                          WHERE {TRAIN} GROUP BY 1""").df())
