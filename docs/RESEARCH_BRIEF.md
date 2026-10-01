# Research brief (from the project owner, 2026-10-01)

> This is the governing brief for the project. It is reproduced from the
> owner's instructions with light formatting only. When the brief and any
> other document disagree, the brief wins. Changes to research direction
> should be recorded here with a date.

## Context

We are researching how genuinely skilled Solana memecoin traders make
short-duration trading decisions.

This project did NOT begin with the assumption that we should invent a
completely new trading strategy. The original problem was:

> Why can certain experienced human memecoin traders repeatedly look at the
> same information available to everyone else and identify trades that appear
> much better than random, while an automated system often becomes enormously
> more complicated and still performs badly?

We previously explored building a sophisticated system involving live
social/narrative monitoring, J7 Tracker, Axiom, token discovery,
holder/developer analysis, transaction activity, machine learning, narrative
classification, fast local decision models, and historical simulations.

However, an important realization emerged: a professional human trader
usually does not reconstruct the entire Solana blockchain manually. They often
use products such as Axiom and J7 Tracker because those products already
organize enormous amounts of information into something a human can evaluate
extremely quickly.

Axiom can expose, in one interface, combinations of: token age, market
capitalization, liquidity, transaction activity, buys / sells, holders,
developer holdings, top-holder concentration, sniper information, insider
information, bundle information, wallet/trader activity, chart behavior,
social links, token metadata, attention/activity indicators, and other
token-specific information.

J7 Tracker can function as a very fast narrative/social-information source. We
have previously verified that J7 exposes structured social posts containing:
post text, author, timestamp, follower information, translation, images,
videos, quoted posts, replies, URLs, and other metadata.

**A professional human trader is still a human.** They cannot calculate
thousands of blockchain variables in their head. Instead, they may have become
extremely good at recognizing a relatively small number of meaningful patterns
from already-organized information. Potentially:

```
J7 / social information + Axiom / market information + chart + experience
        ↓
human recognizes setup
        ↓
BUY / SKIP
        ↓
manage trade
        ↓
EXIT
```

Our objective is to discover what that actual mental decision process is.

- Do NOT assume J7 or Axiom are the only tools that matter. They are important
  examples of the type of information environment these traders operate in.
  If another tool, website, data source, scanner, Telegram feed, wallet
  tracker, terminal, charting platform, bot, or information source repeatedly
  appears in real professional trading workflows, investigate it as well.
- Do NOT assume every trader uses J7 or every trader uses Axiom.
- **Evidence comes first.**

## The traders

Initial seeds: **Cupsey, Decu, Setuh, Leck**. These are SEEDS, not a complete list.

- First verify the correct identity/accounts for each person. Do not
  accidentally study another person with a similar username.
- Find additional traders only when there is reasonable evidence that they:
  actively trade Solana memecoins; have substantial real trading footage or
  documented trades; expose enough of their workflow to study; are not merely
  making generic educational content; have enough history to observe both
  winners and losers.
- Actual recorded trading sessions are considerably more valuable than
  "5 tips to become profitable trading memecoins." Long sessions where actual
  decisions can be observed may be much more informative than a polished
  strategy tutorial.

## Video limitation and method

We cannot literally watch video continuously like a human. For each relevant video:

1. obtain available subtitles/transcript
2. obtain timestamps
3. identify moments involving: token discovery, analysis, rejection, entry,
   add, partial sell, full exit, stop, rug, missed trade, discussion of strategy
4. inspect frames/screenshots at those timestamps
5. inspect frames BEFORE the decision
6. inspect frames AFTER the decision
7. if something changes rapidly, extract a dense sequence of frames around that section

Example: trader buys at 14:32 → do not inspect only 14:32; inspect e.g.
14:20, 14:22, 14:24 … 14:32, 14:34, 14:36 … 14:50, denser if the UI changes rapidly.

Combine **what the trader SAYS + what the SCREEN shows + what the trader
actually DOES**. These are three different forms of evidence.

## Evidence categories — never silently merged

| category | example |
|---|---|
| **STATED RULE** | "I don't chase green candles." |
| **OBSERVED BEHAVIOR** | Across 42 observable entries, 35 occurred after an identifiable pullback. |
| **INFERRED RULE** | The trader appears to require renewed buyer acceleration after that pullback. |
| **QUANTITATIVELY VALIDATED RULE** | When tested against historical candidates, the measurable version of this pattern produces a statistically meaningful improvement out-of-sample. |

Never assume that what a trader says they do is identical to what they actually do.

## Primary research objective

