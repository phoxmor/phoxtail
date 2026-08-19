"""Linode (Akamai) provider — thin httpx wrapper over the v4 REST API."""

import base64
import hashlib
import re
import secrets

import httpx

from .base import Image, Location, Provider, ProviderError, Server, ServerSpec, ServerType, SSHKey

BASE_URL = "https://api.linode.com/v4"

# Linode type class → our cpu_type vocabulary
_CLASS_TO_CPU_TYPE: dict[str, str] = {
    "nanode": "shared",
    "standard": "shared",
    "highmem": "shared",
    "dedicated": "dedicated",
    "gpu": "dedicated",
}

_VERSION_RE = re.compile(r"\d+(?:\.\d+)*")


class LinodeError(ProviderError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, f"Linode API [{code}]: {message}")


def _ssh_fingerprint(public_key: str) -> str:
    """Compute the traditional MD5 fingerprint from a public key string."""
    parts = public_key.strip().split()
    if len(parts) < 2:
        return ""
    try:
        raw = base64.b64decode(parts[1])
        digest = hashlib.md5(raw).digest()
        return ":".join(f"{b:02x}" for b in digest)
    except Exception:
        return ""


def _parse_city_country(label: str) -> tuple[str, str]:
    """Split 'Frankfurt 2, DE' into ('Frankfurt 2', 'DE')."""
    parts = label.rsplit(", ", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return label, ""


def _parse_os_version(label: str) -> str | None:
    m = _VERSION_RE.search(label)
    return m.group(0) if m else None


def _get_price(item: dict, location: str | None) -> tuple[str, str]:
    """Return (price_hourly, price_monthly) strings for a type, preferring region-specific price."""
    if location:
        for rp in item.get("region_prices", []):
            if rp.get("id") == location:
                return str(rp.get("hourly", 0)), str(rp.get("monthly", 0))
    p = item.get("price", {})
    return str(p.get("hourly", 0)), str(p.get("monthly", 0))


class LinodeProvider(Provider):
    display_name = "Linode (Akamai)"
    currency = "$"
    token_env_var = "LINODE_TOKEN"
    architectures = ("x86",)  # Linode only offers x86_64

    def __init__(self, token: str) -> None:
        self._client = httpx.Client(
            base_url=BASE_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "phoxtail-cli",
            },
            timeout=30.0,
        )

    def _raise_for_error(self, resp: httpx.Response) -> None:
        if resp.status_code >= 400:
            try:
                errors = resp.json().get("errors", [{}])
                first = errors[0] if errors else {}
                raise LinodeError(
                    first.get("field", str(resp.status_code)),
                    first.get("reason", resp.text),
                )
            except (ValueError, KeyError):
                resp.raise_for_status()

    def _get_all(self, path: str, **params: str | int | float | bool | None) -> list[dict]:
        """Fetch all pages, returning the merged data list."""
        results: list[dict] = []
        page = 1
        while True:
            resp = self._client.get(path, params={"page": page, "page_size": 100, **params})
            self._raise_for_error(resp)
            data = resp.json()
            results.extend(data["data"])
            if page >= data.get("pages", 1):
                break
            page += 1
        return results

    # ------------------------------------------------------------------
    # Provider interface
    # ------------------------------------------------------------------

    def list_locations(self) -> list[Location]:
        """Return only regions that support the Metadata service (cloud-init)."""
        items = self._get_all("/regions")
        locations = []
        for item in items:
            if item.get("status") != "ok":
                continue
            capabilities = item.get("capabilities", [])
            if "Metadata" not in capabilities:
                continue  # Option A: skip regions that can't run cloud-init
            label = item.get("label", item["id"])
            city, country = _parse_city_country(label)
            locations.append(
                Location(
                    id=item["id"],
                    name=item["id"],  # "de-fra-2" etc — used in create_server
                    description=label,
                    city=city,
                    country=country,
                    network_zone="",
                    metadata_support=True,
                )
            )
        return locations

    def list_server_types(self, *, location: str | None = None) -> list[ServerType]:
        items = self._get_all("/linode/types")
        result = []
        for item in items:
            cls = item.get("class", "standard")
            cpu_type = _CLASS_TO_CPU_TYPE.get(cls, "shared")
            price_hourly, price_monthly = _get_price(item, location)
            result.append(
                ServerType(
                    id=item["id"],
                    name=item["id"],  # "g6-nanode-1" etc — used in create_server
                    description=item.get("label", ""),
                    cores=item.get("vcpus", 0),
                    memory=round(item.get("memory", 0) / 1024, 2),  # MB → GB
                    disk=item.get("disk", 0) // 1024,  # MB → GB
                    cpu_type=cpu_type,
                    architecture="x86",
                    price_hourly=price_hourly,
                    price_monthly=price_monthly,
                )
            )
        return result

    def list_ssh_keys(self) -> list[SSHKey]:
        items = self._get_all("/profile/sshkeys")
        return [
            SSHKey(
                id=item["id"],
                name=item.get("label", ""),
                fingerprint=_ssh_fingerprint(item.get("ssh_key", "")),
                public_key=item.get("ssh_key", ""),
            )
            for item in items
        ]

    def list_images(self, *, architecture: str = "x86") -> list[Image]:
        items = self._get_all("/images")
        result = []
        for item in items:
            if not item.get("is_public"):
                continue
            if item.get("status") != "available":
                continue
            if item.get("deprecated"):
                continue
            label = item.get("label", "")
            # Skip LKE/Kubernetes images — their labels contain k8s version numbers
            # that get mistaken for OS versions and clutter the picker.
            if "kubernetes" in label.lower() or "lke" in label.lower():
                continue
            vendor = item.get("vendor") or ""
            capabilities = item.get("capabilities", [])
            result.append(
                Image(
                    id=item["id"],
                    name=item["id"],  # "linode/ubuntu24.04" — used in create_server
                    description=label,
                    os_flavor=vendor.lower(),
                    os_version=_parse_os_version(label),
                    architecture="x86",
                    cloud_init="cloud-init" in capabilities,
                )
            )
        return result

    def create_server(self, spec: ServerSpec) -> Server:
        payload: dict = {
            "region": spec.location,
            "type": spec.server_type,
            "image": spec.image,
            "label": spec.name,
            "booted": True,
        }

        if spec.ssh_public_keys:
            payload["authorized_keys"] = spec.ssh_public_keys
            root_password = None
        else:
            # Linode requires at least one auth method; generate a root password.
            root_password = secrets.token_urlsafe(24)
            payload["root_pass"] = root_password

        if spec.user_data:
            payload["metadata"] = {"user_data": base64.b64encode(spec.user_data.encode()).decode()}

        resp = self._client.post("/linode/instances", json=payload)
        self._raise_for_error(resp)
        data = resp.json()

        raw_ipv4 = data.get("ipv4") or []
        ipv4 = raw_ipv4[0] if raw_ipv4 else None

        raw_ipv6 = data.get("ipv6") or ""
        ipv6 = raw_ipv6.split("/")[0] if raw_ipv6 else None

        instance_id = data["id"]
        return Server(
            id=instance_id,
            name=data.get("label", spec.name),
            status=data.get("status", ""),
            ipv4=ipv4,
            ipv6=ipv6,
            action_id=instance_id,  # reuse instance id to poll status
            root_password=root_password,
        )

    def delete_server(self, server_id: int) -> None:
        resp = self._client.delete(f"/linode/instances/{server_id}")
        self._raise_for_error(resp)

    def get_action_status(self, action_id: int) -> str:
        """Poll instance status; map to the canonical "running"/"success"/"error" vocabulary."""
        resp = self._client.get(f"/linode/instances/{action_id}")
        self._raise_for_error(resp)
        status = resp.json().get("status", "")
        if status == "running":
            return "success"
        # Treat any transient state as still in-progress; let the timeout be the failure path.
        return "running"

    def validate_server_name(self, name: str) -> bool | str:
        """Linode label: 3–64 chars, alphanumeric start/end, no consecutive separators."""
        name = name.strip()
        if not name:
            return "Server name cannot be empty."
        if len(name) < 3 or len(name) > 64:
            return "Server name must be between 3 and 64 characters."
        if not name[0].isalnum() or not name[-1].isalnum():
            return "Server name must start and end with a letter or digit."
        if re.search(r"[-_.]{2,}", name):
            return "Server name must not contain consecutive hyphens, underscores, or periods."
        if not re.match(r"^[a-zA-Z0-9._-]+$", name):
            return "Server name may only contain letters, digits, hyphens, underscores, and periods."
        return True
