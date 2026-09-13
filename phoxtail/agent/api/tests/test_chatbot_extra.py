"""What the two chat endpoints answer when the chatbot extra is absent.

``phoxtail.agent`` is installed in every project, so its endpoints are served
everywhere. Two of them need ``pydantic_ai``, which arrives only with the
``chatbot`` extra. Without the guard they answer with an unhandled
``ModuleNotFoundError``, which reaches the caller as a 500 and tells whoever
reads the log nothing about what to do.

503 is the accurate answer: the request is fine and the service cannot perform
it, which is a property of the deployment rather than of the caller. The detail
names the extra, so an administrator can act on it.

The rest of the app — providers, artifacts, settings — is plain model editing
and is expected to keep working, which is the other half of what these tests
pin. See ``phoxtail/agent/tests/test_optional_dependency.py`` for the import
side of the same constraint.
"""

from __future__ import annotations

import pytest

PATHS = ["/agent/v1/chat/stream/", "/agent/v1/conversations/some-uuid/"]


@pytest.fixture
def without_the_chatbot_extra(monkeypatch):
    """Answer "not installed" to the endpoint's probe, and only to it.

    ``importlib.util`` is patched rather than a name on the chat module,
    because the endpoint imports ``find_spec`` per call.
    """
    import importlib.util

    real_find_spec = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util,
        "find_spec",
        lambda name, package=None: None if name == "pydantic_ai" else real_find_spec(name, package),
    )


def _call(client, path):
    return client.post(path, json={"message": "hello"}) if "stream" in path else client.get(path)


@pytest.mark.parametrize("path", PATHS)
def test_it_is_503_when_the_extra_is_absent(client, without_the_chatbot_extra, path):
    response = _call(client, path)
    assert response.status_code == 503


@pytest.mark.parametrize("path", PATHS)
def test_the_refusal_names_the_extra(client, without_the_chatbot_extra, path):
    """A 503 that does not say what is missing is a dead end for whoever reads it."""
    assert "chatbot" in _call(client, path).json()["detail"]


@pytest.mark.parametrize("path", PATHS)
def test_it_is_not_503_when_the_extra_is_present(client, path):
    """The guard must be the only thing it changes: every other refusal stands.

    Both paths still fail here — no message, no such conversation — and that is
    the point. What matters is that they are answered by the endpoint's own
    rules rather than turned away at the door.
    """
    assert _call(client, path).status_code != 503
