# Overnight tape analysis — train period

Window: 2026-10-01 12:15 → 15:10 UTC (2.93 h). Tape: 537,514 bonding-curve trades, 9,081 tokens, 49,445 wallets.

All numbers are bonding-curve trades only, from on-chain events. PnL in SOL after the on-chain 1.25% fee, before priority fees. Copy tests add a 0.001 SOL priority fee per tx, 20% slippage tolerance and 2% random tx failure (assumptions).

## Seed traders

### decu

`4vw54BmAogeRV3vPKWyFet5yf8DTLcREzdSzx4rw9Ud9`

```
{
 "closed_trips": 12,
 "open_or_incomplete": 1,
 "pnl_sol": 9.271,
 "win_rate": 0.833,
 "avg_win_sol": 0.9869,
 "avg_loss_sol": -0.299,
 "profit_factor": 16.504,
 "median_hold_s": 35.4,
 "median_size_sol": 2.995,
 "median_entry_mcap_sol": 84.1,
 "median_age_at_entry_s": 11.3,
 "share_multi_buy": 0.667,
 "share_multi_sell": 0.0,
 "best_trade_share_of_pnl": 0.279,
 "share_entries_creation_block": 0.0,
 "share_entries_within_5_slots": 0.083,
 "pnl_from_creation_block_entries_sol": 0,
 "share_entries_with_known_creation": 1.0
}
```
Selection vs random same-moment tokens:
```
{"n": 12, "median_pick_return": 0.049, "median_random_return": 0.0009, "median_difference": 0.0742, "share_pick_beats_random": 0.583, "sign_test_p": 0.7744}
```
Copy test (0.5 SOL per entry):

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 11 | 0.812 | 0.0739 | 0.09090909090909091 | 1.5814187167459426 | 1 | 0.172 |  |
| 1.0s | 9 | -1.302 | -0.1445 | 0.0 | 0.0 | 2 | 0.117 |  |
| 2.0s | 8 | -1.118 | -0.1396 | 0.0 | 0.0 | 3 | 0.105 |  |
| 3.0s | 8 | -1.083 | -0.1352 | 0.0 | 0.0 | 3 | 0.105 |  |
| 5.0s | 9 | -1.248 | -0.1386 | 0.0 | 0.0 | 2 | 0.117 |  |
| 10.0s | 8 | -0.975 | -0.1218 | 0.125 | 0.0958177381050766 | 2 | 0.106 |  |

### cupsey

`2fg5QD1eD7rzNNCsvnhmXFm5hqNgwTTG8p7kQ6f3rx6f`

```
{
 "closed_trips": 10,
 "open_or_incomplete": 6,
 "pnl_sol": -0.5613,
 "win_rate": 0.4,
 "avg_win_sol": 0.2074,
 "avg_loss_sol": -0.2318,
 "profit_factor": 0.596,
 "median_hold_s": 17.3,
 "median_size_sol": 0.677,
 "median_entry_mcap_sol": 71.9,
 "median_age_at_entry_s": 21.0,
 "share_multi_buy": 0.5,
 "share_multi_sell": 0.0,
 "best_trade_share_of_pnl": null,
 "share_entries_creation_block": 0.0,
 "share_entries_within_5_slots": 0.0,
 "pnl_from_creation_block_entries_sol": 0,
 "share_entries_with_known_creation": 1.0
}
```
Selection vs random same-moment tokens:
```
{"n": 10, "median_pick_return": -0.164, "median_random_return": 0.0008, "median_difference": -0.2256, "share_pick_beats_random": 0.4, "sign_test_p": 0.7539}
```
Copy test (0.5 SOL per entry):

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 16 | -2.209 | -0.1381 | 0.125 | 0.23468968536462947 | 0 | 0.210 |  |
| 1.0s | 16 | -2.261 | -0.1413 | 0.125 | 0.21274773056846077 | 0 | 0.209 |  |
| 2.0s | 13 | -1.802 | -0.1384 | 0.15384615384615385 | 0.25768239112780456 | 2 | 0.171 |  |
| 3.0s | 15 | -1.784 | -0.1190 | 0.2 | 0.281591421955673 | 0 | 0.201 |  |
| 5.0s | 13 | -1.989 | -0.1528 | 0.15384615384615385 | 0.09131589536066312 | 2 | 0.169 |  |
| 10.0s | 10 | -1.388 | -0.1386 | 0.1 | 0.14259503919088906 | 3 | 0.135 |  |

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

