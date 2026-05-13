"""Tests for the Hetzner provider using pytest-httpx for HTTP mocking."""

import pytest
from pytest_httpx import HTTPXMock

from phoxtail.cli.server.providers.base import ServerSpec
from phoxtail.cli.server.providers.hetzner import HetznerError, HetznerProvider

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

LOCATIONS_RESPONSE = {
    "locations": [
        {
            "id": 1,
            "name": "fsn1",
            "description": "Falkenstein DC Park 1",
            "city": "Falkenstein",
            "country": "DE",
            "network_zone": "eu-central",
            "latitude": 50.47612,
            "longitude": 12.370071,
        },
        {
            "id": 3,
            "name": "hel1",
            "description": "Helsinki DC Park 1",
            "city": "Helsinki",
            "country": "FI",
            "network_zone": "eu-central",
            "latitude": 60.169855,
            "longitude": 24.938379,
        },
    ],
    "meta": {
        "pagination": {
            "page": 1,
            "per_page": 50,
            "next_page": None,
            "last_page": 1,
            "total_entries": 2,
        }
    },
}

SERVER_TYPES_RESPONSE = {
    "server_types": [
        {
            "id": 22,
            "name": "cpx22",
            "description": "CPX22",
            "cores": 2,
            "memory": 4.0,
            "disk": 80,
            "cpu_type": "shared",
            "architecture": "x86",
            "deprecated": False,
            "prices": [
                {
                    "location": "hel1",
                    "price_hourly": {"net": "0.0084", "gross": "0.0100"},
                    "price_monthly": {"net": "5.0000", "gross": "5.9500"},
                }
            ],
            "locations": [
                {
                    "id": 3,
                    "name": "hel1",
                    "description": "Helsinki DC Park 1",
                    "city": "Helsinki",
                    "country": "FI",
                    "network_zone": "eu-central",
                }
            ],
        },
        {
            "id": 32,
            "name": "cpx32",
            "description": "CPX32",
            "cores": 4,
            "memory": 8.0,
            "disk": 160,
            "cpu_type": "shared",
            "architecture": "x86",
            "deprecated": False,
            "prices": [
                {
                    "location": "hel1",
                    "price_hourly": {"net": "0.0143", "gross": "0.0170"},
                    "price_monthly": {"net": "8.8200", "gross": "10.4958"},
                }
            ],
            "locations": [
                {
                    "id": 3,
                    "name": "hel1",
                    "description": "Helsinki DC Park 1",
                    "city": "Helsinki",
                    "country": "FI",
                    "network_zone": "eu-central",
                }
            ],
        },
    ],
    "meta": {
        "pagination": {
            "page": 1,
            "per_page": 50,
            "next_page": None,
            "last_page": 1,
            "total_entries": 2,
        }
    },
}

IMAGES_RESPONSE = {
    "images": [
        {
            "id": 167547755,
            "type": "system",
            "status": "available",
            "name": "ubuntu-24.04",
            "description": "Ubuntu 24.04",
            "image_size": None,
            "disk_size": 5,
            "created": "2024-04-25T12:00:00+00:00",
            "os_flavor": "ubuntu",
            "os_version": "24.04",
            "architecture": "x86",
            "deprecated": None,
            "labels": {},
        },
        {
            "id": 114690387,
            "type": "system",
            "status": "available",
            "name": "ubuntu-22.04",
            "description": "Ubuntu 22.04",
            "image_size": None,
            "disk_size": 5,
            "created": "2022-04-21T12:00:00+00:00",
            "os_flavor": "ubuntu",
            "os_version": "22.04",
            "architecture": "x86",
            "deprecated": None,
            "labels": {},
        },
    ],
    "meta": {
        "pagination": {
            "page": 1,
            "per_page": 50,
            "next_page": None,
            "last_page": 1,
            "total_entries": 2,
        }
    },
}

SSH_KEYS_RESPONSE = {
    "ssh_keys": [
        {
            "id": 1001,
            "name": "my-laptop",
            "fingerprint": "b7:2f:30:a0:2f:6c:58:6c:21:04:58:61:ba:06:3b:2f",
            "public_key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKeyForPhoxtail u@l",
            "labels": {},
            "created": "2024-01-01T00:00:00+00:00",
        }
    ],
    "meta": {
        "pagination": {
            "page": 1,
            "per_page": 50,
            "next_page": None,
            "last_page": 1,
            "total_entries": 1,
        }
    },
}

CREATE_SERVER_RESPONSE = {
    "server": {
        "id": 99999,
        "name": "my-project",
        "status": "initializing",
        "created": "2024-01-01T00:00:00+00:00",
        "public_net": {
            "ipv4": {"ip": "1.2.3.4", "blocked": False},
            "ipv6": {"ip": "2a01::/64", "blocked": False},
        },
        "server_type": {"id": 22, "name": "cpx22"},
        "labels": {},
        "volume_ids": [],
    },
    "action": {
        "id": 77777,
        "command": "create_server",
        "status": "running",
        "progress": 0,
        "started": "2024-01-01T00:00:00+00:00",
        "completed": None,
        "error": None,
    },
    "next_actions": [],
    "root_password": None,
}

ACTION_SUCCESS_RESPONSE = {
    "action": {
        "id": 77777,
        "command": "create_server",
        "status": "success",
        "progress": 100,
        "started": "2024-01-01T00:00:00+00:00",
        "completed": "2024-01-01T00:01:00+00:00",
        "error": None,
    }
}


@pytest.fixture
def provider():
    return HetznerProvider(token="test-token-abc123")


# ---------------------------------------------------------------------------
# list_locations
# ---------------------------------------------------------------------------


