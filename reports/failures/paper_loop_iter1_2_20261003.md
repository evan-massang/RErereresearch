# Research loop, iterations 1–2 (2026-10-03): both failed before reaching paper trading

The bar (agreed 2026-10-03, enforced by `pipeline/paper.py`): at least 50 forward paper trades, net profit after costs, profit factor above 1.2, and still profitable without the 3 best trades.

## Iteration 1: blind LLM judgement on Decu's candidate set

**Idea.** Decu's picks among creator-dump candidates make +0.27 SOL per simulated trade, against −0.15 for all candidates. Can an AI shown exactly what was visible at the trigger pick like them? It saw the coin, its description, the linked X post with its author stats, and the live tape numbers.

**Method.** `scripts/research/llm_choice_batches.py`:
- 706 train cards (before 16:15 UTC), shuffled, with opaque ids and no outcomes.
- Scored 1–5 card by card by 12 independent agents.
- The first round was discarded because agents had used threshold scripts instead of judging. Those scores are kept in `research/observations/llm_choice_train/discarded_scripted/` for the record.

**Result: FAIL on train** (`research/observations/evidence_llm_choice_train.json`).

| group | cards | SOL per trade |
|---|---|---|
| AI-rated buys (score 4) | 22 | −0.10 |
| score 3 | 57 | −0.13 |
| all candidates | 706 | −0.15 |
| Decu's picks | 8 | +0.27 |

The AI agreed with 2 of Decu's 8 picks. Its buys were only marginally better than buying everything.

## Iteration 2: front-running KOL followers

**Idea.** After a famous KOL buys, followers push the price 10–18% up within seconds. Buy 1 s after the KOL and sell into the followers.

**Method.** `scripts/research/kol_frontrun.py`, costs not yet applied:
- Train: 401 first buys by 99 KOLs.
- Validation: 554 first buys by 110 KOLs.

**Result: FAIL.**
- By the time a 1 s-late entry fills, the price is already up 16% (train median) or 13% (validation) from before the KOL's buy.
- After that, the median return is 0 at 5 s and negative from 10 s on: −1.3% / −0.5% at 10 s and −3.8% / −6.2% at 20 s.
- KOLs whose followers looked slower on train (mean +8% or more at 10 s) reversed on validation: 61 entries, −3.7% at 10 s and −15% at 20 s.

## Also checked (train, no hypothesis)

Good-dev launches inside Decu's candidate set: only 7, at −0.13 SOL per trade.

## What the misses point to

Decu's train picks are launches promoted by small dev accounts whose post points to something trending at that moment: OpenAI's "Todd" toad, a "Dead Internet Theory" post going viral, Phantom's Halloween post, a protest starting that day. Whether the referenced post is *actually spreading right now* is not in any historical data. So iteration 3 collects it live: `pipeline/recorder.py` now snapshots the linked post's views, likes and reposts at launch and again about 60 s later (`tweet_snaps` feed).
