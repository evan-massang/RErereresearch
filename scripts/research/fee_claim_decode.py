"""Decode PumpSwap creator-fee claim events from the raw PumpSwap log files (idea 5, H-CLAIM).

Source of the layouts: the public pump.fun IDLs,
  https://raw.githubusercontent.com/pump-fun/pump-public-docs/main/idl/pump_amm.json  (program pAMMBay6…)
  https://raw.githubusercontent.com/pump-fun/pump-public-docs/main/idl/pump.json      (program 6EF8rrec…)
fetched 2026-10-05. Anchor event discriminator = sha256("event:<Name>")[:8]; the script recomputes it and
asserts it equals the IDL's listed bytes (copied below).

CollectCoinCreatorFeeEvent (IDL disc [232,245,194,238,234,218,58,89]):
    disc(8) | timestamp i64 @8 | coin_creator pubkey @16 | coin_creator_fee u64 @48 (quote lamports)
    | coin_creator_vault_ata pubkey @56 | coin_creator_token_account pubkey @88
The event carries NO pool or mint: the creator vault is one PDA per creator, shared by all their pools.
Pools are attributed through Buy/SellEvent.coin_creator (@312) seen in the same files.

READ-ONLY: reads data/raw/streams/pumpswap_raw and (read_only) data/market.duckdb for pool -> mint/create time.
Writes only research/observations/evidence_fee_claim_counts.json.

Point-in-time / split note: every raw PumpSwap file still on disk is from 2026-10-05 (recv >= 1791162000),
i.e. inside the forward window (>= 1791072000). Per the task rules this script reports descriptive counts
only and computes no price outcome after any claim.
"""
from __future__ import annotations

import base64
import collections
import gzip
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

import base58

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/streams/pumpswap_raw"
OUT = ROOT / "research/observations/evidence_fee_claim_counts.json"
FORWARD_START = 1791072000.0

IDL_DISC = {  # copied from the IDLs above
    "CollectCoinCreatorFeeEvent": [232, 245, 194, 238, 234, 218, 58, 89],
    "BuyEvent": [103, 244, 82, 31, 44, 245, 119, 119],
    "SellEvent": [62, 47, 55, 10, 165, 3, 220, 42],
    "MigratePoolCoinCreatorEvent": [170, 221, 82, 199, 147, 165, 247, 46],
    "SetBondingCurveCoinCreatorEvent": [242, 231, 235, 102, 65, 99, 189, 211],
    "SetMetaplexCoinCreatorEvent": [150, 107, 199, 123, 124, 207, 102, 228],
    "UpdateCreatorFeeConfigEvent": [152, 198, 124, 124, 106, 246, 127, 191],
    # pump (bonding-curve) program, in case of CPI logs
    "CollectCreatorFeeEvent": [122, 2, 127, 1, 14, 191, 12, 175],
    "DistributeCreatorFeesEvent": [165, 55, 129, 112, 4, 179, 202, 40],
}
OTHER_NAMES = ["CreatePoolEvent", "DepositEvent", "WithdrawEvent", "BoostBuyAndBurnEvent", "TransferCreatorFeesToPumpEvent",
               "ClaimTokenIncentivesEvent", "SyncUserVolumeAccumulatorEvent", "InitUserVolumeAccumulatorEvent",
               "ClaimCashbackEvent", "ReservedFeeRecipientsEvent", "UpdateFeeConfigEvent"]


def disc(name: str) -> bytes:
    return hashlib.sha256(f"event:{name}".encode()).digest()[:8]


for n, b in IDL_DISC.items():
    assert disc(n) == bytes(b), n
NAMES = {disc(n): n for n in list(IDL_DISC) + OTHER_NAMES}
D_COLLECT, D_BUY, D_SELL = disc("CollectCoinCreatorFeeEvent"), disc("BuyEvent"), disc("SellEvent")
D_CURVE_COLLECT, D_DISTRIBUTE = disc("CollectCreatorFeeEvent"), disc("DistributeCreatorFeesEvent")


def pk(d: bytes, o: int) -> str:
    return base58.b58encode(d[o:o + 32]).decode()


def rows(f: Path):
    try:
        with gzip.open(f, "rt") as fh:
            for line in fh:
                try:
                    yield json.loads(line)
                except ValueError:
                    continue
    except (EOFError, zlib.error, OSError):
        return


def _q(xs, ps=(0.1, 0.25, 0.5, 0.75, 0.9)):
    xs = sorted(xs)
    return {p: xs[min(len(xs) - 1, int(p * len(xs)))] for p in ps} if xs else {}


def summarize_curve(cc, pools):
    """pump-program CollectCreatorFeeEvent seen only because the same tx also touched PumpSwap (partial view)."""
    wsol = [c["fee"] / 1e9 for c in cc if c["quote_mint"] == WSOL or c["quote_mint"] == SYS]
    return {"n": len(cc), "quote_mints": dict(collections.Counter(c["quote_mint"][:8] for c in cc)),
            "distinct_creators": len({c["creator"] for c in cc}),
            "sol_quantiles": _q(wsol)}


