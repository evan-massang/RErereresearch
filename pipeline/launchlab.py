"""Decode Raydium LaunchLab events (IDL: sources/raydium_launchpad_idl.json) and load them into market.duckdb.

TradeEvent: pool_state, total_base_sell, virtual_base, virtual_quote, real_base_before, real_quote_before,
real_base_after, real_quote_after, amount_in, amount_out, protocol_fee, platform_fee, creator_fee, share_fee
(all u64), trade_direction (0 buy / 1 sell), pool_status (0 Fund / 1 Migrate / 2 Trade), exact_in.
PoolCreateEvent: pool_state, creator, config, then MintParams (decimals, name, symbol, uri), ...

Price (quote per base, raw units) on the constant-product curve:
  (virtual_quote + real_quote) / (virtual_base - real_base)
Logs do not name the trader or the base mint; pools are identified by pool_state.
"""
from __future__ import annotations

import base64
import struct

import base58
import duckdb

from pipeline import config
from pipeline.market import _complete, _read_file

TRADE = bytes([189, 219, 127, 211, 78, 230, 97, 238])
CREATE = bytes([151, 215, 226, 9, 118, 161, 115, 174])


def _str(b: bytes, o: int) -> tuple[str, int]:
    n = struct.unpack_from("<I", b, o)[0]
    return b[o + 4:o + 4 + n].decode("utf-8", "replace"), o + 4 + n


def decode(data: str) -> dict | None:
    b = base64.b64decode(data)
    if b[:8] == TRADE and len(b) >= 8 + 32 + 13 * 8 + 3:
        pool = base58.b58encode(b[8:40]).decode()
        v = struct.unpack_from("<13Q", b, 40)
        o = 40 + 13 * 8
        return {"e": "trade", "pool": pool, "total_base_sell": v[0], "virtual_base": v[1], "virtual_quote": v[2],
                "real_base_before": v[3], "real_quote_before": v[4], "real_base_after": v[5], "real_quote_after": v[6],
                "amount_in": v[7], "amount_out": v[8], "protocol_fee": v[9], "platform_fee": v[10], "creator_fee": v[11],
                "share_fee": v[12], "buy": b[o] == 0, "status": b[o + 1], "exact_in": bool(b[o + 2])}
    if b[:8] == CREATE:
        pool = base58.b58encode(b[8:40]).decode()
        creator = base58.b58encode(b[40:72]).decode()
        cfg = base58.b58encode(b[72:104]).decode()
        o = 104
        dec = b[o]
        name, o = _str(b, o + 1)
        sym, o = _str(b, o)
        uri, o = _str(b, o)
        return {"e": "create", "pool": pool, "creator": creator, "config": cfg, "decimals": dec, "name": name,
                "symbol": sym, "uri": uri}
    return None


def load(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    import pandas as pd

    con.execute("""CREATE TABLE IF NOT EXISTS lab_pools (src_file VARCHAR, sig VARCHAR, recv DOUBLE, slot BIGINT, pool VARCHAR,
                   creator VARCHAR, config VARCHAR, decimals INTEGER, name VARCHAR, symbol VARCHAR, uri VARCHAR);
                   CREATE TABLE IF NOT EXISTS lab_trades (src_file VARCHAR, sig VARCHAR, recv DOUBLE, slot BIGINT, pool VARCHAR,
                   buy BOOLEAN, status INTEGER, amount_in UBIGINT, amount_out UBIGINT, virtual_base UBIGINT,
                   virtual_quote UBIGINT, real_base_after UBIGINT, real_quote_after UBIGINT, total_base_sell UBIGINT,
                   fees UBIGINT);
                   CREATE TABLE IF NOT EXISTS loaded_lab_files (name VARCHAR PRIMARY KEY, complete BOOLEAN);""")
    done = {r[0] for r in con.execute("SELECT name FROM loaded_lab_files WHERE complete").fetchall()}
    added = {"pools": 0, "trades": 0}
    for f in sorted(config.path("raw_streams", "launchlab_raw").glob("*.jsonl.gz"), key=lambda x: x.stat().st_mtime):
        if f.name in done:
            continue
        complete = _complete(f)
        for t in ("lab_pools", "lab_trades"):
            con.execute(f"DELETE FROM {t} WHERE src_file = ?", [f.name])
        pr, tr = [], []
        for r in _read_file(f):
            if not r.get("data"):
                continue
            try:
                ev = decode(r["data"])
            except (struct.error, ValueError, IndexError):
                continue
            if ev is None:
                continue
            if ev["e"] == "trade":
                tr.append((f.name, r["sig"], r["recv"], r.get("slot"), ev["pool"], ev["buy"], ev["status"], ev["amount_in"],
                           ev["amount_out"], ev["virtual_base"], ev["virtual_quote"], ev["real_base_after"],
                           ev["real_quote_after"], ev["total_base_sell"],
                           ev["protocol_fee"] + ev["platform_fee"] + ev["creator_fee"] + ev["share_fee"]))
            else:
                pr.append((f.name, r["sig"], r["recv"], r.get("slot"), ev["pool"], ev["creator"], ev["config"],
                           ev["decimals"], ev["name"], ev["symbol"], ev["uri"]))
        if pr:
            con.register("pr_df", pd.DataFrame(pr, columns=["src_file", "sig", "recv", "slot", "pool", "creator", "config",
                                                          "decimals", "name", "symbol", "uri"]))
            con.execute("INSERT INTO lab_pools SELECT * FROM pr_df")
            con.unregister("pr_df")
        if tr:
            con.register("tr_df", pd.DataFrame(tr, columns=["src_file", "sig", "recv", "slot", "pool", "buy", "status",
                                                          "amount_in", "amount_out", "virtual_base", "virtual_quote",
                                                          "real_base_after", "real_quote_after", "total_base_sell", "fees"]))
            con.execute("INSERT INTO lab_trades SELECT * FROM tr_df")
            con.unregister("tr_df")
        added["pools"] += len(pr)
        added["trades"] += len(tr)
        con.execute("INSERT OR REPLACE INTO loaded_lab_files VALUES (?, ?)", [f.name, complete])
    return added
