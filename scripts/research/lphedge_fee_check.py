"""H-LPHEDGE step 1: confirm the PumpSwap LP fee rate (fee SCHEDULE only, no outcomes) from decoded swaps.

For each pool: getSignaturesForAddress (public Solana RPC) -> getTransaction for up to N recent successful txs ->
PumpSwap 'Program data:' Buy/SellEvents decoded with pipeline.market.decode_amm. The event carries both the bps
fields and the fee AMOUNTS (u[9] = lp_fee, u[11] = protocol_fee, coin_creator_fee at offset 352), so
lp_fee / quote_amount is an exact check of lp_bps. 429s are respected with back-off.

    python scripts/research/lphedge_fee_check.py
Output: data/raw/web/lphedge/fee_check.json
"""
import base64
import json
import struct
import sys
import time
from collections import Counter
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pipeline.market import decode_amm  # noqa: E402

RPC = "https://api.mainnet-beta.solana.com"
OUT = ROOT / "data/raw/web/lphedge/fee_check.json"
POOLS = {"PUMP/USDC": "2uF4Xh61rDwxnG9woyxsVQP7zuA6kLFpb3NvnRQeoiSd",
         "PENGU/SOL": "9qKxzRejsV6Bp2zkefXWCbGvg61c3hHei7ShXJ4FythA",
         "Fartcoin/SOL": "eUsB7o5HXb4xj3RD4eZjumRV6T65PQELbhd8mNFRjk6"}
N = 60
MAX_SIGS = 3000
MAX_TX = 600


def rpc(cl, method, params):
    for attempt in range(8):
        r = cl.post(RPC, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
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
    raise RuntimeError("429 limit")


def main():
    out = {"source": RPC, "method": __doc__, "fetched_at": time.time(), "pools": {}}
    with httpx.Client(timeout=30) as cl:
        for name, pool in POOLS.items():
            sigs, before = [], None
            while len(sigs) < MAX_SIGS:                  # paginate back until enough successful txs are listed
                opt = {"limit": 1000} if before is None else {"limit": 1000, "before": before}
                page = rpc(cl, "getSignaturesForAddress", [pool, opt])
                if not page:
                    break
                before = page[-1]["signature"]
                sigs += [s for s in page if s.get("err") is None]
            rows, n_tx = [], 0
            for s in sigs:
                if len(rows) >= N or n_tx >= MAX_TX:
                    break
                n_tx += 1
                tx = rpc(cl, "getTransaction", [s["signature"], {"encoding": "json", "maxSupportedTransactionVersion": 1,
                                                                 "commitment": "confirmed"}])
                time.sleep(0.4)
                if not tx:
                    continue
                for line in tx["meta"].get("logMessages") or []:
                    if not line.startswith("Program data: "):
                        continue
                    data = line[len("Program data: "):]
                    ev = decode_amm({"data": data})
                    if not ev or ev["e"] != "swap" or ev["pool"] != pool:
                        continue
                    b = base64.b64decode(data)
                    u = [struct.unpack_from("<Q", b, 8 + 8 * i)[0] for i in range(14)]
                    ccfee = struct.unpack_from("<Q", b, 352)[0] if len(b) >= 360 else None
                    q = ev["quote"]
                    rows.append({"sig": s["signature"], "slot": tx["slot"], "buy": ev["buy"], "ev_len": len(b),
                                 "quote": q, "user_quote": ev["user_quote"], "lp_bps": ev["lp_bps"],
                                 "protocol_bps": ev["protocol_bps"], "creator_bps": ev["creator_bps"],
                                 "lp_fee": u[9], "protocol_fee": u[11], "creator_fee": ccfee,
                                 "lp_fee_over_quote_bps": (u[9] / q * 1e4) if q else None})
            tiers = Counter((r["lp_bps"], r["protocol_bps"], r["creator_bps"]) for r in rows)
            implied = [r["lp_fee_over_quote_bps"] for r in rows if r["lp_fee_over_quote_bps"] is not None and r["quote"] > 10 ** 4]
            out["pools"][name] = {"pool": pool, "n_swaps": len(rows), "n_tx_fetched": n_tx,
                                  "tiers_lp_proto_creator_bps": {str(k): v for k, v in tiers.items()},
                                  "implied_lp_bps_min": min(implied) if implied else None,
                                  "implied_lp_bps_max": max(implied) if implied else None,
                                  "slot_range": [min(r["slot"] for r in rows), max(r["slot"] for r in rows)] if rows else None,
                                  "rows": rows}
            print(name, len(rows), dict(tiers), out["pools"][name]["implied_lp_bps_min"],
                  out["pools"][name]["implied_lp_bps_max"], flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
