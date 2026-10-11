"""account/messages.html draws each message as a toast that messages.js and
messages.css know by its classes."""

import pytest
from django.contrib.messages import constants
from django.contrib.messages.storage.base import Message
from django.template.loader import render_to_string
from django.utils import translation


def _render(*messages):
    with translation.override("en"):
        return render_to_string("account/messages.html", {"messages": list(messages)})


@pytest.mark.parametrize(
    ("level", "tone", "label"),
    [
        (constants.ERROR, "error", "Error"),
        (constants.SUCCESS, "success", "Success"),
        (constants.WARNING, "warning", "Warning"),
        (constants.INFO, "info", "Info"),
    ],
)
def test_a_message_is_a_toast_in_its_tone(level, tone, label):
    html = _render(Message(level, "Saved."))

    assert 'id="messages-container" class="phx-toast-container"' in html
    assert f"phx-toast phx-popover phx-toast--hidden phx-toast--{tone}" in html
    assert label in html
    assert '<p class="phx-toast__text">Saved.</p>' in html


def test_the_close_button_is_a_named_button():
    html = _render(Message(constants.ERROR, "Refused."))

    assert 'type="button"' in html
    assert 'class="phoxtail-close-btn phoxtail-close-btn--xsmall"' in html
    assert 'aria-label="Dismiss"' in html


def test_no_messages_draw_nothing():
    assert _render().strip() == ""
