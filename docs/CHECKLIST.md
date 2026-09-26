# Project File Checklist

## Find the Missing Connections

**Version:** 1.2
**Date:** 26 September 2026
**Scope:** Every tracked file in the repository, with its responsibility and the
checks that apply when you touch it.

This is a navigation and maintenance aid. The progress table tracks *verification* of
this document, not delivery of the project. Delivery progress lives in `PHASES.md`;
requirements live in `PRD.md`; technical specification lives in `TRD.md`; structure and
invariants live in `ARCHITECTURE.md` and `../AGENTS.md`.

**Verification basis:** 80 tracked files, enumerated in §15. Code is truth — where this
file and the code disagree, the code wins and this file is the bug.

## How to read the check marks

Every row in every table has a **Done** cell. It tracks one thing only: *has this claim
been verified against the code?*

| Mark | Meaning |
| ---- | ------- |
| `[x]` | Verified. The claim was read out of the source, with `file:line` where relevant. |
| `[ ]` | Not yet verified. Treat the row as a lead, not a fact — it may have drifted. |

Check a row when you confirm it, not when you assume it. A `[ ]` row that turns out to
be wrong is a bug in this file; fix it in the same commit as whatever else you touched.
Re-verify a row whenever the file it describes changes.

## Progress

| § | Section | Done | Verified |
| - | ------- | --- | -------- |
| 1 | Repository Root | [x] | 2026-09-26 |
| 2 | Backend — Application Core | [ ] | — |
| 3 | Backend — Routers | [ ] | — |
| 4 | Backend — Services | [ ] | — |
| 5 | Backend — Tests | [ ] | — |
| 6 | Backend — Config | [ ] | — |
| 7 | Database | [ ] | — |
| 8 | Frontend — Entry Points and Config | [ ] | — |
| 9 | Frontend — Source Core | [ ] | — |
| 10 | Frontend — Pages | [ ] | — |
| 11 | Frontend — Components | [ ] | — |
| 12 | Documentation | [ ] | — |
| 13 | Known Divergences | [ ] | — |
| 14 | Repository-Wide Verification | [ ] | — |
| 15 | File-Count Reference | [x] | 2026-09-26 |

**1 of 15 sections verified.**

---

# 1. Repository Root — [x] verified 2026-09-26 (re-verified after `a48046f`, `97955b0`)

The root holds exactly **2 tracked files** and **4 tracked directories**. Nothing else
is committed here. `DESIGN.md` was **moved to `docs/DESIGN.md`** in `97955b0`.

## 1.1 Top-Level Layout

| Done | Path | Kind | Contents | Documented in |
| ---- | ---- | ---- | -------- | ------------- |
| [x] | `backend/` | dir | 15 app modules, 7 test modules, 4 config files | §2–§6 |
| [x] | `frontend/` | dir | 34 `src` files, 9 config/entry/public files | §8–§11 |
| [x] | `database/` | dir | compose, SQL, readme (3 files) | §7 |
| [x] | `docs/` | dir | PRD, TRD, PHASES, ARCHITECTURE, CHECKLIST, DESIGN (6 files) | §12 |
| [x] | `AGENTS.md` | file | Project instructions — invariants, conventions, commands | §1.2 |
| [x] | `.gitignore` | file | 26 lines of ignore rules | §1.2 |

## 1.2 Tracked Files

| Done | File | Purpose | Check when touched |
| ---- | ---- | ------- | ------------------ |
| [x] | `AGENTS.md` | Load-bearing project instructions: layout, commands, stack, 8 architecture invariants, backend/frontend conventions, testing rules, design-system rules, docs-vs-code warnings, scope lock, Windows quirks, never-do list. | **Read it before any change.** Update it in the same commit as any convention or invariant change. Must stay committed, not ignored. |
| [x] | `.gitignore` | Python (`__pycache__/`, `*.py[cod]`, `.venv/`, `venv/`, `.pytest_cache/`, `.ruff_cache/`), Node (`node_modules/`, `dist/`, `dist-ssr/`, `*.local`), environment (`.env`), dev-server output (`*.log`, added in `a48046f`), editors/OS, and local agent tooling (`.agents/`, `.claude/`, `skills/`, `skills-lock.json`). | `.env` is ignored — never force-add it. `AGENTS.md` is **not** in this file and must stay that way. `.ruff_cache/` is listed even though no ruff is installed; that is harmless. |

