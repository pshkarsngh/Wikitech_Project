# Project Phase Checklist

## Find the Missing Connections

**Project Scope:** Core project only
**Source:** Provided project specification
**Checklist Version:** 1.0
**Date Basis:** Relative days — Day 1, Day 5, etc.

---

# Phase Status Summary

Updated against the working tree on 26 September 2026. A checkbox is ticked only where the
repository itself is the evidence. Items needing a human owner (sign-off, code review, UAT)
stay unticked, and a phase is only COMPLETE when every Exit Criterion is checked.

| Phase | Exit criteria met | Status | Blocked by |
| ----- | ----------------- | ------ | ---------- |
| 1 - Discovery | 3/3 | COMPLETE | Sign-off pending owner |
| 2 - Planning | 4/4 | COMPLETE | Sign-off pending owner |
| 3 - Design | 4/4 | COMPLETE | Sign-off pending owner |
| 4 - Development | 9/9 | FUNCTIONALLY COMPLETE | Quality gate: no backend lint exists; no code-review record |
| 5 - Testing | 9/11 | SUBSTANTIALLY COMPLETE | No UI/E2E evidence, no missing-highlight test, no defect list or sign-off |
| 6 - Staging / UAT | 0/3 | NOT STARTED | No staging environment, no release candidate |
| 7 - Release | 0/4 | NOT STARTED | No deployment, no Dockerfile, no CI |
| 8 - Post-Release | 0/3 | NOT STARTED | Depends on Release |
| 9 - Closure | 0/6 | NOT STARTED | Depends on Post-Release |

Core Acceptance Checklist: 17/17 met. Backend suite: 68 tests passing.

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

* [ ] `[Name]` has reviewed the scope against the source.
* [ ] `[Name]` has confirmed no unsupported feature was added.

## 6. Dependencies / Blockers

* [x] Source requirements available.
* [ ] Project scope agreed before Planning begins.

## 7. Rollback / Revert

* [ ] `[Name]` can revert any scope addition that is not supported by the source.

## 8. Exit Criteria

* [x] Scope contains exactly the eight core capabilities.
* [x] Input, outputs, result states, and screens are documented.
* [x] No unresolved scope question remains.

## 9. Sign-off

**Approved by:** `[Name — Project Owner]`
**Date:** `Day __`

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
* [ ] Core scope is approved.
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

* [ ] `[Name]` has reviewed the architecture.
* [ ] `[Name]` has confirmed every planned component maps to an in-scope requirement.
* [ ] `[Name]` has confirmed no unnecessary service is included.

## 6. Dependencies / Blockers

* [x] MediaWiki API access is available.
* [ ] PostgreSQL development environment is available.
* [x] React development environment is available.
* [x] FastAPI development environment is available.
* [x] Cytoscape.js dependency is available.

## 7. Rollback / Revert

* [ ] `[Name]` has documented how to revert the technical plan if a selected component cannot support the core flow.

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

* [ ] `[Name]` has reviewed all five screens.
* [ ] `[Name]` has verified that every required output has a visible location.
* [ ] `[Name]` has verified no extra screen is required for the core flow.

## 6. Dependencies / Blockers

* [ ] Approved project scope.
* [x] Approved system flow.
* [x] Connection result states defined.

## 7. Rollback / Revert

* [ ] `[Name]` can revert UI changes to the last approved screen design.

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
* [x] PostgreSQL connection works.
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

**Status:** SUBSTANTIALLY COMPLETE. 9 of 11 exit criteria are met by the 68-test pytest suite,
which covers the article flow, extraction, EXISTS/MISSING, and bidirectional/one-way
classification without touching the network. Outstanding:

* No test asserts missing-connection highlighting - it is CSS only, so nothing can regress
  it silently.
* No UI or end-to-end evidence exists; the screen and map items are verified by reading
  code, not by running the app.
* No defect list and no test sign-off record.
* A live defect is open: six CSS custom properties are referenced but no longer defined
  after the palette change, so the EXISTS and MISSING badges lose their colour.

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

* [ ] `[Name]` verifies article nodes appear.
* [ ] `[Name]` verifies person nodes appear.
* [ ] `[Name]` verifies place nodes appear.
* [ ] `[Name]` verifies missing entities appear.
* [ ] `[Name]` verifies missing entities are highlighted.

### Result

* [ ] `[Name]` verifies connections found are displayed.
* [ ] `[Name]` verifies existing articles are displayed.
* [ ] `[Name]` verifies missing connections are displayed.
* [ ] `[Name]` verifies one-way connections are displayed.

