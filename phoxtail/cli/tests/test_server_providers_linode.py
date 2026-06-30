"""Tests for the Linode provider using pytest-httpx for HTTP mocking."""

import base64

import pytest
from pytest_httpx import HTTPXMock

from phoxtail.cli.server.providers.base import ServerSpec
from phoxtail.cli.server.providers.linode import LinodeError, LinodeProvider

# ---------------------------------------------------------------------------
# Fixtures & shared response data
# ---------------------------------------------------------------------------

REGIONS_RESPONSE = {
    "data": [
        {
            "id": "de-fra-2",
            "label": "Frankfurt 2, DE",
            "country": "de",
            "capabilities": ["Linodes", "Metadata", "NodeBalancers"],
            "status": "ok",
            "site_type": "core",
        },
        {
            "id": "nl-ams",
            "label": "Amsterdam, NL",
            "country": "nl",
            "capabilities": ["Linodes", "Metadata", "NodeBalancers"],
            "status": "ok",
            "site_type": "core",
        },
        # Legacy region — no Metadata capability; must be filtered out
        {
            "id": "eu-central",
            "label": "Frankfurt, DE",
            "country": "de",
            "capabilities": ["Linodes", "NodeBalancers"],
            "status": "ok",
            "site_type": "core",
        },
    ],
    "page": 1,
    "pages": 1,
    "results": 3,
}

TYPES_RESPONSE = {
    "data": [
        {
            "id": "g6-nanode-1",
            "label": "Nanode 1GB",
            "vcpus": 1,
            "memory": 1024,
            "disk": 25600,
            "class": "nanode",
            "price": {"hourly": 0.0075, "monthly": 5.0},
            "region_prices": [
                {"id": "id-cgk", "hourly": 0.009, "monthly": 6.0},
            ],
        },
        {
            "id": "g6-standard-2",
            "label": "Linode 4GB",
            "vcpus": 2,
            "memory": 4096,
            "disk": 81920,
            "class": "standard",
            "price": {"hourly": 0.03, "monthly": 20.0},
            "region_prices": [],
        },
        {
            "id": "g6-dedicated-2",
            "label": "Dedicated 4GB",
            "vcpus": 2,
            "memory": 4096,
            "disk": 81920,
            "class": "dedicated",
            "price": {"hourly": 0.045, "monthly": 30.0},
            "region_prices": [],
        },
    ],
    "page": 1,
    "pages": 1,
    "results": 3,
}

IMAGES_RESPONSE = {
    "data": [
        {
            "id": "linode/ubuntu24.04",
            "label": "Ubuntu 24.04 LTS",
            "vendor": "Ubuntu",
            "status": "available",
            "is_public": True,
            "deprecated": False,
            "capabilities": ["cloud-init"],
        },
        {
            "id": "linode/debian12",
            "label": "Debian 12",
            "vendor": "Debian",
            "status": "available",
            "is_public": True,
            "deprecated": False,
            "capabilities": ["cloud-init"],
        },
        # Slackware has no cloud-init
        {
            "id": "linode/slackware15.0",
            "label": "Slackware 15.0",
            "vendor": "Slackware",
            "status": "available",
            "is_public": True,
            "deprecated": False,
            "capabilities": [],
        },
        # Private image — must be filtered out
        {
            "id": "private/12345",
            "label": "My Custom Image",
            "vendor": "Ubuntu",
            "status": "available",
            "is_public": False,
            "deprecated": False,
            "capabilities": ["cloud-init"],
        },
    ],
    "page": 1,
    "pages": 1,
    "results": 4,
}

SSH_KEYS_RESPONSE = {
    "data": [
        {
            "id": 1001,
            "label": "my-laptop",
            "ssh_key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKeyForPhoxtail u@l",
            "created": "2024-01-01T00:00:00",
        }
    ],
    "page": 1,
    "pages": 1,
    "results": 1,
}

CREATE_INSTANCE_RESPONSE = {
    "id": 12345678,
    "label": "my-project",
    "status": "provisioning",
    "ipv4": ["45.33.32.156"],
    "ipv6": "2600:3c01::f03c:91ff:fe86:b37a/128",
    "region": "de-fra-2",
    "type": "g6-nanode-1",
    "image": "linode/ubuntu24.04",
}

INSTANCE_RUNNING_RESPONSE = {
    "id": 12345678,
    "label": "my-project",
    "status": "running",
    "ipv4": ["45.33.32.156"],
    "ipv6": "2600:3c01::f03c:91ff:fe86:b37a/128",
}


@pytest.fixture
def provider():
    return LinodeProvider(token="test-token-abc123")


# ---------------------------------------------------------------------------
# list_locations
# ---------------------------------------------------------------------------


