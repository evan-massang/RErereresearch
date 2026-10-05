"""H-PREMCONV step 3: simulate the 12 pre-registered configs (reports/hypotheses/premconv_preregistration.json).

    python scripts/research/premconv_sim.py --split train
    python scripts/research/premconv_sim.py --split validation   # only configs that met the bar on train (L=1)

Reads data/raw/web/binance_prem/{universe.json,win,daily,funding,fetch_log.json}.
Writes research/observations/evidence_premconv_<split>.json and a trades parquet in the scratch cache dir
(data/raw/web/binance_prem/trades_<split>.parquet).
"""
import argparse
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data/raw/web/binance_prem"
PRE = json.loads((ROOT / "reports/hypotheses/premconv_preregistration.json").read_text())
FEE_SPOT, FEE_PERP = 0.0010, 0.0005
SPLITS = {"train": ("2023-01-01", "2025-07-01"), "validation": ("2025-07-01", "2026-04-01")}
LATS = (0, 1, 2)
PRIMARY_L = 1
STOP = 1.30
COOLDOWN = 60
BAS_IDENTITY_MAX = 0.01  # data-validity: drop symbol-months whose median |BAS| > 1% (spot/perp mapping mismatch)


def minute(s):
    return int(pd.Timestamp(s, tz="UTC").value // 60_000_000_000)


def tier(adv):
    if adv is None or not np.isfinite(adv) or adv < 2e6:
        return None
    return 0.0003 if adv >= 1e8 else (0.0005 if adv >= 2e7 else 0.0015)


def load_symbol(perp):
    w = pd.read_parquet(D / "win" / f"{perp}.parquet")
    dl = pd.read_parquet(D / "daily" / f"{perp}.parquet") if (D / "daily" / f"{perp}.parquet").exists() else None
    fu = pd.read_parquet(D / "funding" / f"{perp}.parquet") if (D / "funding" / f"{perp}.parquet").exists() else None
    piv = dl.pivot_table(index="day", columns="market", values="qv") if dl is not None else None
    return w, piv, fu


def adv_at(piv, day):
    if piv is None or len(piv) == 0 or "fut" not in piv or "spot" not in piv:
        return None
    sl = piv.loc[(piv.index >= day - 7) & (piv.index < day)]
    if sl["fut"].count() < 5 or sl["spot"].count() < 5:
        return None
    return float(min(sl["fut"].mean(), sl["spot"].mean()))


def sim_symbol(perp, months, w, piv, fu, cfg, L, split, spot_fee=FEE_SPOT):
    s0, s1 = SPLITS[split]
    m_lo, m_hi = minute(s0), minute(s1) - 1  # entries and all fills inside [m_lo, m_hi]
    m = w.m.to_numpy().astype(np.int64)
    sig = (w.pi if cfg["signal"] == "PI" else w.bas).to_numpy().astype(float)
    sprev = (w.pi_prev if cfg["signal"] == "PI" else w.bas_prev).to_numpy().astype(float)
    fo, fh, fc = (w[c].to_numpy().astype(float) for c in ("fo", "fh", "fc"))
    so, sc = w.so.to_numpy().astype(float), w.sc.to_numpy().astype(float)
    ft = fu.t_ms.to_numpy() if fu is not None else np.array([])
    fr = fu.rate.to_numpy() if fu is not None else np.array([])
    mon = pd.to_datetime(m * 60, unit="s").strftime("%Y-%m").to_numpy()
    trades, skips = [], defaultdict(int)
    busy_until = -1
    adv_cache = {}
    H = cfg["max_hold_h"] * 60
    X = cfg["exit_signal_le"]
    for i in range(1, len(m)):
        if m[i] < m_lo or m[i] > m_hi or m[i] <= busy_until:
            continue
        if not np.isfinite(sig[i]) or sig[i] < 0.0052 + cfg["entry_extra_over_B"]:
            continue
        if mon[i] not in months:
            continue
        day = m[i] // 1440
        if day not in adv_cache:
            adv_cache[day] = adv_at(piv, day)
        slip = tier(adv_cache[day])
        if slip is None:
            skips["illiquid_or_no_adv"] += 1
            continue
        thr = FEE_SPOT * 2 + FEE_PERP * 2 + 4 * slip + 0.0010 + cfg["entry_extra_over_B"]
        if sig[i] < thr:
            continue
        if not (np.isfinite(sprev[i]) and sprev[i] < thr and m[i - 1] == m[i] - 1):
            continue  # not an onset (or previous bar missing)
        me = m[i] + 1 + L
        k = np.searchsorted(m, me)
        if k >= len(m) or m[k] != me or not (np.isfinite(fo[k]) and np.isfinite(so[k])) or me > m_hi:
            skips["entry_bar_missing"] += 1
            continue
        pe_raw, se_raw = fo[k], so[k]
        pe, se = pe_raw * (1 - slip), se_raw * (1 + slip)
        # decision scan from bar k (its close is known after entry at its open)
        kend = np.searchsorted(m, me + H + 1)
        seg = slice(k, kend)
        cond_sig = np.isfinite(sig[seg]) & (sig[seg] <= X)
        cond_stop = np.isfinite(fh[seg]) & (fh[seg] >= pe_raw * STOP)
        cond_hold = (m[seg] - me) >= H
        cond_end = m[seg] >= m_hi
        anyc = cond_sig | cond_stop | cond_hold | cond_end
        reason = "data_end"
        if anyc.any():
            j = k + int(np.argmax(anyc))
            jj = j - k
            reason = ("stop" if cond_stop[jj] else "signal" if cond_sig[jj] else
                      "hold" if cond_hold[jj] else "split_end")
            if reason == "split_end" and not (cond_sig[jj] or cond_stop[jj] or cond_hold[jj]):
                xk_p = xk_s = j
                px, sx, mx = fc[j], sc[j], m[j]
                forced = True
            else:
                forced = False
        else:
            j = kend - 1
            forced = True
            px, sx, mx = fc[j], sc[j], m[j]
        gap = False
        if not forced:
            mfill = m[j] + 1 + L
            if mfill > m_hi:
                jl = np.searchsorted(m, m_hi, side="right") - 1
                px, sx, mx = fc[jl], sc[jl], m[jl]
                reason += "+split_end"
            else:
                kf = np.searchsorted(m, mfill)
                # next available open for each leg
                kp = kf
                while kp < len(m) and not np.isfinite(fo[kp]):
                    kp += 1
                ks = kf
                while ks < len(m) and not np.isfinite(so[ks]):
                    ks += 1
                if kp >= len(m) or ks >= len(m):
                    jl = len(m) - 1
                    px, sx, mx = fc[jl], sc[jl], m[jl]
                    reason += "+data_end"
                else:
                    gap = (m[kp] != mfill) or (m[ks] != mfill)
                    px, sx, mx = fo[kp], so[ks], max(m[kp], m[ks])
        if not (np.isfinite(px) and np.isfinite(sx)):
            skips["exit_price_nan"] += 1
            continue
        px_f, sx_f = px * (1 + slip), sx * (1 - slip)
        spot_r = sx_f / se - 1
        perp_r = px_f / pe - 1
        fsel = (ft > me * 60000) & (ft <= mx * 60000)
        fund = float(fr[fsel].sum())
        fees = spot_fee * (1 + sx_f / se) + FEE_PERP * (1 + px_f / pe)
        net = spot_r - perp_r + fund - fees
        trades.append({"sym": perp, "t_sig": int(m[i]), "t_in": int(me), "t_out": int(mx), "sig": float(sig[i]),
                       "thr": thr, "slip": slip, "adv": adv_cache[day], "gross_basis": spot_r - perp_r,
                       "fund": fund, "fees": fees, "net": net, "reason": reason, "gap": gap})
        busy_until = mx + COOLDOWN
    return trades, skips


def stats(t):
    if len(t) == 0:
        return {"n": 0}
    x = np.sort(t.net.to_numpy())
    gp, gl = x[x > 0].sum(), -x[x < 0].sum()
    return {"n": int(len(x)), "net": float(x.sum()), "mean_bp": float(x.mean() * 1e4), "median_bp": float(np.median(x) * 1e4),
            "pf": float(gp / gl) if gl > 0 else None, "net_ex_top3": float(x[:-3].sum()) if len(x) > 3 else None,
            "win_rate": float((x > 0).mean()), "gross_basis_bp": float(t.gross_basis.mean() * 1e4),
            "fund_bp": float(t.fund.mean() * 1e4), "fees_bp": float(t.fees.mean() * 1e4),
            "median_hold_min": float((t.t_out - t.t_in).median()), "n_symbols": int(t.sym.nunique()),
            "n_event_days": int(t.assign(d=t.t_sig // 1440).groupby(["sym", "d"]).ngroups),
            "exit_reasons": t.reason.value_counts().to_dict(), "gap_fills": int(t.gap.sum())}


def passes(s):
    return bool(s.get("n", 0) >= 50 and s["net"] > 0 and s["pf"] is not None and s["pf"] > 1.2
                and s["net_ex_top3"] is not None and s["net_ex_top3"] > 0)


def breakdown(t, key):
    out = {}
    for k, g in t.groupby(key):
        x = g.net.to_numpy()
        out[str(k)] = {"n": int(len(x)), "net": float(x.sum()), "mean_bp": float(x.mean() * 1e4)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["train", "validation"], required=True)
    a = ap.parse_args()
    uni = json.loads((D / "universe.json").read_text())["data"]
    flog = json.loads((D / "fetch_log.json").read_text())
    cfgs = PRE["configs"]
    if a.split == "validation":
        tr = json.loads((ROOT / "research/observations/evidence_premconv_train.json").read_text())
        ok = [c for c in tr["configs"] if c["pass_L1"]]
        cfgs = [c for c in cfgs if c["key"] in {o["key"] for o in ok}]
        if not cfgs:
            raise SystemExit("no config met the bar on train: validation is not examined")
    s0, s1 = SPLITS[a.split]
    months_by_sym = defaultdict(set)
    for mo, mem in uni.items():
        if s0[:7] <= mo < s1[:7]:
            for x in mem:
                months_by_sym[x["perp"]].add(mo)
    dropped = []
    for sym, ms in months_by_sym.items():
        lg = flog.get(sym, {}).get("months", {})
        for mo in list(ms):
            e = lg.get(mo)
            if e is None or e.get("missing"):
                dropped.append({"sym": sym, "month": mo, "why": "missing:" + ",".join(e.get("missing", ["log"]) if e else ["no_log"])})
                ms.discard(mo)
            elif abs(e.get("median_bas", 0)) > BAS_IDENTITY_MAX:
                dropped.append({"sym": sym, "month": mo, "why": f"median_bas={e['median_bas']:.4f}"})
                ms.discard(mo)
    data = {}
    for sym in months_by_sym:
        if (D / "win" / f"{sym}.parquet").exists():
            w, piv, fu = load_symbol(sym)
            if len(w):
                data[sym] = (w, piv, fu)
    out = {"hypothesis": "H-PREMCONV", "split": a.split, "run_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
           "preregistration": "reports/hypotheses/premconv_preregistration.json", "is_synthetic": False,
           "symbol_months": int(sum(len(v) for v in months_by_sym.values())), "symbols": len(months_by_sym),
           "dropped_symbol_months": dropped, "configs": []}
    all_tr = []
    for cfg in cfgs:
        res = {"key": cfg["key"], "cfg": cfg, "by_latency": {}}
        for L in LATS:
            T, SK = [], defaultdict(int)
            for sym, (w, piv, fu) in data.items():
                tr_, sk = sim_symbol(sym, months_by_sym[sym], w, piv, fu, cfg, L, a.split)
                T += tr_
                for k, v in sk.items():
                    SK[k] += v
            t = pd.DataFrame(T)
            st = stats(t)
            st["skips"] = dict(SK)
            st["pass"] = passes(st) if st["n"] else False
            if L == PRIMARY_L and len(t):
                t["q"] = pd.to_datetime(t.t_in * 60, unit="s").dt.to_period("Q").astype(str)
                st["by_quarter"] = breakdown(t, "q")
                st["by_symbol"] = dict(sorted(breakdown(t, "sym").items(), key=lambda kv: -abs(kv[1]["net"]))[:15])
                st["top5_trades"] = t.nlargest(5, "net")[["sym", "t_in", "sig", "net", "reason"]].to_dict("records")
                st["worst5_trades"] = t.nsmallest(5, "net")[["sym", "t_in", "sig", "net", "reason"]].to_dict("records")
                st["by_slip_tier"] = breakdown(t, "slip")
                # BNB-discount sensitivity (secondary): spot fee 0.075%
                bnb = t.net + (FEE_SPOT - 0.00075) * 2  # two spot fills
                st["bnb_spot_fee_sensitivity"] = {"net": float(bnb.sum()), "mean_bp": float(bnb.mean() * 1e4)}
                tt = t.copy()
                tt["key"] = cfg["key"]
                all_tr.append(tt)
            res["by_latency"][str(L)] = st
        res["pass_L1"] = res["by_latency"][str(PRIMARY_L)]["pass"]
        out["configs"].append(res)
        b = res["by_latency"]
        print(cfg["key"], " | ".join(f"L{L}: n={b[str(L)].get('n')} net={b[str(L)].get('net', 0):+.3f} "
                                       f"pf={b[str(L)].get('pf') or 0:.2f} mean={b[str(L)].get('mean_bp', 0):+.1f}bp "
                                       f"ex3={b[str(L)].get('net_ex_top3') or 0:+.3f}" for L in LATS),
              "PASS" if res["pass_L1"] else "", flush=True)
    (ROOT / f"research/observations/evidence_premconv_{a.split}.json").write_text(json.dumps(out, indent=1, default=float))
    if all_tr:
        pd.concat(all_tr).to_parquet(D / f"trades_{a.split}.parquet", index=False)


if __name__ == "__main__":
    main()
