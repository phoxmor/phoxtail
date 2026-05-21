from django.urls import path

from phoxtail.agent import views

app_name = "phoxtail_agent"

urlpatterns = [
    path("chat-history/", views.chat_history, name="chat_history"),
    path("media-picker/", views.media_picker, name="media_picker"),
    path("collection-picker/", views.collection_picker, name="collection_picker"),
    path("model-picker/", views.model_picker_panel, name="model_picker_panel"),
    path(
        "screenshot/<int:page_id>/<str:block_uuid>/",
        views.render_page_for_screenshot,
        name="render_page_for_screenshot",
    ),
    path(
        "screenshot/<int:page_id>/",
        views.render_page_for_viewport_screenshot,
        name="render_page_for_viewport_screenshot",
    ),
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
