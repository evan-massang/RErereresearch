"""Pool-selection filters on top of the BOOST base rule (L1.0, THIN <= 150 SOL, single exit +300 s, 0.5 SOL).
Agent boost_select, 2026-10-04. Features: boost_select_lib.py. Train selection only; validation once, only for configs
that pass the full bar on train AND are net positive on Oct 1 and Oct 2 train separately.

Pre-stated grid (28 configs). Thresholds are the train medians / terciles of each feature over the 256 eligible
train pools, computed from features only (no outcomes), and frozen here:
  medians : fill_s 195.5 s, top5_share 0.143, snipe_share 0.047, n_buyers 319
  terciles: fill_s 89.0 / 408.9 s, top5_share 0.113 (low third), snipe_share 0.019 (low third), n_buyers 517 (top third)
Hypothesised "safe" side (stated before results): slow fill, low top-5 concentration, creator sold out on the curve,
low sniper share, many buyers.
  BASE                        reference (all eligible pools)
  12 single median/flag filters: FAST/SLOW, TOP5_LO/TOP5_HI, CRE_OUT/CRE_HOLD, SNIPE_LO/SNIPE_HI, BUY_HI/BUY_LO,
                                 SOCIAL (metadata has twitter/telegram/website; pools without fetched metadata excluded),
                                 NOMAYHEM (is_mayhem known False)
  5 tercile filters: NOT_FASTEST (fill_s >= 89), SLOWEST (fill_s > 408.9), TOP5_LOWEST, SNIPE_LOWEST, BUY_TOP
  10 two-feature pairs of the safe sides at the median: SLOW, TOP5_LO, CRE_OUT, SNIPE_LO, BUY_HI (all 10 pairs)
Usage: python boost_select_grid.py train   |   python boost_select_grid.py valid CFG [CFG ...]
"""
import itertools, json, sys
import numpy as np, pandas as pd
sys.path.insert(0, "/home/user/RErereresearch/scripts/research")
import boost_select_lib as S, amm_flow_lib as L

OUT = "/home/user/RErereresearch/research/observations/evidence_boost_select_{}_20261004.json"
TIPS = (0.001, 0.01)

SINGLE = {
    "FAST": lambda F: F.fill_s <= 195.5, "SLOW": lambda F: F.fill_s > 195.5,
    "TOP5_LO": lambda F: F.top5_share <= 0.143, "TOP5_HI": lambda F: F.top5_share > 0.143,
    "CRE_OUT": lambda F: F.creator_hold == 0, "CRE_HOLD": lambda F: F.creator_hold == 1,
    "SNIPE_LO": lambda F: F.snipe_share <= 0.047, "SNIPE_HI": lambda F: F.snipe_share > 0.047,
    "BUY_HI": lambda F: F.n_buyers >= 319, "BUY_LO": lambda F: F.n_buyers < 319,
    "SOCIAL": lambda F: F.social == 1, "NOMAYHEM": lambda F: F.mayhem == 0,
    "NOT_FASTEST": lambda F: F.fill_s >= 89.0, "SLOWEST": lambda F: F.fill_s > 408.9,
    "TOP5_LOWEST": lambda F: F.top5_share <= 0.113, "SNIPE_LOWEST": lambda F: F.snipe_share <= 0.019,
    "BUY_TOP": lambda F: F.n_buyers >= 517,
}
CONFIGS = {"BASE": lambda F: pd.Series(True, index=F.index)}
CONFIGS.update(SINGLE)
for a, b in itertools.combinations(["SLOW", "TOP5_LO", "CRE_OUT", "SNIPE_LO", "BUY_HI"], 2):
    CONFIGS[f"{a}+{b}"] = (lambda fa, fb: (lambda F: fa(F) & fb(F)))(SINGLE[a], SINGLE[b])
assert len(CONFIGS) == 28


def evaluate(F, split, keep=None):
    res = {}
    for name, fn in CONFIGS.items():
        if keep and name not in keep:
            continue
        s = F[fn(F).fillna(False).astype(bool)]
        res[name] = {}
        for tip in TIPS:
            st = L.stats(s.pnl.to_numpy(), tip)
            st["pass"] = L.passes(st)
            if split == "train":
                st["oct1"] = L.stats(s[s.created < S.DAY2].pnl.to_numpy(), tip)
                st["oct2"] = L.stats(s[s.created >= S.DAY2].pnl.to_numpy(), tip)
                st["both_days_pos"] = bool(st["oct1"].get("net", -1) > 0 and st["oct2"].get("net", -1) > 0)
            res[name][str(tip)] = st
    return res


def coverage(F):
    return {"pools": int(len(F)), "pools_before_guards": int(F.attrs.get("n_before_guards", -1)),
            "metadata_found": int(F.social.notna().sum()), "social_yes": int((F.social == 1).sum()),
            "mayhem_known": int(F.mayhem.notna().sum()), "mayhem_true": int((F.mayhem == 1).sum()),
            "snipe_nan": int(F.snipe_share.isna().sum())}


if __name__ == "__main__":
    split = sys.argv[1]
    T = S.base_trades(split)
    if split == "valid":
        assert T.created.min() >= L.VAL_A
    F = S.features(T, split)
    keep = sys.argv[2:] or None
    res = evaluate(F, split, keep)
    ev = {"agent": "boost_select", "date": "2026-10-04", "split": split, "modality": "onchain",
          "is_synthetic": False, "n_configs": len(CONFIGS), "coverage": coverage(F), "grid_doc": __doc__,
          "results": res}
    json.dump(ev, open(OUT.format(split), "w"), indent=1, default=float)
    print(json.dumps(ev["coverage"]))
    for k, v in sorted(res.items(), key=lambda kv: -(kv[1]["0.001"].get("net") or -99)):
        a, b = v["0.001"], v["0.01"]
        d = f"o1={a['oct1'].get('net')} o2={a['oct2'].get('net')}" if split == "train" else ""
        print(f"{k:18s} n={a['n']:4d} net={a.get('net', 0):7.3f} pf={a.get('pf')} ex3={a.get('net_ex3')} "
              f"{d} | t.01 net={b.get('net', 0):7.3f} pf={b.get('pf')} pass={a['pass']},{b['pass']}")
