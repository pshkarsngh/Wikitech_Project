"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app import db
from app.config import get_settings
from app.dependencies import SettingsDep
from app.routers import analysis, articles
from app.schemas import HealthResponse
from app.services.mediawiki import ArticleNotFoundError, MediaWikiClient, WikipediaError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    # Both are injectable: anything already on the app state wins, so the
    # defaults never replace a client or settings an embedder or a test put
    # there. Overwriting them would silently send requests to the live API
    # instead of the injected one.
    if getattr(app.state, "settings", None) is None:
        app.state.settings = settings
    if getattr(app.state, "wikipedia", None) is None:
        app.state.wikipedia = MediaWikiClient(settings)
    active = app.state.settings

    db.init_engine(active)
    if active.database_enabled:
        try:
            db.create_all()
        except Exception:  # noqa: BLE001 - start without a database
            logger.exception("Could not create database tables, continuing without cache")

    logger.info("%s v%s ready", active.app_name, active.version)
    try:
        yield
    finally:
        wikipedia = getattr(app.state, "wikipedia", None)
        if wikipedia is not None:
            await wikipedia.aclose()
        db.shutdown()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description=(
            "Finds people and places mentioned in Wikipedia articles that have no "
            "article of their own, and connections that only exist in one direction."
        ),
        lifespan=lifespan,
    )

    # Middleware order matters and is not alphabetical. Starlette runs these outside-in in
    # reverse registration order, so the list below registers innermost-first:
    #
    #   1. CORS - the existing dev-server allowance, unchanged and still the outermost
    #      concern for a browser on :5173.
    #   2. TrustedHost - refuses a bad Host header before any routing work happens, so a
    #      Host-header attack never reaches a route. See settings.allowed_hosts.
    #   3. GZip - an analysis response is a few hundred KB of JSON and the SPA is served
    #      by nginx, but /api is proxied through and was going out uncompressed.
    #
    # HTTPSRedirectMiddleware is deliberately absent. The backend is behind nginx and
    # receives plain HTTP on the container network, so it would redirect to itself in a
    # loop. It belongs at the TLS terminator, not here.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    if settings.allowed_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    @app.exception_handler(WikipediaError)
    async def wikipedia_error_handler(_: Request, exc: WikipediaError) -> JSONResponse:
        code = (
            status.HTTP_404_NOT_FOUND
            if isinstance(exc, ArticleNotFoundError)
            else status.HTTP_502_BAD_GATEWAY
        )
        return JSONResponse(status_code=code, content={"detail": str(exc)})

    app.include_router(articles.router, prefix=settings.api_prefix)
    app.include_router(analysis.router, prefix=settings.api_prefix)

    @app.get(f"{settings.api_prefix}/health", response_model=HealthResponse, tags=["meta"])
    async def health(active: SettingsDep) -> HealthResponse:
        # `active` rather than the `settings` this function closes over. The lifespan
        # lets an injected `app.state.settings` win, so every route and the analysis-key
        # gate read that one while a closure read here would report the process
        # environment instead - meaning an embedder or a test could be looking at a
        # different deployment's configuration than the one serving its requests.
        return HealthResponse(
            status="ok",
            version=active.version,
            database_enabled=db.get_engine() is not None,
            # Never let the probe decide the answer. Persistence is best effort, so a
            # database that is down degrades the cache, not the request - and this
            # endpoint still has to report that in a body rather than by failing.
            database_reachable=db.ping(),
            auth_required=active.analysis_key_enabled,
        )

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "docs": "/docs",
            "health": f"{settings.api_prefix}/health",
        }

    return app


app = create_app()
