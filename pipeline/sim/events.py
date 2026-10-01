"""Historical events and the store that holds them.

Times are float seconds since the Unix epoch (UTC).

* ``ts``            when the event happened (block time, post time)
* ``available_at``  when a real-time feed could first have observed it
                    (>= ts; e.g. ts + indexer lag). Strategies see an event only
                    at ``available_at + detection_latency``.

Swap events carry the pool state *after* the swap when the source provides it
(``v_sol`` / ``v_tok`` virtual reserves for constant-product / bonding-curve
pools). Without reserves, a ``liquidity_sol`` estimate is needed to model price
impact; with neither, execution refuses rather than assume zero impact.
"""

from __future__ import annotations

import bisect
import hashlib
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

KINDS = {"create", "swap", "complete", "migrate", "social", "other"}   # complete = curve finished (no flag on the pool)


@dataclass(frozen=True)
class Event:
    ts: float
    available_at: float
    kind: str
    mint: str | None = None
    seq: int = 0
    data: Mapping[str, Any] = field(default_factory=dict, compare=False)

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError(f"unknown event kind {self.kind!r}")
        if self.available_at < self.ts:
            raise ValueError("available_at cannot precede ts")


@dataclass(frozen=True)
class PoolState:
    ts: float
    v_sol: float | None
    v_tok: float | None
    price_sol: float | None          # SOL per token
    liquidity_sol: float | None
    migrated: bool = False


class EventStore:
    """Immutable, time-indexed event history."""

    def __init__(self, events: Iterable[Event], resolution_s: float):
        if resolution_s <= 0:
            raise ValueError("resolution_s must be positive")
        self.resolution_s = resolution_s
        self._events = sorted(events, key=lambda e: (e.available_at, e.ts, e.seq))
        self._avail = [e.available_at for e in self._events]
        self._by_mint: dict[str, list[Event]] = {}
        for e in self._events:
            if e.mint is not None:
                self._by_mint.setdefault(e.mint, []).append(e)
        # per-mint swaps ordered by *event* time, for the execution model
        self._swaps_by_ts: dict[str, list[Event]] = {}
        self._migrated_at: dict[str, float] = {}
        for mint, evs in self._by_mint.items():
            swaps = sorted((e for e in evs if e.kind == "swap"), key=lambda e: (e.ts, e.seq))
            self._swaps_by_ts[mint] = swaps
            mig = [e.ts for e in evs if e.kind == "migrate"]
            if mig:
                self._migrated_at[mint] = min(mig)
        self._swap_ts = {m: [e.ts for e in s] for m, s in self._swaps_by_ts.items()}

    def __len__(self) -> int:
        return len(self._events)

    @property
    def events(self) -> list[Event]:
        return list(self._events)

    def span(self) -> tuple[float, float]:
        if not self._events:
            raise ValueError("empty store")
        return self._events[0].available_at, self._events[-1].available_at

    def visible_prefix(self, cutoff: float, detection_latency: float = 0.0) -> int:
        """Number of events with available_at + detection_latency <= cutoff."""
        return bisect.bisect_right(self._avail, cutoff - detection_latency)

    def events_by_mint(self, mint: str) -> list[Event]:
        return self._by_mint.get(mint, [])

    def until(self, end: float) -> "EventStore":
        """Only events available strictly before ``end`` (used to wall off later splits)."""
        return EventStore((e for e in self._events if e.available_at < end), self.resolution_s)

    # ---- world state for execution (NOT exposed to strategies) ----

    def pool_at(self, mint: str, t: float) -> PoolState | None:
        """True pool state at time t: after every swap with ts <= t.

        Swaps sharing our landing time are assumed to execute before us
        (conservative: we never get ahead of same-block flow).
        """
        ts_list = self._swap_ts.get(mint)
        if not ts_list:
            return None
        i = bisect.bisect_right(ts_list, t) - 1
        if i < 0:
            return None
        d = self._swaps_by_ts[mint][i].data
        mig = self._migrated_at.get(mint)
        return PoolState(ts=ts_list[i], v_sol=d.get("v_sol"), v_tok=d.get("v_tok"), price_sol=d.get("price_sol"),
                         liquidity_sol=d.get("liquidity_sol"), migrated=mig is not None and mig < t)

    def fingerprint(self) -> str:
        h = hashlib.sha256()
        h.update(f"{self.resolution_s}|{len(self._events)}".encode())
        for e in self._events:
            h.update(f"{e.ts:.6f}|{e.available_at:.6f}|{e.kind}|{e.mint}|{e.seq}".encode())
        return h.hexdigest()[:16]
