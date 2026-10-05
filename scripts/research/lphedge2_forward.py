"""H-LPHEDGE-2 forward paper scorer on public data (no trading, no keys, independent of our recorders).

    python scripts/research/lphedge2_forward.py freeze     # once; refuses to overwrite reports/paper/lphedge2.json
    python scripts/research/lphedge2_forward.py score      # re-runnable; rewrites reports/paper/lphedge2_ledger.json

`score` scores every complete UTC pool-day whose 00:00 is after `frozen_at`. It uses the same public sources as the
validation run, fetched fresh into data/raw/web/lphedge/forward/:
  * GeckoTerminal 15m pool OHLCV (usd + token) for PumpSwap PUMP/USDC;
  * Lighter 15m candles + 1h funding for PUMP (hedge) and SOL (gas pricing);
  * PumpSwap Deposit/WithdrawEvents via the LP mint's signatures (public Solana RPC), merged with the historical
    events file, for the pool-liquidity (TVL) reconstruction.
The P&L engine is lphedge2_sim.run (frozen; sha256 checked against the freeze file) with the half spread frozen at
freeze time. Column `frozen` is the rule exactly as validated. Column `with_topups` (INFORMATIONAL, not the bar) moves
capital honestly: at each 00:00 UTC the short's collateral is brought back to 1x its notional by withdrawing that
amount from the LP (balanced withdraw, no swap) or depositing any excess back, so the LP shrinks when the short loses.
Optional cross-check: if the lean pumplean recorder has amm_bars for the pool on a scored day, the exact per-LP fee
growth from logged reserves is compared with the modelled fee yield (read-only).
"""
import hashlib
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/research"))
import lphedge_sim as s1  # noqa: E402

FREEZE = ROOT / "reports/paper/lphedge2.json"
LEDGER = ROOT / "reports/paper/lphedge2_ledger.json"
FWD = ROOT / "data/raw/web/lphedge/forward"
HIST = ROOT / "data/raw/web/lphedge"
POOL = "2uF4Xh61rDwxnG9woyxsVQP7zuA6kLFpb3NvnRQeoiSd"
LP_MINT = "2oC6bUcK8A3JMryKBCUA9cwxNqGrkEK3cbebT2hWf2jU"
RPC = "https://api.mainnet-beta.solana.com"
LIGHTER = "https://mainnet.zklighter.elliot.ai/api/v1"
HASHED = ["scripts/research/lphedge_sim.py", "scripts/research/lphedge2_sim.py"]
DAY = 86400


