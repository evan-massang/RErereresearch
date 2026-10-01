# Overnight tape analysis — train period

Window: 2026-10-01 12:15 → 17:15 UTC (5.0 h). Tape: 905,129 bonding-curve trades, 15,317 tokens, 76,276 wallets.

All numbers are bonding-curve trades only, from on-chain events. PnL in SOL after the on-chain 1.25% fee, before priority fees. Copy tests add a 0.001 SOL priority fee per tx, 20% slippage tolerance and 2% random tx failure (assumptions).

## Seed traders

### decu

`4vw54BmAogeRV3vPKWyFet5yf8DTLcREzdSzx4rw9Ud9`

```
{
 "closed_trips": 17,
 "open_or_incomplete": 5,
 "pnl_sol": 14.1902,
 "win_rate": 0.824,
 "avg_win_sol": 1.0978,
 "avg_loss_sol": -0.3932,
 "profit_factor": 13.031,
 "median_hold_s": 40.8,
 "median_size_sol": 3.094,
 "median_entry_mcap_sol": 87.0,
 "median_age_at_entry_s": 9.2,
 "share_multi_buy": 0.765,
 "share_multi_sell": 0.059,
 "best_trade_share_of_pnl": 0.186,
 "share_entries_creation_block": 0.0,
 "share_entries_within_5_slots": 0.059,
 "pnl_from_creation_block_entries_sol": 0,
 "share_entries_with_known_creation": 1.0
}
```
Selection vs random same-moment tokens:
```
{"n": 17, "median_pick_return": 0.0679, "median_random_return": -0.0146, "median_difference": 0.0825, "share_pick_beats_random": 0.706, "sign_test_p": 0.1435}
```
Copy test (0.5 SOL per entry):

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 20 | 4.287 | 0.2144 | 0.3 | 3.064816972340493 | 1 | 0.349 |  |
| 1.0s | 16 | 0.919 | 0.0576 | 0.25 | 1.5065295341798386 | 4 | 0.250 |  |
| 2.0s | 16 | 0.908 | 0.0569 | 0.25 | 1.4743341331863626 | 4 | 0.249 |  |
| 3.0s | 15 | 1.084 | 0.0725 | 0.26666666666666666 | 1.6591971417293314 | 5 | 0.237 |  |
| 5.0s | 14 | 1.133 | 0.0811 | 0.21428571428571427 | 1.6612495684109148 | 6 | 0.222 |  |
| 10.0s | 15 | 0.795 | 0.0531 | 0.26666666666666666 | 1.4318818592711695 | 4 | 0.232 |  |

### cupsey

`2fg5QD1eD7rzNNCsvnhmXFm5hqNgwTTG8p7kQ6f3rx6f`

