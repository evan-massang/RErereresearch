"""Objective A (decision imitation) and Objective B (trading performance).

These are computed and stored separately on purpose: a strategy can imitate a
trader perfectly and lose money, or trade well while disagreeing with them.
"""

from __future__ import annotations

import statistics
from typing import Iterable

from .engine import SimResult


def _max_drawdown(pnls_in_order: list[float]) -> float:
    peak = cum = 0.0
    dd = 0.0
    for p in pnls_in_order:
        cum += p
        peak = max(peak, cum)
        dd = max(dd, peak - cum)
    return dd


def performance(result: SimResult, rug_recovery_threshold: float = 0.1) -> dict:
    """Objective B on realized (closed) trades; open positions are reported separately."""
    trades = sorted(result.trades, key=lambda t: t.closed_at)
    pnls = [t.pnl_sol for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    total = sum(pnls) - result.failed_entry_fees_sol
    hours = max((result.end - result.start) / 3600, 1e-9)
    ordered = sorted(pnls, reverse=True)
    top_k = max(1, int(round(len(ordered) * 0.05))) if ordered else 0
    fills = [f for _, _, f in result.fills]
    out = {
        "n_trades": len(trades),
        "realized_pnl_sol": total,
        "expectancy_sol": (sum(pnls) / len(pnls)) if pnls else None,
        "median_trade_sol": statistics.median(pnls) if pnls else None,
        "win_rate": (len(wins) / len(pnls)) if pnls else None,
        "avg_win_sol": (sum(wins) / len(wins)) if wins else None,
        "avg_loss_sol": (sum(losses) / len(losses)) if losses else None,
        "profit_factor": (sum(wins) / -sum(losses)) if losses else (None if not wins else float("inf")),
        "max_drawdown_sol": _max_drawdown(pnls),
        "protocol_fee_drag_sol": sum(t.protocol_fees_sol for t in trades),
        "network_fee_drag_sol": sum(t.network_fees_sol for t in trades) + result.failed_entry_fees_sol,
        "slippage_drag_sol": sum(t.slippage_sol for t in trades),
        "failed_tx": sum(1 for f in fills if not f.ok),
        "failed_tx_by_reason": _count(f.reason for f in fills if not f.ok),
        "rug_like_trades": sum(1 for t in trades if t.cost_sol > 0 and t.proceeds_sol / t.cost_sol < rug_recovery_threshold),
        "trades_per_hour": len(trades) / hours,
        "median_hold_s": statistics.median([t.hold_s for t in trades]) if trades else None,
        "pnl_without_best_trade_sol": (total - ordered[0]) if ordered else None,
        "pnl_without_top5pct_sol": (total - sum(ordered[:top_k])) if ordered else None,
        "best_trade_share_of_pnl": (ordered[0] / total) if ordered and total > 0 else None,
        "open_positions_at_end": len(result.open_marked),
        "open_marked_value_pnl_sol": sum(t.pnl_sol for t in result.open_marked),
        "data_resolution_s": result.resolution_s,
    }
    return out


def _count(items: Iterable[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for i in items:
        out[i] = out.get(i, 0) + 1
    return out


def imitation(pairs: Iterable[dict], positive: str = "BUY") -> dict:
    """Objective A. Each pair: {"human": label, "model": label, "human_t": s|None, "model_t": s|None}.

    Pairs are decision points where the human's choice is known (e.g. every token
    they visibly examined, so SKIPs count). Precision/recall are for ``positive``.
    """
    pairs = list(pairs)
    if not pairs:
        return {"n": 0}
    tp = sum(1 for p in pairs if p["human"] == positive and p["model"] == positive)
    fp = sum(1 for p in pairs if p["human"] != positive and p["model"] == positive)
    fn = sum(1 for p in pairs if p["human"] == positive and p["model"] != positive)
    agree = sum(1 for p in pairs if p["human"] == p["model"])
    labels = sorted({p["human"] for p in pairs} | {p["model"] for p in pairs})
    confusion = {h: {m: sum(1 for p in pairs if p["human"] == h and p["model"] == m) for m in labels} for h in labels}
    timing = [p["model_t"] - p["human_t"] for p in pairs
              if p["human"] == p["model"] == positive and p.get("human_t") is not None and p.get("model_t") is not None]
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (2 * precision * recall / (precision + recall)) if precision and recall else None
    q = statistics.quantiles(timing, n=4) if len(timing) >= 2 else None
    return {
        "n": len(pairs), "agreement": agree / len(pairs), "positive_label": positive,
        "precision": precision, "recall": recall, "f1": f1,
        "base_rate": sum(1 for p in pairs if p["human"] == positive) / len(pairs),
        "confusion": confusion,
        "timing_n": len(timing),
        "timing_median_s": statistics.median(timing) if timing else None,
        "timing_iqr_s": (q[2] - q[0]) if q else None,
    }
