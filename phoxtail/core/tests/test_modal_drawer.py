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
    assert html.count('onclick="closeModal(this)"') == 3  # click outside, close button, Close
    assert "closeModal()" not in html


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
