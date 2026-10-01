# Overnight research summary — 2026-10-01

_Written 17:45 UTC; final test results added 19:25 UTC._

## Short answer

**I have not found a profitable strategy a bot can run.** All six pre-registered tests failed, each one negative at every latency from 0.1 to 10 s:
- four rule-based strategies;
- copying a basket of unknown winners;
- copying Decu.

**Nothing reached the holdout.** The 19:15–21:15 data is untouched and stays available as a clean test period.

The traders themselves do make money:
- **Decu**, trading live on stream, netted about **+89 SOL in 2.5 hours** across all venues: 33 tokens, 29 of 32 closed profitably.
- **Setuh** was up modestly with 1-SOL trades.
- A set of 49 unknown wallets kept making money out of sample (+117 SOL in the H4 test window).

What separates them from the bots is visible in the footage. It is mostly:
- **which** tokens they buy, using narrative checks and tracking of labelled wallets;
- **how long they hold** the few that run: Decu's top 3 tokens gave half the profit, all held through migration.

A rule built from the visible tape does not capture either.

## What was built and recorded

**Live market tape:** every pump.fun bonding-curve trade, creation and migration, decoded from Solana RPC logs. It also includes kolscan's public stream of trades by 570 tracked wallets.
- Coverage: 12:17 UTC onward.
- Size in the train period (12:15–17:15): **905k trades, 15k tokens, 76k wallets**.

**Live stream captures:**
- Decu (Twitch, 720p, 13:38 onward)
- Setuh (Twitch, from 16:15)
- SolanaSwaggy (Kick)
- dvces and d4rkuch1ha (leads)

**Research database:** 26 findings (21 observed, 5 inferred; none stated or validated yet). The Decu decisions are 123:
- 117 on-chain BUY / ADD / SELL decisions;
- 5 on-screen SKIPs;
- one SELL with no on-chain counterpart.

Screen readings come from the stream frames.

**Simulator:** strict point-in-time and fully deterministic, with costs taken from real transactions. Six hypotheses were pre-registered with fixed windows; the holdout plan was written before any validation data existed.

## Identities (primary sources)

| trader | verified | probable |
|---|---|---|
| Decu | X @notdecu, Twitch `decu`, wallet `4vw54BmA…Ud9` (posted by the account; trades on stream) | — |
| Setuh | X @Setuhx, YouTube @setuhh, Telegram, Twitch `setuhh`, **wallet `62N1K57D…tuR`** (HARDCAT buy/sell on stream matches chain; tracker label "setuh"; balance matches), Padre referral | — |
| Cupsey | X @Cupseyy | wallet `2fg5QD1e…6f` (kolscan) |
| Leck | X @LeckSol, YouTube @LeckSol | wallet `98T65wcM…3Mp` (no trades seen today) |
| SolanaSwaggy | Kick channel | wallet `AnrXEnft…DXc` (on-screen "YOU" row matches chain) |

## What the footage and chain show about how they decide

**Decu** (all 720p frames and chain-checked):

1. **Entry timing.** 8 of 9 early entries came just after the token's creator dumped a large launch buy of 3–5.5 SOL at a profit, usually 2–20 s after that sell. Only ~8% of launches look like that.
2. **Selection.**
   - Among 328 tokens matching that pattern, Decu bought 8: the ones with about twice the live activity.
   - Before buying they often read the linked X post: a 7-follower project, a "can you tokenize a ghost" Halloween post, and an "anti-AI narrative" post.
   - They open token pages almost only for tokens they then buy. Screening happens on Axiom's Pulse cards.
   - Their tracker feed follows labelled deployer and KOL wallets.
3. **Sizing.** Fixed Axiom presets (0.025, 0.25, 2, 2.5, 3, 5 SOL), 90% slippage, 0.005 SOL priority fee and 0.01 SOL tip. One measured 3-SOL buy cost 2.84% on top of what reached the curve.
4. **Exits** are where the money is.
   - Non-movers are cut within about a minute, near break-even.
   - The few runners are held through migration and sold on Pump AMM: BTC +25.7 SOL, QRCAT +12.4, "token" +4.3.
   - 14 Raydium Launchpad tokens added +28.3 SOL; pump.fun curve flips added +17.8.
5. **Small 0.025/0.25 SOL buys** are not followed by other buyers. Their purpose is not visible; the "pulls in followers" idea was tested and **not supported**.

