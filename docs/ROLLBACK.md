# Rollback and Release Record

**Status:** one production release deployed and verified, `0.1.0-6336d1f`. It is the
first release, so the rollback lever is configured and has a target to name, but it has
**not been exercised** — there is no earlier tag to go back to. Section 5 says exactly
what was and was not rehearsed.

Phase 6 §7 and Phase 7 §7 both ask whether a previous build can be restored.
This document is the answer, and the record of what was actually rolled back.

---

## 1. What rollback is possible here

| Thing | Rollback | How |
| ----- | -------- | --- |
| Backend image | Yes | Change `RELEASE_TAG` in `.env`, `docker compose up -d`. |
| Frontend image | Yes | Same. Both images are addressed by the one `RELEASE_TAG`. |
| Database schema | Not needed | `init.sql` only creates missing objects and contains no `DROP`. An older image against a newer schema still works, because schema changes must be additive. |
| Cached analysis data | Not needed | The PostgreSQL tables are a cache. `article_links` is replaced wholesale on re-analysis and a deleted cache costs a slower response, never a wrong one. |

The tag has to be a **name**, not `latest`. There is no registry yet (section 6), so an
image only exists on the host that built it, and `latest` is overwritten by the next
build. A rollback to `latest` is not a rollback, it is a redeploy of whatever happens to
be newest. `0.1.0-6336d1f` is deliberately named so that the next release does not
destroy the target this one provides.

There is no migration tool, so the one thing that could not be undone is a
schema change that removed or renamed a column. That is why
`backend/app/models.py` and `database/init.sql` must be changed together and
additively: it is what keeps rollback free.

## 2. Live version

- **Currently in production:** `0.1.0-6336d1f`
  (`find-missing-api:0.1.0-6336d1f`, `find-missing-web:0.1.0-6336d1f`).
- **First rollback target:** none yet. `0.1.0-6336d1f` is the earliest tag on this host.
  The next release makes one available, and this section should then name it.

## 3. Release history

| Version | Commit | Date | Released by | Rolled back to | Reason |
| ------- | ------ | ---- | ------------ | -------------- | ------ |
| 0.1.0 | 6336d1f + release rehearsal | 27 September 2026 | unassigned | — | First production release. |

Staging deployments are not listed: they are rebuilt from the working tree and
have no continuity requirement.

## 4. Rollback procedure

### 4.1 Decide

Roll back if a release introduces a release-blocking defect in the core
workflow. The core workflow is: search an article, analyse it, see people and
places, see missing connections, see one-way connections, see the map with
missing entities highlighted. `deploy/smoke_test.py` is the executable
definition — if it fails, that is the trigger.

```bash
python deploy/smoke_test.py --base-url https://your-host --expect-database
```

### 4.2 Identify the target

```bash
docker image ls --format '{{.Repository}}:{{.Tag}} {{.CreatedAt}}' | grep find-missing
```

Both images must go back together. A new backend with an old frontend will work
(the payload is additive) but a new frontend against an old backend can call a
route that does not exist yet.

### 4.3 Restore

```bash
cd deploy
cp .env.production.example .env     # if this is a fresh host
# set RELEASE_TAG to the previous tag
docker compose -f docker-compose.production.yml --env-file .env up -d
docker compose -f docker-compose.production.yml ps
```

`up -d` recreates only the containers whose image tag changed, so the database
volume is untouched and no analysis data is lost.

### 4.4 Verify

```bash
python deploy/smoke_test.py --base-url https://your-host --expect-database
docker compose -f docker-compose.production.yml logs --tail 100 api
```

### 4.5 If the database is genuinely wrong

`init.sql` is idempotent, so re-applying it is always safe:

```bash
docker compose -f docker-compose.production.yml exec -T db \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < ../database/init.sql
```

To discard the cache entirely and force a clean rebuild, drop the volume. This
loses only cached data, never source data, because there is no source data:

```bash
docker compose -f docker-compose.production.yml down
docker volume rm find-missing_pgdata
docker compose -f docker-compose.production.yml up -d
```

## 5. Rehearsal

The procedure in §4.4 was run against staging on 27 September 2026 as part of
Phase 6: images were rebuilt, the stack recreated, and the smoke test re-run
green (14/14, 48.08s). The parts specific to a production host — the `.env`
credential set, the public hostname, TLS termination — are untested, because
there is no production host.

## 6. Known limits

- **No automated rollback trigger.** The smoke test reports; it does not revert.
  Deciding to roll back is a human action.
- **No image registry is configured.** Images are built on the host they deploy
  from, so "rollback" can only reach tags that host still has. Once images are
  pushed somewhere, older tags remain reachable; until then, a host rebuild
  loses them. This is a real gap for Phase 7.
- **Staging is not production.** Same images, but staging has a development
  `POSTGRES_PASSWORD` default and publishes the API on loopback. Neither is true
  in production.
