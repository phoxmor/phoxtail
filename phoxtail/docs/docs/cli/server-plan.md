# Server Management Plan

This document tracks the implementation plan for `phoxtail server` — a CLI module that provisions, deploys, and manages a production server end-to-end. Check items off as each step is completed.

---

## Overview

The goal is to reduce a fresh deployment to a single session of CLI commands with no manual SSH, no copy-pasted shell scripts, and no steps that require the user to look anything up.

The complete flow, once all phases are done:

```
phoxtail hatch myproject          # scaffold project locally
cd myproject
git init && git push ...           # push to GitHub
phoxtail server provision          # provision Hetzner server
phoxtail server deploy <ip>       # clone + configure + start
phoxtail server ssl <ip>          # obtain SSL certificates
```

---

## Phase 1 — Server Provisioning

**Command:** `phoxtail server provision`

- [x] Abstract `Provider` interface and shared data models (`base.py`)
- [x] `HetznerProvider` via raw `httpx` — list locations, server types, images, SSH keys, create/delete server, poll action status
- [x] Interactive wizard: architecture → location → server type → OS image → SSH keys → server name
- [x] Summary panel updates after each selection (mirrors Hetzner Cloud Console sidebar)
- [x] `--dry-run` flag — prints configuration without calling the API
- [x] `HETZNER_TOKEN` env var support with interactive fallback
- [x] Wait for server action to reach `success` before returning IP
- [x] 11 provider tests with `pytest-httpx` (no real API calls)

---

## Phase 2 — Cloud-Init Bootstrap

**What cloud-init is:** Every major cloud provider (Hetzner, AWS, DigitalOcean, GCP) runs a program called `cloud-init` on a server's first boot. You supply a `user_data` script when creating the server via API, and cloud-init executes it automatically — before you ever SSH in. By the time `phoxtail server provision` finishes polling the action, the server can already have Docker installed.

Hetzner accepts cloud-init via the `user_data` field in the create server request. The script must begin with `#cloud-config` (YAML) or `#!/bin/bash` (shell script). The 32 KiB size limit is not a concern for our use case.

**What the bootstrap script will do:**