**Setuh** trades on Padre Terminal with 1-SOL buys, mostly Raydium Launchpad and Pump AMM tokens. Since 16:15: 7 tokens, net +2.7 SOL on those with sells.

**SolanaSwaggy's** wallet bought the creation second of 4 of 5 launches by one deployer, with a twin wallet. That looks like launch-and-snipe (inferred, 0.6), not discretionary picking.

## Market-wide

- Profit on the curve concentrates in token creators and creation-block buyers. Human-paced wallets lose in aggregate.
- Profitability **persists**: 85 wallets were profitable in both halves of the day, against 55 expected by chance.
- Right after a famous KOL buys, the price jumps ~10–18% within seconds as followers pile in. After unknown consistent winners buy, it does not.

- **After migration** (275 tokens, decoded PumpSwap trades before 19:15), prices are typically **up in the first minutes**: a median +28% at 1 min and +37% at 5 min, and 64% reach 2× within 30 min. By 30 min the median is **−92%**. Holding through migration pays only if you sell into that short window, which is what Decu did with BTC, QRCAT and Ansemmas.

## Hypothesis tests (pre-registered, unchanged parameters)

| | idea | window (UTC) | trades | PnL (SOL) | PF | verdict |
|---|---|---|---|---|---|---|
| H1 | hot token + dev sold + few snipers | 12:15–17:15 | 1,036 | −52.46 | 0.40 | **FAIL** |
| H2 | later, calmer entries | 14:00–17:15 | 124 | −4.92 | 0.42 | **FAIL** |
| H3 | Decu's post-dev-dump timing, 20-s hold | 14:45–17:15 | 487 | −77.07 | 0.20 | **FAIL** |
| H4 | copy 49 unknown consistent winners | 15:20–17:15 | 680 | −37.50 | 0.39 | **FAIL** (the wallets themselves: +117) |
| H5 | H3 entry + Decu-like exits (cut fast, let runners run) | 17:45–19:15 | 250 | −40.64 | 0.28 | **FAIL** |
| H6 | copy Decu's wallet at 1 s | 17:45–19:15 | 7 | −0.98 | 0.35 | **FAIL** (too few trades as well) |

Each failure is written up in `reports/failures/`.

On the full train period (in-sample), copying was positive for 6 of 10 wallets tested, including Decu (+0.92 SOL over 16 trades at 1 s). That is why H6 existed. Out of sample, copying Decu lost.

H5 shows that Decu's exit style does not rescue a mechanical entry: most entries never moved and were cut at a loss. The exits only pay on entries as selective as Decu's own. It contradicts an earlier copy result that was computed with a simulator bug; that inference is now marked *weakened*.

## Things that went wrong and were fixed (all in git history)

- **Non-deterministic simulator.** The slot clock sampled random rows, and 22 mis-decoded events could enter the sample, so identical data gave 0, 127 or 217 trades. The fix: a deterministic local clock, and those rows moved to quarantine. Earlier copy results were re-run.
- **Evidence frames off by 0.25 s.** Frames were registered from a segment cut that runs 0.25 s off from the file I read. They were re-registered and their values re-read.
- **H3's registration time reset.** A script re-run reset it; it was restored from git. Hypotheses now keep their id and time across re-runs, and a changed definition is refused.
- **Over-broad deletion.** A cleanup query removed Decu's segment-1 evidence; it was rebuilt from code. `check-findings` now flags hypotheses whose basis is missing.

## Data limits

- **Coverage:**
  - Market tape: 12:17:18 to ~21:26 UTC, 1.76M bonding-curve trades, plus decoded PumpSwap.
  - Decu footage: 13:38:37–16:11:39 (720p from 14:11:39), then 16:15:19–21:20:35.
  - Setuh: 16:15:22–18:06.
  - SolanaSwaggy: 12:25–14:50.
  - d4rkuch1ha: 16:37–18:19.
  - dvces footage (unidentified, 480p) was deleted at 20:35 to free disk.
  - The Decu capture was stopped at 21:20:35 because no disk guard was running.
