# Curve order-flow event triggers (agent curve_flow, 2026-10-04): FAIL on train

**Bar:** at least 50 trades, net profit after costs, profit factor above 1.2, and still profitable without the 3 best trades.

## What was tested

Four discrete order-flow triggers on the pump.fun bonding curve. None had been tested before. The rules were fixed before any outcome was computed (`scripts/research/curve_flow_triggers.py`).

| idea | trigger | variants |
|---|---|---|
| whale | A buy of at least X SOL by a wallet that is neither the creator nor a launch sniper (bought in slot ≤ create slot + 1), and that was already in the recorded tape on an earlier UTC day. | X = 3, 5 |
| absorb | A non-creator sell of at least 2 SOL. The trigger is the first later trade, within N s, that prints above the price just before the sell. Token at least 30 s old. | N = 10, 30 s |
| accum | A non-creator, non-sniper wallet makes its k-th buy of the token. Each buy is at least 0.2 SOL, buys are at least 2 s apart, and the wallet has not sold. | k = 3, 5 |
| burst | At least B distinct first-time buyers inside 30 s, after at least 120 s with no trades, on a token older than 300 s. | B = 4, 7 |

Each trigger uses only trades received at or before it, and fires once per token (the first time).

**Exits:** four take-profit/stop-loss pairs:
- 30/15% and 50/20%, each with a 300 s maximum hold;
- 100/30% and 200/50%, each with an 1800 s maximum hold.

**Grid:** 4 ideas × 2 variants × 4 exits = **32 configs**.

**Fills:** `event_studies.outcomes()`, which gives:
- exact constant-product fills;
- 0.5 SOL per trade;
- 1.25% fee per side;
- 1 s latency;
- completion handling.

**Tips:** 0.001 and 0.01 SOL per transaction (two transactions per trade).

**Data hygiene:**
- Only `curve_trades` outside the holdout window and before Oct 4 00:00 UTC.
- The tape has recording gaps. A trigger is kept only if the token's creation, the trigger and the full 1800 s window sit inside one gap-free recording segment (no gap over 60 s).

**Split:**
- Train: Oct 1 up to 19:15 UTC, plus Oct 2.
- Validation: Oct 3.

## Result: FAIL on train, so validation was not looked at

The figures below are on train at the 0.001 SOL tip (`research/observations/evidence_curve_flow_train_20261004.json`). All 32 configs have a negative mean and a profit factor below 1, and none passes the bar.

| idea / variant | trades | best exit | SOL per trade | profit factor |
|---|---|---|---|---|
| absorb, N = 10 | 877 | TP50/SL20, 300 s | −0.020 | 0.80 |
| absorb, N = 30 | 1271 | TP30/SL15, 300 s | −0.029 | 0.66 |
| whale, 5 SOL | 144 | TP30/SL15, 300 s | −0.033 | 0.59 |
| accum, k = 5 | 174 | TP30/SL15, 300 s | −0.032 | 0.58 |
| burst, B = 7 | 206 | TP30/SL15, 300 s | −0.042 | 0.47 |
| burst, B = 4 | 327 | TP200/SL50, 1800 s | −0.042 | 0.61 |
| accum, k = 3 | 915 | TP30/SL15, 300 s | −0.041 | 0.53 |
| whale, 3 SOL | 628 | TP30/SL15, 300 s | −0.046 | 0.48 |

**The best config is absorb with N = 10 and a TP50/SL20, 300 s exit.**
- At a 0.001 SOL tip: 877 trades, −17.35 SOL in total, PF 0.80, −19.29 SOL without the best 3, 34.5% winners.
- At a 0.01 SOL tip: −33.14 SOL.

**The losses are consistent across train segments.** Every idea and variant is negative on Oct 1 and on Oct 2 separately. For example, absorb N = 10 is −0.022 SOL per trade on Oct 1 and −0.014 on Oct 2.

**Caveat on whale train data.** Whale triggers exist only on Oct 2 train data, because Oct 1 has no earlier recorded day.

Validation events were built in the same pass, but they were not scored, because no config passed on train.

## Reading

Each of these flow events is visible to every bot on the tape. By the time a 1 s-late entry fills, the move the event implies has already happened:
- **whale:** the median whale trigger comes 18 s after launch;
- **accum and burst:** the median entries chase buy flow;
- **absorb:** the recovery print is itself the bounce.

After that, the round-trip fee and slippage (at least about 0.0125 SOL per trade before tips), plus the later fade, outweigh any continuation. This is the same pattern as H1/H2 and iterations 5–13: public on-chain flow signals are priced in before a 1 s trader can act.