def summarize_dist(ds, pools):
    mints = {}
    for x in ds:
        mints.setdefault(x["mint"], []).append(x["recv"])
    mint_of_pool = {m: rv for _, (m, rv) in pools.items()}
    known = [m for m in mints if m in mint_of_pool]
    ages = [(min(v) - mint_of_pool[m]) / 60 for m, v in mints.items() if m in mint_of_pool]
    gaps = []
    for v in mints.values():
        v = sorted(v)
        gaps += [(b - a) / 60 for a, b in zip(v, v[1:])]
    sol = [x["distributed"] / 1e9 for x in ds if x["quote_mint"] in (WSOL, SYS)]
    return {"n": len(ds), "distinct_mints": len(mints), "max_per_mint": max((len(v) for v in mints.values()), default=0),
            "mints_with_2plus": sum(1 for v in mints.values() if len(v) >= 2),
            "mints_migrated_while_recording": len(known),
            "first_seen_minutes_after_pool_create_quantiles": _q(ages),
            "minutes_between_repeat_distributions_quantiles": _q(gaps),
            "n_shareholders_counts": dict(collections.Counter(x["n_shareholders"] for x in ds)),
            "quote_mints": dict(collections.Counter(x["quote_mint"][:8] for x in ds)),
            "zero_distributed": sum(1 for x in ds if x["distributed"] == 0),
            "sol_quantiles": _q(sol)}


WSOL = "So11111111111111111111111111111111111111112"
SYS = "11111111111111111111111111111111"


