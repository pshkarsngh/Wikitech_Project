"""Guards the split deployment: Vercel for the SPA, Render for the API and Postgres.

The compose stacks in ``deploy/`` put nginx in front of the API, and that one component
is carrying four separate responsibilities. Take nginx away - which is what deploying the
two halves to different providers does - and each one has to be re-established somewhere
else, or silently does not exist:

* **Same-origin ``/api``.** ``frontend/src/api/client.js`` defaults to a relative ``/api``.
  Across two origins that resolves to the Vercel host, which serves no API, so the SPA
  needs a build-time ``VITE_API_BASE_URL`` and the backend needs CORS.
* **The Host allow-list.** ``TrustedHostMiddleware`` answers 400 for a Host it does not
  recognise, and the defaults in ``app/config.py`` are container names.
* **The security headers.** They live in ``frontend/nginx-security-headers.conf`` and go
  with nginx. A static host serves the same bytes with none of them.
* **The rate limits.** ``limit_req zone=analyze`` at 6r/m exists to bound this
  deployment's spend against Wikimedia's 200 req/min. Nothing on Render enforces it.

None of these failures is loud. A missing Host entry is a 400 on every route; a
``connect-src`` that omits the API is a browser console message; a missing rate limit is
a bill. The assertions are on the source text of the configuration, which is the same
weaker guarantee ``test_deployment_contract.py`` makes and for the same reason: it proves
the rule is still written down, not that a platform honoured it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

# `pytest.ini` sets `pythonpath = .` and the suite runs from `backend/`.
ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
BACKEND = ROOT / "backend"
NGINX_HEADERS = FRONTEND / "nginx-security-headers.conf"
BACKEND_DOCKERFILE = BACKEND / "Dockerfile"
VERCEL_JSON = FRONTEND / "vercel.json"
RENDER_YAML = ROOT / "render.yaml"

# Cloudflare's documented proxy read timeout. Render routes all inbound traffic through
# Cloudflare but publishes no request-duration ceiling of its own, so this is the number
# the deadline has to stay under for the `aborted` marker to have any chance of reaching
# the browser. If it turns out Render's own limit is lower, this constant is wrong and
# the test below is the place that says so.
CLOUDFLARE_READ_TIMEOUT_SECONDS = 100


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _strip_comments(text: str) -> str:
    """Config with comment lines removed.

    Prose in these files legitimately contains the words the assertions look for - the
    comment explaining why PORT is pinned mentions the port, and the one explaining the
    CORS origin mentions a hostname. Matching commented text is how a check passes for
    the wrong reason.
    """

    return "\n".join(line for line in text.splitlines() if not line.strip().startswith("#"))


@pytest.fixture(scope="module")
def render() -> str:
    return _read(RENDER_YAML)


@pytest.fixture(scope="module")
def vercel() -> dict:
    return json.loads(_read(VERCEL_JSON))


def _service_name(render: str) -> str:
    """The `name:` of the first entry under `services:`.

    Scoped to that block because the `databases:` section has a `name:` too, and taking
    the first match in the file would return whichever happened to be written first.
    """

    body = render[render.index("services:") :]
    match = re.search(r"^\s*name:\s*(\S+)", body, re.MULTILINE)
    assert match, "render.yaml has no service name, so its hostname cannot be derived"
    return match.group(1)


def _image_port() -> int:
    """The port the backend image's CMD binds.

    Read from the command rather than from `EXPOSE`, because `EXPOSE` is documentation
    and the CMD is what uvicorn actually listens on. They can disagree, and the CMD is
    the one that has to match $PORT.
    """

    match = re.search(r"""--port['"]?\s*,\s*['"]?(\d+)""", _read(BACKEND_DOCKERFILE))
    assert match, (
        "could not read --port out of the backend Dockerfile's CMD. If this fails while "
        "test_deployment_contract.py's forwarded-headers test passes, this parser is the "
        "broken one and the command has been reformatted."
    )
    return int(match.group(1))