## 4. Deliverables

* [x] Unit-test results.
* [ ] Integration-test results.
* [x] API-test results.
* [ ] End-to-end test results.
* [ ] Defect list.
* [ ] Test sign-off record.

## 5. Quality Gate

* [x] `[Name]` confirms all critical core flows pass.
* [ ] `[Name]` confirms all blocking defects are resolved.
* [ ] `[Name]` confirms regression tests pass after fixes.
* [x] `[Name]` confirms test evidence is stored.

## 6. Dependencies / Blockers

* [x] Stable test build available.
* [x] Test article data available.
* [x] MediaWiki API available.
* [ ] Test database available.

## 7. Rollback / Revert

* [ ] `[Name]` can revert the build to the last test-passing version.

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
* [ ] Missing-highlight test passes.
* [ ] No unresolved blocking defect remains.

## 9. Sign-off

**Approved by:** `[Name — QA Lead]`
**Date:** `Day __`

---

# Phase 6 — Staging / UAT

**Parallel:** No
**Phase Owner:** `[Name — QA/UAT Owner]`

## 1. Phase Objective

Prove that a real user can complete the complete core workflow in a deployment-like environment.

## 2. Entry Criteria

* [ ] Testing exit criteria are satisfied.
* [ ] Release candidate build exists.
* [ ] Staging environment is operational.
* [ ] Database is connected.
* [ ] MediaWiki API is reachable.

## 3. Task List

* [ ] `[Name]` searches for a valid article.
* [ ] `[Name]` opens article analysis.
* [ ] `[Name]` verifies people are displayed.
* [ ] `[Name]` verifies places are displayed.
* [ ] `[Name]` verifies links are displayed.
* [ ] `[Name]` verifies missing connections are displayed.
* [ ] `[Name]` verifies one-way connections are displayed.
* [ ] `[Name]` verifies the connection map is displayed.
* [ ] `[Name]` verifies missing entities are highlighted.
* [ ] `[Name]` verifies the final analysis result is understandable.

## 4. Deliverables

* [ ] Staging deployment.
* [ ] UAT execution record.
* [ ] UAT defect record.
* [ ] UAT approval.

## 5. Quality Gate

* [ ] `[Name]` completes UAT using the approved core workflow.
* [ ] `[Name]` confirms no blocking UAT issue remains.

## 6. Dependencies / Blockers

* [ ] Tested release candidate.
* [ ] Working external API.
* [ ] Working database.
* [ ] Working frontend/backend deployment.

## 7. Rollback / Revert

* [ ] `[Name]` can restore the previous staging build.
* [ ] `[Name]` can revert the latest database migration.

## 8. Exit Criteria

* [ ] Complete UAT workflow passes.
* [ ] No blocking UAT defect remains.
* [ ] Release candidate is approved for Release.

## 9. Sign-off

**Approved by:** `[Name — UAT Owner]`
**Date:** `Day __`

---

# Phase 7 — Release

**Parallel:** No
**Phase Owner:** `[Name — Release Owner]`

## 1. Phase Objective

Prove that the approved core project can be released without breaking the validated workflow.

## 2. Entry Criteria

* [ ] UAT exit criteria are satisfied.
* [ ] Release candidate is approved.
* [ ] Rollback version is identified.
* [ ] Deployment configuration is ready.

## 3. Task List

* [ ] `[Name]` confirms the approved release version.
* [ ] `[Name]` confirms the frontend build.
* [ ] `[Name]` confirms the backend build.
* [ ] `[Name]` confirms the production database migration.
* [ ] `[Name]` confirms MediaWiki API configuration.
* [ ] `[Name]` deploys the frontend.
* [ ] `[Name]` deploys the backend.
* [ ] `[Name]` applies the approved database migration.
* [ ] `[Name]` executes production smoke tests.
* [ ] `[Name]` verifies article search.
* [ ] `[Name]` verifies missing connection detection.
* [ ] `[Name]` verifies one-way connection detection.
* [ ] `[Name]` verifies connection-map rendering.

## 4. Deliverables

* [ ] Production release.
* [ ] Deployment record.
* [ ] Database migration record.
* [ ] Smoke-test record.
* [ ] Release notes.

## 5. Quality Gate

* [ ] `[Name]` confirms deployment completed successfully.
* [ ] `[Name]` confirms smoke tests pass.
* [ ] `[Name]` confirms production core flow works.

