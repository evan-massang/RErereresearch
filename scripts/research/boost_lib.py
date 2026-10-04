"""BOOST-window study helpers (agent boost, 2026-10-04). Reuses amm_flow_lib fills. READ-ONLY DB.

Universe (point in time): PumpSwap pools whose creation event (amm_pools) shows quote_in ~= 84.99 SOL, the pump.fun
migration pools that carry the 17.585 SOL BOOST budget (train evidence: 541/546 such pools show a per-pool buy-only
wallet totalling <=17.5845 SOL over ~340 s; 0/142 other pools do). Known at the pool-creation event.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import duckdb

import sys
sys.path.insert(0, "/home/user/RErereresearch/scripts/research")
import amm_flow_lib as L  # noqa: E402

HORIZON = 900.0  # pools must have >= this many seconds of allowed data after creation


def load(split: str):
    """Trades of BOOST-universe pools for `split`, first 900 s after creation only; pools whose 900 s window would
    reach an off-limits boundary are dropped."""
    con = duckdb.connect(L.DB, read_only=True)
    segs = L.SEGMENTS[split]
    m = np.zeros(0)
    pools = con.execute(f"""select pool, min(recv) created, max(quote_in) qin from amm_pools group by pool
                            having abs(max(quote_in) - 84.99) < 0.01""").df()
    m = np.zeros(len(pools), bool)
    for a, b in segs:
        m |= (pools.created.to_numpy() >= a) & (pools.created.to_numpy() < b - HORIZON)
    pools = pools[m]
    rcond = " OR ".join(f"(t.recv >= {a} AND t.recv < {b})" for a, b in segs)
    pl = pools.pool.tolist()
    con.register("pl", pd.DataFrame({"pool": pl}))
    df = con.execute(f"""select t.recv, t.pool, hash(t.usr) u, t.buy, t.tok, t.sol, t.pool_tok_logged rt,
                                t.pool_sol_logged rs_log, t.fee_bps
                         from amm_trades t join pl using(pool)
                         where t.tok > 0 and t.sol > 0 and ({rcond})""").df()
    con.close()
    df = df.merge(pools[["pool", "created"]], on="pool")
    df = df[(df.recv >= df.created - 5) & (df.recv < df.created + HORIZON)]
    # safety: no row in off-limits windows
    assert not ((df.recv >= L.HOLD_A) & (df.recv < L.HOLD_B)).any()
    assert not (df.recv >= L.VAL_B).any()
    if split == "train":
        assert not (df.recv >= L.VAL_A).any()
    df = df.sort_values(["pool", "recv"], kind="stable").reset_index(drop=True)
    return df, dict(zip(pools.pool, pools.created))


def sliced_trip(a: dict, t_entry: float, exits: list[float], size: float = L.SIZE):
    """Buy `size` SOL at t_entry; sell equal token slices at each exit time. Own earlier sells are kept in the pool
    for later slices (no reversion assumed: conservative). Returns (net SOL before tips, n_tx) or (nan, n)."""
    T = np.array([t_entry])
    rs, rt, f, ok = L.state_for(a, T, "buy")
    if not ok[0]:
        return np.nan, 1 + len(exits)
    x = size / (1 + f[0])
    q = rt[0] * x / (rs[0] + x)
    k = len(exits)
    out, sold_t, sold_s = 0.0, 0.0, 0.0
    for te in exits:
        rs2, rt2, f2, ok2 = L.state_for(a, np.array([te]), "sell")
        if not ok2[0]:
            return np.nan, 1 + k
        R_s, R_t = max(rs2[0] - sold_s, 1e-6), rt2[0] + sold_t
        qq = q / k
        g = R_s * qq / (R_t + qq)
        out += g * (1 - f2[0])
        sold_t += qq
        sold_s += g
    return out - size, 1 + k