## 1.3 Confirmed Absent

Verified by `Test-Path` on 2026-09-26. Each row is a trap for anyone assuming standard
tooling exists.

| Done | Path | Status | Consequence of assuming it exists |
| ---- | ---- | ------ | ---------------------------------- |
| [x] | `DESIGN.md` (at root) | **Moved to `docs/DESIGN.md`** | It is no longer at the root. `AGENTS.md` §2 and §9 point at the `docs/` path. Do not recreate a root copy. |
| [x] | `README.md` | Absent | There is no committed setup guide. `AGENTS.md` §3 is the only source of truth for commands. If you add one, it must not contradict `AGENTS.md` §3. |
| [x] | `.github/` | Absent | **No CI.** No automated test, lint, or build on push. Every check in §14 is local and manual — you own running them. |
| [x] | `Dockerfile` | Absent | No container image for the app. `database/docker-compose.yml` is the only Docker artefact, and it runs PostgreSQL only. |
| [x] | `pyproject.toml` | Absent | No Python packaging, dependency pinning, or tool config. `requirements.txt` is the only dependency source. |
| [x] | `ruff.toml` | Absent | No Python lint. See §1.4. |
| [x] | `mypy.ini` | Absent | No Python typecheck, despite `# type: ignore[...]` comments in the source. |
| [x] | `.pre-commit-config.yaml` | Absent | No commit hooks. Nothing validates a commit before it lands. |
| [x] | `.gitattributes` | Absent | No line-ending or LFS rules. On Windows, Git warns `LF will be replaced by CRLF` on every text add. That is expected, not a problem. |
| [x] | `.editorconfig` | Absent | No enforced whitespace/indent config. Match the file you are editing. |
| [x] | `CONTRIBUTING.md` | Absent | No contribution guide. `AGENTS.md` fills that role. |
| [x] | `LICENSE` | Absent | No licence file is committed. Do not assume a licence for reuse or redistribution. |
| [x] | `opencode.json` / nested `AGENTS.md` | Absent | No agent config in the repo. The root `AGENTS.md` is the single native instruction file — no nested or per-tool mirrors. |

## 1.4 The Inert `# noqa` Markers

Seven `# noqa` comments exist in the tree. **None of them are enforced by any
installed tool.** They are leftovers from a linter that is not present.

| Done | Count | Code | Linter | Locations |
| ---- | ----: | ---- | ----- | --------- |
| [x] | 4 | `BLE001` | ruff (blind `except Exception`) | `app/db.py:60`, `app/db.py:79`, `app/main.py:43`, `app/services/classifier.py:93` |
| [x] | 3 | `D107` | pydocstyle (missing docstring in `__init__`) | `tests/test_mediawiki.py:54`, `:67`, `:269` |

Keep them as written. They are documentation of intent, not configuration. Deleting
them loses the reason each broad `except` is safe; adding a ruff config to "activate"
them would violate the scope lock in §1.3.

## 1.5 Root-Level Working State

| Done | Item | State |
| ---- | ---- | ----- |
| [x] | Ignored artefacts present | `backend/{app,tests}/**/__pycache__/` only. No `node_modules/`, no `.venv/`, no `dist/`. |
| [x] | Root entry point | None. Every command is CWD-sensitive and lives in `backend/`, `frontend/`, or `database/` — see `AGENTS.md` §3. |

---

# 2. Backend — Application Core

