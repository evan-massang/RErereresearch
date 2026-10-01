"""Record the BUY-vs-SKIP selection results (train data so far) and register hypothesis H1."""
import json, sys, statistics
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pipeline import db, findings, observations  # noqa: E402
from pipeline.ingest_web import ingest_document  # noqa: E402
EX = "claude:selection-2026-10-01"
S = Path("/tmp/claude-0/-home-user-RErereresearch/f8ba0823-6528-5b3d-92e7-a2d8665674ee/scratchpad")
prof = json.load(open(S / "prof_struct.json"))
med = lambda v: round(statistics.median(v), 4)
def summ(rs):
    out = {"n": len(rs), "kol_next30_share": round(sum(r["kol_next30"] for r in rs) / max(1, len(rs)), 3)}
    for h in ("r15", "r30", "r60"):
        v = [r[h] for r in rs if r[h] is not None]
        out[h] = {"median": med(v), "mean": round(statistics.mean(v), 4), "share_up": round(sum(x > 0 for x in v) / len(v), 3)}
    return out
groups = {"profile_all": prof, "profile_kol_next30": [r for r in prof if r["kol_next30"]],
          "profile_no_kol": [r for r in prof if not r["kol_next30"]],
          "dev_sold_and_snipers_lt10": [r for r in prof if r["dev_sold"] and r["snipers_pct_now"] < 10],
          "dev_not_sold": [r for r in prof if not r["dev_sold"]]}
struct = {k: {f: med([float(r[f]) for r in v if r.get(f) is not None]) for f in
              ("dev_sold", "dev_pct_now", "snipers_pct_now", "snipers_5slots", "holders", "top10_pct")}
          for k, v in (("kol_next", groups["profile_kol_next30"]), ("no_kol", groups["profile_no_kol"]),
                       ("r60_up", [r for r in prof if r["r60"] and r["r60"] > 0]),
                       ("r60_crash", [r for r in prof if r["r60"] is not None and r["r60"] <= -0.3]))}
ev = {"window": "train period, recorded 2026-10-01 12:17-13:15 UTC (gap 12:34-12:41)",
      "profile": "age<60s, >=8 unique buyers in last 10s, net inflow >1.5 SOL in last 30s; 5-s snapshots",
      "pick_vs_choice_set_percentiles": {"age_s": 0.115, "uniq_buyers_10s": 0.966, "net_flow_30s": 0.948,
                                         "drawdown_60s": 0.843, "mcap_sol": 0.784, "n_entries": 159,
                                         "avg_choice_set": 191.5},
      "groups": {k: summ(v) for k, v in groups.items()}, "structure_medians": struct,
      "caveat": "mid prices, no fees; snapshots overlap (79 distinct tokens in the dev-sold group)"}
p = ROOT / "research/observations/evidence_selection_2026-10-01.json"
p.write_text(json.dumps(ev, indent=1))
con = db.connect()
con.execute("DELETE FROM hypothesis_basis WHERE hypothesis_id IN (SELECT hypothesis_id FROM hypotheses WHERE rationale LIKE ?)", [f"%{EX}%"])
con.execute("DELETE FROM hypotheses WHERE rationale LIKE ?", [f"%{EX}%"])
con.execute("DELETE FROM finding_evidence WHERE finding_id IN (SELECT finding_id FROM findings WHERE notes LIKE ?)", [f"%{EX}%"])
con.execute("DELETE FROM findings WHERE notes LIKE ?", [f"%{EX}%"])
con.execute("DELETE FROM observations WHERE extractor = ?", [EX])
sid, snap = ingest_document(con, str(p), title="Selection study: tracked picks vs choice set; structure of hot new tokens",
                            canonical_url="stream://pump_curve/2026-10-01/selection-study")
o = observations.add_observation(con, source_id=sid, snapshot_id=snap, modality="onchain", kind="selection_study",
                                 content="Feature percentiles of tracked picks within their choice sets, and forward "
                                         "returns / structure of profile-matching tokens", value=ev, extractor=EX,
                                 status="reviewed")
g = ev["groups"]
f_pick = findings.add_finding(con, trader_id=None, funnel_stage="attention", evidence_type="observed",
    statement="Tracked wallets pick the hottest brand-new tokens of the moment: median pick is 22 s old and in the "
              "~96th-97th percentile of its ~190-token choice set for unique buyers (10 s) and inflow (30 s), "
              "entering after a ~14% dip from the 60-s high.",
    evidence=[("observation", o, "supports")], n_supporting=round(0.9 * 159), n_observable=159, confidence=0.75,
    notes=f"{EX}; n_supporting approximates entries above the 90th percentile on buyers")
f_skip = findings.add_finding(con, trader_id=None, funnel_stage="safety", evidence_type="observed",
    statement="Among tokens matching that profile, the ones no tracked wallet buys next fall a median "
              f"{g['profile_no_kol']['r30']['median']:+.0%} at 30 s and {g['profile_no_kol']['r60']['median']:+.0%} "
              f"at 60 s; the ones they do buy are ~flat/up ({g['profile_kol_next30']['r60']['median']:+.0%} at 60 s). "
              "Bought ones typically have the developer already sold out and fewer sniper wallets still holding "
              "(median ~7.7% vs ~14.3% of supply).",
    evidence=[("observation", o, "supports")], n_supporting=g["profile_kol_next30"]["n"],
    n_observable=g["profile_all"]["n"], confidence=0.6,
    notes=f"{EX}; part of the bought-group lift is the follower flow their own buy causes")
f_inf = findings.add_finding(con, trader_id=None, funnel_stage="safety", evidence_type="inferred",
    statement="Part of what separates their BUY from SKIP among equally hot tokens is supply structure: they avoid "
              "tokens whose developer and early snipers still hold supply that can be dumped ('dev sold and the "
              "market absorbed it' as an entry condition).",
    evidence=[("finding", f_skip, "derived_from"), ("finding", f_pick, "derived_from")], confidence=0.5,
    notes=f"{EX}; tape-only proxy for Axiom's dev/sniper fields; narrative/social inputs not yet observed")
h1 = findings.add_hypothesis(con,
    statement="H1: entering hot new tokens only when the developer has sold and snipers hold <10% has positive "
              "expectancy after realistic costs.",
    measurable_definition="Every 5 s: candidates with age<60s, unique_buyers_10s>=8, net_flow_30s>1.5 SOL, dev_sold, "
                          "snipers_pct_now<10 (tape-derived). Buy 0.5 SOL with 1 s total latency, fee 125 bps, "
                          "priority 0.001 SOL; exit at 60 s or -25% from entry, whichever first. Pass if expectancy > 0 "
                          "and profit factor > 1.2 with >=30 trades.",
    rationale=f"{EX}: the BUY-vs-SKIP study shows tracked wallets favour this structure and that it separates "
              "survivors from crashes among equally hot tokens; test whether the structure alone (without the "
              "trader's own follower flow) is tradable. Thresholds fixed now from the descriptive study, not tuned.",
    basis_finding_ids=[f_skip, f_inf], trader_scope="cross")
print(json.dumps({"findings": [f_pick, f_skip, f_inf], "hypothesis": h1}))