```
{
 "closed_trips": 15,
 "open_or_incomplete": 10,
 "pnl_sol": 0.096,
 "win_rate": 0.467,
 "avg_win_sol": 0.2245,
 "avg_loss_sol": -0.1844,
 "profit_factor": 1.065,
 "median_hold_s": 15.6,
 "median_size_sol": 0.748,
 "median_entry_mcap_sol": 78.7,
 "median_age_at_entry_s": 21.5,
 "share_multi_buy": 0.533,
 "share_multi_sell": 0.0,
 "best_trade_share_of_pnl": 7.264,
 "share_entries_creation_block": 0.0,
 "share_entries_within_5_slots": 0.0,
 "pnl_from_creation_block_entries_sol": 0,
 "share_entries_with_known_creation": 1.0
}
```
Selection vs random same-moment tokens:
```
{"n": 15, "median_pick_return": 0.0039, "median_random_return": -0.0, "median_difference": -0.0986, "share_pick_beats_random": 0.467, "sign_test_p": 1.0}
```
Copy test (0.5 SOL per entry):

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 25 | -2.336 | -0.0934 | 0.16 | 0.4386776428581007 | 0 | 0.342 |  |
| 1.0s | 24 | -2.166 | -0.0902 | 0.16666666666666666 | 0.4249183776815393 | 1 | 0.328 |  |
| 2.0s | 21 | -1.742 | -0.0828 | 0.19047619047619047 | 0.4705511335759907 | 3 | 0.290 |  |
| 3.0s | 24 | -2.111 | -0.0880 | 0.20833333333333334 | 0.4426068499718832 | 1 | 0.330 |  |
| 5.0s | 21 | -1.894 | -0.0900 | 0.23809523809523808 | 0.4109957339571752 | 3 | 0.290 |  |
| 10.0s | 16 | -1.094 | -0.0681 | 0.1875 | 0.5042804612340576 | 5 | 0.228 |  |

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
 "closed_trips": 2,
 "open_or_incomplete": 1,
 "pnl_sol": 1.0665,
 "win_rate": 0.5,
 "avg_win_sol": 1.5435,
 "avg_loss_sol": -0.477,
 "profit_factor": 3.236,
 "median_hold_s": 194.8,
 "median_size_sol": 1.001,
 "median_entry_mcap_sol": 76.9,
 "median_age_at_entry_s": 26.0,
 "share_multi_buy": 0.5,
 "share_multi_sell": 0.0,
 "best_trade_share_of_pnl": 1.447,
 "share_entries_creation_block": 0.0,
 "share_entries_within_5_slots": 0.0,
 "pnl_from_creation_block_entries_sol": 0,
 "share_entries_with_known_creation": 1.0
}
```
Selection vs random same-moment tokens:
```
{"n": 2, "median_pick_return": 0.5012, "median_random_return": 0.101, "median_difference": 0.4002, "share_pick_beats_random": 0.5, "sign_test_p": 1.0}
```
Copy test (0.5 SOL per entry):

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 2 | 0.341 | 0.1705 | 0.5 | 2.2534182884843132 | 0 | 0.034 |  |
| 1.0s | 2 | 0.331 | 0.1653 | 0.5 | 2.2154833808276906 | 0 | 0.033 |  |
| 2.0s | 2 | 0.370 | 0.1852 | 0.5 | 2.4916064067343253 | 0 | 0.034 |  |
| 3.0s | 2 | 0.430 | 0.2149 | 0.5 | 3.49787758289392 | 0 | 0.035 |  |
| 5.0s | 2 | 0.538 | 0.2689 | 0.5 | 5.406641815008834 | 0 | 0.036 |  |
| 10.0s | 2 | 0.429 | 0.2145 | 0.5 | 7.232997862196033 | 0 | 0.035 |  |

## Most profitable tracked wallets in this window

61 wallets had ≥5 closed bonding-curve round trips.

| name | trips | PnL SOL | win rate | PF | median hold s | median entry mcap SOL | best-trade share |
|---|---|---|---|---|---|---|---|
| slingoor | 18 | 74.189 | 0.944 | 132.617 | 610.5 | 59.3 | 0.167 |
| decu | 17 | 14.1902 | 0.824 | 13.031 | 40.8 | 87.0 | 0.186 |
| R4 | 33 | 12.0312 | 0.424 | 3.039 | 50.9 | 100.0 | 0.361 |
| Limfork.eth | 32 | 11.8882 | 0.562 | 4.006 | 40.0 | 77.3 | 0.328 |
| Cented | 30 | 10.0933 | 0.533 | 1.687 | 35.8 | 57.7 | 0.611 |
| Dame | 5 | 6.1434 | 0.8 | 226.293 | 54.0 | 48.5 | 0.314 |
| trunoest | 28 | 5.7667 | 0.643 | 2.299 | 27.2 | 80.6 | 0.476 |
| Mel | 8 | 4.8836 | 1.0 | None | 8.3 | 29.8 | 0.245 |
| Megga | 14 | 4.651 | 0.357 | 2.297 | 19.6 | 66.8 | 0.671 |
| Letterbomb | 17 | 4.1929 | 0.706 | 3.005 | 48.4 | 49.3 | 0.414 |
| Henn | 16 | 4.0963 | 0.312 | 2.198 | 10.0 | 52.4 | 1.055 |
| EustazZ | 30 | 3.9577 | 0.633 | 2.462 | 84.1 | 49.0 | 0.26 |
| KOREAN | 26 | 3.0289 | 0.423 | 2.5 | 7.0 | 60.1 | 0.443 |
| Toxic weast | 6 | 2.5213 | 0.667 | 12.769 | 57.5 | 47.9 | 1.005 |
| Esee06257 | 23 | 2.4447 | 0.261 | 1.591 | 15.3 | 60.6 | 1.335 |
| theo | 10 | 2.1039 | 0.4 | 1.572 | 47.6 | 51.8 | 1.216 |
| Domy | 13 | 1.87 | 0.385 | 1.554 | 34.3 | 51.2 | 1.966 |
| Doji | 6 | 1.7698 | 0.5 | 11.578 | 45.5 | 109.1 | 1.054 |
| Pengu ð« | 5 | 1.5205 | 0.4 | 3.674 | 11.7 | 53.3 | 1.343 |
| ram | 12 | 1.3304 | 0.667 | 2.838 | 32.2 | 36.4 | 0.536 |
| ban | 21 | 1.3077 | 0.429 | 1.66 | 27.0 | 89.1 | 1.258 |
| Betman | 5 | 1.1773 | 0.6 | 2.835 | 63.2 | 80.5 | 0.85 |
| Beaver | 7 | 1.1161 | 0.571 | 1.758 | 64.1 | 97.0 | 1.604 |
| LilMoonLambo | 6 | 0.9586 | 0.833 | 58.445 | 42.5 | 51.8 | 0.261 |
| Coler | 6 | 0.9191 | 0.5 | 2.171 | 20.0 | 67.7 | 1.302 |

## Top wallets: is their selection better than random, and can it be copied?

### slingoor (`5YRgrP3m…`)

Selection edge: `{"n": 18, "median_pick_return": -0.0848, "median_random_return": -0.017, "median_difference": -0.0021, "share_pick_beats_random": 0.5, "sign_test_p": 1.0}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 20 | 1.105 | 0.0552 | 0.55 | 1.8978712892412042 | 1 | 0.318 |  |
| 1.0s | 21 | 1.090 | 0.0519 | 0.5238095238095238 | 1.82125885207218 | 1 | 0.333 |  |
| 2.0s | 19 | 1.314 | 0.0692 | 0.47368421052631576 | 2.0297030561045033 | 3 | 0.307 |  |
| 3.0s | 17 | 1.582 | 0.0932 | 0.5294117647058824 | 2.728658146923179 | 4 | 0.279 |  |
| 5.0s | 16 | 2.321 | 0.1451 | 0.6875 | 4.86595671212081 | 2 | 0.274 |  |
| 10.0s | 10 | 0.377 | 0.0383 | 0.4 | 1.3580245888072806 | 6 | 0.176 |  |

