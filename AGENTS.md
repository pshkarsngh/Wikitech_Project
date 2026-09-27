# Wikitech — Find the Missing Connections

Analyzes an English Wikipedia article and surfaces two gaps: red links (people/places
mentioned but with no article of their own) and one-way links (A links to B, B does not
link back). FastAPI backend over the MediaWiki action API, Vite + React SPA with a
Cytoscape connection map, and an optional PostgreSQL cache.

## 2. Layout

```
backend/
  Dockerfile           release image: venv, non-root, HEALTHCHECK on /api/health
  app/
    main.py            create_app(), lifespan, CORS, WikipediaError handler
    config.py          Settings (pydantic-settings), get_settings() @lru_cache
    db.py              engine, session_scope(), Base.metadata.create_all
    models.py          SQLAlchemy tables: articles, article_links, analysis_runs
    repository.py      the only module that writes rows
    schemas.py         Pydantic request/response models
    dependencies.py    Annotated aliases: ClientDep, SettingsDep, TitleQuery, SearchQuery,
                      require_analysis_key  (the X-Api-Key gate)
    routers/           articles.py, analysis.py  (HTTP only)
    services/          analysis.py, budget.py, classifier.py, mediawiki.py  (no FastAPI)
  tests/               conftest.py, fake_wikipedia.py, smoke_live.py,
                      test_frontend_contract.py, test_persistence.py, test_*.py
  requirements.txt  pytest.ini  .env.example
frontend/
  Dockerfile           release image: vite build, served by nginx
  nginx.conf.template installed as /etc/nginx/templates/default.conf.template
  src/
    pages/             HomePage, SearchPage, Analysis, Entities, Missing/OneWay/Map, NotFound
    components/        Layout, SearchBar, ResultLayout, Article*, Connection*, Entity*,
                      ApiKeyPrompt, ui.jsx
    context/           AnalysisContext.jsx
    hooks/             useArticleParam.js
    api/               client.js, apiKey.js  (sessionStorage-backed key store)
  index.html  vite.config.js  vitest.config.js  package.json  .oxlintrc.json  .env.example
database/              docker-compose.yml, init.sql, README.md
deploy/
  docker-compose.staging.yml     the Phase 6 staging stack
  docker-compose.production.yml  the Phase 7 production stack, addressed by RELEASE_TAG
  .env.production.example        every credential a production host must supply
  smoke_test.py                  stdlib-only HTTP smoke test for a running deployment
  uat/                           recorded smoke-test output
  README.md                      how to run, migrate and roll back
docs/                  PRD.md  TRD.md  PHASES.md  ARCHITECTURE.md  CHECKLIST.md  DESIGN.md
                       UAT.md  ROLLBACK.md
.github/workflows/    ci.yml  (pytest, oxlint, vite build, both images, schema drift)
```

## 3. Commands

Every command is CWD-sensitive. `backend/.env` uses a relative `env_file`, and
`pytest.ini` sets `pythonpath = .`, so backend commands must run from `backend/`.

| CWD | Command |
| --- | ------- |
| `backend` | `python -m venv .venv` → `.venv\Scripts\activate` → `pip install -r requirements.txt` |
| `backend` | `uvicorn app.main:app --reload` (serves on :8000) |
| `backend` | `pytest` |
| `backend` | `pytest tests/test_mediawiki.py -v` |
| `backend` | `$env:TEST_DATABASE_URL='postgresql+psycopg://postgres@127.0.0.1:5432/find_missing_test?connect_timeout=5'; pytest tests/test_persistence.py` (the persistence suite; skipped without it) |
| `backend` | `python -m tests.smoke_live` (hits the real API; not part of pytest) |
| `database` | `docker compose up -d` |
| `frontend` | `npm ci` |
| `frontend` | `npm run dev` (:5173, proxies `/api` → `http://127.0.0.1:8000`) |
| `frontend` | `npm run build` |
| `frontend` | `npm run lint` (oxlint) |
| `frontend` | `npm run test` (vitest) |
| `deploy` | `docker compose -f docker-compose.staging.yml up -d --build` (web :8080, api 127.0.0.1:8081) |
| any | `python deploy/smoke_test.py --base-url http://localhost:8080 --expect-database` |
| `deploy` | `docker compose -f docker-compose.production.yml --env-file .env up -d` |
| `deploy` | `docker compose -f docker-compose.staging.yml down -v` (also drops the volume, so `init.sql` re-runs) |

