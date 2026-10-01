# Research plan and status

_Last updated 2026-10-01 ~16:00 UTC. Status lines summarise the database; details and
sources are in `research/traders/<slug>/identity.md`, `research/observations/` and
`sources/source_ledger.csv`. Overnight results: `reports/simulations/`._

## Where things stand

The network has been opened, so primary sources are now in use:
- X profiles and posts through the fxtwitter mirror.
- A live Solana RPC feed of every pump.fun bonding-curve trade, recorded since 12:17 UTC.
- kolscan's public KOL stream.
- Live Twitch and Kick captures.

The database holds 21 findings: 16 observed and 5 inferred. None are stated or validated yet.

| trader | identity (status) | evidence so far |
|---|---|---|
| Decu | X @notdecu, Twitch `decu`, wallet `4vw54BmA…Ud9` (all **verified**: the account posted the wallet) | Live stream recorded 13:38 onward, 48 on-chain trades coded against footage, 5 on-screen SKIPs, BUY-vs-SKIP choice set |
| Cupsey | X @Cupseyy (verified); wallet `2fg5QD1e…rx6f` (probable, kolscan) | Not live on stream so far; wallet tracked in the tape |
| Setuh | X @Setuhx, YouTube @setuhh, Telegram SetuhTrades (verified); wallet `62N1K57D…tuR` (probable, kolscan "set") | Wallet tracked in the tape |
| Leck | X @LeckSol, YouTube @LeckSol (verified); wallet `98T65wcM…w3Mp` (probable) | Wallet tracked in the tape |
| SolanaSwaggy (found while recording) | Kick channel (verified); wallet `AnrXEnft…bDc` (probable: on-screen "YOU" row matches chain) | Wallet bought the creation second of 4/5 launches by one deployer |

Rejected look-alikes: @decurionz and @DecuTV.

Simulation results so far (details in `reports/simulations/`):
- Copying tracked KOLs is negative at every latency.
- H1 (hot new token, dev sold, few snipers) and H3 (Decu's post-dev-dump timing) are negative in development and in-sample runs.
- H4 (copy unknown consistent winners) loses even in-sample.
- The formal first tests of H1–H4 run after the train period ends at 17:15 UTC.

## The highest-value data design

For Cupsey and Decu the leads point to **both a public wallet and long stream
recordings**. If verified, aligning the two gives, for each trade:

- exact entry/exit times, mint, size and fill price (on-chain), and
- what was on screen in the seconds before (frames), what they said (audio),
  and which tokens they looked at and skipped (frames).

Procedure: anchor VOD time to wall-clock time (`videos.live_start_at`, checked
against an on-screen clock or a known transaction), list the wallet's swaps
during the stream, and create decisions with `wallclock_basis = onchain_tx`.
Then extract decision windows at those moments. Token identity comes from the
mint rather than from reading a ticker off a blurry frame.

Twitch typically deletes past broadcasts after 7–60 days depending on the
account type (check per channel), so capturing recent VODs is time-sensitive
once access exists.

## Phases

1. **Verify identities** from primary sources: the trader's own profiles and
   links (Linktree, Twitch About panel, X bio, a post claiming a wallet). Mark
   lookalikes `rejected`.
2. **Capture sources**: VODs/videos + captions, or audio for transcription;
   profile pages; the trader's own strategy statements.
3. **Code decisions** per trader: BUY, SKIP, SELL... with metric readings from
   frames before each decision, separating said/screen/action. Aim for dozens,
   then hundreds, of decisions per trader, including losses and skips.
4. **Per-trader models** as findings per funnel stage (discovery → exit), each
   typed stated/observed/inferred.
5. **Measurable features + historical market data** (trade-level swap history
   for the relevant tokens), then simulation under the split/holdout rules.

## Access status (updated 2026-10-01 ~16:00 UTC)

The network is open. What still limits the work:

| need | status |
|---|---|
| YouTube videos and captions | Metadata works. Media and captions get a bot wall (403/429 from cloud IPs) and need browser cookies (`--cookies`). |
| Twitch/Kick past broadcasts | The seed channels list no VODs, so live capture (`scripts/stream_watcher.py`) is the only footage. |
| J7 Tracker | The public docs work. The API needs an account JWT, which was not provided. Tokens it deploys are visible on chain by their `metadata.j7tracker.io` metadata. |
| kolscan account API | Returns 403. Only the public SSE stream is used; the block was not worked around. |
| Wallet history from public RPC | `getSignaturesForAddress` for famous wallets is flooded with spam transactions. The live tape replaces it. |
| PumpSwap / Raydium (post-migration) trades | Recorded raw but not decoded. Exits after migration are missing from curve-only PnL. |

## Decisions needed from the project owner

1. **Cookies** for YouTube (Setuh's and Leck's videos), stored as an environment secret.
2. **J7 Tracker JWT**, if J7's feed/API should be used (optional: its deploys are already visible on chain).
3. **On-chain history provider** (e.g. Helius) for full wallet histories, including AMM trades. Needs an API key as an environment secret.
4. **Media storage**: recordings live only in this container, about 3 GB/h while streams are live, and are not committed.
5. **Creator/launch strategies**: profits on the curve concentrate in token creators who dump on buyers. I am not building or testing launch-and-dump strategies.
