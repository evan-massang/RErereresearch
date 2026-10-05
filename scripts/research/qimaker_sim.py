"""H-QIMAKER simulator: queue-imbalance-gated passive quoting on Hyperliquid perps.

Pre-registration: reports/hypotheses/qimaker_preregistration.json (incl. amendment_1).
Imports hlanchor_lib read-only (taker_fill, lot_pnl, bar_stats, fees); does not modify it.

Usage:
  python scripts/research/qimaker_sim.py train            # all 12 configs on train
  python scripts/research/qimaker_sim.py valid CFG        # the ONE selected config, once
  python scripts/research/qimaker_sim.py train CFG --through-only   # informational sensitivity
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import hlanchor_lib as L  # noqa: E402  (read-only)
from hlanchor_fetch import TRAIN, VALID  # noqa: E402
from qimaker_coins import min_tick, tick_arr  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PQ_OLD = ROOT / "data/raw/web/tardis/parquet"
PQ_NEW = ROOT / "data/raw/web/tardis/parquet_qimaker"
OUT = ROOT / "data/raw/web/tardis/results/qimaker"
OUT.mkdir(parents=True, exist_ok=True)
COINS = {"BTC": PQ_NEW, "ETH": PQ_NEW, "SOL": PQ_NEW, "PUMP": PQ_OLD}  # PUMP: validation only (no train data)
LAT = 300 * L.MS
INF = 1 << 62

CONFIGS = {}
for th in (0.5, 0.7, 0.85):
    for T in (5, 30):
        for stop in (False, True):
            CONFIGS[f"th{th}_T{T}_{'stop2' if stop else 'nostop'}"] = dict(theta=th, T_s=T, stop_ticks=2 if stop else None)


def load(coin: str, day: str):
    pq = COINS[coin]
    fq, ft = pq / f"quotes_{day}_{coin}.parquet", pq / f"trades_{day}_{coin}.parquet"
    if not (fq.exists() and ft.exists()):
        return None
    q = pd.read_parquet(fq)
    q = q[(q.bid_price > 0) & (q.ask_price > q.bid_price) & (q.bid_amount > 0) & (q.ask_amount > 0)]
    t = pd.read_parquet(ft).sort_values("timestamp")
    mt = min_tick(q)
    qx = q.sort_values("timestamp")
    e = np.zeros(1)
    d = L.Day(coin, day, e, e, qx.timestamp.to_numpy(np.int64), qx.local_timestamp.to_numpy(np.int64),
              qx.bid_price.to_numpy(float), qx.ask_price.to_numpy(float), qx.bid_amount.to_numpy(float),
              qx.ask_amount.to_numpy(float), t.timestamp.to_numpy(np.int64), t.local_timestamp.to_numpy(np.int64),
              t.price.to_numpy(float), 0, e)
    ql = q.sort_values("local_timestamp")
    snap = dict(tl=ql.local_timestamp.to_numpy(np.int64), b=ql.bid_price.to_numpy(float),
                a=ql.ask_price.to_numpy(float), bq=ql.bid_amount.to_numpy(float), aq=ql.ask_amount.to_numpy(float))
    return d, snap, t.amount.to_numpy(float), mt


def same(x, y):
    return abs(x - y) <= 1e-9 * max(abs(x), abs(y))


def sim(coin, day, theta, T_s, stop_ticks, through_only=False):
    r = load(coin, day)
    if r is None:
        return None
    d, s, tamt, mt = r
    mid = (s["b"] + s["a"]) / 2
    tick = tick_arr(mid, mt)
    one_tick = np.abs((s["a"] - s["b"]) / tick - 1) < 1e-6
    I = (s["bq"] - s["aq"]) / (s["bq"] + s["aq"])
    n_dec, n_tr = len(s["tl"]), len(d.tt_x)
    # merged timeline: decisions at local ts, prints at exchange ts (as hlanchor_lib)
    ev_t = np.concatenate([s["tl"], d.tt_x])
    ev_k = np.concatenate([np.zeros(n_dec, np.int8), np.ones(n_tr, np.int8)])
    ev_i = np.concatenate([np.arange(n_dec), np.arange(n_tr)])
    o = np.lexsort((ev_k, ev_t))
    ev_t, ev_k, ev_i = ev_t[o].tolist(), ev_k[o].tolist(), ev_i[o].tolist()
    tpx, tl_tr, tq = d.tpx.tolist(), d.tt_l.tolist(), tamt.tolist()
    sb, sa, sbq, saq, smid, stk = s["b"].tolist(), s["a"].tolist(), s["bq"].tolist(), s["aq"].tolist(), mid.tolist(), tick.tolist()
    Il, onel = I.tolist(), one_tick.tolist()

    def arrival_check(side, px, t_arr, q_dec):
        """Exchange-side: post-only reject + queue ahead at arrival."""
        j = np.searchsorted(d.ht_x, t_arr, "right") - 1
        if j < 0:
            return False, q_dec
        b, a = d.hbid[j], d.hask[j]
        if side > 0:
            if a <= px + 1e-12 * px:
                return False, 0.0
            q0 = d.hbq[j] if same(b, px) else q_dec
        else:
            if b >= px - 1e-12 * px:
                return False, 0.0
            q0 = d.haq[j] if same(a, px) else q_dec
        return True, float(q0)

    def new_order(side, px, t, role, q_dec):
        ok, q0 = arrival_check(side, px, t + LAT, q_dec)
        return dict(side=side, px=px, frm=t + LAT, until=(INF if ok else t + LAT), ok=ok, q0=q0,
                    qty=L.UNIT_USD / px, cum=0.0, role=role, filled=False, rejected=not ok)

    entry = None   # live/cancelling entry order
    exits: list[dict] = []
    pos = None     # dict(side, px, tf, known)
    pend = None    # pending taker exit: dict(deadline, px, ts, why)
    trades, fills, signals = [], [], []
    n_orders = n_reject = 0
    prev_sig = 0

    def close(px, ts, fee_out, why):
        nonlocal pos
        trades.append(dict(coin=coin, day=day, side=pos["side"], entry_px=pos["px"], exit_px=px,
                           entry_t=pos["tf"], exit_t=ts, why=why, hold_s=(ts - pos["tf"]) / 1e6,
                           pnl=L.lot_pnl(pos["side"], pos["px"], px, L.MAKER_BP, fee_out)))
        pos = None

    for t, k, i in zip(ev_t, ev_k, ev_i):
        if pend is not None and t >= pend["deadline"]:
            if pos is not None:
                close(pend["px"], pend["ts"], L.TAKER_BP, pend["why"])
            exits = []
            pend = None
        if k == 1:  # print at exchange time t
            px, qty = tpx[i], tq[i]
            for od in ([entry] if entry is not None else []) + exits:
                if od["filled"] or not od["ok"] or not (od["frm"] <= t < od["until"]):
                    continue
                sd, p = od["side"], od["px"]
                through = (sd > 0 and px < p and not same(px, p)) or (sd < 0 and px > p and not same(px, p))
                hit = through
                if not through and same(px, p) and not through_only:
                    od["cum"] += qty
                    hit = od["cum"] > od["q0"] + od["qty"]
                if not hit:
                    continue
                od["filled"] = True
                od["until"] = t
                if od["role"] == "entry":
                    if pos is None:
                        pos = dict(side=sd, px=p, tf=t, known=tl_tr[i], why="through" if through else "queue")
                        fills.append(dict(coin=coin, day=day, side=sd, px=p, t=t, how=pos["why"]))
                    entry = None
                elif pos is not None:
                    close(p, t, L.MAKER_BP, "maker_exit")
                    exits = []
                    pend = None
            if entry is not None and entry["until"] <= t:
                entry = None
            continue
        # decision at local time t on snapshot i
        Ii, tk = Il[i], stk[i]
        sig = 1 if (Ii >= theta and onel[i]) else (-1 if (Ii <= -theta and onel[i]) else 0)
        if sig != 0 and sig != prev_sig:
            signals.append(dict(t=t, side=sig, mid=smid[i], tick=tk))
        prev_sig = sig
        if entry is not None and entry["until"] <= t:
            entry = None
        if pos is None:
            if pend is not None:
                continue
            if entry is not None:
                if entry["until"] == INF:
                    sd = entry["side"]
                    touch = sb[i] if sd > 0 else sa[i]
                    if abs(Ii) < theta / 2 or sd * Ii < 0 or not same(touch, entry["px"]):
                        entry["until"] = t + LAT
                continue
            if sig != 0:
                px = sb[i] if sig > 0 else sa[i]
                entry = new_order(sig, px, t, "entry", sbq[i] if sig > 0 else saq[i])
                n_orders += 1
                n_reject += entry["rejected"]
            continue
        # in position
        if t < pos["known"] or pend is not None:
            continue
        sd = pos["side"]
        held = (t - pos["tf"]) / 1e6
        adverse = stop_ticks is not None and sd * (smid[i] - pos["px"]) <= -stop_ticks * tk + 1e-12
        if held >= T_s or adverse:
            fl = L.taker_fill(d, t + LAT, -sd, 1)
            for od in exits:
                od["until"] = min(od["until"], t + LAT)
            if fl is None:
                break
            pend = dict(deadline=t + LAT, px=fl[0], ts=fl[1], why="stop" if adverse and held < T_s else "timeout")
            continue
        xp = sa[i] if sd > 0 else sb[i]
        live = [od for od in exits if od["until"] == INF]
        if live and not same(live[0]["px"], xp):
            live[0]["until"] = t + LAT
            live = []
        exits = [od for od in exits if od["until"] > t]
        pending_reject = any(od["rejected"] and od["until"] > t for od in exits)
        if not live and not pending_reject:
            od = new_order(-sd, xp, t, "exit", saq[i] if sd > 0 else sbq[i])
            exits.append(od)
            n_orders += 1
            n_reject += od["rejected"]
    if pend is not None and pos is not None:
        close(pend["px"], pend["ts"], L.TAKER_BP, pend["why"])
    if pos is not None:
        j = len(d.ht_x) - 1
        close(d.hbid[j] if pos["side"] > 0 else d.hask[j], int(d.ht_x[j]), L.TAKER_BP, "eod")
    for f in fills:
        for h in (1, 5, 30):
            m = L.hl_mid_after(d, f["t"] + h * 1_000_000)
            f[f"mk{h}"] = f["side"] * (m / f["px"] - 1) * 1e4
    # signal markouts: mid change after signal onset (decision snapshot), local clock, ticks and bp
    sig_mk = []
    tl = s["tl"]
    for sg in signals:
        row = dict(side=sg["side"])
        for h in (1, 5, 30):
            j = np.searchsorted(tl, sg["t"] + h * 1_000_000, "left")
            if j < len(tl):
                dm = sg["side"] * (mid[j] - sg["mid"])
                row[f"bp{h}"] = dm / sg["mid"] * 1e4
                row[f"tk{h}"] = dm / sg["tick"]
        sig_mk.append(row)
    sm = pd.DataFrame(sig_mk)
    sig_summary = {c: float(sm[c].mean()) for c in sm.columns if c != "side"} if len(sm) else {}
    return dict(trades=trades, fills=fills, n_signals=len(signals), sig_sum=sig_summary,
                n_orders=n_orders, n_reject=n_reject, tick_bp=float(np.median(tick / mid) * 1e4))


def job(a):
    coin, day, name, through = a
    return coin, day, name, sim(coin, day, **CONFIGS[name], through_only=through)


def main(split, names, through=False):
    days = TRAIN if split == "train" else VALID
    jobs = [(c, d, n, through) for d in days for c in COINS for n in names]
    tr = {n: [] for n in names}
    fl = {n: [] for n in names}
    meta = {n: {"n_signals": 0, "n_orders": 0, "n_reject": 0, "sig": [], "tick_bp": {}} for n in names}
    cover = set()
    with ProcessPoolExecutor(3) as ex:
        for coin, day, n, r in ex.map(job, jobs, chunksize=1):
            if r is None:
                continue
            cover.add(f"{day}:{coin}")
            tr[n] += r["trades"]
            fl[n] += r["fills"]
            m = meta[n]
            m["n_signals"] += r["n_signals"]
            m["n_orders"] += r["n_orders"]
            m["n_reject"] += r["n_reject"]
            m["sig"].append(dict(coin=coin, day=day, n=r["n_signals"], **r["sig_sum"]))
            m["tick_bp"][f"{day}:{coin}"] = round(r["tick_bp"], 3)
    tag = f"{split}{'_throughonly' if through else ''}"
    summary = {}
    for n in names:
        T = pd.DataFrame(tr[n])
        F = pd.DataFrame(fl[n])
        st = L.bar_stats(T.pnl.tolist() if len(T) else [])
        m = meta[n]
        st.update(n_signals=m["n_signals"], n_orders=m["n_orders"], n_post_only_rejects=m["n_reject"],
                  n_entry_fills=len(F))
        if len(F):
            for h in (1, 5, 30):
                st[f"fill_markout{h}s_bp"] = round(float(F[f"mk{h}"].mean()), 3)
            st["entry_fill_how"] = F.how.value_counts().to_dict()
        S = pd.DataFrame(m["sig"])
        if len(S):
            w = S.n / S.n.sum()
            for c in ("bp1", "bp5", "bp30", "tk1", "tk5", "tk30"):
                if c in S:
                    st[f"signal_markout_{c}"] = round(float((S[c].fillna(0) * w).sum()), 3)
        if len(T):
            st["exit_mix"] = T.why.value_counts().to_dict()
            st["by_coin"] = {c: dict(n=len(g), net=round(g.pnl.sum(), 2)) for c, g in T.groupby("coin")}
            st["by_day"] = {dd: dict(n=len(g), net=round(g.pnl.sum(), 2)) for dd, g in T.groupby("day")}
            st["days_positive"] = int((T.groupby("day").pnl.sum() > 0).sum())
            st["days"] = int(T.day.nunique())
            st["gross_mean_bp_before_fees"] = round(float((T.side * (T.exit_px / T.entry_px - 1)).mean() * 1e4), 3)
            st["median_hold_s"] = round(float(T.hold_s.median()), 2)
            T.to_parquet(OUT / f"{tag}_{n}.parquet", index=False)
        st["tick_bp_median_by_coinday"] = m["tick_bp"]
        summary[n] = st
        print(n, json.dumps({k: v for k, v in st.items() if k not in ("by_day", "tick_bp_median_by_coinday")}), flush=True)
    json.dump(dict(coverage=sorted(cover), summary=summary), open(OUT / f"summary_{tag}.json", "w"), indent=1, default=str)
    return summary


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0], args[1:] or list(CONFIGS), through="--through-only" in sys.argv)