def sha(p):
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def utc(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------------------------------------ freeze
def freeze():
    if FREEZE.exists():
        sys.exit(f"{FREEZE} exists; freeze is one-shot")
    pre = json.loads((ROOT / "reports/hypotheses/lphedge2_preregistration.json").read_text())
    val = json.loads((ROOT / "research/observations/evidence_lphedge2_validation.json").read_text())
    now = int(time.time())
    first_day = (now // DAY + 1) * DAY
    hs = val["half_spreads"]
    out = {
        "hypothesis": "H-LPHEDGE-2", "status": "frozen forward paper rule (no trading)",
        "frozen_at": utc(now), "frozen_at_unix": now, "first_scorable_day": utc(first_day)[:10],
        "scoring": "every complete UTC pool-day whose 00:00 is after frozen_at; position opened at the first scored "
                   "day's 00:00 with $5,000 of liquidity and held (setup cost charged once)",
        "rule": {"pool": "PumpSwap PUMP/USDC " + POOL, "hedge": "Lighter PUMP (market 45) short = LP token units",
                 "band_b": 0.05, "check_interval": "1h UTC-aligned", "size_usd": 5000, "lp_fee_bps": 25,
                 "fee_model": "GeckoTerminal 15m USD volume x 25 bp x L_ours/(L_pool+L_ours); pool liquidity from "
                              "Deposit/WithdrawEvents", "coverage_rule": pre["coverage_rule"],
                 "margin_model": pre["costs"]["margin_model"],
                 "costs": {k: v for k, v in pre["costs"].items() if k != "margin_model"},
                 "half_spread_bp_frozen": {k: v["half_bp"] for k, v in hs.items()},
                 "pre_registration": "reports/hypotheses/lphedge2_preregistration.json",
                 "validation_evidence": "research/observations/evidence_lphedge2_validation.json"},
        "code_sha256": {p: sha(p) for p in HASHED},
        "bar": {"n_pool_days_min": 50, "net_usd_gt": 0, "profit_factor_gt": 1.2, "net_excluding_top3_days_gt": 0,
                "note": "verdict only once n >= 50 scored pool-days; before that the ledger is 'accumulating'"},
        "caveats": [
            "Capital top-ups: in validation PUMP rose ~3.4x and the 1x short needed ~$4.6k of collateral top-ups "
            "financed by removing LP value; the frozen rule ignores the LP shrinkage. The ledger's 'with_topups' column "
            "models it (informational, not the bar).",
            "Volume dependence: the edge is LP fee share minus LVR; it passed validation at volume/TVL ~0.30/day but "
            "the same rule made only +$52 (PF 1.17, fails) on train at ~0.12/day.",
            "Fee model checked against exact on-chain fee growth only over 1.5 h (ratio 1.03).",
            "Not modelled: hedge impact beyond $1k book depth, fee compounding, Lighter venue risk; funding sign "
            "convention inferred from Lighter docs."],
        "validation_result": {k: val["result"][k] for k in ("n_pool_days", "net_usd", "pf", "net_ex_top3_usd",
                                                             "mean_bp_per_day")},
        "how_to_score": "python scripts/research/lphedge2_forward.py score",
    }
    FREEZE.parent.mkdir(parents=True, exist_ok=True)
    FREEZE.write_text(json.dumps(out, indent=1))
    print("frozen", out["frozen_at"], "first scorable day", out["first_scorable_day"])


# ------------------------------------------------------------------------------------------------ fetch
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


def fetch(t_from, t_to):
    import base58  # noqa: F401  (imported by lphedge_fetch too; keeps the dependency explicit)
    sys.path.insert(0, str(ROOT / "scripts/research"))
    import lphedge_fetch as lf
    FWD.mkdir(parents=True, exist_ok=True)
    # GeckoTerminal
    with httpx.Client(timeout=30, headers={"Accept": "application/json"}) as cl:
        for cur in ("usd", "token"):
            rows, before = {}, t_to + 900
            while before > t_from:
                for attempt in range(6):
                    r = cl.get(f"https://api.geckoterminal.com/api/v2/networks/solana/pools/{POOL}/ohlcv/minute",
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
            (FWD / f"gt_PUMP_USDC_{cur}.json").write_text(json.dumps({"pool": POOL, "currency": cur, "fetched_at": time.time(),
                                                                       "ohlcv": sorted(v for k, v in rows.items() if k >= t_from)}))
    # Lighter
    with httpx.Client(timeout=30, headers={"User-Agent": "Mozilla/5.0"}) as cl:
        for sym, mid in (("PUMP", 45), ("SOL", 2)):
            rows, t0 = {}, t_from
            while t0 < t_to:
                t1 = min(t0 + 450 * 900, t_to)
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
            (FWD / f"lighter_candles_{sym}.json").write_text(json.dumps({"market_id": mid, "fetched_at": time.time(),
                                                                          "candles": sorted(rows.values(), key=lambda c: c["t"])}))
            fr, t0 = {}, t_from
            while t0 < t_to:
                t1 = min(t0 + 500 * 3600, t_to)
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
            (FWD / f"lighter_funding_{sym}.json").write_text(json.dumps({"market_id": mid, "fetched_at": time.time(),
                                                                          "fundings": sorted(fr.values(), key=lambda f: f["timestamp"])}))
    # LP events: new LP-mint signatures back to t_from - 1 day, merged with the historical file
    hist = json.loads((HIST / "lp_events_PUMP_USDC.json").read_text())["events"]
    have = {e["sig"] for e in hist}
    new = []
    with httpx.Client(timeout=60) as cl:
        sigs, before = [], None
        while True:
            opt = {"limit": 1000} if before is None else {"limit": 1000, "before": before}
            page = rpc(cl, "getSignaturesForAddress", [LP_MINT, opt])
            if not page:
                break
            sigs += page
            before = page[-1]["signature"]
            if (page[-1].get("blockTime") or 0) < t_from - DAY or any(s["signature"] in have for s in page):
                break
        for s in sigs:
            if s.get("err") is not None or s["signature"] in have:
                continue
            tx = rpc(cl, "getTransaction", [s["signature"], {"encoding": "json", "maxSupportedTransactionVersion": 1}])
            time.sleep(0.35)
            for line in (tx or {}).get("meta", {}).get("logMessages") or []:
                if not line.startswith("Program data: "):
                    continue
                import base64
                import struct
                b = base64.b64decode(line[14:])
                kind = lf.EVD.get(b[:8])
                if kind is None or len(b) < 128 or base58_pk(b, 96) != POOL:
                    continue
                u = [struct.unpack_from("<Q", b, 8 + 8 * i)[0] for i in range(11)]
                new.append({"sig": s["signature"], "slot": tx["slot"], "block_time": s.get("blockTime"), "kind": kind,
                            "ts": u[0], "lp_amount": u[1], "pool_base": u[6], "pool_quote": u[7], "base_amt": u[8],
                            "quote_amt": u[9], "lp_supply": u[10]})
    (FWD / "lp_events_PUMP_USDC.json").write_text(json.dumps({"pool": {"pool": POOL, "lp_mint": LP_MINT},
                                                               "fetched_at": time.time(), "n_new": len(new),
                                                               "events": hist + new}))
    return len(new)


def base58_pk(b, o):
    import base58
    return base58.b58encode(b[o:o + 32]).decode()


# ------------------------------------------------------------------------------------------------ engine
def run_topups(t0, t1, hs, topup):
    """Mirror of lphedge2_sim.run for P1 (same rule, same margin model) with optional honest capital top-ups."""
    import lphedge2_sim as s2
    grid, P, vol, have_pool, perp, have_perp, fund = s1.series("P1", t0, t1)
    hi = s2.candles_high()
    Lfn, _, _ = s1.liquidity_fn("P1")
    pp = perp["PUMP"]
    Lo = s1.SIZE / (2 * math.sqrt(P[0]))
    x = lambda k: Lo / math.sqrt(P[k])
    h = x(0)
    c = hs["PUMP"]["half_bp"] / 1e4
    impact = (s1.SIZE / 2) / (Lfn(grid[0]) * math.sqrt(P[0]))
    setup = 2 * (s1.SIZE / 2) * (s1.POOL_FEE_TOTAL_BPS / 1e4 + impact) + 2 * h * pp[0] * c
    equity = h * pp[0]                       # perp account equity (starts at 1x collateral)
    step = s2.IV // s1.BAR
    days, d = [], None
    moved = 0.0
    for k in range(len(grid) - 1):
        t = grid[k]
        if (t - t0) % DAY == 0:
            if d is not None:
                days.append(d)
            transfer = swap_cost = 0.0
            if topup and k > 0:
                need = h * pp[k] - equity      # >0: collateral short of 1x -> withdraw from LP; <0: excess -> deposit
                V = 2 * Lo * math.sqrt(P[k])
                transfer = max(-equity, min(need, V * 0.95))
                Lo *= (V - transfer) / V
                equity += transfer
                moved += abs(transfer)
                # a balanced withdraw gives half in PUMP, which must be sold for USDC collateral (and an excess
                # deposited back needs the token half bought): pool fee 30 bp on half the transfer
                swap_cost = 0.5 * abs(transfer) * s1.POOL_FEE_TOTAL_BPS / 1e4
            else:
                equity = h * pp[k]             # frozen rule: collateral reset to 1x, capital source not modelled
            d = {"day": datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d"), "lp": 0.0, "fee": 0.0,
                 "hedge": 0.0, "lvr_hedge_pool": 0.0, "funding": 0.0, "hcost": 0.0, "liq_loss": 0.0,
                 "gas": s1.TX_PER_DAY * s1.GAS_SOL_PER_TX * perp["SOL"][k], "n_trades": 0, "bars_pool": 0,
                 "bars_perp": 0, "v_start": 2 * Lo * math.sqrt(P[k]), "tvl_start": 2 * Lfn(t) * math.sqrt(P[k]),
                 "vol_usd": 0.0, "transfer_to_perp": transfer, "transfer_swap_cost": swap_cost,
                 "_C": equity, "_hp": 0.0}
        if k % step == 0 and (h == 0.0 or abs(x(k) - h) > s2.B * x(k)):
            cost = abs(x(k) - h) * pp[k] * c
            d["hcost"] += cost
            equity -= cost
            h = x(k)
            d["n_trades"] += 1
        bs = grid[k + 1] - s1.BAR
        if h > 0 and bs in hi:
            H = hi[bs]
            if d["_C"] + d["_hp"] - h * (H - pp[k]) < s2.MMF * h * H:
                d["liq_loss"] += d["_C"] + d["_hp"]
                equity -= d["_C"] + d["_hp"]
                d["_hp"] = -d["_C"]
                h = 0.0
        d["lp"] += 2 * Lo * (math.sqrt(P[k + 1]) - math.sqrt(P[k]))
        d["fee"] += vol[k + 1] * s1.LP_BPS / 1e4 * Lo / (Lfn(grid[k + 1] - s1.BAR / 2) + Lo)
        d["vol_usd"] += vol[k + 1]
        hp = -h * (pp[k + 1] - pp[k])
        d["hedge"] += hp
        d["_hp"] += hp
        equity += hp
        d["lvr_hedge_pool"] += -h * (P[k + 1] - P[k])
        tn = grid[k + 1]
        if tn % 3600 == 0 and h and tn in fund["PUMP"]:
            f = fund["PUMP"][tn] * h * pp[k + 1]
            d["funding"] += f
            equity += f
        d["bars_pool"] += have_pool[k + 1]
        d["bars_perp"] += have_perp["PUMP"][k + 1]
    if d is not None:
        days.append(d)
    pre = json.loads((ROOT / "reports/hypotheses/lphedge2_preregistration.json").read_text())["coverage_rule"]
    for d in days:
        d.pop("_C"); d.pop("_hp")
        d["lvr"] = d["lp"] + d.pop("lvr_hedge_pool")
        d["basis"] = d["hedge"] - (d["lvr"] - d["lp"])
        d["pnl"] = (d["lp"] + d["fee"] + d["hedge"] + d["funding"] - d["hcost"] - d["gas"] - d["liq_loss"]
                    - d["transfer_swap_cost"])
        d["pnl_bp"] = d["pnl"] / d["v_start"] * 1e4
        d["scored"] = d["bars_perp"] >= pre["min_perp_bars"] and d["bars_pool"] >= pre["min_pool_bars"]
    return days, setup, moved


def summary(days, setup):
    sc = [d for d in days if d["scored"]]
    pn = [d["pnl"] for d in sc]
    gp, gl = sum(v for v in pn if v > 0), -sum(v for v in pn if v < 0)
    net = sum(pn) - setup
    s = {"n_pool_days": len(sc), "unscored_days": [d["day"] for d in days if not d["scored"]],
         "net_usd": round(net, 2), "setup_usd": round(setup, 2), "pf": round(gp / gl, 3) if gl else None,
         "net_ex_top3_usd": round(net - sum(sorted(pn, reverse=True)[:3]), 2),
         "mean_bp_per_day": round(float(np.mean([d["pnl_bp"] for d in sc])), 3) if sc else None,
         "components_usd": {k: round(sum(d[k] for d in sc), 2) for k in
                            ("fee", "funding", "lvr", "basis", "hcost", "gas", "liq_loss",
                                                       "transfer_swap_cost")}}
    s["bar_met"] = bool(s["n_pool_days"] >= 50 and net > 0 and (s["pf"] or 0) > 1.2 and s["net_ex_top3_usd"] > 0)
    s["verdict"] = ("accumulating (n < 50)" if s["n_pool_days"] < 50 else ("PASS" if s["bar_met"] else "FAIL"))
    return s


def pumplean_xcheck(days):
    """Exact per-LP fee growth (sqrt(k)/lp_supply over the day's logged reserves) vs modelled fee yield. Read-only."""
    d0 = ROOT / "data/raw/web/pumplean"
    if not any(d0.glob("**/amm_bars_*.parquet")):
        return {"available": False}
    import duckdb
    rows = duckdb.sql(f"""SELECT recv_us // 1000000 AS t, open_pool_base ob, open_pool_quote oq, last_pool_base lb,
                          last_pool_quote lq, first_slot FROM read_parquet('{d0}/**/amm_bars_*.parquet', union_by_name=true)
                          WHERE pool = '{POOL}' ORDER BY first_slot""").fetchall()
    ev = sorted(json.loads((FWD / "lp_events_PUMP_USDC.json").read_text())["events"], key=lambda e: e["ts"])
    out = []
    for d in days:
        t0 = int(datetime.strptime(d["day"], "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
        r = [x for x in rows if t0 <= x[0] < t0 + DAY]
        if len(r) < 200:                       # need most of the day's 288 five-minute buckets
            continue
        if any(t0 <= e["ts"] < t0 + DAY for e in ev):
            continue                           # LP event inside the day: reserves jump; skip (rare)
        g = math.sqrt(r[-1][3] * r[-1][4]) / math.sqrt(r[0][1] * r[0][2]) - 1
        # modelled growth of sqrt(k) per unit liquidity = sum(fee_i)/(TVL_i) ~= fee_usd/ our share / TVL
        share = s1.SIZE / (d["tvl_start"] + s1.SIZE)
        model = d["fee"] / max(share, 1e-12) / d["tvl_start"]
        out.append({"day": d["day"], "n_bars": len(r), "exact_growth_bp": g * 1e4, "model_growth_bp": model * 1e4,
                    "ratio_model_over_exact": model / g if g else None})
    return {"available": True, "days": out}


def score():
    fz = json.loads(FREEZE.read_text())
    drift = {p: sha(p) for p in HASHED if sha(p) != fz["code_sha256"][p]}
    if drift:
        sys.exit(f"frozen code changed since freeze: {sorted(drift)}; score refused")
    first = int(datetime.strptime(fz["first_scorable_day"], "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
    now = int(time.time())
    last_end = (now - 3600) // DAY * DAY            # last complete UTC day, 1 h settle margin for data lags
    out = {"hypothesis": "H-LPHEDGE-2", "freeze": str(FREEZE.relative_to(ROOT)), "scored_at": utc(now),
           "first_scorable_day": fz["first_scorable_day"], "is_synthetic": False}
    if last_end <= first:
        out.update({"n_pool_days": 0, "verdict": "accumulating (no complete day after the freeze yet)",
                    "next_scorable_after": utc(first + DAY + 3600)})
        LEDGER.write_text(json.dumps(out, indent=1))
        print(json.dumps(out, indent=1))
        return
    n_new = fetch(first - DAY, last_end + 900)
    s1.D = FWD                                       # point the frozen loaders at the forward files
    hs = {k: {"half_bp": v} for k, v in fz["rule"]["half_spread_bp_frozen"].items()}
    days_f, setup_f, _ = run_topups(first, last_end, hs, topup=False)
    days_t, setup_t, moved = run_topups(first, last_end, hs, topup=True)
    out.update({"window": [utc(first), utc(last_end)], "new_lp_events_fetched": n_new,
                "frozen": summary(days_f, setup_f),
                "with_topups_INFORMATIONAL": {**summary(days_t, setup_t), "capital_moved_usd": round(moved, 2)},
                "daily_frozen": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items()} for d in days_f],
                "daily_with_topups": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items()} for d in days_t],
                "pumplean_xcheck": pumplean_xcheck(days_f)})
    out["n_pool_days"] = out["frozen"]["n_pool_days"]
    out["verdict"] = out["frozen"]["verdict"]
    LEDGER.write_text(json.dumps(out, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    print(json.dumps({k: out[k] for k in ("window", "n_pool_days", "verdict", "frozen", "with_topups_INFORMATIONAL")},
                     indent=1, default=str))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "freeze":
        freeze()
    elif cmd == "score":
        score()
    elif cmd == "selftest":      # engine parity on the (already examined) validation window, no fetch
        import lphedge2_sim as s2
        val = json.loads((ROOT / "research/observations/evidence_lphedge2_validation.json").read_text())
        hs = val["half_spreads"]
        a, sa, _ = run_topups(*s1.SPLITS["validation"], hs, topup=False)
        b, sb, _, _ = s2.run(*s1.SPLITS["validation"], hs)
        print("frozen-engine parity", round(sum(d["pnl"] for d in a) - sa, 4), round(sum(d["pnl"] for d in b) - sb, 4))
        t, st, mv = run_topups(*s1.SPLITS["validation"], hs, topup=True)
        print("with top-ups", summary(t, st), "moved", round(mv, 2))
    else:
        sys.exit(__doc__)
