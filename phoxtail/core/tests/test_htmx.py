import json

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.http import HttpResponse
from django.template import engines
from django.test import override_settings

from phoxtail.core.htmx import MODAL_EXIT, change_event, changed, replace_modal


def test_a_change_is_named_after_its_models_label():
    assert change_event(Group) == "auth.group:changed"
    assert change_event(Group(name="x")) == "auth.group:changed"
    assert change_event("auth.Group") == "auth.group:changed"


def test_the_user_model_is_whichever_the_project_uses():
    assert change_event("AUTH_USER_MODEL") == change_event(get_user_model())
    with override_settings(AUTH_USER_MODEL="auth.Group"):
        assert change_event("AUTH_USER_MODEL") == "auth.group:changed"


def test_a_label_that_names_no_model_fails_loudly():
    with pytest.raises(LookupError):
        change_event("auth.Grup")


def test_the_listener_hears_what_the_sender_announces():
    source = "{% load phoxtail_core_tags %}{% changed_event 'auth.Group' %}|{% changed_event 'AUTH_USER_MODEL' %}"
    heard = engines["django"].from_string(source).render({}).split("|")

    assert heard == [change_event(Group), change_event(get_user_model())]


def test_changed_answers_204_with_the_change_close_and_toast():
    response = changed(Group, "Saved.")

    assert response.status_code == 204
    assert json.loads(response["HX-Trigger"]) == {
        "auth.group:changed": {},
        "closeModal": {},
        "showToast": {"message": "Saved.", "type": "success"},
    }


def test_changed_carries_the_events_on_a_response_of_its_own():
    response = changed(Group, "Gone.", "error", response=HttpResponse("<p>below</p>"))

    assert response.status_code == 200
    assert response.content == b"<p>below</p>"
    assert json.loads(response["HX-Trigger"])["showToast"] == {"message": "Gone.", "type": "error"}


def _static(path):
    from pathlib import Path

    from django.contrib.staticfiles import finders

    return Path(finders.find(f"phoxtail_core/{path}")).read_text()


def test_replace_modal_answers_in_the_modal_the_request_came_from_after_its_exit():
    response = replace_modal(HttpResponse("<p>next</p>"))

    assert response["HX-Retarget"] == "closest [data-modal-content]"
    assert response["HX-Reswap"] == f"innerHTML swap:{MODAL_EXIT}"


def test_the_exit_lasts_as_long_as_the_drawers_motion():
    import re

    seconds = re.search(r"--phx-drawer-duration:\s*([\d.]+)s;", _static("css/main.css")).group(1)
    assert MODAL_EXIT == f"{round(float(seconds) * 1000)}ms"


def test_each_side_leaves_with_its_own_motion_while_the_swap_is_held():
    css = _static("css/modal.css")
    for side, motion in (("right", "drawerSlideRightOut"), ("left", "drawerSlideLeftOut"), ("center", "fadeOut")):
        selector = f'[data-modal-content].htmx-swapping [data-modal-side="{side}"] .phoxtail-modal-drawer'
        assert f"{selector} {{\n    animation: {motion}" in css


def test_both_levels_mark_their_content():
    from django.template.loader import render_to_string

    for shell in ("phoxtail_core/modal.html", "phoxtail_core/modal_level_1.html"):
        assert "data-modal-content" in render_to_string(shell)
