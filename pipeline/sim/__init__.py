"""Event-driven simulation with enforced temporal causality.

    events.py     Event / EventStore: the historical record (the "world")
    pit.py        PointInTimeView: the only thing a strategy can read; refuses the future
    features.py   causal feature primitives (velocity, acceleration, flows, drawdown...)
    execution.py  latency, fees, priority fee, slippage tolerance, price impact, failed tx
    engine.py     event loop, orders, portfolio, results, latency sweeps
    metrics.py    Objective A (imitation) and Objective B (performance), kept separate
    splits.py     chronological train/validation/holdout with a one-shot holdout

The strategy never receives the EventStore. Execution, which plays the role of
the real market, does read the true state at fill time; that is what makes
fills realistic and is not available to the strategy's decision.
"""

from .engine import Buy, Sell, SimResult, Strategy, run, sweep_latency
from .events import Event, EventStore
from .execution import ExecutionModel
from .pit import LookaheadError, PointInTimeView

__all__ = ["Buy", "Sell", "SimResult", "Strategy", "run", "sweep_latency", "Event", "EventStore",
           "ExecutionModel", "LookaheadError", "PointInTimeView"]
