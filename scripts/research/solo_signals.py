"""Signals a solo trader can see at a token's launch, and what happened to those tokens.

Per recorded pump.fun launch (all point-in-time: only what was observable when the CreateEvent arrived):
  - dev track record in the tape: earlier launches by the same creator and how many of those had migrated
    *before* this launch (history starts 12:17 UTC, so it is a same-day record, not Axiom's lifetime count);
  - name category (animal, politics, AI/tech, ...), by word lists on name + symbol;
  - copycat ("vamp"): an earlier launch in the last 6 h had the same normalised name or symbol;
  - from the metadata JSON (when fetched): X link kind (tweet / profile / community / none), tweet author,
    whether that author's tweets were linked by tokens that migrated earlier (point-in-time).
Outcomes: migrated (curve completion), and the peak market cap in the 30 min after launch relative to the
market cap 5 s after launch.

    python scripts/research/solo_signals.py        # writes data/processed/solo_signals.parquet (gitignored)
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import duckdb  # noqa: E402
import pandas as pd  # noqa: E402

from pipeline import config  # noqa: E402

META = ROOT / "data/raw/web/token_metadata"
CATEGORIES = {
    "animal": r"cat|kitt|dog|doge|pup|inu|shib|frog|pepe|toad|monk|ape|chimp|gorill|bird|penguin|pengu|fish|shark|"
              r"whale|bear|bull|hamster|rabbit|bunny|horse|fox|wolf|duck|goat|capy|otter|panda|tiger|lion|hippo|owl|"
              r"snake|turtle|crab|shrimp|rat|mouse|squirrel|koala|sloth|seal|dolphin|bee|ant|pig|cow|sheep|chicken|"
              r"rooster|eagle|parrot|deer|moose|llama|zebra|giraff|elephant|kang|croc|gator|lizard|dino|unicorn|bat",
    "politics": r"trump|maga|elon|musk|biden|kamala|vance|newsom|putin|xi|milei|obama|president|congress|senat",
    "ai_tech": r"\bai\b|agent|gpt|openai|claude|grok|robot|bot\b|neural|quantum|tesla|spacex|nvidia|apple|google",
    "crypto_meta": r"pump|sol|bonk|coin|token|moon|degen|jeet|rug|whale|chad|wojak|based|gm\b",
    "holiday": r"hallow|ghost|spook|pumpkin|witch|christmas|xmas|santa|easter|valentin",
}


def norm(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def meta(uri: str | None) -> dict | None:
    if not uri:
        return None
    f = META / (uri.rstrip("/").split("/")[-1].replace(".json", "")[:80] + ".json")
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text())
    except ValueError:
        return None


def tweet_author(url: str) -> str | None:
    m = re.search(r"(?:x|twitter)\.com/([A-Za-z0-9_]{1,15})/status/", url or "")
    return m.group(1).lower() if m else None


def main() -> pd.DataFrame:
    con = duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
    cr = con.execute("SELECT mint, recv, creator, name, symbol, uri FROM curve_creates ORDER BY recv, rowid").fetchall()
    comp = dict(con.execute("SELECT mint, min(recv) FROM curve_completes GROUP BY 1").fetchall())
    # market cap 5 s after launch and peak within 30 min (curve only)
    mc = {m: (a, b) for m, a, b in con.execute("""
        SELECT t.mint,
               arg_max(t.vsol / t.vtok, t.recv) FILTER (WHERE t.recv <= c.recv + 5) * 1e9,
               max(t.vsol / t.vtok) FILTER (WHERE t.recv <= c.recv + 1800) * 1e9
        FROM curve_trades t JOIN curve_creates c USING (mint) GROUP BY 1""").fetchall()}
    dev_hist: dict[str, list] = defaultdict(list)          # creator -> [(recv, mint)]
    seen_name: dict[str, float] = {}
    author_hist: dict[str, list] = defaultdict(list)       # tweet author -> [(recv, mint)]
    rows = []
    for mint, t, creator, name, sym, uri in cr:
        prior = dev_hist[creator]
        prior_mig = sum(1 for _, m in prior if comp.get(m, 1e18) < t)
        n_name, n_sym = norm(name), norm(sym)
        vamp = any(k and seen_name.get(k, -1e18) > t - 6 * 3600 for k in (n_name, "s:" + n_sym))
        text = f"{name or ''} {sym or ''}".lower()
        md = meta(uri)
        tw = (md or {}).get("twitter") or ""
        author = tweet_author(tw)
        a_prior = author_hist[author] if author else []
        a_prior_mig = sum(1 for _, m in a_prior if comp.get(m, 1e18) < t)
        m5, mpk = mc.get(mint, (None, None))
        rows.append({
            "mint": mint, "created": t, "creator": creator, "name": name, "symbol": sym,
            "dev_prior_launches": len(prior), "dev_prior_migrations": prior_mig,
            "vamp": vamp, **{f"cat_{k}": bool(re.search(v, text)) for k, v in CATEGORIES.items()},
            "meta_ok": md is not None,
            "x_kind": None if md is None else ("tweet" if "/status/" in tw else "community" if "communit" in tw
                                                else "profile" if tw else "none"),
            "tweet_author": author, "author_prior_tokens": len(a_prior), "author_prior_migrations": a_prior_mig,
            "has_website": None if md is None else bool(md.get("website")),
            "deploy_host": (uri or "").split("/")[2] if uri and "://" in uri else None,
            "migrated": mint in comp, "mcap_5s": m5, "peak_30m_x": (mpk / m5) if (m5 and mpk) else None,
        })
        dev_hist[creator].append((t, mint))
        for k in (n_name, "s:" + n_sym):
            if k and k != "s:":
                seen_name.setdefault(k, t)
        if author:
            author_hist[author].append((t, mint))
    df = pd.DataFrame(rows)
    out = config.path("data") / "processed"
    out.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out / "solo_signals.parquet")
    return df


if __name__ == "__main__":
    d = main()
    print(len(d), "launches;", round(d.migrated.mean(), 4), "migrated;", round(d.meta_ok.mean(), 3), "with metadata")


TRAIN_END = 1790874900.0 - 3600        # launches before 16:15 (17:15 train end minus 1 h for outcomes to resolve)


def train_stats(d: pd.DataFrame) -> dict:
    t = d[d.created < TRAIN_END]
    base = float(t.migrated.mean())
    good = (t.dev_prior_migrations >= 1) & (t.dev_prior_migrations / t.dev_prior_launches.clip(lower=1) >= 0.2)
    groups = {"all": t.migrated == t.migrated, "dev_first_launch_today": t.dev_prior_launches == 0,
              "dev_10plus_launches_today": t.dev_prior_launches >= 10, "dev_1plus_prior_migration": t.dev_prior_migrations >= 1,
              "good_dev_rate_ge_20pct": good, "vamp_name_seen_6h": t.vamp, "original_name": ~t.vamp,
              "deployed_via_j7": t.deploy_host == "metadata.j7tracker.io", "deployed_via_pump_ui_ipfs": t.deploy_host == "ipfs.io",
              **{c: t[c] for c in t.columns if c.startswith("cat_")}}
    return {"window": "launches 12:17-16:15 UTC", "n": len(t), "base_migration_rate": round(base, 4),
            "groups": {k: {"n": int(m.sum()), "migration_rate": round(float(t[m].migrated.mean()), 4),
                           "lift": round(float(t[m].migrated.mean()) / base, 2),
                           "share_peak_30m_ge_3x": round(float((t[m].peak_30m_x >= 3).mean()), 3)}
                       for k, m in groups.items() if m.sum()}}


def record(st: dict) -> None:
    from pipeline import db, findings, observations
    from pipeline.ingest_web import ingest_document

    ex = "claude:solo-signals-2026-10-01"
    p = ROOT / "research/observations/evidence_solo_signals_2026-10-01.json"
    p.write_text(json.dumps(st, indent=1))
    con = db.connect()
    kept = findings.clear_previous(con, ex, ex)
    sid, snap = ingest_document(con, str(p), title="Launch-time signals vs migration (train period)",
                                canonical_url="stream://pump_curve/2026-10-01/solo-signals")
    obs = observations.add_observation(con, source_id=sid, snapshot_id=snap, modality="onchain", kind="signal_study",
                                       extractor=ex, status="reviewed", value=st,
                                       content="Migration rate of launches by launch-time signal, train period.")
    g = st["groups"]
    f = lambda k: f"{g[k]['migration_rate']:.1%} ({g[k]['lift']}x, n={g[k]['n']})"
    new = findings.add_finding(
        con, trader_id=None, funnel_stage="discovery", evidence_type="observed",
        statement=f"Of {st['n']:,} launches (base migration rate {st['base_migration_rate']:.2%}), those by a creator with "
                  f"an earlier migration that day and a >=20% migration rate migrated {f('good_dev_rate_ge_20pct')}; "
                  f"creators already on their 10th+ launch {f('dev_10plus_launches_today')}; copycat names "
                  f"{f('vamp_name_seen_6h')} vs originals {f('original_name')}; animal names {f('cat_animal')}; "
                  f"AI/tech names {f('cat_ai_tech')}; launches deployed via J7's tool {f('deployed_via_j7')}.",
        evidence=[("observation", obs, "supports")], n_supporting=g["good_dev_rate_ge_20pct"]["n"], n_observable=st["n"],
        confidence=0.7, notes=f"{ex}; dev record = same-day tape history since 12:17; migration is not profit")
    for k in kept:
        findings.set_finding_status(con, k, "superseded", "Rebuilt; kept because a hypothesis rests on it.", superseded_by=new)


if "--record" in sys.argv:
    record(train_stats(pd.read_parquet(config.path("data") / "processed" / "solo_signals.parquet")))
    print("recorded")
