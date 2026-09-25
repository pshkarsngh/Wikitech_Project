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
    max_concurrent_requests: int = 4

    max_links_per_article: int = 500
    missing_check_batch_size: int = 50
    one_way_max_targets: int = 25
    classify_max_items: int = 20
    map_node_limit: int = 40

    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    @property
    def database_enabled(self) -> bool:
        return bool(self.database_url.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
