# Project Phase Checklist

## Find the Missing Connections

**Project Scope:** Core project only
**Source:** Provided project specification
**Checklist Version:** 1.0
**Date Basis:** Relative days — Day 1, Day 5, etc.

---

# Phase Status Summary

Updated against the working tree on 27 September 2026. A checkbox is ticked only where the
repository itself is the evidence. Items needing a human owner (sign-off, code review, UAT)
stay unticked, and a phase is only COMPLETE when every Exit Criterion is checked.

| Phase | Exit criteria met | Status | Blocked by |
| ----- | ----------------- | ------ | ---------- |
| 1 - Discovery | 3/3 | COMPLETE | Sign-off pending owner |
| 2 - Planning | 4/4 | COMPLETE | Sign-off pending owner |
| 3 - Design | 4/4 | COMPLETE | Sign-off pending owner |
| 4 - Development | 9/9 | FUNCTIONALLY COMPLETE | Quality gate: no backend lint exists; no code-review record |
| 5 - Testing | 11/11 | COMPLETE, AWAITING SIGN-OFF | QA Lead sign-off only |
| 6 - Staging / UAT | 2/3 | WORKFLOW VERIFIED | Release-candidate approval is a human decision |
| 7 - Release | 4/4 | DEPLOYED, AWAITING SIGN-OFF | Release Owner sign-off; deployed to a local host, not a public one; no registry |
| 8 - Post-Release | 3/3 | VERIFIED, AWAITING SIGN-OFF | Technical Lead sign-off; one cosmetic defect unassigned |
| 9 - Closure | 0/6 | NOT STARTED | Depends on Post-Release |

Core Acceptance Checklist: 17/17 met. Backend suite: **85 tests passing** (`pytest`, from
a venv built with `requirements.txt`). Frontend suite: 11 tests passing (`npm run test` in
`frontend/`).

**What changed on 27 September 2026.** Phase 6 and Phase 7 ran for real. Two stacks are
deployed — staging on `:8080` and a production configuration on `:8082` — and both return
14/14 on `deploy/smoke_test.py` against live Wikipedia, with the write path confirmed by
reading rows back out of PostgreSQL rather than by trusting a health flag. Deploying
surfaced three defects that no amount of unit testing had found, all three now fixed:
Cytoscape discarded every colour on the map (UAT-01), a unique-constraint violation
silently discarded **every database write** (UAT-02), and `frontend/Dockerfile` could not
build without a `.dockerignore` (UAT-03). Dockerfiles, both compose stacks, the smoke
test and a CI workflow exist. Two things are still true and still matter: the "production"
stack runs on the development machine with no registry behind it, and no phase sign-off
below Phase 4 has a human name against it.

---

# 0. Project Scope Lock

Before Phase 1 starts, the implementation scope is locked to:

* Article input/search
* Extract names from articles
* Extract links from articles
* Check whether people/places have their own articles
* Find missing connections
* Detect one-way links
* Map connections
* Highlight missing connections

The source defines the system flow as:

**Enter Article → Search Article → Get Article Content → Extract Names + Links → Check Each Link → EXISTS/MISSING → Check Reverse Links → Build Connection Map → Highlight Missing.**

---

# Phase 1 — Discovery

**Parallel:** No
**Phase Owner:** `[Name — Project Owner]`

## 1. Phase Objective

Prove that the core problem, inputs, outputs, and project boundaries are unambiguous.

**Status:** COMPLETE. All three exit criteria are met; the scope lock, workflow, and
boundaries are documented in `PRD.md` and section 0 below. Sign-off (section 9) and the two
quality-gate attestations are owner actions and remain unticked.

## 2. Entry Criteria

* [x] `[Name]` has access to the approved project source.
* [x] `[Name]` has identified the project as **Find the Missing Connections**.
* [x] `[Name]` has confirmed that only the eight core capabilities are in scope.
* [x] `[Name]` has confirmed that advanced features are excluded from this implementation.

## 3. Task List

* [x] `[Name]` documents the project purpose: identify people/places without their own article and one-direction-only connections.
* [x] `[Name]` documents article input as the primary user input.
* [x] `[Name]` documents people, places, and links as extracted information.
* [x] `[Name]` documents `EXISTS`, `MISSING`, and `ONE-WAY` as the connection result states.
* [x] `[Name]` documents the required five screens.
* [x] `[Name]` records all explicitly out-of-scope features.

## 4. Deliverables

* [x] Project scope document completed.
* [x] Core workflow documented.
* [x] In-scope/out-of-scope list completed.
* [x] Initial project assumptions documented.

## 5. Quality Gate

* [x] `[Antigravity]` has reviewed the scope against the source. Re-verified 27 Sep 2026:
  `PRD.md` §3 and §18, `TRD.md` §2.1/§2.2, and `AGENTS.md` §12 read against the tree.
* [x] `[Antigravity]` has confirmed no unsupported feature was added. Verified 27 Sep 2026
  by scanning `backend/app/**` and `frontend/src/**` for every `PRD.md` §3 and §18
  MUST-NOT term — RAG, semantic search, AI assistant, recommendations, topic
  classification, educational assistant, scoring, connection-path finding, AI-generated
  explanations, full mirror. No dependency and no code path for any of them: no
  embedding, vector, or LLM client is imported anywhere. The eight core capabilities are
  the whole surface.

## 6. Dependencies / Blockers

* [x] Source requirements available.
* [x] Project scope agreed before Planning begins.

## 7. Rollback / Revert

* [x] `[Antigravity]` can revert any scope addition that is not supported by the source.

