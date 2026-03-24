# Phoxtail CLI

Automation tool for Phoxtail projects. Generates configuration files with secure defaults and interactive prompts.

## Installation

### For Development

Run commands directly from source (no install needed):

```bash
uv run phoxtail env create
uv run phoxtail docker create compose
```

### For Global Use

```bash
uv tool install .
```

This installs the `phoxtail` command globally in an isolated environment.

## Commands

### Environment Configuration

Generate `.env` files with secure auto-generated secrets.

```bash
# Interactive mode (outputs to .env)
phoxtail env create

# Specify environment directly
phoxtail env create development
phoxtail env create production

# Custom output file
phoxtail env create development --output .env.local

# Force overwrite
phoxtail env create --force
```

**Features:**

- Secure SECRET_KEY using Django's exact implementation
- Cryptographically secure database passwords (256-bit tokens)
- Interactive prompts with sensible defaults
- Development: All features enabled, simple credentials
- Production: Enforces mandatory fields (domain, SMTP)

### Docker Configuration

#### Dockerfile

Generate a multi-stage Dockerfile for Django/Wagtail.

```bash
# Interactive mode
phoxtail docker create dockerfile

# With options
phoxtail docker create dockerfile --python-version 3.12
phoxtail docker create dockerfile --port 8000 --workers 4
```

**Stages:**

- `base`: System dependencies and Python packages
- `development`: Django runserver
- `production`: Gunicorn WSGI server

#### Docker Compose

Generate environment-specific compose files.

```bash
# Interactive mode (outputs to docker-compose.yaml)
phoxtail docker create compose

# Specify environment
phoxtail docker create compose development
phoxtail docker create compose production

# With options
phoxtail docker create compose production --project-name mysite --postgres-version 17
```

**Services by environment:**

| Environment | Services |
|-------------|----------|
| Development | web, db |
| Production | web, db, nginx, certbot |

**PostgreSQL versions:** 15, 16, 17, 18 (handles v18 data directory change automatically)

### Nginx Configuration

#### Initial (HTTP-only)

Generate nginx.conf for SSL certificate retrieval.

```bash
phoxtail nginx create initial
phoxtail nginx create initial -o nginx.conf --force
```

This creates an HTTP-only configuration that:

- Serves `.well-known/acme-challenge/` for Let's Encrypt
- Proxies all other requests to the web service
- Works with any domain (no server_name directive)

#### Production (HTTPS)

Generate nginx.conf with full SSL/TLS support.

```bash
# Interactive (reads domain from .env)
phoxtail nginx create production

# Specify domain
phoxtail nginx create production --domain example.com
```

**Features:**

- HTTP/2 enabled
- TLS 1.2/1.3 only
- Gzip compression
- Security headers (X-Content-Type-Options, X-Frame-Options)
- Static file caching (30 days for static, 7 days for media)
- HTTP to HTTPS redirect

### Requirements Management

Compile `requirements.in` to `requirements.txt` using uv.

```bash
# Standard compile
phoxtail requirements compile

# Upgrade all packages
phoxtail requirements compile --upgrade
phoxtail requirements compile -u

# Custom files
phoxtail requirements compile --input custom.in --output custom.txt
```

### SSL Management

Manage SSL certificates via Let's Encrypt and Certbot.

```bash
# Obtain standard certificate (HTTP-01 challenge)
phoxtail ssl obtain

# Obtain wildcard certificate (DNS-01 challenge)
phoxtail ssl obtain --wildcard

# Renew certificates and reload nginx
phoxtail ssl renew
```

**Note:** `phoxtail ssl obtain` reads `DOMAIN` and `DOMAIN_EMAIL` from your `.env` file.

## SSL Certificate Workflow

The recommended workflow for obtaining SSL certificates:

```bash
# 1. Generate initial nginx config (HTTP-only)
phoxtail nginx create initial

# 2. Start Docker services
docker compose up -d

# 3. Obtain SSL certificates (reads from .env)
phoxtail ssl obtain

# 4. Generate production nginx config (HTTPS)
phoxtail nginx create production

# 5. Reload nginx (also attempts renewal)
phoxtail ssl renew
```

## Help

```bash
phoxtail --help
phoxtail env --help
phoxtail docker --help
phoxtail docker create --help
phoxtail nginx --help
phoxtail requirements --help
phoxtail ssl --help
phoxtail version
```
