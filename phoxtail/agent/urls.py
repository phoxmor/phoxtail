from django.urls import path

from phoxtail.agent import views

app_name = "phoxtail_agent"

urlpatterns = [
    path("chat-history/", views.chat_history, name="chat_history"),
    path(
        "htmx-partials/blocks/<int:page_id>/<str:block_uuid>/render/",
        views.render_block_fragment,
        name="render_block_fragment",
    ),
    path(
        "htmx-partials/body/<int:page_id>/render/",
        views.render_body_fragment,
        name="render_body_fragment",
    ),
]
