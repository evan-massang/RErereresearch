"""H-FFDIFF-MAKER: the iteration-2 FFDIFF signal with maker execution and a conservative 1h fill model.

Pre-registration (written before this file was run): reports/hypotheses/ffdiff_maker_preregistration.json.
Signal, exits, stop and liquidation are reused from ffdiff_sim.py; only execution differs.

    python scripts/research/ffdiff_maker_sim.py fetch train|validation   # Binance 1h klines for that split only
    python scripts/research/ffdiff_maker_sim.py train|validation
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ffdiff_sim as fs  # noqa: E402
from ffdiff_fetch import bn_zip  # noqa: E402

PRE = json.loads((fs.ROOT / "reports/hypotheses/ffdiff_maker_preregistration.json").read_text())
H = fs.H
MK_HL, MK_BN, TK_HL, TK_BN = 1.5e-4, 2.0e-4, 4.5e-4, 5.0e-4
HAIR, TSLIP, M = 5e-4, 5e-4, 0.0044
MONTHS = {"train": [f"{y}-{m:02d}" for y in (2024, 2025) for m in range(1, 13) if "2024-06" <= f"{y}-{m:02d}" <= "2025-07"],
          "validation": [f"{y}-{m:02d}" for y in (2025, 2026) for m in range(1, 13) if "2025-07" <= f"{y}-{m:02d}" <= "2026-03"]}


def fetch(split):
    u = json.loads((fs.HL / "ffdiff/universe.json").read_text())["pairs"]

    def one(sym):
        f = fs.BN / f"{sym}_k1h_{split}.parquet"
        if f.exists():
            return sym
        rows = []
        with httpx.Client(timeout=60) as cl:
            for m in MONTHS[split]:
                for ln in bn_zip(cl, f"https://data.binance.vision/data/futures/um/monthly/klines/{sym}/1h/{sym}-1h-{m}.zip") or []:
                    p = ln.split(",")
                    rows.append((int(p[0]), float(p[2]), float(p[3]), float(p[4])))
        d = pd.DataFrame(rows, columns=["t", "h", "l", "c"])
        d = d[d.t + 3600_000 <= fs.CUTOFF.value // 10**6].drop_duplicates("t").sort_values("t")
        d.to_parquet(f)
        return sym
    with ThreadPoolExecutor(6) as ex:
        for s in ex.map(one, [p["bn"] for p in u]):
            print(s, flush=True)


def k1h(sym):
    out = []
    for sp in ("train", "validation"):
        f = fs.BN / f"{sym}_k1h_{sp}.parquet"
        if f.exists():
            out.append(pd.read_parquet(f))
    d = pd.concat(out)
    d["t"] = pd.to_datetime(d.t, unit="ms")
    return d.drop_duplicates("t").set_index("t")


def execute(T, s, ph, pb, k, mode):
    """Execute open (mode='open') or close (mode='close') of the pair at boundary T with maker orders.
    s=+1 means the pair is short HL / long BN. Returns (hl_price, bn_price, cost, status) or None (no entry)."""
    # sides: open short-HL => HL sell, BN buy; close reverses
    hl_buy = (s == -1) if mode == "open" else (s == 1)
    bn_buy = not hl_buy
    b0, b1 = k.loc[T] if T in k.index else None, k.loc[T + H] if (T + H) in k.index else None
    if b0 is None or b1 is None:
        return None if mode == "open" else ("taker_close", ph, pb)
    bT = pb  # BN close at T
    hl_fill = (b0.l / bT - 1 < -M) if hl_buy else (b0.h / bT - 1 > M)
    bn_fill = (b0.l < pb) if bn_buy else (b0.h > pb)
    if not hl_fill and not bn_fill and mode == "open":
        return None
    cost, status = 0.0, []

    def hl_taker():
        w = (b1.h if hl_buy else b1.l) / bT * (1 + M if hl_buy else 1 - M)
        return ph * w * (1 + TSLIP if hl_buy else 1 - TSLIP)

    def bn_taker():
        w = b1.h if bn_buy else b1.l
        return w * (1 + TSLIP if bn_buy else 1 - TSLIP)
    if hl_fill:
        hp, c = ph * (1 + HAIR if hl_buy else 1 - HAIR), MK_HL
        status.append("hl_maker")
    else:
        hp, c = hl_taker(), TK_HL
        status.append("hl_taker")
    cost += c
    if bn_fill:
        bp, c = pb * (1 + HAIR if bn_buy else 1 - HAIR), MK_BN
        status.append("bn_maker")
    else:
        bp, c = bn_taker(), TK_BN
        status.append("bn_taker")
    cost += c
    return hp, bp, cost, "+".join(status)


def simulate(p, d, F, cfg, split, k):
    L, X, Z, lev, exit_mode, stop = cfg
    s0, s1 = fs.SPLITS[split]
    hk, bk, hf, bf = d["hk"], d["bk"], d["hf"], d["bf"]
    hc = pd.Series(hk.c.values, index=hk.index + 4 * H)
    bc = pd.Series(bk.c.values, index=bk.index + 4 * H)
    tradable = set(hc.index.intersection(bc.index))
    mm_hl = 1 / (2 * p["hl_maxlev_now"])
    Ts = F.index
    Tlist = [t for t in Ts if s0 <= t < s1]
    eps, j, nofill = [], 0, 0
    while j < len(Tlist):
        T0 = Tlist[j]
        r = F.loc[T0]
        j += 1
        if T0 not in tradable or not r["live"] or np.isnan(r[f"D{L}"]):
            continue
        s = 1 if r[f"D{L}"] > 0 else -1
        if not (s * r[f"D{L}"] >= X and s * r["D24"] >= X):
            continue
        ex = execute(T0, s, hc[T0], bc[T0], k, "open")
        if ex is None:
            nofill += 1
            continue
        ph0, pb0, c_open, st_open = ex
        kk = Ts.get_loc(T0)
        prev, reason, liq_leg = T0, None, None
        while True:
            kk += 1
            if kk >= len(Ts):
                reason, T = "data_end", prev; break
            T = Ts[kk]
            if T > s1:
                reason, T = "split_end", prev; break
            if T not in tradable or not F.loc[T, "live"]:
                reason, T = "gap", prev; break
            bar = T - 4 * H
            hh, hl_, bh, bl = hk.h.get(bar), hk.l.get(bar), bk.h.get(bar), bk.l.get(bar)
            if s == 1:
                if hh >= ph0 * (1 + 1 / lev) / (1 + mm_hl):
                    reason, liq_leg = "liq", "HL"; break
                if bl <= pb0 * (1 - 1 / lev) / (1 - fs.MM_BN):
                    reason, liq_leg = "liq", "BN"; break
            else:
                if bh >= pb0 * (1 + 1 / lev) / (1 + fs.MM_BN):
                    reason, liq_leg = "liq", "BN"; break
                if hl_ <= ph0 * (1 - 1 / lev) / (1 - mm_hl):
                    reason, liq_leg = "liq", "HL"; break
            prev = T
            adv_short = (hc[T] / ph0 - 1) if s == 1 else (bc[T] / pb0 - 1)
            adv_long = -((bc[T] / pb0 - 1) if s == 1 else (hc[T] / ph0 - 1))
            if max(adv_short, adv_long) >= stop:
                reason = "stop"; break
            if s * F.loc[T, f"D{L}"] < 0:
                reason = "exit_signal"; break
            if T - T0 >= pd.Timedelta(days=Z):
                reason = "time"; break
            if T == s1:
                reason = "split_end"; break
        T1 = T
        st_close = None
        if reason in ("exit_signal", "time"):  # maker close; neither/one leg unfilled -> taker at next 1h worst
            ex = execute(T1, s, hc[T1], bc[T1], k, "close")
            if len(ex) == 4:
                ph1, pb1, c_close, st_close = ex
        if st_close is None:  # urgent exits / missing 1h data: taker at the 4h close + 5 bp
            hl_buy = s == 1
            ph1 = hc[T1] * (1 + TSLIP if hl_buy else 1 - TSLIP)
            pb1 = bc[T1] * (1 - TSLIP if hl_buy else 1 + TSLIP)
            c_close, st_close = TK_HL + TK_BN, "taker_close"
        hret, bret = ph1 / ph0 - 1, pb1 / pb0 - 1
        hp = hf[(hf.index > T0 + H) & (hf.index <= T1)]
        bp = bf[(bf.index > T0) & (bf.index <= T1)]
        mh = hc.reindex(hp.index.floor("4h") + 4 * H).values / ph0
        mb = bc.reindex(bp.index.floor("4h") + 4 * H).values / pb0
        funding = s * (float(np.nansum(hp.values * mh)) - float(np.nansum(bp.values * mb)))
        if reason == "liq":
            hl_close = hc[T1] * (1 + TSLIP if s == 1 else 1 - TSLIP)
            bn_close = bc[T1] * (1 - TSLIP if s == 1 else 1 + TSLIP)
            if liq_leg == "HL":
                basis = -1 / lev + s * (bn_close / pb0 - 1)
                c_close = TK_BN
            else:
                basis = -1 / lev - s * (hl_close / ph0 - 1)
                c_close = TK_HL
            st_close = "liq"
        else:
            basis = s * (-hret + bret)
        cost = c_open + c_close  # fees; haircuts and taker slippage are inside the fill prices (in basis)
        net = funding + basis - cost
        eps.append({"coin": p["hl"], "dir": "shortHL" if s == 1 else "shortBN", "t0": str(T0), "t1": str(T1),
                    "days": (T1 - T0).total_seconds() / 86400, "D_entry": float(r[f"D{L}"]), "funding": funding,
                    "basis_incl_fill": basis, "basis": basis, "cost": cost, "net": net, "exit": reason,
                    "liq_leg": liq_leg, "open_exec": st_open, "close_exec": st_close})
        while j < len(Tlist) and Tlist[j] <= T1:
            j += 1
    return eps, nofill


def main():
    if sys.argv[1] == "fetch":
        fetch(sys.argv[2]); return
    split = sys.argv[1]
    cfgs = [(c["L_h"], c["X_ann"], c["Z_days"], c["lev"], c["exit"], c["stop"]) for c in PRE["configs"]]
    keys = [c["key"] for c in PRE["configs"]]
    if len(sys.argv) > 2:  # validation: only the named configs
        sel = sys.argv[2:]
        cfgs = [c for c, kk in zip(cfgs, keys) if kk in sel]
        keys = [kk for kk in keys if kk in sel]
    data = fs.load_all()
    ks = {p["bn"]: k1h(p["bn"]) for p, _, _ in data}
    res = {}
    for key, cfg in zip(keys, cfgs):
        eps, nof = [], 0
        for p, d, F in data:
            e, n = simulate(p, d, F, cfg, split, ks[p["bn"]])
            eps += e; nof += n
        st = fs.stats(eps)
        df = pd.DataFrame(eps)
        st["entry_signals_unfilled"] = nof
        st["open_exec"] = df.open_exec.value_counts().to_dict() if len(df) else {}
        st["close_exec"] = df.close_exec.value_counts().to_dict() if len(df) else {}
        res[key] = {"stats": st, "pass": fs.passes(st), "episodes": eps}
        print(f"{key} n={st['n']} net={st.get('net',0):+.3f} pf={st.get('pf',0):.2f} ex3={st.get('net_ex_top3',0):+.3f} "
              f"fund={st.get('funding',0):+.3f} basis={st.get('basis',0):+.3f} fees={st.get('cost',0):.3f} "
              f"liq={st.get('liq',0)} worst={st.get('worst',0):+.3f} unfilled={nof} PASS={fs.passes(st)}")
        print("  open", st["open_exec"], "close", st["close_exec"], "\n  by_q", st.get("by_quarter"))
    out = fs.OBS / f"evidence_ffdiff_maker_{split}.json"
    out.write_text(json.dumps({"family": "H-FFDIFF-MAKER", "split": split, "preregistration":
                               "reports/hypotheses/ffdiff_maker_preregistration.json", "is_synthetic": False,
                               "configs": res}, indent=1, default=str))
    print("wrote", out)


if __name__ == "__main__":
    main()