37 wallets had ≥5 closed bonding-curve round trips.

| name | trips | PnL SOL | win rate | PF | median hold s | median entry mcap SOL | best-trade share |
|---|---|---|---|---|---|---|---|
| slingoor | 8 | 25.2259 | 1.0 | None | 16.6 | 46.3 | 0.289 |
| R4 | 22 | 10.5526 | 0.409 | 3.212 | 54.9 | 103.0 | 0.411 |
| decu | 12 | 9.271 | 0.833 | 16.504 | 35.4 | 84.1 | 0.279 |
| Limfork.eth | 20 | 8.4802 | 0.5 | 3.874 | 90.4 | 79.3 | 0.46 |
| trunoest | 19 | 7.4773 | 0.737 | 5.581 | 32.5 | 74.2 | 0.367 |
| Cented | 18 | 7.2122 | 0.556 | 1.763 | 33.3 | 58.5 | 0.854 |
| Megga | 7 | 6.8479 | 0.429 | 6.343 | 65.7 | 66.1 | 0.456 |
| Letterbomb | 16 | 4.5398 | 0.75 | 3.603 | 40.0 | 50.4 | 0.382 |
| Henn | 16 | 4.0963 | 0.312 | 2.198 | 10.0 | 52.4 | 1.055 |
| Mel | 6 | 3.3234 | 1.0 | None | 8.5 | 29.8 | 0.359 |
| KOREAN | 18 | 2.3793 | 0.444 | 2.752 | 8.2 | 61.1 | 0.564 |
| Beaver | 6 | 2.1377 | 0.667 | 5.747 | 72.6 | 94.2 | 0.838 |
| EustazZ | 26 | 1.6723 | 0.615 | 1.645 | 61.1 | 49.6 | 0.527 |
| ram | 12 | 1.3304 | 0.667 | 2.838 | 32.2 | 36.4 | 0.536 |
| ban | 21 | 1.3077 | 0.429 | 1.66 | 27.0 | 89.1 | 1.258 |
| leyko | 6 | 0.8384 | 0.333 | 1.443 | 318.2 | 79.0 | 1.684 |
| Daumen | 11 | 0.5976 | 0.636 | 1.454 | 25.8 | 85.0 | 1.078 |
| Qavec | 6 | 0.4392 | 0.333 | 2.816 | 10.1 | 64.7 | 1.224 |
| Nilla | 5 | 0.0274 | 0.4 | 1.02 | 144.0 | 59.9 | 42.985 |
| Thurston (zapped arc) | 5 | -0.0413 | 0.4 | 0.973 | 89.5 | 63.8 | None |
| Zuki | 6 | -0.2913 | 0.5 | 0.747 | 85.1 | 71.4 | None |
| k4ye | 9 | -0.2934 | 0.556 | 0.578 | 9.2 | 88.6 | None |
| Cupsey | 10 | -0.5613 | 0.4 | 0.596 | 17.3 | 71.9 | None |
| parsiiix | 7 | -0.5783 | 0.143 | 0.704 | 12.4 | 65.4 | None |
| Kev | 12 | -0.6385 | 0.25 | 0.459 | 5.3 | 53.4 | None |

## Top wallets: is their selection better than random, and can it be copied?

### slingoor (`5YRgrP3m…`)

