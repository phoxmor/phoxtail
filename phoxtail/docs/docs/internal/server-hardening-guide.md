# Manual Server Hardening Guide for an Existing Production Server

> **Assumption:** Debian/Ubuntu-based server. Adjust package commands if you're on a different distro.

---

## What `phoxtail server provision` actually does

The `provision` command creates the server, then injects a **cloud-init** script (`bootstrap.yml.j2`) that runs once on first boot. Here is everything it carries out:

**User setup**
- Creates a non-root deploy user (default: `phoxtail`) with `sudo` and `docker` group membership
- Adds your Hetzner project SSH keys to that user's `~/.ssh/authorized_keys`

**Package installation**
- Runs `apt update` + full `apt upgrade`
- Installs: `fail2ban`, `ufw`, `unattended-upgrades`, `git`, `curl`

**SSH hardening** (drop-in at `/etc/ssh/sshd_config.d/99-phoxtail-hardening.conf`)
- `PermitRootLogin no`
- `PasswordAuthentication no`
- `KbdInteractiveAuthentication no`
- `ChallengeResponseAuthentication no`
- `MaxAuthTries 3`
- `AllowTcpForwarding no`, `X11Forwarding no`, `AllowAgentForwarding no`
- `AllowUsers <deploy_user>` (restricts SSH to that one user)

**Firewall (UFW)**
- Allows: SSH (22), HTTP (80), HTTPS (443)
- Everything else is blocked

**fail2ban**
- Configured to watch SSH: bans after 3 failures within 5 minutes for 1 hour

**Auto security updates**
- Configures `unattended-upgrades` to auto-apply security patches without auto-reboot

**Docker + tooling**
- Installs Docker Engine + Compose plugin via `get.docker.com`
- Adds deploy user to `docker` group
- Installs `uv` (Python package manager) as the deploy user
- Installs `phoxtail` CLI via `uv tool install phoxtail`

---

## Applying this to your existing live server

Your situation differs from a clean boot in important ways. Read the decision and the safety rules before running anything.

### Decision: keep root or migrate to a deploy user?

The template disables root SSH entirely. Since you are currently running as root with a cloned project, you must choose now:

