# Wikitech — Find the Missing Connections

Analyzes an English Wikipedia article and surfaces two gaps: red links (people/places
mentioned but with no article of their own) and one-way links (A links to B, B does not
link back). FastAPI backend over the MediaWiki action API, Vite + React SPA with a
Cytoscape connection map, and an optional PostgreSQL cache.

## 2. Layout

```
backend/
  app/
    main.py            create_app(), lifespan, CORS, WikipediaError handler
    config.py          Settings (pydantic-settings), get_settings() @lru_cache
    db.py              engine, session_scope(), Base.metadata.create_all
    models.py          SQLAlchemy tables: articles, article_links, analysis_runs
    repository.py      the only module that writes rows
    schemas.py         Pydantic request/response models
    dependencies.py    Annotated aliases: ClientDep, SettingsDep, TitleQuery, SearchQuery
    routers/           articles.py, analysis.py  (HTTP only)
    services/          analysis.py, classifier.py, mediawiki.py  (no FastAPI)
  tests/               conftest.py, fake_wikipedia.py, smoke_live.py, test_*.py
  requirements.txt  pytest.ini  .env.example
frontend/
  src/
    pages/             HomePage, SearchPage, Analysis, Entities, Missing/OneWay/Map, NotFound
    components/        Layout, SearchBar, ResultLayout, Article*, Connection*, Entity*, ui.jsx
    context/           AnalysisContext.jsx
    hooks/             useArticleParam.js
    api/               client.js
  index.html  vite.config.js  vitest.config.js  package.json  .oxlintrc.json  .env.example
database/              docker-compose.yml, init.sql, README.md
docs/                  PRD.md  TRD.md  PHASES.md  ARCHITECTURE.md  CHECKLIST.md  DESIGN.md
```

## 3. Commands

Every command is CWD-sensitive. `backend/.env` uses a relative `env_file`, and
`pytest.ini` sets `pythonpath = .`, so backend commands must run from `backend/`.

| CWD | Command |
| --- | --- |
| `backend` | `python -m venv .venv` → `.venv\Scripts\activate` → `pip install -r requirements.txt` |
| `backend` | `uvicorn app.main:app --reload` (serves on :8000) |
| `backend` | `pytest` |
| `backend` | `pytest tests/test_mediawiki.py -v` |
| `backend` | `python -m tests.smoke_live` (hits the real API; not part of pytest) |
| `database` | `docker compose up -d` |
| `frontend` | `npm ci` |
| `frontend` | `npm run dev` (:5173, proxies `/api` → `http://127.0.0.1:8000`) |
| `frontend` | `npm run build` |
| `frontend` | `npm run lint` (oxlint) |
| `frontend` | `npm run test` (vitest) |

Does not exist — do not claim otherwise, do not add a substitute without asking:

* Backend lint / format / typecheck. There is no `pyproject.toml`, `ruff.toml`,
  `mypy.ini`, or `.pre-commit-config.yaml` in the repo, and no such tool is installed.
* CI. No `.github/`, no `Dockerfile`.

The 7 `# noqa` markers in the tree (`BLE001` in 4 app modules, `D107` in
`tests/test_mediawiki.py`) are ruff/pydocstyle codes left over from a linter that is
not installed. Keep them as written; they are inert comments, not a config.

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
  the engine is unavailable, and `repository` degrades to no-op persistence.
* A partial answer must never masquerade as a complete one. `build_extracted_links`
  (`services/analysis.py:278-284`) drops any link the existence check did not answer
  rather than guessing `exists`/`missing`.
* `app.state` is the injection seam the test harness depends on. `main.py:33-36` only
  assigns when `getattr(app.state, ..., None) is None`; never assign unconditionally.
* Article titles are **query params**, never path params (slashes break routing).
* PostgreSQL is optional. An empty `DATABASE_URL` is the default, not a misconfiguration:
  the app boots and `/api/health` reports `database_enabled: false`. There is no
  history endpoint — `GET /api/analyses/recent` and `repository.recent_analyses` were
  removed in `c7d5344`.

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
