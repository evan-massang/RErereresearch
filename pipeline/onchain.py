"""On-chain wallet activity from a Solana JSON-RPC endpoint.

Swaps are decoded venue-agnostically from the wallet's own balance changes in
each successful transaction: the change in its token balance per mint against
the change in its SOL (+ wrapped SOL) balance, with the network fee added back.

Known distortions (documented, not hidden): Jito tips and other SOL transfers
inside the same transaction, and token-account rent (~0.002 SOL, refunded on
close), are counted in sol_amount. Transactions touching several non-SOL mints
are stored with sol_amount = NULL because the SOL leg cannot be attributed.

Set SOLANA_RPC_URL to use a private endpoint; the public one is rate-limited.
"""

from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

import duckdb
import httpx

from . import db
from .provenance import SourceUnavailable, tracked

PUBLIC_RPC = "https://api.mainnet-beta.solana.com"
WSOL = "So11111111111111111111111111111111111111112"
KNOWN_PROGRAMS = {
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P": "pump_bonding_curve",
    "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA": "pumpswap",
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4": "jupiter",
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "raydium_amm",
    "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C": "raydium_cpmm",
    "LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj": "raydium_launchlab",
    "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo": "meteora_dlmm",
    "cbe2hXc6bFBb1HoR3q5LsfnE8NM9Qht2Hqq3BYKaH9i": "meteora_dbc",
}