`pytest` needs a venv built from `requirements.txt`. Without `pytest-asyncio` and
`httpx2` it does not fail — it aborts with an `INTERNALERROR` and runs **zero** tests,
which reads as a pass. Install first, then trust the count.

Does not exist — do not claim otherwise, do not add a substitute without asking:

* Backend lint / format / typecheck. There is no `pyproject.toml`, `ruff.toml`,
  `mypy.ini`, or `.pre-commit-config.yaml` in the repo, and no such tool is installed.
* Browser automation. Nothing can open a page, so nothing can verify a rendered
  pixel. `npm run test` (vitest, jsdom) asserts components and tokens, not a rendered
  pixel. Any criterion that needs one is a human action.

CI **does** exist: `.github/workflows/ci.yml` runs pytest, oxlint, `vite build`,
builds and boots both images, and fails on `models.py` / `init.sql` table drift.

## 4. Stack

Backend: Python 3.12, FastAPI, uvicorn, pydantic 2 + pydantic-settings, httpx,
SQLAlchemy 2 (sync `Session`) with psycopg 3, pytest + pytest-asyncio.
Frontend: Vite 8, React 19, react-router-dom 7, cytoscape 3, oxlint, vitest 3 +
@testing-library/react + jsdom. Plain JSX — there is no TypeScript and no `tsconfig.json`;
`@types/react*` are installed but unused.

## 5. Architecture invariants

These are load-bearing. Breaking one breaks the tests or the deployment.

* Layering is `routers → services → (mediawiki | repository → db → models)`.
  Routers never build SQL; `sqlalchemy` is imported only in `db.py`, `models.py`, and
  `repository.py`.
* `services/` contains zero `fastapi` imports. If a service needs HTTP-layer context,
  the router passes it in.
* `app/services/mediawiki.py` is the only module that performs HTTP. Everything else
  consumes its results.
* Services raise `WikipediaError` / `ArticleNotFoundError`. Routers translate via their
  local `_upstream_error(exc)` and always `raise ... from exc`.
* A database problem must never fail a request. `db.session_scope()` yields `None` when
  the engine is unavailable, and `repository` degrades to no-op persistence. "A database
  problem" is meant literally: the catch is `SQLAlchemyError`, not `Exception`, because
  the `try` wraps the caller's `yield` and a broad catch would absorb our own bugs behind
  a log line blaming the database. `ping()` is the deliberate exception — no caller code
  runs inside its `try`, and the container `HEALTHCHECK` needs it never to raise.
* A partial answer must never masquerade as a complete one. `build_extracted_links`
  (`services/analysis.py:278-284`) drops any link the existence check did not answer
  rather than guessing `exists`/`missing`. The same rule applies to a whole *stage*:
  a deadline mid-analysis returns `summary.aborted` with `abort_reason` and
  `entity_types_incomplete`, and the three `GET /api/connections/*` routes answer 504
  rather than return a list that was cut short, because a bare list has nowhere to say
  it is partial and a short list is indistinguishable from an empty one.
* Every Wikimedia call passes through `MediaWikiClient._api_get`, and that is where
  `AnalysisBudget` is checked — the single chokepoint, not per call site. A new route
  that crawls must carry `BudgetDep`, which `test_deployment_contract.py` enforces.
  The budget is a `ContextVar`, not a client attribute: the client is one shared
  instance on `app.state`, so an attribute would let concurrent requests overwrite each
  other's deadline. `AnalysisAborted` is not a `WikipediaError` and must not be caught
  by a broad `except Exception` — `classify_titles` re-raises it explicitly for exactly
  that reason.
* `analysis_deadline_seconds` (100) must stay **below** `proxy_read_timeout` in
  `frontend/nginx-proxy-api.conf` (120). At the same value nginx closes the connection
  as the backend writes, so a partial analysis arrives as a bare 502 with no
  `aborted` marker. Both are operator-tunable, which is why the ordering is asserted
  in a test rather than left to a comment.
