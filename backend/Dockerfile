# Release image for the FastAPI backend. One worker, because a single analysis
# already fans out to the MediaWiki API; scaling means more processes, not threads.
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/srv/app/.venv/bin:$PATH"

# The app has no compiled wheels, but psycopg[binary] and uvicorn[standard] want
# libpq and a working ssl/zlib. curl is absent on purpose: the healthcheck uses
# the interpreter that is already here rather than adding a package for it.
WORKDIR /srv/app

COPY requirements.txt ./
RUN python -m venv .venv \
    && .venv/bin/pip install --upgrade pip \
    && .venv/bin/pip install -r requirements.txt

# Only `app/` is copied. `tests/` stays out of the release image, and there is no
# COPY of `.env` at all: Settings reads the process environment, and the
# credentials belong in the orchestrator, not in a layer of history.
COPY app ./app

RUN useradd --system --create-home appuser \
    && chown -R appuser:appuser /srv/app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/api/health', timeout=4).read()"]

# CORS_ORIGINS and DATABASE_URL are supplied at run time. The database stays
# optional: an empty DATABASE_URL boots the app with persistence disabled.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
