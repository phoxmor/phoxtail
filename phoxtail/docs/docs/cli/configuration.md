# Configuration Reference

This page documents the configuration files used by Phoxtail projects. Use the [CLI](cli.md) to generate these files automatically, or use these templates as a reference for manual configuration.

## Environment Variables

### Development (.env)

```bash
# Environment
DJANGO_ENV=development

# Django Core
SECRET_KEY=<generated_50_char_secret>
ALLOWED_HOSTS=localhost
CSRF_TRUSTED_ORIGINS=http://localhost
SITE_NAME=Phoxtail

# Database
POSTGRES_DB=postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<generated_256_bit_token>
POSTGRES_HOST=db
POSTGRES_PORT=5432

# Features
FEATURE_ALLOW_SIGNUP=true

# Backup
BACKUP_FILE=yyyy-mm-dd.sql
```

### Production (.env)

```bash
# Environment
DJANGO_ENV=production

# Django Core
SECRET_KEY=<generated_50_char_secret>
ALLOWED_HOSTS=example.com
CSRF_TRUSTED_ORIGINS=https://example.com
SITE_NAME=Phoxtail

# Database
POSTGRES_DB=postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<generated_256_bit_token>
POSTGRES_HOST=db
POSTGRES_PORT=5432

# Domain
DOMAIN=example.com
DOMAIN_EMAIL=admin@example.com

# Email
USE_SMTP_EMAIL_BACKEND=true
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=<smtp_username>
EMAIL_HOST_PASSWORD=<smtp_password>
DEFAULT_FROM_EMAIL=admin@example.com

# Features
FEATURE_ALLOW_SIGNUP=false

# Backup
BACKUP_FILE=yyyy-mm-dd.sql
```

## Docker

### Dockerfile

Multi-stage build with development and production targets.

```dockerfile
# Base stage with common dependencies
FROM python:3.12-slim-bookworm AS base

EXPOSE 80

ENV PYTHONUNBUFFERED=1 \
    PORT=80

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
 && rm -rf /var/lib/apt/lists/*

# Install Python Dependencies
COPY requirements.txt /
RUN pip install -r /requirements.txt

WORKDIR /app

# Development Stage
FROM base AS development
COPY . .
CMD set -xe; \
    python manage.py migrate --noinput && \
    python manage.py runserver 0.0.0.0:80;

# Production Stage
FROM base AS production
COPY . .
CMD set -xe; \
    python manage.py collectstatic --no-input && \
    python manage.py migrate --noinput && \
    gunicorn src.wsgi:application -w 3 -b :80;
```

### Docker Compose (Development)

```yaml
services:
  web:
    build:
      target: development
    image: phoxmor/project:latest
    restart: always
    volumes:
      - .:/app
      - /path/to/phoxtail:/opt/phoxtail/phoxtail:ro
    environment:
      - PYTHONPATH=/opt/phoxtail
    env_file:
      - ./.env
    ports:
      - "80:80"
    depends_on:
      - db

  db:
    image: postgres:18
    restart: always
    env_file:
      - ./.env
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql
      - ./db-backups:/db-backups

  docs:
    image: phoxmor/project:latest
    profiles: ["docs"]
    working_dir: /app/docs
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    command: sh -c "mkdocs serve --dev-addr 0.0.0.0:8000"

volumes:
  postgres_data:
```

### Docker Compose (Production)

```yaml
services:
  web:
    build:
      target: production
    image: phoxmor/project:latest
    restart: always
    volumes:
      - .:/app
    env_file:
      - ./.env
    depends_on:
      - db

  db:
    image: postgres:18
    restart: always
    env_file:
      - ./.env
    volumes:
      - postgres_data:/var/lib/postgresql
      - ./db-backups:/db-backups

  nginx:
    image: nginx:latest
    restart: always
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./static:/usr/share/nginx/html/static
      - ./media:/usr/share/nginx/html/media
      - ./certbot/conf:/etc/letsencrypt
      - ./certbot/www:/var/www/certbot
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - web

  certbot:
    image: certbot/certbot
    profiles: ["ssl"]
    env_file:
      - ./.env
    volumes:
      - ./certbot/conf:/etc/letsencrypt
      - ./certbot/www:/var/www/certbot
      - ./static:/usr/share/nginx/html/static
      - ./media:/usr/share/nginx/html/media
    depends_on:
      - nginx

volumes:
  postgres_data:
```

