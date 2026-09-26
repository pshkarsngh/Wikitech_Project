# Project Phase Checklist

## Find the Missing Connections

**Project Scope:** Core project only
**Source:** Provided project specification
**Checklist Version:** 1.0
**Date Basis:** Relative days — Day 1, Day 5, etc.

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

## 2. Entry Criteria

* [ ] `[Name]` has access to the approved project source.
* [ ] `[Name]` has identified the project as **Find the Missing Connections**.
* [ ] `[Name]` has confirmed that only the eight core capabilities are in scope.
* [ ] `[Name]` has confirmed that advanced features are excluded from this implementation.

## 3. Task List

* [ ] `[Name]` documents the project purpose: identify people/places without their own article and one-direction-only connections.
* [ ] `[Name]` documents article input as the primary user input.
* [ ] `[Name]` documents people, places, and links as extracted information.
* [ ] `[Name]` documents `EXISTS`, `MISSING`, and `ONE-WAY` as the connection result states.
* [ ] `[Name]` documents the required five screens.
* [ ] `[Name]` records all explicitly out-of-scope features.

## 4. Deliverables

* [ ] Project scope document completed.
* [ ] Core workflow documented.
* [ ] In-scope/out-of-scope list completed.
* [ ] Initial project assumptions documented.

## 5. Quality Gate

* [ ] `[Name]` has reviewed the scope against the source.
* [ ] `[Name]` has confirmed no unsupported feature was added.

## 6. Dependencies / Blockers

* [ ] Source requirements available.
* [ ] Project scope agreed before Planning begins.

## 7. Rollback / Revert

* [ ] `[Name]` can revert any scope addition that is not supported by the source.

## 8. Exit Criteria

* [ ] Scope contains exactly the eight core capabilities.
* [ ] Input, outputs, result states, and screens are documented.
* [ ] No unresolved scope question remains.

## 9. Sign-off

**Approved by:** `[Name — Project Owner]`
**Date:** `Day __`

---

# Phase 2 — Planning

**Parallel:** Design may begin after core scope is locked
**Phase Owner:** `[Name — Technical Lead]`

## 1. Phase Objective

Prove that the implementation can be built using the specified free technology stack and defined system flow.

## 2. Entry Criteria

* [ ] Discovery exit criteria are satisfied.
* [ ] Core scope is approved.
* [ ] Required technology stack is identified.

## 3. Task List

* [ ] `[Name]` confirms React as the frontend technology.
* [ ] `[Name]` confirms Python/FastAPI as the backend technology.
* [ ] `[Name]` confirms Wikipedia/MediaWiki API as the article source.
* [ ] `[Name]` confirms PostgreSQL as the database.
* [ ] `[Name]` confirms Cytoscape.js as the connection-map technology.
* [ ] `[Name]` documents the backend/frontend responsibility split.
* [ ] `[Name]` documents the article → links → existence check → reverse check → graph flow.
* [ ] `[Name]` defines implementation order from article search through connection mapping.

## 4. Deliverables

* [ ] Technical implementation plan.
* [ ] System architecture.
* [ ] Technology stack document.
* [ ] Development sequence.
* [ ] Dependency list.

## 5. Quality Gate

* [ ] `[Name]` has reviewed the architecture.
* [ ] `[Name]` has confirmed every planned component maps to an in-scope requirement.
* [ ] `[Name]` has confirmed no unnecessary service is included.

## 6. Dependencies / Blockers

* [ ] MediaWiki API access is available.
* [ ] PostgreSQL development environment is available.
* [ ] React development environment is available.
* [ ] FastAPI development environment is available.
* [ ] Cytoscape.js dependency is available.

## 7. Rollback / Revert

* [ ] `[Name]` has documented how to revert the technical plan if a selected component cannot support the core flow.

## 8. Exit Criteria

* [ ] Every core requirement has an implementation location.
* [ ] All required technologies are confirmed.
* [ ] External dependencies are identified before Development.
* [ ] No unresolved critical dependency remains.

## 9. Sign-off

**Approved by:** `[Name — Technical Lead]`
**Date:** `Day __`

---

# Phase 3 — Design

**Parallel:** Development preparation may proceed after architecture approval
**Phase Owner:** `[Name — UI/UX Lead]`

