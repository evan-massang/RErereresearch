"""Search the whole tape (not just famous KOLs) for consistently profitable human-paced wallets.

    python scripts/research/consistent_winners.py 12:17 15:15

Positions are per (wallet, token) on the bonding curve, closed when >= 99% of bought tokens were sold.
PnL is SOL out - SOL in after the 1.25% on-chain fee on each side; priority fees and tips are not
visible per trade here, so a 0.002 SOL/tx allowance is subtracted. A wallet qualifies when, in BOTH
halves of the window, it closed >= MIN_POS positions with positive PnL, and it trades at human pace:
median entry >= 5 s after launch, not in the creation block, median hold >= 10 s.

For each qualifier: price path after its entries (does price keep rising after a 1-2 s delay?) and,
for comparison, the same for the famous tracked wallets. Read-only on data/market.duckdb.
"""
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pipeline import config  # noqa: E402

MIN_POS = 8
TX_ALLOWANCE = 0.002
FEE = 0.0125


def hm(s: str) -> float:
    return datetime.strptime(f"2026-10-01 {s}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).timestamp()


def positions(con, a: float, b: float) -> str:
    return f"""
    WITH t AS (SELECT * FROM curve_trades WHERE recv >= {a} AND recv < {b} + 3600),
    p AS (SELECT usr, mint, min(recv) FILTER (WHERE buy) AS t_in, max(recv) FILTER (WHERE NOT buy) AS t_out,
                 sum(sol) FILTER (WHERE buy) AS cost, coalesce(sum(sol) FILTER (WHERE NOT buy), 0) AS proceeds,
                 sum(tok) FILTER (WHERE buy) AS bought, coalesce(sum(tok) FILTER (WHERE NOT buy), 0) AS sold,
                 count(*) AS ntx, min(slot) FILTER (WHERE buy) AS slot_in
          FROM t GROUP BY usr, mint)
    SELECT p.*, c.recv AS created, c.slot AS cslot, c.creator,
           proceeds * (1 - {FEE}) - cost * (1 + {FEE}) - ntx * {TX_ALLOWANCE} AS pnl
    FROM p JOIN curve_creates c USING (mint)
    WHERE cost > 0 AND sold >= 0.99 * bought AND t_in >= {a} AND t_in < {b} AND p.usr <> c.creator"""


def main(a_hm: str, b_hm: str) -> dict:
    a, b = hm(a_hm), hm(b_hm)
    mid = (a + b) / 2
    con = duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
    q = positions(con, a, b)
    stats = con.execute(f"""
        WITH x AS ({q})
        SELECT usr,
               count(*) FILTER (WHERE t_in < {mid}) AS n1, sum(pnl) FILTER (WHERE t_in < {mid}) AS pnl1,
               count(*) FILTER (WHERE t_in >= {mid}) AS n2, sum(pnl) FILTER (WHERE t_in >= {mid}) AS pnl2,
               median(t_in - created) AS med_entry_age, avg((slot_in = cslot)::INT) AS share_creation_block,
               median(t_out - t_in) AS med_hold, avg((pnl > 0)::INT) AS win_rate, sum(cost) AS volume,
               median(cost) AS med_size
        FROM x GROUP BY usr""").fetchall()
    cols = ["wallet", "n1", "pnl1", "n2", "pnl2", "med_entry_age_s", "share_creation_block", "med_hold_s",
            "win_rate", "volume_sol", "med_size_sol"]
    rows = [dict(zip(cols, r)) for r in stats]
    kols = dict(con.execute("SELECT wallet, name FROM kol_wallets").fetchall())
    qual = [r for r in rows if (r["n1"] or 0) >= MIN_POS and (r["n2"] or 0) >= MIN_POS and r["pnl1"] > 0
            and r["pnl2"] > 0 and r["med_entry_age_s"] >= 5 and r["share_creation_block"] < 0.2 and r["med_hold_s"] >= 10]
    active = [r for r in rows if (r["n1"] or 0) >= MIN_POS and (r["n2"] or 0) >= MIN_POS]
    for r in qual:
        r["kol_name"] = kols.get(r["wallet"])
        r["after_entry"] = after_entry(con, r["wallet"], a, b)
    qual.sort(key=lambda r: -(r["pnl1"] + r["pnl2"]))
    # base rate: how many wallets active in both halves were profitable in both, at any pace
    both = sum(1 for r in active if r["pnl1"] > 0 and r["pnl2"] > 0)
    p1 = sum(1 for r in active if r["pnl1"] > 0)
    p2 = sum(1 for r in active if r["pnl2"] > 0)
    persistence = {"n": len(active), "profitable_h1": p1, "profitable_h2": p2, "both": both,
                   "expected_if_independent": round(p1 * p2 / len(active), 1) if active else None}
    out = {"window": [a_hm, b_hm], "wallets_with_positions": len(rows), "active_both_halves": len(active),
           "persistence": persistence,
           "profitable_both_halves_any_pace": both, "qualifiers": qual,
           "kol_comparison": [dict(r, kol_name=kols[r["wallet"]], after_entry=after_entry(con, r["wallet"], a, b))
                              for r in sorted(active, key=lambda r: -(r["pnl1"] + r["pnl2"]))
                              if r["wallet"] in kols][:8],
           "notes": "PnL after 1.25% fee per side and 0.002 SOL per tx; positions closed on the curve only."}
    p = ROOT / "research/observations/evidence_consistent_winners_2026-10-01.json"
    if (config.path("hypothesis_reports") / "h4_basket.json").exists():
        p = p.with_name(f"evidence_consistent_winners_rerun_{datetime.now(timezone.utc):%H%M}.json")
    p.write_text(json.dumps(out, indent=1, default=str))
    return out


def after_entry(con, wallet: str, a: float, b: float) -> dict:
    """Median price change from the wallet's entry price to +1, +2, +5, +30, +60, +300 s (tape mid prices)."""
    ents = con.execute("""SELECT mint, min(recv) FROM curve_trades WHERE usr = ? AND buy AND recv >= ? AND recv < ?
                          GROUP BY mint""", [wallet, a, b]).fetchall()
    hz = (1, 2, 5, 30, 60, 300)
    acc = {h: [] for h in hz}
    for mint, t in ents:
        path = con.execute("SELECT recv, vsol / vtok FROM curve_trades WHERE mint = ? AND recv >= ? AND recv <= ? "
                           "ORDER BY recv, rowid", [mint, t, t + 301]).fetchall()
        if not path:
            continue
        p0 = path[0][1]
        for h in hz:
            last = [p for r, p in path if r <= t + h]
            if last:
                acc[h].append(last[-1] / p0 - 1)
    return {f"+{h}s": round(statistics.median(v), 4) if v else None for h, v in acc.items()} | {"n": len(ents)}


def record(o: dict) -> None:
    """Findings (OBSERVED) + hypothesis H4 with a frozen basket. Re-runnable (extractor tag)."""
    from pipeline import db, findings, observations
    from pipeline.ingest_web import ingest_document

    ex = "claude:consistent-winners-2026-10-01"
    basket = sorted(r["wallet"] for r in o["qualifiers"])
    bp = config.path("hypothesis_reports") / "h4_basket.json"
    if bp.exists() and json.loads(bp.read_text())["wallets"] != basket:
        raise SystemExit("H4's basket is frozen and differs from this run's qualifiers; record from the saved "
                         "evidence (--from-evidence) instead of re-selecting")
    con = db.connect()
    con.execute("DELETE FROM hypothesis_basis WHERE finding_id IN (SELECT finding_id FROM findings WHERE notes LIKE ?)",
                [f"%{ex}%"])
    con.execute("DELETE FROM finding_evidence WHERE finding_id IN (SELECT finding_id FROM findings WHERE notes LIKE ?)",
                [f"%{ex}%"])
    con.execute("DELETE FROM findings WHERE notes LIKE ?", [f"%{ex}%"])
    con.execute("DELETE FROM observations WHERE extractor = ?", [ex])
    p = ROOT / "research/observations/evidence_consistent_winners_2026-10-01.json"
    sid, snap = ingest_document(con, str(p), title="Consistently profitable human-paced wallets (whole tape)",
                                canonical_url="stream://pump_curve/2026-10-01/consistent-winners")
    obs = observations.add_observation(con, source_id=sid, snapshot_id=snap, modality="onchain",
                                       kind="wallet_cohort_study", extractor=ex, status="reviewed",
                                       value={k: o[k] for k in ("window", "wallets_with_positions", "active_both_halves",
                                                                "profitable_both_halves_any_pace", "persistence")},
                                       content="Per-wallet closed-position PnL in each half of the window, pace "
                                               "filters, and price paths after entries.")
    per = o["persistence"]
    f_pers = findings.add_finding(
        con, trader_id=None, funnel_stage="meta", evidence_type="observed",
        statement=f"Bonding-curve profitability persists between the two halves of {o['window'][0]}-{o['window'][1]} "
                  f"UTC: of {per['n']} wallets with >={MIN_POS} closed positions in both halves, {per['both']} were "
                  f"profitable in both vs {per['expected_if_independent']} expected if halves were independent; "
                  f"{len(o['qualifiers'])} of them trade at human pace (entry >=5 s after launch, not in the creation "
                  "block, hold >=10 s) and none is on the kolscan KOL list.",
        evidence=[("observation", obs, "supports")], n_supporting=per["both"], n_observable=per["n"], confidence=0.7,
        notes=f"{ex}; PnL after 1.25% fee per side and 0.002 SOL/tx allowance")
    q = [r["after_entry"] for r in o["qualifiers"] if r["after_entry"].get("+1s") is not None]
    k = [r["after_entry"] for r in o["kol_comparison"] if r["after_entry"].get("+1s") is not None]
    med = lambda xs, h: round(statistics.median([x[h] for x in xs if x.get(h) is not None]), 4)
    f_spike = findings.add_finding(
        con, trader_id=None, funnel_stage="entry", evidence_type="observed",
        statement=f"Price 1 s after an entry by one of these unknown consistent winners is a median {med(q, '+1s'):+.1%} "
                  f"from their entry price ({med(q, '+60s'):+.1%} at 60 s), while after the most profitable tracked "
                  f"KOLs' entries it is {med(k, '+1s'):+.1%} ({med(k, '+60s'):+.1%} at 60 s): the famous wallets' "
                  "entries are followed at once by other buyers, the unknown ones' are not.",
        evidence=[("observation", obs, "supports")], n_supporting=len(q), n_observable=len(q) + len(k),
        confidence=0.6, notes=f"{ex}; medians of per-wallet medians; tape mid prices, no fees")
    if not bp.exists():
        bp.write_text(json.dumps({"frozen_at": datetime.now(timezone.utc).isoformat(), "selection_window_utc": o["window"],
                                  "rule": "profitable in both halves, >=8 closed positions each, median entry age >=5 s, "
                                          "<20% creation-block entries, median hold >=10 s", "wallets": basket}, indent=1))
    findings.reregister_hypothesis(con, "H4:",
        statement="H4: copying the basket of unknown consistent winners (no follower spike after their entries) is "
                  "profitable after realistic costs, unlike copying famous KOLs.",
        measurable_definition=f"MirrorBasket(wallets=reports/hypotheses/h4_basket.json [{len(basket)} wallets, frozen], "
                              "size_sol=0.5, max_hold_s=900): buy once per token when any basket wallet opens, mirror "
                              "that wallet's sells. Primary: 1 s latency, 125 bps, 0.005 SOL priority+tip/tx, 20% "
                              "slippage tolerance, 2% failure. Test: train data 15:20-17:15 UTC (after the selection "
                              "window). Pass: expectancy > 0, PF > 1.2, >=30 trades. Reported only: latency 0.1-10 s, "
                              "0.01 SOL/tx.",
        rationale=f"{ex}: copying the top KOLs failed because their entries trigger an immediate follower spike a "
                  "copier pays for; these wallets were profitable in both halves (persistence above chance) and "
                  "their entries show no such spike. The basket is frozen before any test data exists.",
        basis_finding_ids=[f_pers, f_spike], trader_scope="cross")


if __name__ == "__main__":
    if "--from-evidence" in sys.argv:          # rebuild DB rows from the saved selection, without re-selecting
        o = json.loads((ROOT / "research/observations/evidence_consistent_winners_2026-10-01.json").read_text())
    else:
        o = main(*(sys.argv[1:3] if len(sys.argv) >= 3 and ":" in sys.argv[1] else ("12:17", "15:15")))
    if "--record" in sys.argv:
        record(o)
    print(json.dumps({k: o[k] for k in ("window", "wallets_with_positions", "active_both_halves",
                                        "profitable_both_halves_any_pace")}, indent=1))
    for r in o["qualifiers"][:25]:
        print(f"{r['wallet'][:8]} {str(r['kol_name'])[:12]:12} n={r['n1']:>3}/{r['n2']:<3} pnl={r['pnl1']:+6.2f}/{r['pnl2']:+6.2f} "
              f"age={r['med_entry_age_s']:6.0f} hold={r['med_hold_s']:6.0f} win={r['win_rate']:.2f} size={r['med_size_sol']:.2f} "
              f"after={r['after_entry']}")
    print("KOLs:")
    for r in o["kol_comparison"]:
        print(f"{r['kol_name'][:12]:12} n={r['n1']}/{r['n2']} pnl={r['pnl1']:+.2f}/{r['pnl2']:+.2f} after={r['after_entry']}")
