# Hardening Plan

## Find the Missing Connections

**Version:** 1.2
**Date:** 27 September 2026
**Base commit:** `e8a062a`
**Status:** Most of §2–§6 implemented — see the note below
**Scope:** The researched fix for every finding in `PUBLIC-READINESS.md`
**Owner:** `unassigned`
**Method:** External sources, listed with URLs in §H. Every claim about a third party's
behaviour is sourced; every claim about this codebase was read out of the source.

> **Implemented 27 September 2026.** §2 (all three one-way fixes), §3, §4 (the read path,
> §4.1 only — see below), §5, §6 B3, and §8 D1/D2 are done. Suite is **159 backend +
> 30 frontend**; `backend/tests/test_deployment_contract.py` guards the configuration.
>
> **§4.1 has a hard limit that needs saying.** The read path is implemented as a cache of
> the *whole computed payload* on `articles.analysis_payload`, not as a re-derivation from
> `article_links`. That is deliberate: `article_links` stores the *resolved* target title,
> and the *requested* one is what distinguishes a direct link from a redirect, so
> re-deriving would quietly change the answer. The consequence is that `GET
> /api/connections/{missing,one-way,map}` still recompute, and only `POST /api/analyze`
> benefits. Caching those routes needs the requested title persisted, which is a schema
> change to `article_links` and is not done.
>
> **Not done, and each needs something this repository cannot supply:** §1 the MediaWiki bot
> account, §5 TLS, §7 the authentication decision, §8 the `LICENSE`.



---

## 1. Read this first: the ceiling is external, and it is documented

`PUBLIC-READINESS.md` A1 says rate limiting is missing and frames it as a DoS problem.
Research found something more consequential, and it reorders the whole plan.

**Wikimedia deployed global API rate limits in 2026.** From
<https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits>:

| Client group | Limit |
| ------------ | ----- |
| Unidentified (IP only, no identifying User-Agent) | **10 req/min** |
| Unauthenticated browser request | 200 req/min |
| **Unauthenticated bot with a compliant User-Agent** | **200 req/min** |
| Authenticated request from an account with a bot flag | **Exempt** |
| Wikimedia Cloud Services, or a client granted an exemption | **Exempt** |

The stated purpose is to "reduce the amount of unauthenticated, automated API requests
(about 33% at the end of 2025) and to prevent high-volume commercial consumers from
puting undue load on our infrastructure."

This application has a compliant `User-Agent` (`config.py:19-22`, enforced in production
by `${USER_AGENT:?...}` at `docker-compose.production.yml:61`), so it sits in the
**200 req/min** band. That is a hard ceiling on the **entire deployment**, not per user.

### What one analysis costs

Counted from the recorded production run, `Chandni Chowk`: 444 links, 441 existing,
3 missing (`deploy/uat/smoke-2026-09-27-production.json:62`, `:69`).

| Step | Requests | Source |
| ---- | -------: | ------ |
| `get_article` | 1 | `mediawiki.py:189` |
| `get_article_links` (444 < 500, so one page) | 1 | `mediawiki.py:264` |
| `resolve_titles` — ⌈444/50⌉ batches | 9 | `mediawiki.py:352`, `_MAX_TITLES_PER_REQUEST = 50` |
| `get_page_descriptions` — ⌈441/50⌉ batches | 9 | `mediawiki.py:470` |
| `get_links_for_page_ids` — 25 targets, one batch | 1 | `mediawiki.py:425` |
| `wikidata_descriptions` — capped at `classify_max_items` | 3–20 | `classifier.py:105` |
| **Total** | **24–33** | |

**So the deployment can serve roughly 6–8 full analyses per minute, in total, forever.**
`GET /api/connections/map` costs about twice that, because of B2.

No amount of rate limiting on our side raises this number. It is set by Wikimedia, and it
is measured per client.

### This is why A1 is not really about us

The severity of A1 is not "someone can DoS us". It is that **the product has a hard
capacity of about 6–8 analyses per minute shared by all users**, and the cheapest way to
exceed it is for one person to hold F5. The `PUBLIC-READINESS.md` framing understated this.

### The one change that removes the ceiling

From the same page: an **authenticated request from an account with a bot flag is exempt
from rate limits.** A MediaWiki bot password — created at
`Special:BotPasswords`, <https://www.mediawiki.org/wiki/Manual:Bot_passwords> — is
designed for exactly this and requires no interactive login. It also grants
`apihighlimits`, which raises the property-query ceiling:

