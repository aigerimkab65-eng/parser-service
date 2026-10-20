# syntax=docker/dockerfile:1
# Многоэтапная сборка parser-service.
# VARIANT=lite  — без браузера, цель ≤ 300 МБ
# VARIANT=full  — + Playwright Chromium (тяжелее)
#
# Зависимости ставятся ТОЛЬКО здесь (при сборке), не при старте контейнера.
# Хеши: requirements.lock.txt / requirements.full.lock.txt (uv pip compile --generate-hashes).

ARG PYTHON_VERSION=3.12
# python:3.12-slim multi-arch digest (Docker Hub, проверено 2026-10-20)
ARG PYTHON_IMAGE=python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
ARG VARIANT=lite
ARG VERSION=1.0.0
ARG GIT_COMMIT=unknown

# ---------- builder ----------
FROM ${PYTHON_IMAGE} AS builder

ARG VARIANT
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libxml2-dev \
        libxslt1-dev \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock.txt requirements.full.lock.txt ./
# lite → только requirements.lock.txt; full → полный lock (base + playwright)
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && if [ "$VARIANT" = "full" ]; then \
         /opt/venv/bin/pip install --require-hashes -r requirements.full.lock.txt ; \
       else \
         /opt/venv/bin/pip install --require-hashes -r requirements.lock.txt ; \
       fi \
    && /opt/venv/bin/pip uninstall -y pip \
    && find /opt/venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true \
    && find /opt/venv -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete \
    && find /opt/venv/lib -path "*/babel/locale-data/*" \
         ! -name "en*.dat" ! -name "ru*.dat" ! -name "root.dat" \
         -type f -delete

# ---------- runtime ----------
FROM ${PYTHON_IMAGE} AS runtime

ARG VARIANT=lite
ARG VERSION=1.0.0
ARG GIT_COMMIT=unknown

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    TMPDIR=/tmp \
    HOME=/tmp \
    PARSER_VARIANT=${VARIANT} \
    APP_VERSION=${VERSION} \
    GIT_COMMIT=${GIT_COMMIT} \
    BROWSER_ENABLED=false \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

LABEL org.opencontainers.image.source="https://github.com/aigerimkab65-eng/parser-service" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${GIT_COMMIT}" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.description="HTTP parser-service: URL → Markdown/text JSON"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libxml2 \
        libxslt1.1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home /tmp --shell /usr/sbin/nologin app \
    && mkdir -p /tmp \
    && chmod 1777 /tmp

COPY --from=builder /opt/venv /opt/venv
COPY app ./app
COPY static ./static

# Для full: системные зависимости Chromium + сам браузер (только на этапе сборки)
RUN if [ "$VARIANT" = "full" ]; then \
      apt-get update \
      && /opt/venv/bin/python -m playwright install-deps chromium \
      && /opt/venv/bin/python -m playwright install chromium \
      && rm -rf /var/lib/apt/lists/* \
      && chown -R app:app /ms-playwright ; \
    fi

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

# 1 процесс Hypercorn; временные файлы только в /tmp (read_only + tmpfs)
CMD ["hypercorn", "app.main:app", "--bind", "0.0.0.0:8000", "--workers", "1"]
