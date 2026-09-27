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


@lru_cache
def get_settings() -> Settings:
    return Settings()