> "The results limit can be set as high as 500 for regular users, or **5000 for users with
> the `apihighlimits` right** (typically bots and sysops)."
> — <https://www.mediawiki.org/wiki/API:Properties>

That **also fixes B1 at the root**: the 500-link ceiling that causes the false `ONE-WAY`
becomes 5000. Details in §2.

**Recommendation:** obtain a bot account and a bot password before taking external users.
It is a one-time setup on the MediaWiki side, it needs no secret in the image (it is one
more environment variable), and it removes both the capacity ceiling and the false-positive
bug class. Until it exists, treat 6–8 analyses/minute as the product's stated capacity and
say so in the UI rather than letting users discover it as a timeout.

---

## 2. B1 — the false `ONE-WAY` (highest-value correctness fix)

### Confirmed root cause, with the exact number

<https://www.mediawiki.org/wiki/API:Links>:

> `pllimit` — How many links to return. Type: integer or `max`. **The value must be between
> 1 and 500.** … Maximum number of values is 50 (500 for clients that are allowed higher
> limits).

So for an unauthenticated client, `pllimit=max` returns **at most 500 links, ever**.
`get_links_for_page_ids` requests `pllimit=max`, ignores its own `max_links_per_page`
parameter (`mediawiki.py:413`), and has no continuation loop.

Any target article with more than 500 outgoing links therefore has an **invisible tail**.
If the seed is in that tail, the connection is reported `ONE-WAY` incorrectly, and nothing
in the response says so.

This is not theoretical. Among the 25 one-way targets returned for `Chandni Chowk`
(`smoke-2026-09-27-production.json:76`) are `1951 Asian Games`, `1982 Asian Games` and
`1987 Cricket World Cup` — tournament and series articles that routinely carry several
hundred links.

### Fix, in order of preference

**Option 1 — paginate (do this regardless).** It is correct at any limit and it is what
makes the truncation flag honest:

```python
async def get_links_for_page_ids(
    self, page_ids: Iterable[int], *, max_links_per_page: int = 500
) -> dict[int, set[str]]:
    ids = [int(page_id) for page_id in page_ids if page_id]
    if not ids:
        return {}

    result: dict[int, set[str]] = {}
    for batch in chunked(ids, _MAX_TITLES_PER_REQUEST):
        params = {
            "action": "query",
            "prop": "links",
            "plnamespace": MAIN_NAMESPACE,
            "pllimit": "max",
            "pageids": "|".join(str(page_id) for page_id in batch),
            "redirects": _MAX_REDIRECTS,
        }
        while True:
            data = await self._api_get(params)
            for page in (data.get("query") or {}).get("pages") or []:
                page_id = page.get("pageid")
                if not page_id:
                    continue
                titles = result.setdefault(int(page_id), set())
                for link in page.get("links") or []:
                    title = link.get("title")
                    if title and len(titles) < max_links_per_page:
                        titles.add(title_key(title))
            continuation = data.get("continue")
            if not continuation:
                break
            params = {**params, **continuation}
    return result
```

**Option 2 — a bot password (§1).** Raises the ceiling to 5000 and is worth doing anyway.

**Option 3 — do both, and make the uncertainty visible.** Change the return type to carry
completeness, and refuse to assert `ONE-WAY` on incomplete evidence. This is the part that
actually protects the user, and it mirrors what `build_extracted_links` already does at
`services/analysis.py:278-284`:

```python
@dataclass
class ReverseLinks:
    titles: set[str]
    complete: bool  # False when max_links_per_page was reached
```

then in `detect_one_way_connections` (`services/analysis.py:198`), treat
`complete is False` as **unknown, not one-way**. Add it to the existing honesty contract:
`AnalysisSummary.one_way_truncated` already exists for the *target budget*; this is a
different truncation and needs its own flag, or the two get conflated and neither is
readable.

### Also fix here, same file

`_api_get` (`mediawiki.py:116-147`) ignores `Retry-After`. Wikimedia's guidance is explicit:

> "respect the `Retry-After` header provided with a 429 Too Many Requests status code"
> — <https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits>

Current behaviour: a 429 sleeps a fixed 1 s and retries once, re-entering the same
limiter. Fix: read `Retry-After`, sleep for it, and add jitter.

**And lower the semaphore.** The same page says:

> "limit the number of concurrent requests to **3 or fewer**"

`config.py:28` sets `max_concurrent_requests: int = 4`. **The project is currently over the
documented limit.** Change the default to 3 and document why in the field's comment — this
is exactly the kind of constraint that looks like a typo and gets "fixed" back up later.

**And add `maxlag`.** From <https://www.mediawiki.org/wiki/API:Etiquette>:

