"""Decu's on-stream session on every venue (kolscan's public trade stream), and hypothesis H5.

kolscan relays each tracked wallet's swaps (pump.fun curve, Pump AMM, Raydium Launchpad, ...) with the SOL
amount. Per token: SOL in (buys) and SOL out (sells) during the stream window; tokens still held are listed
as open, not counted as losses or gains. The curve tape cross-checks the pump.fun legs (it misses ~4% of
small buys to websocket drops and, by design, non-SOL-quoted pairs).

    python scripts/research/decu_session_pnl.py
"""
import collections
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import duckdb  # noqa: E402

from pipeline import annotations, config, db, findings, observations  # noqa: E402
from pipeline.ingest_web import ingest_document  # noqa: E402

EX = "claude:decu-session-2026-10-01"
WALLET = "4vw54BmAogeRV3vPKWyFet5yf8DTLcREzdSzx4rw9Ud9"
WSOL = "So11111111111111111111111111111111111111112"
START = datetime(2026, 10, 1, 13, 38, 37, tzinfo=timezone.utc)
END = datetime(2026, 10, 1, 16, 11, 39, tzinfo=timezone.utc)      # end of the continuous 720p capture


def main() -> dict:
    con = duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
    a, b = START.timestamp(), END.timestamp()
    rows = con.execute("""SELECT recv, ts, signature, dex, direction, coalesce(nullif(out_token, ''), nullif(in_token, '')),
                                 sol_change FROM kolscan_msgs WHERE wallet = ? AND recv >= ? AND recv < ? + 1800
                          ORDER BY recv""", [WALLET, a, b]).fetchall()
    sym = dict(con.execute("SELECT mint, symbol FROM curve_creates").fetchall())
    per = collections.defaultdict(lambda: {"in": 0.0, "out": 0.0, "venues": set(), "first": None, "n": 0})
    for recv, ts, sig, dex, d, tok, sol in rows:
        if tok in (None, WSOL):
            continue
        p = per[tok]
        if d == "Buy":
            if recv >= b:                                  # positions opened after the window are not this session's
                continue
            p["in"] += sol or 0
            p["first"] = p["first"] or recv
        else:
            p["out"] += sol or 0
        p["n"] += 1
        if dex:
            p["venues"].add(dex)
    toks = []
    for t, p in per.items():
        if p["first"] is None:
            continue
        toks.append({"mint": t, "symbol": sym.get(t), "sol_in": round(p["in"], 4), "sol_out": round(p["out"], 4),
                     "net_sol": round(p["out"] - p["in"], 4), "venues": sorted(p["venues"]), "msgs": p["n"],
                     "first_buy_utc": datetime.fromtimestamp(p["first"], timezone.utc).isoformat(),
                     "status": "open (no sell yet)" if p["out"] == 0 else "closed or partly sold"})
    toks.sort(key=lambda r: -r["net_sol"])
    closed = [r for r in toks if r["sol_out"] > 0]
    net = sum(r["net_sol"] for r in closed)
    top3 = sum(r["net_sol"] for r in closed[:3])
    out = {"window_utc": [START.isoformat(), END.isoformat()], "sells_counted_until": "window end + 30 min",
           "tokens": toks, "n_tokens": len(toks), "n_with_sells": len(closed),
           "net_sol_tokens_with_sells": round(net, 3), "top3_share": round(top3 / net, 3) if net > 0 else None,
           "losers": [r for r in closed if r["net_sol"] < 0], "open": [r for r in toks if r["sol_out"] == 0],
           "by_venue": {}, "note": "SOL amounts as relayed by kolscan (fees inside the swap included; priority "
                                   "fees and tips not); tokens bought in the window, sells up to 30 min later."}
    for r in closed:
        v = "pump.fun curve only" if r["venues"] == ["Pump.fun"] else (
            "held through migration (Pump AMM exit)" if "Pump AMM" in r["venues"] and "Pump.fun" in r["venues"] else
            "Raydium Launchpad" if any("Raydium" in x for x in r["venues"]) else "other")
        g = out["by_venue"].setdefault(v, {"n": 0, "net_sol": 0.0})
        g["n"] += 1
        g["net_sol"] = round(g["net_sol"] + r["net_sol"], 3)
    p = ROOT / "research/observations/evidence_decu_session_2026-10-01.json"
    p.write_text(json.dumps(out, indent=1, default=str))
    return out


