"""Two ways to stop spending Wikimedia's budget on one request.

An analysis of a real article costs 25-35 calls, each with a 20s timeout and a
concurrency limit of three, so the wall-clock cost has no natural ceiling. Two
things bound it, and they are different in kind:

* a **deadline** - the request has taken too long. The client is still waiting,
  so the work done so far is worth returning, marked as incomplete.
* a **disconnect** - the client has gone. Nobody is waiting, so the work is worth
  nothing and the only correct action is to stop.

The shared ``MediaWikiClient`` is a single instance for the whole process
(``app.state.wikipedia``), so this cannot be an attribute on it. Threading a
parameter through every service and every client method would be a much larger
diff, so the budget travels in a ``ContextVar``: a dependency sets it for the
duration of the request and the client reads it at its one chokepoint.

That is an assumption about the ASGI server running the dependency and the
endpoint in the same context, and it is the load-bearing part of this module. It
is asserted in ``tests/test_budget.py``, which is why that file is not tidied
away as a duplicate of the deadline tests.

Deliberately not ``asyncio.timeout``: that cancels the coroutine mid-flight, and
a cancelled coroutine cannot hand back the links it already resolved.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field

DEADLINE = "deadline"
DISCONNECT = "disconnect"
StopReason = str


class AnalysisAborted(Exception):
    """An analysis will not finish: its clock ran out, or its client left.

    Deliberately not a ``WikipediaError``, because the routers translate those
    into 502 "Wikipedia request failed" and this is not Wikipedia failing. A
    deadline is this deployment failing to finish in time, and a disconnect is not
    even an error - there is no longer anyone to answer.
    """

    def __init__(self, reason: StopReason) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class AnalysisBudget:
    """How long this request may run, and how to notice it has stopped mattering.

    ``is_disconnected`` is injected rather than imported because this module must
    not know about FastAPI or Starlette; the router owns the HTTP-layer detail and
    passes the callable in. It is a callable and not a boolean because detecting a
    disconnect means awaiting the receive channel, which cannot be done from a
    synchronous check.
    """

    deadline_seconds: float
    is_disconnected: Callable[[], Awaitable[bool]] | None = None
    _started: float = field(default_factory=time.monotonic)

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self._started

    @property
    def remaining(self) -> float:
        return self.deadline_seconds - self.elapsed

    def expired(self) -> bool:
        # `<=` rather than `<` so a zero deadline stops before any work, which is
        # what a test or an operator setting it to 0 means.
        return self.elapsed >= self.deadline_seconds

    async def stop_reason(self) -> StopReason | None:
        """Why this analysis should stop now, or ``None`` to carry on.

        The clock is checked first because it costs nothing and the disconnect
        probe is an await. The order does not otherwise matter, since either
        reason is a complete answer.
        """

        if self.expired():
            return DEADLINE
        if self.is_disconnected is not None and await self.is_disconnected():
            return DISCONNECT
        return None

    async def check(self) -> None:
        reason = await self.stop_reason()
        if reason is not None:
            raise AnalysisAborted(reason)


_budget: ContextVar[AnalysisBudget | None] = ContextVar("analysis_budget", default=None)


def current_budget() -> AnalysisBudget | None:
    """The budget for the request being served, or ``None`` if there is none.

    ``None`` means unbounded, which is what every caller outside a request sees:
    a test, ``smoke_live``, a script. That default is what keeps this from
    needing a budget argument on every existing test.
    """

    return _budget.get()


async def check_budget() -> None:
    """Stop if the current request should. A no-op when there is no budget."""

    budget = _budget.get()
    if budget is not None:
        await budget.check()


def request_timeout(default: float) -> float:
    """The longest this request may wait, which is its own timeout or the budget's.

    Without this the deadline is only noticed between requests, so a request that
    is already in flight runs to its own `http_timeout_seconds` before the check
    can fire. That makes the real ceiling `deadline + http_timeout_seconds`, which
    at the shipped defaults is exactly nginx's `proxy_read_timeout` - the proxy
    would give up at the same moment, and the reader would get a bare 502 with no
    body and no `aborted` marker instead of the partial result.

    Clamped to a positive floor so a deadline that has just passed yields a tiny
    timeout rather than a negative one, and `None` when there is no budget, which
    leaves the caller's own timeout in charge.
    """

    budget = _budget.get()
    if budget is None:
        return default
    # `min` so this can only ever shorten a wait, never lengthen one: a generous
    # `http_timeout_seconds` must not become a reason to overrun the deadline.
    return max(0.001, min(default, budget.remaining))


@contextmanager
def budget_scope(budget: AnalysisBudget | None) -> Iterator[AnalysisBudget | None]:
    token: Token[AnalysisBudget | None] = _budget.set(budget)
    try:
        yield budget
    finally:
        _budget.reset(token)