* An aborted result is never cached. It is a subset, and storing it under the article's
  own key would serve that subset to the next reader for the whole TTL.
* `app.state` is the injection seam the test harness depends on. `main.py:33-36` only
  assigns when `getattr(app.state, ..., None) is None`; never assign unconditionally.
* Article titles are **query params**, never path params (slashes break routing).
* PostgreSQL is optional. An empty `DATABASE_URL` is the default, not a misconfiguration:
  the app boots and `/api/health` reports `database_enabled: false`. There is no
  history endpoint — `GET /api/analyses/recent` and `repository.recent_analyses` were
  removed in `c7d5344`.
* The shared analysis key is optional in exactly the same way. An empty
  `ANALYSIS_API_KEY` is the default and means the deployment is open; set, the four crawl
  routes (`POST /api/analyze`, all three `GET /api/connections/*`) refuse anything without a
  matching `X-Api-Key` header, and `/api/health` reports `auth_required`. The read routes
  stay open on purpose. It is a shared secret, not identity — one key, one subject, and
  `analysis_runs` deliberately has no `api_key_id`. `docs/ARCHITECTURE.md` §10.1 is the
  decision; the `Header()` default note in `dependencies.py` is load-bearing, as is the
  frontend rule that the key is **typed**, never a build-time constant.
* A gate must run **before** the work it protects. `require_analysis_key` is a FastAPI
  dependency, not a line inside the handler, so a refused request costs zero calls to
  Wikimedia — asserted directly in `test_api_key.py`. A check placed after the crawl would
  have protected the database and not Wikimedia.
* `/api/health` must read settings through `SettingsDep`, never through the `settings`
  local that `create_app` closes over. The lifespan lets an injected `app.state.settings`
  win, so a closure read reports the process environment while every route reads the
  injected one — two different deployments' configuration for the same request.
* In a deployment the SPA and the API share an origin. `frontend/nginx.conf.template`
  serves the built assets and reverse-proxies `/api` to the backend, so the client's
  relative `/api` never becomes a cross-origin request and CORS stays out of the
  deployed request path. The backend's CORS middleware is for the dev server, where the
  frontend is on :5173 and the backend on :8000. `proxy_pass` there must have **no**
  trailing path, or the `/api` prefix is stripped and every route 404s.
* Schema changes are additive only. There is no migration tool, so a removed or renamed
  column could not be rolled back; `init.sql` is `CREATE ... IF NOT EXISTS` only and
  contains no `DROP`. That is what makes `docs/ROLLBACK.md` §1 true.

## 6. Backend conventions

* `from __future__ import annotations` first, in every module.
* Absolute imports only: `from app.services.mediawiki import ...`.
* Module docstrings state *why* the module exists, not what it contains.
* Typing: PEP 604 unions (`str | None`), `collections.abc` generics, return types on
  every function in `services/` and `routers/`.
* Leading underscore marks module-private helpers and constants.
* No bare `except:`. Broad `except Exception` is allowed only where the code cannot
  propagate, and carries a `# noqa: BLE001 - <reason>`.
* Comments explain *why*, never *what*. Most existing comments are load-bearing; read
  them before editing the surrounding logic.

## 7. Frontend conventions

* Plain JSX. Do not add TypeScript.
* CSS Modules, one `X.module.css` colocated with its `.jsx`, consumed as
  `import styles from './X.module.css'`. No Tailwind, no inline styles, no new colour
  literals — all colour comes from the `index.css` tokens.
* Files exporting one component use a default export; files exporting several
  (`ui.jsx`, `ConnectionLists.jsx`) use named exports.
* Data fetching is `useEffect` + `AbortController` + `.then`/`.catch`. No `async/await`
  in components, no react-query or any other query library.
* Derive, don't store. Counts and filtered lists are `useMemo`-derived; anything
  derivable from props/state must not become its own state variable.
* Guard against stale responses — results belong on screen only if they belong to the
  current query.
* React 19 context form (`<Context value={...}>`), no `.Provider`, and
  `useAnalysis()` throws if used outside the provider.

## 8. Testing rules

Backend (pytest):

* `asyncio_mode = auto` — write bare `async def test_*`, never
  `@pytest.mark.asyncio`.
