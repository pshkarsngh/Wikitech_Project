# Project File Checklist

## Find the Missing Connections

**Version:** 1.0
**Date:** 26 September 2026
**Scope:** Every tracked file in the repository, with its responsibility and the
checks that apply when you touch it.

This is a navigation and maintenance aid, not a progress tracker. Phase-level progress
lives in `PHASES.md`; requirements live in `PRD.md`; technical specification lives in
`TRD.md`; structure and invariants live in `ARCHITECTURE.md` and `../AGENTS.md`.

**Verification basis:** 76 tracked files. Code is truth — where this file and the code
disagree, the code wins and this file is the bug.

---

# 1. Repository Root

| File | Purpose | Check when touched |
| ---- | ------- | ------------------ |
| `AGENTS.md` | Load-bearing project instructions: invariants, conventions, commands. | Read it before any change. Update it in the same commit as any convention change. |
| `DESIGN.md` | Design-system spec (colour, type, radius tokens). Not an architecture doc. | Tokens are already in `frontend/src/index.css:1-71`. Change the CSS, keep this in sync. |
| `.gitignore` | Excludes `.env`, `.agents/`, `.claude/`, `skills/`, `node_modules/`, `.venv/`. | `AGENTS.md` must **not** appear here — it is meant to be committed. |
| `README.md` | **Does not exist.** No root readme is committed. | If you add one, do not invent setup steps that contradict `AGENTS.md` §3. |
| `.github/` | **Does not exist.** No CI. | Do not assume CI catches anything. |
| `Dockerfile` | **Does not exist.** No container image for the app. | `database/docker-compose.yml` is the only Docker artefact. |
| `pyproject.toml` / `ruff.toml` / `mypy.ini` / `.pre-commit-config.yaml` | **Do not exist.** No backend lint, format, or typecheck. | Do not add a substitute without asking. |

---

# 2. Backend — Application Core

| File | Responsibility | Check when touched |
| ---- | -------------- | ------------------ |
| `backend/app/__init__.py` | Package root, exports `__version__ = "0.1.0"`. | Keep in sync with `config.version`. |
| `backend/app/main.py` | `create_app()`, lifespan, CORS middleware, global `WikipediaError` handler, `/api/health`, `/`. | `main.py:33-36` only assigns `app.state` when it is `None` — never make it unconditional. Extend the existing CORS config and exception handler; do not add a parallel error path. |
| `backend/app/config.py` | `Settings` (pydantic-settings) and `get_settings()` (`@lru_cache`). `api_prefix = "/api"` at line 15. | `env_file` is relative, so `.env` only loads when CWD is `backend/`. Settings are read once per process; changing `.env` needs a restart. |
| `backend/app/db.py` | Engine, `session_scope()` contextmanager, `Base.metadata.create_all`, `ping()`. | `session_scope()` yields `None` when the engine is unavailable (`db.py:53`) — persistence must never fail a request. The `# noqa: BLE001` at lines 60 and 79 is deliberate. |
| `backend/app/models.py` | SQLAlchemy tables: `articles` (line 35), `article_links` (line 60), `analysis_runs` (line 88), plus `Base` (line 28). | **Two-file invariant:** must be updated together with `database/init.sql`. |
| `backend/app/repository.py` | The only module that writes rows. Stores analyses, replaces an article's links wholesale, records runs. | Broad `except Exception` is intentional — persistence degrades to no-op rather than failing the request. |
| `backend/app/schemas.py` | Pydantic request/response models, `ExistenceMixin.state` computed field, `ConnectionState` literal. | `state` is `@computed_field`, not settable. API tests assert exact payload dicts, so adding or renaming a field breaks the suite. |
| `backend/app/dependencies.py` | `Annotated` aliases: `ClientDep`, `SettingsDep`, `TitleQuery` (1–512), `SearchQuery` (strip whitespace, 1–256). | `TitleQuery`/`SearchQuery` are the only input-validation seam. Titles are query params, never path params. |

---

# 3. Backend — Routers (HTTP only)

No router builds SQL. `sqlalchemy` must never be imported here.

| File | Endpoints | Check when touched |
| ---- | --------- | ------------------ |
| `backend/app/routers/__init__.py` | Re-exports both routers. | — |
| `backend/app/routers/articles.py` | `GET /api/articles/search` (line 33), `GET /api/articles/find` (53), `GET /api/article` (65), `GET /api/article/links` (75), `GET /api/articles/resolve` (107) | Note the param split: `title=` for `/api/article*`, `q=` for search/find, repeated `titles=` for resolve. `_upstream_error` at line 23 mirrors the copy in `analysis.py` — keep both in sync. |
| `backend/app/routers/analysis.py` | `POST /api/analyze` (line 42), `GET /api/connections/missing` (57), `GET /api/connections/one-way` (76), `GET /api/connections/map` (94), `GET /api/analyses/recent` (110) | `_upstream_error` at line 32 — a deliberate duplicate of the one in `articles.py`, not a shared helper. `/api/analyses/recent` returns `[]` when no database is configured. |