### decu (`4vw54BmA…`)

Selection edge: `{"n": 17, "median_pick_return": 0.0679, "median_random_return": -0.0292, "median_difference": 0.1343, "share_pick_beats_random": 0.706, "sign_test_p": 0.1435}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 20 | 4.287 | 0.2144 | 0.3 | 3.064816972340493 | 1 | 0.349 |  |
| 1.0s | 16 | 0.919 | 0.0576 | 0.25 | 1.5065295341798386 | 4 | 0.250 |  |
| 2.0s | 16 | 0.908 | 0.0569 | 0.25 | 1.4743341331863626 | 4 | 0.249 |  |
| 3.0s | 15 | 1.084 | 0.0725 | 0.26666666666666666 | 1.6591971417293314 | 5 | 0.237 |  |
| 5.0s | 14 | 1.133 | 0.0811 | 0.21428571428571427 | 1.6612495684109148 | 6 | 0.222 |  |
| 10.0s | 15 | 0.795 | 0.0531 | 0.26666666666666666 | 1.4318818592711695 | 4 | 0.232 |  |

### R4 (`Cv5GgkpX…`)

Selection edge: `{"n": 33, "median_pick_return": -0.1233, "median_random_return": 0.0, "median_difference": -0.1233, "share_pick_beats_random": 0.364, "sign_test_p": 0.1628}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 34 | -0.369 | -0.0109 | 0.3235294117647059 | 0.8585382577436904 | 0 | 0.495 |  |
| 1.0s | 34 | -0.204 | -0.0060 | 0.35294117647058826 | 0.9210057860398237 | 0 | 0.497 |  |
| 2.0s | 33 | 0.284 | 0.0086 | 0.42424242424242425 | 1.120343219176848 | 1 | 0.489 |  |
| 3.0s | 34 | 0.334 | 0.0098 | 0.38235294117647056 | 1.1249117145700613 | 0 | 0.504 |  |
| 5.0s | 34 | -0.033 | -0.0010 | 0.38235294117647056 | 0.9884828376877207 | 0 | 0.500 |  |
| 10.0s | 29 | 2.036 | 0.0703 | 0.3103448275862069 | 1.9353300815520156 | 5 | 0.456 |  |

### Limfork.eth (`BQVz7fQ1…`)

