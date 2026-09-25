"""Ad-hoc smoke check against the real MediaWiki API. Not part of pytest."""

import asyncio

from app.config import Settings
from app.services.analysis import analyze_article
from app.services.mediawiki import MediaWikiClient

# Articles chosen because they are likely to contain "red links".
TARGETS = [
    "Bongaon",
    "List of cities in India",
    "Chandni Chowk, Delhi",
]


async def main() -> None:
    settings = Settings(
        classify_max_items=5, one_way_max_targets=3, max_links_per_article=200
    )
    async with MediaWikiClient(settings) as client:
        found = await client.search_articles("Ada Lovelace", limit=3)
        print("search:", [f"{r.title} (id={r.page_id})" for r in found])

        for title in TARGETS:
            result = await analyze_article(client, settings, title)
            print(f"\n=== {result.article.title} ===")
            print("summary:", result.summary.model_dump())
            print("missing:", [(m.title, m.entity_type) for m in result.missing_connections][:8])
            print("one-way:", [c.target_title for c in result.one_way_connections])

        resolved = await client.resolve_titles(
            ["Ada Lovelace", "Ada Lovelaces husband", "zzzqqx"]
        )
        print("\nresolve:", [r.model_dump() for r in resolved])


asyncio.run(main())
