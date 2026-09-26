# Release 0.1.0 — deployment record and release notes

**Released:** 27 September 2026
**Tag:** `0.1.0-6336d1f` (base commit `6336d1f` plus the release work in this changeset)
**Images:** `find-missing-api:0.1.0-6336d1f`, `find-missing-web:0.1.0-6336d1f`

## What this release is

The first deployment of the app as a container pair: a FastAPI backend and a Vite SPA
served by nginx, with an optional PostgreSQL cache, talking to the live MediaWiki API.

It exists because the eight core capabilities were already built and tested, and the only
thing missing between "works on a laptop" and "can be released" was somewhere to release
it *to*. Building it surfaced two defects that no amount of unit testing had found, both
of which are fixed in this release.

## The two defects this release fixes

### UAT-01 — the connection map rendered with no colours at all

Cytoscape resolves style colours through its own `color2tuple`, which accepts a named
colour, hex, `rgb()` or `hsl()` and nothing else. The stylesheet was handing it
`var(--missing)`, which returns nothing, so Cytoscape **dropped the property silently** —
no build error, no lint error, and a graph drawn entirely in its own defaults. Missing
connections were not highlighted, because nothing on the map was highlighted.

Fixed by reading the tokens off `:root` with `getComputedStyle` and passing Cytoscape
literals. `test_cytoscape_styles_never_use_css_custom_properties` now fails if a
`var()` ever reaches the stylesheet again.

### UAT-02 — persistence was broken for every real article

`repository._replace_links` inserted one row per link, but `article_links` is keyed
`UNIQUE (source_page_id, target_normalized_title)`. When an article links both
`Allan G. Bromley` and a title that redirects there, `resolve_titles` returns the same
`page_id` and the same canonical title for both, the bulk insert violates the constraint,
and the whole transaction rolls back. `Ada Lovelace` has 11 such collisions in 425 links,
so **not one row was ever written for any real article.**

The request still returned 200 with correct data, because persistence is best effort by
design. `/api/health` also reported `database_enabled: true`, because `create_engine` is
lazy — the Engine object existed, it had simply never connected successfully. Two layers
of correct-by-design degradation added up to a cache that was silently dead.

Fixed by collapsing duplicates on the constraint's own key before the insert, with 8
regression tests. The blind spot is closed too: `/api/health` now reports
`database_reachable` from a real `SELECT 1`, and the smoke test gates on that instead of
on `database_enabled`.

## Also in this release

- `.dockerignore` for `backend/` and `frontend/`. `frontend/Dockerfile` does `COPY . .`,
  and with no ignore file the host's Windows `node_modules` overwrote the image's Linux
  one, so the Vite build ran against the wrong binaries. It also kept `backend/.env` one
  `COPY` away from a published layer.
- `connect_timeout=5` on the production `DATABASE_URL`. `create_all()` runs on the app's
  lifespan *before* uvicorn accepts connections, so a host that blackholed packets hung
  startup for about two minutes — past the image healthcheck's ~110s budget — and `web`,
  which waits on that healthcheck, never started.
- `.env.production.example` now says `openssl rand -hex 32`, not `-base64 32`. The
  password is substituted into a URL by string interpolation, and base64's `/` terminates
  the authority component, so the recommended password could not connect.
- `RELEASE_TAG` defaults to a name rather than `latest`. With no registry, `latest` is
  overwritten by every build, so a rollback to it is not a rollback at all.

## Verification

| | Staging | Production |
| --- | --- | --- |
| Endpoint | `:8080` via nginx | `:8082` via nginx |
| Smoke result | **14/14 passed**, 43.97s | **14/14 passed**, 35.39s |
| Record | `deploy/uat/smoke-2026-09-27-postfix.json` | `deploy/uat/smoke-2026-09-27-production.json` |
| `article_links` written | 843 | 925 |
| `analysis_runs` written | 2 | 3 |
| Write errors in log | none | none |

The suite is 85 passing from `requirements.txt`. Live MediaWiki and Wikidata were used
throughout; no check was satisfied by a fixture.

## Known limitations, stated rather than discovered later

1. **This is not a public production host.** The stack is production-*configured* and runs
   on the development machine on port 8082. Nothing is exposed to the internet, there is
   no TLS, and there is no domain.
2. **No image registry.** Images exist only on the host that built them. A host rebuild
   loses every tag except the newest. This is the one real gap in the rollback story.
3. **The rollback lever is unexercised.** `0.1.0-6336d1f` is the first tag, so there is no
   earlier one to return to. The mechanism is configured and the target is named; it has
   not been pulled.
4. **No browser was ever opened.** Every screen claim is verified against deployed HTTP
   responses and against the stylesheet contract in
   `backend/tests/test_frontend_contract.py`. The rendered pixel still needs a human.
5. **UAT-03 is open and non-blocking** — see `docs/UAT.md` §5.

## How to roll this back

```sh
cd deploy
# set RELEASE_TAG to an earlier tag, then:
docker compose -f docker-compose.production.yml --env-file .env up -d
```

The database needs no action: the schema is additive, `init.sql` contains no `DROP`, and
the tables are a cache. See `docs/ROLLBACK.md`.
