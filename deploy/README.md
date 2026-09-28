# Deployment

Everything needed to run Find the Missing Connections outside a laptop.

There are **two** deployments, and they are alternatives rather than stages:

| | Shape | Config |
| --- | ----- | ------ |
| **Single host** (below) | nginx + FastAPI + Postgres in one compose stack, one origin | `docker-compose.staging.yml`, `docker-compose.production.yml` |
| **Split** | Vercel for the SPA, Render for the API and Postgres, two origins | `../render.yaml`, `../frontend/vercel.json` |

| File | Purpose |
| ---- | ------- |
| `docker-compose.staging.yml` | The staging stack: PostgreSQL, the API, and nginx. Phase 6 UAT runs against this. |
| `docker-compose.production.yml` | The production stack. Same images, different host. |
| `nginx.conf.template` | Installed into the frontend image. Serves the SPA and reverse-proxies `/api`. |
| `smoke_test.py` | stdlib-only HTTP smoke test for a running deployment. Phase 6 and Phase 7 evidence. |
| `.env.production.example` | Every setting a production host must supply. Copy to `.env`; never commit it. |

The images themselves are built from `../backend/Dockerfile` and
`../frontend/Dockerfile`. Both are committed; there is no build step here that
exists only for deployment. The split deployment reuses the backend image
unchanged — `render.yaml` sets `runtime: docker` against the same Dockerfile, so
there is no second definition of how the API is built.

## The shape of it

```text
                    ┌──────────────────────────────┐
   browser ────────►│ web   nginx:alpine           │
                    │   /            → index.html  │
                    │   /assets/*    → cached 1y   │
                    │   /api/*        → proxied ───┼──► api  FastAPI
                    └──────────────────────────────┘         │
                                                              ▼
                                                          db  PostgreSQL
                                                              │
                                                              ▼
                                                          MediaWiki API
```

One host, three containers. Kubernetes and microservices are out of scope
(`ARCHITECTURE.md` §2.2), and the app has one workflow, so a compose stack is
the whole deployment.

nginx proxies `/api` on the **same origin** as the SPA. That is deliberate: the
client defaults to a relative `/api` (`frontend/src/api/client.js:3`), so in a
deployed environment no request is cross-origin and CORS is never on the request
path. The API's own CORS middleware stays in place for the dev server, where the
frontend is on :5173 and the backend on :8000.

## Staging

```bash
cd deploy
docker compose -f docker-compose.staging.yml up -d --build
```

- Frontend: <http://localhost:8080>
- API, bound to loopback for debugging: <http://127.0.0.1:8081>
- Database: not published. Only the `api` container needs it.

Then verify:

```bash
python deploy/smoke_test.py --base-url http://localhost:8080 --expect-database
```

Tear down with `docker compose -f docker-compose.staging.yml down`. Add `-v` to
destroy the database volume too; that is the only way to re-run `init.sql`, which
the Postgres image executes on first volume creation only.

## Production

Same images, same file, different host. Nothing is rebuilt.

```bash
cp .env.production.example .env      # then edit every credential
docker compose -f docker-compose.production.yml --env-file .env up -d
```

Before the first production deploy, and after any schema change, apply
`database/init.sql` by hand:

```bash
docker compose -f docker-compose.production.yml exec -T db \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < ../database/init.sql
```

`init.sql` is written to be re-runnable — every statement is
`CREATE ... IF NOT EXISTS` inside one transaction — so applying it to a live
database is safe. It creates the tables and indexes and nothing else; there is
no `DROP` anywhere in it. The API also calls `create_all()` on start-up, which
covers the three tables but **not** the partial index `ix_article_links_missing`,
so `init.sql` is still the authority.

## Rollback

The previous images are tagged, so a rollback is a retag and a restart.

```bash
# 1. Find the tag that was running before this release.
docker image ls find-missing --format '{{.Repository}}:{{.Tag}} {{.CreatedAt}}'

# 2. Put the release tag back in the compose file, then:
docker compose -f docker-compose.production.yml --env-file .env up -d

# 3. Confirm.
python deploy/smoke_test.py --base-url https://your-host
```

The database needs no rollback. `init.sql` only creates missing objects, so an
older API image running against a newer schema still works — the tables and
columns it reads are unchanged. A schema change that removed or renamed something
would break that, and there is no migration tool to undo it, so such a change
must be additive only.

`docs/ROLLBACK.md` holds the full record, including the version that was live
before the first production release.

## Split deployment: Vercel (SPA) + Render (API, Postgres)

```text
                    ┌──────────────────────────────┐
    browser ────────►│ Vercel   static host         │
                    │   /            → index.html  │
                    │   /assets/*    → cached 1y   │
                    │   CSP: connect-src → Render  │
                    └──────────┬───────────────────┘
                               │ HTTPS, cross-origin, CORS
                    ┌──────────▼───────────────────┐
                    │ Render   FastAPI/Uvicorn     │
                    │   internal URL ──────────┐   │
                    └──────────────────────────┼───┘
                                               ▼
                                    ┌──────────────────────┐
                                    │ Render Postgres      │
                                    │ private network only │
                                    └──────────────────────┘
```

