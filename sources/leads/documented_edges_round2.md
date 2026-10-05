# Documented edges, round 2: bot mechanics, product changes, paid-promotion events, listings

_Compiled 2026-10-05 by a research agent using web search, web fetch and a few read-only
descriptive queries on our recorded tape. Everything from the web is a **lead** (`document`
modality), not a trader's statement and not a validated finding. The "pre-checks" are exploratory
descriptive counts from our data. They are **not** hypothesis tests, no rule was tuned on them,
and none used the Oct 1 19:15–21:15 holdout. Where a page could not be fetched, the text says so._

Evidence labels are the same as round 1 (`documented_edges_research.md`): **DATA**, **DATA-weak**,
**ANECDOTAL**, **MARKETING**. **OWN-PRECHECK** means a descriptive count we ran ourselves today.

Already tested or running, and not repeated here: BOOST, Telegram-link and socials filters,
exiting before graduation, Mayhem Mode, livestream viewers, wallet-quality ML, copy/KOL/Decu,
LLM narrative judgement, curve and AMM micro-triggers (sniper exit, King of the Hill, whale, crash
bounce, sympathy, committed dev, aged demand), holder-reward fee *carry*, hour-scale post-migration
holds, LaunchLab (SOL configs). Running now: dev funding source, narrative-cluster heat.

---

## 0. What the requested topics turned up (short answers)

