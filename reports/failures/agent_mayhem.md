# pump.fun Mayhem Mode tokens and the Mayhem agent (agent mayhem, 2026-10-04): FAIL on train

**Bar:** at least 50 trades, net profit after costs, profit factor above 1.2, and still profitable without the 3 best trades.

**Result:** none of the 40 configs passes on train, so validation was not opened. The agent's trade direction is a fair coin flip, so its flow cannot be predicted. Mayhem curves are also not backed by their quoted virtual SOL: the agent drains the real SOL.

## Data

**Mayhem flag.** Each mint's flag comes from the `is_mayhem_mode` field of PumpPortal `create` messages (`scripts/research/mayhem_flags.py` → `data/processed/mayhem_flags.parquet`).
- 88,849 creates: 24,121 Mayhem, 63,458 not, and 1,270 with the field missing (left NULL and excluded).
- The field is present from the first file on.
- Truncated gzip files are read up to the last complete line.

**Tape.** `curve_trades` read-only, train window only, for everything below.

## 1. The agent wallet

`BwWK17cbHxwWBKZkUYvzxLcNQ1YVyaFezduWbtm2de6s` (`research/observations/evidence_mayhem_agent.json`):
- it traded 6,409 of the 6,505 Mayhem mints in train, and 0 non-Mayhem mints;
- 341,881 trades;
- `fee_bps = 0` on every trade, against 95 for everyone else. This matches the reported fee exemption.

No other wallet resembles it. The next Mayhem-only wallets are small scalper bots: 300–950 mints each, paying 95 bps, with median sizes of 0.002–0.02 SOL.

**Behaviour (train, 336k agent trades on 6,271 tokens)**

**Timing.**
- It starts about 1 s after launch (median; 90th percentile 8 s).
- It trades every 3 slots (median; 90th percentile 11).
- It makes a median of 28 trades per token (10th–90th percentile: 5–138).
- It mostly stops within minutes, not 24 h: the median last trade is at 44 s and the 90th percentile at 251 s.

**Sizes.**
- Tiny: median 0.025 SOL, 90th percentile 0.20, maximum 20.
- Bought 15,427 SOL and sold 15,471 SOL in total, so roughly flat.

**Price effect.** Its trades rescale the curve's virtual SOL instead of following constant product:
- |Δvsol| per SOL traded has a median of 45× (10th–90th percentile: 3–350×);
- vsol·vtok changes by a factor of 0.55–1.43 (1st–99th percentile);
- each agent buy moves the price by a median of +17% (log), and each sell by −20%;
- the jump grows with trade size.

In arithmetic terms each tick is fair: the mean return per agent trade is +0.12% (s.e. 0.04%), so the price behaves as a martingale with very high volatility. The log price drifts down from volatility drag.

**Direction: unpredictable.** P(buy) is 0.499 overall, and between 0.494 and 0.502 in every bucket of the information it saw before trading:
- the price relative to launch;
- the previous one or two agent actions;
- whether the previous tape trade was the agent's or another wallet's, and a buy or a sell;
- token age;
- the index of the trade within the token;
- real SOL in the curve;
- slot parity;
- the sub-second of receipt.

An early reading of "buys more when above the launch price" (P = 0.63) was look-ahead: the state *after* the trade had been used. On the state before the trade it vanishes.

None of the 10 most active other wallets anticipates the agent: P(next agent trade is a buy) after their trades is 0.47–0.51.

## 2. Curve state for Mayhem tokens

**Supply.** The launch curve is standard: vsol 30, vtok 1,073M, so the 2B supply is outside the curve. Mayhem curves' vtok reaches 2.073B because agent sells push the extra tokens into the curve.

**Constant product between agent ticks.**
- Non-agent trades obey constant product against the previous recorded state: k ratio 1.0000 from the 1st to the 99.9th percentile (0.9985 at the 0.1th).
- A non-agent buy's SOL divided by the implied constant-product cost is 1.0000 (median).
- So the recorded (vsol, vtok) is a valid fill price between agent ticks.

**vsol is not backed by real SOL.**
- Normally vsol = 30 + rsol. On Mayhem curves rsol is typically 0.03–1 SOL (10th–90th percentile before an agent trade) while vsol can be tens of SOL.
- 8.7% of non-agent sells drain at least 99% of the curve's real SOL.
- At 120 s of agent silence the median rsol is about 0.

An exact constant-product exit is therefore **not valid** unless capped by real SOL.