def _nginx_csp() -> str:
    match = re.search(
        r'add_header\s+Content-Security-Policy\s+"([^"]+)"',
        _read(NGINX_HEADERS),
    )
    assert match, "nginx-security-headers.conf sets no Content-Security-Policy"
    return match.group(1)


def _vercel_header(vercel: dict, name: str) -> str:
    for rule in vercel["headers"]:
        for header in rule["headers"]:
            if header["key"] == name:
                return header["value"]
    raise AssertionError(f"vercel.json sets no {name}")


def _connect_src(policy: str) -> str:
    match = re.search(r"connect-src ([^;]+)", policy)
    assert match, f"no connect-src in {policy!r}"
    return match.group(1).strip()


def _env_vars(render: str) -> dict[str, str]:
    """`envVars` entries as key -> value, for the `value:` form only.

    `sync: false` and `fromDatabase:` entries are resolved by Render at deploy time and
    have no value to read here; they are asserted separately, because the reason they are
    in that form is the point.
    """

    body = render[render.index("envVars:") :]
    found: dict[str, str] = {}
    for match in re.finditer(
        r"-\s*key:\s*(\S+)\s*\n\s*value:\s*(.+)", body, re.MULTILINE
    ):
        found[match.group(1)] = match.group(2).strip().strip("'\"")
    return found


# --- database URL ---------------------------------------------------------------
# Render's Blueprint cannot rewrite a URL scheme, and `create_engine` is called from the
# app's lifespan, so a driverless URL does not degrade the cache - it stops the process
# booting, with the reason buried in an environment variable.


def test_a_driverless_database_url_is_pinned_to_psycopg() -> None:
    from app.db import _normalised_url

    assert _normalised_url("postgresql://u:p@host:5432/db") == "postgresql+psycopg://u:p@host:5432/db"
    assert _normalised_url("postgres://u:p@host:5432/db") == "postgresql+psycopg://u:p@host:5432/db"


def test_an_explicit_driver_is_left_alone() -> None:
    """Otherwise this would rewrite the compose and CI URLs onto a driver twice."""

    from app.db import _normalised_url

    for url in (
        "postgresql+psycopg://u:p@host:5432/db",
        "postgresql+asyncpg://u:p@host:5432/db",
    ):
        assert _normalised_url(url) == url


def test_a_query_string_survives_the_scheme_rewrite() -> None:
    """Render's *external* URL ends in `?sslmode=require`, and that is the fallback
    documented in render.yaml. Dropping it would fail the connection, not just the
    certificate check.
    """

    from app.db import _normalised_url

    url = "postgresql://u:p@host:5432/db?sslmode=require"
    assert _normalised_url(url) == "postgresql+psycopg://u:p@host:5432/db?sslmode=require"


def test_the_render_service_reads_its_database_url_from_the_database(render: str) -> None:
    """Not a literal. The password is generated by Render and has no committed value."""

    body = render[render.index("- key: DATABASE_URL") :]
    assert "fromDatabase:" in body, "DATABASE_URL is not wired to the database below it"
    assert "internalConnectionString" in body, (
        "DATABASE_URL uses the external connection string, which publishes the database "
        "port to the internet and adds a TLS hop. The internal one resolves only on "
        "Render's private network."
    )


# --- the port -------------------------------------------------------------------
# A container that is healthy and unreachable looks exactly like a slow one.


def test_the_render_service_binds_the_port_the_image_listens_on(render: str) -> None:
    listen = _image_port()

    env = _env_vars(render)
    assert "PORT" in env, (
        "PORT is not set. Render forwards to $PORT (default 10000) while the image binds "
        f"{listen}, so every request would be refused while the container looked healthy."
    )
    assert int(env["PORT"]) == listen, (
        f"PORT is {env['PORT']} but the image listens on {listen}."
    )


# --- Host header -----------------------------------------------------------------


