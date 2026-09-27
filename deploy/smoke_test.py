"""Smoke test for a deployed Find the Missing Connections environment.

Unlike ``backend/tests/smoke_live.py``, which exercises the MediaWiki client
directly, this script talks to a running deployment over HTTP. It is the
evidence for Phase 6 UAT and for the Phase 7 production smoke-test gate.

It is deliberately stdlib-only: it must run on whatever host the deployment is
on, without installing the application's dependencies. It is never collected by
pytest - the filename does not match ``test_*.py`` - and it is the only kind of
check in the repository that is allowed to touch the network by design.

Usage:
    python deploy/smoke_test.py --base-url http://localhost:8080
    python deploy/smoke_test.py --base-url https://example.com --title Mumbai
    python deploy/smoke_test.py --base-url http://localhost:8081 --json

Exit code is 0 only when every check passes.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable

# One analysis fans out to the MediaWiki API in batches of up to 50 titles, plus
# a reverse-link pass over every one-way candidate. Allow generous time; a slow
# pass is not a failure.
DEFAULT_TIMEOUT = 240.0
FAST_TIMEOUT = 30.0

# Defaults to an article with enough links to produce people, places, missing
# targets and one-way links. Override with --title for a specific article.
DEFAULT_TITLE = "Chandni Chowk"

# Edge statuses build_connection_map can emit. Anything else means the map and
# the Cytoscape stylesheet have drifted apart.
KNOWN_EDGE_STATUSES = {"missing", "one-way", "mutual", "unchecked"}


class SmokeFailure(Exception):
    """A check could not be completed, as opposed to a check that failed."""


@dataclass
class Check:
    name: str
    passed: bool
    detail: str
    phase: str = ""
    duration: float = 0.0


@dataclass
class Report:
    base_url: str
    title: str
    checks: list[Check] = field(default_factory=list)

    @property
    def failures(self) -> list[Check]:
        return [check for check in self.checks if not check.passed]

    def add(self, name: str, passed: bool, detail: str, phase: str) -> None:
        self.checks.append(Check(name, passed, detail, phase))

    def timed(self, name: str, phase: str, fn: Callable[[], tuple[bool, str, Any]]) -> Any:
        """Run one check, recording its outcome and returning its payload.

        Returning the payload from inside the closure is what keeps a check's
        HTTP result available to later checks; a check that raises has no
        payload, so the caller must handle None.
        """

        started = time.monotonic()
        payload: Any = None
        try:
            passed, detail, payload = fn()
        except SmokeFailure as exc:
            passed, detail = False, str(exc)
        self.add(name, passed, detail, phase)
        self.checks[-1].duration = round(time.monotonic() - started, 2)
        return payload

    def as_dict(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "title": self.title,
            "total": len(self.checks),
            "passed": len(self.checks) - len(self.failures),
            "failed": len(self.failures),
            "duration_seconds": round(sum(c.duration for c in self.checks), 2),
            "checks": [
                {
                    "name": c.name,
                    "phase": c.phase,
                    "passed": c.passed,
                    "detail": c.detail,
                    "duration_seconds": c.duration,
                }
                for c in self.checks
            ],
        }


def _request(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: float = FAST_TIMEOUT,
) -> Any:
    url = f"{base_url.rstrip('/')}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        raise SmokeFailure(f"{method} {path} -> HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise SmokeFailure(f"{method} {path} -> unreachable: {exc.reason}") from exc
    except TimeoutError:
        raise SmokeFailure(f"{method} {path} -> timed out after {timeout}s") from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise SmokeFailure(f"{method} {path} -> response was not JSON: {exc}") from exc


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def _status(base_url: str, path: str, timeout: float = FAST_TIMEOUT) -> int:
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}{path}", timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as exc:
        return exc.code


# --- checks -----------------------------------------------------------------
# The phase column is the Phase 6 task-list item each check provides evidence
# for. A check that depends on an earlier payload is skipped, not failed, when
# that payload is missing - the failure is already recorded upstream.


def check_health(report: Report, args: argparse.Namespace) -> dict[str, Any]:
    """Entry criteria: the deployment answers, and the database is really reachable."""

    def run() -> tuple[bool, str, Any]:
        health = _request(args.base_url, "/api/health")
        _require(health.get("status") == "ok", f"status was {health.get('status')!r}")
        if args.expect_database and not health.get("database_enabled"):
            raise SmokeFailure(
                "database_enabled is false; the deployment is running without a cache"
            )
        # `database_enabled` only says an Engine object exists, and create_engine is
        # lazy - a wrong host or a wrong password still leaves one. Gating on it let a
        # deployment whose every write was being rejected pass this check.
        if args.expect_database and not health.get("database_reachable"):
            raise SmokeFailure(
                "database_reachable is false; a cache is configured but not answering, "
                "so every write is being discarded"
            )
        if health.get("database_enabled"):
            state = "connected" if health.get("database_reachable") else "configured but NOT answering"
        else:
            state = "disabled"
        return True, f"version {health.get('version')}, database {state}", health

    health = report.timed("health endpoint responds", "entry criteria", run)
    if health is None:
        return {}
    if health.get("database_enabled"):
        reachable = bool(health.get("database_reachable"))
        report.add(
            "database connected",
            reachable,
            "cache is active and answering" if reachable else "cache is configured but not answering",
            "entry criteria",
        )
    return health


def check_search(report: Report, args: argparse.Namespace) -> list[dict[str, Any]]:
    """Phase 6 task 1: a valid article can be searched."""

    def run() -> tuple[bool, str, Any]:
        query = urllib.parse.urlencode({"q": args.title, "limit": 10})
        payload = _request(args.base_url, f"/api/articles/search?{query}")
        results = payload.get("results", [])
        _require(bool(results), f"no search results for {args.title!r}")
        detail = f"{len(results)} results, first {results[0].get('title')!r}"
        return True, detail, results

    return report.timed("article search returns results", "task 1 - search", run) or []


def check_find(report: Report, args: argparse.Namespace) -> dict[str, Any]:
    """Phase 6 task 2: the name resolves to one article that can be analysed."""

    def run() -> tuple[bool, str, Any]:
        query = urllib.parse.urlencode({"q": args.title})
        payload = _request(args.base_url, f"/api/articles/find?{query}")
        _require(bool(payload.get("title")), "response carried no title")
        _require(payload.get("exists") is True, "resolved article reported as not existing")
        detail = f"resolved to {payload['title']!r} (page {payload.get('page_id')})"
        return True, detail, payload

    return report.timed("name resolves to one article", "task 2 - open analysis", run) or {}


def check_analyze(report: Report, args: argparse.Namespace) -> dict[str, Any]:
    """Phase 6 tasks 3-7 in one call: the full analysis returns, and its counts
    agree with the arrays they summarise."""

    def run() -> tuple[bool, str, Any]:
        payload = _request(
            args.base_url,
            "/api/analyze",
            method="POST",
            payload={"title": args.title},
            timeout=DEFAULT_TIMEOUT,
        )
        summary = payload.get("summary", {})
        _require(bool(payload.get("links")), "no links extracted")
        _require(summary.get("total_links", 0) > 0, "summary reported zero links")

        # These two are built as len() of the array they describe, so a
        # disagreement means the payload was assembled from different passes.
        for key, array_key in (
            ("total_missing", "missing_connections"),
            ("total_one_way", "one_way_connections"),
        ):
            _require(
                summary.get(key, 0) == len(payload.get(array_key, [])),
                f"summary.{key}={summary.get(key)} but "
                f"{len(payload.get(array_key, []))} items in {array_key}",
            )

        # total_links counts every link found in the article; `links` is the
        # subset the existence check answered, and the self-link is dropped.
        # So the list may be shorter, never longer.
        _require(
            len(payload["links"]) <= summary["total_links"],
            f"returned {len(payload['links'])} links but summary counted "
            f"{summary['total_links']} in the article",
        )

        # total_articles is total_links after redirects are resolved, so it can
        # only be smaller. Equal means the article linked no redirect under two
        # names, which is the common case; smaller is UAT-02's Ghalib.
        articles = summary.get("total_articles")
        _require(articles is not None, "summary has no total_articles field")
        _require(
            0 < articles <= summary["total_links"],
            f"summary.total_articles={articles} is not a positive count no larger "
            f"than total_links={summary['total_links']}",
        )

        parts = [
            f"{summary.get('total_people', 0)} people",
            f"{summary.get('total_places', 0)} places",
            f"{summary.get('total_missing', 0)} missing",
            f"{summary.get('total_one_way', 0)} one-way",
        ]
        return True, ", ".join(parts), payload

    return report.timed("analysis runs and counts agree", "tasks 3-7 - analysis", run) or {}


def check_people(report: Report, analysis: dict[str, Any]) -> None:
    """Phase 6 task 3: people are displayed.

    ``total_people`` is counted over the classifier's own map, which covers
    every extracted link, while the returned list is the answered subset. The
    summary count is therefore the one that must be non-zero.
    """

    def run() -> tuple[bool, str, Any]:
        total = analysis["summary"].get("total_people", 0)
        _require(total > 0, "no link in the article was classified as a person")
        listed = [link for link in analysis["links"] if link.get("entity_type") == "person"]
        missing = analysis["summary"].get("missing_people", 0)
        named = ", ".join(link["title"] for link in listed[:3]) or "none in the answered subset"
        detail = f"{total} people ({missing} without an article), listed: {named}"
        return True, detail, None

    report.timed("people are identified", "task 3 - people", run)


def check_places(report: Report, analysis: dict[str, Any]) -> None:
    """Phase 6 task 4: places are displayed."""

    def run() -> tuple[bool, str, Any]:
        total = analysis["summary"].get("total_places", 0)
        _require(total > 0, "no link in the article was classified as a place")
        listed = [link for link in analysis["links"] if link.get("entity_type") == "place"]
        missing = analysis["summary"].get("missing_places", 0)
        named = ", ".join(link["title"] for link in listed[:3]) or "none in the answered subset"
        detail = f"{total} places ({missing} without an article), listed: {named}"
        return True, detail, None

    report.timed("places are identified", "task 4 - places", run)


def check_links(report: Report, analysis: dict[str, Any]) -> None:
    """Phase 6 task 5: links are displayed, each with an existence state."""

    def run() -> tuple[bool, str, Any]:
        links = analysis["links"]
        _require(bool(links), "no links returned")
        unstated = [link["title"] for link in links if link.get("state") not in ("exists", "missing")]
        _require(not unstated, f"{len(unstated)} links had no exists/missing state, e.g. {unstated[:3]}")
        existing = sum(1 for link in links if link.get("exists"))
        detail = f"{len(links)} links answered, {existing} existing, {len(links) - existing} missing"
        return True, detail, None

    report.timed("links carry an existence state", "task 5 - links", run)


def check_missing(report: Report, analysis: dict[str, Any]) -> None:
    """Phase 6 task 6: missing connections are displayed, and the screen's
    person/place filter has something to show."""

    def run() -> tuple[bool, str, Any]:
        missing = analysis["missing_connections"]
        _require(bool(missing), "no missing connections found; nothing for the screen to show")
        wrong = [item["title"] for item in missing if item.get("exists") is not False]
        _require(not wrong, f"{len(wrong)} missing connections reported exists=true, e.g. {wrong[:3]}")
        typed = [item for item in missing if item.get("entity_type") in ("person", "place")]
        _require(
            bool(typed),
            "no missing connection was typed person or place; the screen filters on those",
        )
        named = ", ".join(item["title"] for item in missing[:3])
        detail = f"{len(missing)} missing ({len(typed)} typed), e.g. {named}"
        return True, detail, None

    report.timed("missing connections are shown", "task 6 - missing", run)


def check_one_way(report: Report, analysis: dict[str, Any]) -> None:
    """Phase 6 task 7: one-way connections are displayed, and none of them
    claim the target links back."""

    def run() -> tuple[bool, str, Any]:
        one_way = analysis["one_way_connections"]
        _require(bool(one_way), "no one-way connections found; nothing for the screen to show")
        wrong = [i["target_title"] for i in one_way if i.get("links_back") is not False]
        _require(not wrong, f"{len(wrong)} one-way connections claimed a reverse link, e.g. {wrong[:3]}")
        named = ", ".join(item["target_title"] for item in one_way[:3])
        detail = f"{len(one_way)} one-way, e.g. {named}"
        return True, detail, None

    report.timed("one-way connections are shown", "task 7 - one-way", run)


def check_map(report: Report, args: argparse.Namespace) -> None:
    """Phase 6 task 8: the connection map payload is renderable."""

    def run() -> tuple[bool, str, Any]:
        query = urllib.parse.urlencode({"title": args.title})
        payload = _request(
            args.base_url, f"/api/connections/map?{query}", timeout=DEFAULT_TIMEOUT
        )
        nodes, edges = payload.get("nodes", []), payload.get("edges", [])
        _require(bool(nodes), "map returned no nodes")
        _require(bool(edges), "map returned no edges")

        ids = {node["id"] for node in nodes}
        dangling = [
            edge["id"] for edge in edges if edge["source"] not in ids or edge["target"] not in ids
        ]
        _require(not dangling, f"{len(dangling)} edges reference a node that is not present, e.g. {dangling[:3]}")

        seed = [node for node in nodes if node.get("is_seed")]
        _require(len(seed) == 1, f"expected exactly 1 seed node, found {len(seed)}")

        unknown = {edge.get("status") for edge in edges} - KNOWN_EDGE_STATUSES
        _require(not unknown, f"edges carry statuses Cytoscape does not style: {sorted(unknown)}")

        types = sorted({node.get("entity_type") for node in nodes})
        detail = (
            f"{len(nodes)} nodes, {len(edges)} edges, types {types}"
            f"{', truncated' if payload.get('truncated') else ''}"
        )
        return True, detail, None

    report.timed("connection map is renderable", "task 8 - map", run)


def check_highlight_source(report: Report, args: argparse.Namespace) -> None:
    """Phase 6 task 9: the data that drives missing-entity highlighting.

    Highlighting is CSS and Cytoscape styling, so no API check can prove a pixel
    changed. What is checkable, and what breaks first, is that the map marks
    missing nodes with exists=false and separates edge statuses, so the
    stylesheet has something to distinguish. A human still has to look at
    /connection-map in a browser; see docs/UAT.md.
    """

    def run() -> tuple[bool, str, Any]:
        query = urllib.parse.urlencode({"title": args.title})
        payload = _request(
            args.base_url, f"/api/connections/map?{query}", timeout=DEFAULT_TIMEOUT
        )
        nodes = payload.get("nodes", [])
        missing = [node for node in nodes if node.get("exists") is False]
        _require(bool(missing), "no node has exists=false, so nothing can be highlighted")
        seed = next(node for node in nodes if node.get("is_seed"))
        _require(
            seed.get("exists") is not False,
            "the seed article is marked missing; the whole graph would render as a gap",
        )
        statuses = sorted({edge.get("status") for edge in payload.get("edges", [])})
        _require("missing" in statuses, f"no edge is marked missing, statuses are {statuses}")
        detail = f"{len(missing)} missing nodes, edge statuses {statuses}"
        return True, detail, None

    report.timed("missing nodes are distinguishable", "task 9 - highlight source", run)


def check_understandable(report: Report, analysis: dict[str, Any]) -> None:
    """Phase 6 task 10: the result carries enough context to be read.

    'Understandable' is operationalised as: the article is identified and
    described, a timestamp is present, and the summary states whether the answer
    was truncated. It is not a usability claim, which UAT sign-off covers.
    """

    def run() -> tuple[bool, str, Any]:
        article = analysis.get("article", {})
        _require(bool(article.get("title")), "result carried no article title")
        _require(bool(article.get("url")), "result carried no article URL")
        # generated_at is a sibling of `article` on AnalysisResult, not a field
        # of ArticleDetail.
        _require(bool(analysis.get("generated_at")), "result carried no generated_at timestamp")
        described = bool(article.get("description")) or bool(article.get("extract"))
        _require(described, "article carried neither a description nor an extract")
        summary = analysis["summary"]
        for flag in ("links_truncated", "one_way_truncated", "classify_truncated"):
            _require(
                isinstance(summary.get(flag), bool),
                f"summary.{flag} is not a boolean, so a partial answer could look complete",
            )
        detail = (
            f"{article['title']!r}, {summary['total_links']} links checked, "
            f"{summary['total_missing']} missing, {summary['total_one_way']} one-way"
        )
        return True, detail, None

    report.timed("result is self-describing", "task 10 - readability", run)


def check_error_paths(report: Report, args: argparse.Namespace) -> None:
    """Not a task-list item, but a released API that 500s on bad input does not
    pass. Confirms the two controlled failure modes: a nonexistent article is
    404, an empty title is 422."""

    def run() -> tuple[bool, str, Any]:
        # Kept short on purpose: TitleQuery caps a title at 512 characters and a
        # longer one would be rejected as 422, which is a different check.
        missing_code = _status(
            args.base_url,
            f"/api/article?{urllib.parse.urlencode({'title': 'Qzxwvb nonexistent article 9384'})}",
        )
        _require(
            missing_code == 404,
            f"a nonexistent article returned {missing_code}; expected 404, not a 5xx",
        )
        empty_code = _status(args.base_url, "/api/article?title=")
        _require(empty_code == 422, f"an empty title returned {empty_code}, expected 422")
        detail = f"nonexistent article -> {missing_code}, empty title -> {empty_code}"
        return True, detail, None

    report.timed("error paths stay controlled", "quality gate", run)


def run(report: Report, args: argparse.Namespace) -> None:
    health = check_health(report, args)
    if not health:
        return
    check_search(report, args)
    if not check_find(report, args):
        return
    analysis = check_analyze(report, args)
    if not analysis:
        return
    check_people(report, analysis)
    check_places(report, analysis)
    check_links(report, analysis)
    check_missing(report, analysis)
    check_one_way(report, analysis)
    check_map(report, args)
    check_highlight_source(report, args)
    check_understandable(report, analysis)
    check_error_paths(report, args)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke test a deployed environment.")
    parser.add_argument(
        "--base-url",
        required=True,
        help="Deployment root, e.g. http://localhost:8080 for staging through nginx",
    )
    parser.add_argument("--title", default=DEFAULT_TITLE, help="Article to analyse")
    parser.add_argument(
        "--expect-database",
        action="store_true",
        help="Fail if the deployment reports database_enabled=false",
    )
    parser.add_argument("--json", action="store_true", help="Print a JSON report")
    args = parser.parse_args(argv)

    report = Report(base_url=args.base_url, title=args.title)
    run(report, args)
    payload = report.as_dict()

    if args.json:
        print(json.dumps(payload, indent=2))
        return 1 if payload["failed"] else 0

    print(f"Smoke test: {args.base_url}  article: {args.title!r}")
    print("-" * 78)
    for check in report.checks:
        mark = "PASS" if check.passed else "FAIL"
        print(f"[{mark}] {check.name} ({check.duration:>6.2f}s)")
        print(f"       {check.detail}")
    print("-" * 78)
    print(f"{payload['passed']}/{payload['total']} passed in {payload['duration_seconds']}s")
    return 1 if payload["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