> "If your task is not interactive, i.e. a user is not waiting for the result, you should
> use the `maxlag` parameter. … This will prevent your task from running when the load on
> the servers is high."

Caching and batched prefetch are non-interactive; the interactive path should use it too, so
that a loaded Wikipedia returns a clean error instead of making the user wait. Add
`"maxlag": 5` to the base query in `_api_get` (`mediawiki.py:120`).

`Accept-Encoding: gzip` is already handled — httpx requests it by default, which satisfies
the same page's advice.

---

## 3. A1 — rate limiting (the inbound side)

### Library choice

Research on the current options:

| Option | Verdict |
| ------ | ------- |
| **`slowapi`** | Mature, 2053 stars, health 84/100, MIT. Wraps the `limits` library; supports redis, memcached and in-memory backends. **But:** its own README calls it "alpha quality code", and the decorator **requires an explicit `request: Request` parameter** on every limited endpoint or it silently cannot hook in. |
| `fastapi-limiter` | Built on `pyrate-limiter`. Clean `dependencies=[Depends(RateLimiter(...))]` form, but a very small project. |
| `starlette-rate-limit` | A pure middleware option; no per-endpoint tiers. |
| **Custom `BaseHTTPMiddleware`** | ~30 lines, no new dependency, full control over headers and error body. |

**Recommendation: a custom middleware, plus `nginx limit_req` as the outer layer.**

The reasoning is specific to this codebase, not general:

- The expensive thing here is *one endpoint family*, not a spread of routes. A tiered
  custom middleware can express exactly the distinction that matters — `/api/analyze` and
  `/api/connections/*` cost 24–33 upstream requests each, `/api/article` costs 1 — without a
  library's decorator-ordering and explicit-`request` footguns.
- `slowapi` would require threading `request: Request` into eight route functions, which
  fights the existing `dependencies.py` seam.