Reverse-engineer the actual decision process of strong Solana memecoin traders
at a level detailed enough that another system could eventually attempt to make
the same decision from the same information. Not "summarize Decu's strategy",
but closer to: *"If Decu were presented with these 20 tokens at exactly this
moment, what causes him to focus on token #7, reject #1–6, enter #7 at this
particular moment, hold through this particular sell, and exit 47 seconds later?"*

## The decision funnel (study each stage, per trader)

1. **Discovery** — how a token enters attention: Axiom Pulse, new pairs, final
   stretch, migrations, trending, search, J7/social alerts, X, Telegram, another
   trader, wallet activity, dev activity, scanner, manual browsing, specific
   narratives, sudden acceleration. Does discovery itself provide edge?
2. **Attention** — why this token instead of the other 30 visible: market cap,
   transaction velocity, unusual buy activity, ticker/name, image, narrative,
   social activity, creator, known wallet, chart movement, viewer/attention
   count, migration status, sudden acceleration.
3. **Narrative** (extremely important; do not reduce to keywords) — who
   originated the story, recency, attention acceleration, mainstream pickup,
   crypto-Twitter discovery, memes forming, celebrity/event/news/cultural
   relevance, originality, copycat saturation, canonical token, whether the
   story already peaked, social post velocity, whether attention converts into
   buying. What separates a GOOD NARRATIVE from a story that sounds interesting
   but does not create buyers?
4. **Token/narrative matching** — earliest token, canonical token, creator
   relationship, ticker/name/image match, social links, mint age, copycats,
   actual liquidity, which token captured the community first.
5. **Safety/structure** — dev %, top-10 %, insiders, snipers, bundles, linked
   wallets, dev history, dev selling, mint/freeze authority, LP state,
   concentration, suspicious funding, wash trading, low liquidity, strange
   holder distribution, previous creator launches, fake socials. Determine what
   *values* actually cause each trader to care — do not simply list these.
6. **Market behavior** — buys vs sells, unique buyers, buyer/seller/transaction
   acceleration, volume and volume acceleration, liquidity, market cap, holder
   growth, chart structure, pullbacks, reclaims, breakouts, candles, sell
   absorption, repeated large buyers, smart wallets/pro traders, liquidity
   migration, failed dumps. Especially **derivatives of activity** (velocity,
   acceleration), not levels.
7. **Entry** — immediate buy, breakout, pullback, reclaim, second push,
   migration, dev sells but market absorbs, whale enters, social catalyst,
   narrative confirmed, buyer count accelerates. Capture observable information
   immediately before entry.
8. **Position size** — does it change with confidence, liquidity, narrative
   strength, market cap, wallet size, risk, setup type, recent performance?
9. **Holding** — what keeps them in despite red candles, temporary sell
   pressure, whales selling, narrative slowing, consolidation. As important as entry.
10. **Exit** — fixed %, momentum fading, large seller, buyer velocity
    collapsing, narrative weakening, structure breaking, liquidity change,
    predetermined TP, partial sell, trailing, time-based, dev action,
    market-wide movement. Also cases of exiting early before a much larger move.

### Rejections

Study BUY vs SKIP, not merely WIN vs LOSS. If a trader examines A→skip, B→skip,
C→skip, D→BUY, E→skip, reconstruct why D survived.

### Losses

No mythology. Record winners, losers, rugs, failed entries, missed
opportunities, premature exits, bad narrative calls, revenge trades,
overtrading, trades they later call mistakes. A strategy reconstructed only
from successful clips is useless.

## Structured trader dataset

Fields per decision: trader, video, timestamp, token, mint (if recoverable),
decision timestamp, decision (BUY / SKIP / SELL / HOLD), market cap, liquidity,
token age, transactions, buys, sells, volume, holders, top10, dev, snipers,
insiders, bundles, pro traders, attention/viewer info (if observable), chart
state, narrative description, narrative age, social velocity, entry reason,
exit reason, position size (if observable), result, confidence of extraction,
source. **If a value is not visible or cannot be reconstructed: NULL. Never invent it.**

## Trader-specific models first

Reconstruct a CUPSEY MODEL, DECU MODEL, SETUH MODEL, LECK MODEL, etc., each
answering DISCOVERY → ATTENTION → NARRATIVE → SAFETY → MARKET CONFIRMATION →
ENTRY → HOLD → EXIT. Then compare: what almost all successful traders do, what
only some do, and what is personal style rather than edge. (Any comparison
table is filled only with evidence.)

## Human behavior → measurable features

For each understood behavior, ask whether it can be measured. Examples:

- "Getting attention really fast" → mentions_60s, mentions_5m, mention
  velocity/acceleration, unique accounts, weighted followers, engagement
  velocity, J7 post velocity.
