# Overnight tape analysis — train period

Window: 2026-10-01 12:15 → 12:55 UTC (0.67 h). Tape: 101,305 bonding-curve trades, 2,020 tokens, 15,591 wallets.

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
 "closed_trips": 3,
 "open_or_incomplete": 3,
 "pnl_sol": 0.4162,
 "win_rate": 0.333,
 "avg_win_sol": 0.6976,
 "avg_loss_sol": -0.1407,
 "profit_factor": 2.479,
 "median_hold_s": 35.0,
 "median_size_sol": 0.667,
 "median_entry_mcap_sol": 56.5,
 "median_age_at_entry_s": 13.7,
 "share_multi_buy": 0.667,
 "share_multi_sell": 0.0,
 "best_trade_share_of_pnl": 1.676,
 "share_entries_creation_block": 0.0,
 "share_entries_within_5_slots": 0.0,
 "pnl_from_creation_block_entries_sol": 0,
 "share_entries_with_known_creation": 1.0
}
```
Selection vs random same-moment tokens:
```
{"n": 3, "median_pick_return": -0.0986, "median_random_return": -0.1417, "median_difference": -0.2109, "share_pick_beats_random": 0.333, "sign_test_p": 1.0}
```
Copy test (0.5 SOL per entry):

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 1 | -0.278 | -0.2747 | 0.0 | 0.0 | 3 | 0.014 |  |
| 1.0s | 1 | -0.274 | -0.2710 | 0.0 | 0.0 | 3 | 0.014 |  |
| 2.0s | 1 | -0.269 | -0.2657 | 0.0 | 0.0 | 3 | 0.014 |  |
| 3.0s | 1 | -0.248 | -0.2450 | 0.0 | 0.0 | 4 | 0.015 |  |
| 5.0s | 1 | -0.253 | -0.2499 | 0.0 | 0.0 | 4 | 0.014 |  |
| 10.0s | 1 | -0.181 | -0.1781 | 0.0 | 0.0 | 5 | 0.015 |  |

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

8 wallets had ≥5 closed bonding-curve round trips.

| name | trips | PnL SOL | win rate | PF | median hold s | median entry mcap SOL | best-trade share |
|---|---|---|---|---|---|---|---|
| Henn | 9 | 5.9749 | 0.333 | 5.624 | 7.3 | 47.6 | 0.723 |
| R4 | 5 | 3.4689 | 0.4 | 4.501 | 53.8 | 81.6 | 1.251 |
| ban | 11 | 2.6478 | 0.545 | 6.322 | 15.9 | 55.9 | 0.622 |
| Letterbomb | 5 | 1.7003 | 0.8 | 9.852 | 56.5 | 66.3 | 0.779 |
| ram | 7 | 0.7661 | 0.714 | 3.179 | 52.1 | 38.0 | 0.842 |
| Qavec | 5 | 0.4501 | 0.4 | 2.949 | 11.7 | 68.2 | 1.195 |
| Kev | 6 | -0.7716 | 0.167 | 0.151 | 7.9 | 46.5 | None |
| Flames | 8 | -1.2903 | 0.125 | 0.109 | 32.3 | 52.6 | None |

## Top wallets: is their selection better than random, and can it be copied?

### Henn (`FRbUNvGx…`)

Selection edge: `{"n": 9, "median_pick_return": -0.224, "median_random_return": -0.0064, "median_difference": -0.2215, "share_pick_beats_random": 0.222, "sign_test_p": 0.1797}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 8 | -1.087 | -0.1358 | 0.0 | 0.0 | 1 | 0.104 |  |
| 1.0s | 8 | -0.998 | -0.1246 | 0.0 | 0.0 | 1 | 0.105 |  |
| 2.0s | 9 | -0.868 | -0.0965 | 0.1111111111111111 | 0.01857332592859324 | 0 | 0.121 |  |
| 3.0s | 9 | -1.059 | -0.1176 | 0.0 | 0.0 | 0 | 0.118 |  |
| 5.0s | 6 | -0.683 | -0.1139 | 0.0 | 0.0 | 0 | 0.079 |  |
| 10.0s | 2 | -0.232 | -0.1155 | 0.0 | 0.0 | 2 | 0.027 |  |

### R4 (`Cv5GgkpX…`)

Selection edge: `{"n": 5, "median_pick_return": -0.1824, "median_random_return": -0.0067, "median_difference": -0.1203, "share_pick_beats_random": 0.4, "sign_test_p": 1.0}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 5 | 0.280 | 0.0560 | 0.2 | 1.71856681670053 | 0 | 0.080 |  |
| 1.0s | 5 | 0.316 | 0.0632 | 0.4 | 1.8126879454636922 | 0 | 0.080 |  |
| 2.0s | 5 | 0.072 | 0.0144 | 0.4 | 1.1719654379351399 | 0 | 0.077 |  |
| 3.0s | 5 | 0.139 | 0.0277 | 0.4 | 1.3567554585532062 | 0 | 0.078 |  |
| 5.0s | 5 | 0.212 | 0.0425 | 0.4 | 1.6555218261582914 | 0 | 0.079 |  |
| 10.0s | 4 | 2.026 | 0.5064 | 0.5 | 11.339677338393619 | 1 | 0.088 |  |

### ban (`EqiFgyNw…`)

Selection edge: `{"n": 11, "median_pick_return": -0.0209, "median_random_return": -0.0014, "median_difference": -0.0174, "share_pick_beats_random": 0.364, "sign_test_p": 0.5488}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 9 | -0.850 | -0.0943 | 0.0 | 0.0 | 1 | 0.122 |  |
| 1.0s | 8 | -0.721 | -0.0900 | 0.0 | 0.0 | 1 | 0.109 |  |
| 2.0s | 8 | -0.703 | -0.0878 | 0.125 | 0.005204222631896412 | 1 | 0.109 |  |
| 3.0s | 8 | -0.785 | -0.0980 | 0.0 | 0.0 | 1 | 0.108 |  |
| 5.0s | 8 | -0.801 | -0.0999 | 0.0 | 0.0 | 1 | 0.108 |  |
| 10.0s | 6 | -0.527 | -0.0877 | 0.0 | 0.0 | 1 | 0.082 |  |

