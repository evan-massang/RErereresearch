"""H-WICKNET simulator: deep resting post-only orders around a Binance-implied fair on HL meme perps.

Rules and fill model: reports/hypotheses/wicknet_preregistration.json (frozen before any run).
Imports hlanchor_lib read-only (load_day, basis_at, taker_fill, lot_pnl, bar_stats, fees).

Clocks: decisions on Tardis local time; our orders/cancels take effect at decision + 300 ms and are
compared with HL *exchange* timestamps (exchange runs ~175 ms behind local -> conservative).

Usage: python wicknet_sim.py train            # all 12 pre-registered configs on train
       python wicknet_sim.py valid <config>   # the single selected config on validation
"""
from __future__ import annotations

import heapq
import json
import math
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import hlanchor_lib as L  # noqa: E402  (read-only, frozen)
from hlanchor_fetch import COINS, TRAIN, VALID, HOLDOUT_START  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
BTC = ROOT / "data/raw/web/binance_spot/klines1s"
OUT = ROOT / "data/raw/web/tardis/results/wicknet"
MS = 1000
LAT = 300 * MS
TICK = 250 * MS
EPS = 1e-9
INF = 1 << 62

CONFIGS = {}
for d in (50, 100):
    for ex in ("MK", "TK"):
        for flt in ("off", "on"):
            CONFIGS[f"d{d}_R2_{ex}_{flt}"] = dict(d_bp=d, R_s=2, exit=ex, filt=flt == "on")
for d in (50, 100):
    for ex in ("MK", "TK"):
        CONFIGS[f"d{d}_R5_{ex}_on"] = dict(d_bp=d, R_s=5, exit=ex, filt=True)
assert len(CONFIGS) == 12


def tick_of(px: float) -> float:
    return 10.0 ** (math.floor(math.log10(px)) - 4)  # HL: 5 significant figures


def round_away(px: float, side: int) -> float:
    """bid (side +1) floored, ask (side -1) ceiled to 5 sig figs."""
    tk = tick_of(px)
    q = px / tk
    return (math.floor(q + 1e-9) if side > 0 else math.ceil(q - 1e-9)) * tk


def load_btc(day: str):
    df = pd.read_parquet(BTC / f"BTCUSDT_1s_{day}.parquet")
    known = df.open_time_us.to_numpy(np.int64) + 1_000_000  # close known at end of second
    return known, df.close.to_numpy(float)