| Done | File | Responsibility | Check when touched |
| ---- | ---- | -------------- | ------------------ |
| [ ] | `backend/app/__init__.py` | Package root, exports `__version__ = "0.1.0"`. | Keep in sync with `config.version`. |
| [ ] | `backend/app/main.py` | `create_app()`, lifespan, CORS middleware, global `WikipediaError` handler, `/api/health`, `/`. | `main.py:33-36` only assigns `app.state` when it is `None` — never make it unconditional. Extend the existing CORS config and exception handler; do not add a parallel error path. |
| [ ] | `backend/app/config.py` | `Settings` (pydantic-settings) and `get_settings()` (`@lru_cache`). `api_prefix = "/api"` at line 15. | `env_file` is relative, so `.env` only loads when CWD is `backend/`. Settings are read once per process; changing `.env` needs a restart. |
| [ ] | `backend/app/db.py` | Engine, `session_scope()` contextmanager, `Base.metadata.create_all`, `ping()`. | `session_scope()` yields `None` when the engine is unavailable (`db.py:53`) — persistence must never fail a request. The `# noqa: BLE001` at lines 60 and 79 is deliberate. |
| [ ] | `backend/app/models.py` | SQLAlchemy tables: `articles` (line 35), `article_links` (line 60), `analysis_runs` (line 88), plus `Base` (line 28). | **Two-file invariant:** must be updated together with `database/init.sql`. |
| [ ] | `backend/app/repository.py` | The only module that writes rows. Stores analyses, replaces an article's links wholesale, records runs. | Broad `except Exception` is intentional — persistence degrades to no-op rather than failing the request. |
| [ ] | `backend/app/schemas.py` | Pydantic request/response models, `ExistenceMixin.state` computed field, `ConnectionState` literal. | `state` is `@computed_field`, not settable. API tests assert exact payload dicts, so adding or renaming a field breaks the suite. |
| [ ] | `backend/app/dependencies.py` | `Annotated` aliases: `ClientDep`, `SettingsDep`, `TitleQuery` (1–512), `SearchQuery` (strip whitespace, 1–256). | `TitleQuery`/`SearchQuery` are the only input-validation seam. Titles are query params, never path params. |

---

# 3. Backend — Routers (HTTP only)

No router builds SQL. `sqlalchemy` must never be imported here.

| Done | File | Endpoints | Check when touched |
| ---- | ---- | --------- | ------------------ |
| [ ] | `backend/app/routers/__init__.py` | Re-exports both routers. | — |
| [ ] | `backend/app/routers/articles.py` | `GET /api/articles/search` (line 33), `GET /api/articles/find` (53), `GET /api/article` (65), `GET /api/article/links` (75), `GET /api/articles/resolve` (107) | Note the param split: `title=` for `/api/article*`, `q=` for search/find, repeated `titles=` for resolve. `_upstream_error` at line 23 mirrors the copy in `analysis.py` — keep both in sync. |
| [ ] | `backend/app/routers/analysis.py` | `POST /api/analyze` (line 42), `GET /api/connections/missing` (57), `GET /api/connections/one-way` (76), `GET /api/connections/map` (94). **No history endpoint** — `GET /api/analyses/recent` was removed in `c7d5344`. | `_upstream_error` at line 32 — a deliberate duplicate of the one in `articles.py`, not a shared helper. `repository.recent_analyses` was deleted in the same commit; `AnalysisRun` is still written by `store_analysis`, never read back. |

---

# 4. Backend — Services (no FastAPI)

Zero `fastapi` imports are permitted in this directory.

| Done | File | Responsibility | Check when touched |
| ---- | ---- | -------------- | ------------------ |
| [ ] | `backend/app/services/__init__.py` | Package marker. | — |
| [ ] | `backend/app/services/mediawiki.py` | **The only module that performs HTTP.** Exceptions `WikipediaError` (31) / `ArticleNotFoundError` (35); helpers `normalize_title` (39), `title_key` (45), `chunked` (51), `wiki_host` (57), `is_internal_article_link` (63); `ArticleLinks` (84); `MediaWikiClient` (92) with `search_articles`, `get_article`, `find_article`, `get_article_links`, `resolve_titles`, `get_links_for_page_ids`, `wikidata_descriptions`, and — added in `a48046f` — `get_page_descriptions`. | All requests funnel through the private `_api_get` (line 116). Batch size is the private `_MAX_TITLES_PER_REQUEST = 50`, **not** the `missing_check_batch_size` setting, which is dead config. Two attempts with a 1s sleep between them. |
| [ ] | `backend/app/services/analysis.py` | The analysis pipeline. `index_resolved` (52), `LinkGraph` (76), `OneWayResult` (93), `build_link_graph` (100), `classify_links` (138, **new in `a48046f`**), `detect_missing_connections` (177), `detect_one_way_connections` (198), `build_extracted_links` (256), `build_connection_map` (301), `analyze_article` (398). | `build_extracted_links` (lines 278-284) drops any link the existence check did not answer. Do not "fix" this by defaulting to `exists`/`missing` — a partial answer must not look like a complete one. Line numbers shifted when `classify_links` was inserted. |
| [ ] | `backend/app/services/classifier.py` | Wikidata-description-based `person`/`place`/`other` classification. `classify_description` (63), `looks_like_person` (73), `classify_titles` (81). | Best-effort by design; the `# noqa: BLE001` at line 93 is deliberate. `looks_like_person` is currently uncalled — wired for future use, do not delete as cleanup. |

