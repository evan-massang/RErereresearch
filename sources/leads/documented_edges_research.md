# Documented trading edges on pump.fun / Solana memecoins: literature and lead review

_Compiled 2026-10-04 by a research agent using web search and fetch. All items are **leads**
(`document` modality). Nothing here is a trader's own statement or a validated finding. Numbers are
copied from the cited source and not re-computed by us unless stated. Where a page could not be
fetched, the text says so._

Evidence-quality labels:
- **DATA**: peer-reviewed paper, or a preprint or analytics report with stated data, sample and method.
- **DATA-weak**: a single-author preprint, or an industry report with a partial method.
- **ANECDOTAL**: one-off cases or an operator's write-up with no verifiable trades.
- **MARKETING**: a vendor or tool blog whose claims support a product.

Conditions codes:
- **SPD**: needs speed or infrastructure (Jito, colocated or fast RPC).
- **CAP**: needs meaningful capital.
- **OFF**: needs off-chain data.
- **LAUNCH**: needs launching tokens.

---

## 1. Edges, strategies and stylised facts found

### 1.1 Who actually profits (base rates)

| # | Claim | Evidence | Source | Conditions |
|---|---|---|---|---|
| A1 | **Deployer-funded same-block sniping.** In one month: >15,000 SOL realised profit, 15,000+ launches, 4,600+ sniper wallets, 10,400+ deployers. 87% of snipes were profitable. >50% of tokens were sniped in the same block. 55% of snipes fully exited in <1 min and ~85% in <5 min. Activity clusters 14:00–23:00 UTC. | DATA-weak (Pine Analytics; detection uses only direct SOL funding links, so it is a lower bound) | https://pineanalytics.substack.com/p/exit-liquidity-machines | LAUNCH (insider). **Excluded as an idea**; usable only as an avoid-filter. |
| A2 | Only 0.4% of pump.fun wallets realised ≥$10k profit, and 294 wallets realised >$1M. Excludes post-migration trading and unrealised PnL. | DATA-weak (Dune dashboard, reported by press) | https://decrypt.co/300403/pump-fun-traders-millionaires | — |
| A3 | Share of profitable wallets: 30.1% (Jun 2025), then 56.8% (Feb 2026), 70% (Mar 2026) and 73.3% (Apr 2026). In Apr 2026, 65.1% of wallets made only $1–500. Active wallets fell from 5.2M to 1.8M before recovering. | DATA-weak (CoinGecko Research, realised PnL only). Coincides with the Cashback-coin launch (A4); the cause is not established. | https://www.coingecko.com/research/publications/pump-fun-traders-are-making-a-comeback | — |
| A4 | **Cashback Coins.** The creator chooses at launch, irreversibly, whether fees go to the creator or as cashback to traders. Cashback is claimable only via pump.fun Terminal. | MARKETING / press | https://cointelegraph.com/news/pumpfun-launches-cashback-coins-rewards | Claiming may need an authenticated UI; not used. |
| A5 | Galaxy Research: platforms, not traders, capture the value. Median memecoin hold time fell from 300 s to 100 s. | DATA-weak (press summary; full report not fetched) | https://www.bitdegree.org/crypto/news/galaxy-research-meme-coin-boom-enriches-platforms-not-traders | — |
| A6 | Pump.fun-centric bot cluster (>80% of its transactions on pump.fun): **"near-zero gains with occasional downside tail risk"**. The proprietary-AMM arbitrage cluster was 62.3% profitable. Study of 200 bot addresses and 44M transactions. | DATA (ASE '26 paper) | https://arxiv.org/abs/2607.28424 | Independent support for our recurring finding that generic pump.fun bots do not profit. |
| A7 | Sandwich bot "DeezNode" made 65,880 SOL in 30 days. 16 of its top-20 targets were pump tokens. Atomic arbitrage: 90.4M transactions over a year, $142.8M profit, **$1.58 average per arbitrage**. 3.75M SOL paid in Jito tips. | DATA (Helius, using Jito data) | https://www.helius.dev/blog/solana-mev-report | Sandwiching is **excluded** (harmful). Arbitrage is SPD. |

### 1.2 Academic / preprint findings on pump.fun mechanics

| # | Claim | Evidence | Source | Conditions |
|---|---|---|---|---|
| B1 | Marino, Naviglio, Tarantelli and Lillo, Sept 2025: 655,770 tokens and 0.63% graduation. They define a **breakeven curve for buy-and-hold-to-graduation: profitable only if p(grad \| vSol, θ) > vSol²/1152**. Using vSol alone stays below breakeven. Conditioning on ex-ante top traders (picked in the first two weeks, tested in the next two) raises p, but **still below breakeven**. Rapid accumulation in few trades predicts graduation. Bot-dominated early flow predicts lower graduation. Prolific creators add nothing. | DATA (arXiv, full on-chain dataset) | https://arxiv.org/abs/2602.14860 | Supports our failed "copy top wallets", "good-dev" and "final-stretch" results. |
| B2 | **Same paper: the liquidity discontinuity at graduation.** Virtual reserves vanish at migration, so the same token inventory sells for **more just before graduation than just after**. Worked example: x=115 SOL, y=0.2799e9 before; x′=85 SOL, y′=0.2069e9 after, at the same marginal price. 92.2% of tokens with ≥30 swaps show a 4σ (MAD) dump. Dumps cluster at mid-to-late vSol; 56.4% of dump episodes involve one wallet. | DATA (arXiv) | https://arxiv.org/abs/2602.14860 | Exit-timing rule; no special infrastructure. |
| B3 | Kamat 2026, survival analysis of 832,941 launches (May–Jun 2026). **Telegram link in metadata: graduation 1.485% vs 0.166% (8.94×; Cox HR 5.40).** All three socials: 1.919% vs 0.110% with none. Initial market cap above default: HR 4.51. Concordance 0.858. The author states **"no real-money trading claims"**. The collector undercounts slow graduations, so rates are lower bounds. | DATA-weak (single independent author; corrected v3 after a withdrawn fix) | https://arxiv.org/abs/2607.02823 | OFF (token metadata JSON from the `uri`; public IPFS). |
| B4 | Kamat 2026, 1,012 persistent sniper cohorts (2,965 wallets). Contamination-adjusted matched lift in first-30-min **buyer count +16.1%**, but **SOL inflow +6.3% (CI includes 0)**. In 7% of treated launches nobody followed the cohort. | DATA-weak | https://arxiv.org/abs/2607.02795 | Implies following cohorts adds little real demand. Covered by our wallet-copy failures. |
| B5 | "Meme Coin Factories": 15.2M coins, Jan 2024–Jan 2026. Wash trading affects 8.26% of coins. Top 1% of creator clusters made 58.6% of coins. **Copycat coins (≥10%) graduate at 0.86% vs 9.20% for originals.** 23.5% of coins followed a Twitter or Truth Social post; **31 posts each created ≥$1M of extractable value**, one $113.6M. | DATA (arXiv) | https://arxiv.org/html/2609.10246v1 | OFF (X posts). Being first is what pays. |
| B6 | MemeTrans: 41,470 launches (Dec 2024–Mar 2025) with 122 features. Market-activity and bundle features matter most. An MLP risk filter **"reducing financial loss by up to 56.1%"** compared with random selection. | DATA (arXiv dataset paper) | https://arxiv.org/html/2602.13480v1 | Loss-reduction filter, not a positive edge. |
| B7 | Rug-pull prediction from the first 5 minutes of trading: 6.4M tokens, XGBoost F1 0.79, AUPRC 0.80. Transfer across platforms fails (MCC≈0). | DATA (arXiv) | https://arxiv.org/html/2608.20271 | Filter. Covered in spirit by our ML-on-microstructure failure. |
| B8 | Copy-trading under manipulation: KOLs average 14% per coin, and a bot-resilient copier gets **3%** (before realistic latency). | DATA (arXiv) | https://arxiv.org/abs/2601.08641 | Covered (copy-KOL failure). |
| B9 | Cultural clusters: humour/parody coins have the slowest adoption (mean entry 25,897 s) and the fattest upper tail. CoinCLIP image+text viability model: AUROC 0.92 (viability, not profit). | DATA (arXiv) | https://arxiv.org/abs/2412.04913 ; https://arxiv.org/abs/2412.07591 | Mostly covered (LLM narrative judgement). |
| B10 | Mancino: Q4 2024 descriptive statistics (71.1% of Solana mints, <2% graduation). No profitability data. | DATA (descriptive) | https://arxiv.org/abs/2512.11850 | — |
| B11 | Mongardini & Mei: pump-and-dump and rug-pull losses across chains; Telegram coordination. | DATA (arXiv) | https://arxiv.org/abs/2507.01963 | — |
| B12 | Classic Telegram pump-and-dump studies (2017–2019): predicting pump targets gave up to 60% in-sample. | DATA (USENIX Sec 2019) | https://www.usenix.org/conference/usenixsecurity19/presentation/xu-jiahua | Old CEX setting. Would mean trading alongside a manipulation, so **excluded** on ethics. |

### 1.3 Protocol mechanics creating predictable flow

| # | Claim | Evidence | Source | Conditions |
|---|---|---|---|---|
| C1 | **BOOST (live 2026-07-21, default on every migration).** For about **5 min after migration the protocol TWAP-buys ~17.6 SOL** (≈$2,516 on USDC pairs) of the token in the new PumpSwap pool and **burns** what it buys. The money comes from the ~20% "dead liquidity". Mayhem tokens and pre-cutoff tokens are excluded. Graduation rate rose to 6.7% (from ~0.8% in June). | DATA-weak (The Block Data & Insights; SolanaFloor; pump.fun announcement relayed) | https://www.theblock.co/post/409815/pump-fun-token-graduation-rate-jumps-boost-changes-launch-incentives ; https://solanafloor.com/news/pump-fun-tackles-liquidity-criticism-with-boost-mode | Predictable, announced buy flow. |
| C2 | "The 17.6 SOL Ghost: reverse-engineering BOOST migration arb". The search snippet says the theoretical profit is **+15 SOL per migration, but "+2 to +4 SOL in practice"**. | ANECDOTAL (blog). **Not fetched: Medium returned 403 / Cloudflare.** Only the snippet was seen. | https://medium.datadriveninvestor.com/the-17-6-sol-ghost-reverse-engineering-pump-funs-boost-migration-arb-d443bb51cb62 | SPD likely. |
| C3 | PumpSwap fee split: 0.30% total, of which 0.20% goes to LPs, 0.05% to the protocol and 0.05% to the creator. Anyone can add liquidity (x·y=k). Record day: $840k to LPs. | DATA-weak (fee schedule is documented; returns example is MARKETING) | https://medium.com/@jump_bit/pumpswap-lp-fees-explained-how-to-earn-125-day-from-your-memecoin-pool-6cf6b2c2a918 ; https://defillama.com/protocol/pumpswap | CAP. **No published LP-profitability data found.** |
| C4 | Glass Full Foundation: pump.fun-linked wallets deployed $1.69M into ecosystem tokens over 5 days. | DATA-weak (on-chain, press) | https://thedefiant.io/news/blockchains/pumpfun-launches-glass-full-foundation-to-inject-1-69-million-liquidity-support-d8ddc535 | Discretionary buyer. Copying it is a wallet-copy variant. |

### 1.4 Off-chain event edges

| # | Claim | Evidence | Source | Conditions |
|---|---|---|---|---|
| D1 | CEX perpetual/spot listing announcements pump memecoins: BOME +~250% within hours of the Binance perp announcement; JELLYJELLY +73% on Binance/OKX perps. Possible pre-announcement insider buying. | ANECDOTAL (press cases). No memecoin-specific listing-effect study found. | https://theinformerpost.beehiiv.com/p/new-solana-based-memecoin-explodes-after-binance-launches-perpetual-futures-support ; https://decrypt.co/311713/hyperliquid-delists-solana-meme-coin-liquidation-crisis | OFF, SPD (seconds matter). |
| D2 | Google-search attention correlates positively with crypto returns (general crypto, weekly scale). | DATA-weak (MSc thesis) | https://thesis.eur.nl/pub/73657/582299.pdf | OFF. Too slow for launches. |

### 1.5 Operator and vendor write-ups (unverified)

| # | Claim | Evidence | Source |
|---|---|---|---|
| E1 | "dev buy ≥1 SOL, TP +30%, SL −30%, hold 120 s": 1,034 trades in one hour, 52.7% win rate, +40.26 SOL. The author tried 270 parameter combinations and published the best. | MARKETING (sells pumpapi.io; one hour; no transactions) | https://dev.to/gengengen/my-pumpfun-bot-makes-4000-a-day-here-are-the-4-numbers-51oa |
| E2 | Graduates show ~12 SOL in the first minute versus 0.2–0.4 SOL for non-graduates. A KOL mention "doubles" buying in the next 30 s. | MARKETING (proprietary "Deployer Hunter" dataset) | https://madeonsol.com/blog/pump-fun-first-3-minutes-graduation-math |
| E3 | Sniper-bot infrastructure guides: Jito bundles, staked RPC, ShredStream. | MARKETING (RPC vendor) | https://rpcfast.com/blog/how-to-launches-snipe-pump |
| E4 | Open-source pump.fun / bonk.fun bot with migration listeners. | Code only; no PnL | https://github.com/chainstacklabs/pumpfun-bonkfun-bot |

---

## 2. Coverage against our failed list

| Lead | Status | Note |
|---|---|---|
| A1 deployer-funded sniping | Not runnable (LAUNCH / insider) | Use only as an exclusion filter. |
| A6, B1, B4, B8, E2 (activity, top wallets, cohorts, KOLs) | **COVERED**: heat entries, wallet/KOL/streamer copy, early detectors, ML microstructure | The literature agrees with our results: below breakeven (B1), little real inflow (B4), copier return ~3% gross (B8), pump.fun bots break even (A6). |
| B1 "fast accumulation predicts graduation" | **COVERED** (heat, buyer-burst, final-stretch) | Graduation lift does not equal profit (B1 breakeven). |
| B6, B7 risk/rug filters | **Partly COVERED** (ML on 24 features) | Loss filters only. |
| B9 narrative/image models | **COVERED** (LLM narrative judgement) | — |
| B5 copycat vs original | **Partly COVERED** (sympathy/copycat plays) | The "prefer the original" filter is untested as an overlay. |
| B5 exogenous celebrity posts | **Partly COVERED** (X posts linked to launches, X engagement) | The trigger here is a post by an outside high-reach account, before any launch exists. |
| E1 dev-buy-size momentum | **COVERED** (committed-dev, good-dev) | — |
| **C1/C2 BOOST post-migration TWAP flow** | **NEW** | Hour-scale post-migration and final-stretch tests did not model the 0–300 s protocol buy flow. The repo has no mention of BOOST. |
| **B3 socials in metadata (Telegram/X/website)** | **NEW** | The `uri` is in `curve_creates`, but metadata socials were never a tested feature. |
| **B2 pre-graduation exit (depth discontinuity)** | **NEW** (exit overlay) | — |
| **A7/C3 cross-venue arbitrage of migrated tokens** | **NEW** (SPD) | — |
| **C3 PumpSwap LP provision** | **NEW** | Holder-reward fee carry was creator/holder rewards, not LP fees. |
| **D1 CEX/perp listing announcements** | **NEW** (OFF, SPD) | — |
| A4 Cashback coins | NEW but excluded | Claiming needs pump.fun Terminal (authenticated). |
| C4 GFF wallets | Variant of a COVERED idea (wallet copy) | Low priority. |
| B12 Telegram pump groups | Excluded (ethics) | — |

---

## 3. Top 5 NEW, ethical, testable ideas for a solo trader

Rules are written so they can be run through `PointInTimeView`, with explicit fees: the curve
`fee_bps`/`cfee_bps`, PumpSwap 30 bps, priority/Jito tips, and our 0.25–1 s latency. Each rule
needs a written rationale before simulation (`add-hypothesis --rationale`). None needs launching
tokens, wash trading, sandwiching or authenticated APIs.

### Idea 1: trade alongside the BOOST buyback (C1, C2). Flag: SPD helps.
- **Why it might work:** the buy flow is protocol-scheduled and announced, worth 17.6 SOL over ~300 s.
  Against a ~85 SOL real pool, 17.6 SOL of buying alone would lift price by about
  ((85+17.6)/85)² ≈ 1.46× if no one else traded. This flow does not react to the tape. The open
  question is whether curve holders' exits (B2) and first-block buyers already absorb it.
  Trading next to a scheduled protocol buyback is like index-rebalance trading: no user's order
  is front-run.
- **Rule (H-BOOST-a):** at the first `amm_trades` row of a newly created pool (`amm_pools`), or at
  `curve_completes` + latency L ∈ {0.25, 0.5, 1 s}, buy S ∈ {0.1, 0.5, 1} SOL. Exit in equal
  slices at t = 60/120/180/240 s after pool creation, all out by 280 s (before the TWAP ends).
  Stop out if price < entry − 25%.
- **Rule (H-BOOST-b, conditional):** trade only when the token amount bought on the curve in the
  last 60 s before completion is less than q% of supply (fewer fresh holders who will sell).
  q is set on train data only.
- **Data:** `amm_pools`, `amm_trades` and `curve_trades` (already recorded). First identify the
  BOOST signer: the `usr` that buys in nearly every new pool during 0–300 s and whose tokens are
  burned. Then measure the realised TWAP schedule and the net non-BOOST flow per second.
  Excluding Mayhem tokens needs the Mayhem flag, which another agent is already working on.

### Idea 2: socials-metadata filter with a breakeven test and pre-graduation exit (B3 + B1 + B2)
- **Why:** Telegram presence gives an 8.9× graduation lift, which is large and cheap to observe in
  metadata at creation. Lift is not profit, so use B1's test: enter only if the conditional
  graduation probability beats vSol²/1152 after fees. Exit **before** completion because of B2.
- **Rule (H-SOCIAL):** at creation + L, fetch the metadata JSON at `curve_creates.uri`. If it has
  a Telegram link and (an X link or a website), and vSol is ≤ 35 virtual SOL, buy S. Exit when
  real SOL reaches ≥ 75 (before completion), or after 15 min, or at −30%.
  Variant: require that the X/Telegram URL is not reused across creators (an anti-farm check).
- **Data:** recorded `curve_creates.uri` and `curve_trades`. New public collector: an IPFS gateway
  fetch of the metadata JSON (public, unauthenticated). Fix the cutoffs on the train window only.

### Idea 3: pre-graduation exit overlay applied to everything (B2)
- **Rule (H-EXIT):** for any held position on the curve, sell when real SOL ≥ X (X ∈ {70, 75, 80})
  rather than holding through migration. Compare with "hold to T+5 min after migration" on the
  same entries.
- **Purpose:** this is an execution edge, not a standalone entry. Re-run the least-bad failed
  entries (e.g. good-dev) with this exit and report the change in PnL, without re-tuning the
  entry. Ideas 1 and 3 interact: BOOST may have reversed B2's sign since July 2026, which is
  itself a testable point.
- **Data:** recorded `curve_trades`, `curve_completes` and `amm_trades`.

### Idea 4: cross-venue arbitrage of migrated tokens (A7). Flag: SPD/infrastructure-heavy.
- **Why:** this is the one Solana activity with large, documented aggregate profit (Helius:
  $142.8M a year). It is atomic and non-predatory: it brings prices together across pools and
  touches no user's pending order. The expected margin per trade is small (~$1.58 average), so
  it needs Jito bundles and a fast RPC.
- **Rule (H-ARB):** for mints with a PumpSwap pool and at least one other pool (Meteora DLMM/DAMM,
  Raydium CPMM), if after each PumpSwap trade the quoted round trip (buy cheap venue, sell dear
  venue) at size S gives an edge greater than fees + tip + 1 tick, record an arbitrage at
  latency L. The trade counts as filled only if no third-party transaction closed the gap in
  the same or next slot.
- **Data:** recorded `amm_trades` for PumpSwap. New public collector: `logsSubscribe` on the
  Meteora and Raydium program IDs for the same mints. Results are an upper bound unless we
  model competing arbitrageurs.

### Idea 5: CEX/perp listing-announcement trades on Solana memecoins (D1). Flag: OFF, SPD.
- **Why:** the information is off-chain and public, and listing announcements produce documented
  jumps (BOME, JELLYJELLY). This is the "be first to the news" profile that our data says is the
  only place edge remains.
- **Rule (H-LIST):** when a public announcement feed names an SPL memecoin with a Solana DEX pool,
  buy S on the deepest Solana pool at announcement + L (L ∈ {1, 5, 30 s}). Exit at +5/+15/+60 min
  or −20%. Feeds: Binance and OKX announcement pages, Upbit notices, or a new asset in the
  Hyperliquid `meta` endpoint.
- **Data:** a new public collector polling these unauthenticated endpoints. Historical backfill
  from the announcement archives plus public GeckoTerminal OHLCV, or our own RPC swap history,
  for event studies. Expect few events per month, so pool many months.
- **Risk:** pre-announcement leakage means much of the move may come before the public post.
  Measure the price drift from T−60 min to T to check.

### Also worth an overlay test (not top 5)
- **Avoid-filters:** drop tokens whose deployer funded a same-block buyer (A1: one-hop SOL
  transfer in the 24 h before creation), and drop copycats of an earlier mint with the same
  name and symbol (B5). Then re-run any baseline and check whether losses shrink.
- **PumpSwap LP provision:** earns the 0.20% LP fee in the first 5 min after migration (BOOST
  volume) against impermanent loss on a token that usually falls. No published LP-return data
  was found, but it can be measured from `amm_trades` reserves.

## Gaps and not accessed
- C2 (Medium) was blocked by Cloudflare; only the search snippet was seen.
- The Galaxy Research full report was not fetched (press summary only).
- No published study of PumpSwap LP returns, of BOOST price paths, or of memecoin
  listing-announcement effects was found.
- Kamat's preprints (B3, B4) are single-author and not peer-reviewed.