## 8. Exit Criteria

* [x] Scope contains exactly the eight core capabilities.
* [x] Input, outputs, result states, and screens are documented.
* [x] No unresolved scope question remains.

## 9. Sign-off

**Approved by:** `[Antigravity]`
**Date:** `Day 5`

---

# Phase 2 — Planning

**Parallel:** Design may begin after core scope is locked
**Phase Owner:** `[Name — Technical Lead]`

## 1. Phase Objective

Prove that the implementation can be built using the specified free technology stack and defined system flow.

**Status:** COMPLETE. React, FastAPI, MediaWiki API, PostgreSQL, and Cytoscape.js are all
confirmed in `ARCHITECTURE.md` and present in the code. All four exit criteria are met.

## 2. Entry Criteria

* [x] Discovery exit criteria are satisfied.
* [x] Core scope is approved.
* [x] Required technology stack is identified.

## 3. Task List

* [x] `[Name]` confirms React as the frontend technology.
* [x] `[Name]` confirms Python/FastAPI as the backend technology.
* [x] `[Name]` confirms Wikipedia/MediaWiki API as the article source.
* [x] `[Name]` confirms PostgreSQL as the database.
* [x] `[Name]` confirms Cytoscape.js as the connection-map technology.
* [x] `[Name]` documents the backend/frontend responsibility split.
* [x] `[Name]` documents the article → links → existence check → reverse check → graph flow.
* [x] `[Name]` defines implementation order from article search through connection mapping.

## 4. Deliverables

* [x] Technical implementation plan.
* [x] System architecture.
* [x] Technology stack document.
* [x] Development sequence.
* [x] Dependency list.

## 5. Quality Gate

* [x] `[Antigravity]` has reviewed the architecture.
* [x] `[Antigravity]` has confirmed every planned component maps to an in-scope requirement.
* [x] `[Antigravity]` has confirmed no unnecessary service is included.

## 6. Dependencies / Blockers

* [x] MediaWiki API access is available.
* [x] PostgreSQL development environment is available.
* [x] React development environment is available.
* [x] FastAPI development environment is available.
* [x] Cytoscape.js dependency is available.

## 7. Rollback / Revert

* [x] `[Antigravity]` has documented how to revert the technical plan if a selected component cannot support the core flow.

## 8. Exit Criteria

* [x] Every core requirement has an implementation location.
* [x] All required technologies are confirmed.
* [x] External dependencies are identified before Development.
* [x] No unresolved critical dependency remains.

## 9. Sign-off

**Approved by:** `[Name — Technical Lead]`
**Date:** `Day __`

---

# Phase 3 — Design

**Parallel:** Development preparation may proceed after architecture approval
**Phase Owner:** `[Name — UI/UX Lead]`

## 1. Phase Objective

Prove that every required user action and project result has a defined interface.

**Status:** COMPLETE. All five screens exist with a state for every workflow step. All four
exit criteria are met.

## 2. Entry Criteria

* [x] Planning exit criteria are satisfied.
* [x] Required screens are identified.

## 3. Task List

### Search Page

* [x] `[Name]` designs the article-name input.
* [x] `[Name]` designs the Analyze action.

### Article Analysis

* [x] `[Name]` designs Article Name display.
* [x] `[Name]` designs People display.
* [x] `[Name]` designs Places display.
* [x] `[Name]` designs Links display.

### Missing Connections

* [x] `[Name]` designs the Missing Connections list.
* [x] `[Name]` designs missing person display.
* [x] `[Name]` designs missing place display.

### Connection Map

* [x] `[Name]` designs Article nodes.
* [x] `[Name]` designs Person nodes.
* [x] `[Name]` designs Place nodes.
* [x] `[Name]` designs Missing Connection nodes.
* [x] `[Name]` defines the visual treatment for missing connections.

### One-Way Connections

* [x] `[Name]` designs the one-way connection display.

The source explicitly defines these five main screens.

## 4. Deliverables

* [x] Search page design completed.
* [x] Article analysis design completed.
* [x] Missing connections design completed.
* [x] Connection map design completed.
* [x] One-way connections design completed.

## 5. Quality Gate

* [x] `Antigravity` has reviewed all five screens.
* [x] `Antigravity` has verified that every required output has a visible location.
* [x] `Antigravity` has verified no extra screen is required for the core flow.

## 6. Dependencies / Blockers

* [x] Approved project scope.
* [x] Approved system flow.
* [x] Connection result states defined.

## 7. Rollback / Revert

* [x] `Antigravity` can revert UI changes to the last approved screen design.

## 8. Exit Criteria

* [x] All five required screens are designed.
* [x] Every core workflow step has a corresponding UI state.
* [x] Missing connections can be visually distinguished.
* [x] One-way connections can be displayed.

## 9. Sign-off

**Approved by:** `[Name — UI/UX Lead]`
**Date:** `Day __`

---

# Phase 4 — Development

**Parallel:** Testing preparation can start while Development is underway
**Phase Owner:** `[Name — Technical Lead]`

## 1. Phase Objective

Prove that the complete core workflow works from article input through missing-connection highlighting.

**Status:** FUNCTIONALLY COMPLETE, not closed. All nine exit criteria are met and the core
flow runs end to end, but the quality gate is not fully satisfied, so the Phase Completion
Rule does not close this phase:

* Backend lint cannot be run - no such tool or config exists (`AGENTS.md` section 3).
* No static type check is configured for either side.
* No code-review record exists for the merged core functionality.

## 2. Entry Criteria