---

# 5. Backend — Tests

68 tests total: 25 + 19 + 24. Re-verified 2026-09-26 after `a48046f` (was 59: 16 + 19 + 24).

**The suite does not currently run green in this environment.** `pytest-asyncio` and
`httpx2` are listed in `requirements.txt` but are **not installed**, so
`asyncio_mode = auto` never applies and 43 of the 68 tests fail with 25 passing. This is
a missing-dependency problem, not a code regression. Run
`pip install -r requirements.txt` from `backend/` before trusting any test result.
Until then, `pytest --collect-only` is the only reliable count.

| Done | File | Contents | Check when touched |
| ---- | ---- | -------- | ------------------ |
| [ ] | `backend/tests/__init__.py` | Makes `tests` importable so `python -m tests.smoke_live` works. | — |
| [ ] | `backend/tests/conftest.py` | Exactly one fixture: `settings`, with `database_url=""` and explicit budgets. | `pytest.ini` sets `pythonpath = .`, so pytest must run from `backend/`. |
| [ ] | `backend/tests/fake_wikipedia.py` | `FakeWikipediaClient` — duck-typed stand-in injected through `app.state`. Fixture graph: `Ada Lovelace` (page 1) → `Analytical Engine` (2, mutual), `London` (3, one-way), `Byron's Daughter` (missing, novel → other), `Somerton, Malta` (missing, village → place). Records `link_calls`, `resolve_calls`, `reverse_calls`. | The primary no-network seam. Extend this rather than adding a mocking library. |
| [ ] | `backend/tests/test_analysis.py` | 25 tests (was 16; 9 added in `a48046f`). Graph building, missing/one-way detection, budgets, map edge statuses, self-link removal, redirect attribution, people/place classification and truncation. | Monkeypatches by reassigning instance attributes on the fake. |
| [ ] | `backend/tests/test_api.py` | 19 tests. Every route plus 404/422/502 paths. | **Asserts exact whole payloads.** Any schema field change breaks these. |
| [ ] | `backend/tests/test_mediawiki.py` | 24 tests. Title normalisation, `chunked`, `is_internal_article_link`, `wiki_host`, resolve/redirect/invalid handling, `find_article` fallbacks, namespace filtering, dedup. | Uses `StubClient` / `SequencedStubClient`, which skip `super().__init__()` and replace `_api_get`. The three `# noqa: D107` markers (lines 54, 67, 269) are load-bearing comments. |
| [ ] | `backend/tests/smoke_live.py` | Live script against the real MediaWiki/Wikidata APIs. | **Not collected by pytest** (filename does not match `test_*.py`) and not a substitute for it. The only file permitted to touch the network, and only when run deliberately. |

---

# 6. Backend — Config

| Done | File | Purpose | Check when touched |
| ---- | ---- | ------- | ------------------ |
| [ ] | `backend/requirements.txt` | All `>=` constraints, nothing pinned. Includes the unusual `httpx2>=2.0` with a comment explaining that Starlette's `TestClient` moved to it. | `httpx` (0.x) is still the *runtime* client. Do not "clean up" the duplicate — tests break. |
| [ ] | `backend/pytest.ini` | `asyncio_mode = auto`, `pythonpath = .`, `testpaths = tests`, `filterwarnings = error` with `DeprecationWarning` ignored. | `filterwarnings = error` means any new non-Deprecation warning fails the suite. |
| [ ] | `backend/.env.example` | Template for the 12 settings, all optional. | Copy to `.env`; never commit `.env`. |
| [ ] | `backend/.gitignore` | Backend-local ignores. | — |