* Never touch the network in tests. Use `FakeWikipediaClient` from
  `tests/fake_wikipedia.py` injected through `app.state`, or the
  `StubClient`/`SequencedStubClient` stubs that replace the private `_api_get`. Do not
  add `unittest.mock` or `respx`.
* `filterwarnings = error` in `pytest.ini`: any new warning except
  `DeprecationWarning` fails the suite.
* Assert exact whole dicts/lists. The API tests compare full payloads, so adding or
  renaming a schema field breaks them.
* Test names are behavioural sentences:
  `test_one_way_target_without_reverse_link_is_reported_as_one_way`.
* `tests/test_api_key.py` covers the gate, and its `GATED`/`UNGATED` lists are the
  contract: adding a crawl route to a router without gating it fails `UNGATED`, and gating
  a read route fails `GATED`. Keep both lists in step with `routers/analysis.py`.
* The key is compared with `secrets.compare_digest` and **`.encode()`d**, because
  `compare_digest` rejects non-ASCII `str`. A `Header()` inside an `Annotated` with no
  default is *required* in Pydantic v2, so every gated route would 422 instead of 401 —
  hence the `= None` in the signature, which also has to come last.
* `tests/test_persistence.py` is the one module that opens a database, and it is skipped
  unless `TEST_DATABASE_URL` is set. It exists because **every other test in this
  repository runs with an empty `DATABASE_URL`** — which is how UAT-02, DEF-003 and
  DEF-006 each reached a release with a green suite. Any new claim about a SQL statement,
  a constraint, the retention prune or the cache read path belongs there, not in a unit
  test. Two rules that module depends on:
  * It must stay skippable. `pytest` with no `TEST_DATABASE_URL` is a normal run, and the
    suite must not fail on the absence of a server.
  * A skip must never be mistaken for a pass. The CI `backend` job has a separate step
    that fails the job if this module skips.
* Read the database through a `Session`, never through `db.session_scope`. `session_scope`
  logs and swallows, so a failed query returns an empty result and the test reports a
  missing row instead of the error. A bare `Connection` is not a substitute either —
  executing an ORM `select()` on one returns column values, not objects.
* `backend/tests/test_db.py` needs no `TEST_DATABASE_URL` and is not a persistence test.
  It drives `session_scope` with a stub session, deliberately, so the assertion that a
  caller's `TypeError` propagates runs in a plain `pytest` rather than being skipped. Do
  not "tidy" it into `test_persistence.py` — that would move the guard behind a skip.

Frontend (vitest, `npm run test`):

* Colocate as `*.test.jsx` next to the component. `vitest.config.js` is separate from
  `vite.config.js` on purpose — never merge them, the dev proxy is load-bearing.
* Import `describe`/`it`/`expect` from `vitest`; globals are off.
* Call `afterEach(cleanup)` explicitly. Testing Library only self-registers cleanup when
  the runner exposes a global `afterEach`, which this config does not.
* `esbuild: { jsx: 'automatic' }` is required. Test files import no React binding, so the
  classic transform would throw `React is not defined`.
* jsdom gives `import.meta.url` a non-`file:` scheme. Resolve paths from `process.cwd()`,
  which vitest sets to the directory holding `vitest.config.js`.
* `src/designTokens.test.js` is the guard for §9: it fails if any `var(--...)` under
  `frontend/src` has no definition in `index.css`. That is the regression the Miro palette
  migration caused, and it is invisible to both the build and the component tests.

## 9. Design system

`docs/DESIGN.md` is the source of truth. The tokens are already materialised in
`frontend/src/index.css:1-67` — edit them **there**, not in a component file. The
palette was migrated to Miro, so the pre-migration values below are the ones in
`index.css` now, not the older lime-on-white set.

* `--accent: #4262ff` is the interactive hue. `--primary: #1c1c1e` is the near-black
  action colour, **not** an accent. Do not introduce a second interactive hue.
* `--radius-xl: 16px`. The scale runs `--radius-xs` 4 → `--radius-xxxl` 28.
* Elevation is a real shadow system now: `--shadow-sm`, `--shadow-lg`, `--shadow-focus`.
  `--shadow-lg` is used in exactly one place (`SearchBar.module.css:102`, the results
  dropdown); `--shadow-focus` is the focus ring.
