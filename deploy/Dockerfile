# PenCMS FastAPI brain — build from repo root:
#   Slim (default):    docker build -f deploy/Dockerfile --target api -t pencms-api .
#   Inspect (Chromium): docker build -f deploy/Dockerfile --target inspect -t pencms-api-inspect .
# Unadorned `docker build -f deploy/Dockerfile` also yields the slim image (last stage).
FROM python:3.12-slim AS api

WORKDIR /opt/pencms/backend-python

# Runtime libs for Pillow wheels / common image codecs
RUN apt-get update \
    && apt-get install -y --no-install-recommends libjpeg62-turbo zlib1g \
    && rm -rf /var/lib/apt/lists/*

COPY backend-python/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend-python/ .
COPY deploy/config.docker.ini ./config.ini

# Taxonomy / collections + llms.txt resolve via BASE_DIR.parent / core / ...
COPY core/schemas /opt/pencms/core/schemas
COPY core/docs/llms.txt /opt/pencms/core/docs/llms.txt

RUN mkdir -p /data/content /data/assets ./data \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin pencms \
    && chown -R pencms:pencms /opt/pencms /data

USER pencms

ENV PYTHONUNBUFFERED=1
EXPOSE 8008

# Bind 0.0.0.0 for containers (app __main__ defaults to 127.0.0.1)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8008"]

# In-process Playwright Chromium for Customize inspect. Not a sidecar.
FROM api AS inspect
USER root
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright
RUN python -m playwright install-deps chromium \
    && python -m playwright install --only-shell chromium \
    && chmod -R a+rX /opt/ms-playwright
USER pencms

# Implicit default for `docker build` without --target stays slim.
FROM api
