"""
How an htmx action answers once it went through.

Usually 204 with three client events (changed): the change (what shows the
thing listens for it and redraws itself), closeModal (modal.js closes the
modal the request came from) and showToast (messages.js says what was done).
Actions know no page ids.

A change is announced under its model's name (change_event), the same for
the action that sends it and the page part that listens for it
({% changed_event %}): one rule, no names of an app's own.
"""

from django.apps import apps
from django.conf import settings
from django.db.models import Model
from django.http import HttpResponse
from django_htmx.http import trigger_client_event


def change_event(model):
    """
    The client event a change to *model* is announced under: its Django label,
    lower case, then ":changed" (phoxtail_tokens.accesstoken:changed). *model*
    is a model class or instance, its label ("phoxtail_tokens.AccessToken"),
    or "AUTH_USER_MODEL" for whichever user model the project uses. A label
    that names no installed model raises LookupError.
    """
    if isinstance(model, str):
        model = apps.get_model(settings.AUTH_USER_MODEL if model == "AUTH_USER_MODEL" else model)
    elif isinstance(model, Model):
        model = type(model)
    return f"{model._meta.label_lower}:changed"


def changed(model, message, toast_type="success", response=None):
    """
    Answer an action that went through: 204, a change to *model* announced
    (change_event), the modal the action came from closed, and *message* as a
    toast of *toast_type*. A *response* of the action's own carries the events
    instead of the 204.
    """
    if response is None:
        response = HttpResponse(status=204)
    trigger_client_event(response, change_event(model))
    trigger_client_event(response, "closeModal")
    return trigger_client_event(response, "showToast", {"message": message, "type": toast_type})
