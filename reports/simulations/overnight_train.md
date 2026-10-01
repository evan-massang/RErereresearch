# Overnight tape analysis — train period

Window: 2026-10-01 12:15 → 13:22 UTC (1.13 h). Tape: 188,438 bonding-curve trades, 3,438 tokens, 22,502 wallets.

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
 "closed_trips": 4,
 "open_or_incomplete": 4,
 "pnl_sol": 0.4467,
 "win_rate": 0.5,
 "avg_win_sol": 0.3641,
 "avg_loss_sol": -0.1407,
 "profit_factor": 2.587,
 "median_hold_s": 28.2,
 "median_size_sol": 0.481,
 "median_entry_mcap_sol": 56.1,
 "median_age_at_entry_s": 13.0,
 "share_multi_buy": 0.5,
 "share_multi_sell": 0.0,
 "best_trade_share_of_pnl": 1.562,
 "share_entries_creation_block": 0.0,
 "share_entries_within_5_slots": 0.0,
 "pnl_from_creation_block_entries_sol": 0,
 "share_entries_with_known_creation": 1.0
}
```
Selection vs random same-moment tokens:
```
{"n": 4, "median_pick_return": 0.0087, "median_random_return": -0.0396, "median_difference": 0.0262, "share_pick_beats_random": 0.5, "sign_test_p": 1.0}
```
Copy test (0.5 SOL per entry):

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 5 | -1.129 | -0.2255 | 0.0 | 0.0 | 2 | 0.065 |  |
| 1.0s | 5 | -1.099 | -0.2194 | 0.0 | 0.0 | 2 | 0.065 |  |
| 2.0s | 5 | -1.005 | -0.2005 | 0.0 | 0.0 | 2 | 0.066 |  |
| 3.0s | 5 | -1.049 | -0.2094 | 0.0 | 0.0 | 2 | 0.066 |  |
| 5.0s | 4 | -0.860 | -0.2143 | 0.0 | 0.0 | 3 | 0.055 |  |
| 10.0s | 5 | -1.098 | -0.2192 | 0.0 | 0.0 | 4 | 0.065 |  |

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

17 wallets had ≥5 closed bonding-curve round trips.

| name | trips | PnL SOL | win rate | PF | median hold s | median entry mcap SOL | best-trade share |
|---|---|---|---|---|---|---|---|
| Limfork.eth | 12 | 8.9776 | 0.583 | 7.667 | 90.4 | 108.8 | 0.435 |
| Henn | 10 | 5.8366 | 0.3 | 5.081 | 8.1 | 49.6 | 0.74 |
| Megga | 6 | 3.7285 | 0.333 | 3.909 | 53.5 | 64.8 | 0.765 |
| KOREAN | 7 | 3.3213 | 0.857 | 142.514 | 11.0 | 69.5 | 0.404 |
| R4 | 11 | 3.1744 | 0.364 | 2.325 | 54.7 | 99.9 | 1.367 |
| ban | 13 | 1.7552 | 0.462 | 2.263 | 25.1 | 62.0 | 0.938 |
| EustazZ | 8 | 0.8088 | 0.5 | 2.716 | 34.5 | 45.3 | 1.025 |
| ram | 8 | 0.6291 | 0.625 | 2.287 | 44.4 | 36.4 | 1.026 |
| Qavec | 5 | 0.4501 | 0.4 | 2.949 | 11.7 | 68.2 | 1.195 |
| Letterbomb | 9 | 0.2532 | 0.667 | 1.149 | 48.4 | 66.3 | 5.229 |
| Zuki | 6 | -0.2913 | 0.5 | 0.747 | 85.1 | 71.4 | None |
| Flames | 13 | -0.6762 | 0.308 | 0.685 | 34.8 | 53.9 | None |
| Kev | 7 | -0.7618 | 0.286 | 0.162 | 8.4 | 50.0 | None |
| Maze | 5 | -0.8398 | 0.4 | 0.107 | 28.1 | 46.2 | None |
| dv | 7 | -1.5368 | 0.286 | 0.139 | 29.5 | 72.7 | None |
| Esee06257 | 7 | -1.8091 | 0.143 | 0.234 | 23.9 | 65.6 | None |
| TIL | 5 | -2.0218 | 0.2 | 0.126 | 23.3 | 56.8 | None |

## Top wallets: is their selection better than random, and can it be copied?

### Limfork.eth (`BQVz7fQ1…`)

Selection edge: `{"n": 12, "median_pick_return": -0.0205, "median_random_return": 0.0035, "median_difference": -0.0268, "share_pick_beats_random": 0.417, "sign_test_p": 0.7744}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 9 | -0.279 | -0.0310 | 0.0 | 0.0 | 0 | 0.138 |  |
| 1.0s | 9 | -0.283 | -0.0314 | 0.0 | 0.0 | 0 | 0.137 |  |
| 2.0s | 9 | -0.278 | -0.0309 | 0.0 | 0.0 | 0 | 0.130 |  |
| 3.0s | 9 | -0.278 | -0.0309 | 0.0 | 0.0 | 0 | 0.128 |  |
| 5.0s | 7 | -0.229 | -0.0327 | 0.0 | 0.0 | 0 | 0.099 |  |
| 10.0s | 7 | -0.220 | -0.0315 | 0.0 | 0.0 | 0 | 0.100 |  |

