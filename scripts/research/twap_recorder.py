"""Forward recorder for Hyperliquid TWAP orders (data for H-TWAPRIDE / H-TWAPFADE).

README
------
Why: there is no free history of HL TWAP placements (the HL S3 archive is requester-pays and excluded), so ideas
H-TWAPRIDE and H-TWAPFADE (sources/leads/documented_edges_round6.md) can only be trained and tested on data recorded
forward from now. Plan: recording days 1-2 = train, day 3 = validation, then freeze the pre-registration and
forward-test on later days (reports/hypotheses/twap_data_notes.md).

Sources (all public, unauthenticated, read-only):
  * Hypurrscan `GET https://api.hypurrscan.io/twap/*` (third-party explorer, a LEAD source). Returns the `twapOrder`
    actions of TWAPs that are still running (finished ones drop out; checked 2026-10-05), each with block time, user,
    asset index, side, size, minutes, reduce-only, randomize, block, tx hash, error. Polled every --hs-every s (15).
    Our receive time of the first poll that contains a record is `first_seen_ms`.
  * HL info `twapHistory` (per user): twapId, coin name, trigger, status (activated / finished / terminated / error /
    stopped / waitingForTrigger) with the status event time, executedSz and executedNtl. Polled for every user with a
    tracked TWAP: at first sight, every --status-every s (1800) while active, and at expected end + 2 min. Rate-limited to
    one call per --hist-gap s (default 5 s, i.e. <= 12 calls/min, ~240 of HL's 1200 weight/min per IP).
    Placements found in a user's history that Hypurrscan never showed are recorded with source='hist' (coverage misses).
  * HL info `metaAndAssetCtxs` once a minute: mark, mid, oracle, 24h notional volume, open interest, funding for every
    main-dex perp (and for builder dexes with a running tracked TWAP). This is the 1-minute mid and the point-in-time
    24h volume needed for participation p.
  The HL websocket was not used: its TWAP channels (`userTwapHistory`, `userTwapSliceFills`) are per user and HL caps
  user-specific subscriptions at 10 users per IP; there is no global TWAP channel. `allMids` is replaced by the
  per-minute ctx poll, which also carries volume.

Output (hourly parquet chunks, UTC hour of receive time), data/raw/web/twap/:
  twaps_<YYYY-MM-DD-HH>.parquet   one row per TWAP placement first seen in that hour
      first_seen_ms, block_time_ms, user, asset, coin, side(B/A), sz, minutes, reduce_only, randomize, block, hash,
      error, source ('hs' | 'hist'), initial (True = already listed at recorder start, so lag is meaningless)
  events_<...>.parquet            twapHistory status events (deduped on user, placed_ms, status, event_time_s)
      poll_ms, user, placed_ms, twap_id, coin, side, sz, executed_sz, executed_ntl, minutes, reduce_only,
      randomize, trigger_px, status, status_desc, event_time_s
  ctx_<...>.parquet               ts_ms, coin, mark, mid, oracle, day_ntl_vlm, oi, funding
  recorder.log                    progress, hourly coverage/lag summary, errors

Usage:
    nohup python scripts/research/twap_recorder.py record --hours 48 >> data/raw/web/twap/recorder.log 2>&1 &
    python scripts/research/twap_recorder.py coverage          # coverage + lag summary from the chunks
"""
import argparse
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/raw/web/twap"
HS_URL = "https://api.hypurrscan.io/twap/*"
INFO = "https://api.hyperliquid.xyz/info"
TERMINAL = {"finished", "terminated", "error", "stopped"}
UA = {"User-Agent": "RErereresearch-twap-recorder/1.0 (research; polite polling)"}


def now_ms() -> int:
    return int(time.time() * 1000)


def log(*a):
    print(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), *a, flush=True)


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


class Sink:
    """Buffers rows per table and appends them to the hourly chunk of their receive hour."""

    def __init__(self):
        self.rows = defaultdict(list)   # (table, hour) -> rows

    def add(self, table, row, ts_ms):
        h = datetime.fromtimestamp(ts_ms / 1000, timezone.utc).strftime("%Y-%m-%d-%H")
        self.rows[(table, h)].append(row)

    def flush(self):
        OUT.mkdir(parents=True, exist_ok=True)
        for (table, h), rows in list(self.rows.items()):
            if not rows:
                continue
            p = OUT / f"{table}_{h}.parquet"
            df = pd.DataFrame(rows)
            if p.exists():
                df = pd.concat([pd.read_parquet(p), df], ignore_index=True)
            tmp = p.with_suffix(".tmp")
            df.to_parquet(tmp, index=False, compression="zstd")
            os.replace(tmp, p)
        self.rows.clear()


