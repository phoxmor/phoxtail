"""The HTTP door introduces itself to strangers.

A caller with no credential is refused ``401``; the door already did that.
What these pin is the second half: the refusal says where a credential
comes from, and the place it points at actually answers. A pointer to a
404 would look finished and send every remote client nowhere.
"""

import asyncio
import json

import pytest

from phoxtail.cli.mcp import front_door
from phoxtail.cli.utils.config import load_config

SITE = "https://example.com"


@pytest.fixture
def production_project(tmp_path, monkeypatch):
    toml = tmp_path / "phoxtail.toml"
    toml.write_text('[project]\nname = "t"\n\n[studio]\napi_url = "http://t.localhost"\n')
    monkeypatch.chdir(tmp_path)
    # What the mcp container sees in production: the public domain from
    # .env, and the in-network address of Django, which must not be
    # repeated to the internet.
    monkeypatch.setenv("DOMAIN", "example.com")
    monkeypatch.setenv("PHOXTAIL_API_URL", "http://web")
    load_config.cache_clear()
    yield
    load_config.cache_clear()


def _get(app, url, headers=None):
    import httpx2

    async def run():
        async with app.router.lifespan_context(app):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url=url) as client:
                return await client.get(url, headers=headers or {})

    return asyncio.run(run())


class TestTheDoorNamesTheOffice:
    def test_the_authorization_server_is_the_public_site(self, production_project):
        auth, _ = front_door()
        assert [str(u) for u in auth.authorization_servers] == [f"{SITE}/"]
        assert str(auth.base_url) == "https://mcp.example.com/"

    def test_the_verifier_is_inside_and_the_server_is_untouched(self, production_project):
        """The wrapper adds a pointer around the same verifier; it does not
        replace how a credential is checked. And building it must not
        touch the server: over stdio there is no HTTP door to introduce,
        and the assignment belongs to the --http path alone."""
        from phoxtail.mcp import mcp_server
        from phoxtail.mcp.authorization import WhoamiVerifier

        before = mcp_server.auth
        auth, _ = front_door()
        assert isinstance(auth.token_verifier, WhoamiVerifier)
        assert mcp_server.auth is before

    def test_the_public_host_is_answered(self, production_project):
        _, allowed_hosts = front_door()
        assert "mcp.example.com" in allowed_hosts
        assert "mcp.t.localhost" in allowed_hosts

    def test_the_challenge_points_at_a_document_that_answers(self, production_project):
        """The two halves together, over a real ASGI app."""
        from fastmcp import FastMCP

        auth, allowed_hosts = front_door()
        server = FastMCP("door-probe", auth=auth)
        app = server.http_app(
            path="/mcp",
            allowed_hosts=allowed_hosts,
            allowed_origins=[],
            host_origin_protection=True,
        )

        refused = _get(app, "https://mcp.example.com/mcp")
        assert refused.status_code == 401
        challenge = refused.headers["www-authenticate"]
        pointer = "https://mcp.example.com/.well-known/oauth-protected-resource/mcp"
        assert challenge.startswith("Bearer")
        assert f'resource_metadata="{pointer}"' in challenge

        served = _get(app, pointer)
        assert served.status_code == 200
        document = json.loads(served.text)
        assert document["resource"] == "https://mcp.example.com/mcp"
        # The trailing slash is the SDK's serialisation of a root URL and
        # is what a client will hold as the issuer it expects, compared as
        # a plain string against what the authorization server publishes.
        # Whoever configures that server must publish exactly this.
        assert document["authorization_servers"] == ["https://example.com/"]
