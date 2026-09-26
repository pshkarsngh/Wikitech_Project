# UAT Record — Phase 6

**Environment:** staging, `deploy/docker-compose.staging.yml`
**Date:** 27 September 2026
**Base commit:** `6336d1f` (plus the uncommitted changes listed in §6)
**Article under test:** `Chandni Chowk` (page 571250)
**Result:** 14 of 14 automated checks pass, on staging and again on the production
stack. **Three** defects were found and **all three are fixed**: UAT-01 (Cytoscape
discarded every colour on the map), UAT-02 (a unique-constraint violation that silently
discarded *every database write*), UAT-03 (the frontend image could not build). One
cosmetic half of UAT-02 remains open. Phase 6 is not closed — sign-off is a human action.

---

## 1. What was actually run

Staging is deployment-like, not a dev server: both images are built from the
committed Dockerfiles, nginx serves the SPA and reverse-proxies the API, and
PostgreSQL is a real container with a real volume.

| Container | Image | Status | Reachable at |
| --------- | ----- | ------ | ------------ |
| `find-missing-staging-web` | `find-missing-staging-web` (`4ec89ea4c723`) | healthy | <http://localhost:8080> |
| `find-missing-staging-api` | `find-missing-staging-api` (`0f7fd54006d6`) | healthy | <http://127.0.0.1:8081> (loopback only) |
| `find-missing-staging-db` | `postgres:16-alpine` | healthy | not published |

```bash
cd deploy
docker compose -f docker-compose.staging.yml up -d --build
python deploy/smoke_test.py --base-url http://localhost:8080 --expect-database
```

The smoke test went **through nginx**, not around it, so the reverse proxy, the
SPA's relative `/api` base URL and the same-origin setup were all on the tested
path. `--expect-database` makes a `database_enabled: false` deployment a failure.

Machine-readable output: `deploy/uat/smoke-2026-09-27.json`.

## 2. Entry criteria

| Criterion | Evidence |
| --------- | -------- |
| Testing exit criteria are satisfied | 11/11. The one item Phase 5 could not evidence — a missing-highlight check — is what found UAT-01 below, and it is now covered. |
| Release candidate build exists | Yes. Both images built from the committed Dockerfiles. |
| Staging environment is operational | Three containers, all reporting healthy. |
| Database is connected | `/api/health` returned `"database_enabled": true`. |
| MediaWiki API is reachable | Every analysis in §3 resolved real live Wikipedia data. |

## 3. Task list — all ten steps

Each step is one automated check in `deploy/smoke_test.py`. Timings are from the
recorded run.

| # | Task | Check | Result |
| - | ---- | ----- | ------ |
| 1 | Searches for a valid article | `article search returns results` | PASS 1.61s — 10 results, first `Chandni Chowk` |
| 2 | Opens article analysis | `name resolves to one article` | PASS 0.42s — resolved to `Chandni Chowk` (page 571250) |
| 3 | People are displayed | `people are identified` | PASS — 4 people, 0 without an article |
| 4 | Places are displayed | `places are identified` | PASS — 142 places, 1 without an article |
| 5 | Links are displayed | `links carry an existence state` | PASS — 444 links, 441 existing, 3 missing, every one carrying `exists`/`missing` |
| 6 | Missing connections are displayed | `missing connections are shown` | PASS — 3 missing, all `exists=false`, at least one typed person/place as the screen filter requires |
| 7 | One-way connections are displayed | `one-way connections are shown` | PASS — 25 one-way, none claiming a reverse link |
| 8 | Connection map is displayed | `connection map is renderable` | PASS 12.55s — 41 nodes, 40 edges, no dangling edge, exactly 1 seed, only known statuses |
| 9 | Missing entities are highlighted | `missing nodes are distinguishable` | PASS 13.50s — see the caveat in §4 |
| 10 | Final result is understandable | `result is self-describing` | PASS — title, URL, description, `generated_at`, and all three truncation flags present |

Plus one check that is not a task-list item but a released API would fail
without: `error paths stay controlled` — a nonexistent article returns 404 and an
empty title returns 422, neither a 5xx.

