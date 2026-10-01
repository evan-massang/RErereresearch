# Solo trader signals: J7 Tracker, Axiom and similar terminals (web research leads)

Retrieved 2026-10-01. Every item below is a **lead (`document` modality)**, not a trader statement.
Evidence labels:
- **[DOC]**: the vendor's official docs or the vendor's own shipped app code.
- **[VENDOR-CLAIM]**: a vendor's marketing claim. Not verified.
- **[3P]**: a third-party guide or blog. Usually affiliate or SEO content, so treat it as a weak lead.
- **[COMMUNITY]**: a trader or community opinion.
- **[STUDY]**: research with a stated method.

No trader's own X post could be read (see "Not accessed").

---

## 1. J7 Tracker (j7tracker.io, docs.j7tracker.io)

**What the product is.** J7 is a fast X/social feed combined with a token **deployer**. Its users are largely people who launch ("vamp") tokens off tweets. It is not mainly a screener for new pump.fun launches.
- Site meta description and keywords: "crypto, token deployer, solana, bnb, pump.fun, twitter tracker". [DOC] https://j7tracker.io
- Firefox add-on text: "J7 All-In-One Extension. VAMP coins, auto-search tokens, directly from any of your favorite trading terminals." It requests host access to axiom.trade. [DOC] https://addons.mozilla.org/en-US/firefox/addon/j7-tracker/
- Warning: github.com/0zgunner/j7tracker is an unrelated community project and is **not** J7. Its README says X monitoring was not built. https://github.com/0zgunner/j7tracker

**Docs map.** https://docs.j7tracker.io/llms.txt has these sections:
- Deploy & Trade API: deploy, platforms, bundles & snipers, pair registries, sell, buy, bundle.
- Feed: connect, events, data types, manage accounts, errors & limits.

The docs have **no "filters" page and no new-launch feed**. Keyword filters appear only in the web app, covered below.

### Feed (tweets and socials)
Sources: https://docs.j7tracker.io/docs/feed, https://docs.j7tracker.io/docs/feed-events, https://docs.j7tracker.io/docs/data-types [DOC]

- **Transport.** Socket.IO v4 on nyc.j7tracker.io or dfw.j7tracker.io. The client emits `user_connected` with a JWT and first receives `initialTweets`, a backlog of up to 100 items.
- **Coverage.** The feed carries:
  - posts from J7's shared "main feed" accounts and the user's custom accounts;
  - Truth Social, Instagram, TikTok, YouTube and Binance Square, all delivered as `external_message`;
  - J7 webhook cards for new pump, stonk and pons pairs.
