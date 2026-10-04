"""Pre-migration pool-selection features for the BOOST base rule (agent boost_select, 2026-10-04). READ-ONLY DB.

Base rule (from agent boost, unchanged): BOOST-universe pool (amm_pools.quote_in ~= 84.99), buy 0.5 SOL at pool
creation + 1.0 s, only if the true SOL reserve at entry <= 150 SOL (THIN), single sell at +300 s. Fills are
boost_lib.sliced_trip -> amm_flow_lib exact constant product (reserve = logged + 17.585), fee_bps/1e4 per side,
conservative entry/exit states. Tips charged by amm_flow_lib.stats (2 tx).

Point-in-time pool features, computed ONLY from the token's bonding-curve history (curve_creates + curve_trades with
recv <= pool creation), the token metadata JSON (uri content, fixed at token create) and the Mayhem flag (known at
token create). All known at the pool-creation event.
  fill_s      : pool creation recv - token create recv (seconds; fast vs slow fill)
  top5_share  : share of curve buy SOL from the 5 largest buying wallets
  creator_hold: creator's net curve tokens (buys - sells) at completion > 1% of the creator's gross buys
                (creator wallet only; transfers to other wallets are not visible)
  snipe_share : share of non-creator curve buy SOL in slots <= create slot + 2 (launch block + 2 slots)
  n_buyers    : distinct buying wallets on the curve
  social      : metadata has a non-empty twitter, telegram or website field (NaN if metadata not fetched)
  mayhem      : mayhem_flags.is_mayhem (NaN if unknown)
Data guards: train decisions only; the curve history must not touch the holdout window, so a pool is kept only if
its token was created at recv >= 1790899200 or the pool was created before 1790882100. Tokens whose create event
is not in our data (created before recording) are dropped (history incomplete). Curve trades are loaded with an SQL
filter that excludes the holdout window and anything at/after 1791072000.
"""
from __future__ import annotations

import json, os, sys
import numpy as np, pandas as pd, duckdb

sys.path.insert(0, "/home/user/RErereresearch/scripts/research")
import boost_lib as B, amm_flow_lib as L  # noqa: E402

META = "/home/user/RErereresearch/data/raw/web/token_metadata"
MAYHEM = "/home/user/RErereresearch/data/processed/mayhem_flags.parquet"
DAY2 = 1790899200


def base_trades(split: str) -> pd.DataFrame:
    df, created = B.load(split)
    rows = []
    for pool, g in df.groupby("pool", sort=False):
        a = L.pool_arrays(g)
        c = created[pool]
        rs, rt, f, ok = L.state_for(a, np.array([c + 1.0]), "buy")
        pnl, ntx = B.sliced_trip(a, c + 1.0, [c + 300.0])
        rows.append({"pool": pool, "created": c, "rs_in": rs[0], "pnl": pnl, "ntx": ntx})
    T = pd.DataFrame(rows)
    return T[(T.rs_in <= 150) & T.pnl.notna()].reset_index(drop=True)


def meta_social(uri: str):
    if not isinstance(uri, str) or not uri:
        return np.nan
    key = uri.rstrip("/").split("/")[-1]
    if key.endswith(".json"):
        key = key[:-5]
    p = os.path.join(META, key[:80] + ".json")
    if not os.path.exists(p):
        return np.nan
    try:
        d = json.load(open(p))
    except Exception:
        return np.nan
    if not isinstance(d, dict):
        return np.nan
    return float(any(isinstance(d.get(k), str) and d.get(k).strip() for k in ("twitter", "telegram", "website")))


def features(T: pd.DataFrame, split: str) -> pd.DataFrame:
    con = duckdb.connect(L.DB, read_only=True)
    con.register("pl", pd.DataFrame({"pool": T.pool}))
    pm = con.execute("select pool, any_value(mint) mint from amm_pools join pl using(pool) group by pool").df()
    T = T.merge(pm, on="pool")
    con.register("ml", pd.DataFrame({"mint": T.mint}))
    cr = con.execute("""select mint, min(recv) c_recv, min(slot) c_slot, any_value(creator) creator,
                        any_value(uri) uri from curve_creates join ml using(mint)
                        where recv < 1790882100 or (recv >= 1790899200 and recv < 1791072000) group by mint""").df()
    T = T.merge(cr, on="mint", how="left")
    n0 = len(T)
    T["has_create"] = T.c_recv.notna()
    keep = T.has_create & ((T.c_recv >= L.HOLD_B) | (T.created < L.HOLD_A)) & (T.c_recv <= T.created)
    T = T[keep].reset_index(drop=True)
    con.register("ml2", T[["mint", "created"]])
    ct = con.execute("""select t.mint, t.recv, t.slot, t.usr, t.buy, t.sol, t.tok from curve_trades t join ml2 using(mint)
                        where t.recv <= ml2.created and (t.recv < 1790882100 or (t.recv >= 1790899200 and t.recv < 1791072000))
                     """).df()
    con.close()
    assert not ((ct.recv >= L.HOLD_A) & (ct.recv < L.HOLD_B)).any() and not (ct.recv >= L.VAL_B).any()
    info = T.set_index("mint")
    feats = []
    for mint, g in ct.groupby("mint", sort=False):
        r = info.loc[mint]
        b = g[g.buy]
        bs = b.groupby("usr").sol.sum().sort_values(ascending=False)
        tot = bs.sum()
        cre = g[g.usr == r.creator]
        cb, cs = cre[cre.buy].tok.sum(), cre[~cre.buy].tok.sum()
        nc = b[b.usr != r.creator]
        feats.append({"mint": mint, "n_curve": len(g), "buy_sol": tot,
                      "top5_share": bs.iloc[:5].sum() / tot if tot > 0 else np.nan,
                      "creator_hold": float(cb > 0 and (cb - cs) > 0.01 * cb),
                      "snipe_share": nc[nc.slot <= r.c_slot + 2].sol.sum() / nc.sol.sum() if nc.sol.sum() > 0 else np.nan,
                      "n_buyers": int(b.usr.nunique())})
    F = pd.DataFrame(feats)
    T = T.merge(F, on="mint", how="left")
    T["fill_s"] = T.created - T.c_recv
    T["social"] = [meta_social(u) for u in T.uri]
    mf = pd.read_parquet(MAYHEM)[["mint", "is_mayhem"]].drop_duplicates("mint")
    mf["mayhem"] = mf.is_mayhem.map({True: 1.0, False: 0.0})
    T = T.merge(mf[["mint", "mayhem"]], on="mint", how="left")
    T.attrs["n_before_guards"] = n0
    return T
