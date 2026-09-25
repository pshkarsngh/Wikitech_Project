"""Thin async wrapper around the MediaWiki (and Wikidata) action API.

Every call uses ``formatversion=2`` so responses are lists instead of
page-id keyed maps, and titles are passed as query parameters rather than
inside article titles to avoid path-encoding problems with slashes.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.config import Settings
from app.schemas import ArticleDetail, ResolvedTitle, SearchResultItem

logger = logging.getLogger(__name__)

MAIN_NAMESPACE = 0
_ARTICLE_PATH_PREFIX = "/wiki/"
_LINKS_PROP_LIMIT = "max"
_MAX_TITLES_PER_REQUEST = 50
_MAX_REDIRECTS = 1


class WikipediaError(RuntimeError):
    """Raised when the upstream MediaWiki API cannot be used."""


class ArticleNotFoundError(WikipediaError):
    """Raised when the requested article does not exist."""


def normalize_title(title: str) -> str:
    """MediaWiki title normalisation: underscores become spaces, edges trimmed."""

    return title.replace("_", " ").strip()


def title_key(title: str) -> str:
    """Comparison key for titles (MediaWiki is case-insensitive on first letter)."""

    return normalize_title(title).lower()


def chunked(items: Sequence[Any], size: int) -> Iterator[list[Any]]:
    size = max(1, size)
    for start in range(0, len(items), size):
        yield list(items[start : start + size])


def wiki_host(url: str | None) -> str:
    """The host a URL or MediaWiki endpoint belongs to, e.g. ``en.wikipedia.org``."""

    return urlsplit(url).netloc.lower() if url else ""


def is_internal_article_link(url: str | None, *, host: str) -> bool:
    """True when a link target is an article on the same wiki.

    A target with no URL is still internal: it is a red link, an article on
    this wiki that nobody has written yet. A target on another host is an
    external website, and a same-host path outside ``/wiki/`` is the wiki
    itself rather than an article. When the host is unknown the
    main-namespace request that produced the link is trusted.
    """

    if not url:
        return True
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return False
    if host and parts.netloc.lower() != host:
        return False
    return parts.path.startswith(_ARTICLE_PATH_PREFIX)


@dataclass
class ArticleLinks:
    page_id: int | None
    title: str
    url: str | None
    links: list[str]
    truncated: bool


class MediaWikiClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            timeout=settings.http_timeout_seconds,
            headers={"User-Agent": settings.user_agent},
            follow_redirects=True,
        )
        self._semaphore = asyncio.Semaphore(max(1, settings.max_concurrent_requests))
        self._owns_client = True

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> MediaWikiClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    # ------------------------------------------------------------------
    # transport
    # ------------------------------------------------------------------
    async def _api_get(
        self, params: dict[str, Any], *, endpoint: str | None = None
    ) -> dict[str, Any]:
        url = endpoint or self._settings.wiki_api_url
        query = {"format": "json", "formatversion": "2", "errorformat": "plaintext", **params}

        last_error: Exception | None = None
        for attempt in range(2):
            try:
                async with self._semaphore:
                    response = await self._client.get(url, params=query)
                if response.status_code == 404:
                    raise WikipediaError(f"{url} returned 404")
                if response.status_code == 429 or response.status_code >= 500:
                    raise WikipediaError(
                        f"{url} returned {response.status_code} (upstream busy)"
                    )
                response.raise_for_status()
                payload = response.json()
            except WikipediaError as exc:
                last_error = exc
            except (httpx.HTTPError, ValueError) as exc:
                last_error = WikipediaError(f"Request to {url} failed: {exc}")
            else:
                if isinstance(payload, dict) and "error" in payload:
                    raise WikipediaError(f"MediaWiki API error: {payload['error']}")
                return payload
            if attempt == 0:
                await asyncio.sleep(1.0)

        logger.warning("MediaWiki request failed after retries: %s", last_error)
        raise WikipediaError(str(last_error) or "Unknown MediaWiki failure")

    # ------------------------------------------------------------------
    # article retrieval
    # ------------------------------------------------------------------
    async def search_articles(
        self, query: str, limit: int = 10, *, in_title: bool = False
    ) -> list[SearchResultItem]:
        """Search article names.

        With ``in_title`` the query is matched against titles only, so a name
        that is not an exact page still resolves to an article *about* that name
        instead of to an unrelated article that merely mentions it.
        """

        data = await self._api_get(
            {
                "action": "query",
                "list": "search",
                "srsearch": f"intitle:{query}" if in_title else query,
                "srlimit": max(1, min(limit, 50)),
                "srnamespace": MAIN_NAMESPACE,
                "srprop": "wordcount",
            }
        )
        hits = (data.get("query") or {}).get("search") or []
        return [
            SearchResultItem(
                page_id=hit.get("pageid"),
                title=hit.get("title", ""),
                description=hit.get("snippet"),
                wordcount=hit.get("wordcount"),
            )
            for hit in hits
            if hit.get("title")
        ]

    async def get_article(self, title: str, *, include_extract: bool = True) -> ArticleDetail:
        props = ["info", "pageprops", "description"]
        if include_extract:
            props.append("extracts")

        data = await self._api_get(
            {
                "action": "query",
                "prop": "|".join(props),
                "titles": title,
                "redirects": 1,
                "converttitles": 1,
                "inprop": "url",
                "exintro": 1,
                "explaintext": 1,
                "exsectionformat": "plain",
            }
        )
        pages = (data.get("query") or {}).get("pages") or []
        if not pages:
            raise ArticleNotFoundError(f"No article found for '{title}'")

        page = pages[0]
        if page.get("missing"):
            raise ArticleNotFoundError(f"Article '{title}' does not exist on Wikipedia")

        return ArticleDetail(
            page_id=page.get("pageid"),
            title=page.get("title", title),
            url=page.get("fullurl"),
            description=page.get("description"),
            extract=page.get("extract"),
            length=page.get("length"),
            exists=True,
        )

    # ------------------------------------------------------------------
    # article search
    # ------------------------------------------------------------------
    async def find_article(self, query: str) -> ArticleDetail:
        """Resolve an article name to a single article, with its lead extract.

        An exact title wins, because it is unambiguous and cheap. A partial name
        falls back to a title-only search, so it can still miss, but it can never
        return an unrelated article that merely mentions the name. Raises
        :class:`ArticleNotFoundError` when neither finds a page.
        """

        name = normalize_title(query)
        if not name:
            raise ArticleNotFoundError("Enter an article name to search for")

        try:
            return await self.get_article(name)
        except ArticleNotFoundError:
            pass

        hits = await self.search_articles(name, limit=1, in_title=True)
        if not hits:
            raise ArticleNotFoundError(f"No article found for '{name}'")

        return await self.get_article(hits[0].title)

    # ------------------------------------------------------------------
    # link extraction
    # ------------------------------------------------------------------
    async def get_article_links(
        self, title: str, *, max_links: int | None = None
    ) -> ArticleLinks:
        """Collect the outgoing article links of an article.

        Only links inside the main (article) namespace are returned, and
        external links are never requested, so images, media, files,
        categories, templates, help and the rest of the project namespaces are
        all left out. What comes back is a list of article targets, in the
        order they appear in the article. ``truncated`` is set when the article
        had more links than ``max_links``.
        """

        limit = max_links if max_links is not None else self._settings.max_links_per_article
        params: dict[str, Any] = {
            "action": "query",
            "prop": "links|info",
            "inprop": "url",
            "titles": title,
            "plnamespace": MAIN_NAMESPACE,
            "pllimit": _LINKS_PROP_LIMIT,
            "redirects": 1,
            "converttitles": 1,
        }

        links: list[str] = []
        seen: set[str] = set()
        page_id: int | None = None
        url: str | None = None
        resolved_title = normalize_title(title)
        truncated = False

        while True:
            data = await self._api_get(params)
            query = data.get("query") or {}
            pages = query.get("pages") or []

            for page in pages:
                if page.get("missing"):
                    continue
                if page_id is None and page.get("pageid"):
                    page_id = page["pageid"]
                if page.get("title"):
                    resolved_title = page["title"]
                if url is None and page.get("fullurl"):
                    url = page["fullurl"]
                for link in page.get("links") or []:
                    # The request already asks for the main namespace only.
                    # Re-checking the namespace reported on each link is what
                    # actually guarantees that images, media, files,
                    # categories, templates and other project pages are
                    # dropped, whatever the API decides to send back.
                    namespace = link.get("ns")
                    if namespace is not None and namespace != MAIN_NAMESPACE:
                        continue
                    link_title = link.get("title")
                    if not link_title:
                        continue
                    key = title_key(link_title)
                    if key in seen:
                        continue
                    seen.add(key)
                    links.append(link_title)
                    if len(links) >= limit:
                        break
                if len(links) >= limit:
                    break

            continuation = data.get("continue")
            if not continuation:
                break
            if len(links) >= limit:
                truncated = True
                break
            params = {**params, **continuation}

        return ArticleLinks(
            page_id=page_id,
            title=resolved_title,
            url=url,
            links=links[:limit],
            truncated=truncated,
        )

    # ------------------------------------------------------------------
    # article existence checking
    # ------------------------------------------------------------------
    async def resolve_titles(self, titles: Iterable[str]) -> list[ResolvedTitle]:
        """Batch-resolve titles, reporting whether each one has its own article.

        A redirect counts as existing: the target page is reachable, it simply
        lives under a different name, and the resolved title is the redirect
        target. A title MediaWiki refuses to treat as a page at all is
        reported as missing rather than existing.

        Upstream failures are not swallowed. A batch that cannot be resolved
        raises, so a partial answer is never mistaken for a complete one.
        """

        wanted = list(dict.fromkeys(t for t in (normalize_title(x) for x in titles) if t))
        resolved: dict[str, ResolvedTitle] = {}

        for batch in chunked(wanted, _MAX_TITLES_PER_REQUEST):
            data = await self._api_get(
                {
                    "action": "query",
                    "prop": "info",
                    "inprop": "url",
                    "titles": "|".join(batch),
                    "redirects": _MAX_REDIRECTS,
                    "converttitles": 1,
                }
            )
            query = data.get("query") or {}

            by_final_title: dict[str, dict[str, Any]] = {}
            for page in query.get("pages") or []:
                final_title = page.get("title")
                if final_title:
                    by_final_title[final_title] = page

            # Follow "requested" -> "normalised" -> "redirect target", keeping
            # track of which chains actually used a redirect, since a mere
            # normalisation (case or underscores) is not a redirect.
            mapping = {title: title for title in batch}
            redirected: set[str] = set()
            for kind, entries in (
                ("normalised", query.get("normalized") or []),
                ("redirect", query.get("redirects") or []),
            ):
                for entry in entries:
                    source, target = entry.get("from"), entry.get("to")
                    if not source or not target:
                        continue
                    for original, current in list(mapping.items()):
                        if current == source:
                            mapping[original] = target
                            if kind == "redirect":
                                redirected.add(original)

            for requested, final_title in mapping.items():
                page = by_final_title.get(final_title)
                # No page at all, "missing", or "invalid" all mean there is no
                # article. MediaWiki uses "invalid" for titles that are not
                # valid page titles at all, and it carries no "missing" key,
                # so it has to be checked explicitly or it reads as existing.
                exists = (
                    bool(page)
                    and not page.get("missing")
                    and not page.get("invalid")
                )
                resolved[requested] = ResolvedTitle(
                    requested=requested,
                    title=final_title if page else None,
                    page_id=page.get("pageid") if page else None,
                    url=page.get("fullurl") if page else None,
                    exists=exists,
                    redirected=requested in redirected,
                )

        return [resolved[title] for title in wanted if title in resolved]

    async def get_links_for_page_ids(
        self, page_ids: Iterable[int], *, max_links_per_page: int = 500
    ) -> dict[int, set[str]]:
        """Outgoing main-namespace link titles for many pages, keyed by page id.

        Titles are returned as comparison keys (see :func:`title_key`).
        """

        ids = [int(page_id) for page_id in page_ids if page_id]
        if not ids:
            return {}

        result: dict[int, set[str]] = {}
        for batch in chunked(ids, _MAX_TITLES_PER_REQUEST):
            data = await self._api_get(
                {
                    "action": "query",
                    "prop": "links",
                    "plnamespace": MAIN_NAMESPACE,
                    "pllimit": _LINKS_PROP_LIMIT,
                    "pageids": "|".join(str(page_id) for page_id in batch),
                    "redirects": _MAX_REDIRECTS,
                }
            )
            for page in (data.get("query") or {}).get("pages") or []:
                page_id = page.get("pageid")
                if not page_id:
                    continue
                result[int(page_id)] = {
                    title_key(link["title"])
                    for link in page.get("links") or []
                    if link.get("title")
                }
        return result

    # ------------------------------------------------------------------
    # Wikidata (used only for the person / place guess)
    # ------------------------------------------------------------------
    async def wikidata_descriptions(self, term: str) -> str | None:
        data = await self._api_get(
            {
                "action": "wbsearchentities",
                "search": term,
                "language": "en",
                "uselang": "en",
                "type": "item",
                "limit": 1,
            },
            endpoint=self._settings.wikidata_api_url,
        )
        hits = data.get("search") or []
        if not hits:
            return None
        description = hits[0].get("description")
        return description.strip() if isinstance(description, str) else None