---

# 7. Database

| Done | File | Purpose | Check when touched |
| ---- | ---- | ------- | ------------------ |
| [ ] | `database/docker-compose.yml` | `postgres:16-alpine`, container `find-missing-db`, db/user/password all `find_missing`/`postgres`, port 5432, named volume `pgdata`, healthcheck via `pg_isready`. | `init.sql` is mounted read-only and runs on **first volume creation only**. |
| [ ] | `database/init.sql` | `articles`, `article_links`, `analysis_runs`; wrapped in `BEGIN;`/`COMMIT;` with `IF NOT EXISTS` throughout; ends with three documented example queries. | **Two-file invariant:** must be updated together with `backend/app/models.py`. Already carries one object the models do not: the partial index `ix_article_links_missing ON article_links (target_normalized_title) WHERE NOT exists`. `create_all()` will never produce it. |
| [ ] | `database/README.md` | States the models ↔ `init.sql` obligation explicitly. | The documented reason the two-file invariant exists. |

---

# 8. Frontend — Entry Points and Config

| Done | File | Responsibility | Check when touched |
| ---- | ---- | -------------- | ------------------ |
| [ ] | `frontend/index.html` | Vite HTML entry, mounts `#root`. | — |
| [ ] | `frontend/package.json` | Scripts: `dev`, `build`, `lint`, `preview`. Deps: cytoscape, react, react-dom, react-router-dom. | **No `test` script and no test runner exist.** `@types/react*` are installed but unused — the project is plain JSX. |
| [ ] | `frontend/package-lock.json` | Lockfile, version 3. | Use `npm ci`, not `npm install`, for reproducible installs. |
| [ ] | `frontend/vite.config.js` | React plugin, port 5173, proxies `/api` to `http://127.0.0.1:8000`. | `VITE_API_PROXY_TARGET` is read from `process.env` at line 6 — **not** from a `.env` file. The target is `127.0.0.1`, not `localhost`. |
| [ ] | `frontend/.oxlintrc.json` | Two explicit rules: `react/rules-of-hooks` (error), `react/only-export-components` (warn, `allowConstantExport: true`). | The `allowConstantExport` setting is why `AnalysisContext.jsx` and `Layout.jsx` can co-export constants with components. |
| [ ] | `frontend/.env.example` | Documents `VITE_API_BASE_URL`. | Leave unset to use the dev proxy. |
| [ ] | `frontend/.gitignore` | Frontend-local ignores. | — |
| [ ] | `frontend/public/favicon.svg` | Favicon. | — |
| [ ] | `frontend/public/icons.svg` | Icon sprite. | — |

---

# 9. Frontend — Source Core

| Done | File | Responsibility | Check when touched |
| ---- | ---- | -------------- | ------------------ |
| [ ] | `frontend/src/main.jsx` | React root, router provider, imports `./index.css`. | Uses explicit `.jsx` extensions (unlike most other files — both work under Vite). |
| [ ] | `frontend/src/index.css` | Global reset plus **all design tokens at lines 1-67**. Palette migrated to Miro in `97955b0`. | The only place tokens are edited. `--accent: #4262ff` is the interactive hue; `--primary: #1c1c1e` is the near-black action colour, not an accent. `--radius-xl: 16px`. Success is `--mutual: #00b473` — **there is no `--positive` token any more**. Never add a colour literal in a component. |
| [ ] | `frontend/src/App.jsx` | Route table. `/`, `/search`, `/analyze`, `/people-and-places` (**new in `a48046f`**), `/missing-connections`, `/one-way-connections`, `/connection-map`, `/home` (redirect to `/`), `*` → 404. | `ConnectionMapPage` is `lazy()`-loaded (line 15) because Cytoscape is heavy. Follow that pattern for any new heavy route. |
| [ ] | `frontend/src/api/client.js` | `ApiError` (9), `query` (46), and the endpoint wrappers. | `DEFAULT_BASE_URL = '/api'`. In use: `searchArticles` (SearchBar), `analyzeArticle` (AnalysisContext), `findArticle` (SearchPage), `getConnectionMap` (ConnectionMapPage). **Declared but currently uncalled:** `getArticle`, `getArticleLinks`, `checkArticlesExist`, `getMissingConnections`, `getOneWayConnections` — they exist, so do not treat the backend routes as dead. `status === 0` means the backend was unreachable. |
| [ ] | `frontend/src/context/AnalysisContext.jsx` | Single `useState` object, `AnalysisProvider` (27), `useAnalysis` (75). | React 19 form: `<AnalysisContext value={...}>`, no `.Provider`. `useAnalysis()` throws outside the provider. `run` is `useCallback(fn, [])` to keep identity stable. All result pages share this one context — navigating between them does not refetch. |
| [ ] | `frontend/src/hooks/useArticleParam.js` | Syncs `?title=` with the context. | URL is the source of truth. Uses a `useRef` guard to prevent re-runs, and rewrites the URL with `replace: true` when MediaWiki resolved a different title. |

