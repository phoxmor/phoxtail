from pathlib import Path

from django.template import engines


def render(source, **context):
    return engines["django"].from_string(source).render(context)


def test_modal_drawer_fills_title_body_and_actions_after_close():
    html = render(
        '{% extends "phoxtail_core/modal_drawer.html" %}'
        "{% block title %}Yoga{% endblock %}"
        "{% block body %}<p>Details</p>{% endblock %}"
        '{% block actions %}<button id="act">Book</button>{% endblock %}'
    )
    assert 'class="phoxtail-drawer__title">Yoga</h2>' in html
    assert "<p>Details</p>" in html
    assert html.index("Close</span>") < html.index('id="act"')


def test_modal_drawer_leaves_the_dialog_to_its_modal():
    """The modal around it (modal.html, modal_level_1.html) is the dialog,
    named by the drawer's title in modal.js: the drawer is not a second one."""
    html = render('{% extends "phoxtail_core/modal_drawer.html" %}{% block title %}Yoga{% endblock %}')
    assert 'role="dialog"' not in html
    assert "aria-modal" not in html
    # The title takes its id from its modal (modal.js), so stacked drawers never share one.
    assert '<h2 class="phoxtail-drawer__title">Yoga</h2>' in html


def test_modal_drawer_closes_the_modal_it_is_in_at_either_level():
    html = render('{% extends "phoxtail_core/modal_drawer.html" %}')
    assert html.count('onclick="closeModal(this)"') == 2  # close button, Close
    assert html.count('onclick="dismissModal(this, event)"') == 1  # click outside
    assert "closeModal()" not in html


def test_a_click_inside_the_drawer_reaches_the_page():
    """Nothing in the drawer stops a click: the page's own listeners (an
    overflow menu's, a field's) hear it, and the overlay ignores it."""
    html = render('{% extends "phoxtail_core/modal_drawer.html" %}')
    assert "stopPropagation" not in html


def test_only_a_click_pressed_and_released_on_the_overlay_dismisses():
    script = _script("modal.js")
    assert "if (event && (event.target !== el || _pressedOn !== el || _releasedOn !== el)) return;" in script
    assert "document.addEventListener('pointerdown', function(e) {\n    _pressedOn = e.target;\n}, true);" in script
    assert "document.addEventListener('pointerup', function(e) {\n    _releasedOn = e.target;\n}, true);" in script


def test_modal_drawer_sits_on_the_right_and_closes_any_way_by_default():
    html = render('{% extends "phoxtail_core/modal_drawer.html" %}')
    assert 'data-modal-side="right"' in html
    assert 'data-modal-dismiss=""' in html
    assert "data-modal-animation" not in html  # core decides the motion from the side


def test_modal_drawer_side_and_dismiss_are_the_callers():
    html = render(
        '{% extends "phoxtail_core/modal_drawer.html" %}'
        "{% block side %}center{% endblock %}{% block dismiss %}button{% endblock %}"
    )
    assert 'data-modal-side="center"' in html
    assert 'data-modal-dismiss="button"' in html


def test_modal_drawer_header_can_be_replaced_whole():
    html = render(
        '{% extends "phoxtail_core/modal_drawer.html" %}{% block header %}<span id="own">Mine</span>{% endblock %}'
    )
    assert 'id="own"' in html
    assert "phoxtail-drawer__title-row" not in html


def test_modal_drawer_footer_can_be_replaced_whole():
    html = render(
        '{% extends "phoxtail_core/modal_drawer.html" %}{% block footer %}<span id="own">Mine</span>{% endblock %}'
    )
    assert 'id="own"' in html
    assert "Close</span>" not in html


def test_modal_drawer_width_defaults_to_480px_and_can_be_set():
    assert "--phoxtail-drawer-width: 480px;" in render('{% extends "phoxtail_core/modal_drawer.html" %}')
    assert "--phoxtail-drawer-width: 640px;" in render(
        '{% extends "phoxtail_core/modal_drawer.html" %}{% block width %}640px{% endblock %}'
    )


def _script(name):
    from django.contrib.staticfiles import finders

    return Path(finders.find(f"phoxtail_core/js/{name}")).read_text()


def test_a_toast_closes_no_modal():
    """Closing is the modal's: an action sends closeModal beside showToast."""
    assert "closeModal" not in _script("messages.js")


def test_the_close_event_closes_the_modal_of_the_element_that_sent_it():
    script = _script("modal.js")

    assert "addEventListener('closeModal', function(event) {\n        window.closeModal(event.target);" in script


def test_a_click_outside_or_escape_spares_a_modal_closed_only_by_its_buttons():
    """All three ways a modal is dismissed go through dismissModal, which
    leaves one whose content says data-modal-dismiss="button"."""
    from django.template.loader import render_to_string

    script = _script("modal.js")
    assert "querySelector('[data-modal-dismiss=\"button\"]')" in script
    assert "window.dismissModal(top)" in script  # Escape
    for shell in ("phoxtail_core/modal.html", "phoxtail_core/modal_level_1.html"):
        assert 'onclick="dismissModal(this)"' in render_to_string(shell)  # the backdrop


def test_escape_closes_one_modal_and_only_when_nothing_inside_took_it():
    """Heard on the window as the key goes down, after the page's own
    listeners: a held key closes one level, and an Escape that closed a
    popover, a modal dialog or anything that took it leaves the drawer."""
    script = _script("modal.js")
    assert "window.addEventListener('keydown', function(e) {" in script
    assert "addEventListener('keyup'" not in script
    assert "e.defaultPrevented || e.repeat || e.isComposing" in script
    assert '[popover]:not([popover="manual"]):popover-open, dialog:modal' in script


def test_core_menus_take_the_escape_they_use():
    """A field's open panel and the language menu close on Escape and take
    it, so the drawer around them stays open."""
    for name in ("fields.js", "language_menu.js"):
        script = _script(name)
        escape = script[script.index("Escape') {") :]
        assert "event.preventDefault();" in escape[: escape.index("});")]


def test_the_side_decides_the_motion():
    assert "{right: 'slide-right', left: 'slide-left', center: 'fade'}" in _script("modal.js")
