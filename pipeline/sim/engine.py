"""Event loop, orders, portfolio accounting.

The strategy is called (a) whenever an event becomes visible and (b) on a
regular tick while it holds positions or has orders in flight (for time-based
exits). It sees only the PointInTimeView, and it learns about its own fills
only once they land.
"""

from __future__ import annotations

import dataclasses
import heapq
import itertools
from dataclasses import dataclass, field
from typing import Callable, Iterable, Protocol

from .events import Event, EventStore
from .execution import ExecutionModel, Fill
from .pit import PointInTimeView


@dataclass(frozen=True)
class Buy:
    mint: str
    sol: float
    tag: str = ""

    def __post_init__(self):
        if self.sol <= 0:
            raise ValueError("Buy.sol must be positive")


@dataclass(frozen=True)
class Sell:
    mint: str
    fraction: float = 1.0
    tag: str = ""

    def __post_init__(self):
        if not 0 < self.fraction <= 1:
            raise ValueError("Sell.fraction must be in (0, 1]")


Order = Buy | Sell


class Strategy(Protocol):
    name: str

    def spec(self) -> dict:
        """All parameters that define the strategy (hashed into sim_runs.strategy_hash)."""

    def on_event(self, view: PointInTimeView, event: Event) -> Iterable[Order]:
        ...

    def on_tick(self, view: PointInTimeView) -> Iterable[Order]:
        ...


@dataclass
class Position:
    mint: str
    opened_at: float
    tokens: float = 0.0
    reserved: float = 0.0              # tokens committed to in-flight sells
    cost_sol: float = 0.0              # SOL spent on filled buys (incl. protocol fee)
    proceeds_sol: float = 0.0          # SOL received from filled sells (net of protocol fee)
    protocol_fees_sol: float = 0.0
    network_fees_sol: float = 0.0      # incl. failed transactions
    slippage_sol: float = 0.0
    failed_tx: int = 0
    entry_tags: list[str] = field(default_factory=list)
    exit_tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ClosedTrade:
    mint: str
    opened_at: float
    closed_at: float
    cost_sol: float
    proceeds_sol: float
    protocol_fees_sol: float
    network_fees_sol: float
    slippage_sol: float
    failed_tx: int
    entry_tags: tuple[str, ...]
    exit_tags: tuple[str, ...]
    open_at_end: bool = False          # marked to market at the end, not actually sold

    @property
    def pnl_sol(self) -> float:
        return self.proceeds_sol - self.cost_sol - self.network_fees_sol

    @property
    def hold_s(self) -> float:
        return self.closed_at - self.opened_at


@dataclass
class SimResult:
    strategy: str
    spec: dict
    execution: dict
    start: float
    end: float
    resolution_s: float
    dataset_fingerprint: str
    trades: list[ClosedTrade]
    open_marked: list[ClosedTrade]
    fills: list[tuple[str, str, Fill]]                 # (mint, side, fill)
    failed_entry_fees_sol: float
    events_delivered: int

    @property
    def realized_pnl_sol(self) -> float:
        return sum(t.pnl_sol for t in self.trades) - self.failed_entry_fees_sol


