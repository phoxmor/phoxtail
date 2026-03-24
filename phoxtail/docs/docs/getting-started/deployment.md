# Phoxtail Production Deployment Guide

This guide covers all steps required to deploy a Phoxtail project to a production server from scratch.

> **Note:** This guide describes the current (pre-hatch) workflow where projects are forks of the base repository. Once `phoxtail hatch` is available (v0.2.0), new projects will be generated via `phoxtail hatch myproject` instead of forking. The deployment steps from "Create a New Server" onward will remain the same.

---

## 1. Fork the Base Repository

Create a fork of the base Phoxtail repository for your project:

```
https://github.com/phoxmor/phoxtail.git
```

Fork it via GitHub into your organisation or personal account.

## 2. Create a New Server

Provision a new server. Using **Hetzner** as an example:

1. Log in to the [Hetzner Cloud Console](https://console.hetzner.cloud/)
2. Create a new project (or use an existing one)
3. Add a new server:
   - Select a location close to your target audience
   - Choose an OS image (Ubuntu 24.04 recommended)
   - Select a server type (CX22 or higher recommended)
   - Add your local SSH key for root access
4. Note down the server's public IP address

## 3. Install Docker and Docker Compose

SSH into your server and install Docker:

```bash
ssh root@<server-ip>

# Install Docker (official convenience script)
curl -fsSL https://get.docker.com | sh

# Verify installation
docker --version
docker compose version
```

## 4. Generate an SSH Key on the Server

Generate an SSH key so the server can pull from your private repository.

Follow the official GitHub guide:
https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent?platform=linux

```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
cat ~/.ssh/id_ed25519.pub
```

## 5. Add the Public Key as a Deploy Key

1. Copy the public key output from the previous step
2. Go to your forked repository on GitHub
3. Navigate to **Settings > Deploy keys > Add deploy key**
4. Paste the public key and give it a descriptive title
5. Enable **Allow write access** only if needed (read-only is sufficient for deployments)

## 6. Clone the Repository on the Server

```bash
cd ~
git clone git@github.com:<your-org>/<your-fork>.git
cd <your-fork>
```

## 7. Install uv and the Phoxtail CLI

Install uv (Python package manager) and make the `phoxtail` CLI globally available:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.local/bin/env
uv tool install .
```

After this, the `phoxtail` command is available from anywhere on the server.

## 8. Compile Requirements

Before building any Docker images, compile the Python requirements:

```bash
phoxtail requirements compile
```

## 9. Generate the Production Environment File

```bash
phoxtail env create production
```

This will interactively prompt you for:
- Site name
- Domain name and domain email
- Wildcard subdomain support
- Database credentials (auto-generated secure password by default)
- SMTP email configuration
- Feature flags

The generated `.env` file will contain all necessary configuration for production.

## 10. Generate the Dockerfile

```bash
phoxtail docker create dockerfile
```

Select the appropriate Python version and configure port/workers as needed.

## 11. Generate the Production Docker Compose File

```bash
phoxtail docker create compose production
```

This creates a `docker-compose.yaml` with:
- **web**: Django/Gunicorn application
- **db**: PostgreSQL database
- **nginx**: Reverse proxy with SSL termination
- **certbot**: SSL certificate management (profile: ssl)
- **redis**, **celery-worker**, **celery-beat** (if booking system is enabled)

## 12. Generate the Initial Nginx Configuration

Create the initial HTTP-only nginx config needed for SSL certificate retrieval:

```bash
phoxtail nginx create initial
```

## 13. Create Required Directories

```bash
mkdir -p db-backups media static
```

## 14. Build and Start the Docker Services

```bash
phoxtail docker up --build
```

Wait for all services to start and for the initial migrations to run.

## 15. Obtain SSL Certificates

With the initial nginx config serving HTTP, obtain Let's Encrypt certificates:

```bash
phoxtail ssl obtain
```

Or for wildcard certificates:

```bash
phoxtail ssl obtain --wildcard
```

## 16. Generate the Production Nginx Configuration

Once certificates are obtained, generate the full production nginx config with SSL:

```bash
phoxtail nginx create production
```

Then reload nginx to apply:

```bash
docker compose exec nginx nginx -s reload
```

## 17. Point Your Domain to the Server

Update your domain's DNS records:

- **A record**: `@` → `<server-ip>`
- **A record**: `www` → `<server-ip>` (or CNAME to `@`)
- For wildcard: **A record**: `*` → `<server-ip>`

Allow DNS propagation time before verifying.

## 18. Create a Superuser

```bash
phoxtail manage createsuperuser
```

## 19. Set Up SSL Certificate Auto-Renewal

Add a cron job to automatically renew certificates:

```bash
crontab -e
```

Add:

```
0 3 * * * cd ~/<your-fork> && phoxtail ssl renew >> /var/log/certbot-renew.log 2>&1
```

## 20. Verify Deployment

- [ ] Site loads over HTTPS at your domain
- [ ] HTTP redirects to HTTPS
- [ ] www redirects to non-www (or vice versa)
- [ ] Admin panel accessible at `/admin/`
- [ ] Static files served correctly
- [ ] Media uploads working
- [ ] Email sending working (if SMTP configured)

---

## Ongoing Maintenance

### Database Backups

```bash
phoxtail db backup
```

### Restore a Backup

```bash
phoxtail db restore <filename>.sql
```

### Pull Data from Another Server

```bash
phoxtail db pull cms user@remote-server ~/project
```

### Pull Media from Another Server

```bash
phoxtail media pull user@remote-server ~/project
```

### Update Deployment

```bash
cd ~/<your-fork>
git pull
phoxtail docker up --build
```
