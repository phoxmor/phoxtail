from django.urls import path

from .views import get_core_modal_level_1_with_htmx, get_core_modal_with_htmx

app_name = "phoxtail_core"

urlpatterns = [
    path("htmx-partials/core-modal/", get_core_modal_with_htmx, name="modal"),
    path(
        "htmx-partials/core-modal-level-1/",
        get_core_modal_level_1_with_htmx,
        name="modal_level_1",
    ),
]
