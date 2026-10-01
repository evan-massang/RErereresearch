# Information environment: tools and protocol mechanics

_Generated from `info_environment.json` (web-search leads collected 2026-10-01T11:07:10Z). Everything here came from search-result titles or model-written search summaries; pages were not fetched. Treat each line as a lead to confirm against video frames or official docs, never as fact._

## Axiom (axiom.trade; X account @AxiomExchange; also called Axiom Pro / Axiom Exchange)

> Axiom is the fastest and most feature-rich hybrid web trading experience, designed to elevate your crypto journey with advanced analytics and high-speed execution. With wallet tracking and twitter monitoring, Axiom is packed with powerful features tailored for both beginners and pro traders. — https://docs.axiom.trade/
> Axiom is a one-stop shop for memecoin trading, described as the fastest, cheapest, and most efficient DEX for all levels of traders. — https://docs.axiom.trading/

| field | where in UI | definition given | sources |
|---|---|---|---|
| Pulse lifecycle columns: New Pairs (docs.axiom.trading calls it 'New Creations') / Final Stretch / Migrated (docs: 'Migrated to Raydium') | Pulse (three live columns) | Final Stretch = tokens close to completing the bonding curve; Migrated = tokens that completed migration, newest at top. | https://docs.axiom.trade/axiom/finding-tokens/pulse, https://docs.axiom.trading/features/pulse |
| Token age (minutes) | Pulse filter (whether shown on each card not confirmed by docs text) |  | https://docs.axiom.trade/axiom/finding-tokens/pulse |
| Top 10 holders % | Pulse filter; Pulse row (third-party claim); pair audit (warning threshold) | Total combined token percentage held by the top 10 holders; audit warns above 15%. | https://docs.axiom.trading/features/pair-audits, https://x.com/KingCodjoe/status/1895137794500001962 |
| Dev holding % (and 'Dev Sold' flag) | Pulse filter / Pulse row; 'Dev Sold' appears in a user's description of a Pulse result | Percentage of supply held by the developer (creator) wallet. | https://docs.axiom.trade/axiom/finding-tokens/pulse, https://x.com/KingCodjoe/status/1895137794500001962 |
| Snipers % | Pulse filter / Pulse row | Percentage of early buyers (snipers); no time/block window given in any result. | https://docs.axiom.trade/axiom/finding-tokens/pulse |
| Insiders % | Pulse filter / Pulse row | Percentage held by insiders '(private sales, team members)'; detection method not given. | https://docs.axiom.trade/axiom/finding-tokens/pulse |
| Bundle % (bundled supply) | Pulse filter / Pulse row | Supply held in bundle wallets; a bundle is flagged when at least four transactions happen in the same block. | https://docs.axiom.trade/axiom/finding-tokens/pulse, https://docs.axiom.trade/faqs |
| Pro Traders (shown as a % filter in docs; shown as a count, '801 Pro Traders', in a user post) | Pulse filter / Pulse row | 'percentage of experienced traders holding or trading the token. Indicates traders using other platforms.' (ambiguous) | https://docs.axiom.trade/axiom/finding-tokens/pulse, https://x.com/KingCodjoe/status/1895137794500001962 |
| Holder count | Pulse filter / Pulse row | Number of wallets holding the token. | https://x.com/KingCodjoe/status/1895137794500001962 |
| Liquidity, volume, market cap, transaction counts | Pulse filters (card display not confirmed in docs text) |  | https://docs.axiom.trade/axiom/finding-tokens/pulse |
| LP Burned % | Pair audits (token page) | Percentage of LP claim tokens burned; warning under 50%. | https://docs.axiom.trading/features/pair-audits |
| Dex Paid indicator | Pulse row / token (seen in user post listing a Pulse result) | Whether the token has paid DEX Screener to update its token info (per a third-party Q&A page). | https://x.com/KingCodjoe/status/1895137794500001962, https://academy.pandatool.org/en_US/question/1650 |
| Dev history: 'Dev Migrated 1 token' | Pulse row (user post) | Not defined by any official source found. One search summary interpreted it as liquidity already migrated, which does not match the wording 'Dev Migrated 1 token' (that wording reads like a count attached to the dev). Un | https://x.com/KingCodjoe/status/1895137794500001962 |
| Clusters % | Pulse row (user post); 'Chart Bubble Clusters' in a 2026 update post | Not defined in any result. | https://x.com/KingCodjoe/status/1895137794500001962, https://x.com/watchingmarkets/status/2071879061207490561 |
| Twitter/X preview popup on Pulse; Pulse Twitter handle and stats | Pulse |  | https://docs.axiom.trade/twitter-preview-popup, https://x.com/_gabriel_bessa/status/1900612870804586726 |
| KOL / tracked-wallet holdings (Top KOL and Watched Holding Lines; KOL hovers; dev funding; bubblemaps on Pulse) | Pulse / chart (update posts) |  | https://x.com/AxiomExchange/status/1942592760915321133 |
| Migration market-cap line (chart) | Chart (update list, unattributed) |  | unattributed summary |
| Transactions feed per trade: Trader Level, Age, Price (USD or SOL), Total (USD or SOL); 100 most recent or oldest | Token trading page - Transactions Feed |  | https://docs.axiom.trading/features/trading-page/transactions-feed, https://docs.axiom.trading/features/trading-page |
| Trader Scan: per-wallet bought/sold amounts, current balance, realized PnL | Token page (embedded in the orderbook interface) |  | https://docs.axiom.trade/trader-scan |
| Top holders / top traders with average entry and exit, wallet funding source, Atlas holder map | Token page (third-party description; official update post lists 'Top Holders Avg. Entry/Exit') |  | https://axiompro.app/token-scanner/, https://x.com/AxiomExchange/status/1942592760915321133 |
| Tracked wallets' buys/sells on charts and trade feeds | Chart / trade feed |  | unattributed summary |
| PnL on Pulse; quick-hover price charts; fees in PnL; average entry and exit; pump.fun livestreams; Twitter communities | Pulse / position views (update posts) |  | https://x.com/watchingmarkets/status/2071879061207490561, https://x.com/7xNickk/status/1930163388191257064 |

