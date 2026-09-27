"""Guards the security configuration, because nothing else observes it.

Every defect in this file's scope has the same shape: a control that is written down,
looks right, and is silently not in effect. None of them fails a build, a lint run or a
test, because the thing that breaks is either a config file or a runtime behaviour with no
assertion attached to it.

Three already happened here:

* Cytoscape discarded every design token because it cannot read CSS custom properties
  (UAT-01). The map rendered with no colour and nothing complained.
* `api/client.js` dropped `method` and `body`, so the browser sent `GET /api/analyze` and
  got a 405. The application's core feature had never worked, and the smoke test passed
  because it talks HTTP directly and never uses the client (DEF-003).
* The obvious way to add nginx security headers is to put them in the `server` block.
  nginx drops every inherited `add_header` as soon as a level defines one of its own, so
  that silently strips the headers from `/assets/` and from `index.html` - the two
  responses that most need them. This file is written *because* that trap is invisible.

So the assertions are on the source text of the configuration. That is a weaker guarantee
than a rendered response and does not pretend to be one: it proves the rule is still
written down and that nginx is not in a position to drop it. What it buys is that deleting
a directive, moving one, or editing a compose file without touching nginx now fails the
suite instead of shipping.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# `pytest.ini` sets `pythonpath = .` and the suite runs from `backend/`, so the repo root
# is a fixed relative location rather than being discovered.
ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
BACKEND = ROOT / "backend"
DEPLOY = ROOT / "deploy"

NGINX_CONF = FRONTEND / "nginx.conf.template"
NGINX_HEADERS = FRONTEND / "nginx-security-headers.conf"
NGINX_PROXY = FRONTEND / "nginx-proxy-api.conf"
VITE_CONFIG = FRONTEND / "vite.config.js"
FRONTEND_DOCKERFILE = FRONTEND / "Dockerfile"
BACKEND_DOCKERFILE = BACKEND / "Dockerfile"
COMPOSE_FILES = (
    DEPLOY / "docker-compose.staging.yml",
    DEPLOY / "docker-compose.production.yml",
)
DB_COMPOSE = ROOT / "database" / "docker-compose.yml"

_COMPOSE_SERVICE = re.compile(r"^  ([a-z][a-z0-9_-]*):\s*$", re.MULTILINE)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --- nginx --------------------------------------------------------------------
# WSTG 4.2.12 Test for Content Security Policy, 4.2.14 Test Other HTTP Security Header
# Misconfigurations, 4.2.7 Test HTTP Strict Transport Security.
# https://wstg.owasp.org/latest/4-Web_Application_Security_Testing/02-Configuration_and_Deployment_Management_Testing


def _strip_comments(text: str) -> str:
    """nginx config with comment lines removed.

    Needed because prose in this config legitimately contains the words the assertions
    look for - a comment explaining why `client_max_body_size` sits at server level
    mentions "location", and a comment explaining the proxy trust list contains `*`.
    Matching on commented text is how a check passes or fails for the wrong reason.
    """

    return "\n".join(line for line in text.splitlines() if not line.strip().startswith("#"))


def _server_block(nginx: str) -> str:
    """The `server { ... }` block, with comments and nested location bodies removed.

    Returns only the directives declared directly in the server block, because that is
    the level at which a limit has to sit to apply to every request.
    """

    body = _strip_comments(nginx)
    start = body.index("server {")
    depth = 0
    out: list[str] = []
    for line in body[start:].splitlines():
        depth += line.count("{") - line.count("}")
        if depth <= 0 and out:
            break
        out.append(line)
    # Drop everything from the first location block onward: those directives belong to
    # that location, not to the server.
    server_level: list[str] = []
    nested = 0
    for line in out:
        if nested:
            nested += line.count("{") - line.count("}")
            continue
        if "location" in line:
            nested = 1
            continue
        server_level.append(line)
    return "\n".join(server_level)


def _compose_services(text: str) -> dict[str, str]:
    """Service name -> body, for the keys under the top-level `services:` block only.

    Hand-rolled rather than a YAML parse so the suite keeps working with the dependency
    set it has. The important detail is stopping at the next column-0 key, otherwise
    `volumes:` entries are mistaken for services that need log rotation.
    """

    body = _strip_comments(text)
    if "services:" not in body:
        return {}

    start = body.index("services:")
    rest = body[start + len("services:") :]
    end = len(rest)
    for match in re.finditer(r"^[A-Za-z]", rest, re.MULTILINE):
        end = match.start()
        break
    block = rest[:end]

    services: dict[str, str] = {}
    starts = list(re.finditer(r"^  ([A-Za-z][A-Za-z0-9_.-]*):\s*$", block, re.MULTILINE))
    for index, match in enumerate(starts):
        stop = starts[index + 1].start() if index + 1 < len(starts) else len(block)
        services[match.group(1)] = block[match.end() : stop]
    return services


@pytest.fixture(scope="module")
def nginx() -> str:
    return _read(NGINX_CONF)


@pytest.fixture(scope="module")
def headers() -> str:
    return _read(NGINX_HEADERS)


def test_every_security_header_carries_the_always_flag(headers: str) -> None:
    """Without `always`, nginx omits the header on error responses.

    That is precisely when a 502 from a slow analysis goes out, which is when a
    Content-Security-Policy matters most. nginx syntax puts the flag *before* the
    semicolon - `add_header name value [always];` - so the check looks there.
    """

    directives = re.findall(
        r"^\s*add_header\s+([A-Za-z-]+)\s+.*?;",
        _strip_comments(headers),
        re.MULTILINE,
    )
    assert directives, "no security headers found at all"

    without_always = [
        name
        for name in directives
        if not re.search(
            rf"^\s*add_header\s+{re.escape(name)}\s+.*\balways\s*;",
            _strip_comments(headers),
            re.MULTILINE,
        )
    ]
    assert not without_always, (
        f"these headers are missing the `always` flag: {without_always}. nginx omits "
        "add_header on error responses without it."
    )


@pytest.mark.parametrize(
    "header",
    [
        "Content-Security-Policy",
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Permissions-Policy",
    ],
)
def test_the_header_set_is_complete(headers: str, header: str) -> None:
    assert f"add_header {header} " in headers, f"{header} is not set on any response"


def test_the_content_security_policy_closes_the_dangerous_directives(headers: str) -> None:
    csp = re.search(r'add_header Content-Security-Policy "([^"]+)"', headers)
    assert csp, "no Content-Security-Policy found"

    policy = csp.group(1)
    for directive in ("default-src", "script-src", "object-src", "base-uri", "frame-ancestors"):
        assert f"{directive} " in policy, f"CSP is missing {directive}"

    assert "frame-ancestors 'none'" in policy, "the app must not be framable"
    assert "object-src 'none'" in policy
    assert "base-uri 'self'" in policy, "base-tag hijacking is otherwise unconstrained"
    # A script-src with 'unsafe-inline' or 'unsafe-eval' defeats the point of having a CSP.
    script_src = re.search(r"script-src ([^;]+)", policy)
    assert script_src, "no script-src"
    assert "'unsafe-inline'" not in script_src.group(1)
    assert "'unsafe-eval'" not in script_src.group(1)


def test_the_csp_allows_only_this_origin_for_network_calls(headers: str) -> None:
    """The client uses a relative /api, so no third-party origin is needed at all."""

    csp = re.search(r'add_header Content-Security-Policy "([^"]+)"', headers)
    assert csp
    policy = csp.group(1)
    connect = re.search(r"connect-src ([^;]+)", policy)
    assert connect, "no connect-src"
    assert connect.group(1).strip() == "'self'", (
        "connect-src should be exactly 'self'. A remote origin here means the SPA is "
        "phoning home, and it would widen the policy to whatever that host is."
    )


def _blocks(text: str) -> list[tuple[str, str]]:
    """Every `{ ... }` block in an nginx config, as (header line, body) pairs.

    Brace-aware, because nginx blocks nest and a regex cannot tell where one ends. The
    first pass of this test was written with a regex and it silently passed against a
    config that had the exact defect it exists to catch, so the parser is explicit.
    """

    lines = _strip_comments(text).splitlines()
    found: list[tuple[str, str]] = []
    stack: list[tuple[str, list[str]]] = []
    for line in lines:
        if stack:
            stack[-1][1].append(line)
        opens = line.count("{")
        if opens:
            stack.append((line, []))
        closes = line.count("}")
        for _ in range(closes):
            if stack:
                header, body = stack.pop()
                found.append((header, "\n".join(body)))
    return found


def test_every_level_that_sets_a_header_also_includes_the_header_set(nginx: str) -> None:
    """The nginx inheritance trap, guarded.

    `add_header` is inherited "if and only if there are no add_header directives defined on
    the current level" (https://nginx.org/en/docs/http/ngx_http_headers_module.html). A
    location that sets a header of its own therefore loses every inherited one, silently -
    no error, no warning, and in this config it strips the headers from the hashed
    bundles and from index.html, which is the document that loads them.
    """

    offenders: list[str] = []
    checked = 0

    for header, body in _blocks(nginx):
        if "location" not in header:
            continue
        checked += 1
        defines_own_header = re.search(r"^\s*add_header\s", body, re.MULTILINE)
        includes_snippet = "nginx-security-headers.conf" in body
        if defines_own_header and not includes_snippet:
            offenders.append(header.strip())

    assert checked >= 4, (
        f"only {checked} location blocks were parsed out of the config; the parser is "
        "probably broken, and a parser that finds nothing proves nothing"
    )
    assert not offenders, (
        f"these locations set add_header without including the shared header set: "
        f"{offenders}. nginx drops every inherited add_header once the current level "
        "defines one, so the security headers would be absent from exactly these "
        "responses and nothing would report it."
    )


def test_the_shared_header_snippet_is_actually_included_somewhere(nginx: str) -> None:
    assert "nginx-security-headers.conf" in _strip_comments(nginx), (
        "the site config never includes the security header snippet, so no response "
        "carries any of them"
    )
    assert "nginx-proxy-api.conf" in _strip_comments(nginx), (
        "the site config never includes the shared proxy snippet"
    )


def test_the_api_proxy_has_no_trailing_path() -> None:
    """A trailing slash strips the /api prefix and every route 404s."""

    proxy = _read(NGINX_PROXY)
    line = re.search(r"^\s*proxy_pass\s+(\S+);", proxy, re.MULTILINE)
    assert line, "no proxy_pass found"
    assert not line.group(1).rstrip("/").endswith("/api"), (
        f"proxy_pass {line.group(1)} has a trailing path; it would strip the /api prefix"
    )
    assert line.group(1) == "http://fastapi"


def test_the_backend_implementation_is_not_advertised() -> None:
    proxy = _read(NGINX_PROXY)
    assert "proxy_hide_header X-Powered-By" in proxy
    assert "server_tokens off" in _read(NGINX_CONF)


def test_dotfiles_and_server_side_sources_are_not_served() -> None:
    nginx = _read(NGINX_CONF)
    assert re.search(r"location\s+~\s+/\\\.\(\?!well-known\)\s*\{[^}]*deny all", nginx), (
        "dotfiles are not denied. A stray .env in the build context is a credential leak "
        "waiting to be requested by name."
    )
    assert re.search(r"\\\.\(.*\)\$", nginx), "no deny rule for source/config file types"


def test_the_request_body_is_bounded() -> None:
    """nginx only enforces client_max_body_size once it has selected a location.

    So a limit declared inside some branches is not a limit; it has to be at server level.
    """

    server_level = _server_block(_read(NGINX_CONF))
    assert "client_max_body_size" in server_level, (
        "client_max_body_size must be in the server block, not inside a location, or "
        "requests that never reach one are unbounded"
    )
    match = re.search(r"client_max_body_size\s+(\S+);", server_level)
    assert match
    size = match.group(1)
    if size != "0":
        kilobytes = int(size.rstrip("kKmM").rstrip("K"))
        # The only body this app accepts is {"title": "..."} capped at 512 characters.
        assert kilobytes <= 256, (
            f"client_max_body_size is {size}. The largest legitimate request is under 1 KB."
        )


def test_the_analysis_endpoints_are_rate_limited() -> None:
    """WSTG 4.2 / OWASP API4:2023 Unrestricted Resource Consumption."""

    nginx = _read(NGINX_CONF)
    assert re.search(r"limit_req_zone\s+\$binary_remote_addr\s+zone=analyze", nginx), (
        "no rate-limit zone for the expensive endpoints"
    )
    assert re.search(r"location = /api/analyze\s*\{[^}]*limit_req zone=analyze", nginx), (
        "/api/analyze is not rate limited. It is the single most expensive route in the "
        "application, in this deployment's own request budget and in Wikimedia's."
    )
    assert re.search(
        r"location /api/connections/\s*\{[^}]*limit_req zone=analyze", nginx
    ), "/api/connections/ is not rate limited"
    assert "limit_req_status 429" in nginx, "a throttled request must answer 429, not 503"


def test_the_rate_limit_budget_matches_the_published_upstream_limit() -> None:
    """The zone rate is a consequence of Wikimedia's 200 req/min, not a preference.

    See docs/ARCHITECTURE.md section 12. If either number moves, this test is the reminder
    that the other one has to move with it.
    """

    nginx = _read(NGINX_CONF)
    match = re.search(r"zone=analyze:10m rate=(\d+)r/m", nginx)
    assert match, "the analyze rate limit is not expressed in requests per minute"
    # 200 upstream requests/minute at ~30 per analysis is about 6 analyses/minute.
    assert int(match.group(1)) <= 10, (
        f"the analyze zone allows {match.group(1)}r/m, which is above what Wikimedia's "
        "200 req/min ceiling supports for the whole deployment"
    )


# --- Vite dev server ----------------------------------------------------------
# The dev server is a real attack surface even though it is development-only. There is an
# active mass-scanning campaign against internet-exposed Vite dev servers (F5 counted 800
# attacks in a month) pulling .env files, cloud credentials and /proc/self/environ.


@pytest.fixture(scope="module")
def vite() -> str:
    return _read(VITE_CONFIG)


def test_the_dev_server_is_not_bound_to_every_interface(vite: str) -> None:
    """CVE-2026-39363 and CVE-2026-39364 both require the dev server to be reachable.

    An explicit loopback bind means the exposure has to be a deliberate act rather than a
    default, and the fix versions are already in package.json.
    """

    assert re.search(r"host:\s*'127\.0\.0\.1'", vite), (
        "the dev server has no explicit host. Vite's file-disclosure CVEs of 2025 and 2026 "
        "all required --host or server.host, and exposed instances are being mass-scanned."
    )


def test_the_dev_server_does_not_answer_any_origin(vite: str) -> None:
    """CVE-2025-24010: a wildcard CORS default let any page read the dev server."""

    assert re.search(r"cors:\s*\{", vite), "no explicit dev-server CORS allow-list"
    cors = vite[vite.index("cors: {") :]
    cors = cors[: cors.index("}")]
    assert "*" not in cors, "the dev server CORS allow-list contains a wildcard"


def test_the_dev_server_refuses_to_serve_files_outside_the_project(vite: str) -> None:
    assert re.search(r"fs:\s*\{", vite)
    fs = vite[vite.index("fs: {") :]
    assert "strict: true" in fs, "server.fs.strict is not enabled"
    for denied in (".env", "*.{crt,pem,key", ".git", ".aws", ".tfstate"):
        assert denied in fs, f"server.fs.deny does not cover {denied}"


def test_build_inlines_nothing_as_a_data_uri(vite: str) -> None:
    """Keeps `data:` out of script-src, and closes the assetsInlineLimit path."""

    assert re.search(r"assetsInlineLimit:\s*0", vite), (
        "build.assetsInlineLimit is not 0, so a CSP may need data: in script-src"
    )


# --- backend image ------------------------------------------------------------


def test_the_container_does_not_trust_forwarded_headers_from_anyone() -> None:
    """`*` makes the rate limiter bypassable with one spoofed header.

    The comment above the CMD explains what `*` would mean, so this asserts on the
    command itself rather than on the whole file.
    """

    dockerfile = _strip_comments(_read(BACKEND_DOCKERFILE))
    cmd = [line for line in dockerfile.splitlines() if "forwarded-allow-ips" in line]
    assert cmd, "the container does not set --forwarded-allow-ips at all"
    assert not any('"*"' in line or "'*'" in line for line in cmd), (
        "--forwarded-allow-ips is '*'. The rate limiter keys on X-Forwarded-For, so a "
        "client that forges it chooses its own limit bucket."
    )
    assert any(re.search(r"\d+\.\d+\.\d+\.\d+/\d+", line) for line in cmd), (
        "no CIDR allow-list given for --forwarded-allow-ips"
    )


def test_the_frontend_image_validates_its_own_config_at_build_time() -> None:
    """A missing include should fail the build, not the deployment."""

    dockerfile = _read(FRONTEND_DOCKERFILE)
    assert "nginx-security-headers.conf" in dockerfile, "the header snippet is not copied in"
    assert "nginx-proxy-api.conf" in dockerfile, "the proxy snippet is not copied in"
    assert re.search(r"nginx\s+-t", dockerfile), (
        "the image is never syntax-checked, so a broken include is found in production"
    )


# --- containers ---------------------------------------------------------------


@pytest.mark.parametrize("compose", COMPOSE_FILES, ids=lambda p: p.name)
def test_every_service_rotates_its_logs(compose: Path) -> None:
    """Docker's default json-file driver does not rotate, by design.

    An unbounded log is a slow disk-exhaustion failure, and `db.ping()` plus
    `session_scope()` both log a full traceback on every failure.
    """

    services = _compose_services(_read(compose))
    assert {"db", "api", "web"} <= set(services), (
        f"expected the db, api and web services in {compose.name}, found {sorted(services)}"
    )

    for name in ("db", "api", "web"):
        body = services[name]
        assert "logging:" in body, f"service '{name}' in {compose.name} has no log rotation"
        assert "driver: local" in body, (
            f"service '{name}' in {compose.name} does not use the local driver, which is "
            "the one Docker documents for preventing disk exhaustion"
        )
        assert "max-size" in body and "max-file" in body, (
            f"service '{name}' in {compose.name} sets no rotation limits"
        )


@pytest.mark.parametrize("compose", COMPOSE_FILES, ids=lambda p: p.name)
def test_the_database_port_is_never_published(compose: Path) -> None:
    """A published 5432 puts an unauthenticated database on the host."""

    services = _compose_services(_read(compose))
    assert "ports:" not in services["db"], (
        f"{compose.name} publishes the database port. It uses `expose`, which is "
        "network-internal only."
    )


def test_the_dev_database_port_is_bound_to_loopback() -> None:
    """database/docker-compose.yml is a convenience file and publishes 5432 on all
    interfaces with the password `postgres`."""

    text = _read(DB_COMPOSE)
    published = re.findall(r'^\s*-\s*"([^"]*:\d+:\d+)"', text, re.MULTILINE)
    for mapping in published:
        host_port = mapping.split(":")[0]
        assert host_port in {"127.0.0.1", "localhost"}, (
            f"database/docker-compose.yml publishes {mapping} on every interface with a "
            "default password. Bind it to loopback."
        )


# --- application --------------------------------------------------------------


def test_a_bad_host_header_is_refused() -> None:
    """WSTG 4.2.10 Test for Subdomain Takeover / Host header injection."""

    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import create_app
    from tests.fake_wikipedia import ADA, FakeWikipediaClient

    app = create_app()
    app.state.settings = Settings(database_url="")
    app.state.wikipedia = FakeWikipediaClient()

    with TestClient(app) as client:
        good = client.get("/api/health", headers={"Host": "localhost"})
        assert good.status_code == 200

        bad = client.get("/api/health", headers={"Host": "evil.example.com"})
        assert bad.status_code == 400, (
            "a request with an arbitrary Host header is accepted. TrustedHostMiddleware is "
            "either not installed or its allow-list is empty."
        )


def test_api_responses_are_compressed() -> None:
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import create_app
    from tests.fake_wikipedia import ADA, FakeWikipediaClient

    app = create_app()
    app.state.settings = Settings(database_url="")
    app.state.wikipedia = FakeWikipediaClient()

    with TestClient(app) as client:
        response = client.get(
            "/api/article/links",
            params={"title": ADA},
            headers={"Accept-Encoding": "gzip"},
        )

    assert response.status_code == 200
    assert response.headers.get("content-encoding") == "gzip", (
        "an analysis response goes out uncompressed. GZipMiddleware is not installed."
    )


_CONSTRAINT_WORDS = {
    "constraint",
    "primary",
    "foreign",
    "unique",
    "check",
    "exclude",
    "like",
}


def _model_columns() -> dict[str, set[str]]:
    """Table -> column names, read out of `models.py`.

    Assumes the mapped attribute name is the column name, which holds because no column
    here passes `name=` to `mapped_column`. That assumption is asserted below rather than
    taken on trust, because silently drifting from it would make every comparison in this
    section meaningless.
    """

    source = _read(BACKEND / "app" / "models.py")
    assert not re.search(r"mapped_column\([^)]*\bname\s*=", source), (
        "a column now passes name= to mapped_column, so the attribute name is no longer "
        "the column name. _model_columns has to be taught about it."
    )

    tables: dict[str, set[str]] = {}
    table: str | None = None
    for line in source.splitlines():
        found = re.search(r'__tablename__\s*=\s*"(\w+)"', line)
        if found:
            table = found.group(1)
            tables[table] = set()
            continue
        if table is None:
            continue
        # `= mapped_column(` is required, not just `Mapped[`: a relationship is also
        # annotated as Mapped[list["ArticleLink"]] and is not a column.
        column = re.search(r"^\s{4}(\w+):\s*Mapped\[.*?=\s*mapped_column", line)
        if column:
            tables[table].add(column.group(1))
    return tables


def _sql_columns() -> dict[str, set[str]]:
    """Table -> column names, read out of `init.sql`.

    Both shapes have to be read: the `CREATE TABLE IF NOT EXISTS` body, and the
    `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` block. Reading only the former is exactly
    the gap that let a column be added to the models and never reach an existing database.
    """

    text = _read(ROOT / "database" / "init.sql")
    tables: dict[str, set[str]] = {}

    for match in re.finditer(
        r"CREATE TABLE IF NOT EXISTS\s+(\w+)\s*\((.*?)\n\);", text, re.DOTALL
    ):
        name, body = match.group(1), match.group(2)
        columns: set[str] = set()
        for line in body.splitlines():
            token = line.strip().split()
            if not token:
                continue
            head = token[0].lower()
            if head in _CONSTRAINT_WORDS or head == "references":
                continue
            columns.add(token[0])
        tables.setdefault(name, set()).update(columns)

    for match in re.finditer(
        r"ALTER TABLE\s+(\w+)\s+ADD COLUMN IF NOT EXISTS\s+(\w+)", text, re.IGNORECASE
    ):
        tables.setdefault(match.group(1), set()).add(match.group(2))

    return tables


def test_every_model_column_reaches_init_sql() -> None:
    """The two-file invariant, at column granularity.

    `ci.yml` compares table *names* only, so a column added to `models.py` without a
    matching `init.sql` change passes CI silently - and then never reaches a deployed
    database, because `CREATE TABLE IF NOT EXISTS` is a no-op against an existing table.
    That is not hypothetical: `analysis_payload` is exactly that column.
    """

    models = _model_columns()
    sql = _sql_columns()

    assert models, "no tables parsed out of models.py - the parser is broken"
    assert set(models) == set(sql), (
        f"tables disagree: only in models.py {sorted(set(models) - set(sql))}, "
        f"only in init.sql {sorted(set(sql) - set(models))}"
    )

    drift: dict[str, list[str]] = {}
    for table, columns in models.items():
        missing = columns - sql.get(table, set())
        extra = sql.get(table, set()) - columns
        if missing or extra:
            drift[table] = [
                *(f"missing from init.sql: {c}" for c in sorted(missing)),
                *(f"only in init.sql: {c}" for c in sorted(extra)),
            ]

    assert not drift, (
        f"models.py and init.sql disagree about columns: {drift}. A column that is in the "
        "models but not the SQL will not be created on an existing database and the write "
        "that needs it will fail at runtime."
    )


def test_init_sql_has_a_way_to_add_a_column_to_an_existing_table() -> None:
    """Without an `ADD COLUMN IF NOT EXISTS` there is no working upgrade path.

    `create_all()` creates missing tables and never alters one, and `init.sql` runs on
    first volume creation only, so before this block existed a column added to the models
    could never reach a database that already had the table.
    """

    text = _read(ROOT / "database" / "init.sql")
    assert re.search(
        r"ALTER TABLE\s+(\w+)\s+ADD COLUMN IF NOT EXISTS\s+(\w+)", text, re.IGNORECASE
    ), (
        "init.sql has no ADD COLUMN IF NOT EXISTS, so there is no way to add a column to "
        "a table that already exists"
    )
    # And it must stay additive, because that is what makes rollback free.
    assert not re.search(r"^\s*(DROP|TRUNCATE)\b", text, re.MULTILINE | re.IGNORECASE), (
        "init.sql contains a DROP or TRUNCATE. docs/ROLLBACK.md section 1 depends on it "
        "only ever creating things."
    )


def test_a_render_error_is_caught_by_a_boundary_that_is_actually_mounted() -> None:
    """The boundary's own unit tests are not enough on their own.

    `ErrorBoundary.test.jsx` renders the component directly, so every one of its tests
    still passes if `main.jsx` stops mounting it - and a render error then blanks the page
    again with nothing to show for it. This checks the wiring, which is the part that has
    no test of its own.
    """

    entry = _read(FRONTEND / "src" / "main.jsx")
    stripped = _strip_comments(entry)

    assert "ErrorBoundary" in stripped, (
        "main.jsx does not mount an ErrorBoundary, so any render error blanks the page"
    )
    assert re.search(r"<ErrorBoundary>", stripped), "the boundary is imported but not used"
    # It has to wrap the tree, not sit beside it: as a sibling it would catch nothing.
    assert re.search(r"<ErrorBoundary>\s*<BrowserRouter>", stripped), (
        "the boundary does not wrap the router, so it cannot catch anything the routes throw"
    )
    # Nesting a second role="alert" would make a screen reader announce twice.
    assert stripped.count("role=") == 0 or "role=" not in stripped.split("<ErrorBoundary>")[0]


def test_no_credential_is_ever_baked_into_an_image_layer() -> None:

    for dockerfile, context in (
        (_read(BACKEND_DOCKERFILE), ".env"),
        (_read(FRONTEND_DOCKERFILE), ".env"),
    ):
        assert not re.search(rf"^\s*COPY\s+{re.escape(context)}\b", dockerfile, re.MULTILINE), (
            f"a Dockerfile copies {context} into the image. That is a credential in an "
            "image layer, readable by anyone who can pull it."
        )
        assert not re.search(r"^\s*ADD\s+https?://", dockerfile, re.MULTILINE), (
            "ADD with a URL fetches unpinned, unverified content into the image"
        )


def test_dependencies_are_pinned_so_a_build_is_reproducible() -> None:
    """`>=` means tomorrow's build can install tomorrow's packages.

    For a repository other people clone and build, that is a supply-chain hole: the lock
    that protects them is a range, not a version. npm already has package-lock.json; this
    is the Python equivalent.
    """

    requirements = _read(BACKEND / "requirements.txt")
    unpinned = [
        line.strip()
        for line in requirements.splitlines()
        if line.strip()
        and not line.strip().startswith("#")
        and not line.strip().startswith("-")
        and "==" not in line
    ]
    assert not unpinned, (
        f"these requirements are not pinned to an exact version: {unpinned}. A range lets "
        "a future build silently install different code than the one that was tested."
    )
