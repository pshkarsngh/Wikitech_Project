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
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.config import Settings
from app.schemas import ArticleDetail, ResolvedTitle, SearchResultItem
from app.services.budget import (
    DEADLINE,
    AnalysisAborted,
    check_budget,
    current_budget,
    request_timeout,
)

logger = logging.getLogger(__name__)

MAIN_NAMESPACE = 0
_ARTICLE_PATH_PREFIX = "/wiki/"
_LINKS_PROP_LIMIT = "max"
_MAX_TITLES_PER_REQUEST = 50
_MAX_REDIRECTS = 1
# Wikimedia asks API clients to cap concurrent requests at three or fewer, and to send
# `maxlag` so a request is refused rather than queued when the servers are loaded. Both
# are documented at https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits and
# https://www.mediawiki.org/wiki/API:Etiquette. The limits are external and were new in
# 2026; treat them as a policy, not a tunable.
_MAX_LAG_SECONDS = 5
_RETRY_BACKOFF_SECONDS = 1.0


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


def _retry_delay(response: Any, *, default: float) -> float:
    """Seconds to wait before retrying, from the response's ``Retry-After`` header.

    Wikimedia asks API clients to respect ``Retry-After`` on a 429 rather than retrying on
    their own schedule. The header is either a delay in seconds or an HTTP date, so the
    date form is parsed rather than assumed away; anything unparseable falls back to
    ``default`` instead of failing the request over a header.
    """

    raw = response.headers.get("retry-after") if response.headers else None
    if not raw:
        return default
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        pass
    try:
        when = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return default
    if when is None:
        return default
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())


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


