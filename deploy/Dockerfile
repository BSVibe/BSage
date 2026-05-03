FROM python:3.11-slim AS backend

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# Backend image carries Python only — frontend ships from Vercel
# (sage.bsvibe.dev) so we don't bundle/build it here. Avoids the
# private GitHub Packages auth dance during docker build.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy application code first (needed for package build)
COPY pyproject.toml uv.lock* ./
COPY bsage/ ./bsage/
COPY plugins/ ./plugins/
COPY skills/ ./skills/

# Install Python dependencies
RUN uv pip install --system --no-cache .

ENV PYTHONPATH=/app

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser \
    && mkdir -p /app/vault /app/tmp /app/.credentials /app/logs \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --retries=3 --start-period=15s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"

# --forwarded-allow-ips=* honours Caddy's X-Forwarded-Proto so trailing-slash
# redirects emit https:// (not http://) Location headers, avoiding browser
# CORS rejection on cross-origin requests from https://sage.bsvibe.dev.
CMD ["python", "-m", "uvicorn", "bsage.gateway.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