### Henn (`FRbUNvGx…`)

Selection edge: `{"n": 10, "median_pick_return": -0.1812, "median_random_return": -0.0, "median_difference": -0.179, "share_pick_beats_random": 0.2, "sign_test_p": 0.1094}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 11 | -1.301 | -0.1182 | 0.0 | 0.0 | 0 | 0.145 |  |
| 1.0s | 11 | -1.210 | -0.1100 | 0.0 | 0.0 | 0 | 0.146 |  |
| 2.0s | 11 | -1.006 | -0.0914 | 0.09090909090909091 | 0.01607203983747172 | 0 | 0.149 |  |
| 3.0s | 11 | -1.041 | -0.0946 | 0.0 | 0.0 | 0 | 0.149 |  |
| 5.0s | 8 | -0.750 | -0.0937 | 0.0 | 0.0 | 0 | 0.108 |  |
| 10.0s | 3 | -0.395 | -0.1313 | 0.0 | 0.0 | 2 | 0.040 |  |

### Megga (`H31vEBxS…`)

Selection edge: `{"n": 6, "median_pick_return": -0.0904, "median_random_return": -0.031, "median_difference": -0.0723, "share_pick_beats_random": 0.333, "sign_test_p": 0.6875}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 8 | -0.215 | -0.0268 | 0.0 | 0.0 | 0 | 0.117 |  |
| 1.0s | 8 | -0.215 | -0.0268 | 0.0 | 0.0 | 0 | 0.117 |  |
| 2.0s | 8 | -0.215 | -0.0268 | 0.0 | 0.0 | 0 | 0.117 |  |
| 3.0s | 8 | -0.215 | -0.0268 | 0.0 | 0.0 | 0 | 0.117 |  |
| 5.0s | 8 | -0.215 | -0.0268 | 0.0 | 0.0 | 0 | 0.117 |  |
| 10.0s | 6 | -0.155 | -0.0258 | 0.0 | 0.0 | 0 | 0.089 |  |

### KOREAN (`6KR7Sors…`)

