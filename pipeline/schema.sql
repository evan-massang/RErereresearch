-- Research archive schema (DuckDB). Applied idempotently by pipeline/db.py.
--
-- Conventions
--   * Every table that can hold test data has is_synthetic. Synthetic rows exist
--     only to exercise the pipeline and are removed by `purge-synthetic`.
--     Child rows of a synthetic source (videos, transcripts, frames, ...) inherit
--     the flag through sources.is_synthetic.
--   * Paths are relative to the archive root (see pipeline/config.py).
--   * JSON columns keep the full raw payload so nothing an adapter returned is lost.
--   * Referential integrity is enforced in Python (DuckDB FKs block INSERT OR
--     REPLACE on referenced rows, which the idempotent ingesters rely on).

CREATE TABLE IF NOT EXISTS schema_meta (
    key   VARCHAR PRIMARY KEY,
    value VARCHAR
);

-- One row per piece of evidence: a video, a web page, a document, ...
CREATE TABLE IF NOT EXISTS sources (
    source_id       VARCHAR PRIMARY KEY,
    source_kind     VARCHAR NOT NULL,          -- video | webpage | document | other
    platform        VARCHAR,                   -- youtube | local | web | ... (adapter-reported)
    external_id     VARCHAR,                   -- platform-native ID, if any
    uri             VARCHAR NOT NULL,          -- what was requested
    canonical_url   VARCHAR,                   -- what the platform says it is
    title           VARCHAR,
    author          VARCHAR,                   -- channel / byline / uploader
    published_at    TIMESTAMPTZ,
    first_seen_at   TIMESTAMPTZ NOT NULL,
    last_fetched_at TIMESTAMPTZ,
    adapter         VARCHAR NOT NULL,          -- adapter that produced the row
    metadata        JSON,                      -- raw adapter payload (minus bulky fields)
    is_synthetic    BOOLEAN NOT NULL DEFAULT FALSE,
    notes           VARCHAR
);

-- Provenance log: every attempt to fetch/derive anything, including failures.
CREATE TABLE IF NOT EXISTS fetch_events (
    event_id       VARCHAR PRIMARY KEY,
    source_id      VARCHAR,                    -- NULL if the attempt failed before an ID was known
    stage          VARCHAR NOT NULL,           -- video_metadata | media | captions | transcribe | frames | web | ...
    adapter        VARCHAR NOT NULL,
    requested_uri  VARCHAR NOT NULL,
    status         VARCHAR NOT NULL,           -- ok | blocked | error
    error          VARCHAR,
    started_at     TIMESTAMPTZ NOT NULL,
    finished_at    TIMESTAMPTZ NOT NULL,
    tool_versions  JSON,
    details        JSON
);

-- Every file written into the archive, content-hashed.
CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id   VARCHAR PRIMARY KEY,
    source_id     VARCHAR NOT NULL,
    role          VARCHAR NOT NULL,            -- video | audio | info_json | subtitle | html | transcript_json | document | clip
    local_path    VARCHAR NOT NULL,
    sha256        VARCHAR NOT NULL,
    bytes         BIGINT,
    mime          VARCHAR,
    derived_from  VARCHAR,                     -- parent artifact_id, if derived
    created_at    TIMESTAMPTZ NOT NULL,
    details       JSON
);

-- Video-specific metadata (1:1 with sources where source_kind = 'video').
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
    available_captions JSON                   -- {"manual": [...langs], "auto": [...langs]}
);

CREATE TABLE IF NOT EXISTS transcripts (
    transcript_id VARCHAR PRIMARY KEY,
    source_id     VARCHAR NOT NULL,
    method        VARCHAR NOT NULL,            -- platform_manual | platform_auto | asr | imported
    language      VARCHAR,
    model         VARCHAR,                     -- ASR model name, if method = asr
    artifact_id   VARCHAR,                     -- caption/transcript file it came from
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
    avg_logprob   DOUBLE,                      -- ASR confidence, if available
    PRIMARY KEY (transcript_id, seq)
);

CREATE TABLE IF NOT EXISTS frames (
    frame_id     VARCHAR PRIMARY KEY,
    source_id    VARCHAR NOT NULL,
    timestamp_s  DOUBLE NOT NULL,
    method       VARCHAR NOT NULL,             -- timestamp | interval | scene
    local_path   VARCHAR NOT NULL,
    sha256       VARCHAR NOT NULL,
    width        INTEGER,
    height       INTEGER,
    created_at   TIMESTAMPTZ NOT NULL
);

-- A page can change; each fetch is a snapshot.
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
    extractor        VARCHAR,                  -- trafilatura | bs4_fallback
    word_count       INTEGER,
    language         VARCHAR,
    links            JSON,                     -- outbound links (for discovering further sources)
    page_metadata    JSON
);

CREATE TABLE IF NOT EXISTS traders (
    trader_id     VARCHAR PRIMARY KEY,
    display_name  VARCHAR NOT NULL,
    aliases       VARCHAR[],
    notes         VARCHAR,
    created_at    TIMESTAMPTZ NOT NULL,
    is_synthetic  BOOLEAN NOT NULL DEFAULT FALSE
);

