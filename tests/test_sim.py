"""Simulator tests. All market data here is SYNTHETIC (made-up mints, reserves, wallets)."""

from datetime import datetime, timedelta, timezone

import pytest

from pipeline import annotations, findings, observations
from pipeline.ingest_web import ingest_document
from pipeline.sim import Buy, Event, EventStore, ExecutionModel, LookaheadError, Sell, run, sweep_latency
from pipeline.sim import features as F
from pipeline.sim.engine import ClosedTrade, SimResult
from pipeline.sim.metrics import imitation, performance
from pipeline.sim.splits import HoldoutBurnedError, define_splits, evaluate_holdout, run_on_split
from tests.conftest import FIXTURES

T0 = 1_700_000_000.0
MINT = "SYNTHETIC_MINT_A"


def make_store(n: int = 60, lag: float = 0.0, with_reserves: bool = True, extra: list | None = None) -> EventStore:
    """A SYNTHETIC token: mostly buys (rising price), every 4th swap a sell."""
    evs = [Event(ts=T0, available_at=T0 + lag, kind="create", mint=MINT, data={"symbol": "SYNA", "supply": 1e9})]
    v_sol, v_tok = 30.0, 1.0e9
    for i in range(1, n + 1):
        if i % 4:
            sol = 0.5
            out = v_tok - v_sol * v_tok / (v_sol + sol)
            v_sol, v_tok = v_sol + sol, v_tok - out
            data = {"side": "buy", "trader": f"SYNTH_W{i % 7}", "sol": sol}
        else:
            tok_in = 0.3 * v_tok / v_sol
            sol_out = v_sol - v_sol * v_tok / (v_tok + tok_in)
            v_sol, v_tok = v_sol - sol_out, v_tok + tok_in
            data = {"side": "sell", "trader": f"SYNTH_S{i % 3}", "sol": sol_out}
        data["price_sol"] = v_sol / v_tok
        if with_reserves:
            data |= {"v_sol": v_sol, "v_tok": v_tok}
        evs.append(Event(ts=T0 + i, available_at=T0 + i + lag, kind="swap", mint=MINT, seq=i, data=data))
    return EventStore(evs + (extra or []), resolution_s=1.0)


class BuyThenSell:
    """SYNTHETIC test strategy: buy on the first visible swap, sell everything after hold_s."""

    name = "test_buy_then_sell"

    def __init__(self, sol: float = 1.0, hold_s: float = 10.0, fractions=(1.0,)):
        self.sol, self.hold_s, self.fractions = sol, hold_s, list(fractions)
        self.bought = False
        self.seen = []

    def spec(self):
        return {"sol": self.sol, "hold_s": self.hold_s, "fractions": self.fractions}

    def on_event(self, view, event):
        self.seen.append((view.now, event.available_at))
        if event.kind == "swap" and not self.bought:
            self.bought = True
            return [Buy(event.mint, self.sol)]
        return []

    def on_tick(self, view):
        pos = view.portfolio["positions"].get(MINT)
        if pos and pos["tokens"] > 0 and view.now - pos["opened_at"] >= self.hold_s and self.fractions:
            return [Sell(MINT, self.fractions.pop(0))]
        return []


def model(**kw) -> ExecutionModel:
    base = dict(fee_bps=100, tx_latency_s=0.5, priority_fee_sol=0.001)
    return ExecutionModel(**{**base, **kw})


# ------------------------------------------------------------------ causality

def test_strategy_cannot_request_the_future():
    class Peeker(BuyThenSell):
        def on_event(self, view, event):
            view.events(until=view.now + 5)

    with pytest.raises(LookaheadError):
        run(Peeker(), make_store(), start=T0, end=T0 + 100, execution=model())


