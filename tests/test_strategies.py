"""DevDumpEntry (H3) on a SYNTHETIC tape: enters only after a big creator buy has been sold at a profit."""
from pipeline.copytrade import base_execution
from pipeline.sim import Event, EventStore, run
from pipeline.strategies import DevDumpEntry

T0 = 1_700_000_000.0


def tape(mint="SYNTHETIC_MINT_D", dev_buy=3.0, dev_sell_at=4, create_at=0.0):
    """Creator buys dev_buy SOL at launch, crowd buys 0.5 SOL/s, creator dumps everything at t=dev_sell_at."""
    v_sol, v_tok = 30.0, 1.073e9
    evs = [Event(ts=T0 + create_at, available_at=T0 + create_at + 0.2, kind="create", mint=mint, seq=0,
                 data={"creator": "SYNTH_DEV", "slot": None})]
    dev_tok = 0.0
    for i in range(0, 60):
        t = T0 + create_at + i
        if i == 0:
            who, side, sol = "SYNTH_DEV", "buy", dev_buy
        elif i == dev_sell_at:
            who, side, sol = "SYNTH_DEV", "sell", None
        else:
            who, side, sol = "SYNTH_CROWD", "buy", 0.5
        if side == "buy":
            out = v_tok - v_sol * v_tok / (v_sol + sol)
            v_sol, v_tok, tok = v_sol + sol, v_tok - out, out
            if who == "SYNTH_DEV":
                dev_tok = tok
        else:
            tok = dev_tok
            sol = v_sol - v_sol * v_tok / (v_tok + tok)
            v_sol, v_tok = v_sol - sol, v_tok + tok
        evs.append(Event(ts=t, available_at=t + 0.3, kind="swap", mint=mint, seq=i + 1,
                         data={"side": side, "trader": who, "tok": tok, "sol": sol, "v_sol": v_sol, "v_tok": v_tok}))
    return evs


def go(evs, **kw):
    s = DevDumpEntry(size_sol=0.5, **kw)
    res = run(s, EventStore(evs, resolution_s=0.5), start=T0, end=T0 + 200,
              execution=base_execution(tx_latency_s=0.5, fail_prob=0.0))
    return [f for _, side, f in res.fills if side == "buy" and f.ok], res


def test_enters_after_profitable_dump_and_exits_on_time():
    buys, res = go(tape())
    assert len(buys) == 1
    assert buys[0].land_at >= T0 + 4.3                # never before the creator's sell is visible
    assert len(res.trades) == 1 and res.trades[0].exit_tags == ("time_exit",)


def test_skips_small_creator_buy_and_late_dump():
    assert go(tape(dev_buy=1.0))[0] == []           # creator's launch buy below threshold
    assert go(tape(dev_sell_at=45))[0] == []        # dump after max_age_s


def test_skips_when_creation_not_seen():
    evs = [e for e in tape() if e.kind != "create"]
    assert go(evs)[0] == []
