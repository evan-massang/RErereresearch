"""Copy-trading a tracked wallet, simulated on the recorded bonding-curve tape.

The question this answers: if we see a trader's buy on chain and copy it after a
realistic delay, paying real fees, do we keep any of their edge?

Event times: block timestamps have 1 s resolution, so each trade's time is
estimated from its slot (linear fit of block time on slot, ~0.4 s per slot).
``available_at`` is when our recorder actually received it, so feed latency is
real, not assumed. Data resolution is therefore ~0.5 s; faster delays are flagged.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

import duckdb

from .sim import Buy, Event, EventStore, ExecutionModel, Sell, run, sweep_latency
from .sim.metrics import performance

RESOLUTION_S = 0.5


def slot_clock(con: duckdb.DuckDBPyConnection) -> tuple[float, float]:
    """ts ~= a + b * slot, fitted on recorded trades."""
    rows = con.execute("SELECT slot, ts FROM curve_trades WHERE slot IS NOT NULL USING SAMPLE 20000").fetchall()
    xs, ys = [r[0] for r in rows], [r[1] for r in rows]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    return my - b * mx + 0.5, b          # +0.5: block ts is floored to the second


def build_store(con: duckdb.DuckDBPyConnection, mints: list[str], start: float, end: float) -> EventStore:
    a, b = slot_clock(con)
    ph = ", ".join("?" for _ in mints)
    rows = con.execute(f"""SELECT recv, slot, mint, usr, buy, sol, tok, vsol, vtok FROM curve_trades
                           WHERE mint IN ({ph}) AND recv < ? ORDER BY recv""", [*mints, end]).fetchall()
    events = []
    for i, (recv, slot, mint, usr, buy, sol, tok, vsol, vtok) in enumerate(rows):
        ts = a + b * slot if slot else recv
        ts = min(ts, recv)
        events.append(Event(ts=ts, available_at=recv, kind="swap", mint=mint, seq=i,
                            data={"side": "buy" if buy else "sell", "trader": usr, "sol": sol, "tok": tok,
                                  "v_sol": vsol, "v_tok": vtok, "price_sol": vsol / vtok}))
    return EventStore(events, resolution_s=RESOLUTION_S)


@dataclass
class MirrorWallet:
    """Buy when the wallet opens a position; sell the same fraction when it sells; time stop."""

    wallet: str
    size_sol: float = 0.5
    max_hold_s: float = 900.0
    name: str = "mirror_wallet"
    _their: dict = field(default_factory=dict)      # mint -> their token position (as we have seen it)
    _held: dict = field(default_factory=dict)       # mint -> when we decided to buy

    def spec(self) -> dict:
        return {"wallet": self.wallet, "size_sol": self.size_sol, "max_hold_s": self.max_hold_s}

    def on_event(self, view, event):
        d = event.data
        if d.get("trader") != self.wallet:
            return []
        m = event.mint
        before = self._their.get(m, 0.0)
        if d["side"] == "buy":
            self._their[m] = before + d["tok"]
            if before <= 0 and m not in self._held:
                self._held[m] = view.now
                return [Buy(m, self.size_sol, tag="copy_entry")]
            return []
        after = max(0.0, before - d["tok"])
        self._their[m] = after
        if m in self._held and before > 0:
            frac = 1.0 if after <= 0.01 * before else min(1.0, d["tok"] / before)
            if frac >= 0.999:
                self._held.pop(m, None)
            return [Sell(m, frac, tag="copy_exit")]
        return []

    def on_tick(self, view):
        out = []
        for m, t0 in list(self._held.items()):
            if view.now - t0 >= self.max_hold_s:
                self._held.pop(m)
                out.append(Sell(m, 1.0, tag="time_stop"))
        return out


def base_execution(**kw) -> ExecutionModel:
    """Fees from on-chain TradeEvents (95 bps protocol + 30 bps creator). Priority fee, slippage
    tolerance and failure rate are assumptions, varied in the sensitivity runs."""
    params = dict(fee_bps=125, priority_fee_sol=0.001, slippage_bps=2000, fail_prob=0.02, seed=7,
                  notes="fee_bps=125 read from pump.fun TradeEvent fee fields on 2026-10-01; "
                        "priority fee / slippage / fail_prob are assumptions")
    params.update(kw)
    return ExecutionModel(**params)


def wallet_mints(con, wallet: str, start: float, end: float) -> list[str]:
    return [r[0] for r in con.execute("SELECT DISTINCT mint FROM curve_trades WHERE usr = ? AND recv >= ? "
                                      "AND recv < ?", [wallet, start, end]).fetchall()]


def copy_test(con, wallet: str, start: float, end: float, *, size_sol: float = 0.5,
              delays_s=(0.5, 1, 2, 3, 5, 10), **exec_kw) -> dict:
    mints = wallet_mints(con, wallet, start, end)
    if not mints:
        return {"wallet": wallet, "mints": 0}
    store = build_store(con, mints, start, end)
    sweep = sweep_latency(lambda: MirrorWallet(wallet, size_sol), store, start=start, end=end,
                          base=base_execution(**exec_kw), delays_s=delays_s)
    return {"wallet": wallet, "mints": len(mints), "events": len(store),
            "sweep": [{"delay_s": s["delay_s"], "below_data_resolution": s["below_data_resolution"],
                       **{k: s["metrics"][k] for k in ("n_trades", "realized_pnl_sol", "expectancy_sol",
                                                        "win_rate", "profit_factor", "failed_tx",
                                                        "protocol_fee_drag_sol", "network_fee_drag_sol",
                                                        "slippage_drag_sol", "open_positions_at_end",
                                                        "median_hold_s")}} for s in sweep]}


def single_run(con, wallet: str, start: float, end: float, *, delay_s: float = 1.0, size_sol: float = 0.5,
               **exec_kw):
    mints = wallet_mints(con, wallet, start, end)
    store = build_store(con, mints, start, end)
    model = base_execution(tx_latency_s=delay_s, **exec_kw)
    strat = MirrorWallet(wallet, size_sol)
    res = run(strat, store, start=start, end=end, execution=model)
    return strat, res, performance(res)