## 1. Phase Objective

Prove that every required user action and project result has a defined interface.

## 2. Entry Criteria

* [ ] Planning exit criteria are satisfied.
* [ ] Required screens are identified.

## 3. Task List

### Search Page

* [ ] `[Name]` designs the article-name input.
* [ ] `[Name]` designs the Analyze action.

### Article Analysis

* [ ] `[Name]` designs Article Name display.
* [ ] `[Name]` designs People display.
* [ ] `[Name]` designs Places display.
* [ ] `[Name]` designs Links display.

### Missing Connections

* [ ] `[Name]` designs the Missing Connections list.
* [ ] `[Name]` designs missing person display.
* [ ] `[Name]` designs missing place display.

### Connection Map

* [ ] `[Name]` designs Article nodes.
* [ ] `[Name]` designs Person nodes.
* [ ] `[Name]` designs Place nodes.
* [ ] `[Name]` designs Missing Connection nodes.
* [ ] `[Name]` defines the visual treatment for missing connections.

### One-Way Connections

* [ ] `[Name]` designs the one-way connection display.

The source explicitly defines these five main screens.

## 4. Deliverables

* [ ] Search page design completed.
* [ ] Article analysis design completed.
* [ ] Missing connections design completed.
* [ ] Connection map design completed.
* [ ] One-way connections design completed.

## 5. Quality Gate

* [ ] `[Name]` has reviewed all five screens.
* [ ] `[Name]` has verified that every required output has a visible location.
* [ ] `[Name]` has verified no extra screen is required for the core flow.

## 6. Dependencies / Blockers

* [ ] Approved project scope.
* [ ] Approved system flow.
* [ ] Connection result states defined.

## 7. Rollback / Revert

* [ ] `[Name]` can revert UI changes to the last approved screen design.

## 8. Exit Criteria

* [ ] All five required screens are designed.
* [ ] Every core workflow step has a corresponding UI state.
* [ ] Missing connections can be visually distinguished.
* [ ] One-way connections can be displayed.

## 9. Sign-off

**Approved by:** `[Name — UI/UX Lead]`
**Date:** `Day __`

---

# Phase 4 — Development

**Parallel:** Testing preparation can start while Development is underway
**Phase Owner:** `[Name — Technical Lead]`

## 1. Phase Objective

Prove that the complete core workflow works from article input through missing-connection highlighting.

## 2. Entry Criteria

* [ ] Planning exit criteria are satisfied.
* [ ] Design exit criteria are satisfied.
* [ ] Development environment is ready.
* [ ] MediaWiki API integration is available.
* [ ] PostgreSQL is available.

## 3. Task List

### Frontend

* [ ] `[Name]` implements the Search page.
* [ ] `[Name]` implements article input.
* [ ] `[Name]` implements Analyze action.
* [ ] `[Name]` implements Article Analysis screen.
* [ ] `[Name]` implements Missing Connections screen.
* [ ] `[Name]` implements Connection Map screen.
* [ ] `[Name]` implements One-Way Connections screen.

### Backend

* [ ] `[Name]` implements article search.
* [ ] `[Name]` implements article retrieval.
* [ ] `[Name]` implements article content processing.
* [ ] `[Name]` implements name extraction.
* [ ] `[Name]` implements place extraction.
* [ ] `[Name]` implements link extraction.
* [ ] `[Name]` implements article-existence checking.
* [ ] `[Name]` implements missing-connection detection.
* [ ] `[Name]` implements reverse-link checking.
* [ ] `[Name]` implements one-way connection detection.

### Database

* [ ] `[Name]` creates the Articles table.
* [ ] `[Name]` creates the Links table.
* [ ] `[Name]` creates the Missing Connections table.

The source defines only these three core database structures.

### Graph

* [ ] `[Name]` implements the connection map using Cytoscape.js.
* [ ] `[Name]` implements missing-node highlighting.

## 4. Deliverables

* [ ] React frontend.
* [ ] FastAPI backend.
* [ ] MediaWiki API integration.
* [ ] PostgreSQL schema.
* [ ] Link extraction implementation.
* [ ] Missing connection implementation.
* [ ] One-way connection implementation.
* [ ] Cytoscape connection map.

