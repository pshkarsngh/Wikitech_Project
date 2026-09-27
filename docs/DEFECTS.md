# Defect List

## Find the Missing Connections

**Version:** 1.2
**Date:** 27 September 2026
**Status:** All six entries fixed; **no entry verified against a deployed stack**
**Owner:** `unassigned`

Every entry was reproduced on the working tree at `6336d1f` unless stated otherwise.
"Blocking" means the user-visible result is wrong or a required behaviour does not
happen — not merely untidy.

DEF-006 was found on 27 September 2026, after `704e763`, by the first execution of the
persistence write path — that is B6 in `PUBLIC-READINESS.md`, and it is worth recording
where the list stopped being a review of a commit and became a record of a running
system. DEF-001, DEF-002 and DEF-004 are backends that were fixed but never deployed;
DEF-005 was a first-run schema defect, still conditional on `init.sql` being applied
before first start. The list is open because five entries are fixed and one is fixed in
this change, with none of it verified against a deployed stack.

---

## DEF-003 — The API client discarded `method` and `body`, so analysis never ran in a browser

**Severity:** Blocking
**Status:** **Fixed** — `frontend/src/api/client.js`, with 9 regression tests in
`frontend/src/api/client.test.js`
**Component:** `frontend/src/api/client.js` → `request`

### What happens

`request` destructured only `{ signal }` and then built a fresh `fetch` init object from
scratch, so every other property a caller passed was silently discarded:

```js
async function request(path, { signal } = {}) {
  response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Accept: 'application/json' },
    signal,
  })
```

`analyzeArticle` passes `{ method: 'POST', body: JSON.stringify({ title }), ... }`. All of
it was dropped. The browser therefore sent **`GET /api/analyze`**, and the backend —
which registers only `POST /api/analyze` — answered **405 Method Not Allowed**.

Verified against the application on 27 September 2026:

```text
GET  /api/analyze -> 405
POST /api/analyze -> 200
```

**The core feature of the application has never worked in a browser.** Every analysis
would have failed with "Request failed with status 405".

### Why it survived to 0.1.0

Four independent gaps, each of which had to be absent at the same time:

1. **No browser was ever opened.** `docs/UAT.md` §4 states this plainly and correctly: the
   Phase 6 evidence is deployed HTTP responses, not a rendered page.
2. **The smoke test bypasses the frontend entirely.** `deploy/smoke_test.py` talks HTTP to
   the API with `urllib`, so it exercises the route that works and never the client that
   calls it the wrong way.
3. **No frontend test made a request.** The vitest suite covered one badge component and
   the design tokens. `api/client.js` had no test at all.
4. **The exact-payload API tests assert the server, not the caller.** They pass with the
   client broken, because they do not use it.

This is the same failure class as UAT-01 (Cytoscape silently dropping every colour): a
layer that nothing observes, misbehaving in a way that produces no error at the layer
above it.

### Fix

`request` now forwards the whole init object and merges headers, so a caller can set
`method`, `body` and its own `Content-Type` while `Accept: application/json` stays the
default. The new test file asserts the outgoing request for every wrapper, which is the
layer where the information was being lost.

---

## DEF-004 — One-way detection reported false accusations on long articles

**Severity:** Blocking
**Status:** **Fixed** — `backend/app/services/mediawiki.py`,
`backend/app/services/analysis.py`, with 10 regression tests
**Component:** `MediaWikiClient.get_links_for_page_ids`, `detect_one_way_connections`

### What happens

`get_links_for_page_ids` declared a `max_links_per_page` parameter and **never used it**.
It sent `pllimit=max` with no continuation loop. `pllimit=max` is not "everything":

> The results limit can be set as high as 500 for regular users, or 5000 for users with
> the `apihighlimits` right.
> — <https://www.mediawiki.org/wiki/API:Properties>