1. Install Docker engine + Compose plugin via the official convenience script (`curl -fsSL https://get.docker.com | sh`) — same source as the [Hetzner community tutorial](https://community.hetzner.com/tutorials/howto-docker-install)
2. Install `uv` (Python package manager)
3. Install the `phoxtail` CLI globally via `uv tool install phoxtail`
4. Create standard project directories (`db-backups`, `media`, `static`)
5. Write a sentinel file (`/var/lib/cloud/instance/boot-finished`) so `server deploy` can wait for completion

**Implementation tasks:**

- [x] `cloud_init/bootstrap.yml.j2` template — installs Docker, uv, phoxtail v0.1.1 (PyPI), fail2ban, ufw, unattended-upgrades; creates non-root deploy user; disables root SSH + password auth
- [x] Deploy username wizard step added to `server provision` (default: `phoxtail`)
- [x] Rendered bootstrap injected as `user_data` in `ServerSpec` during `server provision`
- [x] Success panel shows `ssh <deploy_user>@<ip>` and next step hint
- [x] `server provision` waits for cloud-init to finish (polls SSH + sentinel file) before showing success
- [x] 12 template tests — valid YAML, all security directives present, user/key substitution correct
- [ ] Integration test: spin up a real CX22, SSH in, confirm `docker --version` and `phoxtail --version` work

> **Note on PyPI version:** The server installs `phoxtail` v0.1.1 from PyPI. This version has all server-side commands needed (`env`, `docker`, `nginx`, `ssl`, `db`, `media`, `manage`). The `hatch` command is intentionally absent — it is only needed locally.

---

## Phase 3 — Project Sync (Git)

**Strategy:** Git only. The hatched project is pushed to a private GitHub (or any Git host) repository. The server clones it via a deploy key (read-only SSH key scoped to that one repo). rsync is explicitly not supported — git provides atomic updates and a traceable history.

**Why not rsync:** Updates via `git pull` are atomic, auditable, and work identically whether triggered by the developer or a future CI job. rsync would require re-implementing update logic separately.

**Sequence inside `server deploy`:**

1. Generate an `ed25519` SSH key pair on the server (`~/.ssh/deploy_key`)
2. Write SSH config entry for the git host (idempotent)
3. Print the public key and prompt the user to add it as a deploy key on GitHub (**Settings → Deploy keys → Add deploy key**, read-only)
4. Wait for the user to confirm (press Enter)
5. Verify git access to the host
6. Clone the repository into `~/project/` using the deploy key
7. Create runtime directories (`db-backups`, `media`, `static`)
8. Continue to Phase 4

**Implementation tasks:**

- [x] `server deploy <ip>` command with subprocess SSH + ControlMaster connection reuse
- [x] Auto-detect repo URL from local git origin (HTTPS → SSH conversion)
- [x] Generate deploy key on server, display public key, wait for user confirmation
- [x] `git clone` the repo on the server using the deploy key
- [x] Verify clone succeeded before proceeding
- [x] Prerequisite checks (git, docker, phoxtail available on server)

---

## Phase 4 — Application Configuration

**Command:** `phoxtail server deploy <ip>` (continued)

After the repo is cloned, run phoxtail CLI commands on the server remotely over SSH — reusing exactly the same commands that already exist:

| Step | Remote command | Interactive? |
|---|---|---|
| Environment file | `phoxtail env create production` | Yes (domain, DB, SMTP) |
| Dockerfile | `phoxtail docker create dockerfile` | Yes (Python version) |
| Docker Compose | `phoxtail docker create compose production` | Yes (Postgres version) |
| Nginx (initial, HTTP-only) | `phoxtail nginx create initial` | No |
| Build and start | `phoxtail docker up --build` | No (streaming output) |

> **Note:** `uv pip install -e .` is not needed on the host — all project dependencies are installed inside the Docker container via the generated Dockerfile.

The wizard shows ✓/✗ status per step. Interactive steps forward the TTY over SSH (`ssh -t`). Each step can be re-run — `server deploy` skips completed steps automatically.

**Implementation tasks:**

- [x] SSH remote execution helpers (`ssh_run`, `ssh_check`, `ssh_live`) with ControlMaster connection reuse
- [x] Step runner with ✓ done / ✗ failed status per step
- [x] Interactive prompts forwarded over SSH via PTY allocation for commands that need them
- [x] Idempotency: skip steps where output file already exists (`.env`, `Dockerfile`, etc.)

---

## Phase 5 — SSL

**Command:** `phoxtail server ssl <ip>`

Runs after DNS is pointed at the server. Deliberately a separate command because DNS propagation is a human step with an unpredictable wait.

| Step | Remote command |
|---|---|
| Obtain certificates | `phoxtail ssl obtain` (or `--wildcard`) |
| Switch to production nginx config | `phoxtail nginx create production` |
| Reload nginx | `docker compose exec nginx nginx -s reload` |

**Implementation tasks:**

- [ ] `server ssl <ip>` command
- [ ] Prompt for domain and wildcard preference
- [ ] Run obtain + nginx create + reload over SSH
- [ ] Confirm HTTPS is working before returning

---

## Phase 6 — Maintenance Commands

| Command | Purpose | Status |
|---|---|---|
| `phoxtail server list` | List servers in the Hetzner project with IP and status | ☐ |
| `phoxtail server update <ip>` | `git pull` + `docker compose up --build` on server | ☐ |
| `phoxtail server destroy <id>` | Delete server via Hetzner API (requires confirmation) | ☐ |
| `phoxtail server ssh <ip>` | Open interactive SSH session | ☐ |

---

## Testing strategy

- **Unit tests:** `pytest-httpx` mocks — no real API calls. Already in place for Phase 1.
- **Integration tests:** Dedicated `phoxtail-dev` Hetzner project with a separate API token. Use CX22 (cheapest, ~€0.010/h). Always clean up with `phoxtail server destroy`. Label test servers `env=testing`.
- **Cost:** A CX22 running for 10 minutes costs ~€0.002. A full testing session staying up for an hour costs €0.010. Completely negligible.

---

## Documentation plan

A new docs page will be added after each phase is completed and tested:

| Page | Phase |
|---|---|
| `cli/server-provision.md` — provisioning wizard walkthrough | Phase 1 ✓ |
| `cli/server-deploy.md` — git sync + configuration + startup | Phases 2–4 |
| `cli/server-ssl.md` — SSL certificate setup | Phase 5 |
| `cli/server-maintenance.md` — update, destroy, list | Phase 6 |