---

# 10. Frontend — Pages

| Done | File | Route | Responsibility | Check when touched |
| ---- | ---- | ----- | -------------- | ------------------ |
| [ ] | `frontend/src/pages/HomePage.jsx` | `/` | Landing page. `FEATURES` (6), `EXAMPLES` (21: Chandni Chowk, Ada Lovelace, Bongaon). | — |
| [ ] | `frontend/src/pages/SearchPage.jsx` | `/search` | Resolves a name to one article, then hands off to analysis. `IDLE` state (9). | Guards against stale responses — results belong on screen only for the current query. |
| [ ] | `frontend/src/pages/AnalysisPage.jsx` | `/analyze` | Thin wrapper over `ResultLayout` + `ArticleConnections`; gained the entity sections in `a48046f`. | — |
| [ ] | `frontend/src/pages/EntitiesPage.jsx` | `/people-and-places` | **New in `a48046f`.** People and places split by whether the target has an article. | New page — check it against the `/analyze` shape before assuming parity. |
| [ ] | `frontend/src/pages/MissingConnectionsPage.jsx` | `/missing-connections` | Wrapper over `ResultLayout` + `MissingConnectionsList`. | — |
| [ ] | `frontend/src/pages/OneWayConnectionsPage.jsx` | `/one-way-connections` | Wrapper over `ResultLayout` + `OneWayConnectionsList`. | — |
| [ ] | `frontend/src/pages/ConnectionMapPage.jsx` | `/connection-map` | Second, independent call to `getConnectionMap` for the graph. | The only page that fetches on its own; the map payload is not part of `AnalysisResult`. |
| [ ] | `frontend/src/pages/NotFoundPage.jsx` | `*` | 404. | — |
| [ ] | `frontend/src/pages/HomePage.module.css` | — | Home page styles. | Colocated CSS Module. |
| [ ] | `frontend/src/pages/SearchPage.module.css` | — | Search page styles. | Colocated CSS Module. |

---

# 11. Frontend — Components

Every `.jsx` has a colocated `.module.css`. Base/structural classes are camelCase;
modifier/variant classes are snake_case and are built with bracket notation
(`` styles[`badge_${type}`] ``). Copy the nearest neighbour rather than guessing.

