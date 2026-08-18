# Security policy

Phoxtail handles authentication, API credentials, SSL provisioning and remote
server access. Vulnerabilities in it can reach the deployments built on it, so
please report them privately.

## Supported versions

Phoxtail is pre-1.0. **Only the latest release receives security fixes.** There
are no maintenance branches and no backports; upgrading to the current version
is the supported path.

## Reporting a vulnerability

**Do not open a public issue, pull request or discussion.**

Report it through GitHub's private advisory form —
[Security → Report a vulnerability](https://github.com/phoxmor/phoxtail/security/advisories/new) —
which keeps the report visible only to the maintainers. If you would rather not
use GitHub, email **security@phoxtail.com**.

Helpful to include: the affected version, what an attacker can do, and the
smallest reproduction you have. A proof of concept is welcome but not required.

## What happens next

- **Within 72 hours** — acknowledgement that the report arrived.
- **Within 10 working days** — an assessment: whether it is a vulnerability, how
  severe, and the intended fix.
- A fix ships as a patch release as soon as it is ready, rather than waiting for
  the next scheduled release.
- The advisory and the release are published together, so nobody learns of the
  problem before the fix exists.
- You are credited in the advisory unless you prefer otherwise.

Please give us a reasonable opportunity to release a fix before disclosing
publicly.

## Scope

In scope: the `phoxtail` package, its CLI, the API and MCP surfaces, and the
configuration it generates — Dockerfiles, compose files, nginx and SSL setup.

Out of scope: vulnerabilities in dependencies, which belong with their
maintainers — though we are glad to know if a pinned version exposes Phoxtail
users; and sites built with Phoxtail, which belong with whoever operates them.