---

# 4. Backend — Services (no FastAPI)

Zero `fastapi` imports are permitted in this directory.

| File | Responsibility | Check when touched |
| ---- | -------------- | ------------------ |
| `backend/app/services/__init__.py` | Package marker. | — |
| `backend/app/services/mediawiki.py` | **The only module that performs HTTP.** Exceptions `WikipediaError` (31) / `ArticleNotFoundError` (35); helpers `normalize_title` (39), `title_key` (45), `chunked` (51), `wiki_host` (57), `is_internal_article_link` (63); `ArticleLinks` (84); `MediaWikiClient` (92) with `search_articles`, `get_article`, `find_article`, `get_article_links`, `resolve_titles`, `get_links_for_page_ids`, `wikidata_descriptions`. | All requests funnel through the private `_api_get` (line 116). Batch size is the private `_MAX_TITLES_PER_REQUEST = 50`, **not** the `missing_check_batch_size` setting, which is dead config. Two attempts with a 1s sleep between them. |
| `backend/app/services/analysis.py` | The analysis pipeline. `index_resolved` (52), `LinkGraph` (76), `OneWayResult` (93), `build_link_graph` (100), `detect_missing_connections` (138), `detect_one_way_connections` (158), `build_extracted_links` (216), `build_connection_map` (261), `analyze_article` (358). | `build_extracted_links` (lines 238-244) drops any link the existence check did not answer. Do not "fix" this by defaulting to `exists`/`missing` — a partial answer must not look like a complete one. |
| `backend/app/services/classifier.py` | Wikidata-description-based `person`/`place`/`other` classification. `classify_description` (63), `looks_like_person` (73), `classify_titles` (81). | Best-effort by design; the `# noqa: BLE001` at line 93 is deliberate. `looks_like_person` is currently uncalled — wired for future use, do not delete as cleanup. |

---

# 5. Backend — Tests

| File | Contents | Check when touched |
| ---- | -------- | ------------------ |
| `backend/tests/__init__.py` | Makes `tests` importable so `python -m tests.smoke_live` works. | — |
| `backend/tests/conftest.py` | Exactly one fixture: `settings`, with `database_url=""` and explicit budgets. | `pytest.ini` sets `pythonpath = .`, so pytest must run from `backend/`. |
| `backend/tests/fake_wikipedia.py` | `FakeWikipediaClient` — duck-typed stand-in injected through `app.state`. Fixture graph: `Ada Lovelace` (page 1) → `Analytical Engine` (2, mutual), `London` (3, one-way), `Byron's Daughter` (missing, novel → other), `Somerton, Malta` (missing, village → place). Records `link_calls`, `resolve_calls`, `reverse_calls`. | The primary no-network seam. Extend this rather than adding a mocking library. |
| `backend/tests/test_analysis.py` | 16 tests. Graph building, missing/one-way detection, budgets, map edge statuses, self-link removal, redirect attribution. | Monkeypatches by reassigning instance attributes on the fake. |
| `backend/tests/test_api.py` | 19 tests. Every route plus 404/422/502 paths. | **Asserts exact whole payloads.** Any schema field change breaks these. |
| `backend/tests/test_mediawiki.py` | 24 tests. Title normalisation, `chunked`, `is_internal_article_link`, `wiki_host`, resolve/redirect/invalid handling, `find_article` fallbacks, namespace filtering, dedup. | Uses `StubClient` / `SequencedStubClient`, which skip `super().__init__()` and replace `_api_get`. The three `# noqa: D107` markers (lines 54, 67, 269) are load-bearing comments. |
| `backend/tests/smoke_live.py` | Live script against the real MediaWiki/Wikidata APIs. | **Not collected by pytest** (filename does not match `test_*.py`) and not a substitute for it. The only file permitted to touch the network, and only when run deliberately. |

---

# 6. Backend — Config