| Done | File | Exports | Responsibility | Check when touched |
| ---- | ---- | ------- | -------------- | ------------------ |
| [ ] | `frontend/src/components/Layout.jsx` | default `Layout` | Shell + `NAV_ITEMS` (5). | `NAV_ITEMS` co-exists with the component, which is why `allowConstantExport` is on. |
| [ ] | `frontend/src/components/SearchBar.jsx` | default `SearchBar` | Debounced (300ms) search-as-you-type with a results dropdown and click-outside handling. | The one place `--shadow-lg` is used (`SearchBar.module.css:91`). Do not spread it. |
| [ ] | `frontend/src/components/ResultLayout.jsx` | default `ResultLayout` | Shared shell for every result page: SearchBar, Loading, ErrorMessage + retry, EmptyState, ArticleSummary, three StatCards, then children gated on `status === 'ready' && article`. | New result pages should compose this rather than rebuilding it. |
| [ ] | `frontend/src/components/ArticleSummary.jsx` | default `ArticleSummary` | Article title, description, extract, link out to Wikipedia. | External links need `rel="noreferrer noopener"`. |
| [ ] | `frontend/src/components/ArticleConnections.jsx` | default `ArticleConnections` | The full link list with pagination (`PAGE_SIZE = 50`, line 6). | Counts are derived from the rows on screen so the list and numbers always agree. |
| [ ] | `frontend/src/components/ConnectionLists.jsx` | `MissingConnectionsList` (22), `OneWayConnectionsList` (135) | The two gap lists. `FILTERS` (11), `TYPED` (20). | Multi-export file, so named exports only. |
| [ ] | `frontend/src/components/EntitySections.jsx` | default `EntitySections` | **New in `a48046f`.** People and places sections rendered from the classifier split. | New component — same CSS Module and derived-not-stored rules as its neighbours. |
| [ ] | `frontend/src/components/EntitySections.module.css` | — | **New in `a48046f`.** Colocated styles for the above. | Tokens only, no colour literals. |
| [ ] | `frontend/src/components/ConnectionMap.jsx` | default `ConnectionMap` | Cytoscape render. `LEGEND_ITEMS` (7), `elementsFor` (14), `stylesheet` (46). | Pulled in via `lazy()` on purpose. Missing nodes must stay visually distinct. |
| [ ] | `frontend/src/components/ui.jsx` | 8 named exports | `EntityBadge` (9), `ConnectionStateBadge` (18), `StatCard` (33), `Card` (43), `EmptyState` (60), `Loading` (70), `ErrorMessage` (79), `Legend` (96). | `ENTITY_LABELS` (3) is the entity-type display map. `ErrorMessage` accepts an `Error` or a string. |
| [ ] | `components/*.module.css` (8 files) | — | Colocated styles for the components above. | No new colour literals — tokens only. |

---

# 12. Documentation

| Done | File | Purpose | Check when touched |
| ---- | ---- | ------- | ------------------ |
| [ ] | `docs/PRD.md` | Product requirements v1.0, 22 sections. §18 holds the binding MUST / MUST-NOT release scope. §3 lists the non-goals. | §18 is the scope lock. If a task needs a MUST-NOT feature, ask before starting. |
| [ ] | `docs/TRD.md` | Technical requirements v1.0, 25 sections. | **Known-stale** — see §13. |
| [ ] | `docs/PHASES.md` | 9-phase checklist with entry/exit criteria, dependency register, acceptance list. | Phase 4's gate requires "backend lint", which does not exist. |
| [ ] | `docs/ARCHITECTURE.md` | Architecture v1.0, sections 1-10. Section 11 (Deployment / Infrastructure) is a **TODO placeholder** — the source text was truncated when it was written. | Fill section 11 in when the deployment design is decided. |
| [ ] | `docs/DESIGN.md` | Design-system spec: colour, type, radius tokens. **Moved here from the repository root in `97955b0`.** Not an architecture document — it says nothing about setup, routes, or structure. | The tokens are materialised in `frontend/src/index.css:1-67`. Edit the CSS, then keep this in sync. It references tooling not present in this repo (`scripts/derive-examples-block.mjs`, `/preview-design`, `/generate-kit`, `TO_FILL` markers) — do not treat those as available. |
| [ ] | `docs/CHECKLIST.md` | This file. | Update it in the same commit as any file added, removed, or renamed. |

---

# 13. Known Divergences

`docs/` was written as a specification before and alongside the implementation. The
code is the source of truth. Do not edit a doc to make a plan look satisfied — change
the code, and change the doc in the same commit when the spec itself was wrong.

