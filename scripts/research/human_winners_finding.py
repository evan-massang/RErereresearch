"""Record the profitable-vs-losing human-paced wallet contrast (train data < 14:00 UTC) and register H2."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pipeline import db, findings, observations  # noqa: E402
from pipeline.ingest_web import ingest_document  # noqa: E402
EX = "claude:human-winners-2026-10-01"
ev = {"window": "train, recorded data before 2026-10-01 14:00 UTC",
      "selection": "wallets with >=5 closed bonding-curve trips, median hold >=5 s, <50% creation-block entries; "
                   "winners pnl > +0.5 SOL (380 wallets, 7962 trips), losers pnl < -0.5 SOL (592 wallets, 6361 trips)",
      "trip_medians": {"WIN": {"age_at_entry_s": 70.1, "entry_mcap_sol": 73.1, "hold_s": 23.8, "size_sol": 0.795,
                               "share_multi_buy": 0.102, "win_rate": 0.485, "avg_win_frac": 2.251, "avg_loss_frac": -0.165},
                       "LOSE": {"age_at_entry_s": 30.5, "entry_mcap_sol": 75.6, "hold_s": 31.7, "size_sol": 0.717,
                                "share_multi_buy": 0.244, "win_rate": 0.247, "avg_win_frac": 0.322, "avg_loss_frac": -0.297}},
      "entry_feature_medians (sample ~230 entries each, 1 s before entry)": {
          "WIN": {"age_s": 57.5, "uniq_buyers_10s": 10, "uniq_buyers_30s": 22, "net_flow_30s": 2.76, "drawdown_60s": 0.11,
                  "largest_buy_30s": 2.05, "dev_sold": 1, "snipers_pct_now": 2.16, "holders": 41, "top10_pct": 25.1},
          "LOSE": {"age_s": 34.1, "uniq_buyers_10s": 16, "uniq_buyers_30s": 32, "net_flow_30s": 5.68, "drawdown_60s": 0.154,
                   "largest_buy_30s": 2.96, "dev_sold": 1, "snipers_pct_now": 4.83, "holders": 45, "top10_pct": 25.3}},
      "caveat": "grouping by outcome: differences are associations, partly luck; 'human-paced' still includes bots"}
p = ROOT / "research/observations/evidence_human_winners_2026-10-01.json"
p.write_text(json.dumps(ev, indent=1))
con = db.connect()
con.execute("DELETE FROM hypothesis_basis WHERE hypothesis_id IN (SELECT hypothesis_id FROM hypotheses WHERE rationale LIKE ?)", [f"%{EX}%"])
con.execute("DELETE FROM hypotheses WHERE rationale LIKE ?", [f"%{EX}%"])
con.execute("DELETE FROM finding_evidence WHERE finding_id IN (SELECT finding_id FROM findings WHERE notes LIKE ?)", [f"%{EX}%"])
con.execute("DELETE FROM findings WHERE notes LIKE ?", [f"%{EX}%"])
con.execute("DELETE FROM observations WHERE extractor = ?", [EX])
sid, snap = ingest_document(con, str(p), title="Profitable vs losing human-paced wallets on the bonding curve",
                            canonical_url="stream://pump_curve/2026-10-01/human-winners")
o = observations.add_observation(con, source_id=sid, snapshot_id=snap, modality="onchain", kind="wallet_cohort_study",
                                 content="Trip and entry-feature medians, profitable vs losing human-paced wallets",
                                 value=ev, extractor=EX, status="reviewed")
f = findings.add_finding(con, trader_id=None, funnel_stage="entry", evidence_type="observed",
    statement="Profitable human-paced wallets (380) enter later (~1 min old vs ~30 s), into less frenzied activity "
              "(10 vs 16 buyers/10 s; 2.8 vs 5.7 SOL inflow/30 s) with less sniper overhang (2.2% vs 4.8%), average "
              "down less (10% vs 24% of trips) and take smaller losses (-16.5% vs -29.7%) than losing ones (592).",
    evidence=[("observation", o, "supports")], n_supporting=380, n_observable=972, confidence=0.6,
    notes=f"{EX}; n = winners of winners+losers; associations, not causes")
fi = findings.add_finding(con, trader_id=None, funnel_stage="entry", evidence_type="inferred",
    statement="Waiting out the first frenzy and avoiding sniper-heavy supply, then exiting quickly on weakness, is the "
              "human-paced behaviour most associated with profit; chasing the hottest seconds is associated with loss.",
    evidence=[("finding", f, "derived_from")], confidence=0.45, notes=f"{EX}")
h1 = con.execute("SELECT hypothesis_id FROM hypotheses WHERE statement LIKE 'H1:%'").fetchone()[0]
h2 = findings.add_hypothesis(con,
    statement="H2: entering 45-120 s old tokens with moderate activity, dev sold and low sniper overhang, with a "
              "tight stop and short hold, has positive expectancy after realistic costs.",
    measurable_definition="StructureEntry(name='h2', min_age_s=45, max_age_s=120, min_buyers_10s=6, max_buyers_10s=14, "
                          "min_inflow_30s=1.0, max_inflow_30s=4.0, require_dev_sold=True, snipers_max_pct=5, stop_pct=15, "
                          "hold_s=25, size_sol=0.5); 1 s latency, 125 bps fee, 0.001 SOL priority. First test: train data "
                          "from 14:00 to 17:15 UTC (not used to derive the thresholds). Pass: expectancy > 0, PF > 1.2, >=30 trades.",
    rationale=f"{EX}: H1 (hot tokens) lost in development; the cohort study suggests profitable humans do the opposite of "
              "chasing heat: later, calmer entries with low sniper overhang and quick loss-cutting. Thresholds set at "
              "round values around the winners' medians, fixed before looking at post-14:00 data.",
    basis_finding_ids=[f, fi], parent_id=h1, trader_scope="cross")
print(json.dumps({"finding": f, "inferred": fi, "h2": h2}))
