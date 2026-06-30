"""Hetzner Cloud provider — thin httpx wrapper over the v1 REST API."""

import httpx

from .base import Image, Location, Provider, ProviderError, Server, ServerSpec, ServerType, SSHKey

BASE_URL = "https://api.hetzner.cloud/v1"


class HetznerError(ProviderError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, f"Hetzner API [{code}]: {message}")


class HetznerProvider(Provider):
    display_name = "Hetzner Cloud"
    currency = "€"
    token_env_var = "HETZNER_TOKEN"
    architectures = ("x86", "arm")

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
                err = resp.json().get("error", {})
                raise HetznerError(
                    err.get("code", str(resp.status_code)),
                    err.get("message", resp.text),
                )
            except (ValueError, KeyError):
                resp.raise_for_status()

    def _get_all(self, path: str, key: str, **params: object) -> list[dict]:
        """Fetch all pages for a list endpoint, returning the merged item list."""
        results: list[dict] = []
        page = 1
        while True:
            resp = self._client.get(path, params={"page": page, "per_page": 50, **params})
            self._raise_for_error(resp)
            data = resp.json()
            results.extend(data[key])
            if data.get("meta", {}).get("pagination", {}).get("next_page") is None:
                break
            page += 1
        return results

    # ------------------------------------------------------------------
    # Provider interface
    # ------------------------------------------------------------------

    def list_locations(self) -> list[Location]:
        items = self._get_all("/locations", "locations")
        return [
            Location(
                id=item["id"],
                name=item["name"],
                description=item["description"],
                city=item["city"],
                country=item["country"],
                network_zone=item["network_zone"],
            )
            for item in items
        ]

    def list_server_types(self, *, location: str | None = None) -> list[ServerType]:
        items = self._get_all("/server_types", "server_types")

        # Remove deprecated types
        items = [item for item in items if not item.get("deprecated")]

        # Filter to types available at the requested location
        if location:
            items = [item for item in items if any(loc["name"] == location for loc in item.get("locations", []))]

        result = []
        for item in items:
            prices = item.get("prices", [])
            # Prefer price entry for the requested location; fall back to first
            price = next(
                (p for p in prices if location and p["location"] == location),
                prices[0] if prices else None,
            )
            result.append(
                ServerType(
                    id=item["id"],
                    name=item["name"],
                    description=item["description"],
                    cores=item["cores"],
                    memory=float(item["memory"]),
                    disk=int(item["disk"]),
                    cpu_type=item["cpu_type"],
                    architecture=item["architecture"],
                    price_hourly=price["price_hourly"]["gross"] if price else "0",
                    price_monthly=price["price_monthly"]["gross"] if price else "0",
                )
            )
        return result

    def list_ssh_keys(self) -> list[SSHKey]:
        items = self._get_all("/ssh_keys", "ssh_keys")
        return [
            SSHKey(
                id=item["id"],
                name=item["name"],
                fingerprint=item["fingerprint"],
                public_key=item.get("public_key", ""),
            )
            for item in items
        ]

    def list_images(self, *, architecture: str = "x86") -> list[Image]:
        items = self._get_all(
            "/images",
            "images",
            type="system",
            architecture=architecture,
            status="available",
        )
        return [
            Image(
                id=item["id"],
                name=item["name"] or "",
                description=item["description"],
                os_flavor=item["os_flavor"],
                os_version=item.get("os_version"),
                architecture=item["architecture"],
            )
            for item in items
            if item.get("name")  # system images always have names; skip any that don't
        ]

    def create_server(self, spec: ServerSpec) -> Server:
        payload: dict = {
            "name": spec.name,
            "server_type": spec.server_type,
            "image": spec.image,
            "location": spec.location,
            "start_after_create": True,
        }
        if spec.ssh_key_ids:
            payload["ssh_keys"] = spec.ssh_key_ids
        if spec.user_data:
            payload["user_data"] = spec.user_data

        resp = self._client.post("/servers", json=payload)
        self._raise_for_error(resp)
        data = resp.json()
        srv = data["server"]
        action = data.get("action", {})
        return Server(
            id=srv["id"],
            name=srv["name"],
            status=srv["status"],
            ipv4=srv["public_net"]["ipv4"]["ip"] if srv["public_net"].get("ipv4") else None,
            ipv6=srv["public_net"]["ipv6"]["ip"] if srv["public_net"].get("ipv6") else None,
            action_id=action.get("id"),
        )

    def delete_server(self, server_id: int) -> None:
        resp = self._client.delete(f"/servers/{server_id}")
        self._raise_for_error(resp)

    def get_action_status(self, action_id: int) -> str:
        """Return "running", "success", or "error"."""
        resp = self._client.get(f"/actions/{action_id}")
        self._raise_for_error(resp)
        return resp.json()["action"]["status"]