class TestListLocations:
    def test_returns_metadata_capable_regions(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.linode.com/v4/regions?page=1&page_size=100",
            json=REGIONS_RESPONSE,
        )
        locations = provider.list_locations()
        assert len(locations) == 2
        ids = {loc.name for loc in locations}
        assert "de-fra-2" in ids
        assert "nl-ams" in ids

    def test_filters_out_regions_without_metadata(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.linode.com/v4/regions?page=1&page_size=100",
            json=REGIONS_RESPONSE,
        )
        locations = provider.list_locations()
        names = {loc.name for loc in locations}
        assert "eu-central" not in names

    def test_parses_city_and_country_from_label(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.linode.com/v4/regions?page=1&page_size=100",
            json=REGIONS_RESPONSE,
        )
        locations = provider.list_locations()
        fra = next(loc for loc in locations if loc.name == "de-fra-2")
        assert fra.city == "Frankfurt 2"
        assert fra.country == "DE"

    def test_raises_on_auth_error(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.linode.com/v4/regions?page=1&page_size=100",
            status_code=401,
            json={"errors": [{"reason": "Invalid Token", "field": "token"}]},
        )
        with pytest.raises(LinodeError) as exc_info:
            provider.list_locations()
        assert exc_info.value.code == "token"


# ---------------------------------------------------------------------------
# list_server_types
# ---------------------------------------------------------------------------


class TestListServerTypes:
    def test_maps_class_to_cpu_type(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.linode.com/v4/linode/types?page=1&page_size=100",
            json=TYPES_RESPONSE,
        )
        types = provider.list_server_types()
        nanode = next(t for t in types if t.name == "g6-nanode-1")
        dedicated = next(t for t in types if t.name == "g6-dedicated-2")
        assert nanode.cpu_type == "shared"
        assert dedicated.cpu_type == "dedicated"

    def test_converts_memory_and_disk_to_gb(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.linode.com/v4/linode/types?page=1&page_size=100",
            json=TYPES_RESPONSE,
        )
        types = provider.list_server_types()
        nanode = next(t for t in types if t.name == "g6-nanode-1")
        assert nanode.memory == 1.0  # 1024 MB → 1 GB
        assert nanode.disk == 25  # 25600 MB → 25 GB

    def test_uses_region_price_when_available(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.linode.com/v4/linode/types?page=1&page_size=100",
            json=TYPES_RESPONSE,
        )
        types = provider.list_server_types(location="id-cgk")
        nanode = next(t for t in types if t.name == "g6-nanode-1")
        assert float(nanode.price_monthly) == 6.0

    def test_falls_back_to_base_price(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.linode.com/v4/linode/types?page=1&page_size=100",
            json=TYPES_RESPONSE,
        )
        types = provider.list_server_types(location="de-fra-2")
        nanode = next(t for t in types if t.name == "g6-nanode-1")
        assert float(nanode.price_monthly) == 5.0

    def test_stamps_x86_architecture(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.linode.com/v4/linode/types?page=1&page_size=100",
            json=TYPES_RESPONSE,
        )
        types = provider.list_server_types()
        assert all(t.architecture == "x86" for t in types)


# ---------------------------------------------------------------------------
# list_ssh_keys
# ---------------------------------------------------------------------------


class TestListSSHKeys:
    def test_returns_ssh_keys_with_computed_fingerprint(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.linode.com/v4/profile/sshkeys?page=1&page_size=100",
            json=SSH_KEYS_RESPONSE,
        )
        keys = provider.list_ssh_keys()
        assert len(keys) == 1
        assert keys[0].name == "my-laptop"
        assert keys[0].id == 1001
        assert keys[0].public_key.startswith("ssh-ed25519")
        # Fingerprint should be a non-empty colon-separated hex string
        assert ":" in keys[0].fingerprint

    def test_returns_empty_list_when_no_keys(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.linode.com/v4/profile/sshkeys?page=1&page_size=100",
            json={"data": [], "page": 1, "pages": 1, "results": 0},
        )
        keys = provider.list_ssh_keys()
        assert keys == []


# ---------------------------------------------------------------------------
# list_images
# ---------------------------------------------------------------------------


class TestListImages:
    def test_returns_public_available_images(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.linode.com/v4/images?page=1&page_size=100",
            json=IMAGES_RESPONSE,
        )
        images = provider.list_images()
        names = {img.name for img in images}
        assert "linode/ubuntu24.04" in names
        assert "linode/debian12" in names

    def test_filters_out_private_images(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.linode.com/v4/images?page=1&page_size=100",
            json=IMAGES_RESPONSE,
        )
        images = provider.list_images()
        assert all(img.name != "private/12345" for img in images)

    def test_sets_cloud_init_from_capabilities(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.linode.com/v4/images?page=1&page_size=100",
            json=IMAGES_RESPONSE,
        )
        images = provider.list_images()
        ubuntu = next(img for img in images if img.name == "linode/ubuntu24.04")
        slackware = next(img for img in images if img.name == "linode/slackware15.0")
        assert ubuntu.cloud_init is True
        assert slackware.cloud_init is False

    def test_maps_vendor_to_os_flavor_lowercase(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.linode.com/v4/images?page=1&page_size=100",
            json=IMAGES_RESPONSE,
        )
        images = provider.list_images()
        ubuntu = next(img for img in images if img.name == "linode/ubuntu24.04")
        assert ubuntu.os_flavor == "ubuntu"
        assert ubuntu.os_version == "24.04"

    def test_parses_debian_single_version(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.linode.com/v4/images?page=1&page_size=100",
            json=IMAGES_RESPONSE,
        )
        images = provider.list_images()
        debian = next(img for img in images if img.name == "linode/debian12")
        assert debian.os_version == "12"