- In-memory counters are correct here: the deployment is **one uvicorn worker** by design
  (`backend/Dockerfile:1-2`, "One worker, because a single analysis already fans out to the
  MediaWiki API"). If that ever changes to multiple workers or replicas, the counters must
  move to redis — record that as the reason the store is behind a small interface.

The layered shape:

```yaml
# nginx — coarse, survives a Python outage, never reaches the app
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/m;
limit_req_zone $binary_remote_addr zone=analyze:10m rate=30r/m;

location /api/analyze      { limit_req zone=analyze burst=5 nodelay; ... }
location /api/connections/ { limit_req zone=analyze burst=5 nodelay; ... }
location /api/             { limit_req zone=api burst=20 nodelay; ... }
```

Set the app-level budget from the §1 arithmetic, not by feel: at 200 upstream req/min and
~28 per analysis, **6 analyses/minute** is the honest per-IP ceiling. Return `429` with
`Retry-After` and `X-RateLimit-*` headers so a client can back off instead of retrying
immediately.

This is **OWASP API4:2023 Unrestricted Resource Consumption**, ranked #4:
<https://owasp.org/API-Security/editions/2023/en/0xa4-unrestricted-resource-consumption>.
The OWASP guidance matches this plan closely — "Resource limits must be defined at multiple
levels: execution timeouts, memory allocation, file descriptor counts, upload file sizes,
records per page, and number of operations per batched request, and the number of
third-party service providers' spending limit". The last one is the §1 ceiling.

---

## 4. A2 — give the database a read path

`PUBLIC-READINESS.md` A2 established that `repository.py` never reads. The researched fix
is not "add a cache" — it is **stop re-doing work the upstream already did**.

Three layers, in increasing value:

1. **Per-request memoisation.** The frontend already holds the analysis in
   `AnalysisContext`; `ConnectionMapPage.jsx:17` refetches the map anyway. Fold the map
   payload into `AnalysisResult` and delete the second request. This is B2 as well, and it
   halves the most expensive call in the product.
2. **Read `article_links` back.** `articles.normalized_title` is already indexed
   (`models.py:39`, `init.sql:22-23`). Serve a stored link set when
   `fetched_at` is within a TTL, and re-validate only the missing targets whose state
   changes. `ARCHITECTURE.md` §12 already records that no TTL exists — introducing one is a
   decision to state, not a default.
3. **Set a TTL and say so.** Any cache that never expires is a correctness bug waiting to
   happen: a red link that gets written tomorrow stays red forever in the UI.

Read `api/client.js` before starting: five of its wrappers (`getArticle`,
`getArticleLinks`, `checkArticlesExist`, `getMissingConnections`, `getOneWayConnections`)
are declared and never called. Caching at the client is not needed — the context already
does it.

---

## 5. A4 / C-section — infrastructure

### Log rotation (A4)

Docker's own documentation is unusually direct
(<https://docs.docker.com/engine/logging/configure>):

> "**Use the local logging driver to prevent disk-exhaustion.** By default, no log-rotation
> is performed. As a result, log-files stored by the default json-file logging driver can
> cause a significant amount of disk space to be used for containers that generate much
> output, which can lead to disk space exhaustion."

Docker now also has **dual logging**
(<https://docs.docker.com/engine/logging/dual-logging>): the `local` driver keeps a
rotating cache (5 files × 20 MB by default) purely so `docker logs` keeps working. So
switching to `local` costs nothing operationally and fixes the unbounded growth.

Add to all three services in both compose files:

```yaml
logging:
  driver: local
  options:
    max-size: "10m"
    max-file: "5"
    compress: "true"
```

`deploy/README.md` and `ROLLBACK.md` §4 both rely on `docker compose logs` working, so
verify `docker compose -f docker-compose.staging.yml logs --tail 100 api` after the change.

### Security headers (C1)

This is a Vite SPA with no SSR, which makes CSP **simpler** than the usual advice suggests.
Two findings from <https://github.com/vitejs/vite/issues/20531>:

- Vite's `html.cspNonce` is actively **unsuitable** for an SPA: the nonce is generated once
  at build time, so it is not unique per request, and it conflicts with static caching. The
  issue calls deploying it a "false sense of security".
- The correct approach for a static build is a plain `script-src 'self'`. Vite emits external
  module scripts under `/assets`; `index.html` contains no inline script.

**One blocker, and it is the same class of bug as UAT-01.** `ui.jsx:103` sets an inline
style attribute on the legend swatch:

```jsx
style={{ background: item.color, borderColor: item.border ?? item.color }}
```

A CSP cannot express "allow this one attribute" without `style-src-attr 'unsafe-inline'`.
The fix that satisfies both the CSP and `AGENTS.md` §7 is to delete the inline style and
drive the swatch from the same `var(--token)` the legend item already names:

```jsx
<span className={`${styles.swatch} ${styles[`swatch_${item.tone}`]}`} />
```

with a `tone` of `seed | mutual | person | place | missing` mapped to tokens in
`ui.module.css`. That removes the last inline style, keeps colour literals out of the
component, and makes the legend consistent with the Cytoscape fix — where a token had to be
resolved explicitly rather than assumed.

Also set `build: { assetsInlineLimit: 0 }` in `vite.config.js` so nothing becomes a `data:`
URI that `img-src`/`font-src` would have to permit.

Then, in the `server` block of `nginx.conf.template`:

```nginx
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "geolocation=(), microphone=(), camera=(), interest-cohort=()" always;
add_header X-Frame-Options "DENY" always;
server_tokens off;
client_max_body_size 64k;
```

Notes that matter for this app specifically:

- `connect-src 'self'` is sufficient and correct — the client calls a relative `/api`
  (`api/client.js:3`) and nginx proxies it same-origin. Nothing needs a remote origin.
- `always` is required. Without it nginx omits headers on error responses, which is exactly
  when a 502 from the analysis timeout occurs.
- `X-Frame-Options` is redundant alongside `frame-ancestors 'none'`, but costs nothing and
  covers very old browsers.
- `Strict-Transport-Security` is deliberately absent — it is only safe once TLS terminates
  here, and sending it over plain HTTP accomplishes nothing. Add it with C2.
- `client_max_body_size 64k` closes C4. The only POST body is `{"title": "..."}` capped at
  512 characters (`routers/analysis.py:24-31`).
- Deploy the CSP as **`Content-Security-Policy-Report-Only` first**, with
  `report-uri` pointed somewhere, then promote it. Nothing in this repository can observe a
  browser enforcing it, so a silent break would be invisible — which is the UAT-01 lesson
  applied to a new control.

### FastAPI middleware (C1, C5, C2)

The documented order is HTTPSRedirect → TrustedHost → CORS → ProxyHeaders → GZip
(<https://fastapi.tiangolo.com/advanced/middleware/>), and `AGENTS.md` §14 says to extend
`main.py`'s existing configuration rather than add a parallel path. So add to the existing
`create_app()`:

- **`TrustedHostMiddleware`** — guards Host-header attacks. Free, and the app is otherwise
  an open Host acceptor.
- **`GZipMiddleware`** — analysis responses are large JSON; nginx gzips the SPA but the
  proxied `/api` responses currently go out uncompressed.
- **Drop `--forwarded-allow-ips '*'`** (`backend/Dockerfile:36`). This is the C5 finding, and
  the research names the identical failure mode: `ProxyHeadersMiddleware` "defaults to
  `trusted_hosts=["*"]`, which accepts proxy headers from any source. In production, always
  set it to the IP addresses or ranges of reverse proxies you trust to avoid IP spoofing."
  Since nginx is the only thing that should reach uvicorn, name it explicitly — and note
  that `X-Forwarded-For` is what the new rate limiter will key on, so trusting it blindly
  would make the limiter trivially bypassable by a spoofed header.

Do **not** add `HTTPSRedirectMiddleware` yet: the backend is behind nginx and receives
plain HTTP internally, so it would redirect in a loop. It belongs at the TLS terminator.

### Blocking sync DB calls in an async handler

`routers/analysis.py:53` calls `repository.store_analysis` — synchronous SQLAlchemy — from
inside an `async def` route, and `main.py:97` calls `db.ping()` the same way. Both block the
event loop for the duration of a database round trip. With one worker, a slow write stalls
every other request.

The obvious fix — `await run_in_threadpool(store_analysis, result)` — **can deadlock**, and
this is documented. From
<https://github.com/fastapi/fastapi/discussions/9512>: a session is acquired lazily, so N
concurrent requests can each take a thread and block waiting for a pool connection while
the teardown tasks that would release those connections cannot themselves be scheduled.
"async path operations are handled on the main thread" — blocking one blocks the release
path for all of them.

Two safe options:

**Preferred — a background task.** The write is already best-effort and the response does
not depend on it, so it does not belong in the request path at all:

```python
from fastapi import BackgroundTasks

async def analyze(
    client: ClientDep,
    settings: SettingsDep,
    payload: AnalyzeRequest,
    background: BackgroundTasks,
) -> AnalysisResult:
    try:
        result = await analyze_article(client, settings, payload.title)
    except WikipediaError as exc:
        raise _upstream_error(exc) from exc

    background.add_task(repository.store_analysis, result)
    return result
```

FastAPI runs sync background work in a threadpool *after* the response is sent. That
removes the event-loop block, removes the write from user-visible latency, and means a slow
database no longer affects the response at all. It needs one test change: `test_analyze`
will no longer see the write, which is the correct new behaviour.

**Alternative — `fastapi.concurrency.contextmanager_in_threadpool`**, which exists precisely
to handle the deadlock above: it runs `__exit__` under its own `CapacityLimiter` so session
release is never starved. Use this if the write must complete before the response.

For `db.ping()` in the health endpoint, do not move it — a synchronous health probe that
runs in a threadpool is still correct, and `HTTPSRedirect`/health semantics are simpler if
it stays. Instead cache the result for a few seconds so a 30-second healthcheck interval
does not open a fresh connection every time, and downgrade the failure log from
`logger.exception` to a rate-limited `logger.warning` to stop the log-spam amplifier in A4.

### Other C-items

- **C3** — `routers/articles.py:107-112`:
  `titles: list[Annotated[str, StringConstraints(max_length=512)]] = Query(min_length=1, max_length=50)`.
  Same pattern `dependencies.py:22-30` already uses.
- **C9** — one `ErrorBoundary` in `main.jsx` around `<App />`, rendering the existing
  `ErrorMessage` from `ui.jsx:79` so there is one visual language for failure. `main.jsx:10`
  already has `<StrictMode>`, and StrictMode double-mounting is what surfaces a missing
  boundary during development.
- **C10** — `database/docker-compose.yml:11` → `"127.0.0.1:5432:5432"`.
- **C11** — add `?connect_timeout=5` to `docker-compose.staging.yml:49`, matching production
  line 58.
- **C12** — either correct `ARCHITECTURE.md` §11.8 item 2, or make the upsert dialect-aware
  by selecting the insert construct on the bound engine. The documented-but-broken fallback
  is the problem; the simplest honest fix is to correct the document.
- **C13** — `LICENSE` and a root `README.md`. The licence choice is a person's to make.

---

## 6. B-section — the rest

### B3 — the stale-response race (do this one next; it is two lines)

The canonical React fix is `AbortController` in the effect cleanup
(<https://react.dev/learn/you-might-not-need-an-effect>). Two implementation details
specific to this codebase:

**`main.jsx:10` uses `<StrictMode>`, and that constrains the shape.** Creating the
`AbortController` outside the effect is a known trap: StrictMode's double-mount aborts a
controller it then reuses, and the second run fails immediately
(<https://github.com/react/react/issues/25962>). A controller is one-shot — once aborted it
stays aborted, so every request needs a fresh one. It must be created inside the callback
that starts the request.

**`run()` is a `useCallback` in a context, not an effect, so there is no cleanup hook.**
The id check is therefore the better fit here, and it is smaller:

```jsx
const runIdRef = useRef(0)

const run = useCallback(async (title) => {
  const trimmed = String(title ?? '').trim()
  const runId = ++runIdRef.current
  // ...existing validation and loading state...
  try {
    const result = await analyzeArticle(trimmed)
    if (runId !== runIdRef.current) return null   // a newer run owns the screen
    setState({ /* ... */ })
    return result.article.title
  } catch (error) {
    if (runId !== runIdRef.current) return null
    setState({ /* ... */ })
    return null
  }
}, [])
```

Thread an `AbortController` through `analyzeArticle` as well if you want the upstream
request cancelled rather than merely ignored — that also stops the wasted Wikipedia call
described in C7. The id check alone is the correctness fix; the abort is the cost fix.

There is a lint rule for exactly this class of bug —
`web-api-no-leaked-fetch`, in `eslint-plugin-web-api-no-leaked-fetch` — which flags "a
`fetch` started in the setup function of `useEffect` without passing an `AbortSignal` and
aborting it in cleanup". The project uses `oxlint`, not ESLint
(`AGENTS.md` §3 forbids adding tooling unasked), so this is a note for whoever revisits the
linter, not an action.

### B5 — `session_scope` swallowing caller bugs

Narrow the `except` so `"Database write failed"` can only ever mean a database problem.
The cleanest form separates the two failure sources:

```python
session = _session_factory()
try:
    yield session
except Exception:  # noqa: BLE001 - persistence must never break a request
    # A failure in the caller's block, not necessarily the database. Say which,
    # or a bug in repository.py reads as an outage and sends the wrong person.
    logger.exception("Cache write aborted by an error in the caller")
    session.rollback()
else:
    try:
        session.commit()
    except Exception:  # noqa: BLE001 - persistence must never fail a request
        logger.exception("Database write failed, continuing without cache")
        session.rollback()
finally:
    session.close()
```

This keeps the `AGENTS.md` §5 invariant intact — a database problem still cannot fail a
request — while making the log line mean what it says.

### B6 — testing the write path

There is no mocking library in the project and `AGENTS.md` §8 forbids adding one, so the
test needs a real database. The CI `images` job
(`.github/workflows/ci.yml:69-136`) already has Docker and boots containers, so a
`postgres:16-alpine` service with the existing `init.sql` is a few lines. Set
`DATABASE_URL` for that one test only; `conftest.py:11` already parameterises
`database_url=""`, so the other 85 tests stay untouched and offline.

Cover, at minimum: a successful `store_analysis` round-trip, a re-analysis of the same
article (`ON CONFLICT` path, and that `article_links` is replaced not appended), and the
`uq_link` duplicate that was UAT-02. This is the gap that let a SQL-layer defect ship.

### B7 — `looks_like_person`

Confirmed dead: `_NATIONALITY_HINT` is `^\s*`-anchored and matches only a nationality
prefix, so any string satisfying it that also matches `_PERSON_PATTERN` was already
returned as `PERSON` by `classify_description` at `classifier.py:79-80`. It can never
return `True` for a description that reaches it, and it is called from nowhere.

Either implement it as a genuine fallback — a second pattern set for descriptions with no
role word, which is the only place it could add value — or delete it. `AGENTS.md` §14
forbids deleting a module as "cleanup" without checking imports; the check is done and
documented here, so deletion is defensible. `CHECKLIST.md` §4 currently records it as
"wired for future use, do not delete", so that row must change in the same commit.

### B4 — unbounded pagination loop

Add a page cap derived from the link limit, and raise `WikipediaError` if a continuation
page contributes no new titles — that is the exact condition that would otherwise spin
forever holding a semaphore slot.

---

## 7. A3 — authentication: a decision, not an implementation

`ARCHITECTURE.md` §10.1 defers this and `PRD.md` OQ-05 leaves it open. Research adds one
constraint that should shape the answer:

**FastAPI has a published CSRF advisory** — GHSA-8h2j-cgx8-6xv7,
<https://github.com/fastapi/fastapi/security/advisories>. It concerns cookie-based
authentication. The application is **not affected today**: it sets no cookies and
`allow_credentials=False` at `main.py:72`.

It becomes affected the moment cookie auth is added. So the choice in §F of
`PUBLIC-READINESS.md` is really three options with different downstream work:

| Model | CSRF exposure | Work |
| ----- | -------------- | ---- |
| **Open + rate limited** (recommended to start) | None | None beyond §3. Honest about being public, and adequate for a read-only analysis tool. |
| API key in a header | None — not ambient, so not CSRF-able | A key store, a dependency, key rotation, and it must not be logged. |
| Cookie session | **Yes** — needs the token/double-submit pattern | Everything above, plus CSRF tokens. |

The recommendation is the first: this API is read-only, every operation is public
Wikipedia data, and there is nothing to protect but the operator's own capacity. Rate
limiting plus a bot password solves the real problem. Add authentication when there is
something private to hold.

**Whatever is chosen, note the interaction with C5**: the rate limiter keys on client IP,
which arrives via `X-Forwarded-For`. If that header is still trusted from any source, the
limiter is bypassable with one header. Fix C5 in the same change.

---

## 8. Documentation and process gaps

| ID | Fix |
| -- | --- |
| **D1** | Extend the CI `schema` job. `ci.yml:155-156` already parses both files; compare columns and indexes, not just table names. There is live drift to catch: `models.py:97` creates a plain index on `analysis_runs.created_at` while `init.sql:59-60` creates it `DESC`. |
| **D2** | The researched answer, since there is still no migration tool: add an idempotent `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` block to `init.sql`, after the `CREATE TABLE IF NOT EXISTS` statements and inside the same transaction. It preserves the two properties `ROLLBACK.md` §1 depends on — additive only, no `DROP` — and unlike the `CREATE TABLE IF NOT EXISTS` statements it is not a no-op against an existing table. `deploy/README.md` already tells operators to apply `init.sql` by hand; this makes that instruction actually work. |
| **D3** | The decision is still a person's: what does `total_links` count? The researched note is that `GET /api/connections/map` and `POST /api/analyze` must agree, or the smoke test's own invariant (`smoke_test.py:250-258`, which compares `summary.total_*` against array lengths) starts failing for a different reason. |
| **D4** | 4 people from 444 links. The `general` omission at `classifier.py:26-29` is deliberate and defensible. Worth measuring before users depend on the split — and B7's dead second pass was presumably the intended mitigation. |
| **D5** | Fix `DEFECTS.md` and `CHECKLIST.md` in the same commits as the code they describe, per `AGENTS.md` §11. |

**One new documentation obligation.** The Wikimedia limits in §1 are external, dated
("new in 2026 and subject to experimentation and change") and will change without notice.
Record them in `ARCHITECTURE.md` §12 alongside the timeout and retry decisions already
resolved there, with the source URL and the date. Otherwise the next maintainer sees
`max_concurrent_requests = 4` and reasonably "fixes" it back up.

---

## 9. What changes, in order

| # | Change | Fixes | New risk introduced |
| - | ------ | ----- | ------------------- |
| 1 | Bot account + bot password; `max_concurrent_requests` 4 → 3; `maxlag`; `Retry-After` | §1 capacity, B1 ceiling, C8 | A credential in the environment. Never in the image. |
| 2 | Paginate `get_links_for_page_ids`; carry a `complete` flag; never assert `ONE-WAY` on incomplete evidence | **B1** | More upstream requests per analysis — budget for it in step 4. |
| 3 | Request-id guard in `AnalysisContext.run` | **B3** | None. Two lines. |
| 4 | `run_id` + `AbortController`; fold the map into `AnalysisResult`; drop the second fetch | B3 cost, B2, C7 | `test_analyze` payload assertions may need updating. |
| 5 | nginx `limit_req` + app-level limiter, budgets from §1 arithmetic | **A1** | 429s for legitimate bursts. `burst`/`nodelay` mitigate. |
| 6 | Read path for `article_links`; explicit TTL | A2, NFR-01/02 | A stale cache. Hence the TTL and the `fetched_at` check. |
| 7 | `background.add_task` for the write; integration test against real Postgres | Event-loop block, **B6** | The write is no longer complete when the response is sent. Correct, but assert it in the test. |
| 8 | Log driver → `local`; retention on `analysis_runs` | A4 | None. Verify `docker compose logs` still works. |
| 9 | CSP report-only, then enforce; other headers; `TrustedHost`; `GZip`; drop `--forwarded-allow-ips '*'`; `client_max_body_size` | C1, C2, C4, C5 | **CSP can break the app invisibly** — no browser here can see it. Report-only first. |
| 10 | `ErrorBoundary`; per-title length cap; loopback DB port; staging `connect_timeout`; doc corrections | C3, C9, C10, C11, D1, D5 | None. |
| 11 | Decisions for a person: auth model, licence, `total_links`, schema mechanism | A3, C13, D2, D3 | — |

Steps 1–4 are independent and each is small. Step 4's map-folding should come after step 2
so the extra upstream cost is visible in the rate-limit budget before it is tuned.

---

## 10. Sources

All retrieved 27 September 2026.

**Wikimedia / MediaWiki**

- API rate limits (2026), limits table, `Retry-After`, "3 or fewer" concurrency, bot exemption — <https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits>
- API rate limits FAQ — User-Agent compliance — <https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits/FAQ>
- API:Etiquette — `maxlag`, `User-Agent`, `Accept-Encoding`, caching, exponential backoff — <https://www.mediawiki.org/wiki/API:Etiquette>
- API:Properties — 500 vs 5000 result limit, `apihighlimits` — <https://www.mediawiki.org/wiki/API:Properties>
- API:Links — `pllimit` 1–500, `pltitles` 50 values, `plcontinue` — <https://www.mediawiki.org/wiki/API:Links>
- Manual:Bot passwords — <https://www.mediawiki.org/wiki/Manual:Bot_passwords>
- Wikimedia API announce list — rollout of the anonymous limits — <https://lists.wikimedia.org/hyperkitty/list/mediawiki-api-announce@lists.wikimedia.org/thread/PYJ545D33CDPKJRADCMZAQDDWAI7FIGO>

**Security**

- OWASP API Security Top 10 2023 — <https://owasp.org/API-Security/editions/2023/en/0x11-t10>
- OWASP API4:2023 Unrestricted Resource Consumption — <https://owasp.org/API-Security/editions/2023/en/0xa4-unrestricted-resource-consumption>
- FastAPI security advisories, incl. GHSA-8h2j-cgx8-6xv7 (CSRF) — <https://github.com/fastapi/fastapi/security/advisories>

**FastAPI / async Python**

- Middleware reference and recommended order — <https://fastapi.tiangolo.com/advanced/middleware/>
- `fastapi/concurrency.py` — `run_in_threadpool`, `contextmanager_in_threadpool` — <https://github.com/fastapi/fastapi/blob/master/fastapi/concurrency.py>
- Discussion #9512 — threadpool + connection-pool deadlock — <https://github.com/fastapi/fastapi/discussions/9512>
- Discussion #12089 — sync vs async session latency — <https://github.com/fastapi/fastapi/discussions/12089>
- Discussion #5351 — "you will block the event loop" — <https://github.com/fastapi/fastapi/issues/5351>

**Frontend**

- "You Might Not Need an Effect" — stale-response cleanup — <https://react.dev/learn/you-might-not-need-an-effect>
- react/react#25962 — StrictMode aborts a controller created outside the effect — <https://github.com/react/react/issues/25962>
- `web-api-no-leaked-fetch` rule — <https://eslint-react.xyz/docs/rules/web-api-no-leaked-fetch>
- Vite #20531 — why `html.cspNonce` is wrong for an SPA — <https://github.com/vitejs/vite/issues/20531>
- CSP for SPAs — start Report-Only, lock `default-src` and `script-src` first — <https://codefunc.com/blog/content-security-policy-spas-guide>

**Rate limiting**

- slowapi (2053 stars, health 84/100; "alpha quality"; explicit `request` required) — <https://pypi.org/project/slowapi/>
- slowapi limitations — <https://github.com/laurentS/slowapi/blob/master/docs/index.md>
- fastapi-limiter (pyrate-limiter based) — <https://github.com/long2ice/fastapi-limiter>
- FastAPI rate-limiting production guide — in-memory vs redis, `X-RateLimit` headers, log throttling — <https://dev.to/ayush_kumar_085a0f2c54e3f/fastapi-rate-limiting-practical-guide-for-production-2f52>

**Docker**

- Configure logging drivers — "use `local` to prevent disk-exhaustion" — <https://docs.docker.com/engine/logging/configure>
- json-file options — `max-size`, `max-file` — <https://docs.docker.com/engine/logging/drivers/json-file.md>
- Dual logging — `docker logs` still works with `local` — <https://docs.docker.com/engine/logging/dual-logging>

---

## Revision history

| Version | Date | Author | Status | Change |
| ------- | ---- | ------ | ------ | ------ |
| 1.0 | 27 Sep 2026 | `unassigned` | Open | Initial hardening plan. Adds the Wikimedia 2026 rate-limit ceiling, which reorders `PUBLIC-READINESS.md` §F: the external capacity limit and the bot-password path now precede local rate limiting. |