def test_the_render_service_names_its_own_host_in_the_allow_list(render: str) -> None:
    """Render derives the hostname from the service name, so this is predictable.

    Missing it means `TrustedHostMiddleware` answers 400 to every route, including the
    health check Render polls - which reads as a service that will not start rather than
    as a configuration mistake.
    """

    name = _service_name(render)

    hosts = json.loads(_env_vars(render)["ALLOWED_HOSTS"])
    assert f"{name}.onrender.com" in hosts, (
        f"ALLOWED_HOSTS is {hosts}, which does not contain the Render hostname for a "
        f"service named {name}. Every request would be refused with 400."
    )


# --- CORS -----------------------------------------------------------------------
# For the first time, the browser and the API are on different origins.


def test_the_api_allows_the_vercel_origin(render: str) -> None:
    origins = json.loads(_env_vars(render)["CORS_ORIGINS"])
    assert origins, "CORS_ORIGINS is empty, so the browser cannot call the API at all"
    assert not any("localhost" in origin for origin in origins), (
        f"CORS_ORIGINS is still the development default: {origins}"
    )
    assert all(origin.startswith("https://") for origin in origins), (
        f"CORS_ORIGINS lists a non-HTTPS origin: {origins}. The SPA is served over TLS, so "
        "a browser will refuse the mixed content before CORS is ever consulted."
    )


def test_the_cors_allow_list_is_not_a_wildcard(render: str) -> None:
    """`*` would make the shared key the only control between a stranger and this
    deployment's Wikimedia budget, which is precisely what nginx's rate limits existed
    to bound. See the module docstring.
    """

    assert "*" not in _env_vars(render)["CORS_ORIGINS"]


# --- the security headers -------------------------------------------------------
# They are the one thing nginx was doing that a static host does not do for free.


def test_the_platform_serving_the_spa_sets_the_policy(vercel: dict) -> None:
    """nginx is not in the request path on Vercel, so this is the only copy the browser
    will see. Dropping it is a silent loss of a control that reads as present in the
    repository.
    """

    assert _vercel_header(vercel, "Content-Security-Policy").strip()


def test_the_policy_keeps_the_directives_that_stop_whole_classes_of_attack(vercel: dict) -> None:
    policy = _vercel_header(vercel, "Content-Security-Policy")
    for directive in (
        "default-src",
        "script-src",
        "object-src",
        "base-uri",
        "frame-ancestors",
    ):
        assert f"{directive} " in policy, f"the Vercel CSP is missing {directive}"

    assert "frame-ancestors 'none'" in policy
    assert "object-src 'none'" in policy
    script_src = re.search(r"script-src ([^;]+)", policy)
    assert script_src, "no script-src in the Vercel policy"
    assert "'unsafe-inline'" not in script_src.group(1)
    assert "'unsafe-eval'" not in script_src.group(1)


def test_the_policy_carries_every_security_header_nginx_set(vercel: dict) -> None:
    """nginx set seven of these. Moving to a static host does not relax them; it just
    stops them being sent, and nothing in the repository would say so.
    """

    for header in (
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Permissions-Policy",
    ):
        assert _vercel_header(vercel, header).strip(), f"vercel.json sets no {header}"


def test_the_policy_permits_the_api_the_spa_actually_calls(vercel: dict, render: str) -> None:
    """The one directive that cannot be copied across.

    The compose policy is `connect-src 'self'`, and it is complete there because nginx
    serves the API from the same origin. Reused verbatim on Vercel it would block every
    fetch to Render - a CSP violation in the console, with the SPA looking merely broken.
    """

    connect = _connect_src(_vercel_header(vercel, "Content-Security-Policy"))

    for host in json.loads(_env_vars(render)["ALLOWED_HOSTS"]):
        if host == "localhost":
            continue
        assert host in connect, (
            f"connect-src is {connect!r}, which does not permit {host!r} - the API origin "
            "the SPA is built against. Every request would be blocked by the browser "
            "before it reached the network."
        )


