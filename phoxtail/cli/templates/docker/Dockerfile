# ── Build stage (shared) ──────────────────────────────────────────────────
# Build tooling only. Has git and openssh so uv can fetch private repos over
# SSH. Nothing from this stage reaches the runtime image directly — the
# per-target builder stages below run the actual dependency install.
FROM python:{{ python_version }}-slim-bookworm AS builder

ENV UV_PROJECT_ENVIRONMENT=/usr/local

RUN apt-get update --yes --quiet && apt-get install --yes --quiet --no-install-recommends \
    build-essential \
    libpq-dev \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    libwebp-dev \
    git \
    openssh-client \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /usr/local/bin/uv

RUN mkdir -p /root/.ssh && \
    echo "github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl" > /root/.ssh/known_hosts

WORKDIR /app
COPY pyproject.toml uv.lock ./

# One lockfile, two install profiles: the dev dependency group (pytest, ruff,
# ipython, browser-reload, ...) is installed for development and excluded from
# production. Docker only builds the stages the requested target needs.
FROM builder AS builder-production
RUN --mount=type=ssh uv sync --frozen --no-dev

FROM builder AS builder-development
RUN --mount=type=ssh uv sync --frozen

# ── Runtime base ──────────────────────────────────────────────────────────
# Clean image. No git, no openssh, no compiler. Only what the app needs
# to actually run. Packages are copied in from a builder stage above.
FROM python:{{ python_version }}-slim-bookworm AS base

EXPOSE {{ port }}

ENV PYTHONUNBUFFERED=1 \
    PORT={{ port }}

RUN mkdir -p /home/app && chown 1000:1000 /home/app
ENV HOME=/home/app

RUN apt-get update --yes --quiet && apt-get install --yes --quiet --no-install-recommends \
    libpq5 \
    libjpeg62-turbo \
    zlib1g \
    libwebp7 \
    gettext \
    ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Development Stage
FROM base AS development
COPY --from=builder-development /usr/local/lib/python{{ python_version }}/site-packages/ \
                                /usr/local/lib/python{{ python_version }}/site-packages/
COPY --from=builder-development /usr/local/bin/ /usr/local/bin/

# Headless chromium for the studio's render tools, so an agent editing variants
# can screenshot its own work instead of asking for one. Development only:
# production never renders. `--only-shell` skips the 379MB full chromium and
# installs just the headless shell, which is what `chromium.launch()` already
# uses — headed mode is the only thing given up. Above `COPY . .` so source
# edits don't invalidate the layer.
RUN playwright install --with-deps --only-shell chromium \
 && rm -rf /var/lib/apt/lists/*

COPY . .
CMD set -xe; \
    python manage.py migrate --noinput && \
    python manage.py runserver 0.0.0.0:{{ port }};

# Production Stage
FROM base AS production
COPY --from=builder-production /usr/local/lib/python{{ python_version }}/site-packages/ \
                               /usr/local/lib/python{{ python_version }}/site-packages/
COPY --from=builder-production /usr/local/bin/ /usr/local/bin/
COPY --chown=1000:1000 . .
RUN mkdir -p /app/static /app/media && chown 1000:1000 /app/static /app/media
CMD set -xe; \
    python manage.py collectstatic --no-input && \
    python manage.py migrate --noinput && \
    gunicorn src.wsgi:application -w {{ gunicorn_workers }} -b :{{ port }};
