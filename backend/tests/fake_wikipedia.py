"""A fake MediaWiki client so the analysis can be tested without network calls.

The fixture wiki:

    Ada Lovelace (1)
      -> Analytical Engine (2)  exists, links back to Ada Lovelace   => mutual
      -> London (3)            exists, does not link back            => one-way
      -> Byron's Daughter      missing, Wikidata says "novel"        => other
      -> Somerton, Malta       missing, Wikidata says "village"      => place
"""

from __future__ import annotations

from app.schemas import ArticleDetail, ResolvedTitle, SearchResultItem
from app.services.mediawiki import (
    ArticleLinks,
    ArticleNotFoundError,
    normalize_title,
    title_key,
)

ADA = "Ada Lovelace"
ENGINE = "Analytical Engine"
LONDON = "London"
NOVEL = "Byron's Daughter"
VILLAGE = "Somerton, Malta"

PAGES: dict[str, int] = {
    ADA: 1,
    ENGINE: 2,
    LONDON: 3,
}

ADA_LINKS: list[str] = [ENGINE, LONDON, NOVEL, VILLAGE]

OUTGOING: dict[int, list[str]] = {
    1: ADA_LINKS,
    2: [ADA, "Difference engine"],
    3: ["United Kingdom", "Thames"],
}

WIKIDATA_DESCRIPTIONS: dict[str, str | None] = {
    ENGINE: "mechanical general-purpose computer designed by Charles Babbage",
    LONDON: "capital and largest city of England and the United Kingdom",
    NOVEL: None,
    VILLAGE: "village in Malta",
    ADA: "English mathematician and writer",
}


class FakeWikipediaClient:
    """Mirrors the parts of MediaWikiClient the services rely on."""

    def __init__(self) -> None:
        self.link_calls: list[str] = []
        self.resolve_calls: list[list[str]] = []
        self.reverse_calls: list[list[int]] = []

    async def search_articles(
        self, query: str, limit: int = 10, *, in_title: bool = False
    ) -> list[SearchResultItem]:
        needle = query.lower()
        hits = [
            SearchResultItem(
                page_id=page_id,
                title=title,
                description=WIKIDATA_DESCRIPTIONS.get(title),
            )
            for title, page_id in PAGES.items()
            if needle in title.lower()
        ]
        return hits[:limit]

    async def get_article(self, title: str, *, include_extract: bool = True) -> ArticleDetail:
        key = title_key(title)
        for name, page_id in PAGES.items():
            if title_key(name) == key:
                return ArticleDetail(
                    page_id=page_id,
                    title=name,
                    url=f"https://en.wikipedia.org/wiki/{name.replace(' ', '_')}",
                    description=WIKIDATA_DESCRIPTIONS.get(name),
                    extract=f"{name} is a test article.",
                    length=1024,
                )
        raise ArticleNotFoundError(f"Article '{title}' does not exist on Wikipedia")

    async def find_article(self, query: str) -> ArticleDetail:
        hits = await self.search_articles(query, limit=1)
        if not hits:
            raise ArticleNotFoundError(f"No article found for '{query}'")
        return await self.get_article(hits[0].title)

    async def get_article_links(
        self, title: str, *, max_links: int | None = None
    ) -> ArticleLinks:
        self.link_calls.append(title)
        key = title_key(title)
        if key != title_key(ADA) and key not in {title_key(n) for n in PAGES}:
            raise ArticleNotFoundError(
                f"Article '{title}' does not exist on Wikipedia"
            )
        links = ADA_LINKS if key == title_key(ADA) else OUTGOING.get(PAGES.get(title, 0) or 0, [])
        if max_links is not None:
            links = links[:max_links]
        return ArticleLinks(
            page_id=PAGES.get(title),
            title=normalize_title(title),
            url=f"https://en.wikipedia.org/wiki/{normalize_title(title).replace(' ', '_')}",
            links=links,
            truncated=bool(max_links is not None and len(ADA_LINKS) > max_links),
        )

    async def resolve_titles(self, titles) -> list[ResolvedTitle]:
        requested = [normalize_title(title) for title in titles]
        self.resolve_calls.append(requested)
        return [
            ResolvedTitle(
                requested=title,
                title=title if title in PAGES else None,
                page_id=PAGES.get(title),
                url=(
                    f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
                    if title in PAGES
                    else None
                ),
                exists=title in PAGES,
            )
            for title in requested
        ]

    async def get_links_for_page_ids(self, page_ids, *, max_links_per_page: int = 500):
        ids = [int(page_id) for page_id in page_ids if page_id]
        self.reverse_calls.append(ids)
        return {page_id: {title_key(t) for t in OUTGOING.get(page_id, [])} for page_id in ids}

    async def get_page_descriptions(self, page_ids) -> dict[int, str]:
        # An article's own short description is what identifies it as a person or
        # a place, and it comes back a batch at a time.
        titles = {page_id: title for title, page_id in PAGES.items()}
        descriptions: dict[int, str] = {}
        for page_id in page_ids:
            if not page_id:
                continue
            description = WIKIDATA_DESCRIPTIONS.get(titles.get(int(page_id), ""))
            if description:
                descriptions[int(page_id)] = description
        return descriptions

    async def wikidata_descriptions(self, term: str) -> str | None:
        return WIKIDATA_DESCRIPTIONS.get(term)

    async def aclose(self) -> None:
        return None
