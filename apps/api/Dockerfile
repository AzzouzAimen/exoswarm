FROM ghcr.io/astral-sh/uv:0.11.8 AS uv

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    EXOSWARM_DATA_DIR=/app/data \
    EXOSWARM_RUNS_DIR=/app/runs \
    PATH="/app/.venv/bin:$PATH" \
    UV_LINK_MODE=copy

WORKDIR /app
COPY --from=uv /uv /uvx /bin/

# Build from the repository root so the image contains both the API package and
# the exact cached backend authority/data files required by the judged path.
COPY apps/api/pyproject.toml ./pyproject.toml
COPY apps/api/uv.lock ./uv.lock
RUN uv sync --frozen --no-dev --extra science --extra agents --no-install-project
COPY apps/api/src ./src
RUN uv sync --frozen --no-dev --extra science --extra agents

COPY data/targets ./data/targets
COPY data/cached/lightcurves ./data/cached/lightcurves
COPY data/ground_truth ./data/ground_truth

RUN useradd --create-home --uid 10001 exoswarm \
    && mkdir -p /app/runs \
    && chown -R exoswarm:exoswarm /app/runs

USER exoswarm

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).read()"

# The durable controller cache and local-file coordination contract is one API
# process per runs directory. Scale by isolated instances, not Uvicorn workers.
CMD ["uvicorn", "exoswarm.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