**Fill models.** Every model applies a 1.25% fee per side and the `event_studies` exit rule, and a config had to pass under both of the first two:
- **std:** the exit sells into the recorded state, with the payout capped by the recorded rsol. This is conservative.
- **own_impact:** the exit sells into the recorded state plus our own buy, with the payout capped by rsol plus our deposit. This is optimistic: it assumes the agent's rescaling and drain leave our SOL alone.
- **no_reserve_cap:** plain `rt()`, for reference.

## 3. Strategies tested (train only)

`scripts/research/mayhem_strategies.py`:
- 0.5 SOL per trade, 1 s latency.
- Tips of 0.001 and 0.01 SOL per transaction.
- Each strategy fires once per token.
- A trigger is kept only if the token's creation, the trigger and the full 1801 s window lie in one gap-free segment and in one split window.

**Exits:**
- TP30/SL15, 300 s;
- TP50/SL20, 300 s;
- TP100/SL30, 1800 s;
- TP200/SL50, 1800 s.

**Grid:** 4 ideas × 2 parameters × 4 exits = 32 Mayhem configs, plus 8 non-Mayhem comparison configs, for **40** in total.

| idea | rule | trades | best config at 0.001 tip (own_impact) | std (capped) |
|---|---|---|---|---|
| fade_sell (V = 5, 15) | buy after an agent sell of −25% or more; age 5–300 s; vsol ≥ V | 3,388–4,258 | V = 15, TP30/SL15: −0.032 SOL/trade, PF 0.64, without best 3 −111.6 SOL | −0.27 |
| ride_buy (V = 5, 15) | buy after an agent buy of +20% or more; same filters | 3,849–4,355 | V = 15, TP30/SL15: −0.033, PF 0.62 | −0.27 |
| post_agent (R = 2, 8) | the agent has traded at least 10 times, then 120 s of silence; rsol ≥ R and vsol ≥ 5 | **0** | untradeable: the agent leaves the curve with about 0 real SOL (10 of 4,820 tokens qualify before the gap and window filters) | — |
| rsol_cross Mayhem (R = 10, 30) | real SOL first reaches R within 600 s | 95 / 14 | R = 10, TP30/SL15: −0.044, PF 0.61 | −0.08 |
| rsol_cross non-Mayhem (comparison) | same rule on non-Mayhem tokens | 3,078 / 709 | R = 30, TP30/SL15: −0.031, PF 0.60 | −0.04 |

**Tips.** At the 0.01 SOL tip every figure is 0.018 SOL per trade worse. For example, the best Mayhem config (fade_sell V = 15, TP30/SL15) goes to −0.050 per trade and −169.7 SOL in total.

**Overall.** All 40 configs have a negative mean under every fill model, including the uncapped one.

**Mayhem vs non-Mayhem at the same real-SOL level.** Mayhem tokens rarely gather real SOL: 95 of 6,505 reach 10 SOL within 10 min, against 3,078 non-Mayhem tokens. The few that do are not better trades (−0.044 vs −0.037 per trade at R = 10).

**Agent events vs a coin flip.** In the forward check before the grid, prices 1 s after agent buys and after agent sells behave alike:
- mean +0.3% / −1.2% / −4.2% over 5 / 30 / 120 s after a sell;
- −0.2% / −1.0% / −3.4% after a buy.

There is no fade or momentum to exploit. The general downward drift comes from non-agent net selling.

## Why it fails

- The agent is a fee-free random walk generator with zero arithmetic drift. Each tick is ±20%, about 8× the 2.5% round-trip fee, but the direction cannot be predicted from anything visible before it.
- It drains the curve's real SOL, so quoted prices often cannot be sold into.
- TP/SL exits on a martingale only rearrange the loss, which equals fees plus tips plus slippage plus the downward drift of the non-agent flow.
- The small Mayhem-only scalper bots net about +0.3 to +3.7 SOL each over train, on 0.002–0.02 SOL trades and thousands of transactions. At a 0.001 SOL tip per transaction, 2,000–8,500 transactions cost 2–8.5 SOL, so that margin does not survive our costs at any size we could trade.

## Limits

- Fills for Mayhem tokens are modelled. How the agent's virtual-SOL rescaling would treat our position is unknown, which is why both the conservative and the optimistic cap models are reported. Neither is close to passing.
- Validation (Oct 3) was not opened, and nothing touched the holdout or data from Oct 4 on.

## Files

- `scripts/research/mayhem_flags.py`, `mayhem_agent.py` and `mayhem_strategies.py`
- `research/observations/evidence_mayhem_agent.json` and `evidence_mayhem_strategies_train.json`
- Derived data: `data/processed/mayhem_flags.parquet` and `mayhem_events_train.parquet`
