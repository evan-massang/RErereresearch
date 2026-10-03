"""SYNTHETIC test data only: checks the paper-trading bar and the frozen-module guard."""
import pytest

from pipeline import paper


def _t(*pnls):
    return [{"t": float(i), "pnl_sol": p} for i, p in enumerate(pnls)]


def test_bar_needs_50_trades():
    v = paper.verdict(_t(*([0.1] * 49)))
    assert not v["checks"]["min_trades"] and not v["pass"]


def test_bar_rejects_top3_dependence():
    v = paper.verdict(_t(*([-0.1] * 50 + [5.0, 5.0, 5.0])))
    assert v["pnl_sol"] > 0 and v["checks"]["profit_factor"] and not v["checks"]["without_top3"] and not v["pass"]


def test_bar_passes_broad_profit():
    v = paper.verdict(_t(*([0.2] * 30 + [-0.1] * 30)))
    assert v["pass"]


def test_freeze_refuses_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(paper, "DIR", tmp_path)
    paper.freeze("synthetic_x", "paper", "verdict", {}, "SYNTHETIC test", 60)
    with pytest.raises(SystemExit):
        paper.freeze("synthetic_x", "paper", "verdict", {}, "SYNTHETIC test", 60)
