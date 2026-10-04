"""BOOST verification on TRAIN data only (agent boost, 2026-10-04). Reads data/market.duckdb READ-ONLY.

Identifies, per new PumpSwap pool, the BOOST buyer: a wallet that only buys in that pool and whose buys total
~17.5845 SOL (the same constant as the reserve offset found by agent amm_flow). Describes slices and timing.
Writes research/observations/evidence_boost_verify_train_20261004.json.
"""
import json
import duckdb
import numpy as np
import pandas as pd

DB = "/home/user/RErereresearch/data/market.duckdb"
HOLD_A, HOLD_B, VAL_A = 1790882100, 1790899200, 1790985600
TR = f"(t.recv < {HOLD_A} OR (t.recv >= {HOLD_B} AND t.recv < {VAL_A}))"
PTR = f"(p.created < {HOLD_A} - 900 OR (p.created >= {HOLD_B} AND p.created < {VAL_A} - 900))"
OUT = "/home/user/RErereresearch/research/observations/evidence_boost_verify_train_20261004.json"


def main():
    con = duckdb.connect(DB, read_only=True)
    d = con.execute(f"""
      with p as (select pool, min(recv) created, max(quote_in) qin from amm_pools group by pool)
      select t.pool, t.recv - p.created dt, t.slot, t.usr, t.buy, t.sol, t.tok, t.pool_sol_logged rs, p.qin
      from amm_trades t join p using(pool)
      where {TR} and {PTR} and t.recv - p.created < 900 and t.tok > 0 order by t.pool, t.recv""").df()
    pools = con.execute(f"""select count(*) from (select pool, min(recv) created from amm_pools group by pool) p
                            where {PTR}""").fetchone()[0]
    con.close()
    d["bsol"] = np.where(d.buy, d.sol, 0.0)
    a = d.groupby(["pool", "usr"]).agg(n=("buy", "size"), nb=("buy", "sum"), bsol=("bsol", "sum"),
                                         t0=("dt", "min"), t1=("dt", "max")).reset_index()
    a["npools_usr"] = a.groupby("usr").pool.transform("nunique")
    boost = a[(a.n == a.nb) & (a.nb >= 10) & ((a.bsol - 17.5845).abs() < 0.01)]
    loose = a[(a.n == a.nb) & (a.nb >= 10) & (a.npools_usr == 1) & (a.bsol > 5) & (a.bsol < 17.6)
              & (a.t1 - a.t0 > 200) & (a.t1 < 420)]
    first = d.groupby("pool").agg(rs0=("rs", "first"), qin=("qin", "first"), dt0=("dt", "first"))
    first["off0"] = first.qin - first.rs0
    first["offset_pool"] = (first.off0 - 17.585).abs() < 0.01
    first["boosted"] = first.index.isin(boost.pool)
    first["q85"] = (first.qin - 84.99).abs() < 0.01
    first["loose"] = first.index.isin(loose.pool)
    print(pd.crosstab([first.q85, first.offset_pool], [first.boosted, first.loose]))
    part = loose[~loose.pool.isin(boost.pool)]
    ct = pd.crosstab(first.offset_pool, first.boosted)
    # slice-level description
    bs = d.merge(boost[["pool", "usr"]], on=["pool", "usr"])
    bs = bs.sort_values(["pool", "dt"])
    bs["gap"] = bs.groupby("pool").dt.diff()
    q = lambda s: {k: round(float(v), 4) for k, v in s.quantile([.05, .25, .5, .75, .95]).items()}
    ev = {
        "agent": "boost", "date": "2026-10-04", "modality": "onchain", "is_synthetic": False,
        "split": "train only (holdout and forward never loaded); pools created >=900 s before a window end",
        "train_pools_with_trades": int(first.shape[0]), "train_pools_total": int(pools),
        "boost_pools_found": int(boost.pool.nunique()),
        "boost_wallet_reused_across_pools": int((boost.npools_usr > 1).sum()),
        "crosstab_offset17585_vs_boost": {f"offset={i}": {f"boost={j}": int(ct.loc[i, j]) for j in ct.columns}
                                          for i in ct.index},
        "slices_per_pool": q(boost.nb), "total_sol_per_pool": q(boost.bsol),
        "first_slice_s_after_pool_create": q(boost.t0), "last_slice_s_after_pool_create": q(boost.t1),
        "slice_sol": q(bs.sol), "gap_between_slices_s": q(bs.gap.dropna()),
        "pools_quote_in_84.99": int(first.q85.sum()),
        "q85_pools_with_full_boost": int((first.q85 & first.boosted).sum()),
        "q85_pools_with_partial_boost_only": int((first.q85 & ~first.boosted & first.loose).sum()),
        "non_q85_pools_with_any_boost": int((~first.q85 & (first.boosted | first.loose)).sum()),
        "partial_boost_total_sol": q(part.bsol), "partial_boost_slices": q(part.nb),
        "partial_note": "partial = buy-only per-pool wallet, >=10 buys over >200 s ending <420 s, 5-17.58 SOL; "
                        "most likely slices the recorder did not capture (not verified).",
        "note": ("BOOST buyer is a distinct wallet per pool (PDA-like), buys only, total 17.5845 SOL = the "
                 "reserve offset amm_flow found. Pools whose first logged quote reserve is quote_in-17.585 are "
                 "the BOOST pools; this is knowable at pool creation (amm_pools.quote_in vs first trade)."),
    }
    print(json.dumps(ev, indent=1))
    json.dump(ev, open(OUT, "w"), indent=1)


if __name__ == "__main__":
    main()