- **Delivery model.** J7 ingests X from several providers. The first copy to arrive is sent as `tweet`; later, richer copies (media, quote, article, translation) arrive as `tweet_update`. The `provider` field (`p_v0`, `p_v1`, ...) names the ingest path, and "Faster paths can carry less data". This explains why J7 users see text before media.
- **Account events.** These are part of the tweet-tracking product:
  - `tweet_deleted` (includes J7's cached copy);
  - `following_update` and `unfollowing_update`;
  - `affiliated_update`;
  - `profile_update` (with `modifications`: name, description, avatar, banner, location, url, plus a privated flag);
  - pinned and unpinned posts;
  - suspended and deactivated.
- **`follow_scan`.** When a watched account follows someone, J7 sends that followed account's latest posted contract address (`ca`, `chain`, `tweetId`, `tweetTime`, `content`).
- **`token_meta`.** Token info for a contract address found in any received item, up to 5 per item. Fields: `mint`, `symbol`, `name`, `image`, `marketCapUsd`, `marketCapSol`, `market` (e.g. `pumpfun`), `at`.
- **Fields per tweet (`Tweet`).**
  - Identity and content: `id`, `createdAt`, `type` (TWEET/REPLY/QUOTE/RETWEET), `text` (t.co links expanded), `translation`, `components`.
  - Thread structure: `isRetweet`, `isQuote`, `isReply`, `isSelfReply`, `replyTo`, `quotedTweet` (nested up to 3 levels), `originalAuthor`, `retweetedQuote`, `repliedQuote`, `retweetedReplyTo`.
  - Media and attachments: `media`, `originalMedia`, `card`, `article`, `grok` (Grok chat), `poll`.
  - Engagement and links: `metrics` (likes, quotes, replies, retweets, views), `tweetUrl`, `provider`, `isCustomAccount`.
  - On `p_v1` only, when the upstream detects one: `contractAddress`, `chain`, `contractAddressLabel`, `preferredTradingUrl`, `extraContractAddresses`.
- **Author fields.** `id`, `handle`, `name`, `avatar`, `verified`, `badge`, `parody`, `followersCount`, `bio`, `location`, `banner`, `website`, `verifiedType`, `affiliateDescription` / `affiliateBadgeUrl` / `affiliateUrl` / `affiliateLabelType`.
- **Account tracking economics.** Source: https://docs.j7tracker.io/docs/accounts [DOC]
  - The "main feed" is the set of accounts J7 tracks for everyone.
  - A "custom" account costs a slot and J7 starts tracking it.
  - An "available" account is one another user already pays for. It is free to add and stays in the pool while anyone pays.
  - Slots come from deploys: 15+ deploys = 1 slot, 50+ = 2, 100+ = 3. Adding a custom account needs at least 15 deploys.
  - Example handles in the docs: `frankdegods`, `ansem`, `cobie`.
  - The main-feed list itself is behind a JWT (`GET /api/watched-accounts`), so the handles J7 tracks were **not** retrievable.
- **Limits.** Source: https://docs.j7tracker.io/docs/errors [DOC]
  - 5 sockets per user.
  - 15 client messages per second.
  - Watched-accounts reads: 30 per 10 s.
  - Account writes: 20 per 10 s, at most 3 in flight.
  - Error codes include `no_deploys`, `limit_reached` and `tracking_failed_quota`.

### Keyword / word filters (web app)
Source: UI strings in the shipped bundle, https://j7tracker.io/static/js/main.2b264e11.js, fetched 2026-10-01. [DOC, vendor code]

These are filters on **tweets and profile fields, not on new launches**.
- **"Keyword Highlights" / `memeWords`.** These "Light up words from your keyword list in tweets." Each word has a colour and a sound. The default list is **empty**: users build their own. Words can be imported and exported as JSON, and the app counts "N keywords".
- **Match mode `exact` vs `contains`.** In-app example: "ass" will NOT match "assassinate" in exact mode but will in contains mode.
- **Other highlight features.** Ticker highlight, quote highlight, "AI predicted name" highlight, pinned keywords ("PINNED KEYWORD"), and "Pin matching tweets to the top of the feed".
- **Snipers (auto-actions).**
  - **Keyword Sniper:** "Fires when your keyword (case-insensitive substring) shows up in tweet bodies and/or selected profile fields."
  - **CA Sniper:** sources are tweet kinds, follows and profile updates.
  - **Interaction Sniper:** fires when a watched account replies to, quotes, retweets or follows a target.
  - **Profile Change Sniper:** "mint a token using the watched account's CURRENT display name + derived ticker". It can also fire on a profile-picture match via `avatar_phash`.
  - The bundle summarises these as: "Buy on tweet interactions, snipe specific tokens on keyword tweets, auto-buy the moment one handle follows another, plus profile-update triggers".
- **Vamp and deploy UX.**
  - "Paste a tweet URL or id to vamp".
  - AI name and ticker suggestions plus image suggestions per tweet card. Clicking an image card "deploys the first suggestion's name and ticker with that image".
  - "Auto ticker from name" and "Use first word for ticker".
  - The extension can "Vamp coins directly on Axiom, Padre, and GMGN with auto-filled token details".
- **Other trackers in the app.**
  - pump.fun callers: "Pump.fun username, wallet, or profile URL to track callouts".
  - Fomo users: "theses and trades".
  - pump.fun news: "Every news article pump.fun publishes on a trending coin".
  - Discord webhook and sound alerts.
- **Hard-coded `pumpFunWhitelist`.** Contains `a1lon9`, `Pumpfun`, `elonmaah`, `okpasquale`, `kevinafischer`. Its purpose is not stated in the bundle.

**What could not be confirmed for J7:**
- Any filter on new pump.fun launches.
- Any dev/deployer tracking feature.
- Migration alerts, apart from the `follow_scan` contract-address lookup and the trackers above.

### Deploy tool
Sources: https://docs.j7tracker.io/docs/deploy, https://docs.j7tracker.io/docs/bundles, https://docs.j7tracker.io/docs/platforms [DOC]

- **Request.** `POST {base}/submit` with `type: create_token`. Regions are tx-nyc, tx-lax, tx-fra and tx-sgp.
- **Fields.** `name`, `ticker`, `buy_amount` (dev buy), `image_url` (or a server-generated `image_type` letter/ascii), `twitter`/`website`/`telegram`, `vanity_mint_keypair`, and `multi_deploy` (1–10 mints per call).
- **Description.** The default is "Deployed using j7tracker.io" unless `private_desc` is set. This is a possible fingerprint for J7-deployed coins.
- **Same-block bundles.** `bundle_wallets` (`key:sol`), up to 9 wallets on a SOL quote.
- **Delayed snipers.** `sniper_wallets` (`key:sol:delay_ms`), NA East only.
- **Auto-sell.** `auto_sell_wallets` (`key:percent:delay_ms`).
- **Platforms.**
  - Solana: pump (SOL/USDC/stock quotes, fee sharing, mayhem), bonk, stonk, bags, ansem, OTC and "Paid" variants.
  - EVM: four.meme, flap, pons, clanker and others.
- **Research relevance.** The documented tooling builds bundled and sniped launches, so bundle and sniper share on a coin may be the deployer's own wallets.

---

## 2. Axiom (axiom.trade, docs.axiom.trade)

- **Pulse.** Three columns: New Pairs, Final Stretch, and Migrated (the docs still say "Raydium"). Lightning-bolt quick buy. [DOC] https://docs.axiom.trade/axiom/finding-tokens/pulse
- **Documented Pulse filters.**
  - Age.
  - Top 10 Holders %, Dev Holding %, Snipers %, Insiders % ("private sales, team members"), Bundle %.
  - Holders, Pro Traders ("Indicates traders using other platforms").
  - Liquidity, Volume, Market Cap, Txns, Num Buys, Num Sells.
- **Explore page.** Adds "Dex Paid" and a "Search" filter "for sniping specific tickers". It warns "Beware of wash trading". [DOC] https://docs.axiom.trade/axiom/finding-tokens/explore-tokens
- **Bundle Checker definition.** Source: https://docs.axiom.trade/faqs.md [DOC]
  - Rule 1: 4 or more transactions in the same block are flagged.
  - Rule 2: a wallet whose next transaction is not part of a bundle is dropped.
  - There is no time limit, unlike pump.fun's early-block flag. "A bundle does not necessarily have to be from the deployer or team."
- **Tweet Monitor.** "scans key crypto-related Twitter accounts in real time" and adds a "Custom Twitter Tracker" for your own handles. It needs 5 SOL of trading volume. The tracked account list is not published. [DOC] https://docs.axiom.trade/tweet-monitor.md
- **Twitter Preview Popup.** "Many of Solana's Memecoins are based from ... 'narratives'. These Narratives are based on tweets". It works on tweet links, not handles. [DOC] https://docs.axiom.trade/twitter-preview-popup.md
- **Wallet tracker.** Shows tracked-wallet buys on charts and while viewing Pulse, and imports wallets from BullX. [DOC] https://docs.axiom.trade/wallet-tracking/adding-wallets.md, https://docs.axiom.trade/wallet-tracking/monitor-wallets.md
- **Trader Scan.** Per-wallet bought, sold, balance, realised PnL and hold time on any token. [DOC] https://docs.axiom.trade/trader-scan.md
- **Migration sniper buy/sell.** [DOC] https://docs.axiom.trade/axiom/swap/migration-actions.md
- **Pulse "Display → Customize Rows" toggles.** Source: [3P] https://memecoinnavigator.com/how-to-change-theme-and-display-information-in-axiom-trade/
  - Image Reuse ("how many different coins were created using the same image").
  - Market Cap, Volume, Fees ("helps detect artificial trading"), TX, Socials, Holders, Pro Traders.
  - **KOLs**, **Dev Migration**, **Dev Creations**, **Tracked Dev**, Founding Time ("when the dev wallet was created").
  - Snipers, Insider, Bundler, Tax, Dex Paid.
  - Axiom's own docs do not document these toggles, and the app is behind Cloudflare, so they are unverified.
- **Developer tracking.** A dev wallet is labelled "DA". Users add it under Trackers → Wallet Manager and turn on "Tracked Dev". [3P] https://memecoinnavigator.com/how-to-track-and-search-developers-on-axiom/
- **Viewer / "watching" count.** **Not found** in any source I could reach.
- **Speed.** No official latency figures. "a couple seconds faster than Bullx and Photon" appears only in [3P/VENDOR-CLAIM] search snippets from https://axiompro.app/pump-fun/ and Medium guides. Treat it as unverified.
- **Comparable schema.** Mobula's "Axiom-style" Pulse API is a third-party API, not Axiom's, but it shows the usual per-token field set. Source: [DOC, Mobula] https://docs.mobula.io/indexing-stream/stream/websocket/pulse-stream-v2, https://docs.mobula.io/cookbooks/axiom-data-api
  - `deployer`, `deployerMigrationsCount`, `holdersCount`.
  - `top10HoldingsPercentage`, `devHoldingsPercentage`, `insidersHoldingsPercentage`, `bundlersHoldingsPercentage`, `snipersHoldingsPercentage`, `proTradersHoldingsPercentage`, `freshTradersHoldingsPercentage`, `smartTradersHoldingsPercentage`.
  - Counts and buys per category.
  - `twitterReusesCount`, `twitterRenameCount`, `twitterRenameHistory`.
  - `dexscreenerListed` / `dexscreenerAdPaid`.
  - `isOGCoin`: false when an earlier coin with the same name exists on the chain, i.e. a copycat.
  - `bondingPercentage`, `bonded_at`, `migrated_at`.

## 2b. Similar terminals

- **GMGN.** Source: official repo, https://github.com/GMGNAI/gmgn-skills/blob/main/skills/gmgn-market/SKILL.md [DOC]
  - Trenches filters and fields:
    - creator stats: `creator_created_count`, `creator_created_open_count` ("Creator's graduated token count"), `creator_created_open_ratio`, `creator_balance_rate`, `creator_token_status`;
    - wallet categories: `smart_degen_count`, `renowned_count` (KOL);
    - risk: `bundler_trader_amount_rate`, `rat_trader_amount_rate` (insider), `is_wash_trading`, `rug_ratio` (">0.3 high-risk");
    - socials: `x_user_follower`, `twitter_rename_count`, `tg_call_count`.
  - Wallet tags: `smart_degen`, `renowned`, `sniper`, `bundler`, `rat_trader`. Source: https://github.com/GMGNAI/gmgn-skills
- **Padre / Terminal.** pump.fun acquired it and it now runs at terminal.pump.fun.
  - The docs at docs.padre.gg redirect to the app and could not be read.
  - Search snippets of those docs mention:
    - Trenches columns New / Almost Bonded / Recently Bonded;
    - filters for "Dev still holding", "Dev bonded", Symbol and Has social;
    - tracking dev wallets and highlighting them "in any color".
  - Labelled [DOC-via-snippet, unverified]. https://docs.padre.gg/app-guide/trenches
- **Trojan Terminal Trenches.** [DOC] https://docs.trojan.com/terminal-overview/meme-coin-trenches
  - Dev migrated count shown as "Migrated", "Migrated/Launched" or "Migrated %".
  - Holder-category filters, "X Search for Contract Address", and a blacklist with import/export.
- **Photon Memescope.** Custom filtered feeds of new tokens, per Photon's launch post on X (not readable). Later updates reportedly added "successful migrations by dev" and a "DO NOT SHOW" symbol/name blacklist. [DOC-via-snippet] https://x.com/tradewithPhoton/status/1805692173586735464, https://x.com/tradewithPhoton/status/1869443145030947036
- **BullX Neo Vision.** Token age, top 10 %, deployer %, comments, 5-minute volume and price, holders, "holders using trading bots", socials, and reverse image search. [DOC] https://bullx.gitbook.io/bullx-neo-docs/finding-tokens/neo-vision
  - A later update added "See reused Twitter Accounts" and migration snipe. [COMMUNITY, @ohbrox] https://x.com/ohbrox/status/1886541812765987111

---

## 3. What traders say they look for (community; weak evidence)

- **Good devs and dev migrations.** All the major terminals expose a dev migrated or graduated count (Axiom, GMGN, Trojan, Photon above), which shows traders want it.
  - [3P] says "Dev Migrations" is "completely useless for new pairs".
  - [3P] warns of devs who "farm copy traders" by heavy bundling and who "wait for migration to sell from bundles" or "farm the coin at 10k MC". It names "the dev of Fart Coin" as accused of this on X.
  - Sources: https://memecoinnavigator.com/best-axiom-trade-filters-for-new-pairs/, https://memecoinnavigator.com/how-to-track-and-search-developers-on-axiom/
  - **No public list of good-dev wallets from a primary source was found.** Paid lists exist, e.g. walletmaster.tools and gumroad lists, but none were assessed.
- **Vamps (copycats).**
  - The slang definition, "clone or replicate an existing token", comes from an X post seen only as a search snippet. [COMMUNITY] https://x.com/AppleNvidia/status/1966591726438805759
  - Tools that both enable and detect vamps:
    - J7's vamp button (above);
    - Axiom's "Image Reuse";
    - Mobula's `isOGCoin`;
    - Twitter-reuse counts on BullX, GMGN and Mobula.
  - Traders appear to see the first or OG coin for a meme as the one worth trading. The study below supports this.
- **Narratives.** Axiom's own docs say coins are narrative- and tweet-driven (see the Twitter Preview Popup above).
  - The arXiv study (§4) sorts the most profitable source posts into **Culture, News and Animal**. This follows Long, Wong & Cai, "Bridging culture and finance: a multimodal analysis of memecoins", WWW Companion 2025.
  - Popular-press example: PENGUIN went from under $20M to about $170M in roughly one day, and new pump.fun launches hit about 45k on 2026-01-27. [3P] https://coinmarketcap.com/academy/article/meme-coin-news-meme-coin-volumes-hit-2026-high-as-penguin-meme-sparks-breakout-and-more
- **Which X accounts move coins.** The best evidence is Table 10 of arXiv 2609.10246 [STUDY]: 31 posts each produced at least $1M of "extractable value". Not all of the handles are famous.
  - Culture / AI-agent accounts: truth_terminal ($113.6M EV, 245K followers), repligate, AndyAyrey, lumpenspace, MycelialOracle, whyarethis, fabianstelzer, somewheresy, Darkfarms1, 0xracist, quadcarl_carl, shawmakesmagic, DavidSacks, greg16676935420.
  - Animal / pet: tong0x (10.9K followers), CatholicTV, KevinAFischer, aiwdaddyissues, tonyplasencia3, elonmusk (only $1.26M EV despite 239M followers).
  - News: GoFundMemes, STACCoverflow, bitcoinmagazine, alt_layer, Free_Ross, biznez_, d33v33d0, nigwardio (1.5K followers).
  - Inaccessible at the time of the study: john, megs_io, TheMisterFrog, shawmakesmagic.
  - Median follower count was 42.6K, ranging from 5K to 240M. 20 of 27 posts had a picture or video.
- **Public influencer list.** Vendor content, not evidence that these accounts move price. [3P, Bonkbot, 2025-02-24] https://bonkbot.io/library/crypto-memecoin-twitter-influencers
  - Handles: A1lon9, aeyakovenko, blknoiz06, frankdegods, Orangie, Cryptozins, DegenerateNews, 973Meech, 0xVonGogh, CryptoWendyO, lmrankhan, Kmoney_69, TheCryptoLark, MattWallace888, GuruMemeCoin, NotChaseColeman, Rasmr_eth, Renzofks, theunipcs, ValueandTime.
- **J7's built-in handles.** J7's code hard-codes pump.fun-affiliated handles (a1lon9, Pumpfun, okpasquale, kevinafischer, elonmaah). Its docs use frankdegods, ansem and cobie as examples. [DOC, vendor code/docs]

## 4. Measured effectiveness and pitfalls

- **[STUDY] Szwajcok, Tsuchiya, Liu, Soska, Payer, Christin, "Meme Coin Factories: Uncovering Large-Scale Manipulations on pump.fun".** arXiv 2609.10246. https://arxiv.org/html/2609.10246v1
  - Data: all 15.2M coins from Jan 2024 to Jan 2026, plus a 1% transaction sample and a 5-day sample.
  - Post-driven launches: 23.5% of coins (3.57M) were created after Twitter or Truth Social posts. 83.4% of post-based extractable value came from the top 31 posts.
  - Wash trading is about 17% of volume, conservatively. It covers 8.26% of coins, and 50.31% of trading in coins with more than 10k transactions. Graduation odds rise about 19% per doubling of wash trades. **Migrations can therefore be manufactured.**
  - Creator obfuscation: the top 1% of creator clusters made 58.57% of coins. The largest cluster had 10,531 addresses. This means "dev created/migrated" counts per wallet understate operators.
  - Coordinated atomic dumps: 4,402, with a median of 7 senders.
  - Copycats: 10% of coins under strict matching, 36% under loose matching. **Originals graduate at 9.20% versus 0.86% for copycats.**
  - Market-manipulation-as-a-service: 4 sites and 14 GitHub repos offering comment bots, wallet farms and token copying.
- **[STUDY] Ding, Lin, Luo, Xu (2025), "Decompose market manipulation strategies: evidence from on-chain meme coin market".** About 6k coins around the TRUMP launch. Cited by the paper above; not read.
- **[VENDOR-REPORT] Solidus Labs.** 98.6% of pump.fun tokens are rug pulls or pump-and-dumps. Of more than 7M tokens with at least 5 trades (Jan 2024 – Mar 2025), only about 97k kept more than $1k liquidity. https://www.soliduslabs.com/reports/solana-rug-pulls-pump-dumps-crypto-compliance (via https://cryptopotato.com/98-of-tokens-on-pump-fun-are-rug-pulls-or-fraud-report/)
- **[VENDOR-CLAIM] MadeOnSol, KOL wallets.** No independent verification. https://coinstats.app/news/07f38ebd47e8d820af3eb96b00c42a84b9b856c602626e3e4a71afbbd79014d6_KOL-Wallet-Tracking-on-Solana-What-the-Data-Actually-Shows-After-16-Million-Trades/
  - Coverage: 1,058 KOL wallets and 1.6M trades.
  - Median KOL win rate 57.1%.
  - 9,404 "cluster" co-buy events.
  - Only 34 of 10.6k indexed deployers are "elite", with 71% graduation against 1–2% overall.
- **[3P, unverified Arkham figures via Medium].** Serial deployers, e.g. one address with about 29.8k tokens. Do not cite without the primary source. https://medium.com/@abubakarabdulfattah120/serial-rug-deployers-on-pump-fun-a-deep-dive-into-solanas-meme-coin-laundromat-a57ddda190cc
- **Pitfalls stated by the tools themselves [DOC].**
  - Axiom: "Beware of wash trading". Its bundle detection has "false positives or missed bundles".
  - GMGN ships an `is_wash_trading` flag.
  - J7's deploy API builds same-block bundles and delayed snipers. Bundle and sniper share can therefore be the dev's own wallets, and holder counts can be farmed.

## Not accessed / gaps

- **x.com.** Returns HTTP 402. No trader post was read verbatim, and every X item above comes from search snippets only.
- **axiom.trade app.** Behind a Cloudflare challenge. I could not verify the Pulse card icons, a viewer or "watching" count, KOL-buy display, or the X preview contents beyond the docs.
- **docs.padre.gg.** Redirects to the app (302).
- **trenchreview.medium.com.** Returns 403.
- **GitHub tracker repos.** markliu22/MemeCoinAnnouncer and huztfq/memecoin_tracker are not enabled for gh in this session.
- **J7 internals.** The main-feed and Axiom Tweet Monitor account lists are behind auth. The J7 Discord was not accessed.
- **Not found anywhere.**
  - A J7 filter on new pump.fun launches.
  - J7 dev or migration alerts.
  - Any primary-source public list of "good dev" wallets.
  - Any independent latency benchmark comparing J7, Axiom and the other terminals.
