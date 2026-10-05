"""H-LPHEDGE data fetch (run only after reports/hypotheses/lphedge_preregistration.json exists).

All public, unauthenticated, read-only; no trading. Output under data/raw/web/lphedge/ (< 200 MB).
  1. lp_events_<pool>.json   PumpSwap Deposit/WithdrawEvents of each pool (via the pool's LP-mint signatures on the
                             public Solana RPC). Each logs pool reserves + lp_mint_supply -> liquidity (TVL) history.
  2. fee_history.json        lp/protocol/creator bps of a few swaps near each LP event date (pool signatures paged
                             'before' that event) -> checks the fee schedule did not change over the period.
  3. gt_<pool>_<cur>.json    GeckoTerminal 15-min pool OHLCV (currency usd and token), 2026-04-07 -> now.
  4. lighter_candles_<m>.json  Lighter 15-min perp candles (api/v1/candles), same window.
  5. lighter_funding_<m>.json  Lighter hourly funding (api/v1/fundings), same window.
  6. lighter_spreads.jsonl   Lighter order-book snapshots for PUMP/PENGU/SOL (best bid/ask + $1k round trip).

    python scripts/research/lphedge_fetch.py [--only lp,fees,gt,lighter,spreads]
"""
import argparse
import base64
import datetime as dt
import hashlib
import json
import struct
import sys
import time
from pathlib import Path

import base58
import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pipeline.market import decode_amm  # noqa: E402

OUT = ROOT / "data/raw/web/lphedge"
RPC = "https://api.mainnet-beta.solana.com"
LIGHTER = "https://mainnet.zklighter.elliot.ai/api/v1"
POOLS = {"PUMP_USDC": {"pool": "2uF4Xh61rDwxnG9woyxsVQP7zuA6kLFpb3NvnRQeoiSd",
                       "lp_mint": "2oC6bUcK8A3JMryKBCUA9cwxNqGrkEK3cbebT2hWf2jU"},
         "PENGU_SOL": {"pool": "9qKxzRejsV6Bp2zkefXWCbGvg61c3hHei7ShXJ4FythA",
                       "lp_mint": "EZ6S2q86E6moPYXKraR2SDkU4k9enSwFHjDmGkwePynC"}}
MARKETS = {"PUMP": 45, "PENGU": 47, "SOL": 2}
START = int(dt.datetime(2026, 4, 7, tzinfo=dt.timezone.utc).timestamp())
LP_START = int(dt.datetime(2026, 3, 1, tzinfo=dt.timezone.utc).timestamp())
EVD = {hashlib.sha256(f"event:{n}".encode()).digest()[:8]: n for n in ("DepositEvent", "WithdrawEvent")}