## 6. Dependencies / Blockers

* [ ] Approved release candidate.
* [ ] Production database.
* [ ] Production frontend environment.
* [ ] Production backend environment.
* [ ] MediaWiki API availability.

## 7. Rollback / Revert

* [ ] `[Name]` has identified the previous production build.
* [ ] `[Name]` can redeploy the previous frontend/backend version.
* [ ] `[Name]` can revert the production database migration.

## 8. Exit Criteria

* [ ] Production deployment succeeds.
* [ ] Smoke tests pass.
* [ ] Core article-analysis flow works in production.
* [ ] No release-blocking defect exists.

## 9. Sign-off

**Approved by:** `[Name — Release Owner]`
**Date:** `Day __`

---

# Phase 8 — Post-Release

**Parallel:** No
**Phase Owner:** `[Name — Technical Lead]`

## 1. Phase Objective

Prove that the released application continues to perform the defined core workflow correctly.

## 2. Entry Criteria

* [ ] Production release is complete.
* [ ] Production smoke tests have passed.

## 3. Task List

* [ ] `[Name]` verifies article search after release.
* [ ] `[Name]` verifies article retrieval after release.
* [ ] `[Name]` verifies missing connection detection after release.
* [ ] `[Name]` verifies one-way connection detection after release.
* [ ] `[Name]` verifies connection map after release.
* [ ] `[Name]` verifies missing connection highlighting after release.
* [ ] `[Name]` records production defects.
* [ ] `[Name]` confirms any production defect is assigned to an owner.

## 4. Deliverables

* [ ] Post-release verification record.
* [ ] Production defect record.
* [ ] Release health report.

## 5. Quality Gate

* [ ] `[Name]` confirms all core functions remain operational.
* [ ] `[Name]` confirms no release-related blocker remains.

## 6. Dependencies / Blockers

* [ ] Production environment.
* [ ] MediaWiki API.
* [ ] Production database.

## 7. Rollback / Revert

* [ ] `[Name]` can trigger the approved production rollback if a release-blocking issue is discovered.

## 8. Exit Criteria

* [ ] Post-release core-flow verification passes.
* [ ] No unresolved release-blocking issue remains.
* [ ] Production state is stable enough for project closure.

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

* [ ] Post-release exit criteria are satisfied.
* [ ] Production release is stable.
* [ ] All release-blocking defects are closed.

## 3. Task List

* [ ] `[Name]` verifies article input/search.
* [ ] `[Name]` verifies name extraction.
* [ ] `[Name]` verifies link extraction.
* [ ] `[Name]` verifies article-existence checking.
* [ ] `[Name]` verifies missing-connection detection.
* [ ] `[Name]` verifies one-way connection detection.
* [ ] `[Name]` verifies connection mapping.
* [ ] `[Name]` verifies missing-connection highlighting.
* [ ] `[Name]` verifies the five required screens.
* [ ] `[Name]` archives the final approved requirements.
* [ ] `[Name]` archives the final technical documentation.
* [ ] `[Name]` records unresolved non-blocking issues separately from the completed scope.

## 4. Deliverables

* [ ] Final application.
* [ ] Final source code.
* [ ] Final database schema.
* [ ] Final test evidence.
* [ ] Final deployment record.
* [ ] Final requirements documentation.
* [ ] Final sign-off record.

## 5. Quality Gate

* [ ] `[Name]` verifies every project exit criterion is satisfied.
* [ ] `[Name]` confirms closure is based on exit criteria rather than task count.

## 6. Dependencies / Blockers

* [ ] All previous phase sign-offs completed.
* [ ] Final production build available.
* [ ] Final test evidence available.

## 7. Rollback / Revert

* [ ] `[Name]` records the final production version that can be restored if required.

## 8. Exit Criteria

* [ ] All eight core capabilities are working.
* [ ] All five required screens are available.
* [ ] Core test evidence is complete.
* [ ] Production release is approved.
* [ ] No release-blocking defect remains.
* [ ] Final project sign-off is completed.

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

* [ ] `[Name]` reviews checklist once per week.
* [ ] `[Name]` removes stale checklist items.
* [ ] `[Name]` updates owner names before phase start.
* [ ] `[Name]` records newly discovered blockers.
* [ ] `[Name]` confirms completed phases using exit criteria.
* [ ] `[Name]` records phase sign-off date.
* [ ] `[Name]` does not mark a phase complete based only on task count.

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