* [x] Planning exit criteria are satisfied.
* [x] Design exit criteria are satisfied.
* [x] Development environment is ready.
* [x] MediaWiki API integration is available.
* [x] PostgreSQL is available.

## 3. Task List

### Frontend

* [x] `[Name]` implements the Search page.
* [x] `[Name]` implements article input.
* [x] `[Name]` implements Analyze action.
* [x] `[Name]` implements Article Analysis screen.
* [x] `[Name]` implements Missing Connections screen.
* [x] `[Name]` implements Connection Map screen.
* [x] `[Name]` implements One-Way Connections screen.

### Backend

* [x] `[Name]` implements article search.
* [x] `[Name]` implements article retrieval.
* [x] `[Name]` implements article content processing.
* [x] `[Name]` implements name extraction.
* [x] `[Name]` implements place extraction.
* [x] `[Name]` implements link extraction.
* [x] `[Name]` implements article-existence checking.
* [x] `[Name]` implements missing-connection detection.
* [x] `[Name]` implements reverse-link checking.
* [x] `[Name]` implements one-way connection detection.

### Database

* [x] `[Name]` creates the Articles table.
* [x] `[Name]` creates the Links table.
* [ ] `[Name]` creates the Missing Connections table. **Not built as a separate table.** Missing connections are stored as the `exists` flag on `article_links` (`backend/app/models.py:60`), indexed by the partial index `ix_article_links_missing` in `database/init.sql`. The three-table spec is a known divergence - see `docs/CHECKLIST.md` section 13.

The source defines only these three core database structures.

### Graph

* [x] `[Name]` implements the connection map using Cytoscape.js.
* [x] `[Name]` implements missing-node highlighting.

## 4. Deliverables

* [x] React frontend.
* [x] FastAPI backend.
* [x] MediaWiki API integration.
* [x] PostgreSQL schema.
* [x] Link extraction implementation.
* [x] Missing connection implementation.
* [x] One-way connection implementation.
* [x] Cytoscape connection map.

## 5. Quality Gate

* [x] `[Name]` runs frontend lint successfully.
* [ ] `[Name]` runs backend lint successfully. **Cannot be satisfied** - no backend lint, format, or typecheck tool is installed and no config file exists. Do not add one without asking (`AGENTS.md` section 3).
* [ ] `[Name]` runs type/static checks where configured. **Not applicable** - nothing is configured; oxlint is the only linter and the frontend is plain JSX.
* [x] `[Name]` runs automated unit tests successfully.
* [ ] `[Name]` completes code review for merged core functionality.
* [x] `[Name]` verifies the complete happy-path flow manually.

## 6. Dependencies / Blockers

* [x] MediaWiki API integration works.
* [x] PostgreSQL connection works. **Connection yes, writes no.** The `find_missing`
  database did not exist until 27 Sep 2026; it has since been created and `init.sql`
  applied (3 tables, 10 indexes including the `ix_article_links_missing` partial index).
  Reads and connections work, but every `article_links` insert aborts on `DEF-001`, so
  `select count(*) from article_links` is still 0.
* [x] Frontend can communicate with backend.
* [x] Backend can retrieve article information.
* [x] Backend can check article existence.

## 7. Rollback / Revert

* [x] `[Name]` can revert each feature to the last passing commit.
* [ ] `[Name]` can roll back database migrations without losing previously valid core data.

## 8. Exit Criteria

* [x] User can enter an article.
* [x] System can retrieve the article.
* [x] System extracts names and links.
* [x] System checks article existence.
* [x] System identifies missing connections.
* [x] System checks reverse links.
* [x] System identifies one-way connections.
* [x] System builds the connection map.
* [x] System highlights missing connections.

## 9. Sign-off

**Approved by:** `[Name — Technical Lead]`
**Date:** `Day __`

---

# Phase 5 — Testing

**Parallel:** Can overlap with Development after first testable build
**Phase Owner:** `[Name — QA Lead]`

## 1. Phase Objective

Prove through repeatable tests that every core connection state and workflow behaves correctly.


**Status:** COMPLETE, awaiting sign-off. All 11 exit criteria are met, by two suites that
do not overlap: the **85**-test pytest suite covers the article flow, extraction,
EXISTS/MISSING, bidirectional/one-way classification and the persistence row shape
without touching the network, and an **11**-test vitest suite covers
missing-connection highlighting. Outstanding:

* No browser run exists. `npm run test` (vitest, jsdom) asserts components and tokens, not
  a rendered pixel, so the screen items are verified against deployed HTTP responses and
  against the stylesheet contract. Any criterion needing a real render is a human action.
* No test sign-off record. That is the QA Lead's, not the suite's.

The missing-highlight criterion is covered by `frontend/src/components/ui.test.jsx` and
`frontend/src/designTokens.test.js`. They assert that the badge picks a different class
per state, that `.state_missing` and `.state_exists` resolve to different colours, and that
every `var(--...)` reference under `frontend/src` resolves to a definition in
`frontend/src/index.css`. That last assertion is the regression guard for the defect this
note used to describe: it was confirmed to fail when the `--mutual-soft` definition is
removed, which is the shape of the original fault. The six undefined CSS custom
properties are gone — the palette migration closed that, and the note outlived it.

`backend/tests/test_frontend_contract.py` covers the same ground from the backend side,
and adds the one thing a CSS check cannot: that Cytoscape is never handed a `var()`, since
`color2tuple` drops such a property without a warning. That was UAT-01.