def run(strategy: Strategy, store: EventStore, *, start: float, end: float, execution: ExecutionModel,
        tick_s: float = 1.0) -> SimResult:
    """Simulate ``strategy`` over [start, end). Nothing available at or after ``end`` exists."""
    if end <= start:
        raise ValueError("end must be after start")
    world = store.until(end)
    view = PointInTimeView(world, execution.detection_latency_s)
    positions: dict[str, Position] = {}
    closed: list[ClosedTrade] = []
    fills: list[tuple[str, str, Fill]] = []
    failed_entry_fees = 0.0
    in_flight = 0
    counter = itertools.count()
    heap: list = []
    det = execution.detection_latency_s

    for e in world.events:
        vt = e.available_at + det
        if start <= vt < end:
            heap.append((vt, 1, next(counter), "event", e))
    heapq.heapify(heap)
    tick_pending = False
    delivered = 0

    def publish() -> None:
        view.portfolio = {
            "positions": {m: {"tokens": p.tokens - p.reserved, "cost_sol": p.cost_sol,
                              "proceeds_sol": p.proceeds_sol, "opened_at": p.opened_at}
                          for m, p in positions.items() if p.tokens > 0 or p.reserved > 0},
            "in_flight": in_flight,
        }

    def submit(orders: Iterable[Order], t: float) -> None:
        nonlocal in_flight, failed_entry_fees
        for o in orders or []:
            amount = 0.0
            if isinstance(o, Buy):
                fill = execution.execute(world, side="buy", mint=o.mint, decided_at=t, amount=o.sol, end=end)
            else:
                pos = positions.get(o.mint)
                free = (pos.tokens - pos.reserved) if pos else 0.0
                if free <= 0:
                    continue
                amount = free * o.fraction
                pos.reserved += amount
                fill = execution.execute(world, side="sell", mint=o.mint, decided_at=t, amount=amount, end=end)
            if fill.reason == "after_end":
                if isinstance(o, Sell):
                    positions[o.mint].reserved -= amount
                continue
            in_flight += 1
            heapq.heappush(heap, (fill.land_at, 0, next(counter), "fill", (o, fill, amount)))

    def land(o: Order, fill: Fill, reserved: float) -> None:
        nonlocal in_flight, failed_entry_fees
        in_flight -= 1
        side = "buy" if isinstance(o, Buy) else "sell"
        fills.append((o.mint, side, fill))
        pos = positions.get(o.mint)
        if isinstance(o, Buy):
            if not fill.ok:
                if pos:
                    pos.network_fees_sol += fill.network_fee_sol
                    pos.failed_tx += 1
                else:
                    failed_entry_fees += fill.network_fee_sol
                return
            if pos is None:
                pos = positions[o.mint] = Position(mint=o.mint, opened_at=fill.land_at)
            pos.tokens += fill.tokens
            pos.cost_sol += fill.sol
            pos.protocol_fees_sol += fill.protocol_fee_sol
            pos.network_fees_sol += fill.network_fee_sol
            pos.slippage_sol += fill.slippage_sol
            pos.entry_tags.append(o.tag)
            return
        pos.reserved = max(0.0, pos.reserved - reserved)    # this sell's reservation, success or not
        if not fill.ok:
            pos.network_fees_sol += fill.network_fee_sol
            pos.failed_tx += 1
            return
        pos.tokens -= fill.tokens
        pos.proceeds_sol += fill.sol
        pos.protocol_fees_sol += fill.protocol_fee_sol
        pos.network_fees_sol += fill.network_fee_sol
        pos.slippage_sol += fill.slippage_sol
        pos.exit_tags.append(o.tag)
        if pos.tokens <= 1e-9 and pos.reserved <= 1e-9:
            closed.append(_close(pos, fill.land_at))
            del positions[o.mint]

    while heap:
        t, _, _, kind, payload = heapq.heappop(heap)
        if t >= end:
            break
        view._advance(t)
        if kind == "fill":
            land(*payload)
            publish()
            continue
        publish()
        if kind == "event":
            delivered += 1
            submit(strategy.on_event(view, payload), t)
        else:
            tick_pending = False
            submit(strategy.on_tick(view), t)
        publish()
        if (positions or in_flight) and not tick_pending and t + tick_s < end:
            heapq.heappush(heap, (t + tick_s, 2, next(counter), "tick", None))
            tick_pending = True

    open_marked = []
    for pos in positions.values():
        pool = world.pool_at(pos.mint, end)
        value = 0.0
        if pos.tokens > 0 and pool is not None and not pool.migrated:
            try:
                value, _ = execution.quote_sell(pool, pos.tokens)
            except ValueError:
                value = 0.0
        p = dataclasses.replace(pos, proceeds_sol=pos.proceeds_sol + value)
        open_marked.append(_close(p, end, open_at_end=True))

    return SimResult(
        strategy=strategy.name, spec=strategy.spec(), execution=execution.to_dict(), start=start, end=end,
        resolution_s=store.resolution_s, dataset_fingerprint=world.fingerprint(), trades=closed,
        open_marked=open_marked, fills=fills, failed_entry_fees_sol=failed_entry_fees, events_delivered=delivered)


def _close(pos: Position, t: float, open_at_end: bool = False) -> ClosedTrade:
    return ClosedTrade(pos.mint, pos.opened_at, t, pos.cost_sol, pos.proceeds_sol, pos.protocol_fees_sol,
                       pos.network_fees_sol, pos.slippage_sol, pos.failed_tx, tuple(pos.entry_tags),
                       tuple(pos.exit_tags), open_at_end)


def sweep_latency(strategy_factory: Callable[[], Strategy], store: EventStore, *, start: float, end: float,
                  base: ExecutionModel, delays_s: Iterable[float] = (0.1, 0.25, 0.5, 1, 2, 3, 5, 10),
                  metrics_fn: Callable[[SimResult], dict] | None = None) -> list[dict]:
    """Re-run with end-to-end delay d (all latency in tx_latency) for each d.

    Delays finer than the data's time resolution are run but flagged, since the
    data cannot distinguish them.
    """
    from .metrics import performance

    metrics_fn = metrics_fn or performance
    out = []
    for d in delays_s:
        model = dataclasses.replace(base, detection_latency_s=0.0, decision_latency_s=0.0,
                                    quote_latency_s=0.0, tx_latency_s=float(d))
        res = run(strategy_factory(), store, start=start, end=end, execution=model)
        out.append({"delay_s": float(d), "below_data_resolution": d < store.resolution_s,
                    "metrics": metrics_fn(res)})
    return out