def test_view_only_ever_returns_visible_events():
    canary = Event(ts=T0 + 40.5, available_at=T0 + 40.5, kind="social", mint=None, data={"text": "SYNTHETIC canary"})

    class Checker(BuyThenSell):
        def on_event(self, view, event):
            for e in view.events():
                assert e.available_at + view.detection_latency <= view.now
            if view.now < T0 + 40.5:
                assert all(e.kind != "social" for e in view.events())
            return super().on_event(view, event)

    run(Checker(), make_store(extra=[canary]), start=T0, end=T0 + 100, execution=model(detection_latency_s=0.3))


def test_detection_latency_delays_delivery():
    s = BuyThenSell()
    run(s, make_store(lag=0.2), start=T0, end=T0 + 100, execution=model(detection_latency_s=2.0))
    assert all(abs(now - (avail + 2.0)) < 1e-9 for now, avail in s.seen)


def test_later_data_does_not_exist_for_the_run():
    s = BuyThenSell(hold_s=1000)
    run(s, make_store(), start=T0, end=T0 + 20.5, execution=model())
    assert max(avail for _, avail in s.seen) < T0 + 20.5


# ------------------------------------------------------------------ execution

def test_amm_math_and_fee():
    from pipeline.sim.events import PoolState

    m = model(fee_bps=100)
    pool = PoolState(ts=0, v_sol=30.0, v_tok=1e9, price_sol=None, liquidity_sol=None)
    tokens, fee = m.quote_buy(pool, 1.0)
    assert fee == pytest.approx(0.01)
    assert tokens == pytest.approx(1e9 - 30.0 * 1e9 / 30.99)
    sol, fee2 = m.quote_sell(pool, tokens)
    gross = 30.0 - 30.0 * 1e9 / (1e9 + tokens)
    assert sol == pytest.approx(gross * 0.99) and fee2 == pytest.approx(gross * 0.01)


def test_more_latency_means_worse_entry_in_a_rising_market():
    fast = run(BuyThenSell(hold_s=1000), make_store(), start=T0, end=T0 + 60, execution=model(tx_latency_s=0.1))
    slow = run(BuyThenSell(hold_s=1000), make_store(), start=T0, end=T0 + 60, execution=model(tx_latency_s=5.0))
    tok = lambda r: [f for _, side, f in r.fills if side == "buy"][0].tokens
    assert tok(slow) < tok(fast)


def test_slippage_tolerance_reverts_and_still_costs_fees():
    res = run(BuyThenSell(), make_store(), start=T0, end=T0 + 60,
              execution=model(slippage_bps=0, quote_latency_s=0.0, tx_latency_s=3.0))
    (_, _, fill), = res.fills
    assert not fill.ok and fill.reason == "slippage"
    assert res.failed_entry_fees_sol == pytest.approx(0.001 + 5000 / 1e9)
    assert res.trades == [] and res.open_marked == []


def test_failed_transactions():
    res = run(BuyThenSell(), make_store(), start=T0, end=T0 + 60, execution=model(fail_prob=1.0))
    assert all(not f.ok and f.reason == "failed_tx" for _, _, f in res.fills)


def test_orders_landing_after_end_are_never_sent():
    class LateBuyer(BuyThenSell):
        def on_event(self, view, event):
            return [Buy(MINT, 1.0)] if view.now >= T0 + 19 and not self.bought and not setattr(self, "bought", True) else []

    res = run(LateBuyer(), make_store(), start=T0, end=T0 + 20, execution=model(tx_latency_s=5.0))
    assert res.fills == []


def test_missing_reserves_refuse_to_assume_zero_impact():
    with pytest.raises(ValueError, match="zero price impact"):
        run(BuyThenSell(), make_store(with_reserves=False), start=T0, end=T0 + 60, execution=model())


def test_round_trip_accounting():
    res = run(BuyThenSell(hold_s=10), make_store(), start=T0, end=T0 + 60, execution=model())
    (t,) = res.trades
    buys = [f for _, s, f in res.fills if s == "buy" and f.ok]
    sells = [f for _, s, f in res.fills if s == "sell" and f.ok]
    assert t.cost_sol == pytest.approx(sum(f.sol for f in buys))
    assert t.proceeds_sol == pytest.approx(sum(f.sol for f in sells))
    assert t.pnl_sol == pytest.approx(t.proceeds_sol - t.cost_sol - t.network_fees_sol)
    assert t.hold_s >= 10


