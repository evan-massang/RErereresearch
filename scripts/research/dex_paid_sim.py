"""DexScreener paid-order (DEX paid profile / boost) event study with exact fills (agent dex_paid, 2026-10-05).

READ-ONLY on data/market.duckdb. Paid orders come from the cache written by dex_paid_fetch.py.

Point-in-time rule (H-DEXPAID):
- P   = paymentTimestamp of the first APPROVED `tokenProfile` order (variant PB: or the first boost, any amount).
- V   = P + LAG (visibility assumption; main LAG = 120 s, sensitivity 30 s / 600 s). The real lag is NOT measured.
- t20 = first trusted curve state (|vsol - rsol - 30| < 0.01) with real SOL >= 20 (the sample milestone).
- T   = max(V, t20): the first moment both "order is public" and "token reached 20 real SOL" are known.
- Filters fixed in advance: token age at T >= 60 s; not Mayhem; P and T inside the same allowed segment of the
  split; T + 1 + max hold before that segment's end. Curve stage additionally: real SOL at entry <= 75.
- Entry 0.5 SOL at T + 1 s. If the curve is not complete at T+1: exact curve fill (event_studies.rt maths, 1.25%
  fee per side) on the last trusted state <= T+1. If complete: PumpSwap exact constant-product fill
  (amm_flow_lib.state_for, reserve = logged + 17.585, fee_bps incl. LP + protocol + creator).
- Exit: take-profit / stop-loss on every later print (curve price, then PumpSwap mid after migration), filled
  1 s after the decision print; else at max hold. A curve position still open at completion continues on
  PumpSwap (sells there with the conservative sell state), it is NOT sold at the pre-completion curve price.
- Tips 0.001 / 0.01 SOL per transaction, 2 transactions.

    python scripts/research/dex_paid_sim.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path("/home/user/RErereresearch")
sys.path.insert(0, str(ROOT / "scripts/research"))
import amm_flow_lib as L  # noqa: E402

CACHE = ROOT / "data/raw/web/dexscreener_orders"
SIZE, CFEE, LAT = 0.5, 0.0125, 1.0
TIPS = (0.001, 0.01)
EXITS = ((0.3, 0.15), (0.5, 0.2), (1.0, 0.3))
MAXHOLDS = (300, 1800)
SEGS = {"train": [(0, L.HOLD_A), (L.HOLD_B, L.VAL_A)], "valid": [(L.VAL_A, L.VAL_B)]}


def seg_of(t, split):
    for a, b in SEGS[split]:
        if a <= t < b:
            return a, b
    return None


def load_orders():
    rows = []
    for f in CACHE.glob("*.json"):
        d = json.loads(f.read_text())
        r = d["response"]
        prof = [o["paymentTimestamp"] / 1e3 for o in r.get("orders", [])
                if o.get("type") == "tokenProfile" and o.get("status") == "approved" and o.get("paymentTimestamp")]
        anyo = [(o.get("type"), o.get("status")) for o in r.get("orders", [])]
        bst = [b["paymentTimestamp"] / 1e3 for b in r.get("boosts", []) if b.get("paymentTimestamp")]
        rows.append({"mint": d["mint"], "p_prof": min(prof) if prof else np.nan, "p_boost": min(bst) if bst else np.nan,
                     "n_orders": len(anyo), "orders": anyo, "n_boosts": len(r.get("boosts", []))})
    return pd.DataFrame(rows)


def sample(con):
    return con.execute("""
        with m as (select mint, min(recv) t20 from curve_trades
                   where rsol >= 20 and abs(vsol - rsol - 30) < 0.01 group by mint),
             c as (select mint, min(recv) ct from curve_creates group by mint),
             k as (select mint, min(recv) tc from curve_completes group by mint),
             p as (select mint, any_value(pool) pool, min(recv) pc from amm_pools group by mint)
        select * from m left join c using(mint) left join k using(mint) left join p using(mint)""").df()


def tapes(con, mints, split):
    con.register("pm", pd.DataFrame({"mint": list(mints)}))
    segs = " OR ".join(f"(recv >= {a} AND recv < {b})" for a, b in SEGS[split])
    cu = con.execute(f"""select mint, recv, vsol, vtok, rsol from curve_trades join pm using(mint)
                        where abs(vsol - rsol - 30) < 0.01 and ({segs}) order by mint, recv""").df()
    am = con.execute(f"""select recv, pool, mint, hash(usr) u, buy, tok, sol, pool_tok_logged rt,
                                pool_sol_logged rs_log, fee_bps from amm_trades join pm using(mint)
                         where tok > 0 and sol > 0 and ({segs})""").df()
    assert not ((cu.recv >= L.HOLD_A) & (cu.recv < L.HOLD_B)).any() and not (cu.recv >= L.VAL_B).any()
    assert not ((am.recv >= L.HOLD_A) & (am.recv < L.HOLD_B)).any() and not (am.recv >= L.VAL_B).any()
    if split == "train":
        assert not (cu.recv >= L.VAL_A).any() and not (am.recv >= L.VAL_A).any()
    am = am.sort_values(["mint", "recv"], kind="stable")
    return ({m: g for m, g in cu.groupby("mint")}, {m: L.pool_arrays(g) for m, g in am.groupby("mint")})


def curve_buy(vs0, vt0):
    return vt0 - vs0 * vt0 / (vs0 + SIZE * (1 - CFEE))


def curve_sell(vs1, vt1, q):
    return (vs1 - vs1 * vt1 / (vt1 + q)) * (1 - CFEE)


def amm_sell(a, t, q):
    t = max(t, a["recv"][0])
    rs, rt, f, ok = L.state_for(a, np.array([t]), "sell")
    return rs[0] * q / (rt[0] + q) * (1 - f[0]) if ok[0] else np.nan


def trade(T, cu, am, tc, seg_end):
    """Return {config: net SOL before tips} for one trigger at T; {} if not tradable."""
    te = T + LAT
    on_curve = tc is None or np.isnan(tc) or te < tc
    out = {}
    if on_curve:
        if cu is None:
            return {}
        Tc, vs, vt, rs_ = cu.recv.to_numpy(), cu.vsol.to_numpy(), cu.vtok.to_numpy(), cu.rsol.to_numpy()
        k = np.searchsorted(Tc, te, side="right")
        if k == 0 or rs_[k - 1] > 75:
            return {}
        vs0, vt0 = vs[k - 1], vt[k - 1]
        q = curve_buy(vs0, vt0)
        p0 = vs0 / vt0
        pt, pp = Tc[k:], vs[k:] / vt[k:]
        if tc is not None and not np.isnan(tc):
            keep = pt < tc
            pt, pp = pt[keep], pp[keep]
        stage = "curve"
    else:
        if am is None:
            return {}
        rs, rt, f, ok = L.state_for(am, np.array([te]), "buy")
        if not ok[0]:
            return {}
        x = SIZE / (1 + f[0])
        q = rt[0] * x / (rs[0] + x)
        p0 = rs[0] / rt[0]
        pt, pp = np.zeros(0), np.zeros(0)
        stage = "amm"
    if am is not None:
        m = am["recv"] > te
        pt, pp = np.concatenate([pt, am["recv"][m]]), np.concatenate([pp, am["mid"][m]])

    def sell_at(t):
        if on_curve and (tc is None or np.isnan(tc) or t < tc):
            j = np.searchsorted(Tc, t, side="right") - 1
            return curve_sell(vs[j], vt[j], q)
        if am is None:
            return np.nan  # completed but no pool tape: cannot price the exit
        return amm_sell(am, t, q)

    for mh in MAXHOLDS:
        end = te + mh
        if end + LAT + 5 >= seg_end:
            continue
        w = pt <= end
        for a, b in EXITS:
            hit = np.nonzero(w & ((pp >= p0 * (1 + a)) | (pp <= p0 * (1 - b))))[0]
            tx = pt[hit[0]] + LAT if len(hit) else end
            out[f"tp{int(a * 100)}_sl{int(b * 100)}_{mh}"] = sell_at(tx) - SIZE
    out["stage"] = stage
    return out


def build(split, lag, which="prof", con=None, base=False):
    own = con is None
    con = con or duckdb.connect(L.DB, read_only=True)
    s = sample(con)
    o = load_orders()
    may = pd.read_parquet(ROOT / "data/processed/mayhem_flags.parquet")
    mayset = set(may.loc[may.is_mayhem.astype(bool), "mint"])
    s = s.merge(o, on="mint")
    s = s[~s.mint.isin(mayset)]
    s["seg"] = [seg_of(t, split) for t in s.t20]
    s = s[s.seg.notna()]
    p = s.p_prof if which == "prof" else s[["p_prof", "p_boost"]].min(axis=1)
    s = s.assign(P=p)
    if base:  # descriptive control: every sampled token at t20 (no payment condition)
        s = s.assign(T=s.t20)
    else:
        s = s[s.P.notna()]
        s = s[[seg_of(x, split) == g for x, g in zip(s.P, s.seg)]]
        s = s.assign(T=np.maximum(s.P + lag, s.t20))
    s = s[[seg_of(x, split) == g for x, g in zip(s["T"], s.seg)]]
    s = s[s["T"] - s.ct >= 60]
    cu, am = tapes(con, s.mint, split)
    rows = []
    for r in s.itertuples():
        o_ = trade(r.T, cu.get(r.mint), am.get(r.mint), r.tc, r.seg[1])
        if o_:
            rows.append({"mint": r.mint, "T": r.T, "P": r.P, "t20": r.t20, "paid_before_t20": r.P < r.t20 if not base else None, **o_})
    if own:
        con.close()
    return pd.DataFrame(rows)


def grid_stats(df):
    res = {}
    cols = [c for c in df.columns if c.startswith("tp")]
    for univ in ("all", "curve", "amm"):
        d = df if univ == "all" else df[df.stage == univ]
        for c in cols:
            v = d[c].dropna().to_numpy()
            res[f"{univ}|{c}"] = {f"tip{t}": L.stats(v, t) for t in TIPS}
    return res


def passes_both(st):
    return L.passes(st["tip0.001"]) and L.passes(st["tip0.01"])


if __name__ == "__main__":
    split = sys.argv[1] if len(sys.argv) > 1 else "train"
    assert split == "train", "validation is run by dex_paid_validate.py only for configs passing on train"
    con = duckdb.connect(L.DB, read_only=True)
    o = load_orders()
    out = {"split": split, "n_cached": len(o), "grid_size": 3 * len(EXITS) * len(MAXHOLDS) + len(EXITS) * len(MAXHOLDS)}
    for which in ("prof", "prof_or_boost"):
        for lag in (120, 30, 600):
            df = build(split, lag, "prof" if which == "prof" else "pb", con)
            g = grid_stats(df)
            if which != "prof":  # boost variant: 'all' universe only (keeps the grid at 18 + 6 = 24)
                g = {k: v for k, v in g.items() if k.startswith("all|")}
            out[f"{which}|lag{lag}"] = {"n_events": len(df), "stage": df.stage.value_counts().to_dict() if len(df) else {},
                                        "grid": g, "passing": [k for k, v in g.items() if passes_both(v)]}
            print(which, lag, len(df), "passing:", out[f"{which}|lag{lag}"]["passing"], flush=True)
            df.to_parquet(f"/tmp/claude-0/-home-user-RErereresearch/f8ba0823-6528-5b3d-92e7-a2d8665674ee/scratchpad/dex_{split}_{which}_{lag}.parquet")
    base = build(split, 0, base=True, con=con)
    out["control_all_sample_at_t20"] = {"n_events": len(base), "grid": grid_stats(base)}
    Path("/tmp/claude-0/-home-user-RErereresearch/f8ba0823-6528-5b3d-92e7-a2d8665674ee/scratchpad/dex_train.json").write_text(json.dumps(out, indent=1, default=str))
