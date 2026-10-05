"""H-LPHEDGE-2 step 1: do GeckoTerminal's missing 15-min bars for PumpSwap PUMP/USDC mean zero on-chain volume?

No price outcome is computed. For each train-period LP event of the pool (anchor), the pool's signatures are paged
back (public Solana RPC, getSignaturesForAddress 'before' = anchor; 429 back-off) far enough to cover the two
previous full UTC days. Inside the covered time, each 15m bar is classified GT-present / GT-missing. For GT-missing
bars every successful pool transaction is fetched (getTransaction) and counted as a swap if the pool's base or quote
vault token balance changed (pre/postTokenBalances), which does not depend on log decoding.

    python scripts/research/lphedge2_coverage.py
Output: data/raw/web/lphedge/coverage_check.json
"""
import json
import time
from collections import defaultdict
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data/raw/web/lphedge"
RPC = "https://api.mainnet-beta.solana.com"
POOL = "2uF4Xh61rDwxnG9woyxsVQP7zuA6kLFpb3NvnRQeoiSd"
VAULTS = {"8TqK4PL3x7zWR2dNinr1LMi8Uf4vTRSFE2Ev1yYW9bhC", "68Vdm7mQJ7RBxWioLVEUXbeTTpTtyiR1CL9vLRxmdr8t"}
TRAIN = (1775606400, 1784937600)
MAX_TX = 1500


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


def vault_changed(tx):
    keys = tx["transaction"]["message"]["accountKeys"]
    keys = keys + (tx["meta"].get("loadedAddresses", {}).get("writable", []) +
                   tx["meta"].get("loadedAddresses", {}).get("readonly", []))
    pre = {b["accountIndex"]: b["uiTokenAmount"]["amount"] for b in tx["meta"].get("preTokenBalances") or []}
    post = {b["accountIndex"]: b["uiTokenAmount"]["amount"] for b in tx["meta"].get("postTokenBalances") or []}
    for i, k in enumerate(keys):
        if k in VAULTS and pre.get(i) != post.get(i):
            return True
    return False


def main():
    ev = json.loads((D / "lp_events_PUMP_USDC.json").read_text())["events"]
    anchors = {}
    for e in sorted(ev, key=lambda e: e["block_time"]):
        if TRAIN[0] <= e["block_time"] < TRAIN[1]:
            anchors.setdefault(e["block_time"] // 86400, e)          # first event of each day
    gt = {r[0] for r in json.loads((D / "gt_PUMP_USDC_usd.json").read_text())["ohlcv"]}
    sigs_by_bar = defaultdict(list)
    covered = []
    with httpx.Client(timeout=60) as cl:
        for day, e in sorted(anchors.items()):
            stop = (day - 2) * 86400
            before, lo = e["sig"], e["block_time"]
            while lo > stop:
                page = rpc(cl, "getSignaturesForAddress", [POOL, {"limit": 1000, "before": before}])
                if not page:
                    break
                for s in page:
                    if s.get("blockTime"):
                        sigs_by_bar[s["blockTime"] // 900 * 900].append((s["signature"], s.get("err") is None))
                before, lo = page[-1]["signature"], page[-1]["blockTime"]
                time.sleep(0.4)
            covered.append((max(lo, stop) // 900 * 900 + 900, e["block_time"] // 900 * 900))   # full bars only
            print("anchor", time.strftime("%F %T", time.gmtime(e["block_time"])), "covered from",
                  time.strftime("%F %T", time.gmtime(covered[-1][0])), flush=True)
        bars = sorted({b for a, z in covered for b in range(a, z, 900) if TRAIN[0] <= b < TRAIN[1]})
        missing = [b for b in bars if b not in gt]
        present = [b for b in bars if b in gt]
        res_missing, n_tx = [], 0
        for b in missing:
            ok = [s for s, good in sigs_by_bar.get(b, []) if good]
            swaps = 0
            for s in ok:
                if n_tx >= MAX_TX:
                    break
                tx = rpc(cl, "getTransaction", [s, {"encoding": "json", "maxSupportedTransactionVersion": 1}])
                n_tx += 1
                time.sleep(0.35)
                if tx and vault_changed(tx):
                    swaps += 1
            res_missing.append({"bar": b, "n_sigs": len(sigs_by_bar.get(b, [])), "n_success": len(ok), "n_vault_moves": swaps,
                                "fully_checked": n_tx < MAX_TX})
    full_days = defaultdict(int)
    for b in bars:
        full_days[b // 86400] += 1
    out = {"pool": POOL, "source": RPC, "method": __doc__, "fetched_at": time.time(), "is_synthetic": False,
           "n_anchor_days": len(anchors), "covered_windows": covered, "n_bars_covered": len(bars),
           "n_full_days_covered": sum(1 for v in full_days.values() if v == 96),
           "days_covered_bars": {time.strftime("%F", time.gmtime(d * 86400)): v for d, v in sorted(full_days.items())},
           "n_gt_present": len(present), "n_gt_missing": len(missing),
           "present_bars_with_zero_success_sigs": sum(1 for b in present if not any(g for _, g in sigs_by_bar.get(b, []))),
           "present_bar_success_sigs_median": sorted(sum(g for _, g in sigs_by_bar.get(b, [])) for b in present)[len(present) // 2] if present else None,
           "missing": res_missing, "n_tx_fetched": n_tx,
           "missing_bars_with_any_vault_move": sum(1 for r in res_missing if r["n_vault_moves"] > 0)}
    (D / "coverage_check.json").write_text(json.dumps(out, indent=1))
    print({k: out[k] for k in ("n_bars_covered", "n_full_days_covered", "n_gt_present", "n_gt_missing",
                               "missing_bars_with_any_vault_move", "present_bars_with_zero_success_sigs",
                               "present_bar_success_sigs_median", "n_tx_fetched")})


if __name__ == "__main__":
    main()