def test_partial_sells_close_the_position_cleanly():
    res = run(BuyThenSell(hold_s=5, fractions=(0.5, 1.0)), make_store(), start=T0, end=T0 + 60, execution=model())
    assert len(res.trades) == 1 and res.open_marked == []
    assert len([1 for _, s, f in res.fills if s == "sell" and f.ok]) == 2


def test_open_positions_are_marked_not_realized():
    res = run(BuyThenSell(hold_s=1000), make_store(), start=T0, end=T0 + 30, execution=model())
    assert res.trades == [] and len(res.open_marked) == 1
    assert res.open_marked[0].open_at_end


def test_latency_sweep_flags_sub_resolution_delays():
    out = sweep_latency(lambda: BuyThenSell(), make_store(), start=T0, end=T0 + 60, base=model(),
                        delays_s=(0.1, 1, 2))
    assert [o["below_data_resolution"] for o in out] == [True, False, False]


# ------------------------------------------------------------------ features

def test_features_are_causal_and_see_acceleration():
    seen = {}

    class FeatureProbe(BuyThenSell):
        def on_event(self, view, event):
            if abs(view.now - (T0 + 30)) < 1e-9:
                seen["buys10"] = F.in_window(view, MINT, F.buys, 10)
                seen["uniq10"] = F.in_window(view, MINT, F.unique_buyers, 10)
                seen["acc"] = F.acceleration(view, MINT, F.buys, 10)
                seen["age"] = F.age_s(view, MINT)
                seen["dd"] = F.drawdown_from_high(view, MINT, 30)
            return []

    run(FeatureProbe(), make_store(), start=T0, end=T0 + 60, execution=model())
    assert seen["buys10"] == 8          # swaps 21..30: 21,22,23,25,26,27,29,30 are buys
    assert seen["uniq10"] <= 7
    assert seen["age"] == pytest.approx(30)
    assert 0 <= seen["dd"] < 0.05


# ------------------------------------------------------------------ metrics

def _trade(pnl, t):
    return ClosedTrade("SYNTH", t - 10, t, 1.0, 1.0 + pnl, 0.01, 0.0, 0.0, 0, ("e",), ("x",))


def test_performance_metrics_by_hand():
    trades = [_trade(p, T0 + i * 100) for i, p in enumerate([0.5, -0.2, 0.1, -0.3, 2.0])]
    res = SimResult("s", {}, {}, T0, T0 + 3600, 1.0, "fp", trades, [], [], 0.0, 0)
    m = performance(res)
    assert m["n_trades"] == 5
    assert m["realized_pnl_sol"] == pytest.approx(2.1)
    assert m["win_rate"] == pytest.approx(0.6)
    assert m["profit_factor"] == pytest.approx(2.6 / 0.5)
    assert m["max_drawdown_sol"] == pytest.approx(0.4)        # 0.5 -> 0.3 -> 0.4 -> 0.1
    assert m["pnl_without_best_trade_sol"] == pytest.approx(0.1)
    assert m["best_trade_share_of_pnl"] == pytest.approx(2.0 / 2.1)


def test_imitation_metrics():
    pairs = [
        {"human": "BUY", "model": "BUY", "human_t": 10, "model_t": 12},
        {"human": "BUY", "model": "SKIP"},
        {"human": "SKIP", "model": "SKIP"},
        {"human": "SKIP", "model": "BUY"},
        {"human": "BUY", "model": "BUY", "human_t": 50, "model_t": 49},
    ]
    m = imitation(pairs)
    assert m["agreement"] == pytest.approx(3 / 5)
    assert m["precision"] == pytest.approx(2 / 3) and m["recall"] == pytest.approx(2 / 3)
    assert m["timing_n"] == 2 and m["timing_median_s"] == pytest.approx(0.5)
    assert m["confusion"]["BUY"]["SKIP"] == 1


