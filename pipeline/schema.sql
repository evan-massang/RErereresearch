-- Research archive schema (DuckDB), version 2. Applied idempotently by pipeline/db.py.
--
-- Conventions
--   * Every table that can hold test data has is_synthetic (directly or through
--     its parent). Synthetic rows exist only to exercise the pipeline and are
--     removed by `purge-synthetic`.
--   * NULL means "not visible / not recoverable". Values are never invented.
--   * Paths are relative to the project root (see pipeline/config.py).
--   * JSON columns keep the full raw payload so nothing an adapter returned is lost.
--   * Referential integrity and the evidence rules are enforced in Python
--     (DuckDB FKs block INSERT OR REPLACE on referenced rows).
--   * See docs/DATA_MODEL.md for the reasoning behind each table.

CREATE TABLE IF NOT EXISTS schema_meta (
    key   VARCHAR PRIMARY KEY,
    value VARCHAR
);

-- ===================================================================== sources

-- One row per piece of evidence: a video, a web page, a document, a search result citation...
CREATE TABLE IF NOT EXISTS sources (
    source_id       VARCHAR PRIMARY KEY,
    source_kind     VARCHAR NOT NULL,          -- video | webpage | document | search_citation | other
    platform        VARCHAR,                   -- youtube | kick | local | web | ... (adapter-reported)
    external_id     VARCHAR,
    uri             VARCHAR NOT NULL,          -- what was requested / cited
    canonical_url   VARCHAR,
    title           VARCHAR,
    author          VARCHAR,                   -- channel / byline / uploader
    published_at    TIMESTAMPTZ,
    first_seen_at   TIMESTAMPTZ NOT NULL,
    last_fetched_at TIMESTAMPTZ,               -- NULL = registered (e.g. cited by search) but never fetched
    adapter         VARCHAR NOT NULL,
    metadata        JSON,
    is_synthetic    BOOLEAN NOT NULL DEFAULT FALSE,
    notes           VARCHAR
);

-- Sources we know about but have not ingested yet (the research queue).
CREATE TABLE IF NOT EXISTS source_candidates (
    candidate_id        VARCHAR PRIMARY KEY,
    url                 VARCHAR NOT NULL,
    platform            VARCHAR,
    title               VARCHAR,
    published_text      VARCHAR,               -- as shown by the discovery source (not parsed)
    duration_text       VARCHAR,
    content_type        VARCHAR,               -- live_trading_session | recorded_trading_session | trade_recap | tutorial | interview | podcast | short_clip | profile | other | unknown
    trader_id           VARCHAR,               -- NULL if not attributed
    discovered_via      VARCHAR NOT NULL,      -- websearch:<query> | link_from:<source_id> | manual
    discovery_evidence  JSON,
    priority            VARCHAR,               -- high | medium | low
    status              VARCHAR NOT NULL,      -- candidate | queued | ingested | rejected | unavailable
    status_reason       VARCHAR,
    source_id           VARCHAR,               -- set once ingested
    created_at          TIMESTAMPTZ NOT NULL,
    updated_at          TIMESTAMPTZ NOT NULL,
    is_synthetic        BOOLEAN NOT NULL DEFAULT FALSE
);

-- Provenance log: every attempt to fetch/derive anything, including failures.
CREATE TABLE IF NOT EXISTS fetch_events (
    event_id       VARCHAR PRIMARY KEY,
    source_id      VARCHAR,
    stage          VARCHAR NOT NULL,
    adapter        VARCHAR NOT NULL,
    requested_uri  VARCHAR NOT NULL,
    status         VARCHAR NOT NULL,           -- ok | blocked | error
    error          VARCHAR,
    started_at     TIMESTAMPTZ NOT NULL,
    finished_at    TIMESTAMPTZ NOT NULL,
    tool_versions  JSON,
    details        JSON
);

-- Every file written into the project, content-hashed.
CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id   VARCHAR PRIMARY KEY,
    source_id     VARCHAR NOT NULL,
    role          VARCHAR NOT NULL,            -- video | audio | info_json | subtitle | html | document | transcript_json | clip
    local_path    VARCHAR NOT NULL,
    sha256        VARCHAR NOT NULL,
    bytes         BIGINT,
    mime          VARCHAR,
    derived_from  VARCHAR,
    created_at    TIMESTAMPTZ NOT NULL,
    details       JSON
);