| Done | Document claim | Reality |
| ---- | -------------- | ------- |
| [ ] | `TRD.md` §6: base path `/api/v1`, version `v1` | Code serves `/api` (`config.py:15`). The string `v1` appears zero times in `backend/`. |
| [ ] | `TRD.md` §6.8: error envelope `{"error": {"code", "message"}}` | Backend and frontend both use FastAPI's `{"detail": ...}`. |
| [ ] | `TRD.md` §5: tables `links`, `missing_connections` | Code has `articles`, `article_links`, `analysis_runs`. |
| [ ] | `TRD.md` §4.2: all versions "TBD" | Actually constrained in `requirements.txt` / `package.json`. |
| [ ] | `TRD.md` Appendix C: `backend/{api,services,database,wikipedia}`, `tests/{unit,integration,e2e}` | Does not exist. See `AGENTS.md` §2 for the real layout. |
| [ ] | `TRD.md` §16.3: schema changes via versioned migrations | No migration tool. Only `create_all()` and hand-applied `init.sql`. |
| [ ] | No document mentions a history endpoint | `GET /api/analyses/recent` was removed in `c7d5344`. Do not re-add it, and do not document it. |
| [ ] | `ARCHITECTURE.md` §8.1: tables `articles`/`links`/`missing_connections` with `id`/`title`/`url` | Same drift as TRD §5. |
| [ ] | `PHASES.md` Phase 4 gate: "runs backend lint successfully" | No backend lint exists. No `pyproject.toml` / `ruff.toml` / `mypy.ini`. |
| [ ] | `PHASES.md` Phases 1-4 unchecked | Updated in `5773619` to match the implemented state. Re-verify against exit criteria, not task counts. |
| [ ] | `PRD.md` §8 data model: `links`, `missing_connections` | Same drift as TRD §5. |
| [ ] | `PRD.md` `Author: TBD`, §22 approval table `TBD` | Fill in the real owner; do not leave placeholders once known. |
| [ ] | Pre-`97955b0` token values quoted in older docs | `--primary: #9fe870`, `--radius-xl: 24px`, and a `--positive` token no longer exist. Anything still citing them is stale. |

---

# 14. Repository-Wide Verification

Run after any change that touches more than one file.

| Done | Check | Command | CWD |
| ---- | ----- | ------- | --- |
| [ ] | Backend tests pass (68) | `pytest` | `backend` |
| [ ] | Frontend lint passes | `npm run lint` | `frontend` |
| [ ] | Frontend builds | `npm run build` | `frontend` |
| [ ] | Models match SQL | diff `models.py` tables against `init.sql` | — |
| [ ] | Docs match code | re-read §13 of this file | — |
| [ ] | No secrets staged | `git status` + `git diff` | — |

Do **not** add a Python lint/typecheck step to this table — none exists.

**Blocker as of 2026-09-26:** the first row cannot pass. `pytest-asyncio` and `httpx2`
are in `requirements.txt` but absent from the environment, so plain `pytest` dies on
`Unknown config option: asyncio_default_fixture_loop_scope` (via `filterwarnings =
error`) and, with that warning suppressed, reports **43 failed / 25 passed**. Install the
requirements first. `pytest --collect-only` still works and reports 68.

Also note `filterwarnings = error` turns the `PytestConfigWarning` above into a hard
`INTERNALERROR` that runs **zero** tests — a silent pass-looking failure. Suppress it to
see the real result: `pytest -W "ignore::pytest.PytestConfigWarning"`.

---

# 15. File-Count Reference — [x] verified 2026-09-26 (re-verified after `a48046f`, `97955b0`)

| Done | Area | Count | Note |
| ---- | ---- | ----: | ---- |
| [x] | `backend/app/` | 15 | 12 modules + 3 `__init__.py` |
| [x] | `backend/tests/` | 7 | 6 modules + `__init__.py` |
| [x] | Backend config | 4 | `requirements.txt`, `pytest.ini`, `.env.example`, `.gitignore` |
| [x] | `database/` | 3 | compose, SQL, readme |
| [x] | `frontend/src/` | 34 | 20 `.jsx` + 11 `.module.css` + 3 others |
| [x] | Frontend config/entry/public | 9 | incl. `package-lock.json`, `.oxlintrc.json`, 2 SVGs |
| [x] | `docs/` | 6 | PRD, TRD, PHASES, ARCHITECTURE, DESIGN, this file |
| [x] | Repository root | 2 | `.gitignore`, `AGENTS.md` |
| [x] | **Total** | **80** | |

Frontend `src/` detail (34): 20 `.jsx` = `App.jsx`, `main.jsx`,
`context/AnalysisContext.jsx`, 9 in `components/`, 8 in `pages/`; 11 `.module.css` = 9
colocated with components + 2 with pages; 3 others = `index.css`, `api/client.js`,
`hooks/useArticleParam.js`.

Reconcile with `git ls-files` — this table is the thing to check against when a file is
added, removed, or renamed.