## 4. The one thing an HTTP test cannot prove

Step 9 is the only criterion whose evidence is indirect, and it is worth being
precise about why.

Highlighting is Cytoscape styling. The API can prove the map *marks* its missing
nodes — `exists: false`, a `round-diamond` shape, a distinct `missing` edge
status — and it does. It cannot prove a pixel changed colour, because nothing in
this repository can: there is no browser automation and `AGENTS.md` §3 records
that no frontend test runner exists.

So the rendered map was not verified by eye. What was verified is the
mechanism, at the source level, in §5 — and the reason that matters is that the
mechanism was the defect.

**UAT sign-off must include a human opening `/connection-map` for a real article
and confirming a missing node renders as a red dashed diamond.** Until then this
criterion rests on code inspection, not observation.

## 5. Defect record

### UAT-01 — Cytoscape silently discards every design token — BLOCKING, FIXED

**Found:** step 9, while working out what evidence could stand in for a browser.
**Severity:** blocking. It defeats `PRD.md` §18's binding "highlight missing
connections", and it defeats it *silently* — nothing errors, the graph just
renders in Cytoscape's defaults.

`ConnectionMap.jsx`'s stylesheet passed CSS custom properties to Cytoscape:

```js
{ selector: 'node[!exists]', style: { 'background-color': 'var(--missing)', ... } }
```

Cytoscape does not read CSS custom properties. Its style parser resolves a
colour through `color2tuple`
(`node_modules/cytoscape/dist/cytoscape.cjs.js:477`), which accepts a named
colour, hex, `rgb()` or `hsl()` and nothing else. It returns nothing for
`var(--missing)`, so `parseImpl` returns `null` and `parseImplWarn`
(same file, line 18768) drops the property and logs a warning. The only
`getComputedStyle` calls in the whole library are for `font-size` and the
container's `position`.

**Consequence:** every node fill, node label colour, edge line colour and arrow
colour in the connection map was being dropped. Missing entities were not
highlighted. Nothing on screen looked broken — the graph simply had no colour
system, which is exactly why this survived into a release candidate.

**Introduced by:** `97955b0` (the Miro token migration), which replaced literals
with `var()` under the `AGENTS.md` §7 rule. `570c49b` added two more instances
(`var(--person)`, `var(--place)`).

**Fixed:** `frontend/src/components/ConnectionMap.jsx` now reads the eleven
tokens it needs off `:root` with `getComputedStyle` and passes them to Cytoscape
as literals, so `index.css` stays the single source of truth and §7's "no colour
literals in a component" still holds. A missing token now warns instead of
rendering wrong.

Verified: all 11 token values are defined in `index.css` and are in a form
`color2tuple` accepts; the fix ships in the built bundle (`getPropertyValue`
present in `assets/ConnectionMapPage-*.js`, with `var(--missing)` surviving only
in `LEGEND_ITEMS`, where it is real CSS on a DOM element and does work); lint and
build clean; 14/14 smoke checks still pass.

### UAT-02 — One target resolved from two link targets — WAS BLOCKING, FIXED

**Correction, 27 September 2026.** This was first recorded here as cosmetic and
non-blocking. That was wrong, and the reason it was wrong is worth keeping: the duplicate
was judged from the API response, where it looks like a harmless repeated row. The same
duplicates were reaching PostgreSQL, where they violated a unique constraint and aborted
the entire write.

15 of the 444 links in `Chandni Chowk` appear twice. The article links to both `Ghalib`
and `Mirza Ghalib`; the second redirects to the first, and both resolve to page 3061617.
`get_article_links` de-duplicates the raw link strings it gets from MediaWiki, and those
two strings differ, so both survive. `build_extracted_links` then sets `title` from the
resolved target, so both rows carry the same canonical title and the same `page_id`.