class TestListLocations:
    def test_returns_all_locations(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.hetzner.cloud/v1/locations?page=1&per_page=50",
            json=LOCATIONS_RESPONSE,
        )
        locations = provider.list_locations()
        assert len(locations) == 2
        assert locations[0].name == "fsn1"
        assert locations[0].city == "Falkenstein"
        assert locations[0].network_zone == "eu-central"

    def test_raises_on_auth_error(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.hetzner.cloud/v1/locations?page=1&per_page=50",
            status_code=401,
            json={"error": {"code": "unauthorized", "message": "Invalid token"}},
        )
        with pytest.raises(HetznerError) as exc_info:
            provider.list_locations()
        assert exc_info.value.code == "unauthorized"


# ---------------------------------------------------------------------------
# list_server_types
# ---------------------------------------------------------------------------


class TestListServerTypes:
    def test_returns_types_for_location(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.hetzner.cloud/v1/server_types?page=1&per_page=50",
            json=SERVER_TYPES_RESPONSE,
        )
        types = provider.list_server_types(location="hel1")
        assert len(types) == 2
        assert types[0].name == "cpx22"
        assert types[0].cores == 2
        assert types[0].price_monthly == "5.9500"

    def test_filters_out_deprecated(self, provider, httpx_mock: HTTPXMock):
        response = {
            "server_types": [
                {**SERVER_TYPES_RESPONSE["server_types"][0], "deprecated": True},
                SERVER_TYPES_RESPONSE["server_types"][1],
            ],
            "meta": SERVER_TYPES_RESPONSE["meta"],
        }
        httpx_mock.add_response(
            url="https://api.hetzner.cloud/v1/server_types?page=1&per_page=50",
            json=response,
        )
        types = provider.list_server_types()
        assert len(types) == 1
        assert types[0].name == "cpx32"

    def test_filters_by_location_availability(self, provider, httpx_mock: HTTPXMock):
        # cpx32 has no hel1 in its locations list
        response = {
            "server_types": [
                SERVER_TYPES_RESPONSE["server_types"][0],  # has hel1
                {
                    **SERVER_TYPES_RESPONSE["server_types"][1],
                    "locations": [
                        {
                            "id": 1,
                            "name": "fsn1",
                            "description": "Falkenstein",
                            "city": "Falkenstein",
                            "country": "DE",
                            "network_zone": "eu-central",
                        }
                    ],
                },
            ],
            "meta": SERVER_TYPES_RESPONSE["meta"],
        }
        httpx_mock.add_response(
            url="https://api.hetzner.cloud/v1/server_types?page=1&per_page=50",
            json=response,
        )
        types = provider.list_server_types(location="hel1")
        assert len(types) == 1
        assert types[0].name == "cpx22"


# ---------------------------------------------------------------------------
# list_ssh_keys
# ---------------------------------------------------------------------------


class TestListSSHKeys:
    def test_returns_ssh_keys(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.hetzner.cloud/v1/ssh_keys?page=1&per_page=50",
            json=SSH_KEYS_RESPONSE,
        )
        keys = provider.list_ssh_keys()
        assert len(keys) == 1
        assert keys[0].name == "my-laptop"
        assert keys[0].id == 1001
        assert keys[0].public_key.startswith("ssh-ed25519")

    def test_returns_empty_list_when_no_keys(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.hetzner.cloud/v1/ssh_keys?page=1&per_page=50",
            json={
                "ssh_keys": [],
                "meta": {
                    "pagination": {
                        "page": 1,
                        "per_page": 50,
                        "next_page": None,
                        "last_page": 1,
                        "total_entries": 0,
                    }
                },
            },
        )
        keys = provider.list_ssh_keys()
        assert keys == []


# ---------------------------------------------------------------------------
# list_images
# ---------------------------------------------------------------------------


class TestListImages:
    def test_returns_system_images(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.hetzner.cloud/v1/images?page=1&per_page=50&type=system&architecture=x86&status=available",
            json=IMAGES_RESPONSE,
        )
        images = provider.list_images(architecture="x86")
        assert len(images) == 2
        assert images[0].name == "ubuntu-24.04"
        assert images[0].os_flavor == "ubuntu"
        assert images[0].os_version == "24.04"


# ---------------------------------------------------------------------------
# create_server
# ---------------------------------------------------------------------------


class TestCreateServer:
    def test_creates_server_and_returns_ip(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.hetzner.cloud/v1/servers",
            method="POST",
            json=CREATE_SERVER_RESPONSE,
            status_code=201,
        )
        spec = ServerSpec(
            name="my-project",
            server_type="cpx22",
            image="ubuntu-24.04",
            location="hel1",
            ssh_key_ids=[1001],
        )
        server = provider.create_server(spec)
        assert server.id == 99999
        assert server.ipv4 == "1.2.3.4"
        assert server.action_id == 77777

    def test_raises_on_invalid_server_type(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.hetzner.cloud/v1/servers",
            method="POST",
            status_code=422,
            json={"error": {"code": "invalid_input", "message": "server_type is invalid"}},
        )
        spec = ServerSpec(
            name="test",
            server_type="nonexistent",
            image="ubuntu-24.04",
            location="hel1",
        )
        with pytest.raises(HetznerError) as exc_info:
            provider.create_server(spec)
        assert exc_info.value.code == "invalid_input"


# ---------------------------------------------------------------------------
# get_action_status
# ---------------------------------------------------------------------------


class TestGetActionStatus:
    def test_returns_success_status(self, provider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.hetzner.cloud/v1/actions/77777",
            json=ACTION_SUCCESS_RESPONSE,
        )
        status = provider.get_action_status(77777)
        assert status == "success"