Selection edge: `{"n": 8, "median_pick_return": -0.1116, "median_random_return": -0.0234, "median_difference": 0.0102, "share_pick_beats_random": 0.5, "sign_test_p": 1.0}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 14 | 0.206 | 0.0147 | 0.5 | 1.1815967684387112 | 0 | 0.216 |  |
| 1.0s | 14 | 0.357 | 0.0255 | 0.5 | 1.3054960799062143 | 1 | 0.218 |  |
| 2.0s | 14 | 0.619 | 0.0443 | 0.42857142857142855 | 1.5344727688536102 | 3 | 0.223 |  |
| 3.0s | 13 | 1.516 | 0.1167 | 0.5384615384615384 | 2.8759728148116275 | 3 | 0.217 |  |
| 5.0s | 11 | 1.824 | 0.1659 | 0.7272727272727273 | 4.812281783311907 | 1 | 0.192 |  |
| 10.0s | 7 | 0.124 | 0.0184 | 0.42857142857142855 | 1.1359264482729334 | 4 | 0.126 |  |

### R4 (`Cv5GgkpX…`)

Selection edge: `{"n": 22, "median_pick_return": -0.1413, "median_random_return": 0.004, "median_difference": -0.1128, "share_pick_beats_random": 0.364, "sign_test_p": 0.2863}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 22 | -0.003 | -0.0001 | 0.3181818181818182 | 0.9982922413880468 | 0 | 0.325 |  |
| 1.0s | 22 | 0.154 | 0.0070 | 0.36363636363636365 | 1.0814557977586823 | 0 | 0.327 |  |
| 2.0s | 22 | 0.075 | 0.0034 | 0.4090909090909091 | 1.041196286280637 | 0 | 0.326 |  |
| 3.0s | 22 | 0.138 | 0.0063 | 0.36363636363636365 | 1.071995901999025 | 0 | 0.326 |  |
| 5.0s | 22 | 0.104 | 0.0047 | 0.4090909090909091 | 1.0536843088935166 | 0 | 0.326 |  |
| 10.0s | 20 | 1.508 | 0.0755 | 0.3 | 1.892758993651299 | 2 | 0.316 |  |

### decu (`4vw54BmA…`)

Selection edge: `{"n": 12, "median_pick_return": 0.049, "median_random_return": -0.0004, "median_difference": 0.0042, "share_pick_beats_random": 0.5, "sign_test_p": 1.0}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 11 | 0.812 | 0.0739 | 0.09090909090909091 | 1.5814187167459426 | 1 | 0.172 |  |
| 1.0s | 9 | -1.302 | -0.1445 | 0.0 | 0.0 | 2 | 0.117 |  |
| 2.0s | 8 | -1.118 | -0.1396 | 0.0 | 0.0 | 3 | 0.105 |  |
| 3.0s | 8 | -1.083 | -0.1352 | 0.0 | 0.0 | 3 | 0.105 |  |
| 5.0s | 9 | -1.248 | -0.1386 | 0.0 | 0.0 | 2 | 0.117 |  |
| 10.0s | 8 | -0.975 | -0.1218 | 0.125 | 0.0958177381050766 | 2 | 0.106 |  |

### Limfork.eth (`BQVz7fQ1…`)

Selection edge: `{"n": 20, "median_pick_return": -0.0263, "median_random_return": -0.0053, "median_difference": -0.0249, "share_pick_beats_random": 0.45, "sign_test_p": 0.8238}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 18 | -0.618 | -0.0343 | 0.1111111111111111 | 0.7089642947986076 | 0 | 0.265 |  |
| 1.0s | 18 | -0.691 | -0.0384 | 0.1111111111111111 | 0.6881814285682457 | 0 | 0.263 |  |
| 2.0s | 17 | -0.354 | -0.0207 | 0.17647058823529413 | 0.824468436903917 | 1 | 0.247 |  |
| 3.0s | 16 | -0.067 | -0.0041 | 0.25 | 0.9631106451361929 | 2 | 0.234 |  |
| 5.0s | 13 | 0.368 | 0.0284 | 0.23076923076923078 | 1.2401245291065126 | 3 | 0.196 |  |
| 10.0s | 12 | 0.284 | 0.0237 | 0.25 | 1.1828114218838055 | 4 | 0.180 |  |

### trunoest (`ardinRsN…`)

