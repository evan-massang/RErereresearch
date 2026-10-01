"""PointInTimeView: the strategy's entire window onto the world.

At clock time ``now`` an event is visible iff
``event.available_at + detection_latency <= now``. Any request that reaches past
``now`` raises LookaheadError instead of silently returning less. Strategies get
this object and nothing else.
"""

from __future__ import annotations

from typing import Iterable

from .events import Event, EventStore


class LookaheadError(RuntimeError):
    """A strategy asked for information from after the current simulated time."""


class PointInTimeView:
    def __init__(self, store: EventStore, detection_latency: float = 0.0):
        self.__store = store
        self.__detection = detection_latency
        self.__now = float("-inf")
        self.__n_visible = 0
        self.portfolio: dict = {}          # engine-maintained, read-only by convention

    @property
    def now(self) -> float:
        return self.__now

    @property
    def detection_latency(self) -> float:
        return self.__detection

    def _advance(self, t: float) -> None:          # engine only
        if t < self.__now:
            raise RuntimeError("simulation clock cannot move backwards")
        self.__now = t
        self.__n_visible = self.__store.visible_prefix(t, self.__detection)

    def _visible_at(self, e: Event) -> float:
        return e.available_at + self.__detection

    def events(self, *, mint: str | None = None, kind: str | None = None,
               since: float | None = None, until: float | None = None) -> list[Event]:
        """Visible events, optionally filtered; ``since``/``until`` bound the visibility time."""
        if until is not None and until > self.__now:
            raise LookaheadError(f"requested data until {until} but now is {self.__now}")
        cutoff = self.__now if until is None else until
        source: Iterable[Event] = (self.__store.events_by_mint(mint) if mint is not None
                                   else self.__store.events[: self.__n_visible])
        out = []
        for e in source:
            vt = self._visible_at(e)
            if vt > cutoff:
                if mint is not None:
                    break            # per-mint lists are ordered by availability
                continue
            if kind is not None and e.kind != kind:
                continue
            if since is not None and vt < since:
                continue
            out.append(e)
        return out

    def swaps(self, mint: str, since: float | None = None) -> list[Event]:
        return self.events(mint=mint, kind="swap", since=since)

    def last_swap(self, mint: str) -> Event | None:
        s = self.swaps(mint)
        return s[-1] if s else None

    def created(self, mint: str) -> Event | None:
        c = self.events(mint=mint, kind="create")
        return c[0] if c else None

    def mints(self) -> list[str]:
        seen: dict[str, None] = {}
        for e in self.__store.events[: self.__n_visible]:
            if e.mint is not None:
                seen.setdefault(e.mint, None)
        return list(seen)
