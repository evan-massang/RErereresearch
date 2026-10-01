"""Candidate strategies built from research findings. Each reads only what the
PointInTimeView delivers (incremental state from events already seen)."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field

import duckdb

from .market import SUPPLY
from .sim import Buy, Event, EventStore, Sell

RESOLUTION_S = 0.5


def build_market_store(con: duckdb.DuckDBPyConnection, start: float, end: float,
                       history_s: float = 900.0) -> EventStore:
    """All bonding-curve creates + swaps available before ``end`` (with ``history_s`` before ``start``)."""
    from .copytrade import slot_clock

    clock = slot_clock(con)
    events = []
    for i, (recv, slot, mint, creator) in enumerate(con.execute(
            "SELECT recv, slot, mint, creator FROM curve_creates WHERE recv >= ? AND recv < ? ORDER BY recv, rowid",
            [start - history_s, end]).fetchall()):
        ts = min(clock(slot), recv) if slot else recv
        events.append(Event(ts=ts, available_at=recv, kind="create", mint=mint, seq=i,
                            data={"creator": creator, "slot": slot}))
    rows = con.execute("""SELECT recv, slot, mint, usr, buy, sol, tok, vsol, vtok FROM curve_trades
                          WHERE recv >= ? AND recv < ? ORDER BY recv, rowid""", [start - history_s, end]).fetchall()
    for i, (recv, slot, mint, usr, buy, sol, tok, vsol, vtok) in enumerate(rows):
        ts = min(clock(slot), recv) if slot else recv
        events.append(Event(ts=ts, available_at=recv, kind="swap", mint=mint, seq=10_000_000 + i,
                            data={"side": "buy" if buy else "sell", "trader": usr, "sol": sol, "tok": tok,
                                  "slot": slot, "v_sol": vsol, "v_tok": vtok, "price_sol": vsol / vtok}))
    for i, (recv, mint) in enumerate(con.execute(
            "SELECT recv, mint FROM curve_completes WHERE recv >= ? AND recv < ? ORDER BY recv, rowid",
            [start - history_s, end]).fetchall()):
        events.append(Event(ts=recv, available_at=recv, kind="complete", mint=mint, seq=20_000_000 + i, data={}))
    return EventStore(events, resolution_s=RESOLUTION_S)


@dataclass
class _Tok:
    created: float
    creator: str
    cslot: int | None
    pos: dict = field(default_factory=lambda: defaultdict(float))
    buys: deque = field(default_factory=deque)        # (t, wallet) buys, last 30 s
    flow: deque = field(default_factory=deque)        # (t, signed sol), last 30 s
    snipers: set = field(default_factory=set)
    dev_sold: bool = False
    price: float = 0.0


@dataclass
class StructureEntry:
    """H1: hot new token + developer already sold + snipers hold < snipers_max_pct of supply."""

    size_sol: float = 0.5
    max_age_s: float = 60.0
    min_buyers_10s: int = 8
    min_inflow_30s: float = 1.5
    snipers_max_pct: float = 10.0
    hold_s: float = 60.0
    stop_pct: float = 25.0
    min_age_s: float = 0.0
    max_buyers_10s: int | None = None
    max_inflow_30s: float | None = None
    require_dev_sold: bool = True
    name: str = "h1_structure_entry"
    _toks: dict = field(default_factory=dict)
    _held: dict = field(default_factory=dict)           # mint -> (t_decided, ref_price)
    _done: set = field(default_factory=set)

    def spec(self) -> dict:
        return {k: getattr(self, k) for k in ("name", "size_sol", "min_age_s", "max_age_s", "min_buyers_10s",
                                               "max_buyers_10s", "min_inflow_30s", "max_inflow_30s",
                                               "require_dev_sold", "snipers_max_pct", "hold_s", "stop_pct")}

    def on_event(self, view, ev):
        now = view.now
        if ev.kind == "create":
            self._toks[ev.mint] = _Tok(created=ev.ts, creator=ev.data["creator"], cslot=ev.data.get("slot"))
            return []
        if ev.kind != "swap":
            return []
        st = self._toks.get(ev.mint)
        if st is None:
            return []                                   # creation not seen: structure unknown, skip
        d = ev.data
        u = d["trader"]
        st.price = d["v_sol"] / d["v_tok"]
        if d["side"] == "buy":
            st.pos[u] += d["tok"]
            if u != st.creator:
                st.buys.append((now, u))
                if st.cslot is not None and d.get("slot") is not None and d["slot"] <= st.cslot + 5:
                    st.snipers.add(u)
        else:
            st.pos[u] -= d["tok"]
            if u == st.creator:
                st.dev_sold = True
        st.flow.append((now, d["sol"] if d["side"] == "buy" else -d["sol"]))
        while st.buys and st.buys[0][0] < now - 30:
            st.buys.popleft()
        while st.flow and st.flow[0][0] < now - 30:
            st.flow.popleft()
        out = []
        if ev.mint in self._held:
            t0, ref = self._held[ev.mint]
            if st.price <= ref * (1 - self.stop_pct / 100):
                self._held.pop(ev.mint)
                out.append(Sell(ev.mint, 1.0, tag="stop"))
            return out
        age = now - st.created
        if ev.mint in self._done or age > self.max_age_s or age < self.min_age_s:
            return out
        if self.require_dev_sold and not st.dev_sold:
            return out
        buyers_10 = len({w for t, w in st.buys if t >= now - 10})
        inflow_30 = sum(x for _, x in st.flow)
        if buyers_10 < self.min_buyers_10s or inflow_30 < self.min_inflow_30s:
            return out
        if (self.max_buyers_10s is not None and buyers_10 > self.max_buyers_10s) or \
                (self.max_inflow_30s is not None and inflow_30 > self.max_inflow_30s):
            return out
        snip_pct = sum(max(st.pos[w], 0) for w in st.snipers) / SUPPLY * 100
        if snip_pct >= self.snipers_max_pct:
            return out
        self._done.add(ev.mint)
        self._held[ev.mint] = (now, st.price)
        return [Buy(ev.mint, self.size_sol, tag=f"{self.name}_entry")]

    def on_tick(self, view):
        out = []
        for m, (t0, _) in list(self._held.items()):
            if view.now - t0 >= self.hold_s:
                self._held.pop(m)
                out.append(Sell(m, 1.0, tag="time_exit"))
        # drop state of tokens too old to ever qualify (memory)
        if len(self._toks) > 20000:
            cutoff = view.now - 2 * self.max_age_s
            for m in [m for m, s in self._toks.items() if s.created < cutoff and m not in self._held]:
                del self._toks[m]
        return out


@dataclass
class _Dev:
    created: float
    creator: str
    dev_in: float = 0.0                                 # SOL the creator put into the curve
    dev_out: float = 0.0                                # SOL the creator took out
    first_sell: float | None = None
    price: float = 0.0


@dataclass
class DevDumpEntry:
    """H3 (from Decu's on-stream entries): buy a young token shortly after its creator's first sell, when the
    creator put in a large launch buy and has already taken out more SOL than they put in."""

    size_sol: float = 1.0
    max_age_s: float = 30.0
    min_dev_buy_sol: float = 2.9
    max_since_dump_s: float = 20.0
    hold_s: float = 20.0
    stop_pct: float = 20.0
    name: str = "h3_dev_dump_entry"
    _toks: dict = field(default_factory=dict)
    _held: dict = field(default_factory=dict)           # mint -> (t_decided, ref_price)
    _done: set = field(default_factory=set)

    def spec(self) -> dict:
        return {k: getattr(self, k) for k in ("name", "size_sol", "max_age_s", "min_dev_buy_sol", "max_since_dump_s",
                                               "hold_s", "stop_pct")}

    def on_event(self, view, ev):
        now = view.now
        if ev.kind == "create":
            self._toks[ev.mint] = _Dev(created=ev.ts, creator=ev.data["creator"])
            return []
        if ev.kind != "swap":
            return []
        st = self._toks.get(ev.mint)
        if st is None:
            return []                                   # creation not seen: creator unknown, skip
        d = ev.data
        st.price = d["v_sol"] / d["v_tok"]
        if d["trader"] == st.creator:
            if d["side"] == "buy":
                st.dev_in += d["sol"]
            else:
                st.dev_out += d["sol"]
                if st.first_sell is None:
                    st.first_sell = now
        if ev.mint in self._held:
            t0, ref = self._held[ev.mint]
            if st.price <= ref * (1 - self.stop_pct / 100):
                self._held.pop(ev.mint)
                return [Sell(ev.mint, 1.0, tag="stop")]
            return []
        if ev.mint in self._done or now - st.created > self.max_age_s or st.first_sell is None:
            return []
        if st.dev_in < self.min_dev_buy_sol or st.dev_out <= st.dev_in or now - st.first_sell > self.max_since_dump_s:
            return []
        self._done.add(ev.mint)
        self._held[ev.mint] = (now, st.price)
        return [Buy(ev.mint, self.size_sol, tag=f"{self.name}_entry")]

    def on_tick(self, view):
        out = []
        for m, (t0, _) in list(self._held.items()):
            if view.now - t0 >= self.hold_s:
                self._held.pop(m)
                out.append(Sell(m, 1.0, tag="time_exit"))
        if len(self._toks) > 20000:
            cutoff = view.now - 2 * self.max_age_s
            for m in [m for m, s in self._toks.items() if s.created < cutoff and m not in self._held]:
                del self._toks[m]
        return out


@dataclass
class DevDumpRunner(DevDumpEntry):
    """H5: H3's entry with Decu-like exits: cut what does not move quickly, let runners go toward migration.

    Exits, all on the bonding curve: stop at -stop_pct from entry; at follow_through_s, sell unless the price
    is up >= min_gain_pct; trailing stop trail_pct below the peak since entry; take profit once the market cap
    reaches tp_mcap_sol (near migration); time stop at max_hold_s.
    """

    stop_pct: float = 25.0
    follow_through_s: float = 45.0
    min_gain_pct: float = 30.0
    trail_pct: float = 40.0
    tp_mcap_sol: float = 300.0
    max_hold_s: float = 1800.0
    hold_s: float = 1800.0
    name: str = "h5_dev_dump_runner"
    _peak: dict = field(default_factory=dict)
    _checked: set = field(default_factory=set)

    def spec(self) -> dict:
        return {k: getattr(self, k) for k in ("name", "size_sol", "max_age_s", "min_dev_buy_sol", "max_since_dump_s",
                                               "stop_pct", "follow_through_s", "min_gain_pct", "trail_pct",
                                               "tp_mcap_sol", "max_hold_s")}

    def on_event(self, view, ev):
        if ev.kind not in ("create", "swap"):
            return []
        held_before = ev.mint in self._held
        out = super().on_event(view, ev) if not held_before else []
        if not held_before:
            if any(o.tag.endswith("_entry") for o in out):
                self._peak[ev.mint] = self._held[ev.mint][1]
            return out
        # a held position: update state ourselves (the parent's stop is replaced by the exits below)
        st = self._toks.get(ev.mint)
        d = ev.data
        st.price = d["v_sol"] / d["v_tok"]
        t0, ref = self._held[ev.mint]
        self._peak[ev.mint] = max(self._peak[ev.mint], st.price)
        reason = None
        if st.price <= ref * (1 - self.stop_pct / 100):
            reason = "stop"
        elif st.price <= self._peak[ev.mint] * (1 - self.trail_pct / 100):
            reason = "trail"
        elif st.price * SUPPLY >= self.tp_mcap_sol:
            reason = "take_profit"
        if reason:
            self._held.pop(ev.mint)
            return [Sell(ev.mint, 1.0, tag=reason)]
        return []

    def on_tick(self, view):
        out = []
        for m, (t0, ref) in list(self._held.items()):
            st = self._toks.get(m)
            age = view.now - t0
            if age >= self.max_hold_s:
                self._held.pop(m)
                out.append(Sell(m, 1.0, tag="time_exit"))
            elif age >= self.follow_through_s and m not in self._checked:
                self._checked.add(m)
                if st is None or st.price < ref * (1 + self.min_gain_pct / 100):
                    self._held.pop(m)
                    out.append(Sell(m, 1.0, tag="no_follow_through"))
        if len(self._toks) > 20000:
            cutoff = view.now - 2 * self.max_age_s
            for m in [m for m, s in self._toks.items() if s.created < cutoff and m not in self._held]:
                del self._toks[m]
        return out



@dataclass
class GoodDevLaunch:
    """H7 (solo trader, no copying): buy the launch of a creator whose earlier launches (seen since the run
    started) migrated often; cut it if it does not move, let it run toward migration.

    Dev record is point-in-time: launches and curve completions observed before this launch. Entries only
    after trade_from (earlier events build the record). Exits as DevDumpRunner, all on the bonding curve;
    a position still open when its curve completes is sold at the final curve state.
    """

    size_sol: float = 0.5
    min_prior_migrations: int = 1
    min_migration_rate: float = 0.2
    max_prior_launches: int | None = None
    trade_from: float = 0.0
    stop_pct: float = 30.0
    follow_through_s: float = 60.0
    min_gain_pct: float = 20.0
    trail_pct: float = 40.0
    tp_mcap_sol: float = 300.0
    max_hold_s: float = 1800.0
    name: str = "h7_good_dev_launch"
    _launches: dict = field(default_factory=lambda: defaultdict(list))     # creator -> mints
    _creator: dict = field(default_factory=dict)                           # mint -> creator
    _migrated: set = field(default_factory=set)
    _held: dict = field(default_factory=dict)                              # mint -> (t, ref price or None)
    _peak: dict = field(default_factory=dict)
    _price: dict = field(default_factory=dict)
    _checked: set = field(default_factory=set)

    def spec(self) -> dict:
        return {k: getattr(self, k) for k in ("name", "size_sol", "min_prior_migrations", "min_migration_rate",
                                               "max_prior_launches", "trade_from", "stop_pct", "follow_through_s",
                                               "min_gain_pct", "trail_pct", "tp_mcap_sol", "max_hold_s")}

    def _qualifies(self, creator: str) -> bool:
        prior = self._launches[creator]
        mig = sum(1 for m in prior if m in self._migrated)
        if mig < self.min_prior_migrations or mig / max(1, len(prior)) < self.min_migration_rate:
            return False
        return self.max_prior_launches is None or len(prior) <= self.max_prior_launches

    def on_event(self, view, ev):
        now = view.now
        if ev.kind == "complete":
            self._migrated.add(ev.mint)
            if ev.mint in self._held:                 # sell what is left at the final curve state
                self._held.pop(ev.mint)
                return [Sell(ev.mint, 1.0, tag="curve_complete")]
            return []
        if ev.kind == "create":
            c = ev.data["creator"]
            buy = now >= self.trade_from and self._qualifies(c)
            self._launches[c].append(ev.mint)
            self._creator[ev.mint] = c
            if buy:
                self._held[ev.mint] = (now, None)
                return [Buy(ev.mint, self.size_sol, tag=f"{self.name}_entry")]
            return []
        if ev.kind != "swap" or ev.mint not in self._held:
            return []
        p = ev.data["v_sol"] / ev.data["v_tok"]
        self._price[ev.mint] = p
        t0, ref = self._held[ev.mint]
        if ref is None:                               # reference = first price seen after our decision
            self._held[ev.mint] = (t0, p)
            self._peak[ev.mint] = p
            return []
        self._peak[ev.mint] = max(self._peak[ev.mint], p)
        reason = ("stop" if p <= ref * (1 - self.stop_pct / 100) else
                  "trail" if p <= self._peak[ev.mint] * (1 - self.trail_pct / 100) else
                  "take_profit" if p * SUPPLY >= self.tp_mcap_sol else None)
        if reason:
            self._held.pop(ev.mint)
            return [Sell(ev.mint, 1.0, tag=reason)]
        return []

    def on_tick(self, view):
        out = []
        for m, (t0, ref) in list(self._held.items()):
            age = view.now - t0
            if age >= self.max_hold_s:
                self._held.pop(m)
                out.append(Sell(m, 1.0, tag="time_exit"))
            elif age >= self.follow_through_s and m not in self._checked:
                self._checked.add(m)
                if ref is None or self._price.get(m, 0) < ref * (1 + self.min_gain_pct / 100):
                    self._held.pop(m)
                    out.append(Sell(m, 1.0, tag="no_follow_through"))
        return out



@dataclass
class GoodDevDip(GoodDevLaunch):
    """H7: a qualifying good dev's launch, bought after the launch rush has flushed out.

    At entry_delay_s after the launch (first trade seen after that moment), buy if the market cap is at most
    max_entry_mcap_sol. Exit at tp_multiple x the entry price, at -stop_pct, or after max_hold_s.
    """

    entry_delay_s: float = 60.0
    max_entry_mcap_sol: float = 45.0
    tp_multiple: float = 2.0
    stop_pct: float = 35.0
    name: str = "h7_good_dev_dip"
    _pending: dict = field(default_factory=dict)      # mint -> launch time

    def spec(self) -> dict:
        return {k: getattr(self, k) for k in ("name", "size_sol", "min_prior_migrations", "min_migration_rate",
                                               "max_prior_launches", "trade_from", "entry_delay_s",
                                               "max_entry_mcap_sol", "tp_multiple", "stop_pct", "max_hold_s")}

    def on_event(self, view, ev):
        now = view.now
        if ev.kind == "complete":
            self._migrated.add(ev.mint)
            self._pending.pop(ev.mint, None)
            if ev.mint in self._held:
                self._held.pop(ev.mint)
                return [Sell(ev.mint, 1.0, tag="curve_complete")]
            return []
        if ev.kind == "create":
            c = ev.data["creator"]
            if now >= self.trade_from and self._qualifies(c):
                self._pending[ev.mint] = now
            self._launches[c].append(ev.mint)
            return []
        if ev.kind != "swap":
            return []
        p = ev.data["v_sol"] / ev.data["v_tok"]
        m = ev.mint
        if m in self._pending and now - self._pending[m] >= self.entry_delay_s:
            self._pending.pop(m)
            if p * SUPPLY <= self.max_entry_mcap_sol:
                self._held[m] = (now, p)
                return [Buy(m, self.size_sol, tag=f"{self.name}_entry")]
            return []
        if m in self._held:
            t0, ref = self._held[m]
            if p >= ref * self.tp_multiple or p <= ref * (1 - self.stop_pct / 100):
                self._held.pop(m)
                return [Sell(m, 1.0, tag="take_profit" if p >= ref * self.tp_multiple else "stop")]
        return []

    def on_tick(self, view):
        out = []
        for m, (t0, _) in list(self._held.items()):
            if view.now - t0 >= self.max_hold_s:
                self._held.pop(m)
                out.append(Sell(m, 1.0, tag="time_exit"))
        return out
