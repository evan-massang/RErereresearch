"""Pre-graduation exit (arXiv 2602.14860, B2) and socials-in-metadata (arXiv 2607.02823, B3) on the bonding curve.

Ideas (fixed before any outcome was computed; grid = 34 configs, see GRID):
  A  far-along entry: decision at the first trusted print whose real SOL (rsol) >= E (E = 30/40/50);
     exit when a print shows rsol >= X (X = 70/75/80, i.e. before completion at ~85), or price <= entry x 0.7,
     or the time stop TS after entry (900 / 3600 s). All non-Mayhem tokens.           3 x 3 x 2       = 18
  B  as A, restricted to tokens whose launch metadata lists a Telegram link (tg) or at least two of
     Telegram / X / website (soc2). E = 30/50, X = 75, SL 30%, TS 900/3600.          2 x 2 x 2       =  8
  C  early entry on the same social-filtered tokens: decision at the first print >= launch + 2 s (time to fetch
     the metadata JSON) or at the first print with rsol >= 10; X = 75, SL 30/50%, TS 3600.  2 x 2 x 2 =  8

Fills: exact constant product, 0.5 SOL, 1.25% fee per side, decision -> fill at the curve state 1 s after the
decision print (last trusted state with recv <= t + 1 s). If the curve completes before the entry fill, there is
no trade (counted). If it completes before the exit fill, the tokens are sold on PumpSwap at the pool state of
the first swap at/after the fill time (logged pool reserves, constant product, 1.25% fee); if no pool swap is
recorded the trigger is dropped and counted. Trusted states only (|vsol - rsol - 30| < 0.01). One trade per token
per config. A trigger counts only if the token's creation, the decision and the whole window up to
fill + TS + 1 s lie inside one gap-free recording segment (no global gap > 60 s) inside one allowed split.

Splits: train = recv < 1790882100 or 1790899200 <= recv < 1790985600; validation = [1790985600, 1791072000).
Nothing in [1790882100, 1790899200) or >= 1791072000 is read.

    python scripts/research/pregrad_build.py          # writes data/processed/pregrad_trades.parquet (gitignored scratch)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import duckdb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

SIZE, FEE, LAT, GAP = 0.5, 0.0125, 1.0, 60.0
HOLD0, OCT2, OCT3, OCT4 = 1790882100.0, 1790899200.0, 1790985600.0, 1791072000.0
ALLOWED = f"((recv < {HOLD0}) OR (recv >= {OCT2} AND recv < {OCT4}))"
META = ROOT / "data/raw/web/token_metadata"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data/processed/pregrad_trades.parquet"

GRID = []
for E in (30, 40, 50):
    for X in (70, 75, 80):
        for TS in (900, 3600):
            GRID.append(dict(idea="A", filt="all", entry=f"rsol{E}", X=X, SL=0.30, TS=TS))
for f in ("tg", "soc2"):
    for E in (30, 50):
        for TS in (900, 3600):
            GRID.append(dict(idea="B", filt=f, entry=f"rsol{E}", X=75, SL=0.30, TS=TS))
    for ent in ("launch2s", "rsol10"):
        for SL in (0.30, 0.50):
            GRID.append(dict(idea="C", filt=f, entry=ent, X=75, SL=SL, TS=3600))
for g in GRID:
    g["cfg"] = f"{g['idea']}|{g['filt']}|{g['entry']}|X{g['X']}|SL{int(g['SL'] * 100)}|TS{g['TS']}"


def key(uri: str) -> str:
    return uri.rstrip("/").split("/")[-1].replace(".json", "")[:80]


def socials(uri):
    """(covered, tg, x, web) from the cached launch metadata JSON; covered=False when not cached."""
    if not isinstance(uri, str) or not uri.startswith("http"):
        return False, False, False, False
    f = META / f"{key(uri)}.json"
    if not f.exists():
        return False, False, False, False
    try:
        j = json.loads(f.read_text())
    except Exception:
        return False, False, False, False
    if not isinstance(j, dict):
        return False, False, False, False
    h = [isinstance(j.get(k), str) and bool(j.get(k).strip()) for k in ("telegram", "twitter", "website")]
    return True, h[0], h[1], h[2]


def segments(con):
    r = con.execute(f"""WITH t AS (SELECT recv, lag(recv) OVER (ORDER BY recv) p FROM curve_trades WHERE {ALLOWED})
                        SELECT p, recv FROM t WHERE recv - p > {GAP} ORDER BY p""").fetchall()
    lo, hi = con.execute(f"SELECT min(recv), max(recv) FROM curve_trades WHERE {ALLOWED}").fetchone()
    segs = list(zip([lo] + [b for _, b in r], [a for a, _ in r] + [hi]))
    out = []  # cut at split boundaries; a segment end is the last recorded print (window must end before it)
    for a, b in segs:
        cuts = [a] + [c for c in (HOLD0, OCT2, OCT3, OCT4) if a < c < b] + [b]
        for x, y in zip(cuts[:-1], cuts[1:]):
            if x >= HOLD0 and x < OCT2:
                continue
            out.append((x, min(y, HOLD0) if x < HOLD0 else y))
    return np.array(out)


def seg_of(segs, t):
    i = np.searchsorted(segs[:, 0], t, side="right") - 1
    return i if i >= 0 and segs[i, 0] <= t <= segs[i, 1] else -1


def buy_tok(vs, vt):
    return vt - vs * vt / (vs + SIZE * (1 - FEE))


def sell_sol(vs, vt, tok):
    return (vs - vs * vt / (vt + tok)) * (1 - FEE)


def simulate(T, vs, vt, rs, i0, tc, cfg, amm, seg_end):
    """One trade from decision print i0. Returns dict or a skip reason string."""
    tf = T[i0] + LAT
    if tc is not None and tf >= tc:
        return "completed_before_entry"
    ke = np.searchsorted(T, tf, side="right") - 1
    if tf + cfg["TS"] + LAT + 1 > seg_end:
        return "window_not_recorded"
    p0 = vs[ke] / vt[ke]
    tok = buy_tok(vs[ke], vt[ke])
    lim = np.searchsorted(T, tf + cfg["TS"], side="right")
    px = vs[ke + 1:lim] / vt[ke + 1:lim]
    hit = np.nonzero((rs[ke + 1:lim] >= cfg["X"]) | (px <= p0 * (1 - cfg["SL"])))[0]
    if len(hit):
        j = ke + 1 + hit[0]
        dec = T[j]
        why = "target" if rs[j] >= cfg["X"] else "stop"
    else:
        dec, why = tf + cfg["TS"], "time"
    tx = dec + LAT
    if tc is not None and tx >= tc:
        if amm is None or len(amm) == 0:
            return "migrated_no_amm"
        a = np.searchsorted(amm[:, 0], tx, side="left")
        if a >= len(amm):
            return "migrated_no_amm"
        ps, pt = amm[a, 1], amm[a, 2]
        out = (ps - ps * pt / (pt + tok)) * (1 - FEE)
        why = why + "_amm"
    else:
        k = np.searchsorted(T, tx, side="right") - 1
        out = sell_sol(vs[k], vt[k], tok)
    return {"t": T[i0], "t_entry": tf, "entry_rsol": rs[ke], "exit": why, "hold_s": tx - tf, "gross": out - SIZE}


def main():
    con = duckdb.connect(str(ROOT / "data/market.duckdb"), read_only=True)
    con.execute("SET threads=2; SET memory_limit='3GB'")
    segs = segments(con)
    print("segments", [(round(a), round(b), round((b - a) / 3600, 2)) for a, b in segs], flush=True)
    fl = pd.read_parquet(ROOT / "data/processed/mayhem_flags.parquet", columns=["mint", "is_mayhem"])
    cr = con.execute(f"SELECT mint, min(recv) ct, any_value(uri) uri FROM curve_creates WHERE {ALLOWED} GROUP BY 1").df()
    cr = cr.merge(fl.drop_duplicates("mint"), on="mint", how="left")
    n_all = len(cr)
    n_unflag = int(cr.is_mayhem.isna().sum())
    n_may = int((cr.is_mayhem == True).sum())  # noqa: E712
    cr = cr[cr.is_mayhem == False].copy()  # noqa: E712  only tokens known non-Mayhem
    s = cr.uri.map(socials)
    cr["meta"] = [x[0] for x in s]; cr["tg"] = [x[1] for x in s]; cr["x"] = [x[2] for x in s]; cr["web"] = [x[3] for x in s]
    cr["soc2"] = (cr.tg.astype(int) + cr.x.astype(int) + cr.web.astype(int)) >= 2
    cr["split"] = np.where(cr.ct < OCT3, "train", "validation")
    cov = {sp: {"creates_non_mayhem": int(len(g)), "metadata_cached": int(g.meta.sum()),
                "coverage": round(float(g.meta.mean()), 4), "tg": int(g.tg.sum()), "soc2": int(g.soc2.sum()),
                "x": int(g.x.sum()), "web": int(g.web.sum())} for sp, g in cr.groupby("split")}
    cov["excluded"] = {"creates_allowed": n_all, "mayhem": n_may, "unflagged_dropped": n_unflag}
    print(json.dumps(cov), flush=True)
    comp = dict(con.execute(f"SELECT mint, min(recv) FROM curve_completes WHERE {ALLOWED} GROUP BY 1").fetchall())
    con.register("crm", cr[["mint", "ct", "tg", "soc2"]])
    # candidate tokens: reached rsol >= 30 (A/B) or social-filtered (C)
    cand = con.execute(f"""SELECT mint FROM crm WHERE tg OR soc2 UNION
                           SELECT DISTINCT t.mint FROM curve_trades t JOIN crm USING (mint)
                           WHERE {ALLOWED.replace('recv', 't.recv')} AND t.rsol >= 30
                           AND abs(t.vsol - t.rsol - 30) < 0.01""").df()
    con.register("cand", cand)
    print("candidate tokens", len(cand), flush=True)
    tr = con.execute(f"""SELECT mint, recv, vsol, vtok, rsol FROM curve_trades
                         WHERE mint IN (SELECT mint FROM cand) AND {ALLOWED} AND abs(vsol - rsol - 30) < 0.01
                         ORDER BY mint, recv, rowid""").df()
    amm = {m: g[["recv", "ps", "pt"]].to_numpy() for m, g in con.execute(
        f"""SELECT mint, recv, pool_sol_logged ps, pool_tok_logged pt FROM amm_trades
            WHERE mint IN (SELECT mint FROM cand) AND {ALLOWED} AND pool_sol_logged > 0 AND pool_tok_logged > 0
            ORDER BY mint, recv, rowid""").df().groupby("mint")}
    crx = cr.set_index("mint")
    rows, skips = [], {}
    for m, g in tr.groupby("mint", sort=False):
        c = crx.loc[m]
        si = seg_of(segs, c.ct)
        if si < 0:
            continue
        seg_end = segs[si, 1]
        T, vs, vt, rs = g.recv.to_numpy(), g.vsol.to_numpy(), g.vtok.to_numpy(), g.rsol.to_numpy()
        inseg = T <= seg_end
        T, vs, vt, rs = T[inseg], vs[inseg], vt[inseg], rs[inseg]
        tc = comp.get(m)
        for cfg in GRID:
            if cfg["filt"] != "all" and not c[cfg["filt"]]:
                continue
            e = cfg["entry"]
            if e == "launch2s":
                idx = np.nonzero(T >= c.ct + 2.0)[0]
            else:
                idx = np.nonzero(rs >= float(e[4:]))[0]
            if not len(idx):
                continue
            i0 = idx[0]
            if tc is not None and T[i0] >= tc:
                continue
            r = simulate(T, vs, vt, rs, i0, tc, cfg, amm.get(m), seg_end)
            if isinstance(r, str):
                skips.setdefault(cfg["cfg"], {}).setdefault(r, 0)
                skips[cfg["cfg"]][r] += 1
                continue
            rows.append({"cfg": cfg["cfg"], "mint": m, "split": "train" if r["t"] < OCT3 else "validation",
                         "completed": tc is not None, **r})
    d = pd.DataFrame(rows)
    d.to_parquet(OUT)
    (OUT.parent / "pregrad_meta.json").write_text(json.dumps({"coverage": cov, "skips": skips, "segments": segs.tolist(),
                                                              "n_configs": len(GRID)}, indent=1))
    print("rows", len(d), "configs", len(GRID))


if __name__ == "__main__":
    main()
