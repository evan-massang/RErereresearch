# Overnight tape analysis — train period

Window: 2026-10-01 12:15 → 12:22 UTC (0.13 h). Tape: 16,274 bonding-curve trades, 547 tokens, 4,601 wallets.

All numbers are bonding-curve trades only, from on-chain events. PnL in SOL after the on-chain 1.25% fee, before priority fees. Copy tests add a 0.001 SOL priority fee per tx, 20% slippage tolerance and 2% random tx failure (assumptions).

## Seed traders

### decu

`4vw54BmAogeRV3vPKWyFet5yf8DTLcREzdSzx4rw9Ud9`

```
{
 "closed_trips": 0,
 "open_or_incomplete": 0
}
```

### cupsey

`2fg5QD1eD7rzNNCsvnhmXFm5hqNgwTTG8p7kQ6f3rx6f`

```
{
 "closed_trips": 0,
 "open_or_incomplete": 0
}
```

### leck

`98T65wcMEjoNLDTJszBHGZEX75QRe8QaANXokv4yw3Mp`

```
{
 "closed_trips": 0,
 "open_or_incomplete": 0
}
```

### setuh

`62N1K57D37AUDGp68tnDYKPjGDsaAAtmo357nBtEtuR`

```
{
 "closed_trips": 0,
 "open_or_incomplete": 0
}
```

## Most profitable tracked wallets in this window

1 wallets had ≥5 closed bonding-curve round trips.

| name | trips | PnL SOL | win rate | PF | median hold s | median entry mcap SOL | best-trade share |
|---|---|---|---|---|---|---|---|
| ban | 5 | 2.0773 | 0.8 | 289.641 | 9.8 | 94.5 | 0.792 |

## Top wallets: is their selection better than random, and can it be copied?

### ban (`EqiFgyNw…`)

Selection edge: `{"n": 5, "median_pick_return": -0.0121, "median_random_return": -0.0021, "median_difference": 0.0074, "share_pick_beats_random": 0.6, "sign_test_p": 1.0}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 5 | -0.324 | -0.0649 | 0.2 | 0.1235194134251282 | 0 | 0.069 |  |
| 1.0s | 4 | -0.359 | -0.0898 | 0.25 | 0.010126996711633944 | 0 | 0.054 |  |
| 2.0s | 4 | -0.398 | -0.0994 | 0.0 | 0.0 | 0 | 0.053 |  |
| 3.0s | 4 | -0.452 | -0.1129 | 0.0 | 0.0 | 0 | 0.053 |  |
| 5.0s | 4 | -0.467 | -0.1167 | 0.0 | 0.0 | 0 | 0.053 |  |
| 10.0s | 2 | -0.158 | -0.0788 | 0.0 | 0.0 | 0 | 0.027 |  |