- **Tape gaps over 5 s:**
  - 12:34:03–12:41:36 (7.5 min, early recorder);
  - 15 short gaps of 6–43 s from reconnects and restarts: 14:38:35–14:38:59, 15:43:29–15:43:39, 15:59:54–16:00:04, 16:32:23–16:32:33, 16:35:58–16:36:17, 16:42:46–16:42:56, 17:03:56–17:04:07, 18:15:50–18:16:00, 18:35:04–18:35:31, 19:12:24–19:12:34, 20:00:11–20:00:21, 20:34:18–20:35:01, 20:53:27–20:53:34, 20:57:47–20:57:53, 21:09:43–21:09:49;
  - Decu video 16:11:39–16:15:19.
- **Stream watcher:** it ran out at 18:35 and was not restarted (the background-job limit). Streams starting after that were not detected.
- **Missed trades:** the tape misses ~4% of curve trades (websocket drops). Pump tokens quoted in another token instead of SOL are excluded by design.
- **kolscan's per-wallet coverage has gaps.** It relayed none of Decu's 41 curve trades between 18:00 and 19:00. For the 13:38–16:11 session it matched the tape, so the +89 SOL figure stands. Later figures that rely on kolscan would undercount.
- **PumpSwap (AMM) trades are now decoded** from the raw logs (~19:30 UTC): 348 pools and 2.2M swaps. The layout was verified against Decu's QRCAT sale, whose amounts match kolscan exactly. 315 of 334 migrations have their pool decoded; 19 lost the pool-creation event. On curve plus AMM, Decu's day on pump tokens up to 19:15 is **+86.9 SOL** over 35 tokens (23 winners), with positions still open counted at cost. That includes AMM exits kolscan never relayed, such as Ansemmas, +33.6 SOL net. **Raydium Launchpad** trades (Setuh's main venue) are still not decoded. The simulator does not use the AMM data yet, so H5 had to exit on the curve, near migration.
- **Small samples.** Decu's picks are dozens, not hundreds. Every finding states its n.


## Follow-up (after the overnight run)

- **Decu's picks hold up on a bigger sample.** Over 13:38–19:15 there were 1,244 creator-dump candidates, and Decu bought 19. A simulated bot entering on Decu's picks makes +0.28 SOL per 1-SOL trade, winning 60%. On the rest it makes -0.16, winning 12%. The picks are profitable both before 17:00 (+2.15 SOL) and after (+1.99).
- **No model of their choice works.** A model of that choice built from 22 tape and metadata features was trained before 17:00 and tested after. It does no better than chance (AUC 0.524), and its top picks lose. Decu selects on something these features do not contain: what they read in the linked X post and in their labelled-wallet tracker. Capturing that needs text and narrative features, plus more footage-coded decisions.
- **Buying every migration doesn't pay.** Buying each migrated token on PumpSwap 3 s after its first swap and selling 60 s later has a median of about −2% after fees. The positive average comes from a single 60× token; without it the average is about zero, before the buyer's own price impact.
- **Data history fix.** Re-running the choice-set study had deleted the finding H6 was registered on. It was restored from git and marked *superseded*. Rebuilt findings that a hypothesis rests on are now superseded instead of deleted, and `check-findings` flags any hypothesis whose basis is missing.

## What I would do next

1. **Use the decoded PumpSwap data in the simulator**, so exits after migration can be simulated, and **decode Raydium Launchpad**. Most of Decu's profit comes from migration exits and Launchpad tokens, and most of Setuh's trading is on Launchpad.
2. **Model the selection, not the timing.** Decu's picks win where the mechanical candidates lose (p≈0.006). The visible inputs are:
   - the linked X post: its author, follower count and narrative;
   - the labelled wallets in their tracker;
   - copycat waves of the same name.

   These can be measured: metadata URIs and fxtwitter are both reachable. The next hypothesis should be a *selection* model trained on more of Decu's decisions, with its own frozen holdout.
3. **Collect more footage-coded decisions.** Decu streams daily. Each session adds dozens of BUY/SKIP decisions with screen readings.

## Needed from you

1. **YouTube cookies** to get Setuh's and Leck's videos (bot wall from cloud IPs).
2. **An on-chain history API key** (e.g. Helius) for full wallet histories and AMM trades.
3. Optional: a **J7 Tracker** JWT.
4. **Persistent storage** if the recordings should outlive this container (~3 GB/h).
5. **Out of scope:** launching tokens and selling into buyers. That is where curve profits concentrate, and I will not build it.