Selection edge: `{"n": 32, "median_pick_return": -0.0263, "median_random_return": -0.0054, "median_difference": -0.0226, "share_pick_beats_random": 0.469, "sign_test_p": 0.8601}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 33 | 0.013 | 0.0004 | 0.18181818181818182 | 1.003337541797734 | 0 | 0.495 |  |
| 1.0s | 33 | 0.044 | 0.0013 | 0.21212121212121213 | 1.0112675188299483 | 0 | 0.494 |  |
| 2.0s | 31 | 0.739 | 0.0239 | 0.25806451612903225 | 1.2020494608436212 | 1 | 0.481 |  |
| 3.0s | 29 | 1.558 | 0.0538 | 0.3103448275862069 | 1.492892750573969 | 3 | 0.461 |  |
| 5.0s | 23 | 1.292 | 0.0562 | 0.30434782608695654 | 1.4875040645915263 | 7 | 0.357 |  |
| 10.0s | 21 | 1.852 | 0.0883 | 0.2857142857142857 | 1.6929850884949798 | 8 | 0.334 |  |

### Cented (`CyaE1Vxv…`)

Selection edge: `{"n": 30, "median_pick_return": -0.0932, "median_random_return": -0.0006, "median_difference": -0.0979, "share_pick_beats_random": 0.367, "sign_test_p": 0.2005}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 40 | 0.083 | 0.0021 | 0.2 | 1.0162938593861224 | 0 | 0.606 |  |
| 1.0s | 38 | 0.694 | 0.0183 | 0.21052631578947367 | 1.158361217390955 | 3 | 0.587 |  |
| 2.0s | 37 | 0.852 | 0.0231 | 0.2972972972972973 | 1.1953800436163329 | 4 | 0.573 |  |
| 3.0s | 35 | 0.492 | 0.0141 | 0.2 | 1.1099324519323286 | 6 | 0.539 |  |
| 5.0s | 32 | 0.212 | 0.0069 | 0.15625 | 1.0496578978899833 | 9 | 0.490 |  |
| 10.0s | 31 | -2.379 | -0.0765 | 0.12903225806451613 | 0.47060661001147625 | 10 | 0.442 |  |

### Dame (`EtyHwLDf…`)

Selection edge: `{"n": 5, "median_pick_return": -0.0514, "median_random_return": -0.0001, "median_difference": -0.0593, "share_pick_beats_random": 0.4, "sign_test_p": 1.0}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 6 | 1.784 | 0.2974 | 0.16666666666666666 | 5.127107419701276 | 0 | 0.110 |  |
| 1.0s | 6 | 1.792 | 0.2987 | 0.16666666666666666 | 5.227017218788943 | 0 | 0.110 |  |
| 2.0s | 6 | 1.658 | 0.2763 | 0.16666666666666666 | 3.966508562889283 | 0 | 0.109 |  |
| 3.0s | 6 | 1.639 | 0.2731 | 0.16666666666666666 | 4.125160140026158 | 0 | 0.108 |  |
| 5.0s | 6 | 1.559 | 0.2598 | 0.16666666666666666 | 3.514180651524665 | 0 | 0.107 |  |
| 10.0s | 3 | 1.856 | 0.6193 | 0.3333333333333333 | 8.007345084490284 | 3 | 0.069 |  |

### trunoest (`ardinRsN…`)

Selection edge: `{"n": 28, "median_pick_return": -0.0553, "median_random_return": -0.0001, "median_difference": -0.044, "share_pick_beats_random": 0.357, "sign_test_p": 0.1849}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 31 | -1.408 | -0.0454 | 0.12903225806451613 | 0.6763485539448918 | 0 | 0.435 |  |
| 1.0s | 28 | -0.758 | -0.0270 | 0.14285714285714285 | 0.7987027243265972 | 3 | 0.401 |  |
| 2.0s | 26 | -0.596 | -0.0228 | 0.19230769230769232 | 0.8161307035574075 | 6 | 0.377 |  |
| 3.0s | 24 | 0.021 | 0.0011 | 0.20833333333333334 | 1.008898220446295 | 7 | 0.355 |  |
| 5.0s | 20 | -1.226 | -0.0610 | 0.15 | 0.5145148869304998 | 11 | 0.283 |  |
| 10.0s | 14 | -0.494 | -0.0349 | 0.2857142857142857 | 0.7182375424604156 | 12 | 0.204 |  |

### Mel (`36A6mEN5…`)

Selection edge: `{"n": 8, "median_pick_return": 0.0564, "median_random_return": -0.0007, "median_difference": 0.0564, "share_pick_beats_random": 1.0, "sign_test_p": 0.0078}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 8 | -0.547 | -0.0684 | 0.125 | 0.3192583218588012 | 0 | 0.110 |  |
| 1.0s | 7 | -0.398 | -0.0567 | 0.14285714285714285 | 0.33537900245047486 | 1 | 0.098 |  |
| 2.0s | 8 | -0.592 | -0.0740 | 0.125 | 0.2005295016106882 | 0 | 0.109 |  |
| 3.0s | 8 | -0.529 | -0.0662 | 0.125 | 0.23145560405072524 | 0 | 0.110 |  |
| 5.0s | 6 | -0.462 | -0.0768 | 0.16666666666666666 | 0.006964597567914724 | 1 | 0.083 |  |
| 10.0s | 1 | -0.175 | -0.1740 | 0.0 | 0.0 | 1 | 0.013 |  |
