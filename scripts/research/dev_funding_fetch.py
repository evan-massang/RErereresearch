"""Agent dev_funding (2026-10-05): fetch each sampled launch creator's on-chain history BEFORE the launch and
the transaction that first funded it, from the public Solana RPC. Responses are cached as JSON under
data/raw/web/rpc_funding/ so the work is reproducible:

  creators/<creator>.json   getSignaturesForAddress(creator, before=<create sig of its latest sampled launch>),
                            paged back to the wallet's first signature (cap MAX_PAGES x 1000 signatures)
  tx/<signature>.json       getTransaction (jsonParsed) of the creator's earliest successful signature(s)
  funders/<funder>__<sig>.json  getSignaturesForAddress(funder, before=<funding sig>, limit=1000)

Point in time: the creator query starts strictly before the launch's own create signature, and the funder query
strictly before the funding transaction, so nothing after the launch is fetched. (Signatures of the creator between
an earlier sampled launch and its latest sampled launch are filtered by blockTime per launch in dev_funding_build.)

Sample (fixed before any outcome was looked at; seed 20261005): uniform random launches from curve_creates, not
Mayhem Mode (flag False in data/processed/mayhem_flags.parquet; unknown flags excluded), with a create signature,
and whose create time + 1 s + 1800 s lies inside one gap-free recording segment and inside its split.
  train: 2,500 launches   validation: 1,200 launches. No outcome is used for selection; migrations enter in their
  natural proportion.

    python scripts/research/dev_funding_fetch.py sample   # writes the sample parquet (no RPC)
    python scripts/research/dev_funding_fetch.py fetch    # RPC, ~3 req/s, resumable from cache
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "research"))
import duckdb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from pipeline.onchain import Rpc  # noqa: E402
from pipeline.provenance import SourceUnavailable  # noqa: E402

HOLD0, OCT2, OCT3, OCT4 = 1790882100.0, 1790899200.0, 1790985600.0, 1791072000.0
GAP, MAXH = 60.0, 1800.0
ALLOWED = f"recv < {OCT4} AND NOT (recv >= {HOLD0} AND recv < {OCT2})"
CACHE = ROOT / "data/raw/web/rpc_funding"
SAMPLE = CACHE / "sample_launches.parquet"
N_TRAIN, N_VAL, SEED = 2500, 1200, 20261005
MAX_PAGES = 5


def split_of(t):
    if t < HOLD0:
        return "train", HOLD0
    if OCT2 <= t < OCT3:
        return "train", OCT3
    if OCT3 <= t < OCT4:
        return "validation", OCT4
    return None, None


def segments(con):
    r = con.execute(f"""WITH t AS (SELECT recv, lag(recv) OVER (ORDER BY recv) p FROM curve_trades WHERE {ALLOWED})
                        SELECT p, recv FROM t WHERE recv - p > {GAP} ORDER BY p""").fetchall()
    lo, hi = con.execute(f"SELECT min(recv), max(recv) FROM curve_trades WHERE {ALLOWED}").fetchone()
    return np.array(list(zip([lo] + [b for _, b in r], [a for a, _ in r] + [hi])))


def seg_of(segs, t):
    i = np.searchsorted(segs[:, 0], t, side="right") - 1
    return i if i >= 0 and t <= segs[i, 1] else -1


def make_sample():
    con = duckdb.connect(str(ROOT / "data/market.duckdb"), read_only=True)
    con.execute("SET memory_limit='2GB'; SET threads=2")
    segs = segments(con)
    cr = con.execute(f"""SELECT mint, arg_min(creator, recv) creator, arg_min(sig, recv) sig, min(recv) ct,
                         min(slot) cslot FROM curve_creates WHERE {ALLOWED} GROUP BY 1""").df()
    mf = pd.read_parquet(ROOT / "data/processed/mayhem_flags.parquet")[["mint", "is_mayhem"]]
    cr = cr.merge(mf, on="mint", how="left")
    cr = cr[(cr.is_mayhem == False) & cr.sig.notna() & cr.creator.notna()]  # noqa: E712
    keep = []
    for r in cr.itertuples():
        sp, ceil = split_of(r.ct)
        end = r.ct + 1 + MAXH + 1
        ok = sp is not None and end < ceil and seg_of(segs, r.ct) >= 0 and seg_of(segs, r.ct) == seg_of(segs, end)
        keep.append(sp if ok else None)
    cr["split"] = keep
    cr = cr[cr.split.notna()]
    rng = np.random.default_rng(SEED)
    tr = cr[cr.split == "train"]
    va = cr[cr.split == "validation"]
    s = pd.concat([tr.iloc[rng.choice(len(tr), N_TRAIN, replace=False)],
                   va.iloc[rng.choice(len(va), N_VAL, replace=False)]]).sort_values("ct")
    print("eligible train", len(tr), "validation", len(va), "sampled", len(s), "creators", s.creator.nunique())
    s.drop(columns=["is_mayhem"]).to_parquet(SAMPLE)


def jload(p):
    return json.loads(p.read_text()) if p.exists() else None


def jsave(p, obj):
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj))
    tmp.rename(p)


def creator_sigs(rpc, creator, before):
    p = CACHE / "creators" / f"{creator}.json"
    c = jload(p)
    if c is not None and c["before"] == before:
        return c
    sigs, cursor, complete = [], before, False
    for _ in range(MAX_PAGES):
        page = rpc.call("getSignaturesForAddress", [creator, {"limit": 1000, "before": cursor}])
        sigs.extend({"s": x["signature"], "t": x.get("blockTime"), "slot": x.get("slot"), "err": x.get("err") is not None}
                    for x in page)
        if len(page) < 1000:
            complete = True
            break
        cursor = page[-1]["signature"]
    c = {"creator": creator, "before": before, "complete": complete, "fetched": time.time(), "sigs": sigs}
    jsave(p, c)
    return c


def get_tx(rpc, sig):
    p = CACHE / "tx" / f"{sig}.json"
    if p.exists():
        return jload(p)
    tx = rpc.call("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0,
                                           "commitment": "finalized"}])
    jsave(p, tx)
    return tx


def funding_of(tx, wallet):
    """(funder, lamports, funder_pre_balance_lamports) from system transfers / createAccount into wallet."""
    if not tx:
        return None
    meta = tx.get("meta") or {}
    keys = [k["pubkey"] if isinstance(k, dict) else k for k in tx["transaction"]["message"]["accountKeys"]]
    ins = list(tx["transaction"]["message"].get("instructions", []))
    for ii in meta.get("innerInstructions") or []:
        ins.extend(ii.get("instructions", []))
    best = None
    for x in ins:
        pr = x.get("parsed")
        if not isinstance(pr, dict) or x.get("program") != "system":
            continue
        info = pr.get("info", {})
        dest = info.get("destination") or info.get("newAccount")
        src = info.get("source")
        lam = info.get("lamports")
        if dest == wallet and src and src != wallet and lam:
            if best is None or lam > best[1]:
                best = (src, lam)
    if best is None:
        return None
    pre = None
    if best[0] in keys:
        pre = meta["preBalances"][keys.index(best[0])]
    return {"funder": best[0], "lamports": best[1], "funder_pre": pre}


def funder_sigs(rpc, funder, sig):
    p = CACHE / "funders" / f"{funder}__{sig[:16]}.json"
    if p.exists():
        return jload(p)
    page = rpc.call("getSignaturesForAddress", [funder, {"limit": 1000, "before": sig}])
    c = {"funder": funder, "before": sig, "n": len(page), "fetched": time.time(),
         "times": [x.get("blockTime") for x in page]}
    jsave(p, c)
    return c


def fetch():
    s = pd.read_parquet(SAMPLE)
    rpc = Rpc(rps=3.0)
    # latest sampled launch per creator -> query before its create signature
    last = s.sort_values("ct").groupby("creator").tail(1)
    todo = list(last.itertuples())
    t0, n_err = time.time(), 0
    for i, r in enumerate(todo):
        try:
            c = creator_sigs(rpc, r.creator, r.sig)
            if c["complete"]:
                ok = [x for x in c["sigs"] if not x["err"]]
                # earliest successful signature(s): try up to 3 oldest until a funding transfer is found
                for x in list(reversed(ok))[:3]:
                    f = funding_of(get_tx(rpc, x["s"]), r.creator)
                    if f:
                        funder_sigs(rpc, f["funder"], x["s"])
                        break
        except SourceUnavailable as e:
            n_err += 1
            print("ERR", r.creator, e, flush=True)
            time.sleep(10)
        if i % 100 == 0:
            print(f"{i}/{len(todo)} creators, {time.time() - t0:.0f}s, errors {n_err}", flush=True)
    print("done", len(todo), "errors", n_err)


if __name__ == "__main__":
    {"sample": make_sample, "fetch": fetch}[sys.argv[1]]()