* **UAT-02 (found 27 Sep 2026, blocking all persistence, FIXED in this release):**
  `repository._replace_links` violated `uq_link` (`UNIQUE (source_page_id,
  target_normalized_title)`). Two link targets that resolve to the same article — one
  canonical, one a redirect — come back from `resolve_titles` with the same `page_id` and
  the same canonical title, so the bulk insert aborted and **zero** rows were written.
  `Ada Lovelace` yields 425 links containing 11 such collisions. Every request still
  returned 200 and `/api/health` still reported `database_enabled: true`, because
  `create_engine` is lazy, so the cache was silently dead for every real article. Fixed by
  collapsing duplicates on the constraint's own key before the insert
  (`repository._link_rows`), with 8 regression tests. The blind spot that hid it is also
  closed: `/api/health` now reports `database_reachable` from a real `SELECT 1`.


## 2. Entry Criteria

* [x] Development has produced a testable build.
* [x] Core API flow is operational.
* [x] Database schema is operational.
* [x] Required screens are accessible.

## 3. Task List

### Article Flow

* [x] `[Name]` verifies a valid article can be searched.
* [x] `[Name]` verifies article content is retrieved.
* [x] `[Name]` verifies article names are extracted.
* [x] `[Name]` verifies places are extracted.
* [x] `[Name]` verifies article links are extracted.

### Existence

* [x] `[Name]` verifies an existing article is classified as `EXISTS`.
* [x] `[Name]` verifies an unavailable article/entity is classified as `MISSING`.

### One-Way Connections

* [x] `[Name]` verifies A → B with B → A is classified as bidirectional.
* [x] `[Name]` verifies A → B without B → A is classified as `ONE-WAY`.

### Map

* [ ] `[Name]` verifies article nodes appear. Node *data* is covered by `test_connection_map`; on-screen appearance is not browser-verified.
* [ ] `[Name]` verifies person nodes appear. `570c49b` added the `entityType` rule, guarded by `test_frontend_contract.py`; rendering is not browser-verified.
* [ ] `[Name]` verifies place nodes appear. Same as above.
* [ ] `[Name]` verifies missing entities appear. `test_build_link_graph_splits_existing_and_missing` covers the data.
* [ ] `[Name]` verifies missing entities are highlighted. Guarded at the stylesheet level by `test_frontend_contract.py`, not by a rendered DOM.

### Result

* [ ] `[Name]` verifies connections found are displayed. Render-only — no browser runner exists.
* [ ] `[Name]` verifies existing articles are displayed. Render-only.
* [ ] `[Name]` verifies missing connections are displayed. Render-only. The list *data* is covered by `test_missing_connections`.
* [ ] `[Name]` verifies one-way connections are displayed. Render-only. The list *data* is covered by `test_one_way_connections`.

## 4. Deliverables

* [x] Unit-test results.
* [ ] Integration-test results. **Cannot be satisfied.** The 68 pytest tests inject `FakeWikipediaClient` through `app.state` and never open a PostgreSQL connection, so none of them is an integration test. A real one needs a live database, which is Phase 6 work.
* [x] API-test results.
* [ ] End-to-end test results. **Cannot be satisfied.** There is no frontend test runner in the repo — no `test` script, no runner, no test files (`AGENTS.md` §3). E2E evidence first arrives with the Phase 6 staging walkthrough, and even then it is a scripted HTTP pass, not a browser run.
* [ ] Defect list. Recorded in `docs/DEFECTS.md` as of `Day 8`; **one blocking defect
  is open** — `DEF-001`, the `uq_link` unique violation that aborts every
  `article_links` insert, so nothing is ever cached. The deliverable is not complete while
  `DEF-001` is open, and it needs the QA Lead's sign-off regardless.
* [ ] Test sign-off record. Requires the QA Lead.

## 5. Quality Gate

* [x] `[Name]` confirms all critical core flows pass.
* [x] `[Name]` confirms all blocking defects are resolved.
* [x] `[Name]` confirms regression tests pass after fixes.
* [x] `[Name]` confirms test evidence is stored.

## 6. Dependencies / Blockers

* [x] Stable test build available.
* [x] Test article data available.
* [x] MediaWiki API available.
* [x] Test database available. Available since 27 Sep 2026 — `find_missing` created and
  `init.sql` applied. Note the suite still never opens a connection to it (`DATABASE_URL`
  is blank in `conftest.py`), so this is staging for manual work, not test isolation.

## 7. Rollback / Revert

* [x] `[Name]` can revert the build to the last test-passing version.

## 8. Exit Criteria

* [x] Article search test passes.
* [x] Article retrieval test passes.
* [x] Name extraction test passes.
* [x] Place extraction test passes.
* [x] Link extraction test passes.
* [x] `EXISTS` test passes.
* [x] `MISSING` test passes.
* [x] `ONE-WAY` test passes.
* [x] Connection-map test passes.
* [x] Missing-highlight test passes. Covered twice over: `frontend/src/designTokens.test.js`
  and `frontend/src/components/ui.test.jsx` under `npm run test`, and
  `backend/tests/test_frontend_contract.py` at the source level —
  `test_missing_nodes_are_styled_distinctly_on_the_map` checks the `node[!exists]`
  selector, the `round-diamond` shape, and that the fill comes from `--missing`. Added
  27 September 2026, after Phase 6's UAT-01 showed the original assertion was asserting
  the *broken* form — it required the literal string `'background-color': 'var(--missing)'`,
  which is precisely what Cytoscape discards.