# ---------------------------------------------------------------------------
# create_server
# ---------------------------------------------------------------------------


class TestCreateServer:
    def test_creates_server_with_ssh_keys(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.linode.com/v4/linode/instances",
            method="POST",
            json=CREATE_INSTANCE_RESPONSE,
            status_code=200,
        )
        spec = ServerSpec(
            name="my-project",
            server_type="g6-nanode-1",
            image="linode/ubuntu24.04",
            location="de-fra-2",
            ssh_public_keys=["ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKey u@l"],
        )
        server = provider.create_server(spec)
        assert server.id == 12345678
        assert server.ipv4 == "45.33.32.156"
        # action_id is the instance id for polling
        assert server.action_id == 12345678
        # No root_password when SSH keys are provided
        assert server.root_password is None

    def test_strips_ipv6_prefix(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.linode.com/v4/linode/instances",
            method="POST",
            json=CREATE_INSTANCE_RESPONSE,
            status_code=200,
        )
        spec = ServerSpec(
            name="my-project",
            server_type="g6-nanode-1",
            image="linode/ubuntu24.04",
            location="de-fra-2",
            ssh_public_keys=["ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKey u@l"],
        )
        server = provider.create_server(spec)
        assert "/" not in (server.ipv6 or "")

    def test_base64_encodes_user_data(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.linode.com/v4/linode/instances",
            method="POST",
            json=CREATE_INSTANCE_RESPONSE,
            status_code=200,
        )
        spec = ServerSpec(
            name="my-project",
            server_type="g6-nanode-1",
            image="linode/ubuntu24.04",
            location="de-fra-2",
            ssh_public_keys=["ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKey u@l"],
            user_data="#cloud-config\npackages:\n  - git\n",
        )
        provider.create_server(spec)
        request = httpx_mock.get_requests()[0]
        import json

        body = json.loads(request.content)
        encoded = body["metadata"]["user_data"]
        decoded = base64.b64decode(encoded).decode()
        assert decoded == "#cloud-config\npackages:\n  - git\n"

    def test_generates_root_pass_when_no_ssh_keys(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.linode.com/v4/linode/instances",
            method="POST",
            json=CREATE_INSTANCE_RESPONSE,
            status_code=200,
        )
        spec = ServerSpec(
            name="my-project",
            server_type="g6-nanode-1",
            image="linode/ubuntu24.04",
            location="de-fra-2",
        )
        server = provider.create_server(spec)
        assert server.root_password is not None
        assert len(server.root_password) > 0

    def test_raises_on_invalid_region(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.linode.com/v4/linode/instances",
            method="POST",
            status_code=400,
            json={"errors": [{"field": "region", "reason": "Region is not valid."}]},
        )
        spec = ServerSpec(
            name="test",
            server_type="g6-nanode-1",
            image="linode/ubuntu24.04",
            location="nonexistent",
            ssh_public_keys=["ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKey u@l"],
        )
        with pytest.raises(LinodeError) as exc_info:
            provider.create_server(spec)
        assert exc_info.value.code == "region"


# ---------------------------------------------------------------------------
# get_action_status
# ---------------------------------------------------------------------------


class TestGetActionStatus:
    def test_running_status_maps_to_success(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.linode.com/v4/linode/instances/12345678",
            json=INSTANCE_RUNNING_RESPONSE,
        )
        status = provider.get_action_status(12345678)
        assert status == "success"

    def test_provisioning_status_maps_to_running(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.linode.com/v4/linode/instances/12345678",
            json={**INSTANCE_RUNNING_RESPONSE, "status": "provisioning"},
        )
        status = provider.get_action_status(12345678)
        assert status == "running"

    def test_booting_status_maps_to_running(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.linode.com/v4/linode/instances/12345678",
            json={**INSTANCE_RUNNING_RESPONSE, "status": "booting"},
        )
        status = provider.get_action_status(12345678)
        assert status == "running"


# ---------------------------------------------------------------------------
# validate_server_name
# ---------------------------------------------------------------------------


class TestValidateServerName:
    def test_valid_name(self, provider):
        assert provider.validate_server_name("my-project") is True

    def test_rejects_invalid_characters(self, provider):
        result = provider.validate_server_name("my@project")
        assert result is not True

    def test_rejects_too_short(self, provider):
        result = provider.validate_server_name("ab")
        assert result is not True

    def test_rejects_leading_hyphen(self, provider):
        result = provider.validate_server_name("-myproject")
        assert result is not True

    def test_rejects_consecutive_hyphens(self, provider):
        result = provider.validate_server_name("my--project")
        assert result is not True
