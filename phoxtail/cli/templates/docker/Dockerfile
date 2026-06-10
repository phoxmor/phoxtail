# ── Build stage ───────────────────────────────────────────────────────────
# Installs all Python packages. Has git and openssh so uv can fetch private
# repos over SSH. These tools never reach the runtime image.
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

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=ssh \
    mkdir -p /root/.ssh && \
    echo "github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl" > /root/.ssh/known_hosts && \
    uv sync --frozen

# ── Runtime base ──────────────────────────────────────────────────────────
# Clean image. No git, no openssh, no compiler. Only what the app needs
# to actually run. Packages are copied in from the build stage above.
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

COPY --from=builder /usr/local/lib/python{{ python_version }}/site-packages/ \
                    /usr/local/lib/python{{ python_version }}/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

WORKDIR /app

# Development Stage
FROM base AS development
COPY . .
CMD set -xe; \
    python manage.py migrate --noinput && \
    python manage.py runserver 0.0.0.0:{{ port }};

# Production Stage
FROM base AS production
COPY --chown=1000:1000 . .
RUN mkdir -p /app/static /app/media && chown 1000:1000 /app/static /app/media
CMD set -xe; \
    python manage.py collectstatic --no-input && \
    python manage.py migrate --noinput && \
    gunicorn src.wsgi:application -w {{ gunicorn_workers }} -b :{{ port }};
