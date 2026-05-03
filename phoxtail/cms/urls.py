from django.urls import path

from .views import render_block_fragment, render_body_fragment

app_name = "phoxtail_cms"

urlpatterns = [
    path(
        "htmx-partials/blocks/<int:page_id>/<str:block_uuid>/render/",
        render_block_fragment,
        name="render_block_fragment",
    ),
    path(
        "htmx-partials/body/<int:page_id>/render/",
        render_body_fragment,
        name="render_body_fragment",
    ),
]
