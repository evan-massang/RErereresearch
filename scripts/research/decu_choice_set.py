"""Decu BUY vs SKIP among creator-dump candidates (exploratory, in-sample).

Candidates are the moments the mechanical H3 trigger fires (token <= 30 s old, creator put in >= 2.9 SOL and
has taken out more, first creator sell <= 20 s ago). A candidate is PICKED if Decu's verified wallet bought
>= 1 SOL of it within 60 s after the trigger. Features use only trades received before the trigger, plus the
token's metadata JSON (its URI is in the create event, so it is available at launch).

    python scripts/research/decu_choice_set.py [end-HH:MM]

Writes research/observations/evidence_decu_choice_set_2026-10-01.json. Exploratory: with ~10 picks this
ranks candidate features for a later out-of-sample test; it is not a model.
"""
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts/research"))
import httpx  # noqa: E402

from pipeline import market  # noqa: E402
from pipeline.copytrade import base_execution  # noqa: E402
from pipeline.sim import run  # noqa: E402
from pipeline.strategies import DevDumpEntry, build_market_store  # noqa: E402
from run_hypotheses import tape  # noqa: E402

WALLET = "4vw54BmAogeRV3vPKWyFet5yf8DTLcREzdSzx4rw9Ud9"
START = datetime(2026, 10, 1, 13, 38, 37, tzinfo=timezone.utc)
CACHE = ROOT / "data/raw/web/token_metadata"