def rpc(cl, method, params):
    for attempt in range(10):
        try:
            r = cl.post(RPC, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
        except httpx.HTTPError:
            time.sleep(5)
            continue
        if r.status_code == 429:
            time.sleep(min(60, 3 * 2 ** attempt))
            continue
        r.raise_for_status()
        j = r.json()
        if "error" in j:
            if j["error"].get("code") in (-32429, 429):
                time.sleep(min(60, 3 * 2 ** attempt))
                continue
            raise RuntimeError(j["error"])
        return j["result"]
    raise RuntimeError("rate limited")


def get_tx(cl, sig):
    return rpc(cl, "getTransaction", [sig, {"encoding": "json", "maxSupportedTransactionVersion": 1}])


def fetch_lp(cl):
    for name, p in POOLS.items():
        sigs, before = [], None
        while True:
            opt = {"limit": 1000} if before is None else {"limit": 1000, "before": before}
            page = rpc(cl, "getSignaturesForAddress", [p["lp_mint"], opt])
            if not page:
                break
            sigs += page
            before = page[-1]["signature"]
            if (page[-1].get("blockTime") or 0) < LP_START:
                break
            time.sleep(0.5)
        sigs = [s for s in sigs if s.get("err") is None and (s.get("blockTime") or 0) >= LP_START]
        evs, n_nolog = [], 0
        for s in sigs:
            tx = get_tx(cl, s["signature"])
            time.sleep(0.35)
            if not tx:
                continue
            logs = tx["meta"].get("logMessages") or []
            if any("Log truncated" in x for x in logs):
                n_nolog += 1
            for line in logs:
                if not line.startswith("Program data: "):
                    continue
                b = base64.b64decode(line[14:])
                kind = EVD.get(b[:8])
                if kind is None or len(b) < 128:
                    continue
                if base58.b58encode(b[96:128]).decode() != p["pool"]:
                    continue
                u = [struct.unpack_from("<Q", b, 8 + 8 * i)[0] for i in range(11)]
                # Deposit: ts, lp_out, max_base, max_quote, user_base, user_quote, pool_base, pool_quote, base_in,
                # quote_in, lp_mint_supply (post?). Withdraw: ts, lp_in, min_base, min_quote, user_base, user_quote,
                # pool_base, pool_quote, base_out, quote_out, lp_mint_supply. Pre/post semantics checked in the sim.
                evs.append({"sig": s["signature"], "slot": tx["slot"], "block_time": s.get("blockTime"), "kind": kind,
                            "ts": u[0], "lp_amount": u[1], "pool_base": u[6], "pool_quote": u[7], "base_amt": u[8],
                            "quote_amt": u[9], "lp_supply": u[10]})
        (OUT / f"lp_events_{name}.json").write_text(json.dumps({"pool": p, "source": RPC, "fetched_at": time.time(),
                                                                "n_sigs": len(sigs), "n_truncated_logs": n_nolog,
                                                                "events": evs}))
        print(name, "lp sigs", len(sigs), "events", len(evs), "truncated", n_nolog, flush=True)


def fetch_fee_history(cl):
    out = {}
    for name, p in POOLS.items():
        evs = json.loads((OUT / f"lp_events_{name}.json").read_text())["events"]
        evs = sorted([e for e in evs if (e["block_time"] or 0) >= START], key=lambda e: e["slot"])
        picks = [evs[int(i * (len(evs) - 1) / 7)] for i in range(8)] if len(evs) >= 8 else evs
        rows = []
        for e in picks:
            page = rpc(cl, "getSignaturesForAddress", [p["pool"], {"limit": 60, "before": e["sig"]}])
            got = 0
            for s in page:
                if s.get("err") is not None or got >= 4:
                    continue
                tx = get_tx(cl, s["signature"])
                time.sleep(0.35)
                for line in (tx or {}).get("meta", {}).get("logMessages") or []:
                    if not line.startswith("Program data: "):
                        continue
                    ev = decode_amm({"data": line[14:]})
                    if ev and ev["e"] == "swap" and ev["pool"] == p["pool"]:
                        rows.append({"near_event_time": e["block_time"], "block_time": s.get("blockTime"),
                                     "lp_bps": ev["lp_bps"], "protocol_bps": ev["protocol_bps"],
                                     "creator_bps": ev["creator_bps"]})
                        got += 1
        out[name] = rows
        print(name, "historic fee samples", len(rows), sorted({(r["lp_bps"], r["protocol_bps"], r["creator_bps"]) for r in rows}),
              flush=True)
    (OUT / "fee_history.json").write_text(json.dumps(out))


def fetch_gt():
    now = int(time.time())
    with httpx.Client(timeout=30, headers={"Accept": "application/json"}) as cl:
        for name, p in POOLS.items():
            for cur in ("usd", "token"):
                rows, before = {}, now
                while before > START:
                    for attempt in range(6):
                        r = cl.get(f"https://api.geckoterminal.com/api/v2/networks/solana/pools/{p['pool']}/ohlcv/minute",
                                   params={"aggregate": 15, "limit": 1000, "currency": cur, "before_timestamp": before})
                        if r.status_code == 429:
                            time.sleep(15 * (attempt + 1))
                            continue
                        break
                    r.raise_for_status()
                    lst = r.json()["data"]["attributes"]["ohlcv_list"]
                    time.sleep(2.2)
                    if not lst:
                        break
                    for row in lst:
                        rows[row[0]] = row
                    before = min(x[0] for x in lst)
                rows = sorted(v for k, v in rows.items() if k >= START)
                (OUT / f"gt_{name}_{cur}.json").write_text(json.dumps({"pool": p["pool"], "currency": cur,
                    "source": "api.geckoterminal.com ohlcv/minute aggregate=15", "fetched_at": time.time(),
                    "cols": "t_start,o,h,l,c,volume", "ohlcv": rows}))
                print(name, cur, len(rows), rows[0][0] if rows else None, rows[-1][0] if rows else None, flush=True)


def fetch_lighter():
    now = int(time.time())
    with httpx.Client(timeout=30, headers={"User-Agent": "Mozilla/5.0"}) as cl:
        for sym, mid in MARKETS.items():
            rows, t0 = {}, START
            while t0 < now:
                t1 = min(t0 + 450 * 900, now)
                r = cl.get(f"{LIGHTER}/candles", params={"market_id": mid, "resolution": "15m", "start_timestamp": t0 * 1000,
                                                          "end_timestamp": t1 * 1000, "count_back": 500})
                if r.status_code == 429:
                    time.sleep(10)
                    continue
                r.raise_for_status()
                for c in r.json().get("c", []):
                    rows[c["t"]] = c
                t0 = t1
                time.sleep(0.3)
            (OUT / f"lighter_candles_{sym}.json").write_text(json.dumps({"market_id": mid, "source": f"{LIGHTER}/candles 15m",
                                                                          "fetched_at": time.time(), "candles": sorted(rows.values(), key=lambda c: c["t"])}))
            fr, t0 = {}, START
            while t0 < now:
                t1 = min(t0 + 500 * 3600, now)
                r = cl.get(f"{LIGHTER}/fundings", params={"market_id": mid, "resolution": "1h", "start_timestamp": t0,
                                                           "end_timestamp": t1, "count_back": 500})
                if r.status_code == 429:
                    time.sleep(10)
                    continue
                r.raise_for_status()
                for f in r.json().get("fundings", []):
                    fr[f["timestamp"]] = f
                t0 = t1
                time.sleep(0.3)
            (OUT / f"lighter_funding_{sym}.json").write_text(json.dumps({"market_id": mid, "source": f"{LIGHTER}/fundings 1h",
                "units": "rate = percent per hour; direction 'long' = longs pay shorts (inferred, as propcarry_sim.py)",
                "fetched_at": time.time(), "fundings": sorted(fr.values(), key=lambda f: f["timestamp"])}))
            print(sym, "candles", len(rows), "fundings", len(fr), flush=True)


def fetch_spreads(rounds=30, interval=20):
    def vwap(levels, usd):
        q = u = 0.0
        for px, sz in levels:
            take = min(sz, (usd - u) / px)
            q += take
            u += take * px
            if u >= usd - 1e-9:
                return u / q
        return None
    with httpx.Client(timeout=20, headers={"User-Agent": "Mozilla/5.0"}) as cl, \
            open(OUT / "lighter_spreads.jsonl", "a") as fh:
        for _ in range(rounds):
            for sym, mid in MARKETS.items():
                try:
                    d = cl.get(f"{LIGHTER}/orderBookOrders", params={"market_id": mid, "limit": 100}).json()
                except Exception as e:  # noqa: BLE001
                    print("spread err", sym, e)
                    continue
                asks = sorted((float(o["price"]), float(o["remaining_base_amount"])) for o in d["asks"])
                bids = sorted(((float(o["price"]), float(o["remaining_base_amount"])) for o in d["bids"]), reverse=True)
                if not asks or not bids:
                    continue
                mid_px = (asks[0][0] + bids[0][0]) / 2
                ba, bb = vwap(asks, 1000.0), vwap(bids, 1000.0)
                fh.write(json.dumps({"coin": sym, "bid": bids[0][0], "ask": asks[0][0],
                                     "quoted_bp": (asks[0][0] - bids[0][0]) / mid_px * 1e4,
                                     "rt1000_bp": (ba - bb) / mid_px * 1e4 if ba and bb else None,
                                     "ts": time.time(), "is_synthetic": False}) + "\n")
            fh.flush()
            time.sleep(interval)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="lp,fees,gt,lighter,spreads")
    a = set(ap.parse_args().only.split(","))
    OUT.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=60) as cl:
        if "lp" in a:
            fetch_lp(cl)
        if "fees" in a:
            fetch_fee_history(cl)
    if "gt" in a:
        fetch_gt()
    if "lighter" in a:
        fetch_lighter()
    if "spreads" in a:
        fetch_spreads()
