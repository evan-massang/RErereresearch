"""Track devs by the X handle in their launch metadata instead of by wallet (point in time).

Motivation: Decu's picks link X posts made seconds before launch, mostly by accounts that announce launches
(decu_choice_set / tweet_signals, 2026-10-02). Wallet-based "good dev" tracking (H7) misses devs who launch from
a fresh wallet each time; the X handle in the metadata often stays the same.

For each launch, in time order: the handle in its metadata `twitter` field (x.com/<handle> or
x.com/<handle>/status/<id>; communities and search links ignored), how many earlier launches linked that handle,
and how many of those had completed their curve BEFORE this launch. Outcome: did this launch complete (migrate).

    python scripts/research/x_handle_track.py [window ...]   # build data/processed/x_handle.parquet + print lift
                                                          # (default: Oct 1 train + validation only)
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import duckdb  # noqa: E402
import pandas as pd  # noqa: E402

from pipeline import config  # noqa: E402

META = ROOT / "data/raw/web/token_metadata"
RX = re.compile(r"(?:x|twitter)\.com/([A-Za-z0-9_]{1,15})(?:/status/(\d+))?(?:[/?#]|$)")
SKIP = {"i", "home", "search", "intent", "share", "hashtag", "explore"}
U = lambda h, m, d=1: pd.Timestamp(2026, 10, d, h, m, tz="UTC").timestamp()
WINDOWS = {"train_oct1": (U(12, 17), U(16, 15)), "validation_oct1": (U(16, 15), U(18, 15)),
           "oct2_morning": (U(1, 44, 2), U(6, 40, 2)), "oct2_afternoon": (U(16, 56, 2), U(17, 50, 2))}


def handle_of(uri: str | None) -> tuple[str | None, str | None]:
    if not uri:
        return None, None
    try:
        md = json.loads((META / (uri.rstrip("/").split("/")[-1].replace(".json", "")[:80] + ".json")).read_text())
    except (OSError, ValueError):
        return None, "no_meta"
    m = RX.search(str(md.get("twitter") or ""))
    if not m or m.group(1).lower() in SKIP:
        return None, "none"
    return m.group(1).lower(), "status" if m.group(2) else "profile"


def build() -> pd.DataFrame:
    con = duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
    cr = con.execute("SELECT mint, any_value(creator), any_value(uri), min(recv) t FROM curve_creates GROUP BY 1 ORDER BY t").df()
    cr.columns = ["mint", "creator", "uri", "t"]
    comp = dict(con.execute("SELECT mint, min(recv) FROM curve_completes GROUP BY 1").fetchall())
    hs = [handle_of(u) for u in cr.uri]
    cr["handle"], cr["x_kind"] = [h for h, _ in hs], [k for _, k in hs]
    cr["mig_t"] = cr.mint.map(comp)
    prior, prior_mig, dev_prior_mig, dev_prior = [], [], [], []
    by_h, by_c = {}, {}
    for r in cr.itertuples():
        for store, k, a, b in ((by_h, r.handle, prior, prior_mig), (by_c, r.creator, dev_prior, dev_prior_mig)):
            h = store.setdefault(k, []) if k else []
            a.append(len(h))
            b.append(sum(1 for x in h if x == x and x is not None and x < r.t))
            if k:
                h.append(r.mig_t)
    cr["handle_prior"], cr["handle_prior_mig"] = prior, prior_mig
    cr["dev_prior"], cr["dev_prior_mig"] = dev_prior, dev_prior_mig
    cr["migrated"] = cr.mig_t.notna()
    return cr


def lift(cr: pd.DataFrame) -> dict:
    out = {}
    for w, (a, b) in WINDOWS.items():
        g = cr[(cr.t >= a) & (cr.t < b)]
        if not len(g):
            continue
        base = float(g.migrated.mean())
        groups = {
            "all": g, "handle_prior_mig>=1": g[g.handle_prior_mig >= 1],
            "handle_prior_mig>=1 & rate>=20%": g[(g.handle_prior_mig >= 1) & (g.handle_prior_mig / g.handle_prior.clip(lower=1) >= 0.2)],
            "handle new (no prior)": g[g.handle.notna() & (g.handle_prior == 0)],
            "handle prior>=3, 0 mig": g[(g.handle_prior >= 3) & (g.handle_prior_mig == 0)],
            "wallet good dev": g[(g.dev_prior_mig >= 1) & (g.dev_prior_mig / g.dev_prior.clip(lower=1) >= 0.2)],
            "handle good, wallet NOT good": g[(g.handle_prior_mig >= 1) & ~((g.dev_prior_mig >= 1))],
        }
        out[w] = {k: {"n": int(len(x)), "migration_rate": round(float(x.migrated.mean()), 4) if len(x) else None,
                      "lift": round(float(x.migrated.mean()) / base, 2) if len(x) and base else None}
                  for k, x in groups.items()}
    return out


if __name__ == "__main__":
    cr = build()
    cr.drop(columns=["uri"]).to_parquet(config.path("data") / "processed" / "x_handle.parquet")
    show = sys.argv[1:] or ["train_oct1", "validation_oct1"]   # test windows only once a rule is frozen
    for w, d in lift(cr).items():
        if w not in show:
            continue
        print(w)
        for k, v in d.items():
            print(f"  {k:34} n={v['n']:6} migr={v['migration_rate']} lift={v['lift']}")