Features:

- One-click Quick Buy from Trending Pairs, New Pairs and Pulse rows (https://docs.axiom.trading/features/quick-buy, https://x.com/7xNickk/status/1930163388191257064)
- Pulse filters (about 14 numeric filters per third-party guides) (unattributed summary)
- Wallet tracker with live alerts (import from BullX supported). Capacity: 300 wallets in one summary vs. 10,000 after a July 2025 revamp in another; latency claim of 'millisecond delay' from a user post (https://docs.axiom.trade/wallet-tracking/monitor-wallets, https://x.com/0xRiver8/status/1890318942327222742)
- Tweet Monitor / Twitter tracker (built in; scans key crypto accounts; custom handles; notifications; free with at least 5 SOL of trading volume) (https://docs.axiom.trade/tweet-monitor)
- Trader Scan (wallet-level activity inside the orderbook) (https://docs.axiom.trade/trader-scan)
- Multi-wallet trading (https://docs.axiom.trade/multi-wallet, https://x.com/7xNickk/status/1930163388191257064)
- Quick View buttons (quick trending, quick new pairs from any page) (https://docs.axiom.trading/features/quick-view-buttons)
- Buy/sell execution settings: slippage, priority fee (default 0.001), bribe fee, MEV protection modes Off/Reduced/Secure, SMART preset (https://docs.axiom.trading/features/buy-sell-settings, https://docs.axiom.trading/features/buy-sell-settings/bribe-fee (+2))
- Surge (algorithmic alerts), Pulse Tracker, Vision (KOL/insider wallet discovery) - July 2025 (https://x.com/AxiomExchange/status/1942592760915321133)
- Pulse sound alerts; separate Pulse quick-buys; ultra quick buy button; Lighthouse; custom themes (June 2025 user post) (https://x.com/7xNickk/status/1930163388191257064)
- Katana Mode V2; PnL on Pulse; quick-hover price charts; chart bubble clusters (June 2026 user post) (https://x.com/watchingmarkets/status/2071879061207490561)
- Other docs pages seen only as titles: Migration Actions, Limit Orders, Similar Tokens, Explore Tokens, Portfolio, Custom RPC, Moonshot Swaps (https://docs.axiom.trade/axiom/swap/migration-actions, https://docs.axiom.trade/axiom/swap/limit-orders (+4))
- Platform fee and cashback tiers (net 0.95% Starter down to 0.75% Champion) (https://docs.axiom.trade/getting-started/fees/axiom-fees)

Used by traders (leads):

- A user post describes their Axiom Pulse filter setup and the per-token readout (holders, pro traders, dev history, top-10 %, dev sold, snipers, insiders, clusters, dex paid). (https://x.com/KingCodjoe/status/1895137794500001962)
- Twitter trackers (J7) are installed as bookmarks/extensions on top of Axiom (and other terminals), i.e. traders run social feeds inside the trading terminal. (https://www.youtube.com/watch?v=R3iOhSHMTjY)
- Posts by named traders or accounts reference Axiom (content not visible beyond titles). (https://x.com/Cupseyy/status/1950235617125945790?lang=en)
- Multiple third-party guides and reviews of Axiom exist (Coin Bureau, Token Metrics, Boxmining, Medium); they show wide use but are not trader-behaviour evidence. (https://coinbureau.com/review/axiom-trade-review, https://boxmining.com/axiom-memecoin-trading-guide/)

## J7 Tracker (j7tracker.io; X: @j7tracker_ and @j7trackerio; Discord discord.gg/j7tracker)

> J7Tracker offers sub-1ms server-side deploys and social-media tracking under 200ms, positioning itself as the fastest deployer and social tracker in crypto. — unattributed
> J7 Tracker is described as the fastest crypto deployer and social media tracker available, designed to be simple, fast and reliable. — unattributed

| field | where in UI | definition given | sources |
|---|---|---|---|
| Tweets from tracked accounts, aimed at new coin launches / narratives | Overlay/bookmark opened on the trading terminal (Axiom, 'Terminal', Fomo) or on X |  | unattributed summary |
| Translation of coin names, tickers and tweets (hover) | Hover overlay on Axiom Pro |  | unattributed summary |
| Token auto-search from terminals; 'VAMP coins' | J7 browser extension (J7Extension on Chrome; 'J7 Tracker' on Firefox) | 'VAMP' is not defined in any result. | unattributed summary |
| Images (a separate 'J7 Image Extension' exists) | Unknown | Not described. | https://www.youtube.com/watch?v=34mYnf9LiXk |
| Tweet card metadata (author, followers, translation, media, quotes, replies, URLs) | Unknown | NOT FOUND in any search result. | unattributed summary |

Features:

- Latency claim: social-media tracking under 200 ms; sub-1 ms server-side deploys (self-reported) (unattributed summary)
- Token deployer + trading HTTP API (POST /submit; 'type' = action, 'mode' = launchpad; create_token; needs session_id JWT + encrypted API key) (https://docs.j7tracker.io/docs/create-token, https://docs.j7tracker.io/docs/trade-token/buy-token)
- Supported launchpads and launch features: Pump.fun, OTC Desks, LaunchLab (Bonk, StonkFun); SOL/USDC; fee sharing; bundling; sniping; bundle wallets; mayhem (https://docs.j7tracker.io/docs/platforms, https://x.com/imsheepsol/status/1988662218557386947)
- fees.fun integration (claimed 75% saving on deploys and sells; bundle wallets) (https://docs.fees.fun/platforms/j7-tracker)
- Browser extensions and versions (Firefox 'J7 Tracker' v3.0 updated 2026-09-11; Chrome 'J7Extension' v2.088 updated 2026-09-23, per summaries) (unattributed summary)
- RugCheck flags J7Tracker-launched tokens as 'spam launcher' tokens (Oct 2025) (https://x.com/Rugcheckxyz/status/1975154971206365423)

Used by traders (leads):

- Traders use it for narratives and as a Twitter tracker + deployer overlay on terminals. (https://x.com/boogiepnl/status/1988355623927402895, https://x.com/MonyyFN/status/1980392932579635308 (+3))

## GMGN (gmgn.ai)

> GMGN gives access to trending tokens, Trenches new token listings, and professional on-chain data — including Smart Money, KOL, rat trader, and bundler analytics. — unattributed
> GMGN.AI Tutorial — https://docs.gmgn.ai/index

| field | where in UI | definition given | sources |
|---|---|---|---|
| Trenches lifecycle stages: new_creation / near_completion / completed (API naming) | Trenches | new_creation = just created, still on bonding curve; near_completion = bonding curve nearly full; completed = graduated to open market / DEX. | unattributed summary |
| Wallet tags: smart money (smart_degen), KOL (renowned), sniper, bundler, rat trader, dev, insider; others such as whales, new wallets, followed | Token page icons / trade activity | See protocol_mechanics definitions. | https://docs.gmgn.ai/index/featured-icon-definition |
| Token metrics: top-10 holder rate, smart-money count, KOL holders, rat-trader volume share, bundler volume share, sniper count, dev still holds / sold | Token info (API fields; on-screen equivalents likely but not confirmed) |  | unattributed summary |
| Insider traders / snipers / first 70 buyers panel | Token page (docs page title only) |  | https://docs.gmgn.ai/index/insider-traders-snipers-first-70-buyers |
| Chart, multicharts, activity | Token page (docs page title only) |  | https://docs.gmgn.ai/index/token-page-chart-multicharts-activity-trading-system |

Features:

- Smart-money / KOL wallet tagging with 7d/30d profitability filters (unattributed summary)
- Agent/OpenAPI skills for querying tokens, wallets, market data and trading (Solana, BSC, Base) (https://github.com/GMGNAI/gmgn-skills)

## Photon (Photon-SOL)

> Memescope is a customizable real-time feed of new meme coins, and Photon lets users see dev buys, dev sells, and sniper buys on charts. — unattributed

| field | where in UI | definition given | sources |
|---|---|---|---|
| Memescope monitors: Newly Created / About to Graduate / Graduated | Memescope | About to Graduate = 'Coins that are about to fill in real time'; Graduated = 'Coins that recently migrated' (user post). | https://x.com/shahh/status/1886552147224891673 |
| Memescope filters: at least one social; dev holding %; snipers; bot holders; age (mins) | Memescope filters |  | https://x.com/spunosounds/status/1876151219275919429 |
| Dev buys, dev sells and sniper buys marked on charts | Chart |  | unattributed summary |

Used by traders (leads):

- User posts share Memescope filter presets. (https://x.com/spunosounds/status/1876151219275919429)

## BullX / BullX Neo

> Explore Page — https://bullx.gitbook.io/bullx-neo-docs/finding-tokens/explore-page

| field | where in UI | definition given | sources |
|---|---|---|---|
| Pump Vision buckets: New / About to Graduate / Graduated | Pump Vision | About to Graduate = 'approaching the $69K bonding curve completion' (third-party). | unattributed summary |
| Bonding curve %, developer holding %, holder count, token age (filters, June 2024); bot holders | Pump Vision filters |  | https://x.com/bullx_io/status/1806822135710502979?lang=en, https://x.com/bullx_io/status/1806822127154446387 |

Features:

- Wallet lists importable into Axiom's tracker (Axiom docs mention BullX) (https://docs.axiom.trade/wallet-tracking/monitor-wallets)

Used by traders (leads):

- Third-party filter recommendations attributed to 'pro traders' (unverified). (unattributed summary)

## Padre (trade.padre.gg; reportedly now 'Terminal'; acquired by Pump.fun per a headline)

> cointelegraph:747d37f84094b:0 pump fun expands with padre acquisition as memecoin market cools — https://www.tradingview.com/news/cointelegraph:747d37f84094b:0-pump-fun-expands-with-padre-acquisition-as-memecoin-market-cools/
> Based on the search results, here are the key features of Padre trading terminal (now called "Terminal"): — unattributed

| field | where in UI | definition given | sources |
|---|---|---|---|
| 'Live Jeetgrids' (movements of early holders) | Token page (third-party) |  | unattributed summary |
| Developer allocation tracking, honeypot detection, rug warnings | Security indicators (third-party) |  | unattributed summary |

Features:

- Execution speed claim and order types (unattributed summary)
- Fees: 1% standard, down to 0.4% with discounts (third-party) (unattributed summary)

Used by traders (leads):

- J7 overlays are described as usable on 'Terminal' (possibly Padre's renamed product). (unattributed summary)

## Telegram bots: Trojan, BONKbot

> Trojan on Solana is a Telegram trading bot on Solana that has become the largest player in the space, with a lifetime volume of almost $23.4 billion and over 1.7 million total users. While using Trojan on Solana is free, it charges a fee of 0.9% with a referral or 1% without for every successful transaction. — unattributed
> BONKbot's routing is powered by Jupiter, allowing BONKbot to find the best available prices for tokens across DEXs on Solana. There is a charge of 1% fees on every successful swap transaction. — unattributed

Features:

- Trojan: Simple/Advanced modes; MEV protection; auto buy/sell; up to 10 wallets; limit/DCA; copy trading; sniper with mint/freeze-authority checks and blacklists (unattributed summary)
- BONKbot: no launch sniper at time of writing ('Nighthawk' forthcoming) (unattributed summary)

Used by traders (leads):

- Axiom's docs pitch its wallet tracker as replacing Telegram wallet bots, which suggests those bots were part of prior workflows. (https://docs.axiom.trade/wallet-tracking/monitor-wallets)

## Pump.fun (launchpad web UI and related surfaces)

> Pump.fun — Launch and trade memecoins on Solana — https://pump.fun/docs/fees

| field | where in UI | definition given | sources |
|---|---|---|---|
| King of the Hill (homepage top spot) | pump.fun homepage | Token surpassing $30,000 market cap can take the top spot; about 45 SOL needed (third-party). | unattributed summary |
| Pump.fun livestreams (also surfaced inside Axiom per a June 2025 user post) | pump.fun / Axiom |  | https://x.com/7xNickk/status/1930163388191257064 |

Features:

- Mayhem Mode (opt-in AI trading agent during first 24h). See protocol_mechanics. (unattributed summary)
- Ecosystem acquisitions: Kolscan (mid/July 2025) and Padre (date not captured) (https://www.tradingview.com/news/cointelegraph:747d37f84094b:0-pump-fun-expands-with-padre-acquisition-as-memecoin-market-cools/)

Used by traders (leads):

- Axiom docs position Pulse as a replacement for watching pump.fun's own site. (https://docs.axiom.trading/features/pulse)

## DEX Screener

> DEX Screener — https://dexscreener.com/

| field | where in UI | definition given | sources |
|---|---|---|---|
| Trending rank / Trending Score (partly paid via Boosts) | Trending feed | CONFLICT: one description lists volume, liquidity depth, tx frequency, holder growth, active Boosts; another lists market activity, page visits, community reactions, trust signals, with Boost multipliers and an Enhanced  | unattributed summary |
| Enhanced token info (paid profile update) - the basis of 'DEX Paid' badges in terminals | Token profile; mirrored as 'Dex Paid' in Axiom |  | unattributed summary |

## Birdeye

> Birdeye: Live charts, security checks, alerts & in-page swap — https://solanabox.tools/tools/birdeye

| field | where in UI | definition given | sources |
|---|---|---|---|
| Security panel: mint and freeze authority, top-10 holder concentration, LP status; Top Holders Percentage alert | Security tab under the main chart on token page |  | unattributed summary |
| Dashboard lists: trending, top gainers/losers, new listings, market overview | Main dashboard |  | unattributed summary |
| Top traders by PnL (API; Solana only) | API (UI equivalent not confirmed) |  | unattributed summary |

## RugCheck (rugcheck.xyz)

> RugCheck is the most widely used Solana-specific token analyzer that provides a simple Good/Warning/Danger rating based on mint authority, freeze authority, LP burn status, and top holder concentration. — unattributed

| field | where in UI | definition given | sources |
|---|---|---|---|
| Risk score 0-100 (higher = riskier); Good/Warning/Danger | Risk report |  | unattributed summary |
| Mint/freeze authority, LP lock status/duration/% of supply in LP, top holders, insider/connected-wallet graphs | Risk report |  | https://rugcheck.xyz/tokens/7bBzoaugm2faijE4QAGUPszSEzg3Cy4BKdaoGxdtyLvs |
| Spam-launcher detection (Uxento, RapidLaunch, J7Tracker) - Oct 2025 | Risk report / API |  | https://x.com/Rugcheckxyz/status/1975154971206365423 |

## Kolscan (kolscan.io) and KOL leaderboards

> Kolscan is a Solana wallet tracker that monitors the activities of top memecoin traders and KOLs, providing realtime transactions, token PnL, and a leaderboard ranking their performance. — unattributed

| field | where in UI | definition given | sources |
|---|---|---|---|
| Live KOL swap feed; PnL leaderboard; per-wallet trade history, token-level PnL, win rate, trade frequency | kolscan.io | Ranked by trading PnL, not follower count. | unattributed summary |

Features:

- Acquired by Pump.fun (mid-2025 / July 2025); free since (unattributed summary)
- Alternative KOL/PnL leaderboards (Solana Tracker) (https://www.solanatracker.io/leaderboard/pnl, https://docs.solanatracker.io/guides/kol-tracking)

Used by traders (leads):

- Copy-trading guides reference Kolscan wallet lists. (https://medium.com/@GEMQUEENx/best-solana-wallets-to-copy-trading-53bf701e997a)

## Cielo (cielo.finance) wallet tracker

> Cielo Finance is a multi-chain wallet tracker and on-chain activity feed that includes full Solana support. It helps traders monitor wallets, token swaps, NFT activity, and broader market flows in real time through a web app and optional Telegram/Discord alerts. — unattributed

| field | where in UI | definition given | sources |
|---|---|---|---|
| Labelled transaction feed; 'Lite' swap-only feed | Web app feed |  | unattributed summary |

Features:

- Telegram/Discord alerts with rules (first trade of a token; multiple wallets buying same token within X hours; tx type, chain, min USD) (unattributed summary)

Used by traders (leads):

- Described as a leading memecoin whale tracker (third-party claim). (unattributed summary)

## Other social-feed / deployer tools seen in results (titles or one-line summaries only)

> Uxento designs smart tools for users who want to trade and deploy memecoins at the highest level, and is the #1 deployer platform in deploys and transactions in 2026. It offers automations to automate token creation and trading with AI including quick deploy presets, scraper, auto-deployer, and auto-sniper. — unattributed
> Rapid Launch — https://rapidlaunch.io/

## Protocol mechanics (inputs to the execution model — verify before use)

| topic | value / description | as of | conflicts | sources |
|---|---|---|---|---|
| pump.fun graduation (bonding-curve completion) trigger and threshold | Completion is reached when the last real token on the curve is sold, which is described as ~85 SOL of net buying; commonly quoted as ~$69K market cap (a USD figure that depends on SOL/USD). | 2026 guides (exact dates not captured) | Tokens sellable on the curve: ~800M (S30 guide, Raydium-era wording) vs initial real token reserves 793,100,000,000,000 raw units = 793.1M tokens at 6 decimals (S27). The 6 decimals is inferred: S28 g | https://www.soltokencreator.io/blog/pump-fun-graduation-explained |
| pump.fun bonding-curve parameters and pricing formula | Constant product on virtual reserves: virtual_sol_reserves * virtual_token_reserves = k. Initial virtual SOL = 30,000,000,000 lamports (30 SOL); initial virtual token reserves = 1,073,000,000,000,000 raw (also seen as 1,072,999,999,992,855); initial real token reserves = 793,100,000,000,000 raw; token total supply = 1,000,000,000,000,000 raw. Values are initialized from the Global account at coin  |  | Summary errors: S28 says total supply is '1 trillion tokens' although 1e15 raw units with 6 decimals is 1 billion tokens (pump.fun fee docs also use 1 billion). S27's 'approximately 0.000028 SOL' init | unattributed summary |
| pump.fun bonding-curve trading fee (time series) | 1% per bonding-curve swap before May 2025 -> creator fee added May 2025 (0.05%) -> Project Ascend / Dynamic Fees V1 (Sept 2025) with creators earning 0.3% on the curve -> current pump.fun docs: 1.25% total on the curve (creator 0.300% + protocol 0.950% + LP 0%). | Before May 2025: 1%; 2025-05 (creator fees from 2025-05-13 per docs); 2025-09-03 Project Ascend unveiled; current docs read on 2026-10-01 (page undated) | The pre-May-2025 1% figure and the current 1.25% total are from different dates. Whether the protocol share stayed at 0.95% from Sept 2025 to now, and what changed in Jan 2026, was not established. Th | https://pump.fun/docs/fees |
| pump.fun creator-fee schedule (Project Ascend / Dynamic Fees V1) and Jan 2026 changes | Creator fee scales with market cap: 0.95% under $300K down to 0.05% above $20M (Sept 2025). Jan 2026: creator fee sharing across up to 10 wallets, ownership transfer, revoke update authority; founder post says creator fees 'need change'. | 2025-09 (V1); 2026-01 (fee-sharing update; founder post decoded to 2026-01-09) | The Sept 2025 dollar-denominated tiers ($300K / $20M) differ from the SOL-denominated PumpSwap tiers in current docs (420 SOL ... 98,240 SOL). They may be the same schedule expressed in different unit | https://x.com/a1lon9/status/2009677442064024063 |
| PumpSwap fees (post-graduation AMM) | At launch (2025-03-20): 0.25% (0.20% LP + 0.05% protocol); creator 0.05% added May 2025. Current docs: canonical pools tiered by SOL market cap, from 1.25% (0-420 SOL: creator 0.300 / protocol 0.930 / LP 0.020) through 1.20% (420-1470), 1.15% (1470-2460), 1.10% (2460-3440) ... down to 0.30% (>=98,240 SOL: 0.050/0.050/0.200). USDC pools: 1.25% (0-59,000 USDC) down to 0.30% (>=20,000,000 USDC). Non- | Launch 2025-03-20; current docs read 2026-10-01 (undated) | The 0.25% launch fee and the tiered 0.30%-1.25% current schedule are different dates. Intermediate tiers between 3,440 and 98,240 SOL were elided ('...') in the summary and were not captured. | https://pump.fun/docs/fees |
| Graduation / migration fee | 6 SOL when migrating to Raydium (pre-PumpSwap); eliminated at PumpSwap launch (2025-03-20); current docs list a 0.015 SOL graduation fee and 0 SOL coin creation. | pre-2025-03-20: 6 SOL; 2025-03-20: 0; current docs (read 2026-10-01): 0.015 SOL | 'no migration fee' (March 2025 news) vs '0.015 SOL graduation fee' (current docs); different dates. | https://www.kucoin.com/news/articles/pump-fun-debuts-pumpswap-dex-with-0-25-fee-structure-and-zero-sol-migration-fee-to-reclaim-solana-s-memecoin-market, https://pump.fun/docs/fees |
| Migration destination and LP handling | Raydium before March 2025; PumpSwap (Pump.fun's own AMM) since 2025-03-20. Remaining tokens and accumulated SOL seed the pool; LP burned automatically. | 2025-03-20 switch | Axiom docs (both domains) still say 'Migrated to Raydium' for the Pulse column; terminal labels may lag protocol changes. | https://www.theblock.co/post/347360/pump-fun-launches-dex-called-pumpswap-to-instantly-migrate-graduated-tokens |
| King of the Hill (pump.fun homepage feature) | Token passing ~$30,000 market cap can take the homepage top spot; ~45 SOL needed (third-party). |  | No official pump.fun source captured; unknown whether the feature or threshold still exists in 2026. | unattributed summary |
| pump.fun Mayhem Mode | Opt-in at launch; an AI agent ('Agent Pumpy') trades the token randomly during its first 24 hours, minting an extra 1 billion tokens per eligible project and burning unsold ones; started November 12 (year from the related X post ID: 2025). | November 12 (summary gives no year; a J7 post about Mayhem tokens decodes to 2025-11-12) | The summary's phrase 'without creating new tokens' sits next to 'mint an additional 1 billion tokens'; wording is internally inconsistent. Important for simulation: early volume on Mayhem tokens may i | https://x.com/imsheepsol/status/1988662218557386947 |
| Priority fees and Jito tips (execution cost and speed) | Axiom: priority fee default 0.001 (unit not stated, presumably SOL), separate 'bribe' fee, MEV modes Off/Reduced/Secure, SMART preset sets fees dynamically. Third-party ranges: priority 0.0005-0.001 SOL default, 0.002-0.005 SOL for contested snipes, spikes to 0.01+ SOL; Jito tips 0.001-0.01 SOL normal, up to 0.05 SOL in launches; Jito tip is on top of priority fee; ~95% of active stake on Jito cli | Axiom docs undated; third-party guides 2026 | All tip/fee ranges are third-party guidance, not measured from the traders under study. | https://docs.axiom.trading/features/buy-sell-settings, https://docs.axiom.trading/features/buy-sell-settings/bribe-fee, https://docs.axiom.trade/getting-started/fees/solana-fees |
| Terminal / bot platform fees (per trade) | Axiom net 0.95% (Starter) to 0.75% (Champion) after cashback (official docs); third-party says '1% less cashback'. Trojan 1% (0.9% with referral). BONKbot 1%. Padre 1% down to 0.4% (third-party). | Docs/reviews undated (read 2026-10-01) |  | https://docs.axiom.trade/getting-started/fees/axiom-fees |
| Definition: bundle / bundler | Axiom: multiple buys as separate transactions in the same block; flagged as a potential bundle if at least four transactions occur in the same block; Pulse shows Bundle % (supply held in bundle wallets). GMGN: a single account combines multiple wallets' transactions into one bundle processed in the same block; GMGN API exposes bundler volume share. |  | Axiom's heuristic (>=4 txs in one block) is tool-specific; GMGN's wording implies a single Jito-style bundle. The same token can show different bundle numbers in different tools. | https://docs.axiom.trade/faqs, https://docs.axiom.trade/axiom/finding-tokens/pulse, https://docs.gmgn.ai/index/featured-icon-definition |
| Definition: sniper | Axiom: percentage of early buyers (no window given). GMGN: wallets buying within the first few blocks after the pool/trading opened. |  | Neither tool's exact block/time window was found. | https://docs.axiom.trade/axiom/finding-tokens/pulse, https://docs.gmgn.ai/index/featured-icon-definition |
| Definition: insider | Axiom: percentage held by insiders '(private sales, team members)'. GMGN: wallets that hold tokens without having bought after trading opened (e.g., creator's tokens transferred to multiple wallets); 'rat trader' tags insider/sneak trading. |  | Axiom's '(private sales, team members)' wording reads generic; its on-chain detection method is undocumented in results. | https://docs.axiom.trade/axiom/finding-tokens/pulse, https://docs.gmgn.ai/index/featured-icon-definition |
| Definition: dev holdings / dev | Axiom: percentage of supply held by the developer wallet (Dev Holding %); 'Dev Sold' flag seen in a user post. GMGN: Dev = token creator; API reports whether the developer still holds or has sold. |  | Whether 'dev' covers only the creator wallet or also linked/funded wallets is not stated by either tool. | https://docs.axiom.trade/axiom/finding-tokens/pulse, https://docs.gmgn.ai/index/featured-icon-definition, https://x.com/KingCodjoe/status/1895137794500001962 |
| Definition: pro traders (Axiom), smart money / KOL (GMGN), LP burned and top-10 warning thresholds (Axiom pair audits) | Axiom Pro Traders = 'percentage of experienced traders holding or trading the token. Indicates traders using other platforms.' GMGN smart_degen = smart money, renowned = KOL. Axiom audits warn when top-10 > 15% and LP burned < 50%. |  | The 'Pro Traders' definition is ambiguous ('traders using other platforms' could mean wallets trading via other terminals/bots). | https://docs.axiom.trade/axiom/finding-tokens/pulse, https://docs.axiom.trading/features/pair-audits |

## Open questions (settle these from frames / primary sources)

- Which Axiom Pulse fields are printed on each card (vs. only available as filters)? Official docs list filters (age, top-10 %, dev %, snipers, insiders, bundles, pro traders, liquidity, volume, market cap, tx counts) but no card layout. Bonding-curve %/migration progress on Axiom cards and any viewer/watcher counts were NOT found. Video frames must settle this, and the layout changed over time (updates dated 2025-03-14, 2025-06-04, 2025-07-08, 2026-06-30).
- Exact detection rules: Axiom snipers (time/block window), insiders (method), pro traders (definition), 'Clusters %', 'Dev Migrated N token', 'Dex Paid', 'Dev Sold'. Only the bundle rule (>=4 txs same block) was found.
- Which Axiom docs domain is current (docs.axiom.trade vs docs.axiom.trading)? Both still say 'Migrated to Raydium' although pump.fun migrations go to PumpSwap since 2025-03-20.
- J7 Tracker tweet-card metadata (author handle, follower count, verified status, translation, media/images, quoted tweet, reply context, links, contract-address detection) was not found in any result. Also unknown: which accounts J7 tracks by default and whether users add their own lists.
- J7 identity: is j7tracker.co the same product as j7tracker.io? Does the GitHub 0zgunner/j7tracker 'wallet tracking + voice AI' description belong to the same product? Is the 'hover-based translator on Axiom Pro' J7 or the GenX extension?
- All latency claims are self-reported or third-party and unverified: J7 <200 ms social tracking / sub-1 ms deploys; Axiom wallet tracker 'millisecond delay'; Padre ~300 ms vs Axiom ~500 ms.
- pump.fun fee time series between 2025-09 and 2026-10: when the bonding-curve total became 1.25% (0.30 creator + 0.95 protocol), what changed in Jan 2026, and whether the $-denominated Ascend tiers equal the SOL-denominated tiers in current docs. Intermediate PumpSwap tiers (3,440-98,240 SOL) were not captured.
- Post-migration PumpSwap pool initial price/liquidity (affects whether new pools start in the 0-420 SOL 1.25% tier). Derived terminal curve FDV ~411 SOL needs source confirmation.
- Whether terminals flag Mayhem Mode tokens; how agent trades show up in early volume/holder counts; the Mayhem start year (2025 inferred only from an X post ID).
- DEX Screener Trending inputs: two conflicting descriptions; neither is an official source.
- King of the Hill threshold ($30K / ~45 SOL) comes from third-party guides; current existence and threshold unconfirmed.
- Typical priority-fee / Jito-tip settings of the specific traders studied are unknown; only generic ranges were found.
- Kolscan acquisition (mid/July 2025) and Padre acquisition by Pump.fun: dates and whether UI or data changed after them.
- Many Axiom/Padre/BullX explainer domains look unofficial (affiliate/SEO). Before final use, re-verify claims against official docs or screenshots.
