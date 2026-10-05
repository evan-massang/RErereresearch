"""Simulators for H-HLANCHOR (maker quotes on HL around Binance-implied fair) and H-HLLAG
(HL taker after a fast Binance move).

Clocks: decisions use Tardis `local_timestamp` (what a co-located recorder saw). Our orders reach
HL at decision + latency, and that arrival time is compared with HL *exchange* timestamps
(exchange clock runs ~150-200 ms behind local). This adds latency on top of the stated value,
so it is conservative.

Fill model (conservative):
  * maker: fills only when an HL trade prints STRICTLY through our price while the order is live
    (exchange ts >= arrival). Any print strictly through our level implies the level was swept,
    so we are filled regardless of queue position (queue haircut: prints AT our price never fill).
    Cancels take 300 ms; a stale quote can still be hit in that window.
  * taker: fills at the first HL top-of-book snapshot with exchange ts >= decision + latency.
    Buys pay the ask, sells hit the bid. If the order size exceeds displayed top size, the excess
    fills one full spread worse (no depth data -> pessimistic proxy).
  * fees: HL tier-0 maker 1.5 bp, taker 4.5 bp per side (HL fee docs, cited in the leads file).
  * funding ignored (holding times are seconds).
Inventory: at most 2 units of $1,000 per coin; positions are flattened by taker at day end.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PQ = ROOT / "data/raw/web/tardis/parquet"

MAKER_BP = 1.5
TAKER_BP = 4.5
UNIT_USD = 1000.0
MAX_UNITS = 2
MS = 1000  # µs per ms


@dataclass
class Day:
    coin: str
    day: str
    # binance (local ts, mid)
    bt: np.ndarray
    bmid: np.ndarray
    # HL top of book
    ht_x: np.ndarray  # exchange ts
    ht_l: np.ndarray  # local ts
    hbid: np.ndarray
    hask: np.ndarray
    hbq: np.ndarray
    haq: np.ndarray
    # HL trades
    tt_x: np.ndarray
    tt_l: np.ndarray
    tpx: np.ndarray
    # basis on 1-s grid (trailing 10-min median, known at start of second)
    b_sec0: int
    basis: np.ndarray


def load_day(coin: str, day: str) -> Day | None:
    fq, ft, fb = (PQ / f"{k}_{day}_{coin}.parquet" for k in ("quotes", "trades", "book_ticker"))
    if not (fq.exists() and ft.exists() and fb.exists()):
        return None
    q = pd.read_parquet(fq).sort_values("local_timestamp")
    q = q[(q.bid_price > 0) & (q.ask_price > q.bid_price)]
    t = pd.read_parquet(ft).sort_values("timestamp")
    b = pd.read_parquet(fb).sort_values("local_timestamp")
    b = b[(b.bid_price > 0) & (b.ask_price >= b.bid_price)]
    bt = b.local_timestamp.to_numpy(np.int64)
    bmid = ((b.bid_price + b.ask_price) / 2).to_numpy(float)
    hl_l = q.local_timestamp.to_numpy(np.int64)
    hmid = ((q.bid_price + q.ask_price) / 2).to_numpy(float)
    # basis on a 1-s grid, point in time: value for second s uses data with local ts <= s
    s0 = int(max(bt[0], hl_l[0]) // 1_000_000) + 1
    s1 = int(min(bt[-1], hl_l[-1]) // 1_000_000)
    grid = np.arange(s0, s1 + 1, dtype=np.int64) * 1_000_000
    bi = np.searchsorted(bt, grid, "right") - 1
    hi = np.searchsorted(hl_l, grid, "right") - 1
    raw = hmid[hi] / bmid[bi] - 1.0
    # trailing median of the PREVIOUS 600 seconds (excludes current second)
    med = pd.Series(raw).rolling(600, min_periods=600).median().shift(1).to_numpy()
    # HL quotes sorted by exchange ts for fill lookups
    qx = q.sort_values("timestamp")
    return Day(coin, day, bt, bmid,
               qx.timestamp.to_numpy(np.int64), qx.local_timestamp.to_numpy(np.int64),
               qx.bid_price.to_numpy(float), qx.ask_price.to_numpy(float),
               qx.bid_amount.to_numpy(float), qx.ask_amount.to_numpy(float),
               t.timestamp.to_numpy(np.int64), t.local_timestamp.to_numpy(np.int64),
               t.price.to_numpy(float), s0, med)


def basis_at(d: Day, ts: np.ndarray) -> np.ndarray:
    idx = (ts // 1_000_000) - d.b_sec0
    out = np.full(len(ts), np.nan)
    ok = (idx >= 0) & (idx < len(d.basis))
    out[ok] = d.basis[idx[ok]]
    return out


def taker_fill(d: Day, t_arrive: int, side: int, units: int) -> tuple[float, int] | None:
    """side=+1 buy, -1 sell. Returns (avg price, exchange ts) or None if no snapshot left."""
    j = np.searchsorted(d.ht_x, t_arrive, "left")
    if j >= len(d.ht_x):
        return None
    bid, ask = d.hbid[j], d.hask[j]
    spread = ask - bid
    px, qty_top = (ask, d.haq[j]) if side > 0 else (bid, d.hbq[j])
    qty = units * UNIT_USD / px
    if qty <= qty_top:
        return px, int(d.ht_x[j])
    worse = px + side * spread
    avg = (qty_top * px + (qty - qty_top) * worse) / qty
    return avg, int(d.ht_x[j])


def hl_mid_after(d: Day, ts: int) -> float:
    j = np.searchsorted(d.ht_x, ts, "left")
    if j >= len(d.ht_x):
        return np.nan
    return (d.hbid[j] + d.hask[j]) / 2


def lot_pnl(side, entry_px, exit_px, fee_in, fee_out, units=1):
    return units * (UNIT_USD * side * (exit_px / entry_px - 1.0) - UNIT_USD * (fee_in + fee_out) * 1e-4)


# ----------------------------------------------------------------------------------------------
# H-HLANCHOR
# ----------------------------------------------------------------------------------------------

def sim_anchor(d: Day, k_bp: float, T_s: float, lat_ms: int = 300, info_lat_ms: int = 300):
    k = k_bp * 1e-4
    LAT = lat_ms * MS
    # decision times: Binance updates become usable info_lat later; HL snapshots; trade learn times
    dec = np.concatenate([d.bt + info_lat_ms * MS, d.ht_l, d.tt_l])
    dec = np.unique((dec // (100 * MS) + 1) * (100 * MS))  # 100-ms decision clock
    bi = np.searchsorted(d.bt, dec - info_lat_ms * MS, "right") - 1
    bi2 = np.searchsorted(d.bt, dec - info_lat_ms * MS - 2000 * MS, "right") - 1
    hi = np.searchsorted(d.ht_l, dec, "right") - 1
    ok = (bi2 >= 0) & (hi >= 0)
    dec, bi, bi2, hi = dec[ok], bi[ok], bi2[ok], hi[ok]
    bas = basis_at(d, dec)
    ok = ~np.isnan(bas)
    dec, bi, bi2, hi, bas = dec[ok], bi[ok], bi2[ok], hi[ok], bas[ok]
    F = d.bmid[bi] * (1 + bas)
    r2 = np.abs(d.bmid[bi] / d.bmid[bi2] - 1)
    # HL quote known at decision time (quotes array is exchange-sorted; map local idx)
    order_l = np.argsort(d.ht_l, kind="stable")
    hk = order_l[hi]
    kb, ka = d.hbid[hk], d.hask[hk]
    # merge events: decisions keyed by local time, trades keyed by exchange time
    ev_t = np.concatenate([dec, d.tt_x])
    ev_k = np.concatenate([np.zeros(len(dec), np.int8), np.ones(len(d.tt_x), np.int8)])
    ev_i = np.concatenate([np.arange(len(dec)), np.arange(len(d.tt_x))])
    o = np.lexsort((ev_k, ev_t))
    ev_t, ev_k, ev_i = ev_t[o].tolist(), ev_k[o].tolist(), ev_i[o].tolist()
    Fl, r2l, kbl, kal = F.tolist(), r2.tolist(), kb.tolist(), ka.tolist()
    tpx = d.tpx.tolist()

    # orders: dict(side, px, live_from, live_until, role) ; role 'entry' or 'exit'
    orders: list[dict] = []
    lots: list[list] = []  # [side, px, te, fee_in]
    trades, fills = [], []
    F_entry_ref = None  # F at last entry quote placement
    exit_ref = None
    INF = 1 << 62

    def cancel(role, t):
        for od in orders:
            if od["role"] == role and od["until"] > t + LAT:
                od["until"] = t + LAT

    def live(role, t):
        return [od for od in orders if od["role"] == role and od["until"] > t + LAT]

    def close_all(px, te, fee_out, why):
        for side, epx, ete, fin in lots:
            trades.append(dict(coin=d.coin, day=d.day, side=side, entry_px=epx, exit_px=px,
                               entry_t=ete, exit_t=te, why=why,
                               pnl=lot_pnl(side, epx, px, fin, fee_out)))
        lots.clear()

    for t, kind, i in zip(ev_t, ev_k, ev_i):
        if kind == 1:  # HL trade at exchange time t
            px = tpx[i]
            for od in orders:
                if od["filled"] or not (od["from"] <= t < od["until"]):
                    continue
                s, p = od["side"], od["px"]
                if (s > 0 and px < p) or (s < 0 and px > p):
                    od["filled"] = True
                    od["until"] = t
                    if od["role"] == "entry":
                        if len(lots) and lots[0][0] != s:  # opposite stale entry closes a lot
                            lot = lots.pop(0)
                            trades.append(dict(coin=d.coin, day=d.day, side=lot[0], entry_px=lot[1],
                                               exit_px=p, entry_t=lot[2], exit_t=t, why="opp_entry",
                                               pnl=lot_pnl(lot[0], lot[1], p, lot[3], MAKER_BP)))
                        else:  # stale same-side fill can exceed the limit; count it honestly
                            lots.append([s, p, t, MAKER_BP])
                            fills.append(dict(coin=d.coin, day=d.day, side=s, px=p, t=t))
                    else:
                        close_all(p, t, MAKER_BP, "maker_exit")
            orders = [od for od in orders if not od["filled"] and od["until"] > t]
            continue
        # decision at local time t
        f, r, hb, ha = Fl[i], r2l[i], kbl[i], kal[i]
        if not lots:
            cancel("exit", t)
            exit_ref = None
            if r > k:
                cancel("entry", t)
                F_entry_ref = None
                continue
            cur = live("entry", t)
            if (not cur) or F_entry_ref is None or abs(f / F_entry_ref - 1) > k / 2:
                cancel("entry", t)
                F_entry_ref = f
                bp, ap = f * (1 - k), f * (1 + k)
                if bp < ha:  # post-only
                    orders.append(dict(side=1, px=bp, role="entry", **{"from": t + LAT}, until=INF, filled=False))
                if ap > hb:
                    orders.append(dict(side=-1, px=ap, role="entry", **{"from": t + LAT}, until=INF, filled=False))
            continue
        # in position
        cancel("entry", t)
        F_entry_ref = None
        side = lots[0][0]
        avg = sum(l[1] for l in lots) / len(lots)
        hm = (hb + ha) / 2
        adverse = side * (hm / avg - 1) < -3 * k
        timeout = t - lots[0][2] > T_s * 1_000_000
        if adverse or timeout:
            cancel("exit", t)
            orders = [od for od in orders if od["role"] != "exit"]  # taker replaces maker exit
            fl = taker_fill(d, t + LAT, -side, len(lots))
            if fl is None:
                break
            close_all(fl[0], fl[1], TAKER_BP, "stop" if adverse else "timeout")
            exit_ref = None
            continue
        # post-only maker exit at fair; if fair is through the HL touch, rest at the touch instead
        xp = max(f, ha) if side > 0 else min(f, hb)
        cur = live("exit", t)
        if (not cur) or exit_ref is None or abs(xp / exit_ref - 1) > k / 2:
            cancel("exit", t)
            exit_ref = xp
            orders.append(dict(side=-side, px=xp, role="exit", **{"from": t + LAT}, until=INF, filled=False))
    if lots:  # end of day flatten at last snapshot
        j = len(d.ht_x) - 1
        side = lots[0][0]
        px = d.hbid[j] if side > 0 else d.hask[j]
        close_all(px, int(d.ht_x[j]), TAKER_BP, "eod")
    for fl in fills:
        for h in (1, 5, 30):
            m = hl_mid_after(d, fl["t"] + h * 1_000_000)
            fl[f"mk{h}"] = fl["side"] * (m / fl["px"] - 1) * 1e4
    return trades, fills


# ----------------------------------------------------------------------------------------------
# H-HLLAG
# ----------------------------------------------------------------------------------------------

def sim_lag(d: Day, theta_bp: float, L_ms: int, H_s: float, cooldown_s: float = 10.0,
            close_bp: float = 2.0, info_lat_ms: int = 300):
    th = theta_bp * 1e-4
    L = L_ms * MS
    # Binance 2-s return at each Binance event (local clock)
    j2 = np.searchsorted(d.bt, d.bt - 2_000_000, "right") - 1
    okj = j2 >= 0
    ret = np.full(len(d.bt), 0.0)
    ret[okj] = d.bmid[okj] / d.bmid[j2[okj]] - 1
    cand = np.where(np.abs(ret) > th)[0]
    order_l = np.argsort(d.ht_l, kind="stable")
    hl_l_sorted = d.ht_l[order_l]
    hmid_l = ((d.hbid + d.hask) / 2)[order_l]
    hx_mid = (d.hbid + d.hask) / 2
    trades = []
    last_sig = -10**18
    open_until: list[int] = []
    for c in cand.tolist():
        t = int(d.bt[c])
        if t - last_sig < cooldown_s * 1_000_000:
            continue
        a = np.searchsorted(hl_l_sorted, t, "right") - 1
        b0 = np.searchsorted(hl_l_sorted, t - 2_000_000, "right") - 1
        if a < 0 or b0 < 0:
            continue
        s = 1 if ret[c] > 0 else -1
        hret = hmid_l[a] / hmid_l[b0] - 1
        if s * hret >= th / 2:
            continue
        bas = basis_at(d, np.array([t]))[0]
        if np.isnan(bas):
            continue
        last_sig = t
        open_until = [x for x in open_until if x > t]
        if len(open_until) >= MAX_UNITS:
            continue
        ent = taker_fill(d, t + L, s, 1)
        if ent is None:
            break
        epx, ete = ent
        # exit: check HL snapshots (local clock) after entry for gap close, else at H seconds
        start = np.searchsorted(hl_l_sorted, ete, "right")
        deadline = ete + int(H_s * 1_000_000)
        exit_dec, why = deadline, "time"
        k = start
        while close_bp is not None and k < len(hl_l_sorted) and hl_l_sorted[k] < deadline:
            tl = int(hl_l_sorted[k])
            bi = np.searchsorted(d.bt, tl - info_lat_ms * MS, "right") - 1
            fair = d.bmid[bi] * (1 + bas)
            if s * (fair / hmid_l[k] - 1) <= close_bp * 1e-4:
                exit_dec, why = tl, "closed"
                break
            k += 1
        ex = taker_fill(d, exit_dec + L, -s, 1)
        if ex is None:
            break
        xpx, xte = ex
        open_until.append(xte)
        m = {}
        for h in (1, 5, 30):
            jj = np.searchsorted(d.ht_x, ete + h * 1_000_000, "left")
            m[f"mk{h}"] = s * (hx_mid[jj] / epx - 1) * 1e4 if jj < len(d.ht_x) else np.nan
        trades.append(dict(coin=d.coin, day=d.day, side=s, entry_px=epx, exit_px=xpx, entry_t=ete,
                           exit_t=xte, why=why, binret_bp=ret[c] * 1e4, hlret_bp=hret * 1e4,
                           pnl=lot_pnl(s, epx, xpx, TAKER_BP, TAKER_BP), **m))
    return trades


def bar_stats(pnl: list[float]) -> dict:
    p = np.array(pnl, float)
    n = len(p)
    if n == 0:
        return dict(n=0, net=0.0, pf=None, net_ex_top3=0.0, passes=False)
    gw, gl = p[p > 0].sum(), -p[p < 0].sum()
    pf = float(gw / gl) if gl > 0 else float("inf")
    ex3 = float(np.sort(p)[:-3].sum()) if n > 3 else 0.0
    net = float(p.sum())
    return dict(n=n, net=round(net, 2), mean=round(net / n, 3), pf=round(pf, 3),
                net_ex_top3=round(ex3, 2), win=round(float((p > 0).mean()), 3),
                passes=bool(n >= 50 and net > 0 and pf > 1.2 and ex3 > 0))
