# Scope decision 2026-10-05: memecoins only

The user's research goal is memecoin trading. After the user asked why non-memecoin markets were being researched,
the user chose "Memecoins only" (2026-10-05). From now on: Solana/pump.fun memecoins and memecoin perpetuals
(e.g. WIF, BONK, FARTCOIN, PUMP, PENGU, TRUMP, SPX, PEPE, SHIB, DOGE, POPCAT, MOODENG) on any venue.

## Stopped / dropped (no result had been computed at stop time unless noted)
| item | status |
|---|---|
| H-PMDIGI, H-PMFLB, H-WXKALSHI (prediction markets) | dropped; PMDIGI agent stopped |
| H-DELIST (Binance delisting shorts, mostly altcoins) | agent stopped before results |
| H-BETALAG, H-EQLAG, H-LIGHTFADE-EQ, H-CLOSEDPROXY, H-EQOFFREV, H-TWAPXYZ (equities) | dropped before day-1 scoring; betalag and twapxyz recorders stopped, data deleted |
| H-LSRATIO-LC (top-30 majors on Lighter) | forward scoring discontinued (frozen record kept) |
| momentum_xs_l7_lo forward (broad perps; already failed holdout) | forward scoring discontinued |

## Kept, restricted to memecoins by amendment written BEFORE any outcome was computed
- H-HLLAG forward (WIF, kBONK, FARTCOIN, PUMP, TRUMP, SPX, PENGU, kSHIB): unchanged, already memecoins.
- H-LIGHTLAG and H-LIGHTFADE: scoring universe restricted to the memecoins in the recording (PUMP, DOGE).
  The day-1 data has not been opened. Smaller n is expected; n < 50 at validation = inconclusive, as before.
- H-TWAPRIDE / H-TWAPFADE: universe restricted to memecoin perps (list above plus any HL perp tagged as a meme
  in the HL UI category at scoring time is NOT used — the fixed list above plus kPEPE, kFLOKI, kNEIRO, POPCAT,
  MOODENG, MEW, GOAT, BRETT, TURBO, WLD-excluded). No price outcome had been computed.