# ------------------------------------------------------------------ splits & holdout

def _dt(s):
    return datetime.fromtimestamp(T0 + s, timezone.utc)


def _hypothesis(con):
    sid, _ = ingest_document(con, str(FIXTURES / "synthetic_page.html"), is_synthetic=True)
    trader = annotations.add_trader(con, "SYNTHETIC-TRADER-H", is_synthetic=True)
    oid = observations.add_observation(con, source_id=sid, modality="said", kind="quote", trader_id=trader,
                                       content="SYNTHETIC statement", extractor="human", is_synthetic=True)
    fid = findings.add_finding(con, trader_id=trader, funnel_stage="entry", evidence_type="stated",
                               statement="SYNTHETIC stated rule", evidence=[("observation", oid, "supports")],
                               is_synthetic=True)
    return findings.add_hypothesis(con, statement="SYNTHETIC hypothesis", measurable_definition="buy first swap",
                                   rationale="SYNTHETIC test of the holdout machinery", basis_finding_ids=[fid],
                                   is_synthetic=True)


def test_splits_must_be_chronological(archive):
    with pytest.raises(ValueError, match="overlaps"):
        define_splits(archive, "bad", {"train": (_dt(0), _dt(30)), "validation": (_dt(20), _dt(40)),
                                       "holdout": (_dt(40), _dt(60))}, is_synthetic=True)


def test_validation_never_sees_holdout_and_holdout_is_one_shot(archive):
    define_splits(archive, "syn", {"train": (_dt(0), _dt(20)), "validation": (_dt(20), _dt(40)),
                                   "holdout": (_dt(40), _dt(60))}, is_synthetic=True)
    hyp = _hypothesis(archive)
    store = make_store()

    s = BuyThenSell(hold_s=1000)
    run_id, res = run_on_split(archive, strategy=s, store=store, split_set="syn", split_name="validation",
                               execution=model(), hypothesis_id=hyp, is_synthetic=True)
    assert max(avail for _, avail in s.seen) < T0 + 40
    assert archive.execute("SELECT split_name FROM sim_runs WHERE run_id = ?", [run_id]).fetchone()[0] == "validation"
    with pytest.raises(ValueError):
        run_on_split(archive, strategy=s, store=store, split_set="syn", split_name="holdout", execution=model())

    with pytest.raises(ValueError, match="pass criteria"):
        evaluate_holdout(archive, strategy=BuyThenSell(), store=store, split_set="syn", execution=model(),
                         hypothesis_id=hyp, pass_criteria=[], is_synthetic=True)
    crit = [{"metric": "n_trades", "op": ">=", "value": 1}]
    run_id, passed, _ = evaluate_holdout(archive, strategy=BuyThenSell(), store=store, split_set="syn",
                                         execution=model(), hypothesis_id=hyp, pass_criteria=crit, is_synthetic=True)
    assert passed
    assert archive.execute("SELECT status FROM data_splits WHERE split_set='syn' AND split_name='holdout'"
                           ).fetchone()[0] == "burned"
    assert archive.execute("SELECT status FROM hypotheses WHERE hypothesis_id = ?", [hyp]).fetchone()[0] == "holdout_passed"
    with pytest.raises(HoldoutBurnedError):
        evaluate_holdout(archive, strategy=BuyThenSell(hold_s=3), store=store, split_set="syn", execution=model(),
                         hypothesis_id=hyp, pass_criteria=crit, is_synthetic=True)
    actions = [r[0] for r in archive.execute("SELECT action FROM holdout_log ORDER BY logged_at").fetchall()]
    assert actions == ["evaluated", "refused"]
    with pytest.raises(ValueError, match="already exists"):
        define_splits(archive, "syn", {"train": (_dt(0), _dt(20)), "validation": (_dt(20), _dt(40)),
                                       "holdout": (_dt(40), _dt(60))}, is_synthetic=True)
