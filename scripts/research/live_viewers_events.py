"""Tasks 2-3: point-in-time livestream-viewer events on bonding-curve coins, outcomes from the curve tape.

EXPLORATORY. All data is after 2026-10-04 00:00 UTC (forward-test period); no strategy has been frozen on it.
Any rule suggested here must be frozen and then tested only on data recorded AFTER the freeze.

Point in time: an event at poll time t uses only polls with recv <= t. Viewer change compares the viewers at t
with the poll ~1-3 min earlier (min viewers over polls in [t-180, t-60]).

Events (curve coins only, complete == false in the poll at t):
  cross_V    first poll at which the coin shows >= V viewers (V = 3, 5, 10, 20)
  rise_V_X   viewers >= V and viewers >= (1+X) * ref, ref = min viewers in polls [t-180, t-60] (ref may be 0);
             5-min cooldown per mint
Baselines (same horizon / sim rules):
  flat_same  the same event mints at polls where viewers >= 1 and |viewers/ref - 1| <= 10% (sampled every 5 min)
  live_other all other curve coins on the live list, sampled every 5 min (any viewer count)
Outcomes (tape, trusted states only: |vsol - rsol - 30| < 0.01): price change at t+5/15/30 min vs the last state
at or before t (last curve state before completion if it completes), buy/sell SOL in (t, t+h] and (t-h, t],
and the 0.5 SOL round trip from event_studies.outcomes() (exact CP fills, 1.25 %/side, 1 s latency, TP/SL,
max hold 300 / 1800 s) minus 2 x tip (0.001, 0.01).

    python scripts/research/live_viewers_events.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import duckdb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import event_studies as es  # noqa: E402
from live_viewers_lib import ROOT, load_polls  # noqa: E402

HORIZONS = (300, 900, 1800)
CROSS_V = (3, 5, 10, 20)
RISE = ((3, 0.5), (5, 0.5), (5, 1.0), (10, 0.5), (20, 0.3))
COOLDOWN, SAMPLE = 300, 300
# Five curve coins created 2026-09-15 10:13-13:50 UTC, symbol "$"+letters, no stream title, never traded off the
# initial curve (market cap ~28 SOL all day), live in every poll with 5-66 "viewers": one operator's always-on streams.
# Their viewer counts are not a flow signal; they are excluded from events/baselines and counted separately.
FAMILY = {"25eDKr", "7bS1mH", "DN19Uo", "Fn5ikZ", "5so4km"}
OUT = ROOT / "research/observations/evidence_live_viewers_events_20261004.json"


def events_for(rows: pd.DataFrame) -> pd.DataFrame:
    ev = []
    cur = rows[~rows.complete & ~rows.mint.str[:6].isin(FAMILY)].sort_values(["mint", "recv"])
    for m, g in cur.groupby("mint", sort=False):
        T, V = g.recv.to_numpy(), g.viewers.to_numpy()
        crossed = {v: False for v in CROSS_V}
        below = {v: False for v in CROSS_V}  # a cross needs an earlier observed poll below V (not left-censored)
        last_rise = {r: -1e18 for r in RISE}
        last_flat, last_samp = -1e18, -1e18
        for i in range(len(T)):
            t, v = T[i], V[i]
            lo, hi = np.searchsorted(T, t - 180, "left"), np.searchsorted(T, t - 60, "right")
            ref = float(V[lo:hi].min()) if hi > lo else None  # only polls at or before t
            for c in CROSS_V:
                if not crossed[c] and v >= c:
                    crossed[c] = True
                    if below[c]:
                        ev.append((f"cross_{c}", m, t, v, ref))
                elif v < c:
                    below[c] = True
            if ref is not None:
                for (c, x) in RISE:
                    if v >= c and v >= (1 + x) * ref and t - last_rise[(c, x)] >= COOLDOWN:
                        last_rise[(c, x)] = t
                        ev.append((f"rise_{c}_{int(x * 100)}", m, t, v, ref))
                if v >= 1 and ref >= 1 and abs(v / ref - 1) <= 0.10 and t - last_flat >= SAMPLE:
                    last_flat = t
                    ev.append(("flat_any", m, t, v, ref))
            if t - last_samp >= SAMPLE:
                last_samp = t
                ev.append(("sample_any", m, t, v, ref))
    return pd.DataFrame(ev, columns=["kind", "mint", "t", "viewers", "ref"])


def tape(con, mints, t_end):
    con.register("mm", pd.DataFrame({"mint": list(mints)}))
    tr = con.execute("""SELECT mint, recv, buy, sol, vsol, vtok FROM curve_trades
                        WHERE mint IN (SELECT mint FROM mm) AND recv <= ? AND abs(vsol - rsol - 30) < 0.01
                        ORDER BY mint, recv, rowid""", [t_end]).df()
    comp = dict(con.execute("SELECT mint, min(recv) FROM curve_completes WHERE mint IN (SELECT mint FROM mm) GROUP BY 1").fetchall())
    return {m: g for m, g in tr.groupby("mint", sort=False)}, comp


def measure(ev, tapes, comp, data_end):
    out = []
    for r in ev.itertuples():
        g = tapes.get(r.mint)
        tc = comp.get(r.mint)
        row = {"kind": r.kind, "mint": r.mint, "t": r.t, "viewers": r.viewers, "ref": r.ref, "has_tape": g is not None}
        if g is None or r.t + max(HORIZONS) + es.LATENCY > data_end:
            row["covered"] = r.t + max(HORIZONS) + es.LATENCY <= data_end
            out.append(row)
            continue
        row["covered"] = True
        T, vs, vt, buy, sol = (g.recv.to_numpy(), g.vsol.to_numpy(), g.vtok.to_numpy(), g.buy.to_numpy(), g.sol.to_numpy())
        if tc is not None and tc <= r.t:
            row["completed_before"] = True
            out.append(row)
            continue
        k0 = np.searchsorted(T, r.t, "right")
        if k0 == 0:
            row["no_state"] = True
            out.append(row)
            continue
        p0 = vs[k0 - 1] / vt[k0 - 1]
        row["mcap0"] = p0 * 1e9
        row["age_last_trade_s"] = r.t - T[k0 - 1]
        for h in HORIZONS:
            end = r.t + h
            if tc is not None and tc <= end:
                k1 = np.searchsorted(T, tc, "left")
            else:
                k1 = np.searchsorted(T, end, "right")
            k1 = max(k1, k0)
            row[f"ret_{h}"] = vs[k1 - 1] / vt[k1 - 1] / p0 - 1
            w = slice(k0, k1)
            row[f"buy_sol_{h}"] = float(sol[w][buy[w]].sum())
            row[f"sell_sol_{h}"] = float(sol[w][~buy[w]].sum())
            row[f"ntr_{h}"] = int(k1 - k0)
            kb = np.searchsorted(T, r.t - h, "right")
            wb = slice(kb, k0)
            row[f"prev_net_{h}"] = float(sol[wb][buy[wb]].sum() - sol[wb][~buy[wb]].sum())
        row["completed_within_1800"] = bool(tc is not None and tc <= r.t + 1800)
        row.update(es.outcomes(T, vs, vt, r.t, tc))
        out.append(row)
    return pd.DataFrame(out)


def stats(d: pd.DataFrame) -> dict:
    s = {"n": int(len(d)), "mints": int(d.mint.nunique())}
    if not len(d):
        return s
    for h in HORIZONS:
        x = d[f"ret_{h}"].dropna()
        s[f"ret_{h}"] = {"mean": round(float(x.mean()), 4), "median": round(float(x.median()), 4),
                         "p_up": round(float((x > 0).mean()), 3), "p_flat": round(float((x == 0).mean()), 3)}
        nb = d[f"buy_sol_{h}"] - d[f"sell_sol_{h}"]
        s[f"net_buy_sol_{h}"] = {"mean": round(float(nb.mean()), 3), "median": round(float(nb.median()), 3),
                                 "buy_mean": round(float(d[f"buy_sol_{h}"].mean()), 3)}
    s["prev_net_900_mean"] = round(float(d.prev_net_900.mean()), 3)
    s["completed_within_1800"] = int(d.completed_within_1800.sum())
    sim = {}
    for col in [c for c in d.columns if c.startswith("g_")]:
        for tip in es.TIPS:
            v = d[col].dropna().to_numpy() - 2 * tip
            sim[f"{col}|tip{tip}"] = es.summary(v)
    s["sim"] = sim
    # per-mint mean (each mint weighted once) for the 15-min return
    s["ret_900_mean_of_mint_means"] = round(float(d.groupby("mint").ret_900.mean().mean()), 4)
    return s


def main():
    polls, rows, _ = load_polls()
    ev = events_for(rows)
    con = duckdb.connect(str(ROOT / "data" / "market.duckdb"), read_only=True)
    data_end = con.execute("SELECT max(recv) FROM curve_trades").fetchone()[0]
    tapes, comp = tape(con, ev.mint.unique(), data_end)
    d = measure(ev, tapes, comp, data_end)
    event_kinds = sorted(k for k in d.kind.unique() if k.startswith(("cross", "rise")))
    ev_mints = set(d[d.kind.isin(event_kinds)].mint)
    res = {"note": "EXPLORATORY; forward-test-period data (2026-10-04). No rule is frozen; any rule must be frozen and "
                   "tested on data recorded AFTER the freeze.",
           "data_end_tape_utc": str(pd.to_datetime(data_end, unit="s")),
           "poll_span_utc": [str(pd.to_datetime(polls.recv.min(), unit="s")), str(pd.to_datetime(polls.recv.max(), unit="s"))],
           "counts": {}, "stats": {}}
    usable = d[d.covered & d.has_tape & d.ret_900.notna()] if "ret_900" in d else d.iloc[0:0]
    for k in sorted(d.kind.unique()):
        a = d[d.kind == k]
        res["counts"][k] = {"all_polls_span": int(len(a)), "mints": int(a.mint.nunique()),
                            "covered_by_tape_horizon": int(a.covered.sum()),
                            "no_tape_trades_for_mint": int((~a.has_tape).sum()),
                            "usable": int((usable.kind == k).sum())}
    groups = {k: usable[usable.kind == k] for k in event_kinds}
    groups["flat_same_mints"] = usable[(usable.kind == "flat_any") & usable.mint.isin(ev_mints)]
    groups["sample_same_mints"] = usable[(usable.kind == "sample_any") & usable.mint.isin(ev_mints)]
    groups["sample_other_mints"] = usable[(usable.kind == "sample_any") & ~usable.mint.isin(ev_mints)]
    # traded-only baseline: other mints with >= 1 trade in the prior 15 min (events nearly always have recent trades)
    so = groups["sample_other_mints"]
    groups["sample_other_mints_active"] = so[so.age_last_trade_s <= 900]
    for k, g in groups.items():
        res["stats"][k] = stats(g)
    # poll-level lead/lag: viewer change vs forward and past net buy flow (curve coins with tape, sampled every 5 min)
    sa = usable[usable.kind == "sample_any"].copy()
    sa = sa[sa.ref.notna()]
    sa["dv"] = sa.viewers - sa.ref
    if len(sa) > 10:
        res["lead_lag_spearman"] = {
            "n": int(len(sa)), "n_dv_pos": int((sa.dv > 0).sum()),
            "dv_vs_fwd_net_300": round(float(sa.dv.corr(sa.buy_sol_300 - sa.sell_sol_300, method="spearman")), 3),
            "dv_vs_fwd_ret_900": round(float(sa.dv.corr(sa.ret_900, method="spearman")), 3),
            "dv_vs_prev_net_300": round(float(sa.dv.corr(sa.prev_net_300, method="spearman")), 3)}
    # per-event table for the main triggers (small n: list them)
    keep = ["kind", "mint", "t", "viewers", "ref", "mcap0", "ret_300", "ret_900", "ret_1800", "buy_sol_900", "sell_sol_900",
            "prev_net_900", "completed_within_1800", "g_tp50_sl20_1800", "g_tp20_sl10_300"]
    lst = usable[usable.kind.isin(["cross_5", "cross_10", "rise_5_50"])][keep].copy()
    lst["t"] = pd.to_datetime(lst.t, unit="s").astype(str)
    lst["mint"] = lst.mint.str[:8]
    res["event_list"] = json.loads(lst.round(4).to_json(orient="records"))
    OUT.write_text(json.dumps(res, indent=1, default=str))
    for k, s in res["stats"].items():
        if s["n"]:
            print(f"{k:26} n={s['n']:4} mints={s['mints']:3} r5={s['ret_300']['mean']:+.3f} r15={s['ret_900']['mean']:+.3f} "
                  f"(med {s['ret_900']['median']:+.3f}, up {s['ret_900']['p_up']}) r30={s['ret_1800']['mean']:+.3f} "
                  f"net15={s['net_buy_sol_900']['mean']:+.2f} prev15={s['prev_net_900_mean']:+.2f} "
                  f"sim50/20/1800={s['sim'].get('g_tp50_sl20_1800|tip0.001', {}).get('exp')} "
                  f"sim20/10/300={s['sim'].get('g_tp20_sl10_300|tip0.001', {}).get('exp')}")
        else:
            print(k, "n=0")
    print(json.dumps(res["counts"], indent=0))
    print(res.get("lead_lag_spearman"))


if __name__ == "__main__":
    main()
