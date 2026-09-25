-- Find the Missing Connections
-- PostgreSQL schema. Mirrors the SQLAlchemy models in backend/app/models.py.
--
--   psql -U postgres -f database/init.sql
--
-- The database is a cache. The API works without it, it just does not remember
-- previous analyses.

BEGIN;

CREATE TABLE IF NOT EXISTS articles (
    page_id          BIGINT       PRIMARY KEY,
    title            VARCHAR(512) NOT NULL UNIQUE,
    normalized_title VARCHAR(512) NOT NULL,
    description      TEXT,
    extract          TEXT,
    url              TEXT,
    length           INTEGER,
    fetched_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_articles_normalized_title
    ON articles (normalized_title);

-- A directed link from one article to another, as extracted from the wikitext.
-- "exists = false" is a red link: the target is mentioned but has no article.
CREATE TABLE IF NOT EXISTS article_links (
    id                     BIGSERIAL    PRIMARY KEY,
    source_page_id         BIGINT       NOT NULL
                           REFERENCES articles (page_id) ON DELETE CASCADE,
    target_title           VARCHAR(512) NOT NULL,
    target_normalized_title VARCHAR(512) NOT NULL,
    target_page_id         BIGINT,
    exists                 BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at             TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT uq_link UNIQUE (source_page_id, target_normalized_title)
);

-- How often a missing target is linked to, which is the useful first cut at
-- "which red link matters most".
CREATE INDEX IF NOT EXISTS ix_article_links_target_normalized_title
    ON article_links (target_normalized_title);

CREATE INDEX IF NOT EXISTS ix_article_links_missing
    ON article_links (target_normalized_title) WHERE NOT exists;

-- One row per analysis, so runs can be listed without re-reading Wikipedia.
CREATE TABLE IF NOT EXISTS analysis_runs (
    id             BIGSERIAL    PRIMARY KEY,
    seed_page_id   BIGINT,
    seed_title     VARCHAR(512) NOT NULL,
    total_links    INTEGER      NOT NULL DEFAULT 0,
    total_missing  INTEGER      NOT NULL DEFAULT 0,
    total_one_way  INTEGER      NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_analysis_runs_created_at
    ON analysis_runs (created_at DESC);

CREATE INDEX IF NOT EXISTS ix_analysis_runs_seed_title
    ON analysis_runs (seed_title);

-- seed_page_id is not a foreign key: an analysis can be stored for an article
-- that was deleted from Wikipedia in the meantime, and the run history should
-- survive that.

COMMIT;

-- Example queries
-- --------------
-- Most linked missing targets (red links) across every analysed article:
--
--   SELECT target_title, COUNT(DISTINCT source_page_id) AS mentioned_by
--   FROM article_links
--   WHERE NOT exists
--   GROUP BY target_title
--   ORDER BY mentioned_by DESC
--   LIMIT 25;
--
-- Articles analysed more than once, with their averages:
--
--   SELECT seed_title,
--          COUNT(*)              AS runs,
--          AVG(total_missing)   AS avg_missing,
--          AVG(total_one_way)   AS avg_one_way
--   FROM analysis_runs
--   GROUP BY seed_title
--   HAVING COUNT(*) > 1
--   ORDER BY avg_missing DESC;
--
-- Everything a single article links to, missing or not:
--
--   SELECT l.target_title, l.exists, a.title AS source_title
--   FROM article_links l
--   JOIN articles a ON a.page_id = l.source_page_id
--   WHERE a.normalized_title = lower('ada lovelace')
--   ORDER BY l.exists, l.target_title;