| File | Purpose | Check when touched |
| ---- | ------- | ------------------ |
| `backend/requirements.txt` | All `>=` constraints, nothing pinned. Includes the unusual `httpx2>=2.0` with a comment explaining that Starlette's `TestClient` moved to it. | `httpx` (0.x) is still the *runtime* client. Do not "clean up" the duplicate — tests break. |
| `backend/pytest.ini` | `asyncio_mode = auto`, `pythonpath = .`, `testpaths = tests`, `filterwarnings = error` with `DeprecationWarning` ignored. | `filterwarnings = error` means any new non-Deprecation warning fails the suite. |
| `backend/.env.example` | Template for the 12 settings, all optional. | Copy to `.env`; never commit `.env`. |
| `backend/.gitignore` | Backend-local ignores. | — |

---

# 7. Database

| File | Purpose | Check when touched |
| ---- | ------- | ------------------ |
| `database/docker-compose.yml` | `postgres:16-alpine`, container `find-missing-db`, db/user/password all `find_missing`/`postgres`, port 5432, named volume `pgdata`, healthcheck via `pg_isready`. | `init.sql` is mounted read-only and runs on **first volume creation only**. |
| `database/init.sql` | `articles`, `article_links`, `analysis_runs`; wrapped in `BEGIN;`/`COMMIT;` with `IF NOT EXISTS` throughout; ends with three documented example queries. | **Two-file invariant:** must be updated together with `backend/app/models.py`. Already carries one object the models do not: the partial index `ix_article_links_missing ON article_links (target_normalized_title) WHERE NOT exists`. `create_all()` will never produce it. |
| `database/README.md` | States the models ↔ `init.sql` obligation explicitly. | The documented reason the two-file invariant exists. |

---

# 8. Frontend — Entry Points and Config

| File | Responsibility | Check when touched |
| ---- | -------------- | ------------------ |
| `frontend/index.html` | Vite HTML entry, mounts `#root`. | — |
| `frontend/package.json` | Scripts: `dev`, `build`, `lint`, `preview`. Deps: cytoscape, react, react-dom, react-router-dom. | **No `test` script and no test runner exist.** `@types/react*` are installed but unused — the project is plain JSX. |
| `frontend/package-lock.json` | Lockfile, version 3. | Use `npm ci`, not `npm install`, for reproducible installs. |
| `frontend/vite.config.js` | React plugin, port 5173, proxies `/api` to `http://127.0.0.1:8000`. | `VITE_API_PROXY_TARGET` is read from `process.env` at line 6 — **not** from a `.env` file. The target is `127.0.0.1`, not `localhost`. |
| `frontend/.oxlintrc.json` | Two explicit rules: `react/rules-of-hooks` (error), `react/only-export-components` (warn, `allowConstantExport: true`). | The `allowConstantExport` setting is why `AnalysisContext.jsx` and `Layout.jsx` can co-export constants with components. |
| `frontend/.env.example` | Documents `VITE_API_BASE_URL`. | Leave unset to use the dev proxy. |
| `frontend/.gitignore` | Frontend-local ignores. | — |
| `frontend/public/favicon.svg` | Favicon. | — |
| `frontend/public/icons.svg` | Icon sprite. | — |

---

# 9. Frontend — Source Core

| File | Responsibility | Check when touched |
| ---- | -------------- | ------------------ |
| `frontend/src/main.jsx` | React root, router provider, imports `./index.css`. | Uses explicit `.jsx` extensions (unlike most other files — both work under Vite). |
| `frontend/src/index.css` | Global reset plus **all design tokens at lines 1-71**. | The only place tokens are edited. `--primary: #9fe870` is the single accent; `--radius-xl: 24px`; `--positive` is for success. Never add a colour literal in a component. |
| `frontend/src/App.jsx` | Route table. `/`, `/search`, `/analyze`, `/missing-connections`, `/one-way-connections`, `/connection-map`, `/home` (redirect to `/`), `*` → 404. | `ConnectionMapPage` is `lazy()`-loaded (line 14) because Cytoscape is heavy. Follow that pattern for any new heavy route. |
| `frontend/src/api/client.js` | `ApiError` (9), `query` (46), and the endpoint wrappers. | `DEFAULT_BASE_URL = '/api'`. In use: `searchArticles` (SearchBar), `analyzeArticle` (AnalysisContext), `findArticle` (SearchPage), `getConnectionMap` (ConnectionMapPage). **Declared but currently uncalled:** `getArticle`, `getArticleLinks`, `checkArticlesExist`, `getMissingConnections`, `getOneWayConnections` — they exist, so do not treat the backend routes as dead. `status === 0` means the backend was unreachable. |
| `frontend/src/context/AnalysisContext.jsx` | Single `useState` object, `AnalysisProvider` (27), `useAnalysis` (75). | React 19 form: `<AnalysisContext value={...}>`, no `.Provider`. `useAnalysis()` throws outside the provider. `run` is `useCallback(fn, [])` to keep identity stable. All result pages share this one context — navigating between them does not refetch. |
| `frontend/src/hooks/useArticleParam.js` | Syncs `?title=` with the context. | URL is the source of truth. Uses a `useRef` guard to prevent re-runs, and rewrites the URL with `replace: true` when MediaWiki resolved a different title. |

