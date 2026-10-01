"""Market tape analysis: tracked traders' on-chain behaviour on the pump.fun bonding curve.

Inputs are the recorder's files (data/raw/streams). Everything is loaded into a
separate DuckDB file, data/market.duckdb (git-ignored; large), and summaries are
written to reports/.

Caveats that apply to every number derived here:
* Only bonding-curve trades are decoded. Positions that continue after a token
  graduates to PumpSwap are incomplete and flagged, never counted as closed.
* Block timestamps have 1 s resolution; ``recv`` (our receive time) is sub-second
  but includes feed latency.
* Tokens quoted in something other than SOL (vsol == 0) are excluded.
"""

from __future__ import annotations

import gzip
import json
import random
import statistics
import zlib
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import duckdb

from . import config

SUPPLY = 1e9                 # pump.fun tokens: 1,000,000,000 supply
DEFAULT_FEE_BPS = 125        # 95 protocol + 30 creator, read from on-chain TradeEvents (2026-10-01)


def iter_stream(feed: str, since: str | None = None) -> Iterator[dict]:
    """All JSON lines of a feed in file order; truncated gzip tails are tolerated."""
    d = config.path("raw_streams", feed)
    for f in sorted(d.glob("*.jsonl.gz")):
        if since and f.name < since:
            continue
        try:
            with gzip.open(f, "rt") as fh:
                for line in fh:
                    try:
                        yield json.loads(line)
                    except ValueError:
                        continue
        except (EOFError, zlib.error, OSError):
            continue          # file still being written, or a killed writer's tail


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(config.path("data") / "market.duckdb"))
    con.execute("""
        CREATE TABLE IF NOT EXISTS curve_trades (
            src_file VARCHAR, sig VARCHAR, slot BIGINT, recv DOUBLE, ts BIGINT, mint VARCHAR, usr VARCHAR,
            buy BOOLEAN, sol DOUBLE, tok DOUBLE, vsol DOUBLE, vtok DOUBLE, rsol DOUBLE, rtok DOUBLE,
            fee_bps INTEGER, cfee_bps INTEGER);
        CREATE TABLE IF NOT EXISTS curve_creates (
            src_file VARCHAR, mint VARCHAR, sig VARCHAR, slot BIGINT, recv DOUBLE, name VARCHAR, symbol VARCHAR,
            uri VARCHAR, creator VARCHAR);
        CREATE TABLE IF NOT EXISTS curve_completes (src_file VARCHAR, mint VARCHAR, sig VARCHAR, recv DOUBLE);
        CREATE TABLE IF NOT EXISTS kol_wallets (wallet VARCHAR PRIMARY KEY, name VARCHAR, twitter VARCHAR,
            telegram VARCHAR);
        CREATE TABLE IF NOT EXISTS kolscan_msgs (src_file VARCHAR, recv DOUBLE, wallet VARCHAR, signature VARCHAR,
            dex VARCHAR, direction VARCHAR, in_token VARCHAR, out_token VARCHAR, in_amount DOUBLE,
            out_amount DOUBLE, sol_change DOUBLE, ts BIGINT);
        CREATE TABLE IF NOT EXISTS loaded_files (feed VARCHAR, name VARCHAR, complete BOOLEAN,
            PRIMARY KEY (feed, name));
    """)
    return con


def _read_file(f: Path) -> Iterator[dict]:
    try:
        with gzip.open(f, "rt") as fh:
            for line in fh:
                try:
                    yield json.loads(line)
                except ValueError:
                    continue
    except (EOFError, zlib.error, OSError):
        return


def _complete(f: Path) -> bool:
    """A file is final once its writer moved on (an hour later) and it has not changed for 2 minutes."""
    import time
    hour = f.name.split("_")[0] + f.name.split("_")[1]
    now_hour = datetime.now(timezone.utc).strftime("%Y%m%d%H")
    return hour < now_hour and time.time() - f.stat().st_mtime > 120