CREATE TABLE IF NOT EXISTS videos (
    source_id     VARCHAR PRIMARY KEY,
    channel_id    VARCHAR,
    channel_name  VARCHAR,
    uploader      VARCHAR,
    upload_date   DATE,
    duration_s    DOUBLE,
    view_count    BIGINT,
    like_count    BIGINT,
    description   VARCHAR,
    tags          VARCHAR[],
    language      VARCHAR,
    chapters      JSON,
    available_captions JSON,                   -- {"manual": [...], "auto": [...]}
    was_live      BOOLEAN,                     -- recording of a live stream
    live_status   VARCHAR,                     -- yt-dlp live_status
    live_start_at TIMESTAMPTZ                  -- stream start: anchors video time to wall-clock time
);

CREATE TABLE IF NOT EXISTS transcripts (
    transcript_id VARCHAR PRIMARY KEY,
    source_id     VARCHAR NOT NULL,
    method        VARCHAR NOT NULL,            -- platform_manual | platform_auto | asr | imported
    language      VARCHAR,
    model         VARCHAR,
    artifact_id   VARCHAR,
    segment_count INTEGER,
    created_at    TIMESTAMPTZ NOT NULL,
    details       JSON
);

CREATE TABLE IF NOT EXISTS transcript_segments (
    transcript_id VARCHAR NOT NULL,
    seq           INTEGER NOT NULL,
    start_s       DOUBLE,
    end_s         DOUBLE,
    text          VARCHAR NOT NULL,
    avg_logprob   DOUBLE,
    PRIMARY KEY (transcript_id, seq)
);