**Option A — Migrate to a deploy user (recommended, matches phoxtail's expected workflow)**
Create a deploy user, transfer your project, verify key-based login works, then disable root SSH.

**Option B — Harden in place, keep root SSH**
Apply everything except `PermitRootLogin no` and `AllowUsers`. Omit those two lines from the sshd drop-in. This is simpler but means root SSH stays open.

---

### Step 0 — Pre-flight (do this before anything else)

**Open a second SSH session to root and keep it open the entire time.** It is your safety net if you accidentally lock yourself out.

Take a snapshot/backup of the server if your provider supports it.

Inventory what is currently listening — you will need this for UFW:

```bash
ss -tlnp
```

Note every port that is in use (your app's ports, database ports, custom SSH port if any). You will add them to UFW in Step 4.

Check for other users who need SSH access — you must not lock them out:

```bash
getent passwd | awk -F: '$7 ~ /bash|sh/ {print $1}'
```

---

### Step 1 — Create the deploy user (Option A only)

```bash
# Create user with sudo and docker groups
useradd -m -s /bin/bash -G sudo,docker phoxtail

# Verify docker group exists (install docker first if not — see Step 5)
groups phoxtail
```

Grant passwordless sudo — adding the user to the `sudo` group alone still requires a password. The cloud-init template uses `NOPASSWD:ALL`, so match that with a drop-in:

```bash
echo "phoxtail ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/phoxtail
chmod 440 /etc/sudoers.d/phoxtail

# Validate before continuing — bad sudoers syntax can lock you out of sudo entirely
visudo -c -f /etc/sudoers.d/phoxtail
# should print: /etc/sudoers.d/phoxtail: parsed OK
```

Copy your current root authorized_keys to the new user:

```bash
mkdir -p /home/phoxtail/.ssh
cp /root/.ssh/authorized_keys /home/phoxtail/.ssh/authorized_keys
chown -R phoxtail:phoxtail /home/phoxtail/.ssh
chmod 700 /home/phoxtail/.ssh
chmod 600 /home/phoxtail/.ssh/authorized_keys
```

**Before touching SSH config: open a third terminal and verify you can log in as the deploy user with your key.** Do not proceed until this works.

```bash
ssh phoxtail@<your-server-ip>
sudo whoami  # should return: root
```

---

### Step 2 — Transfer your project (Option A only)

Move the project to the deploy user's home and fix ownership. This is safe to do with `-R` because the phoxtail compose template stores Postgres data in a named Docker volume (`postgres_data`), not as a bind mount inside the project directory — so there are no container-owned data dirs to worry about.

```bash
mv /root/your-project-dir /home/phoxtail/project
chown -R phoxtail:phoxtail /home/phoxtail/project
```

---

### Step 3 — SSH hardening

Create the drop-in file (do not edit `/etc/ssh/sshd_config` directly):

```bash
cat > /etc/ssh/sshd_config.d/99-phoxtail-hardening.conf << 'EOF'
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
ChallengeResponseAuthentication no
MaxAuthTries 3
AllowTcpForwarding no
X11Forwarding no
AllowAgentForwarding no
AllowUsers phoxtail
EOF

chmod 600 /etc/ssh/sshd_config.d/99-phoxtail-hardening.conf
```

This is written as a drop-in file rather than editing `/etc/ssh/sshd_config` directly — SSH loads all `*.conf` files from `/etc/ssh/sshd_config.d/` automatically. A drop-in keeps your changes isolated, survives package updates that may overwrite the main file, and is trivial to remove if needed.

Validate the config before restarting — this catches syntax errors:

```bash
sshd -t
```

If it exits without errors, restart sshd:

```bash
systemctl restart ssh
```

**Immediately test from your third terminal** that the phoxtail user can still log in. Only close the safety session once confirmed.

---

### Step 4 — UFW firewall

Install if not present:

```bash
sudo apt install -y ufw
```

**Order matters here.** Allow SSH before enabling the firewall, or you will lock yourself out:

```bash
sudo ufw allow ssh          # allow port 22 first
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

If you have other ports that need to be open (a custom SSH port, etc.) add them now, **before** the next command. The phoxtail production compose template does not expose Postgres to the host — it is internal to the Docker network only — so port 5432 should not be opened here.

```bash
# Example for a non-standard SSH port:
# sudo ufw allow 2222/tcp
```

Check status before enabling:

```bash
sudo ufw show added
```

Enable:

```bash
sudo ufw --force enable
sudo ufw status verbose
```

---

### Step 5 — Docker (if not already installed)

You said you're already serving your application, so Docker is almost certainly installed. Verify:

```bash
docker --version
docker compose version
```

If either is missing, install via the official script:

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker phoxtail
```

---

### Step 6 — fail2ban

Install and configure:

```bash
sudo apt install -y fail2ban
```

Create the local jail config:

```bash
sudo tee /etc/fail2ban/jail.local << 'EOF'
[sshd]
enabled = true
port = ssh
banaction = iptables-multiport
maxretry = 3
findtime = 300
bantime = 3600
EOF
```

Enable and start:

```bash
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
sudo systemctl status fail2ban
```

Verify it's watching SSH:

```bash
sudo fail2ban-client status sshd
```

---

### Step 7 — Unattended security updates

Install and configure:

```bash
sudo apt install -y unattended-upgrades

sudo tee /etc/apt/apt.conf.d/51phoxtail-unattended-upgrades << 'EOF'
Unattended-Upgrade::Automatic-Reboot "false";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Mail "root";
EOF
```

Enable the daily timer:

```bash
sudo dpkg-reconfigure -plow unattended-upgrades
# Select "Yes" when prompted
```

Verify:

```bash
sudo systemctl is-enabled unattended-upgrades
```

---

### Step 8 — Package updates (manual, not automatic)

The cloud-init script does a full `apt upgrade` on a fresh server because nothing is running yet. On a live server, **do not run `apt upgrade -y` blindly** — it can restart postgres, nginx, or docker mid-traffic.

Instead:

```bash
sudo apt update
apt list --upgradable 2>/dev/null
```

Review the list. Apply security-only updates cautiously, or schedule a maintenance window for a full upgrade.

---

### Step 9 — Install uv, clone phoxtail, and install the CLI

Phoxtail is not yet published to PyPI, so it is installed from a local clone.

**Install uv:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
which uv  # confirm it is found
```

**Clone the phoxtail repo alongside your project:**

```bash
git clone git@github.com:phoxmor/phoxtail.git ~/phoxtail
```

**Install the phoxtail CLI from the local clone:**

```bash
uv tool install ~/phoxtail
sudo ln -sf /home/phoxtail/.local/bin/phoxtail /usr/local/bin/phoxtail
phoxtail --version  # confirm
```

To update phoxtail on the server later, just `git pull` inside `~/phoxtail` — the mount means containers pick up changes without a rebuild.

---

### Step 10 — Clone the project and generate config files

Clone your application repo:

```bash
git clone https://<username>:<token>@github.com/<org>/<repo>.git ~/project
cd ~/project
```

Generate the configuration files:

```bash
phoxtail env create production
phoxtail docker create dockerfile
phoxtail docker create compose production
```

`phoxtail docker create dockerfile` emits both `Dockerfile` and `.dockerignore`. The `.dockerignore` excludes runtime-state directories (`certbot/`, `db-backups/`, `media/`, `static/`) and secrets (`.env`) from the Docker build context — this is not optional, it is required for builds to work once certbot has written root-owned files.

**Do not run `phoxtail nginx create production` yet** — you need the initial HTTP-only nginx config first so certbot can verify your domain. Generate that instead:

```bash
phoxtail nginx create initial
```

The generated `docker-compose.yaml` already includes the phoxtail source mount on every service that runs Django code (`web`, `celery-worker`, `celery-beat`). `phoxtail docker create compose` derives the mount source from where the CLI itself is installed — so on the server, install the CLI first (Step 9), then generate compose, and the mount points at the CLI's package dir automatically.

If you want `git pull` in `~/phoxtail` to hot-reload into the containers without reinstalling, use an editable install in Step 9: `uv tool install --editable ~/phoxtail`.

For reference, the generated production compose looks like this:

```yaml
services:
  web:
    build:
      target: production
    image: project_name/project_name:latest
    restart: always
    user: "${HOST_UID:-1000}:${HOST_GID:-1000}"
    volumes:
      - .:/app
      - ~/phoxtail/phoxtail:/opt/phoxtail/phoxtail:ro
    environment:
      - PYTHONPATH=/opt/phoxtail
    env_file:
      - ./.env
    depends_on:
      - db
      - redis

  db:
    image: postgres:18
    restart: always
    env_file:
      - ./.env
    volumes:
      - postgres_data:/var/lib/postgresql
      - ./db-backups:/db-backups

  redis:
    image: redis:7-alpine
    restart: always
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

  celery-worker:
    image: project_name/project_name:latest
    restart: always
    user: "${HOST_UID:-1000}:${HOST_GID:-1000}"
    volumes:
      - .:/app
      - ~/phoxtail/phoxtail:/opt/phoxtail/phoxtail:ro
    environment:
      - PYTHONPATH=/opt/phoxtail
    env_file:
      - ./.env
    command: celery -A src worker --loglevel=info
    depends_on:
      - db
      - redis

  celery-beat:
    image: project_name/project_name:latest
    restart: always
    user: "${HOST_UID:-1000}:${HOST_GID:-1000}"
    volumes:
      - .:/app
      - ~/phoxtail/phoxtail:/opt/phoxtail/phoxtail:ro
    environment:
      - PYTHONPATH=/opt/phoxtail
    env_file:
      - ./.env
    command: celery -A src beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    depends_on:
      - db
      - redis

  nginx:
    image: nginx:latest
    restart: always
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./static:/usr/share/nginx/html/static
      - ./media:/usr/share/nginx/html/media
      - certbot_conf:/etc/letsencrypt
      - certbot_www:/var/www/certbot
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
      - certbot_conf:/etc/letsencrypt
      - certbot_www:/var/www/certbot
      - ./static:/usr/share/nginx/html/static
      - ./media:/usr/share/nginx/html/media
    depends_on:
      - nginx

volumes:
  postgres_data:
  redis_data:
  certbot_conf:
  certbot_www:
```

Certbot state lives in **named Docker volumes** (`certbot_conf`, `certbot_www`), not in bind mounts under the project directory. This is deliberate — certbot writes its account key, certificates, and renewal config as root, and when those root-owned files sit inside the project directory they break the Docker build context for any non-root deploy user. Named volumes avoid the whole problem class. To inspect certs later: `docker compose exec nginx ls /etc/letsencrypt/live/`.

---

### Step 11 — Transfer media and database dump

Once root SSH is disabled, connect as `phoxtail` using your SSH key.

**FileZilla (SFTP):**
- Protocol: **SFTP – SSH File Transfer Protocol**
- Host: your server IP
- Logon Type: **Key file**
- User: `phoxtail`
- Key file: your private key (matching what is in `authorized_keys`)

Target paths on the server:
- Media files → `/home/phoxtail/project/media/`
- Postgres dump → `/home/phoxtail/project/db-backups/`

**Command line alternative for large media directories (faster than FileZilla):**

```bash
rsync -avz ./media/ phoxtail@<server-ip>:/home/phoxtail/project/media/
scp dump.sql phoxtail@<server-ip>:/home/phoxtail/project/db-backups/
```

**Stopping the old root project when you are ready to switch over:**

Since the phoxtail user is in the `docker` group, it can manage all containers regardless of who started them — no need to navigate into root's directory:

```bash
# See what is running
docker ps

# Stop everything
docker stop $(docker ps -q)
```

---

### Step 12 — Start containers and obtain SSL certificate

Point your domain's DNS A record to the server IP before this step. Certbot needs the domain to resolve publicly.

**Start the containers with the initial nginx config:**

```bash
cd ~/project
phoxtail docker up --build
```

**Obtain the SSL certificate:**

```bash
phoxtail ssl obtain
```

This runs certbot via Docker using the HTTP-01 webroot challenge. It reads `DOMAIN` and `DOMAIN_EMAIL` from your `.env`.

**Switch to the production nginx config:**

```bash
phoxtail nginx create production --force
docker compose exec nginx nginx -s reload
```

Your site is now serving over HTTPS.

---

### Step 12.5 — Schedule automatic certificate renewal

Let's Encrypt certificates are valid for 90 days. Schedule a daily renewal check via cron, running **as the deploy user** (not root):

```bash
# Edit phoxtail user's crontab
crontab -e
```

Add:

```
0 3 * * * cd /home/phoxtail/project && /home/phoxtail/.local/bin/phoxtail ssl renew >> /home/phoxtail/cert-renew.log 2>&1
```

Two details that commonly trip people up:

1. **Use the absolute path to `phoxtail`**. Cron runs with a minimal `PATH` and won't find `~/.local/bin/phoxtail` by default. Either spell it out as shown, or set `PATH=` at the top of the crontab.
2. **Log into the user's home, not `/var/log/`**. The deploy user cannot write to `/var/log/` — silent failure.

Do **not** run the renewal as root via `sudo crontab -e`. The whole point of the deploy user is that the project and its Docker resources belong to them; root doesn't need access to any of this.

---

### Step 13 — Restore the database dump

With containers running, load your Postgres dump:

```bash
# Copy the dump into the db container and restore
docker compose exec -T db psql -U <db_user> -d <db_name> < ~/project/db-backups/dump.sql
```

Replace `<db_user>` and `<db_name>` with the values from your `.env`.

---

## Verification checklist

Run these after all steps are complete:

```bash
# Listening ports — confirm nothing unexpected is public
ss -tlnp

# Firewall state
sudo ufw status verbose

# fail2ban watching SSH
sudo fail2ban-client status sshd

# SSH hardening applied
sudo sshd -T | grep -E 'permitrootlogin|passwordauthentication|maxauthtries|allowusers'

# Unattended upgrades enabled
sudo systemctl is-active unattended-upgrades

# Docker running
docker ps

# phoxtail accessible
phoxtail --version
```

And confirm your application is still healthy after all changes.
