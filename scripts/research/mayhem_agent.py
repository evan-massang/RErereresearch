"""Identify the pump.fun Mayhem Mode agent wallet and describe its behaviour (train window only).

1. Wallets ranked by distinct Mayhem mints traded vs distinct non-Mayhem mints (flags: mayhem_flags.py).
2. For the agent: activity window per token, sizes, slot gaps, direction vs everything visible before the trade
   (price level vs launch, previous agent actions, previous tape trade, slot parity, real SOL), the price jump each
   agent trade causes, whether other wallets' trades anticipate its direction, and curve invariants.
Writes research/observations/evidence_mayhem_agent.json.

    python scripts/research/mayhem_agent.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import duckdb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

AGENT = "BwWK17cbHxwWBKZkUYvzxLcNQ1YVyaFezduWbtm2de6s"
HOLD0, OCT2, OCT3, OCT4 = 1790882100.0, 1790899200.0, 1790985600.0, 1791072000.0
TRAIN = f"(recv < {HOLD0} OR (recv >= {OCT2} AND recv < {OCT3}))"
P0 = 30 / 1073e6  # launch price (SOL per token) of the standard curve


def connect():
    con = duckdb.connect(str(ROOT / "data/market.duckdb"), read_only=True)
    con.execute("SET memory_limit='3GB'; SET threads=2")
    con.execute(f"CREATE TEMP VIEW flags AS SELECT mint, is_mayhem FROM read_parquet('{ROOT}/data/processed/mayhem_flags.parquet')")
    return con


def q(s, qs):
    return [round(float(v), 6) for v in s.quantile(qs).values]


def grp(df, key, col="buy"):
    g = df.groupby(key, observed=True)[col].agg(["size", "mean"])
    return {str(k): {"n": int(r["size"]), "p": round(float(r["mean"]), 4)} for k, r in g.iterrows()}


if __name__ == "__main__":
    con = connect()
    ev = {"split": "train", "agent": AGENT}
    w = con.execute(f"""SELECT t.usr, count(DISTINCT CASE WHEN f.is_mayhem THEN t.mint END) mayhem_mints,
                   count(DISTINCT CASE WHEN NOT f.is_mayhem THEN t.mint END) other_mints, count(*) trades,
                   min(t.fee_bps) fee_min, max(t.fee_bps) fee_max
            FROM curve_trades t JOIN flags f USING (mint) WHERE {TRAIN} GROUP BY 1 ORDER BY 2 DESC LIMIT 12""").df()
    ev["top_wallets_by_mayhem_mints"] = w.to_dict("records")
    ev["mayhem_mints_traded_train"] = con.execute(f"""SELECT count(DISTINCT mint) FROM curve_trades JOIN flags USING (mint)
                                                   WHERE {TRAIN} AND is_mayhem""").fetchone()[0]
    print(w.to_string())
    d = con.execute(f"""SELECT t.mint, t.recv, t.slot, t.usr, t.usr = '{AGENT}' ag, t.buy, t.sol, t.tok, t.vsol, t.vtok, t.rsol, c.ct
                        FROM curve_trades t JOIN flags f USING (mint)
                        JOIN (SELECT mint, min(recv) ct FROM curve_creates GROUP BY 1) c USING (mint)
                        WHERE {TRAIN} AND f.is_mayhem ORDER BY t.mint, t.slot, t.recv""").df()
    same = d.mint.eq(d.mint.shift())
    d["age"] = d.recv - d.ct
    lp = np.log(d.vsol / d.vtok / P0)
    d["lp_before"] = lp.shift().where(same)
    d["jump"] = lp - d.lp_before
    k = d.vsol * d.vtok
    kr = (k / k.shift()).where(same)
    d["rs_before"] = d.rsol.shift().where(same)
    ev["curve"] = {
        "k_ratio_nonagent_q001_01_50_99_999": q(kr[same & ~d.ag], [.001, .01, .5, .99, .999]),
        "k_ratio_agent_q01_50_99": q(kr[same & d.ag], [.01, .5, .99]),
        "abs_dvsol_over_sol_agent_q10_50_90": q(((d.vsol - d.vsol.shift()).abs() / d.sol)[same & d.ag], [.1, .5, .9]),
        "nonagent_sells_draining_99pct_of_real_sol": round(float((d.sol / d.rs_before > 0.99)[same & ~d.ag & ~d.buy].mean()), 4),
        "max_vtok": float(d.vtok.max()),
    }
    a = d[d.ag & same].copy()
    a["r"] = np.exp(a.jump) - 1
    g = d[d.ag].groupby("mint")
    ev["agent_activity"] = {
        "tokens": int(g.ngroups), "trades": int(d.ag.sum()),
        "trades_per_token_q10_50_90": q(g.size(), [.1, .5, .9]),
        "first_trade_age_s_q10_50_90": q(g.age.min(), [.1, .5, .9]),
        "last_trade_age_s_q10_50_90": q(g.age.max(), [.1, .5, .9]),
        "slot_gap_q10_50_90_99": q(a.groupby("mint").slot.diff().dropna(), [.1, .5, .9, .99]),
        "sol_size_q10_50_90_99": q(d.sol[d.ag], [.1, .5, .9, .99]), "sol_size_max": float(d.sol[d.ag].max()),
        "sol_bought": round(float(d.sol[d.ag & d.buy].sum()), 2), "sol_sold": round(float(d.sol[d.ag & ~d.buy].sum()), 2),
        "real_sol_before_agent_trade_q10_50_90": q(a.rs_before, [.1, .5, .9]),
    }
    last = d[d.ag].groupby("mint").tail(1)
    ev["agent_activity"]["real_sol_after_last_agent_trade_q10_50_90"] = q(last.rsol, [.1, .5, .9])
    a["prev"] = a.groupby("mint").buy.shift()
    a["prev_tape"] = np.where(d.ag.shift()[a.index], "agent", "other") + "_" + np.where(d.buy.shift()[a.index], "buy", "sell")
    a["idx"] = a.groupby("mint").cumcount()
    ev["direction"] = {
        "p_buy_all": round(float(a.buy.mean()), 4),
        "by_price_level_vs_launch_log": grp(a, pd.cut(a.lp_before, [-20, -3, -1, -0.2, 0, 0.2, 1, 3])),
        "by_previous_agent_action": grp(a, a.prev.astype(str)),
        "by_previous_tape_trade": grp(a, a.prev_tape),
        "by_slot_mod2": grp(a, a.slot % 2),
        "by_agent_trade_index": grp(a, pd.cut(a.idx, [-1, 0, 2, 10, 50, 600])),
        "by_age_s": grp(a, pd.cut(a.age, [0, 10, 60, 300, 3600, 1e6])),
        "by_real_sol_octile": grp(a, pd.qcut(a.rs_before, 8, duplicates="drop")),
    }
    ev["jump"] = {
        "log_jump_buy_q05_50_95": q(a.jump[a.buy], [.05, .5, .95]),
        "log_jump_sell_q05_50_95": q(a.jump[~a.buy], [.05, .5, .95]),
        "mean_arith_return_per_agent_trade": round(float(a.r.mean()), 5),
        "se": round(float(a.r.std() / np.sqrt(len(a))), 5),
        "median_log_jump_by_sol_sextile_buy": {str(k): round(float(v), 4) for k, v in a[a.buy].groupby(pd.qcut(a.sol, 6), observed=True).jump.median().items()},
    }
    # do other wallets anticipate the agent's next direction?
    agb = pd.Series(np.where(d.ag, d.buy.astype(float), np.nan), index=d.index)
    d["next_agent_buy"] = agb.groupby(d.mint).shift(-1).groupby(d.mint).bfill()
    o = d[~d.ag]
    top = o.groupby("usr").mint.nunique().sort_values(ascending=False).head(10).index
    ev["others_anticipation"] = {
        u_: {"n": int((o.usr == u_).sum()),
             "p_next_agent_buy_after_their_buy": round(float(o[(o.usr == u_) & o.buy].next_agent_buy.mean()), 3),
             "p_next_agent_buy_after_their_sell": round(float(o[(o.usr == u_) & ~o.buy].next_agent_buy.mean()), 3)}
        for u_ in top}
    (ROOT / "research/observations/evidence_mayhem_agent.json").write_text(json.dumps(ev, indent=1, default=str))
    print(json.dumps({k: v for k, v in ev.items() if k != "top_wallets_by_mayhem_mints"}, indent=1, default=str))