---

# 10. Frontend — Pages

| File | Route | Responsibility | Check when touched |
| ---- | ----- | -------------- | ------------------ |
| `frontend/src/pages/HomePage.jsx` | `/` | Landing page. `FEATURES` (6), `EXAMPLES` (21: Chandni Chowk, Ada Lovelace, Bongaon). | — |
| `frontend/src/pages/SearchPage.jsx` | `/search` | Resolves a name to one article, then hands off to analysis. `IDLE` state (9). | Guards against stale responses — results belong on screen only for the current query. |
| `frontend/src/pages/AnalysisPage.jsx` | `/analyze` | Thin wrapper over `ResultLayout` + `ArticleConnections`. | — |
| `frontend/src/pages/MissingConnectionsPage.jsx` | `/missing-connections` | Wrapper over `ResultLayout` + `MissingConnectionsList`. | — |
| `frontend/src/pages/OneWayConnectionsPage.jsx` | `/one-way-connections` | Wrapper over `ResultLayout` + `OneWayConnectionsList`. | — |
| `frontend/src/pages/ConnectionMapPage.jsx` | `/connection-map` | Second, independent call to `getConnectionMap` for the graph. | The only page that fetches on its own; the map payload is not part of `AnalysisResult`. |
| `frontend/src/pages/NotFoundPage.jsx` | `*` | 404. | — |
| `frontend/src/pages/HomePage.module.css` | — | Home page styles. | Colocated CSS Module. |
| `frontend/src/pages/SearchPage.module.css` | — | Search page styles. | Colocated CSS Module. |

---

# 11. Frontend — Components

Every `.jsx` has a colocated `.module.css`. Base/structural classes are camelCase;
modifier/variant classes are snake_case and are built with bracket notation
(`styles[\`badge_${type}\`]`). Copy the nearest neighbour rather than guessing.