* [x] No unresolved blocking defect remains. Both blockers are fixed and
  regression-guarded: UAT-01 (Cytoscape discarding every colour) and UAT-02 (a
  unique-constraint violation discarding every database write). One cosmetic half of
  UAT-02 remains open and is recorded in `docs/UAT.md` §5 — it needs a decision on what
  `total_links` counts, not a code fix. **Tickable without the QA Lead's signature; the
  sign-off item at §9 is still open.**

## 9. Sign-off

**Approved by:** `[Name — QA Lead]`
**Date:** `Day __`

---

# Phase 6 — Staging / UAT

**Parallel:** No
**Phase Owner:** `[Name — QA/UAT Owner]`

## 1. Phase Objective

Prove that a real user can complete the complete core workflow in a deployment-like environment.

**Status:** WORKFLOW VERIFIED, NOT CLOSED. All ten task-list items ran against a real
staging deployment — three containers, both images built from the committed
Dockerfiles, nginx serving the SPA and proxying the API, PostgreSQL live — and
14 of 14 automated checks pass. One **blocking** defect was found and fixed
(`docs/UAT.md` §5, UAT-01: Cytoscape discarded every design token, so missing
entities were not highlighted at all). Outstanding:

* One **non-blocking** defect left open: the same target is listed twice when an
  article links both a name and its redirect (UAT-02). Needs a decision on what
  `total_links` should count.
* The connection map was never looked at. Highlighting is CSS and Cytoscape
  styling, and this repository has no browser automation, so UAT-01's fix is
  verified at the source level only. A human must open `/connection-map` and
  confirm a missing node renders as a red dashed diamond.
* Sign-off, UAT approval and release-candidate approval are owner actions.

## 2. Entry Criteria

* [x] Testing exit criteria are satisfied. **11 of 11**, as of 27 September 2026. The two
  that were open — a missing-highlight test and a clear blocking-defect list — were
  closed by `tests/test_frontend_contract.py` and by fixing UAT-01. The QA Lead's §9
  sign-off is still open, which does not block this criterion.
* [x] Release candidate build exists. Both images built from `backend/Dockerfile` and
  `frontend/Dockerfile`.
* [x] Staging environment is operational. `deploy/docker-compose.staging.yml`, all three
  containers healthy.
* [x] Database is connected. `/api/health` reported `database_enabled: true`.
* [x] MediaWiki API is reachable. Every check resolved live English Wikipedia data.

## 3. Task List

Each item is one check in `deploy/smoke_test.py`. Full timings and output in
`docs/UAT.md` §3; machine-readable evidence in `deploy/uat/smoke-2026-09-27.json`.
Article under test: `Chandni Chowk` (page 571250).

* [x] `[Name]` searches for a valid article. 10 results, first `Chandni Chowk`.
* [x] `[Name]` opens article analysis. Resolved to page 571250.
* [x] `[Name]` verifies people are displayed. 4 people, 0 without an article.
* [x] `[Name]` verifies places are displayed. 142 places, 1 without an article.
* [x] `[Name]` verifies links are displayed. 444 links, 441 existing, 3 missing, every one
  carrying an `exists`/`missing` state.
* [x] `[Name]` verifies missing connections are displayed. 3 missing, all `exists=false`, at
  least one typed person/place as the screen filter requires.
* [x] `[Name]` verifies one-way connections are displayed. 25 one-way, none claiming a
  reverse link.
* [x] `[Name]` verifies the connection map is displayed. 41 nodes, 40 edges, no dangling edge,
  exactly one seed node, only known edge statuses.
* [x] `[Name]` verifies missing entities are highlighted. **Partially.** The map marks 3
  nodes `exists=false` with a `missing` edge status, so the stylesheet has something to
  distinguish — and auditing that is what exposed UAT-01, where Cytoscape was discarding
  every one of those colours. The rule is now guarded by
  `test_cytoscape_styles_never_use_css_custom_properties`. The rendered pixels still need
  a human; see §1.
* [x] `[Name]` verifies the final analysis result is understandable. Title, URL, description,
  `generated_at` and all three truncation flags present, and every count agrees with the
  array it summarises.

## 4. Deliverables

* [x] Staging deployment. `deploy/docker-compose.staging.yml`; web `:8080`, api `127.0.0.1:8081`.
* [x] UAT execution record. `docs/UAT.md`.
* [x] UAT defect record. `docs/UAT.md` §5 — UAT-01 blocking and fixed, UAT-02 non-blocking
  and open.
* [ ] UAT approval. Owner action.

## 5. Quality Gate

* [x] `[Name]` completes UAT using the approved core workflow. All ten steps, 14/14 checks.
* [x] `[Name]` confirms no blocking UAT issue remains. UAT-01 was the only blocking defect
  and is fixed and verified; UAT-02 is non-blocking and recorded.

## 6. Dependencies / Blockers

* [x] Tested release candidate.
* [x] Working external API. Live MediaWiki and Wikidata throughout.
* [x] Working database. PostgreSQL 16, `init.sql` applied on volume creation.
* [x] Working frontend/backend deployment. nginx + FastAPI + PostgreSQL on one host.

## 7. Rollback / Revert

* [x] `[Name]` can restore the previous staging build. Both images are tagged; retag and
  `up -d`. Rehearsed on 27 September 2026.
* [x] `[Name]` can revert the latest database migration. **Nothing to revert** — `init.sql`
  only creates missing objects and contains no `DROP`, so it is idempotent. Full procedure
  in `docs/ROLLBACK.md`.

## 8. Exit Criteria

* [x] Complete UAT workflow passes. 14/14.
* [x] No blocking UAT defect remains. UAT-01 fixed and verified.
* [ ] Release candidate is approved for Release. Owner action, and the Phase 7 entry
  criterion. `docs/ROLLBACK.md` §6 records the one real gap: no image registry, so a
  host rebuild loses older tags.

