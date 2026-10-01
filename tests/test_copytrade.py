"""MirrorWallet on a SYNTHETIC tape: entry on the wallet's first buy, proportional exits, time stop."""
from pipeline.copytrade import MirrorWallet, base_execution
from pipeline.sim import Event, EventStore, run

T0 = 1_700_000_000.0
M = "SYNTHETIC_MINT_C"


def tape(sells=((20, 0.5), (30, 1.0))):
    v_sol, v_tok = 30.0, 1.0e9
    evs = []
    for i in range(1, 60):
        who, side = "SYNTH_CROWD", "buy"
        tok = None
        frac = None
        if i == 5:
            who = "SYNTH_TARGET"
        for t, f in sells:
            if i == t:
                who, side, frac = "SYNTH_TARGET", "sell", f
        sol = 0.4
        if side == "buy":
            out = v_tok - v_sol * v_tok / (v_sol + sol)
            v_sol, v_tok, tok = v_sol + sol, v_tok - out, out
        else:
            tok = target_tokens * frac if frac < 1 else target_left
            sol_out = v_sol - v_sol * v_tok / (v_tok + tok)
            v_sol, v_tok = v_sol - sol_out, v_tok + tok
        if who == "SYNTH_TARGET" and side == "buy":
            target_tokens = target_left = tok
        elif who == "SYNTH_TARGET":
            target_left -= tok
        evs.append(Event(ts=T0 + i, available_at=T0 + i + 0.3, kind="swap", mint=M, seq=i,
                         data={"side": side, "trader": who, "tok": tok, "sol": sol, "v_sol": v_sol, "v_tok": v_tok}))
    return EventStore(evs, resolution_s=0.5)


def test_mirror_entry_and_proportional_exit():
    s = MirrorWallet("SYNTH_TARGET", size_sol=0.2)
    res = run(s, tape(), start=T0, end=T0 + 100, execution=base_execution(tx_latency_s=0.5, fail_prob=0.0))
    buys = [f for _, side, f in res.fills if side == "buy" and f.ok]
    sells = [f for _, side, f in res.fills if side == "sell" and f.ok]
    assert len(buys) == 1 and len(sells) == 2
    assert abs(sells[0].tokens - buys[0].tokens * 0.5) / buys[0].tokens < 1e-6
    assert len(res.trades) == 1 and res.open_marked == []


def test_time_stop():
    s = MirrorWallet("SYNTH_TARGET", size_sol=0.2, max_hold_s=10)
    res = run(s, tape(sells=()), start=T0, end=T0 + 100, execution=base_execution(fail_prob=0.0))
    assert len(res.trades) == 1 and res.trades[0].exit_tags == ("time_stop",)


def test_slot_clock_is_deterministic_and_follows_drift():
    """SYNTHETIC slots whose length drifts from 0.40 s to 0.44 s: the local fit tracks it within 1 s."""
    from pipeline.copytrade import SlotClock

    slots, t, ts = [], 1_700_000_000.0, []
    for i in range(20000):
        slots.append(100 + i)
        ts.append(int(t))
        t += 0.40 + 0.04 * i / 20000
    a, b = SlotClock(slots, ts), SlotClock(slots, ts)
    true_t = 1_700_000_000.0 + sum(0.40 + 0.04 * k / 20000 for k in range(15000))
    assert a(15100) == b(15100)
    assert abs(a(15100) - true_t) < 1.0


def test_basket_enters_once_and_follows_the_leader():
    """SYNTHETIC: two basket wallets; only the first opener's sells drive our exit."""
    from pipeline.copytrade import MirrorBasket

    v_sol, v_tok, evs = 30.0, 1.0e9, []
    plan = {5: ("SYNTH_A", "buy"), 7: ("SYNTH_B", "buy"), 20: ("SYNTH_B", "sell"), 30: ("SYNTH_A", "sell")}
    held = {}
    for i in range(1, 50):
        who, side = plan.get(i, ("SYNTH_CROWD", "buy"))
        if side == "buy":
            sol = 0.4
            tok = v_tok - v_sol * v_tok / (v_sol + sol)
            v_sol, v_tok = v_sol + sol, v_tok - tok
            held[who] = held.get(who, 0) + tok
        else:
            tok = held[who]
            sol = v_sol - v_sol * v_tok / (v_tok + tok)
            v_sol, v_tok = v_sol - sol, v_tok + tok
        evs.append(Event(ts=T0 + i, available_at=T0 + i + 0.3, kind="swap", mint=M, seq=i,
                         data={"side": side, "trader": who, "tok": tok, "sol": sol, "v_sol": v_sol, "v_tok": v_tok}))
    s = MirrorBasket(("SYNTH_A", "SYNTH_B"), size_sol=0.2)
    res = run(s, EventStore(evs, resolution_s=0.5), start=T0, end=T0 + 100,
              execution=base_execution(tx_latency_s=0.5, fail_prob=0.0))
    assert len(res.trades) == 1
    assert res.trades[0].closed_at >= T0 + 30          # exit follows SYNTH_A (the opener), not SYNTH_B
