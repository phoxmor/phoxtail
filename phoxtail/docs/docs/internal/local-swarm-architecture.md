# Local Swarm Architecture

This document captures the architecture decisions and remaining work for running multiple Phoxtail projects on a single machine such that AI agents in one project can discover and call the APIs of sibling projects, authenticated.

---

## The Goal

An agency runs three Phoxtail projects for a client. An AI agent working inside Project A needs to pull blocks from Project B and push content to Project C — all locally, without manual token passing. The operator sets this up once; after that, agents work across the swarm automatically.

---

## What Was Proved

### Credentials file replaces the env var

`PHOXTAIL_API_TOKEN` (single env var, one token) was replaced by `~/.phoxtail/credentials` (TOML file, one entry per host). The file is mounted read-only into every container via:

```yaml
- ${HOME}/.phoxtail:/home/app/.phoxtail:ro
```

The container's `HOME` is set correctly via:

```dockerfile
RUN mkdir -p /home/app && chown 1000:1000 /home/app
ENV HOME=/home/app
```

`resolve_token(base_url)` derives the host key from the URL and returns the matching token. This was verified: inside a container, `resolve_token("http://test-local-phoxtail-swarm")` returned the correct token stored under that key.

### Shared Docker network enables container-to-container calls

A shared external network (`phoxtail_proxy`) was created. Both project web containers joined it. A container on this network can reach any other container on it by name — no IP addresses, no host machine involved.

### Network alias makes the name valid

Docker container names use underscores (`test_local_phoxtail_swarm-web-1`) which are invalid hostnames per RFC 1034/1035 — Django rejects them. A network alias set to the project slug (`test-local-phoxtail-swarm`) provides a valid, stable, human-readable address.

### The full chain works

From inside the marketplace container, with `resolve_token()` supplying the auth header:

```python
token = resolve_token("http://test-local-phoxtail-swarm")
r = httpx.get(
    "http://test-local-phoxtail-swarm/api/streams/v1/blocks/",
    headers={"Authorization": f"Bearer {token}"}
)
# → 200, real block data from the sibling project
```

The credential key must match the address used to call the project. A token stored under `localhost:8080` does not match calls to `http://test-local-phoxtail-swarm`. Fixing `api_url` to the slug (see below) makes this automatic.

---

## What Was Decided

### Ports don't scale

Each project publishing a different port (`localhost:8080`, `localhost:9000`) requires manual tracking, produces meaningless credential keys, and breaks down as the swarm grows. The right model is named addressing on a shared network.

### The slug is the stable address

The project slug (`name.replace('_', '-')`) should be the canonical address for a project everywhere:

- `api_url` in `phoxtail.toml` → `http://<slug>`
- network alias in `docker-compose.yaml` → `<slug>`
- credential file key → `<slug>` (derived from `api_url`)

This makes the credential key identical whether you log in from the host (`phoxtail auth login --host <slug>`) or from inside a container calling that address. No manual key matching.

### `*.localhost` subdomains require host DNS

Traefik can route `marketplace.localhost` → the right container, but the host machine still needs DNS to resolve `*.localhost` to `127.0.0.1`. On Linux this requires one dnsmasq config line:

```bash
echo "address=/.localhost/127.0.0.1" | sudo tee /etc/dnsmasq.d/localhost-wildcard.conf
sudo systemctl restart dnsmasq
```

On macOS this works out of the box. On a production server it's a wildcard DNS record at the registrar. This is deferred — the slug-based model works without it for container-to-container calls.

### Traefik is shared infrastructure, not a per-project service

Embedding Traefik in every project's `docker-compose.yaml` causes port collisions — each project instantiates its own Traefik container in its own Compose namespace and they fight over port 80. Traefik must run as a single shared instance. The right approach is for phoxtail to ship a Traefik compose template and provide a command that idempotently ensures the network and proxy are running before bringing up a project.

### Trust model: global credentials = machine-wide access

The shared credentials mount means that if Project A has a token for Project Z, Project B also has it. This is the correct model when one operator owns all projects — the act of running `phoxtail auth login --host <slug>` intentionally makes that project reachable from any other project on the machine.

For multi-tenant scenarios (projects belonging to different clients on the same host), switch to per-project credential mounts (`~/.phoxtail/<slug>/credentials`) and only mount the specific tokens each project is authorised to use. This is a one-line change to the compose volume mount when needed.

---

## What Remains

### 1. Fix `api_url` in the project template — the most important change

`phoxtail/project_template/phoxtail.toml` currently defaults to:

```toml
[studio]
api_url = "http://localhost"
```

It should default to the project slug:

```toml
[studio]
api_url = "http://{{ phoxtail_project_name | slugify }}"
```

This makes the credential key match the swarm address from day one.

### 2. MCP tools cannot yet target a sibling project — the real remaining work

`phoxtail/mcp/_http.py` always resolves both the target URL and the auth token from `api_base_url()` — its own project. There is no mechanism for an MCP tool to target a different project. The credential mechanism is proven to work when the key matches the address; the missing piece is exposing a `peer` parameter through the MCP tool layer so an agent can say "call this tool against project Z."

This is the gap between "the plumbing works" and "agents can actually do it."

### 3. Bake the shared network into `hatch`

Every hatched project should automatically:

- Join `phoxtail_proxy` with a network alias matching the project slug
- Have `api_url = "http://<slug>"` in `phoxtail.toml`
- Have `ALLOWED_HOSTS` include the slug

Currently these are manual edits. They should be part of the scaffolded output.

### 4. Traefik as phoxtail-owned idempotent infrastructure

Add a `phoxtail swarm up` (or similar) command that:

1. Creates `phoxtail_proxy` if it doesn't exist
2. Starts the Traefik container if it isn't running (from a template shipped inside the phoxtail package)
3. Then brings up the project

This removes the "run Traefik from somewhere" friction without the collision trap of embedding it per-project.

### 5. Subdomain routing (north-south, deferred)

Once host DNS is resolved (dnsmasq or deployment to a real server), add a Traefik routing label derived from the slug to each project's compose file. This gives browser-accessible `<slug>.localhost` addresses and is a natural extension of the existing alias. Not needed for agent-to-agent calls; useful for human access in a local swarm.

---

## Current State of the Two Test Projects

Both `phoxtail-marketplace-site` (port 80) and `test_local_phoxtail_swarm` (port 8080) have been reverted to clean state after the experiment. The marketplace retains the permanent auth feature additions (`HOME=/home/app`, credentials mount). The test project is pristine.

The credentials file (`~/.phoxtail/credentials`) retains `localhost` and `localhost:8080` entries only.