So for an unauthenticated client the response stops at 500 links. Any target article with
more outgoing links has a tail the check cannot see. If the seed article sits in that tail,
`links_back` is `False` and the connection is reported as **ONE-WAY — incorrectly**, with
nothing in the response to indicate the answer was short.

Nothing covered it. `one_way_truncated` counts targets skipped by the *budget*, not links
missed inside a target, so the two were indistinguishable and neither was readable.

Among the 25 one-way targets reported for `Chandni Chowk` are `1951 Asian Games`, `1982
Asian Games` and `1987 Cricket World Cup` — exactly the kind of article that carries
several hundred links.

### Why it matters more than a normal bug

The product's second headline feature is an accusation that a specific article fails to
link back. Being wrong about that is worse than being silent about it, and the user has
no way to tell a verified finding from a guess.

### Fix

- `get_links_for_page_ids` paginates with the `continue` token and returns
  `PageLinks(titles, complete)`. `complete` is `False` only when a link actually had to be
  dropped, so a page with exactly 500 links and no continuation is still complete.
- A continuation that returns no new links raises `WikipediaError` rather than looping
  forever holding a concurrency slot.
- `detect_one_way_connections` **does not report a target as one-way when its links could
  not be read in full.** It counts it in `OneWayResult.incomplete_count`, leaves it out of
  `links_back`, and the connection map draws its edge `unchecked`.
- `AnalysisSummary.one_way_incomplete` reports the count, distinct from
  `one_way_truncated`, and the UI says "unverified" rather than implying a clean result.

The root fix is a bot password: `apihighlimits` raises the ceiling to 5000 and also makes
the deployment exempt from Wikimedia's rate limit. Recorded in `ARCHITECTURE.md` §12.

---

## DEF-005 — A superseded analysis could overwrite a newer one

**Severity:** Major
**Status:** **Fixed** — `frontend/src/context/AnalysisContext.jsx`, with 5 tests
**Component:** `AnalysisProvider.run`

### What happens

`run` had no `AbortController` and no request-identity check. Two analyses can be in
flight at once — submit article A, change your mind, submit B — and if B answers first,
A's slower response overwrites it. The screen then shows **A's** people, places, missing
connections and one-way list while the URL says B, with no error and nothing on the page
to tell the user.

This broke the project's own rule in `AGENTS.md` §7: *"results belong on screen only if
they belong to the current query."* `SearchPage` and `ConnectionMapPage` both implement
that guard correctly; the one fetch that carries the whole result did not.

### Fix