Three resources, three providers, no shared origin. The compose stack above stays
valid and is still what CI exercises — this is an additional option, not a
replacement.

### What nginx was doing, and where each job went

Taking nginx out is the whole cost of this topology. It was doing four things, and
three of them have no automatic replacement:

| Job | Single host | Split |
| --- | --- | --- |
| Serve the SPA + deep links | `try_files … /index.html` | rewrite in `vercel.json` |
| Serve `/api` same-origin | `proxy_pass` in nginx | `VITE_API_BASE_URL` + CORS |
| Security headers | `nginx-security-headers.conf` | `headers` in `vercel.json` |
| Rate limit `/api/analyze` at 6r/m | `limit_req zone=analyze` | **nothing — see below** |

### Setup

1. **Render first**, so you have a hostname to put in the Vercel build.

   Render dashboard → New → Blueprint → point at this repository. It reads
   `render.yaml` and creates the web service and the database together. It will
   prompt for `ANALYSIS_API_KEY`; that is the only secret.

2. **Wait for the API to report healthy**, then confirm it answers:

   ```bash
   curl https://find-missing-api.onrender.com/api/health
   ```

   `"auth_required": true` means the key was set. `"database_enabled": true`
   means the internal database URL resolved — if it is `false`, the service and
   the database are in different regions.

3. **Vercel**, with one environment variable.

   Import the repository, set **Root Directory** to `frontend`, framework Vite,
   and add:

   | Variable | Value |
   | -------- | ----- |
   | `VITE_API_BASE_URL` | `https://find-missing-api.onrender.com/api` |

   The `/api` suffix is required. The client concatenates the base with a path
   that already starts with a slash (`frontend/src/api/client.js`), and the
   backend serves everything under `api_prefix`.

   This is a **build-time** value. Vite inlines `import.meta.env.*`, so changing
   it needs a redeploy, not a restart.

4. **Put your real values in `render.yaml`** and commit: the `USER_AGENT` contact
   address, and the Vercel origin in `CORS_ORIGINS`.

### Three hostnames that have to agree

Changing any one of these without the other two is the characteristic failure of
this topology, and none of the three errors names the file that caused it:

- `render.yaml` → `ALLOWED_HOSTS` — the API answers **400 to every route**
  otherwise, including Render's own health check
- `render.yaml` → `CORS_ORIGINS` — the browser blocks every request
- `vercel.json` → `connect-src` — the browser blocks every request, from a
  different direction

`backend/tests/test_split_deployment_contract.py` asserts all three against each
other, so a rename that breaks one fails the suite.

### The two things this topology does not protect

**Rate limiting.** `limit_req zone=analyze` at 6r/m existed to bound this
deployment's spend against Wikimedia's published 200 req/min. Nothing on Render
enforces it. `ANALYSIS_API_KEY` is the only remaining control, and the frontend
asks for it by design rather than baking it in — which is why it has to be set, or
the deployment is open to anyone who finds the URL.

**HSTS.** `nginx-security-headers.conf` deliberately omits it, because there is no
TLS in front of nginx there. Vercel terminates TLS with a real certificate, so
`vercel.json` sets it.

### The free tier has a clock on it

Render's free Postgres expires **30 days** after creation, with a 14-day grace
period and then permanent deletion. Expiry is survivable rather than fatal — the
app boots with an unreachable `DATABASE_URL`, reports `database_enabled: false`,
and still answers every request by crawling Wikipedia uncached. You lose the
cache, so analyses get slower and Wikimedia usage goes up.

Render's free web service also spins down after 15 minutes idle and takes about a
minute to wake. The first analysis after that pays the cold start on top of its own
work; the deadline clock starts inside the app, so it does not eat the budget, but
the request takes longer in wall-clock terms.

### The one number to verify before trusting it

`analysis_deadline_seconds` is 70 in `render.yaml` rather than the app default of
100, because Render publishes no request-duration ceiling and routes inbound
traffic through Cloudflare, whose documented proxy read timeout is 100s. If the
deadline reaches the transport's limit, the connection closes as the response is
written and the reader gets a bare 502 with no `aborted` marker — the same failure
`AGENTS.md` §5 describes for nginx, with a different number.

Run one real analysis end to end and confirm you get JSON back. If it 502s or
524s, lower it further.

## Secrets

Nothing in this directory is a secret and nothing here should be. Every
credential comes from the environment: `POSTGRES_PASSWORD` through
`${POSTGRES_PASSWORD}`, the app's settings through the environment variables
`Settings` already reads. `.env` is already covered by the repository
`.gitignore`.

The backend image contains no `.env` and no `tests/` — the `Dockerfile` copies
`app/` and `requirements.txt` only, so there is no layer in which a credential
could be committed.