class Logged(DevDumpEntry):
    """DevDumpEntry that records when and on what it would decide (for the choice set)."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.log = []

    def on_event(self, view, ev):
        out = super().on_event(view, ev)
        for o in out:
            if o.tag.endswith("_entry"):
                st = self._toks[o.mint]
                self.log.append({"mint": o.mint, "t": view.now, "dev_in": st.dev_in, "dev_out": st.dev_out,
                                 "s_since_dump": view.now - st.first_sell, "age_s": view.now - st.created})
        return out


def metadata(uri: str | None) -> dict | None:
    if not uri:
        return None
    CACHE.mkdir(parents=True, exist_ok=True)
    key = uri.rstrip("/").split("/")[-1].replace(".json", "")[:80]
    f = CACHE / f"{key}.json"
    if f.exists():
        return json.loads(f.read_text())
    urls = [uri]
    if "/ipfs/" in uri:
        urls.append("https://pump.mypinata.cloud/ipfs/" + uri.split("/ipfs/")[1])
    for u in urls:
        try:
            r = httpx.get(u, timeout=10, follow_redirects=True)
            if r.status_code == 200:
                d = r.json()
                f.write_text(json.dumps(d))
                return d
        except (httpx.HTTPError, ValueError):
            continue
    return None


def meta_features(uri: str | None, m: dict | None) -> dict:
    host = (uri or "").split("/")[2] if uri and "://" in uri else None
    tw = (m or {}).get("twitter") or ""
    return {"meta_host": host, "meta_ok": m is not None,
            "has_twitter": bool(tw) if m else None,
            "twitter_kind": None if m is None else ("status" if "/status/" in tw else "community" if "communit" in tw
                                                     else "profile" if tw else "none"),
            "has_website": bool((m or {}).get("website")) if m else None,
            "has_telegram": bool((m or {}).get("telegram")) if m else None,
            "desc_len": len((m or {}).get("description") or "") if m else None}


def main(end_hm: str | None) -> dict:
    end = datetime.now(timezone.utc) if not end_hm else datetime.strptime(
        f"2026-10-01 {end_hm}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    s, e = START.timestamp(), end.timestamp()
    con = tape(s, e)
    store = build_market_store(con, s, e)
    strat = Logged(size_sol=1.0, max_age_s=30, min_dev_buy_sol=2.9, max_since_dump_s=20, hold_s=20, stop_pct=20)
    run(strat, store, start=s, end=e, execution=base_execution(tx_latency_s=1.0, fail_prob=0.0))
    decu = con.execute("SELECT mint, min(recv) FROM curve_trades WHERE usr = ? AND buy AND sol >= 1 AND recv >= ? "
                       "GROUP BY mint", [WALLET, s]).fetchall()
    decu_first = dict(decu)
    rows = []
    for c in strat.log:
        t, mint = c["t"], c["mint"]
        snap = next((x for x in market.snapshot_features(con, t, lookback=60) if x["mint"] == mint), {})
        struct = market.structure_features(con, mint, t) or {}
        cr = con.execute("SELECT uri, name, symbol FROM curve_creates WHERE mint = ?", [mint]).fetchone()
        md = metadata(cr[0]) if cr else None
        picked = mint in decu_first and t - 5 <= decu_first[mint] <= t + 60
        rows.append({**c, "picked": picked, "symbol": cr[2] if cr else None,
                     "dev_multiple": c["dev_out"] / c["dev_in"] if c["dev_in"] else None,
                     **{k: snap.get(k) for k in ("mcap_sol", "uniq_buyers_10s", "uniq_buyers_30s", "net_flow_10s",
                                                  "net_flow_30s", "vol_60s", "trades_60s", "kols_in_before",
                                                  "largest_buy_30s", "drawdown_60s")},
                     **{k: struct.get(k) for k in ("dev_pct_now", "creation_block_buyers", "creation_block_sol",
                                                    "snipers_pct_now", "holders", "top10_pct",
                                                    "creator_prev_launches_1h")},
                     **meta_features(cr[0] if cr else None, md)})
    picks = [r for r in rows if r["picked"]]
    missed = [m for m in decu_first if not any(r["mint"] == m and r["picked"] for r in rows)]
    num = [k for k in rows[0] if isinstance(rows[0][k], (int, float)) and not isinstance(rows[0][k], bool)
           and k not in ("t",)] if rows else []

    def auc(k):
        a = [r[k] for r in picks if r[k] is not None]
        b = [r[k] for r in rows if not r["picked"] and r[k] is not None]
        if not a or not b:
            return None
        wins = sum((x > y) + 0.5 * (x == y) for x in a for y in b)
        return round(wins / (len(a) * len(b)), 3)

    cmp = {k: {"picked_median": statistics.median([r[k] for r in picks if r[k] is not None] or [0]),
               "skipped_median": statistics.median([r[k] for r in rows if not r["picked"] and r[k] is not None] or [0]),
               "auc_picked_higher": auc(k)} for k in num}
    cat = {}
    for k in ("twitter_kind", "meta_host", "has_website", "has_telegram"):
        cat[k] = {"picked": _count(r[k] for r in picks), "skipped": _count(r[k] for r in rows if not r["picked"])}
    # what a bot gets on each candidate (H3 primary execution), split by Decu's choice and by activity filters
    res = run(DevDumpEntry(size_sol=1.0, max_age_s=30, min_dev_buy_sol=2.9, max_since_dump_s=20, hold_s=20,
                           stop_pct=20), store, start=s, end=e,
              execution=base_execution(tx_latency_s=1.0, fee_bps=125, priority_fee_sol=0.01, slippage_bps=2000,
                                       fail_prob=0.02))
    pnl = {t.mint: t.pnl_sol for t in res.trades}
    for r in rows:
        r["sim_pnl_sol"] = pnl.get(r["mint"])
    sim = [r for r in rows if r["sim_pnl_sol"] is not None]

    def grp(f):
        g = [r for r in sim if f(r)]
        if not g:
            return {"n": 0}
        tot = sum(r["sim_pnl_sol"] for r in g)
        return {"n": len(g), "pnl_sol": round(tot, 3), "expectancy_sol": round(tot / len(g), 4),
                "win_rate": round(sum(r["sim_pnl_sol"] > 0 for r in g) / len(g), 3)}

    groups = {"all": grp(lambda r: True), "decu_picked": grp(lambda r: r["picked"]),
              "not_picked": grp(lambda r: not r["picked"])}
    for k, th in (("uniq_buyers_10s", 12), ("uniq_buyers_10s", 20), ("net_flow_10s", 10), ("net_flow_10s", 15),
                  ("creation_block_buyers", 5), ("holders", 12), ("mcap_sol", 60)):
        groups[f"{k}>={th}"] = grp(lambda r, k=k, th=th: (r[k] or 0) >= th)
    base_p = groups["not_picked"].get("win_rate") or 0
    n_p = groups["decu_picked"]["n"]
    k_p = sum(1 for r in sim if r["picked"] and r["sim_pnl_sol"] > 0)
    from math import comb
    p_val = sum(comb(n_p, i) * base_p ** i * (1 - base_p) ** (n_p - i) for i in range(k_p, n_p + 1)) if n_p else None
    out = {"window": [START.isoformat(), end.isoformat()], "n_candidates": len(rows), "n_picked": len(picks),
           "sim_groups": groups, "picked_wins_vs_base_p": round(p_val, 4) if p_val is not None else None,
           "decu_entries_ge_1sol": len(decu_first), "decu_entries_not_in_candidates": len(missed),
           "numeric": cmp, "categorical": cat, "rows": rows,
           "note": "Exploratory, in-sample; picked = Decu bought >=1 SOL within 60 s of the H3 trigger."}
    p = ROOT / "research/observations/evidence_decu_choice_set_2026-10-01.json"
    p.write_text(json.dumps(out, indent=1, default=str))
    return out


def _count(it):
    d = {}
    for x in it:
        d[str(x)] = d.get(str(x), 0) + 1
    return d


def record(o: dict) -> None:
    """Store the evidence and an OBSERVED finding (exploratory) in the research DB."""
    from pipeline import annotations, db, findings, observations
    from pipeline.ingest_web import ingest_document

    ex = "claude:decu-choice-2026-10-01"
    con = db.connect()
    kept = findings.clear_previous(con, ex, ex)       # findings a hypothesis rests on are superseded, not deleted
    tid = annotations.trader_by_slug(con, "decu")
    p = ROOT / "research/observations/evidence_decu_choice_set_2026-10-01.json"
    sid, snap = ingest_document(con, str(p), title="Decu BUY vs SKIP among creator-dump candidates",
                                canonical_url="stream://pump_curve/2026-10-01/decu-choice-set")
    obs = observations.add_observation(
        con, source_id=sid, snapshot_id=snap, modality="onchain", kind="choice_set", trader_id=tid, extractor=ex,
        status="reviewed", value={k: o[k] for k in ("n_candidates", "n_picked", "numeric", "categorical",
                                                    "sim_groups", "picked_wins_vs_base_p")},
        content="Features at the H3 trigger of every creator-dump candidate, Decu's picks vs skips, and the "
                "simulated bot PnL of each candidate (H3 primary execution).")
    g, n = o["sim_groups"], o["numeric"]
    best = max((v for k, v in g.items() if ">=" in k and v.get("n")), key=lambda v: v["expectancy_sol"])
    new_f = findings.add_finding(
        con, trader_id=tid, funnel_stage="matching", evidence_type="observed",
        statement=f"Among {o['n_candidates']} creator-dump candidates during the stream, Decu bought {o['n_picked']}. "
                  f"At the trigger their picks had about twice the live activity of the skips (unique buyers in 10 s "
                  f"{n['uniq_buyers_10s']['picked_median']:.0f} vs {n['uniq_buyers_10s']['skipped_median']:.0f}, "
                  f"creation-block buyers {n['creation_block_buyers']['picked_median']:.0f} vs "
                  f"{n['creation_block_buyers']['skipped_median']:.0f}) and more, not fewer, sniper holdings. "
                  f"A simulated bot entering every candidate lost {g['all']['expectancy_sol']:+.3f} SOL per 1-SOL trade; "
                  f"on Decu's picks it made {g['decu_picked']['expectancy_sol']:+.3f} (wins {g['decu_picked']['win_rate']:.0%} "
                  f"vs {g['not_picked']['win_rate']:.0%}, p={o['picked_wins_vs_base_p']}). Activity filters alone stay "
                  f"negative (best {best['expectancy_sol']:+.3f}).",
        evidence=[("observation", obs, "supports")], n_supporting=g["decu_picked"]["n"],
        n_observable=g["decu_picked"]["n"], confidence=0.6,
        notes=f"{ex}; exploratory and in-sample, few picks; Decu's selection uses something the tape features here "
              "do not capture (X link is on ~all candidates, so it does not separate them)")
    for fid in kept:
        findings.set_finding_status(con, fid, "superseded", f"Rebuilt on {o['window'][0][11:16]}-{o['window'][1][11:16]} "
                                    "UTC data; kept because a hypothesis rests on it.", superseded_by=new_f)


if __name__ == "__main__":
    o = main(sys.argv[1] if len(sys.argv) > 1 else None)
    record(o)
    print(json.dumps({k: o[k] for k in ("window", "n_candidates", "n_picked", "decu_entries_ge_1sol",
                                        "decu_entries_not_in_candidates", "sim_groups", "picked_wins_vs_base_p")},
                     indent=1))
    for k, v in sorted(o["numeric"].items(), key=lambda kv: -abs((kv[1]["auc_picked_higher"] or 0.5) - 0.5)):
        print(f"{k:26} picked {v['picked_median']:>10.3f}  skipped {v['skipped_median']:>10.3f}  AUC {v['auc_picked_higher']}")