- "Buyers keep stepping in" → unique_buyers_10s/30s, net SOL flow,
  buy/sell ratio, buyer velocity/acceleration, sell absorption.
- "Chart looks healthy" → drawdown from local high, recovery speed, higher
  low, volume on recovery, sell volume ratio, price impact of sells.

Potential additional data sources (only where they have a plausible role in the
decision process): DexScreener, Pump.fun / PumpSwap, PumpPortal, Solana RPC,
Helius, Birdeye, GeckoTerminal, RugCheck, GMGN, wallet trackers, public X
information, Telegram/public channels, creator history, token metadata, DEX
trade streams. Do not add data simply because it exists.

## Simulation (after forensic research)

- Convert reconstructed behavior into an explicit candidate strategy. Do not
  optimize everything at once; start with the closest measurable
  representation of what the humans appear to do.
- **Temporal causality**: at timestamp T the strategy may use only information
  available at T. No future peak market cap, rug labels, holder data,
  transaction counts, social activity, or prices.
- **Realistic execution**: detection, decision, quote and transaction latency;
  fees; priority fee; slippage; price impact; failed transactions; liquidity;
  volatility; inability to sell at hypothetical candle highs. Test multiple
  execution delays (100ms, 250ms, 500ms, 1s, 2s, 3s, 5s, 10s) where the data
  resolution supports it.

## Iterative scientific loop

```
RESEARCH HUMANS → FORM HYPOTHESIS → CONVERT TO FEATURE → SIMULATE → COMPARE RESULTS
      ↑                                                                   ↓
REFINE HYPOTHESIS ← RETURN TO TRADER EVIDENCE ← IDENTIFY FAILURE ←────────┘
```

e.g. *Setuh does something repeatedly → we notice it → measurable hypothesis →
historical test → doesn't work → go back to Setuh/Decu/Cupsey evidence → figure
out what we misunderstood → new hypothesis → test again.*

Do NOT tune parameters until historical PnL looks impressive. Every iteration
needs a stated reason. BAD: "changing threshold 17.2→19.4 makes profit
higher." GOOD: "repeated video evidence suggests traders avoid entries until
buyer growth accelerates; test whether positive buyer acceleration adds
predictive value."

## Train / validation / final holdout

Split chronologically: RESEARCH/TRAIN → VALIDATION → FINAL UNTOUCHED TEST.
Iterate against train and validation only. Do not inspect the final test and
then modify the strategy to fix it. If the final test fails, document the
failure; after changes, a new future period becomes the next untouched test.

## Two separate objectives

- **A — Decision imitation**: given the same information, predict BUY / SKIP /
  HOLD / SELL like the trader (precision, recall, agreement, entry/exit timing difference).
- **B — Trading performance**: does the reconstructed strategy survive
  realistic simulation (realized PnL, expectancy, profit factor, win rate,
  average winner/loser, median trade, drawdown, rug exposure, fee drag,
  slippage drag, trade frequency, outlier dependence)?

These remain separate: perfect imitation can be unprofitable, and some habits
may prove unnecessary or harmful.

## Eventual goal: not a clone

professional traders → extract heuristics → measure → test scientifically →
discard bad ones → combine robust ones → discover additional measurable
relationships → **our own strategy**, which may differ from every trader if
the evidence supports it.

"Better than the human" must be earned: robust unseen-period performance,
realistic execution, enough trades, multiple regimes, acceptable drawdown, no
excessive outlier dependency, no leakage, reproducibility.

## Research depth

Do not stop after a few videos, strategy summaries, filters or favorite
indicators. Valuable information may emerge only after dozens or hundreds of
observed decisions. Pay special attention to repeated behavior the trader never
explains (e.g., always checks one metric before buying; avoids a holder
structure; waits seconds after a large sell; enters only after buyers return;
checks J7 before clicking buy; opens X only for certain tokens; skips tokens
with great numbers but weak narrative; exits on a metric change while the
chart still looks bullish).

## Evidence standard

For every important conclusion: SOURCE, TRADER, VIDEO/PAGE, TIMESTAMP,
OBSERVATION, TYPE (stated / observed / inferred / quantitatively validated),
CONFIDENCE, NOTES. Never convert an inference into a fact.

## Final philosophy

Observe experts performing the task. Reconstruct what information they actually
use. Determine how their decisions are made. Convert their intuition into
measurable variables. Test those variables scientifically. Keep only what
survives. Repeat until the remaining process is robust.

The human traders are the starting material. Their claims are not ground truth.
Their actual behavior is evidence. Historical data is the test. Future unseen
data is the judge.