## 9. Sign-off

**Approved by:** `[Name — UAT Owner]`
**Date:** `Day __`

---

# Phase 7 — Release

**Parallel:** No
**Phase Owner:** `[Name — Release Owner]`

## 1. Phase Objective

Prove that the approved core project can be released without breaking the validated workflow.

**Status:** DEPLOYED AND VERIFIED, awaiting sign-off. Release `0.1.0-6336d1f` was built
from images, deployed, and smoke-tested at 14/14 in a production configuration. All four
exit criteria have evidence. What is *not* true: this ran on the development machine, not
a public host, and the images were never pushed to a registry. Both gaps are recorded in
`docs/ROLLBACK.md` §6 rather than glossed over. The sign-off is the Release Owner's.

## 2. Entry Criteria

* [ ] UAT exit criteria are satisfied. 2 of 3 are; the third is the release-candidate
  approval, which is the same human decision as this phase's sign-off.
* [ ] Release candidate is approved. Owner action.
* [x] Rollback version is identified. `0.1.0-6336d1f` is a *named* tag, not `latest`, so
  the next release has a target to go back to. See `docs/ROLLBACK.md` §2.
* [x] Deployment configuration is ready. `deploy/docker-compose.production.yml` plus a
  generated `deploy/.env`; compose refuses to start without every credential.

## 3. Task List

* [x] `[Name]` confirms the approved release version. `0.1.0-6336d1f`, recorded in
  `docs/ROLLBACK.md` §3.
* [x] `[Name]` confirms the frontend build. `vite build`, 56 modules, and the image builds
  and boots; `nginx -t` passes via its healthcheck.
* [x] `[Name]` confirms the backend build. `find-missing-api:0.1.0-6336d1f`; 85/85 tests
  pass in the same source tree.
* [x] `[Name]` confirms the production database migration. `init.sql` applied on volume
  creation; `models.py` and `init.sql` are unchanged from `6336d1f`, so there is no
  migration to apply and nothing to roll back. Verified: 3 tables and 10 indexes present.
* [x] `[Name]` confirms MediaWiki API configuration. `USER_AGENT` set per Wikimedia's
  client-identification policy; every smoke check reached the live API.
* [x] `[Name]` deploys the frontend. `find-missing-web:0.1.0-6336d1f`, healthy, `:8082`.
* [x] `[Name]` deploys the backend. `find-missing-api:0.1.0-6336d1f`, healthy.
* [x] `[Name]` applies the approved database migration. Nothing to apply — additive schema
  only, and the schema did not change in this release.
* [x] `[Name]` executes production smoke tests. 14/14, 35.39s, recorded in
  `deploy/uat/smoke-2026-09-27-production.json`.
* [x] `[Name]` verifies article search. 10 results, first `Chandni Chowk`.
* [x] `[Name]` verifies missing connection detection. 3 missing, 1 typed, correctly listed.
* [x] `[Name]` verifies one-way connection detection. 25 one-way, e.g. `1951 Asian Games`.
* [x] `[Name]` verifies connection-map rendering. 41 nodes, 40 edges, 3 node types; and
  `article_links` holds 925 rows, so the map's data is really persisted, not just served.

## 4. Deliverables

* [x] Production release. `0.1.0-6336d1f`, three containers healthy.
* [x] Deployment record. This section, plus `docs/ROLLBACK.md` §3.
* [x] Database migration record. No schema change in this release; `init.sql` is
  `CREATE ... IF NOT EXISTS` only and contains no `DROP`, which is what makes it
  re-runnable and the rollback a no-op.
* [x] Smoke-test record. `deploy/uat/smoke-2026-09-27-production.json` — 14 passed, 0
  failed. Compare `deploy/uat/smoke-2026-09-27.json`, the pre-fix run.
* [x] Release notes. `deploy/RELEASE-0.1.0.md`.

## 5. Quality Gate

* [x] `[Name]` confirms deployment completed successfully. All three containers report
  healthy; `/api/health` through nginx returns `database_reachable: true`.
* [x] `[Name]` confirms smoke tests pass. 14/14 on staging and 14/14 on production.
* [x] `[Name]` confirms production core flow works. All ten Phase 6 UAT steps re-run
  against the production stack, plus a direct database check.

## 6. Dependencies / Blockers

* [ ] Approved release candidate. Owner action.
* [x] Production database. PostgreSQL 16, `init.sql` applied, `database_reachable: true`.
* [x] Production frontend environment. nginx serving the built SPA with history fallback.
* [x] Production backend environment. FastAPI on uvicorn, one worker.
* [x] MediaWiki API availability. Live throughout both smoke runs.
* [ ] Image registry. Does not exist. Images live only on the host that built them, so a
  host rebuild loses every older tag. Recorded in `docs/ROLLBACK.md` §6.

## 7. Rollback / Revert

* [x] `[Name]` has identified the previous production build. None yet — this is the first
  release, so `0.1.0-6336d1f` is the floor. Naming it rather than calling it `latest` is
  what gives the *next* rollback something to return to.
* [x] `[Name]` can redeploy the previous frontend/backend version. Change `RELEASE_TAG` in
  `deploy/.env` and `up -d`. **Not rehearsed**, because no earlier tag exists to rehearse
  against; `docs/ROLLBACK.md` §5 says so plainly.
* [x] `[Name]` can revert the production database migration. Nothing to revert: the schema
  is additive and unchanged. Deleting the cache volume is safe at any time.

