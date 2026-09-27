# Public Readiness Audit

## Find the Missing Connections

**Version:** 1.4
**Date:** 27 September 2026
**Base commit:** `e8a062a`
**Status:** Open — see the implementation note below
**Scope:** What stands between this codebase and other people using it in production
**Owner:** `unassigned`
**Companion documents:** `HARDENING.md` (researched fixes), `DEFECTS.md` (defect record)

> **Current as of 27 September 2026, at `704e763` plus the B6 change.** Closed: **A1**
> (rate limited at nginx), **A2** (the read path — `articles.analysis_payload` caches the
> computed result with a 1-hour TTL and `X-Cache` names the path that answered; *broken
> until DEF-006, see B6*), **A4** (retention on `analysis_runs` plus log rotation),
> **B1**, **B2**, **B3**, **B6** (13 executed tests, which is what found DEF-006),
> **C1** (headers, verified present on `/assets/` in a real container), **C3**, **C4**,
> **C5**, **C8**, **C9**, **C11**, **D1** (column-level schema drift), **D2**
> (`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, proven against a live PostgreSQL), and
> **A3** in part — `ANALYSIS_API_KEY` gates the four crawl routes, which is a shared key
> and deliberately not identity (`ARCHITECTURE.md` §10.1).
>
> Still open: **A3**'s remaining half — no request logging, no metrics, no alerting, and
> one IP as the only unit of punishment; **B4** the seed link-pagination loop has no
> iteration cap; **B7** `looks_like_person` can never return `True`; **C2** no TLS;
> **C7** no cancellation on disconnect; **C6** a 120s nginx read timeout is a ceiling the
> worst case can still exceed, because nothing bounds total analysis wall-clock;
> **C12** the SQLite fallback
> `ARCHITECTURE.md` §11.8 promises is still impossible; **C13** no `LICENSE` or root
> `README.md`; **D4** the classifier; **D5** the
> remaining documentation drift.
>
> The suite is **205 backend with a database (192 without, one module skipped) + 47
> frontend**. Nothing in this list has been verified against a deployed stack.



---

## 1. Why this document exists

The project is at `0.1.0-6336d1f` and is a complete, working, tested application. It is
also, right now, an **unauthenticated application that fans every request out to a
third-party API and writes to a database nobody reads.** Those are two different
statements and both are true.

This audit was requested in one question: *other people are going to use this — what is
missing?* It answers that, and nothing else. It is not a phase checklist, it is not a
defect list, and it does not replace `DEFECTS.md`. It is the list of things that were
never built because the project so far has only ever had one user.

**Code is truth.** Every finding below cites `file:line` and was read out of the source on
27 September 2026. Where this document and the code disagree, this document is wrong —
fix it in the same commit as whatever else you touched.

---

## 2. Method, and what was *not* verified

Read the whole tree: 104 tracked files, all of `backend/app`, `backend/tests`, `frontend/src`,
`database`, `deploy`, `.github/workflows/ci.yml`, and the eight existing `docs/` files.
Every claim was verified by reading the source and, where the finding was mechanical, by
running a search across it.

Baseline state at the time of writing, all re-run to confirm:

| Check | Command | Result |
| ----- | ------- | ------ |
| Backend suite | `pytest` (from `backend/`) | **85 passed** in 2.06s |
| Frontend suite | `npm run test` (from `frontend/`) | **11 passed**, 2 files |
| Frontend lint | `npm run lint` | 0 errors, 4 warnings |
| Working tree | `git status --porcelain -uall` | clean, 104 tracked, 0 untracked |

**Not verified, and not claimed:**

- **No browser was opened.** Nothing here asserts that a rendered pixel is correct. This
  repository has no browser automation (`AGENTS.md` §3) and none was added. Findings about
  colours, highlighting and rendering are absent for that reason, and the absence is not
  evidence of correctness.
- **No test was run against a live PostgreSQL.** `conftest.py:11` and `test_api.py:18` both
  set `database_url=""`, so no test in the 85 opens a connection. Every database finding
  below is from reading the code, not from observing a failure.
- **No load, abuse or timing test was run.** The availability findings in §C are derived
  from the code's structure and the documented budgets, not from measurement.
- **The deployed stacks were not touched.** Whatever is running on `:8080` and `:8082` was
  left exactly as it was.

---

## 3. How to read the findings

Each finding has an ID, a severity, and a status. IDs are stable — reference them in
commits and in `DEFECTS.md`.

| Severity | Meaning |
| -------- | ------- |
| **Blocker** | Do not let another user in until this is fixed. Either it is a legal exposure, a third-party abuse vector, or it produces wrong answers. |
| **Bug** | Wrong or fragile behaviour a user can hit today, at any scale. |
| **Hardening** | Not exploitable as written, but it removes a defence that public traffic will eventually need. |
| **Gap** | A promised capability or safety net that does not exist. |

| Status | Meaning |
| ------ | ------- |
| `Open` | Confirmed present in the source. Not fixed. |
| `Open (cosmetic)` | Real, user-visible, does not block. |
| `Verified correct` | Checked and found to be right. Recorded so nobody "fixes" it. |

### Summary

| ID | Finding | Severity | Status |
| -- | ------- | -------- | ------ |
| A1 | No rate limiting on any route | Blocker | Fixed in `704e763` — nginx `limit_req` |
| A2 | The database is write-only; it caches nothing | Blocker | Fixed in `704e763` — and broken until DEF-006 |
| A3 | No authentication, identity, or abuse visibility | Blocker | Partly fixed — shared key on the crawl routes; no identity, no visibility |
| A4 | Nothing bounds database or log growth | Blocker | Fixed in `704e763` — retention + log rotation |
| B1 | One-way detection reports false `ONE-WAY` | Bug | Fixed in `704e763` — paginated reverse read |
| B2 | `/connections/map` classifies missing titles twice | Bug | Fixed in `704e763` — one `classify_links` call |
| B3 | Stale-response race overwrites the current result | Bug | Fixed in `704e763` — request-identity guard |
| B4 | Link-pagination loop has no iteration cap | Bug | Open |
| B5 | `session_scope` mislabels code bugs as DB failures | Bug | Fixed |
| B6 | The entire database write path is untested | Bug | Fixed — found DEF-006 on the first run |
| B7 | `looks_like_person` can never return `True` | Bug | Open |
| C1 | No security headers on any response | Hardening | Fixed in `704e763` — `security-headers.conf` |
| C2 | No TLS | Hardening | Open — infrastructure |
| C3 | `/articles/resolve` bounds the list, not the items | Hardening | Fixed in `704e763` — `BatchedTitle` |
| C4 | No request body size limit | Hardening | Fixed in `704e763` — 64k at both layers |
| C5 | `--forwarded-allow-ips '*'` trusts any client | Hardening | Fixed in `704e763` — narrowed to subnets |
| C6 | Slow analyses 502 while the backend keeps working | Hardening | Open — 120s is a ceiling, not a bound |
| C7 | No cancellation when the client disconnects | Hardening | Open |
| C8 | Retries ignore `Retry-After` | Hardening | Fixed in `704e763` |
| C9 | No React error boundary | Hardening | Fixed in `704e763` — `ErrorBoundary` |
| C10 | Dev database publishes 5432 with a default password | Hardening | Fixed |
| C11 | Staging `DATABASE_URL` has no `connect_timeout` | Hardening | Fixed in `704e763` |
| C12 | The SQLite fallback in `ARCHITECTURE.md` §11.8 cannot work | Hardening | Open |
| C13 | No `LICENSE`, no root `README.md` | Gap | Open |
| D1 | CI's schema job only compares table *names* | Gap | Fixed in `704e763` — columns too |
| D2 | No working path to add a column to an existing table | Gap | Fixed in `704e763` — `ADD COLUMN IF NOT EXISTS` |
| D3 | UAT-02's cosmetic half is still open | Gap | Fixed |
| D4 | Classifier under-detects people heavily | Gap | Open (cosmetic) |
| D5 | `DEFECTS.md` and `CHECKLIST.md` are materially stale | Gap | Partly closed; the rest open |

---

# A. Blockers

## A1 — No rate limiting on any route

**Severity:** Blocker · **Status:** **Fixed** in `704e763` — nginx `limit_req` on the analysis and connection routes

`PRD.md` NFR-08 and `TRD-63` both require rate limiting. It does not exist. A search of
`backend/app`, `frontend/src` and `deploy` for `rate limit`, `limiter`, `throttle` and
`slowapi` returns nothing.

`config.py:28` sets `max_concurrent_requests: int = 4`, which reads like a limiter and is
not one. It is an `asyncio.Semaphore(4)` created in `MediaWikiClient.__init__`
(`services/mediawiki.py:100`) that caps **outbound** MediaWiki concurrency inside a single
process. It places no limit whatsoever on inbound requests.

The consequence is not only that this host can be overloaded. Every anonymous request
fans out into 10–20 calls against Wikipedia and Wikidata. A script looping
`POST /api/analyze` makes **Wikimedia absorb the traffic from this deployment's IP
address**, and the outcome is a block or rate-limit on this operator, for something this
operator did not do. That is a third-party abuse problem, and it is the single most
damaging thing about publishing this as-is.

**Fix direction:** a per-IP limiter in front of `/api/analyze`, `/api/connections/*` and
`/api/article*`; nginx `limit_req` as a coarse outer layer so the Python process is never
the first line of defence; and a documented per-IP analysis budget.

---

## A2 — The database is write-only; it caches nothing

**Severity:** Blocker · **Status:** **Fixed** — but only as of DEF-006; the `704e763` code never worked

The read path exists as of `704e763`: `articles.analysis_payload` caches the whole computed
result, `cached_analysis` serves it while fresh, and `routers/analysis.py` reports which path
answered in an `X-Cache` header. The original finding, kept for the record, is that before
that commit `repository.py` defined exactly four functions:

| Line | Function | Reads? |
| ---- | -------- | ------ |
| 24 | `store_analysis` | no |
| 58 | `_upsert_article` | `session.get` at line 86 — reads back the row it just wrote |
| 89 | `_link_rows` | pure function, no session |
| 116 | `_replace_links` | no |

A search for `repository.` across `backend/app/routers/` and `backend/app/services/`
returned **one** hit: `routers/analysis.py:53`, `repository.store_analysis(result)`.

No code anywhere read `articles`, `article_links` or `analysis_runs`. There was no
`get_article`, no `find_cached_analysis`, no read helper. `AnalysisRun` rows were written
and never queried — which is also why `init.sql:59` creates
`ix_analysis_runs_created_at ON analysis_runs (created_at DESC)` for a query that does not
exist.

Therefore:

- `PRD.md` NFR-01 and NFR-02 ("shall not make duplicate article requests when the required
  article data is already available in the application cache", "shall reuse previously
  retrieved article data") are **not implemented**.
- Every page load, every F5 and every route change is a complete fresh crawl of Wikipedia.
- `ARCHITECTURE.md` §12 describes this as "a write-through cache". It is write-only.

This mattered twice over. It was a missing promised capability, and it was the mechanism
that would otherwise absorb A1 — a read path is what makes rate limiting survivable, because
a repeat request becomes cheap instead of refused.

UAT-02 was fixed so that writes would *succeed*. They landed in a table nobody queried.

**The caveat, and it is a real one.** The read path shipped in `704e763` and never once
answered: the writer stored the display title and the reader searched for the lowercased
one, and PostgreSQL compares `VARCHAR` case-sensitively, so `X-Cache` was always `miss`.
That is **DEF-006**, found by the B6 test, and it means the finding above was still true in
substance after the commit that claimed to close it. A feature is not closed because the
code for it exists.

---

## A3 — No authentication, no identity, no abuse visibility

**Severity:** Blocker · **Status:** **Partly fixed** 27 September 2026 — a shared key
(`ANALYSIS_API_KEY`) now gates the four crawl routes. Identity and abuse visibility are
still absent, by decision rather than by oversight.

`ARCHITECTURE.md` §10.1 previously deferred the question, and `PRD.md` OQ-05 still asked
whether the first release needs any. That was a reasonable position with one user. It is
not one with many.

Consequences that follow from each other:

- Anyone can trigger unbounded writes (see A4).
- There is no subject to throttle, block, or attribute. Rate limiting by IP is the only
  lever available, and IP is a weak one behind any proxy or NAT.
- There is no request logging, no metrics endpoint, and no alerting
  (`ARCHITECTURE.md` §11.6 confirms monitoring is not configured). You would not find out
  you were being hammered until Wikipedia blocked you or the disk filled.
- `analysis_runs` records *what was analysed* but never *who*. There is no user to record.

**What was decided, and what it does.** `ANALYSIS_API_KEY`, empty by default. When set,
`POST /api/analyze` and all three `GET /api/connections/*` routes refuse anything without
a matching `X-Api-Key` header, compared with `secrets.compare_digest`. `GET /api/health`
reports `auth_required`, so a deployment that meant to be invite-only and is not is
visible without reading its environment. The full reasoning is `ARCHITECTURE.md` §10.1,
which this finding is what forced it to stop deferring.

**What it does not do, stated plainly.** There is still no identity. One key means one
subject, so there is nothing to attribute — which is also why `analysis_runs` gained no
`api_key_id` column; with a single key it would hold a constant. Nobody's request is
logged, throttled per user, or attributable. The key is a shared secret that stops
anonymous drive-by traffic and can be rotated; it is a speed bump, not access control.

**Also worth noting: the first consequence above is now weaker than it reads.** A1 rate
limits the crawl routes to 6r/m per IP and A4 prunes `analysis_runs`, so "unbounded
writes" was already bounded by the time this was addressed. What remains genuinely open is
the visibility half: no request log, no metrics, no alerting, and one IP as the only unit
of punishment. **Remaining severity: Major, not Blocker** — with the caveat that it is
Major only while the 6r/m limiter and the retention prune are actually in place.

---

## A4 — Nothing bounds database or log growth

**Severity:** Blocker · **Status:** **Fixed** in `704e763` — `analysis_runs` retention and `local` log rotation

`routers/analysis.py:53` calls `store_analysis` unconditionally on every `POST /api/analyze`.
`repository.py:40-48` adds an `AnalysisRun` row each time, and `repository.py:119-121`
deletes and re-inserts that article's `article_links`. There is no TTL, no retention
policy, and no cap anywhere in the tree.

`articles` and `article_links` are naturally bounded by the size of English Wikipedia.
`analysis_runs` is **not** — it is bounded only by request volume. A loop over one article
grows it forever.

Compounding this, neither compose file configures a logging driver. A search of
`deploy/docker-compose.staging.yml` and `deploy/docker-compose.production.yml` for
`logging:`, `driver` and `max-size` returns nothing, so both stacks use Docker's default
`json-file` driver, which **does not rotate**. Meanwhile `db.py:61` and `db.py:80` both log
a full traceback on every failure, and `/api/health` calls `db.ping()` on every request
(`main.py:97`). A database outage therefore produces a full traceback on every health
check, from the Docker healthcheck every 30 seconds, forever, into an unrotated file.

**Fix direction:** a retention job or capped insert on `analysis_runs`; an explicit
`logging:` driver with `max-size` and `max-file` on all three services in both compose
files; and a rate limit on the log level inside `ping()` and `session_scope`.

---

# B. Bugs

## B1 — One-way detection silently reports false `ONE-WAY`

**Severity:** Bug · **Status:** **Fixed** in `704e763` — paginated reverse-link read, and `ONE-WAY` is suppressed when the read is incomplete

`get_links_for_page_ids` (`services/mediawiki.py:412-414`) declares:

```python
async def get_links_for_page_ids(
    self, page_ids: Iterable[int], *, max_links_per_page: int = 500
) -> dict[int, set[str]]:
```

`max_links_per_page` is **never referenced again in the function body.** The request sends
`"pllimit": _LINKS_PROP_LIMIT` (line 431, the literal `"max"`) and the method has **no
continuation loop** — `continue` at lines 439 and 444 are Python `continue` statements
skipping malformed entries, not the MediaWiki `continue` token. The
`get_article_links` method above it (line 282) *does* paginate; this one does not.

So for any target article with more than 500 outgoing links, reverse links beyond the
first 500 are invisible to the check. If the seed article happens to be link number 501,
the connection is reported as one-way **incorrectly**.

No flag covers this. `AnalysisSummary.one_way_truncated` counts *targets checked*
(`services/analysis.py:423-427`), not *links inspected per target*. So a truncated reverse
check is presented to the user as a verified fact, which breaks the invariant in
`AGENTS.md` §5: *"A partial answer must never masquerade as a complete one."*

This is the most consequential correctness finding in the audit, because the product's
second headline feature is an accusation. Being wrong about it is worse than being silent.

**Fix direction:** paginate with the `continue` token, honour `max_links_per_page`, and
return a per-target `complete: bool` so `detect_one_way_connections`
(`services/analysis.py:198`) can refuse to assert `ONE-WAY` for a target whose link set
was truncated — the same treatment `build_extracted_links` already gives unanswered links
at `services/analysis.py:278-284`.

---

## B2 — `/connections/map` classifies missing titles twice

**Severity:** Bug · **Status:** **Fixed** in `704e763` — `classify_links` is called once

`routers/analysis.py:107-108`:

```python
types, _, _ = await classify_links(client, settings, graph)
missing, _ = await detect_missing_connections(client, settings, graph)
```

Both call `classifier.classify_titles` over the same missing-title list —
`services/analysis.py:169` inside `classify_links`, and `services/analysis.py:182` inside
`detect_missing_connections`. That is up to `classify_max_items` (default 20) **duplicate
Wikidata requests per map request**, and the two results are discarded in favour of the
second.

`analyze_article` gets this right by building `missing` inline
(`services/analysis.py:409-417`) instead of calling `detect_missing_connections`. The map
route does not follow that pattern.

It is made worse by the client. `ConnectionMapPage.jsx:17` fetches the map **independently**
of the `AnalysisProvider` analysis the page has already completed. One visit to
`/connection-map` therefore costs roughly **two full analyses** — two link extractions,
two existence checks, two reverse-link passes and two classifications.

Under A1, this is the most abusable endpoint in the application.

**Fix direction:** have the map route reuse the classification `classify_links` already
produced — the same fix shape as `analyze_article` — and consider folding the map payload
into `AnalysisResult` so the page stops paying twice.

---

## B3 — Stale-response race overwrites the current result

**Severity:** Bug · **Status:** **Fixed** in `704e763` — a request-identity guard in `AnalysisContext`

`AnalysisContext.jsx:38-73` — `run()` has **no `AbortController` and no request-identity
check**. It sets `status: 'loading'`, awaits `analyzeArticle(trimmed)`, then unconditionally
writes the result. A search for `AbortController` and `signal` in
`AnalysisContext.jsx`, `main.jsx` and `App.jsx` returns nothing.

This breaks the project's own rule, stated in `AGENTS.md` §7: *"Guard against stale
responses — results belong on screen only if they belong to the current query."*
`SearchPage.jsx:64-66` and `ConnectionMapPage.jsx:27` both implement that guard correctly.
The one fetch that carries the whole result does not.

**Reproduction:** submit article A, then article B, before A resolves. If B returns first
and A second, the second `setState` overwrites the first and the screen shows **A's**
article, its people, its missing connections and its one-way list — while the URL says B.
No error, no warning, no way for the user to tell.

`useArticleParam.js:19`'s `startedFor` ref prevents the *same* title re-running. It does
nothing for two different titles.

**Fix direction:** capture a monotonically increasing request id at the top of `run()` and
drop any response that is not the latest, or thread an `AbortController` through
`analyzeArticle` and abort the previous one. The id check is smaller and has no ordering
subtlety.

---

## B4 — Link-pagination loop has no iteration cap

**Severity:** Bug · **Status:** `Open`

`get_article_links` (`services/mediawiki.py:282-324`) is a `while True` that breaks only
when the link limit is reached (line 321) or the `continue` token is absent (line 319).
There is no page counter and no maximum iteration count.

If the upstream ever returns a `continue` token that does not advance — a malformed
response, a proxy that replays a body, a change in MediaWiki's behaviour — the loop spins
forever, holding a request open and a slot in the `max_concurrent_requests` semaphore. With
that semaphore set to 4, four such requests stop the application answering anything at all.

**Fix direction:** a hard page cap derived from the link limit, and a guard that raises
`WikipediaError` if a page contributes no new titles.

---

## B5 — `session_scope` mislabels code bugs as database failures

**Severity:** Bug · **Status:** **Fixed** 27 September 2026 — narrowed to
`except SQLAlchemyError` in `db.py`, with `tests/test_db.py` (7 tests) covering both
sides. No schema change, so `models.py` and `init.sql` are untouched.

`db.py:57-62`:

```python
try:
    yield session
    session.commit()
except Exception:  # noqa: BLE001 - persistence must never fail a request
    logger.exception("Database write failed, continuing without cache")
    session.rollback()
```

The `try` wraps the `yield`, so an exception raised **inside the caller's block** — a bug
in `store_analysis`, a malformed row, a `TypeError` — is caught here, logged as
`"Database write failed"`, and swallowed. The request still returns `200` with a complete
analysis body.

This is the same failure *shape* as UAT-02: a correct-looking response concealing a total
failure underneath, with a log line that points at the wrong subsystem. When
`store_analysis` breaks, the evidence will say "database problem" and send whoever is
on call to the database instead of to `repository.py`.

**Fix direction:** narrow the `except` to the commit, or re-raise after logging when the
failure did not originate in the database layer — and log the exception type either way, so
`"Database write failed"` is never the message for a `TypeError`.

**Resolution:** the `except` is now `except SQLAlchemyError`, so only a failure that actually
came from the database is absorbed. A `TypeError` three lines up in `repository.py` propagates
and surfaces as a `500` — a repository bug should be visible immediately, not hidden behind a
log line that blames the database.

The `read_only` argument meant the naive "move the commit inside its own `try`" fix was the
wrong one to pick: it would also have stopped the caller's own `SQLAlchemyError` from being
rolled back, and the caller's block legitimately needs a rollback on a database error. Narrowing
the *type* keeps the `yield` inside the `try` and so keeps `rollback()` reachable for every
error that came from the database, at any depth in the caller's block.

`finally: session.close()` still runs when an error propagates, so the connection is released
and the open transaction discarded — a propagating error leaks nothing. Both halves of that are
asserted.

`ping()` keeps its broad `except Exception` on purpose. No caller code runs inside its `try`,
so there is no caller's bug for it to mislabel, and the guarantee that matters there is that it
never raises, because the container `HEALTHCHECK` reads `/api/health` and an exception would
surface as a crash rather than as an unhealthy container with a diagnosis.

**On the test:** `tests/test_db.py` drives the scope with a stub session rather than a real
database, deliberately. The behaviour is worth guarding, and a guard that is skipped without
`TEST_DATABASE_URL` is a guard that will not run when the behaviour breaks. Reverting the
`except` makes `test_a_programming_error_in_the_caller_propagates` fail with the caller's
`ValueError` printed *inside* the swallowed log line, which is the finding reproduced exactly.

---

## B6 — The entire database write path is untested

**Severity:** Bug · **Status:** **Fixed** 27 September 2026 —
`backend/tests/test_persistence.py`, 13 tests, a `postgres:16-alpine` service on the CI
`backend` job. It found a blocking defect on its first run: **DEF-006**.

`test_repository.py` tested **only** `_link_rows`, a pure function that takes a list and
returns a list. A search of `backend/tests/` for `store_analysis`, `_upsert_article`,
`_replace_links` and `session_scope` returned hits only in prose — the module docstring at
`test_repository.py:1` and `:3`. **No test invoked any of them.**

`conftest.py:11` and `test_api.py:18` and `test_api.py:153` all set `database_url=""`, so
across 85 passing tests the process never opened a PostgreSQL connection. `_upsert_article`
constructed a `postgresql insert ... on conflict do update` statement that no test had ever
executed.

UAT-02 was precisely a SQL-layer defect: a unique-constraint violation that silently
discarded every write for every real article. It was found by deploying, not by testing,
and `test_repository.py` was written afterwards to guard the row *shape* — the constraint
is now covered, the statement that violates it is not. The next bug at this layer will also
be found by deploying.

**What was done.** `tests/test_persistence.py` opens a real connection, creates the schema
the way the app does at startup, and truncates between tests. It is skipped unless
`TEST_DATABASE_URL` is set *and* names a database containing `test`, and a second CI step
fails the job if the module skips — a green run that quietly stopped testing anything is the
failure mode being guarded against. What it now executes:

| Test | What it pins |
| ---- | ------------ |
| `test_a_stored_analysis_lands_as_the_rows_it_describes` | every column of the response survives into a row |
| `test_an_article_without_a_page_id_is_not_stored` | the no-primary-key case writes nothing |
| `test_a_target_reached_through_a_redirect_lands_once_and_nothing_is_lost` | UAT-02, executed |
| `test_the_database_rejects_the_duplicate_the_dedupe_prevents` | `uq_link` really exists, so the dedupe is load-bearing |
| `test_re_analysing_an_article_replaces_its_links_rather_than_adding_to_them` | links are replaced, runs accumulate |
| `test_a_stored_analysis_is_served_back_from_the_database` | the write is readable — **this one failed** |
| `test_a_repeat_request_finds_the_cache_however_the_title_is_spelled` | the lookup key is the same on both sides |
| `test_an_expired_analysis_is_not_served` | the TTL is an upper bound |
| `test_the_prune_deletes_runs_past_the_window_and_keeps_the_rest` | retention executes |
| `test_the_prune_does_not_run_on_a_write_below_its_threshold` | the amortisation is real |
| `test_a_write_that_violates_a_constraint_is_swallowed_and_leaves_nothing` | the failure is caught, the transaction is rolled back, and it is logged |
| `test_every_column_the_models_declare_exists_in_the_database` | `create_all()` did not silently skip a column |
| `test_applying_init_sql_upgrades_a_database_the_app_already_created` | the deployment upgrade path, and its idempotency |

**What it found.** `test_a_stored_analysis_is_served_back_from_the_database` failed on the
first run: the cache could never be read. `_upsert_article` stored the display title and
`cached_analysis` searched for the lowercased one, and PostgreSQL compares `VARCHAR`
case-sensitively. `X-Cache` was therefore always `miss` and every request re-crawled
Wikipedia. That is **DEF-006**, and it is the second time the write path has shipped a
silent defect that no assertion about row shape could see. See also **A2**, whose fix this
was.

---

## B7 — `looks_like_person` can never return `True`

**Severity:** Bug · **Status:** `Open`

`classifier.py:86-91`:

```python
def looks_like_person(description: str | None) -> bool:
    if not description:
        return False
    return bool(_NATIONALITY_HINT.search(description)) and _PERSON_PATTERN.search(description)
```

`_NATIONALITY_HINT` (`classifier.py:66-73`) is anchored with `^\s*` and matches only
nationality adjectives. Every string it matches is a prefix of some description. Any
description satisfying it that also matches `_PERSON_PATTERN` was **already returned as
`PERSON`** by `classify_description` at `classifier.py:79-80`, which tests
`_PERSON_PATTERN` alone.

So the function returns `True` only for inputs that never reach it, and it is not called
from anywhere. `CHECKLIST.md` §4 records it as "wired for future use, do not delete as
cleanup" — which is the correct instruction for an unused helper, but this one is not
merely unused, it is unreachable by construction and will mislead whoever eventually wires
it up.

**Fix direction:** decide whether the nationality heuristic is meant to be a *fallback* for
descriptions with no role word. If it is, it needs a different implementation. If it is
not, delete it and say so in the commit — `AGENTS.md` §14 forbids deleting a module as
"cleanup" without checking imports, and this check has been done.

---

# C. Availability and hardening

| ID | Finding | Evidence | Fix direction |
| -- | ------- | -------- | ------------- |
| **C1** | **No security headers.** No `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Strict-Transport-Security`, and no `server_tokens off`. The only `add_header` directives in the whole file are two `Cache-Control` ones. | `nginx.conf.template:33`, `:38` | Add the headers to the `server` block. A CSP is the highest-value one: it is the backstop for the XSS class that `AGENTS.md` §7 currently relies on React's escaping alone to prevent. |
| **C2** | **No TLS.** The production stack is HTTP on port 80 with no certificate. `ROLLBACK.md` §6 and `deploy/RELEASE-0.1.0.md` §1 both record this. | `deploy/docker-compose.production.yml:82` | Terminate TLS in front of nginx. Mandatory before any real user, and mandatory before C2 in this table can be closed. |
| **C3** | **`/api/articles/resolve` bounds the list, not the items.** `titles: list[str] = Query(min_length=1, max_length=50)` applies the 1–50 bound to the *number* of titles. No per-title length is enforced, and every one is forwarded to MediaWiki in a single `titles=` parameter. | `routers/articles.py:107-112` | A `list[Annotated[str, StringConstraints(max_length=512)]]`, matching the treatment `TitleQuery` already gets at `dependencies.py:22-30`. nginx's 8k header buffer limits the deployed path today; the application should not rely on that. |
| **C4** | **No request body limit.** nginx's default `client_max_body_size` (1 MB) is the only cap, and it applies only to requests that arrive through nginx. Staging publishes the API directly on `127.0.0.1:8081` with no such limit. | `deploy/docker-compose.staging.yml:58-59` | Set `client_max_body_size` explicitly rather than inheriting a default, and keep the loopback binding. |
| **C5** | **`--forwarded-allow-ips '*'` trusts `X-Forwarded-For` from any client.** Safe only for as long as the API port is unpublished in production. | `backend/Dockerfile:36` | Narrow to the proxy's address, or drop the flag. Harmless today, dangerous the moment the port is exposed. |
| **C6** | **Slow analyses 502 while the backend keeps working.** Worst case per upstream call is two 20 s attempts plus a 1 s sleep (`services/mediawiki.py:123-144`), across up to 25 reverse-link batches. nginx gives up at `proxy_read_timeout 120s`, returns 502, and the backend keeps fanning out. The natural user response — refresh — doubles the load. The comment at `nginx.conf.template:54-55` assumes the backend aborts; it only aborts on `WikipediaError`, which a slow-but-succeeding upstream never raises. | `frontend/nginx-proxy-api.conf:24-26` (not `nginx.conf.template`, whose `/api` locations only `include` that file); `services/mediawiki.py:123-144` | Either raise the read timeout to match the worst case, or bound total analysis wall-clock in `analyze_article` and abort cleanly so the user gets a real error instead of a 502. The second is better and also addresses C7. |
| **C7** | **No cancellation on client disconnect.** Navigating away from a loading page leaves the entire fan-out running to completion. | — | Propagate `Request.is_disconnected()` or a cancellation scope into the pipeline. Pair with C6. |
| **C8** | **Retries ignore `Retry-After` and use a fixed 1 s sleep.** A 429 or 503 from Wikimedia is re-issued one second later, into the same limiter, guaranteeing a second failure. | `services/mediawiki.py:143-144` | Honour `Retry-After` when present; add jitter. `ARCHITECTURE.md` §12 already notes the absence of exponential backoff as "a possible improvement rather than a gap" — under A1 it becomes a gap. |
| **C9** | **No React error boundary.** A search for `ErrorBoundary`, `componentDidCatch` and `getDerivedStateFromError` in `main.jsx` and `App.jsx` returns nothing. Any render-time throw produces a blank white page with no console-visible explanation for a non-technical user. | verified absent | One `ErrorBoundary` around `<App />` in `main.jsx`, with the same visual language as `ErrorMessage` in `ui.jsx:79`. |
| **C10** | **The dev database publishes 5432 to the host with the password `postgres`**, on all interfaces. | `database/docker-compose.yml:9-11` | **Fixed** 27 September 2026 — bound to `127.0.0.1:5432:5432` and `POSTGRES_PASSWORD` now reads `${POSTGRES_PASSWORD:-postgres}`, matching what staging already did. The default value was deliberately *kept*: it is a loopback-only throwaway holding public Wikipedia data, and changing it would silently break every existing `pgdata` volume for no security gain once the port is bound. |
| **C11** | **Staging's `DATABASE_URL` has no `connect_timeout`.** Production sets `?connect_timeout=5` for the reason given at `docker-compose.production.yml:52-58`; staging omits it, so a blackholed staging database hangs start-up for about two minutes and past the image healthcheck's budget. | `deploy/docker-compose.staging.yml:49` vs `deploy/docker-compose.production.yml:58` | Add the same parameter. |
| **C12** | **The SQLite fallback promised in `ARCHITECTURE.md` §11.8 cannot work.** §11.8 item 2 offers "an in-memory cache (or SQLite)" as the fallback if PostgreSQL is unavailable, but `repository.py:13` imports `from sqlalchemy.dialects.postgresql import insert as pg_insert` and both `_upsert_article` and `_replace_links` use it unconditionally. | `repository.py:13` | Either correct §11.8 to say PostgreSQL-only, or make the upsert dialect-aware. A documented-but-broken fallback is worse than none. |
| **C13** | **No `LICENSE` and no root `README.md`.** `CHECKLIST.md` §1.3 records both as deliberately absent. For "other users" this is a hard blocker of a different kind: **without a licence there is no legal permission to use, copy or modify this**, and without a README there is no setup path for a human — `AGENTS.md` §3 is instructions for an agent, and `deploy/README.md` covers deployment only. | verified absent | Add both. The licence decision is a person's to make, not a default to assume. |

---

# D. Gaps in the safety net

## D1 — CI's schema job only compares table names

`.github/workflows/ci.yml:155-156` extracts `__tablename__` from `models.py` and
`CREATE TABLE IF NOT EXISTS (\w+)` from `init.sql` and compares the two **sets of table
names**. Nothing else is diffed.

So the two-file invariant described in `AGENTS.md` §10 is enforced at table granularity
only. A column added to `models.py` without a matching `init.sql` change, an index that
exists in one file and not the other, a changed type or nullability — all pass CI silently.
There is already one such drift: `models.py:97` creates a plain index on
`analysis_runs.created_at` while `init.sql:59-60` creates it `DESC`.

**Fix direction:** extend the `schema` job to compare columns and indexes, not just table
names. The job already reads both files as text, so this is a regex change.

## D2 — No working path to add a column to an existing table

Three facts combine into a trap:

1. `init.sql` is mounted into the database container and executed by the Postgres entrypoint
   **on first volume creation only** — `deploy/README.md` says so explicitly.
2. `Base.metadata.create_all()` (`db.py:67-70`) creates missing **tables**. It does not add
   columns, indexes or constraints to tables that already exist.
3. There is no migration tool, and `AGENTS.md` §3 forbids adding one without asking.

So an operator who follows the documented procedure — edit `models.py` and `init.sql`
together, redeploy — gets neither change applied to a database whose volume already
exists, and no error anywhere. `ARCHITECTURE.md` §11.5 and `deploy/README.md` both say
"apply `init.sql` by hand on every later schema change", but `init.sql` is written as
`CREATE TABLE IF NOT EXISTS`, which is a no-op for a table that already exists with an
older shape.

**Fix direction:** decide and document one mechanism — an idempotent `ALTER TABLE ... ADD
COLUMN IF NOT EXISTS` block in `init.sql`, which fits the existing additive-only and
no-`DROP` rollback property — or state plainly that schema changes require a hand-written
statement outside the repository.

## D3 — UAT-02's cosmetic half: what `total_links` counts

**Severity:** Gap · **Status:** **Fixed** 27 September 2026 — resolved by decision, not by
redefinition. `total_links` keeps its meaning and `total_articles` was added beside it.

`docs/UAT.md` §5 records the blocking half of UAT-02 as fixed and leaves this open:
`Ghalib` is listed twice, and `summary.total_links` counts both. The project's own evidence
shows it: `deploy/uat/smoke-2026-09-27-production.json:48` reads
`"4 people (0 without an article), listed: Amar Jawan Jyoti, Ghalib, Ghalib"`.

`Chandni Chowk` links both `Ghalib` and `Mirza Ghalib`; the second redirects to the first.
`get_article_links` de-duplicates the raw link strings it receives, those two differ, so
both survive, and `build_extracted_links` (`services/analysis.py:285-297`) then sets
`title` from the resolved target — giving two rows with the same canonical title.

The frontend already de-duplicates for display in three places
(`ConnectionLists.jsx:33-41`, `EntitySections.jsx:62-73`), which is why the screens look
right while the count does not.

`UAT.md` §8 records why it was not fixed: changing this changes what `total_links` means,
which is a contract change for the exact-payload tests in `AGENTS.md` §8. That reasoning is
correct and the item is assigned to nobody. It needs a decision, not a fix.

**The decision, and what it was decided against.** The three options were: redefine
`total_links` to count distinct articles; carry both numbers; or leave it and document the
discrepancy. Redefining was rejected because it throws away a real fact — an author who links
the same page three times wrote three links — and the exact-payload tests would then have been
broken for a cosmetic gain. Leaving it was rejected because the tile a user reads would still
disagree with the list directly beneath it.

So: **`total_links` is unchanged in both name and value** — link targets as written, de-duplicated
by string before redirects are followed, which is a fact about the article. **`total_articles` is
new** — the same set after resolution, existing targets keyed by `page_id` and missing targets by
title, which is a fact about the destination and the number the lists already de-duplicate to.
`LinkGraph.total_articles` (`services/analysis.py:91-123`) sits beside `total_links` so the two
definitions are visible in one place rather than inferred from a field name.

The tile now shows `total_articles` and prints `total_links` next to it only when the two differ:
"440 articles / 444 link targets" is informative, but the same line on a page where they are
equal reads as a bug.

**A third number was wrong in the same place.** `links_truncated` was already returned and
already documented on the schema, but nothing told the reader what it meant: when the budget caps
the crawl, both counts are a *floor* and not a total. That is arguably the more misleading of the
two, and it is now the tile's hint, in preference to the redundant-count line.

**No schema change.** `analysis_runs` keeps recording the raw figure and no `total_articles`
column was added, so the two-file invariant in `AGENTS.md` §10 is untouched and no `init.sql`
change is owed.

**On the tests:** the collision needs a fixture no existing one had — the fake wiki contains no
redirect at all — so `test_two_spellings_of_one_redirect_count_as_two_links_and_one_article`
builds the `Ghalib` shape by overriding `get_article_links` and `resolve_titles`. Its first
version asserted against `Bangaon`/`Bongaon`, which the fake has no page for: both came back
*missing*, two distinct red links genuinely are two articles, and the test failed for the right
reason. It now redirects a second spelling onto a page the fixture really has, and
`test_article_with_no_collisions_reports_both_counts_as_equal` stops that test from passing by
differing unconditionally. Aliasing `total_articles` to `len(self.order)` fails the first.

## D4 — Classifier under-detects people heavily

`Chandni Chowk`: 444 links, **4 people** and 142 places
(`smoke-2026-09-27-production.json:48` and `:55`). A neighbourhood article naming its
politicians, writers and activists returning 4 people is low enough to check the role list
at `classifier.py:33-49` for gaps rather than accept as the documented
"best-effort classifier declining to guess" (`UAT.md` §5).

Note the deliberate omission recorded in the code comment at `classifier.py:26-29`: the
bare word `general` is excluded on purpose, because it is more often an adjective. That
decision is defensible. But it also means genuinely military or diplomatic figures lose
their strongest signal, and a place/person split this lopsided is worth an explicit look
before users rely on it.

`looks_like_person` (B7) was presumably the intended second pass. It cannot work.

## D5 — `DEFECTS.md` and `CHECKLIST.md` are materially stale

Both are in `docs/` and both now contradict the code. Per `AGENTS.md` §11, code is truth,
so these are bugs in the documents and should be fixed in the same commit as whatever
else changes.

**`docs/DEFECTS.md`** — both entries are marked `Open — no fix committed`:

- **DEF-001** (the `uq_link` unique violation that discarded every write) was fixed by
  `repository._link_rows` in `e8a062a`, with 8 regression tests in `test_repository.py`.
- **DEF-002** (`database_enabled` reporting configuration rather than reachability) was
  fixed by adding `HealthResponse.database_reachable` (`schemas.py:193`), fed by
  `db.ping()` at `main.py:97`, with `test_api.py:30-35` asserting the new body.

**`docs/CHECKLIST.md`** — v1.4 disagrees with the tree on at least six points:

| Claim in `CHECKLIST.md` | Reality |
| ----------------------- | ------- |
| "**77** passing" (§ header), "68 on `main`" (§5, §14) | **85 passing** |
| "**80** tracked, 93 in the working tree" (§15) | **104 tracked, 0 untracked** — the Phase 6 work is committed |
| `deploy/`, `.github/workflows/ci.yml`, both Dockerfiles, `test_frontend_contract.py` are "**untracked**" (§1.6, §5, §15) | all committed, in `e8a062a` |
| "**No `test` script and no test runner exist**" (§5, §8) | `package.json:10` has `test: vitest run`; 11 tests pass |
| "There is no browser automation" — correct, but §5 argues the missing-highlight criterion is unevidenced because no runner exists | the runner exists; it is not a browser |
| `ConnectionMap.jsx` `elementsFor` at line 15, `stylesheet` at line 48 (§11) | 36 and 69 |

`CHECKLIST.md` is a useful document and mostly accurate in its architecture sections
(§1–§7 read correctly). It is its status and evidence sections that have drifted.

---

# E. Verified correct — do not "fix" these

Recorded deliberately. Each of these looks like a finding to an auditor who has not read
the code, and three of them have already been the subject of a real defect in this
project's history (UAT-01, UAT-02, UAT-03). Changing them would reintroduce a bug.

| Area | Verdict | Evidence |
| ---- | ------- | -------- |
| **SSRF** | **Safe.** No user-supplied URL is ever fetched. `wiki_api_url` and `wikidata_api_url` come from the environment (`config.py:17-18`) and are never influenced by a request. The only user-controlled values passed upstream are title strings. | `services/mediawiki.py:119-121`; `PRD.md` NFR-09 |
| **XSS** | **Safe.** No `dangerouslySetInnerHTML` anywhere in the tree. All untrusted text — titles, extracts, descriptions, entity names — goes through JSX escaping. `is_internal_article_link` rejects non-`http(s)` schemes before a URL can be used. | `services/mediawiki.py:74-80` |
| **Secrets in the repository** | **Safe.** `backend/.env` and `deploy/.env` exist locally, are covered by `.gitignore:16`, and are untracked. `deploy/.env.production.example` is tracked on purpose and contains no real value. The backend image copies `app/` and `requirements.txt` only, so no credential can reach a layer. | `.gitignore:16`; `backend/Dockerfile:23`; `backend/.dockerignore:7-9` |
| **Container hardening** | **Good.** Non-root `appuser` with `chown`; `HEALTHCHECK` against `/api/health`; `web` gated on `api` being healthy; `db` unpublished via `expose` in both stacks; both `.dockerignore` files present (UAT-03). | `backend/Dockerfile:25-32`; `docker-compose.staging.yml:36-37`; `docker-compose.production.yml:37-38` |
| **Graceful degradation of the database** | **Holds, as documented.** A `DATABASE_URL` pointing at a non-existent database still returns `200` with a complete analysis. `DEFECTS.md` records this as the one thing DEF-001 did not break, and it remains true. | `db.py:29-31`; `db.py:60-62` |
| **Same-origin request path** | **Correct.** nginx proxies `/api` with `proxy_pass http://fastapi` and **no trailing path**, so the `/api` prefix survives. CORS never enters a deployed request path, and the CORS middleware is dev-only. | `nginx.conf.template:44-45`; `AGENTS.md` §5 |
| **Rollback safety of the schema** | **Correct.** `init.sql` is `CREATE ... IF NOT EXISTS` throughout, contains no `DROP`, and is wrapped in one transaction. An older image against a newer schema still works, which is what makes `ROLLBACK.md` §1 true. | `database/init.sql:9-69` |
| **The password-generation guidance** | **Correct.** `openssl rand -hex 32`, not `-base64 32`, with the reason spelled out: base64's `/` terminates the URL authority component, and the password is interpolated into `DATABASE_URL` by string concatenation. | `deploy/.env.production.example:21-25` |
| **Wikimedia User-Agent policy** | **Honoured.** Production compose refuses to start without `USER_AGENT` via `${USER_AGENT:?...}`, so the repository-URL default in `config.py:19-22` cannot reach a deployment. | `docker-compose.production.yml:61` |
| **Compose refusing weak production credentials** | **Correct.** `${POSTGRES_PASSWORD:?...}` and `${POSTGRES_USER:?...}` mean a missing password fails the deploy rather than falling back to a known string. | `docker-compose.production.yml:22-25` |

---

# F. Suggested order

Sequenced so that each step makes the next one cheap or safe. Steps 1–4 are independent of
each other and each is small.

| # | Step | Findings | Why here |
| - | ---- | -------- | -------- |
| 1 | Rate limit the analysis routes | A1 | Without it nothing else matters, and it is the only finding that makes *other people* — Wikimedia — pay for our design. |
| 2 | Fix the one-way false positive | B1 | The product makes accusations. Being wrong about them is worse than being quiet. Smallest fix with the largest correctness payoff. |
| 3 | Guard the analysis context against stale responses | B3 | Users will be shown the wrong article otherwise, with no error. Two-line fix. |
| 4 | Add a read path for stored analyses | A2 | Turns a repeat request from a full Wikipedia crawl into a cache hit, which is what makes step 1 tolerable and satisfies NFR-01/02. |
| 5 | Integration-test the write path | B6 | The gap that let UAT-02 ship. A `psycopg` service in the existing CI `images` job is enough. |
| 6 | Bound growth: retention + log rotation | A4 | Disk exhaustion is a slow, boring failure that takes a site down. |
| 7 | Stop classifying missing titles twice | B2 | Halves the most expensive endpoint's cost. Follows step 4 naturally. |
| 8 | Security headers, then TLS | C1, C2 | C1 is a one-block change with no dependencies. C2 is an infrastructure decision. |
| 9 | Remaining hardening | C3–C13 | Individually small; batch them. |
| 10 | Fix the documentation drift | D1, D5 | Do it alongside the code changes above, not as a separate pass — `AGENTS.md` §11 requires the same commit. |
| 11 | Decisions that need a person | A3, D2, C13 | Auth model, schema-change mechanism, the licence. None of these is a code fix. **D3** has since been decided — carry both counts rather than redefine one. **D4** is still waiting on its owner. |

**On step 11 specifically:** A3, C13, D2 and D4 each need a decision from a human owner
before code is written, and `DEFECTS.md` already carries an `Owner: [QA Lead]` placeholder
that `AGENTS.md` §14 says must not survive once the owner is known. This document does not
assign owners, because it cannot know them. D3 needed a decision too and no longer does: it
was one of three options, and it turned out not to require any fact this repository was
missing.

**Steps 1 to 5 are done.** `704e763` closed the rate limiter (A1, in nginx), the one-way
false positive (B1), the stale-response race (B3) and the read path (A2); the 27 September
2026 change closed B6 and, through it, DEF-006, and the next commit closed B5
(`session_scope` swallowing a caller's own bug) and C10 (the dev database on every
interface). **D3** is closed by a decision rather than a fix, and is recorded here because a
decision is still a change: `total_links` keeps its as-written meaning and a new `total_articles`
carries the resolved count, so no value was redefined and nothing was lost. What moves next is C6
and C7 together — a slow analysis 502s at nginx's read
timeout while the backend is still working on it, and a client who navigates away leaves
the whole fan-out running. Bounding the analysis clock and cancelling on disconnect would
close both. After that: B4, then B7, then D5.

---

# G. Reproducing this audit

Every mechanical claim above can be re-checked from the repository root. Run from
`backend/` unless stated.

| Claim | Command |
| ----- | ------- |
| No rate limiting or auth anywhere | `Select-String -Path backend/app,frontend/src,deploy -Pattern 'rate.?limit\|limiter\|throttle\|api.?key\|bearer' -Recurse` |
| The database is write-only | `Select-String -Path backend/app/repository.py -Pattern 'def \|select(\|session.get'` and `Select-String -Path backend/app/routers/*.py,backend/app/services/*.py -Pattern 'repository\.'` |
| `max_links_per_page` is never used | `Select-String -Path backend/app/services/mediawiki.py -Pattern 'max_links_per_page'` — one hit, the signature at line 413 |
| `classify_titles` runs twice on the map route | `Select-String -Path backend/app/routers/analysis.py -Pattern 'classify'` — lines 107 and 108 |
| No abort or identity guard in `run()` | `Select-String -Path frontend/src/context/AnalysisContext.jsx -Pattern 'AbortController\|signal'` — no hits |
| No security headers in nginx | `Select-String -Path frontend/nginx.conf.template -Pattern 'add_header\|Content-Security\|X-Frame\|X-Content-Type\|Referrer-Policy\|server_tokens\|client_max_body'` — only lines 33 and 38 |
| No log rotation configured | `Select-String -Path deploy/*.yml -Pattern 'logging\|max-size\|driver'` — no hits |
| The write path is untested | Superseded — `backend/tests/test_persistence.py` executes it. Re-check with `Select-String -Path backend/tests/*.py -Pattern 'store_analysis'` |
| CI compares table names only | Superseded — `ci.yml` now compares columns too, and `test_persistence.py` compares the models against a live database |
| `session_scope` absorbs a caller's bug | Superseded — `db.py` catches `SQLAlchemyError`, not `Exception`. Re-check with `Select-String -Path backend/app/db.py -Pattern 'except'` |
| Dev database on every interface | Superseded — `database/docker-compose.yml` binds `127.0.0.1:5432:5432`. Re-check with `Select-String -Path database/docker-compose.yml -Pattern '5432:5432'` |
| Suite state as of this revision | `pytest` (205 passed with `TEST_DATABASE_URL` set, 192 passed + 1 module skipped without it), `npm run test` (47 passed), `npm run lint` (0 errors) |

---

## Revision history

| Version | Date | Author | Status | Change |
| ------- | ---- | ------ | ------ | ------ |
| 1.0 | 27 Sep 2026 | `unassigned` | Open | Initial audit. 29 open findings (4 blockers, 7 bugs, 13 hardening, 5 gaps); 10 areas verified correct. |
| 1.1 | 27 Sep 2026 | `unassigned` | Open | `704e763` closed **A1** (nginx `limit_req` on the analysis and connection routes), **A4** (retention on `analysis_runs` + `local` log driver with rotation on all three services), **B1** (paginated reverse-link read, and `ONE-WAY` is no longer asserted on an incomplete one), **B2** (`classify_links` now called once on the map route), **B3** (request-identity guard in `AnalysisContext`), **C1** (a `security-headers.conf` include — it has to be an `include`, because `add_header` in a nested location cancels the inherited set), **C3** (`BatchedTitle` bounds each item, not just the list), **C4** (`client_max_body_size 64k`), **C5** (`--forwarded-allow-ips` narrowed to the compose subnets), **C8** (`Retry-After` honoured), **C9** (`ErrorBoundary`), **C11** (`connect_timeout` in the staging `DATABASE_URL`), **D1** (CI compares columns, not table names) and **D2** (`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`). **B6** is closed by this revision, and it found **DEF-006**: the read path added in `704e763` never answered, because `_upsert_article` stored the display title while `cached_analysis` searched for the lowercased one. A2 is therefore fixed *now*, not then. **A3, B4, B5, B7, C2, C6, C7, C10, C12, C13, D3, D4 and D5 remain open**, and every body section above still describes the pre-`704e763` tree — treat a section's `Status:` line as the authority and the prose as the original report. |
| 1.2 | 27 Sep 2026 | `unassigned` | Open | `eb7ca71` closed **A3** in part: an optional `ANALYSIS_API_KEY` gates `POST /api/analyze` and the three `GET /api/connections/*` routes, empty by default, compared with `secrets.compare_digest`, and typed into the SPA rather than baked into the bundle. It is a shared secret and not identity, so `analysis_runs` gains no `api_key_id` and A3 keeps a Major remainder — no request logging, metrics, alerting, or per-subject throttling. The same change fixed two things found on the way: `/api/health` was reading the `settings` local `create_app` closes over instead of the injected `app.state.settings`, and every gated route answered 422 rather than 401 because a `Header()` in an `Annotated` with no default is *required* in Pydantic v2. |
| 1.3 | 27 Sep 2026 | `unassigned` | Open | Closed **B5** and **C10**. **B5:** `db.session_scope` caught `Exception` around a `try` that wraps the caller's own `yield`, so a `TypeError` in `repository.py` was logged as `"Database write failed"` and the write silently dropped. Narrowed to `SQLAlchemyError`; `ping()` keeps its broad catch deliberately, and the reason is written down. Guarded by `tests/test_db.py` (7 tests, stub session, no database) so the assertion is available in a plain `pytest` run. **C10:** `database/docker-compose.yml` bound `5432:5432` — every interface — with a hardcoded password; now `127.0.0.1:5432:5432` with `${POSTGRES_PASSWORD:-postgres}`. The guard test for this was itself vacuous: its regex required a three-part mapping, so the two-part form it existed to catch was the one form it could not see, and it passed against the exact configuration it was written to prevent. **A3 (remainder), B4, B7, C2, C6, C7, C12, C13, D3, D4 and D5 remain open.** |
| 1.4 | 27 Sep 2026 | `unassigned` | Open | Closed **D3**, which was the last decision on this list that did not need a new external fact — it needed an owner to choose between redefining `total_links`, carrying both numbers, or documenting the mismatch. Chose the second: `total_links` keeps its as-written value and `total_articles` was added for the resolved count, so the raw figure is not discarded to tidy a tile and the existing field is not silently redefined. The tile shows `total_articles` and prints the raw count only when the two differ, because "440 articles / 444 link targets" is informative while the same line on a page where they are equal reads as a bug. `links_truncated` now also drives the hint: when the budget caps the crawl, both counts are a floor, and that was the more misleading of the two numbers in the same tile. No column was added, so the two-file invariant is untouched. **A3 (remainder), B4, B7, C2, C6, C7, C12, C13, D4 and D5 remain open.** |