## Nginx

### Initial (HTTP-only, for SSL certificate retrieval)

```nginx
worker_processes 1;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    client_max_body_size 50M;
    client_body_buffer_size 50M;

    server {
        listen 80;

        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
            allow all;
        }

        location / {
            proxy_pass http://web:80;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host $host;
            proxy_cache_bypass $http_upgrade;
            proxy_request_buffering on;
            proxy_max_temp_file_size 50M;
        }

        location /static/ {
            alias /usr/share/nginx/html/static/;
        }

        location /media/ {
            alias /usr/share/nginx/html/media/;
        }
    }
}
```

### Production (HTTPS with SSL/TLS)

```nginx
worker_processes auto;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Performance
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;

    # Docker internal DNS resolver (Fixes 3s delay with HTTP/2)
    resolver 127.0.0.11 ipv6=off;

    # Gzip
    gzip on;
    gzip_types text/plain text/css application/javascript application/json application/xml;

    # Limits
    client_max_body_size 50M;
    client_body_buffer_size 50M;

    # SSL Globals
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;

    # Redirect HTTP to HTTPS
    server {
        listen 80;
        server_name example.com www.example.com;

        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }

        location / {
            return 301 https://example.com$request_uri;
        }
    }

    # Main HTTPS Server
    server {
        listen 443 ssl;
        http2 on;
        server_name example.com;

        ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

        # Security headers
        add_header X-Content-Type-Options nosniff;
        add_header X-Frame-Options SAMEORIGIN;
        add_header Referrer-Policy strict-origin-when-cross-origin;

        location / {
            proxy_pass http://web:80;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            proxy_request_buffering on;
            proxy_max_temp_file_size 50M;
        }

        location /static/ {
            alias /usr/share/nginx/html/static/;
            expires 30d;
            add_header Cache-Control "public, immutable";
        }

        location /media/ {
            alias /usr/share/nginx/html/media/;
            expires 7d;
            add_header Cache-Control "public";
        }
    }
}
```

## CLI Command Reference

Phoxtail provides a unified CLI for managing the entire project lifecycle.

```bash
# Project Lifecycle
phoxtail hatch myproject        # Scaffold a new project

# Container Lifecycle
phoxtail docker up              # Start services (detached by default)
phoxtail docker up --build      # Rebuild images before starting
phoxtail docker down            # Stop services
phoxtail docker restart         # Restart services

# Environment & Config Generation
phoxtail env create             # Generate .env file
phoxtail docker create dockerfile # Generate Dockerfile
phoxtail docker create compose  # Generate docker-compose.yaml
phoxtail nginx create initial   # Generate HTTP-only nginx config
phoxtail nginx create production # Generate HTTPS nginx config

# Database
phoxtail manage <cmd>           # Run any Django management command
phoxtail db pull <cluster> <host> <dir> # Pull data from remote server
phoxtail db backup              # Create a timestamped database backup
phoxtail db restore <file>.sql  # Restore from a backup file

# Media
phoxtail media pull <host> <dir> # Sync media files from remote server

# Quality & Testing
phoxtail lint                   # Run ruff + djlint
phoxtail test                   # Run pytest in web container
phoxtail test --cli             # Run CLI unit tests locally

# Requirements
phoxtail requirements compile   # Compile requirements.in → requirements.txt

# TLS Certificates
phoxtail ssl obtain             # Obtain SSL certificate (HTTP-01 challenge)
phoxtail ssl obtain --wildcard  # Obtain wildcard certificate (DNS-01 challenge)
phoxtail ssl renew              # Renew certificates and reload nginx

# Documentation
phoxtail docs                   # Serve the Phoxtail docs locally
phoxtail docs build             # Build documentation as a static site
```

## GitHub Actions (Deploy)

```yaml
name: Remote Deploy

on:
  push:
    branches: [ main ]
  workflow_dispatch:

jobs:
  deploy:
    name: Deploy
    runs-on: ubuntu-latest

    steps:
      - name: SSH into server and deploy
        uses: appleboy/ssh-action@v1.2.2
        with:
          host: ${{ secrets.HOST }}
          username: ${{ secrets.USERNAME }}
          key: ${{ secrets.KEY }}
          script: |
            cd /path/to/project
            git pull origin main
            phoxtail docker up --build
```
