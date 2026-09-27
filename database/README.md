# Database

PostgreSQL is used as a **cache** for what Wikipedia already tells us. Every
analysis is computed live from the MediaWiki API; the database only avoids
re-fetching the same article twice.

The API runs fine with no database at all. Leave `DATABASE_URL` empty in
`backend/.env` and nothing is stored.

## Start a local database

```bash
cd database
docker compose up -d
```

`init.sql` runs automatically the first time the volume is created, creating
`articles`, `article_links` and `analysis_runs`. To apply it by hand to an
existing database:

```bash
psql -U postgres -d find_missing -f database/init.sql
```

Then point the backend at it:

```dotenv
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/find_missing
```

The published port is bound to `127.0.0.1`, so the database is reachable from this
machine only. `"5432:5432"` would listen on every interface, which on a laptop on
wifi puts the whole local network inside the trust boundary. Nothing here is
secret — it is a cache of public Wikipedia data — but a port you did not mean to
open should not be open.

`POSTGRES_PASSWORD` defaults to `postgres` and can be overridden:

```bash
POSTGRES_PASSWORD=my-own-value docker compose up -d
```

Set it before reusing any of this in a real deployment. Changing it has no effect
on an existing `pgdata` volume: the image only applies it when it first creates
the data directory, so you would need `docker compose down -v` (which deletes the
cache) to apply a new one.

## Tables

| Table           | Purpose                                                                  |
| --------------- | ------------------------------------------------------------------------ |
| `articles`      | Articles already seen: title, description, lead extract, fetch time.      |
| `article_links` | Directed links between articles. `exists = false` marks a **red link**.  |
| `analysis_runs` | One row per analysis, with link, missing and one-way counts.             |

`init.sql` ends with a few example queries, including how to find the missing
targets that are linked from the most different articles.

## Notes

- `article_links` is replaced wholesale each time an article is re-analysed, so
  a re-run never leaves stale links behind.
- `analysis_runs.seed_page_id` is deliberately not a foreign key: history should
  survive the article being deleted from Wikipedia.
- The SQLAlchemy models in `backend/app/models.py` are the source of truth. If
  you change a model, update `init.sql` to match.
