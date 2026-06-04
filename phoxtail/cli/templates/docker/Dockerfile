# Base stage with common dependencies
FROM python:{{ python_version }}-slim-bookworm AS base

EXPOSE {{ port }}

ENV PYTHONUNBUFFERED=1 \
    PORT={{ port }}

RUN mkdir -p /home/app && chown 1000:1000 /home/app
ENV HOME=/home/app

# Install System Dependencies
RUN apt-get update --yes --quiet && apt-get install --yes --quiet --no-install-recommends \
    build-essential \
    libpq-dev \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    libwebp-dev \
    gettext \
    graphviz \
    libgraphviz-dev \
    ffmpeg \
 && rm -rf /var/lib/apt/lists/*

# Install private packages from local wheels (remove once published to PyPI)
COPY wheels/ /tmp/wheels/
RUN WHEEL=$(ls /tmp/wheels/phoxtail-*.whl) && pip install "${WHEEL}[dev]" && \
    find /tmp/wheels -name '*.whl' ! -name 'phoxtail-*' -exec pip install {} +

# Install Python Dependencies
COPY requirements.txt /
RUN pip install -r /requirements.txt

WORKDIR /app

# Development Stage
FROM base AS development
COPY . .
CMD set -xe; \
    python manage.py migrate --noinput && \
    python manage.py runserver 0.0.0.0:{{ port }};

# Production Stage
FROM base AS production
COPY . .
CMD set -xe; \
    python manage.py collectstatic --no-input && \
    python manage.py migrate --noinput && \
    gunicorn src.wsgi:application -w {{ gunicorn_workers }} -b :{{ port }};
