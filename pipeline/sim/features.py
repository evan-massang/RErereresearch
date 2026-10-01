"""Causal feature primitives. Every function reads only through a PointInTimeView.

These are building blocks for turning human observations into measurements,
e.g. "buyers keep stepping in" -> unique_buyers(view, mint, 30) and
acceleration(view, mint, unique_buyers, 30). Which of them matter is a research
question; nothing here asserts that any feature predicts anything.
"""

from __future__ import annotations

from typing import Callable

from .events import Event
from .pit import PointInTimeView

WindowFn = Callable[[list[Event]], float]


def _window(view: PointInTimeView, mint: str, window_s: float, offset_s: float = 0.0) -> list[Event]:
    """Swaps that became visible in (now - offset - window, now - offset]."""
    hi = view.now - offset_s
    lo = hi - window_s
    return [e for e in view.events(mint=mint, kind="swap", until=hi)
            if e.available_at + view.detection_latency > lo]


def buys(evs: list[Event]) -> float:
    return float(sum(1 for e in evs if e.data.get("side") == "buy"))


def sells(evs: list[Event]) -> float:
    return float(sum(1 for e in evs if e.data.get("side") == "sell"))


def unique_buyers(evs: list[Event]) -> float:
    return float(len({e.data.get("trader") for e in evs if e.data.get("side") == "buy"}))


def buy_volume_sol(evs: list[Event]) -> float:
    return sum(e.data.get("sol", 0.0) for e in evs if e.data.get("side") == "buy")


def sell_volume_sol(evs: list[Event]) -> float:
    return sum(e.data.get("sol", 0.0) for e in evs if e.data.get("side") == "sell")


def net_flow_sol(evs: list[Event]) -> float:
    return buy_volume_sol(evs) - sell_volume_sol(evs)


def in_window(view: PointInTimeView, mint: str, fn: WindowFn, window_s: float, offset_s: float = 0.0) -> float:
    return fn(_window(view, mint, window_s, offset_s))


def velocity(view: PointInTimeView, mint: str, fn: WindowFn, window_s: float) -> float:
    """fn per second over the last window."""
    return in_window(view, mint, fn, window_s) / window_s


def acceleration(view: PointInTimeView, mint: str, fn: WindowFn, window_s: float) -> float:
    """Change in velocity between the previous window and the latest one (per second, per window)."""
    recent = in_window(view, mint, fn, window_s) / window_s
    prior = in_window(view, mint, fn, window_s, offset_s=window_s) / window_s
    return recent - prior


def price_sol(view: PointInTimeView, mint: str) -> float | None:
    s = view.last_swap(mint)
    if s is None:
        return None
    d = s.data
    if d.get("price_sol") is not None:
        return d["price_sol"]
    if d.get("v_sol") and d.get("v_tok"):
        return d["v_sol"] / d["v_tok"]
    return None


def drawdown_from_high(view: PointInTimeView, mint: str, window_s: float) -> float | None:
    """1 - price_now / max(price over the window); None without prices."""
    evs = _window(view, mint, window_s)
    prices = [e.data.get("price_sol") or (e.data["v_sol"] / e.data["v_tok"] if e.data.get("v_sol") and e.data.get("v_tok") else None)
              for e in evs]
    prices = [p for p in prices if p]
    if not prices:
        return None
    return 1 - prices[-1] / max(prices)


def age_s(view: PointInTimeView, mint: str) -> float | None:
    c = view.created(mint)
    return None if c is None else view.now - c.ts
