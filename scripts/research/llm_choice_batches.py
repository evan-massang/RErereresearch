"""Blind judgement test: can an LLM, shown only what Decu could see at the trigger, pick like Decu?

Candidates are the creator-dump moments of the Decu choice set (decu_choice_set.py). Each card holds what was
visible at that instant: coin name/symbol/description, linked X post text and author stats (followers, account
age, post age at launch), and the live tape numbers at the trigger. No outcome, no mint, no time of day; cards
are shuffled and get opaque ids.

    python scripts/research/llm_choice_batches.py make <dir> --split train|validation
    python scripts/research/llm_choice_batches.py eval <dir> --split train|validation   # after scoring
"""
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import duckdb  # noqa: E402
import pandas as pd  # noqa: E402

from pipeline import config  # noqa: E402

SRC = ROOT / "research/observations/evidence_decu_choice_set_2026-10-01.json"
META = ROOT / "data/raw/web/token_metadata"
SPLITS = {"train": (0, 1790874900.0), "validation": (1790874900.0, 1790882100.0)}  # holdout (19:15+) excluded


def candidates(split: str) -> pd.DataFrame:
    r = pd.DataFrame(json.loads(SRC.read_text())["rows"]).dropna(subset=["sim_pnl_sol"])
    a, b = SPLITS[split]
    return r[(r.t >= a) & (r.t < b)].reset_index(drop=True)


def card(row, names, uris, tw) -> dict:
    name, sym = names.get(row.mint, ("", ""))
    desc = ""
    u = uris.get(row.mint) or ""
    try:
        desc = (json.loads((META / (u.rstrip("/").split("/")[-1].replace(".json", "")[:80] + ".json")).read_text())
                .get("description") or "")[:300]
    except (OSError, ValueError):
        pass
    t = tw.get(row.mint)
    post = None if t is None else {"text": t.text, "author": t.author,
                                   "followers": None if pd.isna(t.followers) else int(t.followers),
                                   "account_age_days": None if pd.isna(t.account_age_d) else round(t.account_age_d),
                                   "post_age_seconds_at_launch": None if pd.isna(t.post_age_min) else round(t.post_age_min * 60),
                                   "is_reply": bool(t.is_reply), "coins_already_made_for_this_post": int(t.rank_for_post) - 1}
    f = lambda x, n=2: None if x is None or pd.isna(x) else round(float(x), n)
    return {"coin_name": name, "symbol": sym, "description": desc, "x_link": row.twitter_kind, "x_post": post,
            "has_website": row.has_website, "token_age_s": f(row.age_s, 1), "mcap_sol": f(row.mcap_sol, 1),
            "creator_bought_sol": f(row.dev_in), "creator_sold_sol": f(row.dev_out), "s_since_creator_sold": f(row.s_since_dump, 1),
            "unique_buyers_10s": int(row.uniq_buyers_10s), "net_inflow_sol_10s": f(row.net_flow_10s),
            "volume_sol_60s": f(row.vol_60s), "holders": None if pd.isna(row.holders) else int(row.holders),
            "top10_pct": f(row.top10_pct, 1), "snipers_pct_now": f(row.snipers_pct_now, 1),
            "launch_block_buyers": None if pd.isna(row.creation_block_buyers) else int(row.creation_block_buyers),
            "tracked_kol_wallets_in": int(row.kols_in_before or 0),
            "creator_launches_last_hour": None if pd.isna(row.creator_prev_launches_1h) else int(row.creator_prev_launches_1h)}


def make(out: Path, split: str) -> None:
    d = candidates(split)
    con = duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
    names = {m: (n, s) for m, n, s in con.execute("SELECT mint, name, symbol FROM curve_creates").fetchall()}
    uris = dict(con.execute("SELECT mint, uri FROM curve_creates").fetchall())
    tw = {r.mint: r for r in pd.read_parquet(config.path("data") / "processed" / "tweet_signals.parquet")
          .query("~post_missing").itertuples()}
    rows = [{"id": f"c{i:04d}"} | card(r, names, uris, tw) for i, r in enumerate(d.itertuples())]
    key = {f"c{i:04d}": r.mint for i, r in enumerate(d.itertuples())}
    random.Random(11).shuffle(rows)
    out.mkdir(parents=True, exist_ok=True)
    (out / "_key.json").write_text(json.dumps(key))          # id -> mint, never shown to the scorer
    for i in range(0, len(rows), 60):
        (out / f"batch_{i // 60:03d}.json").write_text(json.dumps(rows[i:i + 60], ensure_ascii=False, indent=0))
    print(len(rows), "cards in", (len(rows) + 59) // 60, "batches")


def evaluate(out: Path, split: str) -> dict:
    d = candidates(split)
    key = json.loads((out / "_key.json").read_text())
    sc = {}
    for f in sorted(out.glob("batch_*.scores.json")):
        for r in json.loads(f.read_text()):
            sc[key[r["id"]]] = r["score"]
    d["llm"] = d.mint.map(sc)
    d = d.dropna(subset=["llm"])
    g = lambda x: {"n": int(len(x)), "expectancy_sol": round(float(x.sim_pnl_sol.mean()), 4) if len(x) else None,
                   "pnl_sol": round(float(x.sim_pnl_sol.sum()), 3), "decu_picks": int(x.picked.sum())}
    res = {"split": split, "scored": int(len(d)), "all": g(d), "decu_picked": g(d[d.picked]),
           "by_score": {int(s): g(d[d.llm == s]) for s in sorted(d.llm.unique())},
           "score>=4": g(d[d.llm >= 4]), "score==5": g(d[d.llm == 5])}
    return res


if __name__ == "__main__":
    cmd, out = sys.argv[1], Path(sys.argv[2])
    split = sys.argv[sys.argv.index("--split") + 1]
    if cmd == "make":
        make(out, split)
    else:
        print(json.dumps(evaluate(out, split), indent=1))
