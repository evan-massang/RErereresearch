# Research plan and status

_Last updated 2026-10-01. Status lines summarise the database; details and
sources are in `research/traders/<slug>/identity.md` and `sources/source_ledger.csv`._

## Where things stand

**No research findings exist yet.** The only outside evidence gathered so far
comes from web-search results (titles, URLs and model-written summaries)
because this container's network policy blocks direct access to YouTube,
Twitch, X, Hugging Face and every Solana data source (see "Blocked" below).
Everything below is a **lead**, not an established fact.

| trader | strongest identity leads (status) | session-type content found | notes |
|---|---|---|---|
| Cupsey | wallets `2fg5QD1e…rx6f`, `suqh5sHt…CHQfK` (probable); X @Cupseyy, Twitch `cupseyy` (lead) | Twitch VOD list + stream archives (titles mention Axiom/Flippr/filters); podcasts/interviews | A $CUPSEY mascot token and its X accounts share the name; win-rate/trade-count claims conflict across sites |
| Decu | X @notdecu + wallet `4vw54BmA…Ud9` posted by that account (probable); Twitch `decu` (lead) | Twitch VODs (e.g. a 331-minute trading stream, 2026-07-08, per a tracker summary) | `decu0x` influencer profile and two DECU tokens are probably unrelated |
| Setuh | YouTube @setuhh (probable); X @Setuhx, linktr.ee/setuh, Twitch `setuhh` (lead) | 1 live trading video tied to the channel; 4–5 more "(LIVE)" videos not yet tied to it | Twitch bio "realest gambler" may mean casino streams; name often autocorrected to "setup" |
| Leck | YouTube @LeckSol (probable); X @LeckSol, wallet `98T65wcM…w3Mp` (lead) | one "scalping" video; no long sessions or VODs found | the "long recorded sessions" premise is unsupported so far; @LeekSol is a different (token) account |

Tool mentions (Axiom, Flippr, Padre, pump.fun app, BullX) come from stream
titles and referral links. A referral link is not evidence of use; frames are.

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

## Blocked by network policy (as of 2026-10-01)

Verified with `python -m pipeline check-network` and live attempts; the
proxy denied every one (`403` on CONNECT):

| need | hosts to allow |
|---|---|
| YouTube metadata, captions, media | `youtube.com`, `*.youtube.com`, `*.googlevideo.com`, `*.ytimg.com`, `youtubei.googleapis.com` |
| Twitch VODs | `twitch.tv`, `*.twitch.tv`, `*.ttvnw.net`, `*.jtvnw.net`, `*.cloudfront.net` (VOD segments) |
| Kick VODs (other traders) | `kick.com`, `*.kick.com`, `*.live-video.net` |
| Whisper models for transcription | `huggingface.co`, `*.huggingface.co`, `*.hf.co` |
| Profiles and pages to verify identities | `linktr.ee`, `x.com`, `twitter.com`, `kolscan.io`, `gmgn.ai`, `kolexplorer.com`, `orbmarkets.io`, `solscan.io`, plus arbitrary article sites |
| Solana market/on-chain history | e.g. `api.mainnet-beta.solana.com` (rate-limited), Helius, Birdeye, DexScreener, GeckoTerminal, Dune (several need API keys) |

Because sources are open-ended, broad ("full") network access for this
environment is simpler than an allowlist. Allowed today: package registries
(PyPI etc.) and GitHub.

## Decisions needed from the project owner

1. **Network access** for this environment (above).
2. **On-chain history provider** for wallet histories and per-token swap
   streams. A public RPC works for small pulls; a provider with parsed swap
   history (e.g. Helius) needs an API key stored as an environment secret.
3. **Media storage**: the container is temporary and raw media is not
   committed. Either re-download as needed (VODs may expire) or provide
   persistent storage.
4. **Cookies** (optional) if YouTube or Twitch block downloads from cloud IPs.