| Topic | Finding | Consequence |
|---|---|---|
| Telegram/terminal bot TP/SL | Bots offer auto TP/SL and limit orders, and guides suggest 2×/+100% take-profit and −20% to −50% stop-loss presets (Axiom example: "always −20% stop loss, +100% take profit"). **Most bots, BonkBot included, keep the orders off-chain and fire them when price is hit.** Jupiter Trigger v2 orders are "stored off-chain and private by default". pump.fun added native TP/SL limit orders on 2026-09-01, set by price multiple (example: 3× / −50%). Sources: [madeonsol stop-loss guide](https://madeonsol.com/blog/how-to-set-stop-losses-solana-trading-bots) (MARKETING), [coincodecap Trojan settings](https://coincodecap.com/best-settings-for-trojan-bot) (MARKETING), [Jupiter Trigger docs](https://developers.jup.ag/docs/trigger), [Crypto Briefing on pump.fun limit orders](https://cryptobriefing.com/pumpfun-limit-orders-solana-tokens/). | No public on-chain order book of walls exists to read. The only route is to infer clustering from fills: see idea 3, which our pre-check **weakens**. |
| Copy-trade delays | No published delay figures. GMGN, Trojan and others mirror after detecting the target's transaction. | Already covered by the KOL front-run failure: price is up 13–16% by 1 s. |
| Bot fees and routing | Trojan and BonkBot charge 1% per trade (BonkBot uses it to buy BONK). BullX shut down in June 2026. Trojan reports $25B+ volume and 2M users. Sources: [madeonsol BonkBot review](https://madeonsol.com/blog/bonkbot-review), [Crowdfund Insider](https://www.crowdfundinsider.com/?p=246594). | A bot's fee transfer, tip account or router program identifies the terminal behind a buy: see idea 6. |
| pump.fun product mechanics, 2025–26 | Project Ascend dynamic fees ([Blockworks](https://blockworks.com/news/pumpdotfun-fee-model)). Creator-fee sharing with up to 10 wallets, ownership transfer and revoking update authority, Jan 2026 ([The Block](https://www.theblock.co/post/384975/pump-fun-overhauls-creator-fees-token-launches-highest-daily-september), [ForkLog](https://forklog.com/en/news/pump-fun-to-revise-content-creator-fees)). Callout Rewards: daily USDC by volume driven, top 50 earned ~$700k ([Protos](https://protos.com/pump-fun-paid-700k-to-callers-shilling-mostly-tiny-tokens/), [Invezz](https://invezz.com/news/2026/08/14/pump-surges-as-pump-fun-pays-users-to-call-tokens-can-0-003-break-next/)). Holder Rewards replaced Cashback for new launches on 2026-09-12 ([The Defiant](https://thedefiant.io/news/defi/pump-fun-drops-cashback-for-new-launches-adds-holder-rewards), [Crypto Briefing](https://cryptobriefing.com/pumpfun-holder-rewards-cashback-deprecated/)). Charity Coins. PUMP buybacks: about 100% of revenue until Apr 28 2026, about 50% since ([The Block](https://www.theblock.co/amp/post/366783/pumps-average-token-buyback-price-floats-40-above-spot-market-even-as-daily-revenue-trends-lower)). | Ideas 2 and 5. The PUMP buyback concerns one large-cap token and The Block found no predictable intraday schedule, so it is **dropped**. |
| Public pump.fun coin API | `https://frontend-api-v3.pump.fun/coins-v2/{mint}` is unauthenticated (checked 2026-10-05). It returns `is_holder_reward`, `is_cashback_enabled`, `boost_mode` (NONE/COMPLETED), `verified`, `security_verdict`, `ath_market_cap`, socials and more. `/coins/{mint}` returns 404. | Gives a backfill path for the token-type flag in idea 2. |
| Sniper/bundler signatures and exit clocks | Pine: 55% of deployer-funded snipes exit in under 1 min and ~85% in under 5 min ([Pine](https://pineanalytics.substack.com/p/exit-liquidity-machines)). Detection guides: same-slot multi-wallet buys plus shared funding ([Mobula](https://docs.mobula.io/almanac/detecting-snipers-bundlers), [Webacy](https://docs.webacy.com/glossary/snipers-bundlers)). | Covered by the sniper-exit failure (PF 0.32–0.41) and the dev-funding agent. **Not repeated.** |
| Cross-launchpad | Pump.fun ~70% of launches, LetsBonk 15–21%, Believe ~2% (2025 data: [The Block](https://www.theblock.co/post/367266/solana-memecoin-launchpad-war-flips-again-as-pump-takes-top-spot-amid-letsbonk-collapse), [MEXC](https://www.mexc.com/news/422504)). LetsBonk pledged 1% of revenue, about $15k a week, to weekly buybacks of "top pairs" in the BONK ecosystem, with no wallet or schedule given ([The Block](https://www.theblock.co/post/364031/memecoin-launchpad-letsbonk-pledges-1-of-revenue-to-buyback-top-tokens)). Heaven puts 100% of revenue into LIGHT buybacks ([Blockworks](https://blockworks.com/news/heaven-memecoin-launchpad-buys-back-everything)). | No documented mechanism that creates predictable flow into *new* memecoins. The buybacks are tiny or single-token. One open point: iteration 9 kept only SOL-quoted LaunchLab configs, but BONK-quoted pools are most of bonk.fun. That is a venue, not an edge, so **not proposed**. |
| Listings (Binance Alpha, Upbit, Hyperliquid) | Rare for Solana memecoins, and the move happens mostly before the announcement. See idea 7. | Low frequency. |
| Academic 2025–26 | Nothing new beyond round 1 on Telegram bots or limit orders: the papers are B1–B11 in round 1. General listing studies: [Blockchain Research Lab](https://www.blockchainresearchlab.org/portfolio/market-reaction-to-exchange-listings-of-cryptocurrencies/) found +3.2% abnormal returns 3–2 days *before* announcements (327 listings, older sample), and [The TIE 2026](https://www.thetie.io/insights/what-does-an-exchange-listing-actually-deliver-in-2026) studied 1,844 listings from Jan 2023 to Jun 2026. | Supports "the move is before the news". |

---

## 1. Ideas, ranked by how testable they are with data we already hold

### Idea 1. DexScreener paid-profile / boost events on bonding-curve tokens (H-DEXPAID)

**Mechanism.**
- A team that pays ~$299 or more for DexScreener "Enhanced Token Info" (the "DEX paid" badge), or buys Boosts, has made a costly, public commitment.
- The payment is broadcast. GMGN shows "Dexscreener paid" signals ([Apify scraper of GMGN paid signals](https://apify.com/muhammetakkurtt/gmgn-dexscreener-paid-signals-scraper)), and Telegram "DEX PAID" call bots scrape the feed ([example](https://web3market.gumroad.com/l/tg-dexscreener)).
- Boosts multiply DexScreener's trending score ([DexScreener docs](https://docs.dexscreener.com/privacy/boosting-terms-and-conditions)).
- That produces a discrete, timestamped attention event that is not in our tape and none of our 45 families used. Whether it is priced in within a second, like everything else, is exactly what the test settles.

**Evidence quality.** ANECDOTAL/MARKETING for the effect: no study of price after DEX-paid events was found. OWN-PRECHECK for frequency and timing:
- Public endpoint `GET https://api.dexscreener.com/orders/v1/solana/{mint}` (no key, 60 req/min) returns every paid order for **any** mint, with `type` (`tokenProfile`, `communityTakeover`), `status` and `paymentTimestamp` in ms. Boosts come with `amount` and `paymentTimestamp`. **This allows a historical backfill.**
- Sample of 110 random mints that completed the curve (created Oct 3–4): **21 (19%)** had an approved paid profile and 1 had a boost. Of 60 random non-completing launches, **0** had either.
- Among the 21 payers:
  - median payment was **3.5 min after create**;
  - **57% paid before migration**;
  - payment minus migration time had quantiles (min) of 10% −13.4, 25% −3.9, 50% −1.3, 75% +2.2 and 90% +8.3.
- The 19% vs 0% contrast is a selection association: we chose tokens by an outcome. **It is not an edge.**

**Point-in-time caveat.** `paymentTimestamp` is **not** when the public sees the event. Three community takeovers appeared in the public feed (`claimDate`) **40 s, 11 min and 89 min** after payment. Before any backtest:
- run the live collector to measure the visibility lag;
- check whether the per-mint `orders` endpoint shows a pending order before approval.

**Rule (H-DEXPAID-a, curve stage).**
- **Trigger:** the first time a `tokenProfile` order (or a boost with `amount ≥ 10`) is *visible* to our poller for a mint still on the curve. Visible means it appears in `/token-profiles/latest/v1` or `/token-boosts/latest/v1`, or as a new entry in a per-mint `orders` poll.
- **Entry:** buy S ∈ {0.1, 0.5} SOL at visibility + L (L = 1 s), at exact curve fills.
- **Filters, fixed in advance with no tuning:**
  - real SOL is 20–75;
  - token age is at least 60 s;
  - Mayhem tokens are excluded.
- **Exits:** the standard grid (TP/SL from 20/10 to 100/30, maximum hold 300 s or 1,800 s), plus "sell at real SOL ≥ 80".
- **Variant b:** the same rule at the first PumpSwap trade after a payment that was visible before migration.

**Data.**
- Price tape: covered (`curve_trades`, `amm_trades`).
- New public collector:
  - poll `/token-profiles/latest/v1`, `/token-boosts/latest/v1`, `/community-takeovers/latest/v1` and `/ads/latest/v1` every 5–10 s, stamping receive time;
  - poll `orders` for every curve token with real SOL ≥ 20 every 30 s, which fits within 60 req/min only for a few hundred tokens.
- Backfill for train: query `orders` once for every mint that reached real SOL ≥ 20 in the train window. That is about 1 request/s, so a few hours. Use it for frequency and time-of-payment only, not for entry timing, until the visibility lag is known.

**Expected frequency.**
- We record about 945 completions a day (3,336 in 3.5 days), and ~19% pay. That gives ~180 paid graduates a day, and ~100 of them pay while still on the curve.
- Adding non-graduating payers: **about 100–300 trades a day.** Measure it.

---

### Idea 2. Holder-Rewards token type as a hold incentive (H-HR)

**Mechanism.**
- Since 2026-09-12, creators choose at launch between a Creator-Fee token and a Holder-Rewards token.
- Holder-Rewards tokens pay the fees pro rata to holders above $20, several times an hour, with **longer and larger holding earning more**.
- A time-weighted reward should lower holders' sell rate. That would show as slower post-migration decay than in creator-fee tokens, whose creator can also farm fees.
- It also signals that the creator gave up fee income.
- Iteration 14 measured the *yield* as tiny (0.1–0.55% over 4 h), so the incentive may be too small to change behaviour. That is a low prior, stated before testing.

**Evidence quality.** The mechanism is documented ([The Defiant](https://thedefiant.io/news/defi/pump-fun-drops-cashback-for-new-launches-adds-holder-rewards), [Crypto Briefing](https://cryptobriefing.com/pumpfun-holder-rewards-cashback-deprecated/)). No outcome data was found. OWN-PRECHECK via the public `coins-v2` endpoint:
- **6 of 100** random recent launches are Holder-Rewards;
- **3 of 100** random graduates are, so there is no graduation lift (small n);
- 0 of 200 are cashback, consistent with cashback being deprecated;
- 89 of 100 graduates have `boost_mode = COMPLETED`.

**Rule (H-HR).** With no new tuning:
- re-run the frozen iteration-8 hour-scale design (decision 1 h after migration, hold 4 h, 2% per side) on Holder-Rewards graduates only, and compare it with creator-fee graduates in the same hours;
- on the curve, re-run the two closest near-misses (aged demand, PF 0.93; early detectors, PF 0.90) restricted to Holder-Rewards tokens, with their already-frozen parameters.

Report the difference. Do not search new thresholds.

**Data.**
- Covered: the tape, PumpSwap and the GeckoTerminal OHLCV already fetched.
- New: a one-off backfill of `coins-v2/{mint}` for every migrated mint and every mint that triggered a near-miss rule, a few thousand requests at about 2/s. Then a live per-create lookup, or decode the create instruction's trailing flag bytes in `curve_creates.raw` once mapped against `coins-v2`.

**Expected frequency.** About 6% of ~35k launches a day (~2,100 Holder-Rewards launches) and about 25–30 Holder-Rewards graduates a day. Entries depend on the base rule: **about 5–30 trades a day.**

---

### Idea 3. Bot take-profit / stop-loss walls (H-TPWALL). Pre-check: weakened

**Mechanism.**
- Bot and terminal TP/SL orders are set relative to each wallet's own entry: 2×/+100% take-profit, "sell initials" at 2×, and −20% to −50% stop-losses.
- Axiom-style triggers can also be set by USD market cap.
- If many wallets entered at similar prices, a predictable sell cluster sits at 2× their VWAP, or at round USD market caps.

**Evidence quality.** Presets are MARKETING (guides). OWN-PRECHECK on train hours (Oct 2 12:19–Oct 3 00:19 UTC), and it **does not support** the idea:
- **Curve, 38,152 single-buy/single-full-sell round trips:** the exit/entry price-ratio histogram peaks just below 1.0 (fees) and decays smoothly. **There is no spike at 1.5×, 2× or 3×.**
  - The 1.93–2.07 bins hold 115 and 83 trips, against 109 and 75 in the neighbouring bins.
  - The 298 partial sells near 50% have a median ratio of 1.47 and a 75th percentile of 1.98, which hints at "sell initials". The n is small.
- **Round USD market caps on the curve:** 256k trades on clean curves, using SOL/USD from data-api.binance.vision. The sell share within 0–2% of $5k/$10k/$20k/$30k/$40k equals the 4–8% control bands (for example 0.447 vs 0.443 at $10k). It also matches placebo non-round levels ($7.3k, $13.7k, $26.3k, $37.1k).
- **PumpSwap, 122k round trips (Oct 2 12:19–Oct 3 12:19; includes validation hours, descriptive only):** at most a faint bulge at 1.93–2.07× (671/609 vs 633 and 563 in the neighbouring bins) and at 2.64× (342 vs 240/249). That is within noise.

**Remaining testable form (H-TPWALL-cohort).** Clustering may exist per cohort even if the pooled histogram hides it.
- For each token, define the first-60-s buyer cohort's VWAP.
- When price first reaches 2.0× that VWAP, measure the cohort's sell share in the next 30 s against the same at 1.8× and 2.2×.
- Only if that excess is real, a rule follows: enter after price closes more than 5% above 2× the cohort VWAP, with ≥ 50% of cohort tokens sold, and exit on the standard grid.

**Data.** Fully covered (`curve_trades`, `amm_trades`; public SOL/USD klines from data-api.binance.vision. api.binance.com is geo-blocked here).

**Expected frequency.** Hundreds of trades a day if the rule exists. **Low prior: run the descriptive cohort check (about 1 h) before spending more.**

---

### Idea 4. DexScreener community takeover (CTO) on abandoned migrated tokens (H-CTO)

**Mechanism.**
- A CTO is a community paying DexScreener to take over the page of a token whose developer left. It marks the start of an organised revival campaign: new socials, raids, often boosts.
- Unlike launch-second signals it is an hour-scale event on tokens that have already decayed, which is where our iteration 8 found universal decline. That makes it a sharp conditional test of whether a revival changes the decay.

**Evidence quality.** ANECDOTAL. No study found. OWN-PRECHECK: the public `community-takeovers/latest/v1` feed showed 8 Solana CTOs in about 7 h (5 on pump mints). The `orders` endpoint carries `type: communityTakeover` with `paymentTimestamp`, so CTOs can be backfilled. The visibility lag after payment was 40 s to 89 min (see idea 1).

**Rule (H-CTO).**
- **Trigger:** a migrated pump mint whose CTO appears in the feed (`claimDate`, or our poll time if later).
- **Decision:** at the first completed 15-min bar after the trigger, buy if the pool has at least $10k liquidity.
- **Exit:** hold 4 h or 24 h, with a stop at −40%.
- **Costs:** 2% per side, as in iteration 8.
- **Control:** non-CTO migrated tokens of the same age bucket in the same hours.

**Data.** GeckoTerminal OHLCV collector already exists (`fetch_pool_ohlcv.py`), and the PumpSwap tape is covered. New: poll the CTO feed (forward), and backfill `orders` for every recorded migrated mint (~3,300 requests).

**Expected frequency.** About 20–25 Solana CTOs a day, about 12–15 on pump mints. **About 5–15 trades a day.** Reaching 50 forward paper trades takes about 4–10 days.

---

### Idea 5. Creator-fee claims and fee-sharing / authority changes as events (H-CLAIM)

**Mechanism.**
- Creators collect curve and PumpSwap creator fees with on-chain instructions that emit events (`CollectCreatorFeeEvent` on the pump program, and the coin-creator-fee collection event on PumpSwap).
- Since Jan 2026 creators can also share fees with up to 10 wallets, transfer ownership and revoke update authority ([The Block](https://www.theblock.co/post/384975/pump-fun-overhauls-creator-fees-token-launches-highest-daily-september)).
- Two opposite predictions follow, and the event study settles which, if either, holds:
  - **(i)** an early, repeated claim marks a fee farmer who runs volume bots and then leaves (avoid or exit signal; ForkLog and others describe fee farming with bots: [ForkLog](https://forklog.com/en/expert-highlights-bot-infiltration-on-pump-funs-meme-token-platform/));
  - **(ii)** fee-sharing set up with outside wallets, or a revoked authority, marks a committed or collaborative launch.
- These are developer actions that are not in our trade tape. They differ from the dev-funding-source study now running, which looks at where the creator's SOL came from, not at what the creator does after launch.

**Evidence quality.** The mechanics are documented (press). The trading effect is ANECDOTAL only.

**Rule (H-CLAIM-exit).** An overlay on any frozen curve or PumpSwap rule: exit at the creator's first fee-claim event + 1 s, and compare with the base exits on the same entries.

**Rule (H-CLAIM-entry).** For migrated tokens: buy at the first fee-sharing-config or authority-revoke event seen after migration (≥ 10 min after migration), hold 1 h or 4 h, at 2% per side.

**Data.**
- The recorder already `logsSubscribe`s to the pump program but decodes only Trade, Create and Complete. Adding the discriminators for the creator-fee and fee-sharing events is a forward-only change; history needs RPC.
- `pumpswap_raw` stores raw event data, so PumpSwap creator-fee collections may already be recoverable from recorded files. Check this first.

**Expected frequency.** Unknown until decoded. Claims are likely thousands a day; config and revoke events are fewer. Overlay trades equal the base rule's count.

---

### Idea 6. Terminal and route attribution of early buyers (H-ROUTE)

**Mechanism.**
- B1 (arXiv [2602.14860](https://arxiv.org/abs/2602.14860), DATA) finds bot-dominated early flow lowers graduation odds while non-bot participation raises them.
- A6 (arXiv [2607.28424](https://arxiv.org/abs/2607.28424)) finds pump.fun-centric bots roughly break even.
- Our wallet-quality and heat features never used **how** a buy was sent. That shows in the transaction:
  - the router program (we saw GMGN's program `GMgnVF…` and `JUP6Lk…`);
  - tip accounts (Astralane `astra…`, Nozomi `noz…`, Jito);
  - terminal fee wallets (Axiom, Photon, Trojan, BonkBot all take ~1%).
- The share of early SOL from retail terminals is a proxy for human demand, as opposed to snipers or bundlers.

**Evidence quality.** DATA for the graduation link (B1). There is no profit evidence, and graduation lift is not profit (B1's breakeven curve). OWN-PRECHECK on feasibility: of 40 `getTransaction` calls to the public RPC, 13 succeeded, 20 got HTTP 429 and 7 got −32015. Router and tip signatures were visible in those 13.

**Rule (H-ROUTE).**
- At token age 60 s and 120 s, compute retail-terminal SOL share R and bot-route share B over buys from the creation slot to now.
- Enter if R ≥ r and buyer count ≥ k, with (r, k) chosen on train only.
- Exits on the standard grid. Mayhem tokens excluded.
- Labelling: build the terminal fee-wallet and tip-account map from frequency in a train sample (addresses that receive a SOL transfer in more than 1% of pump trades). Never use outcomes for labelling.

**Data.** `curve_trades.sig` is covered. A new collector is needed: `getTransaction` for the first ~30 buys of each candidate token. The public RPC allows roughly 10–20 a minute, enough for a sample but not live. A live version needs a paid RPC or `transactionSubscribe`.

**Expected frequency.** Tens to a few hundred trades a day, depending on (r, k). The bottleneck is collection.

---

### Idea 7. CEX/perp listing announcements of Solana memecoins (H-LIST). Low frequency

**Mechanism.** Listings bring new demand and venue access. Round 1 had this as D1. This round adds frequency and timing.

**Evidence quality.**
- **General listings (DATA-weak):** abnormal returns are concentrated **before** announcements, and the gains mean-revert within about 2 weeks. The TIE: 1,844 listings, Jan 2023–Jun 2026, daily VWAP, no memecoin breakdown. RockawayX: Binance and Bybit DiD positive at 7 days, flat by 30 days ([RockawayX](https://rockawayx.com/insights/bullish-or-bearish-what-really-happens-when-tokens-list-on-a-cex)).
- **Binance Alpha:** 12 of 29 announced tokens fell, and the 23 May listings averaged −5.04%, with Solana tokens +12.32% on a tiny n ([wublock](https://wublock.substack.com/p/binance-alpha-research-how-do-projects), [iTiger summary](https://www.itiger.com/news/2493021754)). Alpha ran ~30 selections a month across all chains in 2025.
- **Upbit Solana memes in 2026:** WIF on May 6 and SPX6900 on Jun 15 ([coinalertnews](https://coinalertnews.com/news/2026/05/06/upbit-lists-dogwifhat-wif)), so about one every 1–2 months.
- **Hyperliquid:** HIP-3 builder perps since Oct 13 2025 are dominated by equities and commodities ([Nansen](https://nansen.ai/post/what-is-hip-3-hyperliquid)). Validator-listed meme perps are rare.
- The DWF Labs Alpha study was **blocked (403)**.

**Rule (H-LIST).**
- Poll the Binance announcements and Alpha list, Upbit notices, and the Hyperliquid `info` `meta`/`perpDexs` endpoints (all public).
- When a token with a Solana DEX pool is named, buy on its deepest Solana pool at announcement + L (L = 5 s).
- Exit at +15/+60 min or −20%.
- Pre-test: a backfilled event study of T−60 min to T drift, to measure leakage, using GeckoTerminal OHLCV.

**Data.** None of it is in our recordings. Needs a new announcement poller plus OHLCV.

**Expected frequency.** About 1–4 qualifying events a month (Binance Alpha Solana memes are the bulk). **The 50-forward-trade bar would take years, so this cannot clear the bar on its own.** Keep it only as a long-running monitor.

---

## 2. Considered and dropped (do not re-research)

| Lead | Why dropped |
|---|---|
| Reading on-chain limit-order walls (Jupiter, bots) | Jupiter Trigger v2 orders are off-chain and private, and bot TP/SL are off-chain ([Jupiter docs](https://developers.jup.ag/docs/trigger), [madeonsol](https://madeonsol.com/blog/how-to-set-stop-losses-solana-trading-bots)). There is nothing to read. |
| PUMP token buyback flow | One large-cap token, not pump.fun memecoins. Execution timing is not disclosed or predictable ([The Block](https://www.theblock.co/amp/post/366783/pumps-average-token-buyback-price-floats-40-above-spot-market-even-as-daily-revenue-trends-lower)). |
| LetsBonk weekly top-pair buyback; Heaven LIGHT buyback | About $15k a week across a few large tokens; Heaven buys a single token. Too small or not memecoin flow. |
| Callout Rewards (pump.fun) | Promotion paid by volume. The callout feed lives in the app with no documented public endpoint, and it is a KOL-promotion variant already failed (KOL front-run). |
| Cashback coins | Deprecated for new launches on 2026-09-12. 0 of 200 sampled recent tokens had cashback enabled. |
| Sniper exit clocks, bundle overhang | Covered by the sniper-exit failure and the dev-funding agent now running. |
| Migration auto-sell / "buy on migration" (Axiom) | Inside the BOOST window, which failed validation. |
| bonk.fun BONK-quoted pools | A venue rather than a mechanism. If revisited, re-run frozen rules on the BONK-quoted LaunchLab configs instead of inventing new ones. |
| SOL/USD shocks moving USD market caps through bots' USD triggers | The round-USD pre-check found no clustering. SOL moved only 117–120 over the 12 h checked, so shocks are rare. |

## 3. Gaps
- No study of price after DexScreener paid events, CTOs, creator-fee claims or Holder-Rewards status was found. All four effects are untested.
- DexScreener visibility lag (payment to public) is measured on only 3 CTOs. It is the main point-in-time risk for ideas 1 and 4.
- The DWF Labs Binance Alpha study returned 403. A DexTools June 2026 bot-activity article returned 404.
- The pre-checks are single-window descriptive counts. Ideas 1 and 2 used tokens created Oct 3–4 (outside the holdout) only for frequency and flag shares, not for any rule.