class Recorder:
    def __init__(self, a):
        self.a = a
        self.s = requests.Session()
        self.s.headers.update(UA)
        self.sink = Sink()
        self.start_ms = now_ms()
        self.seen = set()          # (user, placed_ms) of placements already recorded
        self.ev_seen = set()       # (user, placed_ms, status, event_time_s)
        self.track = {}            # (user, placed_ms) -> dict(end_ms, status, coin)
        self.user_due = {}         # user -> next twapHistory poll (ms)
        self.names = {}            # asset index -> coin name
        self.dex_of = {}           # coin -> dex name ('' = main)
        self.first_hs = True
        self.last_hist = 0.0
        self.stats = defaultdict(int)
        self.lags = []
        self._load_previous()

    # ---------- http ----------
    def info(self, body, timeout=30):
        r = self.s.post(INFO, json=body, timeout=timeout)
        if r.status_code == 429:
            log("HL 429; backing off 60 s")
            time.sleep(60)
            r.raise_for_status()
        r.raise_for_status()
        return r.json()

    # ---------- state ----------
    def _load_previous(self):
        """On restart, do not re-record placements/events already in the last two days of chunks."""
        for p in sorted(OUT.glob("twaps_*.parquet"))[-48:]:
            df = pd.read_parquet(p, columns=["user", "block_time_ms"])
            self.seen.update(zip(df.user, df.block_time_ms.astype("int64")))
        for p in sorted(OUT.glob("events_*.parquet"))[-48:]:
            df = pd.read_parquet(p, columns=["user", "placed_ms", "status", "event_time_s"])
            self.ev_seen.update(zip(df.user, df.placed_ms.astype("int64"), df.status, df.event_time_s.astype("int64")))
        if self.seen:
            log(f"resume: {len(self.seen)} placements, {len(self.ev_seen)} events already recorded")

    def refresh_meta(self):
        dexes = self.info({"type": "perpDexs"})
        names, dex_of = {}, {}
        for i, d in enumerate(dexes):
            dex = "" if d is None else d["name"]
            meta = self.info({"type": "meta", "dex": dex} if dex else {"type": "meta"})
            base = 0 if i == 0 else 100000 + i * 10000
            for j, u in enumerate(meta["universe"]):
                names[base + j] = u["name"]
                dex_of[u["name"]] = dex
            time.sleep(0.5)
        self.names, self.dex_of = names, dex_of
        log(f"meta: {len(names)} perps across {len(dexes)} dexes")

    # ---------- Hypurrscan ----------
    def poll_hs(self):
        r = self.s.get(HS_URL, timeout=30)
        recv = now_ms()
        r.raise_for_status()
        recs = r.json()
        new = 0
        for x in recs:
            t = (x.get("action") or {}).get("twap") or {}
            key = (x["user"], int(x["time"]))
            if key in self.seen:
                continue
            self.seen.add(key)
            new += 1
            asset = int(t.get("a", -1))
            coin = self.names.get(asset) or (f"@{asset - 10000}" if 10000 <= asset < 100000 else None)
            row = dict(first_seen_ms=recv, block_time_ms=key[1], user=x["user"], asset=asset, coin=coin,
                       side="B" if t.get("b") else "A", sz=fnum(t.get("s")), minutes=int(t.get("m") or 0),
                       reduce_only=bool(t.get("r")), randomize=bool(t.get("t")), block=int(x.get("block") or 0),
                       hash=x.get("hash"), error=None if x.get("error") is None else str(x["error"])[:200],
                       source="hs", initial=self.first_hs)
            self.sink.add("twaps", row, recv)
            self.stats["hs_new"] += 1
            if not self.first_hs:
                self.lags.append((recv - key[1]) / 1000)
            self._track(key, row["minutes"], coin, initial=self.first_hs)
        if self.first_hs:
            log(f"hypurrscan initial snapshot: {len(recs)} running TWAPs (initial=True)")
        elif new:
            log(f"hypurrscan: {new} new (list {len(recs)})")
        self.first_hs = False

    def _track(self, key, minutes, coin, initial=False):
        user, placed = key
        self.track[key] = dict(end_ms=placed + minutes * 60_000, status=None, coin=coin)
        due = now_ms() + (self.a.status_every * 1000 if initial else 0)   # new ones: query at once for twapId
        self.user_due[user] = min(self.user_due.get(user, due), due)

    # ---------- twapHistory ----------
    def poll_one_user(self):
        if not self.user_due or time.monotonic() - self.last_hist < self.a.hist_gap:
            return
        user, due = min(self.user_due.items(), key=lambda kv: kv[1])
        if due > now_ms():
            return
        self.last_hist = time.monotonic()
        hist = self.info({"type": "twapHistory", "user": user})
        poll = now_ms()
        self.stats["hist_calls"] += 1
        latest = {}
        for e in hist:
            st = e.get("state") or {}
            placed = int(st.get("timestamp") or 0)
            if placed < self.start_ms - 86_400_000:
                continue
            status = (e.get("status") or {}).get("status")
            k = (user, placed, status, int(e.get("time") or 0))
            key = (user, placed)
            latest.setdefault(key, (status, st.get("coin")))               # history is newest first
            if key not in self.seen and placed >= self.start_ms:          # Hypurrscan never showed it
                self.seen.add(key)
                self.sink.add("twaps", dict(first_seen_ms=poll, block_time_ms=placed, user=user, asset=None,
                                            coin=st.get("coin"), side=st.get("side"), sz=fnum(st.get("sz")),
                                            minutes=int(st.get("minutes") or 0),
                                            reduce_only=bool(st.get("reduceOnly")),
                                            randomize=bool(st.get("randomize")), block=None, hash=None,
                                            error=None, source="hist", initial=False), poll)
                self.stats["hist_missed"] += 1
                self._track(key, int(st.get("minutes") or 0), st.get("coin"))
            if k in self.ev_seen or key not in self.track:
                continue
            self.ev_seen.add(k)
            self.sink.add("events", dict(poll_ms=poll, user=user, placed_ms=placed, twap_id=e.get("twapId"),
                                         coin=st.get("coin"), side=st.get("side"), sz=fnum(st.get("sz")),
                                         executed_sz=fnum(st.get("executedSz")),
                                         executed_ntl=fnum(st.get("executedNtl")), minutes=st.get("minutes"),
                                         reduce_only=st.get("reduceOnly"), randomize=st.get("randomize"),
                                         trigger_px=fnum(st.get("trigger")), status=status,
                                         status_desc=(e.get("status") or {}).get("description"),
                                         event_time_s=k[3]), poll)
            self.stats["events"] += 1
        # schedule next poll for this user
        nxt = None
        for key, tr in list(self.track.items()):
            if key[0] != user:
                continue
            if key in latest:
                tr["status"] = latest[key][0]
                tr["coin"] = tr["coin"] or latest[key][1]
            if tr["status"] in TERMINAL or poll > tr["end_ms"] + 3_600_000:
                del self.track[key]
                continue
            cand = poll + self.a.status_every * 1000
            if tr["status"] != "waitingForTrigger" and poll < tr["end_ms"] + 120_000:
                cand = min(cand, tr["end_ms"] + 120_000)
            nxt = cand if nxt is None else min(nxt, cand)
        if nxt is None:
            self.user_due.pop(user, None)
        else:
            self.user_due[user] = nxt

    # ---------- prices ----------
    def poll_ctx(self):
        dexes = {""} | {self.dex_of.get(tr["coin"], "") for tr in self.track.values() if tr["coin"]}
        for dex in sorted(dexes):
            meta, ctxs = self.info({"type": "metaAndAssetCtxs", "dex": dex} if dex else {"type": "metaAndAssetCtxs"})
            ts = now_ms()
            for u, c in zip(meta["universe"], ctxs):
                self.sink.add("ctx", dict(ts_ms=ts, coin=u["name"], mark=fnum(c.get("markPx")),
                                          mid=fnum(c.get("midPx")), oracle=fnum(c.get("oraclePx")),
                                          day_ntl_vlm=fnum(c.get("dayNtlVlm")), oi=fnum(c.get("openInterest")),
                                          funding=fnum(c.get("funding"))), ts)
            self.stats["ctx_polls"] += 1

    # ---------- main loop ----------
    def summary(self):
        import numpy as np
        lag = np.array(self.lags) if self.lags else np.array([np.nan])
        log(f"summary: hs_new={self.stats['hs_new']} hist_missed={self.stats['hist_missed']} "
            f"events={self.stats['events']} hist_calls={self.stats['hist_calls']} ctx={self.stats['ctx_polls']} "
            f"tracked={len(self.track)} users_queued={len(self.user_due)} "
            f"lag_s p50={np.nanmedian(lag):.1f} p90={np.nanpercentile(lag, 90):.1f} max={np.nanmax(lag):.1f} "
            f"n_lag={len(self.lags)} errors={self.stats['errors']}")

    def run(self, hours):
        stop = time.monotonic() + hours * 3600
        nxt = defaultdict(float)
        nxt["flush"], nxt["summary"] = time.monotonic() + 300, time.monotonic() + 3600
        self.refresh_meta()
        while time.monotonic() < stop:
            t = time.monotonic()
            jobs = [("meta", 3600, self.refresh_meta), ("hs", self.a.hs_every, self.poll_hs),
                    ("ctx", 60, self.poll_ctx), ("flush", 300, self.sink.flush), ("summary", 3600, self.summary)]
            for name, every, fn in jobs:
                if t >= nxt[name]:
                    nxt[name] = (t + every) if name != "ctx" else t + every - (time.time() % 60) + 1
                    self._safe(name, fn)
            self._safe("hist", self.poll_one_user)
            time.sleep(1)
        self.sink.flush()
        self.summary()
        log("stopped: --hours reached")

    def _safe(self, name, fn):
        try:
            fn()
        except Exception as e:  # noqa: BLE001 - a long-running recorder must survive network errors
            self.stats["errors"] += 1
            log(f"{name} error {type(e).__name__}: {str(e)[:200]}")
            time.sleep(2)