## 5. Quality Gate

* [ ] `[Name]` runs frontend lint successfully.
* [ ] `[Name]` runs backend lint successfully.
* [ ] `[Name]` runs type/static checks where configured.
* [ ] `[Name]` runs automated unit tests successfully.
* [ ] `[Name]` completes code review for merged core functionality.
* [ ] `[Name]` verifies the complete happy-path flow manually.

## 6. Dependencies / Blockers

* [ ] MediaWiki API integration works.
* [ ] PostgreSQL connection works.
* [ ] Frontend can communicate with backend.
* [ ] Backend can retrieve article information.
* [ ] Backend can check article existence.

## 7. Rollback / Revert

* [ ] `[Name]` can revert each feature to the last passing commit.
* [ ] `[Name]` can roll back database migrations without losing previously valid core data.

## 8. Exit Criteria

* [ ] User can enter an article.
* [ ] System can retrieve the article.
* [ ] System extracts names and links.
* [ ] System checks article existence.
* [ ] System identifies missing connections.
* [ ] System checks reverse links.
* [ ] System identifies one-way connections.
* [ ] System builds the connection map.
* [ ] System highlights missing connections.

## 9. Sign-off

**Approved by:** `[Name — Technical Lead]`
**Date:** `Day __`

---

# Phase 5 — Testing

**Parallel:** Can overlap with Development after first testable build
**Phase Owner:** `[Name — QA Lead]`

## 1. Phase Objective

Prove through repeatable tests that every core connection state and workflow behaves correctly.

## 2. Entry Criteria

* [ ] Development has produced a testable build.
* [ ] Core API flow is operational.
* [ ] Database schema is operational.
* [ ] Required screens are accessible.

## 3. Task List

### Article Flow

* [ ] `[Name]` verifies a valid article can be searched.
* [ ] `[Name]` verifies article content is retrieved.
* [ ] `[Name]` verifies article names are extracted.
* [ ] `[Name]` verifies places are extracted.
* [ ] `[Name]` verifies article links are extracted.

### Existence

* [ ] `[Name]` verifies an existing article is classified as `EXISTS`.
* [ ] `[Name]` verifies an unavailable article/entity is classified as `MISSING`.

### One-Way Connections

* [ ] `[Name]` verifies A → B with B → A is classified as bidirectional.
* [ ] `[Name]` verifies A → B without B → A is classified as `ONE-WAY`.

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

* [ ] Unit-test results.
* [ ] Integration-test results.
* [ ] API-test results.
* [ ] End-to-end test results.
* [ ] Defect list.
* [ ] Test sign-off record.

## 5. Quality Gate

* [ ] `[Name]` confirms all critical core flows pass.
* [ ] `[Name]` confirms all blocking defects are resolved.
* [ ] `[Name]` confirms regression tests pass after fixes.
* [ ] `[Name]` confirms test evidence is stored.

## 6. Dependencies / Blockers

* [ ] Stable test build available.
* [ ] Test article data available.
* [ ] MediaWiki API available.
* [ ] Test database available.

## 7. Rollback / Revert

* [ ] `[Name]` can revert the build to the last test-passing version.

## 8. Exit Criteria

* [ ] Article search test passes.
* [ ] Article retrieval test passes.
* [ ] Name extraction test passes.
* [ ] Place extraction test passes.
* [ ] Link extraction test passes.
* [ ] `EXISTS` test passes.
* [ ] `MISSING` test passes.
* [ ] `ONE-WAY` test passes.
* [ ] Connection-map test passes.
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

* [ ] User can enter an article.
* [ ] System can search/retrieve the article.
* [ ] System extracts names.
* [ ] System extracts places.
* [ ] System extracts links.
* [ ] System checks whether the referenced article/entity exists.
* [ ] Existing connections are identified.
* [ ] Missing connections are identified.
* [ ] Reverse links are checked.
* [ ] One-way connections are identified.
* [ ] Connection map is generated.
* [ ] Missing entities are highlighted.
* [ ] Search screen works.
* [ ] Article analysis screen works.
* [ ] Missing connections screen works.
* [ ] Connection map screen works.
* [ ] One-way connections screen works.

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