def record(o: dict) -> None:
    con = db.connect()
    con.execute("DELETE FROM hypothesis_basis WHERE finding_id IN (SELECT finding_id FROM findings WHERE notes LIKE ?)",
                [f"%{EX}%"])
    con.execute("DELETE FROM finding_evidence WHERE finding_id IN (SELECT finding_id FROM findings WHERE notes LIKE ?)",
                [f"%{EX}%"])
    con.execute("DELETE FROM findings WHERE notes LIKE ?", [f"%{EX}%"])
    con.execute("DELETE FROM observations WHERE extractor = ?", [EX])
    tid = annotations.trader_by_slug(con, "decu")
    p = ROOT / "research/observations/evidence_decu_session_2026-10-01.json"
    sid, snap = ingest_document(con, str(p), title="Decu's stream session on every venue (kolscan stream)",
                                canonical_url="stream://kolscan/2026-10-01/decu-session")
    obs = observations.add_observation(
        con, source_id=sid, snapshot_id=snap, modality="onchain", kind="session_pnl", trader_id=tid, extractor=EX,
        status="reviewed", value={k: o[k] for k in ("n_tokens", "n_with_sells", "net_sol_tokens_with_sells",
                                                    "top3_share", "by_venue")},
        content="Per-token SOL in/out of Decu's verified wallet during the stream, all venues, from kolscan.")
    bv = o["by_venue"]
    los = ", ".join(f"{r['symbol'] or r['mint'][:6]} {r['net_sol']:+.2f}" for r in o["losers"])
    f = findings.add_finding(
        con, trader_id=tid, funnel_stage="exit", evidence_type="observed",
        statement=f"Over the stream ({o['window_utc'][0][11:16]}-{o['window_utc'][1][11:16]} UTC) Decu's wallet traded "
                  f"{o['n_tokens']} tokens; on the {o['n_with_sells']} with sells it netted "
                  f"{o['net_sol_tokens_with_sells']:+.1f} SOL before priority fees, the top 3 tokens giving "
                  f"{o['top3_share']:.0%}. By venue: " + "; ".join(f"{k}: {v['n']} tokens {v['net_sol']:+.1f} SOL"
                                                               for k, v in bv.items()) +
                  f". Losers: {los or 'none'}; {len(o['open'])} still open. Most profit came from a few tokens held "
                  "through migration and sold on Pump AMM, not from the many sub-minute curve flips.",
        evidence=[("observation", obs, "supports")], n_supporting=o["n_with_sells"], n_observable=o["n_tokens"],
        confidence=0.8, notes=f"{EX}; kolscan relay of on-chain swaps")
    h3 = con.execute("SELECT hypothesis_id FROM hypotheses WHERE statement LIKE 'H3:%'").fetchone()[0]
    run = con.execute("SELECT run_id FROM sim_runs WHERE hypothesis_id = ? AND notes LIKE '%first_test%' "
                      "ORDER BY created_at DESC LIMIT 1", [h3]).fetchone()
    pre = json.loads((ROOT / "reports/hypotheses/h5_preregistration.json").read_text())   # frozen text
    findings.reregister_hypothesis(con, "H5:", statement=pre["statement"],
                                   measurable_definition=pre["measurable_definition"],
                                   rationale=f"{EX}: {pre['rationale']} Frozen at {pre['frozen_at_utc']} in "
                                             "reports/hypotheses/h5_preregistration.json.",
                                   basis_finding_ids=[f], parent_id=h3, motivated_by_run_id=run[0] if run else None,
                                   trader_scope="decu")


if __name__ == "__main__":
    o = main()
    record(o)
    print(json.dumps({k: o[k] for k in ("n_tokens", "n_with_sells", "net_sol_tokens_with_sells", "top3_share",
                                        "by_venue")}, indent=1))
    print("losers", [(r["symbol"], r["net_sol"]) for r in o["losers"]], "open", [(r["symbol"] or r["mint"][:6], r["sol_in"]) for r in o["open"]])
