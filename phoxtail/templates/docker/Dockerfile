# Base stage with common dependencies
FROM python:{{ python_version }}-slim-bookworm AS base

EXPOSE {{ port }}

ENV PYTHONUNBUFFERED=1 \
    PORT={{ port }}

# Install System Dependencies
RUN apt-get update --yes --quiet && apt-get install --yes --quiet --no-install-recommends \
    build-essential \
    libpq-dev \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    libwebp-dev \
    nodejs \
    npm \
    gettext \
    graphviz \
    libgraphviz-dev \
 && rm -rf /var/lib/apt/lists/*

# Install Python Dependencies
COPY requirements.txt /
RUN pip install -r /requirements.txt

WORKDIR /app

# Development Stage
FROM base AS development
COPY . .
CMD set -xe; \
    python manage.py tailwind install && \
    python manage.py makemigrations && \
    python manage.py migrate --noinput && \
    python manage.py runserver 0.0.0.0:{{ port }};

# Production Stage
FROM base AS production
COPY . .
CMD set -xe; \
    python manage.py tailwind install && \
    python manage.py tailwind build && \
    python manage.py collectstatic --no-input && \
    python manage.py makemigrations && \
    python manage.py migrate --noinput && \
    gunicorn src.wsgi:application -w {{ gunicorn_workers }} -b :{{ port }};
