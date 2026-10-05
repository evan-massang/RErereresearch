# Barone & Lillo (arXiv 2606.15715) read in full, plus an ethics and legal note on trading with visible HL TWAPs

_Compiled 2026-10-05 by a research agent for H-TWAPRIDE and H-TWAPFADE (`sources/leads/documented_edges_round6.md`, ideas 1–2)._

**Status: DOCUMENT LEAD** (`document` modality). This is a third-party preprint, not a trader's statement and not a validated
finding. No backtest was run for this file, and no price outcome was computed from our own recorded TWAP data.

**Source.**
- Davide Barone and Fabrizio Lillo (Scuola Normale Superiore, Pisa), "Trading in the Sunshine or in the Shade: Market Impact
  and Adverse Selection on Hyperliquid".
- arXiv:2606.15715v1 [q-fin.TR], submitted 14 Jun 2026. Preprint, not peer reviewed. Links: [abs](https://arxiv.org/abs/2606.15715), [PDF](https://arxiv.org/pdf/2606.15715).
- The PDF was fetched 2026-10-05 (32 pages, sha256 `a52515926e95…7640`) and read in full: text, tables, Figures 3 and 6
  (rendered as images) and Appendix A.
- Page numbers below are the paper's printed page numbers, which match the PDF page index.

**Conventions.**
- Text inside "…" marked **Quote** is verbatim from the PDF text layer. Each quote was checked by string match against
  `pdftotext` output, after normalising whitespace and line-break hyphenation.
- Math symbols the text layer garbles are written in plain form inside [brackets].
- Everything else is our paraphrase or our reading of a figure, and is labelled that way.

---

## 1. What the paper actually measures

### 1.1 Data and definitions

- **Scope.** All 201 HL perpetual markets, 2025-07-28 to 2026-03-23. About 641 M fills.
  - Sample: about 465,000 native TWAPs with ≥ 5 child orders, and about 4.3 M "statistical" (hidden) metaorders with ≥ 10
    child orders. Both are restricted to executions that complete within 24 h.
  - Book snapshots: 1-minute snapshots, 20 levels deep, from 2025-12-15 only (§2, p. 4–5).
- **"465,000 TWAP executions" means parent TWAPs, not slices.**
  - **Quote (p. 5):** "about 465,000 native TWAP metaorders with at least 5 child orders".
  - That is about 1,900 a day over 239 days. This settles the round-6 §4 gap: it is comparable to the about 1,850/day
    `twapId` rate.
- **Normalisations (§2.1, p. 5–6).**
  - Traded fraction ϕ = Q / V24h. Q is the notional actually executed. V24h is same-market notional over the **forward**
    24 h from the order start.
  - Volume-time duration F = V_exec / V24h.
  - Average participation η = Q / V_exec. V_exec is the market volume during the execution window, so η and F are
    **ex-post** quantities.
  - Volatility σ_D is a Parkinson range estimate over the **forward** 24 h window (p. 8).
  - **Quote (p. 4):** "we compute the normalization variables used in the analysis, such as daily traded volume and
    volatility, over a 24-hour forward-looking window anchored at the metaorder start."
  - **Consequence for us.** None of the paper's conditioning variables is available at first sight. Our rule must use
    trailing 24 h volume (`day_ntl_vlm` in `ctx`) and the TWAP's announced size. Our ϕ is therefore an ex-ante proxy of
    theirs.
- **Impact definition.** Temporary impact is the signed relative change in the **last trade price** from start to end of
  execution, divided by σ_D (p. 8). It is a volatility-normalised number, not bp. Bp figures appear only where the paper
  converts them (at the median σ ≈ 0.050) and on the right axis of Figure 3.

### 1.2 TWAP sample shape (§2.1, p. 6–7)

- **Notional.** Median about 9.1 kUSD; 95th percentile about 496 kUSD.
- **Participation.**
  - **Quote (p. 7):** "median η is about 3.4%, while median TWAP participation is about 0.45%."
  - The TWAP 75th percentile is about 5.4%.
- **Volume-time duration.** Median F about 0.012; 95th percentile about 0.23.
- **Child count.** Median about 30 child orders.
- **Child-order interval.** **Quote (p. 4):** "child orders submitted automatically by validators every 30 seconds."

### 1.3 Impact size versus TWAP size: the aggregate law (§3.1, p. 8)

- **Quote (p. 8):** "Native TWAP orders display an approximately linear relation in log-log scale over the displayed range"
- The fitted law is log10 I_tmp = α + β log10 ϕ.
  - **Quote (p. 8):** "with estimates α̂ = −0.780 ± 0.004 and β̂ = 0.303 ± 0.002."
  - **Quote (p. 8):** "with an exponent well below the square-root benchmark."
  - It is fitted over ϕ ≥ 1e-5.
- **Our arithmetic from the fit; not a number printed in the paper.** I_tmp = 10^-0.780 · ϕ^0.303, in σ units. In bp:

| ϕ = Q/V24h | I_tmp (σ units) | bp at σ_D = 3% | bp at σ_D = 5% (paper's median) | bp at σ_D = 8% |
|---|---|---|---|---|
| 1e-4 | 0.010 | 3.1 | 5.1 | 8.1 |
| 5e-4 | 0.017 | 5.0 | 8.3 | 13.3 |
| 1e-3 | 0.021 | 6.1 | 10.2 | 16.4 |
| 3e-3 | 0.029 | 8.6 | 14.3 | 22.8 |
| 1e-2 | 0.041 | 12.3 | 20.6 | 32.9 |
| 3e-2 | 0.057 | 17.2 | 28.7 | 45.9 |

  These are **means of binned averages over all TWAPs**, measured start to end. They are not conditional expectations
  for a trade entered after first sight, and they include whatever trend the TWAP placer selected into (§1.6).

### 1.4 Impact versus participation and duration (§3.1, p. 9; §4.1, p. 15–16)

- **Pooled surface (stat + TWAP):** I_tmp = Y η^δ F^γ1.
  - **Quote (p. 9):** "Ŷ = 0.186 ± 0.004, δ̂ = 0.118 ± 0.003, γ̂1 = 0.306 ± 0.003".
- **TWAP-only surface (p. 15).**
  - **Quote:** "For native TWAPs, the corresponding estimates are YTWAP = 0.294 ± 0.013, δTWAP = 0.010 ± 0.011, and
    γTWAP = 0.622 ± 0.011, with R2 = 0.868."
- **Participation does not matter for TWAPs.**
  - **Quote (p. 15):** "For native TWAPs, the participation exponent is consistent with zero: conditional on volume-time
    duration, participation contains little additional information about temporary impact."
  - Order-level regression (Table 1, p. 16), slope for native TWAPs, in σ units per log unit:
    - log Q: 0.00650 (s.e. 0.00048);
    - log F: 0.00690 (0.00085);
    - log η: −0.00058 (0.00071), not significant.
  - **Quote (p. 16):** "TWAP costs are driven mainly by size and exposure over volume time."
- **Implication for the rule (our inference).** Round 6 keyed the entry on participation p. That is the variable the paper
  finds **uninformative** for TWAPs once duration is controlled for. Size relative to volume (ϕ) and volume-time
  duration (F) are the informative variables. The draft pre-registration therefore keys on ϕ, and keeps p only as a
  grid arm.

### 1.5 The impact path during execution (§3.2, p. 10–11, Figure 3)

- **Quote (p. 10):** "native TWAP trajectories rise in a concave, strictly increasing way over the execution interval; in
  several panels, however, they lie substantially below one, that is, below the impact predicted by the aggregate
  square-root law."
- **Quote (p. 10):** "the same trajectories display the typical concave, square-root-like profile documented in the
  empirical literature, rising as execution proceeds and well fitted by a power law of the form Aτ γ"
- **Quote (p. 3):** "native TWAP trajectories, by contrast, are much closer to the smooth, concave square-root path
  associated with uniform trading in propagator models".
- **Fitted exponents (our reading of the Figure 3 legends).** The A·τ^γ fits have γ ≈ 0.76–1.09 across the nine panels.
  - Short TWAPs: 0.78–1.09.
  - 3.7–23 min: 0.77–0.92.
  - 23 min–1 day: 0.76–0.82.
  - So the build-up is only mildly concave, close to linear in time. "Square-root-like" is the authors' wording. The
    fitted γ is well above 0.5.

**Figure 3 magnitudes, our reading of the right-hand bp axis.** These are approximate (±1–2 bp) and were read from the
rendered figure. The paper prints no table of them.

| Clock duration T | η bin | TWAP n | Peak at τ≈1 (bp) | Level τ = 1.2–2 (bp) | Pre-start τ = −0.5 (bp) |
|---|---|---|---|---|---|
| < 3.66 min | < 0.8% | 24,695 | ≈ 4 | ≈ 0 | ≈ −3.5 |
| < 3.66 min | 0.8–12% | 10,629 | ≈ 8 | ≈ 4 | ≈ −10 |
| < 3.66 min | ≥ 12% | 4,732 | ≈ 7 | ≈ 2 | ≈ −11 |
| 3.66–23.4 min | < 0.8% | 115,448 | ≈ 4 | ≈ 2–2.5 | ≈ −4.5 |
| 3.66–23.4 min | 0.8–12% | 68,546 | ≈ 10–11 | ≈ 7 | ≈ −10 |
| 3.66–23.4 min | ≥ 12% | 44,209 | ≈ 11 | ≈ 7 | ≈ −13 |
| **23.4 min–1 d** | < 0.8% | 113,758 | ≈ 12–13 | ≈ 9–10 | ≈ −10 |
| **23.4 min–1 d** | 0.8–12% | 41,862 | ≈ 15–16 | ≈ 11 | ≈ −18 |
| **23.4 min–1 d** | ≥ 12% | 20,039 | ≈ 21–22 | ≈ 18–19 | ≈ −17 |

- **Reading the columns.** τ = t/T. "Peak" is the signed move from execution start to completion. "Pre-start" is the
  signed move from τ = −0.5 to start. A negative value there means price already moved in the TWAP's direction before it
  started.
- **For TWAPs of 23 min to 24 h, the mean signed start-to-end move is about 12–22 bp.** For TWAPs under 23 min it is
  about 4–11 bp.

### 1.6 TWAPs are placed after a move in their own direction (p. 11)

- **Quote (p. 11):** "Native TWAPs begin with the trend: +18.2 basis points on average (median +13.5), with a
  same-direction share of 58.4%."
- **Quote (p. 11):** "Latent metaorders are thus on average contrarian, while announced TWAPs are trend-following."
- This uses a 30-minute pre-start window.
- **Implication (our inference).** Part of the in-execution drift may be ordinary short-horizon continuation, not causal
  impact. The paper does not separate the two for the during-execution path. That does not matter for a trading rule; it
  does matter for interpreting a pass.

### 1.7 Decay after completion (§4.2, p. 16–18, Figure 6, Table 2)

- **Quote (p. 16):** "In most bins, statistical metaorders retain a larger fraction of their completion impact over the
  post-trade window, while native TWAP orders relax more quickly. The main exceptions are concentrated in longer-duration
  bins, where normalized TWAP paths remain closer to the statistical-metaorder paths or decay more slowly."
- **No half-life is reported.** The decay is summarised by power-law fits. The TWAP "fit gamma" values in the Figure 6
  legends are 0.150–0.488.
- **Our reading of Figure 6: share of completion impact retained at τ = 1.5–4.**

| T | η < 0.8% | η 0.8–12% | η ≥ 12% |
|---|---|---|---|
| < 3.66 min | ≈ 0 (fully reverts, then overshoots) | ≈ 0.5–0.6 | ≈ 0.2–0.6 (noisy) |
| 3.66–23.4 min | ≈ 0.5–0.6 | ≈ 0.75–0.8 | ≈ 0.5–0.6 |
| **23.4 min–1 d** | **≈ 0.85–0.95** | **≈ 0.75–0.8** | **≈ 0.65–0.75** |

  For long TWAPs, most of the drop happens in the first ≈ 0.05–0.2 T after completion, and the curve is then nearly flat
  out to τ = 4.
- **Permanent-impact gap.**
  - **Quote (p. 18):** "In the baseline specification, the TWAP coefficient is between −5.0 and −5.5 basis points and
    highly significant across all horizons."
  - Table 2, Eq. (5): −5.41, −4.99, −5.45, −5.23 bp at τ = 1.5, 2, 3, 4.
  - Without the ϕ control: −3.25 to −3.79 bp.
  - With a pre-start-return control: −5.1 bp at τ = 1.5 and −4.7 bp at τ = 4.
- **The paper never prints the absolute TWAP post-completion reversal in bp.** Combining Figures 3 and 6 (our inference):
  - long TWAPs give back about 2–5 bp of a 12–22 bp peak;
  - short TWAPs give back about 4 bp of a 4–11 bp peak.

### 1.8 "Visible TWAPs have lower impact" (§4.1, p. 14–15)

- **Quote (p. 15):** "The estimated TWAP gap is θ̂ = −0.0177, with standard error 0.0010. At the pooled median volatility,
  σ ≃ 0.050, this corresponds to about 8.9 basis points lower temporary impact for a native TWAP relative to a statistical
  metaorder with the same reference execution profile."
- **Quote (p. 15):** "The median log difference is 0.37, corresponding to a median impact ratio of about 2.3."
- **Quote (p. 15):** "For F ≥ 3 × 10−2 , the two surfaces nearly coincide, with a median ratio close to one and an unstable
  sign."
  - The ratio is 5.4 for F < 3e-3 and 3.1 for 3e-3 ≤ F < 3e-2.
- **Pre-start-return control (p. 15).** With it, θ̂ = −0.0173, about 8.7 bp.
- This is a comparison **with hidden metaorders**. It does not say TWAP impact is small in absolute terms.
  - It is smallest relative to hidden flow for executions concentrated in volume time.
  - It vanishes for the long-in-volume-time executions (F ≥ 0.03) that dominate large TWAPs.

### 1.9 Order-book response (§4.4, p. 22–25, Table 4)

- **Quote (p. 25):** "During the active window, the book becomes more tilted toward the absorbing side, displayed depth
  increases, and fixed-notional sweep costs fall, while quoted spreads widen."
- **Table 4 (pooled across durations).**
  - Relative spread: +0.277 bp (lead +0.210 bp).
  - Imbalance within 5× spread: +0.0219.
  - Depth: +4,182 USD.
  - 10 kUSD sweep cost: −0.025 bp.
  - Size interaction on depth: +3,499 USD per log unit of notional.
- Sample: 56,692 events, ≥ 5 min and ≥ 10 kUSD. Median announced notional about 49 kUSD (p. 24).
- **Consequence for our costs (our inference).**
  - The book effects are economically tiny: tenths of a bp of spread.
  - A $1k taker pays essentially the pre-existing half-spread.
  - The absorbing-side depth is on the side *opposite* to a RIDE entry. A RIDE buy crosses the ask, which is the
    absorbing side for a buy TWAP. That book is a little deeper, while the spread is about 0.3 bp wider.

### 1.10 The paper's own conclusion on front-running, and its limitations

- **Quote (p. 4):** "the evidence is consistent with a sunshine-trading interpretation, in which publicly visible TWAP flow
  is on average less informed and its visibility elicits liquidity provision rather than predatory front-running".
- **Limitations (§5, p. 26).**
  - Traders self-select into TWAPs.
  - **Quote (p. 26):** "a taker-identity prior reaches AUC 0.998".
  - The book barely predicts TWAP arrivals.
  - The data run from July 2025 to March 2026. Regime drift since then is untested.

---

## 2. The round-6 summary, checked

| Round-6 claim (`documented_edges_round6.md`) | Verdict | Correct statement |
|---|---|---|
| 641 M fills, 465,000 visible TWAP executions, 4.3 M hidden metaorders, 2025-07-28 to 2026-03-23 | **Correct** | The 465,000 are parent TWAPs with ≥ 5 child orders, not slices (§1.1). |
| TWAPs "trade nearly uniformly" | **Correct, verbatim** | Abstract, p. 1. |
| "smooth, concave square-root-like profile" that rises and then "gradually decays" | **Partly correct** | "smooth, concave square-root path" (p. 3) and "concave, square-root-like profile" (p. 10) are verbatim. "Gradually decays" is not in the paper. The paper says TWAPs "relax more quickly" than hidden metaorders (p. 16). For TWAPs over 23 min, about 70–95% of completion impact persists to 4× the duration (Fig. 6). Fitted γ ≈ 0.76–1.09, so the path is close to linear. |
| About 8.9 bp lower temporary impact than hidden metaorders | **Correct** | It is relative to hidden metaorders at the median profile and median σ (§1.8). It is not an absolute level. The gap vanishes for F ≥ 0.03. |
| About **55 bp** less post-execution displacement | **Wrong by 10×** | It is **about 5 bp**: −5.0 to −5.5 bp in Table 2 (§1.7). Our guess is that the fetch tool garbled "5.5". |
| "displayed depth rises and the book tilts toward the absorbing side" | **Correct, verbatim** | Abstract. The effects are small in bp (§1.9). |
| Wanted: impact in bp vs participation rate | **Answered, against the round-6 rule** | For TWAPs, participation has **no** conditional effect (δ_TWAP = 0.010 ± 0.011; Table 1 slope −0.00058, n.s.). Size ϕ (exponent 0.303) and volume-time duration matter (§1.3–1.4). The Figure 3 bp levels are in §1.5. |
| Wanted: decay half-life | **Not reported** | No half-life. Retention curves are in §1.7. For long TWAPs there is no half-life within 4× the duration. |
| "Square-root impact … HL magnitude for TWAPs open" | **Answered** | HL TWAP impact follows ϕ^0.30, well below square root. About 10 bp at ϕ = 0.1% and about 21 bp at ϕ = 1% for σ_D = 5% (§1.3). |

**Not in round 6: TWAPs are trend-following at placement**, +18.2 bp over the prior 30 min (§1.6).

### What this means for the two ideas (inference, not a finding)

**H-TWAPRIDE.**
- **Expected gross.** About 12–22 bp mean signed drift from start to completion for 23 min–24 h TWAPs, or 14–21 bp at
  ϕ ≥ 0.3–1% and σ_D ≈ 5%.
- **Costs.** About 12–16 bp per taker round trip.
- **Expected net.** **Around 0 to +8 bp per trade** before selection effects. It is positive only for the larger-ϕ TWAPs
  on liquid coins.
- This is a thin edge, but not excluded by the paper.
- The best exit is at or just before completion: the post-completion step-down is 2–5 bp.

**H-TWAPFADE.**
- **Expected gross.** About 2–5 bp of reversal for long TWAPs, mostly within 0.05–0.2 T of completion.
- **Costs.** 8–16 bp.
- On the paper's own numbers the fade has **negative expected net**.
- **Recommendation: demote it.** Pre-register it only as a cheap control run on the same data, with a prior of FAIL.

---

## 3. Ethics and legal note: trading in the direction of publicly broadcast HL TWAPs

**This is not legal advice.** It summarises public texts and literature so the owner can ask the right questions. **The
user must check the law of their own jurisdiction, and Hyperliquid's terms as they apply to them, with a qualified
lawyer before any live trading.** Nothing here has been reviewed by a lawyer.

### 3.1 What we would be doing

- We read a TWAP's terms (direction, size, duration) from public on-chain data via Hypurrscan and the HL info API. The
  TWAP becomes visible the moment its placement is committed.
- We then take a small position in the same direction (RIDE) and exit at or before completion. Or, for FADE, we take the
  opposite side after completion.
- **What we do not do.**
  - We do not act as broker, agent or executor for the TWAP owner.
  - We receive no client order information.
  - We do not reorder, delay, censor or sandwich any transaction.
  - We submit no transaction conditional on seeing a pending, not-yet-committed transaction.

### 3.2 "Front-running" in the regulated sense is about intermediaries and non-public order information

- **US securities: FINRA Rule 5270**, "Front Running of Block Transactions". It applies to FINRA members and their
  associated persons, for securities and related instruments.
  [FINRA 5270](https://www.finra.org/rules-guidance/rulebooks/finra-rules/5270), fetched 2026-10-05.
  - **Quote, 5270(a):** "No member or person associated with a member shall cause to be executed an order to buy or sell
    a security or a related financial instrument when such member or person associated with a member causing such order
    to be executed has material, non-public market information concerning an imminent block transaction in that security
    … prior to the time information concerning the block transaction has been made publicly available or has otherwise
    become stale or obsolete."
  - **Quote, Supplementary Material .02:** "Information as to a block transaction shall be considered to be publicly
    available when it has been disseminated via a last sale reporting system or high speed communications line of one of
    those systems, a similar system of a national securities exchange under Section 6 of the Exchange Act, an alternative
    trading system under SEC Regulation ATS, or by a third-party news wire service. The requirement that information
    concerning the block transaction be made publicly available will not be satisfied until the entire block transaction
    has been completed and publicly reported."
  - **Note the second sentence.** Under FINRA's narrow definition, an announced but unfinished order is *not yet* "publicly
    available". The rule binds only members, and only for securities, which HL crypto perps are not. But it shows that "it
    is on-chain, so it is public" is not automatically the regulator's test.
- **EU and UK: Market Abuse Regulation (EU) 596/2014, Art. 7(1).** UK-retained text fetched from
  [legislation.gov.uk](https://www.legislation.gov.uk/eur/2014/596/article/7); the EU original was not reachable
  (EUR-Lex returned an empty page).
  - **Quote, 7(1)(a):** inside information is "information of a precise nature, which has not been made public, relating,
    directly or indirectly, to one or more issuers or to one or more financial instruments, and which, if it were made
    public, would be likely to have a significant effect on the prices of those financial instruments".
  - **Quote, 7(1)(d):** "for persons charged with the execution of orders concerning financial instruments, it also means
    information conveyed by a client and relating to the client's pending orders in financial instruments".
  - The classic front-running offence in MAR is therefore an executing intermediary misusing a client's pending-order
    information. That information is non-public by definition.
- **EU crypto-assets: MiCA, Regulation (EU) 2023/1114, Art. 87(1).** Text via
  [springlex.eu](https://www.springlex.eu/en/packages/mica/mica-regulation/article-87/), which reproduces OJ L 150. It is
  not checked against EUR-Lex.
  - The definition mirrors MAR: "information of a precise nature, which has not been made public …" and, for "persons
    charged with the execution of orders for crypto-assets on behalf of clients", information "conveyed by a client and
    relating to the client's pending orders in crypto-assets".
  - Arts. 89–91 prohibit insider dealing, unlawful disclosure and market manipulation for crypto-assets. That is our
    summary; not quoted.
- **US commodity derivatives (CFTC).** This is a **lead only; we fetched no primary text.**
  - Trading-ahead prohibitions for futures intermediaries (CFTC Rules 155.3/155.4) concern customer orders held by FCMs
    and IBs.
  - The general anti-fraud and anti-manipulation provisions (CEA §6(c)(1), Rule 180.1) target manipulation and fraud,
    not trading on public information.
  - Verify with counsel. Whether HL perps are themselves permitted for a given US person is a separate and more basic
    question (§3.4).

**Summary (our reading, not legal advice).**
- In the regulated sense we found, front-running needs either an **intermediary duty** to the order's owner (FINRA 5270,
  MAR 7(1)(d), MiCA 87(1)(c), CFTC trading-ahead rules), or **non-public** information (MAR and MiCA inside information).
- Reading a TWAP from a public chain and trading for our own account matches neither on its face:
  - there is no client relationship;
  - the protocol itself broadcasts the order to everyone;
  - the paper calls it "a protocol-level form of sunshine trading" (p. 5).
- **"Matches neither on its face" is not "lawful everywhere".** See the open questions.

### 3.3 Ethics: separate from legality

- **RIDE trades against the TWAP owner's execution cost.**
  - A same-direction taker adds to the price pressure the TWAP faces. Our gain is partly the TWAP owner's extra cost.
  - This is what Brunnermeier and Pedersen (2005, *Journal of Finance* 60(4), "Predatory Trading") call predatory trading.
    It is also the risk the sunshine-trading literature names: **Quote (Barone & Lillo p. 2):** "public disclosure exposes
    the trader to front-running or strategic behavior by other market participants, who may trade ahead of the announced
    order and move prices adversely".
  - At $1k against TWAPs of tens to hundreds of kUSD, our marginal impact is negligible. But the strategy only works if,
    on average, there is impact to share.
- **FADE is the opposite.** It supplies liquidity after the pressure ends: it buys after a sell TWAP finishes. That is the
  conventional, liquidity-providing side, and it is ethically uncontroversial.
- **The paper finds that on average the market responds to visible TWAPs with liquidity, not predation (p. 4, p. 27).**
  A small RIDE book would not change that, but it is the side of the trade the protocol's transparency was not designed
  to reward.
- **Recommendation.** Keep RIDE to paper trading until the owner has decided on the ethics question, independent of the
  legal answer.

### 3.4 Open questions for the user (answer before anything goes beyond paper)

1. **Your jurisdiction.** Which law applies to you and to any entity you trade through? Is trading HL perps permitted for
   you at all? HL's terms restrict some jurisdictions (round 4 §3); we did not re-fetch the current terms here, because the
   app page rendered empty.
2. **Do HL perps count as "financial instruments" or derivatives where you are**, so that MAR, MiFID or CFTC rules apply? Or
   do crypto-asset regimes like MiCA apply? Or neither?
3. **Is information "made public" if it is broadcast on a public blockchain but only practically readable via an API or a
   third-party explorer (Hypurrscan)?** FINRA's test, though not applicable here, names specific dissemination channels. A
   regulator could take a narrow view.
4. **Do you have any relationship with TWAP placers?** For example: running an execution service, vault, copy-trading
   product, or managing others' funds on HL. If so, intermediary duties could apply, and the analysis changes completely.
5. **Do HL's own terms of use prohibit "abusive" or "manipulative" trading** in language that could cover systematically
   trading ahead of TWAPs? This was not checked; the terms page did not render.
6. **Does the team's own ethics policy accept RIDE**, a predatory-trading-adjacent strategy, as opposed to FADE, which
   provides liquidity?
7. **Tax and reporting** of perp P&L in your jurisdiction. Not researched.

---

## 4. Our recorded data, used for counts only (OWN-PRECHECK, feature-only)

- **Data.** First 0.75 h of `data/raw/web/twap/`, 06:07–06:52 UTC 2026-10-05, read-only while recorder pid 25141 runs.
- **Variables.** Notional uses the `ctx` mark nearest first sight. ϕ = notional / trailing `day_ntl_vlm`.
  p = ϕ · 1440 / minutes.
- **No price path, return or outcome was computed.**

**New placements (`initial = False`), main-dex perps, not reduce-only, no error: n = 41.**
- **Notional.** Median $9.0k; p75 $27.7k; p90 $51k.
- **Duration.** Median 50 min.
- **With 30 ≤ minutes ≤ 1440: n = 18 in 0.75 h**, about 580/day if the rate held.
  - ϕ ≥ 0.05%: 9.
  - ϕ ≥ 0.1%: 5.
  - ϕ ≥ 0.3%: 2.
  - ϕ ≥ 1%: 2.
  - p ≥ 0.25%: 10. p ≥ 1%: 6.
- **Coins.** HYPE 16 of 41, then PURR, VVV, TAO, ETH, BTC.
- **Missing asset index.** Six more main-dex `hist`-only rows (HYPE ×4, BTC, PURR) have no asset index. The draft rule
  classifies them by coin name.

**The TWAPs already running at recorder start** are a stock, not a flow. Of the 137 main-dex TWAPs of 30 min to 24 h, 29
have ϕ ≥ 0.1% and 6 have ϕ ≥ 1%.

**Rate guesses (very noisy).** In 0.75 h there were 5 placements at ϕ ≥ 0.1% and 2 at ϕ ≥ 1%. That is roughly
**60–160/day at ϕ ≥ 0.1%** and **10–60/day at ϕ ≥ 1%** before the one-position-per-coin cap; the Poisson 95% range on 2
events alone is 8–230/day. Re-estimate after 24 h.