Selection edge: `{"n": 19, "median_pick_return": -0.0132, "median_random_return": 0.0, "median_difference": -0.0617, "share_pick_beats_random": 0.316, "sign_test_p": 0.1671}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 21 | -0.017 | -0.0008 | 0.14285714285714285 | 0.9937796066126479 | 0 | 0.307 |  |
| 1.0s | 19 | 0.143 | 0.0076 | 0.15789473684210525 | 1.0558911986859312 | 2 | 0.281 |  |
| 2.0s | 17 | -0.001 | 0.0001 | 0.11764705882352941 | 1.0007986646778249 | 4 | 0.251 |  |
| 3.0s | 17 | 0.632 | 0.0373 | 0.17647058823529413 | 1.321516714162944 | 4 | 0.258 |  |
| 5.0s | 16 | -1.144 | -0.0713 | 0.125 | 0.48191546012635256 | 5 | 0.222 |  |
| 10.0s | 12 | -1.430 | -0.1189 | 0.16666666666666666 | 0.17670689887063684 | 5 | 0.160 |  |

### Cented (`CyaE1Vxv…`)

Selection edge: `{"n": 18, "median_pick_return": -0.1225, "median_random_return": -0.0144, "median_difference": -0.1294, "share_pick_beats_random": 0.333, "sign_test_p": 0.2379}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 24 | 1.919 | 0.0799 | 0.20833333333333334 | 1.6445463352158247 | 0 | 0.390 |  |
| 1.0s | 23 | 2.432 | 0.1058 | 0.21739130434782608 | 1.9776859940340945 | 1 | 0.383 |  |
| 2.0s | 23 | 2.711 | 0.1179 | 0.391304347826087 | 2.1354425432496575 | 1 | 0.386 |  |
| 3.0s | 22 | 2.493 | 0.1133 | 0.2727272727272727 | 2.0539099884198957 | 1 | 0.368 |  |
| 5.0s | 20 | 2.422 | 0.1213 | 0.25 | 2.0864345663219597 | 3 | 0.335 |  |
| 10.0s | 21 | -0.409 | -0.0194 | 0.19047619047619047 | 0.8383145708719574 | 2 | 0.316 |  |

### Megga (`H31vEBxS…`)

Selection edge: `{"n": 7, "median_pick_return": -0.0827, "median_random_return": -0.063, "median_difference": -0.0967, "share_pick_beats_random": 0.429, "sign_test_p": 1.0}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 8 | -0.752 | -0.0939 | 0.125 | 0.3742110726528937 | 1 | 0.109 |  |
| 1.0s | 8 | -0.739 | -0.0923 | 0.125 | 0.38374500712129644 | 1 | 0.110 |  |
| 2.0s | 9 | -0.440 | -0.0489 | 0.3333333333333333 | 0.5563656459254244 | 0 | 0.129 |  |
| 3.0s | 9 | -0.419 | -0.0466 | 0.3333333333333333 | 0.5488739089796679 | 0 | 0.129 |  |
| 5.0s | 9 | -0.614 | -0.0683 | 0.2222222222222222 | 0.3459923007465611 | 0 | 0.127 |  |
| 10.0s | 3 | -0.537 | -0.1779 | 0.0 | 0.0 | 5 | 0.041 |  |

### Letterbomb (`BtMBMPko…`)

Selection edge: `{"n": 16, "median_pick_return": 0.0213, "median_random_return": -0.0006, "median_difference": 0.0479, "share_pick_beats_random": 0.625, "sign_test_p": 0.4545}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 16 | -0.343 | -0.0214 | 0.1875 | 0.8139112874118974 | 1 | 0.243 |  |
| 1.0s | 15 | -0.820 | -0.0546 | 0.13333333333333333 | 0.5527282286262967 | 1 | 0.217 |  |
| 2.0s | 14 | -0.876 | -0.0626 | 0.14285714285714285 | 0.48780907256746786 | 4 | 0.200 |  |
| 3.0s | 14 | -0.818 | -0.0585 | 0.14285714285714285 | 0.5160773168840471 | 4 | 0.200 |  |
| 5.0s | 14 | -1.106 | -0.0789 | 0.14285714285714285 | 0.3532505400691729 | 2 | 0.198 |  |
| 10.0s | 11 | -1.487 | -0.1349 | 0.09090909090909091 | 0.11883290079835891 | 3 | 0.145 |  |