-- Heuristic pointers into a transcript worth reviewing (entry/exit/skip language...).
-- These are triage, not evidence: a moment becomes evidence only once reviewed.
CREATE TABLE IF NOT EXISTS candidate_moments (
    moment_id      VARCHAR PRIMARY KEY,
    transcript_id  VARCHAR NOT NULL,
    seq            INTEGER NOT NULL,
    start_s        DOUBLE,
    category       VARCHAR NOT NULL,           -- entry | add | exit | partial | stop | rug | skip | missed | discovery | analysis | strategy
    matched_text   VARCHAR NOT NULL,
    review_status  VARCHAR NOT NULL,           -- unreviewed | confirmed | false_positive
    decision_id    VARCHAR,                    -- set when a reviewed moment produces a decision
    created_at     TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS frames (
    frame_id     VARCHAR PRIMARY KEY,
    source_id    VARCHAR NOT NULL,
    timestamp_s  DOUBLE NOT NULL,
    method       VARCHAR NOT NULL,             -- timestamp | interval | scene | window
    local_path   VARCHAR NOT NULL,
    sha256       VARCHAR NOT NULL,
    width        INTEGER,
    height       INTEGER,
    anchor_s     DOUBLE,                       -- decision time this frame was extracted around (window method)
    scene_score  DOUBLE,                       -- visual change score that triggered densification, if any
    created_at   TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS web_snapshots (
    snapshot_id      VARCHAR PRIMARY KEY,
    source_id        VARCHAR NOT NULL,
    fetched_at       TIMESTAMPTZ NOT NULL,
    http_status      INTEGER,
    final_url        VARCHAR,
    content_type     VARCHAR,
    html_artifact_id VARCHAR,
    content_sha256   VARCHAR NOT NULL,
    text             VARCHAR,
    extractor        VARCHAR,
    word_count       INTEGER,
    language         VARCHAR,
    links            JSON,
    page_metadata    JSON
);

-- ===================================================================== traders, tokens, narratives

CREATE TABLE IF NOT EXISTS traders (
    trader_id     VARCHAR PRIMARY KEY,
    slug          VARCHAR NOT NULL,            -- directory name under research/traders/
    display_name  VARCHAR NOT NULL,
    aliases       VARCHAR[],
    notes         VARCHAR,
    created_at    TIMESTAMPTZ NOT NULL,
    is_synthetic  BOOLEAN NOT NULL DEFAULT FALSE
);

-- Accounts/handles/wallets attributed to a trader. Nothing is assumed: each starts
-- as a 'lead' and is only 'verified' with primary-source linking evidence.
CREATE TABLE IF NOT EXISTS trader_identities (
    identity_id         VARCHAR PRIMARY KEY,
    trader_id           VARCHAR NOT NULL,
    platform            VARCHAR NOT NULL,      -- x | youtube | kick | twitch | telegram | discord | website | wallet | tracker_profile | other
    handle              VARCHAR,
    url                 VARCHAR,
    evidence_source_id  VARCHAR,
    verification_status VARCHAR NOT NULL,      -- lead | probable | verified | rejected
    verification_notes  VARCHAR,
    created_at          TIMESTAMPTZ NOT NULL,
    updated_at          TIMESTAMPTZ,
    is_synthetic        BOOLEAN NOT NULL DEFAULT FALSE
);

-- Tokens as identified in evidence. The mint may be unknown (NULL) until recovered.
CREATE TABLE IF NOT EXISTS tokens (
    token_id                  VARCHAR PRIMARY KEY,
    chain                     VARCHAR NOT NULL,     -- solana
    mint                      VARCHAR,
    ticker                    VARCHAR,
    name                      VARCHAR,
    launchpad                 VARCHAR,
    created_onchain_at        TIMESTAMPTZ,
    image_description         VARCHAR,
    identification            VARCHAR NOT NULL,     -- ca_visible | ticker_visible | spoken | onchain_match | other
    identification_confidence DOUBLE,
    notes                     VARCHAR,
    created_at                TIMESTAMPTZ NOT NULL,
    is_synthetic              BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS narratives (
    narrative_id       VARCHAR PRIMARY KEY,
    title              VARCHAR NOT NULL,
    description        VARCHAR,
    origin_description VARCHAR,                -- who/what originated the story, as evidenced
    origin_source_id   VARCHAR,
    first_seen_at      TIMESTAMPTZ,            -- earliest evidenced appearance (wall-clock)
    category           VARCHAR,                -- free text until a coding scheme emerges from evidence
    notes              VARCHAR,
    created_at         TIMESTAMPTZ NOT NULL,
    is_synthetic       BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS token_narratives (
    token_id       VARCHAR NOT NULL,
    narrative_id   VARCHAR NOT NULL,
    relation       VARCHAR NOT NULL,           -- canonical | copycat | derivative | unclear
    observation_id VARCHAR,
    PRIMARY KEY (token_id, narrative_id)
);

-- ===================================================================== decisions (the trader dataset)

-- One row per observed decision point. Reasons are kept in three separate
-- columns so what was SAID, what was SEEN and what WE INFER never merge.
CREATE TABLE IF NOT EXISTS decisions (
    decision_id            VARCHAR PRIMARY KEY,
    trader_id              VARCHAR NOT NULL,
    source_id              VARCHAR NOT NULL,    -- the video/session/page where it is observed
    video_ts_s             DOUBLE,              -- position in the video
    decision_wallclock     TIMESTAMPTZ,         -- real-world time, if recoverable
    wallclock_basis        VARCHAR,             -- onchain_tx | stream_start_offset | on_screen_clock
    decision               VARCHAR NOT NULL,    -- BUY | ADD | SKIP | WATCH | HOLD | PARTIAL_SELL | SELL | MISSED
    token_id               VARCHAR,             -- NULL if the token cannot be identified
    trade_id               VARCHAR,             -- trade episode (BUY/ADD/SELL of one token)
    discovery_channel      VARCHAR,             -- how the token reached attention, if observable
    stated_reason          VARCHAR,             -- what the trader SAID (the quote itself lives in observations)
    observed_context       VARCHAR,             -- what the SCREEN showed, described
    inferred_reason        VARCHAR,             -- OUR inference; never presented as the trader's reason
    reason_codes           VARCHAR[],           -- coded later, from evidence
    chart_state            VARCHAR,
    narrative_id           VARCHAR,
    position_size          DOUBLE,
    position_size_unit     VARCHAR,             -- SOL | USD | pct_of_wallet | tokens
    result_pct             DOUBLE,
    result_sol             DOUBLE,
    result_basis           VARCHAR,             -- shown | said | onchain | computed
    extraction_confidence  DOUBLE NOT NULL,     -- confidence that this decision happened as recorded
    extractor              VARCHAR NOT NULL,    -- human | claude | script:<name>
    extractor_version      VARCHAR,
    status                 VARCHAR NOT NULL,    -- draft | reviewed | rejected
    notes                  VARCHAR,
    created_at             TIMESTAMPTZ NOT NULL,
    is_synthetic           BOOLEAN NOT NULL DEFAULT FALSE
);

-- Metric readings anchored to a decision, each with its provenance. Several
-- readings of one metric at different offsets give velocity/acceleration.
-- A metric that was not visible simply has no row (never a guessed value).
CREATE TABLE IF NOT EXISTS decision_metrics (
    reading_id      VARCHAR PRIMARY KEY,
    decision_id     VARCHAR NOT NULL,
    metric          VARCHAR NOT NULL,          -- canonical name (pipeline/decisions.py METRICS) or x_<tool_specific>
    value_num       DOUBLE,
    value_text      VARCHAR,                   -- exactly as displayed/said, e.g. "12.4K"
    unit            VARCHAR,
    metric_window   VARCHAR,                   -- e.g. 5m | 1h | lifetime | unknown (as the tool defines it)
    observed_via    VARCHAR NOT NULL,          -- screen | said | onchain | derived
    frame_id        VARCHAR,
    observation_id  VARCHAR,
    as_of_offset_s  DOUBLE,                    -- reading time minus decision time (negative = before)
    confidence      DOUBLE,
    notes           VARCHAR
);

-- Trade episodes (one token, one trader, entry→exit).
CREATE TABLE IF NOT EXISTS trades (
    trade_id      VARCHAR PRIMARY KEY,
    trader_id     VARCHAR,
    token_id      VARCHAR,
    source_id     VARCHAR,                     -- session where it was observed, if any
    observed_via  VARCHAR,                     -- video | onchain | claimed
    instrument    VARCHAR,
    asset_class   VARCHAR,
    direction     VARCHAR,
    entry_time    TIMESTAMPTZ,
    entry_price   DOUBLE,
    exit_time     TIMESTAMPTZ,
    exit_price    DOUBLE,
    stop_price    DOUBLE,
    target_price  DOUBLE,
    size          DOUBLE,
    size_unit     VARCHAR,
    currency      VARCHAR,
    timeframe     VARCHAR,
    outcome       VARCHAR,                     -- win | loss | breakeven | open | rug | unknown
    pnl           DOUBLE,
    pnl_unit      VARCHAR,
    status        VARCHAR NOT NULL,            -- reported | corroborated | verified | disputed | retracted
    confidence    DOUBLE,
    notes         VARCHAR,
    created_at    TIMESTAMPTZ NOT NULL,
    is_synthetic  BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS trade_evidence (
    trade_id       VARCHAR NOT NULL,
    observation_id VARCHAR NOT NULL,
    role           VARCHAR,
    PRIMARY KEY (trade_id, observation_id)
);

-- Atomic evidence from one source, pinned to a locator. modality separates
-- what the trader SAID, what the SCREEN showed, and what the trader DID.
CREATE TABLE IF NOT EXISTS observations (
    observation_id    VARCHAR PRIMARY KEY,
    source_id         VARCHAR NOT NULL,
    modality          VARCHAR NOT NULL,        -- said | screen | action | onchain | document
    kind              VARCHAR NOT NULL,        -- free text, e.g. quote | metric | setup | identity_link | secondary_claim
    content           VARCHAR NOT NULL,
    quote             VARCHAR,
    quote_verified    BOOLEAN,
    value             JSON,
    trader_id         VARCHAR,
    token_id          VARCHAR,
    decision_id       VARCHAR,
    trade_id          VARCHAR,
    transcript_id     VARCHAR,
    segment_seq       INTEGER,
    start_s           DOUBLE,
    end_s             DOUBLE,
    frame_id          VARCHAR,
    snapshot_id       VARCHAR,
    char_start        INTEGER,
    char_end          INTEGER,
    extractor         VARCHAR NOT NULL,
    extractor_version VARCHAR,
    confidence        DOUBLE,
    status            VARCHAR NOT NULL,        -- draft | reviewed | rejected
    created_at        TIMESTAMPTZ NOT NULL,
    is_synthetic      BOOLEAN NOT NULL DEFAULT FALSE
);

-- ===================================================================== findings & hypotheses

-- Rule-level conclusions. evidence_type is fixed at creation: an inferred finding
-- is never edited into a validated one; a new validated finding is created and
-- linked derived_from the inferred one.
CREATE TABLE IF NOT EXISTS findings (
    finding_id      VARCHAR PRIMARY KEY,
    trader_id       VARCHAR,                   -- NULL = cross-trader
    funnel_stage    VARCHAR NOT NULL,          -- discovery | attention | narrative | matching | safety | market | entry | sizing | hold | exit | risk | tooling | meta
    evidence_type   VARCHAR NOT NULL,          -- stated | observed | inferred | validated
    statement       VARCHAR NOT NULL,
    n_supporting    INTEGER,                   -- e.g. 35 ...
    n_observable    INTEGER,                   -- ... of 42 observable cases
    n_contradicting INTEGER,
    confidence      DOUBLE,
    status          VARCHAR NOT NULL,          -- open | supported | weakened | rejected | superseded
    superseded_by   VARCHAR,
    notes           VARCHAR,
    created_at      TIMESTAMPTZ NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL,
    is_synthetic    BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS finding_evidence (
    finding_id    VARCHAR NOT NULL,
    evidence_kind VARCHAR NOT NULL,            -- observation | decision | finding | sim_run
    evidence_id   VARCHAR NOT NULL,
    relation      VARCHAR NOT NULL,            -- supports | contradicts | derived_from | validated_by
    note          VARCHAR,
    PRIMARY KEY (finding_id, evidence_kind, evidence_id, relation)
);

-- Measurable hypotheses. Every iteration states WHY (rationale) and what it is
-- based on (findings) or what failure prompted it (motivated_by_run_id).
CREATE TABLE IF NOT EXISTS hypotheses (
    hypothesis_id         VARCHAR PRIMARY KEY,
    parent_id             VARCHAR,
    trader_scope          VARCHAR,             -- trader_id or 'cross'
    statement             VARCHAR NOT NULL,
    measurable_definition VARCHAR NOT NULL,
    rationale             VARCHAR NOT NULL,
    motivated_by_run_id   VARCHAR,
    status                VARCHAR NOT NULL,    -- proposed | testing | rejected | supported_validation | holdout_passed | holdout_failed | retired
    created_at            TIMESTAMPTZ NOT NULL,
    updated_at            TIMESTAMPTZ NOT NULL,
    is_synthetic          BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS hypothesis_basis (
    hypothesis_id VARCHAR NOT NULL,
    finding_id    VARCHAR NOT NULL,
    PRIMARY KEY (hypothesis_id, finding_id)
);

-- Human observation -> measurable feature.
CREATE TABLE IF NOT EXISTS features (
    feature_name      VARCHAR PRIMARY KEY,
    human_observation VARCHAR NOT NULL,        -- e.g. "buyers keep stepping in"
    definition        VARCHAR NOT NULL,
    inputs            VARCHAR,
    min_resolution_s  DOUBLE,                  -- finest time resolution the inputs support
    implementation    VARCHAR,                 -- python dotted path
    status            VARCHAR NOT NULL,        -- candidate | in_use | retired
    notes             VARCHAR,
    created_at        TIMESTAMPTZ NOT NULL,
    is_synthetic      BOOLEAN NOT NULL DEFAULT FALSE
);

-- ===================================================================== evaluation discipline

-- Chronological splits. A holdout is evaluated once, then burned.
CREATE TABLE IF NOT EXISTS data_splits (
    split_set     VARCHAR NOT NULL,
    split_name    VARCHAR NOT NULL,            -- train | validation | holdout
    start_at      TIMESTAMPTZ NOT NULL,
    end_at        TIMESTAMPTZ NOT NULL,        -- exclusive
    status        VARCHAR NOT NULL,            -- open | burned
    burned_at     TIMESTAMPTZ,
    burned_by_run VARCHAR,
    notes         VARCHAR,
    created_at    TIMESTAMPTZ NOT NULL,
    is_synthetic  BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (split_set, split_name)
);

CREATE TABLE IF NOT EXISTS sim_runs (
    run_id              VARCHAR PRIMARY KEY,
    hypothesis_id       VARCHAR,
    strategy_name       VARCHAR NOT NULL,
    strategy_hash       VARCHAR NOT NULL,
    strategy_spec       JSON,
    split_set           VARCHAR,
    split_name          VARCHAR,
    data_start          TIMESTAMPTZ,
    data_end            TIMESTAMPTZ,
    execution_model     JSON,
    code_version        VARCHAR,
    dataset_fingerprint VARCHAR,
    metrics_imitation   JSON,                  -- Objective A, kept separate
    metrics_performance JSON,                  -- Objective B, kept separate
    n_trades            INTEGER,
    notes               VARCHAR,
    created_at          TIMESTAMPTZ NOT NULL,
    is_synthetic        BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS holdout_log (
    event_id      VARCHAR PRIMARY KEY,
    split_set     VARCHAR NOT NULL,
    split_name    VARCHAR NOT NULL,
    run_id        VARCHAR,
    strategy_hash VARCHAR,
    action        VARCHAR NOT NULL,            -- evaluated | refused
    reason        VARCHAR,
    logged_at     TIMESTAMPTZ NOT NULL
);

-- Free-form key/value annotations on any record.
CREATE TABLE IF NOT EXISTS annotations (
    annotation_id VARCHAR PRIMARY KEY,
    target_type   VARCHAR NOT NULL,
    target_id     VARCHAR NOT NULL,
    key           VARCHAR NOT NULL,
    value         JSON,
    annotator     VARCHAR NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL,
    is_synthetic  BOOLEAN NOT NULL DEFAULT FALSE
);


-- ===================================================================== on-chain wallet activity

-- Every signature seen for a tracked wallet (including failed transactions).
CREATE TABLE IF NOT EXISTS wallet_signatures (
    wallet      VARCHAR NOT NULL,
    signature   VARCHAR NOT NULL,
    slot        BIGINT,
    block_time  TIMESTAMPTZ,
    failed      BOOLEAN NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (wallet, signature)
);

-- Swaps decoded from the wallet's own balance changes (venue-agnostic):
-- token delta of the wallet for a mint vs its SOL (+WSOL) delta, fee excluded.
CREATE TABLE IF NOT EXISTS wallet_swaps (
    wallet       VARCHAR NOT NULL,
    signature    VARCHAR NOT NULL,
    mint         VARCHAR NOT NULL,
    slot         BIGINT,
    block_time   TIMESTAMPTZ,
    side         VARCHAR NOT NULL,          -- buy | sell
    token_amount DOUBLE NOT NULL,           -- ui amount (decimals applied)
    sol_amount   DOUBLE,                    -- SOL paid/received excluding the tx fee
    fee_sol      DOUBLE,
    price_sol    DOUBLE,                    -- sol_amount / token_amount
    programs     VARCHAR[],
    fetched_at   TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (signature, mint, wallet)
);

-- ===================================================================== views

CREATE OR REPLACE VIEW v_observation_provenance AS
SELECT
    o.observation_id, o.modality, o.kind, o.content, o.quote, o.quote_verified, o.status,
    o.start_s, o.end_s, o.frame_id, o.snapshot_id, o.transcript_id, o.segment_seq,
    o.decision_id, o.extractor, o.confidence,
    s.source_id, s.source_kind, s.platform, s.title AS source_title,
    COALESCE(s.canonical_url, s.uri) AS source_url, s.author AS source_author,
    s.published_at AS source_published_at, s.adapter,
    t.display_name AS trader, o.trader_id,
    (o.is_synthetic OR s.is_synthetic) AS is_synthetic
FROM observations o
JOIN sources s USING (source_id)
LEFT JOIN traders t ON t.trader_id = o.trader_id;

-- The structured trader dataset, one row per decision, using for each metric the
-- reading closest to (and preferably not after) the decision. NULL = not observed.
CREATE OR REPLACE VIEW v_decisions_wide AS
WITH ranked AS (
    SELECT m.*,
           row_number() OVER (
               PARTITION BY decision_id, metric
               ORDER BY CASE WHEN COALESCE(as_of_offset_s, 0) <= 0 THEN 0 ELSE 1 END,
                        abs(COALESCE(as_of_offset_s, 0)),
                        confidence DESC NULLS LAST) AS rn
    FROM decision_metrics m
), best AS (SELECT * FROM ranked WHERE rn = 1)
SELECT
    d.decision_id, tr.slug AS trader, d.source_id, s.title AS video_title,
    COALESCE(s.canonical_url, s.uri) AS video_url, d.video_ts_s, d.decision_wallclock,
    d.decision, tk.ticker, tk.name AS token_name, tk.mint, d.trade_id,
    max(b.value_num) FILTER (WHERE b.metric = 'market_cap_usd')   AS market_cap_usd,
    max(b.value_num) FILTER (WHERE b.metric = 'liquidity_usd')    AS liquidity_usd,
    max(b.value_num) FILTER (WHERE b.metric = 'token_age_s')      AS token_age_s,
    max(b.value_num) FILTER (WHERE b.metric = 'txns')             AS txns,
    max(b.value_num) FILTER (WHERE b.metric = 'buys')             AS buys,
    max(b.value_num) FILTER (WHERE b.metric = 'sells')            AS sells,
    max(b.value_num) FILTER (WHERE b.metric = 'volume_usd')       AS volume_usd,
    max(b.value_num) FILTER (WHERE b.metric = 'holders')          AS holders,
    max(b.value_num) FILTER (WHERE b.metric = 'top10_pct')        AS top10_pct,
    max(b.value_num) FILTER (WHERE b.metric = 'dev_pct')          AS dev_pct,
    max(b.value_num) FILTER (WHERE b.metric = 'snipers_pct')      AS snipers_pct,
    max(b.value_num) FILTER (WHERE b.metric = 'insiders_pct')     AS insiders_pct,
    max(b.value_num) FILTER (WHERE b.metric = 'bundles_pct')      AS bundles_pct,
    max(b.value_num) FILTER (WHERE b.metric = 'pro_traders')      AS pro_traders,
    max(b.value_num) FILTER (WHERE b.metric = 'viewers')          AS viewers,
    max(b.value_num) FILTER (WHERE b.metric = 'bonding_curve_pct') AS bonding_curve_pct,
    d.chart_state, n.title AS narrative, n.first_seen_at AS narrative_first_seen_at,
    max(b.value_num) FILTER (WHERE b.metric = 'social_posts_per_min') AS social_posts_per_min,
    d.stated_reason, d.observed_context, d.inferred_reason, d.discovery_channel,
    d.position_size, d.position_size_unit, d.result_pct, d.result_sol, d.result_basis,
    d.extraction_confidence, d.status,
    (d.is_synthetic OR s.is_synthetic) AS is_synthetic
FROM decisions d
JOIN sources s ON s.source_id = d.source_id
LEFT JOIN traders tr ON tr.trader_id = d.trader_id
LEFT JOIN tokens tk ON tk.token_id = d.token_id
LEFT JOIN narratives n ON n.narrative_id = d.narrative_id
LEFT JOIN best b ON b.decision_id = d.decision_id
GROUP BY ALL;

CREATE OR REPLACE VIEW v_findings AS
SELECT
    f.*, t.slug AS trader,
    count(*) FILTER (WHERE fe.relation = 'supports')     AS n_links_supporting,
    count(*) FILTER (WHERE fe.relation = 'contradicts')  AS n_links_contradicting,
    count(*) FILTER (WHERE fe.relation = 'derived_from') AS n_links_derived_from,
    count(*) FILTER (WHERE fe.relation = 'validated_by') AS n_links_validated_by
FROM findings f
LEFT JOIN traders t ON t.trader_id = f.trader_id
LEFT JOIN finding_evidence fe ON fe.finding_id = f.finding_id
GROUP BY ALL;

CREATE OR REPLACE VIEW v_trade_summary AS
SELECT
    tr.*, t.display_name AS trader, tk.ticker, tk.mint,
    COUNT(te.observation_id) AS evidence_count
FROM trades tr
LEFT JOIN traders t ON t.trader_id = tr.trader_id
LEFT JOIN tokens tk ON tk.token_id = tr.token_id
LEFT JOIN trade_evidence te ON te.trade_id = tr.trade_id
GROUP BY ALL;
