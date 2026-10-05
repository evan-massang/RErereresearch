"""H-SOLLEAD step 2: buy the most liquid active tokens right after a SOL/USD jump, exit after N minutes.

Pre-registered grid (12 configs, fixed before any trade was scored):
  venue in {curve, amm} x SOL lookback h in {1, 3} min x hold N in {2, 5, 10} min.
Signal: SOL log return over klines t-h+1..t >= train 99th percentile (from SOL data in train minutes only),
  10-minute cooldown between signals. Known at the close of kline t, i.e. time t+60.
Universe at t+60 (point-in-time, minute buckets t-4..t only): top K=5 by trailing-5-min SOL volume among
  - curve: trusted, non-Mayhem, not-yet-complete tokens with >= 10 trades in the window and a trade in bucket t;
  - amm: non-Mayhem pools with >= 10 trades in the window, a trade in bucket t and true SOL reserve >= 50.
Fills: entry at state <= t+60+1 s (latency 1 s); exit decision at entry + N min, fill 1 s later.
  curve: event_studies.rt() exact curve math, 1.25% fee per side, trusted states only, exits capped at the
  last state before completion. amm: amm_flow_lib.round_trip() (true reserve = logged + 17.585, fee_bps per side,
  conservative state choice). 0.5 SOL, tips 0.001 / 0.01 SOL per tx (2 tx).
Baseline (not a config, for interpretation): the same universe and exits at every 10th train minute.
Validation is scored only for configs passing the full bar on train at tip 0.001, once.

    python scripts/research/sollead_sim.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sollead_lib as L  # noqa: E402
import amm_flow_lib as A  # noqa: E402
from event_studies import rt as curve_rt  # noqa: E402

OUT = L.ROOT / "research" / "observations" / "evidence_sollead_sim.json"
K, MIN_TR, LAT, COOL = 5, 10, 1.0, 600
HS, NS, TIPS = (1, 3), (2, 5, 10), (0.001, 0.01)


def signals(sol: pd.DataFrame, h: int, thr: float, split: str) -> list:
    sh = sol.r1.rolling(h, min_periods=h).sum()
    # require h consecutive minutes
    cons = pd.Series(sol.index, index=sol.index).diff(h - 1).fillna(0) == 60 * (h - 1) if h > 1 else True
    hit = (sh >= thr) & cons
    ts, last = [], -1e18
    for t in sh.index[hit.to_numpy()]:
        if L.split_of([t + 60 + max(NS) * 60 + 5])[0] != split or L.split_of([t])[0] != split:
            continue
        if t - last >= COOL:
            ts.append(int(t))
            last = t
    return ts


def universe(panel: pd.DataFrame, t: int, venue: str) -> list:
    w = panel[(panel.m >= t - 240) & (panel.m <= t)]
    g = w.groupby("mint").agg(n=("n", "sum"), vol=("vol", "sum"), last_m=("m", "max"))
    g = g[(g.n >= MIN_TR) & (g.last_m == t)]
    if venue == "amm":
        rs = w.sort_values("m").groupby("mint").rs_last.last()
        g = g[rs.reindex(g.index) >= 50]
    return list(g.sort_values("vol", ascending=False).index[:K])


class CurveBook:
    def __init__(self, con):
        self.con, self.cache = con, {}
        self.comp = dict(con.execute("SELECT mint, min(recv) FROM curve_completes GROUP BY 1").fetchall())

    def preload(self, mints):
        if not mints:
            return
        self.con.register("want", pd.DataFrame({"mint": mints}))
        d = self.con.execute(f"""SELECT mint, recv, vsol, vtok FROM curve_trades WHERE mint IN (SELECT mint FROM want)
                                 AND {L.ALLOWED} AND abs(vsol - rsol - 30) < 0.01 AND vtok > 0""").df()
        for m, g in d.sort_values(["mint", "recv"], kind="stable").groupby("mint"):
            self.cache[m] = (g.recv.to_numpy(), g.vsol.to_numpy(), g.vtok.to_numpy())

    def pnl(self, mint, t0, n):
        if mint not in self.cache:
            x = self.con.execute(f"""SELECT recv, vsol, vtok FROM curve_trades WHERE mint = ? AND {L.ALLOWED}
                                     AND abs(vsol - rsol - 30) < 0.01 AND vtok > 0 ORDER BY recv""", [mint]).fetchnumpy()
            self.cache[mint] = (x["recv"], x["vsol"], x["vtok"])
        T, vs, vt = self.cache[mint]
        te = t0 + LAT
        k = np.searchsorted(T, te, side="right")
        if k == 0:
            return np.nan
        tx = te + n * 60 + LAT
        e = np.searchsorted(T, tx, side="right")
        tc = self.comp.get(mint)
        if tc is not None:
            e = min(e, np.searchsorted(T, tc, side="left"))
        e = max(e, k)
        return curve_rt(vs[k - 1], vt[k - 1], vs[e - 1], vt[e - 1])


class AmmBook:
    def __init__(self, con):
        self.con, self.cache = con, {}

    def preload(self, pools):
        if not pools:
            return
        self.con.register("want", pd.DataFrame({"pool": pools}))
        d = self.con.execute(f"""SELECT pool, recv, hash(usr) u, buy, tok, sol, pool_tok_logged rt, pool_sol_logged rs_log,
                                 fee_bps FROM amm_trades WHERE pool IN (SELECT pool FROM want) AND {L.ALLOWED}
                                 AND tok > 0 AND sol > 0""").df()
        for m, g in d.sort_values(["pool", "recv"], kind="stable").groupby("pool"):
            self.cache[m] = A.pool_arrays(g)

    def pnl(self, pool, t0, n):
        if pool not in self.cache:
            g = self.con.execute(f"""SELECT recv, hash(usr) u, buy, tok, sol, pool_tok_logged rt, pool_sol_logged rs_log,
                                     fee_bps FROM amm_trades WHERE pool = ? AND {L.ALLOWED} AND tok > 0 AND sol > 0
                                     ORDER BY recv""", [pool]).df()
            self.cache[pool] = A.pool_arrays(g)
        a = self.cache[pool]
        te = t0 + LAT
        return float(A.round_trip(a, np.array([te]), np.array([te + n * 60 + LAT]))[0])


def run_times(times, panel, book, venue):
    rows = []
    uni = {t: universe(panel, t, venue) for t in times}
    book.preload(sorted({m for v in uni.values() for m in v} - set(book.cache)))
    for t in times:
        for m in uni[t]:
            r = {"t": t, "mint": m}
            for n in NS:
                r[f"N{n}"] = book.pnl(m, t + 60, n)
            rows.append(r)
    return pd.DataFrame(rows)


def main():
    sol = L.sol_minutes()
    tr_mask = L.split_of(sol.index.to_numpy()) == "train"
    con = L.connect()
    panels = {"curve": L.curve_minute_panel(con), "amm": L.amm_minute_panel(con)}
    books = {"curve": CurveBook(con), "amm": AmmBook(con)}
    res = {"grid": "venue{curve,amm} x h{1,3} x N{2,5,10}; K=5; tips 0.001/0.01", "configs": {}}
    thr = {}
    for h in HS:
        sh = sol.r1.rolling(h, min_periods=h).sum()
        thr[h] = float(sh[tr_mask].quantile(0.99))
    res["thresholds_train_p99"] = thr
    passing = []
    for venue in ("curve", "amm"):
        # minutes where the tape is live (index exists) — signals at dead-tape minutes yield no universe anyway
        base_t = [int(t) for t in sol.index[tr_mask][::10] if L.split_of([t + 60 + 660])[0] == "train"]
        bdf = run_times(base_t, panels[venue], books[venue], venue)
        for n in NS:
            res["configs"][f"BASELINE|{venue}|N{n}"] = {str(tip): A.stats(bdf[f"N{n}"].to_numpy(), tip) for tip in TIPS}
        for h in HS:
            ts = signals(sol, h, thr[h], "train")
            df = run_times(ts, panels[venue], books[venue], venue)
            for n in NS:
                key = f"{venue}|h{h}|N{n}"
                st = {str(tip): A.stats(df[f"N{n}"].to_numpy(), tip) for tip in TIPS} if len(df) else {}
                res["configs"][key] = {"n_signals_train": len(ts), "n_signals_with_universe": int(df.t.nunique()) if len(df) else 0,
                                       "train": st}
                print(key, len(ts), st.get("0.001"), flush=True)
                if st and A.passes(st["0.001"]):
                    passing.append((venue, h, n))
    for venue in ("curve", "amm"):
        for n in NS:
            print("BASELINE", venue, n, res["configs"][f"BASELINE|{venue}|N{n}"]["0.001"])
    res["passing_train"] = [f"{v}|h{h}|N{n}" for v, h, n in passing]
    for venue, h, n in passing:  # validation, once, only for train-passing configs
        ts = signals(sol, h, thr[h], "valid")
        df = run_times(ts, panels[venue], books[venue], venue)
        key = f"{venue}|h{h}|N{n}"
        res["configs"][key]["validation"] = {str(tip): A.stats(df[f"N{n}"].to_numpy(), tip) for tip in TIPS}
        res["configs"][key]["n_signals_valid"] = len(ts)
        print("VALID", key, res["configs"][key]["validation"])
    OUT.write_text(json.dumps(res, indent=1))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
