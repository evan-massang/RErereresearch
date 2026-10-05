"""Agent dev_funding (2026-10-05): per-launch funding features from the cached RPC responses
(dev_funding_fetch.py), plus migration outcome and exact curve-fill trade outcomes.

Features (all strictly before the launch: creator signatures with slot < create slot; funder signatures before
the funding transaction; in-sample funder graph uses only fundings with blockTime < launch create time):
  prior_tx       creator's signatures before the launch (capped: complete=False means >= 5,000)
  age_s          launch time - creator's first signature blockTime (NULL if history not complete)
  funder         source of the largest system transfer / createAccount into the creator in its earliest successful
                 transaction (the first of up to 3 oldest that contains one)
  funder_class   pre-declared, first match wins:
      cex        funder is in the Dune spellbook cex_solana_addresses list (cex_hot_wallets_dune.json)
      whale      funder held >= 1,000 SOL just before the funding transaction (unlabelled exchange/custodial-like;
                 checked before farm because unlabelled exchange hot wallets are also busy)
      farm       funder funded >= 2 OTHER sampled creators before this launch, OR funder had >= 500
                 signatures in the 24 h before the funding transaction
      fresh      funder's first signature is <= 7 days before the funding (its pre-funding history < 1,000 sigs)
      other      anything else (an aged, low-activity personal wallet)
      unknown    no complete creator history, or no funding transfer found
  creator_class  fresh (age < 1 d) | young (1-30 d) | aged (>= 30 d) | heavy (>= 5,000 prior sigs) | unknown
  tape_prior     creator's earlier launches in allowed recorded data (point in time)

Outcomes: migrated (curve_completes before the split ceiling); trade outcomes via the event_studies fill model
(exact constant product, 0.5 SOL, 1.25% fee per side, 1 s latency, completion cut), the initial curve state
(vsol 30, vtok 1.073e9) prepended at create time, clean states only
(|vsol - rsol - 30| < 0.01), entry state must be clean. Stored before tips.
  entries:  L1 = decision at create time (fill at first state >= create + 1 s)
            M2 = decision at the first clean print with price >= 2x the initial price (vsol >= 30*sqrt(2)) within
                 600 s of create (fill 1 s later)
  exits:    tp50_sl20 max 300 s | tp100_sl30 max 1800 s | tp200_sl50 max 1800 s

    python scripts/research/dev_funding_build.py train        # features + train outcomes
    python scripts/research/dev_funding_build.py validation   # only after a config passes on train
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "research"))
import duckdb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import event_studies as es  # noqa: E402
from dev_funding_fetch import ALLOWED, CACHE, SAMPLE, funding_of, jload, split_of  # noqa: E402

SCR = Path("/tmp/claude-0/-home-user-RErereresearch/f8ba0823-6528-5b3d-92e7-a2d8665674ee/scratchpad/dev_funding")
EXITS = (("tp50_sl20_300", 0.5, 0.2, 300.0), ("tp100_sl30_1800", 1.0, 0.3, 1800.0), ("tp200_sl50_1800", 2.0, 0.5, 1800.0))
M2_VSOL = 30 * 2 ** 0.5


def features() -> pd.DataFrame:
    s = pd.read_parquet(SAMPLE)
    cex = {a["address"]: a["cex"] for a in json.loads((CACHE / "cex_hot_wallets_dune.json").read_text())["addresses"]}
    con = duckdb.connect(str(ROOT / "data/market.duckdb"), read_only=True)
    allc = con.execute(f"SELECT mint, arg_min(creator, recv) creator, min(recv) ct FROM curve_creates WHERE {ALLOWED} GROUP BY 1").df()
    fund = {}
    for c in s.creator.unique():
        cs = jload(CACHE / "creators" / f"{c}.json")
        if cs is None:
            continue
        f = None
        if cs["complete"]:
            for x in [x for x in reversed(cs["sigs"]) if not x["err"]][:3]:
                tx = jload(CACHE / "tx" / f"{x['s']}.json")
                f = funding_of(tx, c)
                if f:
                    f["sig"], f["t"] = x["s"], x["t"]
                    fs = jload(CACHE / "funders" / f"{f['funder']}__{x['s'][:16]}.json")
                    if fs:
                        ts = [t for t in fs["times"] if t]
                        f["f_n"] = fs["n"]
                        f["f_24h"] = sum(1 for t in ts if x["t"] - t <= 86400)
                        f["f_first"] = min(ts) if ts else None
                    break
        fund[c] = (cs, f)
    # in-sample funder graph: funder -> list of (funding time, creator)
    graph = defaultdict(list)
    for c, (cs, f) in fund.items():
        if f:
            graph[f["funder"]].append((f["t"], c))
    rows = []
    for r in s.itertuples():
        cs, f = fund.get(r.creator, (None, None))
        d = {"mint": r.mint, "creator": r.creator, "ct": r.ct, "cslot": r.cslot, "split": r.split}
        d["tape_prior"] = int(((allc.creator == r.creator) & (allc.ct < r.ct)).sum())
        if cs is None:
            d.update(funder_class="unknown", creator_class="unknown", fetched=False)
            rows.append(d)
            continue
        prior = [x for x in cs["sigs"] if x["slot"] is not None and x["slot"] < r.cslot]
        d["fetched"] = True
        d["prior_tx"] = len(prior)
        d["complete"] = cs["complete"]
        d["age_s"] = (r.ct - min(x["t"] for x in prior if x["t"])) if cs["complete"] and prior else None
        if not cs["complete"]:
            d["creator_class"] = "heavy"
        elif d["age_s"] is None:
            d["creator_class"] = "unknown"
        else:
            d["creator_class"] = "fresh" if d["age_s"] < 86400 else ("young" if d["age_s"] < 30 * 86400 else "aged")
        if f is None or f["t"] is None or f["t"] >= r.ct:
            d["funder_class"] = "unknown"
            rows.append(d)
            continue
        d.update(funder=f["funder"], fund_sol=f["lamports"] / 1e9,
                 funder_pre_sol=(f["funder_pre"] / 1e9) if f.get("funder_pre") is not None else None,
                 f_24h=f.get("f_24h"), f_n=f.get("f_n"))
        others = sum(1 for t, c in graph[f["funder"]] if c != r.creator and t is not None and t < r.ct)
        d["funder_degree"] = others
        if f["funder"] in cex:
            fc = "cex"
            d["cex_name"] = cex[f["funder"]]
        elif d["funder_pre_sol"] is not None and d["funder_pre_sol"] >= 1000:
            fc = "whale"
        elif others >= 2 or (f.get("f_24h") or 0) >= 500:
            fc = "farm"
        elif f.get("f_n") is not None and f["f_n"] < 1000 and f.get("f_first") and f["t"] - f["f_first"] <= 7 * 86400:
            fc = "fresh"
        else:
            fc = "other"
        d["funder_class"] = fc
        rows.append(d)
    return pd.DataFrame(rows)


def sim(T, vs, vt, t, tc, a, b, mh):
    k = np.searchsorted(T, t + es.LATENCY, side="right")
    if k == 0:
        return None
    vs0, vt0 = vs[k - 1], vt[k - 1]
    p0 = vs0 / vt0
    end = t + es.LATENCY + mh
    lim = np.searchsorted(T, min(end, tc), side="left") if tc is not None and tc <= end else np.searchsorted(T, end, side="right")
    lim = max(lim, k)
    px = vs[k:lim] / vt[k:lim]
    hit = np.nonzero((px >= p0 * (1 + a)) | (px <= p0 * (1 - b)))[0]
    e = np.searchsorted(T, T[k + hit[0]] + es.LATENCY, side="right") if len(hit) else lim
    if tc is not None:
        e = min(e, np.searchsorted(T, tc, side="left"))
    e = max(e, k)
    return es.rt(vs0, vt0, vs[e - 1], vt[e - 1])


def outcomes(feat: pd.DataFrame, split: str) -> pd.DataFrame:
    d = feat[feat.split == split].copy()
    con = duckdb.connect(str(ROOT / "data/market.duckdb"), read_only=True)
    con.execute("SET memory_limit='2GB'; SET threads=2")
    comp = dict(con.execute(f"SELECT mint, min(recv) FROM curve_completes WHERE {ALLOWED} GROUP BY 1").fetchall())
    con.register("mm", d[["mint"]])
    ceil = 1790985600.0 if split == "train" else 1791072000.0
    tr = con.execute(f"""SELECT mint, recv, vsol, vtok, rsol FROM curve_trades WHERE mint IN (SELECT mint FROM mm)
                         AND {ALLOWED} AND recv < ? ORDER BY mint, recv, rowid""", [ceil]).df()
    g_by = dict(tuple(tr.groupby("mint", sort=False)))
    out = []
    for r in d.itertuples():
        _, sc = split_of(r.ct)
        tc = comp.get(r.mint)
        tc = tc if tc is not None and tc < sc else None
        rec = {"mint": r.mint, "migrated": tc is not None}
        g = g_by.get(r.mint)
        # the curve starts at the initial state (vsol 30, vtok 1.073e9) before its first trade
        t0 = r.ct if g is None else min(r.ct, float(g.recv.iloc[0]))
        T = np.r_[t0 - 1e-6, g.recv.to_numpy() if g is not None else []]
        vs = np.r_[30.0, g.vsol.to_numpy() if g is not None else []]
        vt = np.r_[1.073e9, g.vtok.to_numpy() if g is not None else []]
        rs = np.r_[0.0, g.rsol.to_numpy() if g is not None else []]
        clean = np.abs(vs - rs - 30) < 0.01
        Tc, vsc, vtc = T[clean], vs[clean], vt[clean]
        upto = T < r.ct + 1800
        rec["peak_x"] = float((vsc[Tc < r.ct + 1800] ** 2).max() / 900) if (Tc < r.ct + 1800).any() else None
        rec["n_trades_30m"] = int(upto.sum())
        mi = np.nonzero(clean & (vs >= M2_VSOL) & (T <= r.ct + 600))[0]
        for ename, t in (("L1", r.ct), ("M2", T[mi[0]] if len(mi) else None)):
            if t is None or (tc is not None and tc <= t + es.LATENCY):
                continue
            kraw = np.searchsorted(T, t + es.LATENCY, side="right")
            if kraw == 0 or not clean[kraw - 1]:
                continue
            for xn, a, b, mh in EXITS:
                rec[f"{ename}_{xn}"] = sim(Tc, vsc, vtc, t, tc, a, b, mh)
        out.append(rec)
    return d.merge(pd.DataFrame(out), on="mint", how="left")


if __name__ == "__main__":
    split = sys.argv[1]
    f = features()
    f.to_parquet(SCR / "dev_funding_features.parquet")
    o = outcomes(f, split)
    o.to_parquet(SCR / f"dev_funding_{split}.parquet")
    print(split, len(o), "fetched", int(o.fetched.sum()))