class Rpc:
    """Minimal JSON-RPC client with retry/backoff and a global request pace."""

    def __init__(self, url: str | None = None, rps: float = 6.0, timeout: float = 30.0):
        self.url = url or os.environ.get("SOLANA_RPC_URL") or PUBLIC_RPC
        self._gap = 1.0 / rps
        self._lock = threading.Lock()
        self._next = 0.0
        verify = os.environ.get("SSL_CERT_FILE") or True
        self._client = httpx.Client(timeout=timeout, verify=verify, headers={"content-type": "application/json"})

    def _pace(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait = self._next - now
            self._next = max(now, self._next) + self._gap
        if wait > 0:
            time.sleep(wait)

    def call(self, method: str, params: list, retries: int = 8) -> Any:
        delay = 1.0
        for attempt in range(retries):
            self._pace()
            try:
                r = self._client.post(self.url, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
            except httpx.HTTPError as e:
                if attempt == retries - 1:
                    raise SourceUnavailable(f"RPC {method}: {e}") from e
                time.sleep(delay)
                delay = min(delay * 2, 30)
                continue
            if r.status_code in (429, 502, 503, 504):
                time.sleep(delay)
                delay = min(delay * 2, 30)
                continue
            if r.status_code != 200:
                raise SourceUnavailable(f"RPC {method}: HTTP {r.status_code} {r.text[:200]}")
            body = r.json()
            if "error" in body:
                err = body["error"]
                if err.get("code") in (-32429, 429, -32005):
                    time.sleep(delay)
                    delay = min(delay * 2, 30)
                    continue
                raise SourceUnavailable(f"RPC {method}: {err}", status="error")
            return body["result"]
        raise SourceUnavailable(f"RPC {method}: rate-limited after {retries} attempts", status="blocked")


def _ts(block_time: int | None) -> datetime | None:
    return datetime.fromtimestamp(block_time, timezone.utc) if block_time else None


def fetch_signatures(rpc: Rpc, wallet: str, *, limit: int, before: str | None = None,
                     until: str | None = None) -> list[dict]:
    out: list[dict] = []
    cursor = before
    while len(out) < limit:
        opts: dict[str, Any] = {"limit": min(1000, limit - len(out))}
        if cursor:
            opts["before"] = cursor
        if until:
            opts["until"] = until
        page = rpc.call("getSignaturesForAddress", [wallet, opts])
        if not page:
            break
        out.extend(page)
        cursor = page[-1]["signature"]
        if len(page) < opts["limit"]:
            break
    return out


def _amount(tb: dict) -> float:
    ui = tb.get("uiTokenAmount") or {}
    s = ui.get("uiAmountString")
    return float(s) if s not in (None, "") else float(ui.get("uiAmount") or 0.0)


def decode_swaps(tx: dict, wallet: str) -> list[dict]:
    """Swaps made by ``wallet`` in one parsed transaction (pure function)."""
    meta = tx.get("meta") or {}
    if meta.get("err") is not None:
        return []
    keys = [k["pubkey"] if isinstance(k, dict) else k for k in tx["transaction"]["message"]["accountKeys"]]
    if wallet not in keys:
        return []
    i = keys.index(wallet)
    fee = (meta.get("fee") or 0) / 1e9
    payer_is_wallet = i == 0
    sol_delta = (meta["postBalances"][i] - meta["preBalances"][i]) / 1e9
    if payer_is_wallet:
        sol_delta += fee                                  # the fee is not part of the trade
    deltas: dict[str, float] = {}
    for tb in meta.get("preTokenBalances") or []:
        if tb.get("owner") == wallet:
            deltas[tb["mint"]] = deltas.get(tb["mint"], 0.0) - _amount(tb)
    for tb in meta.get("postTokenBalances") or []:
        if tb.get("owner") == wallet:
            deltas[tb["mint"]] = deltas.get(tb["mint"], 0.0) + _amount(tb)
    sol_delta += deltas.pop(WSOL, 0.0)
    changed = {m: d for m, d in deltas.items() if abs(d) > 1e-12}
    if not changed:
        return []
    programs = []
    for ins in tx["transaction"]["message"].get("instructions", []):
        pid = ins.get("programId")
        if pid and pid not in programs:
            programs.append(pid)
    single = len(changed) == 1
    out = []
    for mint, d in changed.items():
        side = "buy" if d > 0 else "sell"
        sol_amt = None
        if single and ((side == "buy" and sol_delta < 0) or (side == "sell" and sol_delta > 0)):
            sol_amt = abs(sol_delta)
        out.append({
            "mint": mint, "side": side, "token_amount": abs(d), "sol_amount": sol_amt,
            "fee_sol": fee if payer_is_wallet else 0.0,
            "price_sol": (sol_amt / abs(d)) if sol_amt else None,
            "programs": [KNOWN_PROGRAMS.get(p, p) for p in programs],
        })
    return out


def sync_wallet(con: duckdb.DuckDBPyConnection, wallet: str, *, limit: int = 2000, workers: int = 4,
                rpc: Rpc | None = None, progress: bool = False) -> dict[str, int]:
    """Fetch the newest ``limit`` signatures of a wallet and decode swaps from the successful ones."""
    rpc = rpc or Rpc()
    with tracked(con, stage="wallet_sync", adapter="solana_rpc", uri=wallet) as ev:
        sigs = fetch_signatures(rpc, wallet, limit=limit)
        now = db.now()
        db.insert_many(con, "wallet_signatures", [
            {"wallet": wallet, "signature": s["signature"], "slot": s.get("slot"), "block_time": _ts(s.get("blockTime")),
             "failed": s.get("err") is not None, "fetched_at": now} for s in sigs])
        known = {r[0] for r in con.execute("SELECT DISTINCT signature FROM wallet_swaps WHERE wallet = ?",
                                           [wallet]).fetchall()}
        todo = [s for s in sigs if s.get("err") is None and s["signature"] not in known]

        def get(sig: dict) -> tuple[dict, dict | None]:
            try:
                return sig, rpc.call("getTransaction", [sig["signature"], {
                    "encoding": "jsonParsed", "maxSupportedTransactionVersion": 0, "commitment": "finalized"}])
            except SourceUnavailable:
                return sig, None

        rows, missing, done = [], 0, 0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for sig, tx in pool.map(get, todo):
                done += 1
                if progress and done % 200 == 0:
                    print(f"  {wallet[:6]}: {done}/{len(todo)} transactions", flush=True)
                if tx is None:
                    missing += 1
                    continue
                for sw in decode_swaps(tx, wallet):
                    rows.append({"wallet": wallet, "signature": sig["signature"], "slot": tx.get("slot"),
                                 "block_time": _ts(tx.get("blockTime")), "fetched_at": db.now(), **sw})
                if len(rows) >= 500:
                    db.insert_many(con, "wallet_swaps", rows)
                    rows = []
        db.insert_many(con, "wallet_swaps", rows)
        stats = {"signatures": len(sigs), "failed_tx": sum(1 for s in sigs if s.get("err") is not None),
                 "fetched": len(todo) - missing, "unfetched": missing,
                 "swaps_total": con.execute("SELECT count(*) FROM wallet_swaps WHERE wallet = ?", [wallet]).fetchone()[0]}
        ev.details = stats
    return stats
