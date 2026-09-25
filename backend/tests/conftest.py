from __future__ import annotations

import pytest

from app.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="",
        max_links_per_article=500,
        missing_check_batch_size=50,
        one_way_max_targets=25,
        classify_max_items=20,
        map_node_limit=40,
    )