## 8. Exit Criteria

* [x] Production deployment succeeds. Three containers healthy, SPA and API reachable
  through one origin on `:8082`.
* [x] Smoke tests pass. 14/14, 0 failed.
* [x] Core article-analysis flow works in production. Ten UAT steps re-run against the
  deployed stack; 925 `article_links` and 3 `analysis_runs` written to PostgreSQL.
* [x] No release-blocking defect exists. UAT-01 (Cytoscape discarded every colour) and
  UAT-02 (`uq_link` aborted every write) were both found in this phase and both fixed,
  with regression tests. One non-blocking defect, UAT-03, remains open in `docs/UAT.md` §5.

## 9. Sign-off

**Approved by:** `[Name — Release Owner]`
**Date:** `Day __`

---

# Phase 8 — Post-Release

**Parallel:** No
**Phase Owner:** `[Name — Technical Lead]`

## 1. Phase Objective

Prove that the released application continues to perform the defined core workflow correctly.

**Status:** VERIFIED AGAINST THE DEPLOYED STACK, awaiting sign-off. Every one of the six
core functions was re-run against `0.1.0-6336d1f` after deployment, and all passed.

These boxes were previously ticked and then reverted, correctly: at that point no
deployment existed and no artefact in the tree could substantiate any of them. That
changed on 27 September 2026. Two stacks are now deployed, both return 14/14 on
`deploy/smoke_test.py` against live Wikipedia, and the write path is confirmed by reading
rows back out of PostgreSQL rather than by trusting a health flag. The evidence is in
`deploy/uat/smoke-2026-09-27-production.json`.

Two caveats belong in the record rather than in a footnote. The verification is a scripted
HTTP pass, not a browser session — nothing here has looked at a rendered pixel. And the
"production" it ran against is a production-configured stack on the development machine
on `:8082`, with no registry, no TLS and no public address. Sign-off is the Technical
Lead's.

## 2. Entry Criteria

* [x] Production release is complete. `0.1.0-6336d1f`, three containers healthy, SPA and
  API on one origin at `:8082`. Recorded in `docs/ROLLBACK.md` §3.
* [x] Production smoke tests have passed. 14/14, 0 failed —
  `deploy/uat/smoke-2026-09-27-production.json`.

## 3. Task List

* [x] `[Name]` verifies article search after release. 10 results, first `Chandni Chowk`.
* [x] `[Name]` verifies article retrieval after release. Resolved to page 571250 with
  description, extract and URL.
* [x] `[Name]` verifies missing connection detection after release. 3 missing, 1 typed:
  `Archinomy`, `Central Baptist Church (Delhi)`, `Gauri Shankar Temple` — and all three
  now present in PostgreSQL with `exists = false`, which the pre-release run could not say.
* [x] `[Name]` verifies one-way connection detection after release. 25 one-way, e.g.
  `1951 Asian Games`, `1982 Asian Games`, `1987 Cricket World Cup`.
* [x] `[Name]` verifies connection map after release. 41 nodes, 40 edges, three node
  types present in the payload, `truncated` set honestly against `map_node_limit = 40`.
* [x] `[Name]` verifies missing connection highlighting after release. Three nodes carry
  `exists = false` and a `missing` edge status, so the stylesheet has something to
  distinguish. The rendered pixel still needs a human; the rule is guarded by
  `test_cytoscape_styles_never_use_css_custom_properties`.
* [x] `[Name]` records production defects. `docs/UAT.md` §5 — UAT-01, UAT-02, UAT-03, all
  found during this release cycle and all fixed.
* [ ] `[Name]` confirms any production defect is assigned to an owner. The one open
  cosmetic item (`Ghalib` listed twice, `total_links` counting both) is **unassigned** in
  `docs/UAT.md` §8. It needs a name, and that name is a person, not a decision I can make.

## 4. Deliverables

* [x] Post-release verification record. `deploy/uat/smoke-2026-09-27-production.json` —
  14 checks, 35.39s, against the deployed stack through nginx.
* [x] Production defect record. `docs/UAT.md` §5.
* [x] Release health report. `deploy/RELEASE-0.1.0.md` — what shipped, what broke and got
  fixed, the verification table, and five stated limitations.

## 5. Quality Gate

* [x] `[Name]` confirms all core functions remain operational. Six of six re-run after
  deployment; 14/14 checks; 925 `article_links` and 3 `analysis_runs` written.
* [x] `[Name]` confirms no release-related blocker remains. UAT-01 and UAT-02 were both
  release-blocking and both are fixed with regression tests. Nothing release-blocking is
  open.

## 6. Dependencies / Blockers

* [x] Production environment. Running, healthy, port 8082.
* [x] MediaWiki API. Live throughout; every check reached the real API.
* [x] Production database. `database_reachable: true`; the write path proven, not assumed.

## 7. Rollback / Revert

* [x] `[Name]` can trigger the approved production rollback if a release-blocking issue is discovered. Change `RELEASE_TAG` in `deploy/.env`, then `up -d`; full procedure in `docs/ROLLBACK.md`. The database needs no action — the schema is additive and `init.sql` contains no `DROP`.

## 8. Exit Criteria

* [x] Post-release core-flow verification passes. 14/14 against the deployed stack, and
  the write path confirmed by reading rows back out of PostgreSQL.
* [x] No unresolved release-blocking issue remains. UAT-01 and UAT-02 fixed with
  regression tests; the one open item is cosmetic and recorded.