def load(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Incrementally load recorder output: finished files once, growing files re-read each time."""
    import pandas as pd

    kols = json.loads((config.REPO_ROOT / "sources" / "kolscan_kols.json").read_text())
    con.execute("DELETE FROM kol_wallets")
    con.executemany("INSERT INTO kol_wallets VALUES (?,?,?,?)",
                    [(k["wallet"], k["name"], k["twitter"], k["telegram"]) for k in kols])
    done = {(r[0], r[1]) for r in con.execute("SELECT feed, name FROM loaded_files WHERE complete").fetchall()}
    added = {"curve_trades": 0, "creates": 0, "completes": 0, "kolscan_msgs": 0, "files": 0}
    for feed in ("pump_curve", "kolscan"):
        for f in sorted(config.path("raw_streams", feed).glob("*.jsonl.gz")):
            if (feed, f.name) in done:
                continue
            complete = _complete(f)
            added["files"] += 1
            if feed == "pump_curve":
                for t in ("curve_trades", "curve_creates", "curve_completes"):
                    con.execute(f"DELETE FROM {t} WHERE src_file = ?", [f.name])
                tr, cr, co = [], [], []
                for r in _read_file(f):
                    e = r.get("e")
                    if e == "trade" and r.get("vsol"):
                        tr.append((f.name, r["sig"], r.get("slot"), r["recv"], r["ts"], r["mint"], r["user"], r["buy"],
                                   r["sol"], r["tok"], r["vsol"], r["vtok"], r["rsol"], r["rtok"], r.get("fee_bps"),
                                   r.get("cfee_bps")))
                    elif e == "create":
                        cr.append((f.name, r["mint"], r["sig"], r.get("slot"), r["recv"], r["name"], r["symbol"],
                                   r["uri"], r["user"]))
                    elif e == "complete":
                        co.append((f.name, r["mint"], r["sig"], r["recv"]))
                for table, rows, cols in (
                        ("curve_trades", tr, ["src_file", "sig", "slot", "recv", "ts", "mint", "usr", "buy", "sol",
                                              "tok", "vsol", "vtok", "rsol", "rtok", "fee_bps", "cfee_bps"]),
                        ("curve_creates", cr, ["src_file", "mint", "sig", "slot", "recv", "name", "symbol", "uri",
                                               "creator"]),
                        ("curve_completes", co, ["src_file", "mint", "sig", "recv"])):
                    if rows:
                        df = pd.DataFrame(rows, columns=cols)
                        con.register("_df", df)
                        con.execute(f"INSERT INTO {table} SELECT * FROM _df")
                        con.unregister("_df")
                added["curve_trades"] += len(tr)
                added["creates"] += len(cr)
                added["completes"] += len(co)
            else:
                con.execute("DELETE FROM kolscan_msgs WHERE src_file = ?", [f.name])
                rows = []
                for r in _read_file(f):
                    m = r.get("msg")
                    if m:
                        rows.append((f.name, r["recv"], m.get("wallet_address"), m.get("signature"), m.get("dex"),
                                     m.get("spl_direction"), m.get("in_token_address"), m.get("out_token_address"),
                                     m.get("in_amount"), m.get("out_amount"), m.get("sol_change"), m.get("timestamp")))
                if rows:
                    df = pd.DataFrame(rows, columns=["src_file", "recv", "wallet", "signature", "dex", "direction",
                                                     "in_token", "out_token", "in_amount", "out_amount", "sol_change",
                                                     "ts"])
                    con.register("_df", df)
                    con.execute("INSERT INTO kolscan_msgs SELECT * FROM _df")
                    con.unregister("_df")
                added["kolscan_msgs"] += len(rows)
            con.execute("INSERT OR REPLACE INTO loaded_files VALUES (?, ?, ?)", [feed, f.name, complete])
    added["total_curve_trades"] = con.execute("SELECT count(*) FROM curve_trades").fetchone()[0]
    return added


# ------------------------------------------------------------------ round trips

@dataclass
class Trip:
    wallet: str
    mint: str
    first_ts: float          # recv time of first buy (sub-second)
    last_ts: float
    sol_in: float            # incl. fees
    sol_out: float           # net of fees
    n_buys: int
    n_sells: int
    entry_mcap_sol: float    # price paid on the first buy x supply
    entry_rsol: float        # real SOL in the curve after their first buy (curve progress)
    age_at_entry_s: float | None
    closed: bool             # position back to ~0 on the curve
    graduated: bool          # token completed the curve during/after the trip
    entry_slot_delta: int | None = None   # slots between token creation and their first buy (0 = same block)

    @property
    def pnl(self) -> float:
        return self.sol_out - self.sol_in

    @property
    def hold_s(self) -> float:
        return self.last_ts - self.first_ts


def _fee(bps: int | None, cbps: int | None) -> float:
    if bps is None:
        return DEFAULT_FEE_BPS / 1e4
    return ((bps or 0) + (cbps or 0)) / 1e4


def round_trips(con: duckdb.DuckDBPyConnection, wallets: list[str] | None = None) -> list[Trip]:
    where = "WHERE usr IN (SELECT wallet FROM kol_wallets)" if wallets is None else \
        f"WHERE usr IN ({', '.join('?' for _ in wallets)})"
    rows = con.execute(f"""SELECT usr, mint, recv, ts, buy, sol, tok, vsol, vtok, rsol, fee_bps, cfee_bps, slot
                           FROM curve_trades {where} ORDER BY usr, mint, recv""", wallets or []).fetchall()
    created = dict(con.execute("SELECT mint, recv FROM curve_creates").fetchall())
    create_slot = dict(con.execute("SELECT mint, slot FROM curve_creates").fetchall())
    graduated = {r[0] for r in con.execute("SELECT mint FROM curve_completes").fetchall()}
    trips: list[Trip] = []
    cur: dict[tuple[str, str], dict] = {}
    for usr, mint, recv, ts, buy, sol, tok, vsol, vtok, rsol, fbps, cbps, slot in rows:
        key = (usr, mint)
        f = _fee(fbps, cbps)
        st = cur.get(key)
        if buy:
            if st is None:
                st = cur[key] = {"first": recv, "last": recv, "in": 0.0, "out": 0.0, "nb": 0, "ns": 0, "pos": 0.0,
                                 "peak": 0.0, "mcap": (sol / tok) * SUPPLY if tok else None, "rsol": rsol,
                                 "age": (recv - created[mint]) if mint in created else None,
                                 "dslot": (slot - create_slot[mint]) if (slot and create_slot.get(mint)) else None}
            st["in"] += sol * (1 + f)
            st["pos"] += tok
            st["peak"] = max(st["peak"], st["pos"])
            st["nb"] += 1
            st["last"] = recv
        else:
            if st is None:
                continue                         # sold a position opened before recording started
            st["out"] += sol * (1 - f)
            st["pos"] -= tok
            st["ns"] += 1
            st["last"] = recv
            if st["pos"] <= 0.01 * st["peak"]:
                trips.append(Trip(usr, mint, st["first"], st["last"], st["in"], st["out"], st["nb"], st["ns"],
                                  st["mcap"], st["rsol"], st["age"], True, mint in graduated, st["dslot"]))
                del cur[key]
    for (usr, mint), st in cur.items():
        trips.append(Trip(usr, mint, st["first"], st["last"], st["in"], st["out"], st["nb"], st["ns"],
                          st["mcap"], st["rsol"], st["age"], False, mint in graduated, st["dslot"]))
    return trips


def summarize(trips: list[Trip]) -> dict:
    closed = [t for t in trips if t.closed]
    if not closed:
        return {"closed_trips": 0, "open_or_incomplete": len(trips)}
    pnls = [t.pnl for t in closed]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    ages = [t.age_at_entry_s for t in closed if t.age_at_entry_s is not None]
    return {
        "closed_trips": len(closed),
        "open_or_incomplete": len(trips) - len(closed),
        "pnl_sol": round(sum(pnls), 4),
        "win_rate": round(len(wins) / len(pnls), 3),
        "avg_win_sol": round(statistics.mean(wins), 4) if wins else None,
        "avg_loss_sol": round(statistics.mean(losses), 4) if losses else None,
        "profit_factor": round(sum(wins) / -sum(losses), 3) if losses and sum(losses) < 0 else None,
        "median_hold_s": round(statistics.median(t.hold_s for t in closed), 1),
        "median_size_sol": round(statistics.median(t.sol_in for t in closed), 3),
        "median_entry_mcap_sol": round(statistics.median(t.entry_mcap_sol for t in closed if t.entry_mcap_sol), 1),
        "median_age_at_entry_s": round(statistics.median(ages), 1) if ages else None,
        "share_multi_buy": round(sum(1 for t in closed if t.n_buys > 1) / len(closed), 3),
        "share_multi_sell": round(sum(1 for t in closed if t.n_sells > 1) / len(closed), 3),
        "best_trade_share_of_pnl": round(max(pnls) / sum(pnls), 3) if sum(pnls) > 0 else None,
        # entries in the token's creation block (0 slots) or within ~2 s (<=5 slots): not reproducible by a
        # discretionary trader or a copier; often the deployer's own bundle
        "share_entries_creation_block": _share(closed, lambda t: t.entry_slot_delta == 0),
        "share_entries_within_5_slots": _share(closed, lambda t: t.entry_slot_delta is not None and t.entry_slot_delta <= 5),
        "pnl_from_creation_block_entries_sol": round(sum(t.pnl for t in closed if t.entry_slot_delta == 0), 4),
        "share_entries_with_known_creation": _share(closed, lambda t: t.entry_slot_delta is not None),
    }


def _share(trips, pred) -> float | None:
    return round(sum(1 for t in trips if pred(t)) / len(trips), 3) if trips else None


def leaderboard(con: duckdb.DuckDBPyConnection, min_trips: int = 5) -> list[dict]:
    names = dict(con.execute("SELECT wallet, name FROM kol_wallets").fetchall())
    by: dict[str, list[Trip]] = defaultdict(list)
    for t in round_trips(con):
        by[t.wallet].append(t)
    out = []
    for w, ts in by.items():
        s = summarize(ts)
        if s.get("closed_trips", 0) >= min_trips:
            out.append({"wallet": w, "name": names.get(w), **s})
    return sorted(out, key=lambda r: -r["pnl_sol"])


# ------------------------------------------------------------------ selection edge vs random

def _price_path(con, mint: str) -> tuple[list[float], list[float]]:
    rows = con.execute("SELECT recv, vsol / vtok FROM curve_trades WHERE mint = ? ORDER BY recv", [mint]).fetchall()
    return [r[0] for r in rows], [r[1] for r in rows]


def _price_at(times: list[float], prices: list[float], t: float) -> float | None:
    import bisect
    i = bisect.bisect_right(times, t) - 1
    return prices[i] if i >= 0 else None


def selection_edge(con: duckdb.DuckDBPyConnection, trips: list[Trip], *, horizon_s: float | None = None,
                   mcap_band: float = 0.5, n_random: int = 5, seed: int = 0) -> dict:
    """Did the tokens a trader bought do better than random tokens at the same moment?

    For each entry, compare the token's price change over the trader's hold (or
    ``horizon_s``) with tokens that traded in the 60 s before the entry and had a
    market cap within +/- mcap_band of the trader's token. Uses mid prices from
    reserves, no fees: this isolates *selection*, not execution.
    """
    rng = random.Random(seed)
    paths: dict[str, tuple[list[float], list[float]]] = {}

    def path(m):
        if m not in paths:
            paths[m] = _price_path(con, m)
        return paths[m]

    diffs, picks, rands = [], [], []
    for t in trips:
        h = horizon_s or max(t.hold_s, 5.0)
        tt, pp = path(t.mint)
        p0, p1 = _price_at(tt, pp, t.first_ts), _price_at(tt, pp, t.first_ts + h)
        if not p0 or not p1:
            continue
        mc = p0 * SUPPLY
        cands = con.execute("""SELECT mint, arg_max(vsol / vtok, recv) FROM curve_trades
                               WHERE recv BETWEEN ? AND ? AND mint <> ? GROUP BY mint""",
                            [t.first_ts - 60, t.first_ts, t.mint]).fetchall()
        cands = [m for m, p in cands if p and (1 - mcap_band) * mc <= p * SUPPLY <= (1 + mcap_band) * mc]
        if not cands:
            continue
        r_rets = []
        for m in rng.sample(cands, min(n_random, len(cands))):
            rt, rp = path(m)
            a, b = _price_at(rt, rp, t.first_ts), _price_at(rt, rp, t.first_ts + h)
            if a and b:
                r_rets.append(b / a - 1)
        if not r_rets:
            continue
        pick = p1 / p0 - 1
        rnd = statistics.mean(r_rets)
        picks.append(pick)
        rands.append(rnd)
        diffs.append(pick - rnd)
    if not diffs:
        return {"n": 0}
    wins = sum(1 for d in diffs if d > 0)
    return {"n": len(diffs), "median_pick_return": round(statistics.median(picks), 4),
            "median_random_return": round(statistics.median(rands), 4),
            "median_difference": round(statistics.median(diffs), 4),
            "share_pick_beats_random": round(wins / len(diffs), 3),
            "sign_test_p": round(_sign_test_p(wins, len(diffs)), 4)}


def _sign_test_p(k: int, n: int) -> float:
    """Two-sided exact binomial sign test, p = 0.5."""
    from math import comb
    tail = sum(comb(n, i) for i in range(0, min(k, n - k) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


# ------------------------------------------------------------------ event study: what happens around a tracked entry

def event_study(con: duckdb.DuckDBPyConnection, trips: list[Trip], *, windows=((-30, 0), (0, 5), (5, 15), (15, 60)),
                horizons=(5, 15, 60, 180), exclude_wallet: bool = True) -> dict:
    """Buy/sell flow and price around each tracked entry (t=0 = their first buy, receive time).

    Flow is SOL bought minus SOL sold by *other* wallets per second in each window.
    Price change is measured from the last price *before* their buy, so their own
    impact is included in the move a copier would face.
    """
    import bisect
    flows: dict[tuple, list[float]] = {w: [] for w in windows}
    rets: dict[int, list[float]] = {h: [] for h in horizons}
    n = 0
    for t in trips:
        rows = con.execute("""SELECT recv, usr, buy, sol, vsol / vtok FROM curve_trades
                              WHERE mint = ? AND recv BETWEEN ? AND ? ORDER BY recv""",
                           [t.mint, t.first_ts - 60, t.first_ts + max(horizons) + 1]).fetchall()
        if not rows:
            continue
        times = [r[0] for r in rows]
        i0 = bisect.bisect_left(times, t.first_ts - 1e-6)
        if i0 == 0:
            continue                                  # no price before their buy (bought at creation?)
        p0 = rows[i0 - 1][4]
        n += 1
        for (a, b) in windows:
            net = sum((r[3] if r[2] else -r[3]) for r in rows
                      if t.first_ts + a <= r[0] < t.first_ts + b and not (exclude_wallet and r[1] == t.wallet))
            flows[(a, b)].append(net / (b - a))
        for h in horizons:
            j = bisect.bisect_right(times, t.first_ts + h) - 1
            if j >= i0:
                rets[h].append(rows[j][4] / p0 - 1)
    med = lambda xs: round(statistics.median(xs), 4) if xs else None
    return {"n": n,
            "net_flow_sol_per_s": {f"{a}..{b}s": med(v) for (a, b), v in flows.items()},
            "median_return_from_pre_entry_price": {f"+{h}s": med(v) for h, v in rets.items()},
            "share_up": {f"+{h}s": (round(sum(1 for x in v if x > 0) / len(v), 3) if v else None)
                         for h, v in rets.items()}}


def random_entries(con: duckdb.DuckDBPyConnection, trips: list[Trip], per_trip: int = 3, seed: int = 1) -> list[Trip]:
    """Control group: at each tracked entry time, random other tokens with a similar market cap (+/-50%)."""
    rng = random.Random(seed)
    out = []
    for t in trips:
        cands = con.execute("""SELECT mint, arg_max(vsol / vtok, recv) FROM curve_trades
                               WHERE recv BETWEEN ? AND ? AND mint <> ? GROUP BY mint""",
                            [t.first_ts - 30, t.first_ts, t.mint]).fetchall()
        mc = t.entry_mcap_sol or 0
        cands = [m for m, p in cands if p and 0.5 * mc <= p * SUPPLY <= 1.5 * mc]
        for m in rng.sample(cands, min(per_trip, len(cands))):
            out.append(Trip("RANDOM", m, t.first_ts, t.first_ts, 0, 0, 0, 0, mc, 0, None, True, False))
    return out
