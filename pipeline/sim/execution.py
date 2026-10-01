"""Execution model: what actually happens between "decide" and "filled".

Timeline for an order decided at time t (the strategy's clock):

    submit_at = t + decision_latency          (thinking / compute)
    quote_at  = submit_at + quote_latency     (fetch price to set min-out)
    land_at   = quote_at + tx_latency         (transaction lands on chain)

The quote sets the minimum acceptable output (slippage tolerance). The fill is
computed against the TRUE pool state at ``land_at`` with our size on the AMM
curve (price impact), after protocol fees. If the fill is worse than the
minimum, or the transaction randomly fails, it reverts and only network fees
are paid. Sells can only realise what the pool pays at land time — never a
candle high.

No protocol fee is assumed: ``fee_bps`` must be given explicitly (fees differ
by venue and have changed over time; cite the source in the run notes).
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field

from .events import EventStore, PoolState

LAMPORTS_PER_SOL = 1_000_000_000


@dataclass(frozen=True)
class Fill:
    ok: bool
    reason: str                    # filled | slippage | failed_tx | no_pool | migrated | after_end
    land_at: float
    sol: float                     # SOL spent (buy, excl. network fees) or received (sell, net of protocol fee)
    tokens: float
    expected: float                # output promised by the quote (tokens for buy, SOL for sell)
    protocol_fee_sol: float
    network_fee_sol: float
    slippage_sol: float            # value lost vs the quote, in SOL (>= 0 when worse than quoted)


@dataclass
class ExecutionModel:
    fee_bps: float                           # protocol fee on the SOL leg, e.g. venue trading fee
    detection_latency_s: float = 0.0
    decision_latency_s: float = 0.0
    quote_latency_s: float = 0.0
    tx_latency_s: float = 0.0
    priority_fee_sol: float = 0.0            # per transaction (incl. tips), paid even when it fails
    base_fee_lamports: int = 5000            # Solana base fee per signature
    slippage_bps: float = 1500.0             # min-out tolerance vs the quote
    fail_prob: float = 0.0                   # chance a tx fails for reasons other than slippage
    allow_liquidity_estimate: bool = True    # use liquidity_sol when reserves are missing
    seed: int = 0
    notes: str = ""
    _rng: random.Random = field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self):
        for name in ("fee_bps", "detection_latency_s", "decision_latency_s", "quote_latency_s",
                     "tx_latency_s", "priority_fee_sol", "slippage_bps"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be >= 0")
        if not 0 <= self.fail_prob <= 1:
            raise ValueError("fail_prob must be in [0, 1]")
        self._rng = random.Random(self.seed)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("_rng", None)
        return d

    @property
    def network_fee_sol(self) -> float:
        return self.priority_fee_sol + self.base_fee_lamports / LAMPORTS_PER_SOL

    def timeline(self, decided_at: float) -> tuple[float, float]:
        quote_at = decided_at + self.decision_latency_s + self.quote_latency_s
        return quote_at, quote_at + self.tx_latency_s

    # ---- AMM math (constant product on virtual reserves) ----

    def _reserves(self, pool: PoolState) -> tuple[float, float]:
        if pool.v_sol and pool.v_tok:
            return pool.v_sol, pool.v_tok
        if self.allow_liquidity_estimate and pool.liquidity_sol and pool.price_sol:
            # Approximate a constant-product pool holding liquidity_sol of SOL at the current price.
            return pool.liquidity_sol, pool.liquidity_sol / pool.price_sol
        raise ValueError("pool has neither reserves nor (liquidity_sol and price_sol); "
                         "refusing to assume zero price impact")

    def quote_buy(self, pool: PoolState, sol_in: float) -> tuple[float, float]:
        """(tokens_out, protocol_fee_sol) for spending sol_in."""
        v_sol, v_tok = self._reserves(pool)
        fee = sol_in * self.fee_bps / 1e4
        net = sol_in - fee
        return v_tok - (v_sol * v_tok) / (v_sol + net), fee

    def quote_sell(self, pool: PoolState, tokens_in: float) -> tuple[float, float]:
        """(sol_out_net, protocol_fee_sol) for selling tokens_in."""
        v_sol, v_tok = self._reserves(pool)
        gross = v_sol - (v_sol * v_tok) / (v_tok + tokens_in)
        fee = gross * self.fee_bps / 1e4
        return gross - fee, fee

    # ---- order execution ----

    def _fail(self, reason: str, land_at: float, expected: float) -> Fill:
        return Fill(False, reason, land_at, 0.0, 0.0, expected, 0.0, self.network_fee_sol, 0.0)

    def execute(self, store: EventStore, *, side: str, mint: str, decided_at: float, amount: float,
                end: float | None = None) -> Fill:
        """amount = SOL to spend (buy) or tokens to sell (sell)."""
        quote_at, land_at = self.timeline(decided_at)
        if end is not None and land_at >= end:
            return Fill(False, "after_end", land_at, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)   # never sent
        q_pool = store.pool_at(mint, quote_at)
        if q_pool is None:
            return self._fail("no_pool", land_at, 0.0)
        quote_fn = self.quote_buy if side == "buy" else self.quote_sell
        expected, _ = quote_fn(q_pool, amount)
        l_pool = store.pool_at(mint, land_at)
        if l_pool is None:
            return self._fail("no_pool", land_at, expected)
        if l_pool.migrated:
            return self._fail("migrated", land_at, expected)
        if self._rng.random() < self.fail_prob:
            return self._fail("failed_tx", land_at, expected)
        actual, fee = quote_fn(l_pool, amount)
        if actual < expected * (1 - self.slippage_bps / 1e4):
            return self._fail("slippage", land_at, expected)
        if side == "buy":
            price_land = (amount - fee) / actual if actual > 0 else 0.0
            slippage_sol = max(0.0, (expected - actual) * price_land)
            return Fill(True, "filled", land_at, amount, actual, expected, fee, self.network_fee_sol, slippage_sol)
        return Fill(True, "filled", land_at, actual, amount, expected, fee, self.network_fee_sol,
                    max(0.0, expected - actual))