-- Accounts/handles attributed to a trader, each with the source that supports it.
CREATE TABLE IF NOT EXISTS trader_identities (
    identity_id        VARCHAR PRIMARY KEY,
    trader_id          VARCHAR NOT NULL,
    platform           VARCHAR NOT NULL,
    handle             VARCHAR,
    url                VARCHAR,
    evidence_source_id VARCHAR,
    created_at         TIMESTAMPTZ NOT NULL,
    is_synthetic       BOOLEAN NOT NULL DEFAULT FALSE
);

-- Trade-level records. Values are as reported by the evidence; `status`
-- records how far they have been checked.
CREATE TABLE IF NOT EXISTS trades (
    trade_id      VARCHAR PRIMARY KEY,
    trader_id     VARCHAR,
    instrument    VARCHAR,
    asset_class   VARCHAR,
    direction     VARCHAR,                     -- long | short | unknown
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
    outcome       VARCHAR,                     -- win | loss | breakeven | open | unknown
    pnl           DOUBLE,
    pnl_unit      VARCHAR,
    status        VARCHAR NOT NULL,            -- reported | corroborated | verified | disputed | retracted
    confidence    DOUBLE,
    notes         VARCHAR,
    created_at    TIMESTAMPTZ NOT NULL,
    is_synthetic  BOOLEAN NOT NULL DEFAULT FALSE
);

-- Which observations support a trade record.
CREATE TABLE IF NOT EXISTS trade_evidence (
    trade_id       VARCHAR NOT NULL,
    observation_id VARCHAR NOT NULL,
    role           VARCHAR,                    -- entry | exit | size | pnl | screenshot | other
    PRIMARY KEY (trade_id, observation_id)
);

-- Atomic, evidence-linked statements extracted from a source. Each must point
-- at a source and should point at a precise locator (time range, frame,
-- transcript segment, or character span of a snapshot).
CREATE TABLE IF NOT EXISTS observations (
    observation_id    VARCHAR PRIMARY KEY,
    source_id         VARCHAR NOT NULL,
    kind              VARCHAR NOT NULL,        -- free text, e.g. claim | quote | metric | setup | screenshot
    content           VARCHAR NOT NULL,        -- the observation, in the extractor's words
    quote             VARCHAR,                 -- verbatim supporting text, if any
    quote_verified    BOOLEAN,                 -- quote found verbatim in the linked transcript/snapshot
    value             JSON,                    -- structured payload
    trader_id         VARCHAR,
    trade_id          VARCHAR,
    transcript_id     VARCHAR,
    segment_seq       INTEGER,
    start_s           DOUBLE,
    end_s             DOUBLE,
    frame_id          VARCHAR,
    snapshot_id       VARCHAR,
    char_start        INTEGER,
    char_end          INTEGER,
    extractor         VARCHAR NOT NULL,        -- human | claude | script:<name>
    extractor_version VARCHAR,
    confidence        DOUBLE,
    status            VARCHAR NOT NULL,        -- draft | reviewed | rejected
    created_at        TIMESTAMPTZ NOT NULL,
    is_synthetic      BOOLEAN NOT NULL DEFAULT FALSE
);

-- Free-form key/value annotations on any record.
CREATE TABLE IF NOT EXISTS annotations (
    annotation_id VARCHAR PRIMARY KEY,
    target_type   VARCHAR NOT NULL,            -- source | trader | trade | observation | frame | transcript | snapshot
    target_id     VARCHAR NOT NULL,
    key           VARCHAR NOT NULL,
    value         JSON,
    annotator     VARCHAR NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL,
    is_synthetic  BOOLEAN NOT NULL DEFAULT FALSE
);

-- Observations joined with where they came from.
CREATE OR REPLACE VIEW v_observation_provenance AS
SELECT
    o.observation_id, o.kind, o.content, o.quote, o.quote_verified, o.status,
    o.start_s, o.end_s, o.frame_id, o.snapshot_id, o.transcript_id, o.segment_seq,
    o.extractor, o.confidence,
    s.source_id, s.source_kind, s.platform, s.title AS source_title,
    COALESCE(s.canonical_url, s.uri) AS source_url, s.author AS source_author,
    s.published_at AS source_published_at, s.adapter,
    t.display_name AS trader,
    (o.is_synthetic OR s.is_synthetic) AS is_synthetic
FROM observations o
JOIN sources s USING (source_id)
LEFT JOIN traders t ON t.trader_id = o.trader_id;

-- Trades with how much evidence backs them.
CREATE OR REPLACE VIEW v_trade_summary AS
SELECT
    tr.*, t.display_name AS trader,
    COUNT(te.observation_id) AS evidence_count
FROM trades tr
LEFT JOIN traders t ON t.trader_id = tr.trader_id
LEFT JOIN trade_evidence te ON te.trade_id = tr.trade_id
GROUP BY ALL;