def test_the_policy_does_not_open_connect_src_up(vercel: dict) -> None:
    connect = _connect_src(_vercel_header(vercel, "Content-Security-Policy"))
    assert "*" not in connect, (
        "connect-src contains a wildcard. This is the one place a policy that looks "
        "restrictive can stop being one, and it guards the API rather than the document."
    )


def test_the_nginx_policy_is_unchanged_by_any_of_this() -> None:
    """Two deployments, two policies, and they are not interchangeable.

    The nginx copy has to stay `'self'`, because in that topology `'self'` is the whole
    of what the SPA talks to. Widening it "for consistency" with the Vercel copy would
    weaken the one that does not need it.
    """

    assert _connect_src(_nginx_csp()) == "'self'", (
        "the nginx policy's connect-src is no longer 'self'. It is 'self' because the SPA "
        "and the API share an origin there; anything else widens it for no reason."
    )


# --- deep links -----------------------------------------------------------------
# CI proves this works for nginx (`curl /connection-map`). On Vercel there is no
# `try_files`, so a deep link 404s and react-router never gets to route.


def test_deep_links_are_rewritten_to_the_spa(vercel: dict) -> None:
    assert vercel["rewrites"], "no rewrites, so any client-side route is a 404"

    sources = [rule["source"] for rule in vercel["rewrites"]]
    assert any(
        rule["destination"] == "/index.html" for rule in vercel["rewrites"]
    ), "nothing is rewritten to index.html"


def test_the_rewrite_does_not_swallow_the_hashed_assets(vercel: dict) -> None:
    """A catch-all rewrite to index.html that also matched /assets would serve HTML in
    place of a JavaScript bundle. The exclusion has to be a negative lookahead in the
    source, so this reads the pattern rather than trusting that someone remembered.
    """

    for rule in vercel["rewrites"]:
        if rule["destination"] == "/index.html":
            assert "(?!" in rule["source"], (
                f"the rewrite {rule['source']!r} has no exclusion, so it would also match "
                "the hashed bundles under /assets and serve index.html in their place."
            )


# --- secrets and the deadline ---------------------------------------------------


def test_the_shared_key_is_not_committed(render: str) -> None:
    body = render[render.index("- key: ANALYSIS_API_KEY") :]
    entry = body[: body.index("- key:", 1)] if body.count("- key:") > 1 else body
    assert "sync: false" in entry, (
        "ANALYSIS_API_KEY has a literal value. It is a shared secret and a committed one "
        "stays in git history after it is rotated."
    )


def test_the_deadline_leaves_room_under_a_possible_intermediary(render: str) -> None:
    """Render's own ceiling is undocumented, so this asserts against the one that is.

    The failure being guarded is the same one AGENTS.md section 5 describes for nginx: if
    the backend's deadline reaches the transport's read timeout, the connection closes as
    the response is written and the reader gets a bare 502 with no `aborted` marker. The
    marker is the entire reason a deadline may answer 200 with an incomplete result, so
    losing the race loses the feature.
    """

    deadline = int(float(_env_vars(render)["ANALYSIS_DEADLINE_SECONDS"]))
    assert deadline < CLOUDFLARE_READ_TIMEOUT_SECONDS, (
        f"the Render deadline is {deadline}s and Cloudflare gives up at "
        f"{CLOUDFLARE_READ_TIMEOUT_SECONDS}s. The partial result would never be delivered."
    )
    # Still holds for the compose path, whose documented ceiling is 120s.
    assert deadline < 120


def test_the_service_and_the_database_share_a_region(render: str) -> None:
    """Render resolves an internal hostname only between resources in one region, so a
    mismatch produces a name that does not resolve - and an app that boots without
    persistence, having logged nothing about it.
    """

    regions = re.findall(r"^\s*region:\s*(\S+)", _strip_comments(render), re.MULTILINE)
    assert len(regions) >= 2, (
        f"expected a region on both the service and the database, found {regions}"
    )
    assert len(set(regions)) == 1, (
        f"the service and the database are in different regions ({regions}). The internal "
        "connection string will not resolve."
    )
