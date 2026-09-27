from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Find the Missing Connections"
    version: str = "0.1.0"
    api_prefix: str = "/api"

    wiki_api_url: str = "https://en.wikipedia.org/w/api.php"
    wikidata_api_url: str = "https://www.wikidata.org/w/api.php"
    user_agent: str = (
        "FindTheMissingConnections/0.1 "
        "(https://github.com/pshkarsngh/Wikitech_Project)"
    )

    database_url: str = ""
    database_echo: bool = False

    http_timeout_seconds: float = 20.0
    # Wikimedia asks API clients to keep concurrent requests at three or fewer. This is a
    # published limit on how often this deployment may call them, not a tuning knob, so
    # raising it needs a reason from their documentation and not from a benchmark.
    # https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits
    max_concurrent_requests: int = 3

    max_links_per_article: int = 500
    missing_check_batch_size: int = 50
    one_way_max_targets: int = 25
    classify_max_items: int = 20
    map_node_limit: int = 40

    # How long one analysis may run before it stops asking for more, in seconds.
    # None of the per-request caps above bound wall-clock: a 20s HTTP timeout, a
    # concurrency limit of three and a 500-link article still add up to minutes,
    # and a client that navigates away does not stop them.
    #
    # It must stay below `proxy_read_timeout` in frontend/nginx-proxy-api.conf.
    # A backend deadline at or above the proxy's own read timeout buys nothing:
    # nginx has already closed the connection and the client sees a bare 502
    # with no body, so the partial result and its `aborted` marker never arrive.
    # The backend has to finish and answer first. 100s against a 120s ceiling
    # leaves room for serialising the response and the slowest single request.
    analysis_deadline_seconds: float = 100.0

    # How long an analysis run is kept before it is pruned. `analysis_runs` grows with
    # request volume and nothing else, so it is the one table in this schema that no
    # natural bound applies to: `articles` and `article_links` are capped by the size of
    # Wikipedia, this is not. The prune rides along on the write it follows, amortised
    # over many runs, so it costs no extra round trip on its own.
    analysis_run_retention_days: int = 30

    # One prune per this many stored runs. At the ceiling of ~6-8 analyses a minute
    # (docs/ARCHITECTURE.md section 12) a prune every 100 runs is a few times an hour,
    # so the table never holds much more than a day or two beyond the cutoff.
    analysis_run_prune_every: int = 100

    # How long a stored analysis is served before it is recomputed. This is the freshness
    # policy for the read path and it is a real decision, not a default to be inherited:
    # a red link is a fact about Wikipedia that can change at any moment, so a cache with
    # no expiry is a cache that is eventually wrong and never says so. One hour is short
    # enough that a link created this morning shows up this morning, and long enough that
    # a burst of traffic is served from the database rather than from Wikipedia.
    # Set to 0 to disable the read path entirely and always recompute.
    analysis_cache_ttl_seconds: int = 3600

    # Shared key required by the routes that crawl Wikipedia. Empty means no key, which is
    # the default and not a misconfiguration: the app boots and answers, exactly as it
    # does with an empty `database_url`. A deployment that wants to stop anonymous traffic
    # from spending its Wikimedia budget sets this to any non-empty string, and the
    # expensive routes then refuse everything without a matching `X-Api-Key` header.
    #
    # This is deliberately a single shared secret and not a user account. There is one
    # subject, so there is nothing to attribute, and a per-user model would need a users
    # table, a login surface and a schema change to answer a question this deployment
    # does not yet have. It is a speed bump against drive-by traffic: rotating the string
    # cuts off whoever was using the leaked one. See docs/ARCHITECTURE.md section 10.1.
    analysis_api_key: str = ""

    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Host header allow-list. Every Host the backend legitimately answers to: the container
    # name on the compose network, loopback for a direct hit, and localhost for a hit that
    # came through a local nginx. A request with any other Host is refused with a 400,
    # which closes Host-header poisoning - a Host of `evil.example` reaching a backend that
    # builds absolute URLs or a redirect would put this deployment's name in them.
    # An empty list disables the check, which is the documented way to turn it off if this
    # app is ever fronted by something that rewrites Host in a way not listed here.
    allowed_hosts: list[str] = [
        "localhost",
        "127.0.0.1",
        "api",
        "testserver",
        "web",
    ]

    @property
    def database_enabled(self) -> bool:
        return bool(self.database_url.strip())

    @property
    def analysis_key_enabled(self) -> bool:
        # `.strip()` for the same reason as `database_enabled`: a key of spaces is not a
        # key, and treating it as one would gate the API behind something no caller can
        # type.
        return bool(self.analysis_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