def sim(coin: str, day: str, cfg: dict):
    assert day < HOLDOUT_START
    d = L.load_day(coin, day)
    if d is None:
        return None
    k = cfg["d_bp"] * 1e-4
    R = int(cfg["R_s"] * 1_000_000)
    mk_exit = cfg["exit"] == "MK"
    filt = cfg["filt"]
    H = (60 if mk_exit else 30) * 1_000_000
    bk_t, bk_c = load_btc(day)

    # local-sorted HL snapshots for decisions
    ol = np.argsort(d.ht_l, kind="stable")
    hl_l = d.ht_l[ol]
    hb_l, ha_l = d.hbid[ol], d.hask[ol]
    hx = d.ht_x
    hmid_x = (d.hbid + d.hask) / 2

    t0 = int(max(d.bt[0], hl_l[0], bk_t[0])) + 600 * 1_000_000
    t1 = int(min(d.bt[-1], hl_l[-1]))
    ticks = np.arange((t0 // TICK + 1) * TICK, t1, TICK, dtype=np.int64)
    bas = L.basis_at(d, ticks)
    bi = np.searchsorted(d.bt, ticks, "right") - 1
    F = d.bmid[bi] * (1 + bas)
    bi10 = np.searchsorted(d.bt, ticks - 10_000_000, "right") - 1
    r10 = np.abs(d.bmid[bi] / d.bmid[np.maximum(bi10, 0)] - 1)
    r10[bi10 < 0] = np.nan
    ki = np.searchsorted(bk_t, ticks, "right") - 1
    ki60 = np.searchsorted(bk_t, ticks - 60_000_000, "right") - 1
    rbtc = np.abs(bk_c[np.maximum(ki, 0)] / bk_c[np.maximum(ki60, 0)] - 1)
    rbtc[(ki < 0) | (ki60 < 0)] = np.nan
    hi = np.searchsorted(hl_l, ticks, "right") - 1
    blocked = np.zeros(len(ticks), bool)
    if filt:
        blocked = ~((rbtc < 30e-4) & (r10 < k / 2))  # NaN -> blocked
    Fl, Bl, hil = F.tolist(), blocked.tolist(), hi.tolist()
    tick_l = ticks.tolist()

    def F_at(t):
        b = np.searchsorted(d.bt, t, "right") - 1
        bs = L.basis_at(d, np.array([t]))[0]
        return d.bmid[b] * (1 + bs)

    def snap_local(t):
        j = int(np.searchsorted(hl_l, t, "right") - 1)
        return hb_l[j], ha_l[j]

    def snap_x(t):
        j = int(np.searchsorted(hx, t, "right") - 1)
        return (d.hbid[j], d.hask[j], d.hbq[j], d.haq[j]) if j >= 0 else None

    orders: list[dict] = []
    stats = dict(placed=0, rejected=0, fills_through=0, fills_queue=0, blocked_ticks=int(blocked.sum()),
                 ticks=len(ticks))

    def place(side, px, t_dec, role):
        """post-only order arriving at t_dec + LAT; returns the order or None if rejected."""
        arr = t_dec + LAT
        s = snap_x(arr)
        if s is None:
            return None
        bb, ba, bq, aq = s
        stats["placed"] += 1
        if (side > 0 and px >= ba * (1 - EPS)) or (side < 0 and px <= bb * (1 + EPS)):
            stats["rejected"] += 1
            return None
        touch, tq = (bb, bq) if side > 0 else (ba, aq)
        if abs(px - touch) <= EPS * px:
            queue = tq
        elif (side > 0 and px > touch) or (side < 0 and px < touch):
            queue = 0.0
        else:
            queue = None  # behind the touch: unknown queue -> trade-through only
        od = dict(side=side, px=px, frm=arr, until=INF, role=role, queue=queue, cum=0.0,
                  qty=L.UNIT_USD / px, filled=False)
        orders.append(od)
        return od

    def cancel(od, t_dec):
        if od["until"] > t_dec + LAT:
            od["until"] = t_dec + LAT

    pos = None  # dict(side, px, t_fill, t_learn, exit_order, pending_taker)
    trades, fills = [], []
    last_place_F = None
    heap: list = []  # scheduled taker executions (time, seq)
    seq = 0

    def close(px, t, fee_out, why):
        nonlocal pos
        trades.append(dict(coin=coin, day=day, side=pos["side"], entry_px=pos["px"], exit_px=px,
                           entry_t=pos["t_fill"], exit_t=t, why=why,
                           pnl=L.lot_pnl(pos["side"], pos["px"], px, L.MAKER_BP, fee_out)))
        if pos["exit_order"] is not None:
            cancel(pos["exit_order"], t - LAT)  # gone at once
            pos["exit_order"]["until"] = min(pos["exit_order"]["until"], t)
        pos = None

    def on_entry_fill(od, tx, tl, how):
        nonlocal pos, last_place_F
        stats["fills_" + how] += 1
        if pos is not None and pos["side"] != od["side"]:
            close(od["px"], tx, L.MAKER_BP, "opp_entry")
            return
        if pos is not None:  # same side cannot happen (one order per side)
            return
        side = od["side"]
        fills.append(dict(coin=coin, day=day, side=side, px=od["px"], t=tx, how=how))
        for o in orders:
            if o["role"] == "entry" and o is not od:
                cancel(o, tl)
        last_place_F = None
        pos = dict(side=side, px=od["px"], t_fill=tx, t_learn=tl, exit_order=None, pending=False)
        if mk_exit:
            f = F_at(tl)
            bb, ba = snap_local(tl)
            if side > 0:
                x = round_away(f, -1) if f > bb else ba
            else:
                x = round_away(f, 1) if f < ba else bb
            eo = place(-side, x, tl, "exit")
            if eo is None:  # would cross at arrival: re-post at the far touch, one more latency
                s = snap_x(tl + LAT)
                if s is not None:
                    eo = place(-side, s[1] if side > 0 else s[0], tl + LAT, "exit")
            pos["exit_order"] = eo

    def schedule_taker(t_dec, why):
        nonlocal seq
        if pos is None or pos["pending"]:
            return
        pos["pending"] = True
        if pos["exit_order"] is not None:
            cancel(pos["exit_order"], t_dec)
        seq += 1
        heapq.heappush(heap, (t_dec + LAT, seq, why, id(pos)))

    def run_taker(t_arr, why, pid):
        if pos is None or id(pos) != pid:
            return True
        fl = L.taker_fill(d, t_arr, -pos["side"], 1)
        if fl is None:
            return False
        close(fl[0], fl[1], L.TAKER_BP, why)
        return True

    # merged timeline: ticks (local), trades (exchange); trades first at equal time
    tt_x, tt_l, tpx = d.tt_x.tolist(), d.tt_l.tolist(), d.tpx.tolist()
    tamt = None
    # amounts not in Day; reload trade amounts aligned with Day order (sorted by timestamp, stable)
    tr = pd.read_parquet(L.PQ / f"trades_{day}_{coin}.parquet").sort_values("timestamp")
    tamt = tr.amount.to_numpy(float).tolist()
    assert len(tamt) == len(tt_x)
    i_tr = int(np.searchsorted(d.tt_x, ticks[0] - 1, "left")) if len(ticks) else len(tt_x)
    i_tk = 0
    ntr, ntk = len(tt_x), len(tick_l)
    ok = True
    while ok and (i_tr < ntr or i_tk < ntk):
        nt_tr = tt_x[i_tr] if i_tr < ntr else INF
        nt_tk = tick_l[i_tk] if i_tk < ntk else INF
        nt_h = heap[0][0] if heap else INF
        t = min(nt_tr, nt_tk, nt_h)
        if t >= INF:
            break
        if nt_h == t:
            ta, _, why, pid = heapq.heappop(heap)
            ok = run_taker(ta, why, pid)
            continue
        if nt_tr == t:
            px, amt, tl = tpx[i_tr], tamt[i_tr], tt_l[i_tr]
            i_tr += 1
            for od in list(orders):
                if od["filled"] or not (od["frm"] <= t < od["until"]):
                    continue
                s, p = od["side"], od["px"]
                how = None
                if (s > 0 and px < p * (1 - EPS)) or (s < 0 and px > p * (1 + EPS)):
                    how = "through"
                elif od["queue"] is not None and abs(px - p) <= EPS * p:
                    od["cum"] += amt
                    if od["cum"] > od["queue"] + od["qty"]:
                        how = "queue"
                if how is None:
                    continue
                od["filled"] = True
                od["until"] = t
                if od["role"] == "entry":
                    on_entry_fill(od, t, tl, how)
                elif pos is not None and od is pos["exit_order"]:
                    close(p, t, L.MAKER_BP, "tp_maker")
            orders = [o for o in orders if not o["filled"] and o["until"] > t]
            continue
        # decision tick at local time t
        j = i_tk
        i_tk += 1
        f, blk, h = Fl[j], Bl[j], hil[j]
        if pos is not None:
            if not pos["pending"] and t >= pos["t_learn"]:
                hm = (hb_l[h] + ha_l[h]) / 2
                if pos["side"] * (hm / pos["px"] - 1) <= -k:
                    schedule_taker(t, "stop")
                elif t - pos["t_learn"] >= H:
                    schedule_taker(t, "time")
            continue
        live = [o for o in orders if o["role"] == "entry" and o["until"] > t + LAT]
        if blk:
            for o in live:
                cancel(o, t)
            last_place_F = None
            continue
        if t % R != 0 or not np.isfinite(f):
            continue
        if live and last_place_F is not None and abs(f / last_place_F - 1) <= k / 5:
            continue
        for o in live:
            cancel(o, t)
        last_place_F = f
        place(1, round_away(f * (1 - k), 1), t, "entry")
        place(-1, round_away(f * (1 + k), -1), t, "entry")
    if pos is not None:  # end-of-day flatten
        jj = len(d.ht_x) - 1
        px = d.hbid[jj] if pos["side"] > 0 else d.hask[jj]
        close(px, int(d.ht_x[jj]), L.TAKER_BP, "eod")
    for fl in fills:
        for hh in (1, 5, 30, 60):
            jj = np.searchsorted(hx, fl["t"] + hh * 1_000_000, "left")
            fl[f"mk{hh}"] = fl["side"] * (hmid_x[jj] / fl["px"] - 1) * 1e4 if jj < len(hx) else np.nan
    return trades, fills, stats


def run_job(a):
    coin, day, name = a
    r = sim(coin, day, CONFIGS[name])
    return coin, day, name, r


def summarize(name, trs, fls):
    t = pd.DataFrame(trs)
    f = pd.DataFrame(fls)
    st = L.bar_stats(t.pnl.tolist() if len(t) else [])
    out = dict(config=name, **st)
    if len(f):
        for h in (1, 5, 30, 60):
            out[f"markout_{h}s_bp"] = round(float(f[f"mk{h}"].mean()), 3)
        out["n_entry_fills"] = int(len(f))
        out["kill_test_mk30_pos"] = bool(f["mk30"].mean() > 0)
    else:
        out["n_entry_fills"] = 0
        out["kill_test_mk30_pos"] = False
    if len(t):
        t["gross_bp"] = t.side * (t.exit_px / t.entry_px - 1) * 1e4
        out["gross_bp_mean"] = round(float(t.gross_bp.mean()), 3)
        out["exit_mix"] = t.why.value_counts().to_dict()
        dd = t.groupby("day").pnl.sum()
        out["days_positive"] = f"{int((dd > 0).sum())}/{len(dd)}"
        out["by_day"] = {k: round(v, 2) for k, v in dd.items()}
        out["by_coin"] = {k: round(v, 2) for k, v in t.groupby("coin").pnl.sum().items()}
        out["by_coin_n"] = {k: int(v) for k, v in t.groupby("coin").size().items()}
        out["top3"] = [round(x, 2) for x in sorted(t.pnl, reverse=True)[:3]]
    out["passes_bar_and_kill"] = bool(out["passes"] and out["kill_test_mk30_pos"])
    return out, t, f


def main(split, names):
    days = TRAIN if split == "train" else VALID
    assert all(x < HOLDOUT_START for x in days)
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [(c, dd, n) for n in names for dd in days for c in COINS]
    acc = {n: ([], [], []) for n in names}
    cover = set()
    with ProcessPoolExecutor(3) as ex:
        for coin, day, name, r in ex.map(run_job, jobs):
            if r is None:
                continue
            cover.add((coin, day))
            acc[name][0].extend(r[0])
            acc[name][1].extend(r[1])
            acc[name][2].append(dict(coin=coin, day=day, **r[2]))
    summ = []
    for n in names:
        s, t, f = summarize(n, acc[n][0], acc[n][1])
        st = pd.DataFrame(acc[n][2])
        s["orders_placed"] = int(st.placed.sum())
        s["post_only_rejects"] = int(st.rejected.sum())
        s["fills_through"] = int(st.fills_through.sum())
        s["fills_queue"] = int(st.fills_queue.sum())
        s["blocked_tick_share"] = round(float(st.blocked_ticks.sum() / st.ticks.sum()), 4)
        summ.append(s)
        t.to_parquet(OUT / f"{split}_{n}_trades.parquet") if len(t) else None
        f.to_parquet(OUT / f"{split}_{n}_fills.parquet") if len(f) else None
        print(json.dumps({k: v for k, v in s.items() if k not in ("by_day",)}, default=str))
    res = dict(split=split, coin_days=sorted(f"{c}:{d}" for c, d in cover), n_coin_days=len(cover), configs=summ)
    (OUT / f"summary_{split}.json").write_text(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    sp = sys.argv[1]
    nm = sys.argv[2:] or list(CONFIGS)
    if sp == "valid":
        assert len(nm) == 1, "validation runs exactly one selected config"
    main(sp, nm)