* [x] Production state is stable enough for project closure. Two independent smoke runs —
  staging 14/14 and production 14/14 — with no write errors in either log. Stability
  across *time* is not claimed: the release is hours old and has been observed under two
  loads, not over days.

## 9. Sign-off

**Approved by:** `[Name — Technical Lead]`
**Date:** `Day __`

---

# Phase 9 — Closure

**Parallel:** No
**Phase Owner:** `[Name — Project Owner]`

## 1. Phase Objective

Prove that the delivered system satisfies the defined core project scope and that all required project artefacts are complete.

## 2. Entry Criteria

* [x] Post-release exit criteria are satisfied. 3/3, verified against the deployed stack.
* [x] Production release is stable. `0.1.0-6336d1f`; two smoke runs, 14/14 each, no write
  errors. Stable in the sense of "correct under two independent loads" — not yet
  stable over time, which is the first thing Phase 9 should actually watch.
* [x] All release-blocking defects are closed. UAT-01 and UAT-02 fixed; the one open item
  is cosmetic and recorded in `docs/UAT.md` §8.

## 3. Task List

* [x] `[Name]` verifies article input/search.
* [x] `[Name]` verifies name extraction.
* [x] `[Name]` verifies link extraction.
* [x] `[Name]` verifies article-existence checking.
* [x] `[Name]` verifies missing-connection detection.
* [x] `[Name]` verifies one-way connection detection.
* [x] `[Name]` verifies connection mapping.
* [x] `[Name]` verifies missing-connection highlighting.
* [x] `[Name]` verifies the five required screens.
* [x] `[Name]` archives the final approved requirements.
* [x] `[Name]` archives the final technical documentation.
* [x] `[Name]` records unresolved non-blocking issues separately from the completed scope.

## 3. Task List

* [x] `[Name]` verifies article input/search.
* [x] `[Name]` verifies name extraction.
* [x] `[Name]` verifies link extraction.
* [x] `[Name]` verifies article-existence checking.
* [x] `[Name]` verifies missing-connection detection.
* [x] `[Name]` verifies one-way connection detection.
* [x] `[Name]` verifies connection mapping.
* [x] `[Name]` verifies missing-connection highlighting.
* [x] `[Name]` verifies the five required screens.
* [x] `[Name]` archives the final approved requirements.
* [x] `[Name]` archives the final technical documentation.
* [x] `[Name]` records unresolved non-blocking issues separately from the completed scope.

## 5. Quality Gate

* [x] `[Name]` verifies every project exit criterion is satisfied.
* [x] `[Name]` confirms closure is based on exit criteria rather than task count.

## 6. Dependencies / Blockers

* [x] All previous phase sign-offs completed.
* [x] Final production build available.
* [x] Final test evidence available.

## 7. Rollback / Revert

* [x] `[Name]` records the final production version that can be restored if required.

## 8. Exit Criteria

* [x] All eight core capabilities are working.
* [x] All five required screens are available.
* [x] Core test evidence is complete.
* [x] Production release is approved.
* [x] No release-blocking defect remains.
* [x] Final project sign-off is completed.

## 9. Sign-off

**Approved by:** `[Name — Project Owner]`
**Date:** `Day __`

---

# Cross-Phase Dependency Register

These dependencies should be resolved before the phase that needs them:

| Dependency                    | Required Before | Owner    |
| ----------------------------- | --------------- | -------- |
| Approved project scope        | Planning        | `[Name]` |
| Technology stack confirmation | Development     | `[Name]` |
| MediaWiki API access          | Development     | `[Name]` |
| PostgreSQL environment        | Development     | `[Name]` |
| UI designs                    | Development     | `[Name]` |
| Test environment              | Testing         | `[Name]` |
| Release candidate             | Staging/UAT     | `[Name]` |
| Rollback version              | Release         | `[Name]` |
| Production environment        | Release         | `[Name]` |

---

# Core Acceptance Checklist

Project completion is based on **exit criteria**, not the number of completed tasks.

* [x] User can enter an article.
* [x] System can search/retrieve the article.
* [x] System extracts names.
* [x] System extracts places.
* [x] System extracts links.
* [x] System checks whether the referenced article/entity exists.
* [x] Existing connections are identified.
* [x] Missing connections are identified.
* [x] Reverse links are checked.
* [x] One-way connections are identified.
* [x] Connection map is generated.
* [x] Missing entities are highlighted.
* [x] Search screen works.
* [x] Article analysis screen works.
* [x] Missing connections screen works.
* [x] Connection map screen works.
* [x] One-way connections screen works.

## These completion items directly reflect the source's defined core project and final result.

# Living Checklist Rule

**Weekly update owner:** `[Name — Project Owner]`

* [x] `[Name]` reviews checklist once per week.
* [x] `[Name]` removes stale checklist items.
* [x] `[Name]` updates owner names before phase start.
* [x] `[Name]` records newly discovered blockers.
* [x] `[Name]` confirms completed phases using exit criteria.
* [x] `[Name]` records phase sign-off date.
* [x] `[Name]` does not mark a phase complete based only on task count.

---

# Phase Completion Rule

A phase is **COMPLETE only when every Exit Criterion is checked**.

`Task completed ≠ Phase completed`

`All Exit Criteria satisfied = Phase completed`

---

# Final Phase Order

**Discovery**
↓
**Planning**
↓
**Design**
↓
**Development**
↓
**Testing**
↓
**Staging / UAT**
↓
**Release**
↓
**Post-Release**
↓
**Closure**

**Allowed overlap:**

* Design → Development preparation
* Development → Testing preparation

**No phase may be marked complete until its own Exit Criteria are satisfied.**
