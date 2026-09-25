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
