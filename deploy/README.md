# Deployment

Everything needed to run Find the Missing Connections outside a laptop.

| File | Purpose |
| ---- | ------- |
| `docker-compose.staging.yml` | The staging stack: PostgreSQL, the API, and nginx. Phase 6 UAT runs against this. |
| `nginx.conf.template` | Installed into the frontend image. Serves the SPA and reverse-proxies `/api`. |
| `smoke_test.py` | stdlib-only HTTP smoke test for a running deployment. Phase 6 and Phase 7 evidence. |
| `.env.production.example` | Every setting a production host must supply. Copy to `.env`; never commit it. |

The images themselves are built from `../backend/Dockerfile` and
`../frontend/Dockerfile`. Both are committed; there is no build step here that
exists only for deployment.

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

## Secrets

Nothing in this directory is a secret and nothing here should be. Every
credential comes from the environment: `POSTGRES_PASSWORD` through
`${POSTGRES_PASSWORD}`, the app's settings through the environment variables
`Settings` already reads. `.env` is already covered by the repository
`.gitignore`.

The backend image contains no `.env` and no `tests/` — the `Dockerfile` copies
`app/` and `requirements.txt` only, so there is no layer in which a credential
could be committed.
