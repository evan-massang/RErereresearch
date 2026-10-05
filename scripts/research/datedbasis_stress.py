"""H-DATEDBASIS post-hoc execution stress (NOT used for selection; run after the pre-registered train run).

1. worst-in-bar entries: every 1h futures close is replaced by the bar LOW and every spot close by the bar HIGH,
   so the decision basis and the entry fill are both at the worst print of the bar (fees and slippage on top).
   Delivery settlement is unchanged. Only meaningful for hold-to-delivery variants (V1, V2, V3, V5): for V4's
   early exits the patch would be favourable.
2. capacity: USD volume of the dated future in the fill bar and in the 24h before the decision
   (COIN-M volume is in contracts: BTC $100, others $10; USDS-M volume is in coin);
3. stale-quote check: basis at decision vs basis at the fill bar.
Usage: python scripts/research/datedbasis_stress.py <split> <variant> [...]
"""
import json
import sys

import pandas as pd

import datedbasis_sim as m


def main(split, names):
    fut, spot, dd, fr = m.load()
    # worst-in-bar: replace close by low (future) / high (spot) for the entry bar via patched frames
    fw = fut.copy()
    sw = spot.copy()
    out = {"split": split, "post_hoc": True, "is_synthetic": False, "variants": {}}
    for name in names:
        cfg = m.VARIANTS[name]
        base, _ = m.build_trades(fut, spot, dd, fr, split, cfg)
        # worst-in-bar: run with futures close := low and spot close := high (entries), and the opposite for
        # exits is approximated by the same patch only for entries; delivery exits use the 1m settlement window.
        f2 = fw.assign(close=fw.low)
        s2 = sw.assign(close=sw.high)
        worst, _ = m.build_trades(f2, s2, dd, fr, split, cfg)
        res = {"base": m.stats(base), "worst_in_bar_entry": m.stats(worst),
               "worst_passes": m.passes(m.stats(worst))}
        # capacity and staleness on base trades
        fi = fut.set_index(["symbol", "open_time"]).sort_index()
        si = spot.set_index(["coin", "open_time"]).sort_index()
        caps, stale = [], []
        for t in base.itertuples():
            tf = pd.Timestamp(t.entry) - pd.Timedelta(hours=1)  # fill bar open
            size = (100 if t.coin == "BTC" else 10) if t.market == "cm" else None
            row = fi.loc[(t.symbol, tf)]
            px = row.close
            usd = row.volume * size if size else row.volume * px
            win = fi.loc[t.symbol].loc[tf - pd.Timedelta(hours=24): tf - pd.Timedelta(hours=1)]
            usd24 = (win.volume * size).sum() if size else (win.volume * win.close).sum()
            caps.append(dict(symbol=t.symbol, coin=t.coin, fill_bar_usd=usd, prior24h_usd=usd24, r_ex=t.r_ex))
            sp = si.loc[(t.coin, tf)].close
            stale.append((px / sp - 1) * 365 / t.D_entry - t.basis_ann)
        cap = pd.DataFrame(caps)
        res["capacity_fill_bar_usd_by_coin_median"] = cap.groupby("coin").fill_bar_usd.median().round(0).to_dict()
        res["capacity_prior24h_usd_by_coin_median"] = cap.groupby("coin").prior24h_usd.median().round(0).to_dict()
        # P&L share from trades whose 24h futures volume < $1M
        thin = cap[cap.prior24h_usd < 1e6]
        res["thin_lt_1M_24h"] = {"n": int(len(thin)), "sum_r_ex": float(thin.r_ex.sum()),
                                 "share_of_net": float(thin.r_ex.sum() / base.r_ex.sum())}
        res["thick_ge_1M_24h_stats"] = m.stats(base[cap.prior24h_usd.values >= 1e6])
        res["fill_minus_decision_basis_ann"] = pd.Series(stale).describe().round(4).to_dict()
        out["variants"][name] = res
        print(name, json.dumps({k: v for k, v in res.items() if k != "base"}, default=str)[:2500])
    p = m.OBS / f"evidence_datedbasis_{split}_stress.json"
    p.write_text(json.dumps(out, indent=1, default=str))
    print("wrote", p)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
