# Defect List

## Find the Missing Connections

**Version:** 1.0
**Date:** 27 September 2026
**Status:** Open
**Owner:** `[QA Lead]`

Every entry was reproduced on the working tree at `6336d1f` unless stated otherwise.
"Blocking" means the user-visible result is wrong or a required behaviour does not
happen — not merely untidy.

---

## DEF-001 — `article_links` insert aborts on case-variant duplicates

**Severity:** Blocking
**Status:** Open — no fix committed
**Component:** `backend/app/repository.py` → `_replace_links` (line 106), called from
`store_analysis` (line 39)
**Constraint:** `uq_link` — `UNIQUE (source_page_id, target_normalized_title)`

### What happens

Any analysis whose links include two titles that differ only in case fails to persist
**at all**. The bulk insert hits a unique violation, the transaction rolls back, and zero
rows reach `article_links`.

The HTTP request still returns `200` with a complete, correct analysis body. The failure
is swallowed by the deliberate `except Exception` guard in `db.session_scope`, which
logs `Database write failed, continuing without cache` and returns `None`. That guard is
correct in principle — a database problem must never fail a request — but it means a
permanent write error is indistinguishable from a transient one at the API boundary.

### Reproduction

```text
POST /api/analyze  {"title": "Ada Lovelace"}
```

- 425 links extracted, but only **414** distinct lowercase keys.
- 11 keys collide, e.g. `alfred edward chalon`, `bernoulli number`, `dorothy stein`,
  `open library`, `victoria (british tv series)`.
- Backend log: `psycopg.errors.UniqueViolation: duplicate key value violates unique
  constraint "uq_link"` at `repository.py:106`.
- Afterwards: `select count(*) from article_links` → **0**.

### Why it is easy to miss

1. The response is a correct 200. Nothing in the payload signals the failure.
2. `get_article` and the analysis endpoints read from MediaWiki every time, so the cache
   is never actually consulted — the app behaves identically with the database
   completely empty. The feature is invisible either way.
3. `getsettings().database_enabled` is derived from `DATABASE_URL` being non-empty, not
   from the database being reachable, so `/api/health` reports
   `"database_enabled": true` against a database that does not exist.

### Fix direction

Deduplicate on `target_normalized_title` before the bulk insert in `_replace_links` —
the same set already deduplicates for the in-memory graph, so the persistence path is
where the gap is. A `postgresql insert ... on conflict do nothing` is the alternative
and keeps the statement single-round-trip. Either way, add a regression test that
analyses an article known to produce case variants.

### Verified-good behaviour worth keeping

With a `DATABASE_URL` pointing at a **non-existent** database, `/api/analyze` still
returns `200` with `total_links=425`. The graceful-degradation invariant in `AGENTS.md`
§5 holds. That is the one thing this defect does not break.

---

## DEF-002 — `database_enabled` reports configuration, not reachability

**Severity:** Minor
**Status:** Open
**Component:** `backend/app/config.py` (`Settings.database_enabled`), surfaced by
`/api/health`

`database_enabled` is `bool(database_url)`. A non-empty `DATABASE_URL` therefore reports
`true` even when the server is unreachable, the database is missing, or the credentials
are wrong — all three were observed. A health check that cannot fail is not a health
check. Consider having `/api/health` reflect the result of the existing `db.ping()` rather
than the presence of a string.

---

## Closed

None. The six undefined CSS custom properties previously listed here were re-checked on
27 September 2026 and are **not** a defect: `frontend/src/index.css` defines 54 tokens,
`frontend/src` references 43 distinct ones, and the intersection leaves **0** undefined.
`--missing`, `--oneway`, `--mutual`, `--seed` and every `*-soft` companion resolve. That
entry was stale and has been removed rather than fixed.