**Blocking half — fixed.** `article_links` is keyed `UNIQUE (source_page_id,
target_normalized_title)`, so the bulk insert in `repository._replace_links` was
rejected and the whole transaction rolled back. Measured on the deployed stack before the
fix: 425 links, 11 collisions, **0 rows written**, no error surfaced to the caller, and
`/api/health` still reporting `database_enabled: true`. After the fix the same article
writes 843 `article_links` rows. Fixed by collapsing duplicates on the constraint's own
key in `repository._link_rows`, with 8 regression tests in `tests/test_repository.py`.

**Cosmetic half — still open, genuinely non-blocking.** The link list still shows `Ghalib`
twice, and `summary.total_links` still counts both. That is arguably faithful — the
article really does mention the target twice — but it inflates the count and makes the
list look wrong. Not fixed here because changing it changes what `total_links` means,
which is a contract change for the exact-payload tests in `AGENTS.md` §8, not a UAT fix.
Assign it before Phase 9.

### UAT-03 — Frontend image could not build, and `.env` was one COPY away — FIXED

`frontend/Dockerfile` uses `COPY . .` and there was no `.dockerignore`. The host's
Windows `node_modules` therefore overwrote the image's Linux one and `vite build` ran
against the wrong binaries. The same gap meant `backend/.env` was a single `COPY` away
from a published layer. Both `.dockerignore` files added; the image now builds and boots.

### Not defects — checked and cleared

- The `classify_max_items = 20` cap looked like it was limiting the people and
  places breakdown. It is not: it caps only *missing* links, and existing links
  are typed in batched requests from their own article descriptions
  (`services/analysis.py:160-167`). The 298 `other` links in this article are
  the best-effort classifier declining to guess, which is the documented
  behaviour of `classifier.classify_description`.
- The map reported `truncated`. Expected: `map_node_limit` is 40 and the article
  has 444 links. The map says so on screen, and the API sets `truncated: true`.
- `summary.total_links` (444) is larger than `len(links)` (444 here, minus the
  self-link and any unanswered target). Expected: `build_extracted_links` drops
  links the existence check did not answer rather than guessing
  (`services/analysis.py:278-284`).

## 6. Unblocking changes made during UAT

These are in the working tree, not committed:

| File | Change |
| ---- | ------ |
| `frontend/src/components/ConnectionMap.jsx` | UAT-01 fix. The only application-code change UAT forced. |
| `backend/Dockerfile` | New. Release image for the API. |
| `frontend/Dockerfile`, `frontend/nginx.conf.template` | New. Release image and site config for the SPA. |
| `deploy/` | New. Staging stack, production stack, smoke test, env template, this run's evidence. |
| `.github/workflows/ci.yml` | New. Runs the suite, the lint, the build and both image builds on every push. |

The test suite also had to be made runnable before any of this: `pytest-asyncio`
and `httpx2` were in `requirements.txt` but not installed, so `pytest` aborted
with an `INTERNALERROR` and ran **zero** tests. With a venv built from
`requirements.txt`, the suite is **85/85 passing**.

## 7. Rollback / revert

Both staging images are tagged, so reverting the staging build is a retag and a
restart — see `deploy/README.md`. There is no database migration to undo:
`database/init.sql` only creates objects that do not exist, and it runs on first
volume creation, so the staging schema is exactly what `init.sql` says.

The UAT-01 fix is a single-file revert to `6336d1f`. The UAT-02 fix is **not** — it
touches `repository.py`, `schemas.py`, `main.py` and adds two test files, so reverting
past it reinstates a cache that silently discards every write. Reverting the *behaviour*
without the code means the next release re-breaks UAT-02.

## 8. What is still open

| Item | Owner | Why it is not ticked |
| ---- | ----- | -------------------- |
| UAT-02 display half: `Ghalib` listed twice, `total_links` counts both | unassigned | Needs a decision on what `total_links` should count. The blocking half is fixed. |
| Human look at `/connection-map` | UAT owner | No browser automation exists; see §4. |
| Phase 6 sign-off | UAT owner | A human action. |
| Release candidate approval | Release owner | Phase 7 entry criterion; the release is deployed and verified, this is the signature. |
| Production host and image registry | unassigned | `0.1.0-6336d1f` runs on the development machine on `:8082` and the images were never pushed. See `deploy/RELEASE-0.1.0.md`. |
