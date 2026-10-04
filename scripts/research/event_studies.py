"""Iterations 15-16: two point-in-time event triggers on the bonding-curve tape, with exact curve fills.

15  sniper_exit: launch-block buyers (slot <= create slot + 1, not the creator) have sold >= 90% of what they
    bought, the creator holds <= 10% of what they bought, and >= MIN_BUYERS distinct other wallets have bought;
    token age 10-900 s. Snipers' forced selling is over while organic buyers remain.
16  koth: a token becomes the highest-market-cap bonding-curve token among those traded in the last 10 min
    (pump.fun's "King of the Hill" front-page slot), checked on every trade.

Entry: curve state LATENCY after the event; exits: take-profit / stop-loss on later prints (fill LATENCY after
the decision print), max hold, or the last curve state before completion. 0.5 SOL, 1.25% fee per side, tip per tx.
Train: Oct 1 before 19:15 UTC + Oct 2; validation: Oct 3 (ml_model splits).

    python scripts/research/event_studies.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import duckdb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from pipeline import config  # noqa: E402

SIZE, FEE, LATENCY = 0.5, 0.0125, 1.0
TIPS = (0.001, 0.01)
EXITS = ((0.2, 0.1), (0.3, 0.15), (0.5, 0.2), (1.0, 0.3), (2.0, 0.5))
MAXHOLDS = (300, 1800)
MIN_BUYERS = 10
HOLDOUT_START, OCT2, OCT3, OCT4 = 1790882100.0, 1790899200.0, 1790985600.0, 1791072000.0


def rt(vs0, vt0, vs1, vt1):
    tok = vt0 - vs0 * vt0 / (vs0 + SIZE * (1 - FEE))
    return (vs1 - vs1 * vt1 / (vt1 + tok)) * (1 - FEE) - SIZE


def outcomes(T, vs, vt, t, tc) -> dict:
    k = np.searchsorted(T, t + LATENCY, side="right")
    if k == 0:
        return {}
    vs0, vt0 = vs[k - 1], vt[k - 1]
    p0 = vs0 / vt0
    o = {}
    for mh in MAXHOLDS:
        end = t + LATENCY + mh
        lim = np.searchsorted(T, min(end, tc), side="left") if tc is not None and tc <= end else np.searchsorted(T, end, side="right")
        lim = max(lim, k)
        px = vs[k:lim] / vt[k:lim]
        for a, b in EXITS:
            hit = np.nonzero((px >= p0 * (1 + a)) | (px <= p0 * (1 - b)))[0]
            e = np.searchsorted(T, T[k + hit[0]] + LATENCY, side="right") if len(hit) else lim
            if tc is not None:
                e = min(e, np.searchsorted(T, tc, side="left"))
            e = max(e, k)
            o[f"g_tp{int(a * 100)}_sl{int(b * 100)}_{mh}"] = rt(vs0, vt0, vs[e - 1], vt[e - 1])
    return o


def run() -> pd.DataFrame:
    con = duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
    data_end = con.execute("SELECT max(recv) FROM curve_trades").fetchone()[0]
    cr = con.execute("SELECT mint, any_value(creator) creator, min(recv) ct, min(slot) cslot FROM curve_creates GROUP BY 1").df().set_index("mint")
    comp = dict(con.execute("SELECT mint, min(recv) FROM curve_completes GROUP BY 1").fetchall())
    events = []
    for day in (20727, 20728, 20729):
        a, b = day * 86400.0, (day + 1) * 86400.0
        tr = con.execute("""SELECT mint, recv, slot, usr, buy, sol, tok, vsol, vtok FROM curve_trades
                            WHERE mint IN (SELECT mint FROM curve_creates WHERE recv >= ? AND recv < ?)
                            ORDER BY recv""", [a, b]).df()
        # --- koth: running leader among tokens traded in the last 10 min (global time order)
        last_mc, last_t, leader = {}, {}, None
        for r in tr.itertuples():
            if r.mint not in cr.index:
                continue
            tc = comp.get(r.mint)
            if tc is not None and r.recv >= tc:
                last_mc.pop(r.mint, None)
                continue
            last_mc[r.mint] = r.vsol / r.vtok * 1e9
            last_t[r.mint] = r.recv
            if leader is None or leader not in last_mc or r.recv - last_t.get(leader, 0) > 600 or last_mc[r.mint] > last_mc[leader]:
                if r.mint != leader and (leader is None or leader not in last_mc or r.recv - last_t.get(leader, 0) > 600
                                         or last_mc[r.mint] > last_mc[leader]):
                    new = r.mint
                    # only fresh leaders among recently traded tokens
                    if leader is None or last_mc[new] >= max((v for m, v in last_mc.items() if r.recv - last_t[m] <= 600), default=0):
                        if new != leader:
                            events.append(("koth", new, r.recv, last_mc[new]))
                        leader = new
        # --- sniper exit, per token
        for m, g in tr.groupby("mint", sort=False):
            if m not in cr.index:
                continue
            ci = cr.loc[m]
            T, slot, usr, buy, tok = (g.recv.to_numpy(), g.slot.to_numpy(), g.usr.to_numpy(), g.buy.to_numpy(), g.tok.to_numpy())
            snip_bought, snip_sold, dev_b, dev_s = {}, 0.0, 0.0, 0.0
            others = set()
            sb_total = 0.0
            tc = comp.get(m)
            for i in range(len(T)):
                u = usr[i]
                if u == ci.creator:
                    if buy[i]:
                        dev_b += tok[i]
                    else:
                        dev_s += tok[i]
                elif buy[i] and slot[i] <= ci.cslot + 1:
                    snip_bought[u] = snip_bought.get(u, 0) + tok[i]
                    sb_total += tok[i]
                elif not buy[i] and u in snip_bought:
                    snip_sold += tok[i]
                elif buy[i]:
                    others.add(u)
                age = T[i] - ci.ct
                if age < 10 or age > 900 or (tc is not None and T[i] >= tc):
                    continue
                if sb_total > 0 and snip_sold >= 0.9 * sb_total and dev_s >= 0.9 * dev_b and len(others) >= MIN_BUYERS:
                    events.append(("sniper_exit", m, T[i], g.vsol.iloc[i] / g.vtok.iloc[i] * 1e9))
                    break
        print("day", day, "events", len(events), flush=True)
    ev = pd.DataFrame(events, columns=["kind", "mint", "t", "mcap"])
    rows = []
    for (kind, m), g in ev.groupby(["kind", "mint"]):
        x = con.execute("SELECT recv, vsol, vtok FROM curve_trades WHERE mint = ? ORDER BY recv, rowid", [m]).fetchall()
        T = np.array([r[0] for r in x]); vs = np.array([r[1] for r in x]); vt = np.array([r[2] for r in x])
        for t, mc in zip(g.t, g.mcap):
            if t + LATENCY + max(MAXHOLDS) > data_end:
                continue
            o = outcomes(T, vs, vt, t, comp.get(m))
            if o:
                rows.append({"kind": kind, "mint": m, "t": t, "mcap": mc, **o})
    return pd.DataFrame(rows)


def summary(v: np.ndarray) -> dict:
    v = np.sort(v)
    w, l = v[v > 0], v[v <= 0]
    return {"n": int(len(v)), "exp": round(float(v.mean()), 4) if len(v) else None,
            "pf": round(float(w.sum() / -l.sum()), 3) if len(l) and l.sum() < 0 else None,
            "wo3": round(float(v[:-3].sum()), 3) if len(v) > 3 else None}


if __name__ == "__main__":
    d = run()
    d.to_parquet(config.path("data") / "processed" / "event_studies.parquet")
    tr = d[(d.t < HOLDOUT_START) | ((d.t >= OCT2) & (d.t < OCT3))]
    va = d[d.t >= OCT3]
    out = {}
    for kind in d.kind.unique():
        for col in [c for c in d.columns if c.startswith("g_")]:
            for tip in TIPS:
                a = tr[tr.kind == kind][col].to_numpy() - 2 * tip
                b = va[va.kind == kind][col].to_numpy() - 2 * tip
                out[f"{kind}|{col}|{tip}"] = {"train": summary(a), "validation": summary(b)}
    for k, v in out.items():
        if k.endswith("|0.001"):
            print(f"{k:42} train {v['train']}  val {v['validation']}")
    (ROOT / "research/observations/evidence_event_studies_20261004.json").write_text(json.dumps(out, indent=1))