* Success is `--mutual: #00b473`. There is **no `--positive` token any more** — do not
  reintroduce it. A green CTA is still not a success indicator.
* Status hues: `--missing` red, `--oneway` yellow, `--mutual` green. Entity hues:
  `--person` blue, `--place` coral. Each has a `*-soft` translucent companion.
* Brand palette lives under `--brand-*` (`yellow`, `blue`, `coral`, `rose`, `teal`) with
  `*-light` companions. These are for illustration surfaces, not for status meaning.
* **Cytoscape is the one place a `var()` does not work.** It resolves style colours
  through its own `color2tuple`, which accepts a named colour, hex, `rgb()` or `hsl()`
  and nothing else. Handing it `var(--missing)` makes it *drop the property silently* —
  no build error, no lint error, and the map renders in Cytoscape's defaults. That is
  UAT-01, which shipped a connection map with no colours at all. `ConnectionMap.jsx`
  therefore reads the tokens off `:root` with `getComputedStyle` and passes them as
  literals. `LEGEND_ITEMS` may still use `var()`, because those values land in an inline
  `style` attribute on a real DOM element, which is genuine CSS.
  `test_frontend_contract.py::test_cytoscape_styles_never_use_css_custom_properties`
  guards this.

## 10. Two-file invariant

`backend/app/models.py` and `database/init.sql` describe the same schema and must be
updated together. `database/README.md` says this explicitly.

There is no migration tool. The only two paths are `Base.metadata.create_all()` at
startup and `init.sql` applied by hand. Note that `init.sql` already carries one object
the models do not: the partial index `ix_article_links_missing`.

## 11. Docs vs code

**Code is truth.** The documents in `docs/` were written as a specification before or
alongside the implementation and have drifted. Known divergences:

* `docs/TRD.md` §6 specifies a base path of `/api/v1`. The code serves `/api`
  (`config.py:15`) and the string `v1` does not appear anywhere in `backend/`.
* `docs/TRD.md` §6.8 specifies an error envelope `{"error": {"code", "message"}}`. Both
  the backend and the frontend use FastAPI's `{"detail": ...}`.
* `docs/TRD.md` §5 names tables `links` and `missing_connections`. The code has
  `articles`, `article_links`, and `analysis_runs`.
* `docs/TRD.md` Appendix C prescribes a directory layout that does not exist. Follow
  §2 of this file instead.
* `docs/PHASES.md` Phase 4 gate requires "backend lint". That command does not exist
  (§3).

Do not edit the docs to match the code in order to make a plan look satisfied. Change
the code, and change the doc in the same commit when the spec itself was wrong.

## 12. Scope lock

`docs/PRD.md` §18 is binding. Out of scope for this project: RAG, semantic search, an AI
research assistant, article recommendations, topic classification, educational
assistants, knowledge-gap scoring, connection-path finding, AI-generated explanations,
and any full-Wikipedia mirror. If a task appears to need one of these, ask before
starting.

## 13. Windows quirks

* PowerShell 5.1. `&&` does not exist — use `; if ($?) { ... }`.
* `backend/.env` is only found when CWD is `backend/`, because `Settings` uses a
  relative `env_file`.
* `VITE_API_PROXY_TARGET` is read from `process.env` in `vite.config.js:6`, not from a
  `.env` file. Set it in the shell:
  `$env:VITE_API_PROXY_TARGET='http://127.0.0.1:8123'; npm run dev`.
* The dev proxy targets `127.0.0.1`, not `localhost`. A backend bound to only one of
  those will produce a connection refusal.
* Repo `.gitignore` already excludes `.env`, `.agents/`, and `.claude/`. `AGENTS.md` is
  **not** ignored and is meant to be committed.

## 14. Never do

* Never commit or push without being asked. Check `git status` and `git diff` first.
* Never commit `.env`, credentials, or any other secret.
* Never let a test hit the real network.
* Never delete an empty or seemingly unused module as "cleanup" — check for imports
  first; several helpers exist for the test harness or are wired for future use.
* Never add a new error path around `main.py`'s existing CORS config or
  `WikipediaError` handler. Extend the existing ones.
* Never leave `[Name]`, `[QA Lead]`, or other placeholder text in `docs/` once the real
  owner is known.
