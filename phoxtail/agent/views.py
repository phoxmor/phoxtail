"""Browser-facing HTML views for the Phoxtail Agent (chatbot).

Session-authenticated, superuser-only — same gate as the design bar.
"""

from __future__ import annotations

from functools import wraps

from django.http import HttpResponseForbidden
from django.shortcuts import render
from wagtail.search.backends import get_search_backend

from phoxtail.agent.models import Conversation


def _require_superuser(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_superuser:
            return HttpResponseForbidden("Superuser access required.")
        return view_func(request, *args, **kwargs)

    return wrapper


@_require_superuser
def chat_history(request):
    query = request.GET.get("q", "").strip()
    qs = Conversation.objects.filter(user=request.user)
    if query:
        s = get_search_backend()
        qs = s.autocomplete(query, qs)[:30]
    else:
        qs = qs.exclude(title="")[:30]

    template = "phoxtail_agent/chat_history.html"
    if request.htmx and request.htmx.target == "phoxtail-chat-history-list":
        template = "phoxtail_agent/partials/chat_history_list.html"

    return render(request, template, {"conversations": qs, "query": query})