| File | Exports | Responsibility | Check when touched |
| ---- | ------- | -------------- | ------------------ |
| `frontend/src/components/Layout.jsx` | default `Layout` | Shell + `NAV_ITEMS` (5). | `NAV_ITEMS` co-exists with the component, which is why `allowConstantExport` is on. |
| `frontend/src/components/SearchBar.jsx` | default `SearchBar` | Debounced (300ms) search-as-you-type with a results dropdown and click-outside handling. | The one place `--shadow-lg` is used (`SearchBar.module.css:91`). Do not spread it. |
| `frontend/src/components/ResultLayout.jsx` | default `ResultLayout` | Shared shell for every result page: SearchBar, Loading, ErrorMessage + retry, EmptyState, ArticleSummary, three StatCards, then children gated on `status === 'ready' && article`. | New result pages should compose this rather than rebuilding it. |
| `frontend/src/components/ArticleSummary.jsx` | default `ArticleSummary` | Article title, description, extract, link out to Wikipedia. | External links need `rel="noreferrer noopener"`. |
| `frontend/src/components/ArticleConnections.jsx` | default `ArticleConnections` | The full link list with pagination (`PAGE_SIZE = 50`, line 6). | Counts are derived from the rows on screen so the list and numbers always agree. |
| `frontend/src/components/ConnectionLists.jsx | `MissingConnectionsList` (22), `OneWayConnectionsList` (135) | The two gap lists. `FILTERS` (11), `TYPED` (20). | Multi-export file, so named exports only. |
| `frontend/src/components/ConnectionMap.jsx` | default `ConnectionMap` | Cytoscape render. `LEGEND_ITEMS` (7), `elementsFor` (14), `stylesheet` (46). | Pulled in via `lazy()` on purpose. Missing nodes must stay visually distinct. |
| `frontend/src/components/ui.jsx` | 8 named exports | `EntityBadge` (9), `ConnectionStateBadge` (18), `StatCard` (33), `Card` (43), `EmptyState` (60), `Loading` (70), `ErrorMessage` (79), `Legend` (96). | `ENTITY_LABELS` (3) is the entity-type display map. `ErrorMessage` accepts an `Error` or a string. |
| `*.module.css` (8 files) | — | Colocated styles for the above. | No new colour literals — tokens only. |

---

# 12. Documentation

| File | Purpose | Check when touched |
| ---- | ------- | ------------------ |
| `docs/PRD.md` | Product requirements v1.0, 22 sections. §18 holds the binding MUST / MUST-NOT release scope. §3 lists the non-goals. | §18 is the scope lock. If a task needs a MUST-NOT feature, ask before starting. |
| `docs/TRD.md` | Technical requirements v1.0, 25 sections. | **Known-stale** — see §13. |
| `docs/PHASES.md` | 9-phase checklist with entry/exit criteria, dependency register, acceptance list. | Phase 4's gate requires "backend lint", which does not exist. |
| `docs/ARCHITECTURE.md` | Architecture v1.0, sections 1-10. Section 11 (Deployment / Infrastructure) is a **TODO placeholder** — the source text was truncated when it was written. | Fill section 11 in when the deployment design is decided. |
| `docs/CHECKLIST.md` | This file. | Update it in the same commit as any file added, removed, or renamed. |

---

# 13. Known Divergences

`docs/` was written as a specification before and alongside the implementation. The
code is the source of truth. Do not edit a doc to make a plan look satisfied — change
the code, and change the doc in the same commit when the spec itself was wrong.

| Document claim | Reality |
| -------------- | ------- |
| `TRD.md` §6: base path `/api/v1`, version `v1` | Code serves `/api` (`config.py:15`). The string `v1` appears zero times in `backend/`. |
| `TRD.md` §6.8: error envelope `{"error": {"code", "message"}}` | Backend and frontend both use FastAPI's `{"detail": ...}`. |
| `TRD.md` §5: tables `links`, `missing_connections` | Code has `articles`, `article_links`, `analysis_runs`. |
| `TRD.md` §4.2: all versions "TBD" | Actually pinned in `requirements.txt` / `package.json`. |
| `TRD.md` Appendix C: `backend/{api,services,database,wikipedia}`, `tests/{unit,integration,e2e}` | Does not exist. See `AGENTS.md` §2 for the real layout. |
| `TRD.md` §16.3: schema changes via versioned migrations | No migration tool. Only `create_all()` and hand-applied `init.sql`. |
| `ARCHITECTURE.md` §8.1: tables `articles`/`links`/`missing_connections` with `id`/`title`/`url` | Same drift as TRD §5. |
| `PHASES.md` Phase 4 gate: "runs backend lint successfully" | No backend lint exists. No `pyproject.toml` / `ruff.toml` / `mypy.ini`. |
| `PHASES.md` Phases 1-4 unchecked | Substantially built already. Mark them against exit criteria, not task counts. |
| `PRD.md` §8 data model: `links`, `missing_connections` | Same drift as TRD §5. |
| `PRD.md` `Author: TBD`, §22 approval table `TBD` | Fill in the real owner; do not leave placeholders once known. |

---

# 14. Repository-Wide Verification

Run after any change that touches more than one file.

| Check | Command | CWD |
| ----- | ------- | --- |
| Backend tests pass (59) | `pytest` | `backend` |
| Frontend lint passes | `npm run lint` | `frontend` |
| Frontend builds | `npm run build` | `frontend` |
| Models match SQL | diff `models.py` tables against `init.sql` | — |
| Docs match code | re-read §13 of this file | — |
| No secrets staged | `git status` + `git diff` | — |

Do **not** add a Python lint/typecheck step to this table — none exists.

---

# 15. File-Count Reference

| Area | Count | Note |
| ---- | ----: | ---- |
| `backend/app/` | 15 | 12 modules + 3 `__init__.py` |
| `backend/tests/` | 7 | 6 modules + `__init__.py` |
| Backend config | 4 | `requirements.txt`, `pytest.ini`, `.env.example`, `.gitignore` |
| `database/` | 3 | compose, SQL, readme |
| `frontend/src/` | 31 | 14 `.jsx` + 13 `.module.css` + 4 others |
| Frontend config/entry/public | 9 | incl. `package-lock.json`, `.oxlintrc.json`, 2 SVGs |
| `docs/` | 5 | PRD, TRD, PHASES, ARCHITECTURE, this file |
| Repository root | 3 | `.gitignore`, `AGENTS.md`, `DESIGN.md` |
| **Total** | **77** | |

Frontend `src/` detail: `App.jsx`, `main.jsx`, `index.css`, `api/client.js` (4 others);
9 components as 7 `.jsx` + 7 colocated `.module.css`; 7 pages as 5 `.jsx` + 2
`.module.css`; plus `context/AnalysisContext.jsx` and `hooks/useArticleParam.js`.

Verify with `git ls-files` — this table is the thing to reconcile against.