@dataclass
class PageLinks:
    """One page's outgoing links, and whether the whole set was seen.

    ``complete`` is the point of this type. MediaWiki caps a property query at 500 results
    for a client without the ``apihighlimits`` right, so a page with more links than that
    has a tail this request cannot reach. Reporting the links without saying so is how a
    one-way check ends up accusing an article of not linking back when it does, so a
    truncated answer has to travel with the answer.
    """

    titles: set[str]
    complete: bool


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
        query = {
            "format": "json",
            "formatversion": "2",
            "errorformat": "plaintext",
            # Refuse the request instead of queueing it when replication lag is high,
            # so a busy Wikipedia produces a clean error rather than a slow success.
            "maxlag": _MAX_LAG_SECONDS,
            **params,
        }

        # The one place every Wikimedia request passes through, which is why the
        # budget is checked here and not in each caller. Checked before the
        # request so a blown deadline does not spend one more call, and again
        # after it so a caller does not treat a response that arrived too late as
        # a completed stage.
        await check_budget()

        last_error: Exception | None = None
        for attempt in range(2):
            retry_after: float | None = None
            try:
                # The semaphore is acquired inside the budget's own timeout, so
                # time spent queueing behind the concurrency limit counts against
                # the deadline rather than being free. With `max_concurrent_requests`
                # at 3 and 25+ calls to make, waiting is the normal case and not a
                # pathological one.
                async with asyncio.timeout(
                    request_timeout(self._settings.http_timeout_seconds)
                ):
                    async with self._semaphore:
                        response = await self._client.get(url, params=query)
                if response.status_code == 404:
                    raise WikipediaError(f"{url} returned 404")
                if response.status_code == 429 or response.status_code >= 500:
                    # Wikimedia asks clients to honour Retry-After on a 429. Sleeping a
                    # fixed second re-enters the same limiter and is nearly guaranteed to
                    # be refused again, which is how a rate limit turns into an outage.
                    retry_after = _retry_delay(response, default=_RETRY_BACKOFF_SECONDS)
                    raise WikipediaError(
                        f"{url} returned {response.status_code} (upstream busy)"
                    )
                response.raise_for_status()
                payload = response.json()
            except WikipediaError as exc:
                last_error = exc
            except TimeoutError as exc:
                # Raised by `asyncio.timeout` above, and not by httpx, which is
                # what tells the two apart. A timeout that was the budget's is not
                # an upstream failure: Wikimedia may be perfectly healthy and the
                # request simply ran out of this analysis's time. Reporting it as
                # `WikipediaError` would send the caller to a 502 blaming Wikipedia,
                # and would then be retried, spending another request on a
                # request that has already run out of time.
                budget = current_budget()
                if budget is not None and budget.expired():
                    raise AnalysisAborted(DEADLINE) from exc
                last_error = WikipediaError(f"Request to {url} timed out: {exc}")
            except (httpx.HTTPError, ValueError) as exc:
                last_error = WikipediaError(f"Request to {url} failed: {exc}")
            else:
                if isinstance(payload, dict) and "error" in payload:
                    raise WikipediaError(f"MediaWiki API error: {payload['error']}")
                await check_budget()
                return payload
            if attempt == 0:
                # A little jitter, so several clients that were refused together do not
                # all come back at the same instant and get refused again.
                await asyncio.sleep(
                    retry_after if retry_after is not None else _RETRY_BACKOFF_SECONDS
                )
                # The retry backoff sleeps, so the deadline can pass while waiting
                # and a doomed second attempt would be one more call to Wikimedia.
                await check_budget()

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
    ) -> dict[int, PageLinks]:
        """Outgoing main-namespace link titles for many pages, keyed by page id.

        Titles are returned as comparison keys (see :func:`title_key`).

        Paginates, and reports per page whether it saw every link. ``pllimit=max`` is not
        "everything" - it is capped at 500 for a client without ``apihighlimits``, and the
        response carries a ``continue`` token when more remain. Stopping at the cap and
        reporting the result as if it were the whole set is what made a one-way check
        report a false accusation, so the cap ends the loop *and* marks the page
        incomplete.
        """

        ids = [int(page_id) for page_id in page_ids if page_id]
        if not ids:
            return {}

        result: dict[int, PageLinks] = {}
        for batch in chunked(ids, _MAX_TITLES_PER_REQUEST):
            params: dict[str, Any] = {
                "action": "query",
                "prop": "links",
                "plnamespace": MAIN_NAMESPACE,
                "pllimit": _LINKS_PROP_LIMIT,
                "pageids": "|".join(str(page_id) for page_id in batch),
                "redirects": _MAX_REDIRECTS,
            }
            # Whether this batch dropped a link because the cap was already reached.
            # A continuation that adds nothing is explained by that, and explained
            # stalls must not be reported as a broken token - see below.
            cap_reached = False

            # Paged one query at a time, because a continuation token belongs to the
            # query that produced it and cannot be carried into the next batch.
            while True:
                data = await self._api_get(params)
                before = sum(len(entry.titles) for entry in result.values())

                for page in (data.get("query") or {}).get("pages") or []:
                    page_id = page.get("pageid")
                    if not page_id:
                        continue
                    entry = result.setdefault(
                        int(page_id), PageLinks(titles=set(), complete=True)
                    )
                    for link in page.get("links") or []:
                        title = link.get("title")
                        if not title:
                            continue
                        if len(entry.titles) >= max_links_per_page:
                            # A link we had to drop is a link we cannot see the
                            # destination of, so the answer stops being complete here.
                            entry.complete = False
                            cap_reached = True
                            continue
                        entry.titles.add(title_key(title))

                if not data.get("continue"):
                    break
                if sum(len(entry.titles) for entry in result.values()) == before:
                    # A continuation that brings back nothing new would spin forever,
                    # holding a request and a slot in the concurrency semaphore.
                    #
                    # The cap is the ordinary reason that happens. A page with more
                    # main-namespace links than `max_links_per_page` - Delhi has over
                    # 500 - fills up, is marked incomplete, and every link in the
                    # following pages is then dropped for the same reason. Treating
                    # that as a broken token failed the whole analysis with a 502 for
                    # any article linking somewhere huge, which is most of them. The
                    # page is already marked incomplete, so the honest answer is to
                    # stop and let the caller treat the target as unverified.
                    if cap_reached:
                        break
                    raise WikipediaError(
                        "MediaWiki returned a continuation token that returned no new links"
                    )
                params = {**params, **data["continue"]}

        return result

    # ------------------------------------------------------------------
    # page descriptions (used to tell people and places apart)
    # ------------------------------------------------------------------
    async def get_page_descriptions(self, page_ids: Iterable[int]) -> dict[int, str]:
        """Wikibase short descriptions for many pages, keyed by page id.

        An article's own short description ("English mathematician and writer",
        "village in Malta") is what identifies it as a person or a place, and it
        comes from the article itself rather than from a name search. The API
        returns it for up to 50 pages per request, so describing every link of an
        article costs a handful of requests instead of one per link.

        A page with no description, and any page id that could not be read, is
        simply absent from the result: the caller then has no description to
        classify from, which is different from a description that matched
        nothing.
        """

        ids = sorted({int(page_id) for page_id in page_ids if page_id})
        if not ids:
            return {}

        descriptions: dict[int, str] = {}
        for batch in chunked(ids, _MAX_TITLES_PER_REQUEST):
            data = await self._api_get(
                {
                    "action": "query",
                    "prop": "description",
                    "pageids": "|".join(str(page_id) for page_id in batch),
                    "redirects": _MAX_REDIRECTS,
                }
            )
            for page in (data.get("query") or {}).get("pages") or []:
                page_id = page.get("pageid")
                description = page.get("description")
                if page_id and isinstance(description, str) and description.strip():
                    descriptions[int(page_id)] = description.strip()

        return descriptions

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