A monotonic request id in a ref. Both the success and the error path return early when a
newer run has started. An id check rather than an `AbortController` because `run` is a
`useCallback` with no effect cleanup to hang it from, and because `main.jsx` uses
`<StrictMode>`, which aborts a controller created outside an effect
(<https://github.com/react/react/issues/25962>).

---

## DEF-006 — The analysis cache was written under a key nothing ever looked up

**Severity:** Blocking — every request re-crawls Wikipedia, so the deployment spends
somebody else's quota for an answer it already has
**Status:** **Fixed** — `repository._upsert_article` now writes `title_key(...)`; 13
executed tests in `tests/test_persistence.py`
**Component:** `backend/app/repository.py` → `_upsert_article` (the write) against
`cached_analysis` (the read)

### What happens

The writer and the reader disagreed about the case of the lookup key:

```python
# _upsert_article
"normalized_title": normalize_title(article.title),   # "Ada Lovelace"
# cached_analysis
select(Article.analysis_payload, ...).where(Article.normalized_title == title_key(title))
                                                            # "ada lovelace"
```

`normalized_title` is `VARCHAR(512)` and PostgreSQL compares it case-sensitively, so the
read matched nothing — for any article. Verified directly against PostgreSQL 18: insert a
row with the display spelling, select it with the lowercase key, 0 rows.

The consequence is not a degraded cache but a dead one. `X-Cache` is always `miss`, the
one-hour `analysis_cache_ttl_seconds` never applies, and every `POST /api/analyze` spends
25–35 calls on Wikimedia to recompute an answer that is sitting in the database. Three
things had been built to serve this path and none of them ever fired: the
`articles.analysis_payload` column, the `ix_articles_normalized_title` index, and the
example query at the bottom of `database/init.sql`, which already compares the column to
`lower('ada lovelace')`.

### Why it survived

It was introduced in `704e763`, the same commit that added the read path. Every test in
the repository runs with an empty `DATABASE_URL`, so `cached_analysis` was only ever
exercised on its "no database configured" branch — which returns `None` and is correct.
`test_repository.py` pinned the freshness arithmetic and the payload round trip, neither of
which touches SQL.

This is finding B6 of `PUBLIC-READINESS.md` made concrete: the write path had never been
executed by a test. Writing that test found this on its first run, in the assertion that a
stored analysis comes back.

### Fix

One line. Both sides now call `title_key`, which is the point — `normalize_title` preserves
case and `title_key` does not, and this column is a lookup key, not a display title. The
column's meaning is unchanged: `init.sql` already documented the lowercase form.

**On a database that already holds rows:** every existing `normalized_title` holds the
display spelling and will never be matched again. That is a cache miss, not data loss — the
next analysis of each article rewrites the row with the key, and `article_links` and
`analysis_runs` are untouched. No migration is needed and no index has to be rebuilt. What
does happen, once, is that every cached answer is recomputed the first time it is asked for,
so a deploy that lands with the default 6 requests/minute limiter should expect a short
burst of Wikimedia calls and not read it as a regression.

---

## DEF-001 — `article_links` insert aborts on case-variant duplicates


**Severity:** Blocking
**Status:** **Fixed** in `e8a062a` — `repository._link_rows` collapses duplicates on
`uq_link`'s own key before the insert, with 8 regression tests in
`tests/test_repository.py`. Post-fix, the same article that wrote 0 rows writes 843.
**Component:** `backend/app/repository.py` → `_replace_links` (line 106), called from
`store_analysis` (line 39)
**Constraint:** `uq_link` — `UNIQUE (source_page_id, target_normalized_title)`

> Recorded as open until 27 September 2026. The entry below is the original report and is
> kept as the record of how it presented.

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
**Status:** **Fixed** in `e8a062a` — `HealthResponse` gained `database_reachable`
(`schemas.py`), fed by a real `SELECT 1` in `db.ping()` at `main.py`, and
`deploy/smoke_test.py` gates on it rather than on `database_enabled`. With a compliant
`User-Agent` the deployment now also honours Wikimedia's published limits; see
`ARCHITECTURE.md` §12.
**Component:** `backend/app/config.py` (`Settings.database_enabled`), surfaced by
`/api/health`

`database_enabled` is `bool(database_url)`. A non-empty `DATABASE_URL` therefore reports
`true` even when the server is unreachable, the database is missing, or the credentials
are wrong — all three were observed. A health check that cannot fail is not a health
check. Consider having `/api/health` reflect the result of the existing `db.ping()` rather
than the presence of a string.

---

## Closed

The six undefined CSS custom properties previously listed here were re-checked on
27 September 2026 and are **not** a defect: `frontend/src/index.css` defines 54 tokens,
`frontend/src` references 43 distinct ones, and the intersection leaves **0** undefined.

Five defects were closed earlier: **DEF-001** and **DEF-002** in `e8a062a`, and **DEF-003**,
**DEF-004** and **DEF-005** on 27 September 2026. **DEF-006** was found and fixed the same
day, while closing B6 of `PUBLIC-READINESS.md` — the first executed test of the write path
failed on its first run. **Six are closed and none is open.**

The next entries belong to `PUBLIC-READINESS.md`, which lists what is still missing rather
than what is broken: authentication, TLS, an application rate limit behind nginx, an
executed test for the `looks_like_person` classifier, and the licence.
