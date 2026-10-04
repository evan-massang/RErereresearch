"""Task 1: describe the pump.fun currently-live poll data (EXPLORATORY, forward-test period data).

    python scripts/research/live_viewers_describe.py
Writes research/observations/evidence_live_viewers_describe_20261004.json
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import duckdb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from live_viewers_lib import ROOT, load_polls  # noqa: E402


def q(s, ps=(0.5, 0.75, 0.9, 0.95, 0.99, 1.0)):
    return {str(p): float(s.quantile(p)) for p in ps}


def norm(s):
    return re.sub(r"[^a-z]", "", (s if isinstance(s, str) else "").lower())


def main():
    polls, rows, stats = load_polls()
    out = {"note": "EXPLORATORY; data after 2026-10-04 00:00 UTC (forward-test period). No strategy frozen on it.",
           "load_stats": stats, "n_polls": len(polls),
           "first_recv_utc": str(pd.to_datetime(polls.recv.min(), unit="s")),
           "last_recv_utc": str(pd.to_datetime(polls.recv.max(), unit="s")),
           "poll_gap_s": q(polls.recv.diff().dropna()), "empty_polls": int((polls.ncoins == 0).sum())}
    # live coins per poll over time, by curve / migrated
    per = rows.groupby(["recv", "complete"]).size().unstack(fill_value=0).rename(columns={False: "curve", True: "migrated"})
    per = per.reindex(polls.recv, fill_value=0)
    per.index = pd.to_datetime(per.index, unit="s")
    hourly = per.resample("1h").mean().round(1)
    out["live_per_poll"] = {"curve": q(per.curve, (0, 0.5, 1.0)), "migrated": q(per.migrated, (0, 0.5, 1.0)),
                            "hourly_mean": {str(k): v for k, v in hourly.to_dict("index").items()}}
    # viewer distribution
    cur = rows[~rows.complete]
    out["viewers_all_rows"] = q(rows.viewers)
    out["viewers_curve_rows"] = q(cur.viewers)
    out["viewers_migrated_rows"] = q(rows[rows.complete].viewers)
    out["viewers_curve_rows_share_zero"] = float((cur.viewers == 0).mean())
    mx = cur.groupby("mint").viewers.max()
    out["distinct_mints"] = {"all": int(rows.mint.nunique()), "curve_ever": int(cur.mint.nunique()),
                             "migrated_ever": int(rows[rows.complete].mint.nunique()),
                             "curve_then_migrated_while_live": int(len(set(cur.mint) & set(rows[rows.complete].mint)))}
    out["curve_mints_reaching_viewers"] = {str(v): int((mx >= v).sum()) for v in (1, 3, 5, 10, 20, 50, 100)}
    # the five-coin "$" family (see live_viewers_events.FAMILY): always live, untraded, 5-66 viewers all day
    from live_viewers_events import FAMILY
    fam = cur.mint.str[:6].isin(FAMILY)
    out["family_5_dollar_coins"] = {"rows": int(fam.sum()), "viewers": q(cur[fam].viewers, (0.5, 0.9, 1.0)),
                                    "share_of_curve_rows_with_ge10_viewers": float(fam[cur.viewers >= 10].mean()),
                                    "market_cap_sol_range": [float(cur[fam].market_cap.min()), float(cur[fam].market_cap.max())]}
    nf = cur[~fam]
    out["viewers_curve_rows_ex_family"] = q(nf.viewers)
    mxn = nf.groupby("mint").viewers.max()
    out["curve_mints_reaching_viewers_ex_family"] = {str(v): int((mxn >= v).sum()) for v in (1, 3, 5, 10, 20, 50, 100)}
    span_h = (polls.recv.max() - polls.recv.min()) / 3600
    out["poll_span_hours"] = round(span_h, 2)
    out["new_curve_mints_reaching_per_hour_ex_family"] = {str(v): round(int((mxn >= v).sum()) / span_h, 2) for v in (5, 10, 20)}
    # how long curve coins stay on the list
    life = cur.groupby("mint").recv.agg(["min", "max", "count"])
    out["curve_mint_minutes_on_list"] = q((life["max"] - life["min"]) / 60)
    # coin age (from created_timestamp) when first seen live
    first = cur.sort_values("recv").groupby("mint").first()
    out["curve_age_min_at_first_seen"] = q((first.recv - first.created_timestamp / 1000) / 60, (0.1, 0.25, 0.5, 0.75, 0.9))
    out["curve_mcap_sol_at_first_seen"] = q(first.market_cap, (0.1, 0.25, 0.5, 0.75, 0.9))
    # operator clustering
    mints = rows.drop_duplicates("mint")
    cc = mints.creator.value_counts()
    out["creators"] = {"distinct": int(cc.size), "creators_with_ge2_mints": int((cc >= 2).sum()),
                       "mints_by_multi_creators": int(cc[cc >= 2].sum()),
                       "top": {k[:8] + "..": int(v) for k, v in cc.head(10).items()}}
    tt = Counter(norm(t) for t in mints.livestream_title)
    out["titles_repeated_across_mints"] = {k[:40]: v for k, v in tt.most_common(15) if v >= 2}
    sy = Counter(norm(s) for s in mints.symbol)
    out["symbols_repeated_across_mints"] = {k: v for k, v in sy.most_common(15) if v >= 2}
    # title prefix families (first 2 words)
    pre = Counter(" ".join((t if isinstance(t, str) else "").lower().split()[:2]) for t in mints.livestream_title)
    out["title_prefix_families_ge3"] = {k: v for k, v in pre.most_common(15) if v >= 3}
    # curve coins with >=10 viewers: same creator / title?
    hi = mints[mints.mint.isin(mx[mx >= 10].index)]
    out["hi_viewer_curve_coins"] = [{"symbol": r.symbol, "title": str(r.livestream_title)[:60], "creator": r.creator[:8],
                                     "max_viewers": float(mx[r.mint]), "creator_mints_on_list": int(cc[r.creator])}
                                    for r in hi.itertuples()]
    # tape coverage of curve mints
    con = duckdb.connect(str(ROOT / "data" / "market.duckdb"), read_only=True)
    tmax = con.execute("SELECT max(recv) FROM curve_trades").fetchone()[0]
    con.register("m", pd.DataFrame({"mint": cur.mint.unique()}))
    have = con.execute("SELECT count(DISTINCT mint) FROM curve_trades WHERE recv >= ? AND mint IN (SELECT mint FROM m)",
                       [polls.recv.min() - 3600]).fetchone()[0]
    out["tape"] = {"curve_trades_max_recv_utc": str(pd.to_datetime(tmax, unit="s")),
                   "curve_live_mints_with_tape_trades": int(have), "curve_live_mints": int(cur.mint.nunique())}
    p = ROOT / "research/observations/evidence_live_viewers_describe_20261004.json"
    p.write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
