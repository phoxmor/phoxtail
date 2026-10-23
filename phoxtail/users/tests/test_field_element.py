"""allauth's loose `field` element draws core's outlined field by hand."""

from html.parser import HTMLParser

import pytest
from django import forms
from django.template import Context, Template
from django.template.base import Origin


class _Skeleton(HTMLParser):
    """The nesting of `phx-field*` classes, and each element's attributes by class."""

    VOID = {"input", "br", "img", "hr", "meta", "link"}

    def __init__(self):
        super().__init__()
        self.stack = []
        self.tree = []
        self.attrs = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = [c for c in (attrs.get("class") or "").split() if c.startswith("phx-field")]
        if classes:
            self.tree.append((len(self.stack), " ".join(classes)))
            self.attrs[classes[0]] = attrs
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag not in self.VOID and self.stack:
            self.stack.pop()


def _skeleton(html):
    parser = _Skeleton()
    parser.feed(html)
    depths = sorted({depth for depth, _ in parser.tree})
    return [(depths.index(depth), name) for depth, name in parser.tree], parser.attrs


def _draw(source, **context):
    # allauth's element tag reads the calling template's name.
    origin = Origin("test.html", template_name="test.html")
    return Template("{% load allauth %}" + source, origin=origin).render(Context(context))


class _Form(forms.Form):
    email = forms.EmailField(label="Email")
    codes = forms.CharField(label="Codes", widget=forms.Textarea)


def _core(name, errors):
    form = _Form(data={"email": "x", "codes": ""} if errors else None)
    return Template("{% load phoxtail_core_tags %}{% field form." + name + " %}").render(Context({"form": form}))


def _element(type, errors):
    return _draw(
        '{% element field id="id_x" name="x" type=type errors=errors %}{% slot label %}X{% endslot %}{% endelement %}',
        type=type,
        errors=["Enter a valid email address."] if errors else None,
    )


@pytest.mark.parametrize(("field", "type"), [("email", "email"), ("codes", "textarea")])
@pytest.mark.parametrize("errors", [False, True])
def test_the_element_keeps_cores_skeleton(field, type, errors):
    element, _ = _skeleton(_element(type, errors))

    assert element, "phoxtail's field element was not drawn"
    assert element == _skeleton(_core(field, errors))[0]


@pytest.mark.parametrize(("field", "type"), [("email", "email"), ("codes", "textarea")])
def test_the_control_points_at_its_error_line_as_cores_does(field, type):
    for html in (_core(field, errors=True), _element(type, errors=True)):
        _, attrs = _skeleton(html)
        control, line = attrs["phx-field__control"], attrs["phx-field__supporting"]

        assert control["aria-describedby"] == line["id"]
        assert control["aria-invalid"] == "true"


def test_help_text_is_pointed_at():
    html = _draw(
        '{% element field id="id_x" type="text" %}'
        "{% slot label %}X{% endslot %}{% slot help_text %}Keep it.{% endslot %}{% endelement %}"
    )
    _, attrs = _skeleton(html)

    assert attrs["phx-field__control"]["aria-describedby"] == attrs["phx-field__supporting"]["id"] == "id_x_helptext"


def test_without_an_id_nothing_points_at_a_missing_line():
    html = _draw(
        '{% element field type="text" errors=errors %}{% slot label %}X{% endslot %}{% endelement %}',
        errors=["Wrong."],
    )
    _, attrs = _skeleton(html)

    assert "aria-describedby" not in attrs["phx-field__control"]
    assert attrs["phx-field__control"]["aria-invalid"] == "true"
    assert "id" not in attrs["phx-field__supporting"]


def test_a_textarea_shows_allauths_value():
    html = _draw(
        '{% element field id="codes" type="textarea" rows=2 readonly=True %}'
        "{% slot label %}Codes{% endslot %}{% slot value %}a1\nb2{% endslot %}{% endelement %}"
    )

    assert '<textarea class="phx-field__control"' in html
    assert ">a1\nb2</textarea>" in html
    assert 'rows="2"' in html


def test_a_checkbox_shows_and_points_at_its_help():
    html = _draw(
        '{% element field id="saved" type="checkbox" %}'
        "{% slot label %}Saved{% endslot %}{% slot help_text %}Tick it.{% endslot %}{% endelement %}"
    )

    assert 'aria-describedby="saved_helptext"' in html
    assert '<span class="phx-choice__help" id="saved_helptext">Tick it.</span>' in html


def test_a_radio_without_help_has_no_help_line():
    html = _draw('{% element field id="r" type="radio" %}{% slot label %}R{% endslot %}{% endelement %}')

    assert "phx-choice__help" not in html
    assert "aria-describedby" not in html
