"""What ``phoxtail env create production`` writes for the hosts Django admits.

The public name is the obvious one. The other is ``web``: the MCP server
asks the API who a caller is at ``http://web``, one service-name hop
inside the compose network, and Django refuses a Host it was not told
about — a 400 the door would report as its authority being unreachable.
"""

from unittest.mock import patch

from phoxtail.cli import env


def _production_env(tmp_path, *, wildcard):
    answers = iter(["example.com", "ops@example.com"])
    with (
        patch.object(env, "_prompt_common_config", return_value={}),
        patch.object(env.Prompt, "ask", side_effect=lambda *a, **k: next(answers)),
        patch.object(env.Confirm, "ask", side_effect=lambda q, **k: wildcard if "wildcard" in q else False),
        patch.object(env, "render_template", return_value="") as rendered,
    ):
        env._prompt_production_env(tmp_path / ".env")
    return rendered.call_args.args[1]["allowed_hosts"]


class TestTheApiAdmitsTheDoor:
    def test_web_is_an_allowed_host(self, tmp_path):
        assert _production_env(tmp_path, wildcard=False) == "example.com,web"

    def test_with_wildcard_subdomains_too(self, tmp_path):
        assert _production_env(tmp_path, wildcard=True) == ".example.com,web"
