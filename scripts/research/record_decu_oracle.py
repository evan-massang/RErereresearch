"""Record the Decu oracle result and the entry-order check, and weaken the Decu-picks PnL finding.

    python scripts/research/record_decu_oracle.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts/research"))
import duckdb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import decu_oracle  # noqa: E402
from pipeline import annotations, config, db, findings, market, observations  # noqa: E402
from pipeline.ingest_web import ingest_document  # noqa: E402

PICKS_FINDING = "fnd_41cce628f444439c"


def entry_order() -> dict:
    c = duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
    r = pd.DataFrame(json.loads((ROOT / "research/observations/evidence_decu_choice_set_2026-10-01.json").read_text())["rows"])
    p = r[r.picked & (r.t < 1790882100)].dropna(subset=["sim_pnl_sol"])
    fb = {t.mint: t.first_ts for t in market.round_trips(c, [decu_oracle.WALLET])}
    p = p.assign(decu_after_trigger=[fb.get(m, np.nan) - t for m, t in zip(p.mint, p.t)])
    before = p[p.decu_after_trigger > 1]
    after = p[p.decu_after_trigger <= 1]
    return {"picks": len(p), "bot_entered_before_decu": len(before),
            "pnl_when_bot_before_decu": round(float(before.sim_pnl_sol.sum()), 3),
            "pnl_when_decu_first": round(float(after.sim_pnl_sol.sum()), 3),
            "rows": p[["mint", "symbol", "decu_after_trigger", "sim_pnl_sol"]].round(3).to_dict("records")}


if __name__ == "__main__":
    o = {"oracle_latency_1s": decu_oracle.main(1.0), "oracle_latency_3s": decu_oracle.main(3.0), "entry_order": entry_order()}
    ex = "claude:decu-oracle-2026-10-03"
    p = ROOT / "research/observations/evidence_decu_oracle_2026-10-03.json"
    p.write_text(json.dumps(o, indent=1, default=str))
    con = db.connect()
    kept = findings.clear_previous(con, ex, ex)
    tid = annotations.trader_by_slug(con, "decu")
    sid, snap = ingest_document(con, str(p), title="Decu oracle: entering after Decu, and entry order in the choice set",
                                canonical_url="stream://pump_curve/2026-10-03/decu-oracle")
    obs = observations.add_observation(con, source_id=sid, snapshot_id=snap, modality="onchain", kind="trade_summary",
                                       trader_id=tid, extractor=ex, status="reviewed",
                                       value={k: v for k, v in o.items() if k != "entry_order"} | {"entry_order": {k: v for k, v in o["entry_order"].items() if k != "rows"}},
                                       content="Oracle copy of Decu's picks and entry order relative to the choice-set trigger.")
    O, E = o["oracle_latency_1s"], o["entry_order"]
    best = max((v for k, v in O.items() if isinstance(v, dict) and k.endswith("@0.001")), key=lambda v: v["exp"])
    new = findings.add_finding(
        con, trader_id=tid, funnel_stage="entry", evidence_type="observed",
        statement=f"Knowing Decu's picks is not enough: a bot entering 1 s after each of Decu's {O['n_trips']} buys (Oct 1-3, "
                  f"0.5 SOL, exact curve fills, 0.001 SOL tip) loses with every mechanical exit tested (best "
                  f"{best['exp']:+.4f} SOL/trade), and exiting 1 s after Decu's own sell loses "
                  f"{O['mirror_exit@0.001']['exp']:+.3f} SOL/trade. In the choice-set study the simulated bot entered "
                  f"before Decu in {E['bot_entered_before_decu']} of {E['picks']} picks ({E['pnl_when_bot_before_decu']:+.2f} SOL) "
                  f"and lost on all picks where Decu bought first ({E['pnl_when_decu_first']:+.2f} SOL): the picks' "
                  f"simulated profit came largely from Decu's own buying after the bot's entry.",
        evidence=[("observation", obs, "supports")], n_supporting=O["n_trips"], n_observable=O["n_trips"],
        confidence=0.7, notes=ex)
    findings.set_finding_status(con, PICKS_FINDING, "weakened",
                                f"Entry-order check ({new}): the bot entered before Decu in most picks, so their simulated "
                                f"profit includes Decu's own subsequent buying; an oracle entering after Decu loses.")
    for k in kept:
        findings.set_finding_status(con, k, "superseded", "Rebuilt.", superseded_by=new)
    print(new, json.dumps({k: v for k, v in E.items() if k != "rows"}))