Selection edge: `{"n": 7, "median_pick_return": 0.3184, "median_random_return": 0.0, "median_difference": 0.3171, "share_pick_beats_random": 0.857, "sign_test_p": 0.125}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 8 | -0.203 | -0.0254 | 0.0 | 0.0 | 0 | 0.117 |  |
| 1.0s | 8 | -0.203 | -0.0254 | 0.0 | 0.0 | 0 | 0.117 |  |
| 2.0s | 8 | -0.203 | -0.0254 | 0.0 | 0.0 | 0 | 0.117 |  |
| 3.0s | 8 | -0.203 | -0.0254 | 0.0 | 0.0 | 0 | 0.117 |  |
| 5.0s | 7 | -0.177 | -0.0253 | 0.0 | 0.0 | 0 | 0.103 |  |
| 10.0s | 5 | -0.126 | -0.0252 | 0.0 | 0.0 | 0 | 0.074 |  |

### R4 (`Cv5GgkpX…`)

Selection edge: `{"n": 11, "median_pick_return": -0.1451, "median_random_return": -0.0456, "median_difference": -0.1368, "share_pick_beats_random": 0.455, "sign_test_p": 1.0}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 11 | 0.039 | 0.0035 | 0.2727272727272727 | 1.0384927130490365 | 0 | 0.164 |  |
| 1.0s | 11 | 0.011 | 0.0010 | 0.2727272727272727 | 1.0105682224257528 | 0 | 0.164 |  |
| 2.0s | 11 | -0.071 | -0.0065 | 0.36363636363636365 | 0.9368098560581405 | 0 | 0.163 |  |
| 3.0s | 11 | -0.187 | -0.0170 | 0.36363636363636365 | 0.8321758972386778 | 0 | 0.161 |  |
| 5.0s | 11 | -0.018 | -0.0017 | 0.36363636363636365 | 0.9828526333385195 | 0 | 0.164 |  |
| 10.0s | 8 | -0.419 | -0.0523 | 0.25 | 0.5372847963214892 | 3 | 0.113 |  |

### ban (`EqiFgyNw…`)

Selection edge: `{"n": 13, "median_pick_return": -0.0264, "median_random_return": -0.0283, "median_difference": -0.0189, "share_pick_beats_random": 0.385, "sign_test_p": 0.5811}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 14 | -0.360 | -0.0257 | 0.0 | 0.0 | 0 | 0.202 |  |
| 1.0s | 13 | -0.332 | -0.0255 | 0.0 | 0.0 | 0 | 0.188 |  |
| 2.0s | 13 | -0.332 | -0.0255 | 0.0 | 0.0 | 0 | 0.188 |  |
| 3.0s | 13 | -0.332 | -0.0255 | 0.0 | 0.0 | 0 | 0.188 |  |
| 5.0s | 13 | -0.332 | -0.0255 | 0.0 | 0.0 | 0 | 0.188 |  |
| 10.0s | 10 | -0.252 | -0.0252 | 0.0 | 0.0 | 0 | 0.145 |  |

### EustazZ (`FqamE7xr…`)

Selection edge: `{"n": 8, "median_pick_return": -0.068, "median_random_return": -0.0082, "median_difference": -0.0472, "share_pick_beats_random": 0.375, "sign_test_p": 0.7266}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 10 | -0.230 | -0.0230 | 0.2 | 0.7523243107854707 | 0 | 0.143 |  |
| 1.0s | 10 | -0.186 | -0.0186 | 0.2 | 0.7908115680513949 | 0 | 0.144 |  |
| 2.0s | 10 | -0.143 | -0.0143 | 0.2 | 0.831650221386987 | 0 | 0.144 |  |
| 3.0s | 10 | -0.144 | -0.0144 | 0.2 | 0.829728507749115 | 0 | 0.144 |  |
| 5.0s | 10 | 0.122 | 0.0122 | 0.4 | 1.1546252788777835 | 0 | 0.148 |  |
| 10.0s | 10 | -0.101 | -0.0101 | 0.2 | 0.8821817732660602 | 0 | 0.145 |  |

### ram (`57rXqaQs…`)

Selection edge: `{"n": 8, "median_pick_return": 0.0339, "median_random_return": -0.0078, "median_difference": 0.0619, "share_pick_beats_random": 0.625, "sign_test_p": 0.7266}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 6 | -0.571 | -0.0950 | 0.16666666666666666 | 0.13801350328690723 | 2 | 0.081 |  |
| 1.0s | 6 | -0.533 | -0.0887 | 0.16666666666666666 | 0.1562788512321915 | 2 | 0.082 |  |
| 2.0s | 6 | -0.369 | -0.0614 | 0.3333333333333333 | 0.35004703142163973 | 2 | 0.084 |  |
| 3.0s | 6 | -0.339 | -0.0564 | 0.3333333333333333 | 0.39373585130306893 | 2 | 0.084 |  |
| 5.0s | 6 | -0.153 | -0.0253 | 0.3333333333333333 | 0.7264932976628143 | 2 | 0.087 |  |
| 10.0s | 6 | -0.006 | -0.0009 | 0.3333333333333333 | 0.9893606329431591 | 1 | 0.088 |  |