### Letterbomb (`BtMBMPko…`)

Selection edge: `{"n": 5, "median_pick_return": 0.2548, "median_random_return": -0.0, "median_difference": 0.2549, "share_pick_beats_random": 0.8, "sign_test_p": 0.375}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 4 | 0.225 | 0.0568 | 0.25 | 1.8223481806138462 | 2 | 0.063 |  |
| 1.0s | 3 | -0.281 | -0.0927 | 0.0 | 0.0 | 3 | 0.043 |  |
| 2.0s | 3 | -0.290 | -0.0959 | 0.0 | 0.0 | 2 | 0.042 |  |
| 3.0s | 1 | -0.039 | -0.0354 | 0.0 | 0.0 | 4 | 0.018 |  |
| 5.0s | 2 | -0.053 | -0.0251 | 0.0 | 0.0 | 3 | 0.032 |  |
| 10.0s | 0 | -0.005 | 0.0000 | – | – | 5 | 0.005 |  |

### ram (`57rXqaQs…`)

Selection edge: `{"n": 7, "median_pick_return": 0.0511, "median_random_return": -0.0052, "median_difference": 0.1021, "share_pick_beats_random": 0.714, "sign_test_p": 0.4531}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 5 | -0.146 | -0.0290 | 0.2 | 0.38613650378507514 | 2 | 0.072 |  |
| 1.0s | 5 | -0.141 | -0.0281 | 0.2 | 0.4123211470970757 | 2 | 0.072 |  |
| 2.0s | 5 | -0.144 | -0.0286 | 0.2 | 0.40137555256293767 | 2 | 0.072 |  |
| 3.0s | 5 | -0.144 | -0.0286 | 0.2 | 0.40137555256293767 | 2 | 0.072 |  |
| 5.0s | 5 | 0.082 | 0.0165 | 0.2 | 1.3506581221220122 | 2 | 0.075 |  |
| 10.0s | 5 | 0.071 | 0.0141 | 0.2 | 1.302907916349031 | 1 | 0.074 |  |

### Qavec (`gangJEP5…`)

Selection edge: `{"n": 5, "median_pick_return": -0.0351, "median_random_return": -0.0136, "median_difference": 0.0115, "share_pick_beats_random": 0.6, "sign_test_p": 1.0}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 5 | -0.120 | -0.0239 | 0.4 | 0.4071444513146064 | 0 | 0.072 |  |
| 1.0s | 5 | -0.132 | -0.0263 | 0.4 | 0.324317089911378 | 0 | 0.071 |  |
| 2.0s | 4 | -0.258 | -0.0646 | 0.25 | 0.06910093904262776 | 1 | 0.055 |  |
| 3.0s | 4 | -0.014 | -0.0035 | 0.25 | 0.9185406020912409 | 1 | 0.058 |  |
| 5.0s | 5 | -0.216 | -0.0432 | 0.4 | 0.3915216271756041 | 0 | 0.070 |  |
| 10.0s | 2 | -0.109 | -0.0546 | 0.0 | 0.0 | 1 | 0.028 |  |

### Kev (`BTf4A2ex…`)

Selection edge: `{"n": 6, "median_pick_return": -0.0622, "median_random_return": -0.0071, "median_difference": -0.0622, "share_pick_beats_random": 0.333, "sign_test_p": 0.6875}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 6 | -0.706 | -0.1176 | 0.0 | 0.0 | 0 | 0.079 |  |
| 1.0s | 6 | -0.611 | -0.1018 | 0.0 | 0.0 | 0 | 0.080 |  |
| 2.0s | 6 | -0.731 | -0.1216 | 0.16666666666666666 | 0.05817825106720826 | 1 | 0.079 |  |
| 3.0s | 5 | -0.590 | -0.1177 | 0.0 | 0.0 | 2 | 0.068 |  |
| 5.0s | 4 | -0.395 | -0.0983 | 0.0 | 0.0 | 2 | 0.055 |  |
| 10.0s | 2 | -0.345 | -0.1715 | 0.0 | 0.0 | 2 | 0.027 |  |

### Flames (`6aXFYXbF…`)

Selection edge: `{"n": 8, "median_pick_return": -0.1436, "median_random_return": 0.0, "median_difference": -0.1819, "share_pick_beats_random": 0.0, "sign_test_p": 0.0078}`

| delay | trades | PnL SOL | expectancy | win rate | PF | failed tx | fee drag | note |
|---|---|---|---|---|---|---|---|---|
| 0.5s | 8 | -0.692 | -0.0864 | 0.25 | 0.2320479807576891 | 1 | 0.109 |  |
| 1.0s | 7 | -0.613 | -0.0873 | 0.2857142857142857 | 0.26504952814266863 | 2 | 0.097 |  |
| 2.0s | 8 | -0.586 | -0.0731 | 0.375 | 0.35567316328723736 | 1 | 0.111 |  |
| 3.0s | 7 | -0.518 | -0.0737 | 0.2857142857142857 | 0.3798751088492359 | 2 | 0.098 |  |
| 5.0s | 6 | -0.570 | -0.0949 | 0.16666666666666666 | 0.26089277295897695 | 3 | 0.096 |  |
| 10.0s | 5 | -0.173 | -0.0343 | 0.2 | 0.5984945479308763 | 4 | 0.073 |  |