def main() -> None:
    disc_counts: collections.Counter = collections.Counter()
    claims: list[dict] = []
    curve_claims: list[dict] = []
    distributions: list[dict] = []
    creator_pools: dict[str, set] = collections.defaultdict(set)
    creator_sells: dict[str, list] = collections.defaultdict(list)     # creator wallet's own sells (recv, pool, sig)
    seen = set()
    files = sorted(RAW.glob("*.jsonl.gz"), key=lambda x: x.stat().st_mtime)
    file_info = {}
    for f in files:
        n, lo, hi = 0, None, None
        for r in rows(f):
            data = r.get("data")
            if not data:
                continue
            key = hash((r.get("sig"), data[:120]))
            if key in seen:
                continue
            seen.add(key)
            n += 1
            recv = r["recv"]
            lo = recv if lo is None else min(lo, recv)
            hi = recv if hi is None else max(hi, recv)
            d = base64.b64decode(data)
            k = d[:8]
            disc_counts[NAMES.get(k, k.hex())] += 1
            if k == D_COLLECT and len(d) >= 120:
                claims.append({"recv": recv, "slot": r.get("slot"), "sig": r.get("sig"),
                               "ts": struct.unpack_from("<q", d, 8)[0], "creator": pk(d, 16),
                               "fee_lamports": struct.unpack_from("<Q", d, 48)[0], "vault_ata": pk(d, 56),
                               "dest": pk(d, 88)})
            elif k == D_CURVE_COLLECT and len(d) >= 88:
                curve_claims.append({"recv": recv, "sig": r.get("sig"), "creator": pk(d, 16),
                                     "fee": struct.unpack_from("<Q", d, 48)[0], "quote_mint": pk(d, 56)})
            elif k == D_DISTRIBUTE and len(d) >= 148:
                nsh = struct.unpack_from("<I", d, 144)[0]
                o = 148 + 34 * nsh
                if len(d) >= o + 40:
                    distributions.append({"recv": recv, "sig": r.get("sig"), "mint": pk(d, 16), "admin": pk(d, 112),
                                          "n_shareholders": nsh, "distributed": struct.unpack_from("<Q", d, o)[0],
                                          "quote_mint": pk(d, o + 8)})
            elif k in (D_BUY, D_SELL) and len(d) >= 360:
                cr, pool = pk(d, 312), pk(d, 120)
                creator_pools[cr].add(pool)
                if k == D_SELL and pk(d, 152) == cr:
                    creator_sells[cr].append((recv, pool, r.get("sig")))
        file_info[f.name] = {"records": n, "recv_min": lo, "recv_max": hi}
        print(f.name, file_info[f.name], len(claims), file=sys.stderr, flush=True)

    # pool -> mint / creation recv, from the decoded market db (read-only); pools older than the recording are unknown
    import duckdb
    pools = {}
    try:
        con = duckdb.connect(str(ROOT / "data/market.duckdb"), read_only=True)
        pools = {p: (m, rv) for p, m, rv in con.execute("SELECT pool, mint, recv FROM amm_pools").fetchall()}
        con.close()
    except Exception as e:  # noqa: BLE001
        print("market.duckdb unavailable:", e, file=sys.stderr)

    assert all(c["recv"] >= FORWARD_START for c in claims) or not claims
    n_train_val = sum(1 for c in claims if c["recv"] < FORWARD_START)
    by_hour = collections.Counter(int(c["recv"] // 3600) * 3600 for c in claims)
    fees = sorted(c["fee_lamports"] / 1e9 for c in claims)
    per_creator = collections.Counter(c["creator"] for c in claims)

    def q(xs, p):
        return xs[min(len(xs) - 1, int(p * len(xs)))] if xs else None

    # attribution to recorded pools (migrations seen by our recorder) and age of the pool at the claim
    attributed, ages = 0, []
    single_pool = 0
    sold_same_tx = 0
    for c in claims:
        ps = creator_pools.get(c["creator"], set())
        if len(ps) == 1:
            single_pool += 1
        known = [pools[p] for p in ps if p in pools]
        if known:
            attributed += 1
            ages.append(min(c["recv"] - rv for _, rv in known))
        if any(s[2] == c["sig"] for s in creator_sells.get(c["creator"], [])):
            sold_same_tx += 1
    ages = sorted(a / 60 for a in ages)
    # quote-mint check: the vault ATA should be ATA(PDA(["creator_vault", creator], pAMM), WSOL) for SOL claims
    from solders.pubkey import Pubkey
    amm = Pubkey.from_string("pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA")
    tokp = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
    ataprog = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
    wsol = Pubkey.from_string("So11111111111111111111111111111111111111112")
    wsol_vault = 0
    for c in claims:
        auth, _ = Pubkey.find_program_address([b"creator_vault", bytes(Pubkey.from_string(c["creator"]))], amm)
        ata, _ = Pubkey.find_program_address([bytes(auth), bytes(tokp), bytes(wsol)], ataprog)
        c["wsol_vault"] = str(ata) == c["vault_ata"]
        wsol_vault += c["wsol_vault"]
    age_bins = collections.Counter()
    for a in ages:
        age_bins["<10m" if a < 10 else "10-60m" if a < 60 else "1-6h" if a < 360 else "6-24h" if a < 1440 else ">24h"] += 1

    out = {
        "is_synthetic": False,
        "modality": "onchain",
        "kind": "descriptive_counts_only",
        "idl_source": ["https://raw.githubusercontent.com/pump-fun/pump-public-docs/main/idl/pump_amm.json",
                       "https://raw.githubusercontent.com/pump-fun/pump-public-docs/main/idl/pump.json"],
        "collect_coin_creator_fee_discriminator": IDL_DISC["CollectCoinCreatorFeeEvent"],
        "collect_coin_creator_fee_discriminator_hex": disc("CollectCoinCreatorFeeEvent").hex(),
        "curve_collect_creator_fee_discriminator": IDL_DISC["CollectCreatorFeeEvent"],
        "files": file_info,
        "split_note": "All files are recv >= 1791162000 (2026-10-05 UTC), inside the forward window (>= 1791072000). "
                      "No price outcomes were computed.",
        "claims_total": len(claims),
        "claims_in_train_or_validation": n_train_val,
        "claims_by_utc_hour": {str(k): v for k, v in sorted(by_hour.items())},
        "distinct_claiming_creators": len(per_creator),
        "claims_per_creator_max": max(per_creator.values()) if per_creator else 0,
        "creators_with_2plus_claims": sum(1 for v in per_creator.values() if v >= 2),
        "claim_sol_quantiles": {p: q(fees, p) for p in (0.1, 0.25, 0.5, 0.75, 0.9, 0.99)} if fees else {},
        "claim_sol_total": sum(fees),
        "zero_amount_claims": sum(1 for x in fees if x == 0),
        "claims_creator_traded_in_exactly_one_pool_in_files": single_pool,
        "claims_attributable_to_pool_created_while_recording": attributed,
        "pool_age_at_claim_minutes_bins": dict(age_bins),
        "pool_age_at_claim_minutes_quantiles": {p: q(ages, p) for p in (0.1, 0.25, 0.5, 0.75, 0.9)} if ages else {},
        "claims_with_creator_sell_in_same_tx": sold_same_tx,
        "named_event_counts": {n: disc_counts.get(n, 0) for n in list(IDL_DISC) + OTHER_NAMES},
        "claims_vault_is_wsol_ata": wsol_vault,
        "event_discriminator_counts_top": dict(disc_counts.most_common(10)),
        "sample_claims": claims[:5],
        "curve_collect_creator_fee_events_in_amm_logs": summarize_curve(curve_claims, pools),
        "curve_claims_sharing_tx_with_amm_claim": len({c["sig"] for c in curve_claims} & {c["sig"] for c in claims}),
        "distribute_creator_fees_events_in_amm_logs": summarize_dist(distributions, pools),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k not in ("sample_claims",)}, indent=1))


if __name__ == "__main__":
    main()
