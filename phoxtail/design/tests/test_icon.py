import logging
import re
from pathlib import Path

from django.template import engines

import phoxtail


def render(source):
    return engines["django"].from_string("{% load phoxtail_design_tags %}" + source).render({})


def test_a_known_icon_renders_its_svg():
    assert 'id="icon-graph-5"' in render('{% icon "graph_5" %}')


def test_an_unknown_icon_renders_nothing_and_warns(caplog):
    with caplog.at_level(logging.WARNING, logger="phoxtail.design.templatetags.phoxtail_design_tags"):
        html = render('<p>{% icon "no_such_icon" %}Account</p>')

    assert html == "<p>Account</p>"
    assert "Icon 'no_such_icon' not found" in caplog.text


def test_every_icon_named_in_a_template_or_seeded_variant_exists():
    root = Path(phoxtail.__file__).parent
    have = {path.stem for path in (root / "core/templates/phoxtail_core/svgs").glob("*.html")}
    # Seeded variants live in Python strings, where the quotes may be escaped.
    sources = [*root.glob("**/*.html"), *root.glob("project_template/**/*.py")]
    named = {
        (str(path.relative_to(root)), name)
        for path in sources
        for name in re.findall(r"""\{%\s*icon\s+\\?["']([^"'\\]+)""", path.read_text())
    }

    assert named
    assert sorted((path, name) for path, name in named if name not in have) == []