def coverage():
    """Coverage and lag from recorded chunks (excluding the initial snapshot)."""
    tw = pd.concat([pd.read_parquet(p) for p in sorted(OUT.glob("twaps_*.parquet"))], ignore_index=True)
    ev = pd.concat([pd.read_parquet(p) for p in sorted(OUT.glob("events_*.parquet"))], ignore_index=True)
    live = tw[~tw.initial]
    t0, t1 = live.block_time_ms.min(), live.first_seen_ms.max()
    hs = live[live.source == "hs"]
    lag = (hs.first_seen_ms - hs.block_time_ms) / 1000
    ids = ev.dropna(subset=["twap_id"]).drop_duplicates(["user", "placed_ms"])
    ids = ids[(ids.placed_ms >= t0) & (ids.placed_ms <= t1)]
    ours = ids.merge(live[["user", "block_time_ms", "source"]], left_on=["user", "placed_ms"],
                     right_on=["user", "block_time_ms"], how="inner")
    span = int(ours.twap_id.max() - ours.twap_id.min() + 1) if len(ours) else 0
    out = dict(window_h=round((t1 - t0) / 3.6e6, 2), placements=len(live), via_hypurrscan=len(hs),
               via_history_only=int((live.source == "hist").sum()),
               hs_share_of_known=round(len(hs) / max(len(live), 1), 3),
               twap_id_span=span, distinct_ids_recorded=int(ours.twap_id.nunique()),
               id_coverage=round(ours.twap_id.nunique() / span, 3) if span else None,
               hs_ids_per_hour=round(len(hs) / max((t1 - t0) / 3.6e6, 1e-9), 1),
               id_increase_per_hour=round(span / max((t1 - t0) / 3.6e6, 1e-9), 1),
               lag_s=dict(zip(["p10", "p50", "p90", "p99", "max"],
                              [round(float(lag.quantile(q)), 1) for q in (.1, .5, .9, .99)] + [round(float(lag.max()), 1)])),
               lag_le_60s=round(float((lag <= 60).mean()), 3),
               perp_main=int((hs.asset < 10000).sum()), spot=int(((hs.asset >= 10000) & (hs.asset < 100000)).sum()),
               builder_dex=int((hs.asset >= 100000).sum()), hs_with_twap_id=int(ours[ours.source == "hs"].twap_id.nunique()))
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["record", "coverage"])
    ap.add_argument("--hours", type=float, default=48)
    ap.add_argument("--hs-every", type=float, default=15, help="Hypurrscan poll interval, s")
    ap.add_argument("--status-every", type=float, default=1800, help="twapHistory re-poll per active user, s")
    ap.add_argument("--out", default=str(OUT), help="output dir (tests use a scratch dir)")
    ap.add_argument("--hist-gap", type=float, default=5, help="min seconds between twapHistory calls")
    a = ap.parse_args()
    OUT = Path(a.out)
    if a.cmd == "record":
        OUT.mkdir(parents=True, exist_ok=True)
        log(f"start record hours={a.hours} pid={os.getpid()}")
        Recorder(a).run(a.hours)
    else:
        coverage()
